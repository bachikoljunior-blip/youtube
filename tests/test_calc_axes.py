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


@pytest.mark.parametrize("param", ["step", "steps", "grade", "point"])
def test_格子のつまみは軸に入れない(param):
    """`step` は6本の表に出るが、**走査の刻み**であって意味の軸ではない。

    ここが軸に入ると、意味の繋がっていない組が母数を膨らませます
    （名前の一致で数えたとき、いちばん多い軸が `step` の15組でした）。

    **`base` は 2026-08-19 にここから外しました。**（消さずに向きを変える）
    `src/calc/` に出る `base*` は**全部が金額**です ——
    `shokibo.income_tax` / `tokutei.tax_of` / `zoyo.tax_of` /
    `yoteinozei.with_fukko` の課税標準、`nenkin.base_annual_man` の基礎年額、
    `zaishoku.stop_base` の停止基準額。**つまみは1つもありません。**
    しかも `base_annual_man` は `annual` で**もともと所得へ寄っていた**ので、
    この行は同じ族を2通りに扱っていました。

    **落とした代償のほうが大きかった** —— `base` が寄らないせいで、
    既定値の無い `base` を持つ **6関数が掃引から丸ごと消えていました**
    （計器 `UNCALLABLE` で 2026-08-19 に見えた）。
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


# --- 埋める語彙と、繋ぐ語彙を分けた（2026-08-19）---------------------------
#
# `SEMANTIC_AXES` には消費者が2つあり、要求が正反対でした。
# `axis_of`（`pair_sweep`）は格子のつまみを入れたくない。
# `_axis_fill`（`section_sweep`）は寄せられない名前を関数ごと落とす。
# **どちらか一方を選ぶ話ではなく、表を分ければ両方立ちます。**
#
# ここに固定するのは**向き**だけです（件数ではありません）。

def test_grade_は埋められるが組の軸にはならない():
    """`grade`（障害等級・標準報酬の等級）は**格子のつまみ**。

    埋められないと `shougai` 5本・`zaishoku` 3本が掃引から丸ごと消えます。
    かといって意味の軸にすると、**等級を持つ表どうしが全部組になり**
    母数だけが膨らみます（`SEMANTIC_AXES` の docstring がそう言っている）。

    **この検査が赤くなったら、どちらの側が壊れたかを先に見ること。**
    """
    from src.section_sweep import _axis_fill

    assert axis_of("grade") is None, "grade が組の軸に入った（母数が膨らむ）"
    assert _axis_fill("grade") is not None, "grade が埋められない（8関数が消える）"


@pytest.mark.parametrize("param,axis", [
    ("estate", "所得"),       # 相続財産＝金額
    ("base", "所得"),         # 課税標準＝金額
    ("prescribed", "期間"),   # 所定給付日数
    ("remaining", "期間"),    # 支給残日数
])
def test_2026_08_19に足した軸(param, axis):
    assert axis_of(param) == axis


def test_estate_は所得の代表値では埋めない():
    """**呼べるようになっても、中身が空なら意味がありません。**

    `estate` を所得の代表値 3,000,000 で埋めると、基礎控除（3,600万〜）に
    届かず税額がどの行でも 0 になり、掃引は「不変」で落とします。
    `PARAM_FILL` は `AXIS_FILL` より先に引くこと。
    """
    from src.calc.souzoku import total_tax
    from src.section_sweep import _axis_fill

    fill = _axis_fill("estate")
    assert fill is not None
    assert total_tax(int(fill), heirs=2) > 0, "埋めた額が基礎控除に届いていない"


@pytest.mark.parametrize("mod,fname", [
    ("shougai", "grade_rate"), ("shougai", "kiso"), ("shougai", "nenkin"),
    ("zaishoku", "total_monthly"), ("zaishoku", "paid"),
    ("saishushoku", "rate_of"), ("saishushoku", "benefit_days"),
    ("saishushoku", "cliff_low"),
    ("souzoku", "total_tax"), ("souzoku", "spouse_relief"),
    ("tokutei", "tax_of"), ("shokibo", "income_tax"),
    ("yoteinozei", "with_fukko"),
])
def test_呼べるようになった関数(mod, fname):
    """**消えた側を固定する。** 件数ではなく、名指しで。

    `_enum_axis` の穴（07:3x）も `_sweepable_params` の穴（06:1x）も、
    「候補が何件出たか」しか見ていなかったので気づけませんでした。
    **落ちた関数を名前で押さえておけば、次に同じ形で消えたとき赤くなります。**
    """
    import importlib

    from src.section_sweep import unreachable

    fn = getattr(importlib.import_module(f"src.calc.{mod}"), fname)
    assert unreachable(fn) == "", f"{mod}.{fname} が掃引から落ちている"


@pytest.mark.parametrize("mod,fname", [
    ("haiguusha", "cliff"), ("haiguusha", "recovery"),
    ("inshi", "split_cost"), ("inshi", "zeinuki_limit"),
    ("iryohi", "split_loss"), ("iryohi", "split_months_tax"),
    ("jidou", "monthly"), ("jidou", "total_for"),
    ("jikangai", "next_month_cap"), ("koteishisan", "same_tax_floor"),
    ("kouki", "keigen_rate"), ("kouki", "part"),
    ("koureikoyou", "keep_rate"), ("ninikeizoku", "keigen_kintou"),
    ("sankyu", "premium"), ("shahoken", "bounds"),
    ("yukyu", "granted_at"), ("yukyu", "skip_one_year"),
    ("zangyo", "hours_for_average"), ("zangyo", "marginal_hour"),
])
def test_完全一致の表で呼べるようになった関数(mod, fname):
    """**短い引数名だけで、20関数が掃引から落ちていました**（2026-08-20）。

    `PARAM_FILL` も `FILL_ONLY` も**部分一致**（`name in param`）なので、
    `i` や `n` や `step` はそこに置けません（`i` は `income` にも当たる）。
    足りなかったのは語彙ではなく**引き方**で、`EXACT_FILL`（完全一致）を
    先に引くようにして戻りました（34件 → 14件）。
    """
    import importlib

    from src.section_sweep import unreachable

    fn = getattr(importlib.import_module(f"src.calc.{mod}"), fname)
    assert unreachable(fn) == "", f"{mod}.{fname} が掃引から落ちている"


def test_完全一致の表は部分一致に混ぜない():
    """`EXACT_FILL` の短い名前を `PARAM_FILL` / `FILL_ONLY` に置かないこと。

    あちらは部分一致なので、`i` を置いた瞬間に **`income` も `kikan` も
    12 で埋まります**（＝金額の引数が桁ごと壊れて、掃引は「不変」を返す）。
    **同じ表に混ぜたら壊れる**ことを、ここで固定します。
    """
    from src import calc_axes

    for name in calc_axes.EXACT_FILL:
        assert name not in calc_axes.PARAM_FILL, f"{name} は部分一致に置けない"
        assert name not in calc_axes.FILL_ONLY, f"{name} は部分一致に置けない"
    from src.section_sweep import _axis_fill

    assert _axis_fill("i") == 12
    assert _axis_fill("income") == calc_axes.AXIS_FILL["所得"], "短い名前が金額を食った"
    assert _axis_fill("kikan") == calc_axes.AXIS_FILL["期間"], "短い名前が期間を食った"
