"""`src/calc_axes.py` —— 引数名を意味の軸へ寄せる表を固定する。

**固定するのは「寄せの向き」だけ**で、組の数は固定しません。
表が増えれば組は増えるので、件数を書くと**表を足すたびに赤くなります**。
"""
import pytest

from src.calc_axes import SEMANTIC_AXES, axes_by_calc, axis_of, shared_pairs


@pytest.mark.parametrize("param,axis", [
    ("income", "所得"),
    ("monthly_pay", "所得"),
    ("kyuyo_shotoku", "所得"),
    ("age", "年齢"),
    ("months_from_65", "年齢"),   # 「65歳から何か月」は期間ではなく年齢の軸
    ("members", "世帯"),
    ("months", "期間"),
    ("social_rate", "率"),
    ("floor_area", "面積"),
])
def test_名前は意味の軸へ寄る(param, axis):
    assert axis_of(param) == axis


@pytest.mark.parametrize("param", ["step", "steps", "grade", "point", "base"])
def test_格子のつまみは軸に入れない(param):
    """`step` は6本の表に出るが、**走査の刻み**であって意味の軸ではない。

    ここが軸に入ると、意味の繋がっていない組が母数を膨らませます
    （名前の一致で数えたとき、いちばん多い軸が `step` の15組でした）。
    """
    assert axis_of(param) is None


def test_軸は重ならない():
    """1つの断片が2つの軸に出ていたら、寄せ先が呼び出し順で決まってしまう。"""
    seen: dict[str, str] = {}
    for axis, keys in SEMANTIC_AXES.items():
        for key in keys:
            assert key not in seen, f"{key!r} が {seen.get(key)} と {axis} の両方にある"
            seen[key] = axis


def test_所得の軸がいちばん広い():
    """M19 の掛け算は「所得 18本」に乗っています。**順位だけ**を固定する。"""
    axes, _unmapped = axes_by_calc()
    counts: dict[str, int] = {}
    for got in axes.values():
        for axis in got:
            counts[axis] = counts.get(axis, 0) + 1
    assert counts["所得"] == max(counts.values())
    assert counts["所得"] >= 10


def test_組は表の本数より多い():
    """組で数える意味は「表の本数に比例しない」こと。ここが崩れたら M19 が崩れる。"""
    axes, _unmapped = axes_by_calc()
    pairs = shared_pairs(axes)
    assert len(pairs) > len(axes)
    for a, b, common in pairs:
        assert a != b and common


def test_gassan_の2本は_入力の軸では組にならない():
    """**この寄せ表のいちばん大きな穴を、忘れないために固定する。**

    `gassan`（医療×介護）は、2本の表を同じ物差しに載せて **7節**出した
    唯一の実例です。ところが `kogaku` と `kaigo` は、**入力の引数では
    1つも軸を共有しません**（2026-08-19 の実測）。

        kogaku  {所得, 期間}    ← cost（医療費）・months
        kaigo   {率, 世帯, 帯}  ← rate（負担割合）・people・cap

    `gassan` が2本を繋いだのは**入力ではなく出力**です —— 同じ世帯が
    同じ1年に払う **円**。**入力の名前で組を作る限り、既知の当たりが
    1件も入りません。** `docs/MEANS.md` M19 の2手目
    （`src/pair_sweep.py`）は、ここを踏まえて**出力の側で繋ぐこと。**

    **この検査が赤くなったら、それは進歩です**（寄せ表か抽出が
    出力側を見るようになった、ということ）。**消さずに、書き換えること。**
    """
    axes, _unmapped = axes_by_calc()
    assert axes.get("kogaku"), "kogaku に軸が無い（抽出が狭すぎる）"
    assert axes.get("kaigo"), "kaigo に軸が無い（抽出が狭すぎる）"
    assert not (axes["kogaku"] & axes["kaigo"]), (
        "既知の当たりが入力の軸で繋がった。M19 の掛け算を測り直すこと")


def test_軸の共有はふるいになっていない():
    """**組の8割が「軸を共有する」に入ります。**＝ふるいとして効いていない。

    M19 の掛け算（1組から約5節）は、**組が選ばれていること**を前提に
    しています。ここが 5割を超えているうちは、選んでいるのは
    2手目の「形」（崖の近さ・和の平坦・順序の逆転）のほうです。
    """
    axes, _unmapped = axes_by_calc()
    total = len(axes) * (len(axes) - 1) // 2
    assert len(shared_pairs(axes)) / total > 0.5
