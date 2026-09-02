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


#: **外の作りを写した長尺の絵**（`topics.yaml` の `style: outside_long`・2026-09-03 に足した）。
#:
#: ## なぜ要るか（同じ夜に、外の上位4本のサムネイルを実物で並べた）
#:
#: `scripts/niche_ceiling.py` の長尺の上位（505万・440万・325万・293万回）は、絵の型が揃っています:
#:
#:     上の帯    黄色い箱に黒字で「9月中に必ず確認して！」「R8年4月から」「2026年から」
#:               ＝ **いつ・誰に**の1行。小さく、箱で切れている
#:     本文1     **赤い字に白い縁**（その外に黒い影）で主語 ——「年金に」「申請をしないと」
#:     本文2     黄色か白の字に黒い縁で結論 ——「7万円 一生上乗せ」「234万円 失う！」
#:     左の帯    縦書きの短い煽り（「絶対申請して」「9割が知らない」）。ここは写さない
#:     顔        人の顔。**ここは写せない**（実在しない人を出さない・`verify` の名乗りの門）
#:
#: 自分の控え（`6PKux5HNnUE.thumb.jpg`）は 2行・桃色と白・暗い背景で、**主語（年金）が
#: どこにも無く**、いつの話かも無い。前提「外の作り方を写した長尺」（`config/hypotheses.yaml`）
#: は題と尺と中身を写していて、**絵だけ写していませんでした**。一覧で最初に目に入るのは
#: 絵なので、ここを写さないと「外の作りを写した」の判定が絵のぶんだけ混ざります。
#:
#: 写すのは**色と3段の型**だけ（顔と左の帯は写さない）。`style` が `outside_long` の
#: ときだけ効き、ほかの題材は従来と1ピクセルも変わりません。
#:
#: ## 覆る条件
#:
#: 前提「外の作り方を写した長尺」が外れで閉じたら（48時間で 100回 未満）、この型に
#: 根拠は残りません。そのときは `topics.yaml` の `style:` を外せば、この枝は通りません。
OUTSIDE_STYLE = "outside_long"
OUTSIDE_KICKER_BG = (255, 222, 0)       # 黄色い箱
OUTSIDE_KICKER_FG = (16, 16, 20)        # その上の黒字
OUTSIDE_LINE1 = (226, 28, 28)           # 赤い主語
OUTSIDE_LINE1_EDGE = (255, 255, 255)    # その白い縁
OUTSIDE_LINE2 = (255, 232, 0)           # 黄色い結論
OUTSIDE_MARGIN = 56

#: **描いた人物（実在しない・固定の1体）**（`outside_long` だけ・2026-09-03 06:xx に足した）。
#:
#: ## なぜ要るか
#:
#: 上の註は「顔 ＝ ここは写せない」と書いていました。**写せないのは実在の人物**です
#: （なりすましは目標を壊す・`verify` の名乗りの門）。外の上位4本は 4/4 が人の顔で、
#: 前提「外の作り方を写した長尺」の 09/04・09/05 の2本は「題・尺・中身・絵・冒頭」を
#: 写して**顔だけ写していません**（`docs/JOURNAL.md` 2026-09-03 05:1x の `[道筋]`）。
#: 外の上位（`mL0bwzi8KFM`・325万回）は写真の人物の隣に**描いたキャラクター**も置いており、
#: 描いた人物はこの帯の型の中に在ります。**専門家を名乗らず、名前も肩書きも付けない
#: 1体**なら、名乗りの門（`verify._check_no_human_expert_claim`）の外側です。
#:
#: 置くのは右側の胸像1体（スーツ・笑顔）。本文の幅は `OUTSIDE_FIGURE_LEFT` までに縮む
#: （実測: 7字 の主語が 160px → 110px。外の上位も本文は幅の 6割 で、人物が残りを占める）。
#: `OUTSIDE_FIGURE = False` にすれば、この回より前の絵と1ピクセルも変わりません。
#:
#: ## 覆る条件
#:
#: 09/06 17:00 以降の `1huadpEk6HY` の 48h（顔あり）と、それより前の外の型の長尺
#: （顔なし・`6PKux5HNnUE` は池に private のまま在る）を並べて、顔ありが下なら外す。
#: 前提「外の作り方を写した長尺」が外れで閉じたら、この型ごと根拠を失います。
OUTSIDE_FIGURE = True
OUTSIDE_FIGURE_LEFT = 890               # 人物の左端。本文はここまで
FIGURE_CX = 1110                        # 人物の中心 x
FIGURE_SKIN = (247, 208, 172)
FIGURE_SKIN_SHADE = (214, 164, 130)
FIGURE_HAIR = (52, 38, 34)
FIGURE_SUIT = (34, 46, 96)
FIGURE_SHIRT = (250, 250, 252)
FIGURE_TIE = (178, 34, 46)
FIGURE_LINE = (28, 22, 24)
FIGURE_GLOW = (255, 224, 90, 80)


def _draw_figure(img: Image.Image) -> None:
    """右側に描いた人物1体（胸像）を置く。4倍で描いて縮める（縁がなめらか）。"""
    S = 4
    cx = FIGURE_CX
    o = 7   # 輪郭の太さ（元の px）

    # 後ろの光（外の上位の放射の代わり・柔らかい楕円）
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([(cx - 320, 40), (cx + 320, 700)], fill=FIGURE_GLOW)
    glow = glow.filter(ImageFilter.GaussianBlur(48))
    img.paste(glow, (0, 0), glow)

    layer = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    def bx(x0, y0, x1, y1, pad=0):
        return [((x0 - pad) * S, (y0 - pad) * S), ((x1 + pad) * S, (y1 + pad) * S)]

    def pt(x, y):
        return (x * S, y * S)

    # 輪郭（少し大きく描いた同じ形）→ 本体、の順。
    body = (cx - 225, 480, cx + 225, 820)
    head = (cx - 116, 150, cx + 116, 420)
    ear_l = (cx - 134, 268, cx - 100, 330)
    ear_r = (cx + 100, 268, cx + 134, 330)
    neck = (cx - 46, 380, cx + 46, 500)
    hair_box = (cx - 120, 146, cx + 120, 362)

    d.rounded_rectangle(bx(*body, pad=o), radius=120 * S, fill=FIGURE_LINE)
    d.rectangle(bx(*neck, pad=o), fill=FIGURE_LINE)
    d.ellipse(bx(*ear_l, pad=o), fill=FIGURE_LINE)
    d.ellipse(bx(*ear_r, pad=o), fill=FIGURE_LINE)
    d.ellipse(bx(*head, pad=o), fill=FIGURE_LINE)

    d.rounded_rectangle(bx(*body), radius=120 * S, fill=FIGURE_SUIT)
    # シャツの V と襟、ネクタイ
    d.polygon([pt(cx - 78, 480), pt(cx + 78, 480), pt(cx, 610)], fill=FIGURE_SHIRT)
    d.polygon([pt(cx - 14, 486), pt(cx + 14, 486), pt(cx + 20, 600), pt(cx, 628), pt(cx - 20, 600)],
              fill=FIGURE_TIE)
    d.line([pt(cx - 78, 480), pt(cx, 610), pt(cx + 78, 480)], fill=FIGURE_LINE, width=3 * S)
    # ラペル
    d.polygon([pt(cx - 130, 480), pt(cx - 78, 480), pt(cx - 4, 640), pt(cx - 70, 640)], fill=FIGURE_SUIT)
    d.polygon([pt(cx + 130, 480), pt(cx + 78, 480), pt(cx + 4, 640), pt(cx + 70, 640)], fill=FIGURE_SUIT)
    d.line([pt(cx - 130, 480), pt(cx - 70, 640)], fill=FIGURE_LINE, width=3 * S)
    d.line([pt(cx + 130, 480), pt(cx + 70, 640)], fill=FIGURE_LINE, width=3 * S)

    d.rectangle(bx(*neck), fill=FIGURE_SKIN)
    d.rectangle(bx(cx - 46, 400, cx + 46, 430), fill=FIGURE_SKIN_SHADE)   # あごの影
    d.ellipse(bx(*ear_l), fill=FIGURE_SKIN)
    d.ellipse(bx(*ear_r), fill=FIGURE_SKIN)
    d.ellipse(bx(*head), fill=FIGURE_SKIN)
    # 髪（頭の上半分）ともみあげ
    d.chord(bx(*hair_box), start=180, end=360, fill=FIGURE_HAIR)
    d.polygon([pt(cx - 120, 250), pt(cx - 96, 250), pt(cx - 104, 330), pt(cx - 118, 300)], fill=FIGURE_HAIR)
    d.polygon([pt(cx + 120, 250), pt(cx + 96, 250), pt(cx + 104, 330), pt(cx + 118, 300)], fill=FIGURE_HAIR)
    # 眉・目
    d.line([pt(cx - 88, 278), pt(cx - 40, 268)], fill=FIGURE_HAIR, width=9 * S)
    d.line([pt(cx + 40, 268), pt(cx + 88, 278)], fill=FIGURE_HAIR, width=9 * S)
    for ex in (cx - 62, cx + 62):
        d.ellipse(bx(ex - 24, 290, ex + 24, 320), fill=(255, 255, 255), outline=FIGURE_LINE, width=2 * S)
        d.ellipse(bx(ex - 10, 294, ex + 10, 318), fill=FIGURE_LINE)
        d.ellipse(bx(ex - 8, 296, ex - 2, 302), fill=(255, 255, 255))
    # 鼻・頬・口（開いた笑顔）
    d.line([pt(cx, 300), pt(cx - 10, 344), pt(cx + 8, 346)], fill=FIGURE_SKIN_SHADE, width=4 * S)
    d.ellipse(bx(cx - 108, 336, cx - 72, 356), fill=(244, 168, 156, 170))
    d.ellipse(bx(cx + 72, 336, cx + 108, 356), fill=(244, 168, 156, 170))
    d.chord(bx(cx - 54, 330, cx + 54, 398), start=0, end=180, fill=(150, 40, 50),
            outline=FIGURE_LINE, width=3 * S)
    d.rectangle(bx(cx - 38, 366, cx + 38, 376), fill=(255, 255, 255))

    layer = layer.resize((W, H), Image.LANCZOS)
    img.paste(layer, (0, 0), layer)


def _fit_font(draw: ImageDraw.ImageDraw, text: str, start: int, max_w: int, floor: int = 90):
    """`start` から下げて、幅 `max_w` に入る最大の字を返す。"""
    size = start
    while size > floor:
        f = _font(size)
        if draw.textbbox((0, 0), text or "　", font=f)[2] <= max_w:
            return f
        size -= 10
    return _font(floor)


def _create_outside(img: Image.Image, line1: str, line2: str, kicker: str | None,
                    out_path: Path) -> Path:
    """`OUTSIDE_STYLE` の描き方。上の註に、写した型の出どころ。"""
    if OUTSIDE_FIGURE:
        _draw_figure(img)          # 字より先（字が人物の上に載る側）
    draw = ImageDraw.Draw(img)
    max_w = (OUTSIDE_FIGURE_LEFT - OUTSIDE_MARGIN - 16) if OUTSIDE_FIGURE else W - OUTSIDE_MARGIN * 2
    f1 = _fit_font(draw, line1, 190 if len(line1) <= 6 else 160, max_w)
    f2 = _fit_font(draw, line2, 190 if len(line2) <= 6 else 160, max_w)
    b1 = draw.textbbox((0, 0), line1 or "　", font=f1)
    b2 = draw.textbbox((0, 0), line2 or "　", font=f2)
    h1, h2 = b1[3] - b1[1], b2[3] - b2[1]
    gap = 34

    fk = bk = None
    if kicker:
        fk = _fit_font(draw, kicker, 72 if len(kicker) <= 14 else 62, max_w - 40, floor=48)
        bk = draw.textbbox((0, 0), kicker, font=fk)
    hk = (bk[3] - bk[1] + 36) if bk else 0     # 箱の高さ（上下の余白 18 ずつ）

    block = h1 + h2 + gap + (hk + 30 if hk else 0)
    top = max(24, (H - block) // 2)
    x = OUTSIDE_MARGIN

    if kicker and fk and bk:
        pad = 20
        box = [(x - 6, top), (x + (bk[2] - bk[0]) + pad * 2, top + hk)]
        draw.rectangle(box, fill=OUTSIDE_KICKER_BG)
        draw.text((x - 6 + pad - bk[0], top + 18 - bk[1]), kicker, font=fk, fill=OUTSIDE_KICKER_FG)
        top += hk + 30

    if line1:
        y = top - b1[1]
        # 黒い影 → 白い縁 → 赤い字。外の上位の「赤字に白縁」はこの3層です。
        draw.text((x + 6, y + 8), line1, font=f1, fill=(12, 12, 16), stroke_width=18,
                  stroke_fill=(12, 12, 16))
        draw.text((x, y), line1, font=f1, fill=OUTSIDE_LINE1, stroke_width=12,
                  stroke_fill=OUTSIDE_LINE1_EDGE)
        top += h1 + gap
    if line2:
        y = top - b2[1]
        draw.text((x, y), line2, font=f2, fill=OUTSIDE_LINE2, stroke_width=14,
                  stroke_fill=(12, 12, 16))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    quality = 92
    while quality >= 60:
        img.save(out_path, "JPEG", quality=quality, optimize=True)
        if out_path.stat().st_size < 2_000_000:
            break
        quality -= 8
    return out_path


def create(source: Path, line1: str, line2: str, out_path: Path, work: Path,
           accent: tuple[int, int, int] | None = None,
           kicker: str | None = None, style: str | None = None) -> Path:
    """accent には動画のテーマ色を渡す。渡さないと本文と色が食い違う。

    `style` が `OUTSIDE_STYLE`（`topics.yaml` の `style: outside_long`）なら、
    外の上位の型（黄色い箱の1行・赤字に白縁の主語・黄色の結論）で描く。
    それ以外は従来と1ピクセルも変わらない（`OUTSIDE_STYLE` の上の註）。

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
    if (style or "") == OUTSIDE_STYLE:
        return _create_outside(img, line1, line2, kicker, out_path)
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
