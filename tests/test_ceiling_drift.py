"""**書き置いた天井を、根拠として使わせないこと。**（2026-09-01・最適化の回）

## 何を踏んだか（実測 2026-09-01）

`scripts/eta.py` の見出しは、毎周こう出ます:

    `per_video` は **×4.16 が天井**（実測 3,918 …
     … 弾力性 -0.663 で1段だけ外挿 … `src/rule_per_video.ceiling_at_rule()`）

**出典として関数の名前が書いてあります。** ところが `plan()` が実際に使う数は
`src/arm_speed.ceilings()` —— **`config/hypotheses.yaml` に書き置かれた
`value: 3918` という文字**です。**関数は毎回 動くのに、使われる数は動きません。**

同じ回に、標本の欠け（形の札が付かない本 53本）を1つ直したところ、
生きた計算は **3,918 → 4,101** になりました。**見出しは 3,918 のまま**です。

これは「その回の姿でできた結論を、あとの回が根拠に使う」の一例です ——
**機械はそのあとも動き続けるので、結論より先に、その根拠のほうが腐ります。**

## この検査が守る2つ

1. **書き置きと生きた計算のずれが `CEILING_DRIFT_TOL` を超えたら落ちる** ——
   超えたら直すのは**書き置きのほう**（`config/hypotheses.yaml` の
   `ceiling.value`）。生きた計算に合わせること。
2. **ずれを印字する行が消えないこと** —— ずれていない回でも
   「見出しの数と、いま計算した数は別の物だ」が出ていないと、
   次の回が見出しの数を**測ったばかりの数**として読みます。

## 覆る条件

`plan()` が `arm_speed.ceilings()` ではなく `ceiling_at_rule()` を直接 読むように
なったら、この検査は要らなくなります（ずれが原理的に 0 になる）。
そのときは `ceiling_drift()` ごと消してよい。
"""
from __future__ import annotations

import pytest

from src import rule_per_video


def test_the_strict_gate_already_exists_and_is_stricter():
    """**門は増やしません** —— `tests/test_form_record.py` に**完全一致**の門が既に在ります。

    この回に `ceiling_drift()` を足したとき、同じ門をもう1つ（許容 15%）作りかけました。
    **既存のほうが厳しく**（`recorded == round(live)`）、緩いほうを足すと
    「15% までは黙って通る」という**逆向きの合図**になります。だから足しません。

    ここが見張るのは **2つが別々に定義されていないこと**だけ:
    書き置き（`arm_speed.ceilings()`）が読めて、生きた計算（`ceiling_at_rule()`）も
    読めて、**同じ数であること**。ずれたときに落ちるのは向こうの検査です。
    """
    d = rule_per_video.ceiling_drift()
    if not d.get("live") or not d.get("stored"):
        pytest.skip("天井が片方 測れていません（素材が足りない回）")
    assert round(d["live"]) == round(d["stored"]), (
        f"書き置き {d['stored']:,.0f} と いまの計算 {d['live']:,.0f} がずれています。"
        " 直すのは config/hypotheses.yaml の ceiling.value のほうです"
        "（tests/test_form_record.py が同じずれで落ちます）")


def test_the_two_numbers_are_always_named_apart():
    """**ずれていない回でも、2つが別物だと印字すること。**"""
    lines = rule_per_video.drift_lines(
        {"live": 4101.0, "stored": 3918.0, "ratio": 4101.0 / 3918.0, "drifted": False})
    assert lines, "ずれが許容の内だと、行ごと消えている"
    text = "".join(lines)
    assert "3,918" in text and "4,101" in text, "2つの数が並んで出ていない"
    assert "書き置" in text, "『書き置かれた文字』だと言っていない"


def test_drift_flag_trips_past_the_tolerance():
    """**許容を超えたら `drifted` が立つこと**（この閾値が緩んだら落ちる）。"""
    tol = rule_per_video.CEILING_DRIFT_TOL
    ok = rule_per_video.ceiling_drift(c={"value": 1000.0 * (1 + tol * 0.5)},
                                      stored=1000.0)
    bad = rule_per_video.ceiling_drift(c={"value": 1000.0 * (1 + tol * 2)},
                                       stored=1000.0)
    assert ok["drifted"] is False
    assert bad["drifted"] is True
