"""**維持率の道具が、空で正常終了していた**（2026-08-27）。

`scripts/retention.py` の `videos()` は `data/scan.jsonl` の `尺` 1本道でした。
**その欄は最新の一枚から消えています** —— 実測 2026-08-27: **130本 中 0本**。
だから `videos()` は **130 → 0本** を返し、道具は見出しだけ出して
**1本も描かずに終了コード0で終わります。落ちません。**

結果、`data/retention.json` は 2026-08-20 で止まり、貯まっている21本は
**全部 2026-08-15 以前 ＝ 旧設計**。**いまの作りの維持率カーブは1本もありません。**

`length_of()` が3つの出どころを順に当てて、**123/130本**まで戻しました。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("retention_mod",
                                               ROOT / "scripts" / "retention.py")
retention = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retention)


def test_走査の尺があればそれを使う():
    assert retention.length_of({"id": "x", "尺": 61.0,
                                "averageViewDuration": 9,
                                "averageViewPercentage": 50.0}) == 61.0


def test_走査に尺が無ければ導出する():
    """`averageViewDuration ÷ averageViewPercentage × 100`。
    **これが無いと 0本 に戻ります**（実測 130本 中 0本 が `尺` 欠け）。
    """
    got = retention.length_of({"id": "x", "averageViewDuration": 23,
                               "averageViewPercentage": 76.85})
    assert got is not None
    assert abs(got - 29.93) < 0.05


def test_割合が0や欠けなら当て推量をしない():
    """**無いものを、無いと言うこと。** 当てると横軸が黙って狂います。"""
    assert retention.length_of({"id": "x", "averageViewDuration": 23,
                                "averageViewPercentage": 0}) is None
    assert retention.length_of({"id": "x", "averageViewDuration": 23}) is None
    assert retention.length_of({"id": "x"}) is None


def test_実物の走査から本が拾えること():
    """**この検査が 0本 で通ったら、道具はまた死んでいます。**

    ここが「1本でもあること」を見るのは、`videos()` が**空を返しても
    落ちない**からです（それが 2026-08-20〜27 の1週間 起きていたこと）。
    """
    vs = retention.videos()
    assert len(vs) > 50, f"走査から拾えた本が {len(vs)}本 しかありません"
    for v in vs:
        assert v["尺"] > 0
        assert "尺_導出" in v, "導出で埋めたかの旗が要ります（秒の議論に幅が要るため）"


def test_導出で埋めた本には旗が立つ():
    """秒の議論に使う回が、**±0.5÷(割合/100) 秒**の幅を書けるように。"""
    vs = retention.videos()
    derived = [v for v in vs if v["尺_導出"]]
    assert derived, "いまの走査は `尺` を持たないので、全部 導出のはずです"
