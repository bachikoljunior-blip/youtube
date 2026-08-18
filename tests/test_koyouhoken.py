"""**雇用保険料率の表。**（2026-08-18 に新設）

`check_tables()` が守っているのは「値」で、**主張のほうは守れません。**
ここで固定するのは、docstring が言い切っている7つの主張そのものです。

**故障注入つき** —— 値を壊したときに落ちる側も見ます。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.calc import _checks, koyouhoken as k


def test_事業主の倍率は合計の率の順番と一致しない():
    """**この表の中心。**合計は 1.45 → 1.65 → 1.75 と上がるのに、倍率は下がって上がる。"""
    rows = {r["業種"]: r for r in k.roushi()}
    assert rows["一般の事業"]["事業主は労働者の何倍"] == 1.636
    assert rows["農林水産・清酒製造"]["事業主は労働者の何倍"] == 1.538
    assert rows["建設"]["事業主は労働者の何倍"] == 1.692
    goukei = [rows[n]["合計（パーセント）"] for n in
              ("一般の事業", "農林水産・清酒製造", "建設")]
    bairitsu = [rows[n]["事業主は労働者の何倍"] for n in
                ("一般の事業", "農林水産・清酒製造", "建設")]
    assert goukei == sorted(goukei), "合計の率は昇順のはず"
    # **倍率は昇順ではない**（ここが主張。単調なら「重い業種ほど事業主寄り」と言えてしまう）
    assert bairitsu != sorted(bairitsu)


def test_合計の率の実額():
    rows = {r["業種"]: r for r in k.roushi()}
    assert rows["一般の事業"]["合計（パーセント）"] == 1.45
    assert rows["農林水産・清酒製造"]["合計（パーセント）"] == 1.65
    assert rows["建設"]["合計（パーセント）"] == 1.75


def test_業種の差は労働者側では同じで建設だけ事業主が2倍():
    rows = {r["業種"]: r for r in k.gyoshu_sa()}
    assert rows["農林水産・清酒製造"]["労働者の差（ポイント）"] == 0.1
    assert rows["建設"]["労働者の差（ポイント）"] == 0.1
    assert rows["農林水産・清酒製造"]["事業主の差（ポイント）"] == 0.1
    assert rows["建設"]["事業主の差（ポイント）"] == 0.2
    # 建設だけが労働者側の2倍
    assert (rows["建設"]["事業主の差（ポイント）"]
            == rows["建設"]["労働者の差（ポイント）"] * 2)


def test_労使あわせた4分の1は失業給付に使われない():
    rows = {r["業種"]: r for r in k.nijigyo_share()}
    warr = [r["労使あわせた中の割合（パーセント）"] for r in k.nijigyo_share()]
    assert min(warr) == 21.2
    assert max(warr) == 25.7
    assert rows["一般の事業"]["二事業の割合（パーセント）"] == 38.9
    assert rows["建設"]["二事業の割合（パーセント）"] == 40.9
    assert rows["農林水産・清酒製造"]["二事業の割合（パーセント）"] == 35.0


def test_月給30万で会社は年12600円多く払う():
    rows = {r["月給（円）"]: r for r in k.gaku()}
    assert rows[300_000]["労働者が引かれる（月・円）"] == 1_650
    assert rows[300_000]["会社が払う（月・円）"] == 2_700
    assert rows[300_000]["年12か月ぶんの差（円）"] == 12_600
    assert rows[300_000]["賞与4か月を足した年の差（円）"] == 16_800
    assert rows[1_000_000]["年12か月ぶんの差（円）"] == 42_000


def test_50銭ちょうどは切り捨て境目は月給301000円():
    rows = k.hasuu()
    assert [r["月給（円）"] for r in rows] == [300_999, 301_000, 301_001]
    assert rows[1]["端数（銭）"] == 50.0
    # **ちょうどは切り捨て** ＝ 1円下と同額
    assert rows[1]["引かれる額（円）"] == rows[0]["引かれる額（円）"] == 1_655
    # **1厘超えると切り上げ**
    assert rows[2]["引かれる額（円）"] == 1_656


def test_前年度から下がった額は3業種とも同額():
    rows = k.zennendo(300_000)
    assert {r["労使あわせた年の減り（円）"] for r in rows} == {3_600}
    assert {r["労働者の年の減り（円）"] for r in rows} == {1_800}
    assert {r["会社の年の減り（円）"] for r in rows} == {1_800}
    # 率のほうは業種でちがう（同額なのは下げ幅が同じだから）
    assert len({r["労働者の率（前年度→今年度・パーセント）"] for r in rows}) == 2


def test_雇用保険には上限が無いので比が3倍になる():
    rows = {r["月給（円）"]: r for r in k.jougen()}
    assert rows[300_000]["雇用保険が厚生年金に占める割合（パーセント）"] == 6.01
    assert rows[650_000]["雇用保険が厚生年金に占める割合（パーセント）"] == 6.01
    assert rows[2_000_000]["雇用保険が厚生年金に占める割合（パーセント）"] == 18.5
    assert round(rows[2_000_000]["雇用保険が厚生年金に占める割合（パーセント）"]
                 / rows[650_000]["雇用保険が厚生年金に占める割合（パーセント）"], 2) == 3.08
    # **厚生年金のほうは上限で止まる**
    assert rows[650_000]["厚生年金（本人・円）"] == rows[2_000_000]["厚生年金（本人・円）"]


def test_事業主は必ず労働者より重い():
    for name, _, _ in k.GYOSHU:
        assert k.employer_rate(name) > k.worker_rate(name)


# ---- 故障注入（**壊したときに落ちる側**）--------------------------------

def test_二事業を0にすると事業主のほうが重いという検査が落ちる(monkeypatch):
    broken = [(n, s, Decimal("0")) for n, s, _ in k.GYOSHU]
    monkeypatch.setattr(k, "GYOSHU", broken)
    with pytest.raises(_checks.TableError):
        k.check_tables()


def test_前年度の率を今年度と同じにすると下がっていない側で落ちる(monkeypatch):
    monkeypatch.setattr(k, "LAST_YEAR", {n: s for n, s, _ in k.GYOSHU})
    with pytest.raises(_checks.TableError):
        k.check_tables()


def test_率を1超えにするとratioが落ちる(monkeypatch):
    broken = [(n, Decimal("1.5"), j) for n, _, j in k.GYOSHU]
    monkeypatch.setattr(k, "GYOSHU", broken)
    with pytest.raises(_checks.TableError):
        k.check_tables()


def test_端数を四捨五入にすると50銭ちょうどの行が1円上がって落ちる(monkeypatch):
    from decimal import ROUND_HALF_UP

    def naive(wage: int, name: str = "一般の事業") -> int:
        return int((Decimal(wage) * k.worker_rate(name)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))

    monkeypatch.setattr(k, "worker_yen", naive)
    with pytest.raises(_checks.TableError):
        k.check_tables()
