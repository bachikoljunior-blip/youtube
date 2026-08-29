"""走査の一枚に欠けている **尺** を、後ろの枚から**全部**補う。

**なぜ要るか（2026-08-30 に測って直した）。**
`_last_scan()` は、尺を持つ**最初の一枚**を見つけた時点で補いを打ち切っていました
（`missing.remove(mt)` が無条件）。**一枚が全部の本の尺を持っている前提**です。
持っていません —— 走査の一枚は「その窓で再生のあった本」で作られ、
Data API が途中で日枠に当たれば**部分的に埋まった一枚**が積まれます。

実測（`data/scan.jsonl` 240枚・2026-08-30 02:4x）::

    最後の一枚          156本 ／ 尺を持つ本 **0本**
    一枚だけ補う（前）   尺が付いた本 50本  → 180秒以上 **6本**  ＝ **19再生**
    全部の枚を補う（後） 尺が付いた本 156本 → 180秒以上 **18本** ＝ **137再生**

これは印字だけの話ではありません。待ち `長尺-1000再生`
（腕 `sub_rate` ／ 側 `dist`。`eta.py --alloc` が**いちばん早い腕**と名指し）が
この数で満ち具合を見ており、**同じ閾値を見ている台帳側（286）と 15倍**
ちがっていました。しかも「どの一枚が最初に尺を持つか」は回ごとに変わるので、
**再生が減らないのに `伸び -8.00/日` と出ます**（補いの当たり外れが、
実測の増減に化ける）。

**覆る条件**: `IMMUTABLE_METRICS` に本当は動くものが足されたら、
この全走査は古い値を混ぜる道になります。足すときに確かめること。
"""
from __future__ import annotations

import json

from src import watches


def _line(vals: dict) -> str:
    return json.dumps({"values": vals}, ensure_ascii=False)


def _scan(tmp_path, monkeypatch, lines: list[str]):
    p = tmp_path / "scan.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(watches, "SCAN", p)
    return p


def test_尺は一枚で打ち切らず後ろの枚からも補う(tmp_path, monkeypatch):
    # 古い枚ほど手前。最後の一枚は尺を1本も持っていない（Data API が日枠で 403）。
    _scan(tmp_path, monkeypatch, [
        # いちばん古い枚だけが B の尺を持つ
        _line({"動画.B.尺": 400, "動画.B.views": 1}),
        # 次の枚は A の尺しか持たない ← ここで打ち切っていたのが欠陥
        _line({"動画.A.尺": 500, "動画.A.views": 1}),
        # 最後の一枚: 尺が丸ごと空
        _line({"動画.A.views": 60, "動画.B.views": 77, "動画.C.views": 5}),
    ])
    rows = watches._last_scan()
    assert rows["A"]["尺"] == 500
    assert rows["B"]["尺"] == 400, "**後ろの枚を読まずに打ち切っていた**"
    assert "尺" not in rows["C"], "どの枚にも無い本は、埋めないこと"


def test_長尺の合計が一枚ぶんで切られない(tmp_path, monkeypatch):
    _scan(tmp_path, monkeypatch, [
        _line({"動画.B.尺": 400}),
        _line({"動画.A.尺": 500}),
        _line({"動画.A.views": 60, "動画.B.views": 77, "動画.C.views": 5}),
    ])
    g = watches._k_scan_sum({"metric": "views", "min_length": 180, "need": 1000})
    # 打ち切っていた頃は A だけ ＝ 60。両方 拾えば 137。
    assert g.now == 137.0
    assert "2本" in g.note


def test_最後の一枚が尺を持っていれば後ろは読まない(tmp_path, monkeypatch):
    """**新しい側が勝つこと**（`setdefault` の向きを固定する）。"""
    _scan(tmp_path, monkeypatch, [
        _line({"動画.A.尺": 999}),
        _line({"動画.A.尺": 500, "動画.A.views": 60}),
    ])
    assert watches._last_scan()["A"]["尺"] == 500
