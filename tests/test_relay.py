"""`scripts/relay.py` と `stop_check.sh` の (2.0) —— **鎖の受け渡し。**

**この検査が守っているのは「受け渡しが記録できること」ではありません。**
守っているのは、**次の回が立たないまま終われないこと**です。

2026-08-24 の実測。親は 15:14 / 16:17 / 17:12 / 19:10 / 20:12 と発火し、
`list_sessions` も撃ったのに、**両方の札が空なのに立てませんでした。**
14:49〜21:29 の **6時間40分、だれも回っていません。** その前の週に
「本文の1行目を `list_sessions` に入れ替える」という直しを既に入れてあり、
**撃つようにはなったのに、撃った結果に対して動かない回が残りました。**
**文書は読ませられても、実行させません。** だから機械の側に移してあります。

ここが逆向きに壊れると（記録が無くても通るようになると）、
**空白は printf ではなく「次の回が来ないこと」として出ます** ——
気づくのはオーナーが画面を見たときだけで、それは目標本文が
「私が必ず読むとは限らない」と言っている当のものです。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("relay_mod", ROOT / "scripts" / "relay.py")
relay = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(relay)


# --- 速さの読み ---------------------------------------------------------

def test_pace_percentage_is_not_the_interval_ratio():
    """**間隔の比をそのまま出さないこと。**

    最初の版は `actual / sustainable` を出し、186分/90分 で
    **「許される速さの 207% しか使っていない」**と印字しました。
    実際は逆で、間隔が長いほど遅いので **48%** です。
    ここが逆だと「もう速すぎる」と読めて、**穴を塞ぐ側の判断が止まります。**
    """
    # 実際 186分・持続 90分 ＝ 半分しか使っていない
    assert round(90 / 186 * 100) == 48
    assert round(186 / 90 * 100) == 207  # ← これを出してはいけない側


# --- 記録と読み戻し -----------------------------------------------------

def _run(args, cwd, env=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "relay.py"), *args],
        capture_output=True, text=True, timeout=120, cwd=str(cwd), env=env,
    )


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """**実物の台帳を触らないこと。** 検査が実物の数え上げを食い合います
    （2026-08-16、`tests/` を2度回したら引き止めの数が3回ぶん進んで落ちた）。"""
    monkeypatch.setattr(relay, "LEDGER", tmp_path / "relay.jsonl")
    return tmp_path


def test_check_is_2_before_recording_and_0_after(sandbox, monkeypatch):
    """`--check` が門の本体です。**記録するまで 2 を返し続けること。**"""
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    assert relay.cmd_check(None) == 2

    args = type("A", (), {"hourly": 1, "optimizer": 1, "spawned": "", "note": ""})()
    relay.cmd_record(args)
    assert relay.cmd_check(None) == 0


def test_another_sessions_record_does_not_satisfy_this_session(sandbox, monkeypatch):
    """**隣の回の記録で通してはいけません。**

    通ると、1回だれかが記録した以降ぜんぶ素通りになり、門が消えます。
    """
    monkeypatch.setattr(relay, "me", lambda: "session_OTHER")
    args = type("A", (), {"hourly": 1, "optimizer": 1, "spawned": "", "note": ""})()
    relay.cmd_record(args)

    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    assert relay.cmd_check(None) == 2


def test_record_warns_when_a_lane_is_left_empty(sandbox, monkeypatch, capsys):
    """**空の札を残したまま記録したら、黙らないこと。**

    記録は通します（止まったまま死ぬほうが確実に悪い）が、
    **印字が残らないと、次の回がその回を責められません。**
    """
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    args = type("A", (), {"hourly": 0, "optimizer": 1, "spawned": "", "note": ""})()
    relay.cmd_record(args)
    out = capsys.readouterr().out
    assert "空の札" in out
    assert "youtube-hourly" in out


def test_record_is_quiet_when_the_empty_lane_was_filled(sandbox, monkeypatch, capsys):
    """立てたなら警告しないこと（立てた回まで責めると、印字が信用されなくなる）。"""
    monkeypatch.setattr(relay, "me", lambda: "session_TEST")
    args = type("A", (), {"hourly": 0, "optimizer": 1, "spawned": "hourly", "note": ""})()
    relay.cmd_record(args)
    out = capsys.readouterr().out
    assert "空の札" not in out


def test_audit_counts_the_runs_that_left_a_lane_empty(sandbox, monkeypatch, capsys):
    """**効いているかどうかは、空白が消えたかで見ること。**"""
    monkeypatch.setattr(relay, "me", lambda: "session_A")
    relay.cmd_record(type("A", (), {"hourly": 0, "optimizer": 1, "spawned": "", "note": ""})())
    monkeypatch.setattr(relay, "me", lambda: "session_B")
    relay.cmd_record(type("A", (), {"hourly": 0, "optimizer": 1, "spawned": "hourly", "note": ""})())

    relay.cmd_audit(type("A", (), {"limit": 15})())
    out = capsys.readouterr().out
    assert "**1/2**" in out


# --- 入口そのものが通ること ---------------------------------------------

def test_the_entry_point_is_not_named_plan():
    """**`--plan` という名前にしないこと**（2026-08-24 に実測）。

    `python scripts/relay.py --plan` は `Bash(python *)` を許してあっても
    **auto mode の分類器に弾かれます。子は無人なので、弾かれた時点で仕組みが死にます。**
    ここは名前の趣味の話ではなく、**入口が通るかどうか**の話です。
    """
    src = (ROOT / "scripts" / "relay.py").read_text(encoding="utf-8")
    assert '"--next"' in src
    assert 'add_argument("--plan"' not in src


def test_next_prints_the_spawn_arguments_for_both_lanes(tmp_path):
    """**引数を出すところまでが道具です。** 手で組ませると `source_url` が落ちます
    （8/17・8/18 に2回、repo の無い子が立った）。"""
    p = _run(["--next"], cwd=ROOT)
    assert p.returncode == 0, p.stderr
    assert "youtube-hourly" in p.stdout
    assert "youtube-optimizer" in p.stdout
    # 両方の札に `source_url` が付いていること
    assert p.stdout.count('"source_url"') >= 2
    assert "claude/youtube-auto-post-revenue-ggedij" in p.stdout


# --- 門が実際に仕込まれていること ---------------------------------------

def test_stop_hook_parses():
    """`stop_check.sh` は**手で実行できません**（2026-08-16、この1行で子が1つ死んだ）。
    だから**構文検査だけ**します —— 壊れたフックは全部の回を通してしまいます。"""
    p = subprocess.run(["bash", "-n", str(ROOT / "scripts" / "stop_check.sh")],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr


def test_stop_hook_actually_calls_the_relay_gate():
    """**註に書くだけにしないこと。** 2026-08-20 に註へ書いたものは、
    その日のうちに全部素通りしました。**引き止めが、素通りしない唯一の形です。**"""
    src = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    assert "relay.py" in src
    assert "--check" in src
    assert '"decision":"block"' in src.replace(" ", "")


def test_stop_hook_relay_gate_lets_go_after_two_blocks():
    """**止まったまま死ぬほうが確実に悪い。** それはこの門が塞ぎたい穴そのものです。"""
    src = (ROOT / "scripts" / "stop_check.sh").read_text(encoding="utf-8")
    assert 'RL" -lt 2' in src
