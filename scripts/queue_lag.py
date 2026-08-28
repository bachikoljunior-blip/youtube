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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import day_cap, judgeable, measure_window  # noqa: E402
from src.ab_split import SETTLE_DAYS, published  # noqa: E402

JST = timezone(timedelta(hours=9))

#: 1回の `--plan` が組む入れ替えの上限。**枠（1手 100単位）を一度に使い切らないため。**
MAX_SWAPS = 40


def live_counts(before_at: dict[str, datetime],
                at: dict[str, datetime]) -> list[tuple[str, str, int, int, int]]:
    """群ごとに **(前に生きていた本数, 後で生きている本数, 要る本数)**。

    **数えるのはここ1か所だけです。** `live_cost_lines()`（人が読む行）も
    `Plan._breaks_live()`（計画が読む門）も、これを読みます ——
    この repo で通算15件 出ている「**同じことを2か所が別々に言っていて、
    片方しか読まれていない**」を、ここでも作らないため。

    **実際に作っていました**（2026-08-26 の実測）。`Plan._pull()` は
    **日付だけ**を見て入れ替え、`live_cost_lines()` が**後から**枠を数えて
    「撃たないこと」を出していました。結果:

        入れ替え 12手 まで  **33日 早まる／どの群も割らない**
        入れ替え 16手 から  35日／`opening_motion 対照(動きなし)` 8→7（要 8）
        入れ替え 24手（既定）**38日 だが、まるごと拒否 ＝ 実際に撃てるのは 0日**

    **最後の 5日 を取りに行って、33日 を捨てていました。**
    """
    from scripts import live_slots

    live_b = day_cap.live_ids([{"at": w, "video_id": v}
                               for v, w in before_at.items()])
    live_a = day_cap.live_ids([{"at": w, "video_id": v}
                              for v, w in at.items()])
    out: list[tuple[str, str, int, int, int]] = []
    for key, (groups, n) in sorted(live_slots._groups().items()):
        for g, vids in sorted(groups.items()):
            a = len([v for v in vids if v in live_b])
            b = len([v for v in vids if v in live_a])
            out.append((key, g, a, b, n))
    return out


def _how_short(floor) -> str:
    """**足りない群を、本を作らずに埋められるか。**（API 0単位）

    ## なぜ要るか（2026-08-26。**この1行が、32倍 高い手を指していました**）

    ここはずっと「**本が足りない**」とだけ書いていました。読んだ回は
    「1本 作れ」と読みます —— 生成 ＋ `videos.insert` **1,600単位**。

    **実物はそうではありませんでした。** 同じ日の
    `scripts/live_slots.py --plan` が、**1手 50単位**でこう出しています:

        opening_motion/対照(動きなし)  7本 → **8本（足ります）**
        `reschedule.py --move kH-2eghxy2w 2026-09-02T05:00`（08/26 20:00 の死に枠から）

    **足りないのは本ではなく、生きた枠に居る本でした。**
    予約は 16本 あって、生きているのが 7本 だっただけです。

    **なぜ入れ替え（この道具）では動かないか**: `Plan._swap()` は2本の `at` を
    交換するので、**(日,時刻) の集合が1つも変わりません** ——
    生きた枠の数は不変で、中身が入れ替わるだけです。
    `live_slots` は**上限に余りのある日の空き枠へ置く**ので、総数が増えます
    （実測 380 → 381）。**別の道具なのは、そこが理由です。**

    **覆る条件**: 動かせる死に枠が足りなければ、本当に本が要ります。
    そのときは「作り足すこと」と出ます —— **数えてから言うこと。**
    """
    try:
        from scripts import live_slots

        board = live_slots.Board(live_slots._rows())
        live = board.live()
        groups = live_slots._groups().get(floor.key)
        if not groups:
            return "**`python scripts/live_slots.py --plan` を見ること**"
        gmap, n = groups
        movable = 0
        for _g, vids in gmap.items():
            al = [v for v in vids if v in live]
            if len(al) >= n:
                continue
            movable += sum(1 for v in vids if v not in live and board.movable(v))
        need = sum(c for c in floor.shortfall().values() if c)
        if movable >= need:
            return (f"**死に枠から逃がせば足ります**（動かせる {movable}本／要 {need}本）"
                    "。`python scripts/live_slots.py --plan`"
                    "（**1手 50単位。新しい本は要りません**）")
        return (f"**本を {need - movable}本 作り足すこと**"
                f"（死に枠から逃がせるのは {movable}本 だけ）。"
                "`python scripts/live_slots.py --plan` で逃がせるぶんを先に")
    except Exception:                                          # noqa: BLE001
        return "**`python scripts/live_slots.py --plan` を見ること**"


def live_bad(counts: list[tuple[str, str, int, int, int]]) -> list[str]:
    """**判定に要る本を割った群**（`b < n <= a` ＝ 足りていたのに足りなくなった）。

    もともと足りていない群（`a < n`）は数えません —— それは入れ替えのせいでは
    なく、**本が足りない**という別の話です（`live_slots.py --plan` の担当）。
    """
    return [f"{key}/{g} {a}→{b}（要 {n}）"
            for key, g, a, b, n in counts if b < n <= a]


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


def _lanes() -> tuple[tuple[int, int], ...]:
    """**`batch_build` が実際に予約に渡す時刻**（ショート／長尺）。

    **写さずに実物から引きます** —— `--hour` の既定が動いたら、
    ここも一緒に動かないと、また「印字と実際が食い違う」に戻ります
    （それがこの節そのものです）。
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import batch_build as _bb
        return ((9, 0), (int(_bb.LONG_HOUR_JST), 0))
    except Exception:                                          # noqa: BLE001
        return ((9, 0), (20, 0))


_LANES = _lanes()


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

    ## **その 1〜2日 も、実際に使われる数ではありませんでした**（2026-08-26 11:5x）

    上の直しは `depth()`（32日）を `min/median`（1〜2日）に替えました。
    **どちらも、実際に置かれる日ではありません。**

    実測（この節を書いた回）。`batch_build --count 8` を撃って、
    8本が実際に取った枠:

        2026-10-06 〜 2026-10-13 の 09:00 JST（1日1本）＝ **41〜48日後**
        同じ回の `lag_lines()` の印字                    ＝ **2〜2日後**

    **20倍 外れています。** 向きも前と同じ（**実験は速い**と言う側）で、
    「実験を1つ増やす」判断を**ずっと軽く**見積もらせます。

    理由は `min/median` の取り方です。ここは
    **「予約表のどこかに出てくる時刻」を全部 集めて**、その最短と中央値を出します。
    ところが `uploader.next_publish_at(hour_jst, ...)` は
    **渡された時刻ひとつだけ**を、1日ずつ後ろへ試します
    （`src/uploader.py` の探索は `target += timedelta(days=1)` だけで、
    **時刻は一度も動きません**）。そして `batch_build` が渡す時刻は
    **ショート 09:00 ／ 長尺 20:00 の2つに固定**です（`--hour` の既定）。

    **つまり空きが手前にあっても、その車線が埋まっていれば届きません。**
    09:00 は 10/05 まで埋まっていたので、次の本は 10/06 でした。

    返り: `min_days` / `median_days` ／ `by_slot`（時刻 → 最初に空く日数）
    ＋ **`lane_days`**（`batch_build` が実際に使う時刻 → 最初に空く日数）と
    **`lane_min` / `lane_max`**。**読むのは `lane_*` のほうです。**
    `min/median` は「車線を選べたら、どこまで手前に置けるか」の上振れです。
    """
    now = now or datetime.now(JST)
    if not rows:
        return {"min_days": 0, "median_days": 0, "by_slot": {},
                "lane_days": {}, "lane_min": 0, "lane_max": 0}
    taken = _taken(rows)
    slots = sorted({hm for s in taken.values() for hm in s})
    by_slot = {hm: _first_free(taken, hm, now.date()) for hm in slots}
    waits = sorted(by_slot.values())
    # **`batch_build` が実際に渡す時刻**（`--hour` の既定）。写さずにここから引く。
    lane_days = {hm: _first_free(taken, hm, now.date()) for hm in _LANES}
    lane_waits = sorted(lane_days.values())
    # **いちばん大事なのはここです**（2026-08-27）。上の `lane_*` は
    # 「`--hour` を明示した回」の数で、**既定の回はもう通りません** ——
    # `batch_build.slots()` は時刻を書かなかった回に `live_ring()` で
    # **生きる帯の空き**を選びます。**その実物に聞くこと。写さない。**
    live = _live_days(taken, now.date())
    return {"min_days": waits[0],
            "median_days": waits[len(waits) // 2],
            "by_slot": by_slot,
            "lane_days": lane_days,
            "lane_min": lane_waits[0],
            "lane_max": lane_waits[-1],
            "live_days": live,
            "live_min": min(live) if live else None,
            "live_max": max(live) if live else None}


def _live_days(taken: dict[date, set[tuple[int, int]]], start: date,
               count: int = 8) -> list[int]:
    """**既定の回（時刻を書かない回）が実際に置く日**を、何日後かで返す。

    `batch_build.live_plan()` に**そのまま聞きます**。ここで選び方を写すと、
    向こうが動いたときに**印字と実際がまた食い違います** ——
    この節そのものが、その食い違いの記録です（`placement_days()` の註）。

    **2026-08-27 まで、ここは `live_ring()`（時刻だけ）を受け取ってから
    日を自分で探し直していました。** 答えは一致していましたが（実測で 8本 とも同値）、
    **同じ量を出す式が2本 在る**形です。`live_plan()` が日を返すようになったので、
    **探し直しをやめて、向こうが選んだ日をそのまま読みます。**
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import batch_build as _bb                              # noqa: PLC0415
        plan = _bb.live_plan(count)
    except Exception:                                          # noqa: BLE001
        return []
    return [(d - start).days for _t, d in plan]


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
    lane_detail = "／".join(
        f"{h:02d}:{m:02d}→{place['lane_days'][(h, m)]}日"
        for h, m in sorted(place["lane_days"])
    ) or "車線なし"

    out = [
        "=== 予約の順番待ち（この機械の時定数）===",
        f"  予約に入っている本 **{len(rows)}本** ／ いちばん後ろ {last}"
        f"（{d}日 先） ／ 再生が付く上限 {cap}本/日（実測）",
    ]

    # **既定の回（時刻を書かない回）**。2026-08-27 まで、ここは下の `lane_*`
    # だけを印字していて「いま作った本が予約されるのは 2〜49日後」と言っていました。
    # `batch_build.slots()` が帯の空きから選ぶようになったので、**実物に聞きます。**
    if place.get("live_min") is not None:
        out.append(
            f"  → **いま作った本が予約されるのは {place['live_min']}〜"
            f"{place['live_max']}日後**（`batch_build` の既定 ＝ "
            "`live_ring()` が**生きる帯の空き**から選ぶ。8本ぶんで数えた）")
        out.append(
            f"     `--hour` を明示した回は {place['lane_min']}〜{place['lane_max']}日後"
            f"（{lane_detail}）—— `uploader.next_publish_at()` は"
            "**時刻を動かさず、1日ずつ後ろへ**試すので、"
            "**その時刻が埋まっている日数ぶん、そのまま後ろへ落ちます**")
    else:
        out.append(
            f"  → **いま作った本が予約されるのは {place['lane_min']}〜"
            f"{place['lane_max']}日後**（{lane_detail}）。"
            "**帯の空きが読めませんでした** —— `batch_build` も既定の時刻へ倒します")
    out.append(
        f"     参考: 予約表に出てくる時刻ぜんぶの最短〜中央値は"
        f" {place['min_days']}〜{place['median_days']}日後。"
        "**この数を判断に使わないこと** —— 実測 2026-08-26、"
        "この行が「2〜2日後」と出ていた回の `batch_build --count 8` は "
        f"**41〜48日後（10/06〜10/13 の 09:00）** に置きました。いちばん後ろは {d}日 先")

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

    # **ここは 2026-08-26 まで「θ はこの待ち時間の逆数です」と書いていました。**
    # 系（Little の法則）としては合っていますが、**この機械の実装はそうではありません** ——
    # `src/arm_speed.throughput()` が返す θ は
    # `閉じた前提の件数 ÷ 最初に閉じた日からの経過日数`（**過去だけ**）で、
    # 待ちは1つも入りません。**入れ替えた回の `--reflect` は +0日 と出ます。**
    # そこを「逆数です」と書くと、撃った回が「効かなかった」と読んで手を捨てます。
    out.append(
        "  **待ちを縮めると θ（腕の回る速さ）が上がります** ——"
        " ただし `src/arm_speed.throughput()` が `eta.py` に渡している θ は"
        "**過去の実測（閉じた件数 ÷ 経過日数）**で、待ちは1つも入っていません。"
        "**縮めた直後の `eta.py --reflect` は +0日 と出ます。それが正しい**"
        "（効きは、実際に前提が早く閉じてから遅れて入る）。"
        " 予定表の側から数えた θ は `src/arm_speed.forward()`")
    return out


# --- 取り戻せる日数 ---------------------------------------------------------

def open_floors() -> list[tuple[str, str, int, list[tuple[date, str]]]]:
    """開いている前提の (key, 群, 要る本数, 群の本) —— **`MEMBER_SOURCES` から**。

    **`judgeable.floors()` を使わないこと。** あちらは `SOURCES` を回るので、
    `judgeable.ACCRUING` に入っている群（いまは `request_form`）が**落ちます** ——
    そして `request_form` は腕 `sub_rate`（`eta.py`「凍らせると +118日」）の
    ただ1つの走っている実験で、床は片群 **72本**、いま **9本 と 7本**です。
    **いちばん足りない群が、いちばん先に落ちる**形でした。
    """
    want = judgeable.deadlines()
    out: list[tuple[str, str, int, list[tuple[date, str]]]] = []
    for key, (_make, need) in judgeable.MEMBER_SOURCES.items():
        if key not in want:
            continue
        for g, ms in judgeable.members(key).items():
            out.append((key, g, int(need), sorted(ms)))
    return out


def answering(rows: list[dict]) -> tuple[dict, set[str], list[tuple[str, str, int]]]:
    """**これから公開する『再生が付く枠』の本**を、判定日を決めているかで分ける。

    返り: (日 → [枠の本数, そのうち効く本数], 効く video_id, 足りない群)

    **「どれかの群に入っている」では数えません**（2026-08-27 に一度そう書いて外した）。
    `stat_split` と `opening_motion` は `_members_by_landed()` で割るので、
    **全部の本がどちらかの群に入ります** —— その数え方だと 95% が「効く」と出て、
    **何も言っていない**ことになります。

    数えているのは「**その群の N本目までに入っているか**」だけです。
    判定日は N本目の公開日で決まるので（`_ready()`）、
    **N本目より後ろの本は、判定日を1日も動かしません。**
    """
    live = day_cap.live_ids(published())
    ans: set[str] = set()
    short: list[tuple[str, str, int]] = []
    for key, g, need, ms in open_floors():
        for _d, vid in ms[:need]:
            ans.add(vid)
        if len(ms) < need:
            short.append((key, g, need - len(ms)))
    per_day: dict[date, list[int]] = {}
    for r in rows:
        vid = str(r.get("video_id") or "")
        if vid not in live:
            continue
        d = r["at"].astimezone(JST).date()          # type: ignore[union-attr]
        cell = per_day.setdefault(d, [0, 0])
        cell[0] += 1
        if vid in ans:
            cell[1] += 1
    return per_day, ans, sorted(short, key=lambda x: -x[2])


def _need_videos(short: list[tuple[str, str, int]]) -> tuple[int, dict[str, int]]:
    """**足りない群を埋めるのに、新しいショートが何本 要るか。**

    返すのは（合計, 前提ごと）。**`band_lines()` と `supply_lines()` の両方が
    この1つを使うこと** —— 同じ問いを2か所で解くと、片方だけ直る形になります
    （この repo が通算11回 踏んでいる形。直前の実例が `ee2ec73`）。

    ## **前提をまたいで足さないこと**（2026-08-28 に直した。**19% 膨らんでいました**）

    ここは長らく `sum(n for _k, _g, n in short)` —— **足りない群ぜんぶの単純な和**
    でした。**群が1つの前提の中だけなら、それで正しい**（1本はその前提の
    どちらか片方にしか入らないので、51本 と 48本 は別々の本が要ります）。

    **ちがうのは前提をまたぐときです。** 振り分けはどれも
    **テーマIDだけを見る純関数**で（`src/script_writer.request_form` /
    `src/pipeline.slide_pace`）、**ショートは全部の前提で同時に群を持ちます。**
    実測 2026-08-28（`judgeable._short_topics()` の 400本 に両方を当てた）:

        request_form   途中あり 209 ／ 終端のみ 191   ← 400本 **ぜんぶ**が入る
        slide_pace     遅い     195 ／ 速い     205   ← 同じ 400本 **ぜんぶ**が入る

    公開済みの実物でも、`slide_pace` の 12本 のうち **11本** は
    `request_form` の群にも入っています（残り1本は `request_form` が
    `landed` を先に置いているための取りこぼし）。

    **つまり `slide_pace` の 20本 は、`request_form` のために作る本が
    そのまま埋めます。** 足すと、同じ本を2回 数えます:

        足す（旧）   51 + 48 + 12 + 8 → **119本**
        正しく解く   max(request_form 102, slide_pace 26) → **102本**

    **害は数の大きさでは済みません。** すぐ下の `supply_lines()` は
    この数を材料（実測 104本）と引き算して「**その腕は凍ったまま**」を出します ——
    **119 なら 15本 足りず、102 なら 2本 余ります。符号が変わります。**

    ## 群の中は、割合で割ること（**足し算ではありません**）

    1つの前提の中でも、単純な和は**振り分けが狙って当たる場合**の下限です。
    実際はテーマIDのハッシュで**半々に落ちる**ので、
    片群 51本 を埋めるには 51/0.4775 ≒ 107本 が要ります（実測 2026-08-28 の `request_form` は 102本）。
    **割合は書き写さず、その場で振り分けを実際に当てて測ります**
    （`SLOW_PACE_SHARE` / `MID_REQUEST_SHARE` を読むと、
    片方を変えたときにここが黙って古くなります）。

    ## 覆る条件

    - **どれか1つの前提が「ショートだけではない」形になったら**、ここの
      `max` は成り立ちません（その前提の本は他の前提の本と別物になるので）。
      いまは `ab_split` の `eligible=_shorts_only` が両方に付いています
    - 振り分けが**テーマID以外**（作った時刻・在庫の順など）を見るようになったら、
      同時に群を持つ保証が消えます。**そのときは和へ戻すこと**
    - 測る標本が 50本 未満に落ちたら、割合は使わず和（下限）へ倒します
    """
    per_key: dict[str, int] = {}
    groups: dict[str, list[tuple[str, int]]] = {}
    for k, g, n in short:
        groups.setdefault(k, []).append((g, n))
    try:
        from src import ab_split                                 # noqa: PLC0415

        tops = sorted(judgeable._short_topics())
    except Exception:                                            # noqa: BLE001
        tops = []
    for k, gs in groups.items():
        share: dict[str, float] = {}
        if len(tops) >= 50:
            exp = getattr(ab_split, "EXPERIMENTS", {}).get(k)
            split = getattr(exp, "split", None)
            if split is not None:
                hit: dict[str, int] = {}
                for t in tops:
                    try:
                        hit[str(split(t))] = hit.get(str(split(t)), 0) + 1
                    except Exception:                            # noqa: BLE001
                        hit = {}
                        break
                tot = sum(hit.values())
                if tot:
                    share = {g: c / tot for g, c in hit.items()}
        if share and all(share.get(g, 0.0) > 0 for g, _n in gs):
            per_key[k] = max(int(-(-n // share[g])) for g, n in gs)   # 切り上げ
        else:
            # **割合が測れない回は和**（＝ 振り分けが狙って当たる場合の下限）。
            per_key[k] = sum(n for _g, n in gs)
    return (max(per_key.values()) if per_key else 0), per_key


def band_lines(rows: list[dict],
               short: list[tuple[str, str, int]]) -> list[str]:
    """**足りない群を埋めるのに、あと何日 かかるか**（置ける枠の側から）。

    ## **「入れ替えろ」と言わないこと**（2026-08-27 に一度そう書いて外した）

    `gain_lines()` の入れ替えは **もう予約に在る本**しか動かせません。
    足りない群（いまは `request_form`）は**予約に 9本 と 7本 しか無い**ので、
    **入れ替えでは1本も増えません。** 増やす道は「作って帯へ置く」だけです。

    そして群は**テーマIDのハッシュ**で自動に割れるので
    （`src/script_writer.request_form`）、**特別な本は要りません** ——
    2026-08-26 19:08 JST より後に作ったショートは、どれかの群に入ります。
    **律速は「作れるか」ではなく「帯に空きがあるか」**です:

        作る速さ    13.6〜20本/日（`python -m src.supply`）
        帯の空き    下に実測（`batch_build._band_grid()` の空き枠）

    ## **平均で割らないこと**（2026-08-27 に直した。実測で 11日 楽観でした）

    ここは長らく「帯の空き枠の**1日あたり平均** ÷ 足りない本数」でした。
    **置く側はそう置きません** —— `batch_build.live_plan()`（＝ `live_ring()` の中身）は
    **手前の日から順に埋めます。** 予約は先の日ほど疎なので、
    **平均は先の空いている日に持ち上げられ、手前の詰まりを隠します。**

        平均で割ると      1日 5.7枠 → 128本 に **23日**
        実際に置くと      128本目は **+34日**（`live_plan(128)` の最後の1本）

    **11日 の差**です。しかもこの差は「材料と枠のどちらが先に尽きるか」の
    比較にそのまま乗ります（`docs/JOURNAL.md` 2026-08-26「枠と材料は釣り合っています」）。
    **平均に戻したら `tests/test_queue_lag_band_walk.py` が落ちます。**

    平均も**残して並べます** —— 消すと、次に読む側が
    「なぜ 23日 ではなく 34日 なのか」を追えません。

    ## 覆る条件

    帯の下端 `batch_build.PROVEN_FROM_MIN`（09:00）は
    **08/27 の切り分け待ち**です。「09:00 より前も生きる」と出れば
    枠は 10 → 18 に増え、ここの日数が縮みます（**半分にはなりません** ——
    `day_cap.cap()` が 1日 10本 で頭を打つので、`live_plan` の側で
    上限に達した日は後ろへ回されます）。
    その日が来たら、この節の数字が勝手に動きます（写さないこと）。
    """
    if not short:
        return []
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import batch_build                                       # noqa: PLC0415
        grid = batch_build._band_grid()
    except Exception:                                            # noqa: BLE001
        return []
    taken = _taken(rows)
    days = sorted({r["at"].astimezone(JST).date() for r in rows})  # type: ignore[union-attr]

    def _free(g: list[tuple[int, int]]) -> float:
        """1日あたり、その帯に空いている枠。**`cap()` で頭を打つこと。**

        空き枠が上限より多くても、**再生が付くのは 1日 `cap()` 本まで**です
        （`src/day_cap.py` の実測）。頭を打たないと、帯を広げた側が
        「1日 12.9本 置ける」と出て、**実際には 10本 しか生きません** ——
        この回が一度そう印字して外しました（13日 早い → 実際は 10日）。
        """
        n = sum(1 for d in days for hm in g if hm not in taken.get(d, set()))
        return min(n / max(len(days), 1), float(day_cap.cap()))

    per = _free(grid)
    need, _by_key = _need_videos(short)
    bar = "  "
    who = " / ".join(f"`{k}` {g} あと {n}本" for k, g, n in short[:2])
    out = [f"{bar}**足りないのは本で、入れ替えでは増えません**（{who}）。"
           "**作って帯へ置くこと** —— 群はテーマIDで自動に割れるので"
           "（`src/script_writer`）、ふつうのショートで埋まります"]
    walk = _walk_days(batch_build, need, grid)
    if walk is None:
        out.append(f"{bar}帯（`batch_build._band_grid()`・{len(grid)}枠/日）の空き"
                   f" **1日 {per:.1f}枠** → 足りない {need}本 に"
                   f" **{need / max(per, 0.01):.0f}日**"
                   "（**平均です。置く側は手前から埋めるので、これは楽観**）")
    else:
        last, days_n = walk
        out.append(f"{bar}帯（`batch_build._band_grid()`・{len(grid)}枠/日）に"
                   f" いまから {need}本 を置くと、**最後の1本は {last:%m/%d}"
                   f"（+{days_n}日）**"
                   " ← `batch_build.live_plan()`（**置く側と同じ手順**。手前の日から埋める）")
        out.append(f"{bar}  参考: 空き枠の**平均**で割ると 1日 {per:.1f}枠 →"
                   f" {need / max(per, 0.01):.0f}日。**{days_n - round(need / max(per, 0.01)):+d}日"
                   " ちがいます** —— 平均は、先の空いている日に持ち上げられます"
                   "（**平均のほうを判断に使わないこと**）")
    # **08/27 の切り分けが決めるのは、この差です。**
    #   `PROVEN_FROM_MIN` の註は「枠が 10 → 18 に増える」としか言っていません。
    #   増えて**何日 早まるか**を並べないと、あの測定の値打ちが誰にも見えません。
    try:
        from src import collisions                               # noqa: PLC0415
        wide = [(m // 60, m % 60)
                for m in range(int(collisions.LIVE_FROM_MIN),
                               int(collisions.LIVE_TO_MIN) + 1,
                               max(1, int(day_cap.MIN_GAP_MIN)))]
    except Exception:                                            # noqa: BLE001
        return out
    if len(wide) > len(grid) and walk is not None:
        # **(A) と (B) で符号が逆になります。** 片方だけ出すと、
        # 08/27 の切り分けの値打ちを間違えます（この節の docstring）。
        a = _walk_days(batch_build, need, wide)                 # 1日 cap 本まで
        b = _walk_days(batch_build, need, wide, cap=None)       # T までに出す
        b0 = _walk_days(batch_build, need, grid, cap=None)      # いまの帯・上限なし
        out.append(f"{bar}**帯の下端は 08/27 の切り分け待ち**です"
                   f"（`batch_build.PROVEN_FROM_MIN`）。09:00 より前も生きるなら"
                   f" {len(grid)} → {len(wide)}枠/日 —— "
                   "**値打ちは (A)/(B) で符号ごと変わります**:")
        if a is not None:
            out.append(f"{bar}  (A) 1日 {day_cap.cap()}本 まで → 最後が"
                       f" {a[0]:%m/%d}（+{a[1]}日）。いまの帯は +{walk[1]}日 なので"
                       f" **{walk[1] - a[1]:+d}日**"
                       " —— **上限のほうが先に当たるので、広げても増えません**"
                       "（広げると、いま朝より前に置いてある本が上限を食います）")
        if b is not None and b0 is not None:
            out.append(f"{bar}  (B) 13:30 までに出す（上限なし） → 最後が"
                       f" {b[0]:%m/%d}（+{b[1]}日）。同じ (B) でいまの帯なら"
                       f" +{b0[1]}日 なので **{b0[1] - b[1]:+d}日 早い**")
        out.append(f"{bar}  **だから 14:00 の切り分けは「広げるか」ではなく"
                   "「(A) か (B) か」を決めます。** (A) と出たら、"
                   "`PROVEN_FROM_MIN` を下げても 1日も早まりません")
    out.extend(_over_cap_lines(rows, grid, bar))
    return out


def _over_cap_lines(rows: list[dict], grid: list[tuple[int, int]],
                    bar: str) -> list[str]:
    """**`live_ring()` が上限を越えた日へ置く枠が、いくつ在るか**（API 0単位）。

    `batch_build.live_plan()` の上限の見方は「**その日の帯に何本 置いたか**」で、
    **帯の外に在るショートを1本も数えていません**（09:00 より前・14:00 以降）。
    (A)「1日 C本 まで」なら、そこへ置いた本は**その日の誰かを押し出すだけ**です。

    **数を写さないこと。** 予約の埋まり方で毎日 動きます。
    """
    try:
        from src import judgeable                               # noqa: PLC0415
        ids = judgeable._short_topics()
    except Exception:                                           # noqa: BLE001
        return []
    cap = int(day_cap.cap())
    band, taken = set(grid), _taken(rows)
    per: dict[date, int] = {}
    for r in rows:
        t = str(r.get("topic") or "")
        if t and t in ids:
            d = r["at"].astimezone(JST).date()                  # type: ignore[union-attr]
            per[d] = per.get(d, 0) + 1
    today = datetime.now(JST).date()
    days = [today + timedelta(days=i) for i in range(1, 61)]
    free = over = 0
    hit = 0
    for d in days:
        f = len(grid) - len(taken.get(d, set()) & band)
        if f <= 0:
            continue
        free += f
        room = cap - per.get(d, 0)
        if room <= 0:
            over += f
            hit += 1
        elif room < f:
            over += f - room
            hit += 1
    if over <= 0:
        return []
    return [
        f"{bar}[!] **`live_ring()` は「その日にショートが何本 あるか」を"
        f"見ていません**（帯の枠しか数えない）。今後60日 の帯の空き {free}枠 のうち"
        f" **{over}枠（{over / max(free, 1) * 100:.0f}%）は、その日のショートが"
        f" 既に上限 {cap}本 に届いている日**にあります（**{hit}日ぶん**）。"
        "(A) なら、そこへ置いた本はその日の誰かを押し出すだけです",
        f"{bar}    **直し方は `live_plan()` の註**（1度 入れて外しました ——"
        " 上限を並べ替えの鍵にすると手前を飛ばして遠くへ跳び、**5倍 悪化**）。"
        "**日ごと返して `YYYY-MM-DD@HH:MM` の形で渡す**のが筋ですが、"
        "その形は埋まっていたら**落ちて本が捨てになる**ので、"
        "**きょうだいとの取り合いをどう避けるかが先**です",
    ]


#: `_walk_days` の控え（1周のあいだだけ）。**永続させないこと** ——
#: 予約は回の途中で動くので、次の回は新しい過程で解き直します。
_WALK: dict = {}


def _walk_days(batch_build, need: int,
               grid: list[tuple[int, int]],
               cap: int | str | None = "auto") -> tuple[date, int] | None:
    """`need` 本を**置く側と同じ手順**で並べ、最後の1本の日と、今日からの日数。

    **平均で割らないための1本**です（`band_lines()` の docstring に実測）。
    `batch_build.live_plan()` は `live_ring()` の中身そのものなので、
    ここが出す日は**次の `batch_build` が実際に置く日**と同じ手順から来ています。

    読めなければ `None` —— 呼ぶ側は平均へ倒し、**楽観だと断って印字すること**。
    """
    plan = getattr(batch_build, "live_plan", None)
    if plan is None or need <= 0:
        return None
    # **同じ問いを2度 解かないこと**（`band_lines` と `supply_lines` が同じ数を要ります）。
    # `live_plan()` は 100本 超で数秒 かかるので、1周のうちは控えを使い回します。
    key = (need, tuple(grid), cap)
    if key in _WALK:
        return _WALK[key]
    try:
        got = plan(need, grid=grid, horizon=240, cap=cap)
    except Exception:                                            # noqa: BLE001
        return None
    if len(got) < need:
        return None
    last = got[-1][1]
    _WALK[key] = (last, (last - datetime.now(JST).date()).days)
    return _WALK[key]


def answering_lines(rows: list[dict], now: datetime | None = None) -> list[str]:
    """**枠が、開いている前提の判定日を決めているか**（API 0単位）。

    ## なぜ要るか（2026-08-27・最適化の回。この回に測って足した）

    `depth()` も `placement_days()` も `src/supply` も、**本数と日付**しか見ていません。
    ところが `eta.py` は毎回「**軌跡の腕が動くのは前提を1件閉じたときだけ。
    作る・出す・直すは軌跡の入力に入りません**」と印字しています。
    つまり枠の値打ちは「何本 置けるか」ではなく
    「**その本が、どれかの群の N本目までに入るか**」で決まります
    （判定日は N本目の公開日 ＝ `_ready()`）。

    実測（足した回・予約 367本）: これから 10/13 までの再生が付く枠 **333本**のうち、
    判定日を決めている本は **62本（19%）**。**81% は、出しても判定日を1日も動かしません。**
    そして足りない群は `request_form`（腕 `sub_rate`・床 片群 72本）の
    **あと 63本 と 65本** だけでした。

    **この数は毎日 動きます。写さないこと** —— 上の実測は「この節が何を数えるか」の例です。

    ## 何を言っていないか

    **「その本を消せ」ではありません。** 出せば再生は付き、門（登録者）には効きます。
    言っているのは「**同じ枠に、床の足りない群の本を置けば、再生は同じで
    判定日が前に来る**」だけです。

    **「入れ替えろ」でもありません**（一度そう書いて外しました。`band_lines()` の註）。
    `gain_lines()` の入れ替えは**もう予約に在る本**しか動かせず、
    足りない群は予約に 9本 と 7本 しか無いので**1本も増えません。**

    ## 覆る条件

    - 枠の外の本にも再生が付くと分かったら（`day_cap.window()` の (A)/(B) の
      切り分け）、`live_ids()` の側が広がるので、この数は自動で変わります
    - 開いている前提が全部 床に届いたら、この節は「**効かない 100%**」を出します。
      **それは異常ではありません** —— 次に測るものを決める合図です
      （そのとき下の行が「足りない群はありません」に変わります）
    """
    per_day, ans, short = answering(rows)
    if not per_day:
        return []
    days = sorted(per_day)
    tot = sum(c[0] for c in per_day.values())
    hit = sum(c[1] for c in per_day.values())
    bar = "  "
    out = ["", "=== その枠は、開いている前提に効くか（**本数ではなく中身**。API 0単位）==="]
    out.append(f"{bar}再生が付く枠 **{tot}本**（{days[0]}〜{days[-1]}）のうち、"
               f"開いている前提の群に入る本 **{hit}本（{hit / max(tot, 1):.0%}）**")
    dead = tot - hit
    out.append(f"{bar}残り **{dead}本（{dead / max(tot, 1):.0%}）は、どの群にも入りません**"
               " —— 出せば再生は付きますが、**判定に要る本数は1本も進みません**"
               "（`eta.py`「腕が動くのは前提を1件閉じたときだけ」）")
    # **この 79% を「作りすぎ」と読ませないこと**（2026-08-27 に自分で読み違えかけた）。
    #   ここに居るのは**もう作って予約に入っている本**で、群は作った時刻で決まります
    #   （`judgeable._members_by_request_form` の `built < exp.landed` で落ちる）。
    #   **入れ替えても、後から群には入りません。** 一方これから作る本は、
    #   足りない群に**自動で**入ります —— だから答えは「作るのをやめる」ではなく、
    #   「作り続ける」です。**符号が逆になる読み違えなので、同じ所に書くこと。**
    if short:
        share = _short_share()
        pct = f"（直近の実測 {share[0] / max(share[1], 1):.0%}）" if share else ""
        out.append(f"{bar}  **これは「作りすぎ」ではありません** ——"
                   " ここに居るのは**もう作って予約に入っている本**で、"
                   "群は**作った時刻**で決まります（後から入れ替えても入りません）。"
                   f"**これから作るショートは、足りない群に自動で入ります**{pct} ——"
                   " だから答えは『作るのをやめる』ではなく**『作り続ける』**です")
    run: list[date] = []
    best: list[date] = []
    for d in days:
        c = per_day[d]
        if c[1] <= 1:
            run.append(d)
            if len(run) > len(best):
                best = list(run)
        else:
            run = []
    if len(best) >= 3:
        cap = day_cap.cap()
        out.append(f"{bar}[!] **{best[0]} 〜 {best[-1]} の {len(best)}日**は、"
                   f"1日 {cap}本 のうち効くのが **1本 以下**です")
    out += band_lines(rows, short)
    out += supply_lines(short)
    # **余っている側も出すこと。** 「足りない」だけだと、
    #   **枠がどこへ行っているか**が見えません。実測 2026-08-27:
    #   `request_form` 以外の 8群 は床の **3〜20倍** に届いていました
    #   （`stat_split 対照(前)` は 316本 / 要 16本）。
    #   **答えの出た問いに本を積み続け、まだ答えの出ない問いには 16/144 しか無い** ——
    #   それがこの節の 81% の中身です。
    over = [(k, g, len(ms) - need) for k, g, need, ms in open_floors()
            if len(ms) > need]
    if over:
        # **「延べ」と書くこと。** 1本が `title_form` と `stat_split` の
        #   両方に入るので、群ごとの余りを足すと**同じ本を何度も数えます**。
        #   足すこと自体は正しい（枠がどれだけ答えの出た問いに向いているかの目安）が、
        #   **「549本 の本がある」と読まれると別の話になります。**
        out.append(f"{bar}  一方、**床に届いている {len(over)}群 の余り 延べ"
                   f" {sum(n for _k, _g, n in over):,}本**（群をまたぐ本は重複）"
                   f"（いちばん多い群 {max(over, key=lambda x: x[2])[0]}"
                   f" {max(over, key=lambda x: x[2])[1]} +{max(over, key=lambda x: x[2])[2]}本）"
                   " —— **答えの出た問いに、枠が使われています**")
    if len(short) > 2:
        out.append(f"{bar}  （ほかに床が足りない群 {len(short) - 2}件: "
                   + " / ".join(f"`{k}` {g} あと {n}本" for k, g, n in short[2:]) + "）")
    if not short:
        out.append(f"{bar}  **床が足りない群はありません** ——"
                   " いま足りないのは本ではなく、**次に立てる前提**のほうです"
                   "（`python scripts/eta.py --alloc`）")
    return out


def _short_share(days: int = 30) -> tuple[int, int] | None:
    """`judgeable.short_share()` を呼ぶだけ（**群の中身は1か所**）。"""
    try:
        return judgeable.short_share(days)
    except Exception:                                            # noqa: BLE001
        return None


def _shorts_only(keys: list[str]) -> list[str]:
    """`judgeable.shorts_only()` を呼ぶだけ（**群の中身は1か所**）。"""
    try:
        return judgeable.shorts_only(keys)
    except Exception:                                            # noqa: BLE001
        return []


def supply_lines(short: list[tuple[str, str, int]]) -> list[str]:
    """**その本を、そもそも作れるか。**（`src/supply.py` と突き合わせる。API 0単位）

    ## なぜ要るか（2026-08-27。**2つの道具が、半分ずつ言っていました**）

    すぐ上の `band_lines()` は「足りない **N本** を帯に置くと、最後の1本は M/D」と
    出します —— **置く枠の話しかしていません。** 一方 `python -m src.supply` は
    「在庫＋掃引の候補で **T本**・D日ぶん・いつ尽きる」と出します ——
    **こちらは要る本数を知りません。**

    実測 2026-08-27:

        要る    114本（`request_form` 途中あり 58 ／ 終端のみ 56。**開いた10群のうち、
                足りないのはこの2群だけ**。他8群は床の 3〜20倍 に届いています）
        枠      置ける（最後の1本は 10/01）
        材料    **110本**（在庫 22 ＋ 候補 568×0.156）。しかもこの前提が数えるのは
                **ショートだけ**（直近30日の実測 91%）→ 使えるのは **100本**
        → **14本 足りません。**

    **どちらの道具も「足りない」とは一言も言っていませんでした。**
    片方は枠が足りると言い、片方は材料の日数を言い、
    **その2つを引き算する所が、どこにも無かった**だけです。

    そして足りない前提は `request_form` ただ1件、腕は `sub_rate` ——
    `eta.py --alloc` が3回 続けて名指ししている腕で、
    **凍らせると軌跡が +126日** 動く、台帳で唯一 桁のちがう前提です。

    ## 何を数えているか

    - **材料**: `src.supply.supply()`（在庫 ＋ 掃引の候補 × `SWEEP_YIELD`）
    - **ショート率**: 直近に作った本の実測（`_short_share`）。**べた書きしないこと**
    - **ショートだけか**: 宣言ではなく**いまの群の標本**から（`_shorts_only`）

    ## 覆る条件

    - 掃引の候補が増えて材料が要る本数を超えたら、この節は「足ります」に変わり、
      **律速は枠のほうへ戻ります**（`band_lines`）
    - **床を下げて釣り合わせないこと。** `src/ab_split.floor_of()` が
      「見分けられなかっただけの実験が、効かない実験として閉じる」と言っています
    - 長尺の比率を下げれば使える本は増えますが、**4,000時間の門に入るのは長尺だけ**です
      （`scripts/drift.py`）。**どちらを取るかは、この道具は決めません**
    """
    if not short:
        return []
    need, need_by_key = _need_videos(short)
    try:
        from src import supply as _supply                        # noqa: PLC0415

        sw = _supply.sweep_novel()
        sp = _supply.supply(day_cap.cap(), novel=sw.get("novel"),
                            undecided=sw.get("undecided"))
    except Exception:                                            # noqa: BLE001
        return []
    total = int(sp.get("supply_total") or 0)
    bar = "  "
    keys = sorted({k for k, _g, _n in short})
    out = ["", "=== その本を、そもそも作れるか（**材料の側**。API 0単位）==="]
    body = f"在庫 {int(sp.get('stock') or 0)}本"
    novel = sp.get("sweep_novel")
    if novel:
        body += f" ＋ 掃引の候補 {int(novel):,}件 × {_supply.SWEEP_YIELD:g}"
    age = sw.get("age_hours")
    if age is not None:
        body += f"・掃引の点は **{age:.1f}時間前**"
    out.append(f"{bar}材料 **{total}本**（{body}）"
               + (f"・**{sp['dry_date']} に尽きる**" if sp.get("dry_date") else ""))
    usable = float(total)
    only = _shorts_only(keys)
    share = _short_share()
    if only and share:
        n_s, n_all = share
        usable = total * n_s / max(n_all, 1)
        out.append(f"{bar}このうち使えるのは**ショートだけ**"
                   f"（{' / '.join('`' + k + '`' for k in only)} は長尺を群に入れません"
                   "・いまの標本から見ています）"
                   f" —— 直近に作った {n_all}本 中 {n_s}本 が ショート"
                   f"（{n_s / max(n_all, 1):.0%}）→ **{usable:.0f}本**")
    gap = need - usable
    if gap > 0:
        out.append(f"{bar}[!] **要る {need}本 に {gap:.0f}本 足りません** ——"
                   " 枠が空いていても、いまの材料ではこの床に届きません"
                   "（＝その腕は凍ったまま。`python scripts/eta.py --alloc`）")
        und = sp.get("sweep_undecided")
        fix = [f"{bar}  **まず測り直すこと**: `python -m src.supply --measure`（約47秒・API 0単位）。"
               "実測 2026-08-27、**0.4時間前**の点で「14本 足りない」と出たものが、"
               "測り直すと **10本 余る**に変わりました（候補 568 → 735件）——"
               "**この節の結論は、点の古さで符号ごと変わります**"]
        if und:
            fix.append(f"{bar}  掃引の候補のうち **判定できていない {int(und):,}件**"
                       "（照合できる点が無いだけで、**無いと分かったのではない**）"
                       " —— ここが増えれば材料は増えます")
        fix.append(f"{bar}  **床は下げないこと**（`src/ab_split.floor_of()`）。"
                   "期限のほうを延ばすなら `python scripts/deadline_check.py`"
                   "（`falsified_if` は1文字も触らない）")
        out += fix
    else:
        out.append(f"{bar}→ **足ります**（要る {need}本 ／ 使える {usable:.0f}本）。"
                   "**律速は材料ではなく枠のほうです**（すぐ上の節）")
    lag = SETTLE_DAYS + judgeable.ANALYTICS_LAG_DAYS
    try:
        want = judgeable.deadlines()
    except Exception:                                            # noqa: BLE001
        want = {}
    walk = None
    alone: dict[str, tuple[date, int] | None] = {}
    per_key = dict(need_by_key)
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import batch_build                                       # noqa: PLC0415

        _grid = batch_build._band_grid()
        walk = _walk_days(batch_build, need, _grid)
        # **群ごとにも歩くこと**（2026-08-28）。下の註のとおり、
        #   合計だけで歩くと「その群が**最後に**埋まる場合」しか見ていません。
        for _k, _n in per_key.items():
            alone[_k] = _walk_days(batch_build, _n, _grid)
    except Exception:                                            # noqa: BLE001
        walk = None
    for key in keys:
        d = want.get(key)
        if not d:
            continue
        due = d - timedelta(days=lag)
        out.append(f"{bar}  `{key}` の期限 **{d}**（判定）"
                   f" ＝ **{due} までに公開した本**しか入りません"
                   f"（落ち着き＋Analytics の遅れ {lag}日）")
        if walk is not None:
            # **枠の側も期限に間に合うか。** ここを出さないと、
            # 「材料さえ足せば閉じる」と読めます —— 実測 2026-08-27 は
            # **材料も枠も、どちらも足りていません**でした（最後の1本が期限の翌日）。
            #
            # ## **合計だけで歩かないこと**（2026-08-28 に直した。**符号が逆に出ます**）
            #
            # ここは長らく `need`（＝足りない群 **ぜんぶ**の合計）で1回だけ歩き、
            # **その1つの日付を、群ごとの期限に順に当てて**いました。
            # つまりどの群についても「**その群が最後に埋まる場合**」しか見ていません。
            # **足りない群が2件 以上ある回は、それが全部の群について同時に真には
            # なりえません**（最後に埋まる群は1つだけです）。
            #
            # 実測 2026-08-28（足りない群 2件・合計 119本）:
            #
            #     合計で歩く   119本 → 最後 10/04  → `slide_pace` は 期限を **17日 超過**
            #     群だけで歩く  20本 → 最後 09/11  → `slide_pace` は 期限に **6日 余裕**
            #
            # **`slide_pace` の「間に合いません」は、まるごと偽**でした。
            # `request_form` も 99本 単独なら 10/01（超過 5日 → **2日**）で、
            # **2.5倍 に膨らんでいました。**
            #
            # そして直すと、**独立した2つの道具が一致します** ——
            # `scripts/deadline_check.py` は伸び率から `slide_pace` を
            # 「09-24（±10日）・期限はその帯の中」＝ **間に合う**と出しており、
            # 合計で歩いた側だけが逆を言っていました。
            #
            # **なぜ 08/27 に見つからなかったか**: あの日 足りない群は
            # `request_form` **1件だけ**で、合計 ＝ 単独 でした。
            # **この穴は、群が2件 以上ある回にしか現れません。**
            # 2026-08-27 の `ee2ec73` は「合計です」と**註を足しただけ**で、
            # **数のほうは合計のまま**でした（＝ 表示は直り、判定は直っていない）。
            last, days_n = walk
            solo = alone.get(key)
            n_key = per_key.get(key, need)
            multi = len(keys) > 1
            # **「合計」と書かないこと**（2026-08-28）。`_need_videos()` のとおり、
            #   1本のショートは**全部の前提で同時に群を持つ**ので、
            #   `need` は前提をまたいだ**和ではなく max** です。
            whose = ("" if not multi
                     else f"（{need}本 は**足りない前提 {len(keys)}件 を"
                          "ぜんぶ埋めるのに要る本数**です。"
                          "1本が全部の前提の群に同時に入るので、**和ではありません**）")
            if solo is None:
                solo = walk
            s_last, s_days = solo
            if s_last > due:
                # **順番をどう変えても間に合いません**（この群だけを最優先しても超過）。
                out.append(f"{bar}    [!] **この群だけを最優先しても間に合いません** ——"
                           f" `{key}` に要る {n_key}本 を帯へ置くと最後の1本は"
                           f" {s_last}（+{s_days}日）で、期限を {(s_last - due).days}日"
                           " 越えます。**材料を足しても、この床は期限内に埋まりません**"
                           f"（`band_lines` の帯／`src/day_cap.py` の上限）")
                if multi and last > s_last:
                    out.append(f"{bar}      **最後に回すと {last}（超過"
                               f" {(last - due).days}日）**まで伸びます{whose}")
                out.append(f"{bar}      この {(s_last - due).days}日 は**下限**です ——"
                           " `live_plan()` は**今日から全部 詰めた場合**を解いています。"
                           "実際は1周ずつ置くので、**遅れこそすれ早まりません**")
                # **この行だけで期限を書き換えないこと**（2026-08-27 に危うくやりかけた）。
                #   `scripts/deadline_check.py` は同じ床を**伸び率**から解いていて、
                #   実測 08/27 は `request_form` を **09/30・±10日** と出し、
                #   こちらの帯の歩き（10/01）と **1日** しか違いませんでした。
                #   **あちらの帯の中なら、書き換えても届く日は1日も動きません。**
                out.append(f"{bar}      **`python scripts/deadline_check.py` と"
                           "突き合わせてから動くこと** —— あちらは同じ床を伸び率で解き、"
                           "**帯（±N日）**を持っています。**その帯の中なら期限を"
                           "書き換えないこと**（動かしても届く日は1日も動きません）。"
                           "**床を下げるのは、どちらの場合も禁止**です")
            elif multi and last > due:
                # **ここが、合計で歩いていたときに丸ごと消えていた場面です。**
                #   間に合うかどうかが「作れるか」ではなく「**どの群から埋めるか**」で
                #   決まります —— つまり**この回に選べる手がある**、という意味です。
                others = [k for k in keys if k != key]
                out.append(f"{bar}    **順番で決まります**（間に合わないのは"
                           "「埋められない」ではなく「後回しにした」場合）:")
                out.append(f"{bar}      先に埋めれば **間に合います** ——"
                           f" `{key}` の {n_key}本 だけなら最後の1本は {s_last}"
                           f"（+{s_days}日）で、期限まで **{(due - s_last).days}日 余ります**")
                out.append(f"{bar}      後回しにすると **{last}（超過"
                           f" {(last - due).days}日）** ——"
                           f" {need}本 の最後になる場合{whose}")
                out.append(f"{bar}      → **`{key}` を"
                           + ("／".join(f"`{k}`" for k in others))
                           + " より先に埋めること。**"
                           "作る本数ではなく**順番**が効きます（API 0単位・材料も同じ）")
            else:
                out.append(f"{bar}    枠の側は間に合います"
                           f"（`{key}` の {n_key}本 の最後 {s_last} ≤ {due}"
                           + (f"／ぜんぶ埋める {need}本 でも {last} ≤ {due}"
                              if multi else "")
                           + "）")
    return out


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

    def _breaks_live(self) -> bool:
        """**いまの並びが、判定に要る本を割っていないか**（`live_counts()` で数える）。

        `needed()` との違い（**別のものです。両方 要ります**）:

            needed()       その本が「どれかの群の N本目まで」に入っているか＝**身元**
            _breaks_live() その本が居る枠に、**再生が付くか**＝**枠**

        `_pull()` は身元しか見ていませんでした。だから「早い枠へ移した」つもりの
        本が **死んだ枠**（その日の 10本目より後ろ）に落ち、
        群の生きた本が要る数を割ります —— `falsified_if` は
        「上回らなければ外れ（同点も外れ）」なので、
        **足りない標本は、そのまま「外れ」に化けます。**
        """
        return bool(live_bad(live_counts(self.before_at, self.at)))

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
                # **枠の門は、縮んだかより先には置きません** —— `_breaks_live()` は
                # 1回 60ms（実測・345本）かかるので、**縮んだ手だけ**に当てます。
                # 縮まない手は 99% なので、当てても捨てるだけです。
                if self.potential() < before and not self._breaks_live():
                    return True
                self._swap(mover, early_slot)      # 戻す（縮まなかった／枠を割る）
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
                           " ← **この道具では動きません**"
                           "（入れ替えは (日,時刻) の集合を1つも変えないので、"
                           f"生きた本は増えません）。{_how_short(f)}")
                continue
            mark = f"  → **{gain}日 早まる**" if gain else "  （動きません）"
            out.append(f"  {f.key:16s} 期限 {f.deadline:%m/%d}   "
                       f"判定 {b:%m/%d} → **{a:%m/%d}**{mark}")
        out.append(f"  合計 **{total}日**／入れ替え {len(self.swaps)}手"
                   f"（{len(self.swaps) * 2}回の `--move` ＝ {len(self.swaps) * 100}単位）")
        if total and not self.swaps:
            out.append("  [!] 手が0なのに日数が動いています。**数え方がずれています**")
        out.extend(theta_lines(self))
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


def _ready_by_claim() -> dict:
    """`scripts/deadline_check.py` の「判定できる日」（claim → date）。読めなければ空。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "qlag_deadline_check", ROOT / "scripts" / "deadline_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["qlag_deadline_check"] = mod
    spec.loader.exec_module(mod)
    return mod.ready_by_claim()


def _key_to_claim() -> dict[str, str]:
    """`judgeable` の key（`title_form` など）→ `hypotheses.yaml` の claim。

    yaml の**トップレベルの `key:` 欄**が正本です（実測 4件が持っています）。
    べた書きの対応表を置かないこと —— 前提が増えるたびに腐ります。
    """
    import yaml
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(
        encoding="utf-8")) or {}
    return {str(h["key"]): str(h.get("claim") or "")
            for h in (doc.get("hypotheses") or [])
            if isinstance(h, dict) and h.get("key") and not h.get("closed_on")}


def theta_lines(plan: Plan) -> list[str]:
    """**上の「合計 N日」を、到達日の単位に翻訳する。**

    ## なぜ要るか（2026-08-26・最適化の回。**桁が1つ ちがっていました**）

    `gain_lines()` の見出しは「**何日 早まるか**」で、合計を1つ出します。
    実測 2026-08-26 は **40日** でした。**主語が書いてありません。**
    その 40日 は「**4つの前提の判定日を、それぞれ何日 手前に倒せるか**の足し算」で、
    **`eta.py` の到達日が 40日 早まるという意味ではありません。**

    そして `lag_lines()` と `scripts/batch_build.py::_pull_verdicts_first()` は、
    どちらも **「θ は待ち時間の逆数です」** と書いていました。
    **コードはそうなっていません** —— `src/arm_speed.throughput()` が返すのは
    `閉じた前提の件数 ÷ 最初に閉じた日からの経過日数`、つまり**過去の実測**です。
    待ちは1つも入りません。**入れ替えた回の `eta.py --reflect` は +0日 と出ます。
    それが正しい**（過去は動かないので）。効きは、実際に前提が早く閉じてから、遅れて入る。

    **系（Little の法則）としては「待ちの逆数」で合っています。**
    間違っているのは**この機械の実装についての記述**のほうで、
    その区別が無いと、撃った回が「効かなかった」と読んで手を捨てます。

    ## だから、同じ単位で出す

    `src/arm_speed.forward()` が**予定表から θ を数えます**。入れ替えは
    予定表の日付を手前に倒すので、**その θ は撃った直後に動きます**。
    前後を並べれば、「合計 N日」が到達日の何日にあたるかが読めます。

    実測 2026-08-26（入れ替え 25手）::

        予定表の θ   今後14日 0.50 → 0.64/日（+29%）
                     今後30日 0.33 → 0.37/日（+10%）
                     今後60日 0.20 → 0.20/日（**±0**）

    **60日 窓で動かないのが本質です** —— 入れ替えは前提を1件も増やしません。
    **手前に倒すだけ**なので、長い窓では同じ数に戻ります。
    到達日への効きは **3〜4日** 相当で、印字の **40日 ではありません。**

    **それでも撃つ価値はあります**（2,500単位・投稿を1本も減らさない・
    `batch_build` が自動で先に撃つ）。**捨てる理由にしないこと。**
    直すのは**見込みの立て方**だけ —— `--moves -40` と宣言すると、
    次の回が 36日 の外れを記録します。

    ## 覆る条件

    - **`forward()` が読めない**（`deadline_check` が落ちる）ときは、
      この節ごと黙ります。**推測で数を出さないこと**
    - 入れ替えが**前提の数を増やす**ようになったら（例: 群がそろって
      `opening_motion` に日が出る）、60日 窓も動きます。そのときは
      「手前に倒すだけ」ではなくなるので、この註を書き換えること
    """
    try:
        from src import arm_speed
        ready = _ready_by_claim()
        if not ready:
            return []
        k2c = _key_to_claim()
        after_ready = dict(ready)
        moved = 0
        for key, when in plan.readies().items():
            claim = k2c.get(key)
            if claim and isinstance(when, date) and claim in after_ready:
                if after_ready[claim] != when:
                    moved += 1
                after_ready[claim] = when
        before = arm_speed.forward(ready)
        after = arm_speed.forward(after_ready)
    except Exception:
        return []

    hb, ha = before.get("horizons") or [], after.get("horizons") or []
    if not hb or len(hb) != len(ha):
        return []

    out = ["", "  --- **その「合計」は、到達日の日数ではありません** ---",
           "  上の合計は「4つの前提の判定日を、それぞれ何日 手前に倒せるか」の"
           "足し算です。`eta.py` の到達日が動くのは、"
           "**`src/arm_speed.throughput()` の θ（＝閉じた件数 ÷ 経過日数・**過去だけ**）"
           "が動いたとき**なので、**撃った直後の `--reflect` は +0日 と出ます。それが正しい。**"]
    for b, a in zip(hb, ha):
        d = a["per_day"] - b["per_day"]
        pct = (d / b["per_day"] * 100) if b["per_day"] else 0.0
        mark = f"**+{pct:.0f}%**" if pct > 0.5 else "**±0**"
        out.append(f"    予定表の θ  今後{b['days']:>2}日  "
                   f"{b['per_day']:.2f} → **{a['per_day']:.2f}/日**（{mark}）")
    out.append("  **長い窓ほど差が消えるのが本質です** —— 入れ替えは前提を1件も"
               "増やしません（手前に倒すだけ）。到達日への効きは、"
               "**短い窓の伸びを、その窓の長さのぶんだけ受け取った量**です。")
    out.append("  **`--moves` は、上の合計ではなくこちらで立てること。**"
               " 合計を写すと、次の回がその差を外れとして記録します。")
    if moved:
        out.append(f"  （予定表で日が動く前提: {moved}件"
                   f"／日の付いた開いた前提 {before.get('dated')}件）")
    return out


#: `videos.insert` 1本ぶんの単位（`src/upload_cap.py` の註と同じ）
INSERT_UNITS = 1600
#: **日枠の実測は、この機械にはありません。**
#: YouTube の公表する既定は 10,000単位ですが、このチャンネルは 1日 10〜13本
#: 上げていて、それだけで 16,000〜21,000単位 —— **既定なら毎日 初回から
#: 超えているのに、上がり続けています。** つまり**この事業の日枠は 10,000 ではない**。
#: **だからこの数で門を作らないこと**（`quota_lines` の註）。門にするのは
#: `upload_cap.quota_hits_in_window()`（**403 を実際に観測した回数**）だけです。


def _spend_lines(spend: dict) -> list[str]:
    """**この窓の単位を、誰が何に使ったか。**（`upload_cap.spend_in_window`）

    2026-08-27 まで、この節は「403 が N回」しか出しておらず、
    **尽きた原因を1行も言っていませんでした。** 実測で数えると、その窓の
    通った `videos.update` 173回 のうち **115回（66%）が同じ本の撃ち直し**
    ＝ 5,750単位 で、**日枠 1万 の6割 をそれだけで焼いています。**

    （**2026-08-28 に数え直した** —— それまでここは 273回／215回（79%）／
    10,750単位。`batch_build` が `reschedule._update` の**あとにもう1行**
    帳面へ書いていて、**同じ呼び出しが同じ秒に2行**載っていました。
    `upload_cap.dedupe_ok` の註。**「日枠は 1万ではない」も、その幻です。**）

    `repeats` が 0 に近くないうちは、`reschedule._update` の飛ばしが
    効いていないか、**2つの道具が同じ本を別々の時刻へ取り合っています。**
    どちらかは `by` の並びで分かります（名前が2つ出るなら後者）。
    """
    from src import upload_cap

    if not spend.get("ok"):
        return []
    out = [f"  この窓で通った書き込み **{spend['ok']}回**"
           f"（{spend['videos']}本・**同じ本の撃ち直し {spend['repeats']}回"
           f" ＝ {spend['repeats'] * 50:,}単位**）"]
    if spend["repeats"] > spend["videos"]:
        out.append("  [!] **撃ち直しが本数を超えています。**"
                   "`reschedule._update` の飛ばしが効いていないか、"
                   "2つの道具が同じ本を取り合っています（下の名前が2つなら後者）")
        # **2026-08-28 に、どちらかを実測で決めました ——「取り合い」のほうです。**
        # 窓 08/27 で2回以上 撃たれた 29本 を `data/uploaded.jsonl` の
        # `retimed_at` で割ると、**14本 は同じ時刻へ**（＝ 08/27 10:22Z の関門が
        # 捕まえる側）、**15本 は違う時刻へ**（＝ 素通りする側）。
        # しかも 15本 は食い違いではなく**振動**です（中央値 30日）——
        # 1つの掃きが1か月 先へ置き、19分後の掃きが1か月 手前へ引き戻します。
        # `src.upload_cap.MOVE_CAP`（1本 2回まで）で3つ目以降を落としています。
        out.append(f"       ↑ 実測 08/28: これは「取り合い」の側でした"
                   f"（違う時刻へ 15本／同じ時刻へ 14本・振動の幅 中央値 30日）。"
                   f" **1本 {upload_cap.MOVE_CAP}回まで**に切ってあります"
                   f"（`src.upload_cap.MOVE_CAP`）")
    top = list(spend.get("by", {}).items())[:4]
    if top:
        out.append("  撃ち手: " + " ／ ".join(f"{k} {v}回" for k, v in top))
    return out


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
    lines += _spend_lines(upload_cap.spend_in_window())
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
    """実物へ当てる。**1手 50単位。**片側で落ちたら、そこで止めて言い残す。

    ## ただし「もう公開済み」だけは、止めずに飛ばします（2026-08-28）

    **実測**: この日の `--plan` の**1手目**は `cJw79xThyTY` で、控えでは
    2026-10-04 の予約、**実物は 08-28 11:00:08Z に公開済み**でした
    （きょうだいの回が動かし、控えはまだ merge されていない）。
    公開済みの本に `publishAt` は立たないので、そこで 400 が返ります ——
    そして**この関数は最初の失敗で全部を止める**ので、

        16手（合計 **34日**・`opening_motion` だけで **30日**）→ **0/16**

    **幻が1行あるだけで、入れ替えは丸ごと落ちます。**
    `queue_lag` の 34日 が **3周 印字されて1度も当たっていない**のは、
    「この役の口からは `--apply` が通らない」（08/28 の前の回）だけでなく、
    **通しても1手目で死ぬ**からでした。

    ## 飛ばすのは「組ごと」です（**片側だけ当てないこと**）

    `moves()` は **2行で1組**（早める本 → 後ろへ送る本）。**先の1手が
    落ちたときに後の1手だけ当てると、後ろへ送る側だけが動きます** ——
    早める本は動かないので、**その群の本が1本 遠のくだけの純損**です。
    だから前半が飛んだ組は、後半も撃ちません。
    （**後半だけが公開済み**だった組は、前半をそのまま残します ——
    早めた側は当たっており、戻す理由がありません。）
    """
    from scripts import reschedule

    done = 0
    skipped: list[str] = []

    def _one(vid: str, when: str) -> str:
        """`ok` / `skip` / `stop` のどれか。"""
        try:
            rc = reschedule.main(["--move", vid, when])
        except reschedule.AlreadyPublic as e:      # pragma: no cover - 念のため
            print(f"[queue_lag] {vid} は飛ばします: {e}", flush=True)
            return "skip"
        except SystemExit as e:
            if e.code:
                print(f"[queue_lag] {vid} で止まりました: {e}."
                      " **`--plan` を撃ち直して残りを当てること**", flush=True)
                return "stop"
            return "ok"
        except Exception as e:  # pragma: no cover - 実物の口
            print(f"[queue_lag] {vid} で落ちました: {e}."
                  " **`--plan` を撃ち直して残りを当てること**", flush=True)
            return "stop"
        if rc == reschedule.RC_ALREADY_PUBLIC:
            print(f"[queue_lag] {vid} は**もう公開済み**でした。"
                  " この組は飛ばします（**控えはもう直っています**）", flush=True)
            return "skip"
        return "ok"

    def _record() -> None:
        """**当たった数を、呼ぶ側から読める所へ置く**（`_note_apply` が使う）。
        予定の数を帳面へ書いていたのを 2026-08-28 に直した ―― あの docstring。"""
        try:
            plan.applied = done                    # type: ignore[attr-defined]
            plan.skipped_public = list(skipped)    # type: ignore[attr-defined]
        except Exception:                          # noqa: BLE001
            pass

    moves = plan.moves()
    for i in range(0, len(moves), 2):
        pair = moves[i:i + 2]
        first = _one(*pair[0])
        if first == "stop":
            _record()
            return 1
        if first == "skip":
            skipped.append(pair[0][0])
            continue                      # **後半は撃ちません**（純損になる）
        done += 1
        if len(pair) < 2:
            continue
        second = _one(*pair[1])
        if second == "stop":
            _record()
            return 1
        if second == "skip":
            skipped.append(pair[1][0])
            continue
        done += 1

    _record()
    print(f"[queue_lag] {done}回 動かしました（{done * 50}単位）")
    if skipped:
        print(f"[queue_lag] **もう公開済みで飛ばした本: {len(skipped)}本**"
              f"（{', '.join(skipped[:8])}）。控えは実物へ直しました ——"
              " **`--plan` を撃ち直すと、この本は予約から消えています**",
              flush=True)
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
    counts = live_counts(plan.before_at, plan.at)
    bad = live_bad(counts)
    out = ["", "=== この入れ替えで、判定に要る本を割らないか"
                "（`src/day_cap.py` の実測の枠で数える）==="]
    for key, g, a, b, n in counts:
        if a == b:
            continue
        mark = "   ← [!] **要る本数を割ります**" if b < n <= a else ""
        out.append(f"  {key:16s} {g:14s} {a:4d} → **{b:4d}**"
                   f"（{b - a:+d}／要 {n}）{mark}")
    if len(out) == 2:
        out.append("  （どの群も動きません）")
    if bad:
        # **ここに来たら、`Plan._pull()` の門が抜けています。**
        # 2026-08-26 以降、計画そのものが枠を割る手を採らないので、
        # この節は「割らない」ことの**確認**であって、拒否の場ではありません。
        out.append("  [!] **撃たないこと。** " + " / ".join(bad)
                   + "。判定日を早めるために、**判定そのものを壊しています。**"
                     "`python scripts/live_slots.py --plan` で枠のほうを先に直すこと"
                     "（**`Plan._pull()` の門が抜けています。**"
                     "`tests/test_queue_lag_live.py` を見ること）")
    return out, not bad


def report(plan: Plan | None = None) -> list[str]:
    plan = plan or Plan()
    out = lag_lines(plan.rows, plan.now)
    out += answering_lines(plan.rows, plan.now)
    plan.improve()
    out += plan.gain_lines()
    return out


PROGRESS = ROOT / "data" / "queue_lag.jsonl"


def _stamp(readies: dict) -> dict:
    """判定日の姿を、そのまま帳面に置ける形へ（`date` → `"YYYY-MM-DD"`）。"""
    return {k: (v.isoformat() if v else None) for k, v in readies.items()}


def _last_apply() -> dict | None:
    """**前の `--apply` が、何を約束して何手 撃ったか。**"""
    import json

    if not PROGRESS.exists():
        return None
    last = None
    for line in PROGRESS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last = json.loads(line)
        except ValueError:
            continue
    return last


def _note_apply(before: dict, promised: dict, moves: int,
                skipped: list[str] | None = None) -> None:
    """**`moves` は「実際に当たった手の数」です。予定の数ではありません。**

    2026-08-28 に直しました。ここは長らく `len(plan.swaps) * 2`（＝**組んだ手の
    数**）を書いていて、`apply_moves` が途中で止まった回も**満額で記録**して
    いました。実測（`data/queue_lag.jsonl`・08/27 の4行）:

        帳面   moves 28 / 24 / 20 / 20 …… `opening_motion` を 09/06〜09/07 と約束
        実際   判定日は **10/07 のまま**。08/28 に撃ち直しても同じ手が出てくる

    **止まった理由は、その窓の1手目が「もう公開済み」だったこと**でした
    （`reschedule.AlreadyPublic`）。**帳面のほうは、それを1文字も書いていません。**
    「約束したのに動かない」の原因を探す側が、**当たった数が 0 だったことを
    帳面から知れませんでした。**

    **覆る条件**: `apply_moves` が「途中で止まる」形をやめたとき
    （全部の手が独立に当たるようになったら、予定と実績は一致します）。
    """
    import json

    from src import dupes

    # **検査から本物の帳面へは書きません**（2026-08-28 に踏んだ。
    # 理由と実測は `src/dupes._may_write_ledger`）。この行が読まれるのは
    # `stuck_lines()` の「前の `--apply` が1日も動かしていないなら撃ち直さない」で、
    # **検査の書いた約束が1行 入るだけで、本物の手が「もう撃った」に化けます。**
    if not dupes.may_write_path(PROGRESS):
        return
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "before": _stamp(before), "promised": _stamp(promised),
           "moves": moves}
    if skipped:
        # **飛ばした本を名前で残すこと。** 数だけだと、次の回が
        # 「幻がまだ在るのか、もう直ったのか」を帳面から言えません。
        rec["skipped_public"] = list(skipped)
    with PROGRESS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def stuck_lines(plan: "Plan") -> tuple[list[str], bool]:
    """**前の `--apply` が1日も動かしていないなら、同じ手をもう一度 撃たない。**

    ## なぜ要るか（2026-08-26 に実測で見つけた。**単位を捨てていました**）

    この道具は「入れ替えれば判定日が N日 手前に来る」と印字して撃ちますが、
    **実測では、3周 目から先は撃っても判定日が1日も動きません:**

        1回目  46手  stat_split 10/04 → 09/05 ／ opening_motion 10/16 → 09/12
        2回目  24手  （動いた）
        3回目  26手  （動いた）
        4回目  20手  **判定日 09/06 / 09/10 / 09/05 / 09/12 —— 3回目と同じ**

    それでも `--plan` は毎回「合計 12日 早まる」と出し、`--apply` は
    **20手 ＝ 1,000単位**を撃ちます。**印字と実物が食い違っています**
    （`docs/JOURNAL.md` の「印字と門のあいだで 38日 が止まっていた」と同じ形の3件目）。

    **単位は、この機械のいちばん狭い所です** —— 同じ窓で
    `refresh_thumbnail --missing` の 29本 と `live_slots --all` の 10本 が
    403 で落ちています。**空振りに 1,000単位 を渡すと、その2つが撃てません。**

    ## どう見分けるか

    深い所（なぜ動かないか）は、まだ分かっていません。**ここで止めているのは
    「前の回が動かせなかった」という実測ひとつ**です —— 前の `--apply` の
    **撃つ前の姿**と、いまの**撃つ前の姿**が同じなら、あいだの手は何も変えていません。

    **覆る条件**: 印字と実物が合うように直したら、この門は要りません
    （`plan.gain_lines()` が約束した日付に、実際に着くようになったとき）。
    """
    last = _last_apply()
    if not last or not last.get("moves"):
        return [], True
    if _stamp(plan.before) != last.get("before"):
        return [], True                     # 前の回のあと、実際に動いている
    days = [f"{k}: {v}" for k, v in sorted(_stamp(plan.before).items())]
    return ([
        "",
        "=== 前の `--apply` は、判定日を1日も動かしていません ===",
        f"  前の回: **{last['moves']}手**（{last['moves'] * 50}単位）／"
        f"  そのあと、判定日はこの姿のまま:",
        "    " + " ／ ".join(days),
        "  **同じ手をもう一度 撃ちません。** 印字（「合計 N日 早まる」）と"
        "実物が食い違っています —— **直すのは印字の側**です（`stuck_lines` に実測）。",
        "  **単位は、この機械のいちばん狭い所です。** 空振りに渡すと、"
        "同じ窓の `refresh_thumbnail --missing` と `live_slots --all` が撃てません。",
        "  どうしても撃つなら `--force-stuck`（**理由を JOURNAL に書くこと**）",
    ], False)


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
    ap.add_argument("--force-stuck", action="store_true",
                    help="**前の `--apply` が判定日を1日も動かしていなくても撃つ**"
                         "（既定は撃ちません。理由を JOURNAL に書くこと）")
    args = ap.parse_args(argv)

    plan = Plan()
    lines = lag_lines(plan.rows, plan.now)
    # **枠の「中身」は、入れ替えの話より前に出すこと。**
    #   下の `gain_lines()` は「**もう予約に在る本**を入れ替えると何日 早まるか」で、
    #   在る本しか見ません。**枠を、床の足りない群がそもそも使えていないとき**は、
    #   あちらは「動きません」としか言えず、理由がどこにも出ません。
    lines += answering_lines(plan.rows, plan.now)
    plan.improve(args.max_swaps)
    lines += plan.gain_lines()
    if args.plan or args.apply:
        lines += plan.plan_lines()
    safe = True
    moving = True
    if plan.swaps:
        # **枠の門が先です。**「何日 早まるか」より「判定を壊さないか」のほうが強い。
        cost, safe = live_cost_lines(plan)
        lines += cost
        qlines, ok = quota_lines(plan)
        lines += qlines
        # **その次が「前の回で動いたか」**（`stuck_lines` に実測）。
        slines, moving = stuck_lines(plan)
        lines += slines
    else:
        ok = True
    print("\n".join(lines))
    if args.apply:
        if not moving and not args.force_stuck:
            return 1
        if not safe:
            # **`--force-quota` では抜けられません。** あれは日枠の話で、
            # こちらは**判定そのものを壊すか**の話です。
            print("  [!] **撃ちません。**判定に要る本を割ります"
                  "（上の「割らないか」の節）。`--force-quota` では抜けられません")
            return 1
        if not ok and not args.force_quota:
            return 1
        rc = apply_moves(plan)
        # **撃った回は、必ず残すこと**（途中で止まった回も。次の回が
        # 「動いたか」を、この行と自分の姿で比べます）。
        try:
            _note_apply(plan.before, plan.readies(),
                        getattr(plan, "applied", 0),
                        getattr(plan, "skipped_public", None))
        except Exception:                                      # noqa: BLE001
            pass
        return rc
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
