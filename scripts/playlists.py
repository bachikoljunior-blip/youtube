#!/usr/bin/env python3
"""同じ題材のショートと長尺を、1本の再生リストに並べる（M8 の3つ目の経路）。

    python scripts/playlists.py --dry-run
    python scripts/playlists.py

## なぜ要るか —— **これは「再生を増やす手」ではありません**

詰まりは `WATCH が28日で2`。再生の 99.95% がショートのフィード内で完結し、
**視聴ページに人がいない。** M3（AdSense以外の収益）も M12（推薦面）も、
着手条件をこの数字に置いていて、7回の読みで **+0** です。

M8 は台帳で唯一この詰まりそのものを狙う手で、経路が3つ挙がっていました。

    カード        Data API に無い（Studio 専用＝オーナーの操作が要る）→ 使えない
    固定コメント  投稿はできるが固定が API に無い                    → 使えない
    説明欄        **2026-08-10 に8本へ入れた（`link_longform.py`）**
    最初のコメント **まだ導線が入っていない**
    再生リスト    **これ。まだ実行していなかった**

## 効く経路を、正直に書いておく

**ショートのフィード再生は再生リストを辿りません。** だから
「4,849再生のフィード視聴者が再生リストに流れる」は**起きません。**
`link_longform.py` の冒頭にそう書いてあり、それは正しい。

効くのは**チャンネルページに着いた人**だけです。

    YT_CHANNEL   直近7日で **9再生**（＝28日で約36）
    WATCH        28日で **2**

チャンネルページに来た36に対して視聴ページが2、という比です。
**再生リストの1本目を長尺にしておくと、そこを開いた再生は視聴ページで起きます。**
36 のうち3割が動けば約11で、M3・M12 の着手条件「WATCH が2桁」に届きます。

**上限は小さい。** これは「月に何万再生」を作る手ではなく、
**止まっている門を1つ開けるための手**です。掛け算した上でそう言っています。

## `videosAddedToPlaylists` の +0.65 を根拠にしないこと

M8 の項がこの相関を根拠に挙げていますが、**別のものです。**
あの指標は**視聴者が自分の再生リストに入れた回数**で、
**こちらがチャンネルの再生リストに入れても1も増えません。**
根拠は上の YT_CHANNEL → WATCH の比だけです。

## この変更は、自分の計器を壊しうる

**WATCH を2桁にすること自体が目的化する危険があります。**
M3・M12 の「WATCH が2桁」は「視聴ページに人がいる」の代理指標で、
**再生リストという構造の変更だけでも動きます。**
だから `docs/MEANS.md` 側の着手条件に「流入元」を足しました。
**数字が動いたら、必ず `insightTrafficSourceType` を見てから着手すること。**

## 並べ方

**1本目を長尺にします。** 再生リストを開いた再生が視聴ページで起き、
かつ長尺は1再生113秒なので、収益化の門の 4,000時間 側にも数えます
（ショートの視聴時間はあちらに数えません）。

## 冪等

すでにある再生リストは作り直しません。入っている動画は飛ばします。
何度でも回してよい。
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402

from src import config  # noqa: E402
from src.uploader import _service  # noqa: E402

PAIRS = config.ROOT / "config" / "pairs.yaml"

# **数字を書かないこと。** 説明欄と同じ規則。裏の取れない数字を置かない。
# **このリポジトリの存在も出さないこと。**
DESC = (
    "同じ題材を、短い尺と長い尺の両方で計算した回をまとめています。\n"
    "前提と計算式は、それぞれの動画の画面と説明欄に出しています。"
)


def _reserve_hold() -> str | None:
    """**計測のぶんを残す門**（`src/upload_cap.reserve_hold`）。

    ここは1回で再生リストと項目を何十件も作りうる口です（各 50単位）。
    残しているのは「前提を閉じる読み」で、`eta.py` が毎回
    「軌跡の腕が動くのは前提を1件 閉じたときだけ」と言う操作です。
    **やり残しは消えません** —— 同じ1行が次の窓で拾います。
    """
    try:
        from src import upload_cap                      # noqa: PLC0415

        return upload_cap.reserve_hold()
    except Exception:                                   # noqa: BLE001
        return None       # 読めないなら止めない（推測で止めない）


def _note_quota_ok(detail: str) -> None:
    """**通った書き込みを数える**（2026-08-28）。

    `src/upload_cap.reserve_hold()` は `spent` を読んで止めます。
    その `spent` を作るのは `note_quota_ok` だけなので、
    **数えない口から出た単位は、門にとって存在しません。**
    ここは1回で再生リストと項目を何十件も作りうる口です（各 50単位）。
    """
    try:
        from src import upload_cap                      # noqa: PLC0415

        upload_cap.note_quota_ok(detail=detail)
    except Exception:                                   # noqa: BLE001
        pass          # 数えられないことを理由に、書き込みを失敗にしない


def _pairs() -> dict[str, str]:
    data = yaml.safe_load(PAIRS.read_text(encoding="utf-8")) or {}
    return data.get("pairs") or {}


def _uploads(y) -> list[str]:
    ch = y.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        r = y.playlistItems().list(part="contentDetails", playlistId=up,
                                   maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    return ids


def _snippets(y, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        for it in y.videos().list(part="snippet",
                                  id=",".join(ids[i:i + 50])).execute()["items"]:
            out[it["id"]] = it["snippet"]
    return out


def _retry(call, tries: int = 5):
    """`playlistItems.insert` は作りたての再生リストに対して 409 を返します。

    2026-08-11 に踏みました。`SERVICE_UNAVAILABLE / The operation was aborted`
    で、**中身の問題ではなく伝播待ちです。** 少し待てば通ります。
    落とすと途中まで入った再生リストが残り、次の回が拾い直すことになります。
    """
    for i in range(tries):
        try:
            return call().execute()
        except HttpError as e:
            if e.resp.status not in (409, 500, 503) or i == tries - 1:
                raise
            time.sleep(2 ** i)


def _mine(y) -> dict[str, str]:
    """既にある再生リスト。題 → ID。"""
    out, tok = {}, None
    while True:
        r = y.playlists().list(part="snippet", mine=True,
                               maxResults=50, pageToken=tok).execute()
        for it in r["items"]:
            out[it["snippet"]["title"]] = it["id"]
        tok = r.get("nextPageToken")
        if not tok:
            break
    return out


def _items(y, playlist_id: str) -> list[str]:
    """中身の動画ID。

    **作りたてを引くと 404 が返ります**（2026-08-11 に踏んだ）。
    `playlists.insert` は ID を返しますが、その ID で `playlistItems.list` が
    引けるようになるまで遅れがあり、**「無い」と区別がつきません。**
    作った直後は空だと分かっているので、そもそも引かないこと（下の呼び出し側）。
    保険としてここでも 404 は空として扱います。
    """
    out, tok = [], None
    while True:
        try:
            r = y.playlistItems().list(part="contentDetails", playlistId=playlist_id,
                                       maxResults=50, pageToken=tok).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return out
            raise
        out += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    pairs = _pairs()
    y = _service()
    ids = _uploads(y)
    snips = _snippets(y, ids)

    # 長尺ID → そこに紐づくショートID。**1本目が長尺**になるよう順に積む。
    groups: dict[str, list[str]] = {}
    for vid, sn in snips.items():
        m = re.search(r"\[t:([^\]]+)\]", sn.get("description", ""))
        if not m or m.group(1) not in pairs:
            continue
        target = pairs[m.group(1)]
        if target == vid:                       # 自分自身は入れない
            continue
        if target not in snips:                 # 長尺が見つからない
            print(f"  [!] {vid} の相手 {target} がチャンネルに無い。飛ばします")
            continue
        groups.setdefault(target, []).append(vid)

    existing = _mine(y)
    made = added = skipped = 0

    for long_id, shorts in sorted(groups.items()):
        title = snips[long_id]["title"][:150]
        pid = existing.get(title)
        fresh = pid is None                     # 作りたては空。引かない（_items 参照）
        if pid is None:
            print(f"\n[新] {title}")
            _hold = _reserve_hold()
            if _hold and not args.dry_run:
                print(f"     {_hold}")
                print("     **作りません。**窓が変わった回に同じ1行で作れます。")
                return 1
            if args.dry_run:
                print(f"     1. {long_id}（長尺）")
                for s in shorts:
                    print(f"     +  {s}  {snips[s]['title'][:28]}")
                continue
            pid = y.playlists().insert(part="snippet,status", body={
                "snippet": {"title": title, "description": DESC,
                            "defaultLanguage": "ja"},
                "status": {"privacyStatus": "public"},
            }).execute()["id"]
            _note_quota_ok("playlists.insert")
            made += 1
        else:
            print(f"\n[既] {title}")

        have = [] if fresh else _items(y, pid)
        for vid in [long_id] + shorts:          # **長尺が1本目**
            if vid in have:
                skipped += 1
                continue
            print(f"     + {vid}  {snips[vid]['title'][:28]}")
            if args.dry_run:
                continue
            _hold = _reserve_hold()
            if _hold:
                print(f"     {_hold}")
                print("     **入れません。**窓が変わった回に同じ1行で入ります。")
                return 1
            _retry(lambda: y.playlistItems().insert(part="snippet", body={
                "snippet": {"playlistId": pid, "resourceId": {
                    "kind": "youtube#video", "videoId": vid}},
            }))
            _note_quota_ok(f"playlistItems.insert {vid}")
            added += 1

    print(f"\n再生リスト {made}件を作成 / 動画 {added}件を追加 / "
          f"すでに入っていた {skipped}件"
          + ("（--dry-run なので書き込んでいません）" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
