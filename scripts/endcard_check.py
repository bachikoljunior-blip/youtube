#!/usr/bin/env python
"""**末尾の問いかけ（コメント・共有の枠）を、Analytics だけで判定する。**

    python scripts/endcard_check.py

**Data API は叩きません。** 母集団は `data/uploaded.jsonl` と
`data/critique_queue/` から決めます（理由は `src/endcard_verdict.py` の冒頭）。
日枠（JST 16:00 に戻り数時間で尽きる）が閉じている窓でも下せます。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.discovery import build          # noqa: E402
from googleapiclient.errors import HttpError         # noqa: E402

from src import endcard_verdict as ev                # noqa: E402
from src.auth import credentials                     # noqa: E402

#: Analytics の `filters=video==` は複数IDを取れるが、上限がある。**割って投げる。**
CHUNK = 200


def _totals(an, vids: list[str], start: str, end: str) -> dict[str, int]:
    """動画IDの一覧に対する再生・コメント・共有・登録の合計。"""
    got = {"views": 0, "comments": 0, "shares": 0, "subscribersGained": 0}
    rows_seen = 0
    for i in range(0, len(vids), CHUNK):
        chunk = vids[i:i + CHUNK]
        try:
            res = an.reports().query(
                ids="channel==MINE", startDate=start, endDate=end,
                metrics="views,comments,shares,subscribersGained",
                dimensions="video", filters="video==" + ",".join(chunk),
                maxResults=len(chunk),
            ).execute()
        except HttpError as exc:
            print(f"  [!] {i//CHUNK+1}組目が取れませんでした: {str(exc)[:110]}")
            continue
        headers = [h["name"] for h in res.get("columnHeaders", [])]
        for row in res.get("rows", []):
            r = dict(zip(headers, row))
            rows_seen += 1
            for k in got:
                got[k] += int(r.get(k, 0) or 0)
    got["rows"] = rows_seen
    return got


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=28,
                    help="さかのぼる日数（既定 28）。Analytics は日次で3日遅れます")
    args = ap.parse_args()

    end = date.today()
    start = end - timedelta(days=args.days)

    ask, breakdown = ev.population(ev.load_ledger())
    print("=== 末尾の問いかけ（コメント・共有の枠）の判定 ===")
    print(f"  母集団は手元の控えから（Data API 0単位）: 問いかけ型のショート {len(ask)}本")
    print(f"    内訳 {breakdown}")
    if breakdown["not_ask"] == 0:
        print("    [!] **問いかけでないショートが1本もありません ＝ 対照群がない。**")
        print("        言えるのは「この枠で取れるか」までで、「問いかけが良い／悪い」ではありません。")
    if not ask:
        print("  母集団が空です。判定しません。")
        return 1

    an = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    got = _totals(an, ask, start.isoformat(), end.isoformat())
    print(f"  Analytics（{start}〜{end}・{got['rows']}本に行が立った）:")
    print(f"    再生 {got['views']:,}／コメント {got['comments']}／"
          f"共有 {got['shares']}／登録 {got['subscribersGained']}")

    # **行が立たない本は「公開されていない本」です**（予約のまま Analytics に載らない）。
    # 母集団 375本のうち行が立ったのが5本、という形になります。**再生0ではありません。**
    print(f"    ＊ 行が立たなかった {len(ask) - got['rows']}本は、**まだ公開されていない本**です"
          "（予約のまま）。再生0の本ではありません")

    # **裏取り: チャンネル全体でもコメントは0か。**（2026-08-20 10:3x に足した）
    # 母集団は控えのある本だけなので、08/15 より前に出した本が落ちています。
    # そちらでコメントが付いていたら、この判定は母集団の切り方のせいになります。
    try:
        whole = an.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics="views,comments,shares",
        ).execute()
        row = (whole.get("rows") or [[0, 0, 0]])[0]
        print(f"  裏取り（チャンネル全体・同じ窓）: 再生 {int(row[0]):,}／"
              f"コメント {int(row[1])}／共有 {int(row[2])}")
        if int(row[1]) == 0:
            print("    **全体でも0件。** 母集団の切り方のせいではありません")
    except HttpError as exc:
        print(f"  裏取りが取れませんでした: {str(exc)[:110]}")

    v = ev.verdict(got["views"], got["comments"], got["shares"])
    print(f"  → {v['line']}")
    if got["views"]:
        print(f"    コメント率 {got['comments']/got['views']*100:.4f}%／"
              f"共有率 {got['shares']/got['views']*100:.4f}%")

    # **閉じた判定を開け直すかどうか**（2026-08-31 に足した）。
    # 前は「コメントが1件でも付いたら覆る」で、**2026-08-31 にそのとおり発火し、
    # 発火してから条件のほうが壊れていると分かりました** ——
    # 分母が伸びれば、どんな底の率でもいつか 1件 は出ます。
    # **率で見ること**（`src/endcard_verdict.reversal` の docstring に実測）。
    r = ev.reversal(got["views"], got["comments"])
    print(f"  → 覆る条件（`config/hypotheses.yaml` の 3384行あたり）: {r['line']}")
    if not r["reversed"]:
        print("    **開け直さないこと。** この前提は 2026-08-20 に閉じており、"
              "率はそのとき（0件）より**強く外れ側**に出ています")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
