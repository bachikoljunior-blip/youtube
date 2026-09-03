"""**焼き直しが先。置くのは後**（固定その4 と 規則3 が `--replaces` で衝突していた）。

実測 2026-09-04: 掃き（`ahead_sweep.main`）の中の順は
**`place_today()` → `rebake_today()`** で、置く手のほうが先。置いた瞬間に
`rebake_plan_for()` は「`<ID>` にはもう予約が付いている（`--replaces` が断る側）」で
`do: False` に倒れるので、**同じ掃きの数行 下にある焼き直しが、自分で自分を塞いでいた。**

そのせいで 09:00 に出る `1huadpEk6HY` は 09/03 04:37 に焼いたきりで、
そのあと入った 6件（登録の依頼を画面へ・GPT Image 2.0 の背景ほか）が1つも入っていない。
絵は外の ChatGPT Works が 09/03 20:33 に納品ずみで `assets/images/` に在るのに、
**本に入る道だけが閉じていた。**

待つ長さは `REBAKE_LEAD` と同じもの（新しい定数を作らない）。焼く側は枠まで
`REBAKE_LEAD` を切ったら自分で焼くのをやめるので、**この2つは同じ線の裏表で、
構造上 かみ合わない**（永久に置かれない、は起きない）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts import ahead_sweep

JST = timezone(timedelta(hours=9))
CAND = {"video_id": "V1", "why": "[きょうの1本] 長尺 `t`"}


def _plan(now: datetime, *, rebake_pending: bool) -> dict:
    return ahead_sweep.today_plan(
        now, count=0, cap=1, candidate=CAND, hour=9, quota_open=True,
        rule_on=True, paused="", insert_ok=True, rebake_pending=rebake_pending)


def test_焼き直しが要る本は枠が遠いあいだ置かない() -> None:
    # 03:15 JST・枠 09:00 ＝ 345分 先（`REBAKE_LEAD` 100分 より遠い）
    plan = _plan(datetime(2026, 9, 4, 3, 15, tzinfo=JST), rebake_pending=True)
    assert plan["do"] is False
    assert "--replaces" in plan["why"]
    # **どの本を、いつの枠へ置くつもりだったか**は残すこと（画面から消さない）
    assert plan["video_id"] == "V1"
    assert plan["when"] == "2026-09-04T09:00"


def test_枠が近づいたら焼き直しを待たずに置く() -> None:
    # 08:00 JST・枠 09:00 ＝ 60分 先（`REBAKE_LEAD` 100分 の内側 ＝ 焼く側も焼かない）
    plan = _plan(datetime(2026, 9, 4, 8, 0, tzinfo=JST), rebake_pending=True)
    assert plan["do"] is True
    assert plan["video_id"] == "V1"


def test_焼き直しが要らない本は前と同じに置く() -> None:
    plan = _plan(datetime(2026, 9, 4, 3, 15, tzinfo=JST), rebake_pending=False)
    assert plan["do"] is True
    assert plan["when"] == "2026-09-04T09:00"


def test_既定は前の形のまま() -> None:
    """`rebake_pending` を渡さない呼び手（検査・古い口）は、1ミリも変わらないこと。"""
    plan = ahead_sweep.today_plan(
        datetime(2026, 9, 4, 3, 15, tzinfo=JST), count=0, cap=1, candidate=CAND,
        hour=9, quota_open=True, rule_on=True, paused="", insert_ok=True)
    assert plan["do"] is True


def test_待つ線は焼く側と同じ定数() -> None:
    """別々の数にしないこと —— ずれた瞬間に「永久に置かれない」か「焼く暇が無い」になる。"""
    lead = ahead_sweep.REBAKE_LEAD
    just_outside = datetime(2026, 9, 4, 9, 0, tzinfo=JST) - lead - timedelta(minutes=1)
    just_inside = datetime(2026, 9, 4, 9, 0, tzinfo=JST) - lead + timedelta(minutes=1)
    assert _plan(just_outside, rebake_pending=True)["do"] is False
    assert _plan(just_inside, rebake_pending=True)["do"] is True
