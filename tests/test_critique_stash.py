"""独立評価の材料に `slides_plan.json` を残す（5回持ち越された項目）。

## なぜ残すか（2026-08-15）

`data/critique_queue` には contact sheet と読み上げ文しか入っていませんでした。
**どちらも焼き上がった絵で、焼き直せません。**

8/15 22:0x の回は「実質同じ絵か」を測るために**動画を2本生成しています**
（11分×2）。`slides_plan.json`（＝割った後のコマの列）さえ残っていれば
`scripts/bake_slides.py --plan` で **30秒**、生成0回で済みました。
材料が21本ぶん積んであったのに、**測れる形で積んでいなかった**ということです。

## この検査が見ているもの

1. `slides_plan.json` があれば `<動画ID>.plan.json` として残ること
2. **無くても投稿は止めないこと**（材料が半分でも投稿のほうが優先）
3. **`pending()` が `*.plan.json` を待ちとして数えないこと**

3 が本体です。材料を隣に置いた瞬間、`STASH.glob("*.json")` が
**1本につき2件返すようになります。** 中身は台本ではないので `video_id` が無く、
`meta.stem` から `"<ID>.plan"` という**架空の待ち**が生えます。しかも
その名前で点を付けることはできないので、**永久に消えません。**
`_scored()` が `video` と `video_id` の綴り違いで常に空集合を返していたのと
同じ壊れ方（落ちも警告も出ず、件数を見ても正しく見える）なので、検査で止めます。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import critique_queue  # noqa: E402

SCRIPT = {
    "short": True,
    "segments": [
        {"narration": "副業所得が1円ふえると手取りは1万円減ります"},
        {"narration": "20万円ちょうどなら手取りは18万円です"},
    ],
}
PLAN = [{"kind": "stat", "head": "副業20万円"}, {"kind": "chart", "head": "手取りの差"}]


@pytest.fixture()
def stash_dir(tmp_path, monkeypatch):
    """`data/critique_queue` を tmp に差し替える。**本物を汚さないこと。**"""
    d = tmp_path / "queue"
    monkeypatch.setattr(critique_queue, "STASH", d)
    monkeypatch.setattr(critique_queue, "LEDGER", tmp_path / "critique.jsonl")
    return d


def _work(tmp_path: Path, with_plan: bool) -> Path:
    work = tmp_path / "build" / "s-fukugyo-1"
    work.mkdir(parents=True)
    (work / "inspect.jpg").write_bytes(b"\xff\xd8\xff\xe0not-a-real-jpeg")
    if with_plan:
        (work / "slides_plan.json").write_text(
            json.dumps(PLAN, ensure_ascii=False), encoding="utf-8"
        )
    return work


def test_plan_is_kept(tmp_path, stash_dir):
    """`slides_plan.json` があれば `<動画ID>.plan.json` として残る。"""
    work = _work(tmp_path, with_plan=True)
    critique_queue.stash("s-fukugyo-1", "VID0000001", SCRIPT, work)

    plan = stash_dir / "VID0000001.plan.json"
    assert plan.exists(), "焼き直す入力が残っていません"
    assert json.loads(plan.read_text(encoding="utf-8")) == PLAN

    meta = json.loads((stash_dir / "VID0000001.json").read_text(encoding="utf-8"))
    assert meta["slides_plan"] is True


def test_missing_plan_does_not_block(tmp_path, stash_dir):
    """**無くても投稿は止めない。** 材料が半分でも、投稿のほうが優先。"""
    work = _work(tmp_path, with_plan=False)
    out = critique_queue.stash("s-fukugyo-1", "VID0000002", SCRIPT, work)

    assert out is not None, "plan が無いだけで材料ごと捨ててはいけません"
    assert (stash_dir / "VID0000002.jpg").exists()
    assert not (stash_dir / "VID0000002.plan.json").exists()

    meta = json.loads((stash_dir / "VID0000002.json").read_text(encoding="utf-8"))
    assert meta["slides_plan"] is False, "**残せなかったことが分かる形で記録すること**"


def test_plan_file_is_not_counted_as_a_pending_video(tmp_path, stash_dir):
    """**これが本体。** `*.plan.json` を待ちとして数えないこと。

    数えると、1本を投稿しただけで待ちが2件に増えます
    （しかも片方は `"<ID>.plan"` という、点の付けられない架空の動画）。
    """
    work = _work(tmp_path, with_plan=True)
    critique_queue.stash("s-fukugyo-1", "VID0000003", SCRIPT, work)

    rows = critique_queue.pending()
    ids = [r["video_id"] for r in rows]
    assert ids == ["VID0000003"], f"待ちが増えています: {ids}"
    assert not any(i.endswith(".plan") for i in ids)


def test_plan_that_is_a_bare_list_does_not_crash(tmp_path, stash_dir):
    """`slides_plan.json` は**辞書ではなく配列**です。

    `pending()` が誤って読みにいくと `d.get(...)` が AttributeError で落ちます。
    **落ちるのは待ち行列を見るときで、投稿の後**なので、
    次の回まで気づけません。名指しで固定しておく。
    """
    work = _work(tmp_path, with_plan=True)
    critique_queue.stash("s-fukugyo-1", "VID0000004", SCRIPT, work)
    assert isinstance(json.loads((stash_dir / "VID0000004.plan.json").read_text()), list)
    critique_queue.pending()  # 落ちなければよい
