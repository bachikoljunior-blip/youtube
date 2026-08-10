#!/usr/bin/env python3
"""子（毎時の回）が「実際に走った」ことを1行残す。

    python scripts/run_marker.py --write   # 子が最初に打つ
    python scripts/run_marker.py           # 直近の回がいつだったかを見る

## なぜ要るか

2026-08-10、オーナーの指示で定期実行を親子方式にした。

    親（毎時 :09・常駐）  **子を1つ立てて、終わった子を畳むだけ。他は何もしない**
    子（毎回あたらしい）  **その回の仕事を全部やって、自分を archive する**

> 毎回新しいセッション立ててそこで実行、終わったらアーカイブ
> **ここでしてた作業を全部子セッションにやらせる**

長いセッションで判断が雑になるのを避けるため（恒久指示 A12）。

**このファイルは「回が本当に周っているか」の記録です。**
親は使いません（親はリポジトリを触らない）。**読むのは子と、人。**

## 親の重複防止に使わないこと（**一度そう作って外した**）

最初は「子が印を打ち、親がそれを読んで二重に立てない」形にしていた。**穴があった。**

    11:27  親が子を立てる。子は**自分の器の中で**印を打つ
    12:09  親が発火。**その印はまだ push されていないので見えない**
           → 「子は走っていない」と読んで **2人目を立てる**

**子の印はリポジトリ経由なので、子が最後に push するまで親に届かない。**
走っている最中がちょうど見えない。

そのあと「親が立てた側で書く」形にしたが、**それも外した。**
親がリポジトリに commit/push する時点で、**親が働いている**。
オーナーの指示は「全部子にやらせる」なので、親は repo を触らない。

**いまの重複防止は `list_sessions` の `parent_session_id`。**
親は自分の子だけを正確に絞れるので、記録が要らない。

## だから、この記録の用途は1つだけ

**立ってはいるが、どの子も走り終えていない**という状態を見つけること。
親から見ると子は立っているので正常に見える。**周が回っているかは、
子が自分で残した印でしか分からない。**
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

# 定期実行の間隔（分）。**正本は `docs/TRIGGER.md` の cron `9 */6 * * *`。**
# ここは空きを警告するしきい値を出すためだけに持っています。
INTERVAL_MIN = 360
MARKS = Path(__file__).resolve().parent.parent / "data" / "runs.jsonl"
KEEP = 500

# **常駐の親。ここからの印は数えない。**
#
# 親は普段リポジトリを触らないので打つ機会が無いはずだが、
# 打てば「周が回っている」に見えてしまう。**異常を隠す方向の間違いなので、
# 規律ではなく機械で外す。**
PARENT_SESSION = "session_01PXy8TiBxL1SM7AUc6XAMML"


def session_id() -> str:
    """自分のセッションID。**推測しないこと。**

    `list_sessions` から名前で探すと、似た名前の別セッションを掴む事故になる
    （姉妹ループが同じ注意を書いている）。環境変数が正本。
    """
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    return ("session_" + raw[4:]) if raw.startswith("cse_") else raw


def _records() -> list[dict]:
    out = []
    if not MARKS.exists():
        return out
    for ln in MARKS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if rec.get("session") == PARENT_SESSION:
            continue
        out.append(rec)
    return out


def write() -> int:
    me = session_id() or "(不明)"
    if me == PARENT_SESSION:
        print("[marker] **親からは印を付けません。**"
              " 親が周を回すのは設計の否定なので、平常の心音として数えません。")
        return 0
    MARKS.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": me,
    }, ensure_ascii=False)
    old = [x for x in (MARKS.read_text(encoding="utf-8").splitlines()
                       if MARKS.exists() else []) if x.strip()]
    MARKS.write_text("\n".join((old + [line])[-KEEP:]) + "\n", encoding="utf-8")
    print(f"[marker] 走った印を付けました: {line}")
    return 0


def show() -> int:
    """直近の回を出す。**空きが大きければ、それが一番大事な観測。**"""
    recs = _records()
    if not recs:
        print("[marker] **印が1件もありません。** 子が一度も走り終えていない。")
        print("         立て方そのものが壊れている疑い"
              "（`source_url` と `source_revision` を確かめること）。")
        return 1
    now = datetime.now(JST)
    print(f"[marker] 直近 {min(5, len(recs))}件:")
    for r in recs[-5:]:
        try:
            age = (now - datetime.fromisoformat(r["at"])).total_seconds() / 60
            print(f"    {r['at']}  {age:>5.0f}分前  {r['session']}")
        except (KeyError, ValueError):
            print(f"    （読めない行）{r}")
    try:
        gap = (now - datetime.fromisoformat(recs[-1]["at"])).total_seconds() / 60
    except (KeyError, ValueError):
        return 1
    # **しきい値は間隔の2周ぶん。** 1周ぶんだと、正常に動いていても毎回鳴ります
    # （2026-08-10 に毎時→6時間おきへ変えたとき、180分のままだと**必ず鳴る**状態になった）。
    # **鳴りっぱなしの警告は、無い警告と同じです。**
    # 間隔を変えたら、ここも変えること（正本は `docs/TRIGGER.md` の cron）。
    if gap > INTERVAL_MIN * 2:
        print(f"  [!] **{gap:.0f}分（{gap / 60:.1f}時間）どの子も走り終えていません。**")
        print("      親から見ると子は立っているので、ここでしか気づけません。")
        print("      **なぜ止まったかを JOURNAL に書くこと。**")
        return 1
    print(f"  直近の回は {gap:.0f}分前。**周は回っています。**")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="子: 走った印を付ける")
    args = ap.parse_args(argv)
    return write() if args.write else show()


if __name__ == "__main__":
    raise SystemExit(main())
