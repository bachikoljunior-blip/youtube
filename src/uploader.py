"""YouTube Data API v3 へのアップロード。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from .auth import credentials

JST = timezone(timedelta(hours=9))
RETRYABLE = {500, 502, 503, 504}


def next_publish_at(hour_jst: int, minute_jst: int) -> str:
    """次に来る指定時刻（JST）を RFC3339(UTC) で返す。"""
    now = datetime.now(JST)
    target = now.replace(hour=hour_jst, minute=minute_jst, second=0, microsecond=0)
    if target <= now + timedelta(minutes=20):
        target += timedelta(days=1)
    return target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _service():
    return build("youtube", "v3", credentials=credentials(), cache_discovery=False)


def upload(
    video_path: Path,
    thumbnail_path: Path,
    title: str,
    description: str,
    tags: list[str],
    publish_cfg: dict,
) -> str:
    youtube = _service()

    visibility = publish_cfg.get("visibility", "private")
    status: dict = {
        "privacyStatus": visibility,
        "selfDeclaredMadeForKids": bool(publish_cfg.get("made_for_kids", False)),
        "license": "youtube",
        "embeddable": True,
    }
    # private のときだけ予約公開できる。public 指定なら即時公開。
    if visibility == "private":
        status["publishAt"] = next_publish_at(
            int(publish_cfg.get("publish_hour_jst", 19)),
            int(publish_cfg.get("publish_minute_jst", 0)),
        )

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": [t[:30] for t in tags][:15],
            "categoryId": str(publish_cfg.get("category_id", "27")),
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": status,
    }

    media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    attempt = 0
    while response is None:
        try:
            progress, response = request.next_chunk()
            if progress:
                print(f"[upload] {int(progress.progress() * 100)}%")
        except HttpError as exc:
            if exc.resp.status in RETRYABLE and attempt < 5:
                wait = 2 ** attempt
                attempt += 1
                print(f"[upload] {exc.resp.status} のため {wait}s 後に再試行")
                time.sleep(wait)
                continue
            raise

    video_id = response["id"]
    print(f"[upload] 完了: https://youtu.be/{video_id}")

    if thumbnail_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))
            ).execute()
            print("[upload] サムネイル設定完了")
        except HttpError as exc:
            # チャンネル未確認だとサムネ設定だけ失敗する。動画自体は上がっているので続行。
            print(f"[upload] サムネイル設定に失敗（チャンネルの電話番号確認が必要かも）: {exc}")

    return video_id
