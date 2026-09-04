"""**「動いたか」を、宣言ではなく差し引きで測る**（2026-09-04 22:5x・最適化の回）。

## なぜこの試験が要るのか（実測）

`data/runs.jsonl` の ship 239件（直近5日）を数えたとき:

    `eta_days`   239件 **全部 10^9**（＝ `eta.py` の「出ません」）。
                 `traj_days` が最後に有限だったのは **2026-08-31 07:58Z**。
    `moves`      0 が 232件・0以外 7件 ——**その 7件 は全部 `--moves` に
                 手で打った数**で、差し引きから出た数は 1件も在りませんでした。

**10^9 から 10^9 を引くと、どんな回も 0 です。** ＝ 「その回で目標に近づいたか」
を測る数が、輪のどこにも在りませんでした。近づかない回が選ばれ続けたのは
サボりではなく、**選ぶ側に物差しが無かったから**です。

だから ship 行に `gate1p_days`（門1'・登録者 500人 までの日数。**有限で、
登録の実測で動く**。実測 09/03 532.0日 → 09/04 511.5日）を積み、
直前の ship 行との差を `moves_measured` に置きます。

**覆る条件**: `traj_days` が有限に戻ったら、正本は軌跡へ戻ります
（そのときは `eta_days` の差が使えるので、この欄は残っていても害はありません）。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_marker  # noqa: E402


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                            for r in rows), encoding="utf-8")


def test_gate1p_now_skips_rows_without_the_field(tmp_path, monkeypatch):
    """**最後の1行だけを見ないこと。**

    `eta.py` は撃ち方によって `gate1p_days` を積まない行も書きます
    （実測 1,334行 中 101行 にしか在りません）。最後の1行だけを読むと
    **在るのに「無い」と言う回**が出ます。
    """
    log = tmp_path / "eta.jsonl"
    _write(log, [
        {"at": "2026-09-03T07:00:00+00:00", "gate1p_days": 532.0},
        {"at": "2026-09-04T09:00:00+00:00", "gate1p_days": 511.5},
        {"at": "2026-09-04T13:00:00+00:00", "traj_days": 10 ** 9},   # 欄が無い行
    ])
    monkeypatch.setattr(run_marker, "ETA_LOG", log)
    assert run_marker._gate1p_now() == 511.5


def test_gate1p_now_rejects_the_infinite_ruler(tmp_path, monkeypatch):
    """**10^9 は日数ではありません。** 拾ったら差し引きが永久に 0 になります。"""
    log = tmp_path / "eta.jsonl"
    _write(log, [{"at": "2026-09-04T13:00:00+00:00", "gate1p_days": 10 ** 9}])
    monkeypatch.setattr(run_marker, "ETA_LOG", log)
    assert run_marker._gate1p_now() is None


def test_gate1p_now_is_none_when_the_log_is_missing(tmp_path, monkeypatch):
    """**読めない回でも、回は止めないこと。** この印は記録であって門ではありません。"""
    monkeypatch.setattr(run_marker, "ETA_LOG", tmp_path / "does-not-exist.jsonl")
    assert run_marker._gate1p_now() is None


def test_last_ship_gate1p_reads_ship_rows_not_eta_rows(tmp_path, monkeypatch):
    """差を取る相手は **ship 行**です。

    `eta.jsonl` は1周に何度も書かれるので、そちらで引くと
    「回と回のあいだ」ではなく「印字と印字のあいだ」を測ってしまいます。
    """
    marks = tmp_path / "runs.jsonl"
    _write(marks, [
        {"at": "2026-09-04T20:00:00+09:00", "kind": "ship", "gate1p_days": 532.0},
        {"at": "2026-09-04T21:00:00+09:00", "kind": "ship"},          # 古い形の行
        {"at": "2026-09-04T22:00:00+09:00", "kind": "ship", "gate1p_days": 511.5},
    ])
    monkeypatch.setattr(run_marker, "MARKS", marks)
    assert run_marker._last_ship_gate1p() == 511.5


def test_last_ship_gate1p_is_none_before_the_first_measured_ship(tmp_path,
                                                                 monkeypatch):
    """**最初の1件は差が取れません。** そこで例外にしないこと（回を止めない）。"""
    marks = tmp_path / "runs.jsonl"
    _write(marks, [{"at": "2026-09-04T20:00:00+09:00", "kind": "ship"}])
    monkeypatch.setattr(run_marker, "MARKS", marks)
    assert run_marker._last_ship_gate1p() is None


def test_the_sign_says_closer(tmp_path, monkeypatch):
    """**負 ＝ 近づいた。** 向きを取り違えると、悪い回が褒められます。"""
    log = tmp_path / "eta.jsonl"
    marks = tmp_path / "runs.jsonl"
    _write(log, [{"at": "2026-09-04T13:00:00+00:00", "gate1p_days": 511.5}])
    _write(marks, [{"at": "2026-09-04T20:00:00+09:00", "kind": "ship",
                    "gate1p_days": 532.0}])
    monkeypatch.setattr(run_marker, "ETA_LOG", log)
    monkeypatch.setattr(run_marker, "MARKS", marks)
    now, prev = run_marker._gate1p_now(), run_marker._last_ship_gate1p()
    assert now is not None and prev is not None
    assert round(now - prev, 3) == -20.5      # 532.0 → 511.5 ＝ 20.5日 近づいた
