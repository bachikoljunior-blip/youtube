"""**自分の長尺が何分かを、手で書かずに数えること。**（2026-09-04 15:2x に足した）

`daily_pick.theory_lines()` は、外の上位の尺の中央（**測った数**）の隣に
「自分の長尺は 5分・計算1本・題に数字」と**手で書いた字**を並べていました。
この行の仕事は「だから外の作りを写す価値がある」と言うことなので、
**写した結果が出たら、いちばん先に古くなる字**です。実測 09/04:

    長尺 236本 の中央   312.9秒（5.2分）      ← 「5分」はこの数。正しい
    直近の長尺 6本      1,104〜1,331秒（18〜22分） ← 外の作りを写した本。**もう 5分 ではない**
"""
from __future__ import annotations

import json

from src import daily_pick as dp


def _write(tmp_path, rows):
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_控えの秒数から中央と直近を出す(tmp_path) -> None:
    rows = [{"uploaded_at": "2026-09-01T00:00:00+00:00", "video_id": "a", "duration_s": 300.0},
            {"uploaded_at": "2026-09-02T00:00:00+00:00", "video_id": "b", "duration_s": 320.0},
            {"uploaded_at": "2026-09-03T00:00:00+00:00", "video_id": "c", "duration_s": 1200.0},
            {"uploaded_at": "2026-09-04T00:00:00+00:00", "video_id": "d", "duration_s": 1300.0}]
    got = dp.own_long_secs(recent=2, path=_write(tmp_path, rows))
    assert got["n"] == 4
    assert got["median"] == 760.0
    assert got["recent_median"] == 1250.0
    assert got["latest"] == 1300.0


def test_ショートは入らない(tmp_path) -> None:
    """**形の分かれ目は `forms.SHORT_MAX_SECONDS` の1か所**（写しを持たない）。"""
    from src.forms import SHORT_MAX_SECONDS
    rows = [{"video_id": "s", "duration_s": SHORT_MAX_SECONDS},
            {"video_id": "l", "duration_s": SHORT_MAX_SECONDS + 1}]
    got = dp.own_long_secs(path=_write(tmp_path, rows))
    assert got["n"] == 1 and got["median"] == SHORT_MAX_SECONDS + 1


def test_秒数が無ければ何も言わない(tmp_path) -> None:
    """**推測の数を出さないこと**（2026-08-25 より前の本には `duration_s` がありません）。"""
    got = dp.own_long_secs(path=_write(tmp_path, [{"video_id": "x"}]))
    assert got == {"n": 0, "median": None, "recent_median": None, "latest": None}


def test_控えが無くても倒れない(tmp_path) -> None:
    got = dp.own_long_secs(path=tmp_path / "nope.jsonl")
    assert got["n"] == 0


def test_画面に手で書いた尺が残っていないこと() -> None:
    """**この検査が、戻したときに鳴る側です。**"""
    import inspect
    src = inspect.getsource(dp.theory_lines)
    assert "自分の長尺は 5分" not in src
    assert "own_long_secs()" in src
