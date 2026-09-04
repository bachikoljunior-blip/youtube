#!/usr/bin/env python3
"""**題とサムネだけが落ちている本を、焼き直さずに直す。**

    python scripts/metadata_fix.py <動画ID> [--dry-run] [--no-api]

## なぜ要るか（2026-09-04 21:xx・最適化の回に実測で踏んだ）

09-04 の ship は **65件**（`data/runs.jsonl`）。うち `fix` が **41件**、
`--moves` が 0 以外 は **0件**。同じ日の決めは **14回、全部 長尺**で、
焼き直しが動画IDを **4つ** 捨てました::

    Ec-j1-W4nqw → O_lfBxB7S8Q → XwB8nxtN5D8 → e6sLHLmPhrk

**4本とも、落ちた脚は `(4) 題・サムネ` の同じ2件でした**（API 0単位・実測）::

    題      【年金の受け取り方】…      ← 【 】が題材（相手でも場面でもない）
    kicker  「75歳まで生きた場合・年180万円」全角17文字（門は11文字）

同じ時刻の**手元の台本**は `daily_pick.draft_legs()` = **[]** ＝ 4脚とも ○
（題は【60歳以上の方へ】に直っている）。**直っているのに、門は言い続けます。**

### 算が言っています（意見ではありません）

    焼き 1回        **55〜90分**
    直しが降る間隔   09-04 の commit で **21分 / 26分 / 30分 / 91分**

**直しのほうが焼きより速いので、焼き上がった控えは必ず古い。**
`untreated_slot_block()` は控え（`pick_legs`）を見て「焼き直せ」と言い、
`ahead_sweep` が `rebake_pending` に倒す。焼くあいだにまた直しが降る ——
**`pick_legs` は `draft_legs` に永久に追いつけません。**
出口は「枠の直前に、直っていない本が落ちる」しかありませんでした
（09-04 の `1huadpEk6HY` が実物: 脚3本 ✗ のまま公開・齢12時間で **2回**）。

## 出口

`(4)` が見るのは `title` と `thumbnail_kicker` / `thumbnail_line*` ——
**どれも動画の中身ではなく metadata** です。**20分の動画を4回 焼き直して
直そうとしていたのは、題の文字列 1本 でした。**

この道具は `daily_pick.metadata_fix_plan()`（手元の台本が 4脚とも ○ のときだけ
出る）を読んで、順に撃ちます::

    1. 控え `data/critique_queue/<ID>.script.json` の title / thumbnail_* を
       手元の台本に合わせる                                    **API 0単位**
    2. `refresh_thumbnail.rebuild_stash(<ID>)` で控えの絵を焼き直す  **API 0単位**
    3. `retitle.main(<ID>, title)` で実物の題を差し替える            **50単位**
    4. `refresh_thumbnail.push_missing(only=<ID>, force=True)` で絵を載せる **50単位**

**1 を先にやること。** `rebuild_stash` は控えの台本を読むので、
合わせる前に焼くと古い kicker のまま焼けます。

## 覆る条件

- `outside_title_problems` が `segments`（＝焼かないと変わらない所）も見るように
  なったら、`(4)` は metadata ではなくなります。`daily_pick.METADATA_LEGS` から
  外して、この道具ごと落とすこと。
- 前提「外の作り方を写した長尺」が閉じて `OUTSIDE_LONG_RULE` を使わなくなったら、
  `OUTSIDE_LEGS` ごと落とすこと（`config/hypotheses.yaml`）。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JST = ZoneInfo("Asia/Tokyo")
STASH = ROOT / "data" / "critique_queue"
#: 控えのうち、手元の台本から**写して良い**欄。**ここ以外は触らないこと**
#: （`segments` を写すと「焼いていない中身」を焼いたことにしてしまいます）。
COPY_FIELDS = ("title", "thumbnail_kicker", "thumbnail_line1", "thumbnail_line2")


def _plan(video_id: str) -> dict | None:
    """その本の直しの中身。`daily_pick` の決めから引く。無ければ `None`。API 0単位。"""
    from src import daily_pick as dp

    for d in (date.today(), datetime.now(JST).date()):
        cur = dp.current(d)
        if cur and str(cur.get("video_id") or "") == video_id:
            return dp.metadata_fix_plan(cur)
    # 決めが別の日でも、本が名指されていれば直せる（枠は `ahead_sweep` が見る）。
    for row in reversed(list(dp._jsonl(dp.ROOT / "data" / "daily_pick.jsonl"))):
        if str(row.get("video_id") or "") == video_id:
            return dp.metadata_fix_plan(row)
    return None


def sync_stash(plan: dict, *, dry_run: bool = False) -> list[str]:
    """控えの台本を手元の台本に合わせる。**API 0単位。**変えた欄の名を返す。"""
    path = STASH / f"{plan['video_id']}.script.json"
    script = json.loads(path.read_text(encoding="utf-8"))
    changed = []
    for k in COPY_FIELDS:
        new = plan.get(k)
        if new is None or script.get(k) == new:
            continue
        print(f"  {k}: {script.get(k)!r} → {new!r}")
        script[k] = new
        changed.append(k)
    if changed and not dry_run:
        path.write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    return changed


def main(video_id: str, *, dry_run: bool = False, no_api: bool = False) -> int:
    from src import daily_pick as dp

    plan = _plan(video_id)
    if not plan:
        bad, why = dp.pick_legs(video_id)
        print(f"[meta] {video_id} は直せません —— "
              f"{why or ('落ちた脚が metadata だけではありません: ' + '／'.join(bad) if bad else '脚は全部 ○ です')}")
        print("[meta] **手元の台本が 4脚とも ○ のときだけ直します**"
              "（写す先が無いなら、先に台本を直すこと）。")
        return 1
    print(f"[meta] {video_id}（{plan['topic']}）落ちた脚: {'／'.join(plan['bad'])}")
    changed = sync_stash(plan, dry_run=dry_run)
    if not changed:
        print("[meta] 控えは既に手元の台本と同じでした。実物の側だけ直します。")
    if dry_run:
        print("[meta] --dry-run なので、ここで止めます。")
        return 0

    # 2. 控えの絵を焼き直す（**API 0単位**・控えの台本を読むので 1 のあと）
    from scripts import refresh_thumbnail as rt

    rc = rt.rebuild_stash(video_id, topic=plan["topic"])
    print(f"[meta] 控えの絵を焼き直しました rc={rc}")
    if no_api:
        print("[meta] --no-api なので、実物へは載せません。"
              "`retitle.py` と `refresh_thumbnail.py --missing --video` は別の回で。")
        return 0

    # 3. 実物の題（50単位）
    from scripts import retitle

    rc = retitle.main(video_id, plan["title"])
    print(f"[meta] 題を差し替えました rc={rc}")
    # 4. 実物の絵（50単位）
    rc = rt.push_missing(only_video=video_id, force=True)
    print(f"[meta] 絵を載せました rc={rc}")

    bad, why = dp.pick_legs(video_id)
    print(f"[meta] 直したあとの脚: {bad if not why else why}")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__.strip().splitlines()[2].strip())
        raise SystemExit(2)
    raise SystemExit(main(args[0],
                          dry_run="--dry-run" in sys.argv,
                          no_api="--no-api" in sys.argv))
