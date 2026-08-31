"""**枠の帳面に、当たった先（本ID）を残すこと。**（2026-09-01 に踏んだ）

## 実測（`data/api_calls.jsonl`・窓 08/31）

    videos.update  **9,450単位（枠の 94%）**・189回
    そのうち `detail`（当たった先）の載っている行  **0件**（409行 とも空）

**何にいくつ使ったかは分かるのに、同じ本を何度 書いたかが分かりません。**

`src/upload_cap.RESHOOT_CAP` の註は、窓 08/27 に
「**1つの掃きが1か月 先へ置き、19分後の掃きが1か月 手前へ引き戻す**」振動を実測し、
**8,900単位（ほぼ1日ぶんの枠）**を数えています。その覆る条件には
「`by`（`caller_label`）で2つの掃きを名指しできます」と書いてありますが、
**実物の `by` は `reschedule.py:_update` の1種類だけ** ——
**名指しできるのは撃った側で、当たった先ではありません。**

## この検査が押さえていること

1. `target_of()` が **URI の query**（`thumbnails.set?videoId=…`）と
   **body の JSON**（`videos.update` は URI に本IDが出ません）の両方から引くこと
2. 引けないときは**推測しない**（空文字）
3. `note()` が空の `detail` で**欄を作らない**（「無い」と「空」を区別できる形）
4. `reshoots()` が**書き込みだけ**を数え、**1回きりの本を返さない**こと
5. `detail` の載った書き込みが1件も無い窓で、
   **「振動は無い」ではなく「まだ答えられない」と印字する**こと
   （`detail` は 2026-09-01 に足したので、それ以前の窓は空です）

**戻すにはこの検査を消すしかありません。**
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import quota_ledger  # noqa: E402

NOW = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)


def test_uri_の_query_から引く():
    uri = "https://youtube.googleapis.com/youtube/v3/thumbnails/set?videoId=ABC123"
    assert quota_ledger.target_of(uri) == "ABC123"


def test_body_から引く():
    """`videos.update` は URI に本IDが出ません（body の `id`）。"""
    uri = "https://youtube.googleapis.com/youtube/v3/videos?part=status"
    body = json.dumps({"id": "XYZ789", "status": {"privacyStatus": "private"}})
    assert quota_ledger.target_of(uri, body) == "XYZ789"


def test_引けないときは推測しない():
    uri = "https://youtube.googleapis.com/youtube/v3/channels?part=id&mine=true"
    assert quota_ledger.target_of(uri) == ""
    assert quota_ledger.target_of(uri, b"not json") == ""
    assert quota_ledger.target_of(uri, json.dumps({"snippet": {}})) == ""


def test_複数の本は切り落とさない():
    """`videos.list?id=a,b,c` は、先頭だけを採ると読む側が数を誤ります。"""
    uri = "https://youtube.googleapis.com/youtube/v3/videos?id=a,b,c&part=id"
    assert quota_ledger.target_of(uri) == "a,b,c"


def _rec(vid: str, units: int = 50, method: str = "videos.update") -> dict:
    rec = {"at": NOW.isoformat(timespec="seconds"), "api": "data",
           "method": method, "units": units, "ok": True}
    if vid:
        rec["detail"] = vid
    return rec


def test_撃ち直しは書き込みだけを数える(monkeypatch):
    monkeypatch.setattr(quota_ledger, "rows", lambda now=None: [
        _rec("A"), _rec("A"), _rec("A"),
        _rec("B"),
        _rec("C", units=1, method="videos.list"),
        _rec("C", units=1, method="videos.list"),
    ])
    out = quota_ledger.reshoots(NOW)
    assert out == [("A", 3, 150)], out          # B は1回きり／C は読み


def test_当たった先の無い窓は_無いと言わない(monkeypatch):
    """**「振動は無い」ではなく「この窓の帳面がまだ答えられない」。**"""
    monkeypatch.setattr(quota_ledger, "rows", lambda now=None: [_rec("")])
    text = "\n".join(quota_ledger.reshoot_lines(NOW))
    assert "「振動が無い」ではありません" in text


def test_1本1回の窓は_ありませんと言う(monkeypatch):
    monkeypatch.setattr(quota_ledger, "rows",
                        lambda now=None: [_rec("A"), _rec("B")])
    text = "\n".join(quota_ledger.reshoot_lines(NOW))
    assert "**ありません**" in text


def test_note_は空の欄を作らない(tmp_path, monkeypatch):
    path = tmp_path / "api_calls.jsonl"
    monkeypatch.setattr(quota_ledger.upload_cap, "_write_path", lambda name: path)
    quota_ledger.note("data", "videos.update", 50, by="x", now=NOW, detail="")
    quota_ledger.note("data", "videos.update", 50, by="x", now=NOW, detail="ABC")
    recs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert "detail" not in recs[0]
    assert recs[1]["detail"] == "ABC"


# ------------------------------------------------- 包みの側（`install()` を通す）

def test_包みが_body_の本IDを帳面へ入れること(tmp_path, monkeypatch):
    """**`videos.update` は URI に本IDが出ません。** 包みが body を見ること。"""
    from googleapiclient.http import HttpRequest               # noqa: PLC0415

    from src import config                                     # noqa: PLC0415

    monkeypatch.setattr(config, "ROOT", tmp_path, raising=False)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(HttpRequest, "execute",
                        lambda self, *a, **k: None, raising=False)
    monkeypatch.setattr(quota_ledger, "_installed", False, raising=False)
    assert quota_ledger.install() is True

    class _Req:
        uri = "https://youtube.googleapis.com/youtube/v3/videos?part=status"
        method = "PUT"
        body = json.dumps({"id": "VID999", "status": {"privacyStatus": "private"}})

    HttpRequest.execute(_Req())
    path = tmp_path / quota_ledger.LEDGER
    recs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert recs and recs[-1]["method"] == "videos.update", recs
    assert recs[-1]["detail"] == "VID999", recs
