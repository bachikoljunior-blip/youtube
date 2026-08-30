"""**審査の門（`AUTOMATION_PAUSED.md` の Resume gate）が、床として効いていること。**

## この検査が守っているもの（2026-08-30・最適化の回が足した）

`scripts/eta.py` は、止まっている間ずっと自分でこう印字していました。

    **収益化の審査に受かる確率を 1.0** に置いたまま …… **その項はまだこの機械に
    入っていません。**

**入っていないのは掛け算の項です。** 受からなければ再生がいくつでも収入は 0 円
（`CLAUDE.md`）。なので `p_pass` は到達日に**掛かり**、4本の腕はその**内側**にあります。
そして 08/30 の停止中は、その4本が1つも引けません（`src/pause_guard`）。

固定するのは4つ。**どれも「文言」ではなく、壊れると回の振る舞いが変わる所**です。

1. **確率を捏造しないこと** …… `p_pass()` は `None`。審査に出した実績が 0回 なので
   測れません。**`1.0` を返さないことが、この関数の仕事の全部**です
2. **測れない速さを 0 と印字しないこと** …… 閉じた実績が薄いうちは `None`。
   「測れないことを誤りゼロとして印字する」のが、この種の仕掛けの最悪の壊れ方
   （`docs/JOURNAL.md` 2026-08-30 の覆る条件4）
3. **止まっている間の名指しは `gate`** …… 引けない腕を名指しし続けると、
   `run_marker.py` の `lever_followed` が全部 False で埋まります
   （実測 08/30: ship 40件 の `lever_hint` は 40件とも `per_video`）
4. **条件の本文を写さないこと** …… 正本は `AUTOMATION_PAUSED.md`。
   オーナーがあちらを直したら、こちらは翌回から自動で追随すること
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

from src import levers, resume_gate

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_gate_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


_PAUSE_TEXT = """# AUTOMATION PAUSED — 2026-08-30

## What is blocked

- something

## Resume gate

次の全条件が記録されるまで解除しない。

1. 条件いち
2. 条件に
3. 条件さん

## Override

なにか
"""


def test_conditions_are_read_from_the_owners_file():
    """**正本はオーナーが push したファイル。** 写しを持たないこと（覆る条件3）。"""
    got = resume_gate.conditions(_PAUSE_TEXT)
    assert [n for n, _ in got] == [1, 2, 3]
    assert got[0][1] == "条件いち"
    # `## Override` の側へ食い込んでいないこと
    assert all("なにか" not in body for _, body in got)


def test_the_real_file_still_parses():
    """**実物が読めること。** 読めないまま 0件 を返すと「全部 閉じた」と同じ姿になります。"""
    if not resume_gate.is_paused():
        pytest.skip("停止していません（`AUTOMATION_PAUSED.md` が無い）")
    conds = resume_gate.conditions()
    assert len(conds) >= 1, (
        "`## Resume gate` の番号つき箇条書きが1件も読めません —— "
        "0件 を『全部 閉じた』と読まないこと")


def test_p_pass_never_returns_one():
    """**確率を捏造しないこと。** 審査に出した実績は 0回 です。"""
    assert resume_gate.p_pass(_PAUSE_TEXT) is None


def test_unmeasured_rate_is_none_not_zero(tmp_path):
    """**閉じた実績が薄いうちは `None`。** 0 と書くと「進んでいない」と区別できません。"""
    led = tmp_path / "gate.jsonl"
    assert resume_gate.rate_per_day(_PAUSE_TEXT, led, date(2026, 9, 2)) is None
    assert resume_gate.days_to_close(_PAUSE_TEXT, led, date(2026, 9, 2)) is None

    # 1件 閉じただけでも、まだ言わない（`MIN_CLOSED_FOR_RATE`）
    led.write_text('{"at": "2026-08-31T10:00:00+09:00", "n": 1, "state": "closed",'
                   ' "evidence": "x"}\n', encoding="utf-8")
    assert resume_gate.closed_count(_PAUSE_TEXT, led) == 1
    assert resume_gate.rate_per_day(_PAUSE_TEXT, led, date(2026, 9, 2)) is None


def test_rate_appears_once_there_is_enough_evidence(tmp_path):
    """**3件 閉じたら、速さと残り日数が出ること。**（覆る条件4）"""
    led = tmp_path / "gate.jsonl"
    led.write_text(
        '{"at": "2026-08-31T10:00:00+09:00", "n": 1, "state": "closed", "evidence": "x"}\n'
        '{"at": "2026-09-01T10:00:00+09:00", "n": 2, "state": "closed", "evidence": "y"}\n'
        '{"at": "2026-09-02T10:00:00+09:00", "n": 3, "state": "closed", "evidence": "z"}\n',
        encoding="utf-8")
    assert resume_gate.closed_count(_PAUSE_TEXT, led) == 3
    rate = resume_gate.rate_per_day(_PAUSE_TEXT, led, date(2026, 9, 2))
    assert rate == pytest.approx(3 / 3)
    # 全部 閉じているので残りは 0日（**`None` ではありません** —— 測れているので）
    assert resume_gate.days_to_close(_PAUSE_TEXT, led, date(2026, 9, 2)) == 0.0


def test_reopening_is_possible(tmp_path):
    """**台帳の最後の行が勝つこと。** 開き直しが書けないと、誤って閉じた回を直せません。"""
    led = tmp_path / "gate.jsonl"
    led.write_text(
        '{"at": "2026-08-31T10:00:00+09:00", "n": 1, "state": "closed", "evidence": "x"}\n'
        '{"at": "2026-09-01T10:00:00+09:00", "n": 1, "state": "open", "evidence": "戻した"}\n',
        encoding="utf-8")
    assert resume_gate.closed_count(_PAUSE_TEXT, led) == 0


def test_closing_without_evidence_is_refused(tmp_path):
    """**門は「決めた」ではなく「記録した」ときに閉じる**（`AUTOMATION_PAUSED.md` の原文）。"""
    with pytest.raises(ValueError):
        resume_gate.close(1, "   ", path=tmp_path / "gate.jsonl")


def test_cap_is_undefined_at_zero(tmp_path):
    """**0/6 の倍率は書けないこと。** 0倍 では 6件 になりません。"""
    led = tmp_path / "gate.jsonl"
    assert resume_gate.cap(_PAUSE_TEXT, led) is None
    led.write_text('{"at": "2026-08-31T10:00:00+09:00", "n": 1, "state": "closed",'
                   ' "evidence": "x"}\n', encoding="utf-8")
    assert resume_gate.cap(_PAUSE_TEXT, led) == pytest.approx(3 / 1)


def test_gate_is_a_lever():
    """**選べない腕は、選ばれない。** `--lever gate` が語彙に無いと、
    律速を進めた回が `none`（＝ 予測日を動かさない回）として数えられます。"""
    assert "gate" in levers.LEVERS
    assert "gate" in levers.MOVING


def test_eta_prints_the_gate_instead_of_the_old_prose(monkeypatch):
    """**手書きの『入っていません』を、床の印字に置き換えたこと。**"""
    monkeypatch.setattr(eta.resume_gate, "summary",
                        lambda: {"paused": True, "total": 6, "closed": 0, "open": 6,
                                 "open_items": [{"n": 1, "text": "条件いち"}],
                                 "since": date(2026, 8, 30), "p_pass": None,
                                 "rate_per_day": None, "days_to_close": None,
                                 "cap": None, "min_closed_for_rate": 3})
    body = "\n".join(eta.gate_lines("###"))
    assert "0/6" in body, "何件 閉じたかが出ていない"
    assert "--lever gate" in body, "この回に引ける腕の名前が出ていない"
    assert "測れていません" in body, "測れない速さを、測れたように書いている"
    assert "その項はまだこの機械に入っていません" not in body, (
        "手書きの断り書きが残っている —— 記述は床になりません")


def test_paused_hint_is_gate_and_survives_the_trajectory_override():
    """**軌跡の名指しが、後ろから `gate` を上書きしないこと。**

    `solve()` は `plan()` のあとで `tr["choice"]` の先頭に倒します。そこは
    4本しか見ていないので、素通しにすると名指しが `rpm` などへ戻ります ——
    **この回には引けない腕**です。
    """
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert 'if tr is not None and pl.get("lever_hint") != "gate":' in src, (
        "軌跡の上書きに、門の除外が入っていない")


def test_gate_row_is_json_safe():
    """**`date` を積まないこと。** `data/eta.jsonl` へ書き戻すと
    `TypeError: Object of type date is not JSON serializable` で
    **反映だけが落ち、ship は残ります**（2026-08-26 に同じ罠を踏んでいます）。"""
    import json
    g = dict(resume_gate.summary())
    g["since"] = g["since"].isoformat() if g.get("since") else None
    json.dumps(g, ensure_ascii=False)
