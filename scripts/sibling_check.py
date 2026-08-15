#!/usr/bin/env python3
"""兄弟の子が生きているかを、**判断ではなく計算で**答える。

    python scripts/sibling_check.py --sessions <file>            # 回の最初（§2）
    python scripts/sibling_check.py --sessions <file> --phase spawn   # §6 (f) の直前

`<file>` は MCP の `list_sessions limit=25 mine=true` の返りをそのまま保存したもの。
`scripts/quota.py --ingest` に渡すのと**同じファイルで構いません**。

## なぜ作ったか（2026-08-15、自走の1周目で踏んだ）

`docs/trigger_main.md` §6 (f) で「子が自分で次の子を立てる」形にした回
（`bcf433e`）の**次の子が、これに引っかかりました。** 私です。

§2 はこう書いてありました。

    tags に "youtube-hourly" を含む行のうち、**自分以外**に
    PENDING / RUNNING / IDLE があるか
    → いたら created_at を比べて、**自分のほうが新しければこの場で畳む**

**自走した子は、この条件に必ず当たります。**

    04:59:50  前の子が起きる
    05:09:01  前の子が §6 (f) で**私を立てる**      ← ここで私が生まれる
    05:09:26  前の子はまだ RUNNING（残りは (h) の archive だけ）
    05:09:52  私が §2 を見る → **兄弟が RUNNING、しかも私のほうが新しい**
              → 「この場で畳む」

**立てた側は必ず自分より古く、立てた瞬間はまだ生きています。**
§6 (f) は archive の**前**に置いてあるので（止まっても失うのが archive だけで済むように）、
この重なりは事故ではなく**毎回起きます。**

畳む側は §6 (a)〜(e) を飛ばすので、**次の子も立てません。**
つまり **1周目で鎖が終わり**、親の毎時 cron だけが残ります。
`bcf433e` が消しにきた「48%の空転」が、そのまま戻るところでした。

## 直し方

**自分を立てた相手（`parent_session_id`）を、生死の数から除きます。**

除いて安全な理由は、§6 の順番そのものです。**(f) は (a)〜(e) の後ろ**なので、
私を立てた時点で向こうは記録も push も題名も済ませています。
**残っているのは archive だけで、生成も予約もぶつかりません。**
向こうが詰まって IDLE のまま残っても同じです（何も出せないので害になりません）。

**`parent_session_id` で「絞る」のは今も禁止です**（8/15 に直した理由は §2 のとおり、
孫の親IDが親ではなく子になるため、親IDで絞ると兄弟の半分が見えない）。
ここでやっているのは**絞り込みではなく、1件の除外**です。向きが逆なので両立します。

## 終了コード

    0  進んでよい
    1  返りの中に自分がいない ＝ ファイルが古い。取り直すこと
    2  （`--phase start`）自分より古い兄弟が走っている。この場で畳む
    3  （`--phase spawn`）立てない。兄弟が生きているか、枠が警告帯／閉じている
    4  （`--phase start`）続けてよい。ただし upload は選ばない
    5  （`--phase spawn`）**まだ早い。**表示された秒数だけ待って、
       `list_sessions` を取り直して**この検査からやり直す**（2026-08-15）

## 速さも見ます（2026-08-15 に足した）

**`--phase spawn` は、枠より先に「速すぎないか」を見ます。** 目盛りは
`scripts/quota.py --pace`（`data/usage.jsonl` の%を誕生数で割ったもの）。

**枠が `allowed` でも速すぎることはあります。** `allowed` は「まだ閉じていない」
としか言っていません。閉じてから気づくのでは遅く、8/12〜8/14 はそれで58時間
止まりました。**閉じる前に均すのがここの仕事です。**

## この道具が答えないこと

**「向こうが本当に畳んだか」は見ていません。** 待たない作りです（§2 の
「畳んだことを確認してから走り出す作りにはしない」）。待つと、向こうが
詰まったときにこちらも止まります。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TAG = "youtube-hourly"
LIVE = ("PENDING", "RUNNING", "IDLE")
# **枠が閉じているとき自走しない**（§6 (f) 2）。両方の窓を見る。
WINDOWS = ("five_hour", "seven_day")
OK = "allowed"

#: **予約の在庫がこの日数を切ったら、間隔の下限より生成を優先する**
#: （`docs/TRIGGER.md` の「覆る条件②」。2026-08-16 に機械へ入れた）。
#:
#: この文は 8/15 から `docs/TRIGGER.md` に2か所書いてあり、
#: **申し送りも8回運びました。文書にしか無いものは、読み飛ばせば効きません。**
#: 実際、この間ずっと `--phase spawn` は在庫を1度も見ていません。
#:
#: 止まるのと出せなくなるのとでは、**出せなくなるほうが痛い** ——
#: 間隔を詰めて枠を早く使い切っても、**予約が埋まっていれば公開は続きます**。
#: 逆に在庫が尽きると、枠がいくら余っていても投稿が途切れます。
RUNWAY_FLOOR_DAYS = 14


def runway_days(now: datetime) -> float | None:
    """**予約が何日先まで埋まっているか。** 読めなければ `None`。

    見るのは `data/uploaded.jsonl`（上げた瞬間に1行。2026-08-16 02:5x に入った控え）。
    **API を叩きません** —— この検査は archive の直前に走るので、
    ここで口を叩くと、429 で読めなかった回に鎖が止まります。

    **ずれる向きを選んであります。** 控えは「上げたときの予約時刻」なので、
    あとで外した本（`reschedule.py --unschedule`）が残り、**在庫は多めに出ます。**
    多めに出れば「まだ余裕がある」＝**いままでどおり待つ**になるので、
    読み違えても悪化しません。少なめに出るほうが危ない（枠を余計に食う）ので、
    この向きでよい。
    """
    path = Path(__file__).resolve().parent.parent / "data" / "uploaded.jsonl"
    if not path.exists():
        return None
    latest = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            at = parse_iso(json.loads(line).get("at"))
        except Exception:
            continue
        if at and (latest is None or at > latest):
            latest = at
    if latest is None:
        return None
    return (latest - now).total_seconds() / 86400


def my_session_id() -> str | None:
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID") or ""
    raw = raw.strip()
    if not raw:
        return None
    return "session_" + raw[len("cse_"):] if raw.startswith("cse_") else raw


def iter_sessions(blob):
    """`list_sessions` の返りは入れ子が一定しないので、素直に掘る。"""
    if isinstance(blob, dict):
        if "id" in blob and "created_at" in blob:
            yield blob
            return
        for value in blob.values():
            yield from iter_sessions(value)
    elif isinstance(blob, list):
        for item in blob:
            yield from iter_sessions(item)


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        blob = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise SystemExit("JSON として読めませんでした。MCP の返りをそのまま渡すこと。")
        blob = json.loads(m.group(0))
    return list(iter_sessions(blob))


def is_live(sess: dict) -> bool:
    status = str(sess.get("session_status") or "")
    return any(s in status for s in LIVE)


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def rate_limits(sessions: list[dict], now: datetime | None = None) -> dict[str, dict]:
    """窓ごとに**いちばん新しい観測**を取る。**ただし切れた観測は捨てる。**

    2つ、実データで踏んだ穴があります（2026-08-15）。

    **1. 窓を混ぜない。** `list_sessions` は行ごとに、そのとき効いていた窓を返します。
    8月12日の行には `seven_day`、いまの行には `five_hour` が入っています。
    まとめて見ると「閉じている」が永久に残ります。

    **2. `resetsAt` が過ぎた観測は、いまについて何も言っていません。**
    ここが本題です。1 だけ直して実データに掛けたら、**まだ止まりました。**
    いちばん新しい `seven_day` の観測が 8/12 22:53 の `rejected` で、
    その `resetsAt` は **8/15 07:00 —— すでに過ぎています。**
    枠はそこで回復しており、**あの行は3日前の、しかも別の期間の話**です。
    捨てないと、`seven_day` の新しい観測が返ってくるまで
    （＝週枠が再び効き始めるまで）**二度と自走できません。**

    切れた観測しか無い窓は「観測なし」として扱います。
    **「閉じている」とも「余裕がある」とも読みません。**
    """
    now = now or datetime.now(timezone.utc)
    latest: dict[str, tuple[datetime, dict]] = {}
    for sess in sessions:
        rli = (sess.get("external_metadata") or {}).get("rate_limit_info") or {}
        window = rli.get("rateLimitType")
        seen = parse_iso(sess.get("updated_at"))
        if not window or not seen:
            continue
        resets = rli.get("resetsAt")
        if isinstance(resets, (int, float)):
            if datetime.fromtimestamp(resets, timezone.utc) <= now:
                continue                  # その期間はもう終わっている
        if window not in latest or seen > latest[window][0]:
            latest[window] = (seen, rli)
    return {w: rli for w, (_, rli) in latest.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sessions", required=True,
                    help="list_sessions の返りを保存したファイル")
    ap.add_argument("--me", default=None, help="自分の session_id（既定は環境変数から）")
    ap.add_argument("--phase", choices=("start", "spawn"), default="start",
                    help="start=回の最初（§2） / spawn=次の子を立てる直前（§6 (f)）")
    args = ap.parse_args()

    me = args.me or my_session_id()
    if not me:
        print("**自分の session_id が分かりません。** --me で渡すこと。")
        return 1

    sessions = load(Path(args.sessions))
    by_id = {s.get("id"): s for s in sessions}
    mine = by_id.get(me)
    if not mine:
        print(f"**返りの中に自分（{me}）がいません。**")
        print("  `list_sessions` を取り直すこと。古いファイルを使い回していませんか。")
        return 1

    spawner = mine.get("parent_session_id")
    born = parse_iso(mine.get("created_at"))

    siblings = []
    for sess in sessions:
        if sess.get("id") == me:
            continue
        if TAG not in (sess.get("tags") or []):
            continue
        if not is_live(sess):
            continue
        siblings.append(sess)

    excused = [s for s in siblings if s.get("id") == spawner]
    rivals = [s for s in siblings if s.get("id") != spawner]

    print(f"自分: {me}  生 {born.isoformat() if born else '不明'}")
    if excused:
        print(f"立てた相手: {spawner} —— **数に入れません**")
        print("  §6 (f) は (a)〜(e) の後ろなので、向こうに残っているのは archive だけです。")
    elif spawner:
        print(f"立てた相手: {spawner}（もう生きていません）")

    if not rivals:
        print(f"生きている兄弟: **0件**（{TAG}）")
    else:
        print(f"生きている兄弟: **{len(rivals)}件**（{TAG}）")
        for s in rivals:
            print(f"  {s.get('id')}  生 {s.get('created_at')}  {s.get('session_status')}")

    if args.phase == "spawn":
        # --- 速すぎないか（2026-08-15） --------------------------------
        # **これを一番先に見る。** 待っているあいだに兄弟も枠も変わるので、
        # 先に枠を調べても答えが古くなる。**待ってから調べ直すのが正しい順。**
        #
        # 見ているのは「誕生から誕生まで」。§6 (f) はここで撃つので、
        # **`now - 自分の誕生` が、そのまま次の間隔**になる。
        # 1周が長かった回は待たない（もう間隔が空いている）。
        floor = None
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from quota import recommended_floor_minutes
            floor = recommended_floor_minutes()
        except Exception as exc:                 # 計器が壊れても鎖は止めない
            print(f"速さ: **測れませんでした**（{exc}）。間隔は空けません")
        now = datetime.now(timezone.utc)
        runway = runway_days(now)
        # **在庫が薄いときは、間隔の下限より生成を優先する**（`docs/TRIGGER.md` 覆る条件②）。
        # 枠を早く使い切っても、予約が埋まっていれば公開は続きます。
        # 在庫が尽きたら、枠がいくら余っていても投稿が途切れます。**痛みの大きさが違う。**
        if runway is None:
            print("在庫: **読めませんでした**（`data/uploaded.jsonl`）。下限はそのまま効かせます")
        else:
            print(f"在庫: 予約は **{runway:.1f}日先**まで（下限を外す境目は {RUNWAY_FLOOR_DAYS}日）")
            if runway < RUNWAY_FLOOR_DAYS and floor:
                print(f"  → **間隔の下限 {floor:.0f}分を外します。**"
                      "在庫が薄いので、生成の回数のほうが目標に近い。")
                floor = None

        if floor and born:
            waited = (now - born).total_seconds() / 60
            if waited < floor:
                left = floor - waited
                print()
                print(f"**まだ立てないこと。** 誕生から {waited:.0f}分 / "
                      f"持続できる間隔は **{floor:.0f}分**（`quota.py --pace`）")
                print(f"  **{left * 60:.0f}秒 待ってから、"
                      "`list_sessions` を取り直して、この検査をやり直すこと。**")
                print(f"      Bash(run_in_background=True): sleep {left * 60:.0f}")
                print("  **前倒しに意味はありません。** 速く回しても週の枠は増えず、"
                      "先に使い切ればリセットまで1回も起きられません"
                      "（8/12〜8/14 の58時間）。**待ちは投稿を減らしません** —— "
                      "予約が埋まっていれば、起きなくても公開されます。")
                return 5
            print(f"速さ: 誕生から {waited:.0f}分 ≥ 下限 {floor:.0f}分 —— 待ち不要")

        limits = rate_limits(sessions)
        bad, seen_windows, blind = [], [], []
        for window in WINDOWS:
            rli = limits.get(window)
            if not rli:
                # **観測が無いことを「閉じている」と読まない。**`list_sessions` は
                # そのとき効いている窓しか返さないことがあり、両方そろう保証はない。
                # 読めなかったことを理由に回を止めない（§2「割り引いて読むこと」）。
                print(f"枠 {window}: **観測なし**（この返りには出ていません。閉鎖とは読みません）")
                blind.append(window)
                continue
            status = rli.get("status")
            mark = "" if status == OK else "  ← **立てない**"
            print(f"枠 {window}: {status}{mark}")
            seen_windows.append(window)
            if status != OK:
                bad.append(window)
        if rivals:
            print()
            print("**立てないこと。** 生きている兄弟がいます（親の毎時 cron が拾います）。")
            return 3
        if bad:
            print()
            print("**立てないこと。** 枠が " + " / ".join(bad) + " で警告帯か閉じています。")
            print("  削るのは1回の中身ではなく間隔です。毎時 cron に戻すだけで足ります。")
            return 3
        print()
        ok = " / ".join(seen_windows) if seen_windows else "観測できた窓なし"
        print(f"**立ててよい。** 兄弟0件・{ok} は allowed。")
        if blind:
            print("  観測できなかった窓: " + " / ".join(blind)
                  + "（**余裕があるとも尽きたとも読めません**）")
        return 0

    older = [s for s in rivals
             if (parse_iso(s.get("created_at")) or datetime.max.replace(tzinfo=timezone.utc)) < (born or datetime.max.replace(tzinfo=timezone.utc))]
    if older:
        print()
        print("**この場で畳むこと。** 自分より古い兄弟が走っています（古いほうが勝つ）。")
        print("  §6 (a)〜(e) は要りません。何も出していないので記録することがありません。")
        return 2
    if rivals:
        print()
        print("**続けてよい。ただし upload は選ばないこと**（§2 (2)）。")
        print("  means / verdict / fix に切り替える。向こうが自分で畳みます。")
        return 4
    print()
    print("**続けてよい。** ぶつかる相手はいません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
