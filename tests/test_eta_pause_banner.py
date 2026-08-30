"""`scripts/eta.py` —— **止まっている間、裸の到達日を先に出さないこと。**

## この検査が守っているもの（2026-08-30）

`CLAUDE.md` は、届かないときの印字について次の規則を置いています。

> **裸の「届きません」を出さないこと。**
> 何を固定したせいでそう出たのかを、同じ行に並べること。

**裸の到達日は、その規則の鏡像**です。符号が逆なだけで、同じ欠陥
——「特定の条件で言っているだけなのに、その条件が書いていない」。

実測 2026-08-30、`src/pause_guard` が生成と投稿を塞いでいる状態で、
`headline()` は次を印字していました。

    ### **月20万の到達予測（軌跡）: 2027-01-10**（133日後）
    ### 縛っているのは …… → **この回に引く腕は `per_video`**

**どちらもこの回には引けません。** 腕を引くには本を出す必要があり、
その入口が塞がっているからです。読み手が最初に見るのはこの3行なので
（`headline()` の docstring「最初に見た数字が、その回の入口になります」）、
**塞がっていることは、日付より先に出ないと意味がありません。**

固定するのは次の2つです。

1. **止まっている間、警告が到達日より前に出ること**（順番が逆なら落ちる）
2. **止まっていなければ、この段は自分で黙ること**（平時に雑音を足さない）
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_pause_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


# **最小の payload です。** `headline()` が読むのはこの3つだけ（2026-08-30 に確認）。
# 増えたらここが KeyError で落ちるので、**そのとき足すこと。**
_PL = {"target_date": None, "lever_hint": "per_video", "lever_days": {},
       "binding": "再生数が天井に当たっている"}

# **軌跡を必ず持たせます。** 持たせないと到達日の行が出ず、
# 「警告が日付より前か」の検査が**素通り（vacuous）**になります。
_TR = {"base": {"date": date(2027, 1, 10), "days": 133, "t_work": 47,
                "plan_days": 85, "blocking": []},
       "fast": {"date": date(2026, 12, 20)},
       "slow": {"date": date(2027, 3, 30)}}


def _lines(monkeypatch, *, paused: bool) -> list[str]:
    monkeypatch.setattr(eta.pause_guard, "is_paused", lambda: paused)
    return eta.headline(dict(_PL), None, dict(_TR), None)


def _index(lines: list[str], needle: str) -> int:
    for i, ln in enumerate(lines):
        if needle in ln:
            return i
    return -1


def test_paused_warning_comes_before_any_date(monkeypatch):
    """**止まっている間は、警告が先。** 日付より後ろに落ちたら、読まれません。"""
    lines = _lines(monkeypatch, paused=True)
    warn = _index(lines, "止まっています")
    assert warn >= 0, "止まっているのに、そう書いていない"

    # 到達日の行（出ても出なくても）より前にあること
    date_line = _index(lines, "月20万の到達予測")
    assert date_line >= 0, (
        "到達日の行が出ていない —— この検査が素通りになっている（_TR を見直すこと）")
    assert warn < date_line, (
        "警告が到達日より後ろに出ている —— 最初に見た数字が、その回の入口になる")


def test_paused_names_what_was_frozen(monkeypatch):
    """**何を固定してその日付が出たのかを、同じ所に書くこと。**

    ここでの固定は「収益化の審査に受かる確率 1.0」です。止めた理由が
    まさにそこ（いまの構成が審査の除外側に当たる）なので、これを書かずに
    日付だけ出すと、**落ちる目が無い世界の日付**だと読み手に分かりません。
    """
    body = "\n".join(_lines(monkeypatch, paused=True))
    assert "1.0" in body, "受かる確率を固定していることが書かれていない"
    assert "なりすまし" in body, "止めた理由（人間の実務経歴を名乗る）が書かれていない"
    assert "pause_guard" in body, "どこが塞いでいるのかが名指しされていない"


def test_silent_when_not_paused(monkeypatch):
    """**平時は黙ること。** 常に出る警告は、読まれない警告になります。"""
    body = "\n".join(_lines(monkeypatch, paused=False))
    assert "止まっています" not in body
