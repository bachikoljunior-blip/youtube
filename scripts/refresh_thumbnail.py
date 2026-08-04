"""既存の build/<テーマID>/ からサムネイルを作り直して差し替える。

    python scripts/refresh_thumbnail.py <テーマID> <動画ID> <配色の番号>

サムネイルの作りを直したあと、すでに投稿した動画にも当て直すために使う。
動画そのものを作り直す必要はないので数秒で終わる。
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


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
