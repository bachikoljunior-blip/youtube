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

長いセッションで判断が雑になるのを避けるため。

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

# 定期実行の間隔（分）。**実物は `list_triggers` で見ること。**
# ここは空きを警告するしきい値を出すためだけに持っています。
# 2026-08-15: 親が毎時（cron `9 * * * *`）になったので 60。
INTERVAL_MIN = 60
MARKS = Path(__file__).resolve().parent.parent / "data" / "runs.jsonl"
KEEP = 500

# **常駐の親。ここからの印は数えない。**
#
# 親は普段リポジトリを触らないので打つ機会が無いはずだが、
# 打てば「周が回っている」に見えてしまう。**異常を隠す方向の間違いなので、
# 規律ではなく機械で外す。**
#
# **親は交代します**（重くなったら新しい親に移す）。古いIDを消さずに足すこと。
PARENT_SESSIONS = {
    "session_01PXy8TiBxL1SM7AUc6XAMML",   # 〜2026-08-15
    "session_016PyeT6Afj5KzKQ9xkKE3Kx",   # 2026-08-15〜
}


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
        if rec.get("session") in PARENT_SESSIONS:
            continue
        out.append(rec)
    return out


def _append(rec: dict) -> str:
    MARKS.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False)
    old = [x for x in (MARKS.read_text(encoding="utf-8").splitlines()
                       if MARKS.exists() else []) if x.strip()]
    MARKS.write_text("\n".join((old + [line])[-KEEP:]) + "\n", encoding="utf-8")
    return line


def write() -> int:
    me = session_id() or "(不明)"
    if me in PARENT_SESSIONS:
        print("[marker] **親からは印を付けません。**"
              " 親が周を回すのは設計の否定なので、平常の心音として数えません。")
        return 0
    line = _append({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": me,
        "kind": "start",
    })
    print(f"[marker] 走った印を付けました: {line}")
    return 0


def ship(what: str) -> int:
    """**この回が「出したもの」を1行残す。**（2026-08-15 追加）

    オーナーの指示（原文）: **「子が、少しの作業で終わるの直して」**

    分析して日誌を書いて終わる回が続いていました（8/12〜8/15 の全部）。
    **文書に「小さくてよい」と書いてあったのが原因**なので、まず文書を直し、
    そのうえで**機械で確かめられる形**にしたのがこの印です。

    `scripts/stop_check.sh` が、start はあるのに ship が無いまま終わろうと
    したときに引き止めます。**引き止めるだけで、最後は通します**
    （止まったまま死ぬほうが、目標に対して確実に悪いため）。

    **何を ship と呼ぶか**（`docs/trigger_main.md` §4 の最低ライン）:

        upload   動画を1本、予約まで入れた
        means    手段の台帳（docs/MEANS.md）の1件を、実際に動かした
        verdict  期限の来た前提を、実データで判定した
        fix      実測で見つかった欠陥を塞いだ（道具・生成・投稿のどれか）

    **分析・日誌・文書の整理だけは ship ではありません。** それは前提であって、
    出したものではない。
    """
    me = session_id() or "(不明)"
    line = _append({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": me,
        "kind": "ship",
        "what": what,
    })
    print(f"[marker] 出したものを記録しました: {line}")
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
    print(f"[marker] 直近 {min(8, len(recs))}件:")
    for r in recs[-8:]:
        try:
            age = (now - datetime.fromisoformat(r["at"])).total_seconds() / 60
            kind = r.get("kind", "start")
            tail = f"  ← **出した**: {r['what']}" if kind == "ship" else ""
            print(f"    {r['at']}  {age:>5.0f}分前  {kind:<5} {r['session']}{tail}")
        except (KeyError, ValueError):
            print(f"    （読めない行）{r}")

    # **走った回のうち、何も出さずに終わった割合。**
    # ここが高いままなら、直すのは間隔ではなく1回の中身です。
    starts = [r for r in recs if r.get("kind", "start") == "start"]
    shipped = {r.get("session") for r in recs if r.get("kind") == "ship"}
    recent = starts[-10:]
    empty = [r for r in recent if r.get("session") not in shipped]
    if recent:
        print(f"  直近 {len(recent)}回のうち、**何も出さずに終わった回: {len(empty)}**")
        if len(empty) > len(recent) / 2:
            print("  [!] **半分以上が空回りです。** 分析だけで終える回が既定に"
                  "なっていないか疑うこと（`docs/trigger_main.md` §4 の最低ライン）。")

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
    ap.add_argument("--write", action="store_true", help="子: 走った印を付ける（最初に）")
    ap.add_argument("--ship", metavar="内容",
                    help="子: この回で出したものを記録する（最低ラインの1件）")
    args = ap.parse_args(argv)
    if args.ship:
        return ship(args.ship)
    return write() if args.write else show()


if __name__ == "__main__":
    raise SystemExit(main())
