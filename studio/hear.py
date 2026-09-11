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
from .script import Script, sentence_lens

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


def _particle_he(reading: str, phonetic: str) -> str:
    """助詞の「へ」だけ、janome の 発音（エ）を採る。**「は」は採らない**（下の実測）。

    janome（ipadic）は 読み と 発音 を別に持ち、**表記どおりの助詞だけが割れます**:
    助詞 は 読み ハ／発音 ワ・助詞 へ 読み ヘ／発音 エ（ほかに割れるのは 厚生 コウセイ→コーセイ 型の
    長音表記だけで、そちらは `loose()` が両側で畳むので触らない）。

    **2026-09-11 21:2x（optimizer・Opus）に、どちらを採るかを台帳から数えて分けました**
    （API 0単位・TTS 0回。16:4x の `hourly` の申し送り「助詞だけを別の問いで撃つ」の答え）:

        09/12 の本 12コマ の助詞 **18件**（は 16・では 1・へ 1）に対し、
        20:30 の `heard` の 1字差（`near`）に出た 助詞 は **1件だけ**（コマ3 予定「は」↔ 聞いた「わ」）
        ＝ **whisper は 助詞の「は」を 16/17 で字のまま「は」と書きます。**

    ＝ **「は」の側は、音がどちらでも `は` と書かれるので、原理的に分けられません**
    （TTS が「ハ」と読み違えても、正しく「ワ」と読んでも、聞いた側は同じ「は」）。
    **だから予定の側を「わ」にしてはいけません** —— 1本 16件 の偽の `[?]` が増えるだけで、
    見えるものは 1つ も増えません。

    **「へ」は逆でした**: 実測 2/2 で whisper は音の側（え）を書いています
    （09/10・09/12 の本の コマ1「もらう人へ」→「もらうひとえ」・13:2x と 16:4x の目視）。
    ＝ **予定の側を「え」にすれば、TTS が「ヘ」と読んだ回だけが 1字差で鳴ります**（片側だけの問い）。
    そのために `_LOOSE` の `へ→え` を外しました（**語中の「へ」（部屋→へや）は両側とも読みが「へ」なので、
    外しても比べは壊れません** —— 割れるのは助詞の「へ」だけで、そこは予定の側が「え」になった）。

    **覆る条件**: (1) 助詞の「へ」で `[?]` が 3本 続けて鳴ったら、鳴らしているのは TTS ではなく
    **whisper が字のまま「へ」と書く回**なので、`_LOOSE` の `へ→え` を戻すこと（そのとき「へ」の側も
    「は」と同じ「分けられない」に落ちます ＝ §2 の (b) 抑揚だけが残る）。
    (2) 逆に `[?]` が鳴った回の音を聞いて本当に「ヘ」だったら、§2 の (1)（語を書き換える）で直し、
    その語を §2 に書くこと（オーナー 09/11 12:4x「ひらがなも漢字もあった」の、ひらがなの側の 1例目）。
    (3) 「は」の側は、**whisper が「わ」と書く率が 3本 続けて半分を越えたら**引き直すこと
    （そのとき初めて「は」も片側の問いになる）。
    """
    if phonetic and phonetic != "*" and phonetic != reading and phonetic == reading.replace("ヘ", "エ"):
        return phonetic
    return reading


def _kana_by_janome(text: str, particle_he: bool = True) -> str:
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
        elif particle_he:
            r = _particle_he(r, t.phonetic)
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


def to_kana(text: str, particle_he: bool = True) -> str:
    """字（漢字・数字・記号まじり）→ ひらがなだけ。予定側と、whisper が漢字を混ぜた聞いた側の両方に使う。

    `particle_he=False` は**聞いた側だけ**（`heard_kana`）。助詞の「へ」を音（え）に直すのは
    **予定の側の仕事**で、聞いた側に当てると **whisper が書いた「へ」まで「え」に直してしまい、
    片側の問いが閉じます**（`_particle_he` の註）。
    """
    text = re.sub(r"\s+", "", text)
    text = _fold_kanji_units(text)
    # whisper は「か月」を「ヶ月」「ケ月」「カ月」「箇月」と書く（09/06 14:4x: 「10ヶ月」で pykakasi が「ゖ」を出して !!）
    text = re.sub(r"[ヶケカヵ箇]月", "か月", text)
    for k, v in _SYMBOL_YOMI.items():
        text = text.replace(k, v)
    kana = _kana_by_janome(text, particle_he)
    kana = jaconv.kata2hira(kana)
    return re.sub(r"[^ぁ-ゖー]", "", kana)


_ONE_KANJI = re.compile(r"[一-龥々]")


def _apply_one_kanji_yomi(say: str, ones: dict[str, str]) -> str:
    """**1字の漢字の `yomi` は、janome が1語と見た所にだけ当てる**（2026-09-11 01:3x JST・optimizer・Opus）。

    **穴（09/11 00:4x に踏み、この回に道具へ移した）**: 予定の側の `yomi` は**素の文字列 replace** で、
    語の境目を見ていませんでした。書き手が裸の「日」のために `日 → ひ` を入れると、
    同じ 1字 が**助数詞「1日」にも当たり**、予定が **いちひ**（音は いちにち で **TTS は正しい**）になる。
    ＝ **hear が、正しく読めた本を `!!` で名指しする**（`§15` の 1回目の hear の外れ 1件 は全部これ）。

    **なぜ TTS 側では起きないか**: `customPronunciations` は語で当たるので、TTS は「1日」を割りません。
    **割れるのは予定の側だけ** ＝ これは本の欠陥ではなく、**測る側の欠陥**です。

    **なぜ lint では塞げないか**: `script.uncovered_kanji` は先に `COUNTER_RUN` で助数詞を消してから
    yomi を当てるので、**助数詞の側は「読みを固定しなくてよい」と正しく判定します**。
    ＝ 2つの口が**同じ dict を別の規則で当てていた**（片方は語を見る・片方は見ない）のが本体。

    **当てない所は 2つ**（どちらも実測で割れ、陽性対照で落としてある）:

        数の直後（前の語が `名詞,数`）  1日 → いちひ（正 いちにち）・3人 → さんひと・1分 → いちぶん・
                                     10月分 → じゅうつきぶん（正 じゅうがつぶん）
        1語の中に埋まっている          初日 → はつひ（正 しょにち）・半年 → はんねん・6か月 → ろくかがつ

    **3つ目を書いて、消しました**（`名詞,接尾,助数詞` を別に見る枝）。**陽性対照が落ちません** ——
    外しても検査は 7件 とも通ります。janome に助数詞を出させて数えると、
    **1日・3人・数年・何人も・十数年・数か月 とも、助数詞の前は必ず `名詞,数`** で、
    「数の直後」が**先に**当たっていました（＝ 同じ所を 2度 見ていた枝）。
    **落ちない対照つきの枝は置かないこと**（§5 の教訓の形3つ目・09/10 01:2x の `月分?` の並び順と同じ形）。

    **当てる所は今までどおり**（「その日」→ そのひ）。長い鍵は先に当てるので、
    `月収 → げっしゅう` のような複合語は 1字 の `月` に触られません（実測: 09/11 の本）。

    **実物で確かめた**: 公開ずみ・予約ずみを含む台本 **6本・77コマ**（1字漢字の yomi 鍵 **39個**・
    年・月・分・人・回・歳 を含む）に当てて、**予定が変わったコマは 0**。
    ＝ **いま出ている本を1本も動かさずに、罠だけを閉じます**（教訓の形4つ目・実物から列挙して確かめた）。
    変わらなかった理由も数で出ました: §3 の 9（声の漢字は全部 `yomi`）が**複合語には長い鍵**を作らせるので、
    残る穴は「1字の鍵 × 同じ字の助数詞」だけ ——そこは lint が**わざと**覆っていない所です。

    **覆る条件**: (1) 予定が正しいのに、この規則が `yomi` を当てなかったせいで `!!` が出た回が出たら、
    その形（janome の品詞）を書いて、当てない所から外すこと。
    (2) janome が 1語 と見ない所で助数詞が割れた回が出たら、規則は品詞ではなく `script.COUNTER_RUN` の側
    （lint と同じ正規表現）で書き直すこと ——2つの口が同じ規則を読む形にできる。
    (3) 2字以上の鍵で同じ割れ方をした回が出たら、この関数を長さで分けているのが誤り ＝ 全部を語で当てること。
    """
    out: list[str] = []
    prev_pos: list[str] | None = None
    for t in _tok.tokenize(say):
        sf = t.surface
        pos = t.part_of_speech.split(",")
        after_num = prev_pos is not None and len(prev_pos) > 1 and prev_pos[1] == "数"
        out.append(ones[sf] if (sf in ones and not after_num) else sf)
        prev_pos = pos
    return "".join(out)


def expected_kana(say: str, yomi: dict[str, str], particle_he: bool = True) -> str:
    ones = {k: v for k, v in yomi.items() if len(k) == 1 and _ONE_KANJI.fullmatch(k)}
    for k in sorted((k for k in yomi if k not in ones), key=len, reverse=True):
        say = say.replace(k, yomi[k])
    if ones:
        say = _apply_one_kanji_yomi(say, ones)   # 1字の漢字だけ、語で当てる（註）
    for a, b in _PRE:
        say = re.sub(a, b, say)
    return to_kana(say, particle_he)


# ---------- ゆるい照合 ----------

# 音は同じ（か、音として区別しない）で仮名が揺れる所。両側に当てる。実測 09/06 の whisper の書き方から
_LOOSE = [# ゔ は小さい母音より先に（後だと ゔぃ → ゔい → ぶい。実測 09/06 22:xx「テーキヴィン」）
          ("ゔぁ", "ば"), ("ゔぃ", "び"), ("ゔぇ", "べ"), ("ゔぉ", "ぼ"), ("ゔ", "ぶ"), ("ゑ", "え"), ("ゐ", "い"),
          ("ー", ""), ("っ", ""), ("を", "お"), ("づ", "ず"), ("ぢ", "じ"), ("ぉ", "お"), ("ぇ", "え"), ("ぃ", "い"),
          ("いぇ", "え"), ("やん", "えん"), ("いえん", "えん"), ("ゅう", "ゅ"), ("しち", "なな"), ("ぜろ", "れい"),
          # 助詞の「へ」は「え」と読む。**予定の側の誤り**で、聞いた側は正しく え と書いていた（実測 2026-09-11 13:2x:
          # 09/10・09/12 の本の コマ1 が どちらも 予定 ひとへ ↔ 音 ひとえ）。
          # **2026-09-11 21:2x に、この行を外して予定の側（`_particle_he`）で直しました** ——
          # 両側に当てる形は、**TTS が本当に「ヘ」と読んだ回まで畳んで隠します**（§2 の ひらがなの側）。
          # 予定の側が助詞の「へ」を「え」にしたので、語中の「へ」（部屋 → へや）は両側とも「へ」のまま揃います。
          # **戻す条件は `_particle_he` の註の (1)。**
          ]
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
    k = expected_kana(heard, yomi, particle_he=False)   # whisper が漢字を混ぜても同じ道で仮名にする（助詞の「へ」だけは直さない・`_particle_he` の註）
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


def near_spans(exp: str, got: str) -> list[tuple[str, str]]:
    """`diff_spans` の門（`min_len=2`）が**落としている 1字だけの差**を返す。

    **1モーラの誤読は、hear の門を構造的に通ります。** 日本語で語を分けているのは 1モーラ のことが多いので、
    「一致 12/12」と「読みが正しい」がいちばん離れるのがここです。
    実測 2026-09-11 13:1x（hourly・Opus。オーナー 12:4x「**まだ読みがおかしいのがあるよ。ひらがなも漢字もあった**」
    受け取り帳 `3f4ef885` を受けて撃った・API 0単位・CPU のみ）:

        09/10 の本 コマ9  予定「**つま**の基礎年金」→ **3つの聞き取りが全部「すま／スマ」**
                          （仮名 small・仮名 medium・漢字 medium）。`diffs` は **0件**で `OK` と出ていた
        09/10 の本 コマ7  同じ「妻」が同じ本の別のコマでも「すま」（**同じ 1字差が 2コマ**）
        09/12 の本 13:2x  「**べつ**の決まり」→ 2つの聞き取りが「**れつ**の決まり」。これも 1字差で `OK`
                          （前の回が手で見つけて書き換えた所 —— **手で見つけるしかなかったのは、この門のせい**）

    `_BROKEN_GROUP` の註（09/07 01:xx）が「1字差なので diff_spans が吸って見えなかった」と
    **1例だけ**書いていたのと同じ穴です。1例ずつ畳むのではなく、**落ちている側を印字する**ことにしました。

    **門は動かしません**（`!!` の数 ＝ §7 の測りが動く）。1字差には whisper の癖も混ざるので、
    ここは `[?]` で名指しするだけにして、決めるのは台本を持つ側（§4 (2) と同じ形）。
    **実測の量**（`へ/え` を `_LOOSE` に畳んだ後・実物の本にそのまま当てた）: **09/12 の本 12コマ で 10件**・
    **09/10 の本 11コマ で 7件** ＝ 1本 7〜10件。**ほとんどは whisper の癖**
    （ね→め・ね→れ・た→ぱ・え→べ ＝ 語が変わっても同じ字で出る）。
    **09/11 の本 11コマ で 11件**。そのうち `near_repeats` が `[!]` で名指ししたのは
    **09/12 は 0件・09/10 は 2件・09/11 は 1件**:
    `('つ','す')` コマ7・9（09/10 ＝ **探していた「妻」そのもの**）／`('','い')` コマ2・3（同・「厚生年金」の所）／
    `('ぶ','ふ')` コマ3・6（09/11 ＝「…分だけ」）。**1本 0〜2件** ＝ 読む値段は `[?]` の側にしか無い。

    **覆る条件**: (1) 1本あたり 15件 を越える回が続いたら、印字が読まれなくなる ＝ 畳む側（`_LOOSE` /
    `_WHISPER_ISMS`）へ 1つずつ移すこと。(2) `near_repeats` の名指しが 3本 続けて whisper 側だったら、
    「同じ本で 2コマ 以上」は TTS 側の印にならない ＝ 印字をやめて `near` の生の一覧だけにする。
    (3) `hear` に抑揚を見る口が付いたら、この段ごと作り直す（1字差は「音が違う」側で、抑揚は別の穴）。
    """
    return [(a, b) for a, b in diff_spans(exp, got, min_len=1) if max(len(a), len(b)) < 2]


def isms_pairs() -> set[frozenset[str]]:
    """`_WHISPER_ISMS` が既に「whisper 側だ」と記録している **1字の取り違え**を、そこから数え出す。

    めんきん→ねんきん は `{め, ね}`・れんきん→ねんきん は `{れ, ね}` …。
    **手で並べ直さないこと** —— 次の回が `_WHISPER_ISMS` に 1行 足したら、ここも一緒に広がります
    （`near_spans` の註が「1例ずつ畳むのをやめる」と言っている側と、同じ理由）。
    """
    out: set[frozenset[str]] = set()
    for wrong, right in _WHISPER_ISMS:
        if len(wrong) == len(right):
            out |= {frozenset((a, b)) for a, b in zip(wrong, right) if a != b}
    return out


def near_repeats(rows: list[dict]) -> list[tuple[tuple[str, str], list[int]]]:
    """同じ 1字差が **2コマ以上**に出たものを (差, コマ番号) で返す ＝ **TTS 側を先に疑う所**。

    whisper の聞き違いは**コマをまたいで散り**、TTS の誤読は**同じ語が出るたびに同じだけ崩れます**。
    実測 09/10 の本: `('つ','す')` が コマ7・コマ9 の 2つ（どちらも**コマの頭の「妻」**）。

    **ただし「重なり」だけでは足りませんでした**（2026-09-11 13:4x に、この道具の 1回目の実行で分かった）——
    09/12 の本に当てたら `('ね','め')` **4か所**・`('ね','れ')` **2か所** を名指しし、
    **2つとも `_WHISPER_ISMS` に既に載っている取り違え**でした（めんきん／れんきん → ねんきん）。
    **同じ語（「…年」）が本の中で何度も出れば、whisper の癖もそのぶん重なります。**
    → 名指しから外すのは `isms_pairs()` が**既存の表から数え出した**組だけ
    （手で並べ直さない ＝ 次の回が `_WHISPER_ISMS` を足せば、ここも一緒に広がる）。
    `near` の生の一覧には**残します**（門でも名指しでもなく、読む側が見る所）。

    **数えるのは「コマの数」で、出た回数ではありません**（2026-09-11 14:0x に、実物で自分の規則を破った）——
    09/11 の本に当てたら `('が','か')` を **コマ[10, 10]** と名指しし、**1コマ の中の 2回**を「2コマ以上」と
    数えていました（09/12 の `('ね','め')` も **コマ6・6・8・11**）。**同じコマの中の重なりは 1 と数えます** ——
    1コマ の中で同じ字が何度も出るのは**その字が多い文**というだけで、コマをまたぐ重なりとは別の物です。

    **覆る条件**: (1) `isms_pairs()` で外した組が、あとで TTS 側だったと分かったら、
    `_WHISPER_ISMS` のその行が間違っている ＝ **そちらを直すこと**（ここに例外を足さない）。
    (2) 残りの `near_spans` の (2)。
    """
    skip = isms_pairs()
    seen: dict[tuple[str, str], list[int]] = {}
    for r in rows:
        for pair in dict.fromkeys(r.get("near", ())):   # **同じコマの中の重なりは 1 と数える**（下）
            if frozenset(pair) in skip:
                continue
            seen.setdefault(pair, []).append(r["i"])
    return [(p, ii) for p, ii in seen.items() if len(ii) >= 2]


def near_quiet(rows: list[dict], exp_char: str) -> list[int]:
    """**予定に `exp_char` を持ちながら、その字が崩れなかったコマ**の番号。

    `near_repeats` が `[!]` で名指しする前提は「**TTS の誤読は、同じ語が出るたびに同じだけ崩れる**」です。
    その前提は、**同じ字が同じ本の別のコマで正しく書かれた瞬間に反証されます**（TTS 側なら全部 崩れる）。
    ここはその反証そのものを数えます —— **名指しは外しません**（`near_repeats` の覆る条件 (1) ＝
    例外を足す所ではない）。足りていなかったのは**読む側の材料**のほうでした
    （§5 教訓の形 7つ目 ＝ 覆る条件を註に書いたら、それを読む印字も一緒に作ること）。

    実測 2026-09-12 01:4x（09/13 の本・付加年金・API 0単位）: `('わ','あ')` が コマ3・5 で `[!]`。
    **同じ「上乗せ」が コマ4・13 では「うわのせ」と正しく書かれており、4回 中 2回 だけ崩れていました。**
    印字が無かったので、読む側（この回）は `heard` を目で並べて確かめています。

    **`exp_char` が空の組（差し込み型 `('','い')`）は測れません** —— 空文字はどの予定にも含まれるので、
    `[]`（＝ 材料なし）を返します。**`[]` を「反証が無い ＝ TTS 側」と読まないこと。**

    **覆る条件**: (1) ここが `[]` でない（＝ 反証が在る）のに TTS 側だった本が出たら、
    崩れ方は語ではなく**前後の音**で決まっている ＝ 数える単位を字から前後 1モーラ の組へ広げること。
    (2) 3本 続けて反証が在る本ばかりなら、`near_repeats` の前提そのものを書き直すこと
    （名指しの条件を「重なり」から「重なり ＝ その字の全部」へ）。
    """
    if not exp_char:
        return []
    out: list[int] = []
    for r in rows:
        if exp_char not in (r.get("exp") or ""):
            continue
        if any(p[0] == exp_char for p in r.get("near", ()) or ()):
            continue
        out.append(r["i"])
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

HEAD_PROBE_SEC = 4.0   # 頭だけを聞き直すときに切り出す長さ（実測 2026-09-11 10:3x: コマ6 は 8.32秒 で、頭 4秒 に欠けた 13字 が全部 入る）


def head_gap(exp: str, diffs: list[tuple[str, str]]) -> str | None:
    """差が「予定の**頭**が丸ごと音に無い」形なら、その並びを返す（そうでなければ None）。

    **切り落としは末尾だけではありません**（実測 2026-09-11 10:3x・`hourly`・Opus。09/12 の本 コマ6・43字 8.32秒）:
    `予定「けさんするとさんじゅねんのち」 聞こえた「」` ＝ **頭の 13字（約2.4秒）が丸ごと無い**。
    そのとき `tail_gap`/`tail_probe`/`tail_rate`/`tail_voice` は **4つ とも末尾を見る**ので、1行も印字されませんでした。
    手で撃った頭の窓（先頭 4秒・small）は `けいさんすると30…` と書き、
    字/秒 は 43/8.32 = 5.17（帯の中）・頭が無いなら 30/8.32 = 3.61（帯の外）＝ **音は在り、切ったのは whisper**。
    同じ 43字 のまま第1文を 27 → 20字 に割ると 12/12。

    **`e != exp` を要ります** —— 聞き取りが丸ごと空の行は「頭が無い」ではなく「何も書かなかった」で、
    そちらは `degenerate` と `tail_gap` が既に持っています（**頭の側を足したことで、
    同じ行を 2つ の口が数えることがあってはいけません**）。

    **覆る条件**: 頭が 4字 未満 で切れた回が出たら、門（`len(e) >= 4`）を下げること
    —— いまの 4字 は `tail_gap` に合わせただけで、頭の実測は 13字 の 1例 だけです。"""
    if not diffs:
        return None
    e, g = diffs[0]
    return e if g == "" and len(e) >= 4 and e != exp and exp.startswith(e) else None


def head_probe(h: "Hearer", wav: Path, missing: str, yomi: dict[str, str], sec: float = HEAD_PROBE_SEC) -> dict:
    """コマの**頭 sec 秒だけ**を聞き直して、`missing`（予定に在って音に無かった頭の並び）がそこに在るかを見る。

    `tail_probe` の鏡です（2026-09-11 22:4x・optimizer・Opus。§15 の申し送り (2)）。
    **足す前に、元の手と違う物を見ることを確かめてあります** —— 09/11 10:3x の実測で、
    段を上げる側（small → medium）は同じ所で切れ、**頭 4秒 を渡した側だけが `けいさんすると30…` と書きました**。

    **`tail_probe` が 06:5x に自分で踏んだ穴は、こちらにも在ります** ——
    **窓の中の頭も切られることが在る**ので、`rate`（字/秒）と**並べて**読むこと
    （`ok` でない ＝ 「TTS を疑え」ではなく、「この手では分けられなかった」側に倒れます）。

    返すもの: `{"heard": 頭の仮名, "diffs": 残った差, "ok": 差が無いか}`。
    `ok` でも**一致の数には入れません**（決めるのは Fable・§4 (2)）。
    **覆る条件**: 頭の窓で「在る」と出たコマが、耳で聞いて欠けていた回が 1度でも出たら、この手ごと外すこと。"""
    clip = wav.with_name(wav.stem + "-head.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-t", str(sec), str(clip)])
    heard = h.transcribe(clip)
    got = loose(heard_kana(heard, yomi))
    # 切り出した末に次の語が入り込むが、それは **exp 側が空の差**になるので落とすだけでよい（`tail_probe` と同じ）。
    diffs = [(e, g) for e, g in diff_spans(missing, got) if e]
    return {"heard": got, "diffs": diffs, "ok": not diffs}


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


def _loud_windows(wav: Path, thresh: float, win: float) -> list[int]:
    """閾を越えた窓の番号（`energy_end` / `energy_start` の共通の土台）。**聞き取りを1度もしません。**"""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    n = max(1, int(16000 * win))
    if len(x) < n:
        return []
    x = x[: len(x) // n * n].reshape(-1, n)
    rms = np.sqrt((x * x).mean(axis=1))
    if not rms.max():
        return []
    return [int(i) for i in np.nonzero(rms >= thresh * rms.max())[0]]


def energy_end(wav: Path, thresh: float = ENERGY_THRESH, win: float = ENERGY_WIN) -> float:
    """音のエネルギーが最後に閾を越えた時刻（秒）。**聞き取りを1度もしません。**"""
    loud = _loud_windows(wav, thresh, win)
    return float((loud[-1] + 1) * win) if loud else 0.0


def energy_start(wav: Path, thresh: float = ENERGY_THRESH, win: float = ENERGY_WIN) -> float:
    """音のエネルギーが**最初に**閾を越えた時刻（秒）。**聞き取りを1度もしません。**

    `energy_end` の鏡（2026-09-11 22:4x・optimizer・Opus。§15 の申し送り (2)）。
    **同じ窓・同じ閾**を使うので、頭と末尾で物差しが変わりません
    （閾は「その wav のいちばん大きい窓に対する割合」なので、位置を見ていません）。
    **`energy_end` と違って +win しません** —— 末尾は「越えた窓の終わり」が音の終わりで、
    頭は「越えた窓の始まり」が音の始まりです。"""
    loud = _loud_windows(wav, thresh, win)
    return float(loud[0] * win) if loud else 0.0


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
    return {"energy_end": round(e, 2), "word_end": round(end, 2), "gap": round(gap, 2),
            "verdict": voice_verdict(gap)}


def voice_verdict(gap: float) -> str:
    """音と聞き取りの差（秒）→ `音は在る` / `音が無い` / `分けられない`。**頭と末尾で同じ閾**（`tail_voice` の註）。"""
    return "音は在る" if gap >= VOICE_GAP_PRESENT else ("音が無い" if gap < VOICE_GAP_ABSENT else "分けられない")


def head_voice(h: "Hearer", wav: Path, prompt: str | None = None) -> dict:
    """**音の始まり**と、**仮名モードが最初に書いた語の始まり**を比べる（`tail_voice` の鏡・
    2026-09-11 22:4x・optimizer・Opus。§15 の申し送り (2)）。

    `gap = 聞き取りが始まった時刻 − 音が始まった時刻`。**大きいほど「模型が書かなかった所に音が在る」**
    ＝ 切ったのは whisper。**閾は末尾と同じ**（0.4／0.2秒 ＝ 5モーラ・`voice_verdict`）。

    **この 3つ目だけが、判定の片側に模型を通しません**（`energy_start` は聞き取りを1度もしない）。
    `head_probe`（頭 4秒 をもう一度 聞き取る）と `rate`（字/秒）は、どちらも聞き取りか予定の字数の側です。

    **語が 1つ も返らない回は `分けられない`** —— そこは「頭が無い」ではなく「何も書かなかった」で、
    `head_gap` の `e != exp` が先に落としています（この行は取りこぼしの保険）。

    **覆る条件**: `音は在る` と出たコマを耳で聞いて欠けていた回が 1度でも出たら、この手を外すこと。
    逆に 3本 続けて当たったら、`head_probe` の「TTS 側を疑う」の印字をやめ、こちらに寄せること。"""
    words = h.transcribe_words(wav, prompt)
    e = energy_start(wav)
    if not words:
        return {"energy_start": round(e, 2), "word_start": None, "gap": None, "verdict": "分けられない"}
    start = words[0][1]
    gap = start - e
    return {"energy_start": round(e, 2), "word_start": round(start, 2), "gap": round(gap, 2),
            "verdict": voice_verdict(gap)}


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
               "exp": loose(exp), "got": loose(got), "diffs": diffs,
               # 門が落としている 1字差（`near_spans` の註）。**段を選ぶのは `diffs` の数だけ**なので、
               # ここは選ばれたあとの `got` に当てる ＝ 1字差が多い段が採られることはある（§7 で数えるのはその後）
               "near": near_spans(loose(exp), loose(got))}
        gap = tail_gap(loose(exp), diffs) if escalate else None
        head = head_gap(loose(exp), diffs) if escalate else None
        row["_gap"] = gap
        row["_head"] = head
        row["_wav"] = wav
        if gap or head:
            h2 = h2 or Hearer("medium" if size != "medium" else size)
            # 音の側から見る3つ目（`tail_voice` / `head_voice` の註）。**その行を書いた模型で**時刻を引く
            # —— 段が上がった行の語の終わりを、既定の段で引き直すと、比べている物がずれる。
            hw = h2 if "medium" in how else h
            prompt = _PROMPT if "prompt" in how else None
            # 末尾/頭で鳴ったコマには、**そのコマの文の字数**を並べる（§15 の申し送り (1)・
            # 切り落としが見ているのはコマの長さではなく文の長さ・`script.sentence_lens` の註）
            row["sent"] = sentence_lens(seg.say)
        if gap:   # 末尾が丸ごと無い ＝ 段を上げても分けられない型。末尾だけを聞き直して 切り落とし と 誤読 を分ける
            row["tail"] = tail_probe(h2, wav, gap, s.yomi)
            row["voice"] = tail_voice(hw, wav, prompt)
        if head:  # 頭が丸ごと無い型（2026-09-11 10:3x に実物で出た。末尾の 4つ は 1行も印字しない）
            row["head"] = head_probe(h2, wav, head, s.yomi)
            row["head_voice"] = head_voice(hw, wav, prompt)
        rows.append(row)
    _add_rates(rows)
    for r in rows:
        r.pop("_gap", None)
        r.pop("_head", None)
        r.pop("_wav", None)
    return rows


def _add_rates(rows: list[dict]) -> None:
    """末尾が丸ごと無いコマに、秒数の側の見立てを足す（`tail_rate` の註）。

    **切り落としが1つも無い回は、音の長さを1度も測りません**（`probe_duration` は ffprobe を呼ぶので、
    鳴っていない回にまで撃つと、そのぶん遅くなるし、音が無い所で落ちる）。
    帯は**一致したコマだけ**から作る —— 差の在るコマを分母に入れると、測ろうとしている物で物差しを作ることになる。
    """
    if not any(r.get("_gap") or r.get("_head") for r in rows):
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
        cut = r.get("_gap") or r.get("_head")
        if cut and durs.get(r["i"]):
            r["rate"] = tail_rate(len(r["exp"]), len(cut), durs[r["i"]], band)
            # **`tail_rate` は位置を見ません**（字数と長さの比だけ）＝ 頭の切り落としにもそのまま当たります
            # （2026-09-11 10:3x の実測: 43字/8.32秒 5.17 は帯の中・頭 13字 が無いなら 3.61 で帯の外）。
            # 印字の側が「末尾／頭」を言い分けるために、どちらで鳴ったかだけを足す。
            r["rate"]["where"] = "末尾" if r.get("_gap") else "頭"


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
