"""`src/section_sweep.py` —— **機械が節の候補を拾えるか**（2026-08-17）。

この道具が守らなければならないのは2つです。

1. **本物の形を拾うこと**（崖・頭打ち・逆転・不変）
2. **屑を拾わないこと** —— ここが本体です。1回目の実測では
   `kyugyo` の13件のうち **6件が「入力の再掲」**、
   `ratio_span` の「逆転」は **円未満の切り捨てだけで出来た 0.08% の山**、
   `iryohi.floor_grid` の「崖」は **こちらが選んだ目盛りの粗さ**でした。
   **一覧が当たりを含まないまま育つ**（`src/alerts.py`）と同じ形なので、
   **落とす側を検査に固定します。**

**当たり率で畳む仕掛けには繋いでいません。** この一覧は `status.py` が
件数の1行しか出さず、全文を見るのは人が `--calc` を叩いたときだけなので、
**育っても鳴りっぱなしにはなりません。**
"""
from __future__ import annotations

import copy
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import section_sweep as ss  # noqa: E402


# ---- 実物の全掃引は、この検査の中で **1回だけ** 走らせる（2026-08-26）--------
#
# **この1ファイルだけで 685秒 かかっており、全体の `pytest` が
# 何日も「時間切れで通していません」と申し送られ続けていました**
# （`docs/JOURNAL.md` 2026-08-26 03:5x / 04:3x の申し送り 6・7。
#  `retro.py` の持ち越しにも `pytest` と `test_section_sweep.py` が2回ずつ）。
#
# 実測（`--durations=12`）: 遅い12件が **全部 `ss.sweep_all()` を丸ごと1回ずつ**
# 呼んでおり、合計 608秒 ＝ **ファイル全体の 89%** でした。
# `sweep_all()` は 1回 46〜48秒、**引数が同じなら結果も同じ**
# （実測: 2回続けて呼んで `==` が真・候補1,236件）。
# つまり 11回ぶんは、**同じ計算をやり直しているだけ**です。
#
# **検査の中身は1つも変えていません。** 変えたのは「何回 計算するか」だけ。
# 呼び出し側には毎回コピーを渡すので、どれかが手を入れても次に響きません。
#
# **`monkeypatch` で表を壊してから掃く検査（`test_壊れた表があっても全体は止まらない`）
# だけは、ここを通さず `ss.sweep_all()` を直に呼ぶこと。** 壊した結果を
# ここに載せると、後続の検査がその壊れた一覧を読みます。
_SWEEP_CACHE: dict[tuple[str, ...] | None, list[dict]] = {}


def sweep_once(names: list[str] | None = None) -> list[dict]:
    """同じ引数の `ss.sweep_all()` を、この session で1回に畳む。"""
    key = tuple(names) if names is not None else None
    if key not in _SWEEP_CACHE:
        _SWEEP_CACHE[key] = ss.sweep_all() if names is None else ss.sweep_all(names)
    return copy.deepcopy(_SWEEP_CACHE[key])


# ---- 形を見分ける ------------------------------------------------------

def test_動かない列は不変():
    shape, detail = ss._classify(list(range(6)), [4.2] * 6)
    assert shape == "不変"
    assert detail["値"] == 4.2


def test_途中から動かない列は頭打ち():
    shape, detail = ss._classify(list(range(6)), [10, 20, 30, 40, 40, 40])
    assert shape == "頭打ち"
    assert detail["止まった値"] == 40


def test_1つだけ跳ぶ列は崖():
    shape, detail = ss._classify(list(range(6)), [100, 110, 120, 900, 910, 920])
    assert shape == "崖"
    assert detail["跳ぶ幅"] == 780


def test_山が途中にある列は逆転():
    shape, detail = ss._classify(list(range(6)), [10, 40, 90, 80, 30, 20])
    assert shape == "逆転"
    assert detail["どこ"] == "いちばん高い"
    assert detail["値"] == 90


def test_まっすぐな列は何でもない():
    assert ss._classify(list(range(6)), [10, 20, 30, 40, 50, 60]) is None


def test_点が3つ以下では何も言わない():
    assert ss._classify([0, 1, 2], [1, 5, 1]) is None


# ---- 屑を落とす（**ここが本体**） ---------------------------------------

def test_丸めだけの山は逆転にしない():
    """`ratio_span` の 1.2516 対 1.2515。**0.08% の差は制度ではない。**"""
    ys = [0.0934, 0.09341, 0.0935, 0.09342, 0.09341, 0.0934]
    got = ss._classify(list(range(6)), ys)
    assert got is None or got[0] != "逆転", got


def test_跳ぶ幅が全体の1パーセント未満なら崖にしない():
    ys = [1_000_000, 1_000_000, 1_000_000, 1_000_050, 1_000_050, 1_000_050]
    got = ss._classify(list(range(6)), ys)
    assert got is None or got[0] != "崖"


def test_入力の再掲は不変から外す():
    """`{"月給": monthly, "休んだ日数": days_off}` の欄は、拾っても意味が無い。"""
    assert ss._is_echo(20.0, [300_000.0, 20.0], [150_000, 300_000])
    assert ss._is_echo(300_000.0, [20.0], [150_000, 300_000, 600_000])
    assert not ss._is_echo(4.2, [300_000.0, 20.0], [150_000, 300_000])


def test_表じしんの目盛りは外す():
    """先頭の数値欄が単調なら、それは x 軸。**制度ではなくこちらの選び方。**"""
    rows = [{"total_income": v, "floor": v // 10}
            for v in (1_000_000, 2_000_000, 3_000_000, 5_000_000)]
    assert ss._axis_keys(rows, {"total_income", "floor"}) == {"total_income"}


def test_単調でない先頭の欄は外さない():
    rows = [{"帯": v, "額": 10} for v in (3, 1, 2, 4)]
    assert ss._axis_keys(rows, {"帯", "額"}) == set()


def test_2つめ以降の欄は単調でも外さない():
    rows = [{"年齢": v, "保険料": v * 100} for v in (20, 30, 40, 50)]
    assert ss._axis_keys(rows, {"年齢", "保険料"}) == {"年齢"}


# ---- 実物で動く --------------------------------------------------------

def test_この回で足した表から候補が出る():
    hits = ss.sweep_calc("kyugyo")
    assert hits, "kyugyo から1件も出ていない"
    for h in hits:
        assert h["形"] in ss.SHAPES
        assert h["表"] == "kyugyo"


def test_全部の表を掃引しても落ちない():
    hits = sweep_once()
    assert len(hits) >= 20, f"候補が {len(hits)}件。row モードが効いていない疑い"
    assert not [h for h in hits if h["形"] == "読めない"], \
        [h for h in hits if h["形"] == "読めない"]


def test_行モードが表の中の形を拾う():
    """引数を動かす掃引だけだと、`list` を返す表が丸ごと落ちます。"""
    from_rows = [h for h in sweep_once() if h["動かした引数"] == "（表の行）"]
    assert len(from_rows) >= 10, f"行モードの候補が {len(from_rows)}件"


def test_同じ欄が引数ごとに何度も出るのをまとめる():
    hits = [
        {"表": "x", "関数": "f", "見た値": "a", "形": "不変", "詳しく": {},
         "動かした引数": "p", "x の幅": (0, 1)},
        {"表": "x", "関数": "f", "見た値": "a", "形": "不変", "詳しく": {},
         "動かした引数": "q", "x の幅": (0, 1)},
    ]
    out = ss.dedupe(hits)
    assert len(out) == 1
    assert out[0]["ほかの引数"] == ["q"]


def test_崖と逆転が不変より前に出る():
    hits = [
        {"表": "x", "関数": "f", "見た値": "a", "形": "不変", "詳しく": {},
         "動かした引数": "p", "x の幅": (0, 1)},
        {"表": "x", "関数": "f", "見た値": "b", "形": "崖", "詳しく": {},
         "動かした引数": "p", "x の幅": (0, 1)},
    ]
    assert [h["形"] for h in ss.dedupe(hits)] == ["崖", "不変"]


def test_壊れた表があっても全体は止まらない(monkeypatch):
    monkeypatch.setattr(ss, "calc_modules", lambda: ["ないよ", "kyugyo"])
    hits = ss.sweep_all()
    assert [h for h in hits if h["形"] == "読めない"]
    assert [h for h in hits if h["表"] == "kyugyo"], "1本の壊れで他まで落ちている"


def test_掃引の途中で表がprintしても出力を汚さない(capsys):
    ss.sweep_calc("kyugyo")
    assert capsys.readouterr().out == ""


# ---- 行を名指す欄（2026-08-17。**候補の 13% が同語反復でした**）-----------

def _行の見出し(hits, 見た値):
    h = next(h for h in hits if h["見た値"] == 見た値)
    d = h["詳しく"]
    return next(str(d[k]) for k in ("止まる x", "x", "x の手前", "x の先") if k in d)


def test_文字の見出しが無い表は_表じしんの目盛りで行を名指す():
    """**外すのと、名指すのは別の仕事です。**

    `_axis_keys` が x 軸を「見た値」から外した結果、`_row_label` からも
    見えなくなり、**行の名前が結果の欄になっていました** ——
    `月給=101,000` と言うべきところで `標準報酬月額の跳び=6,000` と言う。
    """
    rows = [{"月給": 93_000, "跳び": 10_000, "増": 10_980},
            {"月給": 101_000, "跳び": 6_000, "増": 6_588},
            {"月給": 107_000, "跳び": 6_000, "増": 6_588},
            {"月給": 114_000, "跳び": 8_000, "増": 8_784},
            {"月給": 122_000, "跳び": 8_000, "増": 8_784}]
    hits = ss.sweep_rows(lambda: rows, name="t")
    assert hits, "1件も出ていない"
    for h in hits:
        assert _行の見出し(hits, h["見た値"]).startswith("月給="), h


def test_行を名指す欄そのものは見た値にしない():
    """「いちばん低い跳びは、跳びが 6,000 の行」は**何も言っていません。**"""
    rows = [{"帯": v, "額": 10} for v in (3, 1, 2, 4)]     # 先頭が単調でない
    hits = ss.sweep_rows(lambda: rows, name="t")
    assert not [h for h in hits if h["見た値"] == "帯"], hits


def test_文字の見出しがあるほうを優先する():
    rows = [{"区分": f"第{i}種", "額": v} for i, v in enumerate((5, 1, 2, 3, 4))]
    hits = ss.sweep_rows(lambda: rows, name="t")
    assert hits
    assert _行の見出し(hits, "額").startswith("第"), hits


def test_実物に同語反復が1件も残っていない():
    for h in sweep_once():
        if h["動かした引数"] != "（表の行）":
            continue
        d = h["詳しく"]
        for k in ("止まる x", "x", "x の手前", "x の先"):
            if k in d:
                assert not str(d[k]).startswith(h["見た値"] + "="), \
                    f"{h['表']}.{h['関数']}: {ss.line_of(h)}"


# ---- 単位つきの文字列で持っている欄（2026-08-17。**率がそこにしか無い表がある**）----

@pytest.mark.parametrize("text,want", [
    ("12.3%", 12.3), ("1,234円", 1234.0), ("16.7年", 16.7),
    ("6か月", 6.0), ("2.5倍", 2.5), ("-3.0%", -3.0), (" 40 ", 40.0),
])
def test_単位つきの文字列を数として読む(text, want):
    assert ss._as_number(text) == pytest.approx(want)


@pytest.mark.parametrize("text", ["第3種", "2026-08-17", "ア", "", "1/2", "20〜30"])
def test_数でない文字列は読まない(text):
    assert ss._as_number(text) is None


def test_真偽値は数として読まない():
    """`True` は `int` の仲間なので、素通しすると 1.0 になります。"""
    assert ss._as_number(True) is None
    assert ss._as_number(False) is None


def test_単位は落とすだけで換算しない():
    """`%` を 0.01 倍すると、単位が混ざった欄で黙って桁が狂います。"""
    assert ss._as_number("33%") == 33.0


def test_文字列の率の欄が掃引に載る():
    """**この欄に、いちばん深い崖がありました**（2026-08-17 に人が手で見つけた）。

    `furusato.bracket_jumps` の `はね上がる率` は `f"{...:.1f}%"` なので、
    直す前は `_scalars()` が1件も拾っていませんでした。
    """
    hits = ss.sweep_calc("furusato")
    got = [h for h in hits if h["見た値"] == "はね上がる率"]
    assert got, [h["見た値"] for h in hits]
    assert got[0]["形"] == "逆転", got[0]


def test_行の見出しは単位を残す():
    """`所得税率=33%` を `33` に落とさないこと。"""
    rows = [{"税率": f"{v}%", "額": a}
            for v, a in ((5, 10), (10, 90), (20, 20), (23, 30), (33, 40))]
    hits = ss.sweep_rows(lambda: rows, name="t")
    assert hits
    d = hits[0]["詳しく"]
    label = next(str(d[k]) for k in ("止まる x", "x", "x の手前", "x の先") if k in d)
    assert label.endswith("%"), label


def test_途中の行だけ単位がちがう欄は比べない():
    rows = [{"区分": f"第{i}", "値": v}
            for i, v in enumerate(("1%", "5%", "こえる", "9%", "2%"))]
    hits = ss.sweep_rows(lambda: rows, name="t")
    assert not [h for h in hits if h["見た値"] == "値"], hits


def test_文字列を足しても表が1本も落ちていない():
    """**片方だけ直すと、`float()` が投げて表ごと消えます**（この回に踏んだ）。"""
    hits = sweep_once()
    unreadable = [h for h in hits if h["形"] == "読めない"]
    assert not unreadable, unreadable


# --- 既に節が言っている候補を落とす（2026-08-17 20:5x に足した） --------------
#
# **候補の件数は (B) の同点破りに使われています**（`src/section_depth.py`）。
# 数えていたのが「拾えた形」で「まだ誰も言っていない形」ではなかったため、
# `ideco`（3件が3件とも既出）が (B) の1位に出ていました。
# **ここの検査は落とす側にかけます** —— 落としすぎると候補が過小に見え、
# 落とさなすぎると元の水増しに戻ります。**両方向を固定すること。**

def _sections(*bodies: str) -> dict[str, str]:
    return {f"=== 節{i} ===": b for i, b in enumerate(bodies)}


def test_止まる点が本文に出ていれば既出():
    hit = {"表": "t", "形": "頭打ち",
           "詳しく": {"止まる x": "年収=11,100,000", "止まった値": 0.33}}
    assert ss.is_covered(hit, _sections("年収11,100,000円 最初の1段 4,018円"))


def test_止まる点が出ていなければ新しい():
    hit = {"表": "t", "形": "頭打ち",
           "詳しく": {"止まる x": "年収=9,900,000", "止まった値": 0.33}}
    assert not ss.is_covered(hit, _sections("年収11,100,000円 最初の1段 4,018円"))


def test_節が帯で書いてあっても既出():
    """**節は点ではなく帯で書かれることがあります**（実測 `ideco.grid`）。"""
    hit = {"表": "t", "形": "頭打ち",
           "詳しく": {"止まる x": "年収=6,600,000", "止まった値": 83959.0}}
    assert ss.is_covered(hit, _sections("帯 年収 6,500,000〜6,800,000円（4点）"))


def test_軸の名前が本文に無い小さい数を既出と読まない():
    """**これを入れた直後に踏んだ**（`years=1` が既出になった）。

    引数名は英語・節は日本語なので、軸で行を絞れません。
    そこで表記の `1` を本文から探すと、**どの表でも必ず当たります。**
    """
    hit = {"表": "t", "形": "崖",
           "詳しく": {"x の手前": "years=1", "x の先": "years=2",
                    "跳ぶ幅": 5.0, "中央の段差": 1.0}}
    assert not ss.is_covered(hit, _sections("1年目は 2 割、3年目から 1 割です"))


def test_軸が無くても結果の値が出ていれば既出():
    """`kokuho.cliff_by_members` の「6人で 92,570円」がこの形。"""
    hit = {"表": "t", "形": "逆転",
           "詳しく": {"どこ": "いちばん高い", "x": "被保険者数=6",
                    "値": 92570.0, "端では": 16520.0}}
    assert ss.is_covered(hit, _sections("6人で折れ（92,570円が頂点）"))
    assert not ss.is_covered(hit, _sections("5人までは比例します"))


def test_節が読めない回は既出と呼ばない():
    """**落とす向きに倒れないこと。**節が空なら判定できません。"""
    hit = {"表": "t", "形": "頭打ち", "詳しく": {"止まる x": "年収=1,000,000",
                                            "止まった値": 1.0}}
    assert not ss.is_covered(hit, None)
    assert not ss.is_covered(hit, {})


def test_novel_counts_は拾えた数と新しい数を両方返す():
    hits = [{"表": "t", "関数": "f", "見た値": "a", "形": "頭打ち",
             "詳しく": {"止まる x": "年収=1,000,000", "止まった値": 1.0}},
            {"表": "t", "関数": "g", "見た値": "b", "形": "頭打ち",
             "詳しく": {"止まる x": "年収=2,000,000", "止まった値": 2.0}}]
    total, novel = ss.novel_counts(hits, {"t": _sections("年収1,000,000円")})
    assert total == {"t": 2}
    assert novel == {"t": 1}


def test_実物で_ideco_は既定値の無い引数を埋めてから掃引される():
    """**この検査は 2026-08-19 07:5x に書き換えました。消していません。**

    元は `total["ideco"] == 3` / `novel["ideco"] == 0` で、
    「前の回が手で確かめた3件は全部既出」を固定していました。**その3件は、
    掃引が `ideco` の関数の大半を呼べていなかったときの数**です ——
    `_enum_axis` が候補を「その引数だけ」で呼び、`_sweepable_params` が
    既定値の無い引数で降りていたので、**引数の多い関数が丸ごと消えていました。**

    埋めるようにしたら **3 → 21件**になり、うち **18件は節が言っていません。**
    **「既出0件」は表が尽きた証拠ではなく、表がほとんど見えていなかった証拠**でした。

    だから固定し直すのは件数ではなく**向き**です:

    - 候補は、前に見えていた3件より**確かに多い**（呼べるようになった）
    - `novel_counts` は**全部を新しいとは言わない**（既出の判定は生きている）
    """
    import sys
    sys.path.insert(0, "scripts")
    import topic_forge as tf

    all_sections, _, _ = tf.survey()
    total, novel = ss.novel_counts(sweep_once(["ideco"]), all_sections)
    assert total["ideco"] > 3, total
    assert 0 < novel["ideco"] < total["ideco"], (total, novel)


def test_実物で_新しい候補が全部は消えていない():
    """**落としすぎの検出。**全部0になったら、この道具は候補を出しません。"""
    import sys
    sys.path.insert(0, "scripts")
    import topic_forge as tf

    all_sections, _, _ = tf.survey()
    total, novel = ss.novel_counts(sweep_once(), all_sections)
    assert sum(novel.values()) > 0, novel
    assert sum(novel.values()) < sum(total.values()), (total, novel)


# --- 片効き（2026-08-17 22:4x に足した）-------------------------------------
#
# **3回続けて申し送りに載っていた穴です。** ここまでの4つの形は
# **1本の列の中の値の並び**しか見ておらず、21:3x の回の5節は1つも掃引から
# 出ていませんでした。その回の主題は「調整支給率が式の片方の項にしか掛からない」＝
# **どの行にも数として現れない、欄どうしの対比**です。

def test_片効き_は動く欄と動かない欄の対比を出す():
    def fn(rate: float = 0.5):
        # `part_a` は rate で動くが、`part_b` は定額（＝片方の項にしか掛からない）
        return {"part_a": 100_000 * rate, "part_b": 5_000}

    hits = ss.sweep_function(fn, name="t")
    one = [h for h in hits if h["形"] == "片効き"]
    assert len(one) == 1, hits
    assert one[0]["詳しく"]["動く"] == ["part_a"]
    assert one[0]["詳しく"]["動かない"] == ["part_b"]


def test_片効き_は全部動くときには出ない():
    def fn(rate: float = 0.5):
        return {"a": 100_000 * rate, "b": 200_000 * rate}

    assert not [h for h in ss.sweep_function(fn, name="t") if h["形"] == "片効き"]


def test_片効き_は全部止まっているときには出ない():
    """**対比が無ければ出さないこと。** 全部不変は「片効き」ではありません。"""
    def fn(rate: float = 0.5):
        return {"a": 5_000, "b": 3_000}

    assert not [h for h in ss.sweep_function(fn, name="t") if h["形"] == "片効き"]


def test_片効き_は入力の再掲を動かない側に数えない():
    """**入力がそのまま返る欄は、動かなくて当たり前**（`_is_echo` と同じ理由）。

    ここを数えると、引数を1つ返しているだけの表が全部「片効き」になります。
    """
    def fn(rate: float = 0.5, months: int = 12):
        return {"amount": 100_000 * rate, "months": months}   # months は再掲

    hits = [h for h in ss.sweep_function(fn, name="t") if h["形"] == "片効き"]
    assert hits == [], hits


def test_片効き_は不変を消さない():
    """**2つは別の主張です。** 「B は動かない」と「x は A だけを動かす」。"""
    def fn(rate: float = 0.5):
        return {"part_a": 100_000 * rate, "part_b": 5_000}

    shapes = {h["形"] for h in ss.sweep_function(fn, name="t")}
    assert "片効き" in shapes and "不変" in shapes


def test_片効き_が実物の表から出る():
    """**実データでの回帰。** 手で作った例だけだと、実装が変わったとき黙ります。"""
    hits = [h for h in sweep_once() if h["形"] == "片効き"]
    assert hits, "実物の表から1件も出ていません"
    for h in hits:
        assert h["詳しく"]["動く"] and h["詳しく"]["動かない"]
        assert ss.line_of(dict(h, 表="x"))          # 印字できること


def test_片効き_も既出の判定にかかる():
    """**判定できないものを「新しい」に数えないこと**（2026-08-17 22:5x に踏んだ）。

    `片効き` は `x の点` を持たないので、`_hit_outcome` に欄を足すまで
    `is_covered` は**構造上いつも False**でした。`status.py` は `novel_counts` で
    (B) の同点を破るので、**新しい形を足した表だけが、中身と無関係に上位へ**上がります。
    """
    hit = {"表": "x", "関数": "f", "動かした引数": "a", "見た値": "b", "形": "片効き",
           "詳しく": {"動く": ["A"], "動かない": ["B"], "動かない値": 5000},
           "x の幅": (1, 9)}
    assert ss._hit_outcome(hit) == 5000
    assert ss.is_covered(hit, {"s": "均等割は 5,000円 のまま動きません"}) is True
    assert ss.is_covered(hit, {"s": "ここには何の数字もありません"}) is False


def test_実物の片効きが全部新しいと出ていたら疑うこと():
    """**全部が「新しい」なら、判定が効いていない可能性のほうが高い。**

    これは値そのものを固定する検査ではありません（節は毎回ふえます）。
    **「1件も既出にならない」＝ 判定が構造上素通りしている**ことだけを見ます。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import topic_forge

    hits = [h for h in sweep_once() if h["形"] == "片効き"]
    if not hits:
        return
    alls, _free, _known = topic_forge.survey()
    # 判定が**動いている**こと（例外なく False を返す実装ではない）を、
    # 節に値を混ぜた写しで確かめる。
    #
    # **`hits[0]` 決め打ちにしないこと**（2026-08-19 09:0x に直した）。
    # ここは長らく先頭の1件だけを見ていて、`_scalars` が組を読むようになった回に
    # 先頭が `fuka.payback_age` の `[0]`（＝**67**）へ入れ替わり、赤になりました。
    # **判定が壊れたのではありません** —— `_point_printed` は**1〜2桁の整数を
    # わざと見ません**（2026-08-18 20:1x。「92歳7か月」のような作り話が
    # 一致してしまうので落とした側）。**先頭が何になるかは掃引の都合**なので、
    # **「照合できる値を持つ候補が1件でもあるか」**を見る形に変えました。
    judged = [h for h in hits
              if ss.is_covered(dict(h), {"s": f'{h["詳しく"]["動かない値"]:,.0f}'})]
    assert judged, (
        "節に値をそのまま書いても1件も既出にならない ＝ is_covered が素通りしている"
        f"（片効き {len(hits)}件）")


# ---------------------------------------------------------------------------
# **一覧と、数えた数が、別のものを見せていた**（2026-08-17 23:5x に、誤読してから足した）
#
# `--calc <表>` は候補を全部並べるのに、**どれが既出かを1文字も出していなかった。**
# その回は上から6件を読み、`topics.yaml` に対応するテーマがあることを確かめて
# 「新しいと数えた6件が6件とも既出だ」と書いた。**計器はそう言っていない**
# （追跡すると `is_covered` は `True`）。**印が出ていれば起きなかった。**
# ---------------------------------------------------------------------------

def _hit(calc="t", fn="f", shape="不変", **detail):
    return {"表": calc, "関数": fn, "形": shape, "見た値": "v",
            "動かした引数": "x", "x の幅": (1, 9), "詳しく": detail}


def test_既出の候補に印が出る(monkeypatch):
    from src import section_sweep as ss

    a, b = _hit(fn="fa", 値=111), _hit(fn="fb", 値=222)
    monkeypatch.setattr(ss, "_covered_map",
                        lambda hits: {id(a): True, id(b): False})
    out = "\n".join(ss.report_lines([a, b]))
    assert "[既]" in out, "既出の印が出ていません"
    assert "111" in out and "222" in out
    # **印は既出の側にだけ付くこと**（逆に付いたら、選ぶ側が正反対に動きます）
    for line in out.splitlines():
        if "222" in line:
            assert not line.startswith("[既]"), "新しい側に印が付いています"
        if "111" in line:
            assert line.startswith("[既]"), "既出の側に印がありません"


def test_見出しに新しい件数が出る(monkeypatch):
    """**一覧の件数だけを読むと、この回のように誤読します。**"""
    from src import section_sweep as ss

    a, b = _hit(fn="fa", 値=111), _hit(fn="fb", 値=222)
    monkeypatch.setattr(ss, "_covered_map",
                        lambda hits: {id(a): True, id(b): False})
    out = "\n".join(ss.report_lines([a, b]))
    assert "まだ節が言っていない 1件" in out
    assert "新しい 1件" in out, "表ごとの行にも出ること"


def test_既出が読めない回は印を出さない(monkeypatch):
    """**読めないことを「新しい」と読ませないこと。** 印ごと消すのが正しい。"""
    from src import section_sweep as ss

    monkeypatch.setattr(ss, "_covered_map", lambda hits: {})
    out = "\n".join(ss.report_lines([_hit(値=111)]))
    assert "[既]" not in out
    assert "まだ節が言っていない" not in out


# ---------------------------------------------------------------------------
# **表の定数を「新しい」に数えていた**（2026-08-18。申し送りに名指しで残っていた）
#
# `_is_echo` が落とすのは**入力の再掲**だけで、**表の中の定数**は素通りでした。
# 実測: `kyugyo` の「新しい5件」のうち **4件**が `暦日の差は3のまま` の類。
# ---------------------------------------------------------------------------

def test_どの引数でも動かない欄は定数として落とす():
    """**横に並べて初めて「定数だ」と言えます。**1本の列では区別がつきません。"""
    from src import section_sweep as ss

    def f(a: float = 100.0, b: float = 200.0) -> dict:
        return {"合計": min(a, 108.0) + b, "軽減の割合": 20.0}

    hits = ss.sweep_function(f, name="f")
    frozen = [h for h in hits if "軽減の割合" in str(h["見た値"])]
    assert frozen == [], f"表の定数が候補に残っています: {frozen}"
    # **合計のほうは残ること**（落とす向きの誤りは黙って効きます）
    assert any("合計" in str(h["見た値"]) for h in hits), "動く欄まで落ちています"


def test_引数が1つの関数には定数の判定を掛けない():
    """区別がつかない場面では落とさない ——「不変」を丸ごと消してしまう。"""
    from src import section_sweep as ss

    def f(a: float = 100.0) -> dict:
        return {"動く": min(a, 108.0) * 2, "止まっている": 3.5}

    assert ss.table_constants([("a", [1, 2, 3, 4], [{"x": 1}] * 4)]) == set()
    hits = ss.sweep_function(f, name="f")
    assert any(h["形"] == "不変" for h in hits), "1引数の不変まで消えています"


def test_片効きの動かない側からも定数を外す():
    """定数どうしの対比は「片効き」になりません（`kyugyo` の4件がこれ）。"""
    from src import section_sweep as ss

    def f(a: float = 100.0, b: float = 200.0) -> dict:
        return {"動く": a + b, "定数": 92.0}

    # **直す前は出ていたこと**を、同じ材料で押さえておく（`consts` を渡さない道）。
    xs = list(range(4))
    rows = [{"動く": 100.0 + 40 * i, "定数": 92.0} for i in range(4)]
    assert ss._one_sided(xs, rows, ["動く", "定数"], [100.0, 200.0], "f", "a")
    assert ss._one_sided(xs, rows, ["動く", "定数"], [100.0, 200.0], "f", "a",
                         {"定数"}) == []

    hits = ss.sweep_function(f, name="f")
    assert [h for h in hits if h["形"] == "片効き"] == [], \
        "定数しか動かない側に無いのに「片効き」が出ています"


def test_table_constants_は動いた欄を定数と呼ばない():
    from src import section_sweep as ss

    swept = [("a", [1, 2, 3, 4], [{"p": 1.0, "q": 5.0} for _ in range(4)]),
             ("b", [1, 2, 3, 4], [{"p": float(i), "q": 5.0} for i in range(4)])]
    assert ss.table_constants(swept) == {"q"}


# ---------------------------------------------------------------------------
# **人が読む唯一の経路でだけ、印が出ていなかった**（2026-08-18）
#
# `_covered_map` は `topic_forge`（`scripts/` の中）を `sys.path` 無しで import
# しており、`python -m src.section_sweep` からは必ず `{}` に落ちていました。
# **入れた回は `status.py` で見て「出た」と書いています**（別の経路）。
# ---------------------------------------------------------------------------

def test_covered_mapはCLIの呼び方でも節を読める():
    """**`sys.path` に `scripts/` が無い状態**で呼んで、空でないこと。"""
    import subprocess
    import sys as _sys

    code = ("import sys; from src import section_sweep as ss;"
            "h={'表':'kokuho','関数':'f','形':'不変','見た値':'v',"
            "'動かした引数':'x','x の幅':(1,9),'詳しく':{'値':1.0}};"
            "print(len(ss._covered_map([h])))")
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([_sys.executable, "-c", code],
                       capture_output=True, text=True, cwd=str(root))
    assert r.returncode == 0, r.stderr[-800:]
    assert r.stdout.strip() == "1", \
        f"CLI の経路で節が読めていません（印が1つも出ません）: {r.stdout!r}"


def test_読めなかったときは黙らずに言う(monkeypatch):
    """**印の無い一覧は「全部が新しい」に見えます。**読めなかったと言うこと。"""
    from src import section_sweep as ss

    monkeypatch.setattr(ss, "_covered_map", lambda hits: {})
    out = "\n".join(ss.report_lines([_hit(値=111)]))
    assert "既出の印は出せません" in out


def test_1本に絞ったときは全部出す():
    """`--calc <表> で全文` の行き先が、6件で切れる自分自身でした。"""
    from src import section_sweep as ss

    hits = [_hit(fn=f"f{i}", 値=float(i)) for i in range(9)]
    out = "\n".join(ss.report_lines(hits, top=10_000))
    assert "ほか" not in out, "1本だけなのに省略されています"
    for i in range(9):
        assert f".f{i}" in out
    # **2本以上あるときは、これまでどおり表ごとに6件で切ること**
    many = hits + [_hit(calc="u", fn="g", 値=1.0)]
    assert "ほか 3件" in "\n".join(ss.report_lines(many, top=10_000))


# ---------------------------------------------------------------------------
# **既出判定が、表の節では構造上いちども当たらなかった**（2026-08-18 に実測）
#
# 「新しい」と数えられた17件を実物に当たると、**9件は値が本文に印字されていた**。
# 原因は3つ。どれも「別の事実」ではなく**書き方の違い**です。
# ---------------------------------------------------------------------------

def test_軸が見出し行にある表では断定しない():
    """節の多くは表で、**軸は見出し行・値は行データ**。同じ行に来ません。

    ここは `False`（＝まだ誰も言っていない）を返しており、`is_covered` は
    `False` を見た時点で打ち切るので、**結果の値を見る控えの道に入れません。**
    """
    from src import section_sweep as ss

    lines = ["  段  月給       標準報酬月額   保険料の増(年)",
             "  3   104,000円   101,000円      6,588円"]
    assert ss._point_printed("月給=101,000", lines) is None, \
        "軸が本文にあるのに値がその行に無いのを「新しい」と断定しています"
    # **同じ行に並んでいれば、これまでどおり True**
    assert ss._point_printed("月給=101,000", ["月給 101,000円 のとき"]) is True
    # **払った代金**: 軸のある道は、もう `False`（新しい）を返しません。
    # 値が本文のどこにも無くても `None` で、新しさは**結果の値のほう**で決まります
    # （`is_covered`）。**落とす向きの誤りは黙って効く**ので、ここに書いておきます ——
    # x が本物に新しいのに、結果の値がたまたま印字されている候補は、既出に倒れます。
    assert ss._point_printed("月給=999,999", ["月給 101,000円 のとき"]) is None
    # **軸そのものが本文に無ければ、これまでどおり**（大きい数は本文ぜんぶで見る）
    assert ss._point_printed("賞与=999,999", ["月給 101,000円 のとき"]) is False


def test_符号のちがいを別の事実として数えない():
    """`跳ぶ幅 -800,000` は、節では「浮く額 800,000円」と書かれます。"""
    from src import section_sweep as ss

    assert ss._found_in(-800000.0, ["1年のばすと浮く額 800,000円"])
    assert ss._found_in(800000.0, ["差は -800,000円"])
    assert not ss._found_in(-800000.0, ["浮く額 12,345円"])


def test_率は百分率で書かれていても同じ量():
    """`所得税率=0.33` と本文の `33%へ` は、別の事実ではありません。"""
    from src import section_sweep as ss

    assert ss._found_in(0.33, ["課税所得 9,000,000円で 33%へ"])
    assert ss._written_forms(0.33) == [0.33, -0.33, 33.0, -33.0]
    # **1 以上の数は百分率に開かないこと**（金額が無関係な行に当たります）
    assert 660000.0 not in ss._written_forms(6600.0)


def test_印の無い候補を先に出す():
    """表ごとに6件で切るので、並べ替えないと**新しいが省略の中に隠れます。**"""
    from src import section_sweep as ss

    old = [_hit(fn=f"o{i}", 値=float(i)) for i in range(6)]
    new = _hit(fn="new1", 値=99.0)
    cov = {id(h): True for h in old}
    cov[id(new)] = False
    ss_covered = old + [new]
    import pytest as _pytest
    monkey = _pytest.MonkeyPatch()
    monkey.setattr(ss, "_covered_map", lambda hits: cov)
    try:
        out = "\n".join(ss.report_lines(ss_covered + [_hit(calc="u", fn="g", 値=1.0)]))
    finally:
        monkey.undo()
    assert ".new1" in out, "新しい候補が `…ほか N件` に隠れています"


# ---- 帯（2026-08-18 に足した形）----------------------------------------

def test_途中だけ違って両端が同じ列は帯():
    """`kokuho.keigen_cliff` の `age` の実物の並び（介護分が乗る帯）。"""
    xs = [22, 30, 38, 46, 54, 62, 70, 78, 86]
    ys = [13200, 13200, 13200, 16520, 16520, 16520, 13200, 13200, 13200]
    shape, d = ss._classify(xs, ys)
    assert shape == "帯", (shape, d)
    assert (d["帯の入口"], d["帯の出口"]) == (46, 62)
    assert (d["帯の中"], d["帯の外"], d["差"]) == (16520, 13200, 3320)


def test_帯は頭打ちより先に決まる():
    """**この順番が本体です。**帯は頭打ちの条件（後ろが平ら・動く段が2つ）も満たします。

    2026-08-18 まで `帯` が無かったので、上の並びは **頭打ち**として出ていました ——
    「70歳から上は 13,200円 で止まる」。**右端だけ見れば正しいが、左端も同じ値**です。
    """
    xs = [22, 30, 38, 46, 54, 62, 70, 78, 86]
    ys = [13200, 13200, 13200, 16520, 16520, 16520, 13200, 13200, 13200]
    tail = ys[-3:]
    assert max(tail) == min(tail), "頭打ちの条件（後ろが平ら）を満たしていない前提が崩れた"
    assert ss._classify(xs, ys)[0] == "帯"


def test_両端の高さが違えば帯にしない():
    xs = list(range(9))
    ys = [10, 10, 10, 20, 20, 20, 15, 15, 15]
    assert ss._classify(xs, ys)[0] != "帯"


def test_段が2つだけなら帯にしない():
    """上がって戻らないものは帯ではありません。

    **この並びは、いまはどの形にもなりません**（段が1つだけなので
    頭打ちの「動く段が2つ以上」にも当たらない）。ここで見たいのは
    **帯と呼ばないこと**だけなので、`None` も答えとして通します。
    """
    xs = list(range(9))
    ys = [10, 10, 10, 10, 20, 20, 20, 20, 20]
    got = ss._classify(xs, ys)
    assert got is None or got[0] != "帯", got


def test_帯の差が全体の1パーセント未満なら帯にしない():
    """丸めの屑で帯を作らないこと（`逆転` と同じしきい値）。"""
    xs = list(range(9))
    ys = [1_000_000] * 3 + [1_000_005] * 3 + [1_000_000] * 3
    got = ss._classify(xs, ys)
    assert got is None or got[0] != "帯", got


def test_帯が実物の表から出る():
    hits = [h for h in ss.sweep_calc("kokuho") if h["形"] == "帯"]
    assert hits, "kokuho から帯が1件も出ていない"


def test_帯も既出の判定にかかる():
    """**形を足したら `_hit_points` と `_hit_outcome` にも足すこと。**

    2026-08-18 に `帯` を足した直後、`kokuho.cliff_by_age` の4件が全部
    「新しい」と出ました。**その表は、その回に書いた節そのもの**です。
    """
    hit = {"表": "kokuho", "関数": "cliff_by_age", "見た値": "跳ぶ額", "形": "帯",
           "動かした引数": "年齢", "x の幅": (22, 86),
           "詳しく": {"帯の入口": 40, "帯の出口": 64,
                    "帯の中": 16520, "帯の外": 13200, "差": 3320}}
    body = {"節": "40歳から64歳までだけ 16,520円、その前後は 13,200円"}
    assert ss.is_covered(hit, body) is True
    assert ss.is_covered(hit, {"節": "年齢では何も変わりません"}) is False


def test_どの形も既出の判定に材料を渡している():
    """**これが、この穴の一般形です。**

    `片効き` を足した回（2026-08-17 22:5x）も、`帯` を足した回（2026-08-18）も、
    **`_hit_points` / `_hit_outcome` に欄を足すのを忘れました。**
    忘れると `is_covered` は構造上いつも False を返し、
    **新しい形を足した表だけが、中身と無関係に「新しい」件数で上位へ上がります。**
    個別に1件ずつ足すのをやめ、**全部の形について**見ます。
    """
    seen: dict[str, int] = {}
    for hit in sweep_once():
        shape = hit["形"]
        seen[shape] = seen.get(shape, 0) + 1
        assert ss._hit_points(hit) or ss._hit_outcome(hit) is not None, \
            f"形 {shape} が is_covered に何も渡していない: {hit['詳しく']}"
    # **形が実物から出ていなければ、上の for は素通りします。**
    # `不変` だけは x を持たない設計（`_hit_points` が空を返す）なので除きます
    for shape in ss.SHAPES:
        assert shape in seen, f"形 {shape} が実物から1件も出ていない（上の検査が素通り）"


def test_status_の内訳が形を1つも落としていない():
    """**形の一覧を写した3か所目**（2026-08-18）。

    `scripts/status.py` の (C) の行は `("崖", "逆転", "頭打ち", "不変")` と
    写してあり、`片効き` と `帯` が足されたあとも4つのままでした。
    **内訳の合計が候補の件数に届かない**（実測 86 対 98）のに、
    **どこにも赤が出ません。** 合計が一致することで見ます。
    """
    import re
    import runpy
    import io
    import contextlib

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import status as st  # noqa: E402

    hits = sweep_once()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        st._print_sweep_hint(hits)
    line = buf.getvalue()
    m = re.search(r"候補 \*\*(\d+)件\*\*.*?（(.+?)）", line, re.S)
    assert m, line
    total = int(m.group(1))
    parts = sum(int(re.search(r"(\d+)$", p.strip()).group(1))
                for p in m.group(2).split("・"))
    assert parts == total, f"内訳の合計 {parts} が候補 {total}件 と合わない: {line}"


# ---- 同点の頂上は、軸によって意味が逆になる（2026-08-18）-----------------

def test_連続量の軸では同点の頂上を名指しさせない():
    """引数を刻んだ掃引の同点は、**目盛りが粗いだけ**かもしれません。

    `nenkin.worst_gap` の「189万で最大(32か月)」は、1万きざみに直すと
    276万でも 32 になりました。**細かくすると頂上そのものが動く**ので、
    その x を名指しした節は追試で再現しません。
    """
    shape, d = ss._classify(list(range(7)), [10, 12, 20, 19, 20, 13, 11])
    assert shape == "逆転"
    assert d["並ぶ点"] > 1
    assert d["数え上げ"] is False
    line = ss.line_of({"表": "t", "関数": "f", "見た値": "v", "形": shape,
                       "詳しく": d, "動かした引数": "x", "x の幅": (0, 6)})
    assert "書けません" in line


def test_数え上げの軸では同点でも節は書ける():
    """表の行を歩くときの同点は、**それが全部**です。

    行の集合は完全なので細かくする余地がありません。段階表では同値が
    並ぶのが正常で、前の回の印は `shitsugyo.double_boundary`
    （**既に節になっている本物**）にも「節は書けません」と鳴っていました。
    壊れるのは「1つだけ」と言うほうなので、**全部書けと言わせます。**
    """
    shape, d = ss._classify(list(range(7)), [10, 12, 20, 19, 20, 13, 11],
                            enumerated=True)
    assert shape == "逆転"
    assert d["並ぶ点"] > 1
    assert d["数え上げ"] is True
    line = ss.line_of({"表": "t", "関数": "f", "見た値": "v", "形": shape,
                       "詳しく": d, "動かした引数": "（表の行）", "x の幅": (0, 6)})
    assert "書けません" not in line
    assert "全部書くこと" in line


def test_行を歩く掃引は数え上げとして判定される():
    """`sweep_rows` から来た候補は、必ず `数え上げ` 側であること。"""
    def 表():
        return [{"帯": f"{i}段", "額": y}
                for i, y in enumerate([10, 12, 20, 19, 20, 13, 11])]

    hits = [h for h in ss.sweep_rows(表, name="表") if h["形"] == "逆転"]
    assert hits, "逆転が拾えていない"
    assert all(h["詳しく"]["数え上げ"] is True for h in hits)


# ---- 行の見出しは、行を一意に指すこと（2026-08-18）-----------------------

def test_見出しが1欄で足りないときは欄を足す():
    """**行が4つ組で決まる表で、見出しが1欄しか使われていませんでした。**

    `shitsugyo.double_boundary` は 12行のうち4行が `age_before='30歳未満'` で、
    印字は `（表の行）が 30歳未満→45歳以上60歳未満 で -552,300 跳ぶ` ——
    実際は行8→行9で、**勤続のほうも動いています。**
    読みにくいのではなく、**節にすると事実と違うことを言います。**
    """
    from src.calc import shitsugyo
    rows = shitsugyo.double_boundary()
    keys = ss._label_keys(rows)
    labels = [ss._join_label(r, keys) for r in rows]
    assert len(set(labels)) == len(rows), f"見出しが行を指していない: {labels}"


def test_見出しは一意になった時点で止める():
    """**欄は少ないほうが読めます。**一意なら1欄で止めること。"""
    rows = [{"帯": f"{i}段", "別名": "同じ", "額": i} for i in range(5)]
    assert ss._label_keys(rows) == ["帯"]


def test_x_のキーは名前で拾う_手書きの並びにしない():
    """**`並ぶ x` が、行番号のまま出ていました**（2026-08-18）。

    見出しに直す欄は `("止まる x", "x", "x の手前", "x の先")` と手書きで、
    前の回が `並ぶ x` を足したときに、この並びのほうを書き忘れています
    （名指した x は `30歳未満`、同点のほうは `7・8`）。
    **手書きである限り、次に x のキーを足す回も同じことをします。**
    いまは `x` を名前に含む欄を全部拾うので、**この検査は名前の規約のほうを見ます。**
    """
    def 表():
        return [{"帯": f"{i}段", "額": y}
                for i, y in enumerate([10, 12, 20, 19, 20, 13, 11])]

    hit = next(h for h in ss.sweep_rows(表, name="表") if h["形"] == "逆転")
    for k, v in hit["詳しく"].items():
        if "x" not in k:
            continue
        vals = v if isinstance(v, list) else [v]
        for one in vals:
            assert isinstance(one, str) and one.endswith("段"), \
                f"{k} が見出しに直っていない: {one!r}"


# ---- 繋いだ見出しの既出判定（2026-08-18）--------------------------------

def test_繋いだ見出しは部品ごとに照合する():
    """`30歳未満・1年未満` は、まるごとでは本文に出ません。

    節はその組を散文で書くので、**繋いだ形の文字列照合は必ず外れます。**
    直前に `_label_keys` を入れた時点で、`shitsugyo` の6件が6件とも
    「新しい」に化けました（節はどれも前からあります）。
    """
    body = ["30歳未満で勤続1年未満なら、給付は 992,400円 で止まります"]
    assert ss._point_printed("30歳未満・1年未満", body) is True


def test_繋いだ見出しは1つも出ていなければ新しい():
    body = ["60歳以上の話しか書いていない節"]
    assert ss._point_printed("30歳未満・1年未満", body) is False


def test_繋いだ見出しは片方だけなら断定しない():
    """**片方だけを `False` にしないこと。**

    `is_covered` は `False` を見た時点で打ち切るので、
    **結果の値を見る控えの道に一度も入れなくなります**（8/18 に踏んだ穴と同じ形）。
    """
    body = ["30歳未満の人は、ここでは扱いません"]
    assert ss._point_printed("30歳未満・1年未満", body) is None


def test_実物の段階表が既出のまま残ること():
    """**見出しを一意にした直しが、既出の判定を壊していないこと。**

    `shitsugyo` の候補は 6件とも、いまの節がもう言っています。
    ここが「新しい」に化けると、(B) の同点破りが
    **見出しを長くした表だけ**を上位へ上げます。
    """
    from src.calc import shitsugyo
    hits = [h for h in sweep_once() if h.get("表") == "shitsugyo"]
    assert hits, "shitsugyo の候補が拾えていない"
    covered = ss._covered_map(hits)
    assert covered, "節が読めていない（読めない回はこの検査が空を通してしまう）"
    bad = [ss.line_of(h) for h in hits if not covered.get(id(h))]
    assert not bad, bad


def test_詳しくの欄は全部_x_か_y_のどちらかに宣言されている():
    """**形を足した回に、新しい欄が x か y かを宣言させる検査**（2026-08-18）。

    宣言しないと、行を歩く掃引で **その欄だけ行番号のまま印字されます** ——
    実際 `帯` の `帯の入口` / `帯の出口` がそうでした。
    「名前に `x` を含む欄」という規約でも拾えません（`帯` に `x` の字が無い）。
    だから `X_KEYS` と `Y_KEYS` の**和が、実物に出る欄を全部覆う**ことで見ます。
    """
    known = set(ss.X_KEYS) | set(ss.Y_KEYS)
    unknown: dict[str, set[str]] = {}
    for hit in sweep_once():
        for k in (hit.get("詳しく") or {}):
            if k not in known:
                unknown.setdefault(hit["形"], set()).add(k)
    assert not unknown, (
        f"x とも y とも宣言されていない欄があります: {unknown}。"
        " x 軸の値なら X_KEYS へ（行を歩く掃引で見出しに直します）、"
        " 結果の値や註なら Y_KEYS へ足すこと。")


def test_帯の入口と出口も見出しに直る():
    """**`帯` は `x` の字を持たないので、名前の規約では拾えません。**"""
    def 表():
        return [{"帯": f"{i}段", "額": y}
                for i, y in enumerate([100, 100, 100, 250, 250, 100, 100, 100])]

    hit = next(h for h in ss.sweep_rows(表, name="表") if h["形"] == "帯")
    for k in ("帯の入口", "帯の出口"):
        assert isinstance(hit["詳しく"][k], str) and hit["詳しく"][k].endswith("段"), \
            f"{k} が行番号のまま: {hit['詳しく'][k]!r}"


def test_名指しの点は共有の並びから引く():
    """`_hit_points` と見出し直しが、**同じ並び**を読んでいること。

    別々の手書きの並びだったころ、**片方だけに欄を足す**のが4回起きています。
    """
    assert set(ss.NAMING_X_KEYS) <= set(ss.X_KEYS)
    assert "並ぶ x" not in ss.NAMING_X_KEYS


# ---- 数え上げの軸を、どの入れ物から採るか（2026-08-18） ------------------

def test_名前と値を1行にまとめた並びからも軸を採る():
    """制度の表は `(名前, 率, 上限)` の並びで持つのが普通です。

    要素が全部 `str` の入れ物しか見ていなかったので、**その形の表は
    軸の候補にすら入っていませんでした**（`kyoiku.PROGRAMS` の6つ）。
    """
    assert ss._names_of(["あ", "い"]) == ["あ", "い"]
    assert ss._names_of([("一般", 0.2, 100), ("特定", 0.4, 200)]) == ["一般", "特定"]
    assert ss._names_of([(0.2, "一般"), (0.4, "特定")]) is None
    assert ss._names_of([("一般", 1), ("一般", 2)]) is None, "同じ名前が2度出る並びは軸ではない"
    assert ss._names_of([]) is None


def test_数え上げの軸はいちばん広い入れ物から採る():
    """**部分集合が先に通ると、半分だけ振った結果を候補として出します。**

    `kyoiku` は `PROGRAMS`（6つ）と `FLOOR_PROGRAMS`（下限のある3つ）を
    両方持っていて、直す前の `cap_of` は **6.4倍を 2.5倍**と報告していました。
    取りこぼしではなく**誤答**なので、検査に固定します。
    """
    import inspect

    from src.calc import kyoiku

    empty = inspect.Parameter.empty
    axis = ss._enum_axis(kyoiku.cap_of, "name", empty)
    assert len(axis) == len(kyoiku.PROGRAMS), f"6つ中 {len(axis)} つしか振っていない: {axis}"
    assert axis[-1] == kyoiku.PROGRAMS[-1][0]


def test_広い入れ物で落ちる関数は狭いほうへ降りる():
    """**広ければよい、ではありません。**

    `min_cost_paid` は下限のある3つでしか定義されていない（他は `ValueError`）。
    「全部が例外なく数字を返す」を通った入れ物どうしの比較なので、
    6つの並びはそもそも候補に残りません。
    """
    import inspect

    from src.calc import kyoiku

    axis = ss._enum_axis(kyoiku.min_cost_paid, "name", inspect.Parameter.empty)
    assert axis == list(kyoiku.FLOOR_PROGRAMS)


def test_分類が返す形は全部_SHAPES_に載っている():
    """**形を足して `SHAPES` に写し忘れる**のを、実物を回さずに捕まえる。

    2026-08-18 に `倍率` を足した回が、まさにこれを踏みました ——
    分類は返るのに一覧に無く、`--shape 倍率` が「そんな形は無い」と弾きます。
    既にある `test_どの形も既出の判定に材料を渡している` は逆向き
    （`SHAPES` の形が実物から出るか）なので、**写し忘れは捕まえません。**
    """
    import re

    src = Path(ss.__file__).read_text(encoding="utf-8")
    body = src[src.index("def _classify("):src.index("def _is_echo(")]
    returned = set(re.findall(r'return "([^"]+)",', body))
    assert returned, "分類の本体が読めていません（切り出しの目印が動いた）"
    assert returned <= set(ss.SHAPES), \
        f"分類は返すのに SHAPES に無い形があります: {sorted(returned - set(ss.SHAPES))}"


# ---- 倍率の既出は、比が書かれているかで見る（2026-08-18） ----------------

def _ratio_hit(ratio: float, seq: list[float]) -> dict:
    return {"形": "倍率", "表": "t", "関数": "f", "動かした引数": "part",
            "見た値": "返り値", "x の幅": ["低", "高"],
            "詳しく": {"いちばん低い": "低", "いちばん高い": "高",
                     "倍率": ratio, "値": 1.0, "並び": seq}}


def test_比は倍でも並びでも読む():
    hit = _ratio_hit(6.0, [1.0, 2.0, 6.0])
    assert ss._ratio_printed(hit, ["1㎡あたりは 6.0倍 になります"])
    assert ss._ratio_printed(hit, ["帯ごとの単価は 1:2:6"])
    assert not ss._ratio_printed(hit, ["200㎡までは6分の1に減ります"]), \
        "素の 6 で当たると、どの節にも書いてある数字で既出になります"
    assert not ss._ratio_printed(hit, ["いちばん高いのは 3.0倍"])


def test_倍率の既出は端の名前では決まらない():
    """**端の名前は、どの節にも普通に出てきます。**

    足した直後の実測は **11件が11件とも既出**でした（`要介護5` や `一般` が
    本文にあるだけ）。比そのものはどこにも書かれていないのに、です。
    """
    hit = _ratio_hit(7.2, [1.0, 3.3, 7.2])
    sections = {"s1": "要支援1から要介護5まで、区分ごとに限度額が決まっています"}
    hit["詳しく"]["いちばん低い"] = "要支援1"
    hit["詳しく"]["いちばん高い"] = "要介護5"
    assert ss.is_covered(hit, sections) is False
    assert ss.is_covered(hit, {"s1": "要支援1と要介護5では 7.2倍 ちがいます"}) is True


def test_比の並びは順番によらない():
    """向きが逆に出る候補があります（`menzei_limit` は 6:3:1）。"""
    hit = _ratio_hit(6.0, [6.0, 3.0, 1.0])
    assert ss._ratio_printed(hit, ["1:3:6 の順で効きます"])


# ---- 数字なのに読めなかった返り値（2026-08-19 09:0x）----
#
# 前の回の申し送りは「残る47件は `_enum_containers` が入れ物を見つけられて
# いない側だ」と書いていました。**開いたら違いました** —— 入れ物（`TIERS`
# `GYOSHU`）は見つかっていて、落ちていたのは**返り値を読む側**です。
# 47件のうち5件がこれで、さらに**7本は例外も出さずに欄0のまま**通っていました。

def test_Decimal_と_Fraction_を数として読む():
    """`src/calc/` は float の丸め落ちを直すたびに厳密な型へ移っています。

    **移した瞬間、その欄は掃引から消えていました。** 例外も警告も出ません。
    """
    assert ss._as_number(Decimal("0.0055")) == pytest.approx(0.0055)
    assert ss._as_number(Fraction(3, 4)) == pytest.approx(0.75)
    assert ss._scalars({"率": Decimal("0.0055"), "額": 100}) == {
        "率": pytest.approx(0.0055), "額": pytest.approx(100.0)}


def test_雇用保険の率は_Decimal_で返るが掃引から見える():
    """`koyouhoken.worker_rate` は `Decimal` を返すので**呼べない関数**に落ちていた。"""
    import src.calc.koyouhoken as m
    assert isinstance(m.worker_rate("一般の事業"), Decimal)
    assert ss.unreachable(m.worker_rate) == "", "Decimal を数として読めていない"


def test_組で返る関数は位置で欄を取る():
    """返りが組の関数は、**欄が1つも取れないので掃引に1件も出ません。**

    そして `_scalars()` は `{}` を返すだけなので、
    **「呼べなかった関数」の一覧にも載りません**（例外が出ないため）。
    どこにも記録の残らない側の落ち方でした。
    """
    assert ss._scalars((3, 5.5)) == {"[0]": 3.0, "[1]": 5.5}
    # 先頭が行の名前の組は、名前だけ落として残りを欄にする
    assert ss._scalars(("ウ", 280000, None, 80100)) == {
        "[1]": 280000.0, "[3]": 80100.0}


def test_ENUM_MAXより長い並びは組として読まない():
    """**それは「記録」ではなく「表そのもの」**です（行は `sweep_rows` が歩く）。

    数え上げの軸と同じ線を使います。1つの表に2度当てないため。
    """
    assert ss._scalars(tuple(range(ss.ENUM_MAX))) != {}
    assert ss._scalars(tuple(range(ss.ENUM_MAX + 1))) == {}


def test_行の並び_dict_の_list_は組として読まない():
    """`sweep_rows` が行として歩く側。ここで欄に潰すと二重に当たります。"""
    assert ss._scalars([{"a": 1}, {"a": 2}]) == {}


def test_高額療養費の区分表は名前で振れる():
    """`kogaku.tier` は `TIERS` を軸に振れるのに、**返りが組**なので消えていた。

    `gassan`（7節）の元になった表の片割れです。
    **いちばん深い表ほど、返り値が組になりやすい**という向きの穴でした。
    """
    import src.calc.kogaku as m
    assert ss.unreachable(m.tier) == "", "組を読めていない"
    assert ss._enum_axis(m.tier, "name", "ウ") == [t[0] for t in m.TIERS]


def test_可変長引数は_必ず埋める引数ではない():
    """`**kw` と `*args` は、**渡さなくても呼べます。**

    掃引の側は「既定値が無い引数」を「必ず埋めなければならない引数」と
    読んでいて、`inspect.signature` が `**kw` にも
    `Parameter.empty` を入れるので、**名前 `kw` を埋めようとして
    関数ごと落としていました。**

    2026-08-19 の申し送りは、残り42件を「数値の引数に文字列を入れて
    例外＝`PARAM_FILL` / `FILL_ONLY` に足せば戻る」と読んでいます。
    **`kw` はそこではありません** —— 語彙に足すと、
    **実在しない引数名が一覧に載ります。**
    """
    import src.calc.furusato as fu
    import src.calc.izoku as iz

    # どちらも、`**kw` を除けば埋められる引数しか残りません
    assert ss.unreachable(fu.bracket_income) == "", "**kw を必須引数と読んでいる"
    assert ss.unreachable(iz.cliff_grid) == "", "**kw を必須引数と読んでいる"


def test_データ組を引数に取る関数も掃引できる():
    """`furusato.limit(p: Person)` は、**表の本体3本がまるごと掃引の外**でした。

    埋められない引数の名前は `p` です。**語彙に `p` を足しても直りません** ——
    要るのは代表値ではなく、`Person` を**組み立てること**だからです。
    欄（`income` / `social_rate` …）は1つずつ寄せられるので、
    **組を開いて欄を引数にすれば、そのまま振れます。**
    """
    import src.calc.furusato as fu

    view = ss.dataclass_view(fu.limit)
    assert view is not None, "Person を開けていない"
    assert ss.unreachable(view) == "", "開いた後も呼べないと言っている"
    # 開いた側は、欄をそのまま引数に取る
    assert view(income=5_000_000, social_rate=0.15) == fu.limit(
        fu.Person(income=5_000_000, social_rate=0.15))
    # そして掃引に出てくる（欄が無ければ候補は1件も出ません）
    hits = ss.sweep_function(view, name="limit")
    assert hits, "組を開いても候補が1件も出ていない"


def test_場合分けの入れ物が別の表にあっても見つける():
    """`iryohi.low_income_grid(tier_name)` の区分名は、**`iryohi` にありません。**

    `iryohi` は高額療養費の区分表を持たず、`kogaku.TIERS` を読みます
    （`from . import kogaku`）。ところが `_enum_containers` は
    **`fn.__module__` の中だけ**を見ていたので、`iryohi` 側からは
    「入れ物が1つも無い」に見え、`tier_name` を取る関数が2本とも
    掃引から落ちていました。

    **語彙を手で並べる直しは採りません。** 入れ物のありかは
    「その表が import している別の表」で、それは import の側から引けます。
    """
    import src.calc.iryohi as ir

    names = {c for c, _ in ss._enum_containers(ir.low_income_grid)}
    assert "TIERS" in names, "import している表の入れ物を見ていない"
    assert ss.unreachable(ir.low_income_grid) == "", "まだ呼べないと言っている"

    # **同じ表の `deduction_start_cost` は、これでも通りません。**
    # 入れ物は見つかりますが、区分エ・オでは `None` を返します
    # （限度額が定額なので、医療費がいくらでも足切りに届かない ＝
    # 「その医療費は存在しない」）。**軸として振れないのが正しい**ので、
    # ここは直す対象ではありません。理由が「入れ物が無い」から
    # 「値の無い区分がある」へ変わったことだけを固定します。
    assert ss._enum_containers(ir.deduction_start_cost), "入れ物は見えているはず"
    assert ir.deduction_start_cost("エ", 3_000_000) is None


def test_引数を取る表も行として歩ける():
    """`sweep_rows` は `fn()` と**引数なしで**しか呼んでいませんでした。

    `iryohi.low_income_grid(tier_name)` は6行の表を返しますが、
    引数が要るので `fn()` は `TypeError` で落ち、`sweep_rows` は
    そこで `[]` を返します。`sweep_function` は数値の引数しか見ず、
    `sweep_enums` は返りが行の並びだと `_scalars` が `{}` を返す ——
    **3つの掃引の全部から同時に外れる形**でした。

    埋めた引数は候補に残すこと（**前提として画面に出す値**なので、
    「どの区分の表か」が消えると節が書けません）。
    """
    import src.calc.iryohi as ir

    hits = ss.sweep_rows(ir.low_income_grid, name="low_income_grid")
    assert hits, "引数を埋めれば歩ける表を、1件も歩いていない"
    assert all(h.get("固定した引数") for h in hits), "埋めた引数が候補に残っていない"


# --------------------------------------------------------------------------
# **格子が「実在しない世界」を歩かないこと**（2026-08-20 に足した）
#
# 8/20 15:5x に歩留りを初めて測ったところ **5/32 = 0.156** で、落ちた27件の
# 最大の族は「引数の振れ幅の作りごと」でした —— `social_rate` を 0.7〜0.9 まで
# 振って住民税が 0、`monthly_pay` を 1,500,000→11,999,999 と振って「不変」。
# **どちらも節に書けません**（そんな世界は無いので）。
#
# ここで固定するのは**幅のほう**です。件数や歩留りは固定しません
# （測り直すたびに動く数なので、検査に入れると測るたびに赤くなる）。
# --------------------------------------------------------------------------

def test_率の格子は名前で決めた実在する幅の中に収まる():
    from src import calc_axes
    for key, (lo, hi) in calc_axes.RATE_BAND.items():
        family, _, param = key.rpartition(".")
        xs = ss._grid((lo + hi) / 2, param, family)
        assert len(xs) >= 4, f"{key}: 点が {len(xs)} 個しかない（掃引に足りない）"
        assert min(xs) >= lo - 1e-9 and max(xs) <= hi + 1e-9, f"{key}: {xs} が幅 {lo}〜{hi} を出た"


def test_名前の無い率は既定値のまわりだけを歩く():
    """`RATE_BAND` に無い率は、**既定値の 0.5〜2倍**。0.1〜0.9 の一律ではない。

    既定値は、その関数を書いた側が置いた「実在の1点」なので、
    そのまわりは必ず実在の側に残ります。
    """
    xs = ss._grid(0.15, "shiranai_rate", "shiranai")
    assert min(xs) >= 0.15 * 0.5 - 1e-9
    assert max(xs) <= 0.15 * 2.0 + 1e-9
    assert max(xs) < 0.5, f"実在しない高さまで振っている: {xs}"


def test_桁の細かい率でも点が潰れない():
    """`koyouhoken` の率は 0.0055。**2桁で丸めると9点が全部 0.01 になる。**

    そうなると `len(xs) < 4` で関数ごと掃引から落ちます（例外も警告も出ない）。
    """
    xs = ss._grid(0.0055, "worker_rate", "koyouhoken")
    assert len(set(xs)) >= 4, f"点が潰れている: {xs}"
    assert xs == sorted(xs)


def test_月額の引数に年収の代表値を入れない():
    """`monthly*` は月給。**所得の軸の 3,000,000 が入ると月給300万円**になる。

    `_grid` は 0.5〜4倍で振るので、月150万〜1,200万を歩きます。
    そこで見つかる崖は1つも実在しません（8/20 の実測で6件）。
    """
    for family, param in [("rousai", "monthly"), ("ikuji", "monthly_pay"),
                          ("shahoken", "monthly_before"), ("izoku", "avg_monthly"),
                          ("koureikoyou", "w60"), ("shobyo", "standard_pay"),
                          ("yukyu", "monthly_wage")]:
        fill = ss._axis_fill(param, family)
        assert fill is not None, f"{family}.{param} が埋められない"
        assert fill <= 500_000, f"{family}.{param} の埋め値が月額として大きすぎる: {fill:,}"


def test_族べつの埋め値は部分一致より先に引く():
    """同じ `monthly` でも、`shokibo` は共済の掛金（月1,000〜70,000円）。"""
    from src import calc_axes
    assert "shokibo.monthly" in calc_axes.PARAM_FILL
    assert ss._axis_fill("monthly", "shokibo") < ss._axis_fill("monthly", "rousai")


def test_量の引数が所得の軸へ落ちていない():
    """`annual_days_off`（年間休日）と `bonus_months`（賞与の月数）は、
    名前に `annual` / `bonus` が入っているだけで所得の軸へ寄っていた。"""
    assert ss._axis_fill("annual_days_off", "zangyo") <= 200
    assert ss._axis_fill("bonus_months", "rousai") <= 12
    assert ss._axis_fill("purchase_ratio", "invoice") < 1
    assert ss._axis_fill("annual_rate", "jutaku") < 1


# ---------------------------------------------------------------------------
# **一部の要素だけで振れる場合分け**（2026-08-21）
#
# `_enum_axis` は「入れ物の要素が**全部**数字を返すこと」を要求していました。
# 関係のない入れ物を弾くにはそれで足りますが、**制度の表は正しい入れ物でも
# 一部の値で「無い」を返します**。そのせいで関数が丸ごと掃引の外にいました。
# ---------------------------------------------------------------------------

def test_一部の区分が値を返さなくても軸として振れる():
    """`iryohi.deduction_start_cost` の返りは、型からして `int | None`。

    区分 ア・イ・ウ は数字を返し、エ・オ は `None`（そこに閾値が無い）。
    **5つ全部を要求していたので、この関数は丸ごと「呼べなかった関数」**でした。
    """
    import src.calc.iryohi as m
    axis = ss._enum_axis(m.deduction_start_cost, "tier_name", None)
    assert axis, "一部が None を返すだけで軸ごと捨てている"
    assert 2 <= len(axis) < 5, f"落ちる区分まで振っている: {axis}"
    assert ss.unreachable(m.deduction_start_cost) == ""


def test_段が1つしかない文書は落とすが表そのものは軸になる():
    """`inshi.edges('17号')` は段が1つで境目が無い。残り4つは境目を返す。"""
    import src.calc.inshi as m
    axis = ss._enum_axis(m.edges, "kind", None)
    assert axis, "1つ落ちるだけで軸ごと捨てている"
    assert "17号" not in axis, "数字を返さない値を軸に入れている"
    assert len(axis) == 4


def test_通った要素が6割に満たない入れ物は捨てる():
    """**線が本体です。** `kyoiku` は `PROGRAMS`（6件）と、その部分集合
    `FLOOR_PROGRAMS`（3件）を持ちます。`min_cost_paid` は下限のある3つでしか
    定義されていないので、`PROGRAMS` は 3/6 ＝ 0.5 で**この線に届きません**。

    2026-08-18 に「6つ中3つだけを振って倍率を 2.5倍（実際は 6.4倍）と
    嘘に書いた」のと同じ形が、一部を許した瞬間に別の入口から戻ります。
    """
    import src.calc.kyoiku as m
    axis = ss._enum_axis(m.min_cost_paid, "name", None)
    assert set(axis) == set(m.FLOOR_PROGRAMS), \
        f"部分集合ではなく広いほうを採っている: {axis}"
    assert len(axis) * 2 <= len(m.PROGRAMS) + 1, "6割の線が効いていない"


def test_全部通った入れ物を_一部だけ通った広い入れ物より先に採る():
    """並べ替えの鍵の先頭が「全部通ったか」であること。"""
    ss.PARTIAL_ENUM.clear()

    WIDE = ("あ", "い", "う", "え", "お")      # 3/5 ＝ 0.6 で線は通る
    NARROW = ("か", "き", "く")                # 3/3

    def fn(x: str) -> float:
        if x in NARROW:
            return 1.0 + NARROW.index(x)
        if x in ("あ", "い", "う"):
            return 10.0
        raise ValueError(x)

    fn.__module__ = __name__
    sys.modules[__name__].WIDE = WIDE
    sys.modules[__name__].NARROW = NARROW
    try:
        assert ss._enum_axis(fn, "x", None) == list(NARROW)
    finally:
        del sys.modules[__name__].WIDE, sys.modules[__name__].NARROW


def test_一部だけ振ったことは計器に残る():
    """**黙って半分だけ振らないこと。** 見えないと節に「全区分のうち」と書きます。"""
    ss.PARTIAL_ENUM.clear()
    import src.calc.inshi as m
    ss._ENUM_CACHE.clear()
    ss._enum_axis(m.edges, "kind", None)
    rows = [r for r in ss.PARTIAL_ENUM if r[1] == "edges"]
    assert rows, "一部だけ振ったのに計器に残っていない"
    _calc, _fn, arg, _cont, good, whole = rows[0]
    assert arg == "kind" and good == 4 and whole == 5


def test_一部だけ振った件数は一覧の頭に出る():
    ss.PARTIAL_ENUM.clear()
    ss.PARTIAL_ENUM.append(("inshi", "edges", "kind", "TABLES", 4, 5))
    head = "\n".join(ss.report_lines([], top=1)[:6])
    assert "一部の要素だけで振った場合分け" in head
    assert "inshi.edges(kind) 4/5" in head


def test_投資の元本は金額の軸に寄る():
    """`nisa.grown` / `nisa.tax_saved` は `principal` を埋められず落ちていた。"""
    from src import calc_axes
    import src.calc.nisa as m
    assert calc_axes.axis_of("principal") == "所得"
    assert ss.unreachable(m.grown) == ""
    assert ss.unreachable(m.tax_saved) == ""


def test_場合分けの名前は文の長さに達しない():
    """`ENUM_NAME_MAX` の**覆る条件**を、検査のほうで見張る。

    前提の文（`ASSUMPTIONS`）を入れ物の候補から外すために、
    **名前ではなく長さ**で切っています。切ったせいで本物の場合分けが
    黙って消えるのが唯一の怖い形なので、**`src/calc/` の全部の入れ物**を
    実際に測って、線の内側にいることを確かめます。

    ここが落ちたら、線を上げる前に **その並びが本当に場合分けか**を見ること。
    """
    import importlib
    import pkgutil

    import src.calc as calc

    over: list[str] = []
    for mod_info in pkgutil.iter_modules(calc.__path__):
        if mod_info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"src.calc.{mod_info.name}")
        for cname, v in vars(mod).items():
            if cname.startswith("_") or cname == "ASSUMPTIONS":
                continue
            if not isinstance(v, (list, tuple, dict)):
                continue
            items = ss._names_of(list(v))
            if not items or not (2 <= len(items) <= ss.ENUM_MAX):
                continue
            longest = max(len(x) for x in items)
            if longest > ss.ENUM_NAME_MAX:
                over.append(f"{mod_info.name}.{cname}（{longest}字）")
    assert not over, f"場合分けの名前が線を越えた（黙って掃引から消える）: {over}"


# --- 「新しい」の中身を割る（2026-08-24）------------------------------------
#
# `is_covered` が `False` を返す道は2本ある。**混ぜると在庫が水増しされる。**
#
#     (1) 印字されていないと **分かった**      → 本当に新しい
#     (2) 照合できる点が無い（`None`）        → **分かっていない**
#
# 実測 2026-08-24: 新しい 568件のうち **203件（36%）が (2)**。
# `src/supply.py` はこの「新しい」を在庫に数えるので、割らずに置くと
# 「あるかどうか分からないもの」を在庫に積んだままになる。

def _report_hit_不変():
    """`line_of` が読める形の `不変`（`x の幅` は hit の直下・値は `詳しく["値"]`）。"""
    return {"表": "t", "関数": "f", "見た値": "v", "形": "不変",
            "動かした引数": "a", "x の幅": (1, 2), "詳しく": {"値": 1.25}}


def _report_hit_崖():
    return {"表": "t", "関数": "g", "見た値": "w", "形": "崖",
            "動かした引数": "b", "x の幅": (3, 4),
            "詳しく": {"x の手前": 3, "x の先": 4, "跳ぶ幅": 5, "中央の段差": 1}}


def _hit_不変(値, 表="nenkin", 軸="months_before_65"):
    return {"表": 表, "形": "不変", "動かした引数": 軸,
            "詳しく": {"動かない値": 値, "x の幅": "6→22"}}


def test_小さい値の不変は_本文に出ていても新しいと数えられる():
    """**この道具の欠陥そのもの。**直す前に、あることを検査で固定する。

    `_LONE_NUMBER_MIN` は 1000。結果が 1.25 のような裸の小さい数だけの候補は、
    `_point_printed` が `None` を返すので **本文に書いてあっても既出にならない。**
    実例は `nenkin.birth_gap_ratio … 1.25 のまま` —— 節は
    「0.5% ÷ 0.4% ＝ 1.25倍で、1か月でも60か月でも同じです」と印字している。
    """
    sections = {"繰上げの生年差": "  **減る額の比は、繰り上げた月数によりません** —— "
                                  "0.5% ÷ 0.4% ＝ 1.25倍で、1か月でも60か月でも同じです。"}
    hit = _hit_不変(1.25)
    assert ss.is_covered(hit, sections) is False, "既出になった（欠陥が直っている）"
    assert ss.undecided(hit, sections) is True, \
        "**判定できなかった**ほうに数えられていない"


def test_印字されていないと分かったものは_判定できなかったに入れない():
    """(1) と (2) を取り違えないこと。**大きい値なら照合できる。**"""
    sections = {"どこか": "  止まった値は 4,063,000円です。"}
    assert ss.undecided(_hit_不変(4_063_000), sections) is False
    assert ss.is_covered(_hit_不変(4_063_000), sections) is True
    # 同じ桁で、本文に無い値
    assert ss.is_covered(_hit_不変(9_999_111), sections) is False
    assert ss.undecided(_hit_不変(9_999_111), sections) is False, \
        "印字されていないと**分かった**のに、判定できなかった側へ落ちている"


def test_節が読めない回は_判定できなかったに数えない():
    """節そのものが読めない回は、**この道具の欠陥ではない。**

    `_covered_map` は節を読めなければ空を返し、印を1つも出さない。
    そこで「全部が判定できなかった」と数えると、**読めなかったことが
    候補の性質のように見えます。**
    """
    assert ss.undecided(_hit_不変(1.25), None) is False
    assert ss.undecided(_hit_不変(1.25), {}) is False


def test_自明な形は一覧の最後に回す():
    """`片効き`・`不変` は実測 32枠中14枠を占め、そこから書けた節は0件。

    表ごとに6件で切るので、先頭に混ざるぶんだけ書ける候補が沈む
    （`src/supply.py` の `SWEEP_YIELD` の註が、この修正を予約していた）。
    """
    assert set(ss.SHAPE_LAST) == {"片効き", "不変"}
    hits = [_report_hit_不変(), _report_hit_崖()]
    lines = ss.report_lines(hits, top=10)
    body = [ln for ln in lines if "t." in ln]
    assert len(body) == 2
    assert "崖" in body[0] and "不変" in body[1], \
        f"自明な形が先頭に残っている: {body}"


def test_判定できなかった件数は一覧の頭に出る():
    """**黙って在庫に積まないこと。**件数が出ていれば、次の回が最初に見る。

    実物の表（`nenkin`）で組みます。`report_lines` は自分で節を読み直すので、
    `_UNDECIDED` に手で入れても上書きされます —— **そこを通すのが本体。**
    `nenkin` の節は「0.5% ÷ 0.4% ＝ 1.25倍」と印字しているのに、
    `_LONE_NUMBER_MIN` が 1000 なので 1.25 は照合できません。
    """
    hit = _report_hit_不変()
    hit["表"] = "nenkin"
    lines = ss.report_lines([hit], top=10)
    head = "\n".join(lines)
    if "[既]" not in head:        # 節が読めない環境。**その回は何も言えない**
        pytest.skip("節が読めないので既出の印そのものが出ない")
    assert "判定できていません" in head
    assert "[未]" in head


# ---- 畳んだことが、次に戻されないための門（2026-08-26）--------------------

def test_実物の全掃引を直に呼ぶ検査は_壊れた表の1件だけ():
    """**`ss.sweep_all()` の直呼びを増やすと、この1ファイルが分単位で伸びます。**

    1回 46〜48秒。ここが 11回に増えていたせいで、このファイルだけで 685秒 かかり、
    **全体の `pytest` が「時間切れで通していません」と何日も申し送られていました**
    （`retro.py` の持ち越しに `pytest` と `test_section_sweep.py` が2回ずつ）。
    畳んだ後（`sweep_once`）に誰かが直呼びを書き足しても、
    **検査は緑のまま通ってしまう** —— 遅くなるだけだからです。
    **だから遅さのほうを検査にします。**

    足すときは `sweep_once()` を使うこと。**それでは駄目な検査**
    （表を壊してから掃く、など）だけ、下の名前に足して直呼びしてよい。

    **数えるのは構文木です**（`ast`）。文字列や註釈に名前が出るだけでは数えません ——
    最初に書いた版は自分の説明文を数えて落ちました。
    """
    import ast

    直呼びしてよい = {"test_壊れた表があっても全体は止まらない"}
    木 = ast.parse(Path(__file__).read_text(encoding="utf-8"))

    いま: set[str] = set()
    for 節 in ast.walk(木):
        if not isinstance(節, ast.FunctionDef) or not 節.name.startswith("test_"):
            continue
        for 中 in ast.walk(節):
            if (isinstance(中, ast.Call)
                    and isinstance(中.func, ast.Attribute)
                    and 中.func.attr == "sweep_all"):
                いま.add(節.name)

    assert いま == 直呼びしてよい, (
        f"`ss.sweep_all()` を直に呼んでいる検査: {sorted(いま)}。"
        f"許しているのは {sorted(直呼びしてよい)} だけです —— "
        "1回 46〜48秒 かかるので `sweep_once()` に替えること"
    )
