"""`trend.channel_steps` の `censored` / `periods` / `bench` と、連なりの「配り」の註の検査
（2026-09-12 02:2x・optimizer・Opus。**API 0単位**）。

**なぜ足したか（この回に実物で引かれた）**: `channel_steps` の覆る条件 (1) は
「刻みが 2つ 以上 台帳に載ったら、その間隔の中央値から `CHANNEL_BLOCK_MIN_H` を
引き直すこと」で、**この回に刻みが 3つ 載りました**（+1,625 / +40 / +44）。
そのとき 2つ 分かった:

  (a) **1つ目の刻みの平らは、左端が台帳の先頭**（見始めた刻）＝ **周期でも手本でもない**。
      それを混ぜると、手本の上端は「見始めてからの長さ」で決まる。
  (b) **時間の門の手本は「直近の 1つ」ではなく「いちばん長い平ら」** ——
      直近で読むと、**すでに実測した 12.7時間 の平ら（その後 刻んだ ＝ 止まっていなかった）
      より短い平ら**を「チャンネルが止まった」と読む。同じ台帳が反証を持っている側。

**陽性対照**（`test_positive_control_*`）: 手本を「直近の 1つ」に戻す／`censored` を
混ぜる、で、この file の主張が落ちる形に書いてある。
"""
from __future__ import annotations

from studio import trend


def _row(at: str, views: int) -> dict:
    return {"at": at, "id": "UCxxx", "event": "channel",
            "subs": 28, "views": views, "videos": 269}


def _three_steps() -> list[dict]:
    """**この回の実物と同じ形**: 左端の見えない長い平ら → 12時間 の平ら → 6時間 の平ら。

    最後の平ら（いま続いている側）は **8時間** ＝ **直近の手本（6時間）は越えるが、
    いちばん長い手本（12時間）には届かない**長さ。**2つ の実装がここで割れる。**
    """
    rows = [_row(f"2026-09-09T{h:02d}:00:00+09:00", 1000) for h in range(4, 24)]
    rows += [_row(f"2026-09-10T{h:02d}:00:00+09:00", 2000) for h in range(0, 12)]
    rows += [_row(f"2026-09-10T{h:02d}:00:00+09:00", 2040) for h in range(12, 18)]
    rows += [_row(f"2026-09-10T{h:02d}:00:00+09:00", 2084) for h in range(18, 24)]
    rows += [_row(f"2026-09-11T{h:02d}:00:00+09:00", 2084) for h in range(0, 3)]
    return rows


def test_左端が台帳の先頭の平らは_censored() -> None:
    st = trend.channel_steps(_three_steps())
    assert [s["censored"] for s in st["steps"]] == [True, False, False]


def test_周期はcensoredでない刻みからだけ数える() -> None:
    p = trend.channel_steps(_three_steps())["periods"]
    assert p["n"] == 2                      # 3つ 載っても、周期になるのは 2つ
    assert p["h"] == [12.0, 6.0]
    assert p["med"] == 9.0 and p["max"] == 12.0


def test_手本はいちばん長い平ら_直近ではない() -> None:
    st = trend.channel_steps(_three_steps())
    assert st["bench"] == {"lo": 11.0, "hi": 12.0, "n": 2, "censored_only": False}
    assert st["last"]["flat_h_hi"] == 6.0   # 直近は 6.0 ＝ **手本ではない**


def test_門は手本の上端で引く_この並びで2つの実装が割れる() -> None:
    """いまの平ら 8時間 は **直近の手本 6.0 は越え・いちばん長い手本 12.0 には届かない**。"""
    g = trend.channel_growth(_three_steps())
    assert g["flat_h"] == 8.0
    assert g["flat_laps"] >= trend.CHANNEL_FLAT_LAPS
    assert g["step_flat_h_hi"] == 12.0 and g["step_bench_n"] == 2
    assert g["flat_readable"] is False      # ＝ 「チャンネルが止まった」とは読めない
    line = trend.channel_line(_three_steps())
    assert "いちばん長いもの 11.0〜12.0時間" in line
    assert "手本は 2例 のうちいちばん長い1つ" in line
    assert "上端**に届いていない" in line


def test_positive_control_手本を直近に戻すと門が裏返る() -> None:
    """**陽性対照**: 手本を `last`（6.0時間）にすると、同じ 8時間 の平らが
    `flat_readable` True ＝ **「止まった」と読める側**へ裏返る。
    ＝ 上の検査は、この並びで 2つ の実装を分けている。
    """
    rows = _three_steps()
    g = trend.channel_growth(rows)
    last_hi = trend.channel_steps(rows)["last"]["flat_h_hi"]
    assert last_hi < g["flat_h"] <= g["step_flat_h_hi"]   # 直近の門なら通り、いまの門は通さない
    assert g["flat_readable"] is False


def test_positive_control_censoredを混ぜると手本が長くなりすぎる() -> None:
    """**陽性対照**: `censored` を手本に入れると、上端は「見始めてからの長さ」20.0 になる。
    ＝ 見始めた刻が早いほど門が遠のく（台帳に無い平らを手本にしている）。
    """
    steps = trend.channel_steps(_three_steps())["steps"]
    assert steps[0]["flat_h_hi"] == 20.0
    assert max(s["flat_h_hi"] for s in steps) == 20.0      # 混ぜたときの上端
    assert trend.channel_steps(_three_steps())["bench"]["hi"] == 12.0


def test_刻みが1つだけの窓は手本1例のまま() -> None:
    """刻みが `censored` の 1つ しか無い窓では、代用の手本を立てて `censored_only` を報せる。"""
    rows = [_row(f"2026-09-10T{h:02d}:00:00+09:00", 1000) for h in range(4, 10)]
    rows += [_row(f"2026-09-10T{h:02d}:00:00+09:00", 1500) for h in range(10, 14)]
    st = trend.channel_steps(rows)
    assert st["periods"]["n"] == 0 and st["periods"]["med"] is None
    assert st["bench"]["censored_only"] is True and st["bench"]["n"] == 1
    assert trend._bench_words({"step_bench_n": 1}) == "1例"


def test_連なりが配りを跨いでいなければ_道具がそう言う() -> None:
    """`_bulk_words`: 連なりの塊が、台帳でいちばん大きい配りを 1つも含まないとき。"""
    g = {"over_max_step": 1625, "over_streak_dv": [44, 40], "over_streak_bulk": False}
    w = trend._bulk_words(g)
    assert "+1625回" in w and "配りの間隔" in w
    assert "+44回／+40回" in w


def test_positive_control_配りを含む連なりには註を出さない() -> None:
    """**陽性対照**: 塊が配りを含んでいれば（`streak_bulk`）、註は 1字も出ない。
    出るなら、門が「跨いだか」を見ずに鳴っている。
    """
    assert trend._bulk_words(
        {"over_max_step": 1625, "over_streak_dv": [1625, 40], "over_streak_bulk": True}) == ""
    assert trend._bulk_words(
        {"over_max_step": 0, "over_streak_dv": [], "over_streak_bulk": None}) == ""


def test_塊の長さは刻みの周期から引いていない() -> None:
    """**この回の決め**: 細かい刻みの周期（12時間）から `CHANNEL_BLOCK_MIN_H` を引かないこと
    （`CHANNEL_BLOCK_MIN_H` の註の実測 —— `over` が偽になるのは大きい配りを含んだ塊だけで、
    長さを伸ばすほど連なりは**速く**埋まる）。**2つ目の大きい配りが載るまで据え置き。**
    """
    assert trend.CHANNEL_BLOCK_MIN_H == 2 * trend.REPLICA_LAG_H
    assert not hasattr(trend, "CHANNEL_STEP_PERIOD_H")
