"""**語る制度と、画面に出る表が別の制度**になるのを、段をそろえて止める。

## 実際に起きたこと（2026-08-30 に見つけた・実測）

2026-08-29 の `topic_forge --new-family` が書いた
`sankyu-14nichi-michi-ga-nai` は、**産休と育休の社会保険料の免除**を語る題で、
主役の数は **27,450円**（`src/calc/sankyu.py` の
`=== 産休には「14日以上」の道が無い（同じ休みでも免除が変わる）===` の
`差の額(円)` そのもの）。ところが `config/topics.yaml` に書かれた `calc:` は
**`kafunenkin`（寡婦年金・死亡一時金）**で、`calc_sections:` は
`寡婦年金がいちばん有利なのは…` を指していました。

**そのまま作れば、読み上げは産休の免除、画面の棒は寡婦年金**になります。
`realign()` の docstring が 2026-08-16（節の粒度）と 08-25（calc の粒度）で
**2回 書いている壊れ方の3回目**です。

## なぜ `CROSS_MARGIN` が止められなかったか（**段のちがう数を比べていた**）

`best_section` は「下限 1000 → 10 → 小数」と**その calc の中だけで**降り、
**どこかで当たったところで止まります**（`rungs` の註）。
`realign` の `cross` は、その一致数を calc どうしで**そのまま**比べます。

    題の金額（下限1000）  {27,450}
    sankyu      下限1000 で 一致 **1**      ← 正しい族
    kafunenkin  下限1000 で 一致 0 → 段を落として 一致 **3**（20 / 25 / 35 …）

**3 > 1 なので、`ctop >= top + CROSS_MARGIN` は永久に成り立ちません。**
正しい族が数で負けています。**段がちがう数を大小で比べると、
答えは段のほうで決まります。**

## この検査が固定していること

  1. 貼られた calc が題の金額を**1つも持たず**、別の calc が持っていれば動かす
  2. 貼られた calc が**1つでも**持っていれば動かさない
     （導出値 —— 表が両端だけを印字し、差を印字しない形。同じ回に鳴った
      `koureikoyou` / `taishoku` / `souzoku` / `kyoiku` / `nenkinmenjo` /
      `yoteinozei` の6件は、**どれも本物ではありませんでした**）
  3. 題に下限1000の数が無ければ、何も言わない（名指しできない）
  4. **同じ金額を2つの表が持つとき**は、同じ段（`SMALL_FLOOR`）で数え直して
     ほどく（実測: `27,450` は `sankyu` と `koyouhoken` の両方に在る）

**覆る条件**: 金額を1円も印字しない calc（年齢と月数だけの表）へ
誤って動かす回が出たら、移り先に「金額の表であること」を足すこと。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "topic_forge", ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)


# `kafunenkin` 側は**小さい整数だけ**が当たる（段を落として一致3になる形）。
SECTIONS = {
    "sankyu": {
        "=== 産休には「14日以上」の道が無い ===":
            "7日 差0か月 0円 / 14日 差1か月 27,450円 / 20日 27,450円 / "
            "25日 27,450円 / 29日 27,450円",
    },
    "kafunenkin": {
        "=== 寡婦年金がいちばん有利なのは20年ちょうどの人 ===":
            "120月(10年) 120,000円 / 180月(15年) 145,000円 / "
            "240月(20年) 170,000円 / 300月(25年) 220,000円 / "
            "420月(35年) 320,000円",
    },
    "koyouhoken": {
        "=== 厚生年金には上限があるのに、雇用保険料には上限が無い ===":
            "標準報酬 650,000円 / 厚生年金 59,475円 / 差 27,450円",
    },
}
MODS = ["sankyu", "kafunenkin", "koyouhoken"]

SANKYU_TEXT = (
    "月初から14日休んでも産休だと免除は0か月 "
    "主役は月初からの日数14日の行。産休の免除月数0、育休の免除月数1、"
    "差は1か月で27,450円。棒にする行は7日（0円）、14日（27,450円）、"
    "29日（27,450円）。20日と25日の27,450円も同じ棒に並べる。"
)


def test_金額を1つも持たない_calc_に貼られていたら動かす():
    got = forge.money_owner(SANKYU_TEXT, "kafunenkin", MODS, SECTIONS)
    assert got is not None, "**段のちがう一致数で負けて、動かないままだった**"
    mod, head, n = got
    assert mod == "sankyu"
    assert "14日以上" in head
    assert n == 1


def test_同じ金額を持つ表が2つあっても_小さい数でほどく():
    """`27,450` は `sankyu` と `koyouhoken` の両方に在る（実測）。"""
    mod, _, _ = forge.money_owner(SANKYU_TEXT, "kafunenkin", MODS, SECTIONS)
    assert mod == "sankyu", "同点を最初に見つけた側で決めていないこと"


def test_1つでも持っていれば動かさない():
    """導出値（表が両端だけを印字し、差を印字しない）の題を動かさない。"""
    text = ("賃金は244,000円から220,000円へ24,000円下がるのに、"
            "給付は24,400円から22,000円へ2,400円減る")
    sections = {
        "koureikoyou": {"=== 下げ幅の何割が戻るか ===":
                        "244,000円 220,000円 24,400円 22,000円"},
        "taishoku": {"=== 無税の上限 ===": "24,000円 8,000,000円"},
    }
    assert forge.money_owner(text, "koureikoyou",
                             ["koureikoyou", "taishoku"], sections) is None


def test_金額が1つも無い題には何も言わない():
    text = "主役は14日の行。差は1か月。7日と29日も並べる。"
    assert forge.money_owner(text, "kafunenkin", MODS, SECTIONS) is None


def test_持っている_calc_が他に無ければ動かさない():
    assert forge.money_owner(SANKYU_TEXT, "kafunenkin",
                             ["kafunenkin"], SECTIONS) is None
