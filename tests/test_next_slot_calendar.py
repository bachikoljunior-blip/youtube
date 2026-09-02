"""**予約の暦が規則（1日1本）と別なら、毎周の最初の画面で鳴ること。**

## なぜこの検査が要るか（2026-09-01 夜・最適化の回）

実測（`data/uploaded.jsonl`・2026-09-01 20:0x）: **09/05 〜 09/23 の 19日、
予約が1本も入っていません。** その手前も 09/03 が空で、
**今後23日のうち20日が空**（実際の密度 0.09本/日 ＝ 規則の 9%）。
一方 09/24 以降は 1日 7〜13本（規則の 7〜13倍）。

**この形は、どの道具の画面にも出ていませんでした。**

    scripts/eta.py      到達日を `PLAN_PUBLISH_PER_DAY = 1` で**解いて**いる
                        （＝ 規則が守られている前提。暦を1日も見ない）
    scripts/queue_lag.py 入れ替えは **(日,時刻) の集合を1つも変えない**ので、
                        空いている日は視野の外。同時刻の実測で
                        「合計 0日／入れ替え 0手」＝ **鳴らない**
    src/next_slot.lines() **次の1本**しか見ない。その後ろが19日 空でも出ない

**投稿が途切れるのが最大の損失**（`CLAUDE.md`「4. 投稿を途切れさせないこと」）
なのに、途切れることが**誰の画面にも出ない**状態でした。

## 発火を確かめてあること（**発火したことのない検査は検査ではない**）

下の `test_hole_fires` は、19日の穴を注入して `[!]` が出ることを見ます。
`test_quiet_when_rule_is_kept` は、1日1本きっかりの暦で `[!]` が出ないことを見ます。
**片方だけだと、常に鳴る／常に黙る実装が通ります。**
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import next_slot  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)   # 09/01 20:00 JST


def _ledger(tmp_path, days: dict[str, int]) -> Path:
    """`YYYY-MM-DD -> 本数` から控えを作る（`at` は JST 09:00 を UTC で書く）。"""
    p = tmp_path / "uploaded.jsonl"
    rows = []
    n = 0
    for day, cnt in sorted(days.items()):
        for i in range(cnt):
            n += 1
            at = datetime.strptime(day, "%Y-%m-%d").replace(
                hour=9 + i, tzinfo=JST).astimezone(timezone.utc)
            rows.append({"video_id": f"v{n:04d}", "topic": f"t-{n}",
                         "title": f"題 {n}",
                         "at": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "uploaded_at": "2026-08-25T00:00:00+00:00"})
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


def _one_per_day(start: str, n: int) -> dict[str, int]:
    d = datetime.strptime(start, "%Y-%m-%d").date()
    return {(d + timedelta(days=i)).strftime("%Y-%m-%d"): 1 for i in range(n)}


@pytest.fixture()
def legacy(monkeypatch):
    """**規則5 が入る前の枝**（「暦の穴が欠陥」）を試すための札。

    2026-09-02 にオーナーが「現在の日付にしか予約しない」を固定したので、
    既定の枝は逆になりました。**下の枝を消していないのは、規則5 が外れたら
    そこへ戻るからです** —— 消すと、戻す先が無くなります。
    """
    from src import house_rule
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", False)
    return house_rule


def test_quiet_when_rule_is_kept(tmp_path, legacy):
    """**1日1本きっかりなら鳴らないこと。** 常に鳴る実装をここで落とします。"""
    p = _ledger(tmp_path, _one_per_day("2026-09-02", 20))
    c = next_slot.calendar(now=NOW, path=p)
    assert c["empty"] == 0, c
    assert c["over"] == [], c
    out = next_slot.calendar_lines(now=NOW, path=p)
    assert out and "[!]" not in out[0], out


def test_hole_fires(tmp_path, legacy):
    """**実測の形（手前が空・後ろが作り置き）を注入して、発火を確かめる。**"""
    days = {"2026-09-01": 1, "2026-09-02": 1, "2026-09-04": 1}
    days.update({"2026-09-24": 7, "2026-09-27": 11, "2026-10-07": 13})
    p = _ledger(tmp_path, days)
    c = next_slot.calendar(now=NOW, path=p)
    # 09/05 〜 09/23 の 19日
    assert c["run"] == 19, c
    assert c["run_from"] == "2026-09-05", c
    assert [d for d, _ in c["over"]] == ["2026-09-24", "2026-09-27", "2026-10-07"], c
    out = next_slot.calendar_lines(now=NOW, path=p)
    assert out[0].startswith("[!]"), out
    body = "\n".join(out)
    assert "19日 連続" in body, body
    # **当てどころまで出ること**（分類で終わらせない）
    assert "reschedule.py --compact" in body, body


# ---------------------------------------------------------------- 規則5（固定その4）
#
# **2026-09-02、オーナーが「現在の日付にしか予約しないってことだからね？」と固定しました。**
# 上の3件が見ている「暦の穴」は、**この規則の下では欠陥ではありません** ——
# 先の日付が空であることが正しい状態で、**先の日付に予約が在るほうが欠陥**です。
#
# **片方だけを検査にしないこと。** 下は
#
#     ・規則5 の下で、先の予約が **在る** → 鳴る／当てどころは `pool_drain --keep 0`
#     ・規則5 の下で、先の予約が **無い** → 鳴らない（穴は正常）
#     ・規則5 の下で、否定された手（`reschedule --compact --apply`）を**名指ししない**
#
# の3つを見ます。上の `legacy` 札と合わせて、**枝が入れ替わったことまで**縛ります。


def test_same_day_rule_fires_on_stockpile(tmp_path):
    """**先の日付に予約が在ったら鳴ること**（規則5・既定の枝）。"""
    days = {"2026-09-01": 1, "2026-09-02": 1, "2026-09-04": 1}
    days.update({"2026-09-24": 7, "2026-09-27": 11, "2026-10-07": 13})
    p = _ledger(tmp_path, days)
    c = next_slot.calendar(now=NOW, path=p)
    assert c["same_day_only"] is True, c
    # NOW は 09/01 20:00 JST ＝ 今日は 09/01。**明日（09/02）以降が全部 欠陥**
    assert c["ahead"] == 1 + 1 + 7 + 11 + 13, c
    assert c["ahead_days"] == 5, c
    assert c["ahead_first"] == "2026-09-02", c
    assert c["ahead_last"] == "2026-10-07", c
    assert c["ahead_top"] == ("2026-10-07", 13), c
    out = next_slot.calendar_lines(now=NOW, path=p)
    assert out[0].startswith("[!]"), out
    body = "\n".join(out)
    assert "pool_drain.py --apply --keep 0" in body, body
    # **否定された手を名指ししないこと**（撃つと欠陥が増えます）
    assert "reschedule.py --compact --apply  #" not in body, body
    assert "日 が空" not in body, body


def test_same_day_rule_is_quiet_when_calendar_is_empty(tmp_path):
    """**先の日付が空なら鳴らないこと。** 穴は正常です（規則5）。

    常に鳴る実装をここで落とします —— この検査が無いと、
    「`ahead` が 0 でも `[!]` を出す」実装が通ってしまいます。
    """
    # **今日ぶんの1本だけが予約に在る、正しい姿**（09/02 08:00 JST に立って見る）
    today_only = datetime(2026, 9, 1, 23, 0, tzinfo=timezone.utc)
    p = _ledger(tmp_path, {"2026-09-02": 1})
    c = next_slot.calendar(now=today_only, path=p)
    assert c["ahead"] == 0, c
    out = next_slot.calendar_lines(now=today_only, path=p)
    assert out and "[!]" not in out[0], out
    assert "正しい状態です" in out[0], out


def test_near_window_is_not_the_average(tmp_path, legacy):
    """**平均は後ろの作り置きに持ち上げられます。**（1発目の実装がここで外れた）

    実測の1発目は「今後39日の平均 **2.77本/日 ＝ 規則の 277%**」と印字しました ——
    **19日 連続で空なのに「規則より多い」と読める形**です。
    縛っているのは**空白が終わるまでの窓**なので、そちらを別に出します。
    """
    days = {"2026-09-01": 1, "2026-09-02": 1, "2026-09-04": 1}
    days.update({"2026-09-24": 7, "2026-09-27": 11, "2026-10-07": 13})
    p = _ledger(tmp_path, days)
    c = next_slot.calendar(now=NOW, path=p)
    assert c["near_until"] == "2026-09-23", c
    assert c["near_days"] == 22, c          # 09/02 〜 09/23（今日は数えない）
    assert c["near_density"] < 0.2, c       # 実物は規則の 1割 未満
    # **平均は、手前の実物の 5倍 以上に見えます** ＝ 平均で読むと符号を誤ります
    assert c["density"] > c["near_density"] * 5, c
    body = "\n".join(next_slot.calendar_lines(now=NOW, path=p))
    assert "縛っているのは手前です" in body, body


def test_no_reservations_is_silent(tmp_path):
    """**予約が1本も無い回は黙ること**（`[次の枠]` の側が既に言っています）。"""
    p = tmp_path / "uploaded.jsonl"
    p.write_text("", encoding="utf-8")
    assert next_slot.calendar_lines(now=NOW, path=p) == []


def test_rule_comes_from_house_rule():
    """**上限の出どころは1か所**（`src/house_rule.py`）。写しを持たないこと。"""
    from src import house_rule
    c = next_slot.calendar(now=NOW)
    assert c["rule"] == max(1, int(house_rule.PUBLISH_PER_DAY))


def test_wired_into_the_first_screen():
    """**毎周いちばん最初に出る画面に載っていること。**

    `run_marker.py --write` が `next_slot.lines()` を呼びます
    （`scripts/run_marker._next_slot_lines()`）。ここが外れると、
    暦は測れているのに**誰も見ない**状態に戻ります。
    """
    src = (ROOT / "src" / "next_slot.py").read_text(encoding="utf-8")
    assert "cal = calendar_lines(now=now)" in src, "lines() が暦を呼んでいません"
    assert "out = list(cal) + [" in src, "暦が `[次の枠]` より前に出ていません"
    rm = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    assert "next_slot.lines()" in rm, "run_marker が next_slot.lines() を呼んでいません"
