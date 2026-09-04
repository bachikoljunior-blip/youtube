"""`levers.latest_arm_state()` / `lever_notes()` —— **免除は、行をまたいで名前を替えないか。**

## なぜ要るか（2026-09-05 05:xx JST・最適化の回。**`scripts/eta.py` と同じ形が2つめ**）

`latest_arm_state()` は `data/eta.jsonl` を後ろから読み、**別々の行**から組みます::

    caps_row  … `arm_caps` を持つ最後の行（`lever_hint_covered` もここから）
    hint_row  … `lever_hint` を持つ最後の行（**名指しはこちらが勝つ**）

`lever_hint_covered`（「名指しした腕の測定は、もう予約済みの本が答える」）は
`eta.plan()` が `blocking["sample"]` ＝ **長尺の1本あたり再生の標本が
n≥`LONG_SAMPLE_MIN` に届く日**から積むもので、**`per_video` の免除**です。
`eta.solve()` はそのあと `gate_arm_pick()` で名指しを門1' の腕（`sub_rate`）へ
書き換えます。

**だから `caps_row` が `per_video`・`hint_row` が `sub_rate` という並びが普通に起きます。**
腕の名前を付けずに混ぜると、`lever_notes()` はこう出します::

    名指しは **`sub_rate`**（床は …）ですが、
    **その測定は予約済みの本が 2026-09-06 に答えます** ——
    `per_video` を引いたのは、`eta.py` の指示どおりです。

**免除ではないものが免除として通り、`sub_rate` を引かなかった回が許されます。**
`scripts/eta.py` の側では、この形で ship 239件 中 **90件（38%）**が出ていました
（引いた腕は `per_video` 69 ／ `none` 12 ／ **`sub_rate` 7**・`moves`≠0 は 3件）。

## ここで固定するもの

1. 免除には腕の名前が付く（`hint_covered_arm`）
2. **腕の名前は `caps_row` の側で確定する** —— `lever_hint` の上書きより**前**。
   後だと `hint_row` の名指しを拾って**必ず一致し、黙る**
3. 古い行（腕の欄が無い）は、**その行自身の名指し**を持ち主と読む
4. 腕が合わない免除では `lever_notes()` は許さない（＝ 理由を書けと訊く側に戻る）

## 覆る条件

`lever_hint_covered` が腕ごとの辞書になったら、この検査は要りません。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import levers  # noqa: E402


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "eta.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_行をまたいだ免除は腕の名前で落ちる(tmp_path):
    """**この検査のいちばんの中身。** 90件 が踏んだ並びをそのまま置く。"""
    path = _write(tmp_path, [
        # 古いほうの行: 軌跡を解いた回（`arm_caps` と `per_video` の免除）
        {"arm_caps": {"per_video": 4.54}, "lever_hint": "per_video",
         "lever_hint_covered": "2026-09-06",
         "lever_hint_covered_arm": "per_video", "binding": "再生数が天井"},
        # 新しいほうの行: 名指しが門1' で `sub_rate` に倒れた回
        {"lever_hint": "sub_rate", "binding": "再生数が天井"},
    ])
    st = levers.latest_arm_state(path)
    assert st["hint"] == "sub_rate"
    assert st["hint_covered_arm"] == "per_video"
    lines = "\n".join(levers.lever_notes("per_video", st))
    assert "`eta.py` の指示どおり" not in lines, (
        "`per_video` の免除が `sub_rate` の名前で許しになっている")
    assert "理由を docs/JOURNAL.md に1行書くこと" in lines


def test_腕が合っていれば今までどおり許す(tmp_path):
    path = _write(tmp_path, [
        {"arm_caps": {"per_video": 4.54}, "lever_hint": "per_video",
         "lever_hint_covered": "2026-09-06",
         "lever_hint_covered_arm": "per_video", "binding": "再生数が天井"},
    ])
    st = levers.latest_arm_state(path)
    assert st["hint"] == "per_video"
    lines = "\n".join(levers.lever_notes("density", st))
    assert "`eta.py` の指示どおり" in lines


def test_腕の欄が無い古い行はその行の名指しを持ち主と読む(tmp_path):
    """**2026-09-05 より前の `data/eta.jsonl` は、この欄を持ちません。**
    そのときは `caps_row` 自身の名指しが持ち主 —— 免除は必ず
    「その行の `lever_hint`」に対して書かれたからです。"""
    path = _write(tmp_path, [
        {"arm_caps": {"per_video": 4.54}, "lever_hint": "per_video",
         "lever_hint_covered": "2026-09-06", "binding": "再生数が天井"},
        {"lever_hint": "sub_rate", "binding": "再生数が天井"},
    ])
    st = levers.latest_arm_state(path)
    assert st["hint_covered_arm"] == "per_video", (
        "腕の欄を `lever_hint` の上書きより後で読んでいる。"
        "後だと `hint_row` の `sub_rate` を拾って必ず一致し、黙る")
    lines = "\n".join(levers.lever_notes("per_video", st))
    assert "`eta.py` の指示どおり" not in lines


def test_免除が無い行は腕の名前も立たない(tmp_path):
    path = _write(tmp_path, [
        {"arm_caps": {"per_video": 4.54}, "lever_hint": "per_video",
         "binding": "再生数が天井"},
    ])
    assert levers.latest_arm_state(path)["hint_covered_arm"] is None
