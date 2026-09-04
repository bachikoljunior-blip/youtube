"""`OUTSIDE_LONG_RULE` の**5つ目の脚**（間合い）を数える口の検査。

規則の脚は4回に分けて数える側へ入りました —— 09-03 に (1) 冒頭、09-04 12:16 に
(2) 章・(3) 締め、12:55 に (4) 題とサムネ。**残っていたのは規則の中ほどの2行**です::

    - 各セグメントの narration は2〜4文。前提（年金額・単身・手取り率の置き方）は
      章の頭で毎回 言い直す。

**実測（2026-09-04・`style: outside_long` の実物 3本すべて）: 3本とも落ちます。
しかも (5a) と (5b) で落ちる本が分かれます** ——
`Ec-j1-W4nqw` は (5a) 16/58・(5b) 6/6 合格、`1huadpEk6HY` / `6PKux5HNnUE` は
(5a) 3/60・**(5b) 0/6**。＝ **片方だけ数えても、もう片方は黙って抜けます。**

だから、この検査が先に押さえるのは「実物が通ること」ではなく
**外れている中身で鳴ること**です（`tests/test_outside_title.py` と同じ姿勢）。
"""
from __future__ import annotations

import json
from pathlib import Path

from src import script_writer as sw

ROOT = Path(__file__).resolve().parents[1]


def _seg(nar: str) -> dict:
    return {"narration": nar, "visual": {"kind": "stat", "headline": "見出し"}}


def _ok_seg(n: int = 3) -> dict:
    return _seg("あ。" * n)


def _script(body, chapters=None):
    """冒頭 4コマ ＋ 本体。冒頭は (5a) の対象外なので、わざと長い文を置く。"""
    head = [_seg("あ。" * 9)] * sw.OUTSIDE_OPENING_SEGS
    out = {"segments": head + list(body)}
    if chapters is not None:
        out["chapters"] = chapters
    return out


def test_2文から4文なら何も言わない():
    s = _script([_ok_seg(2), _ok_seg(3), _ok_seg(4)])
    assert sw.outside_pacing_problems(s) == []


def test_5文以上のコマで鳴る():
    out = sw.outside_pacing_problems(_script([_ok_seg(3), _seg("あ。" * 5)]))
    assert len(out) == 1
    assert "5コマ目 5文" in out[0]


def test_1文のコマでも鳴る():
    """**上限だけ置かないこと。**片側だけの門は、検査そのものが速いほうへ押します
    （`verify._check_reveal_hold` が 2026-08-27 に踏んだ形）。"""
    out = sw.outside_pacing_problems(_script([_seg("あ。")]))
    assert len(out) == 1
    assert "4コマ目 1文" in out[0]


def test_冒頭4コマは数えない():
    """**規則どうしが、そこだけ逆を向いています。**

    (1) の冒頭の型は a〜e の5つを最初の 4コマ に入れろと命じており、5つ入れると
    4文 では収まりません（実測 `Ec-j1-W4nqw` の冒頭は 8/9/5/4 文 で
    `outside_opening_problems` は合格）。ここを鳴らすと、2つの検査が同じ本に
    **反対の直し**を命じます。
    """
    head_only = {"segments": [_seg("あ。" * 9)] * sw.OUTSIDE_OPENING_SEGS}
    assert sw.outside_pacing_problems(head_only) == []


def test_章の頭に前提が無いと鳴る():
    s = _script([_ok_seg(), _ok_seg(), _ok_seg(), _ok_seg()],
                chapters=[{"segment_index": 0, "label": "冒頭"},
                          {"segment_index": 5, "label": "ふたつ目"}])
    out = sw.outside_pacing_problems(s)
    assert len(out) == 1
    assert "章「ふたつ目」" in out[0] and "前提" in out[0]


def test_章の頭に前提が在れば言わない():
    body = [_ok_seg(), {"narration": "前提は同じです。次に決めます。",
                        "visual": {"kind": "stat", "headline": "見出し"}}, _ok_seg()]
    s = _script(body, chapters=[{"segment_index": 0, "label": "冒頭"},
                                {"segment_index": 5, "label": "ふたつ目"}])
    assert sw.outside_pacing_problems(s) == []


def test_冒頭の章は前提を求めない():
    """冒頭の章は `outside_opening_problems` の持ち場（`outside_body_problems` と同じ切り方）。"""
    s = _script([_ok_seg(), _ok_seg()],
                chapters=[{"segment_index": 0, "label": "冒頭"}])
    assert sw.outside_pacing_problems(s) == []


def test_章が無い台本には何も言わない():
    """読めないものは通す（`house_rule.needs_beyond_rule()` と同じ姿勢）。"""
    s = _script([_ok_seg(), _ok_seg()])
    assert sw.outside_pacing_problems(s) == []


def test_空の台本には何も言わない():
    assert sw.outside_pacing_problems({"segments": []}) == []


def test_数は規則の本文から引いていること():
    """**規則の本文と数える側が別々の数を持つと、この repo でいちばん多い壊れ方になります**
    （`OUTSIDE_CHAPTERS_LO` の註）。"""
    assert "2〜4文" in sw.OUTSIDE_LONG_RULE
    assert (sw.OUTSIDE_NARRATION_LO, sw.OUTSIDE_NARRATION_HI) == (2, 4)
    assert "章の頭で毎回 言い直す" in sw.OUTSIDE_LONG_RULE


def test_生成の輪へ配線されていること():
    """**数えても、呼ばれなければ 1件も止まりません。**
    (1)〜(4) と同じ枝（`style: outside_long`）に居ることを押さえます。"""
    import inspect
    src = inspect.getsource(sw.long_script_problems)
    assert "outside_pacing_problems(script)" in src, (
        "`long_script_problems()` が `outside_pacing_problems` を呼んでいません")


def test_実物の3本で鳴る_控えが在れば():
    """**実測を検査に残します。**控えが無い器では黙って飛ばします（`.gitignore` ではないが、
    まっさらな clone には在る）。"""
    seen = 0
    for name, want_pace, want_premise in (("Ec-j1-W4nqw", True, False),
                                          ("1huadpEk6HY", True, True),
                                          ("6PKux5HNnUE", True, True)):
        p = ROOT / "data" / "critique_queue" / f"{name}.script.json"
        if not p.exists():
            continue
        seen += 1
        out = sw.outside_pacing_problems(json.loads(p.read_text(encoding="utf-8")))
        pace = [o for o in out if "narration が" in o]
        premise = [o for o in out if "前提を言い直していない" in o]
        assert bool(pace) is want_pace, (name, out)
        assert bool(premise) is want_premise, (name, out)
    assert seen, "控えが1本も無い（この検査は何も押さえていません）"
