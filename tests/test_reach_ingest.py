"""`scripts/reach.py` の取り込み（**API を叩かない範囲**）。

2026-08-20 21:3x の実測: ジョブには報告が **35本**並んでいたのに、
この道具は `reports[-3:]` の **3本しか落としていませんでした**。
Reporting API は**ジョブを作った時点から30日ぶん遡って**日ごとの CSV を置くので、
**在るのに一度も読まれない日**が残ります（実測 3日 → 34日）。

だから固定するのは2つ:

- **積んだ報告のIDが読み戻せること**（同じ報告を二度落とさない）
- **既定で本数を切らないこと**（`--limit` を明示したときだけ切る）
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("reach_mod", ROOT / "scripts" / "reach.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_積んだ報告のIDを読み戻せる(tmp_path):
    mod = _load()
    p = tmp_path / "reach.jsonl"
    p.write_text(
        json.dumps({"date": "20260810", "video_id": "a", "_report_id": "r1"}) + "\n"
        + json.dumps({"date": "20260811", "video_id": "a", "_report_id": "r1"}) + "\n"
        + json.dumps({"date": "20260812", "video_id": "a", "_report_id": "r2"}) + "\n",
        encoding="utf-8")
    assert mod.seen_report_ids(p) == {"r1", "r2"}


def test_ファイルが無くても空で返る(tmp_path):
    mod = _load()
    assert mod.seen_report_ids(tmp_path / "ない.jsonl") == set()


def test_古い行にIDが無くても落ちない(tmp_path):
    """**8/20 より前に積んだ165行には `_report_id` がありません。**"""
    mod = _load()
    p = tmp_path / "reach.jsonl"
    p.write_text(json.dumps({"date": "20260815", "video_id": "a"}) + "\n"
                 + "こわれた行\n", encoding="utf-8")
    assert mod.seen_report_ids(p) == set()


def test_既定では報告の本数を切らない():
    """`limit=None` が既定。**数字が既定に戻ったら、また3本しか読みません。**"""
    mod = _load()
    assert inspect.signature(mod.show).parameters["limit"].default is None


def test_落とした報告のIDを行に書く():
    """書かなければ、次の回が同じものをもう一度落として二重に積みます。"""
    src = (ROOT / "scripts" / "reach.py").read_text(encoding="utf-8")
    assert '"_report_id"' in src


def test_CTRを100で割らない():
    """**この列は割合です**（`src.reach_split._clicks` に実物の裏取り）。"""
    src = (ROOT / "scripts" / "reach.py").read_text(encoding="utf-8")
    assert "float(row.get(ctr_col) or 0) / 100" not in src
