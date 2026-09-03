"""`list_triggers` の返りの形が変わっても、本文と環境の欄を落とさないこと。

実測 2026-09-03 13:4x: `observed()` は
`job_config.ccr.events[0].data.message.content` の1本しか見ておらず、
いまの返り（`session_request` ＋ `events[0].payload.internal_anthropic_catchall`）
から**本文も `environment_id` も抜けていなかった**。
抜けなかった欄は「無い」ではなく「0字」として保存されるので、
`status.py` は「本文が正本と違います（正本 4,254字 / 実物 1,913字）」と鳴り続け、
観測は 63時間 古いままだった。註は `trigger_sync._ccr_and_body()`。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import trigger_sync as ts  # noqa: E402

_NOW_SHAPE = {
    "id": "T1", "name": "親の心拍", "cron_expression": "59 * * * *", "enabled": True,
    "persistent_session_id": "S1",
    "session_request": {
        "environment_id": "env_X",
        "events": [{"payload": {"internal_anthropic_catchall": {
            "message": {"content": "いまの本文"}}}}],
    },
    "derived_state": {"prompt": "いまの本文"},
}

_OLD_SHAPE = {
    "id": "T1", "name": "親", "cron_expression": "0 * * * *", "enabled": True,
    "persistent_session_id": "S1",
    "job_config": {"ccr": {
        "environment_id": "env_old",
        "events": [{"data": {"message": {"content": "むかしの本文"}}}],
    }},
}


def test_いまの形から本文と環境が抜ける() -> None:
    got = ts.observed({"data": [_NOW_SHAPE]}, "T1")
    assert got is not None
    assert got["body"] == "いまの本文"
    assert got["environment_id"] == "env_X"
    assert got["cron_expression"] == "59 * * * *"


def test_古い形も落とさない() -> None:
    """古い形の観測が `data/trigger_seen.json` に残っている。"""
    got = ts.observed({"data": [_OLD_SHAPE]}, "T1")
    assert got is not None
    assert got["body"] == "むかしの本文"
    assert got["environment_id"] == "env_old"


def test_写しからでも本文を拾う() -> None:
    """`events` が空でも `derived_state.prompt` に同じ本文が在る。"""
    row = {**_NOW_SHAPE, "session_request": {"environment_id": "env_X", "events": []}}
    got = ts.observed({"data": [row]}, "T1")
    assert got is not None
    assert got["body"] == "いまの本文"


def test_本文がどこにも無ければ空() -> None:
    row = {"id": "T1", "name": "x", "cron_expression": "* * * * *", "enabled": True}
    got = ts.observed({"data": [row]}, "T1")
    assert got is not None
    assert got["body"] == ""
