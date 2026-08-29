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
- 置き先は `src/collisions.py` の**生きる帯**（`LIVE_FROM_MIN`〜`LIVE_TO_MIN` の
  30分きざみ）の空き分だけ。**ここに数を写さないこと** —— 下端は実測で動きます
  （2026-08-27 に 05:00 → 09:00。朝に置いた8本が全部0再生だった）
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
           f"（1日 {board.cap}本・間隔 {day_cap.MIN_GAP_MIN:.0f}分・"
           f"帯 {collisions.LIVE_FROM_MIN // 60:02d}:{collisions.LIVE_FROM_MIN % 60:02d}"
           f"〜{collisions.LIVE_TO_MIN // 60:02d}:{collisions.LIVE_TO_MIN % 60:02d}）==="]
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


def band_stray(board: Board) -> list[str]:
    """**(A) では生きているのに、帯の外に居る本**（＝ (B) なら 0再生 の本）。

    `board.live()`（＝ `day_cap.live_ids`）が実装しているのは
    **(A)「その日の先頭 `cap()` 本」だけ**です。帯（09:00〜13:30）は1文字も
    見ていません。だから **1日ちょうど10本 の日は、何時に置いても全部「生きている」**
    と数えます。**(B)「13:30 までに出した本が生きる」なら、そのうち帯の外は全部 0再生**です。

    実測（2026-08-29・この関数を足した回。控えの予約ぶん）:

        (A) で生きている本                446本
        **そのうち帯の外に居る本          78本**   ← (B) なら全部 0再生
        同じ日の帯に空き分があった本       78本   ← **全部 入る**

    返すのは `video_id` の一覧（公開の早い順）。**API 0単位。**
    """
    live = board.live()
    grid = set(GRID)
    out = [(w, v) for v, w in board.at.items()
           if v in live and w > board.now and board.movable(v)
           and (w.hour * 60 + w.minute) not in grid]
    out.sort()
    return [v for _, v in out]


def plan_band(board: Board, limit: int | None = None) -> list[str]:
    """**帯の外に居る本を、同じ日の帯の空き分へ入れ直す**（`--band`）。

    ## なぜ `plan_all()` と別なのか（2026-08-29・最適化の回。**実測で見つけた**）

    `plan_all()` は `same_day_first=False` で走り、その理由をこう書いています ——
    「**同じ日へは置き直しません**。上限を超えている日で同じ日へ動かしても、
    別の1本を押し出すだけで**生きる本は増えません**」。

    **その「増えません」は、(A) を真としたときだけ成り立ちます。**
    `board.live()` は `day_cap.live_ids()` で、あれが実装しているのは
    **(A)「先頭 `cap()` 本」だけ**です（`live_ids` の節に「2段 ＝ 間隔 と 本数」）。
    ところが `day_cap.window()` は **(A)/(B) を切り分けていません**
    （`confounded`。答えが出るのは 2026-09-03）。
    **つまりここは、未決着の片方だけを真として「動かす価値が無い」と結論しています。**
    `eta.py` が自分について「**凍らせた入力から出した結論**」と呼んでいるのと同じ形です。

    ## この手は、**どちらの説明でも損をしません**

        (A) 先頭 `cap()` 本が生きる   同じ日の中で時刻を早めるだけなので、
                                     **その日の生きる本数は変わりません**（±0）
        (B) 13:30 までが生きる        帯の外 → 帯の中 ＝ **その1本は生き返ります**

    だから `live_ring()` の註と同じ理屈で、**賭けになりません。**
    実測（2026-08-29・控えの予約ぶん）: **78本が対象／78本とも同じ日の帯に入り、
    (A) の生存数は 446 → 446（±0）。** (B) なら **+78本 ＝ 約5万再生**
    （帯の中の実測 655回/本）で、**いまのチャンネルの 14日ぶんの産出**にあたります。

    ## 門は1つだけ置いています

    **1手ごとに `board.live()` を数え直し、減ったら戻します。**
    (A) では ±0 のはずですが、`_spaced()`（`MIN_GAP_MIN` 未満は落とす）が
    絡むので、**「はず」で撃たないこと。** 減る手が出たら、その本は飛ばします。

    ## 覆る条件

    - **`day_cap.window()` が (A) と決めたら、この関数は要りません**（消してよい）。
      **(B) と決まったら、`plan_all()` の `same_day_first=False` のほうを直すこと**
    - 帯の外でも再生が付くと実測で出たら、`plan_all()` ごと要りません
    - **検査は `tests/test_live_slots_band.py`**
    """
    out = ["", "=== 帯の外に居る本を、同じ日の帯へ入れ直す"
                "（**(A) では ±0・(B) なら生き返る**。どちらでも損をしません）==="]
    grid = sorted(GRID)
    before = len(board.live())
    moved = 0
    stuck = 0
    for vid in band_stray(board):
        if limit is not None and moved >= limit:
            break
        was = board.at[vid]
        day = was.date()
        taken = board._taken(day)
        placed = None
        for m in grid:
            if m in taken:
                continue
            when = dt.datetime.combine(day, dt.time(m // 60, m % 60), tzinfo=JST)
            if when <= board.now:
                continue
            board.at[vid] = when
            if len(board.live()) < before:
                board.at[vid] = was          # **減る手は撃たない**（上の「門」）
                continue
            placed = when
            break
        if placed is None:
            board.at[vid] = was
            stuck += 1
            continue
        board.moves.append((vid, placed))
        moved += 1
        out.append(f"  python scripts/reschedule.py --move {vid} "
                   f"{placed:%Y-%m-%dT%H:%M}   # {was:%m/%d %H:%M} から（帯の外）")
    after = len(board.live())
    out.append(f"  → 帯の中へ入れ直せるのは **{moved}本**"
               + (f"／同じ日に空き分が無いのが {stuck}本" if stuck else "")
               + f"（{moved * 50}単位）。**(A) の生存数 {before} → {after}**"
               + ("（±0 ＝ 押し出していません）" if after >= before else
                  "  [!] **減っています。撃たないこと**"))
    if moved:
        out.append("  **(B)（13:30 までが生きる）なら、この本数がそのまま生き返ります。**"
                   "(A) なら ±0 ——`day_cap.window()` の切り分けは 2026-09-03")
    return out


#: **1本で全部を止めない**（2026-08-27 16:xx に踏んだ）。
#:
#: ここは最初の1本が落ちた時点で `return 1` していました。実測で
#: `kH-2eghxy2w` が **`invalidPublishAt`（400）** を返し、**残り 43手が
#: 1つも当たりませんでした** —— しかもその本は毎回いちばん前に並ぶので、
#: **撃ち直しても同じ所で止まります。** 「`--plan` を撃ち直して残りを当てること」
#: という案内は、この場合ぜんぶ空振りです。
#:
#: 落ちた本の正体は**もう公開済みの本**でした（`publishAt` は公開後には置けない）。
#: 控え（`data/uploaded.jsonl`）は 08/29 13:30 と言っていますが、実物は
#: **08/26 20:00 に公開済み**です。**控えと実物が食い違っている本は、
#: これからも出ます**（`git merge` で2行入った本・手で動かした本）。
#:
#: だから止め方を変えます —— **その本を飛ばして次へ進み、最後にまとめて言う。**
#: **枠が尽きた合図（403）は別**です。あれは撃つほど悪くなるので、そこで止めます。
_SKIP_REASONS = ("invalidPublishAt", "invalidVideoId", "videoNotFound",
                 "forbidden", "videoRatingDisabled")


def apply_moves(board: Board) -> int:
    from scripts import reschedule

    done = 0
    skipped: list[tuple[str, str]] = []
    for vid, when in board.moves:
        try:
            reschedule.main(["--move", vid, f"{when:%Y-%m-%dT%H:%M}"])
        except SystemExit as e:
            # **枠切れは「飛ばす」ではなく「止める」**（2026-08-27 に見つけた）。
            #
            # 下の `except Exception` に「枠が尽きたら、そこで止めること」と
            # 書いてありますが、**そこへは永久に来ません** ——
            # `reschedule._update` は日枠の 403 を **`SystemExit`** に変えて
            # 投げ、`SystemExit` は `Exception` の子ではないので、
            # **必ずこちらの handler が先に捕まえます。**
            # そしてこちらは `skipped` に積んで **`continue`** していました ＝
            # **尽きた窓で、残りの手ぜんぶを撃ち続けます。**
            # （この repo が通算11回 踏んでいる「言っていることと、
            #   している所が別」の形。08/27 の 403 が窓の中で 29→60回 に
            #   育っているのは、この往復です）
            if reschedule.is_quota_exit(e):
                print(f"[live_slots] 日枠が尽きました（{done}回 動かした時点）。"
                      " **窓が変わってから `--plan` を撃ち直すこと**", flush=True)
                return 1
            if e.code:
                skipped.append((vid, f"終了コード {e.code}"))
                continue
        except Exception as e:                            # noqa: BLE001
            text = str(e)
            if "quotaExceeded" in text or "dailyLimitExceeded" in text:
                # **枠が尽きたら、そこで止めること。** 撃つほど悪くなります。
                # （生の `HttpError` が素通りしてきた回のため。日枠は上で止めます）
                print(f"[live_slots] 日枠が尽きました（{done}回 動かした時点）。"
                      " **窓が変わってから `--plan` を撃ち直すこと**", flush=True)
                return 1
            if any(r in text for r in _SKIP_REASONS):
                skipped.append((vid, text.split('"')[1] if '"' in text else text[:60]))
                continue
            print(f"[live_slots] {vid} で落ちました: {e}."
                  " **`--plan` を撃ち直して残りを当てること**", flush=True)
            return 1
        done += 1
    print(f"[live_slots] {done}回 動かしました（{done * 50}単位）")
    if skipped:
        print(f"[live_slots] **飛ばした {len(skipped)}本**"
              "（控えと実物が食い違っている ＝ もう公開済みなど）:")
        for vid, why in skipped:
            print(f"    {vid}  {why}")
        print("    → **控えのほうが古い**ので、`python scripts/snapshot.py` で"
              "実物を積み直すこと（`videos.list` だけ ＝ 12単位）")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--plan", action="store_true", help="動かす手を出す（API 0単位）")
    ap.add_argument("--apply", action="store_true", help="そのとおりに撃つ（1手 50単位）")
    ap.add_argument("--all", action="store_true",
                    help="A/B に限らず、0再生の枠に居る本を**全部**逃がす"
                         "（上限に余りのある日へ。**生きる本が実際に増えます**）")
    ap.add_argument("--band", action="store_true",
                    help="帯の外に居る本を、**同じ日の帯の空き分**へ入れ直す"
                         "（(A) では ±0・(B) なら生き返る。どちらでも損をしない）")
    args = ap.parse_args(argv)

    board = Board(_rows())
    lines = report(board)
    if args.plan or args.apply:
        if args.band:
            lines += plan_band(board)
        else:
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
