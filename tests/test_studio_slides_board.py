"""studio/slides.py の まん中の板（board）と札（tag）。2026-09-10 13:2x・hourly・Fable。

オーナー 12:4x「画面を有効活用できてないと思う。今のナレーションの説明だけじゃ見てる人が整理しながら
理解していくのむずいと思うよ」（受け取り帳 `52f141fa`）。
実測 09/10 の本の絵: 上の板 y 465〜975・字幕 1108〜1450 で、上 90〜465 と まん中 が絵だけだった。
板が在るコマは show を上へ寄せ、その下に「そのコマまでの前提と数の積み上がり」を描く。
板の無い台本は前の絵のまま（公開ずみの本の見た目を変えない）。
"""
from pathlib import Path

import pytest
from PIL import Image

from studio import critic, script, slides


def test_板は字幕の上に収まる():
    # 5行 でも 字幕 4行 の上端（1108）より上で終わる
    px, lh, top = slides.board_layout(5, show_bottom=540)
    assert top >= slides.BOARD_TOP_MIN
    assert top + 60 + lh * 5 <= slides.BOARD_BOTTOM < 1108
    # 行が少なければ字は大きい（60px）・多ければ小さくなる
    assert slides.board_layout(2, 540)[0] == 60
    assert slides.board_layout(5, 540)[0] <= 60


def test_板はshowが高くても字幕に乗らない():
    px, lh, top = slides.board_layout(5, show_bottom=700)
    assert top == 750
    assert top + 60 + lh * 5 <= 1108


def test_板の無い呼び出しは前の形のまま(tmp_path: Path):
    out = slides.slide("見出し", "小さい字", "字幕の文です。", 1, 3, None, tmp_path / "a.png")
    im = Image.open(out)
    assert im.size == (1080, 1920)
    # 板の無いコマ: 上の板（y 465〜975）と字幕（1327〜）のあいだ y 1050 は背景の色のまま（板の黒い箱は無い）
    r, g, b = im.getpixel((540, 1050))[:3]
    bg = slides.background(None).getpixel((540, 1050))
    assert abs(r - bg[0]) <= 2 and abs(g - bg[1]) <= 2 and abs(b - bg[2]) <= 2


def test_板と札が描かれる(tmp_path: Path):
    out = slides.slide("5年で\n10万円ふえる", "", "字幕。", 7, 11, None, tmp_path / "b.png",
                       tag="結論", board=["1年 66歳 → +2万円", "2年 67歳 → +4万円", "5年 70歳 → +10万円"])
    im = Image.open(out).convert("RGB")
    # 板の箱（黒 140/255）が まん中に在る ＝ 背景より暗い
    bg = slides.background(None).getpixel((540, 700))
    px, lh, top = slides.board_layout(3, 0)
    y = top + 15
    r, g, b = im.getpixel((900, y))
    assert (r + g + b) < sum(bg) - 30
    # 札の色（結論 ＝ 赤系）が show の上に在る
    tag_rgb = slides.TAG_COLORS["結論"]
    found = any(abs(im.getpixel((x, yy))[0] - tag_rgb[0]) < 12 and abs(im.getpixel((x, yy))[1] - tag_rgb[1]) < 12
                for x in range(380, 700, 8) for yy in range(90, 260, 6))
    assert found, "札の色が show の上に見つからない"


def _script(**seg) -> script.Script:
    base = dict(say="たとえば、月収30万円の人が、65歳から70歳まではたらきます。", show="月収30万円", sub="")
    base.update(seg)
    return script.Script(id="t", date="2026-09-11", title="t #Shorts", takeaway="t",
                         yomi={"月収": "げっしゅう"}, segments=[script.Segment(**base)] * 5)


def test_lint_板の行数と字数の門():
    ok = _script(tag="前提", board=["たとえば 月収30万円", "65歳から70歳まではたらく"])
    assert not [p for p in ok.problems() if "board" in p or "tag" in p]
    # 陽性対照: 6行 は止まる・15字 の行は止まる・知らない札は止まる・小数は止まる
    assert any("6行" in p for p in _script(board=["a"] * 6).problems())
    assert any("15字" in p for p in _script(board=["あ" * 15]).problems())
    assert any("tag" in p for p in _script(tag="ポイント").problems())
    assert any("点・小数" in p for p in _script(board=["1.5倍"]).problems())


def test_critique_に札と板が渡る():
    s = _script(tag="前提", board=["たとえば 月収30万円", "65歳から70歳まではたらく"])
    text = critic.critique_screen(s)
    assert "[札: 前提]" in text
    assert "板（そのコマまでの積み上がり" in text and "たとえば 月収30万円 ／ 65歳から70歳まではたらく" in text
    # 陽性対照: 板の無い台本には「板」の行が出ない
    assert "板（" not in critic.critique_screen(_script())


def test_古い台本は読める():
    # tag / board の無い JSON（公開ずみの 5本）はそのまま通る
    s = script.Script.model_validate({"id": "t", "date": "2026-09-10", "title": "t #Shorts", "takeaway": "t",
                                      "segments": [{"say": "a"}] * 5})
    assert s.segments[0].tag == "" and s.segments[0].board == []
