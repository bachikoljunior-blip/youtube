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
