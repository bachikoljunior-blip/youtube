"""**「2つ の側が答えを違えた回」は、その周に台帳へ書いて、道具の側で数えること**
（2026-09-12 01:4x・optimizer・Opus。**API 0単位**）。

**踏んだ形**: `quota.short_verdict` の覆る条件 (2) は 2026-09-11 13:1x から
「2つ の側が**答えを違える回**が出たら、その回の数を METHOD §5 へ並べること
—— **いまは 2つ が重なっている点なので、側を決めた効きはまだ 1度も出ていません**」
と書いてありました。ところが同じ刻の §7「いまの数」には
「**2つ の側が答えを違えた回は 8周目**」と在ります ＝ **条件は 8周 前に引かれ、
註と §5 の (2') だけが「まだ 1度も出ていません」のまま**でした。

**なぜ古いまま残ったか**: その数を出す口が無く、**§7 が手で送っていた**からです
（`margin_series` が 2026-09-11 07:5x に閉じたのと同じ穴 ——
`pace(過去の刻)` から数え直しても、`per_lap` も遅れも**いまの台帳**から引き直されるので
その周が見た数は出ません）。§5 教訓の形 7つ目（**覆る条件を註に書いたら、
その条件を読む印字も一緒に作ること**）の 3例目。

**この検査が固定するのは 4つ**:
  (a) 親が周ごとに `reach_floor` / `reach_carry` / `short_agree` を積むこと（`record_model_choice`）
  (b) 列は**周ごとに 1点**へ畳むこと（親は 1周に 2行 積む ＝ 畳まないと周の数が倍に出る）
  (c) `run` は**続いている「違えた」周だけ**を数えること（一致に戻ったら 0 ＝ 覆る条件 (2)）
  (d) `agree_line` が その数と **§5 13:1x の (2') の指し先**を印字すること

**きょうの状態は当てません**（§5 教訓の形 6つ目）—— 刻も台帳もその場で作り、実物は見ません。

**陽性対照**（`.pyc` を消してから撃った・落ちる件数）:
    `_round_series` を通さず行をそのまま数える（畳みを外す）        **2件**
    `run` を「違えた回の総数」にする（続きを見ない）                **1件**
    `record_model_choice` の 3欄 を落とす                          **1件**
    `agree_line` から (2') の指し先を消す                          **1件**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402


def _row(at, agree=None, role="hourly"):
    r = {"at": at, "work_kind": f"{role}:leverage", "model": "opus"}
    if agree is not None:
        r["short_agree"] = agree
    return r


def _ledger(tmp_path, rows):
    f = tmp_path / "model_choice.jsonl"
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    return f


@pytest.fixture(autouse=True)
def _no_rounds(tmp_path, monkeypatch):
    """**周の台帳を空にする**（`margin_series` の検査と同じ理由・§5 教訓の形 6つ目）。

    塞がないと、作り話の刻が**実物の周**へ寄って、検査が「きょうの台帳」に依ります。
    """
    monkeypatch.setattr(quota, "ROUNDS_LOG", tmp_path / "no-rounds.jsonl")


def test_同じ周の_2行_は_1点_に畳むこと(tmp_path, monkeypatch):
    """(b) 親は 1周に 2行（`hourly` と `optimizer`）積みます。畳まないと `run` が倍に出ます。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, [
        _row("2026-09-12T00:52:51+09:00", False, "hourly"),
        _row("2026-09-12T00:52:52+09:00", False, "optimizer"),
        _row("2026-09-12T01:35:10+09:00", False, "hourly"),
        _row("2026-09-12T01:35:11+09:00", False, "optimizer"),
    ]))
    v = quota.agree_run()
    assert v["pts"] == 2, "4行 ＝ 2周"
    assert v["run"] == 2
    assert v["since"] == "2026-09-12T00:52:51+09:00"


def test_run_は続いている回だけを数えること(tmp_path, monkeypatch):
    """(c) 手前に「違えた」回が在っても、**一致を挟んだら数え直し**。

    2つ の側は重なったり離れたりする数なので、「違え始めた」だけでは窓が閉じません
    （`agree_run` の覆る条件 (2)）。
    """
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, [
        _row("2026-09-11T20:00:00+09:00", False),
        _row("2026-09-11T21:00:00+09:00", False),
        _row("2026-09-11T22:00:00+09:00", True),      # 重なった回
        _row("2026-09-11T23:00:00+09:00", False),
    ]))
    v = quota.agree_run()
    assert v["pts"] == 4
    assert v["run"] == 1, "続いているのは最後の 1周 だけ"
    assert v["since"] == "2026-09-11T23:00:00+09:00"


def test_直近が一致なら_run_は_0(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, [
        _row("2026-09-11T20:00:00+09:00", False),
        _row("2026-09-11T21:00:00+09:00", True),
    ]))
    v = quota.agree_run()
    assert v["run"] == 0 and v["agree"] is True
    assert "0周" in quota.agree_line()


def test_欄の無い古い行は点にしないこと(tmp_path, monkeypatch):
    """`short_agree` を書き始めた回より前の行は「その周は書いていない」＝ 点にしない。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, [
        _row("2026-09-11T18:00:00+09:00"),            # 欄なし
        _row("2026-09-11T19:00:00+09:00"),            # 欄なし
        _row("2026-09-11T20:00:00+09:00", False),
    ]))
    v = quota.agree_run()
    assert v["pts"] == 1 and v["run"] == 1


def test_1点も無ければ_None_と言うこと(tmp_path, monkeypatch):
    """**欠けを黙って詰めないこと**（`margin_series` の覆る条件 (1) と同じ）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", tmp_path / "none.jsonl")
    assert quota.agree_run() is None
    assert "まだ 1点も積まれていません" in quota.agree_line()


def test_印字は_5_の_2ダッシュ_を指すこと(tmp_path, monkeypatch):
    """(d) **数だけ出して指し先が無いと、読む側はどの決めの分子か分かりません**
    （§5 教訓の形 7つ目・`short_words` の 2行目 と同じ決まり）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _ledger(tmp_path, [
        _row("2026-09-12T01:35:10+09:00", False),
    ]))
    line = quota.agree_line()
    assert "1周 続いています" in line
    assert "(2')" in line and "§5" in line
    assert "agree_run" in line, "手で数えないこと ＝ 口の名を出す"


def test_親は周ごとに_2つ_の着地と一致を積むこと(tmp_path, monkeypatch):
    """(a) **その周が見た数は、その周に書くしかありません**（`record_model_choice` の註）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", tmp_path / "mc.jsonl")
    monkeypatch.setattr(quota, "pace", lambda now=None: {
        "used_now": 93.5, "reach_ceiling_margin": 2.317,
        "reach_floor": 99.47, "reach_carry": 97.95,
    })
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None: {"est": 100.0})
    row = quota.record_model_choice("optimizer", "opus", "盤")
    assert row["reach_floor"] == 99.47 and row["reach_carry"] == 97.95
    assert row["short_agree"] is False, "床 99.47 は門 98% の上・間隔 97.95 は下 ＝ 逆の答え"


def test_2つ_の側が重なる回は_True_で積むこと(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", tmp_path / "mc.jsonl")
    monkeypatch.setattr(quota, "pace", lambda now=None: {
        "used_now": 93.5, "reach_ceiling_margin": 2.317,
        "reach_floor": 99.44, "reach_carry": 99.41,
    })
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None: {"est": 100.0})
    assert quota.record_model_choice("hourly", "opus", "盤")["short_agree"] is True
