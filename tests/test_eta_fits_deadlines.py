"""**期限を寄せ直す道具が、毎周ちゃんと撃たれること。**（`eta._fit_deadlines`）

## この検査が守っているもの（2026-08-30・最適化の回に実測して足した）

`scripts/deadline_check.py` は **2026-08-25 から**在り、`--shrink` / `--extend` /
`--fit` まで実装されています。ところが実測 2026-08-30::

    grep -c deadline_check docs/trigger_main.md   →  **0**

**314KB の手順に、この道具の名前が1度も出ていませんでした。** 撃つ側だけが無い。
そのあいだに溜まっていたもの::

    データは揃うのに期限が先    **2件・合計 50日**
    データが来る前に期限がある  **3件・合計 6日**

**この 50日 は、到達日がまるごと止まっていた日数です。** `scripts/eta.py` 自身が
「**軌跡の腕は、前提を1件 閉じたときだけ動く**」と印字するので、データが揃っていても
期限が先なら腕は1日も動きません。そして到達日をいちばん大きく動かすのは
**θ（前提が閉じる速さ）**です（同じ回の実測: θ×2 で **-25日**／天井で **-50日**）。

## **印字は撃たれません**

`scripts/status.py` は 2026-08-25 から「縮めること」と印字していて、
`tests/test_deadline_check.py::test_遅すぎる期限が残っていないこと` は
**赤で止めていました**（実測: この配線を入れるまで赤のまま）。
**赤い検査が在るのに誰も撃たない** —— それがここで塞いだ穴です。

だから配線は文書ではなく**道具の側**に置きました。`scripts/eta.py` は
`CLAUDE.md`「毎回の実行で必ずやること」1 で**毎周いちばん最初に撃たれる**ので、
そこに乗せれば、手順を読み飛ばした回でも寄せ直しが起きます。
（`scripts/eta.py` の冒頭が、同じ判断を同じ言葉で書いています ——
「**文書に手順として書くだけでは飛ばされます**」）

## 固定するのは4つ

1. `eta.main()` が、報告を出す道で `_fit_deadlines()` を**撃っている**
2. **`--offline` では撃たない**（積んだ点から読むだけの回に 42秒 を足さない）
3. 動かした件があれば**その行を返す**（黙って動かさない ＝ 次の回が気づけない）
4. **`deadline_check` が落ちても回を止めない** —— `eta.py` は
   「予測で回を止めない」を既定にしています。ここが門になって回が死ぬと、
   失うのは 50日 より大きい

## 覆る条件

- 寄せ直しを `eta.py` から外して別の入口（Stop フックなど）へ移すなら、
  **この検査ごと移すこと。** 外すだけにしないこと ——
  そうすると 2026-08-25〜08-30 と同じ「道具は在るが撃たれない」に戻ります
- **毎周 1件以上 動く**のが常態になったら、疑うのは配線ではなく
  `deadline_check.Verdict.slack`（帯）の幅です
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eta as E  # noqa: E402


# --- 1・2: 配線されていること（そして `--offline` では撃たないこと） ----------

def test_main_が寄せ直しを撃っている():
    """**道具が在るだけでは 0 です。** `main()` から呼ばれていること。"""
    src = inspect.getsource(E.main)
    assert "_fit_deadlines()" in src, (
        "`eta.main()` が `_fit_deadlines()` を撃っていません —— "
        "2026-08-25〜08-30 と同じ『道具は在るが撃たれない』に戻っています"
    )


def test_offline_では撃たない():
    """積んだ点から読むだけの回に、42秒 を足さないこと。"""
    lines = inspect.getsource(E.main).split("\n")
    at = next(i for i, ln in enumerate(lines) if "_fit_deadlines()" in ln)
    #: 撃つ行の**すぐ手前 3行**のどこかで `--offline` を外していること。
    guard = "\n".join(lines[max(0, at - 3):at])
    assert "args.offline" in guard, (
        "`--offline` の道でも寄せ直しを撃っています（42秒 のむだ）。"
        f" 撃つ行の手前3行: {guard!r}"
    )


# --- 3: 動かしたら、その行を返すこと -----------------------------------------

class _Mod:
    """`deadline_check` の代役（`shrink` / `extend` だけ持つ）。"""

    def __init__(self, shrunk=(), extended=(), boom: bool = False):
        self._s, self._e, self._boom = list(shrunk), list(extended), boom

    def shrink(self):
        if self._boom:
            raise RuntimeError("台帳が読めません")
        return self._s

    def extend(self):
        return self._e


def test_動かした件は行にして返す(monkeypatch):
    monkeypatch.setattr(E, "_deadline_check_mod",
                        lambda: _Mod(shrunk=[("帯の中の位置", "2026-11-10", "2026-09-08")],
                                     extended=[("刻みは速すぎる", "2026-10-05", "2026-10-06")]))
    got = E._fit_deadlines()
    body = "\n".join(got)
    assert "2件" in body, "何件 動かしたかが出ていません"
    assert "2026-11-10 → **2026-09-08**" in body, "縮めた側が行に出ていません"
    assert "2026-10-05 → **2026-10-06**" in body, "延ばした側が行に出ていません"
    assert "falsified_if" in body, "**条件は触っていない**と明示していません（誤読される）"


def test_動かす件が無ければ黙る(monkeypatch):
    """**普通の回は 0件 です。** そのとき頭を汚さないこと。"""
    monkeypatch.setattr(E, "_deadline_check_mod", lambda: _Mod())
    assert E._fit_deadlines() == []


# --- 4: 落ちても回を止めない --------------------------------------------------

def test_落ちても回を止めない(monkeypatch):
    """**門を増やさないこと。** 例外を投げずに、そう言う行を返すだけ。"""
    monkeypatch.setattr(E, "_deadline_check_mod", lambda: _Mod(boom=True))
    got = E._fit_deadlines()
    assert got, "黙って飲み込んでいます（撃てなかったことが誰にも見えません）"
    assert "回は止めません" in "\n".join(got)
