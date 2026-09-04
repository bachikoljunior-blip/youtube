#!/usr/bin/env python3
"""**種別（`ship_kind`）ごとに、到達日を実際に何回動かしたか。**（API 0単位・数十ms）

    from src import kind_yield
    kind_yield.measure()          # 直近5日
    kind_yield.headline()         # eta.py の頭の3行に足す1行

## なぜ要ったか（2026-09-04 昼・最適化の回。**実測で名指しした欠陥を1つ潰すために足した**）

`CLAUDE.md`「毎回の実行で必ずやること」2 は、**腕（`lever`）を先に1つ選べ**と言います。
腕の名指し（`lever_hint`）も、従ったかの記録（`lever_followed`）もあります。
**種別のほうは、どこでも選ばせていませんでした。**

その回に実測した数（`data/runs.jsonl` 直近5日・258 ship）:

    種別      回数   `moves` が 0 以外   歩留り
    fix       182          2            1.1%
    improve    32          0            0.0%
    premise    20          0            0.0%
    verdict    16          9           56.2%
    upload      6          0            0.0%
    means       2          0            0.0%

**`lever_followed=True` の 118回 のうち、115回（97%）は `moves` が 0 でした。
その 118回 の内訳は fix 65 ／ improve 24 ／ premise 18 ／ verdict 6 ／ upload 5。**

つまり **「名指しの腕に従った」という合格の印は、`CLAUDE.md` 自身が
「定義上 0日」と書いている種別（`upload`/`fix`/`means`）で取れていました。**
回は腕を正しく選び、腕に届かない仕事をして、台帳の上では従っています。
**門が測っている物が違った** —— これが「近づかない回が選ばれ続けた」理由です。

`eta.py` は因果のほうを自分で印字しています:

> **軌跡の腕が動くのは、`config/hypotheses.yaml` の前提を1件 閉じたときだけ。
> 作る・出す・直すは、軌跡の入力に入りません**

上の実測はそれと合っています（動いた 11回 のうち **9回 が `verdict`**）。
残り2回の `fix` は **`eta.py` の模型そのものを直した回**（-15日 と -2,184日）で、
「作る・出す・直す」ではなく**測り方**を直しています。**だから fix が常に無駄
という意味ではありません** —— 無駄なのは「腕に届かない fix を、腕に従ったと
数えること」のほうです。

## この道具が出す2つ

- `measure()`  種別ごとの回数・動いた回数・歩留り／`lever_followed` の実態
- `headline()` それを1行にしたもの（`eta.py` の頭の3行の直後に出る）

## 覆る条件（**この道具を消してよい日**）

1. `verdict` の歩留りが他の種別と**差が無くなったら**（名乗る条件が落ちる）。
   `measure()['significant']` が False になったら、この行は名指しをしません。
2. `eta.py` が「腕が動くのは前提を閉じたときだけ」を印字しなくなったら
   （＝ 軌跡が作る・出すを入力に取るようになったら）、種別の序列は作り直しです。
3. 台帳（`config/hypotheses.yaml`）が空になったら、`verdict` は**選べません** ——
   そのときは供給（`premise`）のほうが律速で、この行の名指しも `premise` へ移ります。
   `measure()['ledger_open']` が 0 のときは `headline()` がそう言います。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

#: **腕に届く種別**。`eta.py` が印字する因果（腕が動くのは前提を1件 閉じたとき
#: だけ）から出ています。`premise` はその燃料（閉じる相手を作る側）なので、
#: 直接は動かしませんが、供給が止まれば `verdict` が選べなくなります。
CLOSING = "verdict"
SUPPLY = "premise"

#: **`CLAUDE.md` が「定義上 0日」と書いている種別。**（同ファイル「毎回の実行で
#: 必ずやること」5）。ここに `improve` は入っていません —— 実測でも 0/32 ですが、
#: **文書が 0日 と宣言しているのは3つだけ**なので、勝手に足しません。
BY_DEFINITION_ZERO = ("upload", "fix", "means")


def _rows(days: int) -> list[dict]:
    p = ROOT / "data" / "runs.jsonl"
    if not p.exists():
        return []
    cut = (datetime.now(JST) - timedelta(days=days)).date().isoformat()
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if not isinstance(r, dict) or not r.get("ship_kind"):
            continue
        if str(r.get("at", ""))[:10] >= cut:
            out.append(r)
    return out


def _ledger_open():
    """開いている前提の件数。**読めなければ None**（推測で埋めない）。"""
    p = ROOT / "config" / "hypotheses.yaml"
    if not p.exists():
        return None
    try:
        import yaml
        y = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    items = y if isinstance(y, list) else None
    if items is None and isinstance(y, dict):
        for v in y.values():
            if isinstance(v, list):
                items = v
                break
    if not isinstance(items, list):
        return None
    return sum(1 for h in items
               if isinstance(h, dict) and not h.get("closed_on") and not h.get("verdict"))


#: **物差しの欄**（`scripts/run_marker.py` が ship ごとに積む。門1' ＝ 登録者 500人 までの日数）。
RULER_FIELD = "gate1p_days"

#: **この物差しが「1回ぶんの仕事」を分けられると名乗れる、刻みあたりの ship の上限。**
#: 1刻みに何十本も ship が入るなら、動いた日の手柄は**その日に居合わせた ship の誰か**に
#: 付くだけで、種別の差にはなりません。**2 は「1刻みに2本まで」**という意味です。
RULER_SHIPS_PER_TICK_MAX = 2.0


def ruler(days: int = 5) -> dict:
    """**物差しそのものを測る。**（`data/runs.jsonl` の `gate1p_days` を数えるだけ）

    ## なぜ要ったか（2026-09-05 未明・最適化の回。**実測で名指しした欠陥を1つ潰した**）

    この file の上の表（`measure()`）が数えているのは **`--moves`、つまり回が自分で
    打った宣言**です。`eta.py` の頭は、それを **「直近5日の実測」** と印字していました。

    差し引きの側（`moves_measured` ＝ 門1' の日数の差）は 2026-09-04 22:5x から
    積まれています。**この回が数えたら、こうでした**:

        `gate1p_days` を持つ ship   29件
        その**相異なる値**          **1個**（511.538 —— 1度も動いていない）
        `moves_measured`            28件、**全部 0.0**

    ＝ **差し引きは、定数から定数を引いていました。** 前の物差し（`traj_days`）が
    10^9 で死んでいたのと**同じ形**で、`optimized.py` はその死に方を見張る枝を
    持っていましたが、**標本が 1件でも出ると、その枝を通りません**でした。

    **そして、動き出しても足りません。** 門1' は 475人 ÷ 0.93人/日 で出ており、
    刻むのは登録が1人 増えたときだけ ＝ **1日に約1刻み**。ship は **1日 約50本**。
    **1刻みに 50本 入る物差しで ship を1本ずつ採点することは、測定ではありません。**

    ## 返す物

        n / distinct / values      欄を持つ ship の数・相異なる値の数・値そのもの
        span_h                     いちばん古い ship といちばん新しい ship の隔たり（時間）
        ticks                      値が変わった回数
        ships_per_tick             刻み1つあたりの ship（`ticks` が 0 なら n そのもの）
        frozen                     **1度も動いていない**（`distinct <= 1`）
        too_coarse                 刻みあたりの ship が `RULER_SHIPS_PER_TICK_MAX` を超える
        usable                     `frozen` でも `too_coarse` でもない
        note                       上を1行にしたもの（`headline()` が使う）

    ## 覆る条件（**この節を畳んでよい日**）

    1. `usable` が True になったら（＝ 刻みが ship の粒に追いついたら）、
       `measure()` の分子を `--moves` から `moves_measured` へ移すこと。
       **そのときは、この節ではなく `measure()` の側を書き換えます。**
    2. `run_marker` が `RULER_FIELD` を積まなくなったら、この関数は n=0 を返します
       —— そのときは「物差しが無い」であって「動いていない」ではありません。
    """
    rows = _rows(days)
    seq = [(str(r.get("at") or ""), r.get(RULER_FIELD)) for r in rows]
    seq = [(a, float(v)) for a, v in seq if isinstance(v, (int, float))]
    seq.sort(key=lambda x: x[0])
    n = len(seq)
    vals = [v for _, v in seq]
    distinct = sorted(set(vals))
    ticks = sum(1 for i in range(1, n) if vals[i] != vals[i - 1])

    span_h = None
    if n >= 2:
        try:
            a = datetime.fromisoformat(seq[0][0].replace("Z", "+00:00"))
            b = datetime.fromisoformat(seq[-1][0].replace("Z", "+00:00"))
            span_h = (b - a).total_seconds() / 3600.0
        except Exception:                                          # noqa: BLE001
            span_h = None

    spt = (n / ticks) if ticks else float(n)
    frozen = bool(n >= 2 and len(distinct) <= 1)
    too_coarse = bool(n >= 2 and not frozen and spt > RULER_SHIPS_PER_TICK_MAX)

    if n < 2:
        note = f"`{RULER_FIELD}` を持つ ship が {n}件 —— **まだ測れません**"
    elif frozen:
        one = distinct[0] if distinct else float("nan")
        note = (f"**差し引きの物差し `{RULER_FIELD}` は、この窓で1度も動いていません**"
                f"（{n}件すべて {one:g}"
                + (f"・{span_h:.1f}時間" if span_h is not None else "")
                + "）。**`moves_measured` が 0 なのは、定数から定数を引いたから**で、"
                  "「その回が近づかなかった」ではありません")
    elif too_coarse:
        note = (f"**`{RULER_FIELD}` の刻み1つに ship が {spt:.0f}本 入ります**"
                f"（{n}件・刻み {ticks}回）—— 1本ずつの採点には粗すぎます"
                f"（上限 {RULER_SHIPS_PER_TICK_MAX:g}本/刻み）")
    else:
        note = (f"`{RULER_FIELD}` は {n}件・刻み {ticks}回"
                f"（{spt:.1f}本/刻み）＝ **1本ずつ採点できます**")

    return {"field": RULER_FIELD, "n": n, "distinct": len(distinct),
            "values": distinct[:8], "span_h": span_h, "ticks": ticks,
            "ships_per_tick": spt, "frozen": frozen, "too_coarse": too_coarse,
            "usable": bool(n >= 2 and not frozen and not too_coarse), "note": note}


#: **腕の名指しが積まれている file**（`scripts/eta.py _row()` の `lever_hint`）。
#: **API 0単位**で読めます —— `eta.py --alloc` を撃ち直す必要はありません。
HINT_FILE = ("data", "eta.jsonl")

#: **名指しの割合と、実際に働いた割合の隔たり**が、これを超えたら名指しします。
#: **2.0 は「名指しの半分も働いていない腕が在る」**という意味です。
ARM_GAP_MIN = 2.0


def arms(days: int = 5) -> dict:
    """**名指しされた腕と、実際に働いた腕を、同じ窓で並べる。**（API 0単位・数十ms）

    ## なぜ要ったか（2026-09-05 未明・最適化の回。**実測で名指しした欠陥を1つ潰した**）

    `lever_followed=True` は直近5日で **100回** 立っています。**合格の印です。**
    ところがこの回が同じ窓で数えたら、こうでした:

        腕        名指し（`eta.py` の `lever_hint`）   働いた（`runs.jsonl` の `lever`）
        per_video      359回（60.3%）                    158回（66.4%）
        rpm            146回（24.5%）                      6回（ 2.5%）   ← **10倍 の隔たり**
        sub_rate        90回（15.1%）                     14回（ 5.9%）   ←  2.6倍
        （none）          -                               52回

    **`lever_followed` が測っているのは「腕の名前を書いたか」であって、
    「名指しされた腕を働いたか」ではありません。** だから印は 100回 合格のまま、
    配分は 10倍 ずれていられました。**どの回もこの隔たりを見ていません** ——
    名指しの側は `eta.py`（数分・API を叩く）にしか出ず、時間を切った回は読めない
    からです。この関数は同じ数を **数十ms・API 0単位** で出します。

    ## 返す物

        named / worked   腕ごとの名指し回数・働いた回数
        shares           腕ごとの (名指しの割合, 働いた割合)
        worst            隔たりがいちばん大きい腕 (腕, 名指し%, 働いた%, 倍率)
        gap              その倍率（名指し ÷ 働いた）。働いた 0 なら `inf`
        note             上を1行にしたもの（`headline()` が使う）

    ## 覆る条件（**この節を消してよい日**）

    1. `worst` の倍率が `ARM_GAP_MIN` を下回り続けたら（配分が名指しに追いついた）。
    2. `eta.py` が `lever_hint` を積まなくなったら、`named` が空になります ——
       そのときは「隔たりが無い」ではなく「名指しが無い」です（`note` がそう言います）。
    3. `run_marker` が `lever` を積まなくなったら、同じく `worked` が空になります。
    """
    import collections

    cut = (datetime.now(JST) - timedelta(days=days)).date().isoformat()

    named: collections.Counter = collections.Counter()
    p = ROOT.joinpath(*HINT_FILE)
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:                                      # noqa: BLE001
                continue
            if not isinstance(r, dict):
                continue
            h = r.get("lever_hint")
            if h and str(r.get("at", ""))[:10] >= cut:
                named[str(h)] += 1

    worked: collections.Counter = collections.Counter()
    for r in _rows(days):
        lv = r.get("lever")
        #: **`none` は腕ではありません。**「腕を選ばなかった回」なので、
        #: 働いた側の母数からは外し、`unlevered` として別に数えます。
        if lv and str(lv) != "none":
            worked[str(lv)] += 1
    unlevered = sum(1 for r in _rows(days)
                    if not r.get("lever") or str(r.get("lever")) == "none")

    n_named = sum(named.values())
    n_worked = sum(worked.values())

    shares = {}
    worst = None
    for a in set(named) | set(worked):
        sn = (named[a] / n_named) if n_named else 0.0
        sw = (worked[a] / n_worked) if n_worked else 0.0
        shares[a] = (sn, sw)
        if sn <= 0:
            continue
        g = (sn / sw) if sw > 0 else float("inf")
        if g > 1.0 and (worst is None or g > worst[3]):
            worst = (a, sn, sw, g)

    if not n_named:
        note = "**腕の名指しが在りません**（`data/eta.jsonl` に `lever_hint` が無い窓）"
    elif not n_worked:
        note = "**腕を選んだ ship が在りません**（`lever` が全部 `none`）"
    elif worst is None or worst[3] < ARM_GAP_MIN:
        note = (f"**名指しと配分は合っています**（隔たりの最大 "
                f"{(worst[3] if worst else 1.0):.1f}倍・上限 {ARM_GAP_MIN:g}倍）")
    else:
        a, sn, sw, g = worst
        gs = "∞" if g == float("inf") else f"{g:.0f}倍"
        note = (f"**腕 `{a}` は名指し {sn * 100:.0f}% に対し、働いたのは {sw * 100:.1f}%"
                f"（{gs} の隔たり）** —— `lever_followed` は「腕の名前を書いたか」で、"
                f"「名指しされた腕を働いたか」ではありません")

    return {"days": days, "named": dict(named.most_common()),
            "worked": dict(worked.most_common()), "unlevered": unlevered,
            "n_named": n_named, "n_worked": n_worked,
            "shares": shares, "worst": worst,
            "gap": (worst[3] if worst else 1.0), "note": note}


def measure(days: int = 5) -> dict:
    rows = _rows(days)
    by: dict[str, dict] = {}
    for r in rows:
        k = str(r.get("ship_kind"))
        d = by.setdefault(k, {"n": 0, "moved": 0})
        d["n"] += 1
        if r.get("moves") not in (0, None):
            d["moved"] += 1
    for d in by.values():
        d["rate"] = (d["moved"] / d["n"]) if d["n"] else 0.0

    followed = [r for r in rows if r.get("lever_followed") is True]
    f_zero = sum(1 for r in followed if r.get("moves") in (0, None))
    f_bydef = sum(1 for r in followed if r.get("ship_kind") in BY_DEFINITION_ZERO)

    n = len(rows)
    moved = sum(d["moved"] for d in by.values())
    close = by.get(CLOSING, {"n": 0, "moved": 0, "rate": 0.0})
    rest_n = n - close["n"]
    rest_moved = moved - close["moved"]
    rest_rate = (rest_moved / rest_n) if rest_n else 0.0

    #: **差が本物か**。`verdict` の歩留りが、他の全部の歩留りの **3倍** を超え、
    #: かつ動いた回が `verdict` に **過半数** あるときだけ「差が在る」と名乗ります。
    #: **これは検定ではありません** —— 名乗る条件を書いただけです（覆る条件1）。
    significant = bool(close["n"] >= 5 and close["moved"] >= 3
                       and (rest_rate == 0 or close["rate"] > rest_rate * 3)
                       and close["moved"] * 2 > moved)

    return {
        "days": days, "n": n, "moved": moved,
        "by_kind": dict(sorted(by.items(), key=lambda kv: -kv[1]["n"])),
        "closing": close, "rest_rate": rest_rate,
        "significant": significant,
        "followed_n": len(followed), "followed_zero": f_zero,
        "followed_by_definition_zero": f_bydef,
        "fed_share": ((close["n"] + by.get(SUPPLY, {}).get("n", 0)) / n) if n else 0.0,
        "ledger_open": _ledger_open(),
        #: **上の `by_kind` は `--moves`（回の宣言）で数えています。**
        #: 差し引きの側が使える物差しかどうかは、こちらを見ること（`ruler()` の冒頭）。
        "ruler": ruler(days),
        #: **名指しされた腕と、実際に働いた腕の隔たり**（`arms()` の冒頭）。
        "arms": arms(days),
    }


def headline(days: int = 5):
    """**`eta.py` の頭の3行の直後に出す1行。** 数が足りなければ `None`。"""
    m = measure(days)
    if not m["n"]:
        return None
    open_n = m["ledger_open"]
    if open_n == 0:
        pick = f"`{SUPPLY}`（**台帳が空です。閉じる相手が居ないので `{CLOSING}` は選べません**）"
    elif m["significant"]:
        pick = f"`{CLOSING}`（前提を1件 閉じる）"
        if open_n is not None:
            pick += f"／燃料が要るなら `{SUPPLY}`（開いている前提 {open_n}件）"
    else:
        pick = "**（種別の差は、いまの数では名乗れません。`measure()['significant']` が False）**"

    c = m["closing"]
    parts = ", ".join(f"{k} {v['n']}回→{v['moved']}" for k, v in m["by_kind"].items())

    #: **採点に使えない数から割合を作らない**（2026-09-05 未明・最適化の回に直した）。
    #:
    #: この行は 09/05 01:48 の「その日の1本」の決めに、**そのまま引用されました** ——
    #: 「verdict 7回中3回(43%)、それ以外は 233回中3件(1.3%)」。その引用を根拠に、
    #: 1日1枠の動画が **48h 見込み 1回**（形の実測中央値）の長尺へ回っています。
    #: **引用された 2つの割合は、`significant` が False で、物差し（`ruler()`）も
    #: 使えない窓の数です。** 名乗りは断っているのに、弾だけ配っていました。
    #: **断ったときは、割合を印字しません**（回数はそのまま出します。数は隠しません）。
    scoreable = bool(m["significant"] and (m.get("ruler") or {}).get("usable"))
    if scoreable:
        yields_ = (f"{CLOSING} {c['n']}回 中 {c['moved']}回 が到達日を動かし"
                   f"（{c['rate'] * 100:.0f}%）、"
                   f"**それ以外は {m['n'] - c['n']}回 中 {m['moved'] - c['moved']}回"
                   f"（{m['rest_rate'] * 100:.1f}%）**（{parts}）")
    else:
        yields_ = (f"{CLOSING} {c['n']}回 中 {c['moved']}回、"
                   f"それ以外は {m['n'] - c['n']}回 中 {m['moved'] - c['moved']}回"
                   f"（{parts}）。**割合は出しません** —— "
                   "採点に使えない数から作った割合は、引用されると根拠になります"
                   "（09/05 01:48 の「その日の1本」の決めが、この行の割合を引きました）")

    line = (f"→ **その腕に届く種別は {pick}** —— 直近{m['days']}日の**申告**"
            "（`--moves`。**回が自分で打った数で、差し引きではありません**）: "
            f"{yields_}"
            f"／**腕に届く種別へ行った回は {m['fed_share'] * 100:.0f}%**"
            f"（`run_marker.FIX_RUN_CAP` の天井は 67%。**門は効いていて、天井のほうが高い**）")
    if m["followed_n"]:
        line += (f"\n     [!] **腕に従った印（`lever_followed=True`）は {m['followed_n']}回、"
                 f"うち {m['followed_zero']}回"
                 f"（{m['followed_zero'] / m['followed_n'] * 100:.0f}%）が `moves` 0 です** —— "
                 f"{m['followed_by_definition_zero']}回 は `CLAUDE.md` が「定義上 0日」と"
                 f"書いている種別（{'/'.join(BY_DEFINITION_ZERO)}）で取れています。"
                 "**腕だけ選んで種別を選ばないと、この印は合格のまま日付が動きません。**")

    #: **物差しの状態を、名指しの隣に必ず出す**（2026-09-05 未明に足した）。
    #: これが無いあいだ、`optimized.py` の「動かず 28件」は**測定のように読めて**いました
    #: —— 実物は「29件すべて同じ値」です（`ruler()` の冒頭）。
    rl = m.get("ruler") or {}
    if rl.get("n", 0) >= 2 and not rl.get("usable"):
        line += (f"\n     [!] **上の数は宣言です。差し引きは、まだ採点に使えません** —— "
                 f"{rl['note']}")

    #: **腕の配分の隔たりを、種別の名指しの隣に必ず出す**（2026-09-05 未明に足した）。
    #: 名指しの側は `eta.py`（数分・API を叩く）にしか出ておらず、時間を切った回は
    #: **1度も読めていません**。ここは API 0単位です（`arms()` の冒頭）。
    am = m.get("arms") or {}
    if am.get("n_named") and am.get("n_worked") and am.get("gap", 1.0) >= ARM_GAP_MIN:
        _nm = "／".join(f"{k} {v}回" for k, v in list(am["named"].items())[:4])
        _wk = "／".join(f"{k} {v}回" for k, v in list(am["worked"].items())[:4])
        line += (f"\n     [!] {am['note']}。"
                 f"名指し: {_nm}　働いた: {_wk}"
                 + (f"（腕を選ばなかった回 {am['unlevered']}回）" if am.get("unlevered") else ""))
    return line


if __name__ == "__main__":  # pragma: no cover
    #: **安い入口**（2026-09-05 未明に足した）。この名指しの唯一の出口は
    #: `scripts/eta.py` の頭でしたが、**その道具はこの回の実測で 120秒 では
    #: 1文字も出しませんでした**（全部で 数分・API を叩く）。時間の枠を切った回は
    #: 名指しを読めず、いちばん安い種別（`fix`）へ落ちます —— 直近5日で 60%。
    #: **こちらは API 0単位・数十ms** です。`--dict` で中身も出ます。
    import sys

    if "--dict" in sys.argv:
        import pprint

        pprint.pprint(measure())
    else:
        print(headline() or "（ship がありません）")
