#!/usr/bin/env python3
"""毎時の回が「実際に走ったか」を1行で残し、親がそれを読む。

    python scripts/run_marker.py --write            # 子が最初に打つ
    python scripts/run_marker.py --window 40        # 親: 二重に立てないための確認
    python scripts/run_marker.py --sweep            # 親: 畳んでよい子のIDを出す
    python scripts/run_marker.py --swept <ID> ...   # 親: 畳んだ記録

## なぜ要るか

2026-08-10、オーナーの指示で定期実行を
**「毎回新しいセッションを立てて、そこで実行し、終わったらアーカイブする」**に変えた。
長いセッションで判断が雑になるのを避けるため（A12）。
立て方は**eta改善ループと同じ**、常駐の親から `create_session` で子を立てる方式
（`create_new_session_on_fire` は姉妹ループ2件が「一度も起動しない」と実測済み）。

    親（毎時 :09・常駐）   子を1つ立てる。終わった子を畳む。**周は回さない**
    子（毎回あたらしい）   その回の仕事を全部やって、自分を archive する

**このファイルは、親が「もう子を立てたか」「どの子を畳んでよいか」を
知るためだけのもの。** 子の生存を親の記憶に持たせない（親も落ちる）。

## なぜ git のコミット時刻を使わないか

一度そうしようとした。**このブランチには姉妹ループも push する**（8/10 に実例）。
コミットがあること＝毎時の回が走ったこと、**ではない。**
**別のものを数えている指標を「生きている証拠」にしない。**

## 判定の窓

- **`--window 40`**（親が二重発火を避ける用）… 40分以内に子が始まっていれば立てない
- **既定 75 分**（鎖が死んでいないかの確認用）… 毎時＋余裕

**遅れて始まった回を「死んだ」と誤判定しない**ためで、
逆に2時間空いたら確実に気づく。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

JST = timezone(timedelta(hours=9))
MARKS = Path(__file__).resolve().parent.parent / "data" / "runs.jsonl"
WINDOW_MIN = 75
KEEP = 500

# **親セッション自身の印は、子の生存の証拠にしない。**
#
# 作った直後に踏みかけた。親の回が `--write` を打つと、
# **次の回の親が「もう子が走っている」と読んで、子を立てない。**
# 子が1度も動いていなくても、親どうしで生きているふりが成立してしまう。
# **自分の心音を他人の心音として数える形。**
#
# 規律（「親は --write しない」）で守らない。**機械で外す。**
PARENT_SESSION = "session_01PXy8TiBxL1SM7AUc6XAMML"


def session_id() -> str:
    """自分のセッションID。**推測しないこと。**

    `list_sessions` から探すと、似た名前の別セッションを掴む事故になる
    （姉妹ループが同じ注意を書いている）。環境変数が正本。
    """
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    return ("session_" + raw[4:]) if raw.startswith("cse_") else raw


def write() -> int:
    me = session_id() or "(不明)"
    if me == PARENT_SESSION:
        print("[marker] **親セッションからは印を付けません。**")
        print("         付けると、次の親が自分の心音を子のものと読み違えて、"
              "子を立てなくなります。")
        return 0
    MARKS.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": me,
    }, ensure_ascii=False)
    old = MARKS.read_text(encoding="utf-8").splitlines() if MARKS.exists() else []
    old = [x for x in old if x.strip()]
    MARKS.write_text("\n".join((old + [line])[-KEEP:]) + "\n", encoding="utf-8")
    print(f"[marker] 走った印を付けました: {line}")
    return 0


def last() -> dict | None:
    """**親自身の印は読み飛ばす**（上の `PARENT_SESSION` の理由）。"""
    if not MARKS.exists():
        return None
    for ln in reversed([x for x in MARKS.read_text(encoding="utf-8").splitlines() if x.strip()]):
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if rec.get("session") == PARENT_SESSION:
            continue
        return rec
    return None


def check(window_min: int = WINDOW_MIN) -> int:
    rec = last()
    if rec is None:
        print("[marker] **印が1件もありません。** 子はまだ一度も走っていない。")
        print("         → 親は子を立てること。")
        return 1
    try:
        then = datetime.fromisoformat(rec["at"])
    except (KeyError, ValueError):
        print(f"[marker] 印が読めません: {rec} → 親は子を立てること。")
        return 1
    age = (datetime.now(JST) - then).total_seconds() / 60
    if age <= window_min:
        print(f"[marker] **子は走っています。** 最後の回 {rec['at']}（{age:.0f}分前 / "
              f"窓 {window_min}分）")
        print("         → 親は立てないこと。掃除だけして終える。"
              "**何もしないのが正常です。**")
        return 0
    print(f"[marker] **子が走っていません。** 最後の回 {rec['at']}（{age:.0f}分前 / "
          f"窓 {window_min}分）")
    print("         → 親は子を立てること。**75分以上あいていたなら、"
          "なぜ止まったかを JOURNAL に書くこと。**")
    return 1


SWEPT = MARKS.parent / "archived_sessions.json"
SWEEP_AGE_MIN = 90


def sweep() -> int:
    """**畳んでよい子のIDだけを出す。** 親が掃除に使う。

    子は自分で `archive_session` を呼ぶ。**呼べなかった子のための保険。**
    畳めないとコンテナを掴んだまま溜まる。オーナーの依頼はそこも含んでいる。

    **`list_sessions` から名前で探さないこと。** 姉妹ループが
    「似た名前の別セッションを畳む事故になる」と書いていて、そのとおり。
    **ここで出すのは `runs.jsonl` に子が自分で名乗ったIDだけ**なので、
    毎時の回以外を掴むことがない。

    そのうえで **90分より新しいものは出さない。**
    走っている最中の回を畳むと、その回の仕事が消える。
    """
    done = set()
    if SWEPT.exists():
        try:
            done = set(json.loads(SWEPT.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            done = set()
    now = datetime.now(JST)
    seen, out = set(), []
    if MARKS.exists():
        for ln in MARKS.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            sid = rec.get("session", "")
            if (not sid.startswith("session_") or sid == PARENT_SESSION
                    or sid in done or sid in seen):
                continue
            try:
                age = (now - datetime.fromisoformat(rec["at"])).total_seconds() / 60
            except (KeyError, ValueError):
                continue
            if age >= SWEEP_AGE_MIN:
                seen.add(sid)
                out.append(sid)
    for sid in out:
        print(sid)
    if not out:
        print(f"[marker] 畳む対象はありません（{SWEEP_AGE_MIN}分より古い未処理の回のみ対象）",
              file=sys.stderr)
    return 0


def swept(ids: list[str]) -> int:
    done = []
    if SWEPT.exists():
        try:
            done = json.loads(SWEPT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            done = []
    for sid in ids:
        if sid not in done:
            done.append(sid)
    SWEPT.parent.mkdir(parents=True, exist_ok=True)
    SWEPT.write_text(json.dumps(done[-KEEP:], ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"[marker] 畳んだ記録に {len(ids)}件 足しました（累計 {len(done)}件）")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="走った印を付ける")
    ap.add_argument("--sweep", action="store_true",
                    help="畳んでよい子のIDを出す（親用）")
    ap.add_argument("--swept", nargs="+", metavar="ID",
                    help="畳み終えたセッションIDを記録する")
    ap.add_argument("--window", type=int, default=WINDOW_MIN)
    args = ap.parse_args(argv)
    if args.write:
        return write()
    if args.sweep:
        return sweep()
    if args.swept:
        return swept(args.swept)
    return check(args.window)


if __name__ == "__main__":
    raise SystemExit(main())
