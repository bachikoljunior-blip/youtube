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


def _row(v: dict) -> dict:
    st = v["status"]
    return {"id": v["id"], "title": v["snippet"]["title"], "privacy": st["privacyStatus"],
            "publish_at": st.get("publishAt"), "published_at": v["snippet"]["publishedAt"],
            "duration": v.get("contentDetails", {}).get("duration", ""),
            "views": int(v.get("statistics", {}).get("viewCount", 0)),
            "likes": int(v.get("statistics", {}).get("likeCount", 0))}


_ALL: list[dict] | None = None


def all_videos(refresh: bool = False) -> list[dict]:
    """**チャンネルの全本**（新しく上げた順・ID で重複を落とす）。同じ回では1度だけ引く。

    755本 で playlistItems 16 + videos.list 16 ＝ **約 32単位**（日枠 10,000）。

    **なぜ「上げた順の先頭 N本」では駄目か**（2026-09-07 16:4x・optimizer・Opus が実測）:
    uploads の並びは**上げた順**で、**公開した順ではない**。08/16〜08/19 に上げて private のまま
    置いてあった旧作りの本に、あとから publishAt が付いて公開されると、その本は
    uploads の 690番目あたりに居るので `recent_videos(60)` には**永久に入らない**。
    実測: 09/05 に 5本・09/06 に 8本・09/07 に 1本（`PhQ2KvuQASQ` 09:00・73回）が
    こうして公開されていたのに、`status` の「きょうの枠」にも「直近 公開 10本」にも
    出ず、`measure` は 1行も台帳に書いていなかった（6本 とも measured 0行）。
    §6 の `scheduled_all()` は 09/06 02:1x に同じ穴を private 側だけ塞いだもので、
    **public 側は空いたままだった。**
    """
    global _ALL
    if _ALL is not None and not refresh:
        return _ALL
    up = channel()["uploads"]
    ids, seen, tok = [], set(), None
    while True:
        r = svc().playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
        for i in r["items"]:
            vid = i["contentDetails"]["videoId"]
            if vid not in seen:
                seen.add(vid)
                ids.append(vid)
        tok = r.get("nextPageToken")
        if not tok:
            break
    out = []
    for i in range(0, len(ids), 50):
        r = svc().videos().list(part="snippet,status,statistics,contentDetails", id=",".join(ids[i:i + 50])).execute()
        out += [_row(v) for v in r["items"]]
    _ALL = out
    return out


def published(within_h: float | None = None) -> list[dict]:
    """**公開ずみの本を、公開した順（新しい順）に**。`within_h` を渡すと その齢までに絞る。

    「直近 公開 N本」も `measure` も、**上げた順ではなくこの順で選ぶこと**（上の註）。
    """
    rows = [v for v in all_videos() if v["privacy"] == "public"]
    rows.sort(key=when, reverse=True)
    if within_h is None:
        return rows
    return [v for v in rows if (now_jst() - when(v)).total_seconds() / 3600 <= within_h]


def when(v: dict) -> dt.datetime:
    s = v["publish_at"] or v["published_at"]
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(JST)


def scheduled_all() -> list[dict]:
    """**チャンネルの全本**のうち、publishAt が付いていて まだ public でない本（＝予約）。新しい順。

    上げた順の先頭 N本 だけを見ていると見えない: 実測 2026-09-06 00:01 JST、旧 `ahead_sweep.py` が
    08/16〜08/19 に上げた private の本 8本（uploads の 690番目あたり）に きょうの publishAt を打ち、
    `status` は「きょうの枠: 空」と印字した。→ `all_videos()`（全本・約 32単位・同じ回では1度だけ）。
    """
    return [v for v in all_videos() if v["publish_at"] and v["privacy"] != "public"]


def today_lineup(videos: list[dict] | None = None) -> list[dict]:
    """きょう（JST）に公開ずみ・公開予定の本。**公開ずみも予約も、全本から拾う。**

    2026-09-07 16:4x（optimizer・Opus）に public 側を全本に変えた。それまで公開ずみは
    「上げた順の先頭 60本」から拾っていたので、08月に上げて きょう公開された旧作りの本が
    **1本も見えなかった** —— 実測 09/07 09:00 の `PhQ2KvuQASQ`（73回）は「きょうの枠」に出ず、
    その1時間あとに `schedule` の「1日1本」の門（`cmd_schedule` が この関数で数える）も
    素通りして、きょうは 2本 出ている。`all_videos()` は1度しか引かないので単位は増えない。
    """
    videos = videos if videos is not None else all_videos()
    d = now_jst().date()
    rows = [v for v in videos if v["privacy"] == "public" and when(v).date() == d]
    seen = {v["id"] for v in rows}
    rows += [v for v in scheduled_all() if v["id"] not in seen and when(v).date() == d]
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


def update_meta(video_id: str, title: str, description: str, tags: list[str]) -> None:
    """題・説明欄・tags だけを直す（videos.update 50単位。本は上げ直さない・予約もそのまま）。
    09/07 05:5x（hourly）: 予約ずみの本の説明欄の1文（実の誤り）を、ID を変えずに直すために足した。"""
    svc().videos().update(part="snippet", body={"id": video_id, "snippet": {
        "title": title, "description": description, "tags": [t[:30] for t in tags][:15],
        "categoryId": "27", "defaultLanguage": "ja", "defaultAudioLanguage": "ja"}}).execute()


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
