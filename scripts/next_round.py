#!/usr/bin/env python3
"""**次の周を、いま立ててよいか。立てるならどの役か。**

    python scripts/next_round.py            → GO <役> か WAIT <分>
    python scripts/next_round.py --record <役>   → 立てたことを記録する

## なぜこれが要るのか（2026-08-25・オーナー指示）

> **「2種類の子の代替としてサブを使用。親はサブがやることについて判断しない」**

親が「何をやらせるか」を考え始めると、**その判断が周ごとにぶれます。**
実測でぶれていました —— 8/18以降の ship 240件のうち `verdict` はわずか14件で、
**その回のうちに終わる `fix` に寄っていました**（急いでいる側に、自分の急がせ方は直せない）。

だから親の仕事を**手続き**に落とします。親が答えるのは2つだけ:

    いま立ててよいか   ← この道具が答える（枠の速さから）
    どの役か           ← この道具が答える（前回と違うほうへ交互に）

**中身は渡す本文（`docs/spawn_prompt.rendered.md`）が決めます。親は写すだけ。**

## 間隔をどこから取るか

`scripts/quota.py` の `recommended_floor_minutes()`。
**固定値を持ちません** —— 枠の残りと消費の速さで毎回変わるからです
（実測: 3.3日ぶん 22% のまま走って実際は 75%、**41分 → 65分**にずれていた）。

**取れない回は立てます。** 止めるより出すほうが目標に近い
（`CLAUDE.md`「投稿を途切れさせないこと」）。ただし**その旨を印字**して、
黙って速く走らないようにします。

## 役はなぜ交互なのか

2つの役（主実行・最適化）は独立で、**どちらも止めたくありません。**
同時に2つ立てると1周ぶんの倍を使うので、**交互に立てて、2周で1組**にします。
**覆る条件**: 枠に余裕ができて `floor_min` が1周の長さを下回ったら、
同時に2つ立ててよい（そのときは `--both` を足すこと）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ROUNDS = ROOT / "data" / "rounds.jsonl"

#: 役。`docs/spawn_prompt.rendered.md` の `kind:` と同じ名前にすること。
ROLES = ("hourly", "optimizer")

#: 間隔が取れなかった回に使う下限（分）。**推定ではなく、止めないための安全弁**です。
#: `quota.py` が答えられない回にゼロ間隔で回すと、枠を先に使い切ります。
FALLBACK_MIN = 90.0


def rows() -> list[dict]:
    if not ROUNDS.exists():
        return []
    out = []
    for line in ROUNDS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def last_round() -> dict | None:
    got = rows()
    return got[-1] if got else None


def next_role(prev: dict | None) -> str:
    """**前回と違うほうへ。** 記録が無ければ主実行から（投稿が先）。"""
    if not prev:
        return ROLES[0]
    try:
        i = ROLES.index(str(prev.get("role") or ""))
    except ValueError:
        return ROLES[0]
    return ROLES[(i + 1) % len(ROLES)]


def floor_minutes() -> tuple[float, str]:
    """`(間隔, どこから来たか)`。取れなければ `FALLBACK_MIN`。"""
    try:
        from scripts.quota import recommended_floor_minutes
    except Exception:                                          # noqa: BLE001
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "quota", ROOT / "scripts" / "quota.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            recommended_floor_minutes = mod.recommended_floor_minutes
        except Exception as exc:                               # noqa: BLE001
            return FALLBACK_MIN, f"quota.py を読めませんでした（{str(exc)[:60]}）"
    try:
        got = recommended_floor_minutes()
    except Exception as exc:                                   # noqa: BLE001
        return FALLBACK_MIN, f"quota.py が答えませんでした（{str(exc)[:60]}）"
    if got is None:
        return FALLBACK_MIN, "quota.py が「まだ出せない」と答えました（目盛りが足りない）"
    return float(got), "quota.py の実測"


def decide(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    floor, src = floor_minutes()
    prev = last_round()
    role = next_role(prev)

    if not prev:
        return {"go": True, "role": role, "floor_min": floor, "source": src,
                "why": "前の周の記録がありません（最初の1周）"}

    try:
        started = datetime.fromisoformat(str(prev["at"]))
    except Exception:                                          # noqa: BLE001
        return {"go": True, "role": role, "floor_min": floor, "source": src,
                "why": "前の周の時刻を読めませんでした（止めるより出す）"}
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    passed = (now - started).total_seconds() / 60.0
    if passed >= floor:
        return {"go": True, "role": role, "floor_min": floor, "source": src,
                "passed_min": passed,
                "why": f"前の周の開始から {passed:.0f}分（間隔 {floor:.0f}分）"}
    return {"go": False, "role": role, "floor_min": floor, "source": src,
            "passed_min": passed, "wait_min": floor - passed,
            "why": f"前の周の開始から {passed:.0f}分。あと {floor - passed:.0f}分"}


def record(role: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    row = {"at": now.isoformat(), "role": role}
    ROUNDS.parent.mkdir(parents=True, exist_ok=True)
    with ROUNDS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="次の周を立ててよいか／どの役か")
    ap.add_argument("--record", metavar="ROLE",
                    help="立てたことを記録する（役の名前）")
    args = ap.parse_args()

    if args.record:
        if args.record not in ROLES:
            print(f"役は {ROLES} のどれかです: {args.record}", file=sys.stderr)
            return 2
        row = record(args.record)
        print(f"[next_round] 記録しました: {row['role']} at {row['at']}")
        return 0

    d = decide()
    print(f"[next_round] 間隔 {d['floor_min']:.0f}分（{d['source']}）")
    if d["go"]:
        print(f"GO {d['role']}")
        print(f"  理由: {d['why']}")
        print(f"  本文: docs/spawn_prompt.rendered.md の `kind: {d['role']}` を"
              "**そのまま**渡すこと（親が中身を考えないこと）")
        print("  **isolation: \"worktree\" を必ず付けること**（衝突を避ける）")
        print(f"  立てたら: python scripts/next_round.py --record {d['role']}")
        return 0
    print(f"WAIT {d['wait_min']:.0f}")
    print(f"  理由: {d['why']}")
    print("  **何もしないこと。** 次のトリガーか、走っているサブの完了が拾います")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
