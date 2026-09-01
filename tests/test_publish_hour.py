"""**公開時刻の帯が、規則の密度でだけ数えられていること。**

## なぜこの検査が要るか（2026-09-01・最適化の回）

この道具の値は**そのまま `config/channel.yaml` の `publish_hour_jst` になり、
機械が実際に動画を置く時刻を決めます。** だから壊れ方が2つあり、
**どちらも「静かに悪い時刻へ置く」**という形で出ます:

1. **密度で絞り忘れる。** 全密度で数えると 15〜22時 が中央値 1〜8回 に見えます
   —— あれは `src/day_cap.py` の本数の効果（その日の 13本目以降）で、
   時刻の効果ではありません。**絞り忘れると、朝以外の時刻が全部 死んで見えます。**
2. **n=1〜2 の帯で順位を付ける。** 実測 2026-09-01 で 8時 は **n=1・1,510回** ——
   9時（n=12・940回）より高く見えます。**1本で既定を動かしてはいけません。**

`MIN_N` はそのための門です。**この検査が守っているのは `MIN_N` の効き目**で、
「9時 が最適だ」ではありません（この repo は一度も時刻を実験していません）。

## 覆る条件

- 規則の密度の日が増えて `MIN_N` を満たす帯が2つ以上になったら、
  `best_hour()` は「中央値がいちばん高い」で選びます。**そこは順位の話**なので、
  そのとき初めて「どちらが良いか」を言えます。
- `house_rule.PUBLISH_PER_DAY` が動いたら帯の幅も動きます。
  **この検査は数を書かず、`rule_band()` に per_day を渡して確かめます。**
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src import publish_hour

JST = timezone(timedelta(hours=9))


def _row(day: int, hour: int, life: int, i: int = 0):
    return (datetime(2026, 8, day, hour, 0, tzinfo=JST), f"v{day}{hour}{i}", life)


def test_密度の高い日は帯から落ちる():
    """**同じ時刻でも、その日に何本 出したかで採否が変わること。**"""
    crowded = [_row(20, 9, 5, i) for i in range(6)]        # 6本/日 ＝ 規則の3倍
    thin = [_row(21, 9, 900)]                              # 1本/日
    band = publish_hour.rule_band(crowded + thin, per_day=1, mult=2)
    assert [r[1] for r in band] == ["v2190"], (
        "**規則の密度で絞れていません。**全密度で数えると、`day_cap` の本数の効果が"
        "時刻の効果に化けます（15〜22時 が中央値 1〜8回 に見える）。")


def test_1本しかない帯では既定を動かさない():
    """**n=1 の帯が、n の多い帯を追い越さないこと。**

    実測 2026-09-01: 8時 は n=1 で 1,510回、9時 は n=12 で 940回。
    **1本で `publish_hour_jst` を動かしてはいけません。**
    """
    rows = [_row(21, 8, 1510)] + [_row(20 + i, 9, 900, i) for i in range(publish_hour.MIN_N)]
    # 日を散らして、どの日も 1本/日 にする
    assert publish_hour.best_hour(rows) == 9, (
        f"**n={publish_hour.MIN_N} に満たない帯を候補にしています。**"
        "順位を付けられるだけの本が無い帯で既定を動かさないこと。")


def test_どの帯も足りなければ黙る():
    """**根拠が無い回は `None` を返すこと**（推測で時刻を名指ししない）。"""
    rows = [_row(20 + i, 9 + i, 900) for i in range(3)]
    assert publish_hour.best_hour(rows) is None, (
        "**`MIN_N` に届かないのに時刻を名指ししています。**"
        "`scripts/slot_gate._hour_arg()` はこの `None` を見て `<時>` に戻ります。")


def test_試していない時刻が数えられる():
    rows = [_row(20, 9, 900)]
    un = publish_hour.untested(rows)
    assert 9 not in un and len(un) == 23


def test_機械の既定と計器が同じ時刻を指していること():
    """**言っている所と、している所が別**にならないこと（この repo の最頻の壊れ方）。

    `config/channel.yaml` の `publish_hour_jst` は、実測で選べる回は
    `best_hour()` と一致していること。**選べない回（`None`）は問いません。**
    """
    best = publish_hour.best_hour()
    if best is None:
        return
    cfg = publish_hour.config_hour()
    assert cfg == best, (
        f"`config/channel.yaml` の publish_hour_jst は {cfg}時、"
        f"実測が指すのは {best}時 です。**機械が置く時刻と、"
        "`scripts/eta.py` の per_video が乗っている帯がずれています。**"
        "（時刻を変える判断そのものは自由です —— そのときは"
        "`config/hypotheses.yaml` の前提と、この検査の期待を一緒に直すこと）")
