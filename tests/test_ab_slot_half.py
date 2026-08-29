"""**配信の側の A/B（帯の中の位置）が、名ばかりにならないための検査。**

この実験は「枠と題材の対応を、IDのハッシュで配り直す」ことでしか成立しません。
**配り直しが外れると、群の名札だけが残ります** —— そのとき
`ab_split.side_counts()` は「配信 1件」と言い続けるのに、
実際の枠は `pick()` の score 順のままで、**測っているものが何も無くなります。**
「札が無い実験があると『配信 0件』が見た目だけ解消する」
（`tests/test_arm_speed_sides.py`）の、裏返しの形です。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import ab_split  # noqa: E402


def _order():
    """`scripts/batch_build.py` の配り直し。**import が重いので遅らせます。**"""
    import batch_build  # noqa: PLC0415

    return batch_build._ab_slot_order


def test_配信の側の_AB_が1件は走っている() -> None:
    """**この検査が落ちたら、配信の側の枠がまた 0件 に戻っています。**

    実測 2026-08-29: 中身の側は配信の側の **1/13.9** しか当たっていません
    （`src/arm_speed.sides()`）。それでも A/B の枠は 4件 とも `content` でした。
    **枠は希少**（同じ本の流れに同時に乗る）なので、ここは件数の問題です。
    """
    dist = [n for n, e in ab_split.EXPERIMENTS.items() if e.side == "dist"]
    assert dist, (
        "走っている A/B に配信の側が1件もありません —— "
        "`src/arm_speed.sides()` の実測では、配信の側は中身の側の 13.9倍 当たります"
    )


def test_群はおよそ半々に割れる() -> None:
    """片群に寄ると、床（16本）に届くまでの日数が倍になります。"""
    ids = [f"s-topic-{n}" for n in range(600)]
    early = sum(1 for i in ids if ab_split.slot_half(i) == "早枠")
    assert 0.42 < early / len(ids) < 0.58, f"早枠 {early}/{len(ids)}"


def test_中身の側の群と相関しない() -> None:
    """**塩が効いていること。**

    塩を外すと `sha1(topic_id)` の同じ先頭バイトを見ることになり、
    **配信の側の群が、中身の側の群と完全に相関します** ——
    そのときこの実験が測るのは「早枠」ではなく「題が問いの本」です。
    """
    from src.script_writer import title_form  # noqa: PLC0415

    ids = [f"s-topic-{n}" for n in range(600)]
    same = sum(1 for i in ids
               if (ab_split.slot_half(i) == "早枠") == (title_form(i) == "問い"))
    assert 0.40 < same / len(ids) < 0.60, (
        f"`slot_half` と `title_form` が {same}/{len(ids)} で一致しています —— "
        "`SLOT_HALF_SALT` が効いていません"
    )


def test_作り直しても群は動かない() -> None:
    """落ちて撃ち直した本が別の群へ移ると、比較が壊れます（`title_form` と同じ理由）。"""
    for tid in ("s-nenkin-a", "s-ideco-b", "s-jutaku-c"):
        assert ab_split.slot_half(tid) == ab_split.slot_half(tid)


def test_配り直しは並べ替えだけで_枠を作り替えない() -> None:
    """**ここが本体です。**

    `_ab_slot_order()` が枠を1つでも作り替えたら、1日の本数か、
    埋まる時刻か、帯の外へこぼれる本が変わります。
    実測で **帯の中 537.2再生/本 対 帯の外 0.7再生/本** —— 作り替えは
    そのまま投稿を殺します（`batch_build._rescue_dead_slots()` の実測）。
    """
    topics = [{"id": f"s-topic-{n}"} for n in range(8)]
    when = [f"{9 + n // 2}:{'00' if n % 2 == 0 else '30'}" for n in range(8)]
    out = _order()(topics, when)
    assert sorted(out) == sorted(when), "枠の集合が変わっています（並べ替えではない）"
    assert len(out) == len(when)


def test_早枠は遅枠より手前の枠を取る() -> None:
    """**`when` の並びは `live_plan()` の埋め順**（手前から）なので、添字が早さの順位。

    ここが逆向き・無関係になると、群の名札と実際の枠が食い違います
    —— 判定は名札で数えるので、**そのまま嘘の結論が出ます。**
    """
    topics = [{"id": f"s-topic-{n}"} for n in range(20)]
    when = [f"slot-{n:02d}" for n in range(20)]
    out = _order()(topics, when)
    rank = {w: n for n, w in enumerate(when)}
    early = [rank[out[n]] for n, t in enumerate(topics)
             if ab_split.slot_half(t["id"]) == "早枠"]
    late = [rank[out[n]] for n, t in enumerate(topics)
            if ab_split.slot_half(t["id"]) == "遅枠"]
    assert early and late, "この標本では片群が空です（`slot_half` の割合を見ること）"
    assert max(early) < min(late), (
        f"早枠 {sorted(early)} と 遅枠 {sorted(late)} が混ざっています"
    )


def test_数が合わない回は何もしない() -> None:
    """**投稿を止めないこと。** 枠と本数が食い違う回は、黙って元のまま返す。"""
    topics = [{"id": "s-a"}, {"id": "s-b"}, {"id": "s-c"}]
    when = ["9:00", "9:30"]
    assert _order()(topics, when) == when


def test_配り直しが呼ばれる場所は_live_の回だけ() -> None:
    """`--date` / `--hours` / `--hour` / `--long` は「置き先を指示された」回。

    そこへ割り込むと、**言っている所と、している所が別**になります
    （この repo が通算11回 踏んだ形）。
    """
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    head = src.index("_ab_slot_order(topics, when)")
    before = src[:head][-400:]
    assert "try:" in before, "呼び出しが try の中にありません（落ちると投稿が止まります）"
    assert "if live:" in before, "`live` の回以外でも配り直しています"
