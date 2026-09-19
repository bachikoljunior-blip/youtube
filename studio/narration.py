"""声の時計 —— **いま画面のどこを言っているか**を秒で持つ。

オーナー 2026-09-19 12:3x JST（受け取り帳 `9155fe09`・**一字も変えないこと**）:

    「ナレーションとアニメーションの表現をリンクさせたりしないとわかりやすくなんないでしょ？
     画面がある意味が文字だけになってんのどうにかしろよ」

**この回（2026-09-19 12:4x・optimizer・Opus 5・ultracode）に数えた事実**:

  * 図（`studio/viz.py`）は 2026-09-17 に入っていて、実物の台本 10コマ のうち **7コマ に在ります**。
    **動いていない訳ではありません。** 動く長さは `viz.anim_seconds()` ＝ **コマの頭 0.6〜1.8秒**で、
    その註にこう書いてありました ——「**声がその数を言い終わるより先に絵が出来ている**」。
    ＝ **わざと声から外してありました。** 10秒 のコマなら、絵は 1.8秒 で描き終わって
    **残り 8.2秒 は 1枚の静止画**。声が「600万円の20%は120万円」と言っている間、画面は 1画素も動きません。
    **オーナーが言っている「リンクしていない」は、この 8.2秒 のことです。**
  * もう半分（「画面がある意味が文字だけ」）も実物で数えました。1コマ の画面に字の塊が **4つ**:
    `show`（手取り 1861万1300円）・`sub`（税金は…手取りは1861万1300円）・
    `board`／`viz`（同じ数の並び）・字幕（`say` そのまま）。
    **同じ数を 4回 字で書いています。** しかも `viz` の 7つ のうち **4つ が `kind: "table"`** ＝ 字の表。
    **＝ 画面は「文字だけ」で合っています。**

**この模組が持つのは、その 2つ のうち 1つ目（リンク）です。**
声の時計を作り、**図の 1歩 1歩を、その数を言う瞬間に合わせます**。
2つ目（字の重なり）は `docs/METHOD.md` §5 の決めの側。

---

**時計の作り方**（**API 0単位・TTS も 0回**）

コマの秒数は焼く時に実測で在ります（`tts.synth_segment` が返す長さ）。要るのは**その中の割り当て**です。

  1. `say` を **句点・読点で切る**（`phrases`）。
  2. 各句の**モーラ数**を数える —— 字ではなく音。漢字の読みは台本の `yomi` が全部持っている
     （§3 の 9「声の漢字は全部 `yomi`」）ので、`hear.expected_kana` が**予定の仮名**を正確に出します。
     **これは新しい道具ではありません** —— 毎本の全文照合が 09/03 から使っている同じ関数です。
  3. 句点・読点の**間**を先に引く（TTS は「、」「。」で息を置く。`PAUSE`）。
  4. 残りをモーラ数で比例配分する。

**なぜ whisper の語ごとの時刻（`hear.Hearer.transcribe_words`）を使わないか** ——
使えます（同じ repo に在り、`tail_voice` が既に撃っています・**API 0単位**）。使わないのは **順序**の問題です:
whisper は**焼いたあとの音**を聞くので、焼く前に要る絵の刻みは作れません。
2周（焼く → 聞く → 焼き直す）にすれば使えますが、**1本 の焼きが 92秒 で、在庫 13本 が 2周 になります**。
**まず比例配分で出し、ずれが目で見えたら whisper へ**（覆る条件 (1)）。

**覆る条件**:
 (1) sheet か mp4 で、図の 1歩 が声より **0.4秒 以上** ずれて見えたら、
     `calibrate()`（下・whisper の語ごとの時刻で実測の誤差を出す・**API 0単位**）を撃ち、
     誤差の中央が 0.4秒 を越えていたら **焼きを 2周 にして whisper の時刻を使うこと**。
     `calibrate()` はこの模組に置いてあります ＝ **測る手はもう在ります。先に乗り換えないこと。**
 (2) `PAUSE` の 2つ の数は、`calibrate()` が実測で直せます（句ごとの誤差が
     句読点の数と揃って増えるなら、それはこの数）。**手で動かさないこと。**
 (3) 声を替えたら（`tts` の註の Chirp3-HD へ戻すなど）、`PAUSE` もモーラの重みも別の声の数です ＝ 撃ち直すこと。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# 拗音（前のモーラにくっつく）。促音「っ」と長音「ー」は **1モーラ 数える**（音の長さを持つ）
SMALL = "ぁぃぅぇぉゃゅょゎァィゥェォャュョヮ"
_SKIP = "、。 　「」（）()・…"

# 句読点のあとの息（秒）。**実測で直す数**（`calibrate`・覆る条件 (2)）。
# 初期値は `tts.PAD_SEC`（0.35）より短く取った: PAD はコマの**末尾**に足す無音で、文の中の息とは別物。
PAUSE = {"。": 0.30, "、": 0.15, "！": 0.30, "？": 0.30}

# 1歩 が動く長さの上限（秒）。**始まりは数の頭に合わせたまま**、伸びるほうだけ切る。
# 理由は焼きの枚数です（実測 2026-09-19 12:5x）——「138万8700円」は声で 3.2秒 かかり、
# 12コマ/秒 で 38枚。10コマ の本で **235枚**・長尺 182コマ なら 4,200枚（1枚 0.08秒 ＝ +5.6分）。
# 1.5秒 に切ると 18枚 が上限で、**声と絵の始まりは 1ミリも動きません**（切るのは終わりだけ）。
# 覆る条件: 棒が数の途中で止まって見えたら（sheet ではなく mp4 で見ること）、この数を上げる ——
# そのとき増える焼きは「歩の数 × (新しい上限 − 1.5) × 12 × 0.08秒」で先に数えられます。
MAX_CUE_SECONDS = 1.5

_SPLIT = re.compile(r"[^、。！？\n]*[、。！？\n]|[^、。！？\n]+")
_DIGITS = re.compile(r"[0-9０-９]+")


@dataclass(frozen=True)
class Phrase:
    """`say` の中の 1句 と、その句を言っている秒。`start`/`end` は `say` の中の字の位置。"""
    start: int
    end: int
    text: str
    t0: float
    t1: float


def morae(kana: str) -> int:
    """仮名の列のモーラ数。拗音は前にくっつく・促音と長音は数える・句読点と空白は数えない。"""
    return sum(1 for c in kana if c not in SMALL and c not in _SKIP)


def phrases(say: str) -> list[tuple[int, int, str]]:
    """`say` を句点・読点で切る。**句読点は前の句につける**（画面の光りが句点で消えない）。

    1モーラ しか無い句（「。」だけ・「で、」）は前の句にくっつける —— 0.1秒 で光りが飛ぶと、
    目が追う先が増えるだけで分かりやすくなりません。
    """
    out: list[list] = []
    i = 0
    for m in _SPLIT.finditer(say):
        t = m.group()
        if not t.strip():
            i = m.end()
            continue
        if out and len(t.strip(_SKIP)) <= 1:
            out[-1][1] = m.end()
            out[-1][2] += t
        else:
            out.append([m.start(), m.end(), t])
        i = m.end()
    return [(a, b, t) for a, b, t in out]


def _kana(text: str, yomi: dict[str, str]) -> str:
    """予定の仮名（**毎本の全文照合と同じ関数**）。読めない字が来ても止めない。"""
    from .hear import expected_kana
    try:
        return expected_kana(text, yomi or {})
    except Exception:
        return text


def timeline(say: str, seconds: float, yomi: dict[str, str] | None = None,
             pad: float | None = None) -> list[Phrase]:
    """コマの `say` と**実測の秒数**から、句ごとの秒を作る。

    `seconds` は `tts.synth_segment` が返す長さ（末尾の `PAD_SEC` の無音を含む）。
    `pad` を渡さなければ `tts.PAD_SEC` を引く。
    """
    if pad is None:
        from .tts import PAD_SEC
        pad = PAD_SEC
    ph = phrases(say or "")
    if not ph:
        return []
    speech = max(0.1, float(seconds) - max(0.0, pad))
    pauses = [PAUSE.get(t.strip()[-1:], 0.0) for _a, _b, t in ph]
    pauses[-1] = 0.0                      # 最後の句の息は、コマの末尾の無音（pad）と同じもの
    body = max(0.1, speech - sum(pauses))
    ms = [max(1, morae(_kana(t, yomi or {}))) for _a, _b, t in ph]
    tot = sum(ms)
    out: list[Phrase] = []
    t = 0.0
    for (a, b, txt), m, q in zip(ph, ms, pauses):
        d = body * m / tot
        out.append(Phrase(a, b, txt, t, t + d))
        t += d + q
    return out


def span_time(tl: list[Phrase], say: str, start: int, end: int,
              yomi: dict[str, str] | None = None) -> tuple[float, float] | None:
    """`say` の字 `[start:end)` を**言っている秒**（句の中はモーラで按分する）。外れたら None。

    これが「その数を言う瞬間」です —— 図の 1歩 をここに合わせます。
    """
    for p in tl:
        if p.start <= start < p.end:
            inner = say[p.start:p.end]
            head = _kana(inner[:start - p.start], yomi or {})
            body = _kana(inner[:min(end, p.end) - p.start], yomi or {})
            whole = max(1, morae(_kana(inner, yomi or {})))
            a = p.t0 + (p.t1 - p.t0) * morae(head) / whole
            b = p.t0 + (p.t1 - p.t0) * morae(body) / whole
            return (a, max(b, a + 0.12))
        if start < p.start:
            return (p.t0, p.t1)
    return None


def find_cue(say: str, needle: str, after: int = 0) -> tuple[int, int] | None:
    """`say` の中で `needle`（「800万円」のような**数の字**）が出る所。`after` より後ろを探す。

    見つからなければ **数字の並びだけ**でもう一度探します（台本が「800万」と単位を落とす／
    「約800万円」と冠を付ける回・`fmt_num` は単位まで書く）。

    **数の切れ目を見ます** —— 見ないと「0円」が「60**0**万円」の中に当たりました
    （実測 2026-09-19 12:5x・退職金の本のコマ6: 速算表の「0円」の行が、
    声の「600万円の20%」の 0 に合って、**声と 1歩 ずれた図**になりかけた）。
    **数の前後に数字が在る当たりは、別の数です。**

    **数字の並びは「全部」拾えたときだけ当たりにします**（2026-09-20 00:5x・optimizer・Opus 5・
    ultracode・**API 0単位**）。前の版は、2組 以上 ある数字のうち **1組目 だけ**が当たれば
    そこを返していました ＝ **別の数の頭に当たります**。実測（在庫の台本 56本・`viz` の歩を全部
    当て直した）: **28歩・10本 が別の数に当たっていました**。実物:

        図の数「13万7602円」 ← 声「…残りは13万**2398**円です。」   （`13` だけが当たった）
        図の数「1万5700円」  ← 声「3つを足すと**1**年に15万3300円。」（`1` だけが当たった）

    ＝ 図のその歩は、**声が別の数を言っている所で動いて**いました。オーナー 2026-09-19 12:3x
    `9155fe09`「ナレーションとアニメーションの表現をリンクさせたりしないと」の当のずれです。

    **覆る条件**:
     (a) 台本が数に区切りを入れる形（「1万5,700円」）へ移ったら、`fmt_num` と台本で
         数字の並びが割れます ＝ この当て直しは当たらなくなります（**当たらないほうが安全**です:
         前の版はその場合も「1」に当たっていました）。区切りを入れるなら、
         ここではなく `_DIGITS` の側（区切りを飛ばして読む）を直すこと。
     (b) 1組 しか数字の無い needle（「180万円」）は前と 1字も変わりません。
         **変わるのは 2組 以上 の needle だけ**です。
     (c) 当たらない歩が増えます —— ただし増えるのは `unlinked_viz_steps`（参考の数）で、
         **動く歩（`unmoored_viz_steps`）は減る側**です（当たりが消えると、その歩は
         前後の錨の間に留まるか、幅 0 になる）。増えた分を「悪くなった」と読まないこと。
     (d) **いちばん多く当たらなくなるのは「声が丸めた数」です** —— 図が `2万121円` で
         声が「2万100円」なら、`121` と `100` が合わないので当たりません
         （前の版は `2` だけで当たっており、**それは別の数の頭**でした）。
         **これは欠けではなく、台本と図が別の数を出している印**です。
         直すのは 2つ で、**どちらも台本と図の側**: 声に正確な数を言わせるか、図の値を丸めること
         （`viz` の `text` に「約2万円」と書けば、その字がそのまま鍵になります）。
         **ここを緩めて「1組目 だけ」に戻さないこと** —— 戻すと 28歩 が別の数へ帰ります。
    """
    if not needle:
        return None
    i = _find_num(say, needle, after)
    if i is not None:
        return (i, i + len(needle))
    ds = _DIGITS.findall(needle)
    if not ds:
        return None
    j = _find_num(say, ds[0], after)
    if j is None:
        return None
    end = j + len(ds[0])
    for d in ds[1:]:
        k = _find_num(say, d, end)
        if k is None or k - end > 4:      # 「1861万1300円」の間は 1字。離れていれば別の数
            return None                   # **1組目 だけの当たりは、別の数です**（上の註）
        end = k + len(d)
    return (j, end)


def _find_num(say: str, needle: str, after: int) -> int | None:
    """`needle` が**数として丸ごと**出る所（前後に数字が続かない）。無ければ None。"""
    i = say.find(needle, after)
    while i >= 0:
        before_ok = i == 0 or not _DIGITS.match(say[i - 1])
        j = i + len(needle)
        after_ok = j >= len(say) or not _DIGITS.match(say[j]) or not _DIGITS.match(needle[-1])
        if before_ok and after_ok:
            return i
        i = say.find(needle, i + 1)
    return None


def cue_windows(say: str, seconds: float, keys: list[list[str]],
                yomi: dict[str, str] | None = None,
                default_seconds: float = 0.45,
                carry: int = 0) -> list[tuple[float, float]]:
    """図の 1歩 ごとの (始まり, 終わり) 秒。`keys[k]` はその歩の**候補の字**（先に当たったものを採る）。

    当たらなかった歩は、**前の歩の後ろに詰める**（今までの「順に動く」と同じ形 ＝ 止まりません）。
    返り値は必ず **k の順に単調**で、コマの秒数の中に収まります。

    **`carry` ＝ コマの頭で もう画面に出ている歩の数**（幅 0 の窓 `(0.0, 0.0)` ＝ 動かない）。
    呼ぶ側（`render.build`）が「前のコマで もう動いた歩」を数えて渡します。
    **それとは別に、このコマの声が 1歩 でも指しているなら、その前の「声が指さない歩」も
    自動で `carry` に入ります**（下の `first_hit`）。

    **なぜ**（2026-09-19 14:3x・optimizer・Opus 5・ultracode。在庫 42本 を数えて決めた）:
    オーナー 09/19 12:3x「ナレーションとアニメーションの表現をリンクさせたりしないと…」に当てた
    09/19 12:4x の版は、**当たらなかった歩を前後の当たりの間に等間隔で入れて**いました。
    在庫 42本・図の歩 882 を数えると、**当たらない歩 476 の 36%（172歩）が「先頭の、既に出ている歩」**です
    —— 積み上がる表・棒は、コマが進むごとに 1行 ずつ増え、**声はその回の新しい 1行 しか言いません**。
    実物（`2026-09-20-nenkin-tedori-hayamihyou` コマ30）:
    声「毎月18万円なら約16万円。毎月20万円なら約17万4000円です。」に対し、
    図の歩0〜2（10万・12万・15万 ＝ **前のコマで もう出ている行**）が、
    **声が 18万 の話をしている間に 1行 ずつ湧いて**いました。
    ＝ 「動いているが、声と別のことを指している」 ＝ **オーナーが言っているずれ そのもの**。
    幅 0 の窓にすると、その 3行 は**コマの頭から出ていて動かず**、
    **新しい 1行 だけが、声がその数を言う瞬間に引かれます**。

    **覆る条件**:
     (a) 初めて出る図（前のコマに無い）で、声が**最後の 1つ（合計）しか言わない**ものは、
         この決めだと **棒が全部 いきなり出てから合計だけ伸びます**。
         それが sheet か mp4 で「積み上がりが見えなくなった」と見えたら、
         自動の `first_hit` を外し、`carry` を **呼ぶ側が数えた 既出の分だけ**にすること
         （`render.build` の `seen`）。**外す所は 1行**（下の `first_hit` の行）。
     (b) 声が 1歩 も指さないコマは **図ぜんたいが動きません**（`carry = n`・下の `first_hit >= n`）。
         そこで動きが要ると見えたら、直すのは**この行ではなく台本**です ——
         「その数を声が言っていない」のが本当の欠けで、動かして隠す物ではありません
         （`script.Script.unlinked_viz_steps()` が名指しします・**API 0単位**）。
     (c) この 2つ を入れても、なお **声と無関係に動く歩**が残ります（この回の実測 882歩 中 **127歩 ＝ 14%**。直す前は 476歩 ＝ 54%）。
         残りは「図の途中の歩・最後の歩を、声が言っていない」形 ＝ **台本の側**。
         **次に減らすなら台本を直すこと。ここを触っても減りません。**
    """
    tl = timeline(say, seconds, yomi)
    n = len(keys)
    if not n:
        return []
    if not tl:
        step = max(0.1, float(seconds) / n)
        return [(k * step, (k + 1) * step) for k in range(n)]
    span = float(seconds)
    found: list[tuple[float, float] | None] = []
    at = 0
    for cand in keys:
        hit = None
        for s in cand:
            pos = find_cue(say, s, at)
            if pos:
                w = span_time(tl, say, pos[0], pos[1], yomi)
                if w:
                    hit = w
                    at = pos[1]
                    break
        found.append(hit)
    # **もう画面に出ている歩**は、コマの頭から出ていて動かない（幅 0 の窓）。
    # 声が 1歩 でも指していれば、その**前の当たらない歩は全部** 既出 とみなす（上の註）。
    first_hit = next((i for i, f in enumerate(found) if f is not None), n)
    if first_hit >= n:
        # **声が 1歩 も指さないコマ**は、図は**動きません**（頭から全部 出ている）。
        # 在庫 42本 の実測（2026-09-19 14:4x）: そういうコマは 70 あり、**その 79%（55コマ）は
        # `say` に数字が 1つ も在りません**（例: 「決まりでは、退職金には税金のかからない枠があり、
        # 年数で決まります。」の裏で、表の「20年まで 40万円」「20年をこえた分 70万円」が
        # 1行 ずつ湧いていた）。**声と何の関係も無い動きです** ＝ オーナー 09/19 12:3x が
        # 「リンクしていない」と言っている物そのもの。**動かすのをやめ、読める板として置きます。**
        carry = n
    else:
        carry = min(max(int(carry), first_hit), first_hit)
    # 空いた歩を埋める（前後の当たりの間に等間隔で入れる）
    out: list[tuple[float, float]] = [(0.0, 0.0)] * n
    k = carry
    prev_end = 0.0
    while k < n:
        if found[k] is not None:
            a, b = found[k]
            a = max(a, prev_end)
            b = max(min(b, a + MAX_CUE_SECONDS), a + 0.12)
            out[k] = (a, b)
            prev_end = b
            k += 1
            continue
        j = k
        while j < n and found[j] is None:
            j += 1
        if j >= n:
            # **最後の当たりより後ろの歩は、そこで出そろって止まります**（幅 0 の窓）。
            # `carry`（頭の側）の**鏡**です —— 前は「もう出ている」、ここは「もう出しきった」。
            # 2026-09-19 22:xx・optimizer（Opus 5・ultracode・1周 1体）が在庫 38本 を数えて入れた。
            # **なぜ**: ここに来る歩は、**声が最後にその図の数を言い終わったあと**に、
            # コマの終わりまでの余りを等分して湧いていました。**両側に錨がありません** ——
            # 頭の側（`carry`）は「前のコマで出ている」で説明が付き、当たりと当たりの**あいだ**の歩は
            # 前後の数が錨になりますが、**うしろの歩は何にも留まっていません。**
            # 実物（`2026-09-23-kakyu-1sai-shita-short` コマ8）: 声は「1歳ちがうと42万3700円ちがいます」で、
            # 図は 6行 の表。**1行目 が「42万3700円」で引かれたあと、2〜6行目 が声の無い所で 1行 ずつ湧いて**いました
            # ＝ オーナー 09/19 12:3x『ナレーションとアニメーションの表現をリンクさせたりしないと…』の形そのもの。
            # 在庫 38本 の実測: **動く歩 808 のうち 142歩（17.6%）がこれ**（`Script.unmoored_viz_steps`）。
            # **止めるのではなく、最後の当たりへ寄せます** —— その数を声が言い終わった瞬間に図が出そろい、
            # そのあとの無音では**何も動きません**。
            # **覆る条件**:
            #  (d) 図が **`bars`/`waterfall` で、最後の歩が「合計」**のとき、この決めだと
            #      合計の棒が**伸びずに出ます**。sheet か mp4 で「合計が伸びない」が気になったら、
            #      外すのはこの枝 1つ（`if j >= n`）で、**台本の側で最後の数を声に言わせるほうが先**です
            #      （そちらなら錨が増えて、この枝には来ません）。
            #  (e) **この枝に来る歩の数そのものが、台本の欠け**です。`unmoored_viz_steps` が 0 なら
            #      この枝は 1度も通りません ＝ **数が減っているかを毎周 見ること**（`lint` の助言文）。
            for m in range(k, n):
                out[m] = (prev_end, prev_end)
            k = n
            continue
        nxt = found[j][0]
        room = max(0.12 * (j - k), nxt - prev_end)
        step = room / (j - k)
        for m in range(k, j):
            a = prev_end + step * (m - k)
            out[m] = (a, a + min(default_seconds, step))
            prev_end = out[m][1]
        k = j
    last = out[-1][1]
    if last > span:                        # 詰め込みすぎた（短いコマ）: 全部を縮める
        f = span / last
        out = [(a * f, b * f) for a, b in out]
    return out


# ---------------------------------------------------------------- 実測（覆る条件 (1)(2)）

def calibrate(wav: Path, say: str, yomi: dict[str, str] | None = None,
              size: str = "small") -> dict:
    """**この時計が実際の声と何秒ずれているか**（whisper の語ごとの時刻・**API 0単位・TTS 0回**）。

    焼いたあとの wav を聞き、`say` の中の**数の字**が実際に鳴った秒と、`timeline` の見積もりを比べます。
    返り値の `worst`／`median` が 0.4秒 を越えたら、冒頭の覆る条件 (1)。
    """
    from .common import probe_duration
    from .hear import Hearer
    h = Hearer(size)
    words = h.transcribe_words(wav)
    seconds = probe_duration(wav)
    tl = timeline(say, seconds, yomi)
    heard: list[tuple[str, float]] = []
    for w, a, _b in words:
        for d in _DIGITS.findall(w):
            heard.append((d, float(a)))
    rows = []
    at = 0
    hi = 0
    for m in _DIGITS.finditer(say):
        pos = (m.start(), m.end())
        if pos[0] < at:
            continue
        at = pos[1]
        want = span_time(tl, say, pos[0], pos[1], yomi)
        got = None
        while hi < len(heard):
            if heard[hi][0] == m.group():
                got = heard[hi][1]
                hi += 1
                break
            hi += 1
        if want and got is not None:
            rows.append({"num": m.group(), "est": round(want[0], 2),
                         "heard": round(got, 2), "err": round(want[0] - got, 2)})
    errs = sorted(abs(r["err"]) for r in rows)
    return {"rows": rows, "n": len(rows), "seconds": round(seconds, 2),
            "median": errs[len(errs) // 2] if errs else None,
            "worst": errs[-1] if errs else None}


# ---------------------------------------------------------------- 絵の刻み

def progress_at(t: float, wins: list[tuple[float, float]], n: int) -> float:
    """秒 `t` の図の進み（0〜1）。**歩と歩の間は止まっています**（声が別の話をしている間）。"""
    if n <= 0:
        return 1.0
    p = 0.0
    for k, (a, b) in enumerate(wins):
        if t >= b:
            p = (k + 1) / n
        elif t > a:
            p = (k + (t - a) / max(b - a, 1e-6)) / n
            break
        else:
            break
    return max(0.0, min(1.0, p))


def lit_at(t: float, tl: list[Phrase]) -> tuple[int, int]:
    """秒 `t` に**声が言っている字**の範囲（`say` の中）。息の間は直前の句のまま。"""
    if not tl:
        return (0, 0)
    cur = tl[0]
    for p in tl:
        if t >= p.t0:
            cur = p
        else:
            break
    return (cur.start, cur.end)


def frame_plan(seconds: float, tl: list[Phrase], wins: list[tuple[float, float]], n_steps: int,
               fps: int = 12, min_dt: float = 0.08) -> list[tuple[float, float, int, int]]:
    """(その絵を出す秒, 図の進み, 光る字の始まり, 光る字の終わり) の列。**合計はコマの秒数**。

    刻むのは **2つ の物が動く瞬間だけ**です:
      * 句の変わり目（字幕の光りが次の句へ移る）… 1コマ 2〜5枚
      * 図が動いている間（`wins` の中）… `fps` の刻。**外では 1枚 も焼きません**
    ＝ 絵の枚数は「動く長さ × fps」で決まり、コマの長さでは増えません
    （10秒 のコマで 120枚 ではなく、実物 10コマ で 20〜45枚）。
    """
    seconds = float(seconds)
    marks = {0.0, seconds}
    for p in tl:
        marks.add(p.t0)
    for a, b in wins:
        marks.add(min(a, seconds))
        marks.add(min(b, seconds))
        m = max(1, int(round((b - a) * fps)))
        for j in range(1, m):
            marks.add(min(a + (b - a) * j / m, seconds))
    ts = sorted(x for x in marks if 0.0 <= x <= seconds)
    out: list[list] = []
    for a, b in zip(ts, ts[1:]):
        dt = b - a
        if dt <= 1e-6:
            continue
        pr = progress_at(b, wins, n_steps)
        s0, s1 = lit_at(a, tl)
        if out and dt < min_dt and abs(out[-1][1] - pr) < 1e-9 and out[-1][2] == s0 and out[-1][3] == s1:
            out[-1][0] += dt
            continue
        if out and dt < min_dt:
            out[-1][0] += dt                # 短すぎる刻は前の絵に足す（30fps の 2枚 に満たない絵は焼かない）
            out[-1][1] = pr
            out[-1][2], out[-1][3] = s0, s1
            continue
        out.append([dt, pr, s0, s1])
    if not out:
        return [(seconds, 1.0, 0, len(tl[0].text) if tl else 0)]
    out[-1][1] = 1.0 if n_steps else 0.0
    return [(d, p, a, b) for d, p, a, b in out]
