"""**`--compact` は、再生の付かない枠へ本を詰めてはいけない。**

`spread_plan` は 2026-08-24 に「置き先は『生きる目盛り』の中だけ」へ直りました。
**`compact_plan` は直っていませんでした** —— 同じファイルの、すぐ上の関数です。
あちらの docstring が過去形で「直した」と書いているので、
**こちらも直っていると読めてしまう**のが、この穴の残り方でした。

実測（2026-08-28・公開済みのショートを公開時刻べつに数えた）:

    08〜13時   95本 / 生きた 93本 / 1本あたり 566〜744再生
    14〜21時   31本 / 生きた  5本 / ほとんどの時が 1本あたり 0.5〜2.0

`--compact` の目盛りは既定 9〜21時 なので、**11本目から先は 0再生の枠**でした。

**覆る条件**: `day_cap` の帯が広がったら、`_live_edge_min()` の返りが広がり、
この検査の期待値もいっしょに動きます（**日付も時刻も直に書いていません**）。
帯そのものが「本数ではなく時刻の窓だ」と判定されたら
（`config/hypotheses.yaml` の 2026-09-02 の切り分け）、
`scripts/batch_build.py` の註が言うとおり `collisions.LIVE_FROM_MIN` 側へ
左端を差し替えることになります。**そのときもこの検査は式のまま通ります。**
"""
from __future__ import annotations

import datetime
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "reschedule_mod", ROOT / "scripts" / "reschedule.py")
resched = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(resched)

JST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc


def _rows(n: int, *, start_day: str) -> list[dict]:
    """`n` 本を、**遠い先の 21:00** に1本ずつ置いた控えを作る。

    遠くに置くのは、`compact_plan` が「前へ詰める」道具で、
    **後ろへ動かす割り当てになると例外を上げる**ためです。
    """
    d0 = datetime.date.fromisoformat(start_day)
    out = []
    for i in range(n):
        at = datetime.datetime(d0.year, d0.month, d0.day, 21, 0, tzinfo=JST) \
            + datetime.timedelta(days=i)
        out.append({"id": f"v{i:03d}", "topic": f"t-{i}", "title": f"T{i}",
                    "at": at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out


def test_live_edge_min_keeps_every_slot_inside_the_band():
    """**渡した右端より後ろの目盛りは、1つも使われない。**"""
    now = datetime.datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    rows = _rows(40, start_day="2026-02-01")
    edge = 9 * 60 + 9 * 30          # 09:00 から 30分きざみで10枠 ＝ 13:30

    plan = resched.compact_plan(rows, now=now, step_min=30, hour=9,
                                until_hour=21, max_days=30, lead_min=60,
                                window=("2000-01-01", "2000-01-01"),
                                live_edge_min=edge)

    assert plan, "詰める本が1本も出ていない（前提が崩れています）"
    for p in plan:
        jst = datetime.datetime.fromisoformat(
            p["new"].replace("Z", "+00:00")).astimezone(JST)
        got = jst.hour * 60 + jst.minute
        assert 9 * 60 <= got <= edge, (
            f"{p['id']} が生きる帯の外へ置かれました: {jst:%m/%d %H:%M} JST"
            f"（帯は 09:00〜{edge // 60}:{edge % 60:02d}）")


def test_without_live_edge_the_old_behaviour_still_reaches_evening():
    """**`live_edge_min=None` は今までどおり**（純関数の既定を変えていないこと）。

    ここが変わると、この引数を渡していない呼び出し側の動きが黙って変わります。
    """
    now = datetime.datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    rows = _rows(40, start_day="2026-02-01")

    plan = resched.compact_plan(rows, now=now, step_min=30, hour=9,
                                until_hour=21, max_days=30, lead_min=60,
                                window=("2000-01-01", "2000-01-01"),
                                live_edge_min=None)

    latest = max(
        datetime.datetime.fromisoformat(
            p["new"].replace("Z", "+00:00")).astimezone(JST).hour * 60
        + datetime.datetime.fromisoformat(
            p["new"].replace("Z", "+00:00")).astimezone(JST).minute
        for p in plan)
    assert latest > 9 * 60 + 9 * 30, (
        "`live_edge_min=None` なのに帯の中しか使っていません —— "
        "既定の動きを変えると、渡していない呼び出し側が黙って変わります")


def test_live_edge_helper_follows_the_instrument():
    """**`_live_edge_min()` は式で、定数ではない。**

    `day_cap` の上限が動いたら、右端もいっしょに動くこと。
    """
    per_day = resched._measured_per_day()
    assert resched._live_edge_min(9, 30) == 9 * 60 + (per_day - 1) * 30
    # きざみを細かくすれば、同じ本数でも右端は手前に来ます
    assert resched._live_edge_min(9, 15) == 9 * 60 + (per_day - 1) * 15
    # 始まりを動かせば、そのぶん平行移動します
    assert resched._live_edge_min(10, 30) == resched._live_edge_min(9, 30) + 60
