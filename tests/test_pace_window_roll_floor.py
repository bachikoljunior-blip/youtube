"""**枠が「本当に回った」直後に、床がまるごと消えていた回**（2026-09-12 08:1x に踏んだ）。

`_gauge_reset()` が見つけるのは「**同じ枠の中で**%が戻された」回だけです
（2026-09-02 の実物 ＝ `resets_at_iso` が動かないまま 73% → 3%）。
**`resets_at_iso` が 7日 進んだ回 ＝ 本当のリセットは、そこに引っかかりません。**

実物（`data/usage.jsonl`）::

    09/11 19:23 JST  88%   resets 09/11 22:00Z（＝ 09/12 07:00 JST）
    09/12 07:20 JST   0%   resets 09/18 22:00Z   ← **枠ごと回った**

この回の `pace()` は

    used   = 0%（新しい枠の目盛り）
    births = 0（枠の頭 07:00 から目盛りの 07:20 までに周は立っていない）
    pre    = None（`_gauge_reset()` が None ＝ 床が当たらない）

となり、`per_lap` も `floor_min` も None。**下流が 4つ とも黙りました**::

    next_round.floor_minutes()     → FALLBACK_MIN（90分）。実測できていた床は 54.6分
    spawn_prompt._quota_block()    → 【枠】の段を**まるごと落とす**
    quota.pace_report()            → 「誕生を1件も数えられていません」だけ
    short_words / margin_line / sweep_verdict / clamp_eta → 何も言わない

＝ **枠が戻った回は、新しい目盛りが貼られるほうが、貼られないより悪い**という形でした
（貼られなければ `pace()` の `rolled` の枝が、前の枠の `per_lap` でそのまま運びます）。
親は実際に **90分**（`data/parent_wakes.jsonl` の `source` が「目盛りが無いか…」）で回り、
**枠がいちばん空いている刻に、鎖がいちばん遅く**なっていました（オーナー 09/11 19:4x
「フェイブルずっと使えるように調整するよな？」＝ 枠は配って使い切る側）。

固定するのは4つ:

  1. 枠ごと回った回も、**前の枠で測れていた `per_lap` を床に当てる**
     （1周の重さは枠が戻っても軽くならない ＝ `_per_lap_before` の註）
  2. **`rate` には当てない** —— 新しい枠は本当に 0% から始まっている
  3. `--pace` は、`births` が 0 でも**床が在れば印字する**
  4. 「いまの間隔のまま」が読めない回も、**「床に従えば」と門の判定は印字する**
     （§5 15:1x の門 98% が当てるのは床の側・13:1x）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402

UTC = timezone.utc

OLD_RESET = "2026-09-11T22:00:00Z"                        # 09/12 07:00 JST
NEW_RESET = "2026-09-18T22:00:00Z"                        # 09/19 07:00 JST
OLD_START = datetime(2026, 9, 4, 22, 0, tzinfo=UTC)       # 09/05 07:00 JST
OLD_AT_1 = "2026-09-11T12:38:00+09:00"
OLD_AT_2 = "2026-09-11T19:23:00+09:00"
NEW_AT = "2026-09-12T07:20:00+09:00"
NOW_AT = "2026-09-12T08:15:00+09:00"


@pytest.fixture(autouse=True)
def _restore():
    usage, log, rounds = quota.USAGE_LOG, quota.LOG, quota.ROUNDS_LOG
    yield
    quota.USAGE_LOG, quota.LOG, quota.ROUNDS_LOG = usage, log, rounds


def _write(tmp_path, anchors, *, laps_per_hour=1.0):
    usage = tmp_path / "usage.jsonl"
    usage.write_text("".join(json.dumps({
        "fetched_at": at, "window_id": "seven_day",
        "used_percent": used, "resets_at_iso": rst,
    }) + "\n" for at, used, rst in anchors), encoding="utf-8")

    # **周は枠の頭ちょうどには立ちません**（実物の 09/12 の枠も、頭 07:00 から
    # 目盛りの 07:20 までに 1周も立っていない ＝ `births` 0）。30分 ずらして並べる。
    step = timedelta(hours=1 / laps_per_hour)
    rows, born = [], OLD_START + timedelta(minutes=30)
    end = datetime.fromisoformat(NOW_AT).astimezone(UTC)
    while born <= end:
        rows.append({"at": born.isoformat(), "role": "hourly", "round": born.isoformat()})
        born += step
    log = tmp_path / "quota.jsonl"
    log.write_text("", encoding="utf-8")
    rounds = tmp_path / "rounds.jsonl"
    rounds.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    quota.USAGE_LOG, quota.LOG, quota.ROUNDS_LOG = usage, log, rounds


def _now():
    return datetime.fromisoformat(NOW_AT).astimezone(UTC)


def _rolled(tmp_path):
    _write(tmp_path, [(OLD_AT_1, 83, OLD_RESET),
                      (OLD_AT_2, 88, OLD_RESET),
                      (NEW_AT, 0, NEW_RESET)])
    return quota.pace(_now())


def test_枠ごと回った回は_gauge_reset_では見つからない(tmp_path):
    """**この前提が崩れたら、下の 3件 は別の理由で通ります。**"""
    p = _rolled(tmp_path)
    assert p["reset_at"] is None, "同じ枠の中の戻しではない ＝ ここは None が正しい"
    assert p["births"] == 0, "新しい枠の頭から目盛りまでに周は立っていない"


def test_枠ごと回っても1周の重さは前の枠から床が当たる(tmp_path):
    p = _rolled(tmp_path)
    assert p["per_lap"], "床が当たらないと `floor_min` ごと消える（この回に踏んだ形）"
    assert p["per_lap_floored"] is True
    assert p["pre"] is not None
    assert p["pre"]["at"] == datetime.fromisoformat(OLD_AT_2)
    assert p["per_lap"] == pytest.approx(p["pre"]["per_lap"], rel=1e-9)


def test_床が出れば持続できる間隔も出る(tmp_path):
    p = _rolled(tmp_path)
    assert p["floor_min"] is not None
    assert p["floor_min"] == pytest.approx(p["per_lap"] / p["forward_rate"] * 60, rel=1e-6)
    assert p["floor_min"] < 90.0, "FALLBACK_MIN（90分）より速い側でなければ、直した意味がない"


def test_速さの側には床を当てない(tmp_path):
    """**新しい枠は本当に 0% から始まっています。** ここに前の枠の %/時 を当てると、
    推定が上に外れ、`used_now` が実測でないぶんだけ膨らみます。"""
    p = _rolled(tmp_path)
    assert p["rate_floored"] is False
    assert p["used_now"] == pytest.approx(0.0, abs=1e-9)


def test_普通の枠は1つも動かない(tmp_path):
    """**陽性対照の裏側** —— 枠が回っていない回で床を当ててしまうと、
    測れている `per_lap` が前の枠の数に押し上げられます。"""
    _write(tmp_path, [(OLD_AT_1, 83, OLD_RESET), (OLD_AT_2, 88, OLD_RESET)])
    p = quota.pace(datetime.fromisoformat(OLD_AT_2).astimezone(UTC))
    assert p["per_lap_floored"] is False
    assert p["pre"] is None


def test_pace_report_は床を印字する(tmp_path, capsys):
    """**METHOD が指している口はこちら**（「空欄を『余裕がある』と読まないこと —— `--pace`」）。"""
    _rolled(tmp_path)
    quota.pace_report(_now())
    out = capsys.readouterr().out
    assert "誕生を1件も数えられていません" not in out
    assert "持続できる間隔" in out
    assert "床に従えば" in out, "§5 15:1x の門（98%）が当てるのは床の側"
    assert "いまの間隔のまま **読めません**" in out, "空欄で出さないこと"
