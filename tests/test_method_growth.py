# -*- coding: utf-8 -*-
"""`scripts/method_growth.py` —— METHOD の「毎回 読む」側の伸びを、**道具が数えて門を引く**こと。

2026-09-10 12:1x JST（optimizer・Opus）。冒頭「この文書の読み方」は門を **2つ** 置いています
（行 1周 +20行・本文の字 1周 +300字）が、**どちらにも印字する口がありませんでした** ——
数え方は JOURNAL 05:5x に散文で在るだけで、6周ごとに次の回がそれを探して手で回す形。
`trend.py` の「毎周 印字する数」と同じ扱い（**覚えないこと**）にした、その見張り。

**いちばん大事な検査は `test_11_0x_が手で数えた_3点_と_1字も違わないこと`** ——
道具が別の数を出すなら、置いた門は別の物を測っています。

**陽性対照は撃って落としてある**（§5 の教訓の形3つ目）:
`measure` から引用の除外（`startswith(">")`）を外すと 3点 とも合わなくなる。
"""
import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("method_growth", ROOT / "scripts" / "method_growth.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = _mod()


def _at(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=M.JST)


#: 11:0x の回が **手で** 数えて `docs/METHOD.md` の冒頭へ書いた 3点（窓の端は周の刻・JST）。
#: **この表を道具から作らないこと** —— 借りると、道具と一緒に間違えます。
点 = [
    ("2026-09-09 21:46", "2026-09-10 01:25", 16, 1850),
    ("2026-09-10 01:59", "2026-09-10 05:25", 23, 2758),
    ("2026-09-10 06:07", "2026-09-10 10:17", 3, 3699),
]


@pytest.mark.parametrize("a,b,d_lines,d_chars", 点)
def test_11_0x_が手で数えた_3点_と_1字も違わないこと(a, b, d_lines, d_chars):
    """**道具が別の数を出すなら、置いた門は別の物を測っています。**"""
    ma, mb = M.measure(M.blob_at(_at(a))), M.measure(M.blob_at(_at(b)))
    assert mb["body_lines"] - ma["body_lines"] == d_lines
    assert mb["body_chars"] - ma["body_chars"] == d_chars


def test_引用は本文に数えない():
    """**門は本文（引用を除く）に置かれています**（11:0x）。混ぜたら門の意味が変わる。

    **節の見出しは本文に入ります**（05:5x の手が `L[s0:s7]` で挟んでいる形そのもの）——
    見出しも毎周 読む字なので、外すと 11:0x の 3点 と合わなくなります。
    """
    text = "## 0.\nあいう\n> かきくけこ\n\n## 7.\n## 8.\nさし\n## 9.\n"
    m = M.measure(text)
    assert m["body_lines"] == 4                       # 見出し2つ ＋「あいう」「さし」（空行も引用も数えない）
    assert m["body_chars"] == len("## 0.") + 3 + len("## 8.") + 2
    assert m["quote_chars"] == len("> かきくけこ")


def test_毎回読む側は_7_と_9_を含まないこと():
    """§7（log）と §9 以降（過去の本）は**飛ばす側**なので、物差しに入れない。"""
    text = "## 0.\nA\n## 7.\nBBBB\n## 8.\nC\n## 9.\nDDDD\n"
    m = M.measure(text)
    assert m["body_lines"] == 4                        # 見出し2つ ＋ A と C
    assert m["body_chars"] == len("## 0.") + 1 + len("## 8.") + 1
    # **飛ばす側をいくら太らせても、この数は1字も動かないこと**（＝ 門は log では鳴らない）
    太らせた = text.replace("BBBB", "B" * 9999).replace("DDDD", "D" * 9999)
    assert M.measure(太らせた) == m


def test_節の名が変わったら黙って_0_を返さずに止まること():
    """**外れた数を配るより、止まるほうが安い**（註の覆る条件 (3)）。"""
    with pytest.raises(KeyError):
        M.measure("## 0.\nA\n")          # §7 の見出しが無い


def test_周は_round_で畳む():
    """`rounds.jsonl` は 1周に 2行（hourly・optimizer）入る。畳まないと窓が半分になる。"""
    rs = M.rounds()
    assert len(rs) == len(set(rs)), "周の刻に重複があります ＝ `round` で畳めていません"
    assert rs == sorted(rs)


def test_字の門は_2窓_続いたときだけ引く():
    """**1窓 で引かない**（11:0x が「2つ 続いたら」と書いた形）。"""
    def p(chars_per_lap):
        return {"chars_per_lap": chars_per_lap, "lines_per_lap": 1.0}
    assert "引かれません" in M.verdict([p(400), p(100)])[1]
    assert "引かれました" in M.verdict([p(100), p(400), p(400)])[1]


def test_行の門は字の門と別に印字されること():
    """**行の門は単独では効きません**（点3 は 20行 の 1/40 で +616字/周 積んだ）。
    2つを1行に畳むと、その盲点がまた隠れる。"""
    out = M.verdict([{"chars_per_lap": 400.0, "lines_per_lap": 0.5},
                     {"chars_per_lap": 400.0, "lines_per_lap": 0.5}])
    assert len(out) == 2
    assert "行の門" in out[0] and "引かれません" in out[0]      # 20行 には遠い
    assert "字の門" in out[1] and "引かれました" in out[1]      # それでも字は越えている


def test_報告は窓の端を_JST_の刻で出すこと():
    """次の回が「どこからどこまでを測ったか」を読めること（窓の取り方が違うと点は比べられない）。"""
    out = M.report(laps=6, n=2)
    assert "周の刻で挟む" in out and "commit ではない" in out
    assert "JST" in out


_S7 = ("読み方\n"
       "## 0.\nA\n"
       "## 7.\n"
       "### いまの数\nいまの数の本文\n"
       "**【2026-09-10 21:4x】日付つきの節\n日付つきの中身\n"
       "- **【2026-09-09 01:5x・optimizer】もう1つの日付つきの節\n中身\n"
       "- **形**: 末尾の一覧の1つ目\n"
       "- **声**: 末尾の一覧の2つ目\n"
       "## 8.\nC\n## 9.\nD\n")


def test_毎周読むのに_measure_が見ていない_3塊_を挟めること():
    """冒頭「この文書の読み方」・§7 の「いまの数」・§7 末尾の覆る条件の一覧
    （2026-09-10 23:5x に足した・`section7_spans` の註）。"""
    lines = _S7.split("\n")
    spans = M.section7_spans(lines)
    assert len(spans) == 4                                     # 「いまの数」は 2つ に割れる（`_now_cut`）
    got = M.measure7_split(_S7)
    assert set(got) == set(M.SPAN7_NAMES)
    assert got["読み方"]["body_lines"] == 1                    # 「読み方」だけ（`## 0.` の手前まで）
    assert got["いまの数"]["body_lines"] == 2                  # 見出し ＋ 本文1行
    assert got["次に見る所"]["body_lines"] == 0                # この下敷きには書き出しの語が無い ＝ 空
    assert got["末尾の一覧"]["body_lines"] == 2                # `- **形**` と `- **声**`


_S7N = _S7.replace("いまの数の本文\n", "いまの数の本文\n    次に見る所      (a) 見る所\n(b) もう1つ\n")


def test_いまの数は_数の表_と_次に見る所_に割れること():
    """**門が名指しする先を、実際に伸びている側まで降ろす**（`_now_cut` の註・2026-09-11 12:0x）。

    実測 09/11 08:12 → 11:58（6周）: 塊は 1周 +652字 で、内訳は
    **数の表 +22 ／ 次に見る所 +630** ＝ 伸びの 96% は下側。
    塊のままだと、既に形の効いている上の表を畳みに行きます。
    """
    got = M.measure7_split(_S7N)
    assert got["いまの数"]["body_lines"] == 2                  # 見出し ＋ 本文1行（割る前と同じ）
    assert got["次に見る所"]["body_lines"] == 2                # 書き出しの行 ＋ その続き


def test_割りは足し算を変えないこと():
    """**合計は `measure7` と同じ** —— 割りで数が増えたり減ったりしないこと。"""
    for text in (_S7, _S7N):
        sp = M.measure7_split(text)
        assert sum(v["body_chars"] for v in sp.values()) == M.measure7(text)["body_chars"]


def test_positive_control_次に見る所_を太らせると_その名だけが動くこと():
    """**陽性対照** —— 割りが効いていなければ（＝ 2つ目が常に空なら）この検査は落ちます。"""
    太 = _S7N.replace("(b) もう1つ", "Z" * 500)
    a, b = M.measure7_split(_S7N), M.measure7_split(太)
    assert b["次に見る所"]["body_chars"] - a["次に見る所"]["body_chars"] == 500 - len("(b) もう1つ")
    for name in ("読み方", "いまの数", "末尾の一覧"):
        assert b[name]["body_chars"] == a[name]["body_chars"]


def test_書き出しの語が変わったら黙って_0_を配らずに_2つ目を空にすること():
    """**覆る条件 (1)** —— 割りが外れても**塊の合計は割る前と同じ**（門は割る前と同じに鳴る）。
    `section7_spans` の「止める」（塊そのものが外れる側）とは別の扱いです。"""
    外れ = _S7N.replace("次に見る所", "次にみるところ")
    sp = M.measure7_split(外れ)
    assert sp["次に見る所"]["body_chars"] == 0
    assert sp["いまの数"]["body_chars"] == M.measure7_split(_S7N)["いまの数"]["body_chars"] \
        + M.measure7_split(_S7N)["次に見る所"]["body_chars"] + len("次にみるところ") - len("次に見る所")


def test_日付つきの節は_3塊_に入らないこと():
    """**日付つきの節は飛ばす側**なので、いくら太らせても数は1字も動かないこと。"""
    m = M.measure7(_S7)
    太らせた = _S7.replace("日付つきの中身", "X" * 9999)
    assert M.measure7(太らせた) == m


def test_positive_control_3塊_は_measure_と別の数であること():
    """**陽性対照** —— `measure`（§0〜§6・§8）を太らせても 3塊 の数は動かず、
    逆に 3塊 を太らせても `measure` は動かないこと。
    **同じ数に足してしまうと、12:1x の 3点 が壊れます**（`points` の註）。
    """
    太1 = _S7.replace("\nA\n", "\n" + "A" * 500 + "\n")      # §0〜§6 の側
    assert M.measure7(太1) == M.measure7(_S7)
    assert M.measure(太1) != M.measure(_S7)
    太2 = _S7.replace("いまの数の本文", "Y" * 500)              # 3塊 の側
    assert M.measure(太2) == M.measure(_S7)
    assert M.measure7(太2) != M.measure7(_S7)


def test_3塊_の挟みが外れたら黙って_0_を返さずに止まること():
    """**外れた数を配るより、止まるほうが安い**（`section7_spans` の覆る条件 (1)(2)）。"""
    with pytest.raises(KeyError):
        M.measure7("## 0.\nA\n## 7.\n## 8.\nC\n## 9.\n")     # `### いまの数` が無い
    with pytest.raises(ValueError):
        # 日付つきの節が 1つも無い ＝ 「いまの数」の終わりが取れない
        M.measure7("読み方\n## 0.\nA\n## 7.\n### いまの数\nB\n- **形**: x\n## 8.\nC\n## 9.\n")


def test_門が引かれた回は塊を名指しできること():
    """`--split` は、どの塊がその窓を吸ったかを出す（門の文がそう指している）。"""
    out = M.split_report()
    assert "塊ごとの伸び" in out
    for name in M.SPAN7_NAMES:
        assert name in out


# ---- 「いま」は窓の端の blob ではなく、作業ツリー（2026-09-11 05:1x・optimizer・Opus）----
#
# 実測: §7 末尾の一覧を -4,166字 縮めた直後に撃つと、`report()` は「いま 28,669字」
# （＝ 縮める前の数）と印字していた。**削った回ほど、書き写すと大きい嘘が載る。**
# 窓の差（伸び）は blob のまま —— 動かしたのは「いま」の 2行 だけ。
# 覆る条件は `method_growth.worktree_text` の註。

def test_いまは作業ツリーの字を読むこと():
    """`worktree_text()` は `docs/METHOD.md` を**そのまま**返す（blob ではない）。"""
    assert M.worktree_text() == (ROOT / "docs" / "METHOD.md").read_text(encoding="utf-8")


def test_いまの行は作業ツリーと一致し_窓の端の_blob_ではないこと(monkeypatch):
    """`report()` の「いま」の 2行 は、`points()` の `now`/`s7_now` から取らないこと。

    **陽性対照**: `points()` が返す `now`/`s7_now` を壊しても「いま」の数は動かない
    （＝ そこから取っていない）。
    """
    now = M.measure(M.worktree_text())
    now7 = M.measure7(M.worktree_text())
    out = M.report()
    assert f"いま 本文 {now['body_lines']}行・{now['body_chars']:,}字" in out
    assert f"いま 本文 {now7['body_lines']}行・{now7['body_chars']:,}字" in out

    real = M.points

    def broken(*a, **k):
        ps = real(*a, **k)
        for p in ps:
            p["now"] = {"body_lines": -1, "body_chars": -1, "quote_chars": -1}
            p["s7_now"] = {"body_lines": -2, "body_chars": -2}
        return ps

    monkeypatch.setattr(M, "points", broken)
    assert M.report() == out        # 「いま」は blob 側の `now` には触っていない


def test_positive_control_作業ツリーを差し替えると_いま_だけが動くこと(monkeypatch):
    """**壊したら落ちるまで撃つ**（§5 の教訓の形3つ目）。

    作業ツリーの METHOD に 500字 足すと「いま」の数だけが動き、窓の差（`+N字`）は動かない。
    """
    real_text = M.worktree_text()
    before = M.report()
    monkeypatch.setattr(M, "worktree_text", lambda: real_text.replace("## 0.", "X" * 500 + "\n## 0.", 1))
    after = M.report()
    assert before != after
    bw = [l for l in before.split("\n") if "JST   本文" in l]
    aw = [l for l in after.split("\n") if "JST   本文" in l]
    assert bw == aw


# ---- 4つ目の塊: §9 以降のうち「直近の1本」（2026-09-11 06:5x・optimizer・Opus）----
#
# 冒頭「この文書の読み方」が毎周 読ませているのは 4つ で、4つ目が「§9 以降のうち 直近の1本」。
# 12:1x（§0〜§6・§8）と 23:5x（§7 の 3塊）の物差しは、**その 4つ目を 1字も見ていなかった**。
# 実測（この回）: §14 は **24,125字**（§13 6,002・§15 3,791 の 4倍）で、
# 毎周 読む物のどれよりも大きい。**§14 が自分に置いた門は行の門だけ**で、
# 冒頭が 11:0x に名指しした「行の門は表と長い行に対して構造として盲」に、そのまま当たっている。
# 覆る条件は `method_growth.book_sections` の註。

def test_本の節を_id_で挟めること():
    """節の**番号は本が増えると動く**ので、窓の両端で同じ節を指すには id で挟むこと。"""
    bs = M.book_sections(M.worktree_text().split("\n"))
    assert [b["num"] for b in bs] == sorted(b["num"] for b in bs)
    assert all(b["num"] >= 9 for b in bs)
    assert all(b["a"] < b["b"] for b in bs)
    ids = [b["id"] for b in bs]
    assert len(ids) == len(set(ids))                  # id は 1本 1つ
    assert all(i.startswith("2026-") for i in ids)


def test_毎周読む候補は_いちばん新しい_2つ():
    """きょうの枠が公開前なら `hourly` は 1つ 手前を読む ＝ 候補は 2つ（`BOOK_READ`）。"""
    text = M.worktree_text()
    allb = M.books_all(text)
    live = M.measure_books(text)
    assert len(live) == M.BOOK_READ == 2
    tail = [b["id"] for b in M.book_sections(text.split("\n"))][-2:]
    assert list(live) == tail
    assert all(live[k] == allb[k] for k in live)      # 同じ挟みで数えていること


def test_本の節は_毎回読む側にも_3塊_にも入らないこと():
    """**別の数**（足さないこと）—— §9 以降は `measure`／`measure7` の外に在る。"""
    text = M.worktree_text()
    lines = text.split("\n")
    head9 = M._section_bounds(lines, "## 9.")
    for a, b in M.section7_spans(lines):
        assert b <= head9
    for b in M.book_sections(lines):
        assert b["a"] >= head9


def test_positive_control_本の節の伸びは他の_2つ_に出ないこと():
    """**壊したら落ちるまで撃つ** —— 本の節に 800字 足しても `measure`／`measure7` は動かない。

    ＝ 12:1x と 23:5x の物差しが 4つ目を **1字も見ていない**ことの、道具の側の証拠。
    """
    text = M.worktree_text()
    sid = list(M.measure_books(text))[-1]
    lines = text.split("\n")
    b = [x for x in M.book_sections(lines) if x["id"] == sid][0]
    fat = "\n".join(lines[:b["b"]] + ["Y" * 800] + lines[b["b"]:])
    assert M.measure(fat) == M.measure(text)
    assert M.measure7(fat) == M.measure7(text)
    assert M.measure_books(fat)[sid]["body_chars"] == M.measure_books(text)[sid]["body_chars"] + 800


def test_本の節の挟みが外れたら黙って_0_を返さずに止まること():
    """見出しから id（バッククォートの中の日付）が消えたら止まること（註の覆る条件 (1)）。"""
    with pytest.raises(ValueError):
        M.book_sections(["## 9. 最初の1本", "A"])          # id が無い


def _p(head, per_lap):
    return {"from": _at("2026-09-10 00:00"), "to": _at("2026-09-10 06:00"),
            "books": {head: {"now": 9999, "d": int(per_lap * 6), "per_lap": per_lap}}}


def test_本の節の門は_2窓_続いたときだけ引く():
    """上の 2つ と同じ門（1周 +300字・2窓 続いたら）を、**節ごとに**引くこと。"""
    one = M.book_report([_p("x", 400), _p("x", 10)])
    assert "引かれません" in one[-1]
    two = M.book_report([_p("x", 400), _p("x", 400)])
    assert "**引かれました**" in two[-1] and "x（+400 / +400）" in two[-1]
    # **判定は hourly**（§5・きょうの枠の本）—— optimizer は数を並べるまで
    assert "hourly" in two[-1]


def test_新しい節は伸びではなく書き下ろしと言うこと():
    """1本 出るたびに節は 0 から始まるので、**その窓を「伸び」と呼ばないこと**。"""
    out = M.book_report([{"from": _at("2026-09-10 00:00"), "to": _at("2026-09-10 06:00"),
                          "books": {"new-one": {"now": 3791, "d": None, "per_lap": None}}}])
    assert "この窓の頭には無い節" in "\n".join(out)
    assert "書き下ろし 3,791字" in "\n".join(out)


def test_報告に_4つ目_の水準が出ること():
    """**水準も印字する** —— 伸びだけでは「兄弟の 4倍 の節が居る」が 1度も鳴らない。"""
    out = M.report()
    live = M.measure_books(M.worktree_text())
    assert "毎周 読むのに、上の 2つ が見ていない 4つ目" in out
    for sid, c in live.items():
        assert f"{sid}  いま 本文 **{c['body_chars']:,}字**" in out


def test_positive_control_4つ目_の_いま_は窓の端の_blob_ではないこと(monkeypatch):
    """**壊したら落ちるまで撃つ**（§5 の教訓の形3つ目）。**この回に実物で踏んだ形**:

    相手の押しを merge した直後に撃つと、窓の端の blob は **167字 古い数**（24,292）を出し、
    作業ツリーの実物は 24,125 だった。`points()` の `books` を壊しても「いま」は動かないこと。
    """
    out = M.report()
    real = M.points

    def broken(*a, **k):
        ps = real(*a, **k)
        for p in ps:
            for c in (p.get("books") or {}).values():
                c["now"] = -1
        return ps

    monkeypatch.setattr(M, "points", broken)
    lv = [l for l in M.report().split("\n") if "いま 本文 **" in l]
    assert lv == [l for l in out.split("\n") if "いま 本文 **" in l]
    assert all("-1字" not in l for l in lv)


# ---- 塊ごとの門（合計は打ち消しに対して盲・2026-09-11 07:3x・optimizer・Opus）----
#
# 実測 09/11 03:22 → 06:58: いまの数 +416字/周 / 末尾の一覧 -1,401字/周 → 合計 -882字/周。
# **畳んだ塊と伸びた塊が同じ窓に居ると、合計は下を向く。**
# 4つ目（本の節）の門は最初から節ごとなので、3塊 の側だけが合計で読まれていた。
# 覆る条件は `method_growth.split_drawn` の註。

def _s7p(**per_lap):
    return {"s7_split": {n: float(per_lap.get(n, 0.0)) for n in M.SPAN7_NAMES}}


def test_塊ごとの門は_2窓_続いたときだけ引く():
    assert M.split_drawn([_s7p(いまの数=400), _s7p(いまの数=10)]) == []
    drawn = M.split_drawn([_s7p(いまの数=400), _s7p(いまの数=400)])
    assert drawn == ["いまの数（+400 / +400）"]


def test_塊ごとの門は窓が_1つ_しか無ければ引かないこと():
    assert M.split_drawn([_s7p(いまの数=900)]) == []
    assert M.split_drawn([]) == []


def test_positive_control_合計が下を向いても塊の門は鳴ること():
    """**この門が在る理由そのもの** —— 打ち消しの窓を 2つ 並べる。

    合計（`s7_per_lap`）は -985 と -985 で、字の門は 1度も鳴らない。
    それでも「いまの数」は 2窓 とも +416 で伸びている。
    """
    ps = [{"s7_per_lap": -985.0, **_s7p(いまの数=416, 末尾の一覧=-1401)} for _ in range(2)]
    assert all(p["s7_per_lap"] < 0 for p in ps)          # 合計は下向き
    assert M.split_drawn(ps) == ["いまの数（+416 / +416）"]
    # 畳んだ側（末尾の一覧）は名指ししないこと
    assert "末尾の一覧" not in "".join(M.split_drawn(ps))


def test_塊ごとの門は報告に印字されること():
    assert "塊ごとの門" in M.report()


def test_positive_control_報告の行は_split_drawn_の答えを載せていること(monkeypatch):
    """**壊したら落ちるまで撃つ** —— 行が在るだけでは、その門が繋がっている証拠になりません
    （実測: `sd = []` に潰しても「塊ごとの門: 引かれません」は同じ字で出ました）。"""
    monkeypatch.setattr(M, "split_drawn", lambda ps: ["いまの数（+416 / +416）"])
    line = [l for l in M.report().split("\n") if "塊ごとの門" in l]
    assert len(line) == 1
    assert "**引かれました**" in line[0] and "いまの数（+416 / +416）" in line[0]
    monkeypatch.setattr(M, "split_drawn", lambda ps: [])
    line = [l for l in M.report().split("\n") if "塊ごとの門" in l]
    assert "引かれません" in line[0]


def test_塊ごとの門は_3塊_の名を全部見ること():
    """1つでも見落とすと、その塊だけが測られない側へ移る（12:1x が踏んだ形）。"""
    for n in M.SPAN7_NAMES:
        assert M.split_drawn([_s7p(**{n: 400}), _s7p(**{n: 400})]) == [f"{n}（+400 / +400）"]


def test_points_は塊ごとの数も同じ窓で持つこと():
    ps = M.points()
    assert ps and all(p["s7_split"] is not None for p in ps)
    for p in ps:
        assert set(p["s7_split"]) == set(M.SPAN7_NAMES)
        # 塊の和は合計（`s7_per_lap`）と一致すること
        # ＝ 別の挟みで数えていないことの陽性対照（`section7_spans` を 1つ 落とすと割れる）
        assert abs(sum(p["s7_split"].values()) - p["s7_per_lap"]) < 1e-6


# --- 幅のある窓は「手の効き」を答えられない（2026-09-13 04:3x・optimizer・Opus） -------------
# 実測: 02:5x の手のあと、6周窓は 1窓目 +671 / 2窓目 +678字/周（門 300 の上）だったが、
# 同じ台帳を `--after '2026-09-13 02:42' --laps 1` で読むと +713 → -28字/周。
# ＝ 6周窓の数は「手の前の周」を 5周 ぶん運んでいた。**印字が無いと、次の回は 2窓目 で誤って (ii) を引きます。**

def test_幅のある窓には手の効きを読むなという印字が付くこと():
    line = M.window_caveat(6)
    assert "6周 幅" in line and "最大 5周" in line
    assert "--after" in line          # 直し方（同じ台帳の読み直し）も一緒に言うこと
    assert M.window_caveat(6) in M.report()


def test_窓の頭を手に合わせた回には印字しないこと():
    """`--after` で頭を固定した窓は、もう手の前の周を運んでいない ＝ 註は要らない。"""
    out = M.report(laps=6, n=1, after=_at("2026-09-13 02:42"))
    assert "手を打った回の効きを読まないこと" not in out


def test_窓が_1周_なら印字しないこと():
    """幅 1周 の窓は構造として手の前を運べない（`laps`-1 ＝ 0 周）。"""
    assert "手を打った回の効きを読まないこと" not in M.report(laps=1, n=2)


def test_positive_control_印字が消えたら本体の検査が落ちること(monkeypatch):
    """**陽性対照**（§5 教訓の形 3つ目）: 註を当てにならない版へ差し替えると、上の 1つ目 が落ちること。

    落ちる向きで書いてある（0 へ落ちる側 ＝ §5 教訓の形 3つ目・09/13 02:5x の頭打ちの罠を避ける）。
    """
    monkeypatch.setattr(M, "window_caveat", lambda laps: "  （註を消した版）")
    out = M.report()
    assert "6周 幅" not in out and "--after" not in out


# --- 「引かれません」と「まだ測れません」／門は水準を見ていない（2026-09-13 07:2x・optimizer・Opus） ---
# この回に 2つ 踏んだ。04:3x の申し送りは「手の効きは `--after '<手の刻>' --laps 1` で読め」だが、
# (1) `--laps 5 --points 2` は周が 5つ しか無いので窓を **1つ** しか作れず、それでも「引かれません」と言った。
# (2) `--laps 1` の門は「2周 続けて」を要るので、**同じ水準でも 1周 凹めば鳴りません** ——
#     実測 手の後の 5周 は +713 / -28 / +134 / +45 / +1,019字 ＝ 平均 +377字/周（門の上）なのに沈黙。

def _vp(chars_per_lap, lines_per_lap=1.0):
    return {"chars_per_lap": float(chars_per_lap), "lines_per_lap": lines_per_lap}


def test_窓が_1つ_なら引かれませんではなくまだ測れませんと言うこと():
    """**向きが悪い穴**: 窓が足りない回ほど静かなほうへ倒れる（手の直後がまさにそれ）。"""
    line = M.verdict([_vp(900)])[1]
    assert "まだ測れません" in line and "窓が 1つ" in line
    assert "**「引かれません」ではありません**" in line
    assert "+900字/周" in line          # いまの窓の数は落とさない


def test_窓が_2つ_在れば今までどおり引かれませんと言うこと():
    """**まだ測れません を配りすぎないこと**（2窓 在る回は今までの字のまま）。"""
    line = M.verdict([_vp(400), _vp(10)])[1]
    assert "引かれません" in line and "まだ測れません" not in line


def test_続いていなくても並べた窓の平均が門の上ならそう言うこと():
    """**門は「続いたか」を見ており、水準を見ていません**（実測の 5周 をそのまま置く）。"""
    vals = [713, -28, 134, 45, 1019]
    line = M.verdict([_vp(v) for v in vals])[1]
    assert "引かれません" in line            # 門の答えは変えない
    assert "平均は +377字/周" in line
    assert "--laps" in line                  # 申し送りに幅を書けと言うこと


def test_平均が門の下なら余計な行を足さないこと():
    """**陽性対照の裏**: 静かな窓に註を配らないこと（配ると印が効かなくなる）。"""
    line = M.verdict([_vp(100), _vp(100), _vp(100)])[1]
    assert "平均" not in line


def test_positive_control_平均の行を消すと実測の_5周_が黙ること(monkeypatch):
    """**陽性対照**（§5 教訓の形 3つ目）: `level_caveat` を空へ差し替えると、上の 1つ目 が落ちる。"""
    monkeypatch.setattr(M, "level_caveat", lambda vals: "")
    line = M.verdict([_vp(v) for v in [713, -28, 134, 45, 1019]])[1]
    assert "平均" not in line


def test_4塊_と_塊ごと_と_節ごと_と_本の節_も窓が_1つ_なら測れないと言うこと():
    """**同じ穴が 4か所 に在った** —— 直したのは 1つ ではなく全部（`too_few_windows`）。

    **2026-09-13 12:0x に 5か所目**（節ごとの門・`main_split_drawn`）が足され、
    同じ口を通しています。**門を 1つ 足す回は、この数も 1つ 上げること。**
    """
    cut = _at("2026-09-13 02:42")
    k = len([r for r in M.rounds() if r >= cut])
    # **周は毎周 増えます** —— 幅を刻で固定すると、この検査はいつか窓が 2つ になって黙ります。
    # 端が 2つ（＝ 窓 1つ）になる幅を、そのつど数から取ること。
    out = M.report(laps=k - 1, n=2, after=cut)
    assert out.count("まだ測れません") == 5      # 字の門・節ごと・4塊・塊ごと・本の節
    assert "引かれません（直近 2窓" not in out
