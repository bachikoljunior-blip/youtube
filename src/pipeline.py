"""1本ぶんの動画を作って投稿する。GitHub Actions から日次で呼ばれる。"""
from __future__ import annotations

import shutil
import sys

from . import config, state, subtitles, thumbnail, uploader
from .assets import AssetFetcher
from .renderer import build_narration, build_video, segment_timeline
from .script_writer import VideoScript, generate
from .tts import synthesize_segments
from .util import fmt_timestamp


def pick_topic(pool: dict) -> dict:
    """スコアが最も高い未使用トピック。同点なら先に書かれているものを選ぶ。"""
    candidates = [(i, t) for i, t in enumerate(pool["topics"]) if not t.get("used")]
    if not candidates:
        raise RuntimeError(
            "未使用のトピックがありません。config/topics.yaml に追加するか、"
            "optimize ワークフローを手動実行してください。"
        )
    _, topic = max(candidates, key=lambda pair: (float(pair[1].get("score", 1.0)), -pair[0]))
    return topic


def build_description(script: VideoScript, spans: list[tuple[float, float]], channel: dict, credits: str) -> str:
    parts = [script.description_body.strip(), "", "▼ 目次"]

    seen_zero = False
    lines = []
    for chapter in sorted(script.chapters, key=lambda c: c.segment_index):
        index = max(0, min(chapter.segment_index, len(spans) - 1))
        start = spans[index][0]
        if not lines:
            start, seen_zero = 0.0, True
        lines.append(f"{fmt_timestamp(start)} {chapter.label}")
    if not seen_zero and lines:
        lines.insert(0, "0:00 はじめに")
    parts += lines

    if credits:
        parts += ["", credits]
    parts.append(channel["publish"]["footer"].rstrip())
    return "\n".join(parts)


def main() -> int:
    channel = config.load_channel()
    pool = config.load_topics()
    topic = pick_topic(pool)
    print(f"=== テーマ: {topic['title_seed']} ({topic['id']}) ===")

    work = config.BUILD_DIR / topic["id"]
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    # 1. 台本
    script = generate(channel, topic)
    print(f"[pipeline] タイトル: {script.title}")

    # 2. 音声（ここで各セグメントの実尺が確定する）
    audios = synthesize_segments(
        [s.narration for s in script.segments],
        channel["generation"]["tts"],
        work / "audio",
    )
    if not audios:
        raise RuntimeError("台本のセグメントが空でした。トピックを変えて再実行してください。")

    segment_paths = [p for p, _ in audios]
    durations = [d for _, d in audios]
    spans = segment_timeline(durations)
    total = spans[-1][1]
    print(f"[pipeline] 想定尺: {total / 60:.1f} 分")

    if total < float(channel["video"]["min_minutes"]) * 60:
        print(
            f"[pipeline] 警告: {total / 60:.1f}分しかありません。"
            "8分未満だとミッドロール広告を入れられず収益が大きく落ちます。"
        )

    # 3. 映像素材
    fetcher = AssetFetcher(work / "assets")
    assets = [
        fetcher.fetch(seg.visual_query, i) for i, seg in enumerate(script.segments)
    ]

    # 4. 字幕
    ass_path = subtitles.build(
        [
            {"narration": seg.narration, "on_screen": seg.on_screen, "start": start, "end": end}
            for seg, (start, end) in zip(script.segments, spans)
        ],
        work / "subtitles.ass",
    )

    # 5. 合成
    narration = build_narration(segment_paths, work)
    video_path = build_video(
        assets, durations, narration, ass_path,
        work / "final.mp4", work, channel["video"],
    )

    # 6. サムネイル
    thumb_path = thumbnail.create(
        assets[0].path, script.thumbnail_line1, script.thumbnail_line2,
        work / "thumbnail.jpg", work,
    )

    description = build_description(script, spans, channel, fetcher.credit_line())

    if config.dry_run():
        print("[pipeline] DRY_RUN のためアップロードしません。")
        print(f"  動画: {video_path}")
        print(f"  サムネ: {thumb_path}")
        print(f"  説明欄:\n{description}")
        return 0

    # 7. 投稿
    video_id = uploader.upload(
        video_path, thumb_path, script.title, description,
        script.tags, channel["publish"],
    )

    # 8. 記録（次回以降このテーマは選ばれない）
    topic["used"] = True
    config.save_topics(pool)
    state.record(video_id, topic["id"], script.title)
    print("=== 完了 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
