"""**印字する側の「その日になってから」が、規則5 の実物に従うこと。**

## なぜ要るか（2026-09-05 05:2x の実測）

規則5（先の日付には1本も置かない）の出どころは `house_rule.same_day_only()` /
`house_rule.may_schedule_ahead()` **1か所**です。ところが **書く直前の関門**
（`refuse_future_publish()` ＝ `videos.update` / `videos.insert` の2か所）しか
そこを通っておらず、**回が最初に読む印字のほう**は規則5 の本文を日本語で
写していました:

    src/daily_pick.py   `[きょうの1本]` 「**09/06（JST）になってから**、その日の枠へ」
    src/next_slot.py    `[次の枠]`/`[下書き]` 「明日になってから」「先の日付を書かないこと」×4

2026-09-04 17:3x のオーナー指示（「目標以外全部外して良いよ」＝
`OWNER_FLOORS_LIFTED = True`）で `same_day_only()` は **False** になりましたが、
写しは条件を持たないので **「待て」と言い続けました。** 同じ時刻の
`scripts/slot_gate.py` は「09/06・09/07 が 0本 ＝ **その日は投稿が途切れます**」
（＝ いま置け）。**同じ与件で、2つの道具が正面から食い違っていた** ——
`slot_gate.py` の冒頭が「この repo でいちばん多い壊れ方」と名指ししている形です。

**この検査が赤くなるのは、また写しが増えたときだけです。**
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from src import daily_pick, house_rule, next_slot

ROOT = Path(__file__).resolve().parents[1]
JST = dt.timezone(dt.timedelta(hours=9))


def test_may_schedule_ahead_is_the_inverse_of_rule5():
    """**出どころは1つ。** 裏返しであること（写しを足したら、ここで気づく）。"""
    assert house_rule.may_schedule_ahead() is (not house_rule.same_day_only())


def test_may_schedule_ahead_follows_the_floor_switch(monkeypatch):
    """床を戻したら、印字の側も**自分で**戻ること（手で直す所を残さない）。"""
    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", False)
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", True)
    assert house_rule.same_day_only() is True
    assert house_rule.may_schedule_ahead() is False
    assert next_slot._ahead_ok() is False

    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", True)
    assert house_rule.may_schedule_ahead() is True
    assert next_slot._ahead_ok() is True


def test_printers_do_not_hardcode_rule5():
    """**「になってから」を、条件なしで書かないこと。**

    許すのは (1) `house_rule.py` 自身（判定の本文が在る所）
    (2) 同じ行／近くに `_ahead_ok(` か `may_schedule_ahead(` か `same_day_only(`
    が在る枝（＝ 実物を読んでいる）。
    """
    bad: list[str] = []
    for rel in ("src/daily_pick.py", "src/next_slot.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "になってから" not in line:
                continue
            if line.lstrip().startswith("#"):
                continue                      # 註は写しではない
            window = "\n".join(lines[max(0, i - 14):i + 14])
            if re.search(r"_ahead_ok\(|may_schedule_ahead\(|same_day_only\(", window):
                continue
            bad.append(f"{rel}:{i + 1}  {line.strip()[:70]}")
    assert not bad, (
        "**規則5 の写しが増えています。**"
        " 判定は `house_rule.may_schedule_ahead()` の1か所です:\n  "
        + "\n  ".join(bad)
    )


def test_ahead_move_note_switches_with_the_rule(monkeypatch):
    """`[きょうの1本]` の `--move` の頭が、規則5 の実物で切り替わること。

    **これが赤いと、回は空いている枠を1日 遅らせます**（実測 2026-09-05 05:2x に
    09/06・09/07 の予約が 0本 だったのに、印は「09/06 になってから」と言っていた）。
    """
    day = (dt.datetime.now(JST) + dt.timedelta(days=1)).date()

    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", True)
    lifted = daily_pick.ahead_move_note(day)
    assert "になってから" not in lifted, lifted
    assert "いま置けます" in lifted, lifted

    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", False)
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", True)
    held = daily_pick.ahead_move_note(day)
    assert "になってから" in held, held
    assert "先の日付には置かない" in held, held


def test_the_note_is_actually_printed():
    """**関数が在るだけでは意味がありません** —— 画面がそれを呼んでいること。

    2026-09-04 の実測に同じ形が在ります（`draft_length_lines()` は在ったのに
    呼び手が `if have:` の中だけで、規則3 が名指しする当の1本の尺が
    **どの回にも見えていなかった**）。
    """
    src = (ROOT / "src" / "daily_pick.py").read_text(encoding="utf-8")
    body = src[src.index("def lines("):]
    assert "ahead_move_note(day)" in body, "`lines()` が `ahead_move_note()` を呼んでいません"
