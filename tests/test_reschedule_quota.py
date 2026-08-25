"""日枠が切れているあいだ、`videos.update` が通らないことを**言葉で**返すこと。

## なぜ要るか（2026-08-17 05:2x に実際に叩いた）

前の回（8/17 04:1x）が `unschedule.py` に**手元の控えで読みを代える**道を入れ、
「日枠が切れている13時間、作り直して差し替える道が丸ごと閉じていた」のを
**開けた**と書きました。**開いたのは読みの側だけです。**

    videos.insert（投稿・1600単位）   **日枠が切れていても通る**（8/17 03:5x に実測）
    videos.update（差し替え・50単位）  **403 quotaExceeded**（この回に実測）

**安いほうが先に閉じます。** そして書き込みは、控えでは代えられません ——
控えは手元にありますが、**YouTube 側の状態を変えられるのは口だけ**だからです。

直す前は、ここが**生の traceback** で落ちていました。読んだ側には
「道具が壊れている」ようにしか見えず、**実際は「16:00 以降にやり直せばよい」だけ**です。
`docs/JOURNAL.md` はこの2本を**7回**運んでいます。

**故障注入は両向きに掛けています** —— 権限が無いほうの 403 を
「待てば直る」と読んでしまうと、**待っても直らないものを待ち続ける**ので。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import reschedule  # noqa: E402


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "Forbidden"


def _http_error(status: int, body: str) -> HttpError:
    return HttpError(_Resp(status), body.encode("utf-8"), uri="https://example/x")


QUOTA_BODY = ('{"error":{"code":403,"errors":[{"reason":"quotaExceeded",'
              '"domain":"youtube.quota","message":"exceeded your quota"}]}}')
FORBIDDEN_BODY = ('{"error":{"code":403,"errors":[{"reason":"forbidden",'
                  '"message":"The caller does not have permission"}]}}')


# ------------------------------------------------ 見分けるところ（両向き）

def test_日枠切れの403は日枠だと分かる():
    assert reschedule._is_quota(_http_error(403, QUOTA_BODY))


def test_権限が無い403を日枠と読まないこと():
    """**待っても直りません。** 日枠と読むと、直らないものを待ち続けます。"""
    assert not reschedule._is_quota(_http_error(403, FORBIDDEN_BODY))


def test_403以外は日枠ではない():
    assert not reschedule._is_quota(_http_error(404, QUOTA_BODY))
    assert not reschedule._is_quota(ValueError("quotaExceeded"))


# ------------------------------------------------ 落ち方（言葉で返すこと）

class _Videos:
    """`list` は通り、`update` だけが落ちる口。**この回の実物と同じ形です。**"""

    def __init__(self, update_exc: Exception | None) -> None:
        self._update_exc = update_exc
        self.updated: list[dict] = []

    def list(self, **kw):
        return _Call({"items": [{"status": {"privacyStatus": "private",
                                            "publishAt": "2026-09-06T07:00:00Z",
                                            "uploadStatus": "processed"}}]})

    def update(self, **kw):
        if self._update_exc is not None:
            raise self._update_exc
        self.updated.append(kw)
        return _Call({})


class _Call:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _Svc:
    def __init__(self, videos: _Videos) -> None:
        self._videos = videos

    def videos(self):
        return self._videos


def test_日枠切れなら_やり直す時刻まで言って止まる():
    svc = _Svc(_Videos(_http_error(403, QUOTA_BODY)))

    with pytest.raises(SystemExit) as got:
        reschedule._update(svc, "vid1", None)

    msg = str(got.value)
    assert "16:00" in msg, "**いつやり直せばよいか**が出ていない"
    assert "insert" in msg, "insert とは違う、という肝心の区別が出ていない"
    assert "まだ作り直さないこと" in msg, (
        "§5『外す → 作る → 上げ直す』の順は、ここで止まれば1本も捨てないためにある。"
        "そう言わないと、読んだ側が先に作ってしまう")


def test_権限が無い403は握りつぶさず素通しすること():
    """**直し方が違います。** 日枠の文言を出すと、直らないものを待たせます。"""
    svc = _Svc(_Videos(_http_error(403, FORBIDDEN_BODY)))

    with pytest.raises(HttpError):
        reschedule._update(svc, "vid1", None)


def test_通る回は素通り_余計な例外を足していないこと():
    videos = _Videos(None)

    reschedule._update(_Svc(videos), "vid1", None)

    assert len(videos.updated) == 1
    status = videos.updated[0]["body"]["status"]
    assert status["privacyStatus"] == "private"
    assert "publishAt" not in status, "予約を外したのに publishAt が残っている"
    assert "uploadStatus" not in status, "読み取り専用の欄を送り返している"
