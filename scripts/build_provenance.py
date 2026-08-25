#!/usr/bin/env python3
"""予約中の各本が、**どの時点のコードで作られたか**を出す。

2026-08-15、オーナーの問い（原文は `docs/CONSTRAINTS.md`）:

> 既存の投稿予約の動画は修正加えられないの？

**答えの半分は「加えられる」で、半分は「動画そのものは無理」です。**
YouTube に「動画ファイルの差し替え」は存在しません。題名・説明欄・サムネ・
公開時刻・タグは API で書き換えられますが、**絵と音を直すには消して上げ直す**
しかありません。

そこで先に要るのが**この表**です。予約は十数本あり、そのあいだに
描画の直しが何件も入っています。**どの本にどの直しが入っていないか**が
分からないと、消して上げ直す価値のある本を選べません。

## 何を根拠に言っているか

- 各本の**アップロード時刻**（`snippet.publishedAt`。予約中の動画では
  公開時刻ではなく、上げた時刻が入る）
- その時刻**以前で最後のコミット** ＝ その回のコンテナが持っていたコード
- その後に入った、**絵と音を変えるコミット**（`OUTPUT_PATHS`）

## 正確に言えないところ（**推測を実測に見せないため、分けて出します**）

子はセッション開始時に checkout するので、**手元のコードはアップロード時刻
より古いことがあります。** つまり「アップロード直前のコミット」は
**入っている保証がありません。** `--window`（既定40分）ぶんは
「不明」として別に数え、**入っている側に足しません。**

    python scripts/build_provenance.py            # 予約中のみ
    python scripts/build_provenance.py --all      # 公開済みも
    python scripts/build_provenance.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JST = timezone(timedelta(hours=9))
MARKER_RE = re.compile(r"\[t:([a-z0-9\-]+)\]")

# 絵と音、そして読み上げる文そのものを変えるところ。
# ここが変わった＝**出来上がった動画が違う**。
OUTPUT_PATHS = [
    "src/renderer.py",
    "src/visuals.py",
    "src/bars.py",
    "src/subtitles.py",
    "src/tts.py",
    "src/thumbnail.py",
    "src/script_writer.py",
    "src/pipeline.py",
    "src/calc",
]

# 出来上がりは変えないが、「その本が今なら通ったか」を変えるところ。
# 直後に上げ直す価値の判断に要るので、別枠で出す。
CHECK_PATHS = ["src/verify.py"]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def ensure_full_history() -> str:
    """**子のクローンは浅い。** 深くしないと、この表は黙って過少に出ます。

    2026-08-15 に実測: `git rev-list --count HEAD` が **53**、履歴は 8/10 まで。
    8/09 に上げた7本は「作られたコード ?」になり、
    入っていない直しも**8/10 以降ぶんしか数えられませんでした。**

    「見えない」と「無い」は違います。**黙って少なく出すほうが危ない**ので、
    ここで深くします。落ちたら落ちたと言い、数えられる範囲を明示します。
    """
    if _git("rev-parse", "--is-shallow-repository") != "true":
        return ""
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    target = branch if branch != "HEAD" else ""
    try:
        subprocess.run(
            ["git", "-C", str(ROOT), "fetch", "--unshallow", "origin", *( [target] if target else [] )],
            capture_output=True, text=True, check=True, timeout=180,
        )
    except Exception as exc:  # noqa: BLE001 — 深くできなくても表は出す
        oldest = _git("log", "--reverse", "--pretty=%cI", "-1")
        return (f"履歴を深くできませんでした（{exc}）。"
                f"**{_fmt(oldest)} より前のコミットは数えられていません。**")
    return ""


def _commits(since_iso: str, paths: list[str]) -> list[tuple[str, str, str]]:
    """since_iso より後のコミットを (hash, 時刻, 題名) で返す。"""
    out = _git(
        "log", f"--since={since_iso}", "--date=iso-strict",
        "--pretty=%h\t%cI\t%s", "--", *paths,
    )
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        h, at, subject = line.split("\t", 2)
        rows.append((h, at, subject))
    return rows


def _built_with(upload_iso: str) -> tuple[str, str]:
    """アップロード時刻以前で最後のコミット。**その回が持っていたコードの上限。**"""
    h = _git("rev-list", "-1", f"--before={upload_iso}", "HEAD")
    if not h:
        return ("", "")
    at = _git("show", "-s", "--format=%cI", h)
    return (h[:7], at)


def _fmt(iso: str) -> str:
    if not iso:
        return "?"
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST).strftime("%m/%d %H:%M")


def fetch_videos(include_published: bool) -> list[dict]:
    from googleapiclient.discovery import build

    from src.auth import credentials

    yt = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    items = ch.get("items", [])
    if not items:
        return []
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids: list[str] = []
    token = ""
    while True:
        r = yt.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50,
            pageToken=token or None,
        ).execute()
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken", "")
        if not token:
            break

    videos: list[dict] = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(
            part="snippet,status,contentDetails", id=",".join(ids[i:i + 50])
        ).execute()
        videos += r.get("items", [])

    rows = []
    for v in videos:
        publish_at = v["status"].get("publishAt")
        if not publish_at and not include_published:
            continue
        desc = v["snippet"].get("description", "")
        m = MARKER_RE.search(desc)
        rows.append({
            "id": v["id"],
            "title": v["snippet"]["title"],
            "topic": m.group(1) if m else "",
            "uploaded": v["snippet"]["publishedAt"],
            "publish_at": publish_at or "",
            "privacy": v["status"].get("privacyStatus", ""),
            "duration": v["contentDetails"].get("duration", ""),
        })
    rows.sort(key=lambda r: r["publish_at"] or r["uploaded"])
    return rows


def annotate(rows: list[dict], window_min: int) -> list[dict]:
    for r in rows:
        up = datetime.fromisoformat(r["uploaded"].replace("Z", "+00:00"))
        # checkout はアップロードより前。窓のぶんは「入っている」と言わない。
        safe = (up - timedelta(minutes=window_min)).isoformat()

        h, at = _built_with(r["uploaded"])
        r["built_commit"] = h
        r["built_at"] = at

        after = _commits(r["uploaded"], OUTPUT_PATHS)
        window = [
            c for c in _commits(safe, OUTPUT_PATHS)
            if c not in after
        ]
        r["missing_output"] = after
        r["uncertain_output"] = window
        r["missing_check"] = _commits(r["uploaded"], CHECK_PATHS)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="公開済みも出す")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--window", type=int, default=40,
                    help="checkout の不確かさ（分）。既定40")
    args = ap.parse_args()

    warning = ensure_full_history()
    rows = annotate(fetch_videos(args.all), args.window)
    if not rows:
        print("対象がありません。")
        return 0
    if warning:
        print(f"[注意] {warning}\n")

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print(f"予約・公開の {len(rows)} 本。**アップロード時刻から、入っていない直しを数えます**")
    print("（不明 ＝ アップロード直前 {}分 のコミット。checkout の順序が読めないので"
          "「入っている」に数えません）\n".format(args.window))

    for r in rows:
        n_out = len(r["missing_output"])
        n_unk = len(r["uncertain_output"])
        n_chk = len(r["missing_check"])
        mark = "！" if n_out >= 3 else " "
        when = _fmt(r["publish_at"]) if r["publish_at"] else "公開済み"
        print(f"{mark}{r['id']}  公開 {when}  上げた {_fmt(r['uploaded'])}"
              f"  [{r['topic'] or '?'}]  {r['title'][:26]}")
        print(f"   作られたコード: {r['built_commit'] or '?'} ({_fmt(r['built_at'])})"
              f"  入っていない直し: 絵と音 {n_out} 件 / 不明 {n_unk} 件 / 検査 {n_chk} 件")
        for h, at, subject in r["missing_output"]:
            print(f"     - {h} {_fmt(at)} {subject[:58]}")
        for h, at, subject in r["uncertain_output"]:
            print(f"     ? {h} {_fmt(at)} {subject[:58]}")
        print()

    worst = sorted(rows, key=lambda r: -len(r["missing_output"]))
    print("── 入っていない直しが多い順 ──")
    for r in worst[:5]:
        print(f"  {len(r['missing_output']):2d} 件  {r['id']}  "
              f"公開 {_fmt(r['publish_at']) if r['publish_at'] else '済'}  [{r['topic']}]")
    print()
    print("**消して上げ直すなら、代わりを先に作ること。** 予約の穴は投稿の途切れです。")
    print("題名・説明欄・サムネ・公開時刻だけなら、消さずに直せます"
          "（retitle.py / refresh_thumbnail.py）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
