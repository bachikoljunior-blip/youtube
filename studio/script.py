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
MAX_TOTAL_CHARS = 420   # Chirp3-HD rate 1.15 で約 4.9字/秒 → 90秒 以内（実物の秒数は build が測る）

# 書き手が人間のふりをする言い方（収益化ポリシー: AI が人間の専門家を装って sensitive topic を語る形）
HUMAN_CLAIM = re.compile(r"(私は|わたしは)?(元|現役の)?(税理士|社労士|社会保険労務士|FP|ファイナンシャルプランナー|経理|人事)(として|です|でした|を[0-9０-９]+年)")


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
        if not self.takeaway:
            out.append("takeaway が空")
        return out


def path_for(vid: str) -> Path:
    return SCRIPTS / f"{vid}.json"


def load(vid: str) -> Script:
    return Script.model_validate_json(path_for(vid).read_text(encoding="utf-8"))


def save(s: Script) -> Path:
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    p = path_for(s.id)
    p.write_text(json.dumps(s.model_dump(), ensure_ascii=False, indent=1), encoding="utf-8")
    return p
