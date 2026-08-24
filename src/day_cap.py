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



# --- **「1日N本」と「時刻の壁」は、まだ切り分けられていません** ------------------
#
# 2026-08-24 に、上の 17→10 の測り直しと同じ生データを**公開時刻の側**から並べたら、
# 別の説明が同じ数字を出すことが分かりました。
#
#     08/20  生きた 09:00〜13:30（10本） ／ 13:59 以降は 12本とも 0〜3
#     08/21  生きた 08:59〜13:30（10本） ／ 14:00 以降は 15本とも 0〜5
#     08/22  生きた 09:00〜13:30（10本） ／ 14:00 以降は 15本とも 0〜5
#
# **「1日10本の予算」と「13:30 JST で閉じる窓」は、まったく同じ数字を出します。**
# このチャンネルは**一度も 08:59 より前に公開していない**（`batch_build --hour` の
# 既定が 9 だから）ので、**どちらなのかを区別する日が1日もありません。**
#
# **視聴者の時計では説明できません** —— 死んでいる 14:00〜21:00 JST は日本の視聴の
# ピーク帯です。20:00 に出した本が 1再生 なのに、13:30 の本が 203再生 を取っています。
#
# なぜ効くか: 窓のほうなら、**09:00 より前に置いたぶんは丸ごと上積み**になります
# （05:00 から 30分きざみなら 13:30 まで 18枠 ＝ いまの 1.8倍）。**作る本数は
# 1本も増えません。** 予算のほうなら、早く置いても後ろが死ぬだけで差し引き 0 です。
#
# **切り分ける実験**: 09:00 より前から公開する日を1日作り、その日の**生きた本数**を
# 数える。10本 を超えたら「窓」、10本 のままなら「予算」。
# 2026-08-27 に 05/06/07/08時 の4本を置いてあります（09:00〜13:30 の10本はそのまま）。


def _qual_days(path: pathlib.Path | None = None):
    """上限の証拠に使える日だけを (日, [(公開時刻JST, id, 再生)], 死線) で返す。"""
    out: dict[dt.date, list] = collections.defaultdict(list)
    for vid, (pub, _h, n) in _readings(path).items():
        out[pub.date()].append((pub, vid, n))
    for d in sorted(out):
        rows = sorted(out[d])
        if len(rows) < MIN_PER_DAY:
            continue
        top = statistics.median(sorted((n for _, _, n in rows), reverse=True)[:3])
        if top < MIN_TOP_VIEWS:
            continue
        yield d, rows, top * DEAD_SHARE


MIN_GAP_MIN = 30.0     # これより詰めて出した本は死ぬ（08/21 の :15/:45 が7本とも0）


def _spaced(times: list[dt.datetime], gap_min: float = MIN_GAP_MIN) -> list[dt.datetime]:
    """**間隔で落ちるぶんを先に落とす。** 前に残した本から `gap_min` 未満のものは捨てる。

    2026-08-21 の実測: 08:59〜13:30 に 17本 出して、生きたのは :00/:30 の **10本**。
    あいだの :15/:45 の7本は 0〜2再生。**間隔の効きは、上限の話とは別の軸**なので、
    2つのモデルを比べる前にここで揃えます（揃えないと、間隔で死んだ本が
    「窓のせいで死んだ」に見えます）。
    """
    kept: list[dt.datetime] = []
    for t in sorted(times):
        if not kept or (t - kept[-1]).total_seconds() / 60.0 >= gap_min - 1.0:
            kept.append(t)
    return kept


def window(path: pathlib.Path | None = None) -> dict:
    """**上限が「1日N本」なのか「時刻の窓」なのかを、切り分けられているか。**

    2つのモデルを実測から当てはめて、**同じ数を出しているあいだは「切り分けて
    いない」と言います。** 当て推量（始まりの時刻がどれだけばらけているか）では、
    切り分けの実験が返ってきた回に自分で下りません。

        (A) 本数   生きるのは、間隔で残った本のうち **先頭から C 本**
        (B) 窓     生きるのは、間隔で残った本のうち **T までに出した本 全部**

    C は証拠の日の生きた本数、T は証拠の日で生きた本の**いちばん遅い公開時刻**。
    どちらも 08/20〜08/22 では 10 を出します（09:00 から30分きざみだと
    13:30 がちょうど10本目だから）。**05:00 から出す日を1日置けば、
    (A) は 10・(B) は 18 を出すので、その日の実測が決めます。**

    返り:
      C / T           当てはめた2つのモデルの値
      confounded      True ＝ **どの日でも2つが同じ数**（区別できていない）
      decided_by      切り分けた日（無ければ None）
      verdict         "count" / "window" / None
    """
    per_day: list[tuple[dt.date, list, float, int, int]] = []
    floor = 0
    for d, rows, line in _qual_days(path):
        n_alive = sum(1 for _p, _v, n in rows if n >= line)
        floor = max(floor, n_alive)
        per_day.append((d, rows, line, n_alive, len(rows) - n_alive))
    # **証拠になるのは `measure()` と同じ日だけ**（生きた本数が最良で、なお死んだ本がある日）。
    # 生きた本数が最良より少ない日は、上限ではなく**その日の題材が外れた**日です。
    evidence = [(d, rows, line, a) for d, rows, line, a, dead in per_day
                if dead and a >= floor]
    if not evidence:
        return {"days": 0, "C": None, "T": None, "confounded": False,
                "decided_by": None, "verdict": None, "first_pub": None,
                "last_alive": None}

    C = max(a for _d, _r, _l, a in evidence)
    alive_times = [p for _d, rows, line, _a in evidence
                   for p, _v, n in rows if n >= line]
    T = max(alive_times, key=lambda t: t.hour * 60 + t.minute)
    T_min = T.hour * 60 + T.minute
    first_pub = min((rows[0][0] for _d, rows, _l, _a in evidence),
                    key=lambda t: t.hour * 60 + t.minute)

    def predict(rows) -> tuple[int, int]:
        kept = _spaced([p for p, _v, _n in rows])
        return min(len(kept), C), sum(1 for t in kept
                                      if t.hour * 60 + t.minute <= T_min)

    decided_by = verdict = None
    for d, rows, line, a, _dead in per_day:
        pc, pw = predict(rows)
        if abs(pc - pw) < 3:
            continue                      # 2つの予測が近い日は、どちらにも読める
        near, far = sorted(((abs(a - pc), "count"), (abs(a - pw), "window")))
        # **どちらにも合っていない日で決めないこと。** 2026-08-04（登録者が9人・
        # 18:29 から7本）は 生きた2本 に対し 本数なら4・窓なら0 で、**両方から等距離**
        # です。ここを通していたので、この道具は「窓のほうが上限」と**コインの裏表で
        # 断定**していました（2026-08-24 に踏んで直した）。
        if near[0] > max(1.0, 0.25 * max(pc, pw)):
            continue                      # 実測がどちらのモデルにも乗っていない日
        if far[0] - near[0] < 2:
            continue                      # 差が付いていない
        verdict = near[1]
        decided_by = f"{d}（出した {len(rows)}本・生きた {a}本 ／ 本数なら {pc}・窓なら {pw}）"
        break

    return {"days": len(evidence), "C": C, "T": T.strftime("%H:%M"),
            "confounded": decided_by is None, "decided_by": decided_by,
            "verdict": verdict, "first_pub": first_pub.strftime("%H:%M"),
            "last_alive": T.strftime("%H:%M")}


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
        out.extend(window_lines(path))
    else:
        out.append(f"    **上限より多く出した日がまだありません**（見えている最大 {m['floor']}本）。"
                   "崩れを観測するまで、この数は既定値です")
    return out



def window_lines(path: pathlib.Path | None = None) -> list[str]:
    """**その上限が「本数」なのか「時刻の窓」なのかを、黙って断定しない。**"""
    w = window(path)
    if not w["days"]:
        return []
    if not w["confounded"]:
        which = ("**本数のほうが上限**です（早く出しても、後ろが死ぬだけ）"
                 if w["verdict"] == "count"
                 else f"**時刻の窓のほうが上限**です（**{w['T']} JST までに出した本は全部生きる**）")
        return [f"    切り分け済み: {which}",
                f"      決めた日: {w['decided_by']}"]
    return [
        "    [!] **この本数は「時刻の窓」と切り分けられていません。**",
        f"        当てはまる説明が2つあり、**どの日でも同じ数**を出します ——"
        f" (A) 1日 {w['C']}本 まで ／ (B) **{w['T']} JST** までに出した本は全部生きる。",
        f"        測れている {w['days']}日 は全部 **{w['first_pub']} JST** から始めており、"
        f"30分きざみだと {w['T']} がちょうど {w['C']}本目です。",
        "        窓のほうなら、**その時刻より前に置いたぶんは丸ごと上積み**になります"
        "（作る本数は1本も増えません）。",
        f"        切り分けるには、**{w['first_pub']} より前から公開する日**を1日作り、"
        "その日の**生きた本数**を数えること。",
    ]


if __name__ == "__main__":  # pragma: no cover
    for line in lines():
        print(line)
