"""サムネイル生成。

CTR はタイトルより効く。狙いは「小さくても2語で読める」こと。
1280x720 / 2MB 未満（YouTube の上限）に収める。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

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
    img = ImageEnhance.Brightness(img).enhance(0.42)
    img = ImageEnhance.Color(img).enhance(1.15)
    return img


def _draw_outlined(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, stroke=10) -> None:
    draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(12, 12, 16))


def create(source: Path, line1: str, line2: str, out_path: Path, work: Path,
           accent: tuple[int, int, int] | None = None) -> Path:
    """accent には動画のテーマ色を渡す。渡さないと本文と色が食い違う。"""
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
    top = (H - (h1 + h2 + gap)) // 2 - 10

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
