"""長尺のサムネ（1280x720）—— 2026-09-15 00:xx JST・optimizer・Fable が足した。

なぜ: `cmd_schedule` はサムネに **1コマ目の画面（`slide-01.png`）** をそのまま付けていました。
縦のショートではサムネは 1度も見られない（フィードは動画そのものが流れる）ので、それで答えは変わりません。
横の長尺は逆で、**再生の入口は検索と関連の一覧に並ぶサムネと題**です —— 1コマ目の画面は
左に板・右に見出し・下に字幕 の 3つ が 1920x1080 に並ぶ「読む物」で、一覧の中では 320px 幅に縮みます。
`reporting.py` が読む `video_thumbnail_impressions_ctr` は、この絵で決まる数です。

**ここで描く物**（一覧の 320px で読める形）:
  ・背景は注文の絵（cover-fit・暗くしすぎない 0.25。画面の絵は 0.45＝字幕のため）。無ければ単色の勾配
  ・左に暗い帯（字を立たせる）・大きい字 2〜3行（`Script.thumb`。無ければ 1コマ目の `show` の行）
  ・数の行（`thumb` の最後の行が数を含めば黄色）—— 「127万円」の形。数は 1つ だけ
  ・ロゴ・顔・名乗りは無し（CLAUDE.md の根幹「架空の経歴を要らない作り」）

**ショートの答えは 1つも変えません** —— `cmd_schedule` は `form == "long"` のときだけここを通ります
（検査 `tests/test_studio_thumb.py`）。`thumb` は `build_sig` に入れません（mp4 に渡らない ＝ 焼き直しの理由にならない。
`title` と同じ扱い）。

覆る条件: (1) 長尺 3本 の `video_thumbnail_impressions_ctr`（`reporting`）が旧作りの長尺の中央を下回ったら、
この絵の形を疑う（まず字の大きさ・次に帯の濃さ）。(2) オーナーがサムネに言葉を出したら、その言葉が正本。
(3) YouTube が custom thumbnail を拒む（`thumbnails.set` 403 ＝ 電話の確認が無いチャンネル）なら、
`cmd_schedule` は印字して `slide-01.png` へ戻る（いまの try/except のまま）。
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

from . import slides

THUMB_W, THUMB_H = 1280, 720
MAX_LINES = 3
_NUM = re.compile(r"[0-9０-９]")


def lines_for(s) -> list[str]:
    """サムネの行。`Script.thumb` が在ればそれ（3行まで）・無ければ 1コマ目の `show` の行。"""
    lines = [ln.strip() for ln in (getattr(s, "thumb", None) or []) if ln and ln.strip()]
    if not lines and s.segments:
        lines = [ln.strip() for ln in s.segments[0].show.split("\n") if ln.strip()]
    return lines[:MAX_LINES]


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
        im = Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), 0.25)
    else:
        im = slides.background(None, slides.LONG).resize((W, H), Image.LANCZOS)
    # 左の暗い帯（右へ薄くなる）
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    for x in range(W):
        a = int(200 * max(0.0, 1.0 - x / (W * 0.85)))
        bd.line([(x, 0), (x, H)], fill=(0, 0, 0, a))
    im = Image.alpha_composite(im.convert("RGBA"), band)
    d = ImageDraw.Draw(im)
    lines = lines_for(s)
    if not lines:
        return _save(im, out)
    text_w = W - 160
    # 最後の行に数が在れば黄色の数の行。無ければ全部 白
    accent = len(lines) > 1 and bool(_NUM.search(lines[-1]))
    fonts = []
    for k, ln in enumerate(lines):
        big = accent and k == len(lines) - 1
        f, size = _fit(d, ln, slides.FONT_BLACK, 168 if big else 128, 72, text_w)
        fonts.append((f, size, big))
    gap = 18
    total = sum(int(sz * 1.15) for _, sz, _ in fonts) + gap * (len(fonts) - 1)
    y = (H - total) // 2
    for ln, (f, size, big) in zip(lines, fonts):
        fill = (255, 225, 60) if big else (255, 255, 255)
        d.text((80, y), ln, font=f, fill=fill, stroke_width=10, stroke_fill=(0, 0, 0))
        y += int(size * 1.15) + gap
    return _save(im, out)


def _save(im: Image.Image, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out, "PNG", optimize=True)
    return out
