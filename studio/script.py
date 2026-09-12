"""台本の形。書くのは Fable（サブ本人・セッション内）。ここは形の検査だけ。

台本は `data/studio/scripts/<id>.json`（commit する。次の回が磨き続けるため）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from .common import DATA

SCRIPTS = DATA / "scripts"

# 画面の字幕は 1行 16字 × 3行 に収める。声の1コマは 70字 まで（約 12秒）。
MAX_SAY = 70
# §3 の 6「1文 40字以内」。2026-09-10 19:5x（hourly・Fable）まで lint はコマの 70字 しか見ておらず、
# 09/11 の本は 12:3x〜13:2x の言い回しの直し（「決まりでは、」「会社員の年金、」を足した）で
# 45字・50字 の文が 2つ 入ったまま 10周 の読み直しを抜けた（公開ずみ 5本 は 132文 中 1文 だけ）。
# 長い 1文 は hear の末尾切れ（§4 (2)）が出る当のもの —— 09/11 の 50字 の文を 38+21 に割ったら
# コマ4 の末尾切れが消えた（9/11 → 10/11）。止めない（`[?]`）: 割るか残すかは書き手が決める。
# 覆る条件: `[?]` を残したまま出した本の hear が末尾で鳴らない回が 3本 続いたら、この行は要らない。
MAX_SENTENCE = 40
_SENT_END = re.compile(r"(?<=[。？！])")
MAX_SHOW = 16
MAX_TOTAL_CHARS = 480   # Chirp3-HD 1.2 で実測 5.16字/秒（09/05・458字→88.8秒）→ 93秒。Neural2-D 1.08 は 450字→93.3秒（09/07・4.82字/秒 ＝ 同じ帯）。
                        # 上限は build が測る秒数（MAX_SECONDS）。455字 が 95秒 に当たる域（METHOD §11）
                        # **助言文は「60秒に収まらない」と言っていました**（2026-09-11 11:2x・hourly・Opus が直した）——
                        # この門は 95秒 の代理で、60秒 とは関係がありません。§2 は「60秒を越えてよい理由:
                        # 分かる説明に要る長さを削らない」と書いているので、**助言だけが §2 と逆を向いていました**
                        # （§3 の 9 の「年に」と同じ族 —— 門は正しく、助言文だけが食い違う形。書き手は助言に従います）。
                        # この回に実際に踏んだ: 481字 で鳴り、「60秒」と読めば本を半分に削る向きへ行く。
                        # 検査は tests/test_studio_total_chars_advice.py（**助言文の側の検査**）。
                        # 覆る条件: MAX_SECONDS が 60秒 に変わったら、この註ごと戻すこと。
                        # **この 480 は「まだ1度も焼いていない本」だけの代理です**（2026-09-12 13:4x・hourly・Opus）。
                        # 焼いたことが在る本は `chars_gate()` が**その本の実測 字/秒**から門を引き直します（下）。

MAX_SECONDS = 95.0      # **秒数の上限の正本**（`studio/cli.MAX_SECONDS` はここを読む ＝ 門は1か所・§5 の教訓 7つ目）
BUILD_JITTER = 0.03     # 同じ本でも焼くたびに揺れる幅（§2 の ±3%）。門はこのぶん手前に置く

# **字/秒 は本ごとに違います**（2026-09-12 13:4x・hourly・Opus が台帳 `built` 105件・8本 で数えた。API 0単位）。
# 実測（本ごとの最小 字/秒）: 09/08 **4.823** 〜 09/13 **5.552** ＝ **15%** 開いています。
# 同じ本の中は狭い（09/13 は 10回 焼いて 5.427〜5.552 ＝ 2.3%・09/12 は 3回 で 0.9%）。
# **同じ本文を焼き直した組（`sig` が同じ）は 1組 あり、そこは 90.4秒 → 90.4秒 で 0.00%**
# ＝ §2 の「焼くたびに ±3% 揺れる」は**同じ本文の揺れではなく、本文が違えば字/秒 が違う**ことのほうでした
# （組が 1組 しか無いので §2 は書き換えていません。**2組目が出た回が判定すること**）。
# **＝ 全部の本に同じ 480 を当てると、両側に外れます**:
#   遅い本  09/07 は **480字 で 96.9秒**（`MAX_SECONDS` 超え）を焼いています ＝ 門が**通してしまった**
#   速い本  09/11（503字ぶん）・09/13（500字ぶん）・09/09（486）・09/12（481）＝ 門が**削らせていた**
# だから、焼いたことが在る本は**その本の実測**で引く。8本 に当て直した表は JOURNAL 2026-09-12 13:4x。
# 覆る条件: (1) `sig` の同じ組が 3組 たまって、秒数が 1% 以上 振れていたら `BUILD_JITTER` をその実測へ。
#   (2) この門を越えた本が build で `MAX_SECONDS` を超えたら、`BUILD_JITTER` が足りない ＝ その実測で上げる。
#   (3) 本ごとの最小 字/秒 の差が 5% 未満に縮んだら、本ごとに引く値打ちが無い ＝ 480 の1つに戻す。
#   (4) **「いちばん遅い焼き」は、本の歴史が伸びるほど古い草稿に釘づけになります**
#       （09/13 は 10回 焼いて 5.427〜5.552 で、いちばん遅いのは初期の草稿。いまの本文は 5.501 ＝ 門で 7字 の差）。
#       同じ本の中の振れ（実測 0.9〜2.3%）が `BUILD_JITTER`（3%）の下に収まる回が 3本 続いたら、
#       **いちばん遅い → いちばん新しい** へ移してよい（余白が本文の側へ戻ります）。
#       いま移していないのは、8本 に当て直した表で裏を取ったのが「いちばん遅い」のほうだからです。


def built_rate(vid: str, rows: list[dict] | None = None) -> float | None:
    """その本の実測 字/秒 のうち **いちばん遅いもの**（台帳 `built`）。焼いていなければ None。

    いちばん遅いほうを採るのは、門が**越える側に外れない**ため（上の (2)）。
    """
    from .common import ledger_rows
    rows = ledger_rows() if rows is None else rows
    rates = [r["chars"] / r["seconds"] for r in rows
             if r.get("event") == "built" and r.get("id") == vid
             and r.get("chars") and r.get("seconds")]
    return min(rates) if rates else None


def chars_gate(vid: str, rows: list[dict] | None = None) -> tuple[int, str]:
    """字数の門と、その出どころの1行（助言文に出す）。"""
    rate = built_rate(vid, rows)
    if rate is None:
        return MAX_TOTAL_CHARS, (f"{MAX_TOTAL_CHARS}まで ＝ **まだ1度も焼いていない本の代理**"
                                 f"（`studio/script.MAX_SECONDS` {MAX_SECONDS:.0f}秒 の代理）")
    gate = int(rate * MAX_SECONDS * (1 - BUILD_JITTER))
    return gate, (f"{gate}まで ＝ **この本の実測 {rate:.3f}字/秒** × {MAX_SECONDS:.0f}秒 × "
                  f"{1 - BUILD_JITTER:.2f}（焼き直しの揺れ）。台帳 `built` から引いた")

# 書き手が人間のふりをする言い方（収益化ポリシー: AI が人間の専門家を装って sensitive topic を語る形）
# 裸の「年」＋数字（「年66万円」）。Chirp3-HD は「とし」と読む（実測 09/05・09/06）
# **「年に」も同じ穴です**（2026-09-09 02:5x に足した。`hourly` が名指しし、optimizer が撃った）。
# 実測: 09/10 の本（`2026-09-10-izoku-kosei-4bunno3`・455字）は lint を `[?]` 0 で通り、
# **hear が 11コマ中 5コマ しか一致しませんでした**。外れた 6コマ は全部 `予定「ねん」 聞こえた「とし」` で、
# 「年に」を含む say は **[2,3,5,8,9,10]** ＝ **hear が割った 6コマ とそのまま一致**（API 0単位 で裏を取った）。
# **原因は、この下の助言文そのものでした** —— 145行 が「『1年で』『年に』に」と、**「年に」へ書き換えろ**と
# 言っており、書き手はそのとおりに書いています（「夫の厚生年金は年に120万円」）。
# ＝ **門が見ていない形を、門の助言が勧めていました。** §3 の 9 が挙げているのは「1年で」「12か月で」だけで、
# 「年に」は §3 に無い —— **助言だけが §3 と食い違い、書き手は助言の文を見ます。**
# 直しは2つで、どちらも要ります: (a) 助言から「年に」を外す（下）・(b) この門を「年に」まで広げる（ここ）。
# 「毎年10月」「5年に」は違う（先読みの否定に 一-龥 と数字が入っている ＝ janome が まいとし・ごねん と読む）。
BARE_YEAR = re.compile(r"(?<![0-9０-９一-龥])年(?:に)?(?=[0-9０-９])")
# **画面の側だけに残る「年に」**（2026-09-09 06:5x・optimizer・Opus）。上の門は `s.say` しか読まないので、
# 声だけ直して `show`/`sub` が古いまま残った回を、どの道具も見ていませんでした
# （hear は音にならない画面に当たらず、crosscheck は説明欄と notes しか見ない）。
# **拾うのは「年に」だけで、裸の「年」＋数字 は拾いません。** 先に広いほうで撃って外したからです ——
# 09/06 の本 `zaishoku-62man` コマ8 の show は「年66万円多い」で、声は「1年で66万円です」。
# これは古い残りではなく、**16字の見出しとして正しい縮め方**でした（画面は読まれないので誤読も起きない）。
# 「年に」だけが違うのは、それが縮め方として何も得しない形（「年320万円」のほうが短い）で、
# **§3 が名指しで捨てた言い方**だからです ＝ 在れば、声を直したときの取り残し。
SCREEN_NEN_NI = re.compile(r"(?<![0-9０-９一-龥])年に(?=[0-9０-９])")
# 返信の側の守り（オーナー 2026-09-08 21:4x「コメントで視聴者にAIですかって聞かれたら何で答えるの？」）。
# 答えは「はい」。人間だと名乗る文・AI を否定する文は `cli reply` が止める（`data/studio/replies/ai-desu.txt` が定型の答え）。
# 理由: 声は聞けば分かる（08/29「ＡＩナレーショングダグダ」）ので隠せず、嘘が1つ見つかると数字まで疑われる。
AI_DENIAL = re.compile(r"(AI|ＡＩ|エーアイ|機械|ロボット|自動|ボット)(では|じゃ)(ない|ありません|なく)|(人間|本人|手作業|手)(が|で)(書い|作っ|読ん|話し|返信し)|(私|わたし)は人間|人間です")
HUMAN_CLAIM = re.compile(r"(私は|わたしは)?(元|現役の)?(税理士|社労士|社会保険労務士|FP|ファイナンシャルプランナー|経理|人事)(として|です|でした|を[0-9０-９]+年)")

# 読みの守り（オーナー 09/06「漢字の読み変なのいっぱいだよ。今後一個も出ないように考えて」）。
# hear（whisper → pykakasi）は、TTS が誤読しても whisper がその漢字を書けば両側が同じ仮名になり **見えない**
# （hear.py の冒頭に書いてある盲点。実測: hear 11/11 の本をオーナーが聞いて「読み変なのいっぱい」）。
# だから守りは TTS の側に置く: **声の中の漢字の並びは、全部 `yomi` で読みを固定する**（customPronunciations）。
# 例外は (a) 数字の直後の助数詞（65歳・15万円・5年・60か月）、(b) 送り仮名つきの動詞・形容詞の語幹（増える・待つ・多く）。
# (b) は送り仮名で読みが決まるので固定しなくてよい（固定できない —— TTS が送り仮名つきの phrase を拒む）。
# 語幹はここに足す（足すときは、その送り仮名で読みが1つに決まる字だけ。「先に」「後で」「月に」「得か」「額は」は
# 送り仮名ではなく助詞なので、ここに入れない —— それらは yomi か、ひらがな）。
COUNTER_RUN = re.compile(r"(?<=[0-9０-９])(万円|千円|万|千|百|円|歳|年|倍|日|回|人|か月)")
VERB_STEMS = {"増", "待", "多", "割", "足", "続", "迷", "教", "生", "追", "受", "取", "戻", "同", "引", "決", "遅",
              "少", "長", "高", "安", "早", "働", "払", "見", "知", "言", "考", "選", "始", "終", "変", "違",
              "使", "出", "入", "作", "持", "買", "売", "上", "下", "減", "残", "確", "亡", "住", "越", "超",
              "比", "調", "書", "読", "聞", "思", "立", "止", "届", "落", "抜", "払", "貸", "借", "返"}
KANJI_RUN = re.compile(r"[一-龥々]+")
# 「点」（オーナー 09/05〜06「ナレーションが点って言ってるとこだよ」「点って漢字で動画に出てる」）。
# 小数（0.7・1.42）も声では「れいてんなな」になるので、声と画面に書かない —— 整数で言い換える
# （1か月 0.7% → 10か月で 7%・1.42倍 → 42% 増）。説明欄には書いてよい。
TEN = re.compile(r"点|[0-9０-９]\.[0-9０-９]")
# `yomi`（customPronunciations）を Chirp3-HD が**無視した**語（実測 09/06 15:xx・optimizer。API は 200 で受けて既定の読みのまま）。
# 既定の読みが正しくない・割れる語だけ挙げる: 裸の「額」→ ひたい（08/16 にオーナーが耳で見つけた）・額面 → ひたいめん・市場（いちば/しじょう）・
# 辛い（からい/つらい）・十分（じゅっぷん/じゅうぶん）。yomi で守れないので **本文の語を変える**（額 → 金額・十分 → じゅうぶん）。
# 「金額」「年額」「月額」のような熟語は辞書にあり正しく読む（09/06 17:xx の本で 金額 → きんがく を hear で確認）。
YOMI_IGNORED = re.compile(r"(?<![一-龥])額(?![一-龥])|額面|市場|辛い|十分")


def uncovered_kanji(say: str, yomi: dict[str, str]) -> list[str]:
    """yomi でも助数詞でも語幹でもない漢字の並びを返す（空なら、声の漢字は全部 読みが決まっている）。"""
    keys = sorted((k for k in yomi if re.fullmatch(r"[一-龥々]+", k)), key=len, reverse=True)
    text = COUNTER_RUN.sub(lambda m: "　" * len(m.group()), say)   # 助数詞を消す（幅を保つ）
    bad = []
    for m in KANJI_RUN.finditer(text):
        run = m.group()
        rest = run
        for k in keys:
            rest = rest.replace(k, "")
        if not rest:
            continue
        stem_ok = (len(rest) == 1 and rest in VERB_STEMS and run.endswith(rest)
                   and m.end() < len(text) and re.match(r"[ぁ-ゖ]", text[m.end()]))
        if not stem_ok:
            bad.append(run)
    return bad


# まん中の板（2026-09-10 13:2x・hourly・Fable。オーナー 12:4x「画面を有効活用できてない」・受け取り帳 `52f141fa`）。
# 1行 14字 × 5行 まで（`slides.board_layout` が 60px で 5行 を字幕の上に収める実測）。札は `slides.TAG_COLORS` の 5つ。
MAX_BOARD_LINES = 5
MAX_BOARD_CHARS = 14
# **札「しくみ」は 2026-09-11 20:0x に足した**（hourly・Opus。オーナー 19:5x「制度の仕組みは説明した方が
# 良くない？計算結果だけ出されても何でそうなるの？ってなる」・受け取り帳 `f3edb61f`。19:3x「今回だけ教えても
# またおんなじことになるだろ」＝ その本だけ直すのではなく、**毎本の型**にする）。
# 「決まり」（そう決まっている）と「しくみ」（**なぜそう決まっているか**）は別のもので、
# 5つ の札には後者の置き場がありませんでした。口は決めない（結論・見る所 と同じ・§3 の 7-b）。
TAGS = ("前提", "しくみ", "決まり", "計算", "結論", "見る所")

# 札と声の言い回しの対応（§3 の 7-b。**3つ だけ** —— 結論・見る所・しくみ には口を決めない）。
# 2026-09-11 21:4x（optimizer・Opus）に `lint` の `[?]` にした（§15 の申し送り）。
# **輪も lint も、ここまで `tag` を1度も見ていませんでした** —— `critic.critique_screen` に
# 板と札は渡るが `tag` と `say` の言い回しの対応は誰も見ない（§4 (0) と同じ族）。
# **1文目のどこかに在るか**で見ます（文頭ちょうどではない）—— 実物の 09/12 コマ5 が
# 「そこで決まりでは、…」で、接続詞が 1つ 前に付く形は書き手の慣行だから（撃って数えた:
# 頭ちょうどにすると 09/12 の本で 1件 増える）。**止めない。**
TAG_OPENERS = {"前提": "たとえば、", "決まり": "決まりでは、", "計算": "計算すると、"}
# 覆る条件: (1) `[?]` が 3本 続けて「要らないと決めた理由」で埋まったら、その族には門を当てない
# （§3 の 7-c の覆る条件 (3) と同じ形）。(2) §3 の 7-b が口を変えたら、この表を一緒に直すこと
# （口の出どころは 1か所）。(3) 板を外す回が来たら（7-b の覆る条件）、この門も一緒に戻す。

# notes の中の「コマN「…」」＝ 声の引き写し（2026-09-11 21:4x・optimizer・Opus。§15 の申し送り）。
# **声を書き直した回が、写しを置いていきます** —— 10時間 で 2度 踏み（11:5x・20:0x）、
# 20:0x の コマ11 の写しは**もう声に無い分離課税**を「コマ11 に在る」と言っていました
# ＝ 次の回が、その所を消しにかかる向き（derivation は JOURNAL 09/11 21:2x の hourly の刻）。
# **同じ族**（あとの手の直しが、前の手の答えを古くする）: §4 (0-b)・`loop_sig`・`build_sig`。
# **この族の中で、これだけが機械の門を持っていませんでした。**
# **助詞を 1つ はさむ形も拾います**（`コマ11 は「…」`）—— この形が、いちばん高い写し
# （分離課税がどのコマに在るか）を持っていた当のものでした。はさんでよいのは助詞 1字 と空白だけ
# ＝ `コマ3・コマ4・コマ5）…財務省「…」`（**別の出どころの引用**）には当たりません（撃って確かめた）。
# **`で`／`では` も助詞として通す**（2026-09-13 03:4x・hourly・Fable。実物: 09/14 の notes の
# 「声はコマ13で「ねんきん定期便で見る」」—— コマ4 を削って 12コマ になったあとも 13 を指したまま
# 2周 通った。`で` が無いこの式では **1件も鳴らず**、人が §4 (0) の型で拾った（2本目）。
# 足して全 9本 に当て直すと、増えるのは 09/07（公開ずみ・記録の側）2件 と この 1件 だけ。
# 覆る条件: 助詞の並びがこれで足りない実物（`コマNにも「…」` など）が出たら、そこで広げること。
_NOTE_QUOTE = re.compile(r"コマ\s*([0-9０-９]+)\s*(?:[はがのもで]|では)?\s*[「『]([^」』]{2,})[」』]")
_QUOTE_DROP = re.compile(r"[\s\*＊。、，,\.]")
# **短い引用と、問いの札は見ません**（2026-09-11 21:4x に 7本 の notes へ当てて決めた）。
# 21:2x の述語（部分列かどうか）を素で当てると、実物 7本 ＋ 陽性対照 1本 で **42件** 鳴り、
# **本物は 9件**（09/12 の直す前 5件 ＝ 陽性対照 ＋ 09/11 の 4件 ＝ **公開ずみの本に残っていた本物**
#  —— 09/10 10:0x に `hourly` が コマ5・6 の年齢の数えを直した回が、notes の写しを置いていった側。
#  **この門が無ければ、次に §14 を引く回はそこを「声に在る」と読みます**）でした。
# 外れの 33件 は 2つ の族です:
#   (a) **短い言い回しの断片**（「厚生年金」「くらい」「の金額」「12か月で」…）＝ notes が語を指しているだけ
#   (b) **問いの札**（「なぜ割るのか」「42% がどこから来るか」）＝ 声の引き写しではなく見出し
# 門は **正規化して 10字 以上・末尾が「か」でない** の 2つ。これで **42 → 15件**
# （**本物 9件 は 1件も落ちません** ＝ 外れだけが 33 → 6件）。
# **残る外れは、notes の中の「作業の記録」だけ**（09/06 の 2件・09/07 の 4件 ＝
# 「だから 10か月 の単位そのものを捨てた: コマ2「…」」の形で、**わざと古い字を引いている側**）
# —— これは字面では本物と分けられないので、**残します**（止めないので値段は 1行 読むだけ）。
# 覆る条件: (4) 作業の記録の側が 3本 続けて鳴ったら、notes に記録を書く所を分ける
#           （例: 【この本の直しの記録】の見出しの下は見ない）か、この門ごと外すこと。
# (5) 10字 の門で本物を落とした回が 1度でも出たら、下げること（いま本物の最短は 11字）。
_QUOTE_MIN = 10

# **鳴った行の「札」を分ける印**（2026-09-12 00:0x・optimizer・Opus。§14 の申し送り
# 「直す先は**印字の側**でもよい」）。**門は動かしません** —— 鳴る件数は 1件も変わらず、
# 変わるのは**その行が何と言うか**だけです。
#
# **なぜ印字の側か**（数）: いま鳴る 9件 は**全部 作業の記録**（09/06 2・09/07 4・09/11 3）で、
# 本物は 0件 です。`_QUOTE_MIN` の註の覆る条件 (4) は「記録が 3本 続けて鳴ったら、記録を書く所を
# 見出しで分けるか、門ごと外す」と書いていますが、**どちらも高い**:
#   ・門ごと外す → この門は実物で**本物を 6件** 拾っています（09/11 コマ8 の 1件 ＋ 09/12 の 5件）
#   ・notes の書き方を分ける → 7本 の notes を書き直す（`hourly` の持ち場に手が入る）
# **いま高いのは「読む側が 記録 を本物と読んで、記録を消す向きに直す」こと**（§14 の申し送りの字）で、
# それは**札を変えるだけで消えます**（値段 0）。
#
# **述語（実物 15件 に当てて決めた・API 0単位）**:
#   写しの印  `＝ 声の` が左に在る（`・` で継いだ鎖も同じ ＝ 前の引用から継がれた側）
#             → **本物の 6件 のうち 5件** がこの形。記録の 9件 は **0件**
#   記録の印  引用のすぐ右／左に、書き直しを言う語が在る（下の 2つ の表。
#             **`・` で継いだ鎖も同じ** —— 印は 1つ目の左に在り、長い引用を跨ぐと 24字 から外れます）
#             → **記録の 9件 とも当たり**。本物の 6件 は **0件**
# **順は 写し → 記録 → どちらでもない**。写しの印が在る行は、記録の語が在っても強い札のまま
# （写しの印が付くのは「＝ 声の …」＝ notes が声を引いている所そのものだから）。
# **本物 6件 のうち 2件**（09/12 の コマ11・コマ5）は写しの印を持たず、**いまと同じ札**のまま出ます
# ＝ **この直しで弱くなる行は 1件もありません**（弱い札が付くのは 記録 の 9件 だけ）。
#
# 覆る条件:
#   (6) 写しの印（`＝ 声の`）を持つ行が**記録**だった回が 1度でも出たら、この 2つ の印は分けられない
#       ＝ 札を 1つ に戻すこと（そのときは `_QUOTE_MIN` の (4) の「記録を書く所を分ける」側へ）。
#   (7) 記録の印を持つ行が**本物**だった回が 1度でも出たら、その語を下の表から外すこと
#       （表は「書き直しを言う語」だけ ＝ 出どころや式を言う語を入れないこと）。
#   (8) `＝ 声の` の形を使わない notes の書き方に変わったら、写しの印は空振り ＝ その回が外すこと
#       （(1) と同じ日に引かれます）。
_QUOTE_COPY_MARK = "声の"          # 左 14字 以内（`＝ 声の コマ6「…」` の形）
_QUOTE_COPY_CHAIN = "・"           # 直前の引用から `・` で継がれた側も写し
# 書き直しを言う語（**右**。引用のすぐ後ろ 8字 以内）
_QUOTE_REC_RIGHT = ("→", "だった", "落とした", "捨てた", "外した", "戻した")
# 同じ語（**左**。引用のすぐ前 24字 以内）—— 記録は「…を落とした: コマ2「…」」の向きでも書かれる
_QUOTE_REC_LEFT = ("→", "直し:", "直し：", "直した", "落とした", "捨てた", "収めるため", "のままだと")


def _quote_norm(s: str) -> str:
    """引き写しの照合用: 空白・`*`・句読点を落とす（`hear.loose()` と同じ考え方）。"""
    return _QUOTE_DROP.sub("", s)


def _quote_kind(notes: str, start: int, end: int, prev_end: int, prev_kind: str) -> str:
    """鳴った引用が「写し」か「作業の記録」か（**札を選ぶだけ。門は動かさない**・上の註）。

    返すもの: `"copy"`（写し ＝ 声に合わせる）／`"record"`（作業の記録かもしれない）／`""`（どちらでもない）。
    `prev_end`/`prev_kind` は**同じ notes の 1つ前の引用**（`・` の鎖を継ぐため）。
    """
    left = notes[max(0, start - 24):start]
    right = notes[end:end + 8]
    # (1) 写しの印 —— 左 14字 に `＝ 声の`、または 1つ前の写しから `・` で継がれた側
    if _QUOTE_COPY_MARK in notes[max(0, start - 14):start]:
        return "copy"
    chained = (prev_end is not None
               and _QUOTE_COPY_CHAIN in notes[prev_end:start]
               and not notes[prev_end:start].strip("・ 　"))
    if prev_kind == "copy" and chained:
        return "copy"
    # (2) 記録の印 —— 書き直しを言う語が、すぐ右か左に在る
    if any(w in right for w in _QUOTE_REC_RIGHT) or any(w in left for w in _QUOTE_REC_LEFT):
        return "record"
    # (3) 記録の鎖 —— `捨てた: コマ2「…」・コマ3「…」` の 2つ目（印は 1つ目の左に在り、
    #     長い引用を跨ぐと左 24字 から外れます。**鎖は写しと同じ形で継ぎます**）
    if prev_kind == "record" and chained:
        return "record"
    return ""


def stale_note_quotes(notes: str, says: list[str]) -> list[str]:
    """notes の「コマN「…」」が、そのコマの `say` の部分列でなければ名指しする（止めない）。

    述語（2026-09-11 21:2x に hourly が実物で確かめたもの）: 引用を `…` で割り、
    空白・`*`・句読点を落として、**その `say` に全部 在るか**。
    直したあとの 09/12 の本で **7件 とも OK・外れ 0**、直す前なら **5件** が鳴る。

    **`build_sig` を上げる必要はありません** —— notes は焼きに渡らないので、
    鳴っても焼き直しは不要（`description` も同じ）。

    覆る条件:
      (1) notes が「コマN「…」」の形を使わない書き方に変わったら、この門は空振り ＝ その回が外すこと。
      (2) 鳴った回に「写しのほうが正しく、声が古い」だったことが 1度でも在れば、門の向きが逆
          ＝ そのときは**声を直す側**の印字にする（いまは写しが従で、声が主）。
      (3) `description` の側にも同じ形の写しが出たら、対象を広げる
          （2026-09-11 時点の実測: description に コマ引用は 0件）。

    **札は 3つ に分かれます**（2026-09-12 00:0x・optimizer・Opus。`_QUOTE_COPY_MARK` の註）——
    **鳴る件数は 1件も変わりません**。覆る条件 (6)(7)(8) もそこ。
    """
    out: list[str] = []
    prev_end: int | None = None
    prev_kind = ""
    for m in _NOTE_QUOTE.finditer(notes or ""):
        n = int(m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789")))
        quote = m.group(2)
        flat = _quote_norm(quote).replace("…", "")
        if len(flat) < _QUOTE_MIN or flat.endswith("か"):
            continue      # (a) 短い断片 / (b) 問いの札（`_QUOTE_MIN` の註）
        kind = _quote_kind(notes or "", m.start(), m.end(), prev_end, prev_kind)
        prev_end, prev_kind = m.end(), kind
        if not 1 <= n <= len(says):
            out.append(f"notes の「コマ{n}「{quote[:14]}…」」は、この本に無いコマを指している"
                       f"（コマは 1〜{len(says)}）")
            continue
        say = _quote_norm(says[n - 1])
        missing = [p for p in quote.split("…") if _quote_norm(p) and _quote_norm(p) not in say]
        if missing:
            where = f"外れた所: {'／'.join(x[:14] for x in missing)}"
            if kind == "record":
                # **書き直しの記録らしい行** —— 直す先は notes ではありません。
                # ここを「古い写し」と読んで消すと、**何をどう直したかの記録が消えます**。
                out.append(f"notes の「コマ{n}「{quote[:20]}…」」は、いまの コマ{n} の声に在りません"
                           f"（**すぐ前後に書き直しの語が在る ＝ 作業の記録らしい**。"
                           f"記録なら、そのままでよい —— 消さないこと。{where}）")
            elif kind == "copy":
                out.append(f"notes の「コマ{n}「{quote[:20]}…」」が、いまの コマ{n} の声に在りません"
                           f"（**`＝ 声の` の写し ＝ 写しを声に合わせる**。"
                           f"声を直した回が写しを置いていった側。{where}）")
            else:
                out.append(f"notes の「コマ{n}「{quote[:20]}…」」が、いまの コマ{n} の声に在りません"
                           f"（声を直した回が写しを置いていった側 ＝ 写しを声に合わせる。{where}）")
    return out

# 輪の指紋の**作り方**の版（`Script.loop_sig`）。**作り方を変えたら必ず上げること** ——
# 上げないと、台帳に貯まった古い指紋と比べたときに「本文が動いた」と嘘の印字が出ます
# （2026-09-11 13:2x に 1度 そう出た: 板の継ぎ方を変えた回。`cli.loop_stale` が版で分けます）。
#   1 … 板を行ごとに `|` で継ぐ（12:3x）
#   2 … 板を継いでから署名する（13:1x。行の割り直しでは動かない ＝ 覆る条件 (1)）
LOOP_SIG_VERSION = 2

# 焼き（mp4）の指紋の**作り方**の版（`Script.build_sig`）。**作り方を変えたら必ず上げること**
# （`LOOP_SIG_VERSION` と同じ理由 —— 上げないと古い刻印と比べて「本文が動いた」と嘘を言う）。
#   1 … 焼きが読む物ぜんぶ（2026-09-11 20:5x）
BUILD_SIG_VERSION = 1


class Segment(BaseModel):
    say: str = Field(..., description="声で読む文。ふつうの話し言葉。")
    show: str = Field("", description="画面の大きい字（16字まで）。数字か短い見出し。")
    sub: str = Field("", description="画面の小さい字（任意）。")
    tag: str = Field("", description="札（前提／しくみ／決まり／計算／結論／見る所）。声の言い回し（たとえば・決まりでは・計算すると）と同じ札。「しくみ」は『なぜそう決まっているか』のコマ。")
    board: list[str] = Field([], description="まん中の板。そのコマまでの前提と数の積み上がり（14字×5行まで）。最後の行がいまのコマ。")


class Script(BaseModel):
    id: str
    date: str                       # 公開する日（JST）
    title: str
    takeaway: str                   # 視聴者が言い返せるはずの1文（冷読テストの正解）
    description: str = ""
    tags: list[str] = []
    # 09/07 14:3x に Neural2-D・1.08 へ戻した（オーナー 13:3x「ナレーション前の音声の方が良かった」＝ 09/04 までの 24本の声）。
    # Chirp3-HD-Charon は 09/05〜09/07 の3本だけ。yomi の効き方が声で違う（tts.py 冒頭）。
    voice: str = "ja-JP-Neural2-D"
    rate: float = 1.08
    yomi: dict[str, str] = {}       # 読みを固定する語 → ひらがな（TTS と聞き取り検算の両方が使う）
    kana_in_voice: list[str] = []   # Neural2 系のとき、TTS に渡す文の中で仮名に置き換える語（yomi の語。hear で TTS の誤読が出た語だけ）
    image_prompt: str = ""          # 背景画像の注文文（GPT Image 2.0。文字を入れない）
    segments: list[Segment]
    notes: str = ""                 # 出典・前提・計算の根拠（人が読む）

    def total_chars(self) -> int:
        return sum(len(s.say) for s in self.segments)

    def loop_sig(self) -> str:
        """**輪（§4 (1)）が実際に読んだ本の指紋**（2026-09-11 12:3x・hourly・Opus が足した）。

        なぜ: §4 (1) は「直す → **最初から評価し直す**」と書いていますが、**その順を見ている道具が
        1つもありませんでした**。09/12 の本で実際に踏んだ —— 11:0x の回は コマ8・9・11 を直したあと
        **read も critique も撃たずに** build → hear → sheet → crosscheck へ進み、METHOD §15 に
        「輪を開け直して閉じた」と書いています。台帳の刻で出ます（最後の `critique` 10:58:51・
        最後の `cold_read` 10:59:59・直しの commit 11:01）。12:0x に**その最後の本文**へ
        critique を当てたら **real 2件**（どちらも直した当の コマ11）で、輪は閉じていませんでした。
        ＝ **§4 (0-b) と同じ族**（あとの手の直しが、前の手の答えを古くする）。ただしこちらは
        **輪が自分の答えを古くする**形で、(0-b) のように手を1つ足しても直りません
        —— 要るのは「この答えは、いまの本文のものか」を機械が持つことです。

        指紋は `critique` が読む物ぜんぶ（`critique_screen` ＝ say/show/sub/tag/board。
        `cold_read` の say はその部分集合）。`notes`・`description` は輪に渡らないので入れません
        —— 入れると §4 (0) の説明欄の直しで輪が古い扱いになり、**鳴らない印字**（狼少年）になります。

        **頭に版（`LOOP_SIG_VERSION`）を付けてあります**（2026-09-11 13:2x に、同じ回で踏んで足した）——
        **作り方を変えると、台帳に貯まった指紋は全部 合わなくなります**。版が無いと、その回の印字は
        「本文が動いた」と**嘘をつきます**（実際に 1度 そう出た）。版が違う行は「作り方が変わった」と言い、
        **本文が動いたとは言いません**（`cli.loop_stale`）。

        覆る条件: (1) この印字が「古い」と言った回に、**say/show/sub が 1字も変わっていなかった**
        ことが 1度 でもあれば、指紋の範囲が広すぎる（tag・board を外すこと）。
        **【2026-09-11 13:1x に、この (1) を自分で引きました】** 板の行を割り直しただけの回で鳴った
        —— 外したのは tag・board ではなく**板の行の割り方**だけ（下）。**tag と board の中身は残す**
        （どちらも `critique_screen` が渡している ＝ critic が読む物）。
        **次に (1) を引いたときは、tag を外す番です。**
        (2) 逆に、指紋が同じまま輪の答えが古くなった回が出たら（例: `critique` の問い文を変えた回）、
        指紋に `critic.critique` のプロンプトの版を足すこと（＝ `LOOP_SIG_VERSION` を上げる）。
        """
        import hashlib
        # **板は行を継いでから署名します**（2026-09-11 13:1x に、上の覆る条件 (1) を自分で引いた）——
        # 板の行を割り直しただけの回（`say`/`show`/`sub` は 1字も動いていない）で指紋が動き、
        # 「輪を撃ち直せ」と鳴りました。実物: コマ11 の板を
        # ['1年にとどかない日数', 'も1年ぶんになる'] → ['1年にとどかない日数も', '1年ぶんになる'] へ
        # （語の途中で折れていたのを直しただけ ＝ sheet の折れの直し）。
        # **critique に渡るのは板の中身**（`critique_screen` は ' ／ ' で継いで渡す）で、
        # **行の割り方は渡らない**ので、継いで署名すれば中身の直しだけが指紋を動かします。
        body = "\n".join(f"{g.say}\x1f{g.show}\x1f{g.sub}\x1f{g.tag}\x1f{''.join(g.board)}"
                         for g in self.segments)
        return f"{LOOP_SIG_VERSION}:{hashlib.sha256(body.encode('utf-8')).hexdigest()[:12]}"

    def build_sig(self, image=None) -> str:
        """**焼いた mp4 が、いまの本文で焼かれた物かの指紋**（2026-09-11 20:5x・hourly・Opus が足した）。

        なぜ: **`cmd_schedule` は `work/<id>.mp4` が在るかしか見ていませんでした**
        （`if not mp4.exists()` の 1行 だけ）。題と説明欄は**上げる瞬間の台本**から読むので
        （`yt.upload(mp4, s.title, s.description, ...)`）、**焼いたあとに台本を直して予約すると、
        新しい題と説明欄に古い声と絵が付いた本が出ます** —— しかも印字は「上げた」だけで、
        どこにも「古い」と出ません。§4 (0-b) と `loop_sig` と**同じ族**（あとの手の直しが
        前の手の答えを古くする）で、**ここは族のいちばん最後 ＝ 直す機会がもう無い所**です。

        `loop_sig` では代われません。焼きが読むのに輪が読まない物が **4つ** 在ります:
          voice・rate            声そのもの（09/07 に 1度 入れ替えた）
          yomi・kana_in_voice    読みの直し（§4 (2) の輪が毎本 触る所。**声だけが変わり、字は 1字も動かない**）
          板の行の割り方         `loop_sig` は **継いでから**署名する（行を割り直しても動かない ＝ 13:1x の
                                 覆る条件 (1)）。**絵の上では行の割り方が見える**ので、焼きの側は割り方を入れる
          背景の絵               注文が届く前に焼くと単色。届いたあと焼き直さずに予約すると**単色のまま出る**
                                 （`trend.image_orders` が名指ししている当の形）。名と大きさで見る
                                 （刻は worktree を跨ぐと動くので使わない）

        `title`・`description`・`tags`・`notes` は**入れません** —— 焼きに渡らず、上げる瞬間に
        台本から読み直されるので、直しても mp4 は古くなりません（入れると鳴らない印字＝狼少年になる）。

        覆る条件: (1) この指紋が「古い」と言った回に、**焼き直した mp4 が前と同じ物だった**ことが
        1度 でもあれば、範囲が広すぎる（まず `board` の行の割り方を外す番）。
        (2) 逆に、指紋が同じまま mp4 が古かった回が出たら（例: `slides.py` や `tts.py` を直した回・
        ffmpeg の欄を変えた回）、指紋に**道具の版**を足すこと（＝ `BUILD_SIG_VERSION` を上げる）。
        **いまは道具の版を見ていません** —— `studio/` を直した回は、その回が焼き直すこと。
        """
        import hashlib
        body = "\n".join(f"{g.say}\x1f{g.show}\x1f{g.sub}\x1f{g.tag}\x1f" + "\x1e".join(g.board)
                          for g in self.segments)
        yomi = "\x1f".join(f"{k}={v}" for k, v in sorted(self.yomi.items()))
        kana = "\x1f".join(sorted(self.kana_in_voice))
        img = ""
        if image is not None:
            try:
                img = f"{image.name}:{image.stat().st_size}"
            except OSError:
                img = f"{image.name}:?"
        body = f"{body}\x1d{self.voice}\x1d{self.rate}\x1d{yomi}\x1d{kana}\x1d{img}"
        return f"{BUILD_SIG_VERSION}:{hashlib.sha256(body.encode('utf-8')).hexdigest()[:12]}"


    def problems(self) -> list[str]:
        out = []
        if not re.fullmatch(r"[a-z0-9-]+", self.id):
            out.append("id は英小文字・数字・ハイフンだけ")
        if not (5 <= len(self.segments) <= 16):
            out.append(f"コマ数 {len(self.segments)}（5〜16）")
        for i, s in enumerate(self.segments, 1):
            if len(s.say) > MAX_SAY:
                out.append(f"コマ{i} say が {len(s.say)}字（{MAX_SAY}まで）")
            if len(s.show) > MAX_SHOW:
                out.append(f"コマ{i} show が {len(s.show)}字（{MAX_SHOW}まで）")
            if HUMAN_CLAIM.search(s.say):
                out.append(f"コマ{i} 人間の専門家を名乗っている: {s.say[:30]}")
            for run in uncovered_kanji(s.say, self.yomi):
                out.append(f"コマ{i} 「{run}」の読みが固定されていない（yomi に足すか、ひらがなで書く）")
            for field in ("say", "show", "sub"):
                m = TEN.search(getattr(s, field))
                if m:
                    out.append(f"コマ{i} {field} に「{m.group()}」（点・小数）。整数で言い換える")
            if s.tag and s.tag not in TAGS:
                out.append(f"コマ{i} tag「{s.tag}」は {'／'.join(TAGS)} のどれかに")
            if len(s.board) > MAX_BOARD_LINES:
                out.append(f"コマ{i} board が {len(s.board)}行（{MAX_BOARD_LINES}まで）")
            for ln in s.board:
                if len(ln) > MAX_BOARD_CHARS:
                    out.append(f"コマ{i} board の行「{ln}」が {len(ln)}字（{MAX_BOARD_CHARS}まで）")
                if TEN.search(ln):
                    out.append(f"コマ{i} board に「{TEN.search(ln).group()}」（点・小数）。整数で言い換える")
        gate, why = chars_gate(self.id)
        if self.total_chars() > gate:
            out.append(f"合計 {self.total_chars()}字（{why} ＝ build が測る秒数の上限"
                       f"（`studio/cli.MAX_SECONDS`）に当たる字数。**60秒の門ではありません**"
                       f" —— §2 は 60〜95秒。削るのは秒数であって、分かる説明に要る長さではない）")
        if "#Shorts" not in self.title and "#shorts" not in self.title:
            out.append("title に #Shorts が無い")
        if len(self.title) > 100:
            out.append("title が 100字 を超える")
        alltext = "".join(s.say for s in self.segments)
        for k, v in self.yomi.items():
            if k not in alltext:
                out.append(f"yomi の語「{k}」が本文に無い")
            if not re.fullmatch(r"[ぁ-ゖー]+", v):
                out.append(f"yomi「{k}」の読みがひらがなでない: {v}")
            if not re.fullmatch(r"[一-龥々]+", k):
                out.append(f"yomi の語「{k}」に仮名が混ざっている（TTS が拒むので送られない ＝ 固定されていない）。本文をひらがなに")
        if not self.takeaway:
            out.append("takeaway が空")
        return out

    def warnings(self) -> list[str]:
        """止めない。書き手（Fable）が読んで決める材料（オーナー 09/06「点って言ってるとこ」「漢字の読み変なのいっぱい」）。"""
        out = []
        for i, s in enumerate(self.segments, 1):
            # 「点」と小数は problems() の TEN が止める（hourly 09/06 14:4x）。ここは読みの側だけ
            if BARE_YEAR.search(s.say):
                out.append(f"コマ{i} 裸の「年」＋数字（「年に」も同じ）: TTS が「とし」と読む"
                           f"（実測 09/05・09/06・**09/09 は Neural2-D で 6コマ**）。「1年で」「1年に」「毎年」に")
            # **画面の側**（2026-09-09 06:5x・optimizer・Opus）。ここは読みの話ではありません ——
            # `show`/`sub` は声に出ないので TTS も hear も当たらず、**声だけ直して画面が残った**回を
            # 誰も見ていませんでした。実測 09/10 の本: 03:2x の直しが `say` と `sub` にしか当たらず、
            # コマ3・5・9 の `show` が「年に320万円」のまま ＝ **画面と声が別の言い方**（§3 の 7）。
            # 門（上）は `s.say` しか読まないので、この食い違いは lint を `[?]` 0 で通ります。
            # 「年に」を目印に使うのは、それが **声の側の書き換えが済んだ印**だからで、画面の誤りではない。
            for field, name in ((s.show, "show"), (s.sub, "sub")):
                if SCREEN_NEN_NI.search(field) and not BARE_YEAR.search(s.say):
                    out.append(f"コマ{i} 画面（{name}）だけに「年に」＋数字 が残っている: "
                               f"声は書き換え済みで画面が古い（§3 の 7・字幕は声と同じ文）。声に合わせる")
            m = YOMI_IGNORED.search(s.say)
            if m:
                out.append(f"コマ{i} 「{m.group()}」は yomi を TTS が無視する語（実測 09/06）。金額・じゅうぶん のように語を変える")
            for sent in long_sentences(s.say):
                out.append(f"コマ{i} の 1文 が {len(sent)}字（§3 の 6: {MAX_SENTENCE}字以内。長い文は hear が末尾で鳴る）: {sent[:18]}…")
        # **「なぜそうなるのか」のコマが 0 の本**（2026-09-11 20:0x・hourly・Opus。オーナー 19:5x）。
        # 止めない —— 題材によっては仕組みが結論そのもの（説明する所が無い）ことも在るので、
        # **書き手が「この本には要らない」と決めたなら、その理由をその本の節に書くこと**（§3 の 7-b）。
        if not any(s.tag == "しくみ" for s in self.segments):
            out.append("「しくみ」の札のコマが 0（＝ 計算結果だけの本になっていないか）。"
                       "オーナー 09/11 19:5x「制度の仕組みは説明した方が良くない？計算結果だけ出されても"
                       "何でそうなるの？ってなる」。要らないと決めたら、その理由をその本の節に書くこと")
        # **札と声の言い回しの対応**（`TAG_OPENERS` の註）。止めない
        for i, s in enumerate(self.segments, 1):
            opener = TAG_OPENERS.get(s.tag)
            if opener and opener not in _SENT_END.split(s.say)[0]:
                out.append(f"コマ{i} の札「{s.tag}」に、声の口「{opener}」が 1文目に在りません"
                           f"（§3 の 7-b: 前提「たとえば、」・決まり「決まりでは、」・計算「計算すると、」で文を始める）"
                           f": {s.say[:18]}…")
        # **notes の引き写しが古い**（`stale_note_quotes` の註）。止めない
        out += stale_note_quotes(self.notes, [x.say for x in self.segments])
        return out


def long_sentences(say: str) -> list[str]:
    """say を 。？！ で切り、MAX_SENTENCE を越える文だけ返す（警告の材料。止めない）。"""
    return [x for x in _SENT_END.split(say) if len(x.strip()) > MAX_SENTENCE]


def sentence_lens(say: str) -> list[int]:
    """say を 。？！ で切った文の字数（頭から順）。

    **`hear` が末尾／頭で鳴ったコマに並べて印字します**（§15 の申し送り (1)・2026-09-11 22:4x）——
    切り落としが見ているのは**コマの長さではなく文の長さ**だから
    （実測 09/11 11:1x: 55字/文[21,34] は欠け、56字/文[21,23,12] は通った ＝ コマは 1字 長く 0.2秒 長いのに通った。
    頭の側も同じで、43字 のまま第1文 27 → 20字 で 11/12 → 12/12）。
    **`long_sentences` と同じ切り方**（`_SENT_END`）なので、`lint` の `[?]` と数が食い違いません。"""
    return [len(x.strip()) for x in _SENT_END.split(say) if x.strip()]


def norm_id(vid: str) -> str:
    """道で呼ばれた `id` を **id に戻す**（2026-09-12 02:1x・hourly・Opus）。

    `path_for` は 2026-09-06 から**ファイルの道をそのまま通し**ますが、`cli` の側は
    `a.id` を**そのあとも id として使い続けます** —— `image_for(a.id)`・`workdir(a.id)`・
    `render.built_sig(a.id)`・`ledger(..., a.id)`・`f"{a.id}-bg"`。
    ＝ **道で呼ぶと、台本は読めるのに その本の付属物が 1つも見つかりません。**

    **この回に実物を踏んだ**: `build data/studio/scripts/2026-09-13-….json` が
    **絵が在るのに「背景: 無し（単色）」で焼き**、台帳へ
    `{"id": "data/studio/scripts/2026-09-13-….json", "image": false}` を書きました。
    印字も返り値も **0 でなく正常** ＝ §4 (0-b) の族（「出ていないのを 0件 と読む」）の
    **5つ目の型: 道で呼ぶと、黙って別の物を作る**。
    しかも台帳の id が道なので、`trend.image_orders` の `restale` からも消え、
    **「焼き直し待ち」の名指しが、焼き直した回に消えません**（＝ 次の回も同じ所を踏みます）。

    **直す場所をここにした理由**: `cli` の `a.id` は **20か所** で使われており、
    呼ぶ側を1つずつ直すと**次に足した1か所が同じ穴を開けます**。
    入口で 1度 だけ正規化すれば、`path_for` の「道でも通す」（09/06 の決め）も残ります。

    **覆る条件**: (1) 台本のファイル名（stem）と中身の `id` が食い違う本が出たら、
    ここは stem ではなく**中身の `id`** を読むこと（`save()` は `path_for(s.id)` へ書くので、
    いまは必ず一致します）。(2) `id` を取るコマンドが**台本を持たない物**へ広がったら
    （例: video_id で呼ぶ口）、正規化の入口を そのコマンドの外へ出すこと。
    """
    vid = str(vid)
    return Path(vid).stem if (vid.endswith(".json") or "/" in vid) else vid


def path_for(vid: str) -> Path:
    """id → 台本のファイル。**ファイルの道をそのまま渡されても通す**（2026-09-06）。

    実測: `python -m studio.cli lint data/studio/scripts/<id>.json` が
    `data/studio/scripts/data/studio/scripts/<id>.json.json` を開こうとして落ちた。
    id で呼ぶのが正だが、道で呼んだ回を落とす理由は無い。
    """
    vid = str(vid)
    if vid.endswith(".json") or "/" in vid:
        return Path(vid)
    return SCRIPTS / f"{vid}.json"


def load(vid: str) -> Script:
    return Script.model_validate_json(path_for(vid).read_text(encoding="utf-8"))


def save(s: Script) -> Path:
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    p = path_for(s.id)
    p.write_text(json.dumps(s.model_dump(), ensure_ascii=False, indent=1), encoding="utf-8")
    return p
