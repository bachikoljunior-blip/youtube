"""**床を外しても、その日の1本を置く手は止まらないこと。**（2026-09-04 17:39 に踏んだ）

オーナーが「目標以外全部外して良いよ」と言い、`house_rule.same_day_only()` は
False になりました。**ところが `ahead_sweep.place_today()` は、その1つの述語で
門を作っていた**ので、同じ瞬間に置く手ごと止まりました。実測::

    [today] きょうの1本は置きません —— 規則5 が外れています（この手は規則5 の下だけ）

**外れたのは「先の日付を禁じる」ほうで、「その日の1本を出す」ほうではありません。**
置く手が止まると、枠に本が入るのは**その回が選んだときだけ**に戻ります ——
そこは実測が在ります（09/01 の ship: `fix` 82% ／ `upload` **0件**）。
`CLAUDE.md` の4「**投稿が途切れるのが最大の損失**」。
"""
from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ahead_sweep as _as  # noqa: E402
from src import house_rule  # noqa: E402


def test_置く手は先の日付の禁止とは別の述語で決まる():
    assert hasattr(house_rule, "place_today_on"), \
        "置く手の述語が在りません（`same_day_only()` で代用しないこと）"


def test_床が外れていても置く手は生きている(monkeypatch):
    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", True)
    assert house_rule.same_day_only() is False, "床は外れている前提の検査です"
    assert house_rule.place_today_on() is True, \
        "先の日付を許した瞬間に、その日の1本を置く手まで止まっています"


def test_床を戻しても置く手は生きている(monkeypatch):
    """**どちらの向きでも道連れにしないこと。**"""
    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", False)
    assert house_rule.place_today_on() is True


def test_置く手を止めたいときは自分の旗で止まる(monkeypatch):
    monkeypatch.setattr(house_rule, "PLACE_TODAY_WITHOUT_ASKING", False)
    assert house_rule.place_today_on() is False


def test_呼ぶ側がsame_day_onlyを渡していない():
    """**代用に戻ったら、ここが赤くなります。**"""
    src = inspect.getsource(_as.place_today)
    assert "rule_on=house_rule.place_today_on()" in src, \
        "`place_today` が置く手の述語を渡していません"
    assert "rule_on=house_rule.same_day_only()" not in src, \
        "「先の日付を禁じるか」で「その日の1本を置くか」を決めています"


def test_純関数の側は今までどおり():
    """`today_plan(rule_on=False)` が置かないことは変えていません
    （止めたい回のための口はそのまま残す）。"""
    now = datetime(2026, 9, 4, 3, 0, tzinfo=timezone.utc)
    plan = _as.today_plan(now, count=0, cap=1, candidate={"video_id": "V"},
                          hour=9, quota_open=True, rule_on=False)
    assert plan["do"] is False


def test_残す理由と覆る条件が書いてある():
    """**理由の書いていない規則は、次に来た側が判断できず惰性で残ります**
    （`CLAUDE.md`）。数字と、外してよくなる条件が在ること。"""
    src = inspect.getsource(house_rule)
    head = src.split("PLACE_TODAY_WITHOUT_ASKING", 1)[0][-2000:]
    assert "覆る条件" in src.split("PLACE_TODAY_WITHOUT_ASKING")[0][-2000:] or "覆る条件" in src
    assert "82%" in head and "0件" in head, "残す根拠の実測が書かれていません"
