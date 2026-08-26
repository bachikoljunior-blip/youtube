"""**長尺を、同じ日に複数 置けること**（2026-08-26・最適化の回）。

## なぜこの試験が要るか

`scripts/batch_build.py` の `LONG_HOUR_JST = 20` は、同じ日の朝に
「9時はショートで埋まっているので、長尺の1本目が 33日 後ろへ流れる」を
直したものです。**ところが直ったのは1本目だけでした。**

`slots()` は `--date` が無いと `[str(hour)] * count` を返し、
`uploader.next_publish_at()` は「**その時刻で最初に空いている日**」を返します。
つまり**同じ時刻を N回 渡すと N日 に1本ずつ**ばらけます。

実測（2026-08-26 16:0x・控え545本）:

    長尺は 08/25 に 25本、08/26 に 3本 作られている（`uploaded_at`）
    その 28本 の**予約日**は 08/26〜10/05 の **21日** に散っている ＝ 1.3本/日

**4,000時間の門に入るのは長尺だけ**なので（`src/levers.py`／`src/day_cap.py`）、
長尺の公開が後ろへ流れたぶん、**開いている唯一の門だけが止まります。**
ショートは 99.9% の再生を取っていますが、その門には1分も積みません
（実測・直近28日: `SHORTS_FEED` 64,283再生 ／ `WATCH` 67再生）。

## ここが壊れたと分かる形

`slots()` が長尺の回でも1つの時刻しか配らなくなったら、
**この試験の `同じ日に入る` が落ちます。**
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("bb", ROOT / "scripts" / "batch_build.py")
bb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bb)


def test_ring_gives_distinct_hours():
    """**輪は、別々の時刻を配ること。** 同じ時刻の繰り返しなら1日1本に戻ります。"""
    ring = bb._long_ring()
    assert len(ring) >= 1
    assert len(set(ring)) == len(ring), f"時刻が重なっています: {ring}"


def test_slots_packs_long_form_into_one_day():
    """`ring` を渡した回は、**先頭 len(ring) 本が全部ちがう時刻**になること。"""
    ring = (20, 21, 22, 19, 18)
    got = bb.slots(5, bb.LONG_HOUR_JST, None, [], ring=ring)
    assert got == ["20", "21", "22", "19", "18"]
    assert len(set(got)) == 5, "同じ時刻が混ざると、その2本は別々の日へ流れます"


def test_slots_without_ring_is_unchanged():
    """**`ring` を渡さない回は、今までどおり**（ショートの回を変えないこと）。

    ショートは `SHORTS_FEED` の上限（`day_cap.cap()`）の内側で争っているので、
    詰めても再生は増えません。**ここを共通の既定にしないこと。**
    """
    assert bb.slots(4, 9, None, []) == ["9", "9", "9", "9"]


def test_ring_wraps_to_next_day():
    """`len(ring)` を超えたぶんは輪の先頭へ戻り、**翌日へ回ること**。"""
    ring = (20, 21)
    assert bb.slots(5, 20, None, [], ring=ring) == ["20", "21", "20", "21", "20"]


def test_ring_never_exceeds_measured_ceiling():
    """**測っていない天井を、黙って測りにいかないこと。**

    `src/day_cap.long_form()` の `most` は「いちばん多く出した日の本数」で、
    `collapsed=False` は「そこまでは崩れていない」。**その上は未観測**です
    （`measured=False`）。`_long_ring()` が `most` を超えたら、
    それは前提を立てずに実験を始めたということ。
    """
    from src import day_cap
    lf = day_cap.long_form()
    most = int(lf.get("most") or 0)
    ring = bb._long_ring()
    if most > 0:
        cap = (most - 1) if lf.get("collapsed") else min(most, bb.LONG_PER_DAY)
        assert len(ring) <= max(1, cap), (
            f"輪 {len(ring)}本/日 が実測の上限 {cap} を超えています。"
            "上げるなら config/hypotheses.yaml に前提として立てること")
