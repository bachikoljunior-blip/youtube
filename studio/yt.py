"""YouTube Data API の最小限。認証は環境変数 3つ（YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN）。

日枠（10,000単位/日・16:00 JST に戻る）: videos.insert 1,600・videos.update 50・thumbnails.set 50・
videos.list 1・playlistItems.list 1。
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .common import JST, env, now_jst

_svc = None


def svc():
    global _svc
    if _svc is None:
        creds = Credentials(token=None, refresh_token=env("YT_REFRESH_TOKEN"),
                            token_uri="https://oauth2.googleapis.com/token",
                            client_id=env("YT_CLIENT_ID"), client_secret=env("YT_CLIENT_SECRET"))
        _svc = build("youtube", "v3", credentials=creds, cache_discovery=False)
    return _svc


def channel() -> dict:
    ch = svc().channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    return {"title": ch["snippet"]["title"], "uploads": ch["contentDetails"]["relatedPlaylists"]["uploads"],
            **{k: int(v) for k, v in ch["statistics"].items() if isinstance(v, str) and v.isdigit()}}


def recent_videos(limit: int = 60) -> list[dict]:
    """新しい順。status（private/public・publishAt）と再生数つき。"""
    up = channel()["uploads"]
    ids, tok = [], None
    while len(ids) < limit:
        r = svc().playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    out = []
    for i in range(0, len(ids), 50):
        r = svc().videos().list(part="snippet,status,statistics,contentDetails", id=",".join(ids[i:i + 50])).execute()
        for v in r["items"]:
            st = v["status"]
            out.append({"id": v["id"], "title": v["snippet"]["title"], "privacy": st["privacyStatus"],
                        "publish_at": st.get("publishAt"), "published_at": v["snippet"]["publishedAt"],
                        "duration": v["contentDetails"]["duration"],
                        "views": int(v["statistics"].get("viewCount", 0)),
                        "likes": int(v["statistics"].get("likeCount", 0))})
    return out


def when(v: dict) -> dt.datetime:
    s = v["publish_at"] or v["published_at"]
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST)


def today_lineup(videos: list[dict] | None = None) -> list[dict]:
    """きょう（JST）に公開ずみ・公開予定の本。"""
    videos = videos if videos is not None else recent_videos()
    d = now_jst().date()
    rows = [v for v in videos if v["privacy"] != "unlisted" and when(v).date() == d
            and (v["privacy"] == "public" or v["publish_at"])]
    return sorted(rows, key=when)


def upload(path: Path, title: str, description: str, tags: list[str], publish_at: dt.datetime | None) -> str:
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "license": "youtube", "embeddable": True}
    if publish_at:
        status["publishAt"] = publish_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"snippet": {"title": title, "description": description, "tags": [t[:30] for t in tags][:15],
                        "categoryId": "27", "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
            "status": status}
    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    req = svc().videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def set_thumbnail(video_id: str, png: Path) -> None:
    svc().thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(png), mimetype="image/png")).execute()


def make_private(video_id: str) -> None:
    """予約を外して private のまま残す（消さない。オーナー「消さなくて良いよ」）。"""
    svc().videos().update(part="status", body={"id": video_id, "status": {
        "privacyStatus": "private", "selfDeclaredMadeForKids": False}}).execute()


def reschedule(video_id: str, publish_at: dt.datetime) -> None:
    svc().videos().update(part="status", body={"id": video_id, "status": {
        "privacyStatus": "private", "selfDeclaredMadeForKids": False,
        "publishAt": publish_at.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}}).execute()


def stats(video_ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(video_ids), 50):
        r = svc().videos().list(part="statistics", id=",".join(video_ids[i:i + 50])).execute()
        for v in r["items"]:
            out[v["id"]] = {k: int(x) for k, x in v["statistics"].items() if str(x).isdigit()}
    return out
