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
MAX_SHOW = 16
MAX_TOTAL_CHARS = 480   # rate 1.2 で実測 5.16字/秒（09/05・458字→88.8秒）→ 93秒。上限は build が測る秒数（MAX_SECONDS）

# 書き手が人間のふりをする言い方（収益化ポリシー: AI が人間の専門家を装って sensitive topic を語る形）
# 裸の「年」＋数字（「年66万円」）。Chirp3-HD は「とし」と読む（実測 09/05・09/06）
BARE_YEAR = re.compile(r"(?<![0-9０-９一-龥])年(?=[0-9０-９])")   # 「毎年10月」は違う（janome が まいとし と読む）
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


class Segment(BaseModel):
    say: str = Field(..., description="声で読む文。ふつうの話し言葉。")
    show: str = Field("", description="画面の大きい字（16字まで）。数字か短い見出し。")
    sub: str = Field("", description="画面の小さい字（任意）。")


class Script(BaseModel):
    id: str
    date: str                       # 公開する日（JST）
    title: str
    takeaway: str                   # 視聴者が言い返せるはずの1文（冷読テストの正解）
    description: str = ""
    tags: list[str] = []
    voice: str = "ja-JP-Chirp3-HD-Charon"
    rate: float = 1.1
    yomi: dict[str, str] = {}       # 読みを固定する語 → ひらがな（TTS と聞き取り検算の両方が使う）
    image_prompt: str = ""          # 背景画像の注文文（GPT Image 2.0。文字を入れない）
    segments: list[Segment]
    notes: str = ""                 # 出典・前提・計算の根拠（人が読む）

    def total_chars(self) -> int:
        return sum(len(s.say) for s in self.segments)

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
        if self.total_chars() > MAX_TOTAL_CHARS:
            out.append(f"合計 {self.total_chars()}字（{MAX_TOTAL_CHARS}まで。60秒に収まらない）")
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
                out.append(f"コマ{i} 裸の「年」＋数字: TTS が「とし」と読む（実測 09/05・09/06）。「1年で」「年に」に")
            m = YOMI_IGNORED.search(s.say)
            if m:
                out.append(f"コマ{i} 「{m.group()}」は yomi を TTS が無視する語（実測 09/06）。金額・じゅうぶん のように語を変える")
        return out


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
