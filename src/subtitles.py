"""ASS 字幕の生成。

burned-in にする理由は2つ。無音視聴に耐えること、そして画面の情報量が
上がると視聴維持率（＝収益）が上がること。

見出しは図解（src/visuals.py）側が持っているので、ここでは出さない。
両方が出すと画面上部で重なる。
"""
from __future__ import annotations

from pathlib import Path

FONT = "Noto Sans CJK JP"
MAX_LINE_CHARS = 22
# 縦向き（ショート）は画面が狭いので1行を短くする
MAX_LINE_CHARS_PORTRAIT = 13

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {res_x}
PlayResY: {res_y}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{size},&H00FFFFFF,&H00101010,&H96000000,-1,0,3,6,0,2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _chunk(narration: str, limit: int = MAX_LINE_CHARS) -> list[str]:
    """読点・句点で切って、1行に収まる長さに束ねる。"""
    pieces: list[str] = []
    current = ""
    for ch in narration:
        current += ch
        if ch in "。、！？":
            pieces.append(current)
            current = ""
    if current.strip():
        pieces.append(current)

    lines: list[str] = []
    buf = ""
    for piece in pieces:
        if len(buf) + len(piece) <= limit:
            buf += piece
        else:
            if buf:
                lines.append(buf)
            # 1片で長すぎる場合は機械的に割る
            while len(piece) > limit:
                lines.append(piece[:limit])
                piece = piece[limit:]
            buf = piece
    if buf:
        lines.append(buf)
    return lines or [narration]


def build(segments: list[dict], out_path: Path, portrait: bool = False) -> Path:
    """segments: [{narration, start, end}] を受け取って .ass を書き出す。

    portrait=True でショート向けの縦画面（1080x1920）用に組む。
    画面が狭いので1行の文字数を減らし、字幕の帯も画面の下寄りに置く。
    """
    events: list[str] = []
    limit = MAX_LINE_CHARS_PORTRAIT if portrait else MAX_LINE_CHARS

    for seg in segments:
        start, end = float(seg["start"]), float(seg["end"])
        span = max(0.1, end - start)

        lines = _chunk(seg["narration"], limit)
        total = sum(len(line) for line in lines) or 1
        cursor = start
        for line in lines:
            share = span * (len(line) / total)
            events.append(
                f"Dialogue: 1,{_ts(cursor)},{_ts(min(cursor + share, end))},Caption,,0,0,0,,"
                f"{_escape(line)}"
            )
            cursor += share

    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = HEADER.format(
        font=FONT,
        res_x=1080 if portrait else 1920,
        res_y=1920 if portrait else 1080,
        size=72 if portrait else 64,
        margin_lr=60 if portrait else 120,
        # ショートは下部に UI が重なるので、字幕をかなり上げる
        margin_v=420 if portrait else 72,
    )
    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path
