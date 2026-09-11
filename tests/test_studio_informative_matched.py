"""**§7 の門 (2)（帯の伸び率が外の半分以下）が、帯ではなく齢で通ってしまう**
（2026-09-10 03:0x JST・optimizer・Opus）。

本の公開は全部 10:00 JST に固定なので、帯（02:00〜10:00）に落ちる齢は
**16〜24h・40〜48h…** だけ。**齢 0〜12h・24〜36h・48〜72h は帯に構造的に 1組も入りません。**
そこは伸びのいちばん濃い所なので、**そろえずに比べると、帯を測っているつもりで齢を測ります。**

実測（2026-09-10 03:0x・本物の台帳）:

    生のまま        帯 4/24 (16.7%) 対 外 37/108 (34.3%) ＝ **0.486倍** → 門 0.5 を通る
    齢の束をそろえる 帯 4/24 (16.7%) 対 外 8/54 (14.8%)  ＝ **1.125倍** → 通らない

ここで止めるのは 3つ:

  (1) 帯が 1組も持てない齢の束が `unmatched` に出ること
  (2) **陽性対照** —— 束ごとの伸び率が帯と外で**同じ**なのに、外だけが帯の持てない束に
      濃い伸びを持つ台帳を作ると、**生の比は 0.5 を切り、そろえた比は 1.0 になる**
      （そろえる側を外すと、この検査が落ちる）
  (3) そろえた分母が、そろえない分母を越えないこと
"""
import datetime as dt

from studio import trend
from studio.common import JST

PUB = dt.datetime(2026, 9, 1, 10, 0, tzinfo=JST)


def _m(vid, when, views):
    """公開 09/01 10:00 JST からの齢で `measured` を1行 作る。"""
    return {"event": "measured", "id": vid, "at": when.isoformat(),
            "age_h": round((when - PUB).total_seconds() / 3600.0, 2),
            "views": views, "likes": 0, "title": vid}


def _ledger():
    """帯と外で**束ごとの伸び率が同じ**・外だけが齢 0〜12h に濃い伸びを持つ台帳。"""
    rows = []
    # B: 齢 12〜24h だけを持つ本。22:00〜01:20 が外・02:00〜04:40 が帯（40分 刻み）。
    #    伸びるのは 外で 1組・帯で 1組 だけ ＝ 束の中では同じ率。
    views, grew_out, grew_band = 100, False, False
    t = dt.datetime(2026, 9, 1, 22, 0, tzinfo=JST)
    while t <= dt.datetime(2026, 9, 2, 4, 40, tzinfo=JST):
        rows.append(_m("B", t, views))
        nxt = t + dt.timedelta(minutes=40)
        band = trend.DEAD_START <= nxt.hour < trend.DEAD_END
        if band and not grew_band:
            views, grew_band = views + 5, True
        elif not band and not grew_out:
            views, grew_out = views + 5, True
        t = nxt
    # O: 齢 1〜6h（11:00〜16:00 JST ＝ **必ず帯の外**）で、毎組 伸びる本。
    views = 200
    t = dt.datetime(2026, 9, 1, 11, 0, tzinfo=JST)
    while t <= dt.datetime(2026, 9, 1, 16, 0, tzinfo=JST):
        rows.append(_m("O", t, views))
        views += 30
        t += dt.timedelta(minutes=40)
    return rows


def _ratio(g_n, o_n):
    (bg, bn), (og, on) = g_n, o_n
    return (bg / bn) / (og / on)


def test_帯が1組も持てない齢の束は名指しで出る():
    inf = trend.informative(_ledger())
    assert (0, 12) in inf["unmatched"], inf["unmatched"]
    assert (12, 24) in inf["matched_buckets"], inf["matched_buckets"]


def test_陽性対照_生では門を通りそろえると通らない():
    """**この検査が、そろえる側を外すと落ちる**（＝ `_matched` が効いていることの対照）。"""
    inf = trend.informative(_ledger())
    raw = _ratio(inf["band"], inf["out"])
    matched = _ratio(inf["band_matched"], inf["out_matched"])
    assert raw < 0.5, f"生の比 {raw:.3f} —— 齢の交絡で門 0.5 を通るはず"
    assert 0.9 <= matched <= 1.1, f"そろえた比 {matched:.3f} —— 束ごとの率は同じなので 1.0 のはず"


def test_そろえた分母はそろえない分母を越えない():
    inf = trend.informative(_ledger())
    assert inf["band_matched"][1] <= inf["band"][1]
    assert inf["out_matched"][1] <= inf["out"][1]
    # 落ちるのは外の側だけ（帯は自分の持てる束しか持っていないので）
    assert inf["out_matched"][1] < inf["out"][1]


def test_本物の台帳でも齢の束は帯と外でそろっていない():
    """**この repo の実物**で、帯が持てない束が在ること（無くなったら公開の刻が変わった印）。"""
    from studio.cli import ledger_rows
    inf = trend.informative(ledger_rows())
    assert inf["unmatched"], (
        "帯が持てない齢の束が 0 になった ＝ 公開の刻が 10:00 固定でなくなった。"
        "`_matched` の覆る条件 (1) を読んで数え直すこと")


def test_そろえた側が印字に出る():
    lines = trend.lines(_ledger())
    hit = [ln for ln in lines if "齢の束をそろえると" in ln]
    assert hit, "門 (2) を読む側の数が印字に出ていない"
    assert "帯に1組も無い齢の束" in hit[0]


# ---- 齢の次に「組の長さ」をそろえる（2026-09-10 03:4x・optimizer・Opus） --------
#
# **短い組は「伸びた」と出にくく、しかも短い組は帯の側にしか無い**
# （本物の台帳: 帯の最短 10.7分 対 外の最短 41.0分・10〜30分 の組は 6組 とも帯で 0/6）。
# ＝ そろえないと**帯の率だけが下へ引かれ**、それは**門 0.5 へ向かう向き**です。
# 本物の台帳では齢の側が先に落としてくれて答えが割れませんでした（1.558 対 1.568倍）が、
# **割れる並びは作れます** —— それがこの下の陽性対照で、そろえる側を外すと落ちます。


def _ledger_gap():
    """帯だけが 15分 の平らな組を持つ台帳（束ごとの率は同じ）。"""
    rows = []
    # M: 外にも帯にも 40分 の組を持つ本（齢 12〜24h）。どちらの側でも 1組 だけ伸びる。
    views = 100
    for t, grow in (
        (dt.datetime(2026, 9, 1, 22, 0, tzinfo=JST), False),
        (dt.datetime(2026, 9, 1, 22, 40, tzinfo=JST), False),
        (dt.datetime(2026, 9, 1, 23, 20, tzinfo=JST), True),
        (dt.datetime(2026, 9, 2, 0, 0, tzinfo=JST), False),
        (dt.datetime(2026, 9, 2, 2, 0, tzinfo=JST), False),
        (dt.datetime(2026, 9, 2, 2, 40, tzinfo=JST), True),
        (dt.datetime(2026, 9, 2, 3, 20, tzinfo=JST), False),
        (dt.datetime(2026, 9, 2, 4, 0, tzinfo=JST), False),
    ):
        rows.append(_m("M", t, views))
        if grow:
            views += 5
    # S: 帯にしか無い本。15分 刻みで平ら（＝ 短すぎて伸びが出ない組）＋ 60分 で 1回 伸びる。
    views = 500
    for m in (0, 15, 30, 45, 60):
        rows.append(_m("S", dt.datetime(2026, 9, 2, 5, 0, tzinfo=JST)
                       + dt.timedelta(minutes=m), views))
    rows.append(_m("S", dt.datetime(2026, 9, 2, 7, 0, tzinfo=JST), views + 10))
    return rows


def test_陽性対照_短い組が帯だけに在ると齢だけの比が下へ引かれる():
    """**そろえる側（`GAP_BUCKETS` の突き合わせ）を外すと、この検査が落ちる。**"""
    inf = trend.informative(_ledger_gap())
    age_only = _ratio(inf["band_matched"], inf["out_matched"])
    with_gap = _ratio(inf["band_gapmatched"], inf["out_gapmatched"])
    assert age_only < 0.8, f"齢だけ {age_only:.3f} —— 平らな短い組が帯を下げるはず"
    assert with_gap > age_only + 0.1, (
        f"齢だけ {age_only:.3f} 対 齢＋長さ {with_gap:.3f} —— "
        "長さをそろえたら帯が戻るはず（`_matched` の覆る条件 (0)）")


def test_長さをそろえると帯の分母から短い組が落ちる():
    inf = trend.informative(_ledger_gap())
    assert inf["band_gapmatched"][1] < inf["band_matched"][1]
    # 落ちるのは短い組だけ ＝ 伸びた数は減らない
    assert inf["band_gapmatched"][0] == inf["band_matched"][0]


def test_組の長さの中央値が両側で出る():
    inf = trend.informative(_ledger_gap())
    assert inf["band_gap_med"] is not None and inf["out_gap_med"] is not None
    # 帯の側は 15分 の組を持つので、外より短い
    assert inf["band_gap_med"] < inf["out_gap_med"]


def test_長さもそろえた比が印字に出る():
    hit = [ln for ln in trend.lines(_ledger_gap()) if "齢の束をそろえると" in ln]
    assert hit and "組の長さもそろえると" in hit[0]
    assert "齢だけの比との差" in hit[0]


def test_本物の台帳では門は齢と長さの側で読む():
    """**2026-09-10 09:0x に、差が 0.103倍 で門 0.1 を越えました**（前の回 0.099・7周 続けて開いた）。

    前の形（`test_本物の台帳では長さは門を動かさない`）は「越えたら教える」仕掛けで、
    **狙いどおり赤になって教えました**。越えたあとも同じ assert を残すと毎周 赤のままなので、
    **見張る先を次の門へ移します** —— いまの見張りは 2つ:

      (a) ~~読む側が `齢＋長さ` であること~~ → ~~(6) の「幅」~~ →
          **`side_hi`（24時間 の上限）が門へ戻らないこと**（＝ `gate_span` の覆る条件 (5')）
      (b) その側の比が **0.5倍 を切っていない**こと（＝ 門 (2) が本当に引かれる日。判定は `hourly`・§5）

    **【2026-09-12 04:0x に (a) を次の門へ移しました】** (6) の見張りは **04:0x に狙いどおり
    赤になって教え**（幅 0.075 が門 0.1 を測り 3回 続けて下回った）、その回に **(5)(6) と
    `side_verdict` を畳みました** —— 側は **点（`side_now`）で読む**（derivation は `gate_span` の註）。
    畳んだあとの見張りは、その畳みを開き直す条件 **(5')**: **上限が `GAP_SPLIT` へ戻ったら鋸の歯も戻る**。
    **側そのものは assert しません** —— **「きょうの状態」を不変条件に書かない**
    （§5 の「教訓の形」6つ目）。側は `trend` が毎周 印字します（`_side_line`）。

    **【2026-09-12 03:1x に (a) を (6) へ移しました】** (a) は 09/12 03:0x に**狙いどおり赤になって
    教えました** —— `side_hi` が 0.1614 → **0.0747** に落ち、側が `齢だけ` へ戻った
    （`gate_span` の覆る条件 (5) ＝ その回に初めて引かれた）。

    **【2026-09-10 12:3x に (a) を点から振れ幅へ移しました】** それまでは `informative()` の
    `gate_side`（**1点**）を見ており、**この回に `measure` を 1回 足しただけで赤くなりました** ——
    帯の外から 12:04 に 1回 撃つと 差が **0.101 → 0.020倍** に落ちて側が反転します
    （本の側は 1冊も動いていない）。**見張りは正しく鳴りましたが、鳴った先が刻でした。**
    ＝ 09:4x が**比**について直したのと同じ病気が、**側**にも在った（`gate_span` の註）。
    いまは `side_hi`（24時間 の差の上限・両側 20組 以上 の点だけ）で読むので、
    **鋸の歯のどこで撃っても答えが変わりません。**
    """
    from studio.cli import ledger_rows
    rows = ledger_rows()
    inf = trend.informative(rows)
    if inf["gate_ratio"] is None:
        return
    g = trend.gate_span(rows)
    if g["side_hi"] is not None:
        assert float(g["side_hi"]) < trend.GAP_SPLIT, (
            f"側の差の 24時間 の上限が {float(g['side_hi']):.3f} ＝ 門 {trend.GAP_SPLIT} へ戻った "
            "＝ 鋸の歯が戻っています。`gate_span` の覆る条件 (5') を引くこと"
            "（点で読む畳みを開き直し、上限で読む形へ戻す）。"
            "**戻りは本の側とは限りません** —— 床（`quota.py --pace`）を一緒に見ること")
    assert not (inf["gate_ratio"] < 0.5 and inf["gate_n"] > 20), (
        f"門 (2) が引かれた: {inf['gate_side']} {inf['gate_ratio']:.3f}倍"
        f"（帯 {inf['band_gapmatched']}・n={inf['gate_n']} > 20組）。"
        "そろえた側でも 0.5倍 を切った ＝ 齢では説明が付かない。"
        "**判定は `hourly`**（§5）—— optimizer は数を並べるだけ")


def test_読む側は差が門を越えたときだけ齢と長さになる():
    """**陽性対照**: 同じ道で、差が小さい台帳なら `gate_side` は齢だけへ戻る。"""
    inf = trend.informative(_ledger_gap())
    d = abs(_ratio(inf["band_gapmatched"], inf["out_gapmatched"])
            - _ratio(inf["band_matched"], inf["out_matched"]))
    want = "齢＋長さ" if d >= trend.GAP_SPLIT else "齢だけ"
    assert inf["gate_side"] == want
    assert inf["gate_ratio"] is not None and inf["gate_n"] > 0


def test_読む側が印字に出る():
    hit = [ln for ln in trend.lines(_ledger_gap()) if "門 (2)（0.5倍）を読む側" in ln]
    assert hit, "どちらで読むかは毎周 印字すること（記憶に置かない）"
