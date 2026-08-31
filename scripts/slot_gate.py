#!/usr/bin/env python3
"""**今日から数日のうちに「予約が0本の日」が在るなら、その回を引き止める。**（**API 0単位**）

    python scripts/slot_gate.py          # いま何日 空いているか（人が読む）
    python scripts/slot_gate.py --gate   # 空いていたら exit 2 ＋ 理由を印字（フック用）

読むのは `data/uploaded.jsonl`（`src.dupes.ledger_rows()`）だけです。
**`scripts/status.py` と同じ関数から数えます** —— 同じ与件で2つの道具が
別のことを言うのが、この repo でいちばん多い壊れ方だからです。

## なぜ要るか（2026-09-01・最適化の回。**実測でここが律速でした**）

オーナー規則1は「公開は1日1本」（`src/house_rule.py`）。
規則が入ってから、**主実行が `upload` を出した回は 2日で1件**でした
（`status._upload_pace()`・要るのは 2件）。そして控えには

    2026-09-03 〜 2026-09-11 の **9日 が0本**（その先 09/12 以降に 267本）

が並んでいます。**この9日は投稿が途切れます**（`CLAUDE.md`「途切れるのが最大の損失」）。

### なぜ主実行はそれを選ばなかったのか（**印字の問題ではありません**）

`docs/trigger_main.md` §4「何を選ぶか」の1番目は、こう書いてありました:

    1. **予約が5日先を切っている → `upload`**

この判定が見ているのは **`ahead[-1]`（予約のいちばん後ろ）** です。
いま控えのいちばん後ろは **10/10（39日 先）**。だから条件は**偽**で、
**9日 が真っ暗でも、この規則は `upload` を選ばせません。**

**「どこまで届いているか」と「明日は埋まっているか」は別の問いです。**
作り置き 267本 が先のほうに固まっていると、前者だけが満たされます ——
規則2（作り置きなし）が入った日から、**この判定は構造的に外れています。**

### なぜ印字ではなく門か

`scripts/status.py` は 2026-09-01 06:1x に、この穴と「埋める道は
その日の回が `upload` を1本 出すことだけ」まで**正しく印字していました。**
それでも `upload` は増えていません。**700行の本文の 340行目**に在るからです
（`scripts/stop_check.sh` の 271行目に同じ教訓:
「**印字に格上げしただけでは、同じ穴です —— 出ていても、読まずに終われる**」）。

この repo は既に7つの門を持っています（何も出していない／予測へ入れ直す／
満ちた待ち／期限のずれ／次の回を立てる…）。**そのどれもが帳面の話で、
`CLAUDE.md` が「最大の損失」と呼んでいるものだけが門になっていませんでした。**

## 先読みの日数（`LEAD_DAYS`）を、なぜ 2日 にするか

- `scripts/queue_lag.py` の実測「**いま作った本が予約されるのは 1〜1日後**」
- Data API の日枠が戻るのは **JST 16:00**（尽きた回は次の窓まで撃てない）

**1日 では、日枠が尽きた回に取り返す余地がありません。** 2日 あれば、
枠が戻る窓を1回またげます。逆に長くすると、**穴の先の作り置きを
「詰めろ」と言い出すのと同じ形**になり、規則2 とぶつかります
（この門は *詰めろ* とは一度も言いません。言うのは **1本 作って入れろ** だけです）。

## 規則2 とぶつからないこと

この門が要求するのは **1回に1本**で、埋めるのは **`LEAD_DAYS` 先の1日**だけです。
9日 ぶんをいま作らせません（それが作り置きです）。
**毎日 1本ずつ、2日 先の枠を埋め続ける**のが、この門の定常状態です。

## 覆る条件

- **オーナーが規則1を外したら**、分母（1日1本）の意味が変わります。
  そのときは「0本の日」ではなく「上限に足りない日」を数えること。
- `data/uploaded.jsonl` は**上限側の見積り**です（取り消した本も残る）。
  つまりこの門は**空を見落とす側**に外れます —— 鳴ったら本物です。
  逆に「鳴っていないから埋まっている」は言えません。
- 予約を**手で** YouTube Studio から動かすと控えと食い違います。
  そのときは `scripts/reschedule.py --list` が正。
- **3回で通します**（`scripts/stop_check.sh` 側）。日枠が尽きていて
  本当に撃てない回を、永久に止めないため。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JST = timezone(timedelta(hours=9))

#: **何日 先まで見るか。** 0 ＝ 今日だけ。2 ＝ 今日・明日・明後日。
#: 理由は上の註（作った本が予約に入るまで 1日／日枠が戻るのは JST 16:00）。
LEAD_DAYS = 2


def per_day(rows: list[dict] | None = None) -> dict | None:
    """**JST の暦日ごとの予約本数。** `{date: 本数}`（予約のある日だけ）。

    `scripts/status.py::per_day_counts()` と**同じ数え方**にしてあります
    （未来の `at` だけ・JST へ直してから日で数える）。
    """
    if rows is None:
        # **控えそのものが読めない回は、鳴らしません。**
        # 「測っていないことを、落とす側に倒さないこと」（`src/house_rule.is_stockpile`
        # の註と同じ判断）。**行が在って未来が0本**なら、それは本物の空です。
        if not (ROOT / "data" / "uploaded.jsonl").exists():
            return None
        try:
            from src import dupes                               # noqa: PLC0415
            rows = [r for r in dupes.ledger_rows() if r.get("at")]
        except Exception:                                       # noqa: BLE001
            return None
        if not rows:
            return None
    now = datetime.now(timezone.utc)
    out: dict = {}
    for r in rows:
        at = str(r.get("at") or "")
        if not at:
            continue
        try:
            t = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if t <= now:
            continue
        d = t.astimezone(JST).date()
        out[d] = out.get(d, 0) + 1
    return out


def empty_days(rows: list[dict] | None = None, today=None, lead: int | None = None) -> list:
    """**今日から `lead` 日ぶんのうち、予約が0本の暦日**（早い順）。

    **0本の日は `per_day` の鍵に入っていません。** だから暦を歩いて数えます
    （鍵を一覧の元にしたのが `status.py` 側の元の欠陥でした）。
    """
    per = per_day(rows)
    if per is None:
        return []
    today = today or datetime.now(JST).date()
    n = LEAD_DAYS if lead is None else lead
    return [today + timedelta(days=i) for i in range(n + 1)
            if per.get(today + timedelta(days=i), 0) == 0]


def tail_days(rows: list[dict] | None = None, today=None) -> int:
    """**穴の先に、まだ何日ぶん 予約が並んでいるか**（＝作り置きの厚み）。

    これが 0 なら「まだ作っていない」、正なら「**作ってあるのに出さない**」です。
    門の文面がその2つで変わるので、ここで数えます。
    """
    per = per_day(rows)
    if not per:
        return 0
    today = today or datetime.now(JST).date()
    return sum(1 for d in per if d > today + timedelta(days=LEAD_DAYS))


def lines(rows: list[dict] | None = None, today=None) -> list[str]:
    """門が印字する行。**空いていなければ空リスト。**"""
    today = today or datetime.now(JST).date()
    gap = empty_days(rows, today)
    if not gap:
        return []
    per = per_day(rows) or {}
    cells = " ".join(
        f"{(today + timedelta(days=i)):%m/%d}={per.get(today + timedelta(days=i), 0)}"
        for i in range(LEAD_DAYS + 1))
    out = [
        f"**予約が0本の日が、今日から{LEAD_DAYS}日 のうちに {len(gap)}日 あります: "
        + " ".join(f"{d:%m/%d}" for d in gap) + "**",
        f"  今日から{LEAD_DAYS + 1}日: {cells}   （規則1 ＝ **1日1本**・`src/house_rule.py`）",
        "  **その日は投稿が途切れます。**「途切れるのが最大の損失」（`CLAUDE.md`）。",
    ]
    tail = tail_days(rows, today)
    if tail:
        out.append(
            f"  **その先には、まだ {tail}日 ぶんの予約が並んでいます** ——"
            "つまりこの穴は「まだ作っていない」ではなく**「作ってあるのに出さない」**です。"
            "**それでも詰めないこと** —— `--compact` は `at` しか動かさないので、"
            "詰めた本は作り置きのままで `pool_drain` が同じ本を外します"
            "（`src/house_rule.is_stockpile`）。")
    out += [
        "",
        f"**この回でやること: {gap[0]:%m/%d} の枠に入る1本を、予約まで入れること**"
        "（`docs/trigger_main.md` §5）。**1本だけです**（9日ぶん作るのが作り置きです）:",
        "",
        "    python -m src.pipeline --script build/short.json --topic s-<名前> --short",
        f"    python scripts/upload_only.py s-<名前> \"\" <時>    # 第3引数が予約時刻（JST）",
        "    python scripts/inspect_build.py s-<名前>          # **投稿前に必ず目で見る**",
        "",
        "**撃てないなら**（Data API の日枠 ＝ JST 16:00 に戻る／`AUTOMATION_PAUSED.md`）、"
        "**その理由を `docs/JOURNAL.md` に書いてから終わること。**",
    ]
    return out


def main(argv: list[str]) -> int:
    gate = "--gate" in argv
    out = lines()
    if not out:
        if not gate:
            print(f"予約が0本の日は、今日から{LEAD_DAYS}日 のうちにありません。")
        return 0
    print("\n".join(out))
    return 2 if gate else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
