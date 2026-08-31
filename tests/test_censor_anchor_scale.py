"""**打ち切り補正の比は、記録と同じ桁の分母から採ること。**（2026-08-31・最適化の回）

## なぜこの検査があるか

`src/form_record.censor_factor()` は、**記録に掛ける倍率**を返します。
入った当日（2026-08-31）、その比には**分母の床が1つもありませんでした** ——
条件は `a <= 0` を弾くだけで、**1再生の本が入ります。**

長尺で実際に入っていたのは 5本、分母 **[1, 1, 2, 3, 4] 再生**（記録は **156再生**）。
中身は `1→2`・`2→4`・`4→8`・`3→8`・`1→4` で、中央値 **×2.00** ——
**伸びではなく、1桁の整数の刻み**です（1再生 増えるだけで ×2.00 になります）。

その ×2.00 が記録を 156 → 312 にし、`gaps()` の隔たりを ×21.4 → **×10.7** にして、
`scripts/eta.py` の「**いちばん近い帯**」＝ **その回に引く腕**を決めていました。

同じ関数のショートは分母 **[312 … 1,741] 再生**・記録 1,891再生 で ×1.0000
（n=10・最大 ×1.018）。**ショートは記録と同じ桁で測れていて、長尺は 2桁 下です。**
**同じ数として読めません。**

## この検査が守っていること

1. 床（`CENSOR_MIN_ANCHOR_VIEWS`）が在ること。**消すとこの検査が落ちます**
2. 床を割った標本から出た補正は **`noisy` が立つ**こと（黙って点で出さない）
3. **`noisy` でも `factor` を 1.0 に落とさない**こと —— 長尺が伸び続けるのは
   別に実測できており（168h→480h 中央値 ×2.67）、1.0 は
   「記録は生涯だ」という**もっと外れた側**です
4. 記録と同じ桁で測れている形（ショート）は `noisy` が**立たない**こと
5. `to_hours` と `to_hours_seen` の両方を出すこと —— `_nearest` の許容は
   `hours*0.35+12`（720h なら ±264h）で、**観測の外の地平の名前が付きます**

## 覆る条件

- 床を超えた長尺が `CENSOR_MIN_ANCHOR_VIEWS` × `CENSOR_MIN_N` 本 たまったら、
  `noisy` は自分で偽になります。**そのとき 4番目の検査が長尺にも掛かります**
  （この検査は形を名指ししないので、自動でそうなります）
- `CENSOR_MIN_ANCHOR_VIEWS` を動かすのは自由です。**0 にはできません**（1番目）
"""
from __future__ import annotations

import src.form_record as fr


#: **実物と同じ形にすること**（この形でないと `censor_factor` は何も測りません）。
#:
#: 補正の起点 `a_hours` は**記録の本の最後の読み**です。記録の本を
#: 600時間 まで観測させると、`CENSOR_HORIZONS` の先が 720時間 しか残らず、
#: `_nearest` の許容（±264時間）で 600時間 の読みへ落ちて、**比が必ず ×1.00** に
#: なります。実物の長尺は 記録 `_Mz5rg6jQ_A` が **246時間**まで、
#: 比を出す本が **480〜649時間**まで —— **その並びを写すこと。**
_RECORD_HOURS = 246.0
_DONOR_LATE_HOURS = 600.0


def _synth(anchor_views: int, *, n: int, factor: int,
           record_views: int = 10_000) -> dict[str, list[tuple[float, int]]]:
    """分母が `anchor_views` の本を `n` 本。どれも `factor` 倍に伸びる。

    記録の本を1本 別に置きます（`record_views` 再生・`_RECORD_HOURS` まで）——
    **こちらが `a_hours` を決めます。**
    """
    out: dict[str, list[tuple[float, int]]] = {
        "record": [(174.0, record_views // 2), (_RECORD_HOURS, record_views)],
    }
    out.update({f"v{i}": [(_RECORD_HOURS, anchor_views),
                          (_DONOR_LATE_HOURS, anchor_views * factor)]
                for i in range(n)})
    return out


def test_床が在ること():
    """**床そのものを消せないこと。** 消すと 1再生の本の `1→2` が ×2.00 で入ります。"""
    assert getattr(fr, "CENSOR_MIN_ANCHOR_VIEWS", 0) > 0, (
        "CENSOR_MIN_ANCHOR_VIEWS が無い／0 です。"
        "床が無いと、比の分母に 1再生 の本が入り、`1→2` が ×2.00 として"
        "記録（長尺 156再生）に掛かります。**整数の刻みで、伸びではありません。**")


def test_桁ちがいの標本から出た補正には印が立つ(tmp_path):
    """分母が床を割る標本しか無いとき、`noisy` が真であること。"""
    out = _factor(tmp_path, _synth(1, n=5, factor=2))
    assert out["noisy"] is True, "床を割った標本なのに `noisy` が立っていません"
    assert out["n_clean"] == 0
    assert max(out["anchor_views"]) < fr.CENSOR_MIN_ANCHOR_VIEWS


def test_印が立っても補正は1_0に落とさないこと(tmp_path):
    """**1.0 は「記録は生涯だ」＝もっと外れた側です。** 数は残すこと。"""
    out = _factor(tmp_path, _synth(1, n=5, factor=2))
    assert out["factor"] > 1.0, (
        "`noisy` のときに補正を 1.0 へ落としています。長尺が伸び続けるのは"
        "別に実測できており（168h→480h 中央値 ×2.67・n=5）、1.0 は"
        "**記録を生涯だと言う側**に倒れます。**数は残し、印を立てること。**")


def test_記録と同じ桁で測れていれば印は立たない(tmp_path):
    """ショートのように分母が床を超えていれば `noisy` は偽。"""
    big = fr.CENSOR_MIN_ANCHOR_VIEWS * 20
    out = _factor(tmp_path, _synth(big, n=6, factor=1, record_views=big * 100))
    assert out["noisy"] is False, "床を超えた標本なのに `noisy` が立っています"
    assert out["n_clean"] >= fr.CENSOR_MIN_N


def test_床を超えた標本が在ればそちらを採ること(tmp_path):
    """**混ざっているときは、桁の合う側だけで測ること。**"""
    big = fr.CENSOR_MIN_ANCHOR_VIEWS * 20
    series = _synth(big, n=5, factor=1, record_views=big * 100)   # 桁の合う本: 伸びない
    series.update({f"n{i}": [(_RECORD_HOURS, 1), (_DONOR_LATE_HOURS, 8)]
                   for i in range(9)})            # 桁の合わない本: ×8
    out = _factor(tmp_path, series)
    assert out["noisy"] is False
    assert out["factor"] < 2.0, (
        "床を超えた標本が在るのに、桁の合わない本まで混ぜて測っています "
        f"(factor={out['factor']})")


def test_名指しした地平と実際に読めた齢の両方を出すこと(tmp_path):
    """`_nearest` の許容は `hours*0.35+12`。**観測の外の地平の名前が付きます。**

    実測 2026-08-31: 長尺の最古は 648.6時間 なのに `to_hours=720` と印字して
    いました（許容 ±264時間 ＝ [456h, 984h] に 648.6h が入るため）。
    """
    big = fr.CENSOR_MIN_ANCHOR_VIEWS * 20
    out = _factor(tmp_path, _synth(big, n=6, factor=1, record_views=big * 100))
    assert out.get("to_hours_seen") is not None, "`to_hours_seen` が在りません"
    assert out["to_hours_seen"] <= out["to_hours"], (
        "実際に読めた齢が、名指しした地平より先に出ています")


def test_実データ_長尺は印が立ち_ショートは立たない():
    """**この repo の実物**（`data/views.jsonl`）で、2つが分かれること。"""
    fr.censor_memo_clear()
    lo, sh = fr.censor_factor("長尺"), fr.censor_factor("ショート")
    if lo.get("n"):
        assert lo["noisy"] is True or lo["n_clean"] >= fr.CENSOR_MIN_N, (
            "長尺の補正が、印も立たず床も超えていません")
    if sh.get("n"):
        assert sh["noisy"] is False, (
            "ショートの補正に印が立っています —— 分母は記録と同じ桁のはずです "
            f"(anchor_views={sh.get('anchor_views')})")


# --- 道具 ---

def _factor(tmp_path, series: dict[str, list[tuple[float, int]]]) -> dict:
    """`series` を `views.jsonl` の形で書き出して `censor_factor` に食わせる。"""
    import json

    path = tmp_path / "views.jsonl"
    forms = {vid: "長尺" for vid in series}
    with path.open("w", encoding="utf-8") as f:
        for vid, pts in series.items():
            for h, v in pts:
                f.write(json.dumps({"id": vid, "hours": h, "views": v}) + "\n")
    fr.censor_memo_clear()
    return fr.censor_factor("長尺", views_path=path, forms=forms)
