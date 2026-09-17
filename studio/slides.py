"""画面。縦 1080x1920。1コマ = 1枚の PNG。

  上 1/3    大きい字（show）と小さい字（sub）—— 数字・見出し。その上に札（tag: 前提／しくみ／決まり／計算／結論／見る所）
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


# ---- 形ごとの幾何（2026-09-14 14:2x・optimizer・Opus。`docs/GOAL.md` (4-g) 2 の「長尺の型」） ----------
# **縦（short）の数は 1つも変えていません** —— 上の W/H・SUB_BOTTOM・SUB_CHARS・BOARD_* は
# そのまま `SHORT` の中身で、公開ずみ 9本 の絵は 1画素も動きません（検査の陰性対照）。
# 横（long）は 1920x1080:
#   下の余白      ショートの UI（下 420px）が無いので 60px だけ空ける
#   字幕の字数    幅が 1.78倍 なので 1行 16字 → 28字（54px で 28字 ＝ 1512px ＜ 1920-100）
#   板の置き場    縦が 1080 しかないので、字幕 4行（約 340px）の上に 300〜660 を割く
# **梯子（字数, px）は縦と同じ形**: 4行 に収まるまで字を小さくし、それでも溢れたら字で折る。
# 覆る条件:
#  (1) 横の本を焼いて字幕が 4行 を溢れたら、直すのは `sub_ladder` の字数（幅は測れる ＝ sheet で見る）。
#  (2) 板が 5行 のコマで `board_layout` が最小の字にも収まらなくなったら、横では板の行数を 4行 に絞ること
#      （`script.MAX_BOARD_LINES` を形ごとにする ＝ そのときに足す。**先に足さない**）。
#  (3) 縦の数が 1つでも動いたら、それは long のためではありません ＝ その回が理由を JOURNAL に書くこと。


class Geom:
    """1つの形の画面の数。**`slide()` はここからしか寸法を読みません**（写しを持たない）。"""

    __slots__ = ("w", "h", "sub_bottom", "sub_ladder", "board_top_min", "board_bottom",
                 "show_center", "show_top_with_board", "thumb")

    def __init__(self, w, h, sub_bottom, sub_ladder, board_top_min, board_bottom,
                 show_center, show_top_with_board, thumb):
        self.w = w
        self.h = h
        self.sub_bottom = sub_bottom
        self.sub_ladder = sub_ladder            # ((1行の字数, px), …)。先に当たったものを使う
        self.board_top_min = board_top_min
        self.board_bottom = board_bottom
        self.show_center = show_center          # 板が無いコマの show のまん中
        self.show_top_with_board = show_top_with_board
        self.thumb = thumb                      # contact_sheet の1枚 (w, h)


SHORT = Geom(1080, 1920, 1920 - 470, ((16, 54), (18, 48), (20, 44)), 600, 1080, 700, 150, (270, 480))
LONG = Geom(1920, 1080, 1080 - 60, ((28, 54), (32, 48), (36, 44)), 300, 660, 400, 40, (480, 270))
GEOMS = {"short": SHORT, "long": LONG}


def geom_of(form: str) -> Geom:
    """形の名から幾何へ。知らない名は縦（`script.form_of` と同じ向き）。"""
    return GEOMS.get(form or "short", SHORT)



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
# 09/12 12:5x: 09/13 の本の字幕で「国民\n年金だけの人へ」「国民\n年金のうえに」（janome が 国民/年金 と割る）。国民年金基金 → 付加年金 → 国民年金 の順（長い順）
_ATOM = re.compile(r"年金額改定通知書|国民年金基金|遺族厚生年金|老齢厚生年金|老齢基礎年金|遺族基礎年金|国民年金|付加年金|厚生年金|基礎年金|ねんきん定期便|ねんきんネット|ねんきん")
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


_BG_CACHE: dict[tuple, Image.Image] = {}


def background(image: Path | None, g: Geom = SHORT) -> Image.Image:
    """本の背景。**同じ絵は 1度しか作らない**（2026-09-17 21:xx・`viz` の動く図で 1コマ に十数枚 描くため。
    ぼかしが 1枚 100ms 級なので、憶えずに描くと 1コマ 2秒 が焼きに乗る）。返すのは写し（呼び手が上に描いてよい）。"""
    key = (str(image) if image else None, g.w, g.h)
    if image and image.exists():
        try:
            key += (image.stat().st_size,)
        except OSError:
            pass
    im = _BG_CACHE.get(key)
    if im is None:
        im = _background(image, g)
        _BG_CACHE.clear()          # 1本 の焼きの中で同時に要るのは 1〜2枚。貯めない
        _BG_CACHE[key] = im
    return im.copy()


def _background(image: Path | None, g: Geom = SHORT) -> Image.Image:
    W, H = g.w, g.h
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


def draw_text_block(d: ImageDraw.ImageDraw, lines: list[str], fnt, top: int, fill, stroke=(0, 0, 0), stroke_w=0, gap=1.25, width: int = W) -> int:
    y = top
    for ln in lines:
        bbox = d.textbbox((0, 0), ln, font=fnt)
        w = bbox[2] - bbox[0]
        d.text(((width - w) // 2, y), ln, font=fnt, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)
        y += int(fnt.size * gap)
    return y


# 札（tag）の色。声の言い回し（「たとえば」＝前提・「決まりでは」＝事実・「計算すると」）と同じ札を画面にも出す
# （オーナー 12:3x「言い回しで、事実なのか前提なのかとか分かるようにした方が良い」・受け取り帳 `552fadf1`）
TAG_COLORS = {"前提": (70, 130, 220), "しくみ": (0, 150, 160), "決まり": (60, 160, 90), "計算": (220, 150, 40),
              "結論": (220, 80, 70), "見る所": (140, 90, 200)}
TAG_DEFAULT = (110, 110, 110)

# **名乗りの札**（2026-09-18 00:3x・optimizer・Fable 5.1・ultracode。名は `common.BRAND_NAME` の 1か所）。
# 毎コマ 左上（縦: 進み具合の線の下 y 100〜158・横: 線の上 y 8〜60）に、チャンネル名の小さい札を置く。
# 色は札（tag）のどれとも 12 以上 離す（`tests/test_studio_slides_board.py` が tag の色を x 380〜700 で探す ＝ 重ねない）。
# 幅は 30px × 10字 ＋ 余白 ＝ 約 340px → 縦の tag の札（まん中・x ≥ 438）に当たらない。
# **覆る条件**: (1) sheet で 札 と tag が重なった本が出たら、字を 28px に落とす（位置は動かさない）。
# (2) 名乗りを入れた本の維持率（10% の点・`trend` の維持率カーブ）が入れていない本より 0.05 以上 低ければ、
#     札ではなく**大きさ**を疑う（Shorts の UI の上の帯と重なっていないかを sheet で見る）。
BRAND_COLOR = (150, 95, 45)
BRAND_PX = 30
BOARD_TOP_MIN = 600          # 板の上端（show の下）
BOARD_BOTTOM = 1080          # 板の下端（字幕 4行 の上端 1108 より上）
BOARD_LEFT = 110
SHOW_TOP_WITH_BOARD = 150    # 板が在るコマの show の上端


def board_layout(n_lines: int, show_bottom: int, g: Geom = SHORT) -> tuple[int, int, int]:
    """板の (font px, 行の高さ px, 上端 y)。行が多いほど字を小さくし、字幕の上端より上に収める。
    返り値を検査で挟む（`tests/test_studio_slides_board.py`）。
    **`g` は形ごとの幾何**（既定 `SHORT` ＝ 縦。ここの既定値が動くと公開ずみの絵が動きます）。"""
    top = max(g.board_top_min, show_bottom + 50)
    room = g.board_bottom - top - 60
    for px in (60, 54, 48, 42):
        lh = int(px * 1.45)
        if lh * max(n_lines, 1) <= room:
            return px, lh, top
    # 最小の字でも収まらない（show が高い × 5行）: 行間を詰めて下端に収める（字は 42px のまま）
    return 42, max(46, room // max(n_lines, 1)), top


LONG_COL_TOP, LONG_COL_BOTTOM = 120, 700


def viz_box(g: Geom, show_bottom: int = 0) -> tuple[int, int, int, int]:
    """動く図（`studio/viz.py`）の置き場 (x, y, w, h) ＝ **板と同じ所**。
    縦は show の下（`board_layout` と同じ上端）から板の下端まで・横は左の列。"""
    if g is LONG:
        return 50, LONG_COL_TOP, g.w // 2 - 110, LONG_COL_BOTTOM - LONG_COL_TOP
    top = max(g.board_top_min, show_bottom + 50)
    return 50, top, g.w - 100, g.board_bottom - top


def _slide_long_two_col(im, d, W, show, sub, tag, board, g, viz=None):
    """横（long）の上半分: 左列に板（か 動く図）・右列に show と sub。字幕は呼び手が下に描く（縦と共通）。
    列の下端は字幕 4行（44px）の箱の上端 734 より上（**700**）に収める。"""
    col_top, col_bottom = LONG_COL_TOP, LONG_COL_BOTTOM
    mid = W // 2
    # 左列: 板（か 図）
    left_w = mid - 110
    if viz is not None:
        x, y0, w, h = viz_box(g)
        im.paste(viz, (x, y0 + (h - viz.height) // 2), viz)
    elif board:
        for px in (48, 44, 40, 36):
            bf = font(FONT_BOLD, px)
            lh = int(px * 1.45)
            if lh * len(board) + 60 <= col_bottom - col_top and \
               max(d.textbbox((0, 0), "▶ " + ln, font=bf)[2] for ln in board) <= left_w - 80:
                break
        box_h = lh * len(board) + 60
        top = col_top + (col_bottom - col_top - box_h) // 2
        d.rounded_rectangle([50, top, 50 + left_w, top + box_h], radius=24, fill=(0, 0, 0, 140))
        y = top + 30
        for k, ln in enumerate(board):
            last = k == len(board) - 1
            fill = (255, 225, 120) if last else (235, 235, 235)
            d.text((90, y), ("▶ " if last else "　 ") + ln, font=bf, fill=fill, stroke_width=3, stroke_fill=(0, 0, 0))
            y += lh
    # 右列: show（+sub）。列の幅に収まるまで字を下げる
    x0, right_w = mid + 30, W - mid - 80
    lines = show.split("\n") if show else []
    size = 96
    while size > 56:
        fnt = font(FONT_BLACK, size)
        if not lines or max(d.textbbox((0, 0), ln, font=fnt)[2] for ln in lines) <= right_w - 60:
            break
        size -= 8
    fnt = font(FONT_BLACK, size)
    sub_lines = wrap(sub, 18) if sub else []
    sf = font(FONT_BOLD, 44)
    block_h = int(len(lines) * size * 1.25) + (int(44 * 1.3 * len(sub_lines)) + 20 if sub_lines else 0)
    top = col_top + (90 if tag else 0)
    top = max(top, col_top + (col_bottom - col_top - block_h) // 2)
    d.rounded_rectangle([x0, top - 40, x0 + right_w, min(col_bottom, top + block_h + 30)], radius=30, fill=(0, 0, 0, 110))
    y = top
    for ln in lines:
        w = d.textbbox((0, 0), ln, font=fnt)[2]
        d.text((x0 + (right_w - w) // 2, y), ln, font=fnt, fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
        y += int(size * 1.25)
    if sub_lines:
        y += 20
        for ln in sub_lines:
            w = d.textbbox((0, 0), ln, font=sf)[2]
            d.text((x0 + (right_w - w) // 2, y), ln, font=sf, fill=(255, 225, 120), stroke_width=4, stroke_fill=(0, 0, 0))
            y += int(44 * 1.3)
    if tag:
        tf = font(FONT_BOLD, 40)
        tw = d.textbbox((0, 0), tag, font=tf)[2]
        tx, ty = x0 + (right_w - tw) // 2, top - 40 - 76
        d.rounded_rectangle([tx - 32, ty - 8, tx + tw + 32, ty + 58], radius=30, fill=TAG_COLORS.get(tag, TAG_DEFAULT) + (255,))
        d.text((tx, ty), tag, font=tf, fill=(255, 255, 255))


def brand_strip(d: ImageDraw.ImageDraw, g: Geom, name: str | None = None) -> tuple[int, int, int, int]:
    """名乗りの札を左上に描き、その箱 (x0, y0, x1, y1) を返す（`BRAND_COLOR` の註）。`name` が空なら描かない。"""
    from .common import BRAND_NAME
    name = BRAND_NAME if name is None else name
    if not name:
        return (0, 0, 0, 0)
    f = font(FONT_BOLD, BRAND_PX)
    tw = d.textbbox((0, 0), name, font=f)[2]
    x0, y0 = 60, (100 if g is not LONG else 8)
    box = (x0, y0, x0 + tw + 40, y0 + BRAND_PX + 24)
    d.rounded_rectangle(list(box), radius=18, fill=BRAND_COLOR + (235,))
    d.text((x0 + 20, y0 + 8), name, font=f, fill=(255, 255, 255))
    return box


def slide(show: str, sub: str, say: str, i: int, n: int, image: Path | None, out: Path,
          progress: bool = True, tag: str = "", board: list[str] | tuple[str, ...] = (),
          form: str = "short", viz: Image.Image | None = None, fast: bool = False,
          brand: bool = True) -> Path:
    """1コマ 1枚。`viz` は動く図の 1枚（`studio/viz.draw` の RGBA）—— 在れば板の所に置き、板は描かない。

    `fast` は**動く途中の絵**にだけ使う（2026-09-17 21:xx に実測して足した）: `optimize=True` の PNG は
    写真の背景で **1枚 4秒** かかり（板だけの静止画も同じ ＝ 200コマ の長尺の焼きが 13分 の当のもの）、
    22枚 の動く絵で 1コマ 100秒 になりました。途中の絵は圧縮を最小にして 0.2秒 に落とし、
    **ffmpeg が読んだあと `render.build` が消します**（1枚 4MB × 数百枚 を残さない）。最後の 1枚 は今までどおり。"""
    im = compose(show, sub, say, i, n, image, progress, tag, board, form, viz, brand=brand).convert("RGB")
    if fast:
        im.save(out, "PNG", compress_level=1)
    else:
        im.save(out, "PNG", optimize=True)
    return out


def slide_frames(show: str, sub: str, say: str, i: int, n: int, image: Path | None, out_dir: Path,
                 seconds: float, viz_spec: dict, progress: bool = True, tag: str = "",
                 board: list[str] | tuple[str, ...] = (), form: str = "short") -> list[tuple[Path, float]]:
    """**動く図のコマ**（オーナー 2026-09-17 20:4x `d699098f`・`studio/viz.py` 冒頭）。
    (PNG, その絵を出す秒) の列 —— 合計はコマの秒数。最後の 1枚 が `slide-{i:02d}.png`（sheet と同じ名）。"""
    from . import viz as V
    g = geom_of(form)
    _, _, w, h = viz_box(g, _show_bottom(show, sub, tag, True, g))
    fr = V.frames(viz_spec, seconds, (w, h))
    out = []
    for k, (ov, t) in enumerate(fr):
        last = k == len(fr) - 1
        p = out_dir / (f"slide-{i:02d}.png" if last else f"slide-{i:02d}-{k:02d}.png")
        slide(show, sub, say, i, n, image, p, progress, tag, board, form, viz=ov, fast=not last)
        out.append((p, t))
    return out


def is_transient_frame(p: Path) -> bool:
    """動く途中の絵の名（`slide-03-07.png`）か。最後の 1枚（`slide-03.png`）は違う。"""
    return bool(re.fullmatch(r"slide-\d{2}-\d{2}\.png", p.name))


def _show_bottom(show: str, sub: str, tag: str, with_board: bool, g: Geom) -> int:
    """縦で板（か 図）が在るコマの show の下端（`compose` と同じ式・図の高さを決めるために先に要る）。"""
    if not show or g is LONG:
        return 0
    lines = show.split("\n")
    size = 124 if not with_board else 104
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    while size > 64:
        fnt = font(FONT_BLACK, size)
        if max(d.textbbox((0, 0), ln, font=fnt)[2] for ln in lines) <= g.w - 140:
            break
        size -= 8
    fnt = font(FONT_BLACK, size)
    sub_n = g.sub_ladder[0][0]
    block_h = int(len(lines) * size * 1.25) + (int(56 * 1.25 * len(wrap(sub, sub_n))) + 20 if sub else 0)
    top = g.show_top_with_board + (90 if tag else 0) if with_board else g.show_center - block_h // 2
    return top + block_h + 40


def compose(show: str, sub: str, say: str, i: int, n: int, image: Path | None,
            progress: bool = True, tag: str = "", board: list[str] | tuple[str, ...] = (),
            form: str = "short", viz: Image.Image | None = None, brand: bool = True) -> Image.Image:
    g = geom_of(form)
    W, H = g.w, g.h
    SUB_BOTTOM = g.sub_bottom
    im = background(image, g)
    d = ImageDraw.Draw(im, "RGBA")
    # 進み具合
    if progress and n > 1:
        d.rectangle([60, 70, W - 60, 82], fill=(255, 255, 255, 70))
        d.rectangle([60, 70, 60 + int((W - 120) * i / n), 82], fill=(255, 210, 60, 255))
    # 名乗りの札（左上・毎コマ。`brand=False` は陰性対照 ＝ 前の絵と 1画素も違わない）
    if brand:
        brand_strip(d, g)
    board = [b for b in board if b]
    # **図が在るコマは板を描かない**（同じ所を使う・`viz.py` 冒頭）。show の置き方は板が在るときと同じ
    if viz is not None:
        board_like = True
        board = []
    else:
        board_like = bool(board)
    show_bottom = 0
    if g is LONG and (board or viz is not None):
        # **横（long）は 2列**（2026-09-14 22:4x・optimizer・Fable。長尺の 1本目 の sheet で踏んだ）:
        # 縦の並び（show → 板 → 字幕）を 1920x1080 にそのまま当てると、板の上端が show の下（≈650）に来て
        # `board_bottom`（660）を割り、板が字幕の箱（734〜1020）の上に重なって描かれました（34コマ 中 板 3行以上 の全部）。
        # 横では **左に板・右に show と sub・下に字幕** を置く（字幕は共通の側）。縦の絵は 1バイトも動かしません。
        # 覆る条件: (1) 板 5行 が 左列（幅 W/2-110）に収まらない本が出たら、行数ではなく字（ladder）を下げること。
        # (2) オーナーが横の画面に言葉を出したら、その言葉が正本。
        _slide_long_two_col(im, d, W, show, sub, tag, board, g, viz)
        show_bottom = -1   # 板は描いた（下の共通の枝を通らない）
    # 大きい字（行は書き手の \n で決まる。幅に収まるまで字を小さくする。語の途中で折らない）
    if show and show_bottom == 0:
        lines = show.split("\n")
        size = 124 if not board_like else 104
        while size > 64:
            fnt = font(FONT_BLACK, size)
            if max(d.textbbox((0, 0), ln, font=fnt)[2] for ln in lines) <= W - 140:
                break
            size -= 8
        fnt = font(FONT_BLACK, size)
        sub_n = g.sub_ladder[0][0]
        block_h = int(len(lines) * size * 1.25) + (int(56 * 1.25 * len(wrap(sub, sub_n))) + 20 if sub else 0)
        top = g.show_top_with_board + (90 if tag else 0) if board_like else g.show_center - block_h // 2
        d.rounded_rectangle([40, top - 50, W - 40, top + block_h + 40], radius=30, fill=(0, 0, 0, 110))
        y = draw_text_block(d, lines, fnt, top, (255, 255, 255), stroke_w=6, width=W)
        if sub:
            y = draw_text_block(d, wrap(sub, sub_n), font(FONT_BOLD, 56), y + 20, (255, 225, 120), stroke_w=4, width=W)
        show_bottom = top + block_h + 40
        # 札: show の上に小さい色つきの丸札
        if tag:
            tf = font(FONT_BOLD, 44)
            tw = d.textbbox((0, 0), tag, font=tf)[2]
            tx, ty = (W - tw) // 2, top - 50 - 84
            d.rounded_rectangle([tx - 36, ty - 8, tx + tw + 36, ty + 64], radius=32, fill=TAG_COLORS.get(tag, TAG_DEFAULT) + (255,))
            d.text((tx, ty), tag, font=tf, fill=(255, 255, 255))
    # 動く図（まん中・板と同じ所）
    if viz is not None and show_bottom >= 0:
        x, y0, w, h = viz_box(g, show_bottom)
        ov = viz if viz.size == (w, h) else viz.resize((w, h))
        im.paste(ov, (x, y0), ov)
    # 板（まん中）: そのコマまでの前提と数の積み上がり。最後の行がいまのコマの行（黄色）
    if board and show_bottom >= 0:
        px, lh, top = board_layout(len(board), show_bottom, g)
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
        for chars, px in g.sub_ladder:
            lines = wrap(say, chars)
            if len(lines) <= 4:
                break
        else:
            head, nxt = g.sub_ladder[0], g.sub_ladder[1]
            chars, px = head if len(say) <= head[0] * 4 else nxt
            lines = _wrap_chars(say, chars)[:4]
        fnt = font(FONT_BOLD, px)
        lh = int(px * 1.35)
        box_h = lh * len(lines) + 50
        top = SUB_BOTTOM - box_h
        d.rounded_rectangle([50, top, W - 50, SUB_BOTTOM], radius=24, fill=(0, 0, 0, 165))
        draw_text_block(d, lines, fnt, top + 25, (255, 255, 255), gap=1.35, width=W)
    return im


def contact_sheet(pngs: list[Path], out: Path, cols: int = 4) -> Path:
    """1枚の大きさは**実物の縦横から決めます**（形を引数で渡さない ＝ 渡し忘れる道を作らない）。
    縦 1080x1920 は 270x480・横 1920x1080 は 480x270（`Geom.thumb`）。"""
    with Image.open(pngs[0]) as p0:
        tw, th = (SHORT if p0.height >= p0.width else LONG).thumb
    thumbs = [Image.open(p).resize((tw, th)) for p in pngs]
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (30, 30, 30))
    for k, t in enumerate(thumbs):
        sheet.paste(t, ((k % cols) * tw, (k // cols) * th))
    sheet.save(out)
    return out
