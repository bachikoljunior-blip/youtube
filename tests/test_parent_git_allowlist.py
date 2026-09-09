"""**親の第1節が「省かないこと」と言う git と、「親がやらないこと」の禁止が食い違わないこと。**

（2026-09-09 11:5x・optimizer・Opus が足した）

**なぜ要るか（実測）**: `docs/trigger_parent.md` の「親がやらないこと（**こちらのほうが大事**）」は
2026-08-10 の `fd55abc7`「親を『子を立てて畳むだけ』に削る（repo を一切触らない）」から
**「`git` を打たない。fetch も commit も push もしない」**のまま置かれていました。
その後、親の手順は2度 変わっています:

    git pull --no-rebase origin <枝>    起きたら最初（**省かないこと**）
    git add … && git commit && git push  2026-09-07 22:4x「記録して押す → そのあと立てる」
                                         （第1節・`scripts/next_round.py` の GO の枝・
                                           検査 `tests/test_parent_record_before_spawn.py`）

**どちらも、禁止の行を書き換えずに足されました。** ＝ 第1節が「省かないこと」と
名指しした手を、「こちらのほうが大事」と題した節が名指しで禁じている状態です
（この repo でいちばん多い壊れ方 ——「言っている所と、している所が別」）。
**禁止の側を読んだ親は、押さずに立てます。** そうなると 22:4x が閉じた穴が2つとも開き直ります
（サブの最初の fetch がこの周の押しに間に合わない／立てているあいだ周が押されない窓で
別の親が GO を読む ＝ 08-25「なんでサブ増えてんの？」）。

**この検査は「両方の節を突き合わせる」側です** —— 片方だけを直しても落ちます。
**陽性対照で測ってあります**（禁止の行を 08/10 の形へ戻すと `test_禁止は全面禁止ではない` が落ち、
第1節から `git push` を消すと `test_第1節のgitが許可の側に全部在る` が落ちる）。

**規則B（名指し）で live です** —— `studio` も親の手続きも import せず、`docs/` を読むだけなので
規則A・規則C のどちらでも引けません（`studio/livetests.EXTRA`）。
"""
from __future__ import annotations

import re
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "docs" / "trigger_parent.md"

#: 第1節が「省かないこと」と言っている git の動詞。
REQUIRED_VERBS = ("pull", "add", "commit", "push")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def _section(title: str) -> str:
    """`## <title>` から次の `## ` までを返す。"""
    body = _text()
    i = body.index(f"## {title}")
    j = body.find("\n## ", i + 1)
    return body[i: j if j != -1 else len(body)]


def _rules(title: str) -> str:
    """節の**規則の行だけ**（`- ` で始まる箇条書きの、その1行目）。

    **経緯を読まないための切り分けです** —— この節は禁止を直した経緯として
    **08/10 の古い行を原文のまま引用**しており（METHOD と同じ「原文は消さない」の形）、
    節を丸ごと突き合わせると**その引用に当たって落ちます**（この検査を書いた回に踏んだ）。
    規則は `- ` の行、経緯はその下の字下げの散文。**両方を混ぜないこと。**
    """
    return "\n".join(ln for ln in _section(title).splitlines() if ln.startswith("- "))


def _allowlist() -> list[str]:
    """許可された git の**行**（字下げした塊の、行頭が `git ` のもの）。

    経緯の散文は行の途中に `git pull` と書くので、**行頭でだけ引きます。**
    """
    forbid = _section("親がやらないこと（**こちらのほうが大事**）")
    return [ln.strip() for ln in forbid.splitlines() if re.match(r"^\s{4,}git ", ln)]


def _first_section() -> str:
    """第1節 ＝ 起動口の節（`git pull` と `--record` の順が書いてある所）。"""
    body = _text()
    i = body.index("### 起動口は2つ")
    j = body.find("\n## ", i + 1)
    return body[i: j if j != -1 else len(body)]


def test_第1節はgitを省かないことと言っている() -> None:
    """出発点。ここが変われば、下の2件の前提も変わる。"""
    first = _first_section()
    assert "git pull --no-rebase origin" in first
    assert "git push" in first
    assert "省かないこと" in first


def test_禁止は全面禁止ではない() -> None:
    """**陽性対照の当のもの** —— 08/10 の「`git` を打たない」に戻すと落ちる。"""
    forbid = _rules("親がやらないこと（**こちらのほうが大事**）")
    assert "fetch も commit も push もしない" not in forbid, (
        "「親がやらないこと」が git を全面禁止しています。"
        "第1節は `git pull` と `git add && git commit && git push` を"
        "「省かないこと」と言っており、正面から食い違います"
        "（2026-08-10 `fd55abc7` の行が、手順の2度の変更に取り残された形）。"
    )
    assert "**`git` を打たない。**" not in forbid


def test_第1節のgitが許可の側に全部在る() -> None:
    """第1節が要求する動詞は、禁止の節の許可リストに1つ残らず載っていること。"""
    first = _first_section()
    allowed = "\n".join(_allowlist())
    assert allowed, "許可リストの塊が空です（字下げした `git …` の行が1つも無い）"
    for verb in REQUIRED_VERBS:
        if not re.search(rf"\bgit {verb}\b", first):
            continue
        assert re.search(rf"\bgit {verb}\b", allowed), (
            f"第1節は `git {verb}` を打たせますが、「親がやらないこと」の"
            f"許可リストに載っていません。片方だけ動かさないこと"
        )


def test_許可は第1節の3つに閉じている() -> None:
    """許可を広げないこと（`merge`・`rebase`・`checkout` は親の手ではない）。"""
    allowed = "\n".join(_allowlist())
    for verb in ("merge", "rebase", "checkout", "reset"):
        assert f"git {verb}" not in allowed, (
            f"`git {verb}` が親の許可に混ざっています"
        )
    assert "それ以外は打たない" in _rules("親がやらないこと（**こちらのほうが大事**）")


def test_覆る条件が書いてある() -> None:
    forbid = _section("親がやらないこと（**こちらのほうが大事**）")
    assert "覆る条件" in forbid
    assert "test_parent_git_allowlist.py" in forbid, (
        "この検査の名前が本文に無いと、次の回は突き合わせが在ることに気づけません"
    )
