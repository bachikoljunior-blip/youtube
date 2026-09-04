"""**`fix` の門が、種別の札1枚でリセットされないこと。**

2026-09-04 夕・最適化の回に実測で名指しした欠陥:

    `fix_run_len()` は **連** なので、`improve` を1件 挟むと 0 に戻る。
    `improve` は直近5日 34回 で `moves` が 0 以外 **0件（0.0%）**。
    ＝ **歩留り 0.0% の札で、門が開いていた。**
    実物: `data/runs.jsonl` の `fix_gate` 止め 42行 のうち **12行 は、
    同じ文言の `fix` が数分後に ship として通っている。**

ここで固定するのは `fix_since_move()` の数え方だけです（門の値ではなく数え方）。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "run_marker_t", Path(__file__).resolve().parents[1] / "scripts" / "run_marker.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


def _write(tmp_path, rows) -> Path:
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def _ship(kind: str, moves: int = 0) -> dict:
    return {"at": "2026-09-04T00:00:00+09:00", "kind": "ship",
            "what": kind, "ship_kind": kind, "moves": moves}


def test_improve_does_not_reset(tmp_path):
    """**これが欠陥そのもの。** `improve` を挟んでも数は戻らない。"""
    p = _write(tmp_path, [_ship("fix"), _ship("fix"), _ship("improve"), _ship("fix")])
    assert rm.fix_run_len(p) == 1          # 連は 1 に戻る（＝ 上限 2 を下回り通る）
    assert rm.fix_since_move(p) == 3       # 動いた回から数えると 3


def test_verdict_resets(tmp_path):
    """`verdict` は数を切る —— **腕が動く唯一の道**を撃った回だから。"""
    p = _write(tmp_path, [_ship("fix"), _ship("fix"), _ship("verdict"), _ship("fix")])
    assert rm.fix_since_move(p) == 1


def test_moves_nonzero_resets(tmp_path):
    """`moves` が 0 以外 の回も切る（種別は問わない —— 実測で `fix` が 1件 動かした）。"""
    p = _write(tmp_path, [_ship("fix"), _ship("fix", moves=-15), _ship("fix")])
    assert rm.fix_since_move(p) == 1


def test_non_ship_rows_ignored(tmp_path):
    """`fix_gate` / `claim` / `start` の行は数に入れない（`fix_run_len` と同じ約束）。"""
    p = _write(tmp_path, [_ship("fix"),
                          {"at": "x", "kind": "fix_gate", "what": "y"},
                          {"at": "x", "kind": "claim", "what": "y"},
                          _ship("fix")])
    assert rm.fix_since_move(p) == 2


def test_cap_is_documented_and_reachable(tmp_path):
    """上限は定数で、`improve` 挟みの並びで実際に越えること。"""
    assert rm.FIX_SINCE_MOVE_CAP >= 2
    rows = []
    for _ in range(rm.FIX_SINCE_MOVE_CAP):
        rows += [_ship("fix"), _ship("improve")]
    p = _write(tmp_path, rows)
    assert rm.fix_run_len(p) == 0                       # 連の門は 0 ＝ 素通り
    assert rm.fix_since_move(p) >= rm.FIX_SINCE_MOVE_CAP  # 新しい数では止まる


def test_judgeable_today_is_measurable_not_guessed():
    """**門は「期限が近い」ではなく「きょう判定できる」で立てること。**

    2026-09-04 の実測: 期限が 09-05／09-06 の前提は在るのに、
    **きょう判定できる未閉は 0件**（`ready_by_claim()`）。
    撃てない `verdict` を要求する門は、語の書き換えで抜けられます。
    """
    got = rm.judgeable_today()
    assert got is None or isinstance(got, list)      # 測れないときは None ＝ 門を立てない
    if isinstance(got, list):
        assert all(isinstance(x, str) for x in got)
