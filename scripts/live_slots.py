"""**A/B の本が「再生の付かない枠」に置かれていないか。**（API 0単位。`--apply` だけが撃つ）

    python scripts/live_slots.py            いま何本 落としているか
    python scripts/live_slots.py --plan     動かす手（`--move` の行）
    python scripts/live_slots.py --apply    そのとおりに撃つ（1手 50単位）

## なぜ要るか（2026-08-26。**「2か所が別々に言っている」の13件目**）

`src/day_cap.py` は実測でこう言っています ——
**「1日に再生が付くのは 10本」「30分より詰めた本は死ぬ」。**
実測の差は**再生の中央値 718 対 2**（`day_cap.live_ids` の節）。

`src/judgeable.py` は A/B の群を**公開日だけ**で数えていました。
**0再生と分かっている本も、1本と数えていました。**

`falsified_if` はどれも「上回らなければ外れ（同点も外れ）」です。
**0再生の本を標本に混ぜると、足りないぶんがそのまま「外れ」に化けます。**
2026-08-26 の実物:

    opening_motion 対照(動きなし)   8本中 **5本** が 0再生の枠  → 生きているのは 3本（要 8本）
    stat_split     処置(後)        23本中 **10本** が 0再生の枠 → 生きているのは 13本（要 16本）

**どちらも、期限どおりなら「外れ」と判定されるところでした。**
16本×2群 作って2週間待った代金が、**枠の置き方だけで**消えます。

## `src/collisions.py` は、すでに答えを出していました

同じ分に2本入っている3件（09/06 の 09:00/10:00/11:00）は
`collisions.say()` が**貼れる形で**印字しています。**そのうち2本が
`opening_motion 対照` の本**でした。**直し方は在ったのに、
「実験が標本を失っている」と結び付ける所がどこにも無かった**だけです。

## 落とす条件は「その日の何本目か」だけ

**再生数では落としません。** 結果で条件付けると、処置そのものが再生を
落としている場合に、その効果を隠します。順番は予約を置いた側が決める量なので、
処置とは独立です（`src/judgeable.members` の節）。

## 触らないもの

- **測定の窓の日**（`src/measure_window.py`）は、**動かす側にも置き先にもしません**
- **公開済みの本**は動きません（`publishAt` が過ぎている）
- 置き先は `src/collisions.py` の**生きる帯**（05:00〜13:30 の30分きざみ）の空き分だけ
- 置き先の日の**帯の中の本数が `day_cap.cap()` を超えない**こと
  （同じ日の中で動かすぶんは本数が変わらないので、この門に掛かりません）
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import collisions, day_cap, judgeable, measure_window  # noqa: E402
from src.ab_split import published  # noqa: E402

JST = dt.timezone(dt.timedelta(hours=9))
GRID = list(range(collisions.LIVE_FROM_MIN, collisions.LIVE_TO_MIN + 1,
                  collisions.STEP_MIN))


def _rows() -> list[dict]:
    return [r for r in published()
            if r.get("at") and isinstance(r["at"], dt.datetime) and r.get("video_id")]


class Board:
    """予約の盤面。**動かすたびに、その場で更新します**（次の手が同じ枠を掴まないように）。"""

    def __init__(self, rows: list[dict], now: dt.datetime | None = None) -> None:
        self.now = now or dt.datetime.now(JST)
        self.at: dict[str, dt.datetime] = {str(r["video_id"]): r["at"] for r in rows}
        self.cap = day_cap.cap()
        self.moves: list[tuple[str, dt.datetime]] = []

    # -- 盤面を読む --
    def _taken(self, day: dt.date) -> set[int]:
        return {w.hour * 60 + w.minute for w in self.at.values() if w.date() == day}

    def _in_band(self, day: dt.date) -> int:
        return sum(1 for w in self.at.values() if w.date() == day
                   and collisions.LIVE_FROM_MIN <= w.hour * 60 + w.minute
                   <= collisions.LIVE_TO_MIN)

    def live(self) -> set[str]:
        rows = [{"at": w, "video_id": v} for v, w in self.at.items()]
        return day_cap.live_ids(rows)

    def movable(self, vid: str) -> bool:
        w = self.at.get(vid)
        return bool(w and w > self.now
                    and not measure_window.inside(w.date().isoformat()))

    # -- 置き先を探す --
    def _slots(self, day: dt.date, *, same_day: bool) -> list[int]:
        """その日の、帯の中の空き分。`same_day` なら本数の門は掛かりません。"""
        if measure_window.inside(day.isoformat()):
            return []
        taken = self._taken(day)
        free = [m for m in GRID if m not in taken]
        if same_day:
            return free
        return free[: max(0, self.cap - self._in_band(day))]

    def place(self, vid: str) -> dt.datetime | None:
        """`vid` を、**いちばん早い生きた枠**へ。同じ日に空きがあればそこを先に使う。"""
        cur = self.at[vid]
        floor = self.now.date() + dt.timedelta(days=1)
        last = max(w.date() for w in self.at.values())
        days: list[tuple[dt.date, bool]] = []
        day = floor
        while day <= last:
            days.append((day, day == cur.date()))
            day += dt.timedelta(days=1)
        for d, same in days:
            for m in self._slots(d, same_day=same):
                when = dt.datetime.combine(d, dt.time(m // 60, m % 60), tzinfo=JST)
                if when <= self.now:
                    continue
                self.at[vid] = when
                self.moves.append((vid, when))
                return when
        return None


def _groups() -> dict[str, tuple[dict[str, list[str]], int]]:
    """前提 → (群名 → `video_id` の一覧, 要る本数)。**絞る前の姿**を見ます。"""
    out = {}
    for key, (make, n) in judgeable.MEMBER_SOURCES.items():
        ms = make()
        out[key] = ({g: [v for _, v in rows if v] for g, rows in ms.items()}, n)
    return out


def report(board: Board | None = None) -> list[str]:
    board = board or Board(_rows())
    live = board.live()
    out = ["=== A/B の本のうち、再生が付く枠に居るのは何本か"
           f"（1日 {board.cap}本・間隔 {day_cap.MIN_GAP_MIN:.0f}分・帯 05:00〜13:30）==="]
    short_total = 0
    for key, (groups, n) in sorted(_groups().items()):
        for g, vids in sorted(groups.items()):
            al = [v for v in vids if v in live]
            dead = [v for v in vids if v not in live]
            resc = [v for v in dead if board.movable(v)]
            short = max(0, n - len(al))
            short_total += short
            mark = ""
            if short:
                mark = (f"  ← **あと {short}本 足りません**"
                        f"（動かせる死に枠 {len(resc)}本）")
            out.append(f"  {key:16s} {g:14s} 予約 {len(vids):4d}本 → "
                       f"生きている **{len(al):4d}本**（要 {n}）{mark}")
    if not short_total:
        out.append("  → **どの群も足りています。**")
    else:
        out.append(f"  → **足りない合計 {short_total}本。** "
                   "`--plan` が、動かせるぶんの手を出します")
    return out


def plan(board: Board) -> list[str]:
    """**足りない群から順に**、死に枠の本を生きた枠へ移す。

    ## **生きる枠は増えません。付け替えるだけです**（2026-08-26 に数えて確かめた）

    1日に再生が付くのは `day_cap.cap()` 本ちょうどなので、
    **1本 生き返らせると、必ず1本 死にます**（実測: 生き返り7・死に7・差 0）。
    押し出されるのは、その日の**帯の外**（14:00〜21:00）に居て、
    たまたま10位以内に入っていた本です。

    **それでも撃つ理由**: 押し出される側は A/B の情報を持たない本か、
    すでに標本の足りている群（`stat_split 対照(前)` は 316本 生きています）の本です。
    **再生の総数は1つも減らず、実験の情報だけが増えます。**

    押し出した先が**足りない群の本だった**場合、その群の不足はその場で数え直され、
    次の手で埋めます（だから手の数が、最初の不足より多くなることがあります）。
    """
    out = ["", "=== 手（`scripts/reschedule.py --move` を、この順で）==="]
    was_live = board.live()
    for key, (groups, n) in sorted(_groups().items()):
        for g, vids in sorted(groups.items()):
            live = board.live()
            need = n - len([v for v in vids if v in live])
            if need <= 0:
                continue
            picked = 0
            for vid in sorted((v for v in vids if v not in live and board.movable(v)),
                              key=lambda v: board.at[v]):
                if picked >= need:
                    break
                was = board.at[vid]
                when = board.place(vid)
                if when is None:
                    continue
                picked += 1
                out.append(f"  python scripts/reschedule.py --move {vid} "
                           f"{when:%Y-%m-%dT%H:%M}   # {key}/{g}  "
                           f"{was:%m/%d %H:%M} から（死に枠）")
            still = n - len([v for v in vids if v in board.live()])
            if still > 0:
                out.append(f"  [!] {key}/{g} は **まだ {still}本 足りません** —— "
                           "動かせる死に枠を使い切りました"
                           "（測定の窓の日と公開済みは動かせません）。"
                           "**本を足すか、期限を延ばすこと。`falsified_if` は緩めないこと**")
    if not board.moves:
        out.append("  （動かす手はありません）")
        return out

    now_live = board.live()
    out.append("")
    out.append("=== この入れ替えで、群ごとに何本 増えるか（**総数は増えません。付け替えです**）===")
    for key, (groups, n) in sorted(_groups().items()):
        for g, vids in sorted(groups.items()):
            b = len([v for v in vids if v in was_live])
            a = len([v for v in vids if v in now_live])
            if b == a:
                continue
            short = max(0, n - a)
            tail = "  ← **まだ足りません**" if short else ("  ← **足ります**" if b < n <= a else "")
            out.append(f"  {key:16s} {g:14s} {b:4d}本 → **{a:4d}本**"
                       f"（{a - b:+d}／要 {n}）{tail}")
    out.append(f"  生きている本の総数: {len(was_live)} → {len(now_live)}"
               f"（{len(now_live) - len(was_live):+d}）"
               "  **1日 の上限は変わらないので、ここは 0 になります**")
    return out


def apply_moves(board: Board) -> int:
    from scripts import reschedule

    done = 0
    for vid, when in board.moves:
        try:
            reschedule.main(["--move", vid, f"{when:%Y-%m-%dT%H:%M}"])
        except SystemExit as e:
            if e.code:
                print(f"[live_slots] {vid} で止まりました。"
                      " **`--plan` を撃ち直して残りを当てること**", flush=True)
                return 1
        except Exception as e:                            # noqa: BLE001
            print(f"[live_slots] {vid} で落ちました: {e}."
                  " **`--plan` を撃ち直して残りを当てること**", flush=True)
            return 1
        done += 1
    print(f"[live_slots] {done}回 動かしました（{done * 50}単位）")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--plan", action="store_true", help="動かす手を出す（API 0単位）")
    ap.add_argument("--apply", action="store_true", help="そのとおりに撃つ（1手 50単位）")
    args = ap.parse_args(argv)

    board = Board(_rows())
    lines = report(board)
    if args.plan or args.apply:
        lines += plan(board)
        lines += ["", *day_cap.live_lines(_rows())]
    print("\n".join(lines))
    if args.apply:
        from scripts import queue_lag
        q, ok = queue_lag.quota_lines(queue_lag.Plan())
        print("\n".join(q))
        if not ok:
            print("  [!] **撃ちません。**枠が戻ってから `--apply` を撃つこと")
            return 1
        return apply_moves(board)
    return 0


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
