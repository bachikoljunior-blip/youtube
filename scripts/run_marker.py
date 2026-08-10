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
# **重複を防ぐためだけの窓。** 正規の間隔は60分なので、30分あれば
# 「同じ回の二重発火」だけを弾き、次の正規の回は通す。
#
# 最初 40分 にしていて、**11:31 に立てた子の次が 12:09（38分後）で飛ぶところだった。**
# 窓は「異常を弾く」ためのもので、**正常を弾いたらただの取りこぼし。**
# 何を弾きたいのかを先に決めてから幅を置くこと。
WINDOW_MIN = 30
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


def _append(rec: dict) -> str:
    MARKS.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False)
    old = MARKS.read_text(encoding="utf-8").splitlines() if MARKS.exists() else []
    old = [x for x in old if x.strip()]
    MARKS.write_text("\n".join((old + [line])[-KEEP:]) + "\n", encoding="utf-8")
    return line


def _records(kind: str) -> list[dict]:
    """`kind` の印を古い順に。**`kind` の無い古い行は `ran` とみなす。**"""
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
        if rec.get("kind", "ran") == kind:
            out.append(rec)
    return out


def spawned(sid: str) -> int:
    """**親が「子を立てた」と記録する。立てた直後に push すること。**

    2026-08-10、最初は子だけが印を打つ設計にしていた。**穴があった。**

        11:27  親が子を立てる。子は自分の器の中で印を打つ
        12:09  親が発火。**その印はまだ push されていないので見えない**
               → 「子は走っていない」と読んで、**2人目を立てる**

    **子の印はリポジトリ経由なので、子が最後に push するまで親に届かない。**
    走っている最中がちょうど見えない。**二重に立てない仕組みが、
    二重に立てる原因になっていた。**

    直し方は「誰が書くか」を入れ替えること。**立てた側がその場で書く。**
    親は他に仕事が無いので、書いてすぐ push できる。

    `list_sessions` の tags 絞り込みも試したが
    **「tags filter is not currently available」で使えなかった**ので、
    生きているセッションを問い合わせる道は今は無い。
    """
    line = _append({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": sid,
        "kind": "spawned",
    })
    print(f"[marker] 子を立てた印を付けました: {line}")
    print("         **この直後に commit と push をすること。**"
          "push しないと次の回に2人目が立ちます。")
    return 0


def write() -> int:
    """**子が「実際に走った」と記録する。**

    親の重複判定には使わない（上の `spawned` の理由）。
    使うのは **鎖が本当に周っているかの確認**。
    立てられただけで何もせず死ぬ子が続いたら、ここが止まる。
    """
    me = session_id() or "(不明)"
    if me == PARENT_SESSION:
        print("[marker] **親セッションからは走った印を付けません。**")
        print("         親が周を回すのは MCP が使えない回だけで、"
              "それを平常の心音として数えると異常が見えなくなります。")
        return 0
    line = _append({
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "session": me,
        "kind": "ran",
    })
    print(f"[marker] 走った印を付けました: {line}")
    return 0


def check(window_min: int = WINDOW_MIN) -> int:
    """**親の重複判定。** 見るのは `spawned`（親が自分で書いたもの）。"""
    recs = [r for r in _records("spawned") if r.get("session") != PARENT_SESSION]
    if not recs:
        print("[marker] **立てた印が1件もありません。** → 親は子を立てること。")
        return 1
    rec = recs[-1]
    try:
        then = datetime.fromisoformat(rec["at"])
    except (KeyError, ValueError):
        print(f"[marker] 印が読めません: {rec} → 親は子を立てること。")
        return 1
    age = (datetime.now(JST) - then).total_seconds() / 60
    if age <= window_min:
        print(f"[marker] **直前の子がまだ新しい**（{rec['session']} / "
              f"{age:.0f}分前 / 窓 {window_min}分）")
        print("         → 親は立てないこと。掃除だけして終える。"
              "**何もしないのが正常です。**")
        return 0
    print(f"[marker] 直前に立てた子は {age:.0f}分前（窓 {window_min}分）"
          f" → **親は子を立てること。**")
    # **立てても走っていないなら、それは別の異常。** ここで言う。
    ran = _records("ran")
    if ran:
        last_ran = datetime.fromisoformat(ran[-1]["at"])
        gap = (datetime.now(JST) - last_ran).total_seconds() / 60
        if gap > 180:
            print(f"  [!] **子は立っているのに、3時間以上どの子も走り終えていません**"
                  f"（最後に走った印 {ran[-1]['at']} / {gap:.0f}分前）。")
            print("      立てる前に `list_sessions` で子の状態を見ること。"
                  "`REQUIRES_ACTION` は止まっているという意味です。")
            print("      **なぜ止まったかを JOURNAL に書くこと。**")
    elif len(recs) >= 3:
        print(f"  [!] **{len(recs)}回 立てて、走り終えた子が1つもありません。**")
        print("      立て方そのものが間違っている疑い。"
              "`source_url` と `source_revision` を確かめること。")
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
    # **`spawned` と `ran` の両方から拾う。** 立てたが走らなかった子も畳む対象。
    for rec in _records("spawned") + _records("ran"):
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
    ap.add_argument("--write", action="store_true", help="子: 走った印を付ける")
    ap.add_argument("--spawned", metavar="ID",
                    help="親: 子を立てた印を付ける（**直後に push すること**）")
    ap.add_argument("--sweep", action="store_true",
                    help="畳んでよい子のIDを出す（親用）")
    ap.add_argument("--swept", nargs="+", metavar="ID",
                    help="畳み終えたセッションIDを記録する")
    ap.add_argument("--window", type=int, default=WINDOW_MIN)
    args = ap.parse_args(argv)
    if args.write:
        return write()
    if args.spawned:
        return spawned(args.spawned)
    if args.sweep:
        return sweep()
    if args.swept:
        return swept(args.swept)
    return check(args.window)


if __name__ == "__main__":
    raise SystemExit(main())
