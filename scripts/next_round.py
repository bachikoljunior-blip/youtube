#!/usr/bin/env python3
"""**次の周を、いま立ててよいか。立てるならどの役か。**

    python scripts/next_round.py                       → GO <役> <役> か WAIT <分>
    python scripts/next_round.py --record <役>[,<役>]   → 立てたことを記録する

## なぜこれが要るのか（2026-08-25・オーナー指示）

> **「2種類の子の代替としてサブを使用。親はサブがやることについて判断しない」**

親が「何をやらせるか」を考え始めると、**その判断が周ごとにぶれます。**
実測でぶれていました —— 8/18以降の ship 240件のうち `verdict` はわずか14件で、
**その回のうちに終わる `fix` に寄っていました**（急いでいる側に、自分の急がせ方は直せない）。

だから親の仕事を**手続き**に落とします。親が答えるのは2つだけ:

    いま立ててよいか   ← この道具が答える（枠の速さから）
    どの役か           ← この道具が答える（**2種類とも**。欠けていれば欠けたぶん）

**中身は渡す本文（`docs/spawn_prompt.rendered.md`）が決めます。親は写すだけ。**

## 間隔をどこから取るか

`scripts/quota.py` の `recommended_floor_minutes()`。
**固定値を持ちません** —— 枠の残りと消費の速さで毎回変わるからです
（実測: 3.3日ぶん 22% のまま走って実際は 75%、**41分 → 65分**にずれていた）。

**取れない回は立てます。** 止めるより出すほうが目標に近い
（`CLAUDE.md`「投稿を途切れさせないこと」）。ただし**その旨を印字**して、
黙って速く走らないようにします。

## 1周は「2種類そろって1周」です（2026-08-25 に交互をやめた）

オーナー指示（原文）: **「親が判断せずサブで2種類の実行走らせんだよわかってっか？」**

**それまでは交互でした** —— 2つの役を1周に1つずつ、2周で1組。
**これは設計の劣化でした。** 元の形は子セッション2枚（`youtube-hourly` /
`youtube-optimizer`）が**並行して走り続ける**もので、片方だけが走る時間帯は
ありませんでした。交互にした時点で、**最適化はどの瞬間も半分止まっています。**

実測でその穴を踏んでいます —— **2026-08-25 12:37Z の周は `hourly` だけが立ち、
`optimizer` は33分間どこにも走っていませんでした。**
`--both` は docstring が約束しているだけで**実装されていませんでした。**

だからこの道具は **`ROLES` を全部返します。**

**欠けを埋めるほうは、間隔を待ちません。** いまの周に片方しか記録が無ければ、
残りは**即 GO** です（待つと、その周は片肺のまま終わります）。
1周に立つ数は `len(ROLES)` で頭打ちなので、これで暴走はしません。

**覆る条件**: 枠が尽きかけたら、`quota.py` の間隔が開いて周そのものが減ります。
**役を減らすのではなく、周を減らすこと** —— 減らすと、また片肺に戻ります。
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
#: **1周でこれを全部立てます。**（交互ではありません。上の節）
ROLES = ("hourly", "optimizer")

#: 同じ周とみなす幅の上限（分）。実際の幅は `round_span(floor)` が決めます。
#:
#: **固定の30分で1回落ちています**（2026-08-25、入れたその場で検算に出た）。
#: 実データは `hourly` 12:37Z / `optimizer` 13:10Z の **33.6分差**でした。
#: 30分だと別の周に割れ、**「`hourly` が欠けている」と出ます** ——
#: 主実行はそのとき走っているので、**従うと2枚目が立ちます。**
#: それは 2026-08-15 に「2人の子が同じ日の予約を取り合い、片方の生成が
#: 丸ごと無駄になった」形そのものです。
#:
#: だから幅は**間隔の半分**にします。間隔90分なら45分。
#: 次の周の1件目は前の周の開始から `floor` 以上あとなので、
#: 前の周の最後の記録との差は `floor - 幅` 以上 ＝ 幅より大きく、吸い込みません。
ROUND_SPAN_MAX_MIN = 45.0


def round_span(floor_min: float) -> float:
    """同じ周とみなす幅（分）。**間隔の半分。上限 `ROUND_SPAN_MAX_MIN`。**"""
    return min(ROUND_SPAN_MAX_MIN, max(1.0, float(floor_min) / 2.0))

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


def _at(row: dict) -> datetime | None:
    """記録の時刻。読めなければ `None`（**捨てずに、無い扱い**）。"""
    try:
        got = datetime.fromisoformat(str(row["at"]))
    except Exception:                                          # noqa: BLE001
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def current_round(got: list[dict] | None = None,
                  span_min: float | None = None) -> list[dict]:
    """**いまの周に属する記録**（`span_min` 以内で連なるひと塊）。

    2種類そろって1周なので、**周は行ではなく塊**です。
    最後の1行だけを見ると、「`hourly` を記録した直後」と
    「`hourly` だけで終わった周」を区別できません。
    **区別できないと、片肺の周を完成扱いで見送ります**（8/25 12:37Z に実測）。
    """
    got = rows() if got is None else got
    span = round_span(floor_minutes()[0]) if span_min is None else float(span_min)
    parsed = sorted(((at, r) for r in got if (at := _at(r))), key=lambda x: x[0])
    if not parsed:
        return []
    group = [parsed[-1]]
    for at, r in reversed(parsed[:-1]):
        if (group[0][0] - at).total_seconds() / 60.0 <= span:
            group.insert(0, (at, r))
        else:
            break
    return [r for _, r in group]


def missing_roles(group: list[dict]) -> list[str]:
    """**いまの周で、まだ立っていない役。** 並びは `ROLES` のまま。"""
    have = {str(r.get("role") or "") for r in group}
    return [r for r in ROLES if r not in have]


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
    base = {"floor_min": floor, "source": src}
    group = current_round(span_min=round_span(floor))

    if not group:
        return {**base, "go": True, "roles": list(ROLES),
                "why": "前の周の記録がありません（最初の1周）"}

    starts = [at for at in (_at(r) for r in group) if at]
    if not starts:
        return {**base, "go": True, "roles": list(ROLES),
                "why": "前の周の時刻を読めませんでした（止めるより出す）"}
    started = min(starts)
    passed = (now - started).total_seconds() / 60.0

    # **欠けは間隔を待ちません。** 待つと、その周は片肺のまま終わります。
    # 1周に立つ数は `len(ROLES)` で頭打ちなので、これで暴走はしません。
    missing = missing_roles(group)
    if missing:
        return {**base, "go": True, "roles": missing, "patch": True,
                "passed_min": passed,
                "why": ("いまの周に " + "・".join(missing) + " が立っていません"
                        "（**穴埋め。間隔は待ちません**）")}

    if passed >= floor:
        return {**base, "go": True, "roles": list(ROLES), "passed_min": passed,
                "why": f"前の周の開始から {passed:.0f}分（間隔 {floor:.0f}分）"}
    return {**base, "go": False, "roles": list(ROLES), "passed_min": passed,
            "wait_min": floor - passed,
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
    ap.add_argument("--record", metavar="ROLE[,ROLE]",
                    help="立てたことを記録する（役の名前。カンマ区切りで複数）")
    args = ap.parse_args()

    if args.record:
        want = [s.strip() for s in args.record.split(",") if s.strip()]
        bad = [r for r in want if r not in ROLES]
        if bad:
            print(f"役は {ROLES} のどれかです: {', '.join(bad)}", file=sys.stderr)
            return 2
        for role in want:
            row = record(role)
            print(f"[next_round] 記録しました: {row['role']} at {row['at']}")
        return 0

    d = decide()
    print(f"[next_round] 間隔 {d['floor_min']:.0f}分（{d['source']}）")
    roles = d["roles"]
    if d["go"]:
        print("GO " + " ".join(roles))
        print(f"  理由: {d['why']}")
        print(f"  **この{len(roles)}つを立てること。** 1周は"
              f"{len(ROLES)}種類そろって1周です"
              "（片方だけで終わると、その周は片肺）")
        for role in roles:
            print(f"  本文: docs/spawn_prompt.rendered.md の `kind: {role}` を"
                  "**そのまま**渡すこと（親が中身を考えないこと）")
        print("  **isolation: \"worktree\" と run_in_background: true を"
              "必ず付けること**（衝突を避ける／親を塞がない）")
        print(f"  立てたら: python scripts/next_round.py --record {','.join(roles)}")
        return 0
    print(f"WAIT {d['wait_min']:.0f}")
    print(f"  理由: {d['why']}")
    print(f"  いまの周は {'・'.join(roles)} がそろっています（片肺ではありません）")
    print("  **何もしないこと。** 次のトリガーか、走っているサブの完了が拾います")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
