"""投稿履歴を YouTube 側から復元する。

ファイルに「投稿済み」を書き溜めると、動画を消したときに嘘になる。
消えた動画のテーマがいつまでも使用済みのままになり、新しいランナーでは空になる。
そこで説明欄に [t:<テーマID>] を埋めておき、毎回チャンネルから読み直す。
状態はチャンネルそのものが持ち、こちらは何も覚えない。
"""
from __future__ import annotations

import re

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import credentials

MARKER = "[t:{}]"
MARKER_RE = re.compile(r"\[t:([a-z0-9\-]+)\]")


def marker(topic_id: str) -> str:
    return MARKER.format(topic_id)


def posted_topic_ids() -> set[str]:
    """チャンネルに今ある動画の説明欄から、投稿済みのテーマIDを集める。"""
    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    try:
        channels = youtube.channels().list(part="contentDetails", mine=True).execute()
    except HttpError as exc:
        print(f"[history] チャンネルを読めませんでした（全テーマ未使用として続行）: {exc}")
        return set()

    items = channels.get("items", [])
    if not items:
        return set()
    uploads = items[0]["contentDetails"]["relatedPlaylists"].get("uploads")
    if not uploads:
        return set()

    video_ids: list[str] = []
    page_token = ""
    while len(video_ids) < 200:
        response = youtube.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50,
            pageToken=page_token or None,
        ).execute()
        video_ids += [i["contentDetails"]["videoId"] for i in response.get("items", [])]
        page_token = response.get("nextPageToken", "")
        if not page_token:
            break

    found: set[str] = set()
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        response = youtube.videos().list(part="snippet", id=",".join(chunk)).execute()
        for video in response.get("items", []):
            found.update(MARKER_RE.findall(video["snippet"].get("description", "")))

    print(f"[history] チャンネルの動画 {len(video_ids)}本 / 投稿済みテーマ {len(found)}件")
    return found
