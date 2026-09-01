"""**控えが「動かした」と言っている本のうち、実物を1文字も触っていない本を数える**（API 0単位）。

    python -m src.ledger_truth          # 幻の書き換えを一覧で出す
    python -m src.ledger_truth --all    # 窓ごとの内訳も出す

## なぜ要るか（2026-09-01。**オーナーが画面で見つけました**）

オーナー原文（2026-09-01 16:33 JST）——
**控えは「予約はもう 09/02 以降だけ」と言っているのに、実物の画面には
09/01 の 18:00〜21:00 に4本 予約が残っていた。** `pool_drain` の一覧にも
入っていない。**手元の控えと、外の実物が食い違っていた。**

**原因は「読み落とし」ではありません。こちらの手で作った幻です。**

`reschedule._update()` は **False** を返す道が2つあります:

    (1) 「**もうその値です**」   …… 実物は既にその時刻。撃たなくてよい
    (2) `upload_cap.move_hold`  …… **この窓でその本はもう2回 動かした。撃たない**

**(2) は YouTube を1文字も変えていません。** ところが呼ぶ側の3つ ——
`--spread`／`--compact`／`pool_drain --apply` —— は**返りを見ずに**
`dupes.retime()` を撃っていました。**控えだけが動きます。**

    控え   09/29 09:30 JST に動いた（と書いてある）
    実物   もとの時刻のまま。**その時刻に公開されます**

そして控えの `at` が過去になると `pool_drain.pool()` の
`at <= now` で落ち、**どの道具の一覧にも出なくなります。**
＝ **控えだけを見て「無い」と言い切る**形の、いちばん質の悪いやつです。

**`--move` だけは 2026-08-29 に直っていました**（`if wrote:` の枝と、
その上の長い註）。**残る3つは素通りのまま** ——
この repo が通算12回 踏んでいる「**片方だけ直す**」形です。
3つとも 2026-09-01 に塞ぎ、**塞いだことを見る側がここ**です。

## 何を見ているか（**推測しません。帳面の突き合わせだけです**）

    控え（`data/uploaded.jsonl`）   `retimed_at` ＝ **控えを書き換えた時刻**
    帳面（`data/day_quota.jsonl`）  `videos.update <vid>` ＝ **実物へ通った時刻**

**同じ窓で、その本に既に `MOVE_CAP` 回 通っていて、なおかつ
書き換えの前後5分に1回も通っていない** —— このとき `move_hold` が
撃つのを止めており、**控えだけが動いています。**

`MOVE_CAP` と窓の切り方は `src.upload_cap` から読みます（**写さないこと**。
あちらが 2 でなくなった日に、ここだけ古い数で数えると幻が増えます）。

## 何を言わないか（**この道具は実物を知りません**）

**「正しい時刻はいくつか」は言えません。** それは口（`videos.list`）だけが
知っています。この道具が言えるのは「**この本の控えは信用できない**」まで。
直すには口が要ります（日枠が戻ってから）:

    python scripts/reschedule.py --list     # 実物の予約を引き直す

## 覆る条件

- `move_hold` を撤去したら、この数え方は空になります（別の穴が開きます）
- `data/day_quota.jsonl` を古い窓ごと捨てるようになったら、**古い窓の幻は
  二度と数えられません**（`upload_cap.DAY_QUOTA_HITS` の註と同じ前提）
- **2026-08-26 より前の書き換えは見えません**（`note_quota_ok` がその日に
  入ったので、それ以前は「通った証拠」の側が空です）。
  **だから、ここが 0件 でも「幻は無い」ではありません。**
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, upload_cap

JST = timezone(timedelta(hours=9))
LEDGER = "data/uploaded.jsonl"

#: 「同じ呼び出し」と見なす幅。`_update` は `videos.list` → `videos.update` →
#: `retime` を1つながりに撃つので、実測でも数秒しか離れません。5分は余裕側です。
NEAR = timedelta(seconds=300)

#: **通った証拠の側が始まった日**（`upload_cap.note_quota_ok` が入った日）。
#: これより前の `retimed_at` は、幻かどうかを言えません。
EVIDENCE_SINCE = datetime(2026, 8, 26, tzinfo=timezone.utc)


def _ts(raw: object) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at


def _updates(root: Path | None = None) -> dict[str, list[datetime]]:
    """**実物へ通った `videos.update` の時刻**を、本ごとに（API 0単位）。

    `upload_cap.moves_by_video()` は「**いまの窓だけ**」を数えるので使えません
    —— ここが見たいのは過去の窓に残った幻のほうです。数え方（成功の行だけ・
    `videos.update <vid>` ちょうど2語）は**あちらと同じ**にしてあります。
    """
    path = (root or config.ROOT) / upload_cap.DAY_QUOTA_HITS
    out: dict[str, list[datetime]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("ok") is False:
            continue
        parts = str(row.get("detail", "")).split()
        if len(parts) != 2 or parts[0] != "videos.update":
            continue
        at = _ts(row.get("at"))
        if at:
            out.setdefault(parts[1], []).append(at)
    for v in out:
        out[v].sort()
    return out


def phantoms(root: Path | None = None) -> list[dict]:
    """**控えだけが動いた本**（API 0単位）。新しい順ではなく、書き換えの順。

    返りの1件は `{id, ledger_at, retimed_at, prior, title}`:

        ledger_at   控えがいま言っている公開時刻（**信用できない側**）
        retimed_at  控えを書き換えた時刻
        prior       その窓で、その前に実物へ通っていた回数（>= MOVE_CAP）
    """
    root = root or config.ROOT
    ok = _updates(root)
    path = root / LEDGER
    if not path.exists():
        return []
    seen: set[str] = set()
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        stamp = _ts(row.get("retimed_at"))
        vid = str(row.get("video_id") or "")
        if not stamp or not vid or stamp < EVIDENCE_SINCE:
            continue
        hits = ok.get(vid, [])
        if [u for u in hits if abs((u - stamp).total_seconds())
                <= NEAR.total_seconds()]:
            continue                      # その場で実物へ通っている ＝ 幻ではない
        head, tail = upload_cap.window_start(stamp), upload_cap.window_end(stamp)
        prior = [u for u in hits if head <= u <= stamp < tail]
        if len(prior) < upload_cap.MOVE_CAP:
            continue                      # `move_hold` は掛かっていない
        if vid in seen:
            continue                      # 同じ本の2行目以降は数えない
        seen.add(vid)
        out.append({"id": vid, "ledger_at": row.get("at"),
                    "retimed_at": stamp, "prior": len(prior),
                    "title": str(row.get("title") or "")[:34]})
    out.sort(key=lambda r: r["retimed_at"])
    return out


def report_lines(root: Path | None = None) -> list[str]:
    """`status.py` に出す行（API 0単位）。**1件も無ければ空**（黙る）。"""
    rows = phantoms(root)
    if not rows:
        return []
    lines = [
        f"  [!] **控えだけが動いた本が {len(rows)}本 あります**"
        "（`videos.update` が1度も通っていないのに `retimed_at` が押されている）",
        "      **この本の `at` は信用しないこと。** 実物はもとの時刻のまま"
        "公開されます —— 控えの `at` が過去なら、"
        "`pool_drain` の一覧からも消えています",
    ]
    for r in rows:
        at = _ts(r["ledger_at"])
        shown = at.astimezone(JST).strftime("%m/%d %H:%M JST") if at else "予約なし"
        lines.append(
            f"      {r['id']}  控え={shown}"
            f"  （{r['retimed_at'].astimezone(JST):%m/%d %H:%M} に書き換え・"
            f"その窓で既に {r['prior']}回 動かしたあと）  {r['title']}")
    lines.append(
        "      直すには口が要ります（**この道具は実物を知りません**。日枠が"
        "戻ってから `python scripts/reschedule.py --list` で実物の予約を引き直し、"
        "上の4本の時刻を控えへ入れ直すこと）: "
        + " ".join(r["id"] for r in rows))
    lines.append(
        "      **穴そのものは 2026-09-01 に塞ぎました**"
        "（`--spread`／`--compact`／`pool_drain --apply` が"
        "`_update()` の返りを見るようになった）。**ここに出るのは、"
        "塞ぐ前に作った在庫です**")
    return lines


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="窓ごとの内訳も出す")
    args = ap.parse_args(argv)

    rows = phantoms()
    if not rows:
        print("[ledger] **控えだけが動いた本は 0本**です（API 0単位）。")
        print(f"[ledger] ただし {EVIDENCE_SINCE:%Y-%m-%d} より前の書き換えは"
              "**見えません**（通った証拠の側が空）。0件 ＝ 幻が無い、ではありません。")
        return 0
    for line in report_lines():
        print(line)
    if args.all:
        ok = _updates()
        print("[ledger] --- 窓ごと（成功した `videos.update` の回数）---")
        per: dict[str, int] = {}
        for _v, tl in ok.items():
            for t in tl:
                k = upload_cap.window_start(t).astimezone(JST).strftime("%m/%d")
                per[k] = per.get(k, 0) + 1
        for k in sorted(per):
            print(f"[ledger]   窓 {k}  {per[k]}回")
    return 1


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
