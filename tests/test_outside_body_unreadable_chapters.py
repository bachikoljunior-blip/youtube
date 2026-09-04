"""`outside_body_problems` —— **章が「無い」と「読めない」は別**（2026-09-04 20:5x に踏んだ）。

## なぜ要るか

`outside_body_problems` の docstring は、はっきりこう書いています::

    **`chapters` が無い台本は、何も言いません**（読めないものは通す ——
    `house_rule.needs_beyond_rule()` と同じ姿勢）。章の区切りが引けないので、
    (2) は測っていないのであって、守られていないのではありません。

その姿勢を実装していたのは `if chs:` の1行だけで、**見ているのは「無い」だけ**でした。
`starts` に入るのは `segment_index` が `int` の章だけなので、**章が在っても
1つも読めない**とき（たとえば `title` / `start` で書かれた章）`starts` は空になり、
`n = len(starts) - 1` が **-1** になって、こう刷られていました::

    冒頭を除く章が **-1つ**（5〜7つ。外の上位4本を写した形 …）

**「章が -1つ ある」ではなく「章が1つも読めなかった」です。**

## 直さないと何が起きるか

章の書き方が変わった日から、**全部の本が永久に直せない指摘を1つ持ちます。**
数は台本のせいではないので、`clarity_loop` / `generate()` の書き直しは
3回とも外して落ちます（`long_script_problems` 経由で毎回 撃たれる口です）。

**負の個数を刷らないこと** —— 数が負なら、それは中身の話ではなく読み手の話です。

**覆る条件**: 章に `segment_index` 以外の書き方を足すなら、そちらを読めるようにすること
（読めるようにするのが本筋で、この枝は「読めなかったと言う」ためだけに在ります）。
前提「外の作り方を写した長尺」が外れたら `OUTSIDE_LONG_RULE` ごと落とすので、ここも一緒に。
"""
import json
from pathlib import Path

from src import script_writer as sw

ROOT = Path(__file__).resolve().parent.parent


def _segs(n: int = 20) -> list[dict]:
    return [{"narration": "ふつうの文です。ふたつめです。",
             "visual": {"kind": "chart", "headline": "h"}} for _ in range(n)]


def test_読めない章では負の個数を刷らない():
    got = sw.outside_body_problems(
        {"segments": _segs(), "chapters": [{"title": "a", "start": 0},
                                           {"title": "b", "start": 4}]})
    assert not any("-1つ" in p for p in got), got
    assert any("読めるものが 1つもありません" in p for p in got), got


def test_読めない章でも締めは数える():
    """(3) 締めは章に依りません。**読めない章のせいで、数えられる脚まで落とさないこと。**"""
    got = sw.outside_body_problems(
        {"segments": _segs(), "chapters": [{"title": "a", "start": 0}]})
    assert any("締めの手順が無い" in p for p in got), got


def test_章が無い台本は今までどおり何も言わない():
    """docstring の姿勢そのもの。**章の検査は 1件も出ないこと**（(3) は別）。"""
    got = sw.outside_body_problems({"segments": _segs()})
    assert not any("章" in p for p in got), got


def test_実物の台本は今までどおり通る():
    """**この直しで、通っていた本を落としていないこと。**"""
    p = ROOT / "data" / "scripts" / "nenkin-uketorikata-65-70-75-handan.script.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    assert sw.outside_body_problems(d) == []


def test_章の数が足りない本は今までどおり落ちる():
    """**読めない章の枝を足したせいで、本物の (2a) が黙っていないこと。**"""
    chs = [{"segment_index": i * 4, "label": f"ch{i}"} for i in range(3)]
    got = sw.outside_body_problems({"segments": _segs(), "chapters": chs})
    assert any("冒頭を除く章が 2つ" in p for p in got), got
