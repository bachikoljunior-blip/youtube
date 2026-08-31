"""サムネイル生成。

CTR はタイトルより効く。狙いは「小さくても2語で読める」こと。
1280x720 / 2MB 未満（YouTube の上限）に収める。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

from .util import run

W, H = 1280, 720
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    # 最後の砦。太さは足りないが、少なくとも日本語は出る。
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
]
ACCENT = (255, 204, 0)   # 既定。動画のテーマ色を渡せばそちらを使う
MOSAIC_W = 80            # 背景をいったんここまで縮める。字形が残らない幅

# **背景の行き先**（平均輝度・0〜255）。**掛け算ではなく行き先で決める**理由は
# `_base_image()` の中に書いてあります。46 は「白い字が十分に立ち、かつ
# 一覧の中で黒い長方形に見えない」ところ。**素材の明るさに依らず、ここへ来ます。**
BG_TARGET_LUMA = 46.0
# **挟む幅は広く取ります。** 狭いと、そこで頭打ちになった素材の明るさが
# そのまま出来上がりに漏れ、**行き先で決める意味が消えます**
# （実測: 0.25〜3.20 では、ほぼ白の素材が 61、ほぼ黒の素材が 29 になり、
#  行き先 46 に届きませんでした ―― `tests/test_thumbnail_not_black.py`）。
# **粒は心配ありません** —— 明るくするのは `MOSAIC_W` で潰して
# ぼかした**あと**なので、持ち上げる粒がそもそも残っていません。
BG_GAIN_MIN = 0.10       # 明るい素材を落とせる下限
BG_GAIN_MAX = 6.00       # 暗い素材を持ち上げる上限

# **題材の1行**（`kicker`）。本文の 120〜150 に対して十分に小さく ——
# 同じ大きさで3行 並べると、どれが結論か分からなくなります。
KICKER_SIZE = 62
KICKER_GAP = 30


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    raise RuntimeError(
        "日本語フォントが見つかりません。Ubuntu なら `sudo apt-get install -y fonts-noto-cjk`"
    )


def _base_image(source: Path, work: Path) -> Image.Image:
    """素材が動画ならフレームを1枚抜き、字が**原理的に残らない**ところまで潰す。

    ここは**背景**であって、情報を載せる場所ではない。

    この処理は2回壊れている。1回目は 1.5 秒の位置から抜いていて1枚目の結論が
    そのまま読めた。抜く位置を後ろにずらして直したつもりが、2回目は中央の
    スライドが stat（巨大な数字1つ）で、ぼかし22でも形が残り、重ねた文字と
    同じ数字が背後に二重に見えた。

    「強くぼかす」で直そうとしたのが間違い。ぼかしは文字の大きさに対して
    相対的で、160px の数字1つは 22 のぼかしでは消えない。**大きさに依存しない
    方法**でないと、また同じ壊れ方をする。

    だから解像度そのものを落とす。幅80pxまで縮めれば、元が何ptだろうと
    字形は情報として消える。そこから引き伸ばして色の面だけを残す。
    """
    if source.suffix.lower() in (".mp4", ".mov", ".webm"):
        frame = work / "thumb_frame.jpg"
        # 1枚目を避ける。冒頭の結論と文字がぶつかるため。
        run(["ffmpeg", "-y", "-ss", "25", "-i", str(source), "-frames:v", "1", str(frame)])
        if not frame.exists():   # ショートなど短いものは冒頭から
            run(["ffmpeg", "-y", "-ss", "3", "-i", str(source), "-frames:v", "1", str(frame)])
        source = frame

    img = Image.open(source).convert("RGB")
    # 中央寄せでクロップ
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))

    # 縮めてから戻す。字の大きさに関係なく、字形が情報として消える。
    small = img.resize((MOSAIC_W, round(H * MOSAIC_W / W)), Image.BILINEAR)
    img = small.resize((W, H), Image.BILINEAR)
    img = img.filter(ImageFilter.GaussianBlur(12))

    # **明るさは掛け算ではなく、行き先を決めて合わせる**（2026-08-31 に直した）。
    #
    # ここは長らく `Brightness(0.42)` の**固定の掛け算**でした。掛け算は
    # **元の明るさに対して相対的**なので、暗いスライドから作った本は
    # **ほぼ真っ黒**になります（実測: `UIWHsypOPPg` の控えは、**字の無いところで
    # 平均輝度 7〜16/255** ＝ 一覧の中では黒い長方形。字は読めても、面が死んでいます）。
    #
    # **これは、この file の上の docstring が1度 踏んだのと同じ形の間違いです** ——
    # あちらは「ぼかしは字の大きさに対して相対的」で、`MOSAIC_W` という
    # **大きさに依存しない方法**に替えて直りました。**明るさも同じで、
    # 元の明るさに依存しない方法**でないと、素材ごとに出来上がりが振れます。
    #
    # だから**行き先の平均輝度を決めて、そこへ合わせます。** 素材が暗くても
    # 明るくても、背景は同じ濃さになり、白と accent の字が同じだけ立ちます。
    # 上限を付けているのは、暗い素材を持ち上げすぎて粒が出るのを避けるため。
    stat = ImageStat.Stat(img.convert("L"))
    mean = max(stat.mean[0], 1.0)
    img = ImageEnhance.Brightness(img).enhance(
        min(BG_GAIN_MAX, max(BG_GAIN_MIN, BG_TARGET_LUMA / mean)))
    img = ImageEnhance.Color(img).enhance(1.15)
    return img


def _draw_outlined(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, stroke=10) -> None:
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(12, 12, 16))


def create(source: Path, line1: str, line2: str, out_path: Path, work: Path,
           accent: tuple[int, int, int] | None = None,
           kicker: str | None = None) -> Path:
    """accent には動画のテーマ色を渡す。渡さないと本文と色が食い違う。

    `kicker` は**題材そのもの**を1行で書く欄（省略可）。

    ## なぜ足したか（2026-08-31）

    `UIWHsypOPPg` の控えを一覧の大きさで見たら、載っていたのは
    **「元金0円が108回 / 113,608円」の2行だけ**でした。**数字は合っていますが、
    何の話かがどこにも書いてありません** —— 住宅ローンとも、変動金利とも、
    5年ルールとも、1文字も言っていない。**流れてくる側は、自分に関係が
    あるかどうかを判断できません。**

    2行の型は「小さくても2語で読める」ために選ばれたもので、そこは正しい。
    **足りなかったのは、その2語が何についてかのほう**です。だから
    **本文の字を小さくせずに、上の空きへ題材を1行**入れます
    （実測: 字の無い上の帯が 150px ぶん空いていました）。

    **kicker の中身はテーマごとに違います**（型ではなく、その本の題材）。
    渡さなければ、これまでと1ピクセルも変わりません。
    """
    accent = accent or ACCENT
    img = _base_image(source, work)
    draw = ImageDraw.Draw(img)

    # 左端のアクセントバー
    draw.rectangle([(0, 0), (18, H)], fill=accent)

    size1 = 150 if len(line1) <= 7 else 120
    size2 = 150 if len(line2) <= 7 else 120
    f1, f2 = _font(size1), _font(size2)

    h1 = draw.textbbox((0, 0), line1 or "　", font=f1)[3]
    h2 = draw.textbbox((0, 0), line2 or "　", font=f2)[3]
    gap = 26

    fk = hk = None
    if kicker:
        # **本文より明らかに小さく。** 同じ大きさで3行 並べると、
        # どれが結論か分からなくなります（読む順が決まらない）。
        fk = _font(KICKER_SIZE if len(kicker) <= 18 else KICKER_SIZE - 10)
        hk = draw.textbbox((0, 0), kicker, font=fk)[3]

    block = h1 + h2 + gap + ((hk + KICKER_GAP) if hk else 0)
    top = (H - block) // 2 - 10

    if kicker:
        _draw_outlined(draw, (72, top), kicker, fk, (236, 238, 242), stroke=7)
        top += hk + KICKER_GAP

    if line1:
        _draw_outlined(draw, (72, top), line1, f1, accent)
    if line2:
        _draw_outlined(draw, (72, top + h1 + gap), line2, f2, (255, 255, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    quality = 92
    while quality >= 60:
        img.save(out_path, "JPEG", quality=quality, optimize=True)
        if out_path.stat().st_size < 2_000_000:
            break
        quality -= 8
    return out_path
