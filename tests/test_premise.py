"""`src/premise.py` —— 節が「画面に出しようがない前提」を持っていないか。

**故障注入を両向きに掛けます。** 当たりを見つけることと、
**当たっていないものを鳴らさないこと**は別の性質で、片方だけでは
「全部鳴らす検査」と区別がつきません（`docs/JOURNAL.md` 2026-08-16）。
"""
from __future__ import annotations

import importlib
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

import src.calc as C
from src import premise

ROOT = Path(__file__).resolve().parent.parent


def _calc_names() -> list[str]:
    return sorted(mi.name for mi in pkgutil.iter_modules(C.__path__)
                  if not mi.name.startswith("_"))


def _run(name: str) -> str:
    proc = subprocess.run([sys.executable, "-m", f"src.calc.{name}"],
                          capture_output=True, text=True, timeout=300, cwd=ROOT)
    assert proc.returncode == 0, f"src.calc.{name} が落ちました: {proc.stderr[-400:]}"
    return proc.stdout


# ---- 書き方の同一視 ------------------------------------------------------

def test_万と億と桁区切りを同じ値として見る():
    assert "4,600,000" in premise.forms(4_600_000)
    assert "460万" in premise.forms(4_600_000)
    # **億を落とすと souzoku が誤報になります**（見出しが「1億5000万円」）
    assert "1億5000万" in premise.forms(150_000_000)
    assert "1億" in premise.forms(100_000_000)


# ---- 故障注入（当たる側） ------------------------------------------------

_HIDDEN = '''
def table(income):
    return [{"段": 1, "額": income // 10}]

if __name__ == "__main__":
    print("\\n=== 段ごとの額 ===")
    for row in table(4_600_000):
        print(f"  段{row['段']}  {row['額']:,}円")
'''

_SHOWN = '''
def table(income):
    return [{"段": 1, "額": income // 10}]

if __name__ == "__main__":
    print("\\n=== 段ごとの額 ===")
    print(f"  前提の年収 {4_600_000:,}円")
    for row in table(4_600_000):
        print(f"  段{row['段']}  {row['額']:,}円")
'''


def test_節を決めている値が出ていなければ鳴る():
    out = "=== 段ごとの額 ===\n  段1  460,000円\n"
    problems = premise.invisible(_HIDDEN, out)
    assert len(problems) == 1
    assert "4,600,000" in problems[0]


def test_同じ値が節に出ていれば鳴らない():
    out = "=== 段ごとの額 ===\n  前提の年収 4,600,000円\n  段1  460,000円\n"
    assert premise.invisible(_SHOWN, out) == []


def test_別の節に出ていても鳴る():
    """**stdout 全体で見てはいけません。** 1節＝1本なので、
    別の節に出ていても、その動画を書く側には届きません。"""
    out = ("=== 年収べつ ===\n  年収 4,600,000円  節税 90,000円\n"
           "\n=== 段ごとの額 ===\n  段1  460,000円\n")
    problems = premise.invisible(_HIDDEN, out)
    assert len(problems) == 1


# ---- 故障注入（鳴らしてはいけない側） ------------------------------------

_REUSED_NAME = '''
def a(x):
    return [{"v": x}]

def b():
    return [{"v": 1}]

if __name__ == "__main__":
    print("\\n=== ひとつめ ===")
    for row in a(300_000):
        print(f"  {row['v']:,}円")

    print("\\n=== ふたつめ ===")
    for row in b():
        print(f"  {row['v']}")
'''


def test_使い回しの名前が前の節の値を持ち越さない():
    """`row` や `r` は節をまたいで使われます。**前の節の値を
    次の節の濡れ衣にしないこと**（2026-08-17 に `zangyo` で踏んだ）。"""
    out = ("=== ひとつめ ===\n  300,000円\n"
           "\n=== ふたつめ ===\n  1\n")
    assert premise.invisible(_REUSED_NAME, out) == []


_BOUND_BEFORE_NEXT = '''
class W:
    def __init__(self, base):
        self.base = base

def grid(w):
    return [{"v": w.base}]

if __name__ == "__main__":
    print("\\n=== みだしだけ ===")
    print("  何も計算していません")

    w = W(base=250_000)
    print("\\n=== 表 ===")
    print(f"  前提 250,000円")
    for row in grid(w):
        print(f"  {row['v']:,}円")
'''


def test_束ねただけの行は置かれている節の持ち物にならない():
    """`w = W(base=250_000)` が節の**後ろ**に置かれ、**次の節で**使われる
    書き方が実物にあります（`zangyo`）。値を使っていない節を鳴らさないこと。"""
    out = ("=== みだしだけ ===\n  何も計算していません\n"
           "\n=== 表 ===\n  前提 250,000円\n  250,000円\n")
    assert premise.invisible(_BOUND_BEFORE_NEXT, out) == []


def test_千円未満は見ない():
    src = '''
def t(n):
    return [{"v": n}]

if __name__ == "__main__":
    print("\\n=== 小さい定数 ===")
    for row in t(12):
        print(f"  {row['v']}か月")
'''
    out = "=== 小さい定数 ===\n  12か月\n"
    assert premise.invisible(src, out) == []


# ---- 実データ（calc 24本ぜんぶ） ----------------------------------------

@pytest.mark.parametrize("name", _calc_names())
def test_実物の全ての節が前提を画面に出している(name: str):
    """**これが赤いときは、その calc から作った動画が追試できません。**

    直し方は2つ。行に列として足すか、節の見出し／前提の行に書くこと。
    **検査のほうを緩めないこと** —— 前提を画面に出すのはこの作りの根幹です
    （`CLAUDE.md`「前提と計算式を、画面と説明欄に全部出す」）。
    """
    mod = importlib.import_module(f"src.calc.{name}")
    holes = premise.scan(mod.__file__, _run(name))
    assert holes == [], "\n".join(holes)
