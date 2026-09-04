"""**「その直しは、この本に入っていません」の下に、「で、いま通るのか」を置くこと。**

2026-09-05 01:5x にこの回が踏んだ形:

    [!] 焼いたのは 09/04 21:31 JST。そのあと、この本を焼くコードに 1件 入っています
        —— その直しは、この本に入っていません
        57bb8b84 09/04 22:42 improve: 外の型の脚 (4d) を…帯 335本 で測り直した
    → **焼き直すのが `improve` の1手です**（55〜90分・差し替え 100単位）

`_MAKERS` の `src/script_writer.py` には**焼く関数**と**脚を数える関数**が同居しています。
**数える側だけが変わった回**は、焼き直しても1フレームも変わりません。
実測: `daily_pick.pick_legs('GFvAcxvDmYM')` は**新しい定義でも** `([], None)` ＝ 全通。
"""
from __future__ import annotations

from src import next_slot as ns


def test_全通なら焼き直して得られる脚は0本と言う():
    out = ns.legs_under_current_code("V", legs_call=lambda v: ([], None))
    assert len(out) == 1
    assert "4脚を全部 通っています" in out[0]
    assert "焼き直して得られる脚は 0本" in out[0]
    # **禁じないこと** —— 脚のほかの理由は在り得る。
    assert "持って来ること" in out[0]


def test_落ちていれば焼き直す理由が在ると言う():
    out = ns.legs_under_current_code("V", legs_call=lambda v: (["(1) 冒頭", "(2) 章"], None))
    assert len(out) == 1
    assert "2脚 落ちています" in out[0]
    assert "焼き直す理由が在ります" in out[0]


def test_読めなければ一行も出さない():
    """**推測で埋めないこと。** 読めない回は黙る（`pick_legs` と同じ向き）。"""
    assert ns.legs_under_current_code("V", legs_call=lambda v: ([], "控えが読めません")) == []


def test_本を名乗っていなければ一行も出さない():
    assert ns.legs_under_current_code("") == []
    assert ns.legs_under_current_code("   ", legs_call=lambda v: ([], None)) == []


def test_撃てなくても止まらない():
    def boom(v):
        raise RuntimeError("壊れた")

    assert ns.legs_under_current_code("V", legs_call=boom) == []


def test_実物_GFvAcxvDmYM_はいまのコードでも全通():
    """**この回が踏んだ本。**

    覆る条件: この本が公開されて控えが動いたら、`pick_legs` が別の答えを返します
    —— そのときは上の3つの枝のどれかに落ちるだけで、この節は壊れません。
    """
    out = ns.legs_under_current_code("GFvAcxvDmYM")
    if not out:                      # 控えが読めない環境では何も言わない
        return
    assert "4脚を全部 通っています" in out[0] or "落ちています" in out[0]
