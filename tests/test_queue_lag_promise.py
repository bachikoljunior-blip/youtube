"""**前の `--apply` の約束は守られたか。守られていない理由まで言えたときだけ止める。**

`stuck_lines` は「前の回の `before` と、いまの `before` が同じか」を見ます。
**この帯にはきょうだい（主実行）が毎周 本を足す**ので、判定日は勝手に
1〜2日 ずれ、**`before` は二度と一致しません** —— 門は開きっぱなしになります。

実測（2026-08-29 12:0x・`data/queue_lag.jsonl` の最後の行）:

    2026-08-27 07:43  **20手（1,000単位）**  約束 opening_motion **09-07**
    2026-08-29 12:0x  実物                    opening_motion **10-07**（**+30日**）
                      title_form +0 ／ stat_split +1 ／ hook_form +2 —— **遅れの合計 33日**

    そしてこの日の `--plan` は、opening_motion に **09-07 をもう一度 約束**
    （13手 ＝ 1,300単位）。**一度も守られたことのない約束**です。

`stuck_lines` はこの回 何も言いません（`before` が「ずれている」ため。
**ずれた向きは見ていません** —— 4つのうち2つは悪化しています）。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from scripts import queue_lag


class _Plan:
    """`promise_lines` が読むのは `before` と `readies()` だけです。"""

    def __init__(self, before: dict, after: dict | None = None) -> None:
        self.before = before
        self._again = after if after is not None else before

    def readies(self) -> dict:
        return self._again


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "queue_lag.jsonl"
    monkeypatch.setattr(queue_lag, "PROGRESS", path)
    return path


def _row(before: dict, promised: dict, moves: int = 20,
         after: dict | None = None) -> str:
    rec = {"at": "2026-08-27T07:43:36+00:00",
           "before": queue_lag._stamp(before),
           "promised": queue_lag._stamp(promised),
           "moves": moves}
    if after is not None:
        rec["after"] = queue_lag._stamp(after)
    return json.dumps(rec, ensure_ascii=False)


def test_no_ledger_means_go(ledger) -> None:
    lines, ok = queue_lag.promise_lines(_Plan({"a": date(2026, 9, 6)}))
    assert ok is True and lines == []


def test_promise_kept_means_go(ledger) -> None:
    promised = {"a": date(2026, 9, 7)}
    ledger.write_text(_row({"a": date(2026, 10, 6)}, promised) + "\n",
                      encoding="utf-8")
    # 実物が約束どおり（か、それより早い）なら通します
    lines, ok = queue_lag.promise_lines(_Plan({"a": date(2026, 9, 7)}))
    assert ok is True and lines == []


_BEFORE = {"title_form": date(2026, 9, 6), "stat_split": date(2026, 9, 5),
           "hook_form": date(2026, 9, 10), "opening_motion": date(2026, 10, 6)}
_PROMISED = {"title_form": date(2026, 9, 6), "stat_split": date(2026, 9, 5),
             "hook_form": date(2026, 9, 7), "opening_motion": date(2026, 9, 7)}
_NOW = {"title_form": date(2026, 9, 6), "stat_split": date(2026, 9, 6),
        "hook_form": date(2026, 9, 9), "opening_motion": date(2026, 10, 7)}
_AGAIN = {"title_form": date(2026, 9, 6), "stat_split": date(2026, 9, 6),
          "hook_form": date(2026, 9, 7), "opening_motion": date(2026, 9, 7)}


def test_the_2026_08_29_case_is_reported(ledger) -> None:
    """**実測そのもの。** 約束 09-07 ／ 実物 10-07 ／ この回もまた 09-07。

    そして `stuck_lines` はこの回 何も言いません（`before` がずれているため）。
    **この検査がこの門の存在理由**です —— 落ちたら、片方だけで足りる形に
    なったということなので、そのときは両方を読み直すこと。
    """
    ledger.write_text(_row(_BEFORE, _PROMISED) + "\n", encoding="utf-8")
    lines, _ok = queue_lag.promise_lines(_Plan(_NOW, _AGAIN))
    assert any("約束は、守られていません" in x for x in lines)
    assert any("+30日" in x for x in lines)          # opening_motion
    assert any("遅れの合計 **33日**" in x for x in lines)

    slines, moving = queue_lag.stuck_lines(_Plan(_NOW, _AGAIN))
    assert moving is True and slines == []


def test_no_after_in_the_ledger_still_fires(ledger) -> None:
    """**止めないこと。** `after` が無い回の一撃は、原因を分ける測定そのもの。

    最初の版はここで止めていました。**強すぎます** —— 止めると
    (1) 組み方 / (2) 当たっていない / (3) 戻された が永久に分かれません。
    """
    ledger.write_text(_row(_BEFORE, _PROMISED) + "\n", encoding="utf-8")
    lines, ok = queue_lag.promise_lines(_Plan(_NOW, _AGAIN))
    assert ok is True
    assert any("この一撃が、その3つを分ける測定です" in x for x in lines)


def test_after_equals_before_and_same_promise_is_refused(ledger) -> None:
    """`after == before` ＝ **手が1つも当たっていない**。同じ約束なら止める。"""
    ledger.write_text(_row(_BEFORE, _PROMISED, after=_BEFORE) + "\n",
                      encoding="utf-8")
    lines, ok = queue_lag.promise_lines(_Plan(_NOW, _AGAIN))
    assert ok is False
    assert any("手が" in x and "当たっていません" in x for x in lines)
    assert any("--force-stuck" in x for x in lines)


def test_after_equals_promised_is_not_blocked(ledger) -> None:
    """`after != before` ＝ **当たってはいる**。遠のいたのはきょうだい ——

    単位では直らないので止めても意味がありません。**通して、そう言う。**
    """
    ledger.write_text(_row(_BEFORE, _PROMISED, after=_PROMISED) + "\n",
                      encoding="utf-8")
    lines, ok = queue_lag.promise_lines(_Plan(_NOW, _AGAIN))
    assert ok is True
    assert any("手は当たっています" in x for x in lines)
    assert any("単位では直りません" in x for x in lines)


def test_a_different_promise_is_not_blocked(ledger) -> None:
    """守られなかっただけで永久に止めない —— **同じ日付を撃ち直すとき**だけ止める。"""
    ledger.write_text(_row({"a": date(2026, 10, 6)}, {"a": date(2026, 9, 7)},
                           after={"a": date(2026, 10, 6)}) + "\n",
                      encoding="utf-8")
    lines, ok = queue_lag.promise_lines(
        _Plan({"a": date(2026, 10, 7)}, {"a": date(2026, 9, 20)}))
    assert ok is True
    assert any("止めません" in x for x in lines)


def test_note_apply_records_the_reread(tmp_path, monkeypatch) -> None:
    """**`after`（撃った直後の実物）が帳面に入ること。**

    これが無いと、次の回は「模型が広すぎた」と「手が当たっていない」を
    帳面から切り分けられません（`stuck_lines` が自分でそう書いています）。
    """
    path = tmp_path / "queue_lag.jsonl"
    monkeypatch.setattr(queue_lag, "PROGRESS", path)
    from src import dupes
    monkeypatch.setattr(dupes, "may_write_path", lambda _p: True)
    queue_lag._note_apply({"a": date(2026, 10, 6)}, {"a": date(2026, 9, 7)}, 20,
                          None, {"a": date(2026, 10, 6)})
    rec = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["after"] == {"a": "2026-10-06"}
    # `after == before` ＝ **手が当たっていない**の側
    assert rec["after"] == rec["before"] != rec["promised"]


# ---- 撃つ手前で返った回（`blocked`）----------------------------------------
#
# 2026-08-29 の実測: `data/queue_lag.jsonl` は **全4行、全部 08/27**。
# `_note_apply` は `apply_moves` の後にしか呼ばれないので、
# **枠／判定／前の回 のどれかで返った回は、帳面に1文字も残らない** ——
# 「撃たれていない」のか「撃つ手前で返っていた」のかが言えませんでした。


class _P2:
    """`_note_blocked` が読むのは `before` / `readies()` / `swaps` だけ。"""

    def __init__(self) -> None:
        self.before = {"a": date(2026, 10, 6)}
        self.swaps = [("x", "y")]

    def readies(self) -> dict:
        return {"a": date(2026, 9, 7)}


def test_a_blocked_run_is_recorded(ledger, monkeypatch) -> None:
    from src import dupes
    monkeypatch.setattr(dupes, "may_write_path", lambda _p: True)
    queue_lag._note_blocked(_P2(), "quota")
    rec = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["blocked"] == "quota"
    assert rec["would_promise"] == {"a": "2026-09-07"}
    assert rec["swaps"] == 1
    assert "moves" not in rec           # **約束はしていません**


def test_blocked_rows_never_shadow_the_last_real_apply(ledger, monkeypatch) -> None:
    """**混ぜないこと。** 飛ばさないと、両方の門が「前に撃たなかった回」を見ます。"""
    from src import dupes
    monkeypatch.setattr(dupes, "may_write_path", lambda _p: True)
    ledger.write_text(_row(_BEFORE, _PROMISED) + "\n", encoding="utf-8")
    queue_lag._note_blocked(_P2(), "quota")
    last = queue_lag._last_apply()
    assert last is not None and last["moves"] == 20
    assert last["promised"]["opening_motion"] == "2026-09-07"
    # 門も、撃った行のほうを見ています
    lines, ok = queue_lag.promise_lines(_Plan(_NOW, _AGAIN))
    assert ok is True                    # `after` が無いので通す
    assert any("+30日" in x for x in lines)
