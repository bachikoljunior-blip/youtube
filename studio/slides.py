"""画面。縦 1080x1920。1コマ = 1枚の PNG。

  上 1/3    大きい字（show）と小さい字（sub）—— 数字・見出し。その上に札（tag: 前提／決まり／計算／結論／見る所）
  まん中    板（board）—— そのコマまでに出た前提と数の積み上がり（2026-09-10 13:2x・hourly・Fable。
            オーナー 12:4x「画面を有効活用できてないと思う。今のナレーションの説明だけじゃ見てる人が
            整理しながら理解していくのむずいと思うよ」・受け取り帳 `52f141fa`）。
            **板が在るコマだけ** show を上へ寄せて（y 140〜）その下に板を描く。板の無い台本は前の絵のまま
            （公開ずみの本の見た目を変えない）。実測 09/10 の本: 前の形では上の板が y 465〜975・字幕が 1108〜1450 で、
            **上 90〜465 の 375px が進み具合の線しか持っていなかった**。
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
# 実測 09/09 15:5x: 「夫の厚生年金の4分の\n3です」（「N分のM」の分数も1語。09/10 の本のコマ4・sheet.png）。
# 実測 09/10 01:2x: 「はたらいているあいだに、毎年10\n月分の年金から」（09/11 の本のコマ8・sheet.png）。
#   **接尾の一覧に、裸の「月」が無かった** —— 「か月」「カ月」「ヶ月」は在るのに「10月」「10月分」が拾えず、
#   `毎年10` ＋ `月分` の2語に割れていた。「N月」「N月分」は暦の月なので1語（`月分?`）。
#   **並び順は効きません**（陽性対照で確かめた・01:3x）: `月分?` を `か月` より前へ動かしても
#   「6か月」「12か月」「1ヶ月」は割れない —— `月` は「か」に当たれないので、そこで必ず `か月` へ落ちる。
#   最初この註に「か月 より後ろでないと割れる」と書きかけたが、**壊して撃ったら落ちなかった**（§5 の教訓の形3つ目）。
_NUM = re.compile(r"(?:毎月|毎年|約|月|年)?[0-9０-９][0-9０-９,，.]*(?:[万千億][0-9０-９]*)*(?:分の[0-9０-９]+|か月|カ月|ヶ月|円|人|歳|日|回|割|％|%|倍|年|月分?)?")


def _tokens(text: str) -> list[str]:
    out, i = [], 0
    while i < len(text):
        m = _NUM.match(text, i)
        if m and m.end() > i:
            out.append(m.group()); i = m.end()
        else:
            out.append(text[i]); i += 1
    return out


_GLUE_POS = ("助詞", "助動詞", "記号")     # 前の語にくっつける（行頭に来ない）
_GLUE_SUB = ("非自立", "接尾")             # 2つ目の札がこれなら前の語にくっつける（もらい続けた・定期便）
_GLUE_NEXT = ("接頭詞",)                   # 次の語にくっつける（約・毎）
# janome が割る仮名まじりの1語（「ねんきん」→ ねん＋きん）。数字のかたまりと同じく1語として持つ
# 09/09 15:5x: janome が 遺族/厚生/年金 と3語に割るので「遺族厚生\n年金」と折れた（09/10 の本のコマ4）。制度名の複合語は1語として持つ（長い順）
_ATOM = re.compile(r"年金額改定通知書|遺族厚生年金|老齢厚生年金|老齢基礎年金|遺族基礎年金|厚生年金|基礎年金|ねんきん定期便|ねんきんネット|ねんきん")
_tok = None


def _chunks(text: str) -> list[str]:
    """語のかたまり（語＋助詞＋句読点）。行の途中で折らない単位。
    実測 09/06 17:3x: 「国の決\nまりで」（16字で機械的に折ると語の途中で折れる）→ janome で語を切り、
    助詞・助動詞・句読点は前の語に、接頭詞（約）は次の語にくっつける。数字のかたまりは _NUM のまま。"""
    global _tok
    if _tok is None:
        from janome.tokenizer import Tokenizer
        _tok = Tokenizer()
    out: list[str] = []
    pend = ""
    # 数字のかたまりと、そのあいだの文字列（janome にかける）に分ける
    runs: list[tuple[bool, str]] = []
    i = 0
    while i < len(text):
        m = _NUM.match(text, i) or _ATOM.match(text, i)
        if m and m.end() > i:
            runs.append((True, m.group())); i = m.end()
            continue
        if runs and not runs[-1][0]:
            runs[-1] = (False, runs[-1][1] + text[i])
        else:
            runs.append((False, text[i]))
        i += 1
    for k, (is_num, piece) in enumerate(runs):
        if is_num:
            out.append(pend + piece); pend = ""
            continue
        toks = [(t.surface, *t.part_of_speech.split(",")[:2]) for t in _tok.tokenize(piece)]
        if k and runs[k - 1][0]:
            # 数字の直後の助詞は、文脈が無いと接続詞に見える（「で」「なら」）。仮の数字を前に置いて切り、捨てる
            toks = [(t.surface, *t.part_of_speech.split(",")[:2]) for t in _tok.tokenize("3" + piece)]
            if toks and toks[0][0] == "3":
                toks = toks[1:]
            elif toks and toks[0][0].startswith("3"):    # 仮の数字が次の語とくっついた（3多く など）
                toks[0] = (toks[0][0][1:], toks[0][1], toks[0][2])
        for surface, pos, sub in toks:
            if pos in _GLUE_NEXT:
                pend += surface
            elif (pos in _GLUE_POS or sub in _GLUE_SUB) and out and not pend:
                out[-1] += surface
            else:
                out.append(pend + surface); pend = ""
    if pend:
        out.append(pend)
    return out


def wrap(text: str, n: int) -> list[str]:
    """語の途中で折らない。長さ n を越えるかたまりだけ字で折る。"""
    if "\n" in text:
        return [ln for part in text.split("\n") for ln in wrap(part, n)]
    lines, cur = [], ""
    for ch in _chunks(text):
        if len(ch) > n:
            if cur:
                lines.append(cur); cur = ""
            lines.extend(_wrap_chars(ch, n)[:-1])
            cur = _wrap_chars(ch, n)[-1]
            continue
        if len(cur) + len(ch) > n and cur:
            lines.append(cur)
            cur = ""
        cur += ch
    if cur:
        lines.append(cur)
    return _hang(lines)


def _hang(lines: list[str]) -> list[str]:
    # ぶら下がり: 行頭の「、。」を前の行へ
    fixed: list[str] = []
    for ln in lines:
        if fixed and ln and ln[0] in "、。」）":
            fixed[-1] += ln[0]
            ln = ln[1:]
        if ln:
            fixed.append(ln)
    return fixed


def _wrap_chars(text: str, n: int) -> list[str]:
    """字で折る（前の形。数字のかたまりだけ守る）。語で折ると行が足りないときの逃げ道。
    句読点が行頭に来る所は、前の行の最後の1語（数字のかたまりなら丸ごと）を句読点と一緒に次の行へ送る
    （09/06 19:5x・optimizer: 旧の `_hang` は句読点を前の行に足して n+1 字の行を作っていた。実測 60字 の字幕で 17字）。"""
    lines: list[list[str]] = []
    cur: list[str] = []
    for tok in _tokens(text):
        if sum(map(len, cur)) + len(tok) > n and cur:
            if tok[0] in "、。」）" and len(cur) > 1:
                carry = cur.pop()
                lines.append(cur)
                cur = [carry]
            else:
                lines.append(cur)
                cur = []
        cur.append(tok)
    if cur:
        lines.append(cur)
    return _hang(["".join(ln) for ln in lines])


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


# 札（tag）の色。声の言い回し（「たとえば」＝前提・「決まりでは」＝事実・「計算すると」）と同じ札を画面にも出す
# （オーナー 12:3x「言い回しで、事実なのか前提なのかとか分かるようにした方が良い」・受け取り帳 `552fadf1`）
TAG_COLORS = {"前提": (70, 130, 220), "決まり": (60, 160, 90), "計算": (220, 150, 40),
              "結論": (220, 80, 70), "見る所": (140, 90, 200)}
TAG_DEFAULT = (110, 110, 110)
BOARD_TOP_MIN = 600          # 板の上端（show の下）
BOARD_BOTTOM = 1080          # 板の下端（字幕 4行 の上端 1108 より上）
BOARD_LEFT = 110
SHOW_TOP_WITH_BOARD = 150    # 板が在るコマの show の上端


def board_layout(n_lines: int, show_bottom: int) -> tuple[int, int, int]:
    """板の (font px, 行の高さ px, 上端 y)。行が多いほど字を小さくし、字幕の上端より上に収める。
    返り値を検査で挟む（`tests/test_studio_slides_board.py`）。"""
    top = max(BOARD_TOP_MIN, show_bottom + 50)
    room = BOARD_BOTTOM - top - 60
    for px in (60, 54, 48, 42):
        lh = int(px * 1.45)
        if lh * max(n_lines, 1) <= room:
            return px, lh, top
    # 最小の字でも収まらない（show が高い × 5行）: 行間を詰めて下端に収める（字は 42px のまま）
    return 42, max(46, room // max(n_lines, 1)), top


def slide(show: str, sub: str, say: str, i: int, n: int, image: Path | None, out: Path,
          progress: bool = True, tag: str = "", board: list[str] | tuple[str, ...] = ()) -> Path:
    im = background(image)
    d = ImageDraw.Draw(im, "RGBA")
    # 進み具合
    if progress and n > 1:
        d.rectangle([60, 70, W - 60, 82], fill=(255, 255, 255, 70))
        d.rectangle([60, 70, 60 + int((W - 120) * i / n), 82], fill=(255, 210, 60, 255))
    board = [b for b in board if b]
    show_bottom = 0
    # 大きい字（行は書き手の \n で決まる。幅に収まるまで字を小さくする。語の途中で折らない）
    if show:
        lines = show.split("\n")
        size = 124 if not board else 104
        while size > 64:
            fnt = font(FONT_BLACK, size)
            if max(d.textbbox((0, 0), ln, font=fnt)[2] for ln in lines) <= W - 140:
                break
            size -= 8
        fnt = font(FONT_BLACK, size)
        block_h = int(len(lines) * size * 1.25) + (int(56 * 1.25 * len(wrap(sub, 16))) + 20 if sub else 0)
        top = SHOW_TOP_WITH_BOARD + (90 if tag else 0) if board else 700 - block_h // 2
        d.rounded_rectangle([40, top - 50, W - 40, top + block_h + 40], radius=30, fill=(0, 0, 0, 110))
        y = draw_text_block(d, lines, fnt, top, (255, 255, 255), stroke_w=6)
        if sub:
            y = draw_text_block(d, wrap(sub, 16), font(FONT_BOLD, 56), y + 20, (255, 225, 120), stroke_w=4)
        show_bottom = top + block_h + 40
        # 札: show の上に小さい色つきの丸札
        if tag:
            tf = font(FONT_BOLD, 44)
            tw = d.textbbox((0, 0), tag, font=tf)[2]
            tx, ty = (W - tw) // 2, top - 50 - 84
            d.rounded_rectangle([tx - 36, ty - 8, tx + tw + 36, ty + 64], radius=32, fill=TAG_COLORS.get(tag, TAG_DEFAULT) + (255,))
            d.text((tx, ty), tag, font=tf, fill=(255, 255, 255))
    # 板（まん中）: そのコマまでの前提と数の積み上がり。最後の行がいまのコマの行（黄色）
    if board:
        px, lh, top = board_layout(len(board), show_bottom)
        bf = font(FONT_BOLD, px)
        box_h = lh * len(board) + 60
        d.rounded_rectangle([50, top, W - 50, top + box_h], radius=24, fill=(0, 0, 0, 140))
        y = top + 30
        for k, ln in enumerate(board):
            last = k == len(board) - 1
            fill = (255, 225, 120) if last else (235, 235, 235)
            d.text((BOARD_LEFT, y), ("▶ " if last else "　 ") + ln, font=bf, fill=fill, stroke_width=3, stroke_fill=(0, 0, 0))
            y += lh
    # 字幕
    if say:
        # 64字 までは 16字×4行・54px。それ以上は 18字×4行・48px（say の上限 70字 が収まる）
        # 語で折ると行が増えるので、4行に収まる字数まで 16 → 18 → 20 と広げ、それでも溢れたら字で折る
        for chars, px in ((SUB_CHARS, 54), (18, 48), (20, 44)):
            lines = wrap(say, chars)
            if len(lines) <= 4:
                break
        else:
            chars, px = (SUB_CHARS, 54) if len(say) <= SUB_CHARS * 4 else (18, 48)
            lines = _wrap_chars(say, chars)[:4]
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
