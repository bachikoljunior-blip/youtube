"""`scripts/fast_tests.py` —— **判定が、いちばん下に無かった。**

## なぜ要るか（2026-08-30 06:1x の実測）

この道具が出した最後の12行:

    ...............F........................................................ [ 55%]
    ........................................................................ [ 69%]
    ...................................................
    [fast_tests] **これは全体の検査ではありません。** …
    [fast_tests] 全体は `python scripts/fast_tests.py --all`（16分）。…

**`F` が1つ出ているのに、名前がどこにもありません。**
`pytest -q` は落ちた名前を進捗の**後ろ**に出しますが、この道具はそのあとに
自分の2行を足すので、**端末で `| tail -N` すると名前だけが押し出されます**
（この repo の走らせ方は必ず尾を読みます）。結果、**赤い走りと緑の走りが、
いちばん下だけ見ると同じ顔**になります。

この道具の docstring は自分でこう言っています ——
「**16分の検査は、実質 走っていない検査です**」。
**判定が尾に無い検査も、実質 走っていない検査**です。同じ形の1段 上です。

実測: あの `F` の名前を突き止めるのに、**別の走りを7本**（約35分）使いました。

## ここで固定するもの

1. **緑なら「緑」と、いちばん下で言う**
2. **赤なら件数と名前を、いちばん下で言う**（`FAILED …` / `ERROR …` を拾う）
3. **名前が拾えなくても「赤」とは言う**（書式が変わっても、判定は消えない）

## 覆る条件

`pytest` の短い要約の書式（`FAILED tests/x.py::y`）が変わったら 2 は空になります。
そのときも 3 が残ります。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "fast_tests_mod", ROOT / "scripts" / "fast_tests.py")
ft = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ft)


def test_緑はいちばん下で緑と言う(capsys):
    ft._verdict(0, [])
    out = capsys.readouterr().out
    assert "**緑**" in out
    assert out.strip().splitlines()[-1].startswith("[fast_tests]")


def test_赤は件数と名前をいちばん下で言う(capsys):
    ft._verdict(1, ["FAILED tests/test_x.py::test_y - AssertionError",
                    "FAILED tests/test_z.py::test_w"])
    out = capsys.readouterr().out
    assert "**赤 2件**" in out
    assert "tests/test_x.py::test_y" in out
    assert "tests/test_z.py::test_w" in out
    # **名前の無い赤を残さないための1行**（次に来た側が読む先）。
    assert "docs/JOURNAL.md" in out


def test_名前が拾えなくても赤とは言う(capsys):
    ft._verdict(1, [])
    out = capsys.readouterr().out
    assert "**赤**" in out
    assert "名前が拾えませんでした" in out


def test_落ちた行だけを拾う():
    """進捗の点や見出しを名前として数えないこと。"""
    lines = [".....F....  [ 55%]\n", "FAILED tests/a.py::t - boom\n",
             "=== short test summary info ===\n", "ERROR tests/b.py::u\n",
             "1 failed, 2 passed\n"]
    got = [l.rstrip() for l in lines if l.startswith(("FAILED ", "ERROR "))]
    assert got == ["FAILED tests/a.py::t - boom", "ERROR tests/b.py::u"]
