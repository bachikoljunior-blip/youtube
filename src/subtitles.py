"""ASS 字幕の生成。

burned-in にする理由は2つ。ショート的な無音視聴に耐えること、
そして画面の情報量が上がると視聴維持率（＝収益）が上がること。
"""
from __future__ import annotations

from pathlib import Path

FONT = "Noto Sans CJK JP"
MAX_LINE_CHARS = 22

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},64,&H00FFFFFF,&H00101010,&H96000000,-1,0,3,6,0,2,120,120,72,1
Style: Headline,{font},96,&H0028E0FF,&H00101010,&H00000000,-1,0,1,8,3,8,120,120,150,1

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


def _chunk(narration: str) -> list[str]:
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
        if len(buf) + len(piece) <= MAX_LINE_CHARS:
            buf += piece
        else:
            if buf:
                lines.append(buf)
            # 1片で長すぎる場合は機械的に割る
            while len(piece) > MAX_LINE_CHARS:
                lines.append(piece[:MAX_LINE_CHARS])
                piece = piece[MAX_LINE_CHARS:]
            buf = piece
    if buf:
        lines.append(buf)
    return lines or [narration]


def build(segments: list[dict], out_path: Path) -> Path:
    """segments: [{narration, on_screen, start, end}] を受け取って .ass を書き出す。"""
    events: list[str] = []

    for seg in segments:
        start, end = float(seg["start"]), float(seg["end"])
        span = max(0.1, end - start)

        headline = _escape(seg.get("on_screen", "")).strip()
        if headline:
            # 見出しはセグメント冒頭で少しだけ拡大して出す
            events.append(
                f"Dialogue: 0,{_ts(start)},{_ts(end)},Headline,,0,0,0,,"
                f"{{\\fad(220,220)\\t(0,260,\\fscx108\\fscy108)\\t(260,520,\\fscx100\\fscy100)}}{headline}"
            )

        lines = _chunk(seg["narration"])
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
    out_path.write_text(HEADER.format(font=FONT) + "\n".join(events) + "\n", encoding="utf-8")
    return out_path
