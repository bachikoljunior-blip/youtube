"""長尺のサムネ（1280x720）—— 2026-09-15 00:xx JST・optimizer・Fable が足した。

なぜ: `cmd_schedule` はサムネに **1コマ目の画面（`slide-01.png`）** をそのまま付けていました。
縦のショートではサムネは 1度も見られない（フィードは動画そのものが流れる）ので、それで答えは変わりません。
横の長尺は逆で、**再生の入口は検索と関連の一覧に並ぶサムネと題**です —— 1コマ目の画面は
左に板・右に見出し・下に字幕 の 3つ が 1920x1080 に並ぶ「読む物」で、一覧の中では 320px 幅に縮みます。
`reporting.py` が読む `video_thumbnail_impressions_ctr` は、この絵で決まる数です。

## **【2026-09-16 02:0x・optimizer・Fable・ultracode】形を、速い 6チャンネルの実物へ当て直した**

**09/15 00:xx のこの形は、手もとの理屈だけで描いたものでした**（`peers.py` が立つ 21時間 前）。
21:0x の (4-j) は同じ 6チャンネルから**題の形**を写しましたが、**一覧で先に目に入るのは絵の側**で、
そちらは写していませんでした ＝ **`GOAL.md` (4-j) の、撃っていなかった半分。**

**この回に実物を見ました**（`peers.top[].id` → `https://i.ytimg.com/vi/<id>/maxresdefault.jpg`・**API 0単位**・
`cli peers` の 6チャンネル の上位から 6枚。うち `カメ先生のもらえるお金` は齢 44日 で 5,780人 ＝ 期限の中で門を抜けた口）。
**6枚 とも同じ形でした**:

    1. 背景は**ほとんど見えません**（濃紺か黒の単色、または文字が乗る所を潰した写真）
    2. 上に**小さいチップ**（黄の地に黒字、または黒帯に黄字）＝ **対象か締切**「50歳以上へ」「9月中に必ず確認して！」
    3. 真ん中に**巨大な 2行**（白 と 黄／赤・太い黒縁）＝ 損と数。1行が画面の **25% 前後**の高さ
    4. 下に**赤帯 ＋ 白字**（1行）＝ 結果か指示「届出をするかどうかだけで変わる」「消える4つを先に確かめてください」
    5. 字が画面の **9割** を占める。顔は 6枚 中 2枚 だけ（速い口 `カメ先生` は **顔なし**）＝ **こちらは顔を使いません**
       （CLAUDE.md の根幹「架空の経歴を要らない作り」。写真の人物を載せると、その人が話しているように読めます）

**前の形との差**（同じ本 `2026-09-17-teikibin-nai-okane-6tsu` で並べた）:

    背景の暗さ   0.25（写真が読める）        → **0.62**（写真は質感だけ・字が勝つ）
    行           左に 3行・白白黄・高さ 15%   → **チップ ＋ 巨大 2行 ＋ 赤帯**・1行 22〜26%
    字の起点     168／128px                  → **214／176px**（同じ `_fit` で幅に合わせて落ちる）
    占有         縦 6割                      → **縦 9割**

**チップと赤帯は、題から引けます** —— (4-j) が写した題の形 `【対象】＋ 損か締切 ＋ 数｜補足` が、
**この絵の 4つの役と 1対1 で対応します**（`【】`→チップ・`｜` の後ろ→赤帯）。
`Script.thumb` に 4行 書けばそちらが勝ちます（`chip_of` / `band_of` / `big_lines`）。

**ここで描く物**（一覧の 320px で読める形）:
  ・背景は注文の絵（cover-fit・**0.62** まで落とす）。無ければ単色の勾配
  ・上のチップ（黄地・黒字）＝ 対象か締切。無ければ描かない
  ・巨大 2行（白 ＋ 黄）。数を含む行が黄（無ければ 2行目が黄）
  ・下の赤帯（白字）＝ 結果か指示。無ければ描かない
  ・ロゴ・顔・名乗りは無し（CLAUDE.md の根幹「架空の経歴を要らない作り」）

**ショートの答えは 1つも変えません** —— `cmd_schedule` は `form == "long"` のときだけここを通ります
（検査 `tests/test_studio_thumb.py`）。`thumb` は `build_sig` に入れません（mp4 に渡らない ＝ 焼き直しの理由にならない。
`title` と同じ扱い）。**＝ この形は、焼き直さずに既に上がっている本にも当てられます**（`thumbnails.set` 50単位）。

覆る条件:
 (1) 長尺の `video_thumbnail_impressions_ctr`（`reporting`）が、**この形に替える前の本の中央を下回ったら**、
     形を戻すのではなく**どの役が効いていないか**を見る（チップ／赤帯／背景の暗さ の順で 1つずつ）。
     **impressions/CTR は Analytics API では読めません**（`metrics=impressions` に 400。`studio/analytics.py` 冒頭）
     ＝ 読めるのは `reporting.py` の口だけ。**そこが読めないあいだは、判定は 48h の再生で代理すること。**
 (2) `peers` の上位の形が変わったら（`【】` でも赤帯でもなくなったら）、**この註ごと当て直すこと** ——
     ここに書いてあるのは「2026-09-16 に他人がそうしていた」だけで、因果ではありません。
 (3) オーナーがサムネに言葉を出したら、その言葉が正本。
 (4) YouTube が custom thumbnail を拒む（`thumbnails.set` 403 ＝ 電話の確認が無いチャンネル）なら、
     `cmd_schedule` は印字して `slide-01.png` へ戻る（いまの try/except のまま）。
derivation は `docs/JOURNAL.md` 2026-09-16 02:0x。
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

from . import slides

THUMB_W, THUMB_H = 1280, 720
MAX_LINES = 3
DIM = 0.72                      # 背景をここまで黒へ寄せる（peers は字が 9割・背景は質感だけ）
CHIP_BG = (255, 214, 0)         # チップの地（黄）
CHIP_FG = (0, 0, 0)
BAND_BG = (208, 24, 24)         # 下の帯（赤）
BAND_FG = (255, 255, 255)
BIG_WHITE = (255, 255, 255)
BIG_YELLOW = (255, 225, 60)
_NUM = re.compile(r"[0-9０-９]")
_CHIP = re.compile(r"^[【\[]([^】\]]{1,14})[】\]]")


def lines_for(s) -> list[str]:
    """サムネの行。`Script.thumb` が在ればそれ（3行まで）・無ければ 1コマ目の `show` の行。

    **巨大な 2行 のもと**です（チップと赤帯は `chip_of` / `band_of` が別に引きます）。
    """
    lines = [ln.strip() for ln in (getattr(s, "thumb", None) or []) if ln and ln.strip()]
    if not lines and s.segments:
        lines = [ln.strip() for ln in s.segments[0].show.split("\n") if ln.strip()]
    return lines[:MAX_LINES]


def chip_of(s) -> str | None:
    """上のチップの字 ＝ **誰に向けた本か**。

    `Script.thumb` が **4行** なら 1行目。無ければ**題の `【…】`**（(4-j) が写した題の形）。
    どちらも無ければ None ＝ チップを描きません（無い物を作らない）。
    """
    raw = [ln.strip() for ln in (getattr(s, "thumb", None) or []) if ln and ln.strip()]
    if len(raw) >= 4:
        return raw[0]
    m = _CHIP.match((getattr(s, "title", "") or "").strip())
    return m.group(1) if m else None


def band_of(s) -> str | None:
    """下の赤帯の字 ＝ **結果か指示**（「申請しないと来ません」）。

    `Script.thumb` が **4行** なら 4行目。無ければ**題の `｜` の後ろ**（同じく (4-j) の題の形）。
    24字 を越えたら描きません（320px で読めない ＝ 帯の意味が無い）。
    """
    raw = [ln.strip() for ln in (getattr(s, "thumb", None) or []) if ln and ln.strip()]
    if len(raw) >= 4:
        out = raw[3]
    else:
        t = (getattr(s, "title", "") or "").strip()
        out = t.split("｜", 1)[1].strip() if "｜" in t else ""
    return out if 0 < len(out) <= 24 else None


def big_lines(s) -> list[str]:
    """真ん中の巨大な行（2行まで）。4行 渡されていれば 2〜3行目、そうでなければ `lines_for`。"""
    raw = [ln.strip() for ln in (getattr(s, "thumb", None) or []) if ln and ln.strip()]
    if len(raw) >= 4:
        return raw[1:3]
    return lines_for(s)[:MAX_LINES]


def _accent_of(lines: list[str]) -> int:
    """黄にする行 ＝ **数がいちばん濃い行**（「382万7800円」）。

    `_NUM.search` の最初の当たりで選ぶと、「載っていないお金6つ」の `6` が
    「382万7800円」より先に立ちます（実測 2026-09-16 02:1x）—— peers の 6枚 で
    黄／赤になっているのは **金額の行**なので、濃さで選びます。数が 1つも無ければ最後の行。
    """
    best, score = len(lines) - 1, 0.0
    for k, ln in enumerate(lines):
        r = len(_NUM.findall(ln)) / max(1, len(ln))
        if r > score:
            best, score = k, r
    return best


def _fit(d: ImageDraw.ImageDraw, text: str, path: str, start: int, floor: int, width: int):
    size = start
    while size > floor:
        f = slides.font(path, size)
        if d.textbbox((0, 0), text, font=f)[2] <= width:
            return f, size
        size -= 6
    return slides.font(path, floor), floor


def render(s, image: Path | None, out: Path) -> Path:
    W, H = THUMB_W, THUMB_H
    if image and Path(image).exists():
        im = Image.open(image).convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        x, y = (im.width - W) // 2, (im.height - H) // 2
        im = im.crop((x, y, x + W, y + H))
        im = Image.blend(im, Image.new("RGB", (W, H), (6, 14, 38)), DIM)
    else:
        im = slides.background(None, slides.LONG).resize((W, H), Image.LANCZOS)
        im = Image.blend(im.convert("RGB"), Image.new("RGB", (W, H), (6, 14, 38)), 0.45)
    im = im.convert("RGBA")
    d = ImageDraw.Draw(im)

    pad = 28
    text_w = W - pad * 2
    chip, band = chip_of(s), band_of(s)
    bigs = [ln for ln in big_lines(s) if ln]
    if not bigs:
        return _save(im, out)

    # --- 下の赤帯（先に高さを取る。字は帯いっぱい） ---
    band_h = 0
    if band:
        bf, bsz = _fit(d, band, slides.FONT_BLACK, 86, 44, text_w - 24)
        band_h = int(bsz * 1.52)
        d.rectangle([0, H - band_h, W, H], fill=BAND_BG)
        bb = d.textbbox((0, 0), band, font=bf)
        d.text(((W - (bb[2] - bb[0])) // 2, H - band_h + (band_h - (bb[3] - bb[1])) // 2 - bb[1]),
               band, font=bf, fill=BAND_FG)

    # --- 上のチップ（黄の地・黒字） ---
    chip_h = 0
    if chip:
        cf, csz = _fit(d, chip, slides.FONT_BLACK, 76, 40, text_w - 80)
        cb = d.textbbox((0, 0), chip, font=cf)
        cw, ch = cb[2] - cb[0], cb[3] - cb[1]
        chip_h = ch + 34
        x0 = (W - (cw + 56)) // 2
        d.rectangle([x0, pad, x0 + cw + 56, pad + chip_h], fill=CHIP_BG)
        d.text((x0 + 28, pad + (chip_h - ch) // 2 - cb[1]), chip, font=cf, fill=CHIP_FG)

    # --- 真ん中の巨大 2行（白 ＋ 黄・太い黒縁）。残りの高さを埋める ---
    top = pad + chip_h + (18 if chip else 0)
    room = (H - band_h - 14) - top
    accent = _accent_of(bigs)
    fonts = []
    for k, ln in enumerate(bigs):
        f, size = _fit(d, ln, slides.FONT_BLACK, 214 if k == accent else 176, 64, text_w)
        fonts.append((f, size))
    gap = 6
    total = sum(int(sz * 1.12) for _, sz in fonts) + gap * (len(fonts) - 1)
    while total > room and any(sz > 64 for _, sz in fonts):
        fonts = [(slides.font(slides.FONT_BLACK, max(64, sz - 8)), max(64, sz - 8)) for _, sz in fonts]
        total = sum(int(sz * 1.12) for _, sz in fonts) + gap * (len(fonts) - 1)
    y = top + max(0, (room - total) // 2)
    for k, (ln, (f, size)) in enumerate(zip(bigs, fonts)):
        fill = BIG_YELLOW if k == accent else BIG_WHITE
        bb = d.textbbox((0, 0), ln, font=f)
        d.text(((W - (bb[2] - bb[0])) // 2, y), ln, font=f, fill=fill,
               stroke_width=13, stroke_fill=(0, 0, 0))
        y += int(size * 1.12) + gap
    return _save(im, out)


def _save(im: Image.Image, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out, "PNG", optimize=True)
    return out
