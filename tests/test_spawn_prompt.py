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
    assert "他に走っている子は" in alone
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
