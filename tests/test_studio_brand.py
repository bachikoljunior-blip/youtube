"""本の中の名乗り（2026-09-18 00:3x・optimizer・Fable 5.1・ultracode。名は `common.BRAND_NAME` の 1か所）。

登録/1,000再生 が 0.35（corpus 中央 5.29）で、縛っているのは登録。チャンネルの題は API で変えられず
（`channel_rename_refused`）、手はオーナーの Studio に在る。**本の側は待たずに名乗る**:
毎コマ 左上の札（`slides.brand_strip`）と、出口の声（`script.default_cta`）。
"""
from pathlib import Path

from PIL import Image, ImageDraw

from studio import cli, common, script, slides


def _near(px, rgb, tol=12) -> bool:
    return all(abs(a - c) <= tol for a, c in zip(px[:3], rgb))


def test_名は1か所():
    assert cli.RENAME_TARGET is common.BRAND_NAME
    assert common.BRAND_NAME and "年金" in common.BRAND_NAME


def test_縦のコマに札が出る(tmp_path: Path):
    out = slides.slide("見出し", "", "字幕。", 1, 3, None, tmp_path / "a.png")
    im = Image.open(out).convert("RGB")
    # 札の色（BRAND_COLOR）が左上（y 100〜158・x 60〜）に在る
    assert _near(im.getpixel((70, 128)), slides.BRAND_COLOR), im.getpixel((70, 128))
    # tag の札（まん中・x ≥ 438）と重ならない: x 440 の同じ高さは札の色ではない
    assert not _near(im.getpixel((440, 128)), slides.BRAND_COLOR), im.getpixel((440, 128))


def test_横のコマにも札が出る(tmp_path: Path):
    out = slides.slide("見出し", "", "字幕。", 1, 3, None, tmp_path / "b.png", form="long")
    im = Image.open(out).convert("RGB")
    assert _near(im.getpixel((70, 34)), slides.BRAND_COLOR), im.getpixel((70, 34))


def test_陰性対照_brand_False_は前の絵のまま(tmp_path: Path):
    a = slides.slide("見出し", "小さい字", "字幕の文です。", 2, 5, None, tmp_path / "a.png", brand=False)
    im = Image.open(a).convert("RGB")
    bg = slides.background(None).getpixel((70, 128))
    assert _near(im.getpixel((70, 128)), bg, tol=2)


def test_札は板や図と同じ所を使わない():
    d = ImageDraw.Draw(Image.new("RGBA", (1080, 1920)))
    x0, y0, x1, y1 = slides.brand_strip(d, slides.SHORT)
    # 進み具合の線（y 70〜82）より下・板が在るコマの show の箱（top-50 ＝ 190）より上・tag の札（x ≥ 438）より左
    assert y0 >= 84 and y1 <= 190
    assert x1 < 438
    # 空の名は描かない
    assert slides.brand_strip(d, slides.SHORT, name="") == (0, 0, 0, 0)


def test_出口の型は名を言う():
    c = script.default_cta()
    assert c.say.startswith(common.BRAND_NAME)
    assert len(c.say) <= script.MAX_SAY
    assert script.has_cta(c)
    assert c.show.replace("\n", "") == common.BRAND_NAME


def test_出口の型は名の読みを連れてくる():
    # 名の漢字は、型の辞書（CTA_YOMI）と、出口の型が前から持っていた語（どの本の yomi にも在る）で全部 覆える
    before = {"年金": "ねんきん", "税金": "ぜいきん", "計算": "けいさん", "毎日": "まいにち",
              "出": "だ", "登録": "とうろく", "分": "ぶん"}
    left = script.uncovered_kanji(script.default_cta().say, {**before, **script.CTA_YOMI})
    assert not left, left
    # 陽性対照: 型の辞書を外すと名の漢字が残る
    assert script.uncovered_kanji(script.default_cta().say, before)
