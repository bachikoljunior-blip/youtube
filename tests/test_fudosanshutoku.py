"""不動産取得税（`src/calc/fudosanshutoku.py`）の主題を固定する。

**壊れても値は「もっともらしい」ままなので、形と境目のほうを見ています。**
"""
import pytest

from src.calc import fudosanshutoku as f


def test_check_tables_passes():
    f.check_tables()


# ---- 節1: 0円で済むのは控除額までではない ------------------------------
def test_zero_limit_is_above_the_deduction():
    """**「1,200万円まで非課税」は間違い。**免税点のぶん上に伸びます。"""
    assert f.kaoku_zero_limit() == 12_229_999
    assert f.kaoku_tax(12_229_999, 100) == 0
    assert f.kaoku_tax(12_230_000, 100) == 6_900


def test_choki_has_the_same_margin_and_the_same_cliff():
    """控除が100万円ちがっても、**余白も崖も1円も違いません。**"""
    a = f.kaoku_zero_limit()
    b = f.kaoku_zero_limit(choki=True)
    assert b - a == f.CHOKI_KOJO - f.SHINCHIKU_KOJO
    assert f.kaoku_tax(a + 1, 100) == f.kaoku_tax(b + 1, 100, choki=True) == 6_900


def test_menzeiten_is_not_swallowed_by_the_deduction():
    """免税点を落とすと 12,000,001円で課税が始まります（**この検査が落とす**）。"""
    assert f.kaoku_tax(12_000_001, 100) == 0


# ---- 節2: 床面積の崖は上と下の両方にある -------------------------------
@pytest.mark.parametrize("value", [15_000_000, 20_000_000, 30_000_000])
def test_floor_cliff_exists_on_both_ends_and_is_equal(value):
    low = f.kaoku_tax(value, f.FLOOR_MIN - 1) - f.kaoku_tax(value, f.FLOOR_MIN)
    high = f.kaoku_tax(value, f.FLOOR_MAX + 1) - f.kaoku_tax(value, f.FLOOR_MAX)
    assert low == high > 0


def test_floor_cliff_tops_out_at_the_deduction_times_the_rate():
    """崖は**控除額×税率で頭打ち**。評価額をいくら上げても増えません。"""
    assert f.floor_cliff_max()["跳ぶ額の上限"] == 360_000
    for value in (50_000_000, 100_000_000):
        jump = f.kaoku_tax(value, 241) - f.kaoku_tax(value, 240)
        assert jump == 360_000


def test_49_and_241_are_the_same_amount():
    """**両端の崖は同額**（下の崖を落とすと、ここだけが赤くなります）。"""
    v = 20_000_000
    assert f.kaoku_tax(v, 49) == f.kaoku_tax(v, 241) == 600_000
    assert f.kaoku_tax(v, 50) == f.kaoku_tax(v, 240) == 240_000


# ---- 節3: 土地の税額は「はみ出した面積」で決まる ------------------------
@pytest.mark.parametrize("unit", [50_000, 200_000, 1_000_000])
def test_zero_land_area_does_not_move_with_the_unit_price(unit):
    """**単価によりません。**2億円の土地でも、はみ出していなければ0円。"""
    limit = f.tochi_zero_area(100)
    assert limit == 200
    assert f.tochi_tax(limit, unit, 100) == 0
    assert f.tochi_tax(limit + 1, unit, 100) > 0


def test_land_tax_is_proportional_to_the_excess_area():
    """はみ出した面積が2倍なら税額も2倍（**下限が効かない帯で**）。"""
    rows = {r["土地面積"]: r["税額"] for r in f.tochi_excess_grid()}
    assert rows[250] == 150_000 and rows[300] == 300_000 and rows[400] == 600_000


# ---- 節4: 土地の控除は床面積100平方メートルで頭打ち ---------------------
def test_land_credit_flattens_at_100_sqm():
    assert f.tochi_credit(200_000, 100) == f.tochi_credit(200_000, 240) == 600_000
    assert f.tochi_credit(200_000, 50) == 300_000
    flat = f.floor_credit_flat_from()
    assert flat["頭打ちになる床面積"] == 100
    assert flat["同額で並ぶ幅"] == 140


# ---- 節5: 45,000円の下限が効く単価の敷居 -------------------------------
def test_floor_price_threshold_halves_and_then_stops():
    assert round(f.floor_credit_cap(50)) == 30_000
    assert round(f.floor_credit_cap(100)) == 15_000
    assert round(f.floor_credit_cap(240)) == 15_000
    assert f.floor_price_threshold_span()["倍率"] == 2.0


# ---- 節6: 「2分の1」は上限であって、下回ることがある --------------------
def test_half_is_a_ceiling_not_an_equality():
    ratios = [r["残る割合"] for r in f.hangaku_grid() if r["残る割合"] is not None]
    assert max(ratios) == 0.5
    assert min(ratios) == 0.0
    assert 0.25 in ratios


def test_the_special_rule_moves_the_vanishing_point():
    """特例は「半額」ではなく、**税額が消える単価の境目を動かします。**"""
    with_h = f.hangaku_zero_limit()
    without = f.hangaku_zero_limit(hangaku=False)
    assert with_h == 10_026 and without == 5_013
    assert with_h > without


# ---- 節7: 中古住宅は新築時期で12倍 -------------------------------------
def test_chuko_steps_are_not_monotone():
    """**段差は単調ではありません。**いちばん浅い段の次が、いちばん深い段です。"""
    rows = f.chuko_grid()
    steps = [r["1つ前の段との差"] for r in rows if r["1つ前の段との差"] is not None]
    assert steps == [15_000, 24_000, 36_000, 21_000, 9_000, 165_000, 60_000]
    assert steps.index(min(steps)) + 1 == steps.index(max(steps))


def test_chuko_span():
    span = f.chuko_span()
    assert span["控除の倍率"] == 12
    assert span["段数"] == 8
    assert span["税額の最大差"] == 330_000


# ---- 台帳との接続 ------------------------------------------------------
def test_topic_is_wired_to_this_table():
    """**表を書いても、繋がなければ在庫は1本も増えません**（4回踏んでいます）。"""
    from src import config
    topics = config.load_topics()["topics"]
    row = next(t for t in topics if t["id"] == "fudosanshutoku-zei")
    assert row["calc"] == "fudosanshutoku"


def test_subject_words_registered():
    """`SUBJECT_WORDS` の足し忘れは通算6件。**ここで止めます。**"""
    from src.script_writer import SUBJECT_WORDS
    assert "不動産取得税" in SUBJECT_WORDS["fudosanshutoku"]
