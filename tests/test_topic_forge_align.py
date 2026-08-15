"""**書かせた順に節を貼らない。**中身の数字が載っている節へ貼り直せているか。

2026-08-16 に実物で踏んだ穴です。`zoyo` の4件を頼んだところ、書き手は
**1つめの節から2件**書き、残り3件が1つずつ後ろへずれました。`zip` は順番だけで
貼るので、**「1年から2年で80万円浮く」に「誰から誰への贈与か」の表**が付きます。

`calc_sections` は **画面に出す表そのものを選ぶ鍵**（`src/script_writer.py`）なので、
ずれたまま作ると**語っている数字と画面の表が別物**になります。
機械検査は「表の中の数字か」しか見ておらず、**どの表かは誰も見ていませんでした。**

ここで使っている題と狙いは、**そのとき実際に返ってきた文そのもの**です。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "topic_forge", ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)

from src.calc import zoyo  # noqa: E402


def sections() -> dict[str, str]:
    """`zoyo` の節ごとの表。**印字と同じ形**で作る（突き合わせる相手がこれ）。"""
    split = "\n".join(
        f"{r['years']}年 1年あたり {r['per_year']:,}円 総税額 {r['total_tax']:,}円 "
        f"1年のばすと浮く額 {r['saved_by_one_more_year'] or 0:,}円"
        for r in zoyo.split_grid(10_000_000, 10))
    gap = "\n".join(
        f"{r['amount']:,}円 一般 {r['general_tax']:,}円 特例 {r['special_tax']:,}円 "
        f"差 {r['gap']:,}円"
        for r in zoyo.rate_gap_grid())
    edge = "\n".join(
        f"贈与額 {a:,}円 特例 {zoyo.gift_tax(a):,}円 一般 {zoyo.gift_tax(a, special=False):,}円"
        for a in (1_100_000, 1_100_001, 1_200_000, 2_000_000, 3_100_000))
    zero = "\n".join(
        f"{a:,}円 0円になる年数 {zoyo.years_to_zero(a)}年 "
        f"1年で渡した場合の税額 {zoyo.gift_tax(a):,}円"
        for a in (5_000_000, 10_000_000, 20_000_000, 30_000_000, 50_000_000))
    return {"1000万円を何年に分けるか。税額は年数に反比例しない": split,
            "同じ額でも、誰から誰への贈与かで税額が変わる": gap,
            "基礎控除110万円のすぐ上。またいでも税額はすぐには出ない": edge,
            "無税で渡し切るには何年かかるか。一括の税額と並べる": zero}


class _Item:
    def __init__(self, tid: str, title: str, angle: str):
        self.id, self.title_seed, self.angle = tid, title, angle


class _Set:
    def __init__(self, topics):
        self.topics = topics


# ---- 2026-08-16 に実際に返ってきた4件（1件目だけが正しく、あとは1つずつずれている）
REAL = [
    ("s-zoyo-1000man-10nen-zero", "1000万円を10年に分けると贈与税は0円",
     "主役の数字は、1000万円を10年に分けたときの総税額0円。9年なら9999円、"
     "1年なら1,770,000円。1年あたり1,000,000円に落ちる",
     "1000万円を何年に分けるか。税額は年数に反比例しない"),
    ("s-zoyo-1nen-nobasu-80man", "1年から2年に分けるだけで80万円浮く計算",
     "主役の数字は、1000万円を1年から2年に分けたときに浮く800,000円。"
     "2年から3年で浮くのは265,000円、3年から4年では145,000円と落ちていく",
     "1000万円を何年に分けるか。税額は年数に反比例しない"),
    ("s-zoyo-1000man-ippan-tokurei-54man", "同じ1000万円でも誰から誰かで54万円ちがう",
     "主役の数字は、1000万円の贈与で一般2,310,000円と特例1,770,000円、その差540,000円。"
     "3,000,000円では一般も特例も190,000円で差は0円",
     "同じ額でも、誰から誰への贈与かで税額が変わる"),
    ("s-zoyo-110man-mataide-1man", "110万円を1円こえても贈与税は0円のまま",
     "主役の数字は、贈与額1,100,001円のときの税額0円と、1,200,000円のときの10,000円。"
     "2,000,000円なら90,000円、3,100,000円なら200,000円",
     "基礎控除110万円のすぐ上。またいでも税額はすぐには出ない"),
]


def test_ずれた割り当てを中身の数字で貼り直す():
    heads = list(sections())
    items = [_Item(tid, title, angle) for tid, title, angle, _ in REAL]
    # **書かせた順に貼った**状態（実物がこうなっていた）
    picked = [("zoyo", h) for h in heads]
    fixed = forge.realign(_Set(items[:1] + items[2:]), picked[:1] + picked[2:],
                          {"zoyo": sections()})
    want = [REAL[0][3], REAL[2][3], REAL[3][3]]
    assert [h for _, h in fixed] == want


def test_同じ節に2件当たったら失敗させる():
    """1件目と2件目は**どちらも同じ節**から書かれている。在庫の数え方が崩れる。"""
    items = [_Item(tid, title, angle) for tid, title, angle, _ in REAL[:2]]
    picked = [("zoyo", h) for h in list(sections())[:2]]
    with pytest.raises(SystemExit) as e:
        forge.realign(_Set(items), picked, {"zoyo": sections()})
    assert "同じ節" in str(e.value)


def test_表に無い数字だけの題は落とす():
    item = _Item("s-zoyo-nise", "贈与税は年間7,654,321円まで無税",
                 "主役の数字は7,654,321円。表のどこにも無い数字を使っている")
    with pytest.raises(SystemExit) as e:
        forge.realign(_Set([item]), [("zoyo", list(sections())[0])],
                      {"zoyo": sections()})
    assert "どの節の表にも載っていません" in str(e.value)


def test_万と桁区切りを同じ数として読む():
    assert 800_000 in forge.numbers("80万円")
    assert 800_000 in forge.numbers("800,000円")
    assert 1_100_001 in forge.numbers("110万1円")
    assert 265_000 in forge.numbers("26万5000円")
    # 年数のような小さい数は当てにしない（どの表にも出るので、印にならない）
    assert 9 not in forge.numbers("9年")


# ---- 下限を表から決める（2026-08-16。**新しい題材を足して実際に踏んだ**）----
#
# `numbers()` の下限は長らく 1000 固定でした。理由は「年数や桁の小さい語を
# 当てにしない」ですが、**表に載っているのが金額のときにだけ正しい**仮定です。
# 同日に足した `yukyu`（日数）と `jikangai`（時間）は表の数字が全部3桁以下で、
# `best_section` の一致数が全節で0になり、**`realign` が正しい企画を
# 「表の外の数字」と誤って止めました**（2回連続）。

def test_金額の表を持つ_calc_は下限が1000のまま():
    """**既存16本の挙動は変えない。** ここが動くと、年数が印として拾われ始めます。"""
    assert forge.section_floor(sections()) == forge.MONEY_FLOOR


def test_金額を持たない表は下限が下がる():
    small = {"=== 有給の日数 ===": "勤続 6か月 10日 / 6年6か月 20日 累計 361日",
             "=== 残業の上限 ===": "3か月 240時間 6か月 480時間 差 114時間"}
    assert forge.section_floor(small) == forge.SMALL_FLOOR


def test_日数と時間の題が節に当たる():
    """**下限を下げないと、ここが 0 になって realign が止まります。**"""
    small = {"=== 有給の日数 ===": "勤続 6か月 10日 / 6年6か月 20日 累計 361日",
             "=== 残業の上限 ===": "3か月 240時間 6か月 480時間 差 114時間"}
    top, head = forge.best_section("繁忙期3か月に置けるのは240時間", small)[0]
    assert top > 0
    assert head == "=== 残業の上限 ==="


def test_下限を渡せば小さい数も拾う():
    assert 45 in forge.numbers("月45時間", floor=10)
    assert 45 not in forge.numbers("月45時間")
    # 1桁は、下限を下げても拾わない（どの表にも出るので印にならない）
    assert 6 not in forge.numbers("6か月", floor=forge.SMALL_FLOOR)


# ---- 同点では動かさない（2026-08-16。**回ごと落ちて気づいた**）----
#
# `realign` は「一致数が最大の節」を無条件に採っていました。**同点のときに
# 勝つのは dict の順で、根拠がありません。** 節をまたいで同じ数字が出るのは
# むしろ普通（制度の定数・同じ日額）なので、正しく割り当てられた企画が
# 隣の節へ飛び、そのあと「同じ節に2件」で回ごと落ちました。

def _two_sections():
    return {"=== A ===": "40日 と 120時間",
            "=== B ===": "40日 と 250時間"}


def test_同点なら割り当て先のまま動かさない():
    item = _Item("s-x-40", "40日で決まる", "主役は40日。どちらの節にも出る数")
    got = forge.realign(_Set([item]), [("m", "=== B ===")],
                        {"m": _two_sections()})
    assert got == [("m", "=== B ===")]


def test_厳密に強ければ貼り直す():
    item = _Item("s-x-250", "40日と250時間", "主役は250時間。片方の節にしか出ない")
    got = forge.realign(_Set([item]), [("m", "=== A ===")],
                        {"m": _two_sections()})
    assert got == [("m", "=== B ===")]
