"""同じニッチの他人を数える口（`studio/peers.py`）。

2026-09-15 21:0x・optimizer・Fable 5.1（ultracode）。固定 2（期限内にできるか → できる以外なら やり方を疑え）で
疑った先: **7周 続けて「できない」と答えてきたが、その外挿には比べる相手が 1つ も無かった**。
理由と覆る条件は `studio/peers.py` の冒頭・JOURNAL 2026-09-15 21:0x。

**陽性対照**（撃って落とした）: `FAST_SUBS_PER_DAY` を 0 にすると `test_遅い相手は選ばない` が落ち、
`YOUNG_DAYS` を 100000 にすると `test_古い相手は選ばない` が落ちる。
"""
import datetime as dt

import pytest

from studio import peers

JST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 9, 15, 21, 0, tzinfo=JST)


def _ch(cid, subs, days, title="x"):
    created = (NOW - dt.timedelta(days=days)).isoformat()
    return {"id": cid, "title": title, "created": created, "subs": subs, "views": 0, "videos": 0}


def test_登録_日は開設からの割り算():
    r = peers.rank([_ch("UC1", 4400, 44)], now=NOW)[0]
    assert r["age_days"] == 44
    assert r["subs_per_day"] == pytest.approx(100.0)


def test_遅い相手は選ばない():
    # 門 FAST_SUBS_PER_DAY（60人/日）の下は落ちる。0 にすると この検査が落ちる（陽性対照）
    keep = peers.young_fast([_ch("UC1", 4400, 44), _ch("UC2", 100, 44)])
    assert [c["id"] for c in keep] == ["UC1"]


def test_古い相手は選ばない():
    # 齢 400日 以上 は落ちる。YOUNG_DAYS を大きくすると この検査が落ちる（陽性対照）
    keep = peers.young_fast([_ch("UC1", 4400, 44), _ch("UC2", 900000, 3000)])
    assert [c["id"] for c in keep] == ["UC1"]


def test_尺を秒に直す():
    assert peers.iso_secs("PT36M40S") == 2200
    assert peers.iso_secs("PT1H2M3S") == 3723
    assert peers.iso_secs("PT59S") == 59
    assert peers.iso_secs("") == 0            # 欄が無いのは 0秒 ではなく「読めない」——呼ぶ側が長短を決める


def test_形は長短を分けて数える():
    items = [{"dur": "PT27M", "views": 1000, "likes": 10, "comments": 1},
             {"dur": "PT58S", "views": 100, "likes": 0, "comments": 0},
             {"dur": "PT20M", "views": 500, "likes": 5, "comments": 0}]
    s = peers.shape(items)
    assert s["long"] == 2 and s["short"] == 1
    assert s["views_median"] == 500 and s["views_max"] == 1000
    assert s["like_rate"] == pytest.approx(100 * 15 / 1600)


def test_台帳が新しければ撃たない():
    row = {"at": (NOW - dt.timedelta(hours=1)).isoformat()}
    assert peers.fresh_enough(row, now=NOW) is True
    old = {"at": (NOW - dt.timedelta(hours=peers.PEERS_MIN_H + 1)).isoformat()}
    assert peers.fresh_enough(old, now=NOW) is False
    assert peers.fresh_enough(None, now=NOW) is False


class _FakeSvc:
    """`channels().list()` / `playlistItems().list()` / `videos().list()` だけの偽物。"""

    def __init__(self):
        self.units = 0

    def channels(self):
        return self

    def playlistItems(self):
        return self

    def videos(self):
        return self

    def list(self, **kw):
        self.units += 1
        self.kw = kw
        return self

    def execute(self):
        kw = self.kw
        if "mine" in kw:
            return {"items": []}
        if kw.get("part") == "snippet,statistics":
            return {"items": [{"id": "UC1", "snippet": {"title": "速い", "publishedAt": (NOW - dt.timedelta(days=44)).isoformat()},
                               "statistics": {"subscriberCount": "5000", "viewCount": "900000", "videoCount": "40"}},
                              {"id": "UC2", "snippet": {"title": "遅い", "publishedAt": (NOW - dt.timedelta(days=44)).isoformat()},
                               "statistics": {"subscriberCount": "10", "viewCount": "100", "videoCount": "5"}}]}
        if "playlistId" in kw:
            return {"items": [{"contentDetails": {"videoId": "v1"}}]}
        if kw.get("part") == "contentDetails":
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        return {"items": [{"id": "v1", "snippet": {"title": "t", "publishedAt": "2026-08-05T00:00:00Z"},
                           "contentDetails": {"duration": "PT27M"},
                           "statistics": {"viewCount": "1000", "likeCount": "10", "commentCount": "1"}}]}


def test_撃つのは門を通った相手のぶんだけ():
    svc = _FakeSvc()
    row = peers.pull(svc, ["UC1", "UC2"], now=NOW)
    assert row["scanned"] == 2
    assert [c["id"] for c in row["channels"]] == ["UC1"]      # 遅い UC2 のぶんは 1単位も撃たない
    assert row["units"] == 4                                  # channels 1 + contentDetails 1 + playlistItems 1 + videos 1
    assert row["channels"][0]["shape"]["secs_median"] == 1620


def test_印字は数を並べるだけ_判定しない():
    row = {"at": NOW.isoformat(), "units": 4, "scanned": 2,
           "channels": [{**_ch("UC1", 5000, 44, "速い"), "age_days": 44, "subs_per_day": 113.6,
                         "shape": peers.shape([{"dur": "PT27M", "views": 1000, "likes": 10, "comments": 1}])}]}
    out = "\n".join(peers.lines(row, {"subs": 29, "age_days": 378, "subs_per_day": 0.08,
                                      "n": 295, "secs_median": 90, "views_median": 89,
                                      "views_max": 1891, "like_rate": 0.151}))
    assert "速い" in out and "うち" in out
    # **判定の語を持たないこと**（覆る条件 (4)）——この口が「だから長尺にしろ」と言い始めたら、
    # 次の回はこの行が落ちて気づく
    for word in ("すべき", "してください", "間違"):
        assert word not in out
