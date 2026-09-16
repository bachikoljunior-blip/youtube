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


# ---------------------------------------------------------------------------
# `capacity` の控え（登録者の帯で割る）。2026-09-16 17:0x・optimizer・Fable 5.1・ultracode。
# 疑った先: **`capacity` の「16% が 400,000回 を越える」は、このニッチの1本の力ではなく
# チャンネルの大きさだった**（同じ罠の 3度目 ＝ `title_shape` 54.4→1.02倍・`families` 5,087→2.35倍）。
# **陽性対照**: `_band_info` の登録者を全部 大きい側へ振ると帯が 1つ に潰れる（下の assert）。
# ---------------------------------------------------------------------------

def _band_rows():
    """小さい口の本は伸びず、大きい口の本は伸びる —— という形の 4本。"""
    return [
        {"id": "s1", "channel": "UCsmall", "views": 500, "secs": 400, "form": "long", "q": "a"},
        {"id": "s2", "channel": "UCsmall", "views": 30_000, "secs": 400, "form": "long", "q": "a"},
        {"id": "b1", "channel": "UCbig", "views": 300_000, "secs": 1500, "form": "long", "q": "a"},
        {"id": "b2", "channel": "UCbig", "views": 900_000, "secs": 1500, "form": "long", "q": "a"},
    ]


def _band_info(monkeypatch, small_subs=100):
    monkeypatch.setattr(peers, "niche_channels", lambda: {
        "UCsmall": {"id": "UCsmall", "subs": small_subs},
        "UCbig": {"id": "UCbig", "subs": 500_000},
    })


def test_うちの帯では扉を越えた本が1本もない(monkeypatch):
    _band_info(monkeypatch)
    c = peers.capacity_by_size(_band_rows())
    low = [b for b in c["bands"] if b["lo"] == 0][0]
    assert low["n"] == 2 and low["over_gate"] == 0       # 30,000回 は 60,000 に届かない
    assert low["max"] == 30_000
    top = [b for b in c["bands"] if b["lo"] == 100_000][0]
    assert top["over_gate"] == 2                         # 同じ 4本 でも、大きい帯では 2本 とも越える
    # **陽性対照**: 小さい口を 500,000人 にすると帯が 1つ に潰れる
    _band_info(monkeypatch, small_subs=500_000)
    assert [b["lo"] for b in peers.capacity_by_size(_band_rows())["bands"]] == [100_000]


def test_台帳が無ければ黙らずに引けないと言う(monkeypatch):
    monkeypatch.setattr(peers, "niche_channels", lambda: {})
    line = peers.capacity_by_size_line(_band_rows())
    assert "引けません" in line and "5単位" in line
    assert peers.capacity_by_size(_band_rows())["bands"] == []


def test_生の比だけが印字される道は無い(monkeypatch):
    """`capacity_line` は控えを**必ず**隣に並べる（JOURNAL 09/16 15:1x の覆る条件・3度目）。"""
    _band_info(monkeypatch)
    line = peers.capacity_line(_band_rows())
    assert "門の先（月20万）の距離" in line                  # 生の比の側は残っている
    assert "登録者の帯で割る" in line                       # **控えが必ず付く**
    monkeypatch.setattr(peers, "niche_channels", lambda: {})
    assert "引けません" in peers.capacity_line(_band_rows())


# ---------------------------------------------------------------------------
# 転換率（登録÷総再生）。同じ回。**14周 が触っていた「1本あたり再生」は分布の中で、
# 215口 中 213口 が持っていない欠陥は転換率のほう**（うち 0.32 対 中央 5.29）。
# **陽性対照**: うちの転換率を中央より上に振ると「下から」の順位が反転する（下の assert）。
# ---------------------------------------------------------------------------

def _conv_info(monkeypatch):
    monkeypatch.setattr(peers, "niche_channels", lambda: {
        f"UC{i}": {"id": f"UC{i}", "title": f"ch{i}", "subs": 100 * i,
                   "views": 10_000, "videos": 50}
        for i in range(1, 6)})           # 転換率 10/20/30/40/50 per 1k


def test_小さすぎる口は転換率の母数に入れない(monkeypatch):
    monkeypatch.setattr(peers, "niche_channels", lambda: {
        "UCa": {"id": "UCa", "subs": 9, "views": 999, "videos": 50},      # 総再生 が床の下
        "UCb": {"id": "UCb", "subs": 9, "views": 10_000, "videos": 4},    # 本数 が床の下
        "UCc": {"id": "UCc", "subs": 50, "views": 10_000, "videos": 50}})
    assert peers.conversion()["n"] == 1


def test_うちの順位は下から数える(monkeypatch):
    _conv_info(monkeypatch)
    c = peers.conversion({"subs": 1, "views": 10_000, "videos": 50})      # 0.1/1k ＝ いちばん下
    assert c["mine"]["rank_sub"] == 1
    assert c["mine"]["x_to_p50"] == pytest.approx(300.0)                  # 中央 30 ÷ 0.1
    # **陽性対照**: 中央より上へ振ると順位が上がる
    c2 = peers.conversion({"subs": 450, "views": 10_000, "videos": 50})   # 45/1k
    assert c2["mine"]["rank_sub"] == 5 and c2["mine"]["x_to_p50"] < 1


def test_転換率の行は判定せずに数を並べる(monkeypatch):
    _conv_info(monkeypatch)
    line = peers.conversion_line({"subs": 1, "views": 10_000, "videos": 50})
    assert "登録/1,000再生" in line and "下から" in line
    for word in ("すべき", "してください"):
        assert word not in line
    monkeypatch.setattr(peers, "niche_channels", lambda: {})
    assert "引けません" in peers.conversion_line(None)
