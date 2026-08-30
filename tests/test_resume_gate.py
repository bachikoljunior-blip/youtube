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
    traj = src.index('pl["lever_from"] = "軌跡"')
    gate = src.index('pl["lever_from"] = "門"')
    assert gate > traj, (
        "門の名指しが、軌跡の上書きより**前**にある —— 後ろから 4本のどれかに戻されます")
    # **`plan()` の中で倒さないこと。** あちらは4本の模型で、
    # `test_eta_supply_density` などが「床の名前ではなく差の大きさで決まる」を
    # 直接 見ています。門は模型の外側の項なので、外側で倒すこと。
    plan_at = src.index("def plan(")
    solve_at = src.index("def solve(")
    assert plan_at < solve_at, "この検査は plan が solve より前にある前提で書いています"
    assert gate > solve_at, "門の上書きが `plan()` の中にある（模型の出力を書き換えている）"


def test_gate_row_is_json_safe():
    """**`date` を積まないこと。** `data/eta.jsonl` へ書き戻すと
    `TypeError: Object of type date is not JSON serializable` で
    **反映だけが落ち、ship は残ります**（2026-08-26 に同じ罠を踏んでいます）。"""
    import json
    g = dict(resume_gate.summary())
    g["since"] = g["since"].isoformat() if g.get("since") else None
    json.dumps(g, ensure_ascii=False)


def test_a_closed_mark_in_the_owners_file_wins(tmp_path):
    """**正本の印を勝たせること。**（2026-08-30 に実際に踏んだ）

    同じ日に2つの回が別々にここへ着き、片方は `data/resume_gate.jsonl` に積み、
    もう片方は `AUTOMATION_PAUSED.md` の箇条書きへ直接 印を書きました。
    合流直後の実測 —— `eta.py` が **同じ1行の中で**こう印字しました。

        開いている 5件: **1** sensitive-topic AI persona を使わない
        **← 2026-08-30 に閉じた（下の「進捗」）** ／ …
    """
    text = _PAUSE_TEXT.replace(
        "1. 条件いち", "1. 条件いち  **← 2026-08-30 に閉じた（下の「進捗」）**")
    st = resume_gate.state(text, tmp_path / "gate.jsonl")
    one = next(r for r in st if r["n"] == 1)
    assert one["closed"], "正本が「閉じた」と言っているのに、開いていることになっている"
    assert "閉じた" not in one["text"], "印が条件の本文に残っている（そのまま印字されます）"
    assert one["unrecorded"], "根拠が台帳に無いことが立っていない"


def test_a_mark_without_evidence_is_not_a_record(tmp_path):
    """**印は記録ではない。** 原文は「次の全条件が**記録される**まで解除しない」。

    日付の無い閉じ方を速さの分母に入れると、**測っていない速さ**が出ます。
    """
    text = _PAUSE_TEXT.replace("1. 条件いち", "1. 条件いち **← 閉じた**")
    led = tmp_path / "gate.jsonl"
    assert resume_gate.closed_count(text, led) == 1
    # 印だけの1件は、速さの実績に数えない
    assert resume_gate.rate_per_day(text, led, date(2026, 9, 5)) is None
    assert resume_gate.summary(text, led)["unrecorded"], "食い違いが summary に出ていない"


def test_the_queue_is_counted_after_dedupe(tmp_path):
    """**予約の列は、`video_id` で重複排除して後の行を勝たせること。**

    `retimed_at` で予定が動くので、**同じ本が何度も出ます。** 素で数えると
    「これから公開される本数」が水増しされ、**急ぐ理由の大きさが嘘になります。**
    """
    from datetime import datetime, timezone
    led = tmp_path / "uploaded.jsonl"
    led.write_text(
        '{"video_id": "a", "at": "2026-09-01T10:00:00Z"}\n'
        '{"video_id": "a", "at": "2026-09-05T10:00:00Z"}\n'   # 同じ本を後ろへ動かした
        '{"video_id": "b", "at": "2026-08-01T10:00:00Z"}\n'   # もう公開ずみ
        '{"video_id": "c"}\n',                                 # `at` が無い（数えない）
        encoding="utf-8")
    q = resume_gate.queue(led, now=datetime(2026, 8, 30, tzinfo=timezone.utc))
    assert q["held"] == 2, "`at` を持たない行まで控えに数えている"
    assert q["upcoming"] == 1, "重複排除できていない（同じ本を2回 数えた）"
    assert q["first"].date().isoformat() == "2026-09-05", "後の行が勝っていない"


def test_an_empty_queue_says_nothing(tmp_path):
    """**予約が尽きたら、この行は自分で消えること。**（覆る条件）"""
    from datetime import datetime, timezone
    led = tmp_path / "uploaded.jsonl"
    led.write_text('{"video_id": "b", "at": "2026-08-01T10:00:00Z"}\n', encoding="utf-8")
    q = resume_gate.queue(led, now=datetime(2026, 8, 30, tzinfo=timezone.utc))
    assert q["upcoming"] == 0
    assert q["per_day"] is None, "0本 なのにペースを言っている"
