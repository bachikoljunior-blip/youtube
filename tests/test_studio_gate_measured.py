"""扉(b) を、前提ではなく**報告の台帳**で測る（2026-09-19 03:xx・optimizer・Opus 5・1周1体）。

**何を挟むか**: `rev_deadline` / `slot_value` の扉(b) は **「再生 × 分/回」**から出ており、
その 分/回 は自分で「前提で、実測ではありません」と書いています（`REV_LONG_MIN_PER_VIEW`）。
**ところが扉(b) の通貨そのもの（視聴時間・登録）は `data/studio/reporting.jsonl` に
実物が載っています**（`watch_time_minutes` / `subscribers_gained`）。
＝ **測れる数を前提で置いていた**、というのがこの回の 1件目です。

**この検査が押さえるのは 4つ**:
  1. **ショートの視聴時間が扉(b) に入らない**こと（GOAL (4-g) 1）——
     入れてしまうと距離が 20倍 近く短く出ます（実測 131.3時間 対 7.4時間）
  2. `days_to_hours` が **long の 時間/日 だけ**から出ること
  3. **陽性対照** —— long の視聴時間だけを動かすと、距離が実際にその向きへ動くこと
     （「差がありませんでした」は計器が死んでいても同じ字で出るため）
  4. **前提の側（`ifpeer`）が実測と混ざらないこと** ＝ 別の袋に入っていること

決めと覆る条件は `studio/trend.gate_measured` の註と `docs/METHOD.md` §5。
"""
import json

import pytest

from studio import trend


def _reporting(tmp_path, rows):
    p = tmp_path / "reporting.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def _row(date, vid, views, wmin, sg=0):
    return {"date": date, "video_id": vid, "views": views,
            "watch_time_minutes": wmin, "subscribers_gained": sg, "subscribers_lost": 0}


@pytest.fixture()
def fake(monkeypatch, tmp_path):
    """報告の台帳と `_forms()` を差し替える（**disk も API も触りません**）。"""
    from studio import reporting

    def _install(rows, forms):
        p = _reporting(tmp_path, rows)
        monkeypatch.setattr(reporting, "STORE", p, raising=False)
        monkeypatch.setattr(reporting, "load_rows", lambda path=None: [
            json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()])
        monkeypatch.setattr(reporting, "_forms", lambda: forms)
        return _install
    return _install


def test_ショートの視聴時間は扉bに入らない(fake):
    """短いほうを 100倍 にしても、扉(b) までの日数は 1日 も動かないこと。"""
    forms = {"S1": True, "L1": False}
    base = [_row("20260901", "S1", 1000, 100.0), _row("20260901", "L1", 10, 60.0)]
    fake(base, forms)
    a = trend.gate_measured()
    fake([_row("20260901", "S1", 1000, 10_000.0), _row("20260901", "L1", 10, 60.0)], forms)
    b = trend.gate_measured()
    assert a["days_to_hours"] == b["days_to_hours"], "ショートの視聴が扉(b) に入っています"
    assert a["long_hours"] == pytest.approx(1.0)
    assert b["by_form"]["short"]["hours"] == pytest.approx(166.6667, rel=1e-3)


def test_陽性対照_長尺の視聴時間を動かすと距離が動く(fake):
    """計器が生きていることを先に測る（長尺を 2倍 にすると日数は半分）。"""
    forms = {"L1": False}
    fake([_row("20260901", "L1", 10, 60.0)], forms)
    a = trend.gate_measured()
    fake([_row("20260901", "L1", 10, 120.0)], forms)
    b = trend.gate_measured()
    assert a["days_to_hours"] == pytest.approx(b["days_to_hours"] * 2, rel=1e-6)


def test_日数は台帳に在る日の数で割る(fake):
    """同じ視聴時間でも、窓が 2日 なら 時間/日 は半分になること。"""
    forms = {"L1": False}
    fake([_row("20260901", "L1", 10, 60.0)], forms)
    one = trend.gate_measured()
    fake([_row("20260901", "L1", 5, 30.0), _row("20260902", "L1", 5, 30.0)], forms)
    two = trend.gate_measured()
    assert one["days"] == 1 and two["days"] == 2
    assert two["long_hours_per_day"] == pytest.approx(one["long_hours_per_day"] / 2)


def test_前提の側は別の袋に入っている(fake):
    """`ifpeer` は**前提**で、実測（`long_hours_per_day`）と混ざらないこと。"""
    forms = {"L1": False}
    fake([_row("20260901", "L1", 10, 60.0)], forms)
    g = trend.gate_measured()
    ip = g["ifpeer"]
    assert ip["views"] == trend.GATE_IF_PEER_VIEWS
    assert ip["hours_per_day"] != g["long_hours_per_day"], "前提が実測の欄に入っています"
    # 前提の 時間/日 は 再生/本 × 枠 × 分/回 ÷ 60 の 1本道
    assert ip["hours_per_day"] == pytest.approx(
        trend.GATE_IF_PEER_VIEWS * trend.SLOTS_PER_DAY * trend.GATE_IF_PEER_MIN / 60.0)


def test_行は実測と前提の両方を字で名指しする(fake):
    """読む側が 1つ の数に混ぜられないよう、行に **実測** と **前提** が両方 出ること。"""
    forms = {"S1": True, "L1": False}
    fake([_row("20260901", "S1", 1000, 100.0, sg=3), _row("20260901", "L1", 10, 60.0)], forms)
    line = trend.gate_measured_line(None)
    assert "実測" in line and "前提" in line
    assert "扉(b) に 1秒も入りません" in line
