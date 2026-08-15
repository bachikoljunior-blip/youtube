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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import critique_queue  # noqa: E402  scripts/ 直下。独立評価の材料を残す

from src import bars, config, uploader  # noqa: E402

# 動画に出してはいけない語。オーナーの指示でリポジトリの存在を伏せている。
FORBIDDEN = ("github", "GitHub", "リポジトリ", "コードを公開", "ソースコード")


def main(topic: str, visibility: str | None = None, hour: int | None = None) -> int:
    """hour を渡すと、その時刻（JST）で予約する。

    **ショートは朝のほうが強い**（2026-08-05 の実測）。09:21 公開の1本が1245回、
    18:29〜19:55 に固めて出した5本が最良で558回・後発3本は0回。
    `config/channel.yaml` の 19:00 は長尺（視聴ピーク）に合わせた値なので、
    ショートはここで上書きする。**まだ n=1 なので、時刻の効果と本数の効果は
    分離できていない。** 毎日1本を続けて確かめること。
    """
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
    if hour is not None:
        channel["publish"] = dict(channel["publish"])
        channel["publish"]["publish_hour_jst"] = hour
        print(f"[check] 予約時刻を {hour}:00 JST で上書き")

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
    # 公開した棒を残す。`build/` は .gitignore なので、これをやらないと
    # 次のコンテナで「同じ図」検査の比較対象がゼロになる（`src/bars.py`）。
    bars.record(topic, video_id, script)
    # 独立評価（M13）の材料も同じ理由で残す。**残さないと、投稿した回で評価を
    # 回せなかった時点で永久に評価できません**（`scripts/critique_queue.py`）。
    critique_queue.stash(topic, video_id, script, work)

    print(f"VIDEO_ID {video_id}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3, 4):
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) >= 3 and sys.argv[2] else None,
        int(sys.argv[3]) if len(sys.argv) == 4 else None,
    ))
