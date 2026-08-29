"""**`--group` の段は「置いた本数」で括ること。**「生きた本数」ではありません。

## なぜ要るか（2026-08-29 に踏んだ。**待ちが9回 鳴って、9回とも答えが出ない**）

`config/watches.yaml` の `予約30分きざみ-3日` は `src/watches.py` の
`_k_days_with_min_videos` で **その日に置いた本**を数えて「満ちました」を出し、
`then:` に `scripts/per_day_views.py --hours 168 --group 8-13,16-99` を名指しします。

ところが `--group` は `len(vs)` —— **`min_views` を通った本だけ**で括っていました。
実測 2026-08-29: 門が数えた 08/20 **25本** ／ 08/21 **32本** ／ 08/22 **25本** が、
道具の側では **10 / 11 / 12本**。**`16-99本/日` は「該当日0日。判定できません」**で、
待ちは 00:58 から 9回 鳴り、9回とも同じ答えを返していました。

**門と判定が別の母集団を数える形は、これが2件目です**
（1件目は `src/deep_short.py`・同じ日の `fix: 門と判定の手順が、別の母集団を数えていた`）。

そして中身の側でも、置いた本数で括るほうが正しい —— この待ちが問うているのは
**「1日に何本 置くと1本あたりが落ちるか」**で、主語は置いた本数です。
生きた本数で括ると、08/20（置いた25本・中央 374）と 08/23（置いた13本・中央 1,046）が
**同じ「10本/日」の段**に入ります。**括る軸が、測りたいものと別でした。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import per_day_views as P  # noqa: E402

JST = timezone(timedelta(hours=9))


def _points(published: datetime, hours: float, views: int):
    """`views_at` / `published_at` が読める形の観測を1本ぶん作る。"""
    return [(hours, views, published + timedelta(hours=hours))]


def _build() -> dict:
    """**同じ「生きた本数」で、置いた本数だけが違う2日**を作る。

        A日  置いた 20本（うち 4本 だけが床を越える。越えた本は 400回）
        B日  置いた  4本（4本 とも床を越える。      同じく    1000回）

    生きた本数で括ると **どちらも 4本/日** になり、同じ段に落ちます。
    置いた本数で括れば **20本/日 と 4本/日** で、段が分かれます。
    """
    a = datetime(2026, 8, 20, 10, 0, tzinfo=JST)
    b = datetime(2026, 8, 23, 10, 0, tzinfo=JST)
    by_id: dict[str, list] = {}
    for i in range(4):
        by_id[f"a-live-{i}"] = _points(a, 168.0, 400)
    for i in range(16):
        by_id[f"a-dead-{i}"] = _points(a, 168.0, 1)      # 床（10回）に届かない
    for i in range(4):
        by_id[f"b-live-{i}"] = _points(b, 168.0, 1000)
    return by_id


def test_置いた本数で数える() -> None:
    placed = P.placed_per_day(_build(), target=168.0)
    assert placed["2026-08-20"] == 20, f"置いた本数が 20本 でない: {placed}"
    assert placed["2026-08-23"] == 4, f"置いた本数が 4本 でない: {placed}"


def test_生きた本数とは別の数である() -> None:
    """**この2つが同じ数になったら、段を括る軸が1本に戻っています。**"""
    by_id = _build()
    live = P.per_day(by_id, target=168.0, min_views=10)
    placed = P.placed_per_day(by_id, target=168.0)
    assert len(live["2026-08-20"]) == 4, "生きた本数の作りが変わった"
    assert placed["2026-08-20"] != len(live["2026-08-20"]), (
        "置いた本数と生きた本数が同じになっている ——"
        " 段を括る軸が『生きた本数』へ戻っていないか確かめること")


def test_段は置いた本数で分かれる(capsys) -> None:
    """**門が『満ちました』と言う日が、この表に現れること。**

    生きた本数で括っていた版は、この入力で `16-99本/日` を
    `**該当日0日。判定できません**` と出します（どちらの日も生きたのは 4本 なので）。
    """
    by_id = _build()
    orig = P._load
    P._load = lambda *a, **k: by_id                       # type: ignore[assignment]
    try:
        rc = P.main(["--hours", "168", "--group", "1-9,16-99"])
    finally:
        P._load = orig                                    # type: ignore[assignment]
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "該当日0日" not in out, (
        "置いた 20本 の日が段に入っていません（生きた本数で括っています）:\n" + out)
    assert "16-99本/日  1日" in out, "16-99 の段が1日になっていない:\n" + out
    assert "1-9本/日  1日" in out, "1-9 の段が1日になっていない:\n" + out
    # 400 と 1000 なので 0.4倍 ＝ 2割以上の下げ
    assert "**2割以上落ちた ＝ ここが上限**" in out, out


def test_読みの無い本は置いた数にも入らない() -> None:
    """床は当てませんが、**その時点の読みが無い本**は数えません。

    `views_at` が `None` を返す本まで数えると、置いた本数が
    「予約した本」に近づき、**門（公開した本）とまた別の数になります。**
    """
    by_id = _build()
    by_id["a-noread"] = _points(datetime(2026, 8, 20, 10, 0, tzinfo=JST), 4.0, 900)
    placed = P.placed_per_day(by_id, target=168.0)
    assert placed["2026-08-20"] == 20, (
        f"168時間の読みが無い本を数えている: {placed}")
