"""**下限を、下限のまま分母に使わないこと**（2026-08-31・最適化の回の第2手）。

## この検査が持っている主題

`src/form_record.py` は 2026-08-31 の朝から、記録ごとに `settled`（伸びきったか）を
返していました。`scripts/eta.py` はそれを受けて、こう**印字**していました ——

    [!] **その ×21.4 は隔たりの『上限』で、実測の隔たりではありません**
        —— 分母の 156回 は長尺の記録ですが、**長尺は伸びきっていません**

**そして、その 156 をそのまま分母にして ×21.4 を出していました。**
「この数は下限です」と言いながら、**下限で割った答えを結論として印字する** ——
`CLAUDE.md`「言っている所と、している所が別」の、いちばん高くつく形です。
到達日そのものではなく、**到達日が動くかどうかの判断**がこの倍率に乗っています。

## 実測（2026-08-31・`data/views.jsonl` 22,667点・API 0単位）

記録の本 `_Mz5rg6jQ_A`（長尺）の軌跡の末尾::

    174h  97      197h 131      245h 156      246h 156   ← **登りながら観測が切れている**

同じ形の対応のある比（246時間 → 720時間・n=5）は **中央値 ×2.00**。
いっぽうショートの記録の本 `NHKylqsNfTw` は **366h〜372h で 1863 のまま平ら**で、
対応のある比は **×1.00**（n=10）。**補正が要るのは長尺だけ**です。

    長尺の記録   156 → **312**      形をまたがない最大  ¥9,360 → **¥18,720/月**
    隔たり     ×21.4 → **×10.7**   目標の              4.7% → **9.4%**

## この検査が見ている2点

1. **伸びきった形に、補正を掛けないこと**（ショートは ×1.00 のまま）
2. **伸びきっていない形の隔たりを、生の記録で割らないこと**（`gaps()` の分母）

**緩めないこと。** 緩めた瞬間、機械は「届きません」を実際より 2倍 遠くに言い直します。
"""
from __future__ import annotations

import pytest

from src import form_record


def test_伸びきった形には補正を掛けない():
    """ショートは 366h〜372h で平ら。**補正 ×1.00 から動かさないこと。**

    落ちたときの直し方: `censor_factor()` の `_settled()` の分岐を見ること。
    ショートが伸びきらなくなったのなら、それ自体が所見です（先に `settle.py` を疑う）。
    """
    recs = form_record.per_video_best()
    if not recs.get("ショート"):
        pytest.skip("data/views.jsonl か data/video_forms.json がまだ無い")
    s = recs["ショート"]
    assert s["censor"]["factor"] == 1.0, (
        f"ショートに打ち切り補正 ×{s['censor']['factor']} が掛かっています。"
        "ショートは伸びきっている形です（実測 366h〜372h で平ら）——"
        f"理由: {s['censor']['why']}"
    )
    assert s["best_settled"] == s["best"]


def test_伸びきっていない形は生の記録で割らない():
    """**`gaps()` の分母が、下限のままになっていないこと。**

    `settled` が偽なら記録は打ち切られた下限です。そのとき `gaps()` の
    `record` は `record_raw` より**大きく**なっていなければなりません
    （＝補正が実際に効いている）。

    **補正が測れない回は通します** —— `censor_factor` は n が足りなければ
    ×1.00 を返します（埋めないほうが安全側）。ここが見るのは
    「**測れているのに使っていない**」という食い違いの1点だけです。
    """
    recs = form_record.per_video_best()
    unsettled = {f: r for f, r in recs.items() if not r.get("settled")}
    if not unsettled:
        pytest.skip("伸びきっていない形がありません（補正の出番なし）")

    g = form_record.gaps({"長尺 お金 高": 2_000, "ショート 高": 60},
                         {"長尺 お金 高": 3_333.0, "ショート 高": 3_333.0},
                         per_day=1.0, target_yen=200_000)
    assert g, "gaps() が1行も返しません"
    for row in g:
        rec = recs.get(row["form"]) or {}
        f = float(rec.get("censor", {}).get("factor") or 1.0)
        if f <= 1.0:
            continue                      # 測れていない ＝ 通す
        assert row["record"] > row["record_raw"], (
            f"{row['form']} は伸びきっていない（記録 {row['record_raw']} は下限）のに、"
            f"gaps() の分母が生の記録のままです。"
            f"実測の補正は ×{f:.2f} —— 下限で割ると隔たりを {f:.2f}倍 遠くに言います"
        )
        assert row["ratio"] == pytest.approx(row["need"] / row["record"]), (
            "ratio が record と別の数で割られています（分母の出どころは1つにすること）"
        )


def test_補正は1倍を下回らない():
    """**補正が記録を減らさないこと。** 減るなら、それは打ち切りではなく別の話です。"""
    for form, rec in form_record.per_video_best().items():
        assert rec["censor"]["factor"] >= 1.0, f"{form} の補正が 1.0 未満です"
        assert rec["best_settled"] >= rec["best"], f"{form} の補正後が記録より小さい"
