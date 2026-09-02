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


@pytest.fixture(autouse=True)
def _枠の番人を外す(monkeypatch):
    """**日枠の番人を、この検査ファイルのあいだだけ黙らせる。**（2026-08-31・最適化の回）

    `reschedule._update` は `videos.update` の手前で
    **`upload_cap.reserve_hold()`（実物の日枠の控えを読む番人）**に当たり、
    枠が尽きている日は `SystemExit` で落ちます。**コードは壊れていません** ——
    `data/day_quota.jsonl` が「きょうの枠は尽きた」と言っているだけです。

    **番人は本番のまま**（`scripts/reschedule.py` は1文字も変えていません）。
    外しているのは**検査が実物の可変な状態を読んでいること**のほうです。
    この検査ファイルが守っているのは番人ではないので、番人はここでは邪魔です。

    **番人そのものの検査は別に在ります** ——
    `tests/test_quota_reserve.py` ／ `test_reserve_hold_same_yardstick.py` ／
    `test_quota_ok_call_sites.py`（**`reschedule` が番人を呼ぶこと自体**を釘で留めています）。
    だからここで外しても、番人の網は1つも減りません。

    **値打ち**: 枠が尽きた日に 10件 以上が赤くなると、**赤の意味が薄れます。**
    次の回は赤を見て「またこれか」と読み、本物の壊れを同じ顔で見逃します。
    検査は「いま測れない」と「壊れている」を別の顔で言うこと。
    """
    monkeypatch.setattr(reschedule.upload_cap, "reserve_hold",
                        lambda *a, **k: None, raising=False)
    monkeypatch.setattr(reschedule.upload_cap, "move_hold",
                        lambda *a, **k: None, raising=False)

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


class _ReadFails:
    """**`list`（読み・1単位）のほうが落ちる口。** 2026-09-01 20:2x の実物と同じ形。"""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.updated: list[dict] = []

    def list(self, **kw):
        raise self._exc

    def update(self, **kw):                                   # pragma: no cover
        self.updated.append(kw)
        return _Call({})



def _today_stamp() -> str:
    """**きょう（JST）**の予約時刻を1つ作る。

    ここは 2026-09-02 まで `"2026-09-03T00:00:00Z"` を直書きしていました。
    `reschedule._update` が規則5（先の日付には置かない・
    `src.house_rule.refuse_future_publish`）の関門を持ったので、
    **直書きの「明日」は門で止まり、この検査が見たい読みの側まで届きません。**
    見たいのは `videos.list` の 403 の扱いなので、**日付は何でもよい** ——
    きょうにして、門を通してから落とします。
    """
    from datetime import datetime, timedelta, timezone
    jst = timezone(timedelta(hours=9))
    t = datetime.now(jst).replace(hour=23, minute=0, second=0, microsecond=0)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_読みの側の日枠切れも_言葉で止まること(monkeypatch):
    """**安いほうが先に閉じます。** 読み 1単位 は、書き 50単位 より先に 403 になる。

    ## なぜ足したか（2026-09-01 20:2x に実際に叩いた）

    上の `test_日枠切れなら_やり直す時刻まで言って止まる` が守っていたのは
    **`videos.update`（書き）だけ**でした。その1つ手前の
    `videos.list`（読み・1単位）には handling が無く、
    枠が尽きた窓の `--move` は **生の traceback 14行**で落ちていました。

    **traceback そのものより悪いのは、観測が残らないことです。**
    書きの側の枝はこう註記しています —— 「残さないと
    `upload_cap.day_quota()` が **open=True**（まだ押せる）と答え続け、
    **次の回が同じ 403 をもう一度 買います**」。
    読みの側には、その `note_day_quota()` がありませんでした。
    """
    seen: list[str] = []
    monkeypatch.setattr(reschedule.auth, "note_day_quota",
                        lambda exc, where: seen.append(where))
    svc = _Svc(_ReadFails(_http_error(403, QUOTA_BODY)))

    with pytest.raises(SystemExit) as got:
        reschedule._update(svc, "vid1", _today_stamp())

    msg = str(got.value)
    assert "16:00" in msg, "**いつやり直せばよいか**が出ていない"
    assert "1つも変わっていません" in msg, (
        "読みで止まった回は YouTube 側が無傷。そう言わないと、"
        "読んだ側が『途中まで動いたかもしれない』と疑って二度 撃つ")
    assert seen and seen[0].startswith("videos.list"), (
        "`note_day_quota()` を残していない —— 次の回が同じ 403 をもう一度 買う")


def test_読みの側の権限403は素通しすること(monkeypatch):
    """**待っても直りません。** 日枠の文言を出すと、直らないものを待たせます。"""
    monkeypatch.setattr(reschedule.auth, "note_day_quota",
                        lambda exc, where: None)
    svc = _Svc(_ReadFails(_http_error(403, FORBIDDEN_BODY)))

    with pytest.raises(HttpError):
        reschedule._update(svc, "vid1", _today_stamp())


def test_通る回は素通り_余計な例外を足していないこと():
    videos = _Videos(None)

    reschedule._update(_Svc(videos), "vid1", None)

    assert len(videos.updated) == 1
    status = videos.updated[0]["body"]["status"]
    assert status["privacyStatus"] == "private"
    assert "publishAt" not in status, "予約を外したのに publishAt が残っている"
    assert "uploadStatus" not in status, "読み取り専用の欄を送り返している"
