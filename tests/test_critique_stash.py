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

    rows = critique_queue.pending(deadline={})
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
    critique_queue.pending(deadline={})  # 落ちなければよい


# ---------------------------------------------------------------------------
# 待ち行列の**並び**（2026-08-16。持ち越し7回目を、原因のほうから閉じた）
#
# 1周で回せるのは1〜3本、待ちは38本。**つまり順番が選択そのものです。**
# それまでの並びは `sorted(glob("*.json"))` ＝ **動画IDのアルファベット順**で、
# 評価の値打ちと何の関係もありませんでした。実測（8/16 11:2x・待ち38本）:
#
#     `--next` の先頭    J0QK59pUg-4  公開まで **あと244時間**
#     いちばん近い本     crO3FUvL2NI  あと **22時間** なのに **24番目**
#     上位10件のうち4件  **予約なし**（重なりで外した本＝二度と公開されない）
#
# **予約なしを評価しても直す先がありません。** engaged も付かないので M13 の
# 較正にも入らない ＝ `claude -p` 3体ぶんが丸ごと捨てになります。
# ---------------------------------------------------------------------------


def _stash_many(tmp_path: Path, ids: list[str]) -> None:
    for i, vid in enumerate(ids):
        work = tmp_path / "build" / f"t{i}"
        work.mkdir(parents=True)
        (work / "inspect.jpg").write_bytes(b"\xff\xd8\xff\xe0x")
        critique_queue.stash(f"s-topic-{i}", vid, SCRIPT, work)


def test_queue_is_ordered_by_deadline_not_by_video_id(tmp_path, stash_dir):
    """**締切の近い順**に返すこと。動画IDの綴りは値打ちと無関係です。"""
    _stash_many(tmp_path, ["AAA0000001", "BBB0000002", "CCC0000003"])
    # AAA が一番遠く、CCC が一番近い ＝ **アルファベット順とちょうど逆**
    dl = {"AAA0000001": (0, 500.0), "BBB0000002": (0, 200.0), "CCC0000003": (0, 22.0)}

    ids = [d["video_id"] for d in critique_queue.pending(deadline=dl)]
    assert ids == ["CCC0000003", "BBB0000002", "AAA0000001"], ids


def test_stranded_videos_are_not_offered(tmp_path, stash_dir):
    """**予約なしは既定で出さない。** 直す先も engaged も無いので捨てになります。"""
    _stash_many(tmp_path, ["AAA0000001", "BBB0000002"])
    dl = {"AAA0000001": (2, 0.0), "BBB0000002": (0, 100.0)}

    ids = [d["video_id"] for d in critique_queue.pending(deadline=dl)]
    assert ids == ["BBB0000002"], ids

    # **黙って消さないこと。** 見たいときは出せる。
    both = [d["video_id"] for d in critique_queue.pending(include_stranded=True, deadline=dl)]
    assert sorted(both) == ["AAA0000001", "BBB0000002"], both


def test_published_ranks_after_scheduled_but_before_stranded(tmp_path, stash_dir):
    """公開済みは**直せません**が、engaged が付くので M13 の較正には使えます。

    だから「予約あり（＝まだ直せる）→ 公開済み（＝計器になる）」の順。
    """
    _stash_many(tmp_path, ["AAA0000001", "BBB0000002", "CCC0000003"])
    dl = {
        "AAA0000001": (1, 0.0),      # 公開済み
        "BBB0000002": (0, 400.0),    # 予約あり（遠い）
        "CCC0000003": (2, 0.0),      # 予約なし
    }
    ids = [d["video_id"] for d in critique_queue.pending(include_stranded=True, deadline=dl)]
    assert ids == ["BBB0000002", "AAA0000001", "CCC0000003"], ids


def test_unknown_deadline_is_not_treated_as_disposable(tmp_path, stash_dir):
    """締切が**分からない**本を「捨ててよい」と読まないこと。

    口が落ちた回や、控えにも無い本がこれに当たります。段0の末尾
    （＝予約ありの一番後ろ）に置き、**予約なしと同じ扱いにはしません。**
    """
    _stash_many(tmp_path, ["AAA0000001", "BBB0000002"])
    dl = {"BBB0000002": (2, 0.0)}   # AAA は口に無い

    ids = [d["video_id"] for d in critique_queue.pending(deadline=dl)]
    assert ids == ["AAA0000001"], f"締切不明が消えています: {ids}"


def test_critique_run_uses_the_same_queue(tmp_path, stash_dir, monkeypatch):
    """**待ち行列の定義は1か所だけ。**

    `critique_run.pending_ids()` は長らく `glob` を自前でもう一度書いており、
    直しが片方にしか入らない形が**通算7回**続きました（`*.plan.json` の偽物・
    `--next` の `[:1]`・この並び）。**数えるのをやめて、片方を消しています。**
    ここが自前の実装に戻っていたら、この検査が落ちます。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import critique_run
    assert critique_run.pending_ids.__module__ == "critique_run"

    _stash_many(tmp_path, ["AAA0000001", "BBB0000002"])
    monkeypatch.setattr(critique_queue, "deadlines",
                        lambda *a, **k: ({"AAA0000001": (0, 500.0),
                                          "BBB0000002": (0, 20.0)}, "test"))
    assert critique_run.pending_ids() == ["BBB0000002", "AAA0000001"]
