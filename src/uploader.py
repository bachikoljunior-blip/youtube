"""YouTube Data API v3 へのアップロード。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from .auth import credentials, explain

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


def _find_or_create_playlist(youtube, title: str) -> str:
    """同名の再生リストを探し、無ければ作る。"""
    page_token = ""
    while True:
        response = youtube.playlists().list(
            part="snippet", mine=True, maxResults=50, pageToken=page_token or None
        ).execute()
        for item in response.get("items", []):
            if item["snippet"]["title"] == title:
                return item["id"]
        page_token = response.get("nextPageToken", "")
        if not page_token:
            break

    created = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": title, "description": ""},
            "status": {"privacyStatus": "public"},
        },
    ).execute()
    print(f"[upload] 再生リストを新規作成: {title}")
    return created["id"]


def _post_actions(youtube, video_id: str, publish_cfg: dict) -> None:
    """投稿後の付随処理。ここで失敗しても動画は既に上がっているので落とさない。"""
    playlist = (publish_cfg.get("playlist") or "").strip()
    if playlist:
        try:
            playlist_id = _find_or_create_playlist(youtube, playlist)
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
            print(f"[upload] 再生リストに追加: {playlist}")
        except HttpError as exc:
            print(f"[upload] 再生リストへの追加に失敗（動画は投稿済み）: {exc}")

    comment = (publish_cfg.get("first_comment") or "").strip()
    if comment:
        try:
            youtube.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "topLevelComment": {"snippet": {"textOriginal": comment[:9000]}},
                    }
                },
            ).execute()
            # 固定だけは API に無い。Studio で1タップしてもらう。
            print("[upload] 最初のコメントを投稿しました。"
                  "固定はAPIでできないので、Studioで「固定」を押してください:")
            print(f"         https://studio.youtube.com/video/{video_id}/comments")
        except HttpError as exc:
            print(f"[upload] コメント投稿に失敗（動画は投稿済み）: {exc}")


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

    # 分割アップロード。20MB超を一発で送ると、途中で切れたときに
    # 上がったのかどうかも分からなくなる。
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
            raise RuntimeError(explain(exc)) from exc
        except Exception as exc:
            raise RuntimeError(explain(exc)) from exc

    video_id = response["id"]
    print(f"[upload] 完了: https://youtu.be/{video_id}")

    _post_actions(youtube, video_id, publish_cfg)

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
