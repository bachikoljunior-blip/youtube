"""「逆転」の頂上が平らなとき、x を名指しさせないこと。

`ys.index(hi)` は最初の1点を返すので、頂上が平らでも1つの x を名指しします。
`nenkin.worst_gap` は掃引の粗い目盛りで 189 が一意に見えますが、
1万きざみで回すと 276 も同じ 32か月です。**目盛りが一意に見せていただけ。**
"""
from src import section_sweep as ss


def test_平らな頂上には並ぶ点が付く():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [25.0, 31.0, 32.0, 31.0, 28.0]   # nenkin.worst_gap と同じ形
    shape, d = ss._classify(xs, ys)
    assert shape == "逆転"
    assert d["並ぶ点"] >= 3, d


def test_尖った頂上には並ぶ点が付かない():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [10.0, 12.0, 90.0, 12.0, 10.0]
    shape, d = ss._classify(xs, ys)
    assert shape == "逆転"
    assert d["並ぶ点"] == 1, d
    assert d["並ぶ x"] == []


def test_端は並ぶ点に数えない():
    """端が同じ高さでも、それは「逆転」の主張とは別の話。"""
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [10.0, 12.0, 90.0, 12.0, 10.0]
    _, d = ss._classify(xs, ys)
    assert 1.0 not in d["並ぶ x"] and 5.0 not in d["並ぶ x"]
