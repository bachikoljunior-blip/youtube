"""**誕生の分母は `data/runs.jsonl` からも数えること**（2026-09-01・最適化の回）。

## 何が壊れていたか（撃って出た数）

`pace()` は「1周いくら ＝ 使用% ÷ 誕生数」で持続できる間隔を出します。
その誕生数を `data/quota.jsonl` だけから数えていましたが、**あの台帳に
誕生が入るのは `list_sessions` の返りを `--ingest` で写した回だけ**で、
毎周ではありません。実測::

    枠 08/29 07:00 → 09/01 11:55 JST（76.9時間・使用 73%）
      quota.jsonl から       …… 誕生   **2件** → 1周 36.500% → 間隔 289.7時間
      data/runs.jsonl から   …… 誕生 **109件** → 1周  0.670% → 間隔   5.3時間

**×54 の食い違い**です。そして `FLOOR_MAX_CLAMP` が 289.7時間 を **90分** へ
叩き落としていたので、呼ぶ側（`next_round.py`）は
`間隔 90分（quota.py の実測）` と印字していました —— **90 は実測ではなく定数**で、
区間で数えた真値 **174分** より **1.9倍 速い側**です。
**2つの欠陥が打ち消し合って、たまたま「速すぎる」に着地していました。**

ここで見るのは3つ:

  1. `runs.jsonl` の誕生が数に入ること（多いほうを採る）
  2. 歯止めで切られたら `floor_clipped` が立ち、生の数が渡ること
  3. 歯止めの上限が、オーナーの固定規則（1日1本）を守れる線であること
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


def test_births_counts_distinct_sessions_in_runs(tmp_path, monkeypatch):
    """`runs.jsonl` の別セッションを数える。**同じ回の複数行は1件。**"""
    p = tmp_path / "runs.jsonl"
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    _write(p, [
        {"at": (t0 + timedelta(minutes=i)).isoformat(), "session": s}
        for i, s in enumerate(["s#a", "s#a", "s#b", "s#c", "s#c", "s#c"])
    ])
    monkeypatch.setattr(quota, "RUNS_LOG", p)
    got = quota._births_from_runs(t0 - timedelta(hours=1), t0 + timedelta(hours=1))
    assert got == 3, f"別セッションは3件のはずが {got}"


def test_births_between_takes_the_larger_source(tmp_path, monkeypatch):
    """**多いほうを採る。** 数え落とすと 1周 が過大 ＝ 速すぎる側に出るため。"""
    p = tmp_path / "runs.jsonl"
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    _write(p, [{"at": (t0 + timedelta(minutes=i)).isoformat(), "session": f"s#{i}"}
               for i in range(9)])
    monkeypatch.setattr(quota, "RUNS_LOG", p)
    quota_rows = [{"session_id": "old", "born_at": t0.isoformat()}]
    got = quota._births_between(quota_rows, t0 - timedelta(hours=1),
                                t0 + timedelta(hours=1))
    assert got == 9, f"runs.jsonl の 9件 を採るはずが {got}"


def test_births_outside_the_window_are_not_counted(tmp_path, monkeypatch):
    p = tmp_path / "runs.jsonl"
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    _write(p, [
        {"at": (t0 - timedelta(days=3)).isoformat(), "session": "old#a"},
        {"at": t0.isoformat(), "session": "new#a"},
    ])
    monkeypatch.setattr(quota, "RUNS_LOG", p)
    assert quota._births_from_runs(t0 - timedelta(hours=1),
                                   t0 + timedelta(hours=1)) == 1


def test_missing_runs_log_is_zero_not_an_error(tmp_path, monkeypatch):
    """読めなければ 0。**呼ぶ側が `max()` するので、元の数へ戻るだけ。**"""
    monkeypatch.setattr(quota, "RUNS_LOG", tmp_path / "does-not-exist.jsonl")
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert quota._births_from_runs(t0 - timedelta(days=1), t0) == 0


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
    # 誕生1件・使用90% ＝ 1周 90% → 生の間隔は歯止めよりはるかに大きい
    _write(runs, [{"at": anchor.isoformat(), "session": "s#a"}])
    monkeypatch.setattr(quota, "USAGE_LOG", usage)
    monkeypatch.setattr(quota, "RUNS_LOG", runs)
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
