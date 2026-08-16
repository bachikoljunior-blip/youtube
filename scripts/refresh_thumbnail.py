"""投稿済みの動画に、サムネイルを載せ直す。**入口は2つあります。**

    python scripts/refresh_thumbnail.py --missing
        **控えに残した bytes を、載っていない本すべてに押す**（2026-08-17 に追加）。
        `build/` は要りません。ふつうはこちらです

    python scripts/refresh_thumbnail.py <テーマID> <動画ID> <配色の番号>
        `build/<テーマID>/` から**作り直して**差し替える。
        サムネイルの作りそのものを変えたときだけ

## `--missing` を足した理由（**3回持ち越された項目**）

日枠が切れている13時間は `thumbnails.set` だけが 403 になり、
`videos.insert` は通ります。つまり**サムネイルの無い予約**が積まれます。

申し送りは3回とも「枠が戻った回に `refresh_thumbnail.py` を回すこと」と
書いていました。**その手順は実行できません。** 下の作り直しの道が読むのは
`build/<テーマID>/` ですが、**`build/` は .gitignore で、1周ごとに
コンテナごと消えます。** 枠が戻る JST 16:00 には、03時台に上げた本の
`build/` はとっくにありません。**不可能なことを3回頼み続けていました。**

そして**焼き直す必要はありません。** サムネイルは投稿の時点でもう出来ていて、
YouTube に載らなかっただけです。`scripts/critique_queue.stash()` が
bytes を `data/critique_queue/<動画ID>.thumb.jpg` に残すので、
**後の回は押すだけで済みます**（1本 約70KB）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import MediaFileUpload  # noqa: E402

from src import thumbnail, visuals  # noqa: E402
from src.auth import credentials  # noqa: E402


def main(topic: str, video_id: str, theme_index: int) -> int:
    work = Path("build") / topic
    slides = sorted((work / "slides").glob("slide_*.png"))
    if not slides:
        print(f"{work}/slides がありません")
        return 1

    script = json.loads((work / "script.json").read_text(encoding="utf-8"))
    theme = visuals.theme_for(topic, theme_index)
    accent = tuple(int(theme["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))

    out = thumbnail.create(
        slides[len(slides) // 2],
        script["thumbnail_line1"], script["thumbnail_line2"],
        work / "thumbnail.jpg", work, accent=accent,
    )
    print(f"[thumb] 作り直しました: {out} accent={theme['accent']}")

    y = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    y.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(out))).execute()
    print(f"[thumb] 差し替え完了: https://youtu.be/{video_id}")
    return 0


def push_missing(dry_run: bool = False) -> int:
    """控えに残した bytes を、載っていない本すべてに押す。**`build/` は要りません。**"""
    import critique_queue

    rows = critique_queue.missing_thumbnail()
    if not rows:
        print("[thumb] サムネイルの載っていない本はありません")
        return 0

    print(f"[thumb] サムネイルの載っていない本: **{len(rows)}本**")
    for row in rows:
        print(f"  {row['video_id']}  {row['topic']}  ({row['stashed_at']})")
    if dry_run:
        print("[thumb] --dry-run なので押していません")
        return 0

    y = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    ok = 0
    for row in rows:
        try:
            y.thumbnails().set(
                videoId=row["video_id"],
                media_body=MediaFileUpload(str(row["thumb"])),
            ).execute()
        except Exception as exc:
            # **1本落ちても止めない。** 日枠がまだ戻っていないだけのことがあり、
            # そこで抜けると、押せるはずの残りまで押さずに終わります。
            print(f"[thumb] ✗ {row['video_id']}: {str(exc)[:160]}")
            continue
        # **押せた本だけ印を消す。** 消してから押すと、落ちた本が
        # 一覧から消えて二度と拾われません
        critique_queue.mark_thumbnail_set(row["video_id"])
        ok += 1
        print(f"[thumb] ✓ {row['video_id']}  https://youtu.be/{row['video_id']}")
    print(f"[thumb] **{ok} / {len(rows)} 本に載せました**")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    if "--missing" in sys.argv:
        raise SystemExit(push_missing(dry_run="--dry-run" in sys.argv))
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
