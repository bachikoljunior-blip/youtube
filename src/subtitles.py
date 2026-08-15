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
# 数字のかたまりを作る文字。**ここで割ると読めなくなる。**
# 小数点（. ．）は 2026-08-07 に追加。「1か月0.」／「4パーセント、」と割れた。
# **数字のかたまりは数字だけでできていない**（元号は _ERA、小数点はここ）。
# **漢数字も数字。** 2026-08-07、「三年で六十一万九」／「千円戻ります。」と割れた。
# 読み上げ用の narration では漢数字が普通に出る（TTS が読みやすいため）。
# 元号（_ERA）・小数点に続いて3回目。**数字のかたまりは数字だけでできていない。**
# これ以下の長さの行は、隣に寄せる（単独で映すと短すぎる）。
# **4 だと寄せすぎる。** 「所得税は」(4文字) を寄せて枠を超えた（2026-08-08）。
MIN_LINE_CHARS = 3

# Dialogue の Name 欄に刷る、文の通し番号の頭。**カンマを含めないこと**
# （.ass は行をカンマで割るので、混ざると本文がずれる）。
SEGMENT_NAME_PREFIX = "seg"

_NUM_TOKEN = set("0123456789．."
                 "〇一二三四五六七八九十百千万億兆"
                 "円日年月時分秒人回倍％%割点歳"
                 # 条文の番号。「労働基準法37条5」／「項・施行規則21条」と
                 # 割れた（2026-08-08）。**これも数字のかたまりの一部。**
                 "条項号")

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
    """**ひらがなだけ。** カタカナを入れてはいけない。

    規則2は「ひらがな→ひらがな以外」を語の頭とみなす。
    ここにカタカナを入れると「の｜パーセント」が境目でなくなり、
    **一番良い切れ目を自分で潰す。**
    カタカナの連続を守るのは `_is_katakana`（別物）。
    """
    return "ぁ" <= ch <= "ゟ"


def _is_katakana(ch: str) -> bool:
    """カタカナ（長音符を含む）。**「・」は入れない**（あれは良い切れ目）。

    2026-08-08、「税率20パーセン」／「ト で計算します」と割れた。
    規則3は「かなの連続の途中で割らない」と書いてあったのに、
    `_is_kana` がひらがなしか見ておらず、**カタカナは素通りしていた。**
    ひらがな・漢字と塞いできて、**3つ目の文字種を数え落としていた。**
    """
    return "ァ" <= ch <= "ヺ" or ch == "ー"


# 1文字で語を区切れるひらがな（助詞）。ここに無い1文字のひらがなは送り仮名とみなす。
_PARTICLES = "のはをにがとでもやへ"

# 助数詞。**数字の直後に来たときだけ**「かたまりの一部」とみなす。
# `_NUM_TOKEN` とは別に持つ（あちらは両側を見るので、`本` を入れると
# 「日｜本」まで割れなくなる）。ここに無いものは順次足すこと。
_COUNTERS = "本件名枚個台冊社校泊食品位番着足杯匹頭軒室戸機"

# 元号。直後の年数と切り離すと読めなくなる。
_ERA = ("令和", "平成", "昭和", "大正", "明治")


def _is_kanji(ch: str) -> bool:
    """漢字か。送り仮名の判定に使う（数字やカタカナと区別するため）。"""
    return "\u4e00" <= ch <= "\u9fff" or ch == "\u3005"


def _is_okurigana(piece: str, cut: int) -> bool:
    """cut の直前のひらがなが、送り仮名の途中か。

    規則2（ひらがなの次は語の頭）は**複合語で誤爆する**。
    「組**み**合わせ」の「み」を語尾と見て「組み／合わせ」と割った
    （2026-08-05、失業給付のショート）。「読み書き」「取り組み」も同じ形。

    見分け方は**ひらがなが1文字しか挟まっていないか**。
    漢字＋ひらがな1文字＋漢字 は、ほぼ送り仮名の入った複合語。
    ただし助詞（の・は・を…）は1文字でも正当な切れ目なので、そこは除く。
    「制度**の**内容」は割ってよい。
    """
    if cut < 2:
        return False
    if piece[cut - 1] in _PARTICLES:
        return False                      # 助詞なら切ってよい
    # **前が漢字のときだけ。** 「60歳0か月」の「か」を送り仮名と誤判定して、
    # 正しい切れ目を却下していた（2026-08-07）。数字の後のかなは送り仮名ではない。
    return _is_kanji(piece[cut - 2])      # 漢字＋かな1文字＋漢字 → 送り仮名


def _best_cut(piece: str, limit: int, strict: bool = False) -> int:
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
        if piece[cut - 1] in _NUM_TOKEN and piece[cut] in _NUM_TOKEN:
            return False
        # 「か月」「か国」「か所」の途中でも割らない（2026-08-07、「0か／月から」）。
        # **「か」を _NUM_TOKEN に入れると助詞の「か」まで巻き込む**ので、
        # 単位としての並びだけを見る。
        if piece[cut - 1] in "かヶケ箇" and piece[cut] in "月年国所":
            return False
        # 数字と助数詞のあいだでも割らない。「毎朝1」／「本ぶんを計算する」と
        # 割れた（2026-08-08）。**助数詞は `_NUM_TOKEN` に入れないこと。**
        # あれは「両側とも数字なら割らない」に使っていて、`本` を入れると
        # 「日｜本」のような、数字と関係ない組み合わせまで巻き込む。
        if piece[cut - 1] in _NUM_TOKEN and piece[cut] in _COUNTERS:
            return False
        # **単位はカタカナでも書かれる。** 「社会保険料率15」／「パーセントの仮定」と
        # 割れた（2026-08-09）。助数詞を漢字（_COUNTERS）だけで塞いでいて、
        # パーセント・ポイント・メートルのようなカタカナの単位が抜けていた。
        # **数字の直後のカタカナは、単位とみなして切らない。**
        if piece[cut - 1] in _NUM_TOKEN and _is_katakana(piece[cut]):
            return False
        # 元号と年数のあいだでも割らない。「日額は令和」／「8年8月1日改定」と
        # 割れて読めなかった（2026-08-05）。元号は _NUM_TOKEN に入っていないので
        # 上の規則に引っかからない。**数字のかたまりは数字だけでできていない。**
        if piece[max(0, cut - 2):cut] in _ERA and piece[cut].isdigit():
            return False
        # **漢字が続いているところでも割らない。**
        # 2026-08-08、「総所得300万円・医療」／「費が毎年30万円の場合」と
        # **「医療費」が「医療」＋「費」に割れた。** 規則3は「かなの連続の
        # 途中で割らない」だけを見ていて、**漢字の連続は素通りしていた。**
        # 日本語の複合語は漢字が続くところで作られる。
        # かな側だけ塞いで漢字側を忘れる形は、これで4回目。
        #
        # **ただし数字の終わりは別。** 「千円／戻ります」の「円｜戻」は
        # 語の境目そのもので、ここを塞ぐと逃げ場が無くなって
        # 「戻／ります」（送り仮名の途中）に落ちる。**塞ぎすぎると悪化する。**
        #
        # 見るのは「単位の字か」ではなく「**その手前も数字か**」。
        # 「年」を単位というだけで通すと、「全額戻る年／末残高」のように
        # 数字と関係ない「年末」まで割れた。手前が数字のときだけ通す。
        a, b = piece[cut - 1], piece[cut]
        num_end = a in _NUM_TOKEN and cut >= 2 and piece[cut - 2] in _NUM_TOKEN
        if _is_kanji(a) and _is_kanji(b) and not num_end and b not in _NUM_TOKEN:
            return False
        # カタカナの連続の途中でも割らない（「パーセン」／「ト」）。
        if _is_katakana(a) and _is_katakana(b):
            return False
        return True

    # 1. 句読点の直後
    for cut in range(limit, floor - 1, -1):
        if piece[cut - 1] in "、。！？" and ok(cut):
            return cut
    # 2. ひらがな → 漢字・カタカナ・数字の変わり目（ほぼ語の頭）
    for cut in range(limit, floor - 1, -1):
        if (_is_kana(piece[cut - 1]) and not _is_kana(piece[cut])
                and ok(cut) and not _is_okurigana(piece, cut)):
            return cut
    # 3. ひらがなの連続の途中では割らない。
    #    「60歳0か月か」／「ら受け取ると」、「自分の場合はねんき」／「ん定期便」
    #    のように、行頭に「ら」「ん」が来ると読めない（2026-08-07）。
    #    規則2は「かな→漢字」しか見ていないので、かな同士の境目が素通りしていた。
    #
    #    **漢字→かなも、できれば避ける。** 送り仮名（「戻／ります」）か
    #    助詞（「時給／がいくら」）のどちらかで、どちらも行頭が読みにくい。
    #    ただし**避けられないことがある**ので、まず避けて探し、
    #    見つからなければ許す。**禁止にすると、もっと悪い所へ落ちる。**
    for avoid_okurigana in (True, False):
        for cut in range(limit, floor - 1, -1):
            a, b = piece[cut - 1], piece[cut]
            if _is_kana(a) and _is_kana(b):
                continue
            if avoid_okurigana and _is_kanji(a) and _is_kana(b):
                continue
            if ok(cut):
                return cut
    # 4. どの規則にも当てはまらない。**strict なら「見つからなかった」と返す。**
    #    呼び出し側が limit いっぱいで探し直せるようにするため。
    #    2026-08-07、真ん中寄りで割ろうとして数字のかたまりに入り、
    #    「令和8年8月1」「60歳0か」と妥協していた。**妥協する前に、もう一度探す。**
    if strict:
        return 0
    cut = limit
    while cut > floor and not ok(cut):
        cut -= 1
    if ok(cut):
        return cut
    # **floor まで戻っても無いなら、floor より手前も見る。**
    # 2026-08-15、『残る割合は73.5パーセントから70.3パーセントへ』が
    # **『残る割合は73.5パーセン』／『トから70.3パーセントへ』**と割れました
    # （独立評価の3体のうち2体と、目視の1体が別々に指摘）。
    # limit 13 に対して floor は 6 で、**6〜13 のどこにも良い切れ目がありません**
    #  6〜8 は数字の中、9 は数字と単位のあいだ、10〜13 はカタカナの中。
    # そこで `ok()` を捨てて limit で割っていました。**「カタカナの途中では
    # 割らない」と書いた規則を、最後の1行が黙って踏み越えていた。**
    #
    # 5文字目（『残る割合は』／『73.5…』）は、かな→数字で規則2そのものです。
    # **短い行が1本できるだけで、読めない行は消えます。**
    # 短すぎる行は、この後の「短すぎる行を隣に寄せる」処理が拾います。
    for cut in range(floor - 1, 1, -1):
        if ok(cut):
            return cut
    return limit


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
            #
            # **残りが極端に短い行として孤立しないようにする。**
            # 2026-08-05、「最大およそ136万円変わり」／「ます。」と割れ、
            # 3文字の行が0.6秒だけ映った。limit いっぱいまで詰めてから割ると、
            # 端数が最後の行に落ちる。**2行に収まるなら、真ん中寄りで割る。**
            while len(piece) > limit:
                hi = limit if len(piece) > limit * 2 else (len(piece) + 1) // 2
                cut = 0
                if hi < limit:
                    # まず真ん中寄りで、良い切れ目だけを探す（端数の孤立を避ける）
                    cut = _best_cut(piece, max(2, hi), strict=True)
                    # **端数が頭に来ることもある。** 「時給」／「がいくら変わるか」と
                    # 2文字の行が出た（2026-08-08）。真ん中寄りの探索は
                    # **尻の孤立しか見ていなかった。** 頭が短すぎたら、
                    # 妥協せず limit いっぱいで探し直す。
                    #
                    # **切れ目の質でも見る。** 2026-08-09、「扶養1人」／「ぶんで下がる額」と
                    # 割れた。真ん中寄り（limit 6）では漢字→かなしか無く、
                    # そこで妥協していた。**limit 9 まで広げれば「扶養1人ぶんで」／
                    # 「下がる額」という助詞区切りがある。**
                    # 端数の孤立を避けるための探索が、**もっと悪い切れ目を選んでいた。**
                    if cut and (cut < MIN_LINE_CHARS
                                or (_is_kanji(piece[cut - 1]) and _is_kana(piece[cut]))):
                        cut = 0
                if not cut:
                    cut = _best_cut(piece, limit)
                lines.append(piece[:cut])
                piece = piece[cut:]
            buf = piece
    if buf:
        lines.append(buf)

    # **短すぎる行を隣に寄せる。** 読点で切った断片がそのまま1行になると、
    # 「手当が」のような3文字が0.6秒だけ映る（2026-08-07）。
    # 割る側（_best_cut）をいくら直しても、**束ねる側で出る**ので別に処理する。
    # 前に寄せられなければ後ろへ。どちらも溢れるならそのまま残す。
    if len(lines) > 1:
        packed: list[str] = []
        i = 0
        while i < len(lines):
            cur = lines[i]
            # **寄せた結果が limit を超えてはいけない。** 以前 `limit + 2` まで
            # 許していたら、「所得税は」(4) ＋「復興特別所得税」(7) = 11文字が
            # 9文字の枠に入らず、**画面側でさらに折られた**（2026-08-08）。
            # 字幕は溢れないが、同じ関数を使う箇条書き・見出しでは溢れる。
            if len(cur) <= MIN_LINE_CHARS and packed and len(packed[-1]) + len(cur) <= limit:
                packed[-1] += cur
            elif (len(cur) <= MIN_LINE_CHARS and i + 1 < len(lines)
                    and len(cur) + len(lines[i + 1]) <= limit):
                lines[i + 1] = cur + lines[i + 1]
            else:
                packed.append(cur)
            i += 1
        lines = packed

    # 行頭に句読点を残さない。前の行に戻す。
    # 「75歳開始なら1.84倍で」「、年331万2千円。」のように、
    # 読点が次の行の先頭に来ると読みにくい。
    #
    # **ここは limit を見ない。意図的。** 句読点1文字だけの行が残るほうが、
    # 1文字ぶん溢れるより悪い。図解側は `render()` が文字数を詰めて焼き直すので
    # 溢れは吸収される。**下の「短すぎる余りを戻す」処理とは判断が逆**だが、
    # あちらは最大2文字ぶん溢れうるので線を引いた。
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
    #
    # **戻した結果が limit を超えてはいけない。** 2026-08-09、ここだけ
    # 長さを見ておらず、`扶養1人ぶんで下がる`(10) ＋ `額`(1) を繋いで
    # 11文字にしていた（limit 10）。`15パーセントの`(8) ＋ `仮定`(2) も同じ。
    # **上の「短すぎる行を寄せる」処理には同じ検査があるのに、ここだけ無かった。**
    # 片方だけ直す形。溢れるくらいなら、短い行のまま残すほうがまし。
    merged: list[str] = []
    for line in lines:
        if merged and len(line) <= 2 and len(merged[-1]) + len(line) <= limit:
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

    # **どの文から折れた行かを、Name の欄に刷る。**
    # 2026-08-15、`_check_subtitles`（投稿前の検査）が
    # 『手取り増は35万9318円』→『13%なら』を「数字の途中で改行」と読んで
    # **投稿を止めました。** この2行は別の文の末尾と先頭で、折り返しではありません。
    # .ass だけを見ると文の切れ目が分からないので、検査は繋げて読んでいました。
    # Name はどの描画も使わない欄なので、ここに文の番号を置けば区別できます。
    for idx, seg in enumerate(segments):
        start, end = float(seg["start"]), float(seg["end"])
        span = max(0.1, end - start)

        lines = _chunk(seg["narration"], limit)
        total = sum(len(line) for line in lines) or 1
        cursor = start
        for line in lines:
            share = span * (len(line) / total)
            events.append(
                f"Dialogue: 1,{_ts(cursor)},{_ts(min(cursor + share, end))},Caption,"
                f"{SEGMENT_NAME_PREFIX}{idx},0,0,0,,"
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
