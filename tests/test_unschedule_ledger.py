"""`unschedule.py` が、口の落ちた回に**手元の控え**で代えられること。

**この検査が要る理由は、通した側ではなく止めた側にあります。**
控えは再生数を持っていないので、素直に代えると「公開済みを private にする」
事故が通ります。だから通してよいのは
**「控えの予約時刻がいまより先」＝ まだ一度も公開されていない**と
示せた行だけで、それ以外は全部止まること。**故障注入は両向きに掛けています。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import unschedule  # noqa: E402


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat().replace("+00:00", "Z")


@pytest.fixture
def rows(monkeypatch):
    """`dupes.ledger_rows()` の返りを差し替える。"""
    box: list[dict] = []

    from src import dupes
    monkeypatch.setattr(dupes, "ledger_rows", lambda *a, **k: box)
    return box


def test_未来の予約なら控えで代えられる(rows):
    at = _iso(timedelta(days=20))
    rows.append({"id": "vid1", "topic": "s-x", "title": "題", "at": at})

    state = unschedule._ledger_state("vid1")

    assert state is not None
    assert state["publish_at"] == at
    assert state["title"] == "題"


def test_控えに行が無ければ代えない(rows):
    rows.append({"id": "other", "title": "題", "at": _iso(timedelta(days=20))})

    assert unschedule._ledger_state("vid1") is None


def test_予約時刻が過去なら代えない(rows):
    """**公開済みかもしれません。** 控えには再生数が無いので、示せない側は止める。"""
    rows.append({"id": "vid1", "title": "題", "at": _iso(timedelta(days=-1))})

    assert unschedule._ledger_state("vid1") is None


def test_境目の余白のうちは代えない(rows):
    """ちょうど境目の行を「まだ先」と読まないこと（`LEDGER_MARGIN`）。"""
    rows.append({"id": "vid1", "title": "題",
                 "at": _iso(unschedule.LEDGER_MARGIN - timedelta(minutes=5))})

    assert unschedule._ledger_state("vid1") is None

    # 余白を超えていれば通る（同じ行で向きだけ変える）
    rows[0]["at"] = _iso(unschedule.LEDGER_MARGIN + timedelta(minutes=5))
    assert unschedule._ledger_state("vid1") is not None


def test_予約時刻が読めない行は代えない(rows):
    rows.append({"id": "vid1", "title": "題", "at": "きのう"})

    assert unschedule._ledger_state("vid1") is None


def test_予約時刻の欄が無い行は代えない(rows):
    rows.append({"id": "vid1", "title": "題"})

    assert unschedule._ledger_state("vid1") is None


def test_控えそのものが読めなくても落ちない(monkeypatch):
    from src import dupes

    def boom(*a, **k):
        raise OSError("控えが読めない")

    monkeypatch.setattr(dupes, "ledger_rows", boom)

    assert unschedule._ledger_state("vid1") is None


def test_タイムゾーンの無い予約時刻はUTCとして読む(rows):
    naive = (datetime.now(timezone.utc) + timedelta(days=20)).replace(
        tzinfo=None).isoformat()
    rows.append({"id": "vid1", "title": "題", "at": naive})

    assert unschedule._ledger_state("vid1") is not None


# --- 書き込みの側（`reschedule._update`）にも同じ穴がありました -------------
# 門を控えで通しても、`videos().update` は部分更新ではないので
# **書く前に現状を読みます**。そこが読めないと、門を抜けた先で落ちます。
# 8/17 に実際にそこで落ちました（門は通ったのに書き込みで 403）。


class _Boom:
    """`videos().list` が必ず落ちる service。`update` は控えておく。"""

    def __init__(self):
        self.updated = None

    def videos(self):
        return self

    def list(self, **kw):
        raise RuntimeError("403 quotaExceeded")

    def update(self, part=None, body=None):
        self.updated = {"part": part, "body": body}
        return self

    def execute(self):
        if self.updated is None:
            raise RuntimeError("403 quotaExceeded")
        return {}


def test_渡さなければこれまでどおり落ちる():
    """**既定は代えません。** 示せていない呼び側に既定値で上書きさせないため。"""
    import reschedule

    with pytest.raises(RuntimeError):
        reschedule._update(_Boom(), "vid1", None)


def _pin_quota(monkeypatch) -> None:
    """**その日の日枠の残りを、この検査に混ぜない。**（2026-08-31 に足した）

    `reschedule._update()` は書く前に `upload_cap.reserve_hold()` を読み、
    **窓の残りが計測ぶんを割っていたら `SystemExit`** を投げます
    （2026-08-28 に足った、正しい門です）。

    ところがこの2件が見ているのは **「控えの `status` で代えられるか」**で、
    日枠の残りではありません。**日枠が尽きている日には、主題と関係なく赤くなります** ——
    実測 2026-08-31（この欄を足した日・枠が尽きていた）::

        SystemExit: [reschedule] **この窓の単位は、計測のぶんを残して止めています**
                    （使った 9,400 ／ 実測の枠 9,050 ／ 残す 400）

    `docs/trigger_main.md` §4「**既知の当たりを実データの偶然に置かないこと**」の、
    この file ぶんです。**門そのものは消していません** —— 門は
    `tests/test_upload_cap*.py` が主題として持ちます（**置き場所を分けるだけ**）。

    **`_update` は撃ちません**（`svc` は差し替えた `_Boom`）。日枠は減りません。
    """
    from src import upload_cap
    monkeypatch.setattr(upload_cap, "reserve_hold", lambda *a, **k: None)
    monkeypatch.setattr(upload_cap, "move_hold", lambda *a, **k: None)


def test_渡せば控えのstatusで予約を外せる(monkeypatch):
    import reschedule
    from src import uploader

    _pin_quota(monkeypatch)
    svc = _Boom()
    reschedule._update(svc, "vid1", None, fallback_status=uploader.base_status())

    body = svc.updated["body"]
    assert body["id"] == "vid1"
    assert body["status"]["privacyStatus"] == "private"
    assert "publishAt" not in body["status"], "予約が落ちていません"


def test_渡したstatusでも予約を置き直せる(monkeypatch):
    import reschedule
    from src import uploader

    _pin_quota(monkeypatch)
    svc = _Boom()
    reschedule._update(svc, "vid1", "2026-09-06T07:00:00Z",
                       fallback_status=uploader.base_status())

    assert svc.updated["body"]["status"]["publishAt"] == "2026-09-06T07:00:00Z"


def test_base_statusは投稿のときに立てる4欄と同じ():
    """**切り出しで値が変わっていないこと。** ここがずれると巻き添えで欄が消えます。"""
    from src import uploader

    s = uploader.base_status()
    assert s == {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
                 "license": "youtube", "embeddable": True}
    assert "publishAt" not in s

    s2 = uploader.base_status({"visibility": "public", "made_for_kids": True})
    assert s2["privacyStatus"] == "public"
    assert s2["selfDeclaredMadeForKids"] is True


# --------------------------------------------------------------------------
# **外したら控えにも書き戻すこと**（2026-08-18 16:0x に、実物で10本ぶん踏んだ）
# --------------------------------------------------------------------------
# 外した本の `at` が控えに残っていると、`reschedule.py --compact` が
# **控えだけを見て割り当てを作る**ので（API 0単位で計画を出すための設計）、
# 外したばかりの本に新しい publishAt を書き戻します。
# 実測: 重複10本を外した直後の `--compact --apply` で**8本が予約に戻り**、
# うち2本は前の回から外れていた本＝**外れていたものが新たに予約に入りました。**
#
# **同じ形が2回出ています** —— 「片方だけ直す」。書き戻す口（`dupes.retime`）は
# 既にあって、`--compact` は自分の書き換えを控えへ反映していました。
# **足りなかったのは `unschedule` 側の呼び出しだけ**です。


def test_外した本は控えの予約から落ちる(tmp_path, monkeypatch):
    """`dupes.retime(id, None)` が控えの `at` を消し、`--compact` の対象から外れること。"""
    import json

    from src import config, dupes

    ledger = tmp_path / "data" / "uploaded.jsonl"
    ledger.parent.mkdir(parents=True)
    at = _iso(timedelta(days=20))
    ledger.write_text(
        json.dumps({"video_id": "vid1", "topic": "s-x", "title": "題",
                    "at": at, "uploaded_at": "2026-08-18T00:00:00"}) + "\n"
        + json.dumps({"video_id": "vid2", "topic": "s-y", "title": "題2",
                      "at": at, "uploaded_at": "2026-08-18T00:00:00"}) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)

    before = {r["id"] for r in dupes.ledger_rows() if r.get("at")}
    assert before == {"vid1", "vid2"}

    assert dupes.retime("vid1", None) is True

    after = {r["id"] for r in dupes.ledger_rows() if r.get("at")}
    assert after == {"vid2"}, "外した本が控えの予約に残っている（--compact が書き戻す）"
    # 本体の行は消さないこと（**なぜ予約が1本減ったか**を次の回が追えなくなる）
    assert {r["id"] for r in dupes.ledger_rows()} == {"vid1", "vid2"}


def test_外したあと控えへの書き戻しを呼んでいる():
    """**呼び出しそのもの**を見る。口があっても呼ばなければ同じことが起きる。"""
    src = (Path(__file__).resolve().parent.parent
           / "scripts" / "unschedule.py").read_text(encoding="utf-8")

    assert "dupes.retime(args.video_id, None)" in src, (
        "外したあと控えに書き戻していない。"
        "`reschedule.py --compact` が控えを見て予約を書き戻します")
