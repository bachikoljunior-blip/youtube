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

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import section_sweep as ss  # noqa: E402


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
    hits = ss.sweep_all()
    assert len(hits) >= 20, f"候補が {len(hits)}件。row モードが効いていない疑い"
    assert not [h for h in hits if h["形"] == "読めない"], \
        [h for h in hits if h["形"] == "読めない"]


def test_行モードが表の中の形を拾う():
    """引数を動かす掃引だけだと、`list` を返す表が丸ごと落ちます。"""
    from_rows = [h for h in ss.sweep_all() if h["動かした引数"] == "（表の行）"]
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
    for h in ss.sweep_all():
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
    hits = ss.sweep_all()
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


def test_実物で_ideco_の3件は全部既出():
    """**前の回が手で確かめた1件**（申し送り）。ここが緑でなければ直しは効いていません。"""
    import sys
    sys.path.insert(0, "scripts")
    import topic_forge as tf

    all_sections, _, _ = tf.survey()
    total, novel = ss.novel_counts(ss.sweep_all(["ideco"]), all_sections)
    assert total["ideco"] == 3, total
    assert novel["ideco"] == 0, novel


def test_実物で_新しい候補が全部は消えていない():
    """**落としすぎの検出。**全部0になったら、この道具は候補を出しません。"""
    import sys
    sys.path.insert(0, "scripts")
    import topic_forge as tf

    all_sections, _, _ = tf.survey()
    total, novel = ss.novel_counts(ss.sweep_all(), all_sections)
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
    hits = [h for h in ss.sweep_all() if h["形"] == "片効き"]
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

    hits = [h for h in ss.sweep_all() if h["形"] == "片効き"]
    if not hits:
        return
    alls, _free, _known = topic_forge.survey()
    # 判定が**動いている**こと（例外なく False を返す実装ではない）を、
    # 節に値を混ぜた写しで確かめる。
    probe = dict(hits[0])
    val = probe["詳しく"]["動かない値"]
    assert ss.is_covered(probe, {"s": f"{val:,.0f}"}) is True


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
    for hit in ss.sweep_all():
        shape = hit["形"]
        seen[shape] = seen.get(shape, 0) + 1
        assert ss._hit_points(hit) or ss._hit_outcome(hit) is not None, \
            f"形 {shape} が is_covered に何も渡していない: {hit['詳しく']}"
    # **形が実物から出ていなければ、上の for は素通りします。**
    # `不変` だけは x を持たない設計（`_hit_points` が空を返す）なので除きます
    for shape in ss.SHAPES:
        assert shape in seen, f"形 {shape} が実物から1件も出ていない（上の検査が素通り）"
