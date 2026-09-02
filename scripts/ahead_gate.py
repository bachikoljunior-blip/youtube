#!/usr/bin/env python3
"""**先の日付（明日以降 JST）の予約が 0本 であることを、毎周 数えて、実物で確かめる。**

    python scripts/ahead_gate.py           # いま何本 先に置いてあるか（**API 0単位**）
    python scripts/ahead_gate.py --live    # **実物**（口）で数え直す（十数単位）
    python scripts/ahead_gate.py --gate    # 0本でなければ exit 2 ＋ 理由（フック用）

## なぜ要るか（2026-09-02・オーナー原文）

> **「1日一本になってないんだけど、今後こういうことが一切ないようにしろ」**

固定その4（`src/house_rule.SAME_DAY_SCHEDULING_ONLY`）はこう言っています ——

    その日の1本を、**その日に**予約する。**先の日付には1本も置かない。**
    **先の日付が空であることが、正しい状態です。**

**規則は 08/31 に固定されました。それから2日 経って、先の日付の予約は
459本 → 107本 にしか減っていません**（9/24〜10/10・**6.3本/日**）。
放置すれば 09/24 から**1日6本**出ます。

### 減らなかった理由は「怠け」ではありません。**形です**

減らす手（`scripts/pool_drain.py --apply`）は在りました。手順にも書いてあります。
それでも減らなかったのは、**その回が選べば撃つ形**だったからです ——
`docs/trigger_main.md` §4 は候補を並べ、`pool_drain` はその1つ。
実測（09/01）は **`fix` 82% ／ `upload` 0件**。**選ばれない手は、撃たれません。**

**この repo は同じ形を何度も踏んでいます。** `scripts/stop_check.sh` の 271行目:

> **印字に格上げしただけでは、同じ穴です —— 出ていても、読まずに終われる。**

`scripts/run_marker.py` は 2026-08-19 に自分でそう書き、**09/02 に2度目の実測**が
出ました。`density` / `sub_rate` の腕も、註では止まらず**門にして初めて止まりました**。

**だから、これは選択肢ではなく門です。**

## 何を見ているか（**控えと実物の両方。片方では足りません**）

    控え（`data/uploaded.jsonl`）  `at` が明日（JST）以降 ＝ **規則5 の違反**
    実物（`videos.list` の `publishAt`）  同じことを口に訊く

**控えだけでは足りません**（2026-09-01 16:33 にオーナーが画面で踏んだ）——
控えは「予約はもう 09/02 以降だけ」と言い、**Studio には 09/01 の4本**が
残っていました。控えの `at` が過去だと `pool_drain.pool()` の `at <= now` で落ち、
**どの一覧にも出ないまま公開されます**（`src/ledger_truth.py`）。

**実物だけでも足りません** —— 口は日枠が尽きた窓では1文字も返しません
（`upload_cap.day_quota()`）。そのときは控えが唯一の目です。

## 門の効き方（**逃げ道は「枠が無い」1つだけ。回の裁量ではありません**）

    枠が開いている ＋ 先の日付に 1本でも在る   → **止める**（その回で外す）
    枠が開いている ＋ 控えは0本・実物を見ていない → **止める**（`--live` を撃たせる）
    枠が開いている ＋ 控えも実物も0本            → 通す（**これが正しい状態**）
    枠が尽きている                              → 通す（撃てないので）＋ 受け取り帳へ

**「枠が尽きている」は、この道具が自分で `upload_cap.day_quota()` に訊きます。**
回の申告ではありません —— 申告にすると、また「その回が選ぶ」形に戻ります。

## 覆る条件

- `house_rule.same_day_only()` が `False` になったら（オーナーが「先の日付にも
  置いてよい」と言ったら）、**この門はまるごと黙ります。** 判定はそこ1か所です
- 実物の観測は **その枠の窓のあいだだけ**有効です（窓が変われば見直し）
- 控えが上限側に外れる形（口に在って控えに無い）は `dupes.observe_scheduled()` が
  塞いでいます。**`--live` はそれを通るので、読んだついでに控えが直ります**

検査は `tests/test_ahead_gate.py`。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import config, dupes, house_rule, upload_cap  # noqa: E402

JST = timezone(timedelta(hours=9))

#: **実物を見た記録の置き場**（控えではなく、口が何と言ったか）。
#: 1行 ＝ 1回の観測。`{"at","count","ids","source"}`。
OBSERVED = "data/ahead_live.jsonl"


def _path() -> Path:
    return Path(config.ROOT) / OBSERVED


def _parse(raw: object) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at


# ------------------------------------------------------------------ 控えの側
def ahead(rows: list[dict] | None = None,
          now: datetime | None = None) -> list[dict]:
    """**明日（JST）以降に予約が入っている行**を、公開の早い順に返す。**API 0単位**。

    数え方は `src.house_rule.ahead_of_today()` の1か所です（**写さないこと**）。
    ここが足すのは「**まだ公開されていない**」の絞りだけ —— 控えの `at` は
    公開ずみの本にも残るので、それを数えると永久に 0本 になりません。
    """
    now = now or datetime.now(timezone.utc)
    rows = dupes.ledger_rows() if rows is None else rows
    live = []
    for r in rows:
        at = _parse(r.get("at"))
        if at is not None and at > now:                # まだ来ていない予約だけ
            live.append(r)
    out = []
    for r in house_rule.ahead_of_today(live, now=now):
        at = _parse(r.get("at"))
        out.append({"id": r.get("id") or r.get("video_id") or "",
                    "at": at, "title": r.get("title", "")})
    out.sort(key=lambda r: r["at"] or now)
    return out


def by_day(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        at = r.get("at")
        if at is None:
            continue
        key = at.astimezone(JST).strftime("%Y-%m-%d")
        out[key] = out.get(key, 0) + 1
    return out


# ------------------------------------------------------------------ 実物の側
def observations() -> list[dict]:
    """記録ずみの観測を、**古い順**に返す（読めなければ空）。"""
    try:
        text = _path().read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def last_observation(now: datetime | None = None) -> dict | None:
    """**いまの枠の窓の中でした観測**のうち、いちばん新しいもの（無ければ None）。

    窓の切り方は `upload_cap.window_start()` の1か所です（**写さないこと**）。
    窓が変われば口の中身も変わりうるので、**前の窓の観測は証拠になりません。**
    """
    now = now or datetime.now(timezone.utc)
    head = upload_cap.window_start(now)
    best, best_at = None, None
    for row in observations():
        at = _parse(row.get("at"))
        if at is None or at < head or at > now + timedelta(minutes=5):
            continue
        if best_at is None or at >= best_at:
            best, best_at = row, at
    return best


def record(count: int, ids: list[str], source: str,
           now: datetime | None = None) -> dict:
    """観測を1行 追記して返す。**推測を書かないこと** —— ここに入るのは口の返りだけ。"""
    now = now or datetime.now(timezone.utc)
    row = {"at": now.isoformat(), "count": int(count),
           "ids": list(ids)[:200], "source": source}
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def live_ahead(now: datetime | None = None) -> tuple[list[dict], str]:
    """**口に訊く。** 返りは `(明日以降の予約, 読めなかった理由)`。

    取り口は `scripts/reschedule._scheduled()` の1か所です（**写さないこと**）——
    あれは `history.channel_video_ids` を通るので予約中の本が落ちず、
    **読んだついでに控えを実物へ合わせます**（`dupes.observe_scheduled`）。
    """
    now = now or datetime.now(timezone.utc)
    try:
        import reschedule                                      # noqa: PLC0415
        from src import uploader                               # noqa: PLC0415
        svc = uploader._service()
        rows = reschedule._scheduled(svc)
    except (KeyboardInterrupt, MemoryError):
        raise
    except BaseException as exc:                               # noqa: BLE001
        return [], str(exc)[:200]
    today = now.astimezone(JST).date()
    out = []
    for r in rows:
        at = _parse(r.get("at"))
        if at is None or at <= now:
            continue
        if at.astimezone(JST).date() > today:
            out.append({"id": r.get("id", ""), "at": at, "title": r.get("title", "")})
    out.sort(key=lambda r: r["at"])
    record(len(out), [r["id"] for r in out], "videos.list", now)
    return out, ""


# ------------------------------------------------------------------ 判定
def verdict(now: datetime | None = None, rows: list[dict] | None = None) -> dict:
    """**この回、止めるべきか**を返す（**API 0単位**）。

    返り: `{"block","why","lines","ahead","quota_open","seen"}`
    """
    now = now or datetime.now(timezone.utc)
    if not house_rule.same_day_only():
        return {"block": False, "why": "規則5 が外れています（先の日付に置いてよい）",
                "lines": [], "ahead": 0, "quota_open": True, "seen": None}

    mine = ahead(rows, now)
    days = by_day(mine)
    try:
        q = upload_cap.day_quota(now)
        quota_open = bool(q.open)
        qline = q.line
    except Exception as exc:                                   # noqa: BLE001
        quota_open, qline = True, f"日枠: 読めませんでした（{str(exc)[:60]}）"

    seen = last_observation(now)
    lines: list[str] = []

    if mine:
        span = f"{min(days)} 〜 {max(days)}" if days else "?"
        per_day = len(mine) / max(1, len(days))
        lines.append(f"[ahead] **先の日付（明日 JST 以降）の予約 {len(mine)}本**"
                     f"／{span}／**{per_day:.1f}本/日**（控え）")
        for d in sorted(days)[:5]:
            lines.append(f"[ahead]   {d}  {days[d]}本")
        if len(days) > 5:
            lines.append(f"[ahead]   …ほか {len(days) - 5}日")
    else:
        lines.append("[ahead] 先の日付の予約: **控えでは 0本**")

    if seen is not None:
        stamp = (_parse(seen.get("at")) or now).astimezone(JST).strftime("%m/%d %H:%M JST")
        lines.append(f"[ahead] 実物（口）: **{seen.get('count')}本**"
                     f"（{stamp} に `videos.list` で見た。いまの窓の中）")
    else:
        lines.append("[ahead] 実物（口）: **この窓では一度も見ていません**"
                     " —— 控えだけでは足りません"
                     "（2026-09-01 16:33: 控え 0本／Studio に4本）")

    lines.append(f"[ahead] {qline}")

    if not quota_open:
        return {"block": False, "ahead": len(mine), "quota_open": False, "seen": seen,
                "why": "日枠が尽きています（この窓では外せません）", "lines": lines}

    if mine:
        return {"block": True, "ahead": len(mine), "quota_open": True, "seen": seen,
                "why": f"先の日付に **{len(mine)}本** 残っています", "lines": lines}

    if seen is None:
        return {"block": True, "ahead": 0, "quota_open": True, "seen": None,
                "why": "控えは 0本 ですが、**実物をこの窓で一度も見ていません**",
                "lines": lines}

    if int(seen.get("count") or 0) > 0:
        return {"block": True, "ahead": 0, "quota_open": True, "seen": seen,
                "why": f"控えは 0本 ですが、**実物には {seen.get('count')}本** 在ります",
                "lines": lines}

    return {"block": False, "ahead": 0, "quota_open": True, "seen": seen,
            "why": "先の日付は空です（**これが正しい状態**）", "lines": lines}


HOWTO = (
    "[ahead] → **この回で外すこと**（順番も固定）:\n"
    "[ahead]     python scripts/ahead_gate.py --live            # 実物を引く"
    "（読んだついでに控えを合わせる）\n"
    "[ahead]     python -m src.ledger_truth                     # 食い違いを名指し\n"
    "[ahead]     python scripts/pool_drain.py --apply --keep 0  # **削除しない**"
    "・private へ戻すだけ\n"
    "[ahead] **きょうのぶんが未公開で予約に在るなら、それは外さないこと**"
    "（`pool_drain.plan()` が守ります）。"
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="先の日付（明日 JST 以降）の予約が 0本 であることを見る門")
    ap.add_argument("--gate", action="store_true",
                    help="0本でなければ exit 2 ＋ 理由を印字（フック用）")
    ap.add_argument("--live", action="store_true",
                    help="**実物**（`videos.list`）で数え直して記録する（十数単位）")
    ap.add_argument("--json", action="store_true", help="機械向けに1行で出す")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)

    if args.live:
        rows, err = live_ahead(now)
        if err:
            print(f"[ahead] 実物が読めませんでした: {err}", flush=True)
        else:
            print(f"[ahead] **実物（口）の先の日付の予約: {len(rows)}本**"
                  f"（`{OBSERVED}` に記録しました）", flush=True)
            for r in rows[:10]:
                print(f"[ahead]   {r['at'].astimezone(JST).strftime('%m/%d %H:%M JST')}"
                      f"  {r['id']}  {r['title'][:36]}", flush=True)
            if len(rows) > 10:
                print(f"[ahead]   …ほか {len(rows) - 10}本", flush=True)

    v = verdict(now)

    if args.json:
        print(json.dumps({k: v[k] for k in ("block", "why", "ahead", "quota_open")},
                         ensure_ascii=False))
        return 2 if (args.gate and v["block"]) else 0

    for line in v["lines"]:
        print(line, flush=True)

    if v["block"]:
        print(f"[ahead] [!] **{v['why']}**", flush=True)
        print(HOWTO, flush=True)
        return 2 if args.gate else 1

    if not v["quota_open"] and v["ahead"]:
        # **撃てない回の残件は、受け取り帳へ。** 次の窓の回が拾います
        # （`pool_drain` と同じ形。同じ本文なら同じ ID に積まれます）。
        try:
            from src import inbox                              # noqa: PLC0415
            rec = inbox.add(
                f"先の日付（明日 JST 以降）の予約が **{v['ahead']}本** 残っています。"
                " 日枠が戻ったら `python scripts/ahead_gate.py --live` →"
                " `python scripts/pool_drain.py --apply --keep 0` を撃つこと"
                "（固定その4・規則5「先の日付には1本も置かない」）。",
                source="ahead_gate")
            print(f"[ahead] 残件を受け取り帳に置きました: {rec['id']}", flush=True)
        except Exception as exc:                               # noqa: BLE001
            print(f"[ahead] 受け取り帳へ置けませんでした: {str(exc)[:80]}", flush=True)

    print(f"[ahead] {v['why']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
