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


def test_渡せば控えのstatusで予約を外せる():
    import reschedule
    from src import uploader

    svc = _Boom()
    reschedule._update(svc, "vid1", None, fallback_status=uploader.base_status())

    body = svc.updated["body"]
    assert body["id"] == "vid1"
    assert body["status"]["privacyStatus"] == "private"
    assert "publishAt" not in body["status"], "予約が落ちていません"


def test_渡したstatusでも予約を置き直せる():
    import reschedule
    from src import uploader

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
