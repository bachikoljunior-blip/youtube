"""**上げた直後に、上がった snippet が台本どおりか見て、違えば入れ直すこと**（2026-09-13 00:1x・hourly・Opus）。

実測でこれを足した: 09/13 の本（`Edmce94ZVKs`・00:01 JST）は `videos.insert` に tags 8語 を渡しているのに、
上がった snippet は **tags が 1つも無い**状態で返った（題・説明欄は一致・`processingStatus` が `succeeded` に
なっても戻らない）。`yt.update_meta`（50単位）で 8語 とも入った。
直前の 2本 は同じ 1分後の `ready_checked` が `meta_drift` `[]`（`mja40GJ-GHU`・`4l3DDCLIRxg`）＝ **毎回ではない**。

`cmd_status` の突き合わせは「予約ずみの本を持つ周が status を撃ったとき」にしか走らないので、
予約して終わる回のあと 10:00 までに誰も status を撃たなければ、tags の無い本がそのまま公開される。
"""
import json

import pytest

from studio import cli, script


@pytest.fixture
def s(tmp_path, monkeypatch):
    d = {"id": "2026-09-13-x", "date": "2026-09-13", "title": "題A #Shorts", "takeaway": "t",
         "description": "説明欄A", "tags": ["付加年金", "国民年金"],
         "segments": [{"say": "あ", "show": "あ", "sub": "あ"}], "notes": "n"}
    (tmp_path / "2026-09-13-x.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(script, "SCRIPTS", tmp_path)
    return script.load("2026-09-13-x")


def _wire(monkeypatch, reads, rows):
    """`yt.readiness` が `reads` を順に返し、`update_meta` と `ledger` の呼びを `rows` に積む。"""
    seq = list(reads)

    def _readiness(vid):
        return seq.pop(0)

    monkeypatch.setattr(cli.yt, "readiness", _readiness)
    monkeypatch.setattr(cli.yt, "update_meta", lambda *a: rows.append(("update_meta", a[0])))
    monkeypatch.setattr(cli, "ledger", lambda ev, sid, **kw: rows.append((ev, sid, kw)))
    # 2回目 の前の待ち（`META_REPAIR_RETRY_WAIT`）は眠らず記録する（2026-09-15 09:2x・2回 に上げた側）
    monkeypatch.setattr(cli.time, "sleep", lambda sec: rows.append(("sleep", sec)))
    return seq


def _ok(s, tags=None):
    return {"ok": True, "title": s.title, "description": s.description,
            "tags": list(s.tags if tags is None else tags)}


def test_台本どおりなら_update_metaを撃たない(s, monkeypatch):
    rows = []
    _wire(monkeypatch, [_ok(s)], rows)
    assert cli.verify_meta("VID", s) == []
    assert rows == []


def test_tagsが空なら入れ直して台帳に残す(s, monkeypatch):
    """実測の型そのもの: 題・説明欄は一致、tags だけ空で返る。"""
    rows = []
    seq = _wire(monkeypatch, [_ok(s, tags=[]), _ok(s)], rows)
    assert cli.verify_meta("VID", s) == []
    assert not seq, "直したあとに readiness を引き直していない（直ったかを見ていない）"
    assert ("update_meta", "VID") in rows
    ev = [r for r in rows if r[0] == "meta_repaired"]
    assert ev and ev[0][1] == "2026-09-13-x"
    assert ev[0][2]["fields"] == "tags" and ev[0][2]["left"] is None


def test_tagsは並びを見ない(s, monkeypatch):
    rows = []
    _wire(monkeypatch, [_ok(s, tags=list(reversed(s.tags)))], rows)
    assert cli.verify_meta("VID", s) == []
    assert rows == []


def test_直しても残るなら_残りを返して台帳に載せる(s, monkeypatch):
    """覆る条件 (2): 直しても残る欄が出たら `yt.upload` の body の側を疑う ＝ 次の回に見えること。
    2026-09-15 09:2x から 2回 撃つ（`META_REPAIR_TRIES`）＝ readiness は 初回 ＋ 撃った回数 ぶん。"""
    rows = []
    bad = dict(_ok(s, tags=[]), description="古い説明欄")
    _wire(monkeypatch, [bad] * (1 + cli.META_REPAIR_TRIES), rows)
    assert cli.verify_meta("VID", s) == ["説明欄", "tags"]
    ev = [r for r in rows if r[0] == "meta_repaired"]
    assert ev and ev[0][2]["left"] == ["説明欄", "tags"]
    assert ev[0][2]["tries"] == cli.META_REPAIR_TRIES
    assert sum(1 for r in rows if r[0] == "update_meta") == cli.META_REPAIR_TRIES


def test_1回目で残り2回目で入る(s, monkeypatch):
    """実測の型（2026-09-15・`uc0SceBfoxQ`・`PyVf22V74Ks`・`cA-XdGquFpM`）: 1回目 の `update_meta` は通っても
    readiness に tags が残り、数分 置いた 2回目 で入る。＝ 2回目 の前に `META_REPAIR_RETRY_WAIT` 置くこと。"""
    rows = []
    _wire(monkeypatch, [_ok(s, tags=[]), _ok(s, tags=[]), _ok(s)], rows)
    assert cli.verify_meta("VID", s) == []
    assert sum(1 for r in rows if r[0] == "update_meta") == 2
    assert ("sleep", cli.META_REPAIR_RETRY_WAIT) in rows
    ev = [r for r in rows if r[0] == "meta_repaired"]
    assert ev and ev[0][2]["left"] is None and ev[0][2]["tries"] == 2


def test_再試行は1回では足りない側に置いてある():
    """陽性対照: 1 に戻すと上の検査が落ちる ＝ 定数が門を持つ（覆る条件は `cli.META_REPAIR_TRIES` の註）。"""
    assert cli.META_REPAIR_TRIES >= 2
    assert cli.META_REPAIR_RETRY_WAIT >= 60


def test_引けない本は黙って通す(s, monkeypatch):
    """`readiness` が本を見つけられない回（title None）。ここで update_meta を撃つと題を空で上書きする。"""
    rows = []
    _wire(monkeypatch, [{"ok": False, "title": None, "description": None, "tags": None}], rows)
    assert cli.verify_meta("VID", s) == []
    assert rows == []


def test_cmd_scheduleが上げたあとにこれを撃つ():
    """配線の側（この関数を誰も呼ばなければ、上の検査は全部 緑のまま効かない）。"""
    import inspect
    src = inspect.getsource(cli.cmd_schedule)
    assert "verify_meta(vid, s)" in src
    assert src.index("yt.upload") < src.index("verify_meta")
