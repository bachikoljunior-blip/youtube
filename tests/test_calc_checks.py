"""`src/calc/_checks.py` に、**故障を注入して全部止まることを確かめる。**

**発火したことのない検査は検査ではありません。** ここは
`docs/JOURNAL.md` 2026-08-15 の流儀（「`check_tables()` に故障を3種類注入して、
全部止まることを確かめた」）をそのまま道具の側に移したものです。

とくに `per_unit_steps` は、**実際に素通りした欠陥**（`taishoku.py` が5年とびの行に
「1年あたりの伸び」と書いて前の行との差そのものを出していた）を固定しています。
"""
from __future__ import annotations

import pytest

from src.calc import _checks as C

# 所得税の速算表（正しいもの）。故障はこれを崩して作る。
GOOD = [
    (1_950_000, 0.05, 0),
    (3_300_000, 0.10, 97_500),
    (6_950_000, 0.20, 427_500),
    (9_000_000, 0.23, 636_000),
    (18_000_000, 0.33, 1_536_000),
    (40_000_000, 0.40, 2_796_000),
    (None, 0.45, 4_796_000),
]


def tax_with(table):
    def tax_of(base):
        for cap, rate, sub in table:
            if cap is None or base <= cap:
                return base * rate - sub
        raise AssertionError("速算表に当たらない")
    return tax_of


# ------------------------------------------------------------ 速算表

def test_good_table_passes():
    C.bracket_table(GOOD, tax_with(GOOD))


def test_bracket_rejects_swapped_rows():
    """行を入れ替える（列ずれの典型）。"""
    bad = GOOD[:2][::-1] + GOOD[2:]
    with pytest.raises(C.TableError):
        C.bracket_table(bad, tax_with(bad))


def test_bracket_rejects_dropped_digit():
    """控除額の桁落ち（97,500 → 9,750）。**境目で税額が飛ぶ。**"""
    bad = [GOOD[0], (3_300_000, 0.10, 9_750)] + GOOD[2:]
    with pytest.raises(C.TableError) as e:
        C.bracket_table(bad, tax_with(bad))
    assert "飛んでいる" in str(e.value)


def test_bracket_rejects_percent_written_as_whole_number():
    """税率を 0.05 ではなく 5 と書く。"""
    bad = [(1_950_000, 5, 0)] + GOOD[1:]
    with pytest.raises(C.TableError):
        C.bracket_table(bad, tax_with(bad))


def test_bracket_rejects_open_middle_row():
    """途中の段に上限が無い（表が途中で切れている）。"""
    bad = [GOOD[0], (None, 0.10, 97_500)] + GOOD[2:]
    with pytest.raises(C.TableError):
        C.bracket_table(bad, tax_with(bad))


def test_bracket_rejects_sentinel_top_that_is_not_max():
    """番人の値で最上段を書いたのに、それが最大でない。"""
    bad = GOOD[:-1] + [(1_000, 0.45, 4_796_000)]
    with pytest.raises(C.TableError):
        C.bracket_table(bad, tax_with(bad))


def test_bracket_accepts_sentinel_top():
    """`jutaku.py` のように 10**12 で最上段を書く形も通ること。"""
    ok = GOOD[:-1] + [(10**12, 0.45, 4_796_000)]
    C.bracket_table(ok, tax_with(ok))


def test_bracket_rejects_two_row_table_with_gap():
    bad = [(1_000_000, 0.10, 0), (None, 0.20, 0)]
    with pytest.raises(C.TableError):
        C.bracket_table(bad, tax_with(bad))


# ------------------------------------------------------------ 法令の値・率

def test_statutory_reports_both_sides():
    with pytest.raises(C.TableError) as e:
        C.statutory(1.021, 1.0, "復興特別所得税の係数", source="復興財確法")
    assert "復興財確法" in str(e.value)


def test_ratio_catches_percent_as_whole_number():
    with pytest.raises(C.TableError):
        C.ratio(5, "住民税の所得割")
    C.ratio(0.05, "住民税の所得割")


def test_digits_catches_man_yen_mixup():
    with pytest.raises(C.TableError):
        C.digits(38, 10_000, 1_000_000, "扶養控除")
    C.digits(380_000, 10_000, 1_000_000, "扶養控除")


# ------------------------------------------------------------ 並びと向き

def test_ascending_and_strict():
    C.ascending([1, 1, 2], "段")
    with pytest.raises(C.TableError):
        C.ascending([1, 1, 2], "段", strict=True)
    with pytest.raises(C.TableError):
        C.ascending([2, 1], "段")


def test_increases_with_rejects_flat():
    C.increases_with(lambda x: x * 2, [1, 2, 3], "増えていない")
    with pytest.raises(C.TableError):
        C.increases_with(lambda x: 5, [1, 2, 3], "増えていない")


def test_never_decreases_allows_flat_but_not_drop():
    C.never_decreases(lambda x: min(x, 2), [1, 2, 3], "減っている")
    with pytest.raises(C.TableError):
        C.never_decreases(lambda x: -x, [1, 2, 3], "減っている")


def test_decreases_with():
    C.decreases_with(lambda x: -x, [1, 2, 3], "減っていない")
    with pytest.raises(C.TableError):
        C.decreases_with(lambda x: x, [1, 2, 3], "減っていない")


def test_greater_and_unique():
    C.greater(2, 1, "大きいほうが小さい")
    with pytest.raises(C.TableError):
        C.greater(1, 1, "大きいほうが小さい")
    rows = [{"name": "a"}, {"name": "b"}]
    C.unique_by(rows, lambda r: r["name"], "控除の表")
    with pytest.raises(C.TableError):
        C.unique_by(rows + [{"name": "a"}], lambda r: r["name"], "控除の表")


def test_rounding_fixes_the_order():
    C.rounding(6_667, 6_667, "標準報酬30万円の日額")
    with pytest.raises(C.TableError):
        C.rounding(6_666, 6_667, "標準報酬30万円の日額")


def test_close_accepts_the_last_bit_but_not_a_real_gap():
    """**`rounding` は率には使えません**（浮動小数の最後の1桁で落ちる）。

    実物は `koureikoyou.py` の傾き —— 率と境目から出した `0.15*0.61/0.14` と、
    公表されている `183/280` は、数学的には同じで最後の1桁だけ違います。
    """
    derived = 0.15 * 0.61 / (0.75 - 0.61)
    published = 183 / 280
    assert derived != published            # ← `rounding` はこれで落ちていた
    C.close(derived, published, "改正前の傾き")

    # 本物の食い違いは、ちゃんと止まること
    with pytest.raises(C.TableError):
        C.close(0.10 * 0.61 / (0.75 - 0.61), published, "改正後の傾き")
    with pytest.raises(C.TableError):
        C.close(0.0305, 0.0306, "減額の比", tol=1e-6)


def test_rounding_says_when_it_is_only_the_last_bit():
    """**`rounding` のメッセージは「丸めの順番」としか言いませんでした。**

    最後の1桁で落ちた回は、そこから計算のほうを疑いにいきます（実測6分）。
    近すぎるときは `close` を指す1行が出ること。**遠いときは出ないこと**
    （出すと本物の食い違いのときに読み手を迷わせます）。
    """
    with pytest.raises(C.TableError) as near:
        C.rounding(0.15 * 0.61 / (0.75 - 0.61), 183 / 280, "改正前の傾き")
    assert "close" in str(near.value)

    with pytest.raises(C.TableError) as far:
        C.rounding(6_666, 6_667, "標準報酬30万円の日額")
    assert "close" not in str(far.value)


# -------------------------------------------- ラベルと値（実際に素通りした欠陥）

ROWS_5Y = [{"years": y, "free": f} for y, f in
           ((5, 2_000_000), (10, 4_000_000), (15, 6_000_000), (20, 8_000_000))]


def test_per_unit_divides_by_the_row_step():
    """**これが 2026-08-15 の欠陥そのもの。**

    行は5年とび。差は200万円だが、「1年あたり」と言うなら **40万円** でなければ
    ならない。旧実装は差をそのまま出していて、`check_tables()` は素通りした。
    """
    got = C.per_unit_steps(ROWS_5Y, "years", "free", label="1年あたりの伸び", x_unit="年")
    assert got[0] is None
    assert got[1:] == [400_000, 400_000, 400_000]
    assert 2_000_000 not in got  # 差そのものを出していたら、ここで落ちる


def test_per_unit_rejects_label_without_a_unit():
    with pytest.raises(C.TableError) as e:
        C.per_unit_steps(ROWS_5Y, "years", "free", label="伸び", x_unit="年")
    assert "単位" in str(e.value)


def test_per_unit_rejects_label_that_names_the_wrong_unit():
    """見出しが「1か月あたり」なのに、表は年で並んでいる。"""
    with pytest.raises(C.TableError):
        C.per_unit_steps(ROWS_5Y, "years", "free", label="1か月あたりの伸び", x_unit="年")


def test_per_unit_rejects_non_increasing_x():
    bad = [{"years": 10, "free": 1}, {"years": 10, "free": 2}]
    with pytest.raises(C.TableError):
        C.per_unit_steps(bad, "years", "free", label="1年あたりの伸び", x_unit="年")


def test_declared_unit():
    assert C.declared_unit("1年あたりの伸び") == "年"
    assert C.declared_unit("1か月あたり0.7パーセント") == "か月"
    assert C.declared_unit("1日あたりの額") == "日"
    assert C.declared_unit("前年からの増え") is None


# ------------------------------------------------------------ ひな型

def test_template_refuses_to_run_unfilled():
    """`_template.py` は、埋めるまで必ず落ちること。

    **埋め忘れたまま台本を書かせる道を作らないための固定です。**
    """
    from src.calc import _template
    with pytest.raises(C.TableError):
        _template.check_tables()


def test_template_is_not_a_topic_source():
    """`_` 始まりは `topic_forge.py` が拾わないこと。"""
    import scripts.topic_forge as tf
    assert "_template" not in tf.calc_modules()
    assert "_checks" not in tf.calc_modules()


# ------------------------------------- 本物の calc が、この道具で通ること

def test_real_tables_pass():
    """**実物で通らない道具は道具ではありません。**"""
    from src.calc import jutaku, souzoku, taishoku
    C.bracket_table(souzoku.TAX_TABLE, souzoku.tax_of, name="相続税の速算表")
    C.bracket_table(taishoku.TAX_TABLE, taishoku.income_tax_raw, name="所得税の速算表")
    C.bracket_table(jutaku.BRACKETS, jutaku.income_tax, name="所得税の速算表")


def test_every_calc_module_still_passes_its_own_checks():
    """12本ぜんぶの `check_tables()` が、いまも通ること。"""
    import importlib
    import pathlib
    names = sorted(p.stem for p in pathlib.Path("src/calc").glob("*.py")
                   if not p.stem.startswith("_"))
    assert len(names) >= 12, names
    for name in names:
        mod = importlib.import_module(f"src.calc.{name}")
        assert hasattr(mod, "check_tables"), f"{name} に check_tables が無い"
        mod.check_tables()
