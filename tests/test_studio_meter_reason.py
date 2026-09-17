"""**403 の `reason` を、字のまま残す。**（2026-09-17 15:0x・optimizer・Fable 5.1・ultracode）

## 踏んだ当のもの（実測・`data/studio/ledger.jsonl` 09/16 の窓）

    16:49:51  `channel`（`channels.list`）**通った**
    19:01:08  `status` **403**
    21:14:44  `channel` **通った**   ← **403 の 2時間13分 あと**
    21:17:47  `watermark` **403**

**日枠は単調です** —— 尽きたものが同じ窓の中で戻ることはありません。
＝ 19:01 の 403 は「日枠 10,000 を使い切った」ではない側が在り得るのに、
**うちの口は 403 を全部 `quota_exceeded` と書いていました。**

そして `data/batch_runs.jsonl`（2026-08-24）には、実物の別の形が残っていました:
`Quota exceeded for quota metric 'Search Queries' and limit 'Search Queries per day'`
＝ **`reason: rateLimitExceeded`・HTTP 429**。**この口は metric ごとに別の枠を持ちます。**

## この検査が固定するもの

    1. `googleapiclient` の失敗から `reason` と `message` の字が取れる
    2. 取れない形（中身が無い・JSON でない）でも**例外を出さない**（数えるために本番を落とさない）
    3. `line()` が、その窓の `reason` を並べる
    4. **`reason` を持たない古い行は数えない**（＝ 陽性対照）

**覆る条件**: `reason` が 2窓 続けて `quotaExceeded` だけなら、この列は役目を終えます。
"""
from __future__ import annotations

import studio.meter as meter

SINCE = "2026-09-17T16:00:00+09:00"


class _Err(Exception):
    def __init__(self, content):
        self.content = content


def test_reasonの字が取れる():
    e = _Err(b'{"error":{"code":403,"message":"quota gone",'
             b'"errors":[{"reason":"quotaExceeded","domain":"youtube.quota"}]}}')
    assert meter.reason_of(e) == ("quotaExceeded", "quota gone")


def test_短い窓の絞りは別の字で出る():
    """**これが本体です。** 日枠と絞りが同じ字で出たら、割れません。"""
    e = _Err(b'{"error":{"code":403,"message":"Rate Limit Exceeded",'
             b'"errors":[{"reason":"rateLimitExceeded"}]}}')
    assert meter.reason_of(e)[0] == "rateLimitExceeded"


def test_読めない形でも落ちない():
    assert meter.reason_of(_Err(None)) == ("", "")
    assert meter.reason_of(_Err(b"<html>500</html>")) == ("", "")
    assert meter.reason_of(object()) == ("", "")


def test_lineがreasonを並べる():
    rows = [
        {"at": "2026-09-17T16:01:00+09:00", "api": "youtube", "method": "channels.list",
         "units": 1, "ok": False, "status": 403, "reason": "quotaExceeded"},
        {"at": "2026-09-17T16:02:00+09:00", "api": "youtube", "method": "videos.list",
         "units": 1, "ok": False, "status": 403, "reason": "rateLimitExceeded"},
    ]
    out = meter.line(SINCE, 10_000, rows)
    assert "quotaExceeded" in out and "rateLimitExceeded" in out
    assert meter.reasons(SINCE, rows) == [("quotaExceeded", 1), ("rateLimitExceeded", 1)]


def test_reasonを持たない古い行は数えない():
    """**陽性対照**: この回より前の行は `reason` を持ちません。空の字で数を作らないこと。"""
    rows = [{"at": "2026-09-17T16:01:00+09:00", "api": "youtube", "method": "channels.list",
             "units": 1, "ok": False, "status": 403}]
    assert meter.reasons(SINCE, rows) == []
    assert "失敗の `reason`" not in (meter.line(SINCE, 10_000, rows) or "")


def test_通った口はreasonに数えない():
    """**陽性対照**: `ok` の行に `reason` が付いていても、失敗の数には入れないこと。"""
    rows = [{"at": "2026-09-17T16:01:00+09:00", "api": "youtube", "method": "channels.list",
             "units": 1, "ok": True, "reason": "quotaExceeded"}]
    assert meter.reasons(SINCE, rows) == []
