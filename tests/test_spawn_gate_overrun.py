"""**待ちが親の発火をまたぐなら、その待ちは成立していない。**

2026-08-19 に2周続けて、`--phase spawn` の待ち（背景 `sleep`）の最中に鎖が切れた。
切れたのは `sleep` ではなく、**親が毎時 9分に起きて、黙っている子を畳んだ**ほう。

    22:3x の子   13:39 に黙る／明けるのは 14:14／**親は 14:09 に来た**（5分差）

だからこの検査は、**「下限が明ける時刻」と「親の次の発火」の前後関係だけ**を見る。
またぐなら 6（待たずに畳む）、またがないなら 5（待つ）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sibling_check.py"
ME = "session_TESTME"


def _sessions(born: datetime) -> list[dict]:
    """自分1件だけ。兄弟は無し・枠は allowed・深さ2（壁ではない）。"""
    return [
        {
            "id": ME,
            "session_status": "SESSION_STATUS_RUNNING",
            "created_at": born.strftime("%Y-%m-%dT%H:%M:%S.000000Z"),
            "parent_session_id": "session_PARENT",
            "external_metadata": {
                "rate_limit_info": {
                    "rateLimitType": "seven_day",
                    "resetsAt": int((born + timedelta(days=3)).timestamp()),
                    "status": "allowed",
                },
            },
        },
        {
            "id": "session_PARENT",
            "session_status": "SESSION_STATUS_ARCHIVED",
            "created_at": (born - timedelta(hours=9)).strftime(
                "%Y-%m-%dT%H:%M:%S.000000Z"),
        },
    ]


def _run(tmp_path: Path, born_minutes_ago: float, cron_minute: int) -> tuple[int, str]:
    now = datetime.now(timezone.utc)
    born = now - timedelta(minutes=born_minutes_ago)
    f = tmp_path / "sessions.json"
    f.write_text(json.dumps({"ccr": {"data": _sessions(born)}}), encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--sessions", str(f), "--phase", "spawn",
         "--me", ME, "--cron-minute", str(cron_minute)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return p.returncode, p.stdout + p.stderr


def _floor() -> float | None:
    """**いま実際に効いている下限**（`quota.effective_floor_minutes()`）。

    **ここを固定値で書かないこと**（2026-08-30 に踏んだ）。
    子は本物の `data/usage.jsonl` を読むので下限は実測で動きます ——
    オーナーの画面を積んだ日に 90分 → 275分 になり、
    「誕生は60分前・親は58分後」で作っていたこの回は**またぐ側**へ落ちて、
    待つ枝ではなく畳む枝（6）を測っていました。**見たいのは分数ではなく枝です。**
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "quota_for_gate", ROOT / "scripts" / "quota.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.effective_floor_minutes()


def test_gate_before_parent_fire_waits(tmp_path):
    """明けるのが親の発火より**前**なら、いつもどおり 5（待つ）。"""
    import pytest
    now = datetime.now(timezone.utc)
    floor = _floor()
    if floor is None:
        pytest.skip("目盛りが無い ＝ 下限そのものが無い")
    # 親の発火を「いまから58分後」に置き、**下限が明けるのを30分後**にする
    # ＝ またがない側。誕生の古さは下限から作ること（固定値にしない）。
    cron = (now + timedelta(minutes=58)).minute
    code, out = _run(tmp_path, born_minutes_ago=max(1.0, floor - 30.0),
                     cron_minute=cron)
    assert code in (0, 5), out
    if code == 5:
        assert "秒 待ってから" in out, out


def test_gate_after_parent_fire_folds(tmp_path):
    """明けるのが親の発火より**後**なら 6（待たずに畳む）。

    誕生が1分前 ＝ 下限まであと60分以上。親の発火を「いまから3分後」に置くと、
    どんな下限でも必ずまたぐ。
    """
    now = datetime.now(timezone.utc)
    cron = (now + timedelta(minutes=3)).minute
    code, out = _run(tmp_path, born_minutes_ago=1.0, cron_minute=cron)
    assert code == 6, out
    assert "待たずに畳む" in out, out
    assert "create_session` を呼ばないこと" in out, out


def test_fold_does_not_tell_you_to_sleep(tmp_path):
    """6 の回に `sleep` の行を出さないこと（**出すと両方やろうとする**）。"""
    now = datetime.now(timezone.utc)
    cron = (now + timedelta(minutes=3)).minute
    code, out = _run(tmp_path, born_minutes_ago=1.0, cron_minute=cron)
    assert code == 6, out
    assert "sleep" not in out, out
