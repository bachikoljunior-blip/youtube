"""**`--pick-only` は、選ぶところまでで止まる**（2026-08-29 13:4x・定期の回）

## なぜ要るか

08/29 10:2x の申し送りが名指ししていた欠陥です（原文）:

> `batch_build` に「選ぶところまでで止める」口を足すこと。`--report` は台帳を
> 並べるだけで `pick()` を通しません。この回はそれが無くて、**4回 撃ち直して
> 3回ぶんの生成を捨てました。**

**捨てたのは生成（1本 約10分）です。** 見たかったのは `[pick]` の3行
（着地点／避けた calc／選んだ本）だけでした。

そして 13:4x の回は、それに加えて **A/B の群**と**本当に生きる枠のある日**を
手で解いています（`python -c` で `pick()` を呼び、`live_slots.Board` を回した。
実測 約4分）。**どちらもテーマIDと控えだけで決まる**ので、この口が出せます。

## 既知の当たり（**この検査が押さえているもの**）

1. **単位を1つも使わないこと。** `--pick-only` の回が `_pull_verdicts_first()`
   （1,300単位）や `_push_thumbnails_first()`（50単位/本）を撃つと、
   **同じ窓の投稿がそのぶん減ります**（`videos.insert` は 1本 1,600単位）。
   **見るだけの回が、出す回の枠を食ってはいけません。**
2. **群は、手で作ったテーマIDで確かめること**（実データの偶然に置かない ——
   `docs/trigger_main.md` §4「その『既知の当たり』を、実データの偶然に置かないこと」）。
   `pipeline.slide_pace()` は `sha1("pace:"+id)` の純関数なので、
   **`ab_split.group_of()` の答えと一致していなければならない。**

## 覆る条件

`pick()` が「足りない群」を見て並べるようになったら、1 の印字は要りません
（そのとき `_print_ab_groups` を消して、この検査もその項だけ落とすこと）。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build  # noqa: E402
from src import ab_split, pipeline  # noqa: E402


def test_pick_only_という口が在る():
    """**`--report` では代わりになりません**（あちらは `pick()` を通さない）。"""
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    assert "--pick-only" in src
    assert "args.pick_only" in src


def test_pick_only_は単位を使う手を撃たない():
    """1,300単位 と 50単位/本 の手が、**見るだけの回に掛からない**こと。

    **文字で見ています。** 実際に `main()` を走らせると `pick()` が
    チャンネルの読みに入る（窓の外なら API を叩く）ので、検査の側で
    枠を減らすわけにいきません。
    """
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    i = src.index("_pull_verdicts_first()\n        _push_thumbnails_first()")
    head = src[:i]
    # 直前に `if not args.pick_only:` が立っていること
    assert head.rstrip().endswith("if not args.pick_only:"), (
        "`--pick-only` の回に `_pull_verdicts_first` / `_push_thumbnails_first` が"
        " 掛かっています。**見るだけの回が、出す回の枠を食います。**"
    )
    assert "if not args.skip_upload and not args.pick_only:" in src, (
        "`--pick-only` の回が投稿の本数枠を読みに行っています"
    )


def test_既知の当たり_群は手で作ったIDで一致する():
    """`ab_split.group_of()` と `pipeline.slide_pace()` が同じ答えを出すこと。

    **実データのテーマは使いません。** 使うと、控え（`data/ab_labels.json`）に
    名札が焼かれた瞬間に、この検査は「関数どうしの一致」ではなく
    「控えとの一致」を見るようになります。
    """
    exp = ab_split.EXPERIMENTS["slide_pace"]
    made = [f"tests-pick-only-{i}" for i in range(40)]
    labels = {ab_split.group_of(exp, i) for i in made}
    assert labels <= {exp.treated, exp.control}
    # **両方の群が出ること** —— 片側しか出ないなら、振り分けが畳まれています
    # （`SLOW_PACE_SHARE = 0`）。そのときは床を埋める道が消えているので、
    # **この検査が落ちるのが正しい**（`config/hypotheses.yaml` の閉じ方の項）。
    assert labels == {exp.treated, exp.control}
    for i in made:
        want = exp.treated if pipeline.slide_pace(i) == pipeline.SHORT_SLIDE_SECONDS_SLOW \
            else exp.control
        assert ab_split.group_of(exp, i) == want, i


def test_生きた枠の日は_Board_から読む():
    """`live_plan()` の帯の空きではなく、`live_slots.Board` の生きた枠で数えること。

    **この2つは別の数です** —— `live_plan()` は「その日の帯に何本 置いたか」しか
    見ておらず、**その日のショートが既に上限に達しているかを見ません**
    （同関数の中の註）。実測 2026-08-29 13:4x: 既定は 09/08 を返し、
    `Board` は 09/23 まで満杯・いちばん早い生きた枠は 09/24 でした。
    """
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    i = src.index("def _print_live_days(")
    body = src[i:i + 3000]
    assert "live_slots" in body and "Board" in body, (
        "`_print_live_days` が `live_slots.Board` を読んでいません。"
        " `live_plan()` の帯の空きで代用すると、**上限に達している日を空きと読みます**"
    )
    assert hasattr(batch_build, "_print_live_days")
