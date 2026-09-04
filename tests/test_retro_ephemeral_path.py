"""**申し送りが「これを読め」と書いても、次の回には無いファイルを名指しする。**

## なぜ要るか（2026-09-04 に、**実測 2件**を踏んで足した）

`retro.py` の持ち越しは「言及 N回 ／ 実物に当たった M回」を出し、
`tool_suspect()` が「N が伸びて M が伸びないなら、**その語を出している道具の側**を
先に疑え」と印を付けます。**そこに 3つ目の理由が抜けていました。**

    `tail -5 data/rebake.log`   5周 運ばれて 実物に当たった **0回**
    `data/ahead_sweep.log`      5周 運ばれて 実物に当たった **0回**

**どちらも `.gitignore` に載っています** ＝ 枝に乗らないので、次の回の
コンテナには前の回の中身がありません。実測 2026-09-04 10:0x の回の頭:
`data/rebake.log` は**ファイルそのものが在りませんでした**（焼きが走っていない間は
誰も書かない）。`data/ahead_sweep.log` は `SessionStart` が書き直すので在りますが、
**前の回の行は1行も入っていません。**

**道具は正しく、申し送りのほうが実行不能でした。** 5周 とも「いちばん先に
`tail -5 data/rebake.log`」と書かれ、5周 とも読めていません。これは
「難しくて潰せない」でも「道具が間違っている」でもなく、
**書いた回にしか読めないものを、次の回への指示にしていた**という第3の形です。

固定するのは3つ:

1. **枝に乗らないパスを名指しした語は、そう出ること**
2. **枝に乗るパス（`data/daily_pick.jsonl` など）は出ないこと**（誤検出は雑音）
3. **その語に「道具の側を疑え」の印を当てないこと** —— 読めない語の M/N には
   情報が1ビットも入っていません（`tool_suspect()` の `sunk` と同じ理由）
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("retro_eph_mod", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retro)


def test_実物の_gitignore_に載っているパスを名指しする():
    """**実物の `.gitignore` で撃つこと**（型を検査の中に写すと、外れた日に気づけない）。"""
    hit = retro.ephemeral_paths("tail -5 data/rebake.log")
    assert [p for p, _ in hit] == ["data/rebake.log"], hit

    hit = retro.ephemeral_paths("`data/ahead_sweep.log` の `[today]`")
    assert [p for p, _ in hit] == ["data/ahead_sweep.log"], hit


def test_枝に乗るパスは出さないこと():
    """**誤検出は雑音**。`data/daily_pick.jsonl` は追跡されているので、次の回も読めます。"""
    assert retro.ephemeral_paths("data/daily_pick.jsonl") == []
    assert retro.ephemeral_paths("data/rebake.jsonl") == []
    assert retro.ephemeral_paths("config/hypotheses.yaml") == []


def test_パスでない語を拾わないこと():
    """`first_comment_posted` は欄の名前、`place_today()` は関数。**どちらもファイルではありません。**"""
    for tok in ("first_comment_posted", "ahead_sweep.place_today()",
                "src/rpm_mix.surface_ceiling()", "python -m pytest -q tests/",
                "REBAKE_LEAD", "**差し替えました**"):
        assert retro.ephemeral_paths(tok) == [], tok


def test_いま在るかを返すこと():
    """**在っても「この回が作ったぶん」です。** 呼ぶ側がそう書けるよう、真偽を返します。"""
    got = retro.ephemeral_paths("data/kienai.log と data/nai.log",
                                patterns=("data/kienai.log", "data/nai.log"),
                                root=ROOT)
    assert dict(got) == {"data/kienai.log": False, "data/nai.log": False}, got


def test_読めない語に道具を疑えの印を当てないこと():
    """`tool_suspect()` の `sunk` と同じ理由 —— **M は構造的に 0** で、情報が入っていません。

    ここが False にならないと、持ち越しの行が
    「5周 運ばれて実物に当たったのは 0回 —— 道具の側を先に疑うこと」と出ます。
    **道具は正しい**ので、開いた回はそのぶん空振りします（実測 5周）。
    """
    n = retro.SUSPECT_MENTIONS + 2
    assert retro.tool_suspect(n, 0, sunk=False) is True     # 印が付く既定
    assert retro.tool_suspect(n, 0, sunk=True) is False     # 読めない語は当てない


def test_印字に出ること():
    """**関数が正しくても、印字に出なければ誰も読みません**（この repo が何度も踏んだ形）。"""
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    assert "次の回には残りません" in src, "持ち越しの行に印が出ていない"
    assert "sunk=_sinks(tok) or bool(eph)" in src, (
        "読めない語が `tool_suspect()` の除外に入っていない —— "
        "同じ行で『道具を疑え』と『次の回には残りません』が両方 出ます")
