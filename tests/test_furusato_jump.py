"""`furusato.jump_by_step()` の主張を固定する（2026-08-17）。

**この節は、機械の掃引が指した所の「隣」から出ました。**
`src/section_sweep.py` が出した候補は
「`境目の上限` が 40%→45% で 1,083,845円 跳ぶ」で、**これは節になりません** ——
速算表の段は 1,800万→4,000万 と幅そのものが桁違いなので、
**跳んでいるのは制度ではなく段の置き方**です。

実物を並べて分かったのは2つ:

1. **いちばん深い崖は 33% の境目（+18.00%）**で、最上段の 45%（+11.57%）より深い。
   いちばん浅いのは真ん中の 23%（+4.56%）。**どちらも端ではありません。**
   決めているのは税率の高さではなく、**その境目で税率が何ポイント上がるか**
2. **掃引はこれを見られませんでした** —— `はね上がる率` が
   `f"{...:.1f}%"` の**文字列**だから。`_scalars()` は数字しか拾いません
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import _checks, furusato  # noqa: E402


def test_制度の値の検査は通る():
    furusato.check_tables()


def test_いちばん深い崖は33パーセントの境目():
    rows = furusato.jump_by_step()
    deep = max(rows, key=lambda r: r["はね上がる率パーセント"])
    assert deep["所得税率"] == pytest.approx(0.33)
    assert deep["はね上がる率パーセント"] == pytest.approx(18.00, abs=0.05)


def test_最上段より真ん中のほうが深い():
    rows = furusato.jump_by_step()
    top = rows[-1]
    deep = max(rows, key=lambda r: r["はね上がる率パーセント"])
    assert top["所得税率"] == pytest.approx(0.45)
    assert deep["はね上がる率パーセント"] > top["はね上がる率パーセント"]


def test_いちばん浅い崖は23パーセントの境目():
    rows = furusato.jump_by_step()
    shallow = min(rows, key=lambda r: r["はね上がる率パーセント"])
    assert shallow["所得税率"] == pytest.approx(0.23)
    assert shallow["段の幅ポイント"] == 3
    assert shallow["はね上がる率パーセント"] == pytest.approx(4.56, abs=0.05)


def test_深さは端にない():
    """端にあると「税率が高いほど深い」で読めてしまい、節が成立しません。"""
    depth = [r["はね上がる率パーセント"] for r in furusato.jump_by_step()]
    assert depth.index(max(depth)) not in (0, len(depth) - 1)
    assert depth.index(min(depth)) not in (0, len(depth) - 1)


def test_1ポイントあたりの効きは税率が上がるほど強くなる():
    """分母 `90% − 税率 × 1.021` が縮むから。**ここは単調です。**"""
    per = [r["1ポイントあたりパーセント"] for r in furusato.jump_by_step()]
    assert per == sorted(per), per
    assert per[0] == pytest.approx(1.228, abs=0.01)
    assert per[-1] == pytest.approx(2.315, abs=0.01)


def test_式の分母は90パーセントから税率かける1_021を引いたもの():
    for r in furusato.jump_by_step():
        assert r["式の分母"] == pytest.approx(
            0.9 - r["所得税率"] * furusato.RECONSTRUCTION)


def test_段の幅は必ず正():
    for r in furusato.jump_by_step():
        assert r["段の幅ポイント"] > 0


def test_深さと段の幅は同じ向きに動く_順位で():
    """**ぴったり比例はしません**（1ポイントあたりの効きが効くので）。
    それでも、幅が広い側が深い側に来ること。"""
    rows = furusato.jump_by_step()
    widest = max(rows, key=lambda r: r["段の幅ポイント"])
    narrowest = min(rows, key=lambda r: r["段の幅ポイント"])
    assert widest["はね上がる率パーセント"] > narrowest["はね上がる率パーセント"]


# ---- 故障注入 -----------------------------------------------------------

def test_深さがすべて単調なら検査が落ちる(monkeypatch):
    """「税率が高いほど深い」に直すと、この節の主張が消えます。"""
    rows = furusato.jump_by_step()
    for i, r in enumerate(rows):
        r["はね上がる率パーセント"] = 5.0 + i
    monkeypatch.setattr(furusato, "jump_by_step", lambda **kw: rows)
    with pytest.raises(ValueError):
        furusato.check_tables()


def test_1ポイントあたりの向きが崩れると検査が落ちる(monkeypatch):
    rows = furusato.jump_by_step()
    rows[0]["1ポイントあたりパーセント"] = 99.0
    monkeypatch.setattr(furusato, "jump_by_step", lambda **kw: rows)
    with pytest.raises((ValueError, _checks.TableError)):
        furusato.check_tables()


def test_分母を取り違えると検査が落ちる(monkeypatch):
    rows = furusato.jump_by_step()
    for r in rows:
        r["式の分母"] = 1.0 - r["所得税率"]      # 90% を 100% にする、よくある取り違え
    monkeypatch.setattr(furusato, "jump_by_step", lambda **kw: rows)
    with pytest.raises((ValueError, _checks.TableError)):
        furusato.check_tables()
