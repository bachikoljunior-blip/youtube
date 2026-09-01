"""**間隔の分母は「周」であること**（2026-09-01・最適化の回に撃って直した）。

## 何が壊れていたか（撃って出た数）

`pace()` は「1周いくら ＝ 使用% ÷ 分母」で持続できる間隔を出し、
`next_round.decide()` はそれを**「前の周の開始から何分」**と比べます
＝ **周から周**です。ところが分母は `data/quota.jsonl` の**サブの誕生数**でした。

    枠 08/29 07:00 → 09/01 11:55 JST（76.9時間・使用 73%）
      quota.jsonl の誕生   …… **2件**  → 1周 36.500% → 生の間隔 289.7時間
      rounds.jsonl の周    …… **48件** → 1周  1.521% → 生の間隔  12.1時間
      runs.jsonl のサブ    …… **109体**（1周に 2.27体。**周ではない**）

**数え落とし自体は安全側**（分母が小さい ＝ 間隔が長い）ですが、
`FLOOR_MAX_CLAMP` が 289.7時間 を **90分** へ叩き落としていたので、
`next_round.py` は `間隔 90分（quota.py の実測）` と印字していました ——
**90 は実測ではなく定数**で、周単位の真値 **459分**（直近の区間）より
**5.1倍 速い側**です。

ここで見るのは4つ:

  1. 分母が `rounds.jsonl` の周であること
  2. サブの誕生数（周より多い ＝ 速すぎる側）へは落ちないこと
  3. 歯止めで切られたら `floor_clipped` が立ち、生の数が渡ること
  4. 歯止めの上限が、オーナーの固定規則（1日1本）を守れる線であること
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone

from src.config import ROOT

spec = importlib.util.spec_from_file_location("quota", ROOT / "scripts" / "quota.py")
quota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quota)


def _write(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def test_laps_counts_distinct_rounds(tmp_path, monkeypatch):
    """`rounds.jsonl` の `round` の別数を数える。**1周の複数の役は1件。**"""
    p = tmp_path / "rounds.jsonl"
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    _write(p, [
        {"at": (t0 + timedelta(minutes=i)).isoformat(), "role": role, "round": rid}
        for i, (role, rid) in enumerate([
            ("hourly", "r1"), ("optimizer", "r1"),
            ("hourly", "r2"), ("optimizer", "r2"),
            ("hourly", "r3"),
        ])
    ])
    monkeypatch.setattr(quota, "ROUNDS_LOG", p)
    got = quota._laps_between(t0 - timedelta(hours=1), t0 + timedelta(hours=1))
    assert got == 3, f"周は3件のはずが {got}（役の数を数えていないか）"


def test_denominator_is_rounds_not_subagents(tmp_path, monkeypatch):
    """**周 ＜ サブ。** サブを分母にすると `per_lap` が小さく ＝ 速すぎる側。"""
    rounds = tmp_path / "rounds.jsonl"
    runs = tmp_path / "runs.jsonl"
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    _write(rounds, [{"at": t0.isoformat(), "role": "hourly", "round": f"r{i}"}
                    for i in range(4)])
    _write(runs, [{"at": t0.isoformat(), "session": f"s#{i}"} for i in range(20)])
    monkeypatch.setattr(quota, "ROUNDS_LOG", rounds)
    monkeypatch.setattr(quota, "RUNS_LOG", runs)
    got = quota._births_between([], t0 - timedelta(hours=1), t0 + timedelta(hours=1))
    assert got == 4, f"周の 4件 を採るはずが {got}（サブの 20体 に落ちていないか）"


def test_rounds_outside_the_window_are_not_counted(tmp_path, monkeypatch):
    p = tmp_path / "rounds.jsonl"
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    _write(p, [
        {"at": (t0 - timedelta(days=3)).isoformat(), "round": "old"},
        {"at": t0.isoformat(), "round": "new"},
    ])
    monkeypatch.setattr(quota, "ROUNDS_LOG", p)
    assert quota._laps_between(t0 - timedelta(hours=1), t0 + timedelta(hours=1)) == 1


def test_missing_rounds_log_falls_back_to_quota_not_to_subagents(tmp_path, monkeypatch):
    """周が数えられなければ `quota.jsonl` の誕生へ。**サブへは落ちない。**

    どちらも数え落としますが、**数え落としは間隔を長くする側**なので、
    落ちても鎖は速くなりません。
    """
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    runs = tmp_path / "runs.jsonl"
    _write(runs, [{"at": t0.isoformat(), "session": f"s#{i}"} for i in range(20)])
    monkeypatch.setattr(quota, "ROUNDS_LOG", tmp_path / "missing.jsonl")
    monkeypatch.setattr(quota, "RUNS_LOG", runs)
    assert quota._laps_between(t0 - timedelta(days=1), t0 + timedelta(days=1)) == 0
    rows = [{"session_id": "a", "born_at": t0.isoformat()},
            {"session_id": "b", "born_at": t0.isoformat()}]
    got = quota._births_between(rows, t0 - timedelta(days=1), t0 + timedelta(days=1))
    assert got == 2, f"quota.jsonl の 2件 へ落ちるはずが {got}"


def test_clipped_floor_is_reported_not_passed_off_as_measured(tmp_path, monkeypatch):
    """**歯止めで切られたら、切られたと言うこと。**

    `next_round.py` はこの欄を見て `（quota.py の実測）` と名乗るのをやめます。
    """
    usage = tmp_path / "usage.jsonl"
    runs = tmp_path / "runs.jsonl"
    reset = datetime(2026, 9, 5, 22, 0, tzinfo=timezone.utc)
    anchor = reset - timedelta(hours=90)
    _write(usage, [{"fetched_at": anchor.isoformat(), "window_id": "seven_day",
                    "used_percent": 90, "resets_at_iso": reset.isoformat()}])
    # 周1件・使用90% ＝ 1周 90% → 生の間隔は歯止めよりはるかに大きい
    _write(runs, [{"at": anchor.isoformat(), "round": "r1"}])
    monkeypatch.setattr(quota, "USAGE_LOG", usage)
    monkeypatch.setattr(quota, "ROUNDS_LOG", runs)
    monkeypatch.setattr(quota, "LOG", tmp_path / "quota.jsonl")
    p = quota.pace(now=anchor + timedelta(minutes=1))
    assert p is not None
    assert p["floor_clipped"] == "max", p["floor_clipped"]
    assert p["floor_raw"] > quota.FLOOR_MAX_CLAMP
    assert p["floor_min"] == quota.FLOOR_MAX_CLAMP


def test_clamp_still_lets_the_house_rule_run():
    """**歯止めの上限は、1日1本（`src/house_rule.py`）を守れる線であること。**

    歯止めの役目は「計器が壊れても鎖を止めない」ことなので、
    **止まらない条件のほうから決めます。** 1日に最低2回 起きられれば、
    規則の1本は出せます。90分 にはこの根拠がありませんでした。
    """
    from src.house_rule import PUBLISH_PER_DAY
    assert PUBLISH_PER_DAY == 1
    wakes_per_day = 24 * 60 / quota.FLOOR_MAX_CLAMP
    assert wakes_per_day >= 2, (
        f"上限 {quota.FLOOR_MAX_CLAMP:.0f}分 では1日に "
        f"{wakes_per_day:.1f}回 しか起きられません（1日1本 が出せない）")
