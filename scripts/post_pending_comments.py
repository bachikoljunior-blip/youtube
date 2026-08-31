#!/usr/bin/env python3
"""公開済みの動画で、最初のコメントがまだ付いていないものに付ける。

    python scripts/post_pending_comments.py [--dry-run]

なぜ要るか。**予約公開した動画のコメントは、公開されるまで書き込めない。**
private の動画に commentThreads().insert すると 403 が返る。だから投稿時には
付けられず、公開時刻をまたいで誰かが付けに来る必要がある。

これまではセッションが起きているときに手で付けていた。つまり**公開時刻に
セッションが生きていなければ、そのまま付かない。** 人の作業（あるいは
たまたま起きていること）に依存する設計になっていた。

最初のコメントは固定表示されて要点の要約になるので、維持率と理解に効く。
落とすのはもったいないが、それ以上に「人がいないと止まる」のが問題。

冪等。すでに自分のコメントが付いている動画は飛ばすので、何度でも回してよい。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import history  # noqa: E402
from src.uploader import _service  # noqa: E402

# 動画に出してはいけない語。オーナーの指示でリポジトリの存在を伏せている。
FORBIDDEN = ("github", "GitHub", "リポジトリ", "コードを公開", "ソースコード")


def _first_comments() -> dict[str, str]:
    """build/<テーマID>/script.json から {テーマID: 最初のコメント} を集める。"""
    out = {}
    for path in sorted(Path("build").glob("*/script.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        comment = (data.get("first_comment") or "").strip()
        if comment:
            out[path.parent.name] = comment
    return out


def main(dry: bool = False) -> int:
    comments = _first_comments()
    if not comments:
        print("build/ に最初のコメントが見つかりません")
        return 0

    youtube = _service()
    channel = youtube.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    items = youtube.playlistItems().list(
        part="contentDetails", playlistId=uploads, maxResults=50
    ).execute().get("items", [])
    ids = [i["contentDetails"]["videoId"] for i in items]
    if not ids:
        print("動画がありません")
        return 0

    videos = youtube.videos().list(part="snippet,status", id=",".join(ids)).execute()["items"]

    posted = 0
    for video in videos:
        if video["status"]["privacyStatus"] != "public":
            continue

        description = video["snippet"].get("description", "")
        topic = next((t for t in comments if history.marker(t) in description), None)
        if not topic:
            continue

        # すでに付いていれば飛ばす。冪等にしておかないと二重投稿する。
        threads = youtube.commentThreads().list(
            part="snippet", videoId=video["id"], maxResults=50, textFormat="plainText"
        ).execute().get("items", [])
        mine = [
            t for t in threads
            if t["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {}).get("value")
            == video["snippet"]["channelId"]
        ]
        if mine:
            continue

        comment = comments[topic]
        bad = next((w for w in FORBIDDEN if w in comment), None)
        if bad:
            print(f"[skip] {video['id']} のコメントに「{bad}」が入っています")
            continue

        print(f"[post] {video['id']} ({topic}) {comment[:40]}…")
        if dry:
            continue
        # **50単位**。残しているのは「前提を閉じる読み」で、`eta.py` が
        # 毎回「軌跡の腕が動くのは前提を1件 閉じたときだけ」と言う操作です。
        # **この道具はやり残しを拾う側なので、次の窓で同じ1行が拾います。**
        from src import upload_cap                      # noqa: PLC0415

        hold = upload_cap.reserve_hold()
        if hold:
            print(f"[post] {hold}")
            print(f"[post] **ここで止めます**（付けた {posted}件）。"
                  " 窓が変わった回に同じ1行で続きから拾えます。")
            break
        youtube.commentThreads().insert(
            part="snippet",
            body={"snippet": {"videoId": video["id"], "topLevelComment": {
                "snippet": {"textOriginal": comment}}}},
        ).execute()
        # **通ったら数えること**（2026-08-28）。50単位。
        from src import upload_cap                      # noqa: PLC0415
        upload_cap.note_quota_ok(detail=f"commentThreads.insert {video['id']}")
        posted += 1

    print(f"{'（確認のみ）' if dry else ''}付けたコメント: {posted}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
