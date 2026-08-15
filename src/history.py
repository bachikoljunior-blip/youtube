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


def topic_video_map() -> dict[str, str]:
    """テーマID → 動画ID。**独立評価のスコアを実績に結びつけるのに要る。**

    2026-08-15 に見つけた穴。`data/critique.jsonl` はスコアを **テーマID**
    （`s-zangyo-2`）で積んでいるのに、`critique_record.py --check` が
    突き合わせる Analytics は **動画ID**（`7b2-Z6Jw5DQ`）で来ます。
    `perf.get("s-zangyo-2")` は**必ず None** なので、
    **突き合わせは1件も成立しません。**

    それでも画面には「engaged と突き合わせられたもの 0件 / 必要 6件」と出て、
    続けて「公開直後は Analytics に行が出ません。2〜3日遅れます」と説明されます。
    **待てば埋まるように見えて、構造上いつまでも埋まりません。**

    これが止めていたもの: M13 の較正は「6本たまった時点」で終わる約束で、
    その較正が終わるまで独立評価の門は宙づり、そして
    `docs/CRITIQUE.md` によればその門が **M14（唯一残っている伸ばす手）** を塞ぎます。

    テーマIDは説明欄の `[t:...]` にあるので、**チャンネル側から引き直せます。**
    記録の書き方は変えません（評価は投稿の前にやるので、その時点で動画IDはまだ無い）。
    **突き合わせる側で解決します。**
    """
    return _scan(want_map=True)


def posted_topic_ids() -> set[str]:
    """チャンネルに今ある動画の説明欄から、投稿済みのテーマIDを集める。"""
    return _scan(want_map=False)


def _scan(want_map: bool):
    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    try:
        channels = youtube.channels().list(part="contentDetails", mine=True).execute()
    except HttpError as exc:
        print(f"[history] チャンネルを読めませんでした（全テーマ未使用として続行）: {exc}")
        return {} if want_map else set()

    items = channels.get("items", [])
    if not items:
        return {} if want_map else set()
    uploads = items[0]["contentDetails"]["relatedPlaylists"].get("uploads")
    if not uploads:
        return {} if want_map else set()

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
    mapping: dict[str, str] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        response = youtube.videos().list(part="snippet", id=",".join(chunk)).execute()
        for video in response.get("items", []):
            topics = MARKER_RE.findall(video["snippet"].get("description", ""))
            found.update(topics)
            for topic_id in topics:
                # uploads プレイリストは新しい順。**先に見たほうが新しい**ので、
                # 同じテーマを撮り直していたら新しい動画を残す。
                mapping.setdefault(topic_id, video["id"])

    if want_map:
        print(f"[history] チャンネルの動画 {len(video_ids)}本 / テーマ→動画 {len(mapping)}件")
        return mapping
    print(f"[history] チャンネルの動画 {len(video_ids)}本 / 投稿済みテーマ {len(found)}件")
    return found
