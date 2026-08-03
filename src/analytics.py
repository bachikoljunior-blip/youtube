"""YouTube Analytics の実績を読んで、トピックプールを更新する。

伸びたテーマの周辺を厚くし、伸びなかったテーマから離れる。
これが「広告収益の最大化」に効く唯一の自動ループなので、週1で必ず回す。
"""
from __future__ import annotations

import json
import statistics
from datetime import date, timedelta
from typing import Any

import anthropic
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field

from . import config, state
from .auth import credentials


class TopicIdea(BaseModel):
    id: str = Field(description="英小文字とハイフンだけのID。既存と重複しないもの")
    title_seed: str = Field(description="動画テーマ。全角30文字以内")
    angle: str = Field(description="他と差がつく切り口。全角80文字以内")


class TopicIdeas(BaseModel):
    topics: list[TopicIdea] = Field(description="新しいトピック案を5件")


def fetch_report(days: int = 28) -> list[dict[str, Any]]:
    """直近 N 日の動画別実績。収益は取れれば取る。"""
    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)

    metric_sets = [
        "views,estimatedMinutesWatched,averageViewPercentage,estimatedRevenue",
        "views,estimatedMinutesWatched,averageViewPercentage",
    ]
    for metrics in metric_sets:
        try:
            response = analytics.reports().query(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics=metrics,
                dimensions="video",
                sort="-estimatedMinutesWatched",
                maxResults=50,
            ).execute()
        except HttpError as exc:
            # 収益メトリクスは YPP 承認前だと弾かれる。落として再挑戦。
            print(f"[analytics] {metrics} は取得できず: {exc.resp.status}")
            continue

        headers = [h["name"] for h in response.get("columnHeaders", [])]
        return [dict(zip(headers, row)) for row in response.get("rows", [])]

    return []


def _summarize(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """視聴時間の中央値を基準に、勝ち筋と負け筋のタイトルを分ける。"""
    history = {entry["video_id"]: entry for entry in state.load()}
    scored = []
    for row in rows:
        entry = history.get(row.get("video"))
        if not entry:
            continue
        scored.append((row.get("estimatedMinutesWatched", 0), entry["title"], row))

    if len(scored) < 4:
        return [], []

    median = statistics.median(v for v, _, _ in scored)
    winners = [title for value, title, _ in scored if value >= median * 1.3]
    losers = [title for value, title, _ in scored if value <= median * 0.6]
    return winners[:8], losers[:8]


def propose_topics(channel: dict, winners: list[str], losers: list[str], existing: list[str]) -> list[dict]:
    client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"))
    cfg = channel["channel"]

    prompt = f"""YouTubeチャンネルの次の企画を5本考えてください。

# チャンネル
{cfg['name']} — {cfg['niche']}
視聴者: {cfg['audience']}

# 直近28日で伸びた動画
{chr(10).join('- ' + t for t in winners) or '（データなし）'}

# 伸びなかった動画
{chr(10).join('- ' + t for t in losers) or '（データなし）'}

# すでにプールにあるID（重複禁止）
{', '.join(existing)}

伸びたもののパターンを言語化し、その隣接テーマを提案してください。
同じ話の焼き直しは避け、視聴者が検索しそうな実務的な悩みを選んでください。
"""

    from .script_writer import _strict  # スキーマ整形は同じルールを使う

    with client.messages.stream(
        model=channel["generation"]["model"],
        max_tokens=8000,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": _strict(TopicIdeas.model_json_schema())},
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        print("[analytics] 企画生成が停止しました。スキップします。")
        return []

    text = next(b.text for b in message.content if b.type == "text")
    ideas = TopicIdeas.model_validate(json.loads(text))
    # 実績に基づく提案なので、初期スコアを少し高くして先に消化させる
    return [{**idea.model_dump(), "score": 1.4, "used": False} for idea in ideas.topics]


def optimize() -> None:
    channel = config.load_channel()
    pool = config.load_topics()
    existing_ids = [t["id"] for t in pool["topics"]]

    rows = fetch_report()
    print(f"[analytics] {len(rows)} 本ぶんの実績を取得")
    winners, losers = _summarize(rows)
    if winners:
        print(f"[analytics] 伸びた: {winners}")
    if losers:
        print(f"[analytics] 伸びなかった: {losers}")

    # 未消化のトピックが十分あるなら、無理に増やさない
    unused = [t for t in pool["topics"] if not t.get("used")]
    if len(unused) >= 12 and not winners:
        print("[analytics] 未消化トピックが十分あるため追加しません。")
        return

    new_topics = propose_topics(channel, winners, losers, existing_ids)
    added = [t for t in new_topics if t["id"] not in existing_ids]
    if not added:
        print("[analytics] 追加する新トピックはありません。")
        return

    pool["topics"].extend(added)
    config.save_topics(pool)
    print(f"[analytics] {len(added)} 件のトピックを追加しました: {[t['id'] for t in added]}")


if __name__ == "__main__":
    optimize()
