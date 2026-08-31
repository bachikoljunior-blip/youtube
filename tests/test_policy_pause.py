"""収益化ポリシーの門が、ファイル1つ消しただけで開かないこと。

2026-08-30 に止めた理由（AUTOMATION_PAUSED.md）は、YouTube の収益化ポリシーが
「sensitive topic について人間の専門家を名乗る AI persona」と「テンプレートの
大量生産」を収益化不可と明示していることだった。

2026-08-31、解除条件を1つも満たさないまま AUTOMATION_PAUSED.md だけが消された。
門の本体（hooks・CI・import）はそのまま残っていたので、**止まっているように見えて
実際は全開**という状態になっていた。これはその再発を止める検査。

**収益化されなければ RPM がいくつでも収入はゼロ**（docs/JOURNAL.md 2026-08-04）。
だからこの門は安全装置であると同時に、目標そのものの前提条件でもある。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_guard():
    spec = importlib.util.spec_from_file_location(
        "pause_guard_under_test", ROOT / "src" / "pause_guard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPLIANT_CHANNEL = """channel:
  name: "数字で見る手続き"
  niche: "公開データを計算して図にするチャンネル"
  persona: |
    このチャンネルはAIが台本と図を生成しています。
    人物を名乗りません。助言はせず、出典と計算式だけを画面に出します。
"""


def test_marker_file_alone_does_not_open_the_gate(tmp_path):
    """AUTOMATION_PAUSED.md を消すだけでは開かない。これが 08/31 に起きたこと。"""
    guard = _load_guard()
    guard.PAUSE_FILE = tmp_path / "absent.md"
    assert guard.is_paused() is True, (
        "マーカーを消しただけで門が開いた。config/channel.yaml が"
        "まだ非収益化の構成を宣言している間は開いてはいけない。"
    )


def test_current_config_still_trips_the_policy():
    """いまの config/channel.yaml は、まだ解除条件 1・2 を満たしていない。"""
    guard = _load_guard()
    tripped, why = guard.config_trips_policy()
    assert tripped is True
    assert "channel.yaml" in why


def test_generation_entry_points_are_blocked():
    guard = _load_guard()
    original = sys.argv[0]
    try:
        for name in ("pipeline.py", "uploader.py", "batch_build.py", "reschedule.py"):
            sys.argv[0] = name
            with pytest.raises(RuntimeError, match="AUTOMATION PAUSED"):
                guard.enforce_current_process()
    finally:
        sys.argv[0] = original


def test_analysis_entry_points_stay_open():
    """分析とデータ保全は止めない。止めるのは中身を作る口だけ。"""
    guard = _load_guard()
    original = sys.argv[0]
    try:
        for name in ("status.py", "eta.py", "reach.py", "retention.py"):
            sys.argv[0] = name
            guard.enforce_current_process()
    finally:
        sys.argv[0] = original


def test_gate_opens_when_the_config_is_actually_fixed(tmp_path):
    """恒久ブレーキではない。構成を直せば、自動で開く。

    オーナーの権限を奪わないための検査。門が開く条件は「ファイルを消すこと」
    ではなく「解除条件を実際に満たすこと」に移っただけ。
    """
    guard = _load_guard()
    channel = tmp_path / "channel.yaml"
    channel.write_text(COMPLIANT_CHANNEL, encoding="utf-8")
    guard.CHANNEL_FILE = channel
    guard.PAUSE_FILE = tmp_path / "absent.md"

    assert guard.is_paused() is False
    original = sys.argv[0]
    try:
        sys.argv[0] = "pipeline.py"
        guard.enforce_current_process()
    finally:
        sys.argv[0] = original


def test_marker_file_is_still_an_explicit_manual_pause(tmp_path):
    """構成が適合していても、マーカーがあれば止まる（手で止める口は残す）。"""
    guard = _load_guard()
    channel = tmp_path / "channel.yaml"
    channel.write_text(COMPLIANT_CHANNEL, encoding="utf-8")
    guard.CHANNEL_FILE = channel
    marker = tmp_path / "AUTOMATION_PAUSED.md"
    marker.write_text("paused", encoding="utf-8")
    guard.PAUSE_FILE = marker
    assert guard.is_paused() is True


def test_unreadable_config_fails_closed(tmp_path):
    """設定が読めないなら「適合している」とは言えない。開かない。"""
    guard = _load_guard()
    guard.CHANNEL_FILE = tmp_path / "does_not_exist.yaml"
    guard.PAUSE_FILE = tmp_path / "absent.md"
    assert guard.is_paused() is True
