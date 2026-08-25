#!/usr/bin/env python3
"""**この repo だけを読んで、いまの状態と次の一手を組み立てる。**（2026-08-23）

## なぜ要るか

**引き継ぎのたびに、前の親が長い申し送りを手で書いていた。** 書き忘れれば落ち、
書きすぎれば読まれない。そして**書けるのは、まだ生きているセッションだけ**なので、
**落ちた回のぶんは誰にも渡らない**（8/15・8/16 に依頼が2回消えたのがこれ）。

**渡すのをやめて、置いておく。** 状態は全部この repo にあるので、
**新しいセッションは会話履歴を読まずに、ここから復元できる。**

    python scripts/resume.py          # API 0単位・数秒
    python scripts/resume.py --full   # 予測（eta）も出す。約1分

## 何を読むか（**全部この repo の中**）

    docs/JOURNAL.md          直近の見出し（何をしたか）
    data/inbox.jsonl         オーナーからの依頼で、まだ閉じていないもの
    config/watches.yaml      満ちた待ち／満ちない待ち（`src/watches` `src/watch_eta`）
    config/hypotheses.yaml   期限の近い前提
    data/build_flags.jsonl   A/B の群の台帳（作ったときの値）
    build/                   まだ予約していない本（**コンテナと一緒に消える**）

## 覆る条件

**この出力が長くなったら、それは失敗です。** 読まれずに飛ばされるので、
**画面1枚に収まる範囲で削ること。** 詳しく知りたい回は元のファイルを読む。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))          # `src` を読むため（scripts/ から呼ばれる）
JST = timezone(timedelta(hours=9))


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def journal_heads(n: int = 6) -> list[str]:
    p = ROOT / "docs" / "JOURNAL.md"
    if not p.exists():
        return []
    heads = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
             if l.startswith("## ")]
    return heads[-n:]


def open_requests() -> list[str]:
    """**閉じていないオーナーの依頼。**

    `scripts/inbox.py` は同じ `id` で `kind="open"` と `kind="close"` の2行を書く。
    **最初この判定を `state` という在りもしない欄で書き、22件すべてを「未処理」と
    出した**（2026-08-23）。**欄の名前を確かめずに書いたため。**
    """
    rows = _jsonl(ROOT / "data" / "inbox.jsonl")
    closed = {r.get("id") for r in rows if r.get("kind") == "close"}
    out = []
    for r in rows:
        if r.get("kind") != "open" or r.get("id") in closed:
            continue
        text = str(r.get("text") or "").replace("\n", " ")
        out.append(f"{r.get('id', '')[:8]} {r.get('at', '')[:16]} {text[:110]}")
    return out


def unreserved_builds() -> list[str]:
    """**まだ予約していない本。** `--skip-upload` の本はコンテナと一緒に消える。"""
    build = ROOT / "build"
    if not build.is_dir():
        return []
    posted = {r.get("topic") for r in _jsonl(ROOT / "data" / "uploaded.jsonl")}
    return sorted(d.name for d in build.iterdir() if d.is_dir() and d.name not in posted)


def ab_ledger() -> str:
    rows = _jsonl(ROOT / "data" / "build_flags.jsonl")
    off = sum(1 for r in rows if not r.get("opening_motion"))
    on = len(rows) - off
    return f"対照（動きなし）{off}本 ／ 動きあり {on}本"


def main() -> None:
    now = datetime.now(JST)
    print(f"=== いまの状態（repo から復元。{now:%m/%d %H:%M} JST）===")
    print()
    print("--- 直近にやったこと（docs/JOURNAL.md の見出し）---")
    for h in journal_heads():
        print("  " + h[3:][:100])
    print()
    reqs = open_requests()
    print(f"--- 閉じていないオーナーの依頼: {len(reqs)}件 ---")
    for r in reqs[:5]:
        print("  " + r)
    print()
    print("--- 待ち（config/watches.yaml）---")
    try:
        from src import watches as W
        met = W.unanswered()
        print(f"  **満ちて答えていない待ち: {len(met)}件**"
              + ("".join(f"\n    [!] {w.id}: {w.what[:70]}" for w in met) if met else ""))
    except Exception as exc:                                   # noqa: BLE001
        print(f"  読めません: {exc}")
    try:
        from src import watch_eta
        from src import watches as W2
        for w in [x for x in W2.load() if not x.answered]:
            f = watch_eta.forecast(w)
            if f and f.in_time is False and not f.not_started:
                print(f"  [!] **埋まらない待ち** {w.id}: {f.now:.0f}/{f.need:.0f}"
                      f"（伸び {f.per_day:.2f}/日・期限 {f.deadline}）")
    except Exception:                                          # noqa: BLE001
        pass
    print()
    print("--- A/B の群（data/build_flags.jsonl）---")
    print("  " + ab_ledger())
    print()
    left = unreserved_builds()
    if left:
        print(f"--- **予約していない本が {len(left)}本**（コンテナと一緒に消えます）---")
        for t in left:
            print("  " + t)
        print()
    print("--- 次にやること ---")
    print("  1. `python scripts/status.py` を読む（日枠・在庫・待ち）")
    print("  2. `python scripts/eta.py` の3行（--full なら下に出します）")
    print("  3. 上の「満ちた待ち」「埋まらない待ち」「閉じていない依頼」を潰す")
    print("  4. 出したら `python scripts/run_marker.py --ship … --lever … --moves …`")
    print()
    print("  **予約の位置は `python scripts/reschedule.py --list` を見ること。**")
    print("  `data/uploaded.jsonl` は古い行を持ちます（8/23 実測: 台帳17本／実物8本）")

    if "--full" in sys.argv:
        print()
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "eta.py")],
                             capture_output=True, text=True, timeout=900)
        for line in out.stdout.splitlines():
            if line.startswith("### "):
                print("  " + line[4:][:140])


if __name__ == "__main__":
    main()
