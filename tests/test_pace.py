"""週枠を均して使い切るための「速さ」を固定する（2026-08-15）。

**なぜ要るか。** 8/12〜8/14 に**58時間、鎖が丸ごと止まりました**。枠を先に
使い切ったからです。8/15 に自走（`docs/trigger_main.md` §6 (f)）を入れて空転を
消したぶん、**回転が上がって同じ穴に近づきました** —— オーナーの実測で
0.758 %/時、持続できる速さの **+27%**。このままなら 8/20 19:00 に 100% に達し、
リセットまで36時間止まります。

**この計算が静かに壊れると、壊れたことに気づけません。** `quota.py --pace` が
None を返せば `sibling_check.py` は待たなくなり、鎖は元の速さに戻り、
**次に気づくのは枠が閉じたとき**です。だから機械に見張らせます。

固定するのは4つ:

  1. **目盛りの算術**（%÷誕生数 → 1周いくら → 持続できる間隔）
  2. **目盛りが無いとき None を返すこと** —— **止めないこと。**
     測れないことを理由に鎖を止めるのは、58時間と同じ損失
  3. **上下の歯止め** —— 計器が暴れても間隔が0分にも1日にもならない
  4. **`sibling_check --phase spawn` が実際に待たせること**（終了コード5）
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402

JST = timezone(timedelta(hours=9))
UTC = timezone.utc

# 8/15 の実物と同じ形。リセット 8/15 07:00 JST → 8/22 07:00 JST。
RESET = "2026-08-21T22:00:00Z"
START = datetime(2026, 8, 14, 22, 0, tzinfo=UTC)
ANCHOR_AT = "2026-08-15T20:12:00+09:00"


def _write(tmp_path, used_percent, births, *, window="seven_day", anchor_at=ANCHOR_AT):
    """%の点1つと、`births` 件の誕生を持つ計器を作る。"""
    usage = tmp_path / "usage.jsonl"
    usage.write_text(json.dumps({
        "fetched_at": anchor_at, "window_id": window,
        "used_percent": used_percent, "resets_at_iso": RESET,
    }) + "\n", encoding="utf-8")

    rows = []
    for i in range(births):
        born = START + timedelta(minutes=10 * i)
        rows.append({
            "seen_at": born.isoformat(), "born_at": born.isoformat(),
            "session_id": f"session_{i:03d}", "tags": ["youtube-hourly"],
        })
    log = tmp_path / "quota.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    quota.USAGE_LOG, quota.LOG = usage, log
    return usage, log


@pytest.fixture(autouse=True)
def _restore():
    usage, log = quota.USAGE_LOG, quota.LOG
    yield
    quota.USAGE_LOG, quota.LOG = usage, log


def test_算術は実測を再現する(tmp_path):
    """オーナーの実測（13.2時間で10%・誕生33件）から出る数字を固定する。"""
    _write(tmp_path, 10, 33)
    p = quota.pace()

    assert p["births"] == 33
    assert p["hours"] == pytest.approx(13.2, abs=0.05)
    assert p["rate"] == pytest.approx(0.758, abs=0.005)      # %/時
    assert p["per_lap"] == pytest.approx(0.303, abs=0.005)   # 1周いくら
    assert p["over"] == pytest.approx(0.27, abs=0.02)        # +27%
    assert p["floor_min"] == pytest.approx(30.5, abs=0.6)    # → 31分

    # 100% は 8/20 19時ごろ。リセット（8/22 07:00）まで36時間死ぬ。
    assert p["exhaust_at"].astimezone(JST).strftime("%m/%d %H") == "08/20 19"
    assert p["dead_hours"] == pytest.approx(36, abs=1)


def test_持続できる速さなら死なない(tmp_path):
    """**均して使い切れているときは「止まります」と言わせない。**

    ここが逆に出ると、間に合っているのに間隔を延ばし続けることになる。
    """
    # 13.2時間で7.5% ＝ 0.568 %/時。持続線（0.595）より**下**。
    # 境目は薄い: 8% だと 0.606 %/時 で、これはもう3時間ぶん足りない。
    _write(tmp_path, 7.5, 33)
    p = quota.pace()
    assert p["rate"] == pytest.approx(0.568, abs=0.005)
    assert p["over"] < 0                     # 持続線より遅い
    assert p["dead_hours"] == 0              # リセットまで届く


def test_目盛りが無ければ止めない(tmp_path):
    """**%の点が1つも無いとき、`None` を返すこと（0分でも上限でもなく）。**

    `sibling_check` は None を「待ちなし」と読む。**測れないことを理由に
    鎖を止めない** —— 止めれば 8/12 の58時間と同じ損失になる。
    """
    (tmp_path / "usage.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "quota.jsonl").write_text("", encoding="utf-8")
    quota.USAGE_LOG = tmp_path / "usage.jsonl"
    quota.LOG = tmp_path / "quota.jsonl"

    assert quota.pace() is None
    assert quota.recommended_floor_minutes() is None


def test_5時間枠の点は目盛りに使わない(tmp_path):
    """**混ぜると桁が狂う。** 週枠の話をしているので `seven_day` だけ拾う。"""
    _write(tmp_path, 10, 33, window="five_hour")
    assert quota.pace() is None


def test_誕生が0件でも落ちない(tmp_path):
    """`quota.jsonl` が空でも、速さ（%/時）までは言えること。

    **間隔は言えない**ので None のまま —— 分からないのに数字を出さない。
    """
    _write(tmp_path, 10, 0)
    p = quota.pace()
    assert p is not None
    assert p["births"] == 0
    assert p["per_lap"] is None and p["floor_min"] is None
    assert quota.recommended_floor_minutes() is None


@pytest.mark.parametrize("used,births,expect", [
    (100, 1, quota.FLOOR_MAX_CLAMP),   # 1周100% → 天井で止める
    (0.01, 500, quota.FLOOR_MIN_CLAMP),  # ほぼ0 → 床で止める
])
def test_歯止めが効く(tmp_path, used, births, expect):
    """**計器が暴れても、間隔が0分にも1日にもならないこと。**

    上が無いと1周で鎖が死に、下が無いと歯止めそのものが消える。
    """
    _write(tmp_path, used, births)
    assert quota.recommended_floor_minutes() == pytest.approx(expect)


# --------------------------------------------------------------------------
# 門が実際に閉まるか（ここが本体。上の算術が正しくても、門が読まなければ無意味）
# --------------------------------------------------------------------------

def _sessions_file(tmp_path, born_minutes_ago):
    now = datetime.now(UTC)
    blob = {"ccr": {"data": [
        {"id": "session_ME",
         "created_at": (now - timedelta(minutes=born_minutes_ago)).isoformat(),
         "updated_at": now.isoformat(), "session_status": "RUNNING",
         "tags": ["youtube-hourly"], "parent_session_id": "session_SPAWNER",
         "external_metadata": {"rate_limit_info": {
             "rateLimitType": "seven_day",
             "resetsAt": int((now + timedelta(days=6)).timestamp()),
             "status": "allowed"}}},
        {"id": "session_SPAWNER",
         "created_at": (now - timedelta(minutes=born_minutes_ago + 20)).isoformat(),
         "updated_at": now.isoformat(), "session_status": "ARCHIVED",
         "tags": ["youtube-hourly"],
         "external_metadata": {"rate_limit_info": {
             "rateLimitType": "five_hour",
             "resetsAt": int((now + timedelta(hours=2)).timestamp()),
             "status": "allowed"}}},
    ]}}
    path = tmp_path / f"sessions_{born_minutes_ago}.json"
    path.write_text(json.dumps(blob), encoding="utf-8")
    return path


def _spawn_check(path):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sibling_check.py"),
         "--sessions", str(path), "--me", "session_ME", "--phase", "spawn"],
        capture_output=True, text=True, cwd=ROOT)


def test_早すぎる子は待たされる(tmp_path):
    """**兄弟0件・枠 allowed でも、早ければ立てさせないこと。**

    `allowed` は「まだ閉じていない」としか言っていない。
    ここを素通りさせると、閉じるまで気づけない。
    """
    r = _spawn_check(_sessions_file(tmp_path, 8))
    assert r.returncode == 5, r.stdout
    assert "まだ立てないこと" in r.stdout
    assert "sleep " in r.stdout          # 待ち方まで出すこと（人が計算しない）


def test_十分あいた子はそのまま立てられる(tmp_path):
    """**1周が長かった回を、さらに待たせないこと。**

    待ちは「間隔の下限」であって上乗せではない。
    """
    r = _spawn_check(_sessions_file(tmp_path, 90))
    assert r.returncode == 0, r.stdout
    assert "待ち不要" in r.stdout
    assert "立ててよい" in r.stdout
