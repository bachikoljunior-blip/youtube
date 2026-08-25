"""**同じ分に2本入っている予約を数える。**

    from src import collisions
    collisions.upcoming()        # → [{"day": "2026-08-27", "at": "09:00", "video_ids": [...]}, …]
    collisions.say()             # → status.py に出す行（無ければ空）

## なぜ計器が要るか（2026-08-25）

前の回（2383a69）は、控えを1本1行にたたんで 08/27 を**手で並べて**
同じ分の2本を見つけました。**手で並べたから見つかったのであって、
どの道具も鳴らしていません。**

    `reschedule.py --list`   「二重予約」は**同じテーマ**の重なりを見ています
                             （受け取り帳 c23c90a9 —— 長尺とショートすら区別していない）
    `status.py`              日ごとの**本数**は出しますが、分は見ていません
    `batch_build`            置くときに避けますが、**置いたあとは見ません**

`src/lanes.py` を入れて、これから置くぶんの衝突はほぼ消えます。
**ただし2つ残ります** —— (1) 既に入っている 8本（08/27 に5組・09/06 に3組）、
(2) 3つ以上の回が重なった日（車線が足りない）。**どちらも「置いたあと」なので、
計器で見つけて `reschedule.py --move` で直すしかありません。**

## なぜ捨て置けないか

`src/day_cap.py` の `MIN_GAP_MIN = 30` は「08/21 に :15/:45 で出した7本が
0〜2再生」という実測です。**同じ分の2本は、間隔0** ——
少なくとも片方はその側だと見るのが自然です（推測。同分そのものは測っていません）。

そして 08/27 は**窓の切り分けの測定日**（`src/measure_window.py`）。
そこで衝突して死んだ本は、「1日10本の上限で死んだ本」と**見分けが付きません。**
測定日の衝突は、その日の答えを1つ壊します。
"""
from __future__ import annotations

import collections
import datetime as dt

JST = dt.timezone(dt.timedelta(hours=9))


def _at(raw) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(JST)
    except (ValueError, TypeError):
        return None


def upcoming(rows: list[dict] | None = None, *, today: str | None = None) -> list[dict]:
    """**これから公開される**ぶんで、同じ分に2本以上いる組を返す。

    過ぎた日は返しません（もう動かせないので、鳴らしても手がありません）。
    `rows` を渡さなければ手元の控え（`data/uploaded.jsonl`）を読みます。**API 0単位。**
    """
    if rows is None:
        from . import dupes
        try:
            rows = dupes.ledger_rows()
        except Exception:                                    # noqa: BLE001
            return []
    if today is None:
        today = dt.datetime.now(JST).strftime("%Y-%m-%d")

    slot: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for row in rows:
        when = _at(row.get("at"))
        if when is None:
            continue
        day = when.strftime("%Y-%m-%d")
        if day < today:
            continue
        # **キーは `id`**（`dupes.ledger_rows()` が返す形。生の控えの `video_id` は
        # `_collapse` の中で `id` に変わります —— 生の名前で読むと全部 None になり、
        # **衝突が1件も見えません**。2026-08-25 に踏んだ）
        slot[(day, when.strftime("%H:%M"))].append(str(row.get("id") or "?"))

    out = []
    for (day, at), vids in sorted(slot.items()):
        # 同じIDが2行あるのは**控えの二重行**（`dupes._collapse` が畳み残したぶん）で、
        # 動画は1本です。**IDの分からない行（`?`）だけは畳みません** ——
        # 畳むと「全部 `?`」の日が1本に見えて、**衝突が丸ごと消えます。**
        seen, uniq = set(), []
        for v in vids:
            if v != "?" and v in seen:
                continue
            seen.add(v)
            uniq.append(v)
        if len(uniq) > 1:
            out.append({"day": day, "at": at, "video_ids": uniq})
    return out


def excess(hits: list[dict] | None = None) -> int:
    """**片づければ消える本数**（1つの分に3本なら2本）。"""
    hits = upcoming() if hits is None else hits
    return sum(len(h["video_ids"]) - 1 for h in hits)


# **生きる帯**（`src/day_cap.py` の実測 + `src/measure_window.py` の切り分け）。
# 08/21 の実測で 08:59〜13:30 の :00/:30 が10本とも生き、あいだの :15/:45 は7本とも
# 0〜2再生でした。**30分きざみでこの帯に置く**のが、いま分かっている最善です。
LIVE_FROM_MIN = 5 * 60          # 05:00 JST
LIVE_TO_MIN = 13 * 60 + 30      # 13:30 JST
STEP_MIN = 30
PER_DAY = 10                    # `src/day_cap.py` の実測（11本目から先が 0〜3再生）


def _latest(taken: dict[int, list[str]]) -> int | None:
    """その日にいま入っている、**いちばん遅い分**（本が1本も無ければ None）。"""
    live = [m for m, vids in taken.items() if vids]
    return max(live) if live else None


def _by_day(rows: list[dict]) -> dict[str, dict[int, list[str]]]:
    out: dict[str, dict[int, list[str]]] = collections.defaultdict(dict)
    for row in rows:
        when = _at(row.get("at"))
        if when is None:
            continue
        day = when.strftime("%Y-%m-%d")
        out[day].setdefault(when.hour * 60 + when.minute, []).append(str(row.get("id") or "?"))
    return out


def plan(rows: list[dict] | None = None, *, today: str | None = None) -> list[dict]:
    """**どれを、いつへ動かせば衝突が消えるか**を、実際の時刻まで決めて返す。

    「HH:MM」を人に埋めさせないのは、この輪では**埋める回が来ないから**です
    （`refresh_thumbnail --missing` の2本は3回続けて積み残されました）。
    日枠の戻った回が**そのまま貼れる**形にしておくこと。

    ## 測定の窓の日は、**まずその日の空き分へ寄せます**（2026-08-25 に逆へ直した）

    **ここには「窓の日からは別の日へ出す」と書いてありました。理由が事実と違いました。**
    書いてあったのは「同じ日の空きへ逃がすと 13:30 より後ろへ出る」ですが、
    逃がす先は `grid`（`LIVE_FROM_MIN`〜`LIVE_TO_MIN`）からしか採らないので、
    **13:30 より後ろの分は最初から候補にありません。**

    実物を数えると、08/27 は **05:00〜13:30 の18枠のうち14枠が埋まっていて、
    空いている4枠は全部 09:00 より前**でした（05:30 / 06:30 / 07:30 / 08:30）。

        別の日へ出す（前の版）  08/27 は 14分・19本 → 間隔で残るのは 14本
                                本数の説 **10** ／ 窓の説 **14** —— 差 4
        同じ日へ寄せる（いま）  08/27 は 18分・18本 → 間隔で残るのは 18本
                                本数の説 **10** ／ 窓の説 **18** —— 差 8

    **この差が、そのまま切り分けの分解能です。** `day_cap.window()` は
    2つの予測の近いほうを採り、`far - near < 2` なら「差が付いていない」として
    降ります。差 4 の側は、実測が 12本 に出ただけで**どちらとも言えなく**なります
    （|12-10| = |12-14|）。差 8 なら 12本 は「本数」、16本 は「窓」と読めます。

    そして `src/day_cap.py` の切り分けの節が要求しているのは、まさにこの形です ——
    **「05:00 から出す日を1日置けば、(A) は 10・(B) は 18 を出す」。**
    別の日へ出す版は、その 18 を 14 に削っていました。

    **1つだけ守ります**: 窓の日の同じ日へ寄せるとき、**その日にいま入っている
    いちばん遅い分より後ろへは出しません**（`_latest`）。後ろへ伸ばすと
    「13:30 までの本は全部生きる」の T を自分で動かすことになり、
    説そのものが検証できなくなります。**穴を埋めるだけ**にしています。
    """
    if rows is None:
        from . import dupes
        try:
            rows = dupes.ledger_rows()
        except Exception:                                    # noqa: BLE001
            return []
    if today is None:
        today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    from . import measure_window

    days = _by_day(rows)
    grid = list(range(LIVE_FROM_MIN, LIVE_TO_MIN + 1, STEP_MIN))

    def free(day: str, *, same_day: bool = False) -> list[int]:
        taken = days.get(day, {})
        # **数えるのは分ではなく本数**（同じ分に2本入っているのが、まさにこの相手です。
        # 分で数えると 09/06 は「8本」に見えて、実際は10本 —— 2026-08-25 に踏んだ）。
        # **同じ日の中で動かすときは上限を見ません** —— その日の本数は変わらないので、
        # 上限で断ると、いちばん安い直し（同じ日の空き分へ寄せる）が使えなくなります。
        if not same_day and sum(len(v) for v in taken.values()) >= PER_DAY:
            return []
        return [m for m in grid if m not in taken]

    def window(day: str) -> bool:
        try:
            return measure_window.inside(day)
        except Exception:                                    # noqa: BLE001
            return False

    horizon = sorted(d for d in days if d > today)
    out = []
    for hit in upcoming(rows, today=today):
        day, at = hit["day"], hit["at"]
        minute = int(at[:2]) * 60 + int(at[3:])
        # **残すのは1本目**（控えに先に載ったほう）。動かすのはそれ以外。
        for vid in days.get(day, {}).get(minute, [])[1:]:
            dest_days = [day] + [d for d in horizon if d != day and not window(d)]
            for dest in dest_days:
                slots = free(dest, same_day=(dest == day))
                if dest == day and window(day):
                    # **穴を埋めるだけ**。いま入っているいちばん遅い分より後ろへは
                    # 出しません（上の docstring「1つだけ守ります」）。
                    ceiling = _latest(days.get(day, {}))
                    slots = [m for m in slots if ceiling is not None and m <= ceiling]
                if not slots:
                    continue
                m = slots[0]
                days.setdefault(dest, {})[m] = [vid]
                days[day][minute] = [v for v in days[day][minute] if v != vid]
                out.append({"id": vid, "from": f"{day} {at}",
                            "to": f"{dest}T{m // 60:02d}:{m % 60:02d}",
                            "force_window": window(dest)})
                break
    return out


def say(rows: list[dict] | None = None, *, today: str | None = None) -> str:
    """`status.py` に出す文字列。衝突が無ければ空文字。"""
    hits = upcoming(rows, today=today)
    if not hits:
        return ""
    from . import measure_window

    lines = [f"=== 同じ分に2本入っている予約（**{excess(hits)}本ぶん**）===",
             "  **`reschedule.py --list` の「二重予約」は同じテーマの重なりを見ています。"
             "ここは別物です**（違うテーマが同じ分に入っている）。",
             "  間隔0は `src/day_cap.py` の `MIN_GAP_MIN=30` の外側 ——"
             "**少なくとも片方は死ぬ側**だと見るのが自然です（推測。同分そのものは未測定）。"]
    by_day: dict[str, list[dict]] = collections.defaultdict(list)
    for h in hits:
        by_day[h["day"]].append(h)
    for day in sorted(by_day):
        mark = ""
        try:
            if measure_window.inside(day):
                mark = "  ← **測定の窓**。ここの衝突は、窓の答えを1つ壊します"
        except Exception:                                    # noqa: BLE001
            pass
        times = " ".join(f"{h['at']}×{len(h['video_ids'])}" for h in by_day[day])
        lines.append(f"  {day}  {times}{mark}")
    moves = plan(rows, today=today)
    if moves:
        lines.append(f"  **そのまま貼れます**（{len(moves)}本 × 50単位 ＝ "
                     f"{len(moves) * 50}単位・日枠が要ります）:")
        for mv in moves:
            flag = " --force-window" if mv["force_window"] else ""
            lines.append(f"      python scripts/reschedule.py --move {mv['id']} "
                         f"{mv['to']}{flag}   # {mv['from']} から")
    else:
        lines.append("  [!] **逃がす先がありません**（近い日が全部 10本 か 測定の窓）。"
                     "`reschedule.py --spread` で先に均すこと。")
    lines.append("  **これから置くぶんは `src/lanes.py` が避けます。**"
                 "ここに残るのは (1) 車線を入れる前に置いたぶん (2) 3つ以上の回が重なった日 の2つだけ。")
    return "\n".join(lines)
