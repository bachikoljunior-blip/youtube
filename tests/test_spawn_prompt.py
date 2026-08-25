"""**子に渡すプロンプトの型**（`docs/spawn_prompt.md`）の検査。

## この検査が守っているもの（2026-08-20）

渡し方が**親のターンの中にしかなく、子が直せませんでした。** 毎時走るので、
ここの欠陥は他のどこよりも回数を掛けて効きます。実測で3回壊れています:

    source_url の付け忘れ      8/17 04:1x・8/18 23:5x（repo の無い子が立つ。
                               8/17 の回は**1件も出せずに終わっています**）
    親が要約して条件を落とす    8/10（別リポジトリで観測）
    申し送りが親と一緒に消える  8/15・8/16

**だから、この3つが崩れたら赤くします。**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("spawn_prompt",
                                               ROOT / "scripts" / "spawn_prompt.py")
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)


def test_every_template_exists_and_is_not_empty() -> None:
    tpl = sp.templates()
    for name in sp.NEEDED:
        assert tpl.get(name, "").strip(), f"`docs/spawn_prompt.md` に {name} がありません"


def test_repo_and_branch_can_never_be_forgotten() -> None:
    """**`source_url` / `source_revision` は道具が必ず入れます。**

    ここが空で立つと、子は `/home/user/youtube` の無いまま1周ぶんの枠を溶かします
    （8/17 04:1x の回。26回で初めて、1件も出せずに終わりました）。
    """
    args = sp.create_session_args("hourly")
    assert args["source_url"].endswith("/youtube")
    assert args["source_revision"].startswith("claude/")
    assert "youtube-hourly" in args["tags"]
    assert args["prompt"].strip()


def test_only_replaces_the_round_instead_of_adding_to_it() -> None:
    """**`--only` の回に「1周してください」が残ると、子は両方やろうとします。**"""
    out = sp.build("hourly", only="eta.py の _drift だけ")
    assert "この回はこれだけです" in out
    assert "1周してください" not in out
    assert "1周はやらないこと" in out


def test_plain_hourly_still_asks_for_the_round() -> None:
    out = sp.build("hourly")
    assert "1周してください" in out
    assert "最低1件は出してから終わること" in out


def test_note_is_carried_verbatim() -> None:
    """**要約しないこと。** 親が解釈すると、そこで事実が1回劣化します。"""
    note = "週90%、5時間枠は32%。11/18までに1日+5.22%。"
    out = sp.build("owner-record", note=note)
    assert note in out


def test_owner_kinds_refuse_to_build_without_the_note() -> None:
    with pytest.raises(SystemExit):
        sp.build("owner-full", note="   ")


def test_owner_kinds_push_the_inbox_first() -> None:
    """申し送りは**親の文脈にしかありません。** 押す前に子が死ぬと依頼ごと消えます
    （8/15・8/16 に2回消えました）。だから `inbox.py --open` が先頭に要ります。"""
    for kind in ("owner-full", "owner-record"):
        out = sp.build(kind, note="なにか")
        head = out.split("\n\n")[1]
        assert "inbox.py --open" in head, f"{kind}: 受け取り帳が先頭にありません"


def test_owner_record_never_asks_for_the_round() -> None:
    """記録だけの回に1周が乗ると、2人で同じ日の予約を取り合います（8/15 の再発）。"""
    out = sp.build("owner-record", note="なにか")
    assert "1周はやらないこと" in out
    assert "1周をやること" not in out


def test_siblings_are_named_and_absence_is_stated() -> None:
    """**「いない」と書いてあることに意味があります。**

    書いていないと、受け取った子は「調べていないだけ」と区別できません。
    """
    named = sp.build("hourly", siblings=["016bZbYd", "01Cja6DK"])
    assert "016bZbYd" in named and "01Cja6DK" in named
    alone = sp.build("hourly", siblings=[])
    # **語ではなく意味で固定する**（2026-08-25 に「子」→「相手」へ変えたら落ちた）。
    # 立てられる側はサブエージェントになったので「子」ではありません。
    # 守りたいのは**「いないと明記してある」**ことだけです。
    assert "他に走っている" in alone and "いません" in alone
    for out in (named, alone):
        assert "git fetch" in out and "捨てないこと" in out


def test_rendered_copy_for_the_parent_is_current() -> None:
    """**親は repo を触れないので、この道具を回せません。**

    親が取るのは写しです。古いと、親は古い型で子を立て続けます。
    """
    want = sp.RENDERED.read_text(encoding="utf-8")
    sp.write_rendered()
    got = sp.RENDERED.read_text(encoding="utf-8")
    assert got == want, ("`docs/spawn_prompt.rendered.md` が古いです。"
                         "`python scripts/spawn_prompt.py --write-rendered` を打つこと")


def test_rendered_copy_keeps_the_repo_arguments() -> None:
    text = sp.RENDERED.read_text(encoding="utf-8")
    for kind in sp.KINDS:
        assert f"## kind: {kind}" in text
    assert text.count('"source_url"') == len(sp.KINDS)
    assert text.count('"source_revision"') == len(sp.KINDS)


# --- 役が2つになった（2026-08-24。オーナー提案「並行して、主実行を目標に
#     最適化し続ける子を動かしたら？」）---------------------------------------
#
# **いちばん壊れると危ないのは札です。** 親は札で子の生死を見るので、
# 最適化の子が `youtube-hourly` を名乗ると、**主実行が立たなくなります**
# （親は「子が生きている」と読んで見送る）。ここを検査で留めます。

def test_optimizerの札はhourlyと別_混ざると主実行が立たなくなる():
    import scripts.spawn_prompt as sp
    assert sp.create_session_args("optimizer")["tags"] == ["youtube-optimizer"]
    assert sp.create_session_args("hourly")["tags"] == ["youtube-hourly"]


def test_optimizerは1周を頼まない():
    """**主実行と同じことをさせないこと。** 同じなら役を分けた意味がありません。"""
    import scripts.spawn_prompt as sp
    body = sp.build("optimizer")
    assert "1周してください" not in body
    assert "最適化の回" in body


def test_optimizerに規則の一覧を書き足させない():
    """**この役に渡すのは、目標と実測した事実だけ**（2026-08-24 に書き直した）。

    最初の版は、オーナーが言っていないことを私が足していました ——
    「触ってよいファイルの一覧」「触らない一覧」「合格の4つの型」「1件」。
    **オーナーの言葉は「主実行を目標に最適化し続ける役」だけ**で、
    やり方の指定はどこにもありませんでした。

    **`CLAUDE.md` の冒頭が言っているのと同じ失敗です** ——
    「自分で規則の一覧を作って聖域と呼び、守ることを仕事にしていた。
    それは目標から出てきたものではありません」。
    **診断した歪みを、別の子に対して再生産していました。**

    **この検査が守るのは「規則が無いこと」ではありません**
    （事実や道具の紹介まで消すと、次の子は何も知らずに始めます）。
    守るのは**「決めるのは渡された側だ」と明示されていること**です。
    """
    import scripts.spawn_prompt as sp
    body = sp.build("optimizer")
    assert "それ以外に与件はありません" in body
    assert "全部あなたが決めます" in body
    # **禁止の一覧を書き戻したら、ここで落ちること。**
    for banned in ("何を触らないか", "何を触るか（**ここだけ**）",
                   "この回の合格", "この役の成果ではありません"):
        assert banned not in body, f"勝手な規則が戻っています: {banned}"


def test_optimizerは資源の衝突を規則ではなく事実として渡す():
    """**8/15 の予約の取り合いは実測です。禁止に翻訳しないこと。**

    起きたことを渡せば、避けるかどうかは向こうが決められます。
    「予約するな」と書くと、**避ける価値のある場面をこちらが先に決めてしまう。**
    """
    import scripts.spawn_prompt as sp
    body = sp.build("optimizer")
    assert "2026-08-15" in body
    assert "あなたの判断です" in body


def test_optimizerもrepoと枝を必ず持つ():
    """`source_url` の付け忘れで repo の無い子が立った事故は2回（8/17・8/18）。"""
    import scripts.spawn_prompt as sp
    a = sp.create_session_args("optimizer")
    assert a["source_url"].endswith("/youtube")
    assert a["source_revision"].startswith("claude/")


# --- 逐語で渡す役に、埋まっていない差し込み口を残さない（2026-08-25）-----------
#
# **親の手順は「`prompt` を1字も変えずに渡す」です。**
# それなのに写しの `hourly` には
# `<<いま走っている子の識別子。いなければこの行ごと消す>>` が入っていました。
# **両方を守ると、サブはプレースホルダの文字列を「走っている相手の名前」として
# 受け取ります。** しかも `_siblings_block()` は
# 「**いないと明記してある**ことに意味がある」ために作った段なので、
# **逐語コピーの規則が、その段の意味をちょうど壊していました。**
#
# 埋めさせてよいのは `owner-*` だけです（オーナーの言葉は repo から求まらない）。

#: 親がそのまま渡す役。ここに差し込み口があってはならない。
VERBATIM_KINDS = ("hourly", "optimizer")


def test_逐語で渡す役には差し込み口が残っていない():
    import json
    import re as _re

    text = sp.RENDERED.read_text(encoding="utf-8")
    blocks = dict(_re.findall(
        r"^## kind: ([\w-]+)\s*\n\n```json\n(.*?)^```", text, _re.M | _re.S))
    for kind in VERBATIM_KINDS:
        assert kind in blocks, f"写しに `## kind: {kind}` がありません"
        prompt = json.loads(blocks[kind])["prompt"]
        left = _re.findall(r"<<[^>]*>>", prompt)
        assert not left, (
            f"`{kind}` の prompt に埋まっていない差し込み口が残っています: {left}。"
            "**親は1字も変えずに渡すので、これはそのままサブに届きます。**"
            "写しの既定を「埋まった側」にすること"
            "（`scripts/spawn_prompt.py` の `write_rendered`）。"
        )


def test_相手がいない回は_いないと書いてある側が写しの既定():
    """**空欄ではなく「いません」と書いてあること。**

    差し込み口を消すだけだと、`_siblings_block()` の
    「調べていないだけと区別できない」という穴に戻ります。
    """
    import json
    import re as _re

    text = sp.RENDERED.read_text(encoding="utf-8")
    blocks = dict(_re.findall(
        r"^## kind: ([\w-]+)\s*\n\n```json\n(.*?)^```", text, _re.M | _re.S))
    prompt = json.loads(blocks["hourly"])["prompt"]
    assert "他に走っている" in prompt and "いません" in prompt, (
        "写しの `hourly` に「他に走っている相手はいません」が書かれていません。"
        "**書いていないと、受け取った側は「調べていないだけ」と区別できません。**"
    )


def test_枝の名前が本文に入る() -> None:
    """**差し込み口の中の差し込み口**（2026-08-25 夜に踏んだ）。

    サブへ移してから `create_session` の `source_revision` が使われなくなり、
    **ワークツリーが `main` から切られる**ようになりました
    （実測: 8/25 夜のサブ3枚が3枚とも、同じ合流を自分でやり直している）。
    型の「最初の1手」がその合流を頼みますが、**`<<lead>>` は段まるごと
    差し込む口**なので、その中の `<<branch>>` は行ごとの置換を通りません。

    **置換が漏れると、受け取った側は `git merge origin/<<branch>>` を
    そのまま読みます。** 枝の名前は `docs/trigger_spec.json` の1か所だけに置き、
    型には書き写さないこと。
    """
    import json
    branch = json.loads(
        (ROOT / "docs" / "trigger_spec.json").read_text(encoding="utf-8"))["branch"]
    for kind in ("hourly", "optimizer"):
        text = sp.build(kind)
        assert "<<branch>>" not in text, f"{kind}: 差し込み口が残っています"
        assert f"git merge origin/{branch}" in text, kind


def test_最初の1手は_どの役でも本文の頭のほうに出る():
    """**「最初の1手」と名乗るものが本文の最後に出ていたら、名前が嘘です**（2026-08-26）。

    この日、枝を合わせる段を1か所へまとめるとき、**まとめ先を
    `_siblings_block()`（＝本文のいちばん下）にしました。** 文言は1つになりましたが、
    「最初の1手」が **58行の本文の 31行目**、`optimizer` では **142行中 99行目**に
    出るようになりました。**受け取る側は上から読みます。**

    だから **文言は1か所（`FIRST_MOVE`）・位置は型の側（`<<first_move>>`）** に分けました。
    ここはその位置を縛ります。
    """
    for kind in sp.KINDS:
        text = sp.build(kind, note="（原文）")
        lines = text.splitlines()
        at = [i for i, ln in enumerate(lines) if "最初の1手" in ln]
        assert at, f"{kind}: 「最初の1手」の段がありません"
        assert at[0] <= max(14, len(lines) // 5), (
            f"{kind}: 「最初の1手」が {at[0]}行目（全 {len(lines)}行）。"
            "**上から読む相手に、最初の1手を最後に見せないこと。**"
            "位置は型の `<<first_move>>` で決めます"
        )


def test_どの役にも差し込み口が残らない():
    """`test_逐語で渡す役には…` は `hourly` / `optimizer` だけを見ています。

    **`<<first_move>>` は4つの型 全部に入った**ので、`owner-*` も見ます。
    段まるごと差し込む口（`<<lead>>`）の中に置いた差し込み口は、
    **行ごとの置換を通りません** —— 2026-08-26 に、まさにそれで
    `<<first_move>>` の6文字が本文に残りました。
    """
    import re as _re
    for kind in sp.KINDS:
        text = sp.build(kind, note="（原文）")
        left = _re.findall(r"<<[^>]*>>", text)
        assert not left, f"{kind}: 埋まっていない差し込み口 {left}"


# --- 最適化の回は、事実より先に「問い」を読む（2026-08-26・オーナー指示）------
#
# オーナー原文: 「毎回最初に新しく考えさせれば？
#                目標に対して主実行を最適化する役にどうやったらできる？って」
#
# **なぜ規則ではなく問いなのか**: 仕組みを置くと、その仕組みの世話が
# 次の回の仕事になります。実測 —— この型は142行まで育ち、撃てと名指ししていた
# 3つの道具は3つとも機械の内臓を印字し、門までの距離（登録者 22/1,000・
# 長尺の総再生時間 1.0/4,000時間）を出す道具は1つもありませんでした。
# 直近7日の ship 249件のうち **201件(81%)が道具と手順**、
# 到達日を動かすと宣言した回は **8%**、前提を閉じる速さは
# **実績 11周に1回 → 見込み 29周に1回** と悪化。
# **サブは渡されたものを正しく直していました。漂流は渡し方の帰結です。**
#
# **この検査が守るのは順番だけです。** 中身（どう答えるか）は毎回サブが決めます。


def test_最適化の回は事実より先に問いを読む():
    out = sp.build("optimizer")
    q = out.find("どうすればなれるか")
    assert q != -1, (
        "最適化の本文から「この役にどうすればなれるか」の問いが消えています。"
        "**仕組みを置くと、その仕組みの世話が次の回の仕事になります**"
        "（2026-08-26 オーナー指示。理由は同節の引用ブロック）"
    )

    # 「いま分かっている事実」より前にあること。埋もれたら効きません。
    facts = out.find("いま分かっている事実")
    assert facts == -1 or q < facts, (
        f"問いが事実の節より後ろにあります（問い {q} / 事実 {facts}）。"
        "**先に読まれる側が勝ちます** —— 事実が先だと、事実が仕事になります"
    )


def test_問いが前の回の答えを読ませる():
    """毎回まっさらに考えるが、**前の答えを見ずに**ではありません。

    見ないと、同じ答えに何度も辿り着くだけで θ は動きません。
    """
    out = sp.build("optimizer")
    assert "docs/JOURNAL.md" in out and "前の回の答え" in out, (
        "問いが「前の回の答えを読め」と言っていません。"
        "**毎回ゼロから考えると、同じ答えを引き直すだけになります**"
    )


def test_問いを捨ててよいと書かない():
    """**この問いには覆る条件がありません**（2026-08-26 夜にオーナーが指摘）。

    最初の版は「答えが毎回変わるのに θ が改善しないなら、
    **問いの立て方のほうが間違っている**」と書いていました。**誤りです。**

    オーナー原文: 「問いごと捨てた後はどうすんの？ 問いは捨てずにやり方変える
    しかなくない？ 最適化させる必要は消えないんだから最初の問いが間違うことある？」

    問いの中身は「**この役はどうすれば役目を果たせるか**」で、
    **役が在るかぎり偽になりません。** 捨てた後に何も残りません。
    **そして「捨ててよい」は逃げ道です** —— 問いが居心地の悪い回がそれを引けば、
    道具いじりに戻れます。**この節が防ごうとしていたもの、そのものです。**

    **覆るのは「答え方」だけ。** それは書いてあること。
    """
    out = sp.build("optimizer")

    # 覆るのが「答え方」だと書いてあること
    assert "答え方" in out, (
        "何が覆るのかが書かれていません。**答えと答え方だけが覆ります**"
    )

    # 「問いのほうが間違い」「問いを捨てる」と**指示している**行を禁じる。
    # **オーナーの引用（`> > ` で始まる行）は対象外** —— そこでこの誤りを
    # 指摘してもらった当の文なので、消したら理由が消えます。
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("> >"):            # オーナー原文の引用
            continue
        if "誤り" in s or "間違いです" in s:  # 誤りだと言っている側
            continue
        for bad in ("問いの立て方のほうが間違", "問いを捨て", "問いごと捨て"):
            if bad in s:
                raise AssertionError(
                    f"問いを捨ててよいと読める行があります: {s[:80]}。"
                    "**最適化する必要は消えないので、捨てた後に何も残りません**"
                )


def test_答えが安定しても問うのをやめないと書いてある():
    """**固定した瞬間、それは仕組みになり、次の回はその世話をします。**"""
    out = sp.build("optimizer")
    assert "毎回問うのはやめない" in out, (
        "「答えが安定しても毎回問う」が書かれていません。"
        "**3回同じだから型に固定してよい、は問いを止める逃げ道でした**"
    )
