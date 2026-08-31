"""**検査は、本物の `data/critique_queue/*.json` に書かないこと**（2026-08-28・通算9件目）。

## 何が起きたか（**統計の汚れでは済みません**）

`pytest tests/ -q -k "eta or cap or lever or drift or arm or forward"`
（**620件・13分00秒・全部 緑**）を背景で走らせている最中に、
`data/critique_queue/` の **19本**が書き換わりました:

    thumbnail_set: false → **true**   （19本とも同じ。実測 11:15:15）

**そして `data/day_quota.jsonl` に `thumbnails.set` は1行も増えていません**
（その窓の最後は **10:54:30**）—— **YouTube 側は動いておらず、
控えだけが嘘になりました。** 8件目（`data/uploaded.jsonl`）と同じ形です。

## なぜ「サムネイルくらい」で済まないか

`critique_queue.pending_thumbnails()` は **`thumbnail_set is False`** の本しか
返しません。push していれば、**その19本は `--missing` の一覧から永久に消え、
サムネイル無しのまま**残ります。サムネイルは面（インプレッション）そのもので、
`eta.py` の `rpm`（混ざり方 ＝ 面 × CTR）と `per_video` の**両方の腕**が
その上に立っています。**嘘が入る先が、腕の入力**でした。

## なぜ「呼ぶ側で気をつける」ではないのか

`src/upload_cap.py::_write_path`（08/27）と `src/dupes.py`（08/28）が
同じ理由で同じことを書いています ——「**関係のない検査に『その帳面に
気をつけろ』と約束させるのは無理**なので、書く側を機械で閉じる」。
**`data/critique_queue/` は、その掛かりに入っていませんでした。**

## 覆る条件

本物の控えへ**わざと**書く検査が要るようになったら `YT_LEDGER_WRITE=1`
（そのときは理由を `docs/JOURNAL.md` に）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import critique_queue  # noqa: E402


def _first_real_meta() -> Path | None:
    """本物の控えのうち、`thumbnail_set is False` の1本。**書けてしまうならここが動きます。**"""
    if not critique_queue.STASH.exists():
        return None
    for p in sorted(critique_queue.STASH.glob("*.json")):
        if p.name.endswith(".plan.json"):
            continue
        try:
            if json.loads(p.read_text(encoding="utf-8")).get("thumbnail_set") is False:
                return p
        except (OSError, ValueError):
            continue
    return None


def test_本物の控えは検査から書き換わらない():
    """**これが本体です。** 実際に `mark_thumbnail_set` を撃って、1バイトも動かないこと。"""
    meta = _first_real_meta()
    if meta is None:
        pytest.skip("`thumbnail_set is False` の本が手元にありません")
    before = meta.read_bytes()
    assert critique_queue.mark_thumbnail_set(meta.stem) is False, (
        "**検査から本物の控えに書けています。**`may_write_path` の掛かりが外れました")
    assert meta.read_bytes() == before, f"{meta} が書き換わりました"


def test_差し替えた先には今までどおり書ける(tmp_path, monkeypatch):
    """**黙らせただけにしないこと。** repo の外へ差し替えた検査は通ります。"""
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    (tmp_path / "zzz.json").write_text(
        json.dumps({"thumbnail_set": False}), encoding="utf-8")
    assert critique_queue.mark_thumbnail_set("zzz") is True
    assert json.loads((tmp_path / "zzz.json").read_text())["thumbnail_set"] is True


def test_無い本は今までどおり_False():
    assert critique_queue.mark_thumbnail_set("この動画IDは存在しません") is False


def test_掛かりは共通の口を使っている():
    """**正本は `src/dupes.may_write_path`**（`upload_cap` / `dupes` と同じ1つ）。"""
    import inspect
    src = inspect.getsource(critique_queue.mark_thumbnail_set)
    assert "may_write_path" in src, (
        "自前の門を書かないこと —— 掛かりが増えると、次に片方だけ直ります")
