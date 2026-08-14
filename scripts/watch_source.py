#!/usr/bin/env python3
"""**WATCH（視聴ページ）の再生が、どの手段の成果かを分ける。**

## なぜ要るか（2026-08-15）

`status.py` が出す `insightPlaybackLocationType.WATCH` は**1つの数**です。
M3・M12 の着手条件も、M8 の効き目の判定も、**全部この1つの数を見ていました。**
そして 8/15 に「WATCH 2→11 なので M8 は効いている」と判定しました。

**間違いです。分けたら、M8 由来は1件もありませんでした。**

    長尺10 ＋ ショート1 ＝ WATCH 11
    長尺10 の流入元: RELATED_VIDEO 6 ／ EXT_URL 2 ／ YT_SEARCH 1 ／ YT_CHANNEL 1

**説明欄の導線（M8）を示す行は1つもありません。** 増分の主犯は関連動画です。
1つの数を複数の手段の成績表に使うと、**どの手段の成果かが混ざります。**

## 分けられること・分けられないこと

**分けられる。** 長尺かショートか。長尺の流入元の内訳。

**分けられない。** 説明欄のクリック数そのもの（API に無い。Studio 専用）。
だから M8 の成績は「**他の経路で説明できない残り**」としてしか読めません。
`residual()` がそれを出します。**0 なら、効いている証拠が無いという意味です**
（効いていない証拠ではありません。ここを混ぜないこと）。

## 使い方

    python scripts/watch_source.py

`dimensions=video` と `filters=insightPlaybackLocationType` の組み合わせは
**400 で弾かれます**（サポート外）。だから動画ごとに引いています。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402

from src.auth import credentials  # noqa: E402

START = "2026-08-01"

# 他の手段で説明がつく経路。M8（説明欄の導線）の成績から差し引く。
#   RELATED_VIDEO … 関連動画。これは M12（推薦面）の面
#   YT_SEARCH     … 検索。M4
#   YT_CHANNEL    … チャンネルページ経由
#   EXT_URL       … 外部リンク。M10（GitHub Pages）が該当しうる
ATTRIBUTED = ("RELATED_VIDEO", "YT_SEARCH", "YT_CHANNEL", "EXT_URL")


def _videos() -> tuple[list[str], list[str]]:
    """公開済みの動画IDを、長尺とショートに分けて返す。"""
    yt = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, token = [], None
    while True:
        page = yt.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token
        ).execute()
        ids += [x["contentDetails"]["videoId"] for x in page["items"]]
        token = page.get("nextPageToken")
        if not token:
            break

    long_, short = [], []
    for chunk in (ids[i:i + 50] for i in range(0, len(ids), 50)):
        info = yt.videos().list(part="contentDetails,status", id=",".join(chunk)).execute()
        for item in info["items"]:
            if item["status"]["privacyStatus"] != "public":
                continue
            dur = item["contentDetails"]["duration"]  # ISO8601
            mins = int(dur.split("PT")[1].split("M")[0]) if "M" in dur else 0
            (long_ if mins >= 3 else short).append(item["id"])
    return long_, short


def _query(an, vid: str, dimension: str) -> dict[str, int]:
    try:
        res = an.reports().query(
            ids="channel==MINE", startDate=START, endDate=date.today().isoformat(),
            metrics="views", dimensions=dimension, filters=f"video=={vid}",
        ).execute()
    except HttpError as exc:
        print(f"    {vid}  取れず: {str(exc)[:70]}")
        return {}
    return {row[0]: row[1] for row in res.get("rows", []) if row[1]}


def main() -> int:
    an = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    long_, short = _videos()

    print("=== WATCH（視聴ページ）の再生は、どこの誰か ===")
    watch = {"長尺": 0, "ショート": 0}
    for label, ids in (("長尺", long_), ("ショート", short)):
        for vid in ids:
            watch[label] += _query(an, vid, "insightPlaybackLocationType").get("WATCH", 0)
    total = watch["長尺"] + watch["ショート"]
    print(f"  長尺 {watch['長尺']} ／ ショート {watch['ショート']} ＝ 合計 {total}")
    if total and watch["長尺"] / total > 0.8:
        print("  **WATCH はほぼ長尺の再生数そのものです。**")
        print("  M3・M12 の着手条件『WATCH が1日30人』は、"
              "実質『長尺が1日30再生』と同じ意味になります。")

    print("\n=== その長尺は、どこから来たのか ===")
    src: dict[str, int] = {}
    for vid in long_:
        for key, val in _query(an, vid, "insightTrafficSourceType").items():
            src[key] = src.get(key, 0) + val
    for key, val in sorted(src.items(), key=lambda x: -x[1]):
        mark = "  ← 他の手段で説明がつく" if key in ATTRIBUTED else ""
        print(f"  {key:<18} {val}{mark}")

    residual = sum(v for k, v in src.items() if k not in ATTRIBUTED)
    print(f"\n  **M8（説明欄の導線）に帰せる残り: {residual}**")
    if residual == 0:
        print("  **0 は「効いていない」ではなく「効いている証拠が無い」です。**"
              " 混ぜないこと。")
    if src.get("RELATED_VIDEO", 0) > residual:
        print(f"  関連動画が {src['RELATED_VIDEO']} で最大。**これは M12（推薦面）の面です。**")
        print("  M12 は「WATCH が伸びたら着手」で保留していますが、"
              "**その WATCH を伸ばしている当のものが M12 の面です。条件が循環しています。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
