"""画面。縦 1080x1920。1コマ = 1枚の PNG。

  上 1/3    大きい字（show）と小さい字（sub）—— 数字・見出し
  下        字幕（say をそのまま。1行 16字・3行まで。下から 420px は Shorts の UI と重なるので空ける）
  背景      GPT Image 2.0 の絵（届いていれば）か、単色のグラデーション
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FONT_BLACK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SUB_BOTTOM = H - 470       # 字幕の下端
SUB_CHARS = 16


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=0)


# 数字のかたまり（「10万円」「5万5千円」「12か月」）は行の途中で折らない。
# 実測 09/05: 18字×4行 の字幕で「1\n0万円」「10万\n円」が出た（sheet.png）。
# 実測 09/06 15:0x: 「毎\n月15万円」（数字の前の「毎月」「約」も数字と一緒に持つ）。
_NUM = re.compile(r"(?:毎月|毎年|約|月|年)?[0-9０-９][0-9０-９,，.]*(?:[万千億][0-9０-９]*)*(?:か月|カ月|ヶ月|円|人|歳|日|回|割|％|%|倍|年)?")


def _tokens(text: str) -> list[str]:
    out, i = [], 0
    while i < len(text):
        m = _NUM.match(text, i)
        if m and m.end() > i:
            out.append(m.group()); i = m.end()
        else:
            out.append(text[i]); i += 1
    return out


def wrap(text: str, n: int) -> list[str]:
    if "\n" in text:
        return [ln for part in text.split("\n") for ln in wrap(part, n)]
    lines, cur = [], ""
    for tok in _tokens(text):
        if len(cur) + len(tok) > n and cur:
            lines.append(cur)
            cur = ""
        cur += tok
        if len(cur) >= n:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    # ぶら下がり: 行頭の「、。」を前の行へ
    fixed: list[str] = []
    for ln in lines:
        if fixed and ln and ln[0] in "、。」）":
            fixed[-1] += ln[0]
            ln = ln[1:]
        if ln:
            fixed.append(ln)
    return fixed


def background(image: Path | None) -> Image.Image:
    if image and image.exists():
        im = Image.open(image).convert("RGB")
        # cover-fit
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        x, y = (im.width - W) // 2, (im.height - H) // 2
        im = im.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(2))
        # 暗くして字を立たせる
        dark = Image.new("RGB", (W, H), (0, 0, 0))
        return Image.blend(im, dark, 0.45)
    im = Image.new("RGB", (W, H), (18, 30, 48))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(18 + 20 * t), int(30 + 30 * t), int(48 + 60 * t)))
    return im


def draw_text_block(d: ImageDraw.ImageDraw, lines: list[str], fnt, top: int, fill, stroke=(0, 0, 0), stroke_w=0, gap=1.25) -> int:
    y = top
    for ln in lines:
        bbox = d.textbbox((0, 0), ln, font=fnt)
        w = bbox[2] - bbox[0]
        d.text(((W - w) // 2, y), ln, font=fnt, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)
        y += int(fnt.size * gap)
    return y


def slide(show: str, sub: str, say: str, i: int, n: int, image: Path | None, out: Path,
          progress: bool = True) -> Path:
    im = background(image)
    d = ImageDraw.Draw(im, "RGBA")
    # 進み具合
    if progress and n > 1:
        d.rectangle([60, 70, W - 60, 82], fill=(255, 255, 255, 70))
        d.rectangle([60, 70, 60 + int((W - 120) * i / n), 82], fill=(255, 210, 60, 255))
    # 大きい字（行は書き手の \n で決まる。幅に収まるまで字を小さくする。語の途中で折らない）
    if show:
        lines = show.split("\n")
        size = 124
        while size > 64:
            fnt = font(FONT_BLACK, size)
            if max(d.textbbox((0, 0), ln, font=fnt)[2] for ln in lines) <= W - 140:
                break
            size -= 8
        fnt = font(FONT_BLACK, size)
        block_h = int(len(lines) * size * 1.25) + (int(56 * 1.25 * len(wrap(sub, 16))) + 20 if sub else 0)
        top = 700 - block_h // 2
        d.rounded_rectangle([40, top - 50, W - 40, top + block_h + 40], radius=30, fill=(0, 0, 0, 110))
        y = draw_text_block(d, lines, fnt, top, (255, 255, 255), stroke_w=6)
        if sub:
            y = draw_text_block(d, wrap(sub, 16), font(FONT_BOLD, 56), y + 20, (255, 225, 120), stroke_w=4)
    # 字幕
    if say:
        # 64字 までは 16字×4行・54px。それ以上は 18字×4行・48px（say の上限 70字 が収まる）
        chars, px = (SUB_CHARS, 54) if len(say) <= SUB_CHARS * 4 else (18, 48)
        lines = wrap(say, chars)[:4]
        fnt = font(FONT_BOLD, px)
        lh = int(px * 1.35)
        box_h = lh * len(lines) + 50
        top = SUB_BOTTOM - box_h
        d.rounded_rectangle([50, top, W - 50, SUB_BOTTOM], radius=24, fill=(0, 0, 0, 165))
        draw_text_block(d, lines, fnt, top + 25, (255, 255, 255), gap=1.35)
    im.convert("RGB").save(out, "PNG", optimize=True)
    return out


def contact_sheet(pngs: list[Path], out: Path, cols: int = 4) -> Path:
    thumbs = [Image.open(p).resize((270, 480)) for p in pngs]
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 270, rows * 480), (30, 30, 30))
    for k, t in enumerate(thumbs):
        sheet.paste(t, ((k % cols) * 270, (k // cols) * 480))
    sheet.save(out)
    return out
