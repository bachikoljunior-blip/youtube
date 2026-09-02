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

## **コメントの置き場は `build/` ではありません**（2026-09-03 04:xx に踏んだ）

この道具は 2026-09-03 まで `build/<テーマID>/script.json` だけを読んでいました。
**`build/` は `.gitignore` に在り、まっさらなコンテナには1つも無い** ——
`ls build` → `No such file or directory`。＝ この道具は、サブの回から撃つと
**必ず「build/ に最初のコメントが見つかりません」で 0本** でした。

実測 `data/api_calls.jsonl`（08/31 から 7,205行）: `commentThreads` **0件**。
規則5（下書きで上げ、当日に予約）の下では**全部の本が private で上がる**ので、
`uploader._post_actions` の insert は毎本 403 で落ち、拾い直しはこの道具だけ。
**その道具が 0本 なので、09/01 から出た本に最初のコメントは1本も付いていません。**

申し送りは 6周 続けて「16:00 JST 以降の回: `post_pending_comments.py`」と
運び（`retro.py` の持ち越し・実物に当たった回 0）、**撃たれても 0本 でした。**

正本は **`data/critique_queue/<動画ID>.script.json`**（`critique_queue.stash()` が
`build/<題材>/script.json` を動画ID で控えに写す・`first_comment` を持つ）。
こちらは repo に在り、動画ID が鍵なので**説明欄の印で当てにいく必要もありません**
（`videos.list` は ID 指定・1単位/50本）。`build/` は残してありますが、控えの後ろです。

## **撃つのは回ではなく `scripts/ahead_sweep.py`**（同じ日に配線した）

`ahead_sweep.comment_pending()` が、きょうの1本を置いてサムネイルを押した後に
この `main()` を呼びます（`run_marker.py --write` / `next_round.py` の `kick()` から
20分ごと・背景）。**回が「16:00 以降に撃つ」と覚えておく必要はもうありません**
—— 覚えておく形が 6周 続けて 0本 だったので、機械へ移しました。

代金: 控えに未処理の本が無ければ **0単位**（API を呼ばない）。在れば
`videos.list` 1単位 ＋ public の本ごとに `commentThreads.list` 1単位 ＋ 付ける本に 50単位。
付けたら `critique_queue.mark_first_comment_posted()` で印を消すので、二度と数えません。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import critique_queue  # noqa: E402
from src import history  # noqa: E402

# 動画に出してはいけない語。オーナーの指示でリポジトリの存在を伏せている。
FORBIDDEN = ("github", "GitHub", "リポジトリ", "コードを公開", "ソースコード")


def _first_comments() -> dict[str, str]:
    """build/<テーマID>/script.json から {テーマID: 最初のコメント} を集める（古い道）。"""
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


def pending_from_stash() -> dict[str, str]:
    """{動画ID: 最初のコメント}。**API 0単位。** 印（`first_comment_posted`）が付いた本は出ない。"""
    return {r["video_id"]: r["comment"] for r in critique_queue.pending_first_comments()}


def _chunks(seq: list[str], n: int = 50):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _mine_exists(youtube, video: dict) -> bool:
    """自分のコメントが既に付いているか（`commentThreads.list`・1単位）。"""
    threads = youtube.commentThreads().list(
        part="snippet", videoId=video["id"], maxResults=50, textFormat="plainText"
    ).execute().get("items", [])
    return any(
        t["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {}).get("value")
        == video["snippet"]["channelId"]
        for t in threads
    )


def _post(youtube, video_id: str, comment: str) -> None:
    youtube.commentThreads().insert(
        part="snippet",
        body={"snippet": {"videoId": video_id, "topLevelComment": {
            "snippet": {"textOriginal": comment[:9000]}}}},
    ).execute()


def main(dry: bool = False, *, service=None, reserve_hold=None, note_ok=None,
         mark=None, stash=None, build=None) -> int:
    """付けた本数を印字して 0 を返す。`service`〜`build` は検査の差し替え口。"""
    stash = pending_from_stash() if stash is None else dict(stash)
    build = _first_comments() if build is None else dict(build)
    if not stash and not build:
        print("付ける相手がありません（控え `data/critique_queue/*.script.json` に未処理の本が無く、"
              "`build/` にも最初のコメントが無い）。API は呼びません")
        return 0
    if mark is None:
        mark = critique_queue.mark_first_comment_posted
    if reserve_hold is None or note_ok is None:
        from src import upload_cap                          # noqa: PLC0415
        reserve_hold = reserve_hold or upload_cap.reserve_hold
        note_ok = note_ok or (lambda detail: upload_cap.note_quota_ok(detail=detail))
    if service is None:
        from src.uploader import _service                   # noqa: PLC0415
        service = _service
    youtube = service()

    # 1. 控えの本は ID で引く（**1単位/50本**）。
    videos: list[dict] = []
    for ids in _chunks(sorted(stash)):
        videos += youtube.videos().list(part="snippet,status", id=",".join(ids)) \
            .execute().get("items", [])
    # 2. `build/` の古い道は、アップロード一覧から説明欄の印で当てる（控えに無い本だけ）。
    if build:
        channel = youtube.channels().list(part="contentDetails", mine=True) \
            .execute()["items"][0]
        uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
        items = youtube.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50
        ).execute().get("items", [])
        ids = [i["contentDetails"]["videoId"] for i in items
               if i["contentDetails"]["videoId"] not in stash]
        for chunk in _chunks(ids):
            videos += youtube.videos().list(part="snippet,status", id=",".join(chunk)) \
                .execute().get("items", [])

    posted = 0
    for video in videos:
        vid = video["id"]
        if video["status"]["privacyStatus"] != "public":
            continue                                   # まだ出ていない。次の回が拾う
        comment = stash.get(vid)
        if comment is None:
            description = video["snippet"].get("description", "")
            topic = next((t for t in build if history.marker(t) in description), None)
            if not topic:
                continue
            comment = build[topic]

        # すでに付いていれば飛ばす。冪等にしておかないと二重投稿する。
        if _mine_exists(youtube, video):
            if vid in stash:
                mark(vid)                              # 二度と数えない（0単位に戻す）
            continue

        bad = next((w for w in FORBIDDEN if w in comment), None)
        if bad:
            print(f"[skip] {vid} のコメントに「{bad}」が入っています")
            continue

        print(f"[post] {vid} {comment[:40]}…")
        if dry:
            continue
        # **50単位**。残しているのは「前提を閉じる読み」で、`eta.py` が
        # 毎回「軌跡の腕が動くのは前提を1件 閉じたときだけ」と言う操作です。
        # **この道具はやり残しを拾う側なので、次の窓で同じ1行が拾います。**
        hold = reserve_hold()
        if hold:
            print(f"[post] {hold}")
            print(f"[post] **ここで止めます**（付けた {posted}件）。"
                  " 窓が変わった回に同じ1行で続きから拾えます。")
            break
        _post(youtube, vid, comment)
        # **通ったら数えること**（2026-08-28）。50単位。
        note_ok(f"commentThreads.insert {vid}")
        if vid in stash:
            mark(vid)
        posted += 1

    print(f"{'（確認のみ）' if dry else ''}付けたコメント: {posted}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
