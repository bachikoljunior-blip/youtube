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

# 数字と単位のかたまり。この中では改行しない。
# 「23万」「6250円」のように割れると読めなくなる。
# このチャンネルは数字が主役なので、ここは崩さない。
_NUM_TOKEN = set("0123456789円日年月時分秒人回倍万千億％%割点")

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


def _is_kana(ch: str) -> bool:
    return "ぁ" <= ch <= "ゟ"


def _best_cut(piece: str, limit: int) -> int:
    """1行に収まらない文から、**どこで割るか**を選ぶ。

    機械的に limit 文字目で割ると、単語の途中で切れる。実際に
    「額面と手／取りで」「1年き／ざみの」「在職老齢年金は入／れていません」
    のように読めない字幕が出た。

    日本語には空白が無いので語の切れ目は自明ではないが、
    **ひらがなの次に漢字・カタカナ・数字が来る位置は、ほぼ語の頭**になる。
    形態素解析を持ち込まなくても、この一点だけでほとんどの事故が消える。

    優先順位は、句読点の直後 → ひらがなから他種への変わり目 → 諦めて limit。
    数字と単位のかたまりの中では、どの規則より優先して割らない
    （このチャンネルは数字が主役なので「1875円か1687」で切れると読めない）。
    """
    floor = max(2, limit // 2)      # これ以上戻ると行が短くなりすぎる

    def ok(cut: int) -> bool:
        # 数字と単位のかたまりの途中では割らない
        return not (piece[cut - 1] in _NUM_TOKEN and piece[cut] in _NUM_TOKEN)

    # 1. 句読点の直後
    for cut in range(limit, floor - 1, -1):
        if piece[cut - 1] in "、。！？" and ok(cut):
            return cut
    # 2. ひらがな → 漢字・カタカナ・数字の変わり目（ほぼ語の頭）
    for cut in range(limit, floor - 1, -1):
        if _is_kana(piece[cut - 1]) and not _is_kana(piece[cut]) and ok(cut):
            return cut
    # 3. 少なくとも数字は割らない
    cut = limit
    while cut > floor and not ok(cut):
        cut -= 1
    return cut if ok(cut) else limit


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
            # 1片で長すぎる場合は割る。**どこで割るかを選ぶ。**
            while len(piece) > limit:
                cut = _best_cut(piece, limit)
                lines.append(piece[:cut])
                piece = piece[cut:]
            buf = piece
    if buf:
        lines.append(buf)

    # 行頭に句読点を残さない。前の行に戻す。
    # 「75歳開始なら1.84倍で」「、年331万2千円。」のように、
    # 読点が次の行の先頭に来ると読みにくい。
    fixed: list[str] = []
    for line in lines:
        # 空文字は "、。！？" の部分文字列とみなされるので、必ず長さを見ること
        while fixed and line and line[0] in "、。！？":
            fixed[-1] += line[0]
            line = line[1:]
        if line:
            fixed.append(line)
    lines = fixed

    # 「。」だけの行のような、短すぎる余りは前の行に戻す。
    # 縦向きは1行が13字と短いので、句点だけが1行に取り残されやすい。
    merged: list[str] = []
    for line in lines:
        if merged and len(line) <= 2:
            merged[-1] += line
        else:
            merged.append(line)
    return merged or [narration]


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
