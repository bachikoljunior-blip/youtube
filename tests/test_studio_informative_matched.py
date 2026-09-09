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
