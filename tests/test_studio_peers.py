"""同じニッチの他人を数える口（`studio/peers.py`）。

2026-09-15 21:0x・optimizer・Fable 5.1（ultracode）。固定 2（期限内にできるか → できる以外なら やり方を疑え）で
疑った先: **7周 続けて「できない」と答えてきたが、その外挿には比べる相手が 1つ も無かった**。
理由と覆る条件は `studio/peers.py` の冒頭・JOURNAL 2026-09-15 21:0x。

**陽性対照**（撃って落とした）: `FAST_SUBS_PER_DAY` を 0 にすると `test_遅い相手は選ばない` が落ち、
`YOUNG_DAYS` を 100000 にすると `test_古い相手は選ばない` が落ちる。
"""
import datetime as dt
import re

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


# ---------------------------------------------------------------------------
# **3因子の分解**（`peers.throughput` / `throughput_line`・2026-09-18 08:xx）
# ---------------------------------------------------------------------------

def _thr_info(monkeypatch):
    """**本/日 が多い口ほど 登録/日 が低い**作りの corpus（12口・齢はそろえる）。

    1本あたり再生 を 登録/日 と揃え、本/日 はその逆に並べます ＝
    **相関の向きが実物と同じ盤**（実測: 1本あたり +0.886・本/日 は齢を揃えると -0.073）。
    """
    rows = {}
    for i in range(12):
        vpv = 1000 * (i + 1)            # 1本あたり再生 は i とともに増える
        n = 12 - i                      # 本数は i とともに減る（齢は共通 100日）
        views = vpv * n
        subs = int(views * 0.01)        # 登録/再生 は全口 1% でそろえる
        rows[f"UC{i}"] = {"id": f"UC{i}", "title": f"ch{i}", "subs": subs, "views": views,
                          "videos": n, "created": "2026-06-10T00:00:00Z"}   # 齢 100日
    monkeypatch.setattr(peers, "niche_channels", lambda: rows)
    return rows


def test_3因子は恒等式になっている(monkeypatch):
    _thr_info(monkeypatch)
    t = peers.throughput({"subs": 32, "views": 91_206, "videos": 283},
                         _ch_rows(), today=dt.date(2026, 9, 18))
    m = t["mine"]
    assert m["spd"] == pytest.approx(m["vpd"] * m["vpv"] * m["spv"])


def test_本数の順位相関は1本あたり再生より低く出る(monkeypatch):
    _thr_info(monkeypatch)
    t = peers.throughput(today=dt.date(2026, 9, 18))
    assert t["rho"]["vpv"] > 0.85             # 1本あたり再生 は 登録/日 と強く同順
    assert t["rho"]["vpd"] < 0                # 本/日 は逆向き
    assert t["rho"]["vpv"] > t["rho"]["vpd"]
    # **陽性対照**: 本数と 登録/日 を揃えた盤では 本/日 の相関が正に戻る
    rows = {f"UC{i}": {"id": f"UC{i}", "title": f"c{i}", "subs": 100 * (i + 1),
                       "views": 100_000, "videos": 5 * (i + 1),
                       "created": "2026-06-10T00:00:00Z"} for i in range(12)}
    monkeypatch.setattr(peers, "niche_channels", lambda: rows)
    assert peers.throughput(today=dt.date(2026, 9, 18))["rho"]["vpd"] > 0.9


def _ch_rows(days: float = 7.0, d_videos: int = 13):
    """台帳の `channel` の 2行（`mine_videos_per_day` が読む形）。"""
    t0 = dt.datetime(2026, 9, 11, 8, 0)
    return [{"event": "channel", "at": t0.isoformat(), "videos": 270, "subs": 27, "views": 84_781},
            {"event": "channel", "at": (t0 + dt.timedelta(days=days)).isoformat(),
             "videos": 270 + d_videos, "subs": 32, "views": 91_206}]


def test_うちの本数は台帳の差から引く():
    assert peers.mine_videos_per_day(_ch_rows(days=7.0, d_videos=14)) == pytest.approx(2.0)
    # 窓が短すぎる／行が足りない／本数が減った ＝ **黙って数を返さない**
    assert peers.mine_videos_per_day(_ch_rows(days=1.0, d_videos=2)) is None
    assert peers.mine_videos_per_day(_ch_rows()[:1]) is None
    assert peers.mine_videos_per_day(None) is None
    assert peers.mine_videos_per_day(_ch_rows(days=7.0, d_videos=-5)) is None


def test_分解の行は判定せず数を並べる(monkeypatch):
    _thr_info(monkeypatch)
    line = peers.throughput_line({"subs": 32, "views": 91_206, "videos": 283},
                                 _ch_rows(), today=dt.date(2026, 9, 18))
    assert "登録/日 ＝ 本/日 × 1本あたり再生 × 登録/再生" in line
    assert "p" in line and "順位相関" in line
    for word in ("すべき", "してください", "落としなさい"):
        assert word not in line
    # **本数を落とせ、とは言わない**（`throughput` の註 ＝ -0.014 はそこまで言わない）
    assert "本数を落とせば伸びる" not in line or "ではありません" in line
    # 台帳が無ければ「引けません」（**黙って 0 を出さない**）
    monkeypatch.setattr(peers, "niche_channels", lambda: {})
    assert "引けません" in peers.throughput_line(None)


def test_本数が窓から引けないときも行は出る(monkeypatch):
    _thr_info(monkeypatch)
    line = peers.throughput_line({"subs": 32, "views": 91_206, "videos": 283},
                                 None, today=dt.date(2026, 9, 18))
    assert "本/日 **引けません**" in line
    assert "1本あたり" in line          # 残りの 2軸 は出る

# ---------------------------------------------------------------------------
# **人格の印**（`peers.persona` / `persona_line`・2026-09-16 19:xx）
# ---------------------------------------------------------------------------

def _persona_info(monkeypatch, extra=None):
    """名前あり 3口・名前なし 3口・**肩書き 2口**（外されるはずの側）。"""
    base = [
        # 名前あり（肩書きは無い）＝ うちに開いている側
        {"id": "n1", "title": "きな子のシニアお金ゼミ", "subs": 1000, "views": 100_000,
         "videos": 100, "created": "2025-09-16T00:00:00Z"},
        {"id": "n2", "title": "タヌキの年金相談室", "subs": 900, "views": 100_000,
         "videos": 50, "created": "2025-09-16T00:00:00Z"},
        {"id": "n3", "title": "としこの年金相談所", "subs": 800, "views": 100_000,
         "videos": 80, "created": "2025-09-16T00:00:00Z"},
        # 名前なし
        {"id": "p1", "title": "年金解説チャンネル", "subs": 100, "views": 100_000,
         "videos": 100, "created": "2025-09-16T00:00:00Z"},
        {"id": "p2", "title": "お金と仕事の教科書", "subs": 90, "views": 100_000,
         "videos": 200, "created": "2025-09-16T00:00:00Z"},
        {"id": "p3", "title": "シニアマネー研究", "subs": 80, "views": 100_000,
         "videos": 150, "created": "2025-09-16T00:00:00Z"},
        # **肩書きを持つ口** ＝ うちには閉じている腕。数から外れなければ検査が落ちる
        {"id": "c1", "title": "元ハローワーク職員ケンの退職サポート", "subs": 90_000,
         "views": 100_000, "videos": 30, "created": "2025-09-16T00:00:00Z"},
        {"id": "c2", "title": "あき姉 元銀行員FPが教える資産形成術", "subs": 80_000,
         "views": 100_000, "videos": 40, "created": "2025-09-16T00:00:00Z"},
    ]
    if extra:
        base.extend(extra)
    monkeypatch.setattr(peers, "niche_channels", lambda: {c["id"]: c for c in base})
    return base


def test_肩書きを持つ口は数から外れる(monkeypatch):
    """**うちに閉じている腕の効きを、開いている腕の効きとして読まないこと。**

    `元ハローワーク職員ケン` と `あき姉 元銀行員FP` は転換 900/1,000 で、
    外さなければ「名前なし」側の中央を吊り上げます。
    """
    _persona_info(monkeypatch)
    p = peers.persona(today=dt.date(2026, 9, 16))
    assert p["n"] == 6, p["n"]                      # 8口 のうち 肩書き 2口 が落ちる
    titles = {e["title"] for e in p["examples"]}
    assert not any("職員" in t or "FP" in t for t in titles)
    assert p["all"]["plain"]["n"] == 3 and p["all"]["named"]["n"] == 3
    # **陽性対照**: 外す線を消すと、その 2口 が比べる側へ入ってくる
    #   （**中央値は 2口 の外れ値では動きません** —— だから n で見ます。
    #    2026-09-16 19:xx に、中央が動くほうへ賭けた検査を撃って外しました）
    monkeypatch.setattr(peers, "CRED_RE", re.compile(r"(?!x)x"))
    p2 = peers.persona(today=dt.date(2026, 9, 16))
    assert p2["n"] == 8
    assert p2["all"]["plain"]["n"] + p2["all"]["named"]["n"] == 8
    assert p2["all"]["plain"]["n"] > p["all"]["plain"]["n"]


def test_名前の印は題の頭の名前だけを拾う(monkeypatch):
    _persona_info(monkeypatch)
    assert peers.PERSONA_RE.match("きな子のシニアお金ゼミ")
    assert peers.PERSONA_RE.match("タヌキの年金相談室")
    assert not peers.PERSONA_RE.match("お金と仕事の教科書")
    assert not peers.PERSONA_RE.match("年金解説チャンネル")


def test_人格の行は控えを必ず隣に並べる(monkeypatch):
    """**生の「N倍」だけが印字される道を塞ぐ**（2026-09-16 15:1x の覆る条件）。

    比を出すなら、同じ行に **名前なし側の数**と**本/日の控え**が並んでいること。
    """
    _persona_info(monkeypatch)
    line = peers.persona_line("お金と仕事の教科書")
    assert "名前あり" in line and "名前なし" in line          # 控えが隣に在る
    assert "本/日" in line                                  # 「たくさん出した」の控え
    assert "倍" in line
    assert "肩書きの腕は うちには閉じています" in line
    assert "名前 **無し**" in line                           # うちの判定
    for word in ("すべき", "してください"):                    # 判定はしない
        assert word not in line


def test_うちの題に名前が在れば在りと出る(monkeypatch):
    """**陽性対照** —— 題を振ると印字が反転する。"""
    _persona_info(monkeypatch)
    assert "名前 **在り**" in peers.persona_line("タヌキの年金相談室")
    assert "名前 **無し**" in peers.persona_line("お金と仕事の教科書")


def test_台帳が無ければ黙って比を返さない(monkeypatch):
    monkeypatch.setattr(peers, "niche_channels", lambda: {})
    assert "引けません" in peers.persona_line("お金と仕事の教科書")
    assert peers.persona(today=dt.date(2026, 9, 16)) == {"n": 0}
