"""完成音声を機械で聞き取り、予定の読みと照合する（オーナー 2026-09-03「最初から最後までを機械で聞き取り…」・09/06「漢字の読み変なのいっぱいだよ。今後一個も出ないように考えて」）。

    予定の読み = say（yomi の語をひらがなに置換） → janome（文脈つきの読み）＋ 数字は直接かな
    聞いた読み = faster-whisper に**漢字のトークンを禁じて**書かせた、音そのままの仮名

**09/06 14:xx までの形（whisper に漢字で書かせ、両側を pykakasi で仮名にする）は、誤読が見えなかった。**
実測 09/06 15:xx（Chirp3-HD Charon・small）: `額面`→「ひたいめん」/`年金`→「としかね」と TTS に言わせても、
whisper は文脈から「額面」「年金」と漢字で書き、pykakasi が両側を同じ仮名にするので **一致 と出た**。
同じ漢字に戻される誤読は全部 素通りだった。だから聞く側は漢字を禁じ（`kanji_token_ids`）、音の仮名を取る。

もう1つの実測（同）: **`yomi`（customPronunciations）は語によって効かない。** 大家→たいか・何人→なにじん・
年→ねん・月給→つききゅう・送料→おくりりょう は効いた。額→ひたい・年金→としかね・市場→いちば・辛い→からい・
十分→じゅっぷん は**無視された**（既定の読みのまま）。yomi は「お願い」で、読みが正しいことの証拠ではない。
証拠はこの hear だけ。

照合は「ゆるい仮名」で行う（`loose`）: 長音・促音・を/お・小さい母音など、**音は同じで仮名が揺れる所**は
両側から落とす。それでも残った差が `diffs`。**差が出たら Fable が読んで決める**: TTS の誤読なら yomi か言い換え、
whisper の聞き違い（実測: ねんきん→めんきん/れんきん・4がつ→4かつ・まんえん→まんやん）なら通す。
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

import jaconv
import pykakasi
from janome.tokenizer import Tokenizer

from .script import Script

_kks = pykakasi.kakasi()
_tok = Tokenizer()

# ---------- 数字を直接かなに（pykakasi 経由だと 四→し/よん・七→しち/なな が文脈で揺れた） ----------

_D1 = ["", "いち", "に", "さん", "よん", "ご", "ろく", "なな", "はち", "きゅう"]
_COUNT_TSU = {"1": "ひとつ", "2": "ふたつ", "3": "みっつ", "4": "よっつ", "5": "いつつ", "6": "むっつ", "7": "ななつ", "8": "やっつ", "9": "ここのつ"}


def _four_kana(v: int) -> str:
    s = ""
    for unit, div, one, three, six, eight in (("せん", 1000, "せん", "さんぜん", "ろくせん", "はっせん"),
                                              ("ひゃく", 100, "ひゃく", "さんびゃく", "ろっぴゃく", "はっぴゃく"),
                                              ("じゅう", 10, "じゅう", "さんじゅう", "ろくじゅう", "はちじゅう")):
        q, v = divmod(v, div)
        if q == 1:
            s += one
        elif q == 3:
            s += three
        elif q == 6:
            s += six
        elif q == 8:
            s += eight
        elif q:
            s += _D1[q] + unit
    return s + _D1[v]


def num_to_kana(n: str) -> str:
    """'423700' → 'よんじゅうにまんさんぜんななひゃく'。'0.7' → 'れいてんなな'。両側で同じことが大事。"""
    n = n.replace(",", "")
    if "." in n:
        a, b = n.split(".", 1)
        return (num_to_kana(a) if a else "れい") + "てん" + "".join("れい" if c == "0" else _D1[int(c)] for c in b)
    v = int(n)
    if v == 0:
        return "れい"
    out = ""
    for unit in ("", "まん", "おく", "ちょう"):
        part, v = v % 10000, v // 10000
        if part:
            out = _four_kana(part) + unit + out
        if not v:
            break
    return out


# ---------- 予定の読み ----------

# 書き方で読みが決まっている所（janome が外す。TTS はこう読む）
_PRE = [
    (r"か月", "かげつ"),
    (r"(?<=[0-9０-９])月", "がつ"),                    # 4月
    (r"(?<![0-9０-９一-龥])月(?=[0-9０-９])", "つき"),   # 月5万円（毎月6万円 は janome に任せる）
    (r"(?<![0-9０-９一-龥])年(?=[0-9０-９])", "とし"),   # 裸の「年66万円」は TTS が「とし」と読む（実測 09/05・09/06）。lint が [?] を出す
    (r"([1-9])つ", lambda m: _COUNT_TSU[m.group(1)]),   # 2つ → ふたつ
]
# janome（ipadic）が外す語（実測 09/06）。TTS は正しかった
_JANOME_FIX = {"割る": "わる", "割れ": "われ"}

_NUM = re.compile(r"[0-9][0-9,]*(?:\.[0-9]+)?")
_SYMBOL_YOMI = {"×": "かける", "✕": "かける", "÷": "わる", "＋": "たす", "+": "たす", "−": "ひく", "－": "ひく", "％": "ぱーせんと", "%": "ぱーせんと"}


# 09/06 14:4x（hourly）の「後」→「あと」の置換は入れていない: 聞く側は漢字を禁じたので whisper は「後」を書かず、
# 予定の側は「後」を yomi で固定する（script.py の lint）。両側に当てると「午後」が「ごあと」になる。


def _kana_by_janome(text: str) -> str:
    out = []
    buf = ""
    for t in _tok.tokenize(text):
        sf = t.surface
        if re.fullmatch(r"[0-9.,]+", sf):
            buf += sf
            continue
        if buf:
            out.append(num_to_kana(buf.strip(".,")))
            buf = ""
        if sf in _JANOME_FIX:
            out.append(_JANOME_FIX[sf])
            continue
        r = t.reading
        if r == "*" or not r:
            r = "".join(w["hira"] for w in _kks.convert(sf))
        out.append(jaconv.kata2hira(r))
    if buf:
        out.append(num_to_kana(buf.strip(".,")))
    return "".join(out)


def to_kana(text: str) -> str:
    """字（漢字・数字・記号まじり）→ ひらがなだけ。予定側と、whisper が漢字を混ぜた聞いた側の両方に使う。"""
    text = re.sub(r"\s+", "", text)
    # whisper は「か月」を「ヶ月」「ケ月」「カ月」「箇月」と書く（09/06 14:4x: 「10ヶ月」で pykakasi が「ゖ」を出して !!）
    text = re.sub(r"[ヶケカヵ箇]月", "か月", text)
    for k, v in _SYMBOL_YOMI.items():
        text = text.replace(k, v)
    kana = _kana_by_janome(text)
    kana = jaconv.kata2hira(kana)
    return re.sub(r"[^ぁ-ゖー]", "", kana)


def expected_kana(say: str, yomi: dict[str, str]) -> str:
    for k in sorted(yomi, key=len, reverse=True):
        say = say.replace(k, yomi[k])
    for a, b in _PRE:
        say = re.sub(a, b, say)
    return to_kana(say)


# ---------- ゆるい照合 ----------

# 音は同じ（か、音として区別しない）で仮名が揺れる所。両側に当てる。実測 09/06 の whisper の書き方から
_LOOSE = [("ー", ""), ("っ", ""), ("を", "お"), ("づ", "ず"), ("ぢ", "じ"), ("ぉ", "お"), ("ぇ", "え"), ("ぃ", "い"),
          ("いぇ", "え"), ("やん", "えん"), ("いえん", "えん"), ("ゅう", "ゅ"), ("しち", "なな"), ("ぜろ", "れい")]
# whisper が決まって書き違える語（音は正しい。実測 09/06 で 22コマ中 8コマ）。聞いた側だけに当てる
_WHISPER_ISMS = [("めんきん", "ねんきん"), ("れんきん", "ねんきん"), ("でんきん", "ねんきん"),
                 ("ねんきぃ", "ねんきん"), ("ねんきい", "ねんきん")]
# 「万円」を whisper は マンイェン・マンゲン・マヨン・マイエム … と書く（実測 09/06・6コマ）。音は全部「まんえん」
_MANEN = re.compile(r"ま[んいーう]{0,2}(?:い?[えぇ]ん|げん|ぐえん|やん|よん|あん|えむ|いえむ)")


def loose(k: str) -> str:
    for a, b in _LOOSE:
        k = k.replace(a, b)
    k = re.sub(r"([おこそとのほもよろごぞどぼぽょ])う", r"\1", k)   # きゅうりょう → きゅりょ
    k = re.sub(r"([えけせてねへめれげぜでべぺ])い", r"\1", k)       # ぜいきん → ぜきん
    return k


# whisper が範囲を「84~86さい」「84〜86」と圧縮して書く（実測 09/06 17:2x: 「84歳から86歳」→「84~86」で `!!`）。
# 単位が後ろに付いていれば前の数にも配る（84さいから86さい）。付いていなければ「から」だけ足す
_RANGE_UNIT = r"さい|ねん|かげつ|まんえん|えん|ぱーせんと|かい|にん|にち|ばい|わり"
_RANGE = re.compile(r"([0-9０-９][0-9０-９,]*)\s*[~〜～\-ー]\s*([0-9０-９][0-9０-９,]*)(" + _RANGE_UNIT + r")?")
# 「6倍」を whisper は「6x」と書く（実測 09/06 15:xx）。× は「かける」のまま（_SYMBOL_YOMI）
_TIMES_X = re.compile(r"(?<=[0-9０-９])\s*[xXｘＸ](?![a-zA-Z])")


def _range_sub(m: re.Match) -> str:
    a, b, u = m.group(1), m.group(2), m.group(3) or ""
    return f"{a}{u}から{b}{u}"


def heard_kana(heard: str, yomi: dict[str, str]) -> str:
    heard = re.sub(r"[（(]\d+[)）]", "", heard)   # whisper が付ける「(4)」の番号（実測 09/06 コマ10）
    heard = _TIMES_X.sub("ばい", heard)
    heard = _RANGE.sub(_range_sub, heard)
    k = expected_kana(heard, yomi)   # whisper が漢字を混ぜても同じ道で仮名にする
    for a, b in _WHISPER_ISMS:
        k = k.replace(a, b)
    k = _MANEN.sub("まんえん", k)
    return k


def diff_spans(exp: str, got: str, min_len: int = 2) -> list[tuple[str, str]]:
    """違う所を (予定, 聞こえた) で返す。1字だけ同じ字を挟んだ差はつなぐ（実測 09/06: 月給→「つききゅう」と誤読させた音が
    「げきゅ」vs「つきゆ」で、真ん中の「き」が同じなので 1字の差 2つ に割れ、min_len で消えた）。"""
    sm = difflib.SequenceMatcher(None, exp, got, autojunk=False)
    spans: list[list] = []   # [i1, i2, j1, j2]
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if spans and i1 - spans[-1][1] <= 1 and j1 - spans[-1][3] <= 1:
            spans[-1][1], spans[-1][3] = i2, j2
        else:
            spans.append([i1, i2, j1, j2])
    out = []
    for i1, i2, j1, j2 in spans:
        a, b = exp[i1:i2], got[j1:j2]
        if max(len(a), len(b)) >= min_len:
            out.append((a, b))
    return out


# ---------- 聞く ----------

def _bytes_to_unicode():
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(2**8):
        if b not in bs:
            bs.append(b)
            cs.append(2**8 + n)
            n += 1
    return dict(zip(bs, [chr(c) for c in cs]))


_U2B = {v: k for k, v in _bytes_to_unicode().items()}


def kanji_token_ids(tok) -> list[int]:
    """語彙のうち、UTF-8 の先頭バイト E4〜E9（U+4000〜U+9FFF ＝ 漢字）を含むトークン。whisper に禁じる。
    実測 09/06: 文字で見ると 1,487個 しか無く、whisper はバイト片から「燃筋」「豪傾」を組み立てた。バイトで見ると 1,680個 で止まる。"""
    out = []
    for s, i in tok.get_vocab().items():
        try:
            b = bytes(_U2B[c] for c in s)
        except KeyError:
            continue
        if any(0xE4 <= x <= 0xE9 for x in b):
            out.append(i)
    return sorted(out)


class Hearer:
    def __init__(self, size: str = "small"):
        from faster_whisper import WhisperModel
        self.size = size
        self.model = WhisperModel(size, device="cpu", compute_type="int8")
        self.suppress = kanji_token_ids(self.model.hf_tokenizer)

    def transcribe(self, wav: Path, prompt: str | None = None) -> str:
        """漢字を禁じた聞き取り（仮名・数字・記号）。"""
        kw = {"initial_prompt": prompt} if prompt else {}
        segs, _ = self.model.transcribe(str(wav), language="ja", beam_size=5, suppress_tokens=self.suppress,
                                        condition_on_previous_text=False, repetition_penalty=1.2,
                                        no_repeat_ngram_size=3, **kw)
        return "".join(s.text for s in segs)

    def transcribe_plain(self, wav: Path) -> str:
        """漢字ありの聞き取り（人が読むため。照合には使わない）。"""
        segs, _ = self.model.transcribe(str(wav), language="ja", beam_size=5)
        return "".join(s.text for s in segs)


def degenerate(heard: str, exp: str) -> bool:
    """漢字を禁じると whisper が崩れることがある（実測 09/06: 「、、、、」の連打・空）。短すぎる／同じ片の連打で見る。"""
    k = to_kana(heard)
    return len(k) < 0.7 * len(exp) or bool(re.search(r"(.{1,3})\1{4,}", heard))


_PROMPT = "ひらがなだけでかきます。すうじもひらがなでかきます。"


def check(s: Script, wavs: list[Path], size: str = "small", escalate: bool = True) -> list[dict]:
    """コマごとに {i, say, heard, exp, got, diffs}。diffs が空なら一致。

    small で差が出たコマだけ medium で聞き直し、差が少ないほうを採る（`escalate`）。
    実測 09/06 17:xx（hourly）: small の `!!` 3/11 は全部 whisper 側で、medium は 3つとも予定どおりに聞いた
    （末尾の1語の欠落・1か月→1かけず・11年→11イネ）。TTS の誤読なら medium でも同じ差が残るので、隠れない。
    medium を全コマの既定にしない理由: 2.5倍 遅く、`!!` は減らなかった（6/11。§4 (2)）。"""
    h = Hearer(size)
    h2: Hearer | None = None
    rows = []
    for i, (seg, wav) in enumerate(zip(s.segments, wavs), 1):
        exp = expected_kana(seg.say, s.yomi)
        heard = h.transcribe(wav)
        how = size
        if degenerate(heard, exp):
            heard, how = h.transcribe(wav, _PROMPT), size + "+prompt"
        if degenerate(heard, exp) and size != "medium":
            h2 = h2 or Hearer("medium")
            heard, how = h2.transcribe(wav), "medium"
        got = heard_kana(heard, s.yomi)
        diffs = diff_spans(loose(exp), loose(got))
        if diffs and escalate and size != "medium" and how != "medium":
            h2 = h2 or Hearer("medium")
            heard2 = h2.transcribe(wav)
            got2 = heard_kana(heard2, s.yomi)
            diffs2 = diff_spans(loose(exp), loose(got2))
            if len(diffs2) < len(diffs) or (len(diffs2) == len(diffs) and not degenerate(heard2, exp)
                                            and sum(map(len, map("".join, diffs2))) < sum(map(len, map("".join, diffs)))):
                heard, got, diffs, how = heard2, got2, diffs2, f"{size}→medium"
        rows.append({"i": i, "say": seg.say, "heard": heard, "how": how,
                     "exp": loose(exp), "got": loose(got), "diffs": diffs})
    return rows
