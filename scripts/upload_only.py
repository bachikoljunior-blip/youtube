"""検査済みの build/<テーマID>/ を、作り直さずにそのまま投稿する。

    python scripts/upload_only.py <テーマID>

なぜ要るか。--dry-run で作った final.mp4 は、本番投稿するものと完全に同一で、
verify も通っている。それをもう一度パイプラインに通すと、音声合成と38枚の
レンダリングでまた30分かかる。中身は1バイトも変わらないので、待つ意味がない。

投稿前に、タイトル・説明欄・最初のコメントにリポジトリへの言及が無いことを
確認する。ここは動画に出してはいけない（CLAUDE.md 参照）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, uploader  # noqa: E402

# 動画に出してはいけない語。オーナーの指示でリポジトリの存在を伏せている。
FORBIDDEN = ("github", "GitHub", "リポジトリ", "コードを公開", "ソースコード")


def main(topic: str, visibility: str | None = None) -> int:
    work = Path("build") / topic
    if not (work / "final.mp4").exists():
        print(f"{work}/final.mp4 がありません。先に --dry-run で作ってください")
        return 1

    script = json.loads((work / "script.json").read_text(encoding="utf-8"))
    # title.txt は人が見る用で、A/Bテストの別案まで書いてある。
    # そのまま投稿タイトルにすると別案ごと出てしまうので、script.json を使う。
    title = script["title"].strip()
    description = (work / "description.txt").read_text(encoding="utf-8")
    channel = config.load_channel()
    if visibility:
        # ショートは即時公開のほうがフィード配信に乗りやすく、数字も早く取れる。
        # 予約公開は private のときしか効かないので、public を指定したら即時になる。
        channel["publish"] = dict(channel["publish"])
        channel["publish"]["visibility"] = visibility
        print(f"[check] 公開設定を {visibility} で上書き")

    if "[t:" not in description:
        print("説明欄にテーマ印がありません。投稿済みの記録が残らないので中止します")
        return 1
    for field, text in (
        ("タイトル", title),
        ("説明欄", description),
        ("最初のコメント", script.get("first_comment", "")),
    ):
        for word in FORBIDDEN:
            if word in text:
                print(f"{field}に「{word}」が入っています。投稿を中止します")
                return 1
    print("[check] リポジトリへの言及なし")

    video_id = uploader.upload(
        work / "final.mp4",
        work / "thumbnail.jpg",
        title,
        description,
        script["tags"],
        channel["publish"],
    )
    print(f"VIDEO_ID {video_id}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None))
