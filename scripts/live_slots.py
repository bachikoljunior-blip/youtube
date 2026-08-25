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
    def _alive_on(self, day: dt.date, live: set[str] | None = None) -> int:
        """その日に**いま再生が付いている本の数**。

        **`_in_band` で代用しないこと**（2026-08-26 に数え直した）。帯の外
        （14:00〜21:00）に居ても、その日の本数が上限に届いていなければ
        **その本は生きています。** 帯の中の数だけで「空き」を出すと、
        **すでに埋まっている日を空いていると読み**、置いたぶんだけ
        別の本を押し出します（実測: それで 24手 打って正味 **+4本**しか増えなかった）。
        """
        live = self.live() if live is None else live
        return sum(1 for v, w in self.at.items() if w.date() == day and v in live)

    def _slots(self, day: dt.date, *, same_day: bool,
               live: set[str] | None = None) -> list[int]:
        """その日の、帯の中の空き分。`same_day` なら本数の門は掛かりません。"""
        if measure_window.inside(day.isoformat()):
            return []
        taken = self._taken(day)
        free = [m for m in GRID if m not in taken]
        if same_day:
            return free
        return free[: max(0, self.cap - self._alive_on(day, live))]

    def place(self, vid: str, *, same_day_first: bool = True) -> dt.datetime | None:
        """`vid` を、**いちばん早い生きた枠**へ。

        `same_day_first` が真なら、**同じ日の空き分を先に**使います。同じ日の中で
        動かすぶんは その日の本数が変わらないので、本数の門に掛かりません
        （同じ分に2本ある「間隔で死んだ本」を直すのは、この道です）。

        **真にしてよいのは、本数では死んでいない本だけ**です。その日が既に上限を
        超えているなら、同じ日へ置き直しても**別の1本を押し出すだけ**（付け替え）で、
        生きる本は1本も増えません。`--all` はここを偽にして、
        **本当に空いている日**（上限に余りのある日）へ逃がします。
        """
        cur = self.at[vid]
        floor = self.now.date() + dt.timedelta(days=1)
        last = max(w.date() for w in self.at.values())
        days: list[tuple[dt.date, bool]] = []
        day = floor
        while day <= last:
            days.append((day, same_day_first and day == cur.date()))
            day += dt.timedelta(days=1)
        live = self.live()          # **1本ごとに1回だけ**（日ごとの空きを正しく読むため）
        for d, same in days:
            for m in self._slots(d, same_day=same, live=live):
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


def _free_live_before(board: Board, limit: dt.date) -> int:
    """**期限までに、上限の余っている生きた枠が何本あるか。**（API 0単位）

    **「本を足すこと」と言う前に、置く所があるかを数えるためのもの**です
    （2026-08-26 04:2x に足した）。ここが 0 なら、**作った本はその日の
    `cap()+1` 本目 ＝ 死に枠に入ります** —— いま逃がしている場所に
    新しく積むだけで、その群は1本も増えません。

    実測（08/26）: 期限 09/13 までの**全部の日**が上限ちょうどか超過で、
    **余りは 0本**でした。それでも申し送りは3回続けて
    「対照を2本 作り足すこと」と書いていました。
    """
    live = board.live()
    day = board.now.date()
    free = 0
    while day <= limit:
        if not measure_window.inside(day.isoformat()):
            free += max(0, board.cap - board._alive_on(day, live))
        day += dt.timedelta(days=1)
    return free


def _needed(board: Board, live: set[str] | None = None) -> set[str]:
    """**押し出してはいけない本**（どこかの群が、判定に要る床のぶんとして使っている本）。

    群ごとに、生きている本を公開の早い順に並べ、**先頭 N本**が「要る本」です。
    そこから溢れたぶんは**余り**で、押し出しても判定は1件も遅れません
    （実測 08/26: `stat_split 対照(前)` は 床 16 に対して **316本** 生きています）。
    """
    live = board.live() if live is None else live
    keep: set[str] = set()
    for _key, (groups, n) in _groups().items():
        for _g, vids in groups.items():
            alive = sorted((v for v in vids if v in live), key=lambda v: board.at[v])
            keep.update(alive[:n])
    return keep


def _swap_candidates(board: Board, limit: dt.date, want: int) -> list[tuple[str, dt.datetime]]:
    """**時刻を交換してよい相手**を、早い順に。（API 0単位）

    ## なぜ「空き枠」ではなく「交換」なのか（2026-08-26 に数えて足した）

    上限に達している日には、**空いた生きた枠というものがありません。**
    その日に生きるのはちょうど `cap()` 本で、どの時刻に置いても本数は変わらない ——
    **新しく足した本は必ず `cap()+1` 本目（0再生）になります。**
    だから「枠を空けてから入れる」は成立しません（空けた瞬間に、その日の
    別の本が繰り上がって埋めます）。**成立するのは交換だけです。**

    **2本の `at` を入れ替えると、(日, 時刻) の集合は1つも変わりません。**
    どの本がどの枠に居るかだけが入れ替わるので、**生きている本の総数も、
    再生の総数も変わりません。** 動くのは「その枠に居るのがどちらか」だけ ——
    つまり**実験の情報だけが増えます**（`plan()` の節が言っているのと同じ形）。

    **相手に選んでよいのは「余り」だけ**です（`_needed()`）。
    どこかの群が床のぶんとして使っている本を押し出すと、**別の前提を1件 遅らせます。**
    """
    live = board.live()
    keep = _needed(board, live)
    out: list[tuple[str, dt.datetime]] = []
    for vid, when in sorted(board.at.items(), key=lambda kv: kv[1]):
        if len(out) >= want:
            break
        if vid not in live or vid in keep:
            continue
        if when.date() > limit or not board.movable(vid):
            continue
        out.append((vid, when))
    return out


def _how_to_fill(board: Board, key: str, still: int) -> str:
    """**足りないぶんを、どう埋めるか。**置く所の有無で言うことが変わります。"""
    limit = next((f.deadline for f in judgeable.floors() if f.key == key), None)
    if limit is None:
        return ("**本を足すか、期限を延ばすこと。"
                "`falsified_if` は緩めないこと**")
    free = _free_live_before(board, limit)
    if free >= still:
        return (f"**本を {still}本 足すこと**"
                f"（期限 {limit:%m/%d} までに空いた生きた枠が {free}本 あります）。"
                "**`falsified_if` は緩めないこと**")
    head = (f"[!] **「作り足す」だけでは埋まりません** —— 期限 {limit:%m/%d} までに"
            f"空いた生きた枠は **{free}本** しかありません"
            f"（要 {still}本）。作った本はその日の {board.cap + 1}本目 ＝"
            "**死に枠**に入り、いま逃がしている場所に積むだけです。"
            "**効くのは「作って、早い日の生きた枠へ入れて、A/B でない本を1本 押し出す」"
            "まで通した1手だけ**（`live_slots` の交換と同じ形。総再生は変わらず、"
            "実験の情報だけが増えます）。")
    # **その「1手」の相手を、ここで名指しすること**（2026-08-26 に足した）。
    #     この文はずっと「交換すれば効く」と言うだけで、**誰と交換するのかを
    #     出していませんでした。** 出さないと、読んだ回が自分で盤面を数え直す
    #     ところから始めます（実測: 申し送りが3回続けて具体の手を書き、
    #     3回とも盤面が変わっていて外した。`docs/trigger_main.md`）。
    #     **書き置きではなく、撃つたびにその場の実物から出すこと。**
    swaps = _swap_candidates(board, limit, still)
    tail = ("**それが無理なら期限を延ばすこと。`falsified_if` は緩めないこと**")
    if len(swaps) < still:
        return (head + f"[!] **交換の相手も {len(swaps)}本 しか居ません**（要 {still}本）。"
                + tail)
    named = " ／ ".join(f"`{v}`（{w:%m/%d %H:%M}）" for v, w in swaps)
    return (head + f"**交換してよい余りの本**（床を割らないもの）: {named}。"
            f" 作った {still}本 を投稿してから、この本と `at` を入れ替えること"
            "（1組 2手・100単位。**(日,時刻) の集合は1つも変わりません**）。" + tail)


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

    ## 押し出しは起きます。**総数は減りません**（2026-08-26 に数え直した）

    置き先の日が**上限に余っている**なら、押し出す相手は居ません（生きる本が増える）。
    余りが無い日へ置くと、その日の誰か1本と**付け替え**になります。
    どちらになるかは `_alive_on()` が日ごとに見ています。

    **最初の版は `_in_band()`（帯の中の本数）で空きを数えていて、
    埋まっている日を空いていると読んでいました。** 帯の外（14:00〜21:00）に居ても、
    その日が上限に届いていなければ**その本は生きています。**
    実測: その誤りのまま 24手 打って、正味 **+4本**しか増えませんでした
    （正しく数えると同じ 24手 で **+24本**）。

    **付け替えになる場合でも撃つ理由**: 押し出される側は A/B の情報を持たない本か、
    すでに標本の足りている群（`stat_split 対照(前)` は 316本 生きています）の本です。
    **再生の総数は減らず、実験の情報だけが増えます。**

    押し出した先が**足りない群の本だった**場合、その群の不足はその場で数え直され、
    次の手で埋めます（だから手の数が、最初の不足より多くなることがあります）。
    """
    out = ["", "=== 手（`scripts/reschedule.py --move` を、この順で）==="]
    was_live = board.live()
    #: (前提, 群, まだ足りない本数)。**埋め方は、置き終えてから言います**
    shortfalls: list[tuple[str, str, int]] = []
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
                # **どう埋めるかは、全部の手を置き終えてから言うこと**（04:4x に直した）。
                # ここで数えると、**このあとの群がまだ使う枠まで「空いている」と
                # 数えます** —— 実物で 3本 空きと出したのに、そのうち3本とも
                # 次の群の置き先でした。`shortfalls` に溜めて、下でまとめて言います。
                shortfalls.append((key, g, still))
                out.append(f"  [!] {key}/{g} は **まだ {still}本 足りません** —— "
                           "動かせる死に枠を使い切りました"
                           "（測定の窓の日と公開済みは動かせません）")
    if shortfalls:
        out.append("")
        out.append("=== 足りないぶんを、どう埋めるか"
                   "（**上の手を全部 置いたあとの空きで数えています**）===")
        for key, g, still in shortfalls:
            out.append(f"  {key}/{g}  あと {still}本 —— " + _how_to_fill(board, key, still))
    if not board.moves:
        out.append("  （動かす手はありません）")
        return out

    now_live = board.live()
    out.append("")
    out.append("=== この入れ替えで、群ごとに何本 増えるか"
               "（上限に余りのある日へ置けたぶんは**総数も増えます**）===")
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
               f"（**{len(now_live) - len(was_live):+d}**）"
               "  上限に余りのある日へ置けたぶん。0 なら全部 付け替えです")
    return out


def plan_all(board: Board) -> list[str]:
    """**A/B に限らず、0再生の枠に居る本を全部** 生きた枠へ逃がす。

    ## なぜ別の手にするか（2026-08-26 に数えて足した）

    上の `plan()` は**判定に要る本**だけを直します。生きる枠は 1日 `cap()` 本 ちょうどで
    固定なので、あれは**付け替え**でした（生き返り7・死に7・差0）。

    **こちらは違います。** 予約の後ろのほう（09/20〜09/27）は**上限に余りがあります** ——
    実測 2026-08-26: 生きた枠の空き **123**、0再生の枠に居て動かせる本 **24**。
    **上限の余っている日へ逃がすぶんは、押し出す相手が居ません。**

    実測の差は**再生の中央値 718 対 2**（`day_cap.live_ids` の節）。
    24本 ぶんは、**新しい本を1本も作らずに**取り戻せます。

    **同じ日へは置き直しません**（`same_day_first=False`）。上限を超えている日で
    同じ日へ動かしても、別の1本を押し出すだけで**生きる本は増えません。**

    ## 覆る条件

    **公開は遅くなります。** 08/26 の死に枠から 09/25 の生きた枠へ移すと、
    その本が出るのは1か月 後ろです。**0再生のまま出すより良い**という判断ですが、
    これは `day_cap` の上限が本物であることに乗っています。
    **上限が上がったら（`cap()` は実測から動きます）、この手は要らなくなります。**
    """
    out = ["", "=== 0再生の枠に居る本を、上限の余っている日へ逃がす"
                "（**新しい本は1本も要りません**）==="]
    was = board.live()
    dead = sorted((v for v, w in board.at.items()
                   if v not in was and w > board.now and board.movable(v)),
                  key=lambda v: board.at[v])
    for vid in dead:
        before = board.at[vid]
        when = board.place(vid, same_day_first=False)
        if when is None:
            continue
        out.append(f"  python scripts/reschedule.py --move {vid} "
                   f"{when:%Y-%m-%dT%H:%M}   # {before:%m/%d %H:%M} から（死に枠）")
    now_live = board.live()
    gain = len(now_live) - len(was)
    out.append(f"  → 生きている本 **{len(was)} → {len(now_live)}**（**{gain:+d}本**）／"
               f"{len(board.moves)}手（{len(board.moves) * 50}単位）")
    if gain <= 0:
        out.append("  [!] **増えていません。**上限に余りのある日が無いか、"
                   "数え方がずれています。**撃たないこと**")
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
    ap.add_argument("--all", action="store_true",
                    help="A/B に限らず、0再生の枠に居る本を**全部**逃がす"
                         "（上限に余りのある日へ。**生きる本が実際に増えます**）")
    args = ap.parse_args(argv)

    board = Board(_rows())
    lines = report(board)
    if args.plan or args.apply:
        lines += plan(board) if not args.all else plan_all(board)
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
