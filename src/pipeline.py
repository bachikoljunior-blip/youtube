"""1本ぶんの動画を作って投稿する。

流れ:
  チャンネルから投稿済みを読む → テーマを選ぶ → 台本 → 音声 → 図解 → 合成
  → 検査 → 投稿 → テーマが減っていれば補充
"""
from __future__ import annotations

import json
import random
import shutil
import sys

from . import config, history, subtitles, thumbnail, uploader, verify, visuals
from .renderer import build_narration, build_video, segment_timeline
from .script_writer import VideoScript, generate
from .tts import synthesize_segments
from .util import fmt_timestamp

LOW_WATER_MARK = 6
EXPLORE_RATE = 0.3


def pick_topic(pool: dict, posted: set[str], topic_id: str = "") -> dict:
    """次に作るテーマを選ぶ。

    基本はスコア最大。ただし3割の確率で、未投稿のものから無作為に選ぶ。
    スコアはあくまで推測なので、常に最大を取ると、推測が外れていたときに
    そこから抜け出せない。たまに違うものを試して確かめる。
    """
    if topic_id:
        for topic in pool["topics"]:
            if topic["id"] == topic_id:
                return topic
        raise RuntimeError(
            f"テーマ '{topic_id}' が config/topics.yaml にありません。"
            f"使えるID: {', '.join(t['id'] for t in pool['topics'][:20])}"
        )

    candidates = [t for t in pool["topics"] if t["id"] not in posted]
    if not candidates:
        raise RuntimeError(
            "未投稿のテーマがありません。config/topics.yaml に追加するか、"
            "「3. テーマを実績から入れ替える」を実行してください。"
        )

    if len(candidates) > 1 and random.random() < EXPLORE_RATE:
        topic = random.choice(candidates)
        print(f"[pipeline] 探索: 無作為に選びました（{int(EXPLORE_RATE * 100)}%の確率）")
        return topic
    return max(candidates, key=lambda t: float(t.get("score", 1.0)))


def build_description(script: VideoScript, spans: list[tuple[float, float]],
                      channel: dict, topic_id: str) -> str:
    parts = [script.description_body.strip(), "", "▼ 目次"]

    lines = []
    for chapter in sorted(script.chapters, key=lambda c: c.segment_index):
        index = max(0, min(chapter.segment_index, len(spans) - 1))
        start = 0.0 if not lines else spans[index][0]
        lines.append(f"{fmt_timestamp(start)} {chapter.label}")
    if not lines:
        lines = ["0:00 はじめに"]
    parts += lines

    parts.append(channel["publish"]["footer"].rstrip())
    # 投稿済みの印。次回このテーマが選ばれないための唯一の記録で、
    # 動画を消せばこの記録も一緒に消える（＝また作れるようになる）。
    parts += ["", history.marker(topic_id)]
    return "\n".join(parts)


def refill_topics_if_low(posted: set[str]) -> None:
    """未投稿のテーマが減ってきたら補充する。投稿自体は失敗させない。"""
    unused = [t for t in config.load_topics()["topics"] if t["id"] not in posted]
    if len(unused) > LOW_WATER_MARK:
        print(f"[pipeline] 未投稿テーマ {len(unused)} 件。補充は不要。")
        return

    print(f"[pipeline] 未投稿テーマが {len(unused)} 件まで減ったので補充します。")
    try:
        from . import analytics

        analytics.optimize(posted)
    except Exception as exc:
        print(f"[pipeline] テーマの補充に失敗しました（投稿は成功しています）: {exc}")


def main() -> int:
    channel = config.load_channel()
    pool = config.load_topics()
    dry = config.dry_run()

    override = config.env("VISIBILITY", required=False)
    if override:
        channel["publish"]["visibility"] = override
        print(f"[pipeline] 公開設定を {override} で上書き")

    # 投稿済みはチャンネルから読む。ファイルには持たない。
    posted: set[str] = set() if dry else history.posted_topic_ids()
    topic = pick_topic(pool, posted, config.env("TOPIC_ID", required=False))
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
        raise RuntimeError("台本のセグメントが空でした。テーマを変えて再実行してください。")

    segment_paths = [p for p, _ in audios]
    durations = [d for _, d in audios]
    spans = segment_timeline(durations)
    print(f"[pipeline] 想定尺: {spans[-1][1] / 60:.1f} 分")

    # 3. 図解を自前で描いて撮る
    slides = visuals.render([s.visual.model_dump() for s in script.segments], work / "slides")

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
        slides, durations, narration, ass_path,
        work / "final.mp4", work, channel["video"],
    )

    # 6. サムネイル
    thumb_path = thumbnail.create(
        slides[0], script.thumbnail_line1, script.thumbnail_line2,
        work / "thumbnail.jpg", work,
    )

    description = build_description(script, spans, channel, topic["id"])

    (work / "title.txt").write_text(
        script.title + "\n\n[別案]\n" + "\n".join(script.title_alternatives) + "\n",
        encoding="utf-8",
    )
    (work / "description.txt").write_text(description + "\n", encoding="utf-8")
    (work / "script.json").write_text(
        json.dumps(script.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 7. 投稿前の検査。ここで落ちたら投稿しない。
    verify.check(video_path, channel["video"], float(channel["video"]["min_minutes"]), work)

    if dry:
        print("[pipeline] DRY_RUN のためアップロードしません。")
        print(f"  動画: {video_path}\n  サムネ: {thumb_path}")
        print(f"\n  タイトル: {script.title}\n  説明欄:\n{description}")
        return 0

    # 8. 投稿。最初のコメントは台本と一緒に生成させたものを使う。
    channel["publish"]["first_comment"] = script.first_comment
    video_id = uploader.upload(
        video_path, thumb_path, script.title, description,
        script.tags, channel["publish"],
    )

    refill_topics_if_low(posted | {topic["id"]})
    print("=== 完了 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
