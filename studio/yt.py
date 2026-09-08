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
    ch = svc().channels().list(part="id,snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    return {"id": ch["id"], "title": ch["snippet"]["title"],
            "uploads": ch["contentDetails"]["relatedPlaylists"]["uploads"],
            **{k: int(v) for k, v in ch["statistics"].items() if isinstance(v, str) and v.isdigit()}}


def _row(v: dict) -> dict:
    st = v["status"]
    return {"id": v["id"], "title": v["snippet"]["title"], "privacy": st["privacyStatus"],
            "publish_at": st.get("publishAt"), "published_at": v["snippet"]["publishedAt"],
            "duration": v.get("contentDetails", {}).get("duration", ""),
            "views": int(v.get("statistics", {}).get("viewCount", 0)),
            "likes": int(v.get("statistics", {}).get("likeCount", 0)),
            # コメント数。2026-09-07 20:4x まで、道具はこれを1度も見ていなかった（`viewer_comments()` の註）。
            "comments": int(v.get("statistics", {}).get("commentCount", 0))}


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


def readiness(video_id: str) -> dict:
    """予約ずみの本が **10:00 に本当に出る状態か**（2026-09-08 02:5x・hourly・Fable）。

    `status` の「きょうの枠」は privacy しか見ていなかった。YouTube 側の処理
    （uploadStatus / processingStatus）が失敗していても private のまま黙って出ないので、
    公開前の周がそれを見られるように 1単位 で引く。
    実測 09/08 02:4x `lQHX9LJ80Sg`: upload=processed・processing=succeeded・失敗 None。

    **2026-09-09 01:5x（hourly・Fable）**: 同じ 1単位 に `snippet` を足し、上がっている題・説明欄・tags も返す。
    処理が通っていても、**上がっている説明欄が台本と違えば古いまま出る**（説明欄だけ直す回 ＝ 09/07 05:5x・09/08 19:1x
    が、予約の後に来たら `update_meta` を撃たない限り誰にも見えない）。突き合わせは `cli.meta_drift`。
    実測 09/09 01:4x `gv1u7n_pCAQ`: 題・説明欄 815字 一致。tags は同じ 9語 だが **YouTube は並べ替えて返す**
    （['65歳', 'シニア', …] の順）ので、比べるときは集合で。
    """
    r = svc().videos().list(part="snippet,status,processingDetails", id=video_id).execute()
    if not r.get("items"):
        return {"upload": "missing", "processing": "missing", "failure": None, "rejection": None, "ok": False,
                "title": None, "description": None, "tags": None}
    v = r["items"][0]
    sn, st, pd = v.get("snippet", {}), v.get("status", {}), v.get("processingDetails", {})
    up, pr = st.get("uploadStatus"), pd.get("processingStatus")
    fail, rej = st.get("failureReason"), st.get("rejectionReason")
    ok = up == "processed" and pr in ("succeeded", None) and not fail and not rej
    return {"upload": up, "processing": pr, "failure": fail, "rejection": rej, "ok": ok,
            "title": sn.get("title"), "description": sn.get("description"), "tags": sn.get("tags")}


def stats(video_ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(video_ids), 50):
        r = svc().videos().list(part="statistics", id=",".join(video_ids[i:i + 50])).execute()
        for v in r["items"]:
            out[v["id"]] = {k: int(x) for k, x in v["statistics"].items() if str(x).isdigit()}
    return out


def viewer_comments(with_moderation: bool = True) -> list[dict]:
    """**視聴者が書いたコメント**を、新しい順に。自分のチャンネルが書いた分は落とす。

    返す各行に `status` が付く: `published` / `heldForReview` / `likelySpam`。

    `commentThreads.list(allThreadsRelatedToChannelId=...)` は**チャンネル全部**を1度に引く
    （1ページ 100件・実測 21件 ＝ **1単位**。本ごとに引くと 227単位 かかる）。

    **なぜ要るか（2026-09-07 20:4x JST・optimizer・Opus が実測して足した）**:
    §1 は「高評価 1,441回の本で 0」、§7 は「likes 合計 0・登録 +0 なら…」と、
    **押された数だけ**で視聴者の反応を測ってきた。**コメントは1度も数えていない。**
    実測（この回に初めて引いた）: チャンネル全部で 21スレッド。うち **18 は自分**
    （旧 `src/` の pipeline が上げる時に自動で置いていた「この計算は毎日1本ずつ出しています」）。
    **視聴者が書いたのは 3件だけ**で、そのうち中身のある1件は:

        2026-08-29 10:08  DSZfGUQ_NyQ（962回）  「ＡＩナレーショングダグダ」（同じ人が2回）

    ＝ **このチャンネルが受け取った唯一の批評は「ナレーションがグダグダ」で、9日間 誰も読んでいなかった。**
    オーナーの 09/07 13:3x「ナレーション前の音声の方が良かった」と**同じ所**を指している
    （別々の人が、別々の日に、声について言っている ＝ n=2 の一致）。
    likes は 0/1 しか動かないので分解能が無いが、コメントは文で来る。**数えること。**

    自分の分を落とすのは `authorChannelId` == 自分のチャンネル ID（表示名では見ない）。
    **保留と迷惑の列も引くこと（2026-09-08 15:0x JST・optimizer・Opus が足した）**:
    `commentThreads.list` は `moderationStatus` を省くと **`published` だけ**を返す。
    上の 20:4x の実装はそれを省いていたので、**保留（`heldForReview`）と迷惑（`likelySpam`）に
    落ちたコメントは、道具からは1件も見えなかった** —— 見えないだけでなく、
    「新着 0件」と**published と同じ顔で**印字されていた。

    これを引いた事の起こり: 09/08 12:39 JST、`lQHX9LJ80Sg`（新しい作りの3本目）に
    視聴者 `@sakimura5257` が **「コメントしたのに消えた」**と書いた（その 70秒前に
    「65歳までに死んだら丸々損したことにならないの？そこが知りたい」＝ このチャンネルが
    受け取った**初めての中身のある質問**）。**道具にはこの問いに答える口が無く**、
    その回は使い捨ての script を書いて API を直に叩くことになった。

    そのとき実測した数（2026-09-08 15:0x JST）:

        published      23スレッド（うち自分 18 ＝ 旧 pipeline の自動コメント）
        heldForReview  **0**
        likelySpam     **0**

    ＝ **消えたコメントは、こちらの保留にも迷惑にも入っていない**（YouTube 側が黙って
    消したか、投稿が届いていない）。**この回については「こちらが握り潰した」ではないと言える。**
    値打ちは、次にこれを訊かれたときに **`comments` を撃つだけで答えが出る**こと。

    API は列ごとに 1単位 ＝ **3単位**（前は 1単位）。1日の枠 10,000 に対して無視できる。

    **覆る条件**: スパムや無関係なコメントが視聴者側に混ざり始めたら、ここで選り分けず
    そのまま出して、読む側（次の回）が判断する（いまは 5件なので選り分けは要らない）。
    保留・迷惑が常に 0 のまま 1か月 続いたら、その2列は引かずに `published` だけへ戻してよい
    （そのときは、この註と `with_moderation` を消すこと）。
    """
    cid = channel()["id"]
    cols = ("published", "heldForReview", "likelySpam") if with_moderation else ("published",)
    out = []
    for col in cols:
        tok = None
        while True:
            try:
                r = svc().commentThreads().list(
                    part="snippet", allThreadsRelatedToChannelId=cid, moderationStatus=col,
                    maxResults=100, pageToken=tok, textFormat="plainText").execute()
            except Exception:  # noqa: BLE001
                # 保留・迷惑の列は権限や仕様で落ちることがある。published を落とさない。
                if col == "published":
                    raise
                break
            for t in r.get("items", []):
                s = t["snippet"]["topLevelComment"]["snippet"]
                if s.get("authorChannelId", {}).get("value") == cid:
                    continue
                out.append({"id": t["id"], "video_id": t["snippet"].get("videoId", ""),
                            "author": s.get("authorDisplayName", ""),
                            "at": s.get("publishedAt", ""), "likes": int(s.get("likeCount", 0)),
                            "status": col,
                            "text": (s.get("textDisplay") or "").strip()})
            tok = r.get("nextPageToken")
            if not tok:
                break
    return sorted(out, key=lambda c: c["at"], reverse=True)


def reply(comment_id: str, text: str) -> str:
    """視聴者のコメント1件に、**手で書いた**返信を1つ付ける（`comments.insert`・**50単位**）。

    2026-09-08 15:1x JST（hourly・Fable）に足した。新しい作りの本 `lQHX9LJ80Sg` に付いた最初の
    視聴者の問い「65歳までに死んだら丸々損したことにならないの？そこが知りたい」に答えるため。
    §7 20:4x の「唯一の批評が 9日間 未読」は読む側の穴だったが、読んだあと**答える口が無い**のも同じ穴。
    旧 `scripts/post_pending_comments.py` の自動投稿（全本に同じ1文を機械で置く ＝ §8 で止めた口）とは違う:
    **文はサブ本人が書き、`cli reply` から1件ずつ・台帳に `replied` を残して**撃つ。背景から呼ぶ口は作らない。
    `comment_id` は `viewer_comments()` の `id`（スレッド ID ＝ 最上位コメントの ID。`parentId` に渡せる）。
    スコープは旧 `src/auth.py` と同じ refresh token（`youtube.force-ssl` 込み）。
    """
    r = svc().comments().insert(part="snippet", body={"snippet": {
        "parentId": comment_id, "textOriginal": text[:9000]}}).execute()
    return r.get("id", "")
