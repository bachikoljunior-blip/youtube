"""**「1本あたりが落ちた」を読むとき、落とした本を黙って消さないこと。**（2026-08-28）

## なぜこの検査が要るか（実測で1度 外しかけた）

オーナーの問い「1,2日間の動画前より再生数少ないのはなんで？」に答えるとき、
手元にあった道具は `scripts/per_day_views.py` だけでした。あれは本を
**2か所で黙って落とします**:

    (1) `--min-views 10` 未満 ＝「長尺とみなす」
    (2) 齢 24h ±35% に読みが無い

(2) の実害: **08-25 は帯内 10本 のうち 3本**にしか 24h の読みが無く、
あちらは「**3本 中央 226**」と印字します。**7本 落ちたことはどこにも出ません。**
齢を 20〜120h に広げた本当の中央は **220** で結論は変わりませんでしたが、
**それは運です** —— 落ちた 7本 が偏っていれば、逆の結論が同じ顔で出ます。

だから `scripts/per_video_why.py` は「読めた本 / 落とした本」を必ず並べます。
**この検査は、その欄が消えたら落ちます。**

## もう1つ守っているもの —— **帯を1つに決めない**

`src/day_cap.window()` は `confounded=True`（(A)本数 と (B)窓 の
どちらが上限かは**まだ決まっていない**）。実測 08-27 は
(A) が中央 **0**、(B) が **68** と食い違います。**片方だけを印字すると、
決まっていないことを決まったように見せます。**

**覆る条件**: `window()` が `confounded=False` になったら（切り分けの実測は
2026-09-02 に予約済み）、`verdict` の側だけを出してよくなります。
そのとき `test_shows_both_bands` は「両方 出すこと」を要求しなくなるので、
**この検査のほうを、その回に書き換えること。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import per_video_why as why      # noqa: E402

JST = timezone(timedelta(hours=9))


def _points(published: datetime, ages_views: list[tuple[float, int]]):
    """(齢, 再生) の並びから、`views.jsonl` と同じ形の点を作る。"""
    return [(h, v, (published + timedelta(hours=h)).astimezone(timezone.utc))
            for h, v in ages_views]


def test_aligned_returns_none_instead_of_guessing():
    """齢の合う読みが無い本は `None`。**近い値で埋めない。**"""
    pub = datetime(2026, 8, 25, 9, 0, tzinfo=JST)
    # 齢 5h の読みしかない ＝ 20〜120h に1つも無い
    assert why.aligned(_points(pub, [(5.0, 300)])) is None
    # 齢 48h があれば、それを採る
    assert why.aligned(_points(pub, [(5.0, 300), (48.0, 900)])) == 900


def test_aligned_takes_first_reading_in_range():
    """幅の中に何本あっても、**いちばん若い読み**で揃える（日ごとにブレさせない）。"""
    pub = datetime(2026, 8, 25, 9, 0, tzinfo=JST)
    got = why.aligned(_points(pub, [(24.0, 500), (48.0, 510), (96.0, 520)]))
    assert got == 500


def test_dropped_videos_are_counted_not_hidden(capsys):
    """**落とした本が出力に出ること。** これが消えたら 08-25 の読み違いが戻ります。"""
    pub_day = datetime(2026, 8, 25, tzinfo=JST)
    by = {}
    for i in range(10):
        pub = pub_day.replace(hour=9) + timedelta(minutes=30 * i)
        # 先頭3本だけ齢 24h の読みを持ち、残り7本は齢 5h しか無い
        ages = [(24.0, 200 + i)] if i < 3 else [(5.0, 10 + i)]
        by[f"v{i}"] = _points(pub, ages)

    rows = why.collect(by, {}, {}, "2026-08-01", "window", 10, 30.0, "13:30")
    assert len(rows) == 10, "帯には 10本 入るはず（落とすのは再生の読みだけ）"
    got = [r for r in rows if r["views"] is not None]
    missing = [r for r in rows if r["views"] is None]
    assert len(got) == 3 and len(missing) == 7, (
        "読めた3本・落とした7本。**この比が見えないと「3本 中央226」になります**")


def test_shows_both_bands(capsys):
    """`window()` が切り分いていないあいだは、**(A)本数 と (B)窓 を両方**出すこと。"""
    rc = why.main(["--since", "2026-08-19"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "(A)" in out and "(B)" in out, "片方だけの帯で印字してはいけません"
    assert "落とした" in out or "n/落" in out, "落とした本の欄が消えています"


def test_band_params_are_pulled_not_copied():
    """帯の数は `src/day_cap.py` から引くこと（**写すと、動いた日にここだけ古びます**）。"""
    from src import day_cap
    cap_n, gap_min, edge, _decided = why.band_params()
    assert cap_n == day_cap.cap()
    assert gap_min == day_cap.MIN_GAP_MIN
    assert edge == str(day_cap.window().get("T"))


def test_count_and_window_disagree_when_early_videos_die():
    """08-27 の形 —— 早い時間に出した本があると、2つのモデルは別の帯を返す。"""
    day = datetime(2026, 8, 27, tzinfo=JST)
    rows = [(day.replace(hour=5) + timedelta(minutes=30 * i), f"early{i}") for i in range(8)]
    rows += [(day.replace(hour=9) + timedelta(minutes=30 * i), f"live{i}") for i in range(10)]
    count = why.band_of_day(rows, "count", 10, 30.0, "13:30")
    window = why.band_of_day(rows, "window", 10, 30.0, "13:30")
    assert count[:8] == [f"early{i}" for i in range(8)], "本数モデルは先頭10本を採る"
    assert len(window) == 18, "窓モデルは 13:30 までを全部 採る"
    assert count != window, "食い違う日があるからこそ、両方 出す意味があります"
