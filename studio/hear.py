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
import subprocess
from pathlib import Path

import jaconv
import pykakasi
from janome.tokenizer import Tokenizer

from .common import probe_duration, run
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
    (r"(?<=[何数])千", "ぜん"),                          # 何千円・数千円（janome は せん。TTS は ぜん）
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


# 「3千円」「8千円」「1千万円」「3百円」: janome は 千・百 を別の語に切り「さんせん」「はちせん」「いちせん」「さんひゃく」と読む。
# TTS は さんぜん・はっせん・いっせん・さんびゃく と正しく言うので、予定の側だけが外れて `!!` になっていた
# （実測 09/06 19:5x・あすの本 コマ6「6万3千円」。hourly の申し送り）。数字に畳んで `num_to_kana` に渡す（連濁はそこに在る）。
_D = r"[0-9０-９]+"
_KANJI_UNITS = [   # 大きい単位から。3千5百20 → 3520・21万3千 → 21万3000・1千万 → 1000万・3百 → 300
    (re.compile(rf"(?<![0-9０-９])({_D})千(?:({_D})百)?(?:({_D})十)?({_D})?(?![0-9０-９]*[千百十])"), (1000, 100, 10, 1)),
    (re.compile(rf"(?<![0-9０-９])({_D})百(?:({_D})十)?({_D})?(?![0-9０-９]*[百十])"), (100, 10, 1)),
    (re.compile(rf"(?<![0-9０-９])({_D})十({_D})?(?![0-9０-９]*十)"), (10, 1)),
]


def _fold_kanji_units(text: str) -> str:
    for pat, weights in _KANJI_UNITS:
        def rep(m: re.Match, weights=weights) -> str:
            return str(sum(int(jaconv.z2h(g, digit=True)) * w for g, w in zip(m.groups(), weights) if g))
        text = pat.sub(rep, text)
    return text


def to_kana(text: str) -> str:
    """字（漢字・数字・記号まじり）→ ひらがなだけ。予定側と、whisper が漢字を混ぜた聞いた側の両方に使う。"""
    text = re.sub(r"\s+", "", text)
    text = _fold_kanji_units(text)
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
_LOOSE = [# ゔ は小さい母音より先に（後だと ゔぃ → ゔい → ぶい。実測 09/06 22:xx「テーキヴィン」）
          ("ゔぁ", "ば"), ("ゔぃ", "び"), ("ゔぇ", "べ"), ("ゔぉ", "ぼ"), ("ゔ", "ぶ"), ("ゑ", "え"), ("ゐ", "い"),
          ("ー", ""), ("っ", ""), ("を", "お"), ("づ", "ず"), ("ぢ", "じ"), ("ぉ", "お"), ("ぇ", "え"), ("ぃ", "い"),
          ("いぇ", "え"), ("やん", "えん"), ("いえん", "えん"), ("ゅう", "ゅ"), ("しち", "なな"), ("ぜろ", "れい")]
# whisper が決まって書き違える語（音は正しい。実測 09/06 で 22コマ中 8コマ）。聞いた側だけに当てる
_WHISPER_ISMS = [("めんきん", "ねんきん"), ("れんきん", "ねんきん"), ("でんきん", "ねんきん"),
                 ("ねんきぃ", "ねんきん"), ("ねんきい", "ねんきん"),
                 ("ゑう", "ゅう")]   # 「よんじゅう」を medium が「よんじゑう」と書いた（実測 09/06 19:5x）。予定の側に ゑ は出ない
# 「万円」を whisper は マンイェン・マンゲン・マヨン・マイエム … と書く（実測 09/06・6コマ）。音は全部「まんえん」
_MANEN = re.compile(r"ま[んいーう]{0,2}(?:い?[えぇ]ん|げん|ぐえん|やん|よん(?!せん|ぜん|[ひびぴ]ゃく|じゅ)|あん|えむ|いえむ)")
# 「まんよん」は 万円 の聞き違いだが、「11万4千円」の「まんよんせん」まで まんえん に畳んでいた（09/07 01:xx 実測:
# 予定 じゅういちまんよんせんえん ↔ 聞いた 114,000えん → じゅういちまんえんせんえん。1字差なので diff_spans が吸って見えなかった）。
# 後ろに 千・百・十 が続く「よん」は数字なので畳まない。
_BROKEN_GROUP = re.compile(r"(\d),(\d{1,2})(?!\d)")   # whisper の桁区切りの欠け「63,00」（6万3千円の音。09/07 00:5x hourly）→ 63,000
# 「3千円」を whisper は「3000ゲン」と書く（実測 09/06 22:xx・コマ6）。万円 の外の「円」も同じ癖なので 千・百 の後だけ吸う
_YEN_AFTER_UNIT = re.compile(r"(せん|ぜん|ひゃく|びゃく|ぴゃく)げん")


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
    heard = re.sub(r"[（(\[［]\d+[)）\]］]", "", heard)   # whisper が付ける「(4)」「[1]」の番号（実測 09/06 コマ10。[1] は「いち」に読まれていた）
    heard = _TIMES_X.sub("ばい", heard)
    heard = _RANGE.sub(_range_sub, heard)
    heard = _BROKEN_GROUP.sub(lambda m: m.group(1) + "," + m.group(2).ljust(3, "0"), heard)
    k = expected_kana(heard, yomi)   # whisper が漢字を混ぜても同じ道で仮名にする
    for a, b in _WHISPER_ISMS:
        k = k.replace(a, b)
    k = _MANEN.sub("まんえん", k)
    k = _YEN_AFTER_UNIT.sub(r"\1えん", k)
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
    """語彙のうち、UTF-8 の先頭バイト E4〜E9（U+4000〜U+9FFF ＝ 漢字）と EA〜ED（U+A000〜U+D7FF ＝ ハングルなど。仮名は E3）を含むトークン。whisper に禁じる。
    実測 09/06: 文字で見ると 1,487個 しか無く、whisper はバイト片から「燃筋」「豪傾」を組み立てた。バイトで見ると 1,680個 で止まる。
    09/06 22:xx: 漢字を禁じた small が「5年」を「5 년」（ハングル）と書いた（あすの本 コマ3）。ハングルの帯も禁じる。"""
    out = []
    for s, i in tok.get_vocab().items():
        try:
            b = bytes(_U2B[c] for c in s)
        except KeyError:
            continue
        if any(0xE4 <= x <= 0xED for x in b) or b"\xe3\x80\x85" in b or b"\xe3\x80\x86" in b or b"\xe3\x80\x87" in b:
            out.append(i)   # 々〆〇（U+3005〜3007）は仮名と同じ先頭バイト E3 なので3バイトで見る。ハングルを禁じた small が次に「〇〇」「〆」を書いた（09/06 22:xx）
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

    def transcribe_words(self, wav: Path, prompt: str | None = None) -> list[tuple[str, float, float]]:
        """漢字を禁じた聞き取りを、語ごとの (語, 始まり, 終わり) で。`tail_voice` が末尾の時刻を引く。"""
        kw = {"initial_prompt": prompt} if prompt else {}
        segs, _ = self.model.transcribe(str(wav), language="ja", beam_size=5, suppress_tokens=self.suppress,
                                        condition_on_previous_text=False, repetition_penalty=1.2,
                                        no_repeat_ngram_size=3, word_timestamps=True, **kw)
        return [(w.word, w.start, w.end) for s in segs for w in (s.words or [])]

    def transcribe_plain(self, wav: Path) -> str:
        """漢字ありの聞き取り（人が読むため。照合には使わない）。"""
        segs, _ = self.model.transcribe(str(wav), language="ja", beam_size=5)
        return "".join(s.text for s in segs)


TAIL_PROBE_SEC = 5.0   # 末尾だけを聞き直すときに切り出す長さ（実測 09/09 05:5x: コマ8 は 11.1秒 で、末尾 5秒 に欠けた並びが全部 入る）


def tail_gap(exp: str, diffs: list[tuple[str, str]]) -> str | None:
    """差が「予定の末尾が丸ごと音に無い」形なら、その並びを返す（そうでなければ None）。

    **whisper は長いコマの末尾を落とします**（実測 2026-09-09 05:5x・optimizer・Opus。09/10 の本 コマ8・59字 11.1秒）:
    small も medium も、末尾の「多ければ計算が変わります」を1字も書きませんでした。
    §4 (2) は「TTS の誤読なら medium でも同じ差が残るので隠れない」と書いていますが、
    **この型は medium でも同じ差が残るのに、TTS の誤読ではありません** ——
    `escalate` は medium を撃って「差が減らない」と見て small のまま置き、
    台帳には「予定『おおければけさんがかわります』 聞こえた『』」だけが残ります。
    ＝ **段を上げる手では、切り落とし と 誤読 を分けられません。**（`tail_probe` が分けます）"""
    if not diffs:
        return None
    e, g = diffs[-1]
    return e if g == "" and len(e) >= 4 and exp.endswith(e) else None

def degenerate(heard: str, exp: str) -> bool:
    """漢字を禁じると whisper が崩れることがある（実測 09/06: 「、、、、」の連打・空）。短すぎる／同じ片の連打で見る。"""
    k = to_kana(heard)
    return len(k) < 0.7 * len(exp) or bool(re.search(r"(.{1,3})\1{4,}", heard))



def tail_probe(h: "Hearer", wav: Path, missing: str, yomi: dict[str, str], sec: float = TAIL_PROBE_SEC) -> dict:
    """コマの**末尾 sec 秒だけ**を聞き直して、`missing`（予定に在って音に無かった末尾の並び）が
    そこに在るかを見る。在れば「whisper が切り落とした」・無ければ「TTS が別に読んだ／読んでいない」。

    **足す前に、元の手と違う物を見ることを撃って確かめました**（§5 の「教訓の形」）——
    `escalate`（段を上げる）は同じ 11秒 の音を medium で聞き直すだけで、**同じ所で切れます**。
    こちらは**同じ模型に短い音を渡す**ので、答えが割れます（実測 2026-09-09 05:5x・API 0単位）:

        コマ8 全部 small   …ときのかたちで                        ← 末尾が無い
        コマ8 全部 medium  …おっとのはんぶんより                  ← medium は**もっと**早く切れた
        コマ8 **末尾 5秒** medium  …おおければけいさんがかわります  ← **在る**（0差）

    **陽性対照**（同じ回に撃った・捨てないこと）: 同じコマの末尾だけを
    「年66万円ふえます」（裸の年 ＝ Neural2-D が「とし」と読む・§3 の 9）に差し替えて焼くと、
    全部の聞き取りは**同じ形**で切れ（予定「ねんろくじゅろくまんえんふえます」 聞こえた「」）、
    **末尾 5秒 は「としろくじゅろくまんえんふえます」と聞いて 差が残ります**。
    ＝ **この手は「切り落とし」だけを通し、「誤読」は通しません。**

    返すもの: `{"heard": 末尾の仮名, "diffs": 残った差, "ok": 差が無いか}`。
    `ok` でも**一致の数には入れません**（決めるのは Fable・§4 (2)）。
    **覆る条件**: `ok` が出たコマを Fable が 3本 続けてそのまま通したら、そのときは一致に数えてよい
    （＝ 人が読む所を1つ減らせる）。逆に `ok` なのに耳で聞くと欠けている本が1本でも出たら、この手ごと外すこと。"""
    clip = wav.with_name(wav.stem + "-tail.wav")
    dur = probe_duration(wav)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ss", str(max(0.0, dur - sec)), str(clip)])
    heard = h.transcribe(clip)
    got = loose(heard_kana(heard, yomi))
    # 切り出した頭に前の語が入り込むが、それは **exp 側が空の差**になるので落とすだけでよい。
    # **末尾の窓（`got[-(len(missing)+4):]`）で切ってから比べる形も書いて、撃って外した**（2026-09-09 05:5x）——
    # 実測の2つ（切り落とし・陽性対照の誤読）でも検査 6件 でも、窓の有無で答えが1つも変わらなかった。
    # ＝ **同じ物を見る2つ目の手**なので置かない（§5 の「確かめる手を足すときは、元の手と違う物を見ているかを先に撃つ」）。
    diffs = [(e, g) for e, g in diff_spans(missing, got) if e]
    return {"heard": got, "diffs": diffs, "ok": not diffs}


ENERGY_THRESH = 0.05    # 無音の閾（その wav のいちばん大きい窓に対する割合）
ENERGY_WIN = 0.05       # 窓の長さ（秒）
VOICE_GAP_PRESENT = 0.4 # これ以上 空いていれば「音は在る」（5モーラぶん ＝ 「たされます」1語）
VOICE_GAP_ABSENT = 0.2  # これ未満なら「音が無い」。あいだは**分けない**


def energy_end(wav: Path, thresh: float = ENERGY_THRESH, win: float = ENERGY_WIN) -> float:
    """音のエネルギーが最後に閾を越えた時刻（秒）。**聞き取りを1度もしません。**"""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    n = max(1, int(16000 * win))
    if len(x) < n:
        return 0.0
    x = x[: len(x) // n * n].reshape(-1, n)
    rms = np.sqrt((x * x).mean(axis=1))
    if not rms.max():
        return 0.0
    loud = np.nonzero(rms >= thresh * rms.max())[0]
    return float((loud[-1] + 1) * win) if len(loud) else 0.0


def tail_voice(h: "Hearer", wav: Path, prompt: str | None = None) -> dict:
    """**音の終わり**と、**仮名モードが最後に書いた語の終わり**を比べる（2026-09-09 16:2x・optimizer・Opus）。

    **これは `hourly` の申し送りです**（09/09 10:4x・§4 (2)）—— その回、末尾の差が出た コマ7 で
    `tail_probe` と `tail_rate` が**2つとも「TTS 側を疑え」と答え、2つとも外れました**。
    hourly が耳の代わりに撃った2つ（音のエネルギーの終わり 8.10秒／漢字を許した medium が
    `word_timestamps` で「足されます。」を 7.58〜8.42秒 に書いた）が当たっており、
    **その手を道具に入れたのが、この関数です。**

    **なぜ 3つ目を足すのか**（§5 の「必ず一致する2つ目の意見に、確かめる力は無い」——
    足す前に、元の2つと**違う物を見ているか**を撃って確かめること）:

        `tail_probe`  末尾 5秒 を**もう一度 聞き取る**      → whisper が窓の中でも切ると、同じ所で落ちる
        `tail_rate`   **予定の字数**と長さの比を帯で見る    → 帯は一致したコマから作るので、
                                                             長いコマが通ると広がり、5字 の欠けが帯に入る
        `tail_voice`  **音そのもの**（エネルギー）と、
                      **聞き取りが止まった時刻**の差        → 聞き取りを 1回 しかせず、
                                                             判定の片側は模型を通らない

    ＝ 3つ目だけが、**「模型が書かなかった所に音が在るか」を音の側から**見ます。

    返すもの: `{"energy_end", "word_end", "gap", "verdict"}`。
    `verdict` は `音は在る`（gap ≥ 0.4秒 ＝ whisper が切った）／`音が無い`（gap < 0.2秒 ＝ TTS 側を疑う）／
    **`分けられない`**（あいだ）。**一致の数は変えません**（決めるのは Fable・§4 (2)）。
    **あいだを「在る」に丸めないこと** —— 5モーラ 未満の欠けは、この手では分けられません。

    **覆る条件**: `音は在る` と出たコマを耳で聞いて欠けていた回が1度でも出たら、この手を外す。
    逆に 3本 続けて当たったら、`tail_probe` の「TTS 側を疑う」の印字をやめ、こちらに寄せる
    （そのとき `tail_probe` は 0差 の確認だけに使う）。
    **`分けられない` が 3本 続けて出るなら、閾（0.2／0.4秒）が音の実物と合っていない** ——
    そのときは閾ではなく、**欠けた語のモーラ数から要る秒数を出す**側へ変えること。"""
    words = h.transcribe_words(wav, prompt)
    end = words[-1][2] if words else 0.0
    e = energy_end(wav)
    gap = e - end
    verdict = "音は在る" if gap >= VOICE_GAP_PRESENT else ("音が無い" if gap < VOICE_GAP_ABSENT else "分けられない")
    return {"energy_end": round(e, 2), "word_end": round(end, 2), "gap": round(gap, 2), "verdict": verdict}


def tail_rate(exp_len: int, gap_len: int, dur: float, band: tuple[float, float]) -> dict:
    """**秒数の側から**、末尾が音に在るかを見る（2026-09-09 06:5x・optimizer・Opus）。

    `tail_probe` は「末尾 5秒 を同じ模型に渡す」手で、**聞き取りをもう1回する**ものです。
    ところが whisper は**渡された音の終わりを切る**ことがあり、そのときは
    **末尾だけを渡しても同じ所で切れます** ＝ 5秒 の窓でも末尾が出ず、
    `tail_probe` は「差が残る → TTS 側を疑う」と答えます。**これは誤りです。**

    実測 2026-09-09 06:5x（09/10 の本・コマ7「…50万円が、遺族の分として足されます。」）:

        全部 small→medium+prompt   …ごじゅまんへんがいぞくのぶんとして   ← 「たされます」が無い
        **末尾 5秒** medium        ごじゅまんえんまでたりないごじゅまんえんが
                                   ← **窓の中の末尾（いぞくのぶんとしてたされます）も落ちた**
        → `tail_probe` は `ok=False`（TTS 側を疑え）と答えた

    **こちらは音の長さを見るので、聞き取りとは別の物を見ます**（§5 の「教訓の形」——
    確かめる手を足すときは、それが元の手と違う物を見ているかを先に撃つ）。
    同じコマの秒数は、末尾を**読んでいる**前提でしか説明が付きません:

        コマ7  48字 / 9.2秒 = **5.22 字/秒**（この本の帯 4.77〜5.53 の中）
               「たされます」(5字) が音に無いなら 43字 / 9.2秒 = **4.67 字/秒** ＝ **帯の外**
        コマ3  64字 / 12.2秒 = 5.25 字/秒 ／ 末尾 17字 が無いなら **3.85 字/秒** ＝ 帯の外

    ＝ **どちらも音は在り、切ったのは whisper です**（`tail_probe` の答えと逆）。

    帯は**その本の 一致したコマ だけ**から作ります（差の在るコマを分母に入れると、
    測ろうとしている物で物差しを作ることになる）。

    **この手が分けられるのは「音そのものが無い」か「音は在る」かの1つだけです。**
    **誤読 と 切り落とし は分けません** —— TTS が末尾を別の語で読んだ場合も音の長さは残るので、
    ここは `present` に出ます。そちらを分けるのは `tail_probe` の仕事で、
    **2つは並べて読みます**（`tail_probe` が末尾の語を聞き取れた ＝ 切り落とし／
    別の語を聞き取った ＝ 誤読／何も聞き取れないのに `present` ＝ **窓の側も切られた**）。

    返すもの: `{"rate": いまの速さ, "without": 末尾が無い場合の速さ, "band": 帯,
                "present": 末尾が無いと帯の外へ出るか}`。
    **`present` でも一致の数には入れません**（決めるのは Fable・§4 (2)）。
    **覆る条件**: `present` と `tail_probe.ok` が食い違ったコマを、耳で聞いて
    `tail_probe` のほうが当たっていた回が1度でも出たら、この手を外すこと。
    逆に 3本 続けて `present` の側が当たったら、`tail_probe` の「TTS 側を疑う」の
    印字をやめ、こちらに寄せること（そのときは `tail_probe` は 0差 の確認だけに使う）。"""
    lo, hi = band
    rate = exp_len / dur if dur else 0.0
    without = (exp_len - gap_len) / dur if dur else 0.0
    return {"rate": round(rate, 2), "without": round(without, 2),
            "band": (round(lo, 2), round(hi, 2)), "present": without < lo}


_PROMPT = "ひらがなだけでかきます。すうじもひらがなでかきます。"


def check(s: Script, wavs: list[Path], size: str = "small", escalate: bool = True) -> list[dict]:
    """コマごとに {i, say, heard, exp, got, diffs}。diffs が空なら一致。

    small で差が出たコマだけ medium で聞き直し、差が少ないほうを採る（`escalate`）。
    実測 09/06 17:xx（hourly）: small の `!!` 3/11 は全部 whisper 側で、medium は 3つとも予定どおりに聞いた
    （末尾の1語の欠落・1か月→1かけず・11年→11イネ）。TTS の誤読なら medium でも同じ差が残るので、隠れない。
    medium を全コマの既定にしない理由: 2.5倍 遅く、`!!` は減らなかった（6/11。§4 (2)）。

    **段を上げても分けられない型が1つ在ります**（2026-09-09 05:5x・optimizer・Opus）: 長いコマの**末尾の切り落とし**。
    medium は同じ所か、もっと手前で切ります。差が「予定の末尾が丸ごと無い」形のときだけ `tail_probe` を撃ち、
    行に `tail`（末尾 5秒 だけの聞き取り）を足します。**一致の数は変えません**（決めるのは Fable・§4 (2)）。"""
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
            # medium でも差が残ったら medium＋prompt も試す（09/07 01:xx optimizer 実測: コマ5「60歳から64歳の5年で…684万円」を
            # small が「60 〇〇から 64 〃の 5 〉で … 680 4」・medium が「60~64の5で…684,000」と数字の帯に崩し（差 5・7）、
            # medium＋prompt だけが 0差。数が密なコマで whisper が助数詞を捨てる型。TTS の誤読なら prompt でも同じ差が残る）
            for prompt, label in ((None, f"{size}→medium"), (_PROMPT, f"{size}→medium+prompt")):
                heard2 = h2.transcribe(wav, prompt)
                got2 = heard_kana(heard2, s.yomi)
                diffs2 = diff_spans(loose(exp), loose(got2))
                if _fewer(diffs2, heard2, diffs, exp):
                    heard, got, diffs, how = heard2, got2, diffs2, label
                if not diffs:
                    break
        row = {"i": i, "say": seg.say, "heard": heard, "how": how,
               "exp": loose(exp), "got": loose(got), "diffs": diffs}
        gap = tail_gap(loose(exp), diffs) if escalate else None
        row["_gap"] = gap
        row["_wav"] = wav
        if gap:   # 末尾が丸ごと無い ＝ 段を上げても分けられない型。末尾だけを聞き直して 切り落とし と 誤読 を分ける
            h2 = h2 or Hearer("medium" if size != "medium" else size)
            row["tail"] = tail_probe(h2, wav, gap, s.yomi)
            # 音の側から見る3つ目（`tail_voice` の註）。**その行を書いた模型で**時刻を引く
            # —— 段が上がった行の語の終わりを、既定の段で引き直すと、比べている物がずれる。
            hw = h2 if "medium" in how else h
            row["voice"] = tail_voice(hw, wav, _PROMPT if "prompt" in how else None)
        rows.append(row)
    _add_rates(rows)
    for r in rows:
        r.pop("_gap", None)
        r.pop("_wav", None)
    return rows


def _add_rates(rows: list[dict]) -> None:
    """末尾が丸ごと無いコマに、秒数の側の見立てを足す（`tail_rate` の註）。

    **切り落としが1つも無い回は、音の長さを1度も測りません**（`probe_duration` は ffprobe を呼ぶので、
    鳴っていない回にまで撃つと、そのぶん遅くなるし、音が無い所で落ちる）。
    帯は**一致したコマだけ**から作る —— 差の在るコマを分母に入れると、測ろうとしている物で物差しを作ることになる。
    """
    if not any(r.get("_gap") for r in rows):
        return
    durs: dict[int, float] = {}
    for r in rows:
        try:
            durs[r["i"]] = probe_duration(r["_wav"])
        except Exception:                                          # noqa: BLE001
            return   # 長さが引けない回は、秒数の側を黙って出さない（`tail_probe` の答えだけが残る）
    ok_rates = [len(r["exp"]) / durs[r["i"]] for r in rows if not r["diffs"] and durs.get(r["i"])]
    if not ok_rates:
        return
    band = (min(ok_rates), max(ok_rates))
    for r in rows:
        if r.get("_gap") and durs.get(r["i"]):
            r["rate"] = tail_rate(len(r["exp"]), len(r["_gap"]), durs[r["i"]], band)


def escalations(rows: list[dict]) -> dict[str, str]:
    """台帳に書く「コマ → 通った段」（既定の模型で通ったコマは書かない）。
    09/07 01:3x の覆る条件「7本で `medium+prompt` が 1度も採られなければ段を外す」は、台帳の `heard` に段が無いと数えられなかった
    （`escalated` はコマ番号だけ）。"""
    return {str(r["i"]): r["how"] for r in rows if "→" in r["how"] or "+prompt" in r["how"]}


def _fewer(new: list, heard_new: str, old: list, exp: str) -> bool:
    """聞き直しの結果を採るか: 差の数が減った／同数なら崩れておらず差の字数が短い。"""
    if len(new) < len(old):
        return True
    return (len(new) == len(old) and not degenerate(heard_new, exp)
            and sum(map(len, map("".join, new))) < sum(map(len, map("".join, old))))
