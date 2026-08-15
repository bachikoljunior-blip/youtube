#!/usr/bin/env python3
"""独立評価を、**この環境で実際に回せる形**で回す（`docs/CRITIQUE.md` の実装）。

    python scripts/critique_run.py <動画ID>            # 3体に投げて、点まで記録する
    python scripts/critique_run.py --next              # 待ち行列の先頭を1本
    python scripts/critique_run.py --count 4 --jobs 4  # 先頭から4本を同時に
    python scripts/critique_run.py <動画ID> --dry      # 投げるだけで記録しない

## なぜ要るか（2026-08-15）

`docs/CRITIQUE.md` は「**意図を知らない3体**に、同じメッセージで同時に投げる」と
書いてあり、手順は `Agent` ツール（サブエージェント）を前提にしていました。
**この環境ではそれが使えません。** 結果、8/15 の回が続けて
「環境がサブエージェント禁止で回せず」と書いて終え、**待ち行列は9本まで伸びました。**

`docs/trigger_main.md` §5 はこう言っています ——
**「`Agent` ツールが禁じられているように見えるなら、使えるやり方に自分で置き換える」。**
**回らない検査は、生成費だけ増やす儀式です。**

**置き換え先は、既にこのリポジトリの中で動いていました。**
台本生成は `src/claude_cli.py` から `claude -p`（ヘッドレス）を叩いています。
**同じ道で3体を立てられます。** しかも**別プロセス・別セッション**なので、
サブエージェントより独立性は強いくらいです（互いの答えが原理的に見えない）。

## 独立を保つために、ここでやっていること

**`claude -p` を、リポジトリの外で走らせます。**

これが要ります。CLI は cwd の `CLAUDE.md` をプロジェクト指示として読み込むので、
リポジトリの中で走らせると **3体とも「この動画の目的・合格基準・いま試している仮説」を
全部読んでから見る**ことになります。`docs/CRITIQUE.md` が
「渡してはいけないもの」に挙げているものが、**丸ごと入ります。**
それでは「意図を知っている検査」＝いまの目視と同じものになり、**手が無意味になります。**

だから contact sheet だけを一時ディレクトリに置き、**そこを cwd にして呼びます。**
渡すのは `docs/CRITIQUE.md` の2つだけ ——**コマの画像と、読み上げ文。**

## この道具が答えないこと

**点が本物かは答えません。** それは `config/hypotheses.yaml`
（「独立したエージェントの評価スコアは、engaged 比率を予測する」）の仕事で、
判定は engaged と突き合わせた6本がたまってからです。
**較正期間なので、点が低くても公開は止めません**（`docs/CRITIQUE.md`）。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.claude_cli import _binary, _child_env, _parse_envelope  # noqa: E402

QUEUE = ROOT / "data" / "critique_queue"
CRITICS = 3
TIMEOUT = 900

# **`docs/CRITIQUE.md`「投げる文」をそのまま使う。**
# 書き換えたら、あちらと一緒に直して記録に残すこと（片方だけ動かすと、
# 過去の点と比べられなくなります）。
PROMPT = """あなたは日本語のショート動画をスクロールしている視聴者です。
同じフォルダにある {sheet} が、動画のコマを時間順に並べた画像です（{orient}動画）。
**まずその画像を開いて見てください。**

読み上げられる文は、次のとおりです。

{narration}

**この動画が何を目的に作られたかは知らされていません。知る必要もありません。**
次の5つに、この順で答えてください。前置きは要りません。

1. 最初の1.5秒（左上の1〜2コマ）で親指が止まりますか。はい/いいえ と理由1行
2. これは何の動画か、1文で言えますか。言えるならその1文。**言えないなら「言えない」**
3. 出ている数字を信じられますか。**前提が画面に出ているか**で答えてください
4. 画面は1〜2秒ごとに変わりますか。変わらない区間があればその位置
5. **総合 0〜10。** 10 は「最後まで見てしまう」、0 は「1秒で飛ばす」

最後の行は `SCORE: <数字>` だけにしてください。
"""


def load(video_id: str) -> tuple[dict, Path]:
    meta_path = QUEUE / f"{video_id}.json"
    sheet = QUEUE / f"{video_id}.jpg"
    if not meta_path.exists():
        raise SystemExit(f"待ち行列に {video_id} がありません: {meta_path}")
    if not sheet.exists():
        raise SystemExit(
            f"contact sheet がありません: {sheet}\n"
            "**画像が無い本には点を付けないこと**（docs/CRITIQUE.md）。"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not meta.get("narration"):
        raise SystemExit(
            f"{video_id} は読み上げ文が0行です。**渡してよいもの2つのうち片方が無いので評価しません**"
            "（docs/CRITIQUE.md「最初の2本は、材料が半分しか残っていません」）。"
        )
    return meta, sheet


def ask_one(n: int, prompt: str, workdir: Path) -> tuple[int, str]:
    """1体ぶん。**リポジトリの外**で走らせる（CLAUDE.md を読ませないため）。"""
    args = [_binary(), "-p", prompt, "--output-format", "json", "--model", "opus"]
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=TIMEOUT,
            env=_child_env(), cwd=workdir,
        )
    except subprocess.TimeoutExpired:
        return n, ""
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip()[-400:]
        print(f"[critique] {n}体目が異常終了 (exit {proc.returncode})\n{tail}")
        return n, ""
    try:
        body, _ = _parse_envelope(proc.stdout)
    except Exception as exc:  # noqa: BLE001
        print(f"[critique] {n}体目の返りを読めません: {str(exc)[:200]}")
        return n, ""
    return n, body


def score_of(body: str) -> float | None:
    """最終行の `SCORE: n` を拾う。**無ければ None**（推測で埋めないこと）。"""
    hits = re.findall(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)", body)
    if not hits:
        return None
    value = float(hits[-1])
    return value if 0 <= value <= 10 else None


def scored_ids() -> set[str]:
    """既に点の付いた動画。`data/critique.jsonl` から拾う。"""
    out: set[str] = set()
    log = ROOT / "data" / "critique.jsonl"
    if not log.exists():
        return out
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if isinstance(rec, dict):
            out.add(rec.get("video") or rec.get("topic"))
    return out


def pending_ids() -> list[str]:
    """まだ点の付いていない動画。**古い順**（投稿した順）に返す。

    #### `*.plan.json` を数に入れないこと（2026-08-16 に、まだ残っていた）

    待ち行列には1本につき2つのファイルが入ります ——
    `<ID>.json`（読み上げ文）と `<ID>.plan.json`（コマの列）。
    `glob("*.json")` は**両方**返し、`Path.stem` は後者から
    **`<ID>.plan` という、点の付けようがない名前**を作ります。

    8/15 23:4x の回がこの穴を見つけて `scripts/critique_queue.py`（一覧）を
    直しましたが、**点を付ける側（ここ）は直っていませんでした。**
    実測で **52件中13件**が `.plan` の偽物です。`<ID>.plan` は `<ID>` の
    すぐ後ろに並ぶので、**本物に点が付いた次の回で必ず先頭に来て、
    `load()` が SystemExit で止まります**（＝待ち行列がそこで永久に詰まる）。

    **片方だけ直す形は、このリポジトリで通算5回目です。**
    """
    scored = scored_ids()
    ids = []
    for p in sorted(QUEUE.glob("*.json")):
        if p.name.endswith(".plan.json"):
            continue
        if p.stem in scored:
            continue
        ids.append(p.stem)
    return ids


def critique_one(video_id: str, pool: ThreadPoolExecutor) -> list:
    """1本ぶんの3体を `pool` に積んで、Future の一覧を返す。

    **作業場（リポジトリの外）は本ごとに別**です。同じ場所に2本ぶんの
    contact sheet を置くと、3体が隣の本の画像を開けてしまいます
    （2026-08-15 に、生成側の `claude -p` が cwd 共有で隣の題を出した件と同じ形）。
    """
    meta, sheet = load(video_id)
    narration = "\n".join(f"{i}. {t}" for i, t in enumerate(meta["narration"], 1))
    tmp = tempfile.mkdtemp(prefix=f"critique-{video_id}-")
    work = Path(tmp)
    shutil.copy2(sheet, work / sheet.name)
    prompt = PROMPT.format(
        sheet=sheet.name,
        orient=meta.get("orientation", "縦"),
        narration=narration,
    )
    print(f"[critique] {video_id} を {CRITICS}体に**同時に**投げます"
          f"（互いの答えは見えません・cwd={work}）", flush=True)
    return [pool.submit(ask_one, n, prompt, work) for n in range(1, CRITICS + 1)]


def report(video_id: str, answers: list[tuple[int, str]]) -> list[float]:
    scores: list[float] = []
    for n, body in answers:
        print(f"\n===== {video_id} / {n}体目 =====")
        print(body.strip() if body else "（返りなし）")
        s = score_of(body)
        if s is None:
            print(f"[critique] **{n}体目の点が読めません。**")
        else:
            scores.append(s)
    print(f"\n[critique] {video_id} 取れた点: {scores}")
    return scores


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="独立評価を3体に投げて記録する")
    ap.add_argument("video_id", nargs="?", default="", help="動画ID")
    ap.add_argument("--next", action="store_true", help="待ち行列の先頭を1本")
    ap.add_argument("--count", type=int, default=0,
                    help="待ち行列の先頭から N 本を**同時に**回す（--next の複数版）")
    ap.add_argument("--jobs", type=int, default=3,
                    help="同時に走らせる本数。1体あたり claude -p が1つ立つので、"
                         f"実際のプロセス数は jobs×{CRITICS}")
    ap.add_argument("--dry", action="store_true", help="投げるが記録しない")
    args = ap.parse_args(argv)

    # **`--count` を足した理由**（2026-08-16。前の回の (a2) 問い3）。
    #
    # 待ち行列は37本まで伸びていて、`--next` は**1回に1本**しか回しません。
    # 3体が同時に走るのはその1本ぶんだけで、**残りは積まれるほうが速い**状態でした。
    # 生成の段では `--jobs` の実測（同時6で2.66倍）を取ってあるのに、
    # **評価の段では取っていませんでした。**
    # 材料（`.jpg` と `.plan.json`）はディスクにあるので、**生成は0回**です。
    if args.count and args.video_id:
        ap.error("--count と動画IDは一緒に使えません")
    # **`want` は「回したい本数」であって、待ち行列の先頭N本ではありません。**
    # 材料の欠けた本（読み上げ文0行）は永久に評価できないので、
    # **先頭N本を切り取る形にすると、その本が毎回1枠ずつ食い続けます**
    # （2026-08-16 の実測で、未評価36本のうち2本がこれ）。**足りるまで繰り上げます。**
    if args.count:
        queue = pending_ids()
        want = args.count
        if not queue:
            print("[critique] 待ち行列は空です。")
            return 0
        print(f"[critique] 待ち行列 {len(queue)}本のうち {min(want, len(queue))}本を回します"
              f"（同時 {args.jobs}本 ＝ claude -p は最大 {args.jobs * CRITICS} 個）")
    elif args.video_id:
        queue, want = [args.video_id], 1
    elif args.next:
        queue, want = pending_ids()[:1], 1
        if not queue:
            print("[critique] 待ち行列は空です。")
            return 0
        print(f"[critique] 待ち行列の先頭: {queue[0]}")
    else:
        ap.error("動画ID か --next か --count のどれかが要ります")

    started = time.monotonic()
    futures: dict[str, list] = {}
    skipped: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs) * CRITICS) as pool:
        for vid in queue:
            if len(futures) >= want:
                break
            try:
                futures[vid] = critique_one(vid, pool)
            except SystemExit as exc:
                # **1本の材料が欠けただけで、残りを落とさないこと。**
                print(f"[critique] {vid} は飛ばします: {exc}")
                skipped.append(vid)
        results = {vid: [f.result() for f in fs] for vid, fs in futures.items()}
    elapsed = time.monotonic() - started
    ids = list(futures)

    # **点を付けるのは1本ずつ。** `critique_record.py` は共有の台帳
    # （`data/critique.jsonl`）に書くので、ここを並列にすると行が壊れます。
    # **並列にしてよいのは「訊く段」だけ**（`batch_build.py` の予約と同じ理由）。
    rc = 0
    done = 0
    for vid in ids:
        if vid not in results:
            continue
        scores = report(vid, results[vid])
        if len(scores) < CRITICS:
            print(f"**{CRITICS}体そろっていないので {vid} は記録しません**"
                  "（`critique_record.py` に嘘の点を入れると検査そのものが死にます）。")
            rc = 1
            continue
        if args.dry:
            print(f"[critique] --dry なので {vid} は記録しません。")
            continue
        cmd = [sys.executable, str(ROOT / "scripts" / "critique_record.py"), vid]
        cmd += [str(s) for s in scores]
        print(f"[critique] $ {' '.join(cmd)}", flush=True)
        rc = subprocess.run(cmd, cwd=ROOT).returncode or rc
        done += 1

    if len(ids) > 1:
        # **速さを実測で残す。** 「速くなったはず」で終えないこと
        # （生成側の `--jobs` はここを測らなかったせいで4回持ち越されました）。
        per = elapsed / max(len(results), 1)
        print(f"\n[critique] {len(results)}本を {elapsed / 60:.1f}分"
              f"（1本あたり {per / 60:.1f}分・同時 {args.jobs}本）"
              f" 記録 {done}本／飛ばし {len(skipped)}本")
        print(f"[critique] 残り {len(pending_ids())}本")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
