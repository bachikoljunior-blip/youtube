"""`worst_gap` を年額で掃引したときの形が「山」ではなく「頭打ち」であること。

掃引の道具は `nenkin.worst_gap（ずれ_月）… いちばん高いのは端ではなく
base_annual_man=189` と拾った。**その読みは間違っている** —— 189 は
のこぎりの歯が1本たまたま高いだけで、同じ 32か月は 276万でも出る。
節が「189万で最大」と名指しすると、**再現しない数字を画面に出すことになる。**

だからここで固定するのは最大値の位置ではなく、**形のほう**:

  - 下の端（60万）から入口までは大きく動く（3倍近い）
  - 入口から上は、年額を2倍以上にしても振れ幅が数か月に収まる
"""
from src.calc import nenkin


def test_下の端から入口までは大きく動く():
    pl = nenkin.worst_gap_plateau()
    assert pl["下の端でのずれ_月"] < pl["入口でのずれ_月"]
    assert pl["入口までの倍率"] >= 2.0, pl


def test_入口より上は頭打ちで振れ幅が小さい():
    pl = nenkin.worst_gap_plateau()
    # 入口(131万)から300万は2.3倍。ずれが年額に比例するなら同じだけ広がるはず。
    assert pl["入口より上の振れ幅_月"] <= 3, pl
    assert pl["頭打ちの入口_万"] < 300.0, pl


def test_最大値の位置を名指しできないこと():
    """最大のずれを取る年額が複数あることを固定する（189 は一意ではない）。"""
    gaps = {man: nenkin.worst_gap(float(man))["ずれ_月"]
            for man in range(60, 301, 1)}
    top = max(gaps.values())
    at_top = [man for man, g in gaps.items() if g == top]
    assert len(at_top) > 1, f"最大 {top}か月 を取る年額が1点だけ: {at_top}"


def test_掃引が拾った189は最大帯の中の1点にすぎない():
    gaps = {man: nenkin.worst_gap(float(man))["ずれ_月"]
            for man in range(60, 301, 1)}
    assert gaps[189] == max(gaps.values())
    # 189 より上にも同じ高さの点がある ＝「189で最大」は言えない
    assert any(g == gaps[189] for man, g in gaps.items() if man > 189)


def test_表の行は掃引の範囲を全部おおう():
    rows = nenkin.worst_gap_by_base()
    assert rows[0]["65歳の年額_万"] == 60.0
    assert rows[-1]["65歳の年額_万"] == 300.0
    assert all(r["ずれ_月"] > 0 for r in rows)
    # 単調増加ではない（比例だと読ませないための固定）
    seq = [r["ずれ_月"] for r in rows]
    assert seq != sorted(seq), seq
