"""隣り合う2枚が同じ画に見えていないか、と、計算式が画面に出ているか。

**なぜこの2つを同じファイルで見るか。** どちらも 2026-08-15 の独立評価で
**意図を渡していない3体が独立に指摘**したのに、**機械の検査はどこも見ていなかった**もの。
8/15 16:0x の回では6体が「同じ見出しが2枚続く」を書いている（通算9体・2回の持ち越し）。

**穴の種類が同じ**なので、塞ぎ方も1か所にまとめる ——
「人が見れば一目で分かる欠陥を、機械が素通りさせる」。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import verify, visuals


def _script(*visuals_):
    return {"segments": [{"narration": "…", "visual": v} for v in visuals_]}


def _ok_formula():
    return {"kind": "stat", "headline": "退職金の無税枠", "stat": "800万円",
            "formula": "800万円 ＝ 40万円 × 20年"}


# ---------------------------------------------------------------- 隣り合う2枚

def test_同じ見出しが隣り合うと落ちる():
    s = _script(
        {"kind": "stat", "headline": "退職金の無税枠", "stat": "800万円"},
        {"kind": "chart", "headline": "退職金の無税枠", "bars": [{"display": "800万円"}]},
    )
    problems = verify._check_adjacent_repeat(s)
    assert any("見出しが同一" in p for p in problems), problems


def test_離れた位置の同じ見出しは落とさない():
    """まとめや対比として成立するので、隣り合っていなければ通す。"""
    s = _script(
        {"kind": "stat", "headline": "退職金の無税枠", "stat": "800万円"},
        {"kind": "chart", "headline": "勤続年数で変わる", "bars": [{"display": "800万円"}]},
        {"kind": "stat", "headline": "退職金の無税枠", "stat": "800万円"},
    )
    assert not any("見出しが同一" in p for p in verify._check_adjacent_repeat(s))


def test_見出しの空白の差は同一とみなす():
    s = _script(
        {"kind": "stat", "headline": "退職金の 無税枠"},
        {"kind": "stat", "headline": "退職金の無税枠"},
    )
    assert any("見出しが同一" in p for p in verify._check_adjacent_repeat(s))


def test_棒が1本増えるだけの2枚は落ちる():
    """独立評価の3体が書いた文言そのもの。"""
    s = _script(
        {"kind": "chart", "headline": "勤続10年", "bars": [
            {"display": "400万円"}, {"display": "600万円"}]},
        {"kind": "chart", "headline": "勤続20年", "bars": [
            {"display": "400万円"}, {"display": "600万円"}, {"display": "800万円"}]},
    )
    problems = verify._check_adjacent_repeat(s)
    assert any("包含関係" in p for p in problems), problems


def test_棒の中身が違えば通る():
    s = _script(
        {"kind": "chart", "headline": "勤続10年", "bars": [
            {"display": "400万円"}, {"display": "600万円"}]},
        {"kind": "chart", "headline": "勤続20年", "bars": [
            {"display": "800万円"}, {"display": "1000万円"}]},
    )
    assert not any("包含関係" in p for p in verify._check_adjacent_repeat(s))


def test_chart以外の隣り合わせは棒の判定にかけない():
    s = _script(
        {"kind": "stat", "headline": "あ", "bars": [{"display": "1"}]},
        {"kind": "stat", "headline": "い", "bars": [{"display": "1"}]},
    )
    assert not any("包含関係" in p for p in verify._check_adjacent_repeat(s))


# ---------------------------------------------------------------- 計算式

def test_式が1枚も無いと落ちる():
    s = _script({"kind": "stat", "headline": "退職金の無税枠", "stat": "800万円"})
    problems = verify._check_formula_shown(s)
    assert any("計算式が1枚も画面に出ていません" in p for p in problems), problems


def test_式が1枚あれば通る():
    assert verify._check_formula_shown(_script(_ok_formula())) == []


def test_数字の再掲は式ではない():
    v = dict(_ok_formula(), formula="800万円")
    problems = verify._check_formula_shown(_script(v))
    assert any("`=` が無い" in p for p in problems), problems


def test_演算子の無い言い換えは落ちる():
    v = dict(_ok_formula(), formula="合計 ＝ 35万9318円")
    problems = verify._check_formula_shown(_script(v))
    assert any("演算子が無い" in p for p in problems), problems


def test_数字がほとんど無い式は落ちる():
    v = dict(_ok_formula(), formula="控除額 ＝ 単価 × 年数")
    problems = verify._check_formula_shown(_script(v))
    assert any("数字がほとんど無い" in p for p in problems), problems


def test_半角イコールも受ける():
    v = dict(_ok_formula(), formula="800万円 = 40万円 * 20年")
    assert verify._check_formula_shown(_script(v)) == []


# ------------------------------------------------- めくりの見出し（本当の出どころ）

def _bars(n):
    return [{"label": f"勤続{i}年", "value": float(i), "display": f"{i}00万円"}
            for i in range(1, n + 1)]


def test_めくりで見出しが全コマ同じにならない():
    """**ここが本当の出どころ。** 台本は chart 1枚なので、台本側の検査には
    絶対に出てこない。割っているのは `reveal_variants` のほう。"""
    v = {"kind": "chart", "headline": "勤続年数で変わる枠", "bars": _bars(4)}
    heads = [x["headline"] for x in visuals.reveal_variants(v, 4)]
    assert len(set(heads)) == len(heads), heads


def test_めくりの最終コマも見出しを戻さない():
    """`out[-1] = dict(visual)` で元に戻すと、k=2 のとき2コマとも同じになる。"""
    v = {"kind": "chart", "headline": "勤続年数で変わる枠", "bars": _bars(2)}
    frames = visuals.reveal_variants(v, 2)
    assert frames[0]["headline"] != frames[1]["headline"]
    # 最終コマは棒が全部出ていること（見出しだけ変えて中身は落とさない）
    assert len(frames[-1]["bars"]) == 2


def test_めくりの見出しは枠に収まる():
    v = {"kind": "chart", "headline": "非常に長い見出しをわざと置いてみる場合",
         "bars": _bars(3)}
    frames = visuals.reveal_variants(v, 3)
    # 元の見出しが既に枠を超えているときは、**足さずにそのまま出す。**
    # 削って収めると語の途中で切れる（下の2件がその実例）。
    assert all(f["headline"] == v["headline"] for f in frames), frames


def test_長い元の見出しを削らない():
    """実物で出た: 「10年の境界でふえる日数」→「10年の境界でふえる」。"""
    head = "10年の境界でふえる日数"
    v = {"kind": "chart", "headline": head, "bars": [
        {"label": "自己都合など", "value": 30.0, "display": "30日"},
        {"label": "倒産解雇など", "value": 60.0, "display": "60日"}]}
    for f in visuals.reveal_variants(v, 2):
        assert f["headline"].startswith(head), f["headline"]


def test_長いラベルは切らずに捨てる():
    """実物で出た: 「＋自己都合などの離」（「離職」の途中で切れていた）。"""
    v = {"kind": "steps", "headline": "この計算の前提",
         "items": ["30歳未満であること", "自己都合などの離職で退職していること"]}
    frames = visuals.reveal_variants(v, 2)
    for f in frames:
        assert "の離　" not in f["headline"]
        assert f["headline"] in ("この計算の前提",), f["headline"]


def test_枠に入るラベルは丸ごと出す():
    v = {"kind": "steps", "headline": "この計算の前提",
         "items": ["30歳未満であること", "自己都合などの離職"]}
    frames = visuals.reveal_variants(v, 2)
    assert frames[-1]["headline"] == "この計算の前提　＋自己都合などの離職", frames[-1]["headline"]


def test_めくりの見出しに増えた要素の名前が出る():
    v = {"kind": "chart", "headline": "枠", "bars": _bars(3)}
    frames = visuals.reveal_variants(v, 3)
    assert "勤続3年" in frames[-1]["headline"], frames[-1]["headline"]


def test_式は本文の外に置かれる():
    """`.body` の中に入れるとコマごとに上下に動く。根拠は同じ場所にあること。"""
    html = visuals.build_html(_ok_formula())
    assert 'class="formula"' in html
    assert html.index('class="formula"') > html.index('class="body"')
