"""**作った本を、48日 先の車線へ置かない。**

## この試験が守っているもの（2026-08-27・最適化の回）

`uploader.next_publish_at()` は**時刻を一度も動かしません**（`target += timedelta(days=1)`
だけ）。`batch_build.slots()` は `--date` の無い回に `[str(hour)] * count` を返すので、
**その時刻が埋まっている日数ぶん、新しい本はそのまま後ろへ落ちます。**

実測（2026-08-27 の控え 362本）: 既定の **09:00 は 48日 先**まで埋まっていて、
同じ日の**生きる帯**（05:00〜13:30・`src/collisions.py`）には空き枠が 5〜8個 ありました。
開いている前提の期日はいちばん遠くて **17日 先**なので、
**48日 先に置いた本は、いま開いている前提を1件も閉じません。**

`eta.py` は「軌跡の腕が動くのは前提を1件閉じたときだけ」と印字します。
つまり **48日 先の本は、到達日を1日も動かせません。**

## 壊れ方の形

**印字は正しいまま、実際だけがずれます。** `batch_build` は
「予約は 9:00 JST の空き枠へ」と言い、`slots()` は文字を組み立てるだけで、
日を決めるのは20分あとの `next_publish_at` です。だから
**渡した側からは正しく動いているように見えます**（`batch_build` の
`--date` の節が、同じ形の欠陥を別の場所で記録しています）。
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build as bb                                       # noqa: E402
import queue_lag                                               # noqa: E402

JST = timezone(timedelta(hours=9))


def _rows(pairs: list[tuple[date, tuple[int, int]]]) -> list[dict]:
    """`queue_lag.scheduled()` が返す形（`at` は JST 付きの datetime）。"""
    return [{"at": datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=JST)}
            for d, hm in pairs]


@pytest.fixture()
def 控え(monkeypatch):
    """**09:00 だけ 40日ぶん埋まっている**控え。帯の他の枠は全部 空き。"""
    today = datetime.now(JST).date()
    pairs = [(today + timedelta(days=i), (9, 0)) for i in range(1, 41)]
    monkeypatch.setattr(queue_lag, "scheduled", lambda *a, **k: _rows(pairs))
    monkeypatch.setattr(queue_lag, "_in_window", lambda d: False)
    return today


def _land(spec: str, taken: dict, today: date) -> int:
    """`next_publish_at()` と同じ探し方で、その指定が着地する日（何日後か）。"""
    hh, _, mm = spec.partition(":")
    hm = (int(hh), int(mm or 0))
    for i in range(1, 91):
        if hm not in taken.get(today + timedelta(days=i), set()):
            return i
    return 91


def test_埋まった車線ではなく帯の空きを選ぶ(控え):
    """**これが本体です。** 09:00 は 40日 先、帯の空きは 1日 先。"""
    today = 控え
    taken = {d: set(s) for d, s in
             queue_lag._taken(queue_lag.scheduled()).items()}

    picked = bb.live_ring(4)
    assert picked, "帯の空きが読めていません"

    新 = [_land(s, taken, today) for s in picked]
    旧 = [_land("9", taken, today) for _ in picked]

    assert max(新) < min(旧), (
        f"帯の空きのほうが後ろです（新 {新} / 旧 {旧}）。"
        "**この試験が守っているのは、そこだけです**"
    )
    assert min(旧) >= 40, "この試験の前提（09:00 が埋まっている）が崩れています"


def test_選ぶのは生きる帯の中だけ(控え):
    """**帯の外へ逃がさないこと。** 空いているだけの 20:00 は、生死が未測定です。"""
    band = set(bb._band_grid())
    for spec in bb.live_ring(8) or []:
        hh, _, mm = spec.partition(":")
        assert (int(hh), int(mm or 0)) in band, f"帯の外を選びました: {spec}"


def test_同じ日に上限を超えて積まない(控え):
    """**(A)（1日 C本 まで）で死ぬ置き方をしないこと。**

    `day_cap` の (A)/(B) は未判定なので、**どちらでも損をしない側**へ倒します ——
    帯へ置くのは (B) なら上積み、(A) なら「早く出た C本」の側です。
    ただし **1日に C本 を超えて積むと (A) では死ぬ**ので、そこは日を割ります。
    """
    today = 控え
    from src import day_cap
    cap = int(day_cap.cap())
    band = set(bb._band_grid())

    taken = {d: set(s) for d, s in
             queue_lag._taken(queue_lag.scheduled()).items()}
    for spec in bb.live_ring(cap * 3) or []:
        hh, _, mm = spec.partition(":")
        hm = (int(hh), int(mm or 0))
        i = _land(spec, taken, today)
        taken.setdefault(today + timedelta(days=i), set()).add(hm)

    for d, s in taken.items():
        n = sum(1 for t in s if t in band)
        assert n <= cap, f"{d} の帯に {n}本（上限 {cap}）"


def test_明示した回には触らない(控え, monkeypatch):
    """`--hour` / `--hours` / `--date` / 長尺の輪は**指示**なので、探索に掛けません。

    門は2枚あります。`live=False`（呼ぶ側が `--hour` などを見て決める）と、
    `ring`／`date_jst`（`slots()` の中で先に返る道）。**どちらも `live_ring()`
    を呼びません** —— 呼んだら落ちるように差し替えて確かめます。
    """
    def 呼ぶな(*a, **k):                                       # noqa: ANN002
        raise AssertionError("明示した回に live_ring() を呼びました")

    monkeypatch.setattr(bb, "live_ring", 呼ぶな)
    assert bb.slots(3, 9, None, [], live=False) == ["9", "9", "9"]
    assert bb.slots(3, 20, None, [], ring=(20, 21), live=True) == ["20", "21", "20"]
    # `--date` の道は帯を見ません（日に釘づけ ＝ 測定のための置き方）
    明日 = (datetime.now(JST).date() + timedelta(days=3)).isoformat()
    assert all(w.startswith(明日) for w in
               bb.slots(2, 11, 明日, [11, 12], taken=set(), live=True))


def test_読めない回は今までどおりに倒す(monkeypatch):
    """**黙って粗くしないこと。** 控えが読めなければ `None` を返し、呼ぶ側が既定へ戻ります。"""
    monkeypatch.setattr(queue_lag, "scheduled", lambda *a, **k: [])
    assert bb.live_ring(3) is None
    assert bb.slots(3, 9, None, [], live=True) == ["9", "9", "9"]


def test_帯は写さずに実物から引く():
    """**べた書きしないこと。** 上端もきざみも、測っている側が動けば一緒に動きます。"""
    from src import collisions, day_cap
    grid = bb._band_grid()
    assert grid[-1][0] * 60 + grid[-1][1] <= collisions.LIVE_TO_MIN
    step = (grid[1][0] * 60 + grid[1][1]) - (grid[0][0] * 60 + grid[0][1])
    assert step == int(day_cap.MIN_GAP_MIN), (
        "きざみが `day_cap.MIN_GAP_MIN`（これより詰めた本は死ぬ）と食い違っています"
    )


def test_測定中の帯へは置かない():
    """**その測定は 2026-08-27 に終わりました。答えは「前は生きない」**です。

    05:00〜08:30 に置いた 8本は**全部 0再生**（齢 7.5〜11時間・8本とも
    `public`/`processed`）。生きたのは 08:59 以降の10本だけです。

    だから `collisions.LIVE_FROM_MIN` は **09:00 へ戻して**あり、
    `PROVEN_FROM_MIN` と**同じ**になりました ——
    「まだ測っている最中の帯」は、もう存在しません。

    **覆る条件**: 左端は面が育てば早い時刻へ動くかもしれません
    （`day_cap.left_edge()` が毎回その場で測り直します）。
    そのときは両方の下端が一緒に下がるので、この試験はそのまま効きます。
    """
    from src import collisions, day_cap
    grid = bb._band_grid()
    assert min(h * 60 + m for h, m in grid) == bb.PROVEN_FROM_MIN
    assert bb.PROVEN_FROM_MIN >= collisions.LIVE_FROM_MIN, (
        "生きると測れている下端より前を、置き先にしています"
    )
    # 枠の数と1日の上限は、どちらも 08/21 の同じ実測から来ています
    assert len(grid) == int(day_cap.cap()), (
        f"枠 {len(grid)} と 1日の上限 {day_cap.cap()} が食い違っています —— "
        "どちらかが測り直しで動いたのに、片方だけが残っています"
    )
