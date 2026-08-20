"""**その回の実測を、予測へ入れ直したか。**（API は 0 単位・手元の台帳だけ）

## なぜ要るか（2026-08-20・オーナー指示。原文）

> 毎回の実行で予測するように言ったはずなので、毎回その予測に反映して

予測は回の**最初**に出ます（`CLAUDE.md`「毎回の実行で必ずやること」1）。
そのあと腕を引いて何かを出すので、**出したものは、その回の予測に入っていません。**
入れ直さないと、次の回はまた「作業の前の予測」から始まります ——
**動かしたはずのものが、どの日付にも一度も現れない。**

`run_marker.py --ship` は `data/eta.jsonl` の**最後の点**を `eta_target` に写します。
入れ直していない回では、それは**作業前の日付**です。だから

    ship の `at` より新しい eta の点が1つも無い ＝ **入れ直していない**

これが機械で見える形の全部です。`--offline` で撃ち直した点も数えます
（外の口が閉じていても入れ直せること自体に意味がある。1日のうち Analytics 側の
入力は動かず、回が動かすのは `config/hypotheses.yaml` と供給のほうなので、
`--offline` でも軌跡はちゃんと組み替わります）。

## なぜ文書ではなくここなのか

**`docs/trigger_main.md` は 197KB で、読み飛ばされた記録があります**（2026-08-18 23:4x）。
親自身も `docs/trigger_parent.md` を毎回は読んでいません。**「読め」と書く方式は、
実測として機能していません。** 機械的に必ず入るのは3つだけ ——
フックが差し込む文字列・`CLAUDE.md`・**走って落ちるもの**。ここは3つ目です。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _at(row: dict) -> datetime | None:
    """`at` を時刻に。**壊れた行では例外を出さない**（台帳の傷で回を殺さない）。"""
    raw = str(row.get("at") or "").replace("Z", "+00:00")
    try:
        t = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return t


def _rows(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for ln in text.splitlines():
        try:
            r = json.loads(ln)
        except Exception:                                      # noqa: BLE001
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def pending(root: Path | None = None, session: str | None = None) -> dict | None:
    """**入れ直していない ship** を返す（無ければ `None`）。

    `session` を渡すとその回だけ見ます（フック用）。渡さなければ台帳の最後の ship
    ＝ **前の回が入れ直したか**を見ます（`status.py` 用）。
    """
    root = Path(root or ROOT)
    session = session or None            # 空文字は「指定なし」（フックが `${ME}` を空で渡し得る）
    ships = [r for r in _rows(root / "data" / "runs.jsonl")
             if r.get("kind") == "ship" and (session is None or r.get("session") == session)]
    if not ships:
        return None
    ship = ships[-1]
    ship_at = _at(ship)
    if ship_at is None:
        return None
    etas = [t for t in (_at(r) for r in _rows(root / "data" / "eta.jsonl")) if t is not None]
    eta_at = etas[-1] if etas else None
    if eta_at is not None and eta_at > ship_at:
        return None
    return {"at": ship.get("at"), "what": ship.get("what") or "", "lever": ship.get("lever"),
            "moves": ship.get("moves"), "eta_at": ship.get("eta_target"), "session": ship.get("session")}


def lines(root: Path | None = None, session: str | None = None) -> list[str]:
    """出す行。**入れ直してあれば空**（黙る）。"""
    p = pending(root, session)
    if p is None:
        return []
    what = p["what"][:60] + ("…" if len(p["what"]) > 60 else "")
    return [
        f"出した: {p['at']}  腕 {p.get('lever') or '?'}  宣言 {p.get('moves')}日  「{what}」",
        f"そのときの予測: {p.get('eta_at') or '不明'}  ← **作業の前の日付です**",
        "入れ直す: `python scripts/eta.py`（外の口が閉じていれば `--offline`）",
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="その回の実測を予測へ入れ直したか")
    ap.add_argument("--pending", action="store_true", help="入れ直していなければ行を出す")
    ap.add_argument("--session", default=None, help="この回だけ見る")
    a = ap.parse_args()
    for ln in lines(session=a.session):
        print(ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
