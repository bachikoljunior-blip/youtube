#!/usr/bin/env python3
"""**予約の順番待ちが、目標までの日数をいくら食っているか。**（既定は API 0単位）

    python scripts/queue_lag.py            # 待ち時間と、取り戻せる日数
    python scripts/queue_lag.py --plan     # 入れ替えの手（`--move` の行）を出す
    python scripts/queue_lag.py --apply    # そのとおりに撃つ（1手 100単位＝50×2）

## なぜ要るか（2026-08-26。**この機械の時定数に、名前が付いていませんでした**）

`scripts/eta.py` は毎回こう印字します ——
**「軌跡の腕が動くのは、`config/hypotheses.yaml` の前提を1件閉じたときだけ」**。
つまり到達日を決めているのは **θ ＝ 前提が閉じる速さ**（実測 1.2日に1件）です。

**その θ を決めているのは、予約の順番待ちです。**
`src/judgeable.py` が既に足し算を書いています:

    処置が実装に入る → その作りの本ができる → **予約の順番待ち** → 公開
      → 落ち着き7日 → Analytics の遅れ3日 → 判定できる

実測（2026-08-26）: 予約は **337本**・いちばん後ろは **32日先**。
1日に再生が付く上限は **10本**（`src/day_cap.py`）なので、
**いま作った本が公開されるのは 32日後**、判定できるのは **42日後**です。

**税は2回かかります。ここが誰も書いていなかった所です。**

    1回目  いま立てた前提は、**42日たたないと判定できない**（θ が下がる）
    2回目  判定が出ても、**その先 32日ぶんの公開枠はもう埋まっています。**
           勝った作りが画面に出るのは、さらに **32日後**

**9月に閉じる4件の A/B の結果は、10月まで1本にも反映できません。**
待ち時間が 5日 なら、同じ結論が 15日 で出て 5日 で反映されます。
**θ が2.8倍**になるということは、`src/arm_speed.py` の
`rate = p · log(g) · θ` がそのまま2.8倍になるということです。

## この道具が出す「取り戻せる日数」

**新しい本は1本も要りません。** 判定に要る本は、もう予約の中に在ります ——
ただし**後ろのほう**に。実測（2026-08-26）:

    opening_motion  対照(動きなし) は 8本ちょうど。うち4本が **09/06**
                    → 8本目 09/06 なので ready は 09/16
                    その4本を 08/29〜08/30 へ入れ替えると ready **09/09**（**7日**）

**入れ替え（swap）であって、前詰めではありません。** 2本の公開時刻を
**そのまま交換する**ので、**1日の本数も、時刻の埋まり方も 1つも変わりません。**
`day_cap`（10本/日）を1本も超えません。ここを「前へ詰める」でやると、
その日が上限を超えて、**足したぶんが 0再生**になります（`--compact` の穴）。

## 触らないもの

- **測定の窓**（`src.measure_window`）の日は、**置き先からも、動かす対象からも**外します。
  `--move` の門は 2026-08-26 に「元の日」も見るようになりました
  （`scripts/reschedule.py::_check_source_window`）。ここは、その手前で外します
- **判定に要っている本**は、後ろへ送る側に選びません（送ると別の前提が遅れます）
- **公開済みの本**（`publishAt` が過ぎている）は動きません

## 分かっていないこと（**言っておく**）

- **`--apply` は撃つ順番を守れません。** 交換の片側だけが通った状態で落ちると、
  2本が同じ時刻に並びます。**落ちたら `--plan` を撃ち直して、残りを当てること**
  （交換は冪等ではありませんが、`--plan` は毎回**実物の控えから**組み直します）
- **待ち時間そのものは、この道具では縮みません。** 縮むのは
  「もう予約に在る本の並び」だけです。**32日 → 5日 にするには、
  作る本数（実測 13.6本/日）を、再生が付く上限（10本/日）まで落とすか、
  後ろの予約を外して private の控えに戻すしかありません。**
  どちらも本1本ぶんの判断なので、この道具は**数字を出すところまで**にしています
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import day_cap, judgeable, measure_window  # noqa: E402
from src.ab_split import SETTLE_DAYS, published  # noqa: E402

JST = timezone(timedelta(hours=9))

#: 1回の `--plan` が組む入れ替えの上限。**枠（1手 100単位）を一度に使い切らないため。**
MAX_SWAPS = 40


# --- 予約の姿 ---------------------------------------------------------------

def scheduled(now: datetime | None = None) -> list[dict]:
    """**これから公開される本**を、公開時刻の昇順で。（控えから。API 0単位）

    畳み方は `ab_split.published()` に持たせています（同じ `video_id` の行が
    動かすたびに増える／日は JST）。**ここで畳み直さないこと。**
    """
    now = now or datetime.now(JST)
    rows = [r for r in published()
            if isinstance(r.get("at"), datetime) and r["at"] > now]  # type: ignore[operator]
    rows.sort(key=lambda r: r["at"])  # type: ignore[index,return-value]
    return rows


def depth(rows: list[dict], now: datetime | None = None) -> int:
    """**いま作った本が公開されるまでの日数**（予約のいちばん後ろまで）。"""
    if not rows:
        return 0
    now = now or datetime.now(JST)
    return (rows[-1]["at"].date() - now.date()).days  # type: ignore[union-attr]


def lag_lines(rows: list[dict], now: datetime | None = None) -> list[str]:
    d = depth(rows, now)
    cap = day_cap.cap()
    judge = d + SETTLE_DAYS + judgeable.ANALYTICS_LAG_DAYS
    last = rows[-1]["at"].date().isoformat() if rows else "—"  # type: ignore[union-attr]
    return [
        "=== 予約の順番待ち（この機械の時定数）===",
        f"  予約に入っている本 **{len(rows)}本** ／ いちばん後ろ {last}"
        f"（**{d}日 先**） ／ 再生が付く上限 {cap}本/日（実測）",
        f"  → **いま作った本が公開されるのは {d}日後。**"
        f" 判定できるのは ＋落ち着き{SETTLE_DAYS}日 ＋Analytics {judgeable.ANALYTICS_LAG_DAYS}日"
        f" ＝ **{judge}日後**",
        f"  [!] **税は2回**: いま立てた前提は {judge}日 判定できない。"
        f"そのうえ、判定が出ても**先 {d}日ぶんの枠は埋まっている**ので、"
        f"勝った作りが画面に出るのはさらに {d}日後",
        "  **`eta.py` の腕が動く速さ θ は、この待ち時間の逆数です**"
        "（`src/arm_speed.py`: rate = p · log(g) · θ）。"
        "**待ちを縮めることだけが、作る本数と無関係に θ を上げます。**",
    ]


# --- 取り戻せる日数 ---------------------------------------------------------

def _ready(nths: list[date]) -> date:
    return max(nths) + timedelta(days=SETTLE_DAYS + judgeable.ANALYTICS_LAG_DAYS)


def _nth(days: list[date], n: int) -> date | None:
    return sorted(days)[n - 1] if len(days) >= n else None


class Plan:
    """いまの割り当てと、そこから組んだ入れ替え。"""

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(JST)
        self.rows = scheduled(self.now)
        #: video_id → いまの公開時刻（JST）。**入れ替えのたびに書き換える**
        self.at: dict[str, datetime] = {
            str(r["video_id"]): r["at"] for r in self.rows  # type: ignore[misc]
            if r.get("video_id")
        }
        self.floors = [f for f in judgeable.floors()]
        #: key → 群 → [(公開日, video_id)]
        self.groups: dict[str, dict[str, list[tuple[date, str]]]] = {
            f.key: judgeable.members(f.key) for f in self.floors
        }
        self.n: dict[str, int] = {f.key: f.min_per_group for f in self.floors}
        self.swaps: list[tuple[str, str]] = []      # (早める本, 後ろへ送る本)
        self.before = self.readies()

    # -- いまの姿 --
    def _days_of(self, key: str, group: str) -> list[date]:
        """**いまの割り当て**での公開日（動かした本は新しい時刻で数える）。"""
        out = []
        for day, vid in self.groups[key][group]:
            out.append(self.at[vid].date() if vid in self.at else day)
        return out

    def readies(self) -> dict[str, date | None]:
        out: dict[str, date | None] = {}
        for f in self.floors:
            nths = [_nth(self._days_of(f.key, g), self.n[f.key])
                    for g in self.groups[f.key]]
            out[f.key] = None if any(x is None for x in nths) else _ready(
                [x for x in nths if x is not None])
        return out

    def needed(self) -> set[str]:
        """**判定に要っている本**（どれかの群の、いまの N本目までに入っている）。

        後ろへ送る側に選ぶと、その前提が遅れます。**送らないこと。**
        """
        keep: set[str] = set()
        for f in self.floors:
            n = self.n[f.key]
            for group, ms in self.groups[f.key].items():
                order = sorted(ms, key=lambda m: (self.at[m[1]].date()
                                                  if m[1] in self.at else m[0]))
                for _, vid in order[:n]:
                    if vid:
                        keep.add(vid)
        return keep

    # -- 入れ替え --
    def _locked(self, when: datetime) -> bool:
        return measure_window.inside(when.date().isoformat())

    def _swap(self, early_vid: str, late_vid: str) -> None:
        self.at[early_vid], self.at[late_vid] = self.at[late_vid], self.at[early_vid]
        self.swaps.append((early_vid, late_vid))

    def potential(self) -> int:
        """**全部の群の「N本目までの公開日」の合計**（小さいほど早い）。

        1手ごとに `ready` が縮むとは限りません。**群の本数がちょうど N のとき**
        （`opening_motion` の対照は 8本ちょうど）、N本目 ＝ いちばん遅い本なので、
        **4本を全部前へ出すまで 1日も縮みません。**
        1手で縮むことを条件にすると、この群は**永久に動きません**
        （2026-08-26 の最初の版がそれで、`opening_motion` だけ 0日 でした）。

        だから見るのは `ready` ではなく、**この合計が減ったか**です。
        合計は下に有界なので、**必ず止まります**（ping-pong もしません）。
        """
        base = date(2026, 1, 1)
        total = 0
        for f in self.floors:
            n = self.n[f.key]
            for group in self.groups[f.key]:
                for d in sorted(self._days_of(f.key, group))[:n]:
                    total += (d - base).days
        return total

    def improve(self, limit: int = MAX_SWAPS) -> None:
        """**いちばん遅い前提から順に、1手ずつ縮める。**縮まなくなったら止める。"""
        while len(self.swaps) < limit:
            if not self._one_step():
                break

    def _one_step(self) -> bool:
        readies = self.readies()
        # 判定できない（群がそろわない）前提は、入れ替えでは動かせません
        cand = [f for f in self.floors if readies.get(f.key)]
        cand.sort(key=lambda f: readies[f.key], reverse=True)  # type: ignore[arg-type,index]
        keep = self.needed()
        for f in cand:
            n = self.n[f.key]
            # 縛っている群 ＝ N本目がいちばん遅い群
            gs = sorted(self.groups[f.key],
                        key=lambda g: _nth(self._days_of(f.key, g), n) or date.max,
                        reverse=True)
            for group in gs:
                cur = _nth(self._days_of(f.key, group), n)
                if cur is None:
                    continue
                if self._pull(f.key, group, cur, keep):
                    return True
        return False

    def _pull(self, key: str, group: str, cur: date, keep: set[str]) -> bool:
        """その群の「N本目 `cur`」を、1つ早い枠へ入れ替える。できたら True。"""
        # 早める側: この群の本で、いま `cur` 以降に居るもの（遅い順に試す）
        late = sorted(
            (vid for _, vid in self.groups[key][group]
             if vid in self.at and self.at[vid].date() >= cur
             and not self._locked(self.at[vid])),
            key=lambda v: self.at[v], reverse=True)
        if not late:
            return False
        # 後ろへ送る側: `cur` より前の枠に居て、どの前提にも要っていない本
        free = sorted(
            (vid for vid, when in self.at.items()
             if when.date() < cur and vid not in keep and not self._locked(when)),
            key=lambda v: self.at[v])
        if not free:
            return False
        for early_slot in free[:8]:
            for mover in late:
                if self.at[mover] <= self.at[early_slot]:
                    continue
                before = self.potential()
                self._swap(mover, early_slot)
                if self.potential() < before:
                    return True
                self._swap(mover, early_slot)      # 戻す（縮まなかった）
                self.swaps.pop()
                self.swaps.pop()
        return False

    # -- 出す --
    def gain_lines(self) -> list[str]:
        after = self.readies()
        out = ["", "=== もう予約に在る本を入れ替えるだけで、何日 早まるか"
               "（**新しい本は1本も要りません**）==="]
        total = 0
        for f in sorted(self.floors, key=lambda f: f.deadline):
            b, a = self.before.get(f.key), after.get(f.key)
            if b is None or a is None:
                short = ", ".join(f"{g} あと{c}本" for g, c in f.shortfall().items() if c)
                out.append(f"  {f.key:16s} **判定できる日が出ません**（{short}）"
                           " ← 入れ替えでは動きません。**本が足りない**")
                continue
            gain = (b - a).days
            total += gain
            mark = f"  → **{gain}日 早まる**" if gain else "  （動きません）"
            out.append(f"  {f.key:16s} 期限 {f.deadline:%m/%d}   "
                       f"判定 {b:%m/%d} → **{a:%m/%d}**{mark}")
        out.append(f"  合計 **{total}日**／入れ替え {len(self.swaps)}手"
                   f"（{len(self.swaps) * 2}回の `--move` ＝ {len(self.swaps) * 100}単位）")
        if total and not self.swaps:
            out.append("  [!] 手が0なのに日数が動いています。**数え方がずれています**")
        return out

    def moves(self) -> list[tuple[str, str]]:
        """撃つ順の (video_id, `YYYY-MM-DDTHH:MM` JST)。**交換は2行で1組。**"""
        out: list[tuple[str, str]] = []
        for a, b in self.swaps:
            out.append((a, self.at[a].strftime("%Y-%m-%dT%H:%M")))
            out.append((b, self.at[b].strftime("%Y-%m-%dT%H:%M")))
        return out

    def plan_lines(self) -> list[str]:
        if not self.swaps:
            return ["", "  （入れ替える手はありません）"]
        out = ["", "=== 手（`scripts/reschedule.py --move` を、この順で）==="]
        for vid, when in self.moves():
            out.append(f"  python scripts/reschedule.py --move {vid} {when}")
        return out


def apply_moves(plan: Plan) -> int:
    """実物へ当てる。**1手 100単位。**片側で落ちたら、そこで止めて言い残す。"""
    from scripts import reschedule

    done = 0
    for vid, when in plan.moves():
        try:
            reschedule.main(["--move", vid, when])
        except SystemExit as e:
            if e.code:
                print(f"[queue_lag] {vid} で止まりました: {e}."
                      " **`--plan` を撃ち直して残りを当てること**", flush=True)
                return 1
        except Exception as e:  # pragma: no cover - 実物の口
            print(f"[queue_lag] {vid} で落ちました: {e}."
                  " **`--plan` を撃ち直して残りを当てること**", flush=True)
            return 1
        done += 1
    print(f"[queue_lag] {done}回 動かしました（{done * 50}単位）")
    return 0


def report(plan: Plan | None = None) -> list[str]:
    plan = plan or Plan()
    out = lag_lines(plan.rows, plan.now)
    plan.improve()
    out += plan.gain_lines()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="予約の順番待ちが、判定までの日数をいくら食っているか")
    ap.add_argument("--plan", action="store_true",
                    help="入れ替えの手（`--move` の行）も出す（**API 0単位**）")
    ap.add_argument("--apply", action="store_true",
                    help="そのとおりに撃つ（**1手 100単位**）")
    ap.add_argument("--max-swaps", type=int, default=MAX_SWAPS,
                    help=f"組む入れ替えの上限（既定 {MAX_SWAPS}）")
    args = ap.parse_args(argv)

    plan = Plan()
    lines = lag_lines(plan.rows, plan.now)
    plan.improve(args.max_swaps)
    lines += plan.gain_lines()
    if args.plan or args.apply:
        lines += plan.plan_lines()
    print("\n".join(lines))
    if args.apply:
        return apply_moves(plan)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
