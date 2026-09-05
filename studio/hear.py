"""完成音声を機械で聞き取り、予定の読みと照合する（オーナー 2026-09-03「最初から最後までを機械で聞き取り…」）。

    予定の読み = say（yomi の語をひらがなに置換） → 数字を読みに → pykakasi でひらがな
    聞いた読み = faster-whisper の文字起こし              → 数字を読みに → pykakasi でひらがな

両側を同じ関数で仮名にするので、同じ漢字は同じ仮名になり、差が出るのは**音が違った所だけ**。
ただし whisper が同音の別の漢字を書いても仮名は同じ（＝見えない）。だから読みが割れる語は
`yomi` で TTS 側に固定しておく（固定した語は、そもそも誤読しない）。ここが見るのは、その外側。
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

import pykakasi

from .script import Script

_kks = pykakasi.kakasi()

_DIG = "〇一二三四五六七八九"


def num_to_kanji(n: str) -> str:
    """'423700' → '四十二万三千七百'。読みの比較用（正確さより両側で同じことが大事）。"""
    n = n.replace(",", "")
    if "." in n:
        a, b = n.split(".", 1)
        return num_to_kanji(a) + "てん" + "".join(_DIG[int(c)] for c in b)
    v = int(n)
    if v == 0:
        return "ゼロ"
    units = ["", "万", "億", "兆"]
    out = ""
    i = 0
    while v > 0 and i < len(units):
        part = v % 10000
        if part:
            out = _four(part) + units[i] + out
        v //= 10000
        i += 1
    return out


def _four(v: int) -> str:
    s = ""
    for unit, div in (("千", 1000), ("百", 100), ("十", 10)):
        d = v // div
        v %= div
        if d:
            s += (_DIG[d] if d != 1 else "") + unit
    if v:
        s += _DIG[v]
    return s


# whisper が声の「かける」「わる」「たす」を記号で書く（実測 09/06 03:3x: 「15万円かける60か月」→「15万円×60か月」で !!）。
# TTS は正しく言っていたので、記号を両側で同じ読みに戻す。声の側に記号は無いので、当たるのは聞いた側だけ。
_SYMBOL_YOMI = {"×": "かける", "✕": "かける", "÷": "わる", "＋": "たす", "+": "たす"}


def to_kana(text: str) -> str:
    # whisper は語のあいだに空白を入れることがある（実測 09/06 08:3x: 「65 歳 から 月 15 万 円 …」）。
    # 空白があると pykakasi が「歳」を1語で読んで「とし」、「七十」を「しち」と読み、TTS は正しかったのに !! が出た。
    # 日本語の声に空白は無いので、両側とも先に消す。
    text = re.sub(r"\s+", "", text)
    for k, v in _SYMBOL_YOMI.items():
        text = text.replace(k, v)
    text = re.sub(r"[0-9][0-9,]*(?:\.[0-9]+)?", lambda m: num_to_kanji(m.group()), text)
    text = text.replace("％", "パーセント").replace("%", "パーセント")
    kana = "".join(w["hira"] for w in _kks.convert(text))
    kana = re.sub(r"[^ぁ-ゖー]", "", kana)
    return kana


def expected_kana(say: str, yomi: dict[str, str]) -> str:
    for k in sorted(yomi, key=len, reverse=True):
        say = say.replace(k, yomi[k])
    return to_kana(say)


class Hearer:
    def __init__(self, size: str = "small"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(size, device="cpu", compute_type="int8")

    def transcribe(self, wav: Path) -> str:
        segs, _ = self.model.transcribe(str(wav), language="ja", beam_size=5)
        return "".join(s.text for s in segs)


def diff_spans(exp: str, got: str, min_len: int = 2) -> list[tuple[str, str]]:
    sm = difflib.SequenceMatcher(None, exp, got, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        a, b = exp[i1:i2], got[j1:j2]
        if max(len(a), len(b)) >= min_len:
            out.append((a, b))
    return out


def check(s: Script, wavs: list[Path], size: str = "small") -> list[dict]:
    """コマごとに {i, say, heard, diffs}。diffs が空なら一致。"""
    h = Hearer(size)
    rows = []
    for i, (seg, wav) in enumerate(zip(s.segments, wavs), 1):
        heard = h.transcribe(wav)
        # 聞いた側にも yomi を当てる: whisper が漢字で書いた「額面」を pykakasi が「ひたいめん」と読み、
        # TTS は正しく「がくめん」と言っていたのに !! が出た（09/05 20:3x）。差が出るのは音が違った所だけ、にする
        exp, got = expected_kana(seg.say, s.yomi), expected_kana(heard, s.yomi)
        rows.append({"i": i, "say": seg.say, "heard": heard, "diffs": diff_spans(exp, got)})
    return rows
