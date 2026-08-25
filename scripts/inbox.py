#!/usr/bin/env python3
"""受け取り帳の入口。中身と理由は `src/inbox.py` を読むこと。

    python scripts/inbox.py --open "<運ばれてきた本文>"   # **受け取った直後に打つ**
    python scripts/inbox.py                               # 開いているものを見る
    python scripts/inbox.py --all
    python scripts/inbox.py --close <id> --note "<何をしたか>"

**`--open` は自分で commit + push します**（`--no-push` で止められます）。
押すところまでが1件です —— 手元に書いただけのものは、
**コンテナが消えれば無かったことになります。**
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import inbox  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="運ばれてきた依頼を、着いた瞬間に残す")
    ap.add_argument("--open", metavar="原文", help="受け取った依頼を1件足す")
    ap.add_argument("--source", default="owner", help="どこから来たか（既定: owner）")
    ap.add_argument("--close", metavar="ID", help="閉じる（先頭一致でよい）")
    ap.add_argument("--note", default="", help="--close のとき、何をしたか1行")
    ap.add_argument("--all", action="store_true", help="閉じたものも出す")
    ap.add_argument("--no-push", action="store_true", help="commit/push をしない")
    args = ap.parse_args()

    if args.open and args.close:
        print("[!] --open と --close は一緒に打たないこと", file=sys.stderr)
        return 2

    if args.open:
        rec = inbox.add(args.open, source=args.source)
        n = next((it["deliveries"] for it in inbox.items() if it["id"] == rec["id"]), 1)
        print(f"受け取り帳に足しました: {rec['id']}（{n}回目）")
        if n > 1:
            print("  **同じ依頼が繰り返し運ばれています。**"
                  "前の回は途中で落ちたか、閉じ忘れています。")
        if args.no_push:
            print("  [!] **push していません。** ここで死ぬと消えます。")
            return 0
        ok, detail = inbox.git_save(f"inbox: 依頼を受け取った（{rec['id']}）")
        if not ok:
            print("  [!] **push できませんでした。手で push すること。**", file=sys.stderr)
            print(f"      {detail}", file=sys.stderr)
            return 1
        print("  push まで済み。**ここで死んでも、次の子が拾えます。**")
        return 0

    if args.close:
        try:
            rec = inbox.close(args.close, args.note)
        except KeyError:
            print(f"[!] 開いている依頼に {args.close} がありません", file=sys.stderr)
            print(inbox.render(), file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"[!] {exc}", file=sys.stderr)
            return 2
        print(f"閉じました: {rec['id']}")
        if args.no_push:
            return 0
        ok, detail = inbox.git_save(f"inbox: 依頼を閉じた（{rec['id']}）")
        if not ok:
            print(f"  [!] push できませんでした: {detail}", file=sys.stderr)
            return 1
        return 0

    print(inbox.render(show_all=args.all))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
