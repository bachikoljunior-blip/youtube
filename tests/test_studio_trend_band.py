"""**帯（02〜10時 JST）の 0 を、齢と長さから分けて数えられるか**
（2026-09-09 00:2x JST・optimizer・Opus）。

`studio/trend.py` の `dead_window` の註は「公開が 10:00 JST 固定なので、帯は齢 16〜19h／40〜43h と
重なっており、**刻と齢を分けられません**」と書いていた。**それは半分だけ本当だった** ——
旧作りは 06:59〜18:59 のいろいろな刻に公開されているので、帯に落ちる2点組の齢は **9h〜191h に散っている**。

ここで止めるのは 3つ:

  (1) `MIN_PAIR_MIN` 未満の2点組を数えないこと（長さの違う組を同じ分母に入れない）
  (2) 齢を揃えた `expected` が、齢だけで説明できるときに **observed に寄る**こと
      ＝ **陽性対照**（帯の中でも外と同じ率で伸びている台帳を作ると、p が大きくなる）
  (3) 帯の数が、帯の外の回でも印字されること（§7 が毎周 書き写しているので）
"""
import datetime as dt

from studio import trend
from studio.common import JST


def _m(vid, at, age_h, views):
    return {"event": "measured", "id": vid, "at": at, "age_h": age_h,
            "views": views, "likes": 0, "title": vid}


def test_10分未満の2点組は数えない():
    rows = [
        _m("A", "2026-09-08T12:00:00+09:00", 2.0, 100),
        _m("A", "2026-09-08T12:03:00+09:00", 2.05, 100),   # 3分 —— 落とす
        _m("A", "2026-09-08T14:00:00+09:00", 4.0, 120),    # 2時間 —— 数える
    ]
    nm, nt, om, ot = trend.dead_window(rows)
    assert (nm, nt) == (0, 0), (nm, nt)
    assert (om, ot) == (1, 1), (om, ot)   # 3組 あるが、数えるのは 1組 だけ


def test_分の粒度でも数え直しは動く_落とす理由は長さのほう():
    """註が「構造的に平ら」と書きかけて外した所。**短い組も動く**（実測 +7/5.2分）。"""
    rows = [
        _m("A", "2026-09-07T16:30:47+09:00", 30.0, 122),
        _m("A", "2026-09-07T16:35:57+09:00", 30.1, 129),
    ]
    pairs = trend._pairs(rows)
    assert pairs == [], "10分 未満なので落ちる"
    # 落ちるのは「動かないから」ではない —— 生の差は +7 で、確かに動いている
    assert rows[1]["views"] - rows[0]["views"] == 7


def test_帯の数は帯の外の回でも印字される():
    rows = [
        _m("A", "2026-09-08T12:00:00+09:00", 2.0, 100),
        _m("A", "2026-09-08T14:00:00+09:00", 4.0, 120),
    ]
    out = "\n".join(trend.lines(rows, now=dt.datetime(2026, 9, 8, 14, 0, tzinfo=JST)))
    assert "帯 02:00〜10:00 JST の2点組" in out, out
    assert "10分 未満の2点組は数えていません" in out, out


def _band_rows(band_grows: int):
    """**1本につき、帯の中の2点組と 帯の外の2点組を1つずつ**（同じ齢の束・同じ長さ 120分）。

    **本ごとに両側を持たせるのが要点**です —— 並べ替えは札を**本の中でだけ**入れ替えるので、
    「帯にしか点が無い本」と「外にしか点が無い本」に分かれた台帳では、
    札の行き先が最初から決まっていて **p は必ず 1.0 になります**（この検査を書いたとき、
    本を V/W に分けた最初の形がそれで、`p_va` が 1.0 で落ちた）。
    **本物の台帳は両側を持ちます** —— `measure` は刻を選ばずに走るので、1本の並びが
    帯の中と外の両方に落ちる。だから実データでは並べ替えに効き目があります（p_video 0.011）。

    **1本 4点 なので2点組は 3つ できます**（04→06 が帯・06→14 と 14→16 が外）。
    まん中の 06→14 は**跨ぎの組**で、ここは伸ばしません ——
    伸ばすと「外の率」に混ざって対照の数が読めなくなる。数は:

        帯の組 24（伸びるのは `band_grows` 個）
        外の組 48 ＝ 跨ぎ 24（0個 伸びる）＋ 14→16 の 24（12個 伸びる）
        → 外の率 12/48 ＝ 0.25 → 齢を揃えた expected ＝ 0.25 × 24 ＝ **6.0**
    """
    rows = []
    for i in range(24):
        v = 100
        day = f"2026-09-{1 + i:02d}"
        grew = 1 if i < band_grows else 0
        # 帯の中（04:00 → 06:00 JST・120分）
        rows.append(_m(f"V{i}", f"{day}T04:00:00+09:00", 100.0, v))
        rows.append(_m(f"V{i}", f"{day}T06:00:00+09:00", 102.0, v + grew))
        # 跨ぎ（06:00 → 14:00・帯の外に落ちる）—— 伸ばさない
        rows.append(_m(f"V{i}", f"{day}T14:00:00+09:00", 110.0, v + grew))
        # 帯の外（14:00 → 16:00 JST・120分・同じ齢の束）・半分が伸びる
        rows.append(_m(f"V{i}", f"{day}T16:00:00+09:00", 112.0,
                       v + grew + (1 if i % 2 == 0 else 0)))
    return rows


def test_片側にしか点が無い本ばかりだと並べ替えは効かない():
    """**この道具の効き目の前提**を、明示的に止める（上の `_band_rows` の註）。"""
    rows = []
    for i in range(12):
        day = f"2026-09-{10 + i:02d}"
        rows.append(_m(f"B{i}", f"{day}T04:00:00+09:00", 100.0, 100))
        rows.append(_m(f"B{i}", f"{day}T06:00:00+09:00", 102.0, 100))       # 帯・伸びない
        rows.append(_m(f"O{i}", f"{day}T14:00:00+09:00", 110.0, 100))
        rows.append(_m(f"O{i}", f"{day}T16:00:00+09:00", 112.0, 100 + (i % 2 == 0)))
    r = trend.band_vs_age(rows, iters=500)
    assert r["observed"] == 0 and r["expected"] > 5, r
    assert r["p_video"] == 1.0, r   # 札の行き先が本ごとに決まっている ＝ 偶然を訊けない


def test_帯の中でも外と同じ率で伸びていれば_pは大きい():
    """**陽性対照**: 帯が特別でない台帳では、並べ替えの p は小さくならない。

    帯の 24組 のうち 12組 が伸びている台帳 ＝ 帯は外より**よく**伸びている。
    """
    r = trend.band_vs_age(_band_rows(band_grows=12), iters=800)
    assert r["observed"] == 12, r
    assert abs(r["expected"] - 6.0) < 0.01, r      # 外の率 12/48 × 帯 24組
    assert r["p_va"] > 0.2, r


def test_帯だけが伸びなければ_pは小さい():
    """**陰性側**: 同じ齢・同じ長さで帯だけ 0 なら、並べ替えは偶然と言わない。

    伸びを持つ本は 12本、その1つの札が 3組 のどれに乗るかは 1/3 —— 全部 外に乗る率は
    (2/3)^12 ＝ **0.0077**。並べ替えがそこへ寄ることを止める。
    """
    r = trend.band_vs_age(_band_rows(band_grows=0), iters=2000)
    assert r["observed"] == 0, r
    assert abs(r["expected"] - 6.0) < 0.01, r
    assert r["p_va"] < 0.05, r


def test_長さで揃えた対照も出る():
    """100〜200分 の組だけで揃える ＝ 跨ぎの 480分 の組が落ちる。"""
    r = trend.band_vs_age(_band_rows(band_grows=0), iters=200)
    grew_b, n_b, grew_o, n_o = r["matched"]
    assert (n_b, n_o) == (24, 24), r["matched"]     # 120分 の組が両側 24ずつ
    assert (grew_b, grew_o) == (0, 12), r["matched"]
    assert r["expected_per_hour"] > 2.0, r
