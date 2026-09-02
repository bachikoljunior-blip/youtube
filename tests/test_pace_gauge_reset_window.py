"""**枠は動かないまま、目盛りだけ戻された回**（2026-09-02 10:43 JST に踏んだ）。

オーナーの画面で週の枠がリセットされ、`data/usage.jsonl` はこうなりました:

    09/01 11:55 JST  73%   resets 09/05 07:00 JST
    09/02 10:43 JST   3%   resets 09/05 07:00 JST   ← **枠は同じ。%だけ戻った**

`pace()` は枠の頭を `resets - 7日` ＝ **08/29 06:59** から取ります。すると

    分子  リセット後の **3%**（＝ 09/01 11:55 以降のぶんだけ）
    分母  08/29 から数えた **99.7時間・58周**

と**窓が食い違い**、1周 **0.052%** ＝ 持続できる間隔が **10分** に潰れました。
通算 0.030 %/時・「100% 到達は 01/14」も同じ食い違いから出ています。
**09/01 に直した「歯止めが実測を潰す」と同じ形で、こちらは窓のほうです。**

固定するのは4つ:

  1. **リセットを見つけること**（同じ枠・%が減った）
  2. **分子と分母の窓を揃えること** —— 分母もリセットから数え直す
  3. **それが下限だと言うこと** —— リセットの瞬間は測れないので、
     いちばん広い窓 ＝ いちばん多い周 ＝ **`per_lap` は最小**に出る。
     だから**リセット前に測れていた数を床に当てる**
     （1周の重さは、枠が戻っても軽くなりません）
  4. **床を当てたことを呼ぶ側へ渡すこと**（`*_floored` / `*_raw`）
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
JST = timezone(timedelta(hours=9))

RESET_ISO = "2026-09-04T22:00:00Z"                       # 09/05 07:00 JST
WIN_START = datetime(2026, 8, 28, 22, 0, tzinfo=UTC)     # 08/29 07:00 JST
PRE_AT = "2026-09-01T11:55:00+09:00"
NOW_AT = "2026-09-02T10:43:00+09:00"


@pytest.fixture(autouse=True)
def _restore():
    usage, log = quota.USAGE_LOG, quota.LOG
    yield
    quota.USAGE_LOG, quota.LOG = usage, log


def _write(tmp_path, anchors, *, births_per_hour=0.6):
    """`anchors` は `(fetched_at, used_percent, resets_iso)` の並び（新しい順は問わない）。

    誕生は枠の頭から一定間隔で並べる（実物と同じ密度: 99.7時間で58件 ≒ 0.58/時）。
    """
    usage = tmp_path / "usage.jsonl"
    usage.write_text("".join(json.dumps({
        "fetched_at": at, "window_id": "seven_day",
        "used_percent": used, "resets_at_iso": rst,
    }) + "\n" for at, used, rst in anchors), encoding="utf-8")

    step = timedelta(hours=1 / births_per_hour)
    rows, born = [], WIN_START
    end = datetime.fromisoformat(NOW_AT).astimezone(UTC)
    i = 0
    while born <= end:
        rows.append({"seen_at": born.isoformat(), "born_at": born.isoformat(),
                     "session_id": f"session_{i:03d}", "tags": ["youtube-hourly"]})
        born, i = born + step, i + 1
    log = tmp_path / "quota.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    quota.USAGE_LOG, quota.LOG = usage, log


def _now():
    return datetime.fromisoformat(NOW_AT).astimezone(UTC)


def test_同じ枠で目盛りが減ったらリセットとして見つける(tmp_path):
    _write(tmp_path, [(PRE_AT, 73, RESET_ISO), (NOW_AT, 3, RESET_ISO)])
    p = quota.pace(_now())

    assert p["reset_at"] is not None, "同じ枠で 73%→3% はリセット。見落とすと窓が食い違う"
    assert p["reset_at"] == datetime.fromisoformat(PRE_AT).astimezone(UTC)
    assert p["reset_from"] == 73


def test_分母もリセットから数え直す(tmp_path):
    """**これが潰れていた所。** 分子はリセット後・分母は枠ぜんぶ、では 1周が 1/5 に出る。"""
    _write(tmp_path, [(PRE_AT, 73, RESET_ISO), (NOW_AT, 3, RESET_ISO)])
    p = quota.pace(_now())

    span = (datetime.fromisoformat(NOW_AT) - datetime.fromisoformat(PRE_AT))
    assert p["hours"] == pytest.approx(span.total_seconds() / 3600, abs=0.05)
    assert p["hours"] < 24, "枠の頭（99.7時間）から数えていたら、また潰れている"
    # 枠そのものの表示は本物の枠のまま（計測の窓とは別物）
    assert p["window_start"] == WIN_START


def test_リセット直後の1周は下限で床が当たる(tmp_path):
    """リセットの瞬間は測れない。**採っているのは窓の下限 ＝ 周の上限 ＝ 1周の最小。**

    枠が戻っても1周の重さは軽くならないので、**リセット前に測れていた数を床**に置く。
    床を当てたことは `per_lap_floored` / `per_lap_raw` で外へ出す。
    """
    _write(tmp_path, [("2026-09-01T06:14:00+09:00", 69, RESET_ISO),
                      (PRE_AT, 73, RESET_ISO), (NOW_AT, 3, RESET_ISO)])
    p = quota.pace(_now())

    assert p["per_lap_floored"] is True
    assert p["per_lap_raw"] < p["per_lap"], "床は、測って出た下限より上でなければ意味がない"
    assert p["rate_floored"] is True
    assert p["rate_raw"] < p["rate"]
    assert p["pre"]["per_lap"] == pytest.approx(p["per_lap"], rel=1e-6)


def test_区間はリセットをまたがない(tmp_path):
    """またいだ差は「使った量」ではない。3% と 73% の差を区間にしないこと。"""
    _write(tmp_path, [(PRE_AT, 73, RESET_ISO), (NOW_AT, 3, RESET_ISO)])
    p = quota.pace(_now())
    assert p["seg"] is None


def test_リセットが無ければ何も変わらない(tmp_path):
    """**普通の回を壊していないこと。** %が増えているだけなら窓は枠の頭のまま。"""
    _write(tmp_path, [(PRE_AT, 40, RESET_ISO), (NOW_AT, 45, RESET_ISO)])
    p = quota.pace(_now())

    assert p["reset_at"] is None
    assert p["per_lap_floored"] is False
    assert p["rate_floored"] is False
    assert p["hours"] == pytest.approx(
        (datetime.fromisoformat(NOW_AT).astimezone(UTC) - WIN_START).total_seconds() / 3600,
        abs=0.05)
    assert p["seg"] is not None, "同じ枠の2点は区間になる"


def test_写し違いの1分で別の枠に化けないこと(tmp_path):
    """`resets_at` は手で写されます。**21:59 と 22:00 が混ざっています**（実物）。

    `==` で比べていたので、同じ枠の2点が「別の枠」に化け、区間もリセットも
    見えませんでした。分のずれは許すこと。
    """
    _write(tmp_path, [(PRE_AT, 73, "2026-09-04T22:00:00Z"),
                      (NOW_AT, 3, "2026-09-04T21:59:00Z")])
    p = quota.pace(_now())
    assert p["reset_at"] is not None, "1分の写し違いでリセットを見落としてはいけない"


def test_潰れていた数を再現し直った数と並べる(tmp_path):
    """**回帰の本体。** 実物と同じ形で、間隔が 10分 に潰れないこと。"""
    _write(tmp_path, [("2026-09-01T06:14:00+09:00", 69, RESET_ISO),
                      (PRE_AT, 73, "2026-09-04T22:00:00Z"),
                      (NOW_AT, 3, "2026-09-04T21:59:00Z")])
    p = quota.pace(_now())

    assert p["floor_min"] > quota.FLOOR_MIN_CLAMP, (
        "歯止めの下限に貼りついている ＝ 窓がまだ食い違っている")
    assert p["per_lap"] > 0.3, f"1周 {p['per_lap']:.3f}% は下限のまま（床が当たっていない）"
    # 尽きる時刻も窓の食い違いで飛んでいた（01/14 と出ていた）
    assert p["exhaust_at"] is not None
    assert (p["exhaust_at"] - _now()).days < 30
