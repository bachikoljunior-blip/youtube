"""**日枠が切れた回でも、予約の段まで進めること**（2026-08-17）。

Data API の1日枠が切れると `scheduled_publish_times()` の `channels.list` が
403 で落ちます。そこは `uploader.upload()` から素通しで呼ばれていたので、
**例外がそのまま上がって投稿ごと死んでいました。**

止まっていたのは「予約できるか」ではなく「**確かめられるか**」のほうです ——
申し送りは3回とも「枯れているのは読みだけかもしれない。`videos.insert` を
実際に叩いた回は1つも無い」と言っていて、3回とも確かめられていません。
**確かめる道そのものが、この1行で塞がっていました。**

`taken` の使い道は「その時刻が埋まっていないか」と「何日ぶん後ろへ送るか」の
2つだけで、**どちらも手元の控えで答えが出ます。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import uploader  # noqa: E402


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "quotaExceeded"


def _http_error(status: int) -> HttpError:
    return HttpError(_Resp(status), b'{"error": {"message": "quota"}}')


def test_reads_the_mouth_when_it_answers(monkeypatch):
    """口が読める回の動きは**変えていません**。"""
    monkeypatch.setattr(uploader, "scheduled_publish_times",
                        lambda _yt: {"2026-09-01T02:00:00Z"})
    assert uploader.taken_publish_times(object()) == {"2026-09-01T02:00:00Z"}


@pytest.mark.parametrize("status", [403, 429])
def test_falls_back_to_the_ledger_when_the_quota_is_out(monkeypatch, capsys, status):
    """日枠切れ（403）と叩きすぎ（429）は、**控えで代えて先へ進む。**"""
    def boom(_yt):
        raise _http_error(status)

    monkeypatch.setattr(uploader, "scheduled_publish_times", boom)
    monkeypatch.setattr(uploader, "ledger_publish_times",
                        lambda: {"2026-09-01T02:00:00Z", "2026-09-01T03:00:00Z"})
    got = uploader.taken_publish_times(object())
    assert got == {"2026-09-01T02:00:00Z", "2026-09-01T03:00:00Z"}
    assert "控え" in capsys.readouterr().out


def test_other_http_errors_still_raise(monkeypatch):
    """**握りつぶさないこと。** 認証切れ（401）を控えで代えると、嘘の予約になります。"""
    def boom(_yt):
        raise _http_error(401)

    monkeypatch.setattr(uploader, "scheduled_publish_times", boom)
    with pytest.raises(HttpError):
        uploader.taken_publish_times(object())


def test_ledger_times_are_rfc3339_strings(monkeypatch):
    """控えは `scheduled_publish_times()` と**同じ形**を返すこと（比べる相手が同じ）。"""
    from src import dupes

    monkeypatch.setattr(dupes, "ledger_rows", lambda: [
        {"id": "a", "title": "t", "at": "2026-09-01T02:00:00Z"},
        {"id": "b", "title": "t", "at": None},          # ← 予約なし。落とす
    ])
    assert uploader.ledger_publish_times() == {"2026-09-01T02:00:00Z"}


def test_upload_uses_the_falling_back_reader():
    """**`upload()` が呼ぶ先が、素通しのほうに戻っていないこと。**

    ここが戻ると、日枠切れの回はまた投稿ごと死にます。
    症状は「予約の段で落ちた」だけなので、**検査が無いと気づけません。**
    """
    src = (ROOT / "src" / "uploader.py").read_text(encoding="utf-8")
    body = src.split("def upload(", 1)[1]
    assert "taken=taken_publish_times(youtube)" in body
    assert "taken=scheduled_publish_times(youtube)" not in body
