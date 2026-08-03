"""Claude で動画台本とメタデータを生成する。

出力は JSON スキーマで固定しているので、後工程はパース失敗を心配しなくていい。
"""
from __future__ import annotations

import json
from typing import Any

import anthropic
from pydantic import BaseModel, Field

from . import config

# 日本語 TTS の実測。speaking_rate=1.0 でおよそこのくらい進む。
CHARS_PER_MINUTE = 360.0


class Segment(BaseModel):
    narration: str = Field(description="読み上げる文章。1〜3文。話し言葉。記号や箇条書き記号は使わない")
    on_screen: str = Field(description="画面に大きく出す要約テキスト。18文字以内。数字を優先して残す")
    visual_query: str = Field(description="背景映像を探すための英語の検索語。2〜4語。例: 'japanese office desk'")


class Chapter(BaseModel):
    segment_index: int = Field(description="このチャプターが始まるセグメントの0始まりの番号")
    label: str = Field(description="チャプター名。全角14文字以内")


class VideoScript(BaseModel):
    title: str = Field(description="採用するタイトル。全角32文字以内。数字と具体名を入れる。煽らない")
    title_alternatives: list[str] = Field(description="A/Bテスト用の別案を2つ")
    description_body: str = Field(description="説明欄の本文。3〜5行の要約＋出典の探し方。URLは書かない")
    tags: list[str] = Field(description="検索タグを10〜15個。日本語中心。1語あたり全角20文字以内")
    thumbnail_line1: str = Field(description="サムネ1行目。全角9文字以内。一番強い数字か結論")
    thumbnail_line2: str = Field(description="サムネ2行目。全角9文字以内")
    segments: list[Segment] = Field(description="本編。冒頭は結論、次に条件、最後に手順の順で並べる")
    chapters: list[Chapter] = Field(description="チャプター4〜7個")


SYSTEM = """あなたは日本語YouTubeの解説動画の構成作家です。

守ること:
- 視聴維持率がすべて。冒頭の1セグメント目で「この動画で分かる結論」を数字ごと言い切る。前置き・自己紹介・チャンネル登録の依頼は書かない。
- 一般論を書かない。金額・割合・期限・書類名など、検証可能な具体を必ず入れる。
- 制度や数字には必ず適用条件を添える。「年収600万・扶養なしの場合」のように。
- 断定できないことは「〜の場合が多い」と書く。絶対・確実・必ず儲かる、は使わない。
- 読み上げ用なので、括弧書き・箇条書き記号・URL・英数字の羅列は narration に入れない。数字は「およそ48万円」のように読める形で書く。
- 各セグメントの narration は 60〜160文字。短く切ってテンポを作る。
- 最後のセグメントは「明日やること」を3つ、手順として言う。

タイトル:
- 検索されそうな語を前半に置く。クリックベイトにしない。
- 全角32文字以内。「」や【】は使わない。
"""

USER_TEMPLATE = """次の条件で動画1本ぶんの台本を作ってください。

# チャンネル
名前: {channel_name}
扱う領域: {niche}
想定視聴者: {audience}

# 書き手の人格
{persona}

# 扱わないこと
{avoid}

# 今回のテーマ
{topic_title}
切り口: {topic_angle}

# 尺
narration の合計を {min_chars}〜{max_chars} 文字にしてください。
これは読み上げて約{target_minutes}分になる分量です。セグメント数は {min_segments}〜{max_segments} 個が目安。
文字数が足りないと動画が短くなり収益化条件を満たさないので、必ず下限を超えてください。
"""


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Structured Outputs の要求に合わせて object を閉じ、全プロパティを required にする。"""
    if schema.get("type") == "object" and "properties" in schema:
        schema["additionalProperties"] = False
        schema["required"] = list(schema["properties"].keys())
    for key in ("properties", "$defs"):
        for child in schema.get(key, {}).values():
            _strict(child)
    if "items" in schema:
        _strict(schema["items"])
    return schema


def _total_chars(script: VideoScript) -> int:
    return sum(len(s.narration) for s in script.segments)


def generate(channel: dict, topic: dict) -> VideoScript:
    """台本を1本生成する。尺が足りなければ一度だけ書き足させる。"""
    cfg = channel["channel"]
    vid = channel["video"]
    gen = channel["generation"]

    target = float(vid["target_minutes"])
    min_chars = int(float(vid["min_minutes"]) * CHARS_PER_MINUTE)
    max_chars = int((target + 1.5) * CHARS_PER_MINUTE)

    prompt = USER_TEMPLATE.format(
        channel_name=cfg["name"],
        niche=cfg["niche"],
        audience=cfg["audience"],
        persona=cfg["persona"].strip(),
        avoid="\n".join(f"- {a}" for a in cfg["avoid"]),
        topic_title=topic["title_seed"],
        topic_angle=topic["angle"],
        min_chars=min_chars,
        max_chars=max_chars,
        target_minutes=target,
        min_segments=int(min_chars / 130),
        max_segments=int(max_chars / 80),
    )

    client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"))
    schema = _strict(VideoScript.model_json_schema())
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    for attempt in range(2):
        with client.messages.stream(
            model=gen["model"],
            max_tokens=32000,
            system=SYSTEM,
            output_config={
                "effort": gen.get("effort", "high"),
                "format": {"type": "json_schema", "schema": schema},
            },
            messages=messages,
        ) as stream:
            message = stream.get_final_message()

        if message.stop_reason == "refusal":
            raise RuntimeError(
                "台本生成が安全性の判定で停止しました。トピックの切り口を見直してください: "
                f"{getattr(message.stop_details, 'category', None)}"
            )

        text = next(b.text for b in message.content if b.type == "text")
        script = VideoScript.model_validate(json.loads(text))
        chars = _total_chars(script)
        print(f"[script] 試行{attempt + 1}: {len(script.segments)}セグメント / {chars}文字")

        if chars >= min_chars or attempt == 1:
            if chars < min_chars:
                print(f"[script] 警告: 目標{min_chars}文字に届きませんでした（{chars}文字）")
            return script

        # 短すぎた場合だけ、同じ会話を続けて書き足させる
        messages += [
            {"role": "assistant", "content": text},
            {
                "role": "user",
                "content": (
                    f"narration の合計が{chars}文字しかなく、目標の{min_chars}文字に届いていません。"
                    "内容を薄めずに、具体例・数値・手順・よくある間違いを足してセグメントを増やし、"
                    "同じJSON形式で全体を出し直してください。"
                ),
            },
        ]

    raise RuntimeError("unreachable")
