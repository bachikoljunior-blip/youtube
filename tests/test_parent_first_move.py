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


def test_first_section_tells_the_parent_to_run_the_loop_itself() -> None:
    """**先頭の節が「親が自分で1周する」であること。**

    ## 2026-08-25 に、この検査が守る中身が入れ替わりました

    それまでここは「**先頭の節は子の確認（`list_sessions` → `create_session`）**」
    を固定していました。**意図は正しく、中身が実測で否定されました。**

    オーナーの一言（「上手くいってるように見えてるところは私が承認押しまくってる
    おかげかもよ」）から測ったところ、**同じ MCP でも読む側と書く側で全く違いました:**

        list_sessions      10.7秒 / 20.2秒 で成功           ← 素通り
        set_session_title  **4,636秒（77分）待って拒否**     ← 人が触るまで動かない
        create_session     **許可リストに入れても開かない**

    つまり旧・第1節は、**「先頭には承認待ちになる操作を置かない」という
    この検査の目的そのものに違反していました** —— `create_session` がまさに
    その操作だったからです。実測で 2026-08-24 23:49 → 翌 06:29 JST の
    6時間40分、親6回・予備6回の発火に対し**自力復帰ゼロ**でした。

    **発火で親が起きるのに承認は要りません**（サーバが時刻で撃つ）。
    親には `Bash` も `git` も `python` もリポジトリもあるので、
    **承認の要る呼びを1つも通さずに1周できます。**

    だから固定する中身を入れ替えます。**守っているものは同じです** ——
    「**先頭には、承認なしで必ず実行できることを置く**」。

    **覆る条件**: `create_session` が承認なしで通る回を2回観測したら、
    子に戻してよい（子のほうが文脈が新しく、親は要約で薄れる）。
    そのときはこの検査も旧版に戻すこと。
    """
    body = _doc()
    # 表題（`# …`）の次に来る最初の節を切り出す
    sections = re.split(r"^## ", body, flags=re.M)
    assert len(sections) >= 2, "`## ` の節が1つもありません"
    first = sections[1]

    assert "next_round.py" in first, (
        "親の手順書の第1節に `scripts/next_round.py` がありません。"
        "**第1節の仕事は「サブを立てる。中身は判断しない」です**"
        "（2026-08-25 夜・オーナー指示「親はサブがやることについて判断しない」）。"
        "**先頭にあるものだけが確実に実行されます。**"
    )
    assert "spawn_prompt.rendered.md" in first, (
        "第1節に、サブへ渡す本文の出どころ（`docs/spawn_prompt.rendered.md`）が"
        "ありません。**親が本文を composeし始めると、周ごとに中身がぶれます** ——"
        "実測: ship 240件のうち `verdict` は14件で、その回に終わる `fix` に寄っていた。"
    )
    assert "worktree" in first, (
        "第1節に `worktree` がありません。**隔離せずに並列で走らせると衝突します** ——"
        "2026-08-25 に `config/hypotheses.yaml` が5か所ぶつかりました（YAML は両方残せない）。"
    )
    # **第1節に、承認待ちになる操作を「やること」として置かないこと。**
    # 触れるのは構いません（なぜ置かないかの説明が要る）が、
    # 「余裕があれば」「諦めて終える」のような**降格の言葉が要ります。**
    if "create_session" in first:
        assert ("余裕があれば" in first or "上振れ" in first), (
            "第1節が `create_session` を『やること』として置いています。"
            "**これは許可リストに入れても承認待ちになります**（2026-08-25 実測）。"
            "置くなら『余裕があれば』『立てば上振れ』と降格した形にすること。"
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
