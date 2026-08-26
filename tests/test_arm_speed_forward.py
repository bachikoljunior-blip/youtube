"""**予定表から数えた θ**（`src/arm_speed.forward()`）を見張る。

## なぜ要るか（2026-08-26・最適化の回）

`scripts/eta.py` の頭は「腕を **N日** 動かして、そこから M日」と出し、
その N は `rate = p · log(g) · θ` の **θ に反比例**します
—— 実測 2026-08-26 で **124日 のうち 50日** がこの1つの数の上に乗っていました。

その θ（`throughput()`）は `closed_on` の**過去だけ**を見ています。
`forward()` は**この機械自身の予定表**（開いた前提の「判定できる日」）から
同じ θ を数え、`eta.py` が両方を並べます。

**この検査が守るのは3つだけ**です。どれも「並べるという扱い」そのものが壊れる形:

1. **黙って 0 にしないこと** —— `ready` が空のとき 0 を返すと θ が 0 になり、
   到達日が「出ません」に化けます。**読めなかったと言うこと**
2. **合っていたら黙ること** —— 並べる意味は「合っていない」ことにあります。
   14日窓の比が 0.8 を超えたら行は消えます（**自分で消える覆る条件**）
3. **窓が長いほど密度は下がる**（同じ件数を長い窓で割るので）。
   ここが逆転したら数え方が壊れています
"""
from __future__ import annotations

from datetime import date

import pytest

from src import arm_speed


TODAY = date(2026, 8, 26)

#: 閉じた前提が2件。**`throughput()` が ちょうど 1.0/日 を返すように置いてあります**
#: （最初に閉じた日 08-24 → 今日 08-26 ＝ 2日 に 2件）。倍率を読む検査が
#: 分母に引きずられないように、**ここは 1.0 に固定すること**。
DOC = {
    "hypotheses": [
        {"claim": "A", "lever": "per_video", "effect": 1.5,
         "closed_on": "2026-08-24"},
        {"claim": "B", "lever": "rpm", "effect": 2.0,
         "closed_on": "2026-08-26"},
        {"claim": "C", "lever": "density"},          # 開いている
        {"claim": "D", "lever": "per_video"},        # 開いている
        {"claim": "E", "lever": "rpm"},              # 開いている（日が無い）
    ],
}


def test_readyが空なら黙って0にせず読めなかったと言うこと():
    """**0 を返すと θ が 0 になり、到達日が「出ません」に化けます。**"""
    fw = arm_speed.forward({}, doc=DOC, today=TODAY)
    assert fw["missing"], "読めなかったことを言っていません"
    assert fw["horizons"] == [], "読めていないのに窓を数えています"
    assert fw["undated"] == 3, "開いている前提の数を数えていません"

    line = arm_speed.forward_line(fw)
    assert line and "裏取りができません" in line, (
        "読めなかった回に黙っています。**黙ると、過去だけの θ が"
        "裏取り済みに見えます**")


def test_予定表が過去に追いついていたら行が消えること():
    """**並べる意味は「合っていない」ことにあります。**（自分で消える覆る条件）"""
    ready = {"C": date(2026, 8, 27), "D": date(2026, 8, 28),
             "E": date(2026, 8, 29)}
    fw = arm_speed.forward(ready, doc=DOC, today=TODAY, horizons=(3,))
    assert fw["horizons"][0]["n"] == 3
    assert fw["horizons"][0]["per_day"] == pytest.approx(1.0)
    assert fw["horizons"][0]["ratio"] == pytest.approx(1.0)
    assert arm_speed.forward_line(fw) is None, (
        "合っているのに行を出しています")


def test_合っていなければ行を出し倍率を添えること():
    ready = {"C": date(2026, 8, 27), "D": date(2026, 11, 1),
             "E": date(2026, 12, 1)}
    fw = arm_speed.forward(ready, doc=DOC, today=TODAY, horizons=(14,))
    assert fw["horizons"][0]["n"] == 1
    assert fw["horizons"][0]["ratio"] < 0.8

    line = arm_speed.forward_line(fw)
    assert line, "合っていないのに黙っています"
    assert "0.07/日" in line, f"予定表の側の数が出ていません: {line}"
    assert "下限" in line, (
        "**下限だと言っていません。** これから立つ前提を数えていないので、"
        "正として読まれると到達日を遅い側へ振り切ります")


def test_窓が長いほど1日あたりは下がること():
    """同じ件数を長い窓で割るので、**逆転したら数え方が壊れています**。"""
    ready = {"C": date(2026, 8, 27), "D": date(2026, 9, 20),
             "E": date(2026, 10, 20)}
    fw = arm_speed.forward(ready, doc=DOC, today=TODAY, horizons=(14, 30, 60))
    per = [h["per_day"] for h in fw["horizons"]]
    assert per == sorted(per, reverse=True), (
        f"窓を伸ばしたのに密度が上がっています: {per}")


def test_窓の外の日は数えないこと():
    ready = {"C": date(2027, 1, 1)}
    fw = arm_speed.forward(ready, doc=DOC, today=TODAY, horizons=(14,))
    assert fw["horizons"][0]["n"] == 0
    assert fw["dated"] == 1, "日の付いた件数まで 0 にしています"


def test_過ぎた日は数えないこと():
    """**期日を過ぎたまま閉じていない前提**を「これから閉じる」に数えないこと。"""
    ready = {"C": date(2026, 8, 1), "D": date(2026, 8, 27)}
    fw = arm_speed.forward(ready, doc=DOC, today=TODAY, horizons=(14,))
    assert fw["horizons"][0]["n"] == 1, (
        "過ぎた日を数えています。**過ぎているのに閉じていないのは、"
        "速いのではなく遅れている姿です**")


def test_実物で落ちないこと():
    """**実際の台帳と予定表**で、例外を上げず数を返すこと（API 0単位）。"""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "t_deadline_check", arm_speed.ROOT / "scripts" / "deadline_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["t_deadline_check"] = mod
    spec.loader.exec_module(mod)

    fw = arm_speed.forward(mod.ready_by_claim())
    assert fw["backward"] is not None, "過去の θ が出ていません"
    if fw["missing"]:
        return                       # 予定表が読めない日もある。そのときは黙る
    assert fw["horizons"], "窓を1つも数えていません"
    for h in fw["horizons"]:
        assert 0 <= h["n"] <= fw["dated"]
        assert h["per_day"] >= 0
