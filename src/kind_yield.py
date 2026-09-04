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
    line = (f"→ **その腕に届く種別は {pick}** —— 直近{m['days']}日の実測: "
            f"{CLOSING} {c['n']}回 中 {c['moved']}回 が到達日を動かし（{c['rate'] * 100:.0f}%）、"
            f"**それ以外は {m['n'] - c['n']}回 中 {m['moved'] - c['moved']}回"
            f"（{m['rest_rate'] * 100:.1f}%）**（{parts}）"
            f"／**腕に届く種別へ行った回は {m['fed_share'] * 100:.0f}%**"
            f"（`run_marker.FIX_RUN_CAP` の天井は 67%。**門は効いていて、天井のほうが高い**）")
    if m["followed_n"]:
        line += (f"\n     [!] **腕に従った印（`lever_followed=True`）は {m['followed_n']}回、"
                 f"うち {m['followed_zero']}回"
                 f"（{m['followed_zero'] / m['followed_n'] * 100:.0f}%）が `moves` 0 です** —— "
                 f"{m['followed_by_definition_zero']}回 は `CLAUDE.md` が「定義上 0日」と"
                 f"書いている種別（{'/'.join(BY_DEFINITION_ZERO)}）で取れています。"
                 "**腕だけ選んで種別を選ばないと、この印は合格のまま日付が動きません。**")
    return line


if __name__ == "__main__":  # pragma: no cover
    import pprint

    pprint.pprint(measure())
    print()
    print(headline())
