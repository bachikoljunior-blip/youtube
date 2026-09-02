"""**「人間にわかるか」を人の側の数に当てる所**（`src/clarity.py`・2026-09-02）。

オーナー原文（2026-09-02・`CLAUDE.md` 冒頭「固定その3」）:

> **「動画内の説明は人間にわかるようにして」**

**この検査が守っているのは、道具の正しさではなく「読み違えない形」のほうです。**

    陽性対照が生きていること          ← 死んだ計器の「関係なし」を、結論と読ませない
    物差しに**向き**が書いてあること   ← 向きが無いと、どんな数でも「そういうもの」で通る
    報告が n を必ず添えること         ← rho だけの引用が、この repo の常習犯
    `src/` から `scripts/deixis_count` を import しないこと
                                    ← import した瞬間、あの道具の (c) の札が黙って剥がれる
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import clarity  # noqa: E402


def _curve(points):
    return [(x, y, 0.5) for x, y in points]


def test_話速が_pipeline_と同じ():
    """時間割は文字数 ÷ 話速。**2か所に別の値が在ると、位置がずれます。**"""
    src = (ROOT / "src" / "pipeline.py").read_text()
    m = re.search(r"^CHARS_PER_SECOND\s*=\s*([\d.]+)", src, re.M)
    assert m, "pipeline.CHARS_PER_SECOND が読めません"
    assert float(m.group(1)) == clarity.CHARS_PER_SECOND


#: 語彙の正本が置いてある道具。**道の形（`scripts` + `/` + 名前 + `.py`）を
#: この file に literal で書かないこと** —— `retro._CALL_RE` がそれを「撃つ側」と
#: 読み、あの道具の (c)（わざと寝かせてある）の札が黙って剥がれます。
#: 組み立てて渡します（2026-09-02 に踏んで、`tests/test_unwired_tools.py` が2件 落ちた）。
_VOCAB_SRC = ROOT / "scripts" / "deixis_count.py"


def test_指示語の語彙が_正本と同じ():
    """正本はあちらの `WIDE`。**写しがずれたら、別の物を数えています。**"""
    src = _VOCAB_SRC.read_text()
    body = src[src.index("NARROW = "):]
    body = body[:body.index("\ndef ")]
    ns: dict = {}
    exec(compile(body, "<vocab>", "exec"), ns)      # noqa: S102
    assert ns["WIDE"] == clarity.DEIXIS_WIDE


def test_srcからscriptsをimportしていない():
    """**`retro._CALL_RE` は「道を書いた側」を撃つ側とみなします。**

    語彙の正本の道具は (c)（わざと寝かせてある）で、
    `tests/test_unwired_tools.py` がその札を数えています。
    `src/clarity.py` があの道を書くと、**札が黙って剥がれます**
    （2026-09-02 に実際に踏んで、検査が2件 落ちました）。

    **見るのは「道の形」だけです** —— 名前を地の文で書くのは害がありません
    （`_CALL_RE` は `scripts` + `/` + 名前 + `.py` の形にしか当たりません）。
    """
    road = "scripts" + "/" + "deixis_count" + ".py"
    for rel in (("src", "clarity.py"), ("tests", "test_clarity.py")):
        body = (ROOT / rel[0] / rel[1]).read_text()
        assert road not in body, f"{rel[1]} が道の形で書いています: {road}"


def test_spearman_は同順位を潰す():
    # 指示語は 0 だらけ。同順位を潰さないと、rho が意味を失います。
    assert clarity.spearman([0, 0, 0, 0], [1, 2, 3, 4]) == 0.0
    assert clarity.spearman([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert clarity.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0


def test_有意の門と要る本数が逆向き():
    n = clarity.needed_for(0.30)
    assert abs(clarity.significant_at(n) - 0.30) < 0.01
    # 小さい関係ほど、たくさん要る
    assert clarity.needed_for(0.20) > clarity.needed_for(0.30)


def test_curve_at_は線形に読む():
    c = _curve([(0.0, 1.0), (1.0, 0.0)])
    assert abs(clarity.curve_at(c, 0.5) - 0.5) < 1e-9
    assert clarity.curve_at(c, 0.0) == 1.0
    assert clarity.curve_at(c, 2.0) == 0.0      # 端の外は端の値
    assert clarity.curve_at([], 0.5) == 0.0


def test_コマの時間割が_文字数に比例する():
    rows = clarity.segment_rows(["あ" * 52, "い" * 52])
    assert len(rows) == 2
    assert abs(rows[0]["sec"] - 10.0) < 1e-9
    assert abs(rows[0]["end"] - 0.5) < 1e-9
    long = clarity.segment_rows(["あ" * 52, "い" * 156])
    assert abs(long[0]["end"] - 0.25) < 1e-9


def test_物差しに向きが必ず書いてある():
    """**向きの無い物差しは、どんな数が出ても「そういうもの」で通ります。**"""
    assert clarity.MEASURES, "物差しが空です"
    for name, (fn, sign) in clarity.MEASURES.items():
        assert sign in (-1, 1), f"{name} の向きが ±1 ではありません"
        assert callable(fn)


def test_配線ずみの物差しが_表に居る():
    """`WIRED` は `verify._check_ear_load` の物差し。**表から消えると比べられません。**"""
    assert clarity.WIRED in clarity.MEASURES
    ear = (ROOT / "src" / "verify.py").read_text()
    assert "EAR_LOAD_MAX" in ear


def test_出口が2つ以上ある():
    """1つだけだと、その出口の癖を物差しの性質と読み違えます。"""
    assert len(clarity.OUTCOMES) >= 2


def test_報告は_n_を必ず添える():
    lines = "\n".join(clarity.report_lines())
    assert "本" in lines
    # 数が出る回は、必ず陽性対照と門も出る
    if "陽性対照" in lines:
        assert "rho" in lines


def test_陽性対照が生きている():
    """**落ちは前に寄る。** これが出ないうちは、下の数を読んではいけません。

    実測 2026-09-02: rho = -0.468（69本・410コマ）。
    **門 -0.20 は「半分になっても通る」ゆるさ**で置いています。
    赤くなったら、先に疑うのは `segment_rows` の時間割のほうです。
    """
    bs = clarity.books()
    if len(bs) < 20:
        return          # 控えかカーブが無い環境では何も言わない
    rho, ncoma = clarity.control(bs)
    assert ncoma > 0
    assert rho <= clarity.CONTROL_MAX_RHO, (
        f"陽性対照が {rho:+.3f}（門 {clarity.CONTROL_MAX_RHO}）。"
        "計器が死んでいます —— `segment_rows` の時間割を先に疑うこと")


def test_台帳に前提が置いてある():
    """**測っただけで終わらせないため。** 判定できる日と条件が台帳に在ること。"""
    y = (ROOT / "config" / "hypotheses.yaml").read_text()
    assert "clarity_ear_load_sign" in y
