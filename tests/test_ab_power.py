"""`src/ab_power.py` —— **判定の規則そのものが当てられるか**を測る道具の検査。

**既知の当たりは、実データではなく手で出した不変量に置いてあります**
（`docs/trigger_main.md` §4「その『既知の当たり』を、実データの偶然に置かないこと」）。
実データ側に固定してよいのは「まだ測れていない」ことのほうです。

置いてある当たりは2つ:

1. **効きがゼロなら、中央値の大小はコイン投げ**（対称性から 50%）。
   **n を増やしても下がりません** —— これがこの回に見つけた欠陥そのものです
2. **順位和を足すと、空振り率は α に張り付く**（n によらない）

どちらも実データが動いても意味が変わりません。
"""

from __future__ import annotations

import json

import pytest

from src import ab_power


# ---- 手で出せる1件（完全に分かれた 5対5）------------------------------------

def test_既知の当たり_順位和は手で出せる():
    """5対5 で treated が全部大きいとき、片側 p は手計算と合う。

    U = 25 ／ mu = 12.5 ／ sd = sqrt(5*5*11/12) = 4.7871
    z = (25 - 12.5 - 0.5) / 4.7871 = 2.5068  →  p = 0.0061
    """
    p = ab_power.rank_sum_p([10, 11, 12, 13, 14], [1, 2, 3, 4, 5])
    assert p == pytest.approx(0.0061, abs=0.0005)


def test_順位和_同じ標本なら片側pは半分より大きい():
    same = [1.0, 2.0, 3.0, 4.0]
    assert ab_power.rank_sum_p(same, list(same)) > 0.5


def test_順位和_空の群は判定しない():
    assert ab_power.rank_sum_p([], [1.0]) == 1.0
    assert ab_power.rank_sum_p([1.0], []) == 1.0


# ---- この回に見つけた欠陥（不変量なので実データに寄りかからない）------------

SPREAD = [12.0, 15.0, 18.0, 21.0, 25.0, 29.0, 33.0, 38.0, 42.0, 47.0]


@pytest.mark.parametrize("n", [8, 30])
def test_既知の当たり_中央値だけの規則は効きがゼロならコイン投げ(n):
    """**本数を増やしても下がりません。** ここが欠陥の本体です。"""
    r = ab_power.hit_rate(SPREAD, n, 1.0, rule=ab_power.median_rule, trials=2000)
    assert 0.40 <= r <= 0.60


@pytest.mark.parametrize("n", [8, 30])
def test_既知の当たり_順位和を足すと空振りはαに張り付く(n):
    r = ab_power.hit_rate(SPREAD, n, 1.0, trials=2000)
    assert r <= ab_power.ALPHA + 0.06


def test_倍率が大きいほど当てる率が上がる():
    rates = [ab_power.hit_rate(SPREAD, 16, x, trials=2000) for x in (1.0, 1.3, 2.0)]
    assert rates[0] < rates[1] < rates[2]


def test_本数が増えると当てる率が上がる():
    small = ab_power.hit_rate(SPREAD, 8, 1.5, trials=2000)
    large = ab_power.hit_rate(SPREAD, 32, 1.5, trials=2000)
    assert large > small


def test_種を固定しているので返りは毎回同じ():
    a = ab_power.hit_rate(SPREAD, 12, 1.3, trials=800)
    b = ab_power.hit_rate(SPREAD, 12, 1.3, trials=800)
    assert a == b


def test_効きがゼロなら要る本数は出ない():
    assert ab_power.needed_n(SPREAD, 1.0, trials=600, candidates=(8, 16, 32)) is None


def test_大きい効きなら小さい本数で足りる():
    assert ab_power.needed_n(SPREAD, 3.0, trials=600, candidates=(8, 16, 32)) == 8


def test_比率は100で頭打ちにする():
    """engaged 比率は上が 100% なので、倍率をかけた側は 100 で止めます（安全側）。

    もう 100% の本しか無いところに倍率をかけても、**両群とも 100 になって同点**です。
    同点は外れなので、当てる率は 0 —— 頭打ちが効いていなければ 1.0 になります。
    """
    assert ab_power.hit_rate([100.0], 8, 5.0, trials=200) == 0.0


# ---- 実データを読む側 --------------------------------------------------------

def _scan(tmp_path, values):
    p = tmp_path / "scan.jsonl"
    p.write_text(json.dumps({"at": "x", "values": values}, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def test_走査から比率を引く(tmp_path):
    path = _scan(tmp_path, {
        "動画.AAA.views": 100, "動画.AAA.engagedViews": 40,
        "動画.BBB.views": 200, "動画.BBB.engagedViews": 30,
        "合計.views": 300,
    })
    assert ab_power.observed_ratios(path) == [15.0, 40.0]


def test_再生の少ない本は落とす(tmp_path):
    path = _scan(tmp_path, {
        "動画.AAA.views": 100, "動画.AAA.engagedViews": 40,
        "動画.SMALL.views": ab_power.MIN_VIEWS - 1, "動画.SMALL.engagedViews": 5,
    })
    assert ab_power.observed_ratios(path) == [40.0]


def test_engaged_の無い本は落とす(tmp_path):
    path = _scan(tmp_path, {"動画.AAA.views": 100})
    assert ab_power.observed_ratios(path) == []


def test_走査が無ければ空(tmp_path):
    assert ab_power.observed_ratios(tmp_path / "no-such.jsonl") == []


def test_標本が足りなければ判定しない():
    assert ab_power.verdict(16, values=[10.0, 20.0]) is None


def test_判定の当てっこは本数の不足を名指しする():
    v = ab_power.verdict(8, values=SPREAD, ratio=1.3, trials=800)
    assert v is not None
    assert v.null_median > 0.35          # コイン投げ側
    assert v.null_ranksum < v.null_median  # 順位和を足したほうが締まる
    text = "\n".join(v.lines())
    assert "コイン投げ" in text


def test_表は実データが無くても落ちない():
    assert "標本が足りません" in ab_power.table(values=[1.0])
