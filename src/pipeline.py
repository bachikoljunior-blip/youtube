"""1本ぶんの動画を作って投稿する。

流れ:
  チャンネルから投稿済みを読む → テーマを選ぶ → 台本 → 音声 → 図解 → 合成
  → 検査 → 投稿 → テーマが減っていれば補充
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

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
        if topic_id.startswith("s-"):
            # ショートは長尺のテーマ枠を消費しない。s- で始まるIDは
            # topics.yaml に置かず、その場で作る。長尺のプールを汚さないため。
            #
            # ただし calc は引き継ぐ。引き継がないと台本を書く側に数字が渡らず、
            # **発明するしかなくなる**。
            #
            # `s-<計算モジュール名>-<連番>` と名付ける。s-nenkin-1 なら src/calc/nenkin.py。
            # これまで実際にそう名付けてきた（s-zangyo-1 / s-kojo-1 / s-shitsugyo-1）ので、
            # 規則を後から合わせるのではなく、その規則をそのまま使う。
            stem = topic_id[2:].rsplit("-", 1)[0]
            calc = stem if (config.ROOT / "src" / "calc" / f"{stem}.py").exists() else ""
            if not calc:
                base = next(
                    (t for t in pool["topics"] if t["id"].startswith(stem) and t.get("calc")), None
                )
                calc = base["calc"] if base else ""
            return {
                "id": topic_id, "title_seed": topic_id, "angle": "ショート", "score": 1.0,
                **({"calc": calc} if calc else {}),
            }
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


def pick_thumbnail_slide(script: VideoScript) -> int:
    """サムネイルの背景に使うスライドの番号を返す。

    1枚目は使わない。冒頭の結論——サムネに重ねるのと同じ数字——が書いてあるため。
    「真ん中を取る」にしたら真ん中が stat（巨大な数字1つ）に当たって、また
    同じ数字が背後に透けた。位置で選ぶかぎり運任せになる。

    だから**種類で選ぶ**。chart と table は細かい要素が散っていて、潰したときに
    色の面として残る。stat は要素が1つしかないので、何をしても形が残る。
    """
    for wanted in ("chart", "table", "steps", "compare"):
        for i, seg in enumerate(script.segments):
            if i > 0 and seg.visual.kind == wanted:
                return i
    return min(len(script.segments) - 1, max(1, len(script.segments) // 2))


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="動画を1本作って投稿する")
    parser.add_argument(
        "--script",
        help="台本JSONのパス。渡すと台本生成を飛ばす。"
             "常駐セッションが自分で書いた台本を使うときはこれ",
    )
    parser.add_argument("--topic", help="テーマID。--script を使うときは必須")
    parser.add_argument(
        "--calc",
        help="使う計算モジュール名（src/calc/<名前>.py）。テーマ側の calc を上書きする。"
             "台本を書く側にはここで出た数字しか渡らない",
    )
    parser.add_argument("--visibility", choices=["private", "unlisted", "public"])
    parser.add_argument("--dry-run", action="store_true", help="投稿せず build/ に出すだけ")
    parser.add_argument(
        "--short", action="store_true",
        help="ショート（縦1080x1920・60秒以内）として作る。長尺の尺の下限は適用しない",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    channel = config.load_channel()
    pool = config.load_topics()
    dry = args.dry_run or config.dry_run()

    # ショートは縦画面で、尺の下限も別。長尺の 8.5 分はミッドロール広告のための
    # 下限なので、ショートには意味がない。
    if args.short:
        channel["video"] = dict(channel["video"])
        channel["video"]["resolution"] = [1080, 1920]
        channel["video"]["min_minutes"] = 0.25
        print("[pipeline] ショートとして作ります（1080x1920・尺の下限0.25分）")

    override = args.visibility or config.env("VISIBILITY", required=False)
    if override:
        channel["publish"]["visibility"] = override
        print(f"[pipeline] 公開設定を {override} で上書き")

    # 投稿済みはチャンネルから読む。ファイルには持たない。
    # --dry-run でも本数だけは実際に数える。配色を投稿済み本数で回しているので、
    # ここを 0 にすると dry-run と本番で色が変わってしまう。
    # dry-run で作った final.mp4 をそのまま投稿する運用（scripts/upload_only.py）
    # なので、dry-run 側が本番の色でなければ意味がない。
    already = history.posted_topic_ids()
    posted: set[str] = set() if dry else already
    theme_index = len(already)
    topic_id = args.topic or config.env("TOPIC_ID", required=False)
    if args.script and not topic_id:
        raise RuntimeError("--script を使うときは --topic でテーマIDを指定してください")
    topic = pick_topic(pool, posted, topic_id)
    if args.calc:
        topic = {**topic, "calc": args.calc}
    print(f"=== テーマ: {topic['title_seed']} ({topic['id']}) ===")
    if not args.script and not topic.get("calc"):
        # 台本を生成させるのに計算が無いと、数字を発明させることになる。
        # 「裏の取れない数字は動画に入れない」はここで守らないと守れない。
        raise RuntimeError(
            f"テーマ {topic['id']} に calc がありません。"
            "config/topics.yaml に calc: <モジュール名> を書くか、--calc で渡すか、"
            "--script で自分の書いた台本を渡してください"
        )

    work = config.BUILD_DIR / topic["id"]
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    # 1. 台本。セッションが自分で書いたものがあればそれを使い、無ければ生成する。
    if args.script:
        script = VideoScript.model_validate_json(Path(args.script).read_text(encoding="utf-8"))
        print(f"[pipeline] 台本を読み込みました: {args.script}")
    else:
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
    # 配色は投稿済みの本数から順番に回す。連続する回が同じ色にならないように。
    slides = visuals.render(
        [s.visual.model_dump() for s in script.segments], work / "slides", topic["id"],
        theme_index=theme_index, portrait=args.short,
    )

    # 4. 字幕
    ass_path = subtitles.build(
        [
            {"narration": seg.narration, "start": start, "end": end}
            for seg, (start, end) in zip(script.segments, spans)
        ],
        work / "subtitles.ass",
        portrait=args.short,
    )

    # 5. 合成
    narration = build_narration(segment_paths, work)
    video_path = build_video(
        slides, durations, narration, ass_path,
        work / "final.mp4", work, channel["video"],
    )

    # 6. サムネイル
    theme = visuals.theme_for(topic["id"], theme_index)
    accent = tuple(int(theme["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    thumb_path = thumbnail.create(
        slides[pick_thumbnail_slide(script)], script.thumbnail_line1, script.thumbnail_line2,
        work / "thumbnail.jpg", work, accent=accent,
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
