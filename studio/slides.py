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


_PUNCT = "、。」）"


def _breaks(text: str) -> tuple[set[int], set[int]]:
    """(折ってよい位置, 数字のかたまりの中の位置)。折ってよいのは janome の語の頭のうち、助詞・助動詞・非自立・接尾・
    複合名詞の続き・句読点の前でない所と、数字のかたまりの両端。
    実測 09/06 17:3x（hourly）: 字幕「国の決\nまりで」が語の途中で折れた（読めるので置いた）。"""
    from janome.tokenizer import Tokenizer
    global _tok
    if _tok is None:
        _tok = Tokenizer()
    ok: set[int] = set()
    pos = 0
    prev = ("記号", "")
    for tk in _tok.tokenize(text):
        j = text.find(tk.surface, pos)
        if j < 0:
            break
        pos = j + len(tk.surface)
        p1, p2 = (tk.part_of_speech.split(",") + ["", ""])[:2]
        glued = (p1 in ("助詞", "助動詞", "記号")          # 助詞・助動詞は前の語につく（国の|決まり ではなく 国の決まり）
                 or p2 in ("非自立", "接尾")               # もらい続けた・教えてください・定期便
                 or (p1 == "名詞" and prev[0] == "名詞")   # 複合名詞（健康保険料・ねんきん定期便）
                 or prev == ("助詞", "終助詞"))            # janome が「ねんきん」を ねん(終助詞)+きん に割る
        if j and not glued:
            ok.add(j)
        prev = (p1, p2)
    inside: set[int] = set()
    for m in _NUM.finditer(text):
        ok.add(m.start()); ok.add(m.end())
        inside.update(range(m.start() + 1, m.end()))
    return {p for p in ok if p not in inside and 0 < p < len(text) and text[p] not in _PUNCT}, inside


_tok = None


def wrap_words(text: str, n: int, slack: int = 8) -> list[str]:
    """語の切れ目で折る。切れ目が遠すぎて行が n-slack より短くなるときだけ、字で折る（数字のかたまりと句読点は守る）。"""
    if "\n" in text:
        return [ln for part in text.split("\n") for ln in wrap_words(part, n, slack)]
    brk, inside = _breaks(text)
    lines, i = [], 0
    while len(text) - i > n:
        cands = [p for p in brk if i < p <= i + n]
        p = max(cands) if cands else 0
        if p - i < n - slack:
            p = i + n
            while p > i + 1 and (p in inside or text[p] in _PUNCT):
                p -= 1
        lines.append(text[i:p]); i = p
    if i < len(text):
        lines.append(text[i:])
    return [ln for ln in lines if ln]


def wrap(text: str, n: int, max_lines: int | None = None) -> list[str]:
    """字幕・小さい字の折り返し。まず語の切れ目で折り、行数が `max_lines` を越えるときだけ字で折る（旧 09/05 の形）。"""
    ws = wrap_words(text, n)
    if all(len(ln) <= n for ln in ws) and (max_lines is None or len(ws) <= max_lines):
        return ws
    return wrap_chars(text, n)


def wrap_chars(text: str, n: int) -> list[str]:
    """字で折る（数字のかたまりは守る・句読点は行頭に置かない）。09/05 の形。旧の「行頭の句読点を前の行へ足す」は
    行が n+1 字になっていた（実測 09/06 19:5x: 60字 の字幕で 17字 の行）。"""
    return wrap_words(text, n, slack=0)


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
        # 16字×4行・54px に語で折って入るならそれ。入らなければ 18字×4行・48px（say の上限 70字 が収まる）。
        # それでも 5行 になるなら字で折る（09/05 の形）。前は 64字 を越えた say だけ 18字 だった
        chars, px = SUB_CHARS, 54
        lines = wrap_words(say, chars)
        if len(lines) > 4:
            chars, px = 18, 48
            lines = wrap_words(say, chars)
        if len(lines) > 4:
            lines = wrap_chars(say, chars)
        lines = lines[:4]
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
