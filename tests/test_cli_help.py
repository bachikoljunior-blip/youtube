"""**道具が自分の使い方を言えるか。**（2026-08-20 09:3x に踏んだ）

## なぜ要るか

この回、`batch_build.py --help` を叩いたら**引数の一覧ではなく traceback** が出ました。

    ValueError: unsupported format character '?' (0x304c) at index 31

argparse は help の文字列を `% params` に掛けます（`--help` を**組み立てるとき
だけ**）。だから **`%` を1つ書くと、その道具は使い方を言えなくなります。**
書いた側は気づきません —— `--help` を叩くまで、他の全部が普通に動くからです。

**踏んだ2つは、どちらも毎周の道具でした**（`batch_build.py` は生成そのもの、
`quota.py` は §2 で必ず叩きます）。前の回の設計の見直し（§6 (a2)）は
**直近9件のうち6件で「手順の読み」と「何を出すか決めるところ」が最大の時間食い**
だと書いています。`--help` が落ちると、その読みは**1,000行のソース**に移ります。

## ここで見ていること

**1つの `%` を直すのではなく、この種類を閉じます。**
`scripts/` の中で argparse を使っている道具は、**全部 `--help` が出ること。**
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _argparse_scripts() -> list[Path]:
    """**一覧を手で持たないこと。** 足した道具が黙って外れます。"""
    out = []
    for p in sorted(SCRIPTS.glob("*.py")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if "ArgumentParser(" in text:
            out.append(p)
    return out


def test_argparse_を使う道具を1つは見つけている():
    """**空を全部緑と読まないため。**（走査が壊れたら、この検査は黙ります）"""
    got = _argparse_scripts()
    assert len(got) >= 10, f"走査が壊れています（{len(got)}件）"


@pytest.mark.parametrize("script", _argparse_scripts(), ids=lambda p: p.name)
def test_使い方を言える(script: Path):
    got = subprocess.run([sys.executable, str(script), "--help"],
                         capture_output=True, text=True, timeout=120)
    assert got.returncode == 0, (
        f"{script.name} --help が落ちます（{got.returncode}）。"
        f"**help の中の `%` は `%%` と書くこと**:\n{got.stderr[-800:]}")
    assert "usage:" in got.stdout, f"{script.name} が使い方を出していません"
