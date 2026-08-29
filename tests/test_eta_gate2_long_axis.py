"""**段2（門2a・長尺4,000時間）は、動かせる側の軸も解くこと。**

2026-08-29 に踏んだ形が2つ。どちらも「凍らせた入力から出した『届きません』」で、
`CLAUDE.md`（「裸の『届きません』を出さないこと」）が名指ししているものです。

1. **表が L＝1/2/4本/日 しか持たず**、実測の1本あたり再生を当てて
   「**いちばん甘い行でも 5倍 足りない。全部の行を下回っています**」で閉じ、
   そのあと「段2 が測るのは**1本あたりを何倍にできるか**」と言っていた。
   **Lはこの機械が自分で動かせる側**（族を1つ足せば +2本/7日）で、
   1本あたり再生は配信が決める側。**動かせるほうが画面に出ていなかった。**

2. 面の行が「**ここから先で効くのは CTR のほうです（要る CTR 7.3%・サムネと題）**」と
   次に引く腕まで名指ししていたのに、**要る CTR が実測の振れの中か外かを
   1度も見ていなかった。** 実測 67/4,001 ＝ 1.67%・95%区間 [1.32%, 2.13%] で、
   **7.3% は上端の 3.4倍 外**。サムネを直して届く帯ではありません。

**覆る条件はテストごとに下に書いてあります。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import eta  # noqa: E402


def _fake_a() -> dict:
    """`_long_break_even()` の返りだけを持つ、最小の `a`。"""
    return {
        "long_minutes_needed": 239_898.0,
        "long_break_even": [
            {"label": "尺4分・維持20%", "min_per_view": 0.8, "views": {}},
            {"label": "尺7分・維持40%", "min_per_view": 2.8, "views": {}},
        ],
    }


def test_needed_per_day_is_the_inverse_of_the_break_even_table():
    """**同じ式の裏返し**であること（片方だけ直ると、2つの数がずれます）。

    `_long_break_even()` は L を固定して1本あたり再生を解き、
    `_long_needed_per_day()` は1本あたり再生を固定して L を解きます。
    どちらも `要る視聴分 ÷ (L × 日数 × 1再生の視聴分)` の同じ1本なので、
    **片方の答えをもう片方に入れると元の入力が返る**はずです。
    """
    a = _fake_a()
    days = 491.0
    lpv = 8.0
    rows = eta._long_needed_per_day(a, lpv, days)
    assert [r["label"] for r in rows] == ["尺4分・維持20%", "尺7分・維持40%"]
    for r in rows:
        # 出た L を `_gate2_bar` に入れ直すと、固定した1本あたり再生に戻る
        back = eta._gate2_bar(a, {"min_per_view": r["min_per_view"]}, r["per_day"], days)
        assert abs(back - lpv) < 1e-6, (r, back)


def test_easiest_shape_needs_far_more_than_the_printed_scenarios():
    """**表の3列（1/2/4本/日）では、実測の1本あたり再生に届かない。**

    ここが落ちるのは、実測の1本あたり再生が上がって L＝4本/日 で足りるように
    なったときです（＝ この検査の目的そのものが済んだとき）。
    **そのときは、この検査ごと消してよい。**
    """
    a = _fake_a()
    rows = eta._long_needed_per_day(a, 8.0, 491.0)
    best = min(r["per_day"] for r in rows)
    assert best > max(eta.LONG_PER_DAY_SCENARIOS), best


def test_family_ceiling_reads_topic_forge_and_does_not_copy_the_constant():
    """**天井の式は `topic_forge` から読むこと**（写した瞬間に古くなります）。

    `per_calc` と窓の日数は `scripts/topic_forge.py` の定数です。
    ここに写しがあると、あちらを変えた回に段2 だけ古い数で印字します。
    """
    import topic_forge  # noqa: PLC0415

    fam = eta._long_family_ceiling()
    if fam is None:                       # 帳面が読めない環境では素通り
        return
    assert fam["per_calc"] == topic_forge.PER_CALC_DEFAULT
    assert fam["window"] == topic_forge.LONG_WINDOW_DAYS
    # 天井は「族 × per_calc」と在庫の低いほう（`print_long_stock()` と同じ式）
    assert fam["ceiling_7d"] <= fam["families"] * fam["per_calc"]
    assert fam["ceiling_7d"] <= fam["stock"]
    assert fam["per_day"] * fam["window"] == fam["ceiling_7d"]


def test_wilson_interval_brackets_the_point_estimate():
    """区間は点推定をまたぎ、負に食い込まないこと（分子が小さい帯で使うため）。"""
    lo, hi = eta._wilson(67, 4001)
    assert lo < 67 / 4001 < hi
    assert lo > 0.0
    # 実測（2026-08-29）の帯。**要る CTR 7.3% は、この上端の外**
    assert 0.012 < lo < 0.015 and 0.020 < hi < 0.023, (lo, hi)
    assert eta._wilson(0, 0) is None
    # 分子0 でも区間は出る（上端だけが立つ）
    z = eta._wilson(0, 100)
    assert z is not None and z[0] == 0.0 and z[1] > 0.0


def test_surface_line_does_not_name_ctr_when_the_need_is_outside_the_interval():
    """**要る CTR が実測の区間の外なら、「CTR が縛っている」と名指ししないこと。**

    2026-08-29 まで、この行は区間を1度も見ずに
    「ここから先で効くのは CTR のほうです（サムネと題）」と印字していました。

    **覆る条件**: 区間の上端が要る CTR を超えたら（標本が薄い／CTR が上がった）、
    同じ枝が「その区間の中」と印字して名指しをやめます —— 下の2つ目がそれです。
    """
    others = {"ctr": 1.6745813, "ctr_n": 4001.0, "ctr_k": 67.0,
              "per_publish": 318.1, "planned_pubs": 7.57}
    s = eta._gate2_surface_note(2408.7, 175.0, others=others)
    assert "95%区間" in s
    assert "サムネと題では届きません" in s
    assert "ここから先で効くのは CTR のほうです" not in s
    # **裸で「届きません」を出さないこと** —— 面の側の倍率と本数が同じ行に出る
    assert "同じ不足を面の側で閉じるなら" in s and "本/日" in s

    # 区間の中に入るケース（CTR が上がった／標本が薄い）では名指しへ戻る
    wide = {"ctr": 6.0, "ctr_n": 200.0, "ctr_k": 12.0}
    s2 = eta._gate2_surface_note(2408.7, 175.0, others=wide)
    assert "その区間の中" in s2
    assert "サムネと題では届きません" not in s2
