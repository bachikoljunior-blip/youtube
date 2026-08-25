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
    """**予約のいちばん後ろの日まで**の日数。

    **これは「いま作った本が公開されるまでの日数」ではありません**（2026-08-26）。
    そう書いてあったので直しました —— 理由は `placement_days()` の註。
    """
    if not rows:
        return 0
    now = now or datetime.now(JST)
    return (rows[-1]["at"].date() - now.date()).days  # type: ignore[union-attr]


def _taken(rows: list[dict]) -> dict[date, set[tuple[int, int]]]:
    """日（JST）→ その日に埋まっている (時, 分)。"""
    out: dict[date, set[tuple[int, int]]] = {}
    for r in rows:
        t = r["at"].astimezone(JST)             # type: ignore[union-attr]
        out.setdefault(t.date(), set()).add((t.hour, t.minute))
    return out


def _in_window(d: date) -> bool:
    """**測定の窓の日か。**

    `uploader.next_publish_at()` は、自動で探す道では**窓の日を飛ばします**
    （その docstring の「2つの道で、止め方が違います」）。**ここも飛ばすこと** ——
    飛ばさないと「明日 置けます」と印字して、実際には置けない日を指します
    （2026-08-26 に踏んだ: 明日 08/27 は `day_cap` の切り分けの窓でした）。
    """
    try:
        return measure_window.inside(d.isoformat())
    except Exception:                                          # noqa: BLE001
        return False


def _first_free(taken: dict[date, set[tuple[int, int]]], hm: tuple[int, int],
                start: date, horizon: int = 90) -> int:
    """`uploader.next_publish_at()` と同じ探し方で、`hm` が空く最初の日までの日数。"""
    for i in range(1, horizon + 1):
        d = start + timedelta(days=i)
        if _in_window(d):
            continue                    # 窓の日は飛ばす（`next_publish_at` と同じ）
        if hm not in taken.get(d, set()):
            return i
    return horizon


def placement_days(rows: list[dict], now: datetime | None = None) -> dict:
    """**いま作った本が、実際にはいつ予約されるか。**

    ## なぜ `depth()` ではないのか（2026-08-26・最適化の回）

    `depth()` は**予約のいちばん後ろの日**を返します。`lag_lines()` はそれを
    「**いま作った本が公開されるのは N日後**」と印字し、判定日も θ も
    「税は2回」も、全部その N の上に乗っていました。

    **新しい本は、いちばん後ろには置かれません。**
    予約時刻を決めているのは `uploader.next_publish_at()` **だけ**で
    （その docstring がそう書いています）、あれは
    **指定の時刻で最初に空いている日**へ置きます。予約は密ではないので、
    空きは手前にあります。

    **実測（2026-08-26 03:5x）。** 予約 328本・いちばん後ろ 32日先。ところが:

        使われている時刻べつの「最初に空く日」   最短 **1日** ／ 中央値 **2日**
        実際に作った本が待った日数（実績）        08/24 **3.5日** ／ 08/26 **9.7日**
        `depth()` が印字していた数                **32日**

    **3〜10倍 外れています。** 外れる向きは「実験は遅い」と言うほうなので、
    **実験を1つ増やす判断を、ずっと重く見積もっていました。**

    返り: `min_days` / `median_days` ／ `by_slot`（時刻 → 最初に空く日数）
    """
    now = now or datetime.now(JST)
    if not rows:
        return {"min_days": 0, "median_days": 0, "by_slot": {}}
    taken = _taken(rows)
    slots = sorted({hm for s in taken.values() for hm in s})
    by_slot = {hm: _first_free(taken, hm, now.date()) for hm in slots}
    waits = sorted(by_slot.values())
    return {"min_days": waits[0],
            "median_days": waits[len(waits) // 2],
            "by_slot": by_slot}


def views_days(rows: list[dict], now: datetime | None = None) -> dict:
    """**その本が「再生を得られる」のはいつか。** ——`day_cap` の2つのモデルべつに。

    **置けることと、再生が付くことは別です。** `placement_days()` は前者だけ。
    `src/day_cap.py` は「1日に再生が付く上限」に**当てはまる説明が2つある**と
    言っていて（`window()` の `confounded`）、**この待ち時間はモデルで桁が変わります**:

        (A) 1日 C本 まで   → **その日の予約が C本 未満**の最初の日
        (B) T までに出す   → **T 以前に空きがある**最初の日

    実測（2026-08-26）: (A) なら **25日**、(B) なら **2日**。**12倍 ちがいます。**
    どちらが真かは `day_cap.window()` がまだ決めておらず、
    **切り分けの実測は既に予約済み**です（同じ docstring が日付を持っています）。

    **片方だけを印字しないこと。** それがこの機械の時定数 θ そのもので、
    12倍 は「実験を1つ増やすか」の判断をひっくり返します。
    """
    now = now or datetime.now(JST)
    w = day_cap.window()
    cap_n = day_cap.cap()
    try:
        hh, mm = (int(x) for x in str(w.get("T") or "23:59").split(":"))
    except ValueError:
        hh, mm = 23, 59
    cutoff_min = hh * 60 + mm

    # **本数はセットで数えないこと**（2026-08-26 に踏んだ）。同じ分に2本ある日が
    # あるので（`day_cap.ties()`: 08/27 は 5組10本）、`{(時,分)}` の大きさは
    # **本数より小さく**なり、(A) の「空きのある最初の日」が手前へずれます。
    per_day_n: dict[date, int] = {}
    per_day_min: dict[date, list[int]] = {}
    for r in rows:
        t = r["at"].astimezone(JST)               # type: ignore[union-attr]
        per_day_n[t.date()] = per_day_n.get(t.date(), 0) + 1
        per_day_min.setdefault(t.date(), []).append(t.hour * 60 + t.minute)

    gap = int(day_cap.MIN_GAP_MIN)                # 詰めて置いた本は死ぬ（実測）

    def _room_before_cutoff(mins: list[int]) -> bool:
        """`cutoff` までに、**前後 gap分 空いた**置き場が残っているか。"""
        busy = sorted(mins)
        t = 0
        for b in busy + [cutoff_min + gap]:
            if b > cutoff_min:
                b = cutoff_min + gap
            if b - t >= gap:
                return True
            t = max(t, b + gap)
            if t > cutoff_min:
                return False
        return t <= cutoff_min

    a_days = b_days = None
    for i in range(1, 91):
        d = now.date() + timedelta(days=i)
        if _in_window(d):
            continue                    # 窓の日には置けない（`next_publish_at` が飛ばす）
        if a_days is None and per_day_n.get(d, 0) < cap_n:
            a_days = i
        if b_days is None and _room_before_cutoff(per_day_min.get(d, [])):
            b_days = i
        if a_days is not None and b_days is not None:
            break
    return {"count_days": a_days, "window_days": b_days,
            "cap": cap_n, "cutoff": w.get("T"), "gap_min": gap,
            "confounded": w.get("confounded"), "verdict": w.get("verdict")}


def lag_lines(rows: list[dict], now: datetime | None = None) -> list[str]:
    """**この機械の時定数。**

    2026-08-26 まで、ここは `depth()`（＝予約のいちばん後ろの日）を
    「いま作った本が公開されるのは N日後」として印字していました。
    **新しい本はいちばん後ろには置かれません**（`placement_days()` の註）。
    いまは実際に置かれる日と、**再生が付く日**（`day_cap` の2モデルべつ）を出します。
    """
    d = depth(rows, now)
    cap = day_cap.cap()
    place = placement_days(rows, now)
    v = views_days(rows, now)
    last = rows[-1]["at"].date().isoformat() if rows else "—"  # type: ignore[union-attr]
    tail = SETTLE_DAYS + judgeable.ANALYTICS_LAG_DAYS

    out = [
        "=== 予約の順番待ち（この機械の時定数）===",
        f"  予約に入っている本 **{len(rows)}本** ／ いちばん後ろ {last}"
        f"（{d}日 先） ／ 再生が付く上限 {cap}本/日（実測）",
        f"  → **いま作った本が予約されるのは {place['min_days']}〜"
        f"{place['median_days']}日後**"
        f"（`uploader.next_publish_at()` と同じ探し方。**いちばん後ろの"
        f" {d}日 ではありません** —— 予約は疎で、空きは手前にあります）",
    ]

    a, b = v["count_days"], v["window_days"]
    if v["confounded"] and a is not None and b is not None and a != b:
        out += [
            f"  [!] **その本に再生が付く日は、まだ決まっていません**"
            f"（`day_cap.window()` が切り分けていない）:",
            f"        (A) 1日 {v['cap']}本 まで   → **{a}日後**"
            f"（＋落ち着き{SETTLE_DAYS}＋Analytics {judgeable.ANALYTICS_LAG_DAYS}"
            f" ＝ 判定 **{a + tail}日後**）",
            f"        (B) {v['cutoff']} までに出す → **{b}日後**"
            f"（同 ＝ 判定 **{b + tail}日後**）",
            f"  **{a / b:.0f}倍 ちがいます。** これが θ そのものなので、"
            "**どちらかに賭けて動かないこと** —— "
            "切り分けの実測は既に予約済みです（`src/day_cap.py` が日付を持っています）",
        ]
    else:
        eff = a if v["verdict"] == "count" else b
        eff = d if eff is None else eff
        out.append(f"  → **再生が付くのは {eff}日後**"
                   f"（`day_cap` の判定: {v['verdict'] or '未'}）。"
                   f" 判定できるのは ＋落ち着き{SETTLE_DAYS}日"
                   f" ＋Analytics {judgeable.ANALYTICS_LAG_DAYS}日 ＝ **{eff + tail}日後**")

    out.append(
        "  **`eta.py` の腕が動く速さ θ は、この待ち時間の逆数です**"
        "（`src/arm_speed.py`: rate = p · log(g) · θ）。"
        "**待ちを縮めることだけが、作る本数と無関係に θ を上げます。**")
    return out


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
        #: **入れ替える前**の割り当て。`live_cost_lines()` が前後を比べるのに使う
        self.before_at: dict[str, datetime] = dict(self.at)

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
    def gains(self) -> dict[str, int | None]:
        """前提ごとに、**入れ替えで何日 早まるか**（`None` ＝ 判定できる日が出ない）。

        **引き算はここ1か所だけです。** `gain_lines()`（人が読む行）も
        `gain_days()`（機械が読む数）も、これを読みます。
        この repo で通算15件出ている「**同じことを2か所が別々に言っていて、
        片方しか読まれていない**」を、この道具でも作らないため
        —— 印字と門が別々に数えていると、**印字が8日と言っているのに
        門が0日で撃たない**が起こります。
        """
        after = self.readies()
        out: dict[str, int | None] = {}
        for f in self.floors:
            b, a = self.before.get(f.key), after.get(f.key)
            out[f.key] = None if (b is None or a is None) else (b - a).days
        return out

    def gain_days(self) -> int:
        """**この入れ替えで取り戻せる合計日数**（API 0単位）。

        自動で撃つ側（`scripts/batch_build.py::_pull_verdicts_first`）の門です。
        **0日なら単位を使いません。**
        """
        return sum(v for v in self.gains().values() if v)

    def gain_lines(self) -> list[str]:
        g = self.gains()
        out = ["", "=== もう予約に在る本を入れ替えるだけで、何日 早まるか"
               "（**新しい本は1本も要りません**）==="]
        total = self.gain_days()
        after = self.readies()
        for f in sorted(self.floors, key=lambda f: f.deadline):
            b, a = self.before.get(f.key), after.get(f.key)
            gain = g.get(f.key)
            if gain is None or b is None or a is None:
                short = ", ".join(f"{g2} あと{c}本" for g2, c in f.shortfall().items() if c)
                out.append(f"  {f.key:16s} **判定できる日が出ません**（{short}）"
                           " ← 入れ替えでは動きません。**本が足りない**")
                continue
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


#: `videos.insert` 1本ぶんの単位（`src/upload_cap.py` の註と同じ）
INSERT_UNITS = 1600
#: **日枠の実測は、この機械にはありません。**
#: YouTube の公表する既定は 10,000単位ですが、このチャンネルは 1日 10〜13本
#: 上げていて、それだけで 16,000〜21,000単位 —— **既定なら毎日 初回から
#: 超えているのに、上がり続けています。** つまり**この事業の日枠は 10,000 ではない**。
#: **だからこの数で門を作らないこと**（`quota_lines` の註）。門にするのは
#: `upload_cap.quota_hits_in_window()`（**403 を実際に観測した回数**）だけです。


def quota_lines(plan: Plan) -> tuple[list[str], bool]:
    """**この入れ替えを撃つと、今日の投稿を止めないか。**（返り: 行, 撃ってよいか）

    ## なぜ要るか（2026-08-26。**撃つ直前に気づいた**）

    `--move` は1回 50単位で、16手なら 1,600単位です。安く見えますが、
    **同じ日枠から `videos.insert`（1本 1,600単位）が出ています。**
    実測（2026-08-25 の窓）: 既に **7本** 上がっており、
    7 × 1,600 ＝ 11,200単位 ＝ **既定の日枠 10,000 を超えています**
    （`src/upload_cap.py` の `day_quota()` が同じことを言っています ——
    「7本上げた後はまず尽きています」）。

    **この理由は 2026-08-26 03:5x に取り下げました**（下の「取り違えていた」）。
    門は残しますが、**理由は「投稿が止まるから」ではありません。**

    ## **取り違えていた**: `insert` と `update` は、別々に閉じます

    `src/auth.py` が先に測っていました ——
    **「8/17 05:2x の実測 —— `insert`(1600) が通るのに `update`(50) が 403。
    安いほうが先に閉じます」「403 は読みと `thumbnails.set` / `videos.update`
    だけを止めるので、投稿は続けること」。**

    **08/26 の実物も同じです** —— 同じ窓で **403 を 22回 観測しながら、
    投稿は 11本 通っています**（1本 1,600単位 なら 17,600単位。
    **同じ 10,000 の袋なら不可能**）。

    **つまり、入れ替えに単位を使っても投稿は減りません。**
    それでも 403 のあとに撃たないのは、**撃っても通らないから**です
    —— 止まっているのは `videos.update` そのもの。

    ## **見積りで門を作らないこと**（2026-08-26 に、作った直後に直した）

    最初の版は「上げた本数 × 1,600 が 10,000 を超えたら止める」でした。
    **その門は永久に閉じます** —— このチャンネルは 1日 10〜13本 上げていて、
    それだけで 16,000〜21,000単位。**既定の 10,000 では毎日 初回から超えます。**
    それでも上がり続けているので、**この事業の日枠は 10,000 ではありません。**

    **10,000 はこちらが持ち込んだ数で、実測ではありません。**
    見積りで止めると、**実際には撃てる回まで全部止まります** ——
    「観測していない残量を、残っていることにしない」の**裏返しの過ち**で、
    観測していない**上限**を、あることにしています。

    **だから門は実測だけで作ります**: `src/upload_cap.py` が
    **403（日枠）を実際に観測した回数**を控えています（`data/day_quota.jsonl`）。
    **この窓で1回でも観測していたら、枠は本当に尽きています。**
    見積りのほうは**参考として印字**します（止める根拠には使いません）。
    """
    from src import upload_cap

    st = upload_cap.state()
    spent = st.counted * INSERT_UNITS
    need = len(plan.swaps) * 2 * 50
    hits = upload_cap.quota_hits_in_window()
    ok = not hits
    lines = ["", "=== 枠（撃つ前に見ること）===",
             f"  この窓で上げた本 **{st.counted}本** ＝ 概算 {spent:,}単位"
             f"（`videos.insert` 1本 {INSERT_UNITS:,}。**参考。止める根拠には使いません**）",
             f"  この入れ替え **{need:,}単位**",
             f"  **日枠の 403 をこの窓で観測した回数: {len(hits)}回**（これが門）",
             f"  窓が変わるのは {st.resets_at.astimezone(JST):%m/%d %H:%M} JST"]
    if ok:
        lines.append("  → **撃てます**（403 をまだ1回も観測していません）")
    else:
        last = str(hits[-1].get("detail", ""))[:40]
        lines.append(f"  [!] **撃たないこと。枠は本当に尽きています**"
                     f"（最後の 403: {last}）。"
                     "**撃っても通りません** —— 403 が止めているのは"
                     "`videos.update` そのものです。"
                     "**窓が変わってから撃つこと。手は消えません**"
                     "（`--plan` は毎回、実物の控えから組み直します）。"
                     " どうしても今なら `--force-quota`")
    return lines, ok


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


def live_cost_lines(plan: Plan) -> tuple[list[str], bool]:
    """**この入れ替えで、判定に要る本を割らないか。**（返り: 行, 撃ってよいか）

    ## なぜ要るか（2026-08-26。**入れた日に、まだ当たっていないだけでした**）

    この道具は**日付だけ**を見て入れ替えます。ところが再生が付くかどうかは
    **その日の何本目か**で決まります（`src/day_cap.py`・実測で
    帯に入る本は再生の中央値 **718**、入らない本は **2**）。

    **つまり「早い枠へ移した」つもりが「死んだ枠へ移した」ことがありえます。**
    そうなると `ready` は早まったのに、**その群の生きた本が要る数を割る** ——
    `falsified_if` は「上回らなければ外れ（同点も外れ）」なので、
    **足りない標本はそのまま「外れ」に化けます。**

    2026-08-26 に実物で数えたときは、**たまたま**どの群も割りませんでした
    （`stat_split 処置(後)` は 13→16 で、むしろ助かっています）。
    **たまたまを門にしないこと。** ここで数えて、割るなら撃ちません。
    """
    from src import day_cap
    from scripts import live_slots

    live_now = day_cap.live_ids([{"at": w, "video_id": v}
                                 for v, w in plan.before_at.items()])
    live_next = day_cap.live_ids([{"at": w, "video_id": v}
                                  for v, w in plan.at.items()])
    out = ["", "=== この入れ替えで、判定に要る本を割らないか"
                "（`src/day_cap.py` の実測の枠で数える）==="]
    bad: list[str] = []
    for key, (groups, n) in sorted(live_slots._groups().items()):
        for g, vids in sorted(groups.items()):
            a = len([v for v in vids if v in live_now])
            b = len([v for v in vids if v in live_next])
            if a == b:
                continue
            mark = ""
            if b < n <= a:
                mark = "   ← [!] **要る本数を割ります**"
                bad.append(f"{key}/{g} {a}→{b}（要 {n}）")
            out.append(f"  {key:16s} {g:14s} {a:4d} → **{b:4d}**"
                       f"（{b - a:+d}／要 {n}）{mark}")
    if len(out) == 2:
        out.append("  （どの群も動きません）")
    if bad:
        out.append("  [!] **撃たないこと。** " + " / ".join(bad)
                   + "。判定日を早めるために、**判定そのものを壊しています。**"
                     "`python scripts/live_slots.py --plan` で枠のほうを先に直すこと")
    return out, not bad


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
    ap.add_argument("--force-quota", action="store_true",
                    help="日枠が尽きていそうでも撃つ（**投稿が止まります。**"
                         "理由を JOURNAL に書くこと）")
    args = ap.parse_args(argv)

    plan = Plan()
    lines = lag_lines(plan.rows, plan.now)
    plan.improve(args.max_swaps)
    lines += plan.gain_lines()
    if args.plan or args.apply:
        lines += plan.plan_lines()
    safe = True
    if plan.swaps:
        # **枠の門が先です。**「何日 早まるか」より「判定を壊さないか」のほうが強い。
        cost, safe = live_cost_lines(plan)
        lines += cost
        qlines, ok = quota_lines(plan)
        lines += qlines
    else:
        ok = True
    print("\n".join(lines))
    if args.apply:
        if not safe:
            # **`--force-quota` では抜けられません。** あれは日枠の話で、
            # こちらは**判定そのものを壊すか**の話です。
            print("  [!] **撃ちません。**判定に要る本を割ります"
                  "（上の「割らないか」の節）。`--force-quota` では抜けられません")
            return 1
        if not ok and not args.force_quota:
            return 1
        return apply_moves(plan)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
