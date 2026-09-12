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
    """覆る条件 (2): 直しても残る欄が出たら `yt.upload` の body の側を疑う ＝ 次の回に見えること。"""
    rows = []
    bad = dict(_ok(s, tags=[]), description="古い説明欄")
    _wire(monkeypatch, [bad, bad], rows)
    assert cli.verify_meta("VID", s) == ["説明欄", "tags"]
    ev = [r for r in rows if r[0] == "meta_repaired"]
    assert ev and ev[0][2]["left"] == ["説明欄", "tags"]


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
