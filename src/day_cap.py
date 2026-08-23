"""**1日に何本まで「再生される」か。**（API は 0 単位。読むのは `data/views.jsonl` だけ）

## なぜ要るか（2026-08-21 16:2x に測って足した）

`src/supply.py` は **「25本/日 を作れるか」**を測っています。ここが測るのは別の所で、
**「作って出したとして、その25本に再生が付くか」**です。**付きませんでした。**

実測（`data/views.jsonl`・公開から6時間以上たった読み・長尺は最初から0なので除く）:

    2026-08-20 は 25本 公開した。**11本目から先は 25本中 15本が 0〜3再生**
      #9=352  #10=1111  |  #11=0  #12=0  #13=1  #14=0 … #25=2

**これは「時刻が遅いから」ではありません。** 切り分けが1組あります:

    08/16 の 14時 = その日の **#4** → **1361再生**
    08/20 の 14時 = その日の **#12** → **0再生**
    08/20 の 13時台に3本: #9=352 / #10=1111 / **#11=0**（同じ日・同じ時刻帯・同じ齢）

**同じ時刻でも、その日の何本目かで 1361 と 0 に割れます。**
だから軸は時刻ではなく **その日の通し番号** です。

## **何本目か、ではなく何本か**（2026-08-24 に測り直した。17本 → 10本）

上の切り分けは正しいのですが、**数え方が「生きたいちばん後ろの番号」でした。**
公開の順番と、YouTube が配信する順番は**同じではありません。** 実測（08/21・32本）:

    00:00 280  00:15   1  00:30 184  00:45   5  01:00 996  01:15  1  01:30 1066
    02:00 367  02:15   0  02:30 314  02:45   0  03:00 1045  03:15 13  03:30 1097
    03:45   3  04:00 1075  04:30 190  |  05:00 以降の15本は全部 0〜5

**生きたのは :00 と :30 の 10本ちょうど**で、そのあいだに挟まれた :15/:45 の7本は
死んでいます。**番号で数えると「#17 まで生きた」＝ 上限17本**になりますが、
**実際に再生が付いた本数は 10本**です。08/20・08/22 も 25本 出して **ちょうど 10本**。

    08/20  25本 → 生きた 10本      08/21  32本 → 生きた 10本      08/22  25本 → 生きた 10本
    08/19   8本 → 生きた  8本（上限より少ない日。上限の証拠にはならない）

**3日とも 10本で一致**しているので、上限は**その日の本数**であって順番ではありません。
17本 のままだと、段1 が **1.7倍 楽観**になります（`scripts/eta.py`）。

**覆る条件**: 上限より多く出した日に、**生きた本数が 10本を超えたら**上へ動きます
（`floor` が自動で追います。定数ではありません）。

## 何を壊していたか

`scripts/eta.py` の段1 は

    days_subs_at[n] = 残りの登録者 / (n × 1本あたり再生 × 登録率)

で、**n を増やせば増やすだけ再生が増える**と読んでいました。実測は
**n が上限を超えたぶんは 0 再生**なので、25本/日 の段1 は **2.5倍 楽観**です。

## 覆る条件（**上限は測り直せます**）

上限を上へ動かせるのは、**「上限より多く出した日」に、上限より後ろの本が
再生を取ったとき**だけです（`floor` が下から、`collapse` が上から挟みます）。
1日 10本しか出していない日は、**上限が10であることの証拠になりません** ——
崩れ方を観測していないので、この道具はそういう日から上限を読みません。

**上限が YouTube 側の1日あたりの押し出し量なら、登録者が増えると上がるはず**です。
そのときは崩れる番号が後ろへ動き、ここが自動で追います（定数ではありません）。
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"

JST = dt.timezone(dt.timedelta(hours=9))

MIN_AGE_H = 6.0        # これより若い読みは「まだ伸びていない」と見分けが付かない
DEAD_SHARE = 0.05      # その日の上位3本の中央値の 5% 未満なら「再生が付いていない」
MIN_PER_DAY = 3        # 崩れを見るのに要る最低の本数
MIN_TOP_VIEWS = 50     # その日の上位3本の中央値がこれ未満なら、面に載っていない日
FALLBACK = 10          # 読みが足りないときの既定（**この日の実測そのもの**）


def _readings(path: pathlib.Path | None = None) -> dict[str, tuple[dt.datetime, float, int]]:
    """id → (公開時刻JST, 齢, 再生)。**齢は 6時間にいちばん近いものを採ります。**"""
    p = path or VIEWS
    if not p.exists():
        return {}
    first: dict[str, dt.datetime] = {}
    best: dict[str, tuple[float, int]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        at = dt.datetime.fromisoformat(r["at"].replace("Z", "+00:00"))
        pub = at - dt.timedelta(hours=r["hours"])
        if r["id"] not in first or pub < first[r["id"]]:
            first[r["id"]] = pub
        if r["hours"] < MIN_AGE_H:
            continue
        cur = best.get(r["id"])
        # **いちばん若い読みを採ります**（伸びきる前で揃えたい。齢が散ると
        # 「後ろの本は若いだけ」という別の説明が残ります）
        if cur is None or r["hours"] < cur[0]:
            best[r["id"]] = (r["hours"], r["views"])
    return {v: (first[v].astimezone(JST), h, n) for v, (h, n) in best.items() if v in first}


def by_day(path: pathlib.Path | None = None) -> dict[dt.date, list[tuple[str, int, float]]]:
    """公開日（JST）→ [(id, 再生, 齢)]。**公開の早い順**。"""
    out: dict[dt.date, list] = collections.defaultdict(list)
    for vid, (pub, h, n) in _readings(path).items():
        out[pub.date()].append((pub, vid, n, h))
    return {d: [(v, n, h) for _, v, n, h in sorted(rows)] for d, rows in out.items()}


def measure(path: pathlib.Path | None = None) -> dict:
    """**上限を、崩れた日から読む。**

    返り:
      cap        1日に何本まで再生が付くか
      floor      「ここまでは付いた」と観測できている番号（下から）
      collapse   その `floor` より後ろで崩れた、いちばん小さい番号（無ければ None）
      days       証拠に使った日
      measured   `floor` より後ろの崩れを観測しているか（False なら `cap` は既定値）

    **1本ごとの不発と、上限とを分けています。** ある日の #3 から先が 0 でも、
    別の日に #10 が 1,111再生 を取っているなら、それは上限ではなく**その3本が
    外れた**だけです。上限だと言えるのは、**これまでに効いたいちばん後ろの番号
    （`floor`）より、さらに後ろで崩れたとき**だけ。
    """
    days = by_day(path)
    qual: list[tuple[dt.date, list, float, int, int]] = []
    floor = 0
    for d, rows in sorted(days.items()):
        if len(rows) < MIN_PER_DAY:
            continue
        top = statistics.median(sorted((n for _, n, _ in rows), reverse=True)[:3])
        if top < MIN_TOP_VIEWS:
            continue                      # その日は面に載っていない。上限の話ではない
        line = top * DEAD_SHARE
        # **数えるのは「生きた本数」で、生きたいちばん後ろの番号ではありません**
        # （2026-08-24 に測り直した。理由はこのファイルの冒頭「何本目か、何本か」）。
        n_alive = sum(1 for _, n, _ in rows if n >= line)
        floor = max(floor, n_alive)
        qual.append((d, rows, line, n_alive, len(rows) - n_alive))

    probes: list[tuple[int, str]] = []
    for d, rows, line, n_alive, n_dead in qual:
        # **上限の証拠になるのは、「生きた本数が最良の日と同じで、なお死んだ本が
        # ある日」だけです。** 生きた本数が最良より少ない日は、上限ではなく
        # **その日の題材が外れた**日です（08/04 の7本で cap=2 と出た形）。
        if n_dead and n_alive >= floor:
            probes.append((n_alive + 1,
                           f"{d} {len(rows)}本→再生が付いたのは {n_alive}本"
                           f"（{n_dead}本が0）"))

    if probes:
        collapse = min(r for r, _ in probes)
        return {"cap": max(min(floor, collapse - 1), 1), "floor": floor,
                "collapse": collapse, "days": [t for _, t in probes[-3:]], "measured": True}
    return {"cap": max(FALLBACK, floor), "floor": floor, "collapse": None,
            "days": [], "measured": False}


def cap(path: pathlib.Path | None = None) -> int:
    return measure(path)["cap"]


def effective(per_day: float, path: pathlib.Path | None = None) -> float:
    """**その本数のうち、再生が付くぶん。** 上限を超えたぶんは 0 として数えます。"""
    return min(float(per_day), float(cap(path)))


def lines(path: pathlib.Path | None = None) -> list[str]:
    m = measure(path)
    out = [f"  **1日に再生が付く本数の上限: {m['cap']}本**"
           + ("（実測）" if m["measured"] else "（**崩れをまだ観測していません**・既定値）")]
    if m["measured"]:
        out.append(f"    再生が付いた本数の最大: {m['floor']}本 ／ "
                   f"それ以上出しても付かなかった: {m['collapse']}本目から")
        for d in m["days"][-3:]:
            out.append(f"      {d}")
        out.append("    **上限を超えて出したぶんは 0再生です。**本数を増やしても、"
                   "ここを超えたぶんは登録者に効きません")
    else:
        out.append(f"    **上限より多く出した日がまだありません**（見えている最大 {m['floor']}本）。"
                   "崩れを観測するまで、この数は既定値です")
    return out


if __name__ == "__main__":  # pragma: no cover
    for line in lines():
        print(line)
