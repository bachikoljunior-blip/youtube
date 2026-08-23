"""**冒頭の動きの A/B を「作ったときの値」で割る。**（2026-08-23）

## なぜ日付で割ってはいけないか（実測で2回踏んだ）

    2026-08-19  `src/ab_split.py` —— 題・冒頭の問いかけを**テーマIDで割っていた**。
                指示が入る前に作った本も「問い」側に数えられ、両群の中身が同じだった
    2026-08-23  「冒頭0.9秒の動き」（期限 09/05）—— **公開日で割っていた**。
                動きは 8/15 の実装で、**作った記録 405本すべてが 8/15 以降**。
                **対照群が1本も無く、測る前から「外れ」が確定**していた

**実装は在庫より先に効き、在庫は数週間先まで予約されています。**
だから「いつ公開したか」も「いつ実装したか」も群を表しません。
**表すのは「その本を作ったときに、どの設定だったか」だけ**です。

`scripts/batch_build.py` が `data/batch_runs.jsonl` の各回に `opening_motion` を
残すようにしたので（同日）、ここはそれを読むだけにしてあります。

## 記録の無い本は、どちらにも入れない

8/23 より前の回には `opening_motion` がありません。**「無い＝動きあり」と
みなすこともできますが、しません** —— 実装前に作った本が混ざる可能性を
ゼロにできないからです。**分からないものは数えない**（標本は減りますが、
群が汚れるより安いです。8/19 の教訓）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "batch_runs.jsonl"
UPLOADED = ROOT / "data" / "uploaded.jsonl"


def motion_by_topic(runs: Path = RUNS) -> dict[str, bool]:
    """テーマID → **作ったときに動きが入っていたか**。記録の無い回は入れない。"""
    out: dict[str, bool] = {}
    if not runs.exists():
        return out
    for line in runs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "opening_motion" not in row:
            continue
        flag = bool(row["opening_motion"])
        for res in row.get("results") or []:
            tid = res.get("topic")
            if tid:
                out.setdefault(tid, flag)
    return out


def topic_by_video(uploaded: Path = UPLOADED) -> dict[str, str]:
    """video_id → テーマID。"""
    out: dict[str, str] = {}
    if not uploaded.exists():
        return out
    for line in uploaded.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("video_id") and row.get("topic"):
            out.setdefault(row["video_id"], row["topic"])
    return out


def groups(video_ids: list[str] | None = None,
           motion: dict[str, bool] | None = None,
           topics: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """`(対照＝動きなし, 動きあり)`。**どちらにも入らない本は捨てます。**"""
    motion = motion_by_topic() if motion is None else motion
    topics = topic_by_video() if topics is None else topics
    ids = list(topics) if video_ids is None else video_ids
    off: list[str] = []
    on: list[str] = []
    for vid in ids:
        tid = topics.get(vid)
        if tid is None or tid not in motion:
            continue                       # **分からないものは数えない**
        (on if motion[tid] else off).append(vid)
    return sorted(off), sorted(on)


def main() -> None:  # pragma: no cover - 画面出力だけ
    off, on = groups()
    print("=== 冒頭の動き A/B（作ったときの値で割る）===")
    print(f"  対照（動きなし） {len(off)}本 ／ 動きあり {len(on)}本")
    if not off:
        print("  **対照群がまだ 0本です。** `YT_OPENING_MOTION=0` で作らないかぎり増えません")
        print("  （`config/hypotheses.yaml` の `control_group_todo`: 8本以上・同じ日に交互で予約）")


if __name__ == "__main__":  # pragma: no cover
    main()
