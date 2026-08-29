"""**禁止の文の中の「N回 外れた」が、台帳の実数と合っているか。**

## なぜ要るか（2026-08-30 に足した）

`arm_speed.ban_lines()` の締めは、読む側にこう言っています::

    開いている前提の `next_if_false` は条件つきです …
    **ただし、同じ腕で既に外れた回数がそこに書いてあるなら、
    それは条件つきではありません。**

**「回数が書いてあること」が、条件つきの禁止を無条件の禁止へ格上げする鍵**
になっています。ところがその回数は**散文の中の手書き**で、
2026-08-30 まで台帳と突き合わせている所がどこにもありませんでした。

実測（同日）: `sub_rate` の禁止の文は「**4回 外れたことになる**」と書き、
台帳の実数は **2件**。`eta.py --alloc` はこの禁止で 5回 続けて
`sub_rate`（いちばん早い＝ 2027-01-18）を落とし、`per_video`（2027-01-21）
に振り替えていました。**差は 3日。**

**この検査が守るのは「禁止するな」ではありません** ——
禁止は台帳のもので、台帳のほうが事情を知っています。
守るのは「**書いてある数が台帳から出ていること**」だけです。

**覆る条件**: 回数を散文ではなく欄（例 `ban_because: {falsified: N}`）で
書くようにしたら、`_BAN_COUNT_RE` ごと要りません。
"""
from __future__ import annotations

import src.arm_speed as arm_speed


def _doc(claim: str, lever: str, line: str, closed: list[dict] | None = None) -> dict:
    return {
        "hypotheses": [
            {"claim": claim, "lever": lever, "side": "content",
             "deadline": "2026-09-09", "next_if_false": [line]},
            *(closed or []),
        ]
    }


def test_count_that_matches_the_ledger_is_not_flagged():
    doc = _doc(
        "ホームに紹介動画を置くと登録率が上がる", "sub_rate",
        "**`sub_rate` の腕は 1回 外れている**。次の1件はそこに立てないこと。",
        [{"claim": "終端で言うと登録につながる", "lever": "sub_rate",
          "outcome": "falsified", "closed_on": "2026-08-08", "effect": 1.0}],
    )
    assert arm_speed.falsified_count("sub_rate", doc) == 1
    assert arm_speed.ban_facts("sub_rate", doc) == []


def test_count_that_disagrees_with_the_ledger_is_flagged():
    doc = _doc(
        "ホームに紹介動画を置くと登録率が上がる", "sub_rate",
        "**`sub_rate` の腕は、動画の外側でも4回 外れたことになる**。"
        "次の1件はそこに立てないこと。",
        [{"claim": "終端で言うと登録につながる", "lever": "sub_rate",
          "outcome": "falsified", "closed_on": "2026-08-08", "effect": 1.0}],
    )
    facts = arm_speed.ban_facts("sub_rate", doc)
    assert len(facts) == 1
    assert facts[0]["said"] == 4
    assert facts[0]["actual"] == 1

    lines = arm_speed.ban_lines("sub_rate", doc)
    joined = "\n".join(lines)
    # **禁止そのものは消さない。** 読む側が重みを決める材料を足すだけ。
    assert "次の1件はそこに立てるな" in joined
    assert "4回 外れた" in joined and "台帳は 1件" in joined
    # 格上げの逃げ道（「条件つきではありません」）を、この行では使わせない。
    assert "上の [!] の行は別です" in joined


def test_effectless_rows_still_count():
    """`closed()` は `effect` の無い行を落とす。**回数はそれでも数える。**

    落とすと「判定はしたが効き幅を書かなかった」外れが数から消え、
    散文の側と食い違って見えます（**本当に食い違っているのは道具のほう**）。
    """
    doc = _doc(
        "ホームに紹介動画を置くと登録率が上がる", "sub_rate",
        "**`sub_rate` の腕は 2回 外れている**。次の1件はそこに立てないこと。",
        [{"claim": "A", "lever": "sub_rate", "outcome": "falsified",
          "closed_on": "2026-08-08", "effect": 1.0},
         {"claim": "B", "lever": "sub_rate", "outcome": "falsified",
          "closed_on": "2026-08-20"}],  # ← effect が無い
    )
    assert arm_speed.falsified_count("sub_rate", doc) == 2
    assert arm_speed.ban_facts("sub_rate", doc) == []


def test_unrelated_counts_in_the_same_prose_are_not_read_as_the_arm_record():
    """同じ散文の「5回 続けて名指しした」を、腕の実績として数えないこと。"""
    doc = _doc(
        "ホームに紹介動画を置くと登録率が上がる", "sub_rate",
        "`eta.py --alloc` は 5回 続けて名指ししているが、次の1件はそこに立てないこと。",
        [{"claim": "A", "lever": "sub_rate", "outcome": "falsified",
          "closed_on": "2026-08-08", "effect": 1.0}],
    )
    assert arm_speed.ban_facts("sub_rate", doc) == []


def test_the_live_ledger_agrees_with_its_own_prose():
    """**実物の台帳**で、禁止の文の回数が実数と合っていること。

    合わなくなったら、直すのは `config/hypotheses.yaml` の**その文**です
    （道具でも、この検査でもありません）。
    """
    bad = {lever: arm_speed.ban_facts(lever) for lever in arm_speed.ARMS}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, f"禁止の文の回数が台帳と食い違っています: {bad}"
