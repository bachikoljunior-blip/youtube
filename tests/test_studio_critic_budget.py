# -*- coding: utf-8 -*-
"""`critic.budget` —— **`claude -p` の待ち時間を、渡す字の長さで伸ばす**。

2026-09-16 00:2x（optimizer・Fable・ultracode）に足した。実測: 長尺 8本目（113コマ・5,532字）の
`crosscheck` が **300秒 の定数で TimeoutExpired**（`critique` は 5周 とも通った ＝ 落ちるのは
説明欄と notes まで渡す `crosscheck` の側から）。

**陽性対照つき**（門が本当に効いているかを、逆向きに撃って確かめる）。
"""
from __future__ import annotations

import studio.critic as critic


def test_短い本は床のあたりに収まる():
    # 90秒 のショート（約480字 ＋ 問いの字）は、床の 300秒 をわずかに越えるだけ
    assert critic.budget("x" * 480) == 348
    assert critic.budget("") == 300


def test_長い本は字に比例して伸びる():
    # 5,500字 の本 ＝ 300 + 550 = 850秒（300秒 の定数では落ちていた側）
    assert critic.budget("x" * 5500) == 850
    assert critic.budget("x" * 5500) > 300


def test_上限で止まる():
    assert critic.budget("x" * 1_000_000) == 1200


def test_単調に増える():
    vals = [critic.budget("x" * n) for n in (0, 1000, 5000, 9000, 20000)]
    assert vals == sorted(vals)


def test_陽性対照_床と上限を入れかえると壊れる():
    """**この検査が本当に `budget` を見ているか**を、逆向きに撃って確かめる。"""
    assert critic.budget("x" * 5500, floor=300, cap=400) == 400   # 上限が効く
    assert critic.budget("", floor=999) == 999                    # 床が効く


def test_crosscheck_と_critique_が_budget_を_使っている():
    """**定数 300 に戻したら落ちる**（この検査が守っている当のもの）。"""
    src = open(critic.__file__, encoding="utf-8").read()
    assert 'ask(p, "sonnet", budget(p))' in src
    assert 'ask(p, "sonnet", 300)' not in src
