"""1本ぶんの動画を作って投稿する。GitHub Actions から日次で呼ばれる。"""
from __future__ import annotations

import json
import shutil
import sys

from . import config, state, subtitles, thumbnail, uploader
from .assets import AssetFetcher
from .renderer import build_narration, build_video, segment_timeline
from .script_writer import VideoScript, generate
from .tts import synthesize_segments
from .util import fmt_timestamp


def pick_topic(pool: dict, topic_id: str = "") -> dict:
    """スコアが最も高い未使用トピック。同点なら先に書かれているものを選ぶ。

    topic_id を指定すると、used かどうかに関わらずそれを使う（撮り直し用）。
    """
    if topic_id:
        for topic in pool["topics"]:
            if topic["id"] == topic_id:
                return topic
        raise RuntimeError(
            f"トピック '{topic_id}' が config/topics.yaml にありません。"
            f"使えるID: {', '.join(t['id'] for t in pool['topics'][:20])}"
        )

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


LOW_WATER_MARK = 6


def refill_topics_if_low() -> None:
    """未使用テーマが減ってきたら補充する。

    毎日投稿すると初期プールは10日で尽きる。投稿が止まる前に自動で足しておく。
    ここで失敗しても投稿自体は成功しているので、握りつぶして次回に回す。
    """
    unused = [t for t in config.load_topics()["topics"] if not t.get("used")]
    if len(unused) > LOW_WATER_MARK:
        print(f"[pipeline] 未使用テーマ {len(unused)} 件。補充は不要。")
        return

    print(f"[pipeline] 未使用テーマが {len(unused)} 件まで減ったので補充します。")
    try:
        from . import analytics

        analytics.optimize()
    except Exception as exc:  # 補充の失敗で投稿済みの回を失敗扱いにしない
        print(f"[pipeline] テーマの補充に失敗しました（投稿は成功しています）: {exc}")


def main() -> int:
    channel = config.load_channel()
    pool = config.load_topics()

    # 手動実行のときだけ、ワークフローの入力で上書きできるようにしておく
    override = config.env("VISIBILITY", required=False)
    if override:
        channel["publish"]["visibility"] = override
        print(f"[pipeline] 公開設定を {override} で上書き")

    topic = pick_topic(pool, config.env("TOPIC_ID", required=False))
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

    # スマホから中身を確認できるように、成果物と一緒に落とせる形で残す
    (work / "title.txt").write_text(
        script.title + "\n\n[別案]\n" + "\n".join(script.title_alternatives) + "\n",
        encoding="utf-8",
    )
    (work / "description.txt").write_text(description + "\n", encoding="utf-8")
    (work / "script.json").write_text(
        json.dumps(script.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if config.dry_run():
        print("[pipeline] DRY_RUN のためアップロードしません。")
        print(f"  動画: {video_path}")
        print(f"  サムネ: {thumb_path}")
        print(f"\n  タイトル: {script.title}")
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

    refill_topics_if_low()
    print("=== 完了 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
