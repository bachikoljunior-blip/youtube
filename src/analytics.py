"""YouTube Analytics の実績を読んで、トピックプールを更新する。

伸びたテーマの周辺を厚くし、伸びなかったテーマから離れる。
これが「広告収益の最大化」に効く唯一の自動ループなので、週1で必ず回す。
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field

from . import config
from .auth import credentials
from .claude_cli import ClaudeCliError, ask


class TopicIdea(BaseModel):
    id: str = Field(description="英小文字とハイフンだけのID。既存と重複しないもの")
    title_seed: str = Field(description="動画テーマ。全角30文字以内")
    angle: str = Field(description="他と差がつく切り口。全角80文字以内")


class TopicIdeas(BaseModel):
    topics: list[TopicIdea] = Field(description="新しいトピック案を5件")


def fetch_traffic(days: int = 28) -> list[dict[str, Any]]:
    """流入経路べつの再生数。**表示されているのかどうかを見る唯一の手段。**

    インプレッションと CTR は YouTube Analytics API では取れない（Studio だけ）。
    実際に metrics="impressions" を投げると Unknown identifier で 400 が返る。
    Studio を開くのはオーナーの作業になり、「人手に依存する計画を立てるな」に反する。

    代わりに流入経路を見る。同じ問い——検索に出ているのか、ショートのフィードに
    乗っているのか、関連動画から来ているのか——には、こちらで答えられる。

    主な値：
      YT_SEARCH        YouTube 検索
      RELATED_VIDEO    関連動画
      SHORTS           ショートのフィード
      BROWSE_FEATURES  ホームや登録チャンネルのフィード
      NO_LINK_OTHER    直接・不明
    """
    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)
    try:
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched",
            dimensions="insightTrafficSourceType",
            sort="-views",
        ).execute()
    except HttpError as exc:
        print(f"[analytics] 流入経路を取得できませんでした: {exc.resp.status}")
        return []
    headers = [h["name"] for h in response.get("columnHeaders", [])]
    return [dict(zip(headers, row)) for row in response.get("rows", [])]


def fetch_subscribers(days: int = 28) -> list[dict[str, Any]]:
    """動画べつの登録者の増減。**律速は登録者なので、ここが本丸。**"""
    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)
    try:
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,subscribersGained,subscribersLost",
            dimensions="video",
            sort="-subscribersGained",
            maxResults=50,
        ).execute()
    except HttpError as exc:
        print(f"[analytics] 登録者の増減を取得できませんでした: {exc.resp.status}")
        return []
    headers = [h["name"] for h in response.get("columnHeaders", [])]
    rows = [dict(zip(headers, row)) for row in response.get("rows", [])]
    for row in rows:
        views = row.get("views") or 0
        row["subscribeRate"] = (row.get("subscribersGained", 0) / views) if views else 0.0
    return rows


def fetch_report(days: int = 28) -> list[dict[str, Any]]:
    """直近 N 日の動画別実績。タイトルは Data API 側から引く。

    分析APIは動画IDしか返さないので、タイトルは別で取る。
    ファイルに投稿履歴を持たないので、ここがタイトルの唯一の出どころになる。
    """
    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)

    try:
        response = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched,averageViewPercentage",
            dimensions="video",
            sort="-views",
            maxResults=50,
        ).execute()
    except HttpError as exc:
        print(f"[analytics] 実績を取得できませんでした: {exc.resp.status}")
        return []

    headers = [h["name"] for h in response.get("columnHeaders", [])]
    rows = [dict(zip(headers, row)) for row in response.get("rows", [])]
    if not rows:
        return []

    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    ids = [r["video"] for r in rows][:50]
    meta = youtube.videos().list(part="snippet", id=",".join(ids)).execute()
    titles = {v["id"]: v["snippet"]["title"] for v in meta.get("items", [])}
    for row in rows:
        row["title"] = titles.get(row["video"], "(取得できず)")
    return rows


def _summarize(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """勝ち筋と負け筋を分ける。

    再生回数ではなく **視聴維持率** で見る。再生回数は単に古い動画ほど積み上がるので、
    「どの切り口が効いたか」を測る物差しにならない。
    """
    scored = [
        (float(r.get("averageViewPercentage") or 0), r.get("title", ""))
        for r in rows
        if r.get("title")
    ]
    if len(scored) < 4:
        return [], []

    median = statistics.median(value for value, _ in scored)
    winners = [title for value, title in scored if value >= median * 1.15]
    losers = [title for value, title in scored if value <= median * 0.8]
    return winners[:8], losers[:8]


def propose_topics(channel: dict, winners: list[str], losers: list[str], existing: list[str]) -> list[dict]:
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

    try:
        ideas, _ = ask(TopicIdeas, prompt, model=channel["generation"]["model"])
    except ClaudeCliError as exc:
        print(f"[analytics] 企画生成に失敗しました。今週はスキップします: {exc}")
        return []

    # 実績に基づく提案なので、初期スコアを少し高くして先に消化させる
    return [{**idea.model_dump(), "score": 1.4} for idea in ideas.topics]


def optimize(posted: set[str] | None = None) -> None:
    from .history import posted_topic_ids

    channel = config.load_channel()
    pool = config.load_topics()
    existing_ids = [t["id"] for t in pool["topics"]]
    if posted is None:
        posted = posted_topic_ids()

    rows = fetch_report()
    print(f"[analytics] {len(rows)} 本ぶんの実績を取得")
    winners, losers = _summarize(rows)
    if winners:
        print(f"[analytics] 維持率が高い: {winners}")
    if losers:
        print(f"[analytics] 維持率が低い: {losers}")

    # 未消化のトピックが十分あるなら、無理に増やさない
    unused = [t for t in pool["topics"] if t["id"] not in posted]
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
