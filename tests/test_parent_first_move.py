"""**親の手順書で、子の確認より先に「承認が要る操作」が来たら落ちる検査。**

## この検査が守っているもの（2026-08-24）

**2026-08-24、同じ日に2回、親は発火したのに子を立てずに終わりました。**

    09:1x  オーナー「今子ないけど平気そう？」 → 親が立て直した
    12:0x  オーナー「今止まってていいの？」   → 親が立て直した（**2回目**）

**2回ともオーナーが気づいて直りました。** 目標本文は「私が必ず読むとは限らない」なので、
**人が見ていないと埋まらない形は、それ自体が目標に反しています。**

原因は2つあり、**どちらも「順番」でした。**

**(1) 手順書の中ほどに書いた順番は、実行されません。**
`docs/trigger_parent.md` の「親がやること」には
「2. 子を見る 3. いなければ立てる」と**書いてありました**。それでも 11:17Z の回、
親はオーナーの使用状況を積むほうに気を取られ、**子を一度も見ていません。**
**先頭にあるものだけが、確実に実行されます。**

**(2) 手順書の先頭が、承認待ちで親を殺す操作でした。**
当時の第1節は「本文が写しと違ったら `update_trigger` を撃て。**人手は要りません**」。
12:10:35Z に親がそれを撃ち、`SESSION_STATUS_REQUIRES_ACTION` /
`Waiting on permission: …update_trigger` で止まりました。
**承認待ちの親には次の発火が届きません** ＝ 鎖の復帰口そのものが死にます。

**同じ文書の下のほうには「承認が要る道を、親の手順に入れないこと」と
書いてあり、承認待ちで親が死んだ実測が3件（8/22 に18時間・8/16 に依頼1件・
8/23 に引き継ぎ直後）並んでいました。** 先に読まれる側が禁を破っていて、
**先に読まれる側が勝ちます。**

だから、次の4つが崩れたら赤くします。**文書は自分で順番を守りません。**
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARENT_DOC = ROOT / "docs" / "trigger_parent.md"

# 撃つと承認待ちになりうる操作。親がこれで止まると、次の発火が届かない。
BLOCKING_VERBS = ("update_trigger", "delete_trigger", "create_trigger", "fire_trigger")


def _doc() -> str:
    return PARENT_DOC.read_text(encoding="utf-8")


def test_first_section_is_the_child_check() -> None:
    """**先頭の節が子の確認であること。** ここが変わると (1) の事故に戻ります。"""
    body = _doc()
    # 表題（`# …`）の次に来る最初の節を切り出す
    sections = re.split(r"^## ", body, flags=re.M)
    assert len(sections) >= 2, "`## ` の節が1つもありません"
    first = sections[1]

    assert "list_sessions" in first, (
        "親の手順書の第1節に `list_sessions` がありません。"
        "**先頭にあるものだけが確実に実行されます**（2026-08-24 の事故）。"
    )
    assert "create_session" in first, (
        "第1節に `create_session` がありません。見るだけでなく、立てるところまでが第1節です。"
    )
    for tag in ("youtube-hourly", "youtube-optimizer"):
        assert tag in first, (
            f"第1節に札 `{tag}` がありません。**2つは独立に見る必要があります** ——"
            "札を見ずに「子が1つ生きている」で止めると、主実行が最適化の子に隠れます。"
        )


def test_no_approval_gated_verb_before_the_child_check() -> None:
    """**承認が要る操作を、子の確認より前に置かないこと。**

    置くと、親はそこで `REQUIRES_ACTION` に落ち、**次の発火が届きません**
    （2026-08-24 12:10:35Z に実測。同型の死が 8/22・8/16・8/23 にも1件ずつ）。
    """
    body = _doc()
    first_check = body.find("list_sessions")
    assert first_check != -1, "手順書に `list_sessions` が1度も出てきません"

    for verb in BLOCKING_VERBS:
        for m in re.finditer(re.escape(verb), body):
            if m.start() >= first_check:
                continue
            line_no = body.count("\n", 0, m.start()) + 1
            raise AssertionError(
                f"`{verb}` が子の確認より前（{PARENT_DOC.name}:{line_no}）にあります。"
                "**承認待ちで親が止まると、次の発火が届かず鎖ごと死にます。**"
                "承認が要る操作は、子を立て終えた後に置くこと。"
            )


def test_parent_todo_list_starts_with_the_child_check() -> None:
    """**「親がやること」の 1. が子の確認であること。**

    2026-08-24 まで 1. は依頼の表示で、子は 2. と 3. にありました。
    **依頼を1回出しそこねても次の窓が拾いますが、子を立てそこねると
    次の発火まで誰も回りません。** 落としてよい側が先に来ていました。
    """
    body = _doc()
    head = body.index("## 親がやること")
    block = body[head:head + 1200]
    m = re.search(r"^1\. (.+)$", block, flags=re.M)
    assert m, "「親がやること」に番号付きの 1. が見つかりません"
    assert "list_sessions" in m.group(1), (
        f"「親がやること」の 1. が子の確認ではありません: {m.group(1)!r}"
    )


def test_the_tool_does_not_tell_the_parent_to_fire_the_body_fix() -> None:
    """**道具のほうも、同じ嘘を言わないこと。**

    `scripts/trigger_sync.py` は本文がズレたとき
    「親がやること: 自分で `update_trigger` を当てる。**人手は要りません。**」
    と印字していました。**手順書を直しても、こちらが残っていれば同じ死に方をします**
    ——「同じことを2か所が別々に言っていて、片方しか読まれていない」形です。
    """
    spec = importlib.util.spec_from_file_location(
        "trigger_sync", ROOT / "scripts" / "trigger_sync.py")
    ts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ts)

    # seen=None ＝ 実物を一度も観測していない ＝ 本文の節が必ず出る
    out = ts.plan(ts.load_spec(), None)

    assert "本文" in out, "本文の節が出ていません（この検査の前提が崩れています）"
    assert "人手は要りません" not in out, (
        "`trigger_sync.py` が「人手は要りません」と印字しています。"
        "**実測で偽です**（2026-08-24 12:10:35Z、親が承認待ちで止まった）。"
    )
    assert "何もしない" in out, (
        "本文がズレたときの親の仕事は **何もしない** です。"
        "撃たせると承認待ちで鎖が死にます。"
    )
