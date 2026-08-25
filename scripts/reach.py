#!/usr/bin/env python3
"""**インプレッションとクリック率を、自分で取る。**（2026-08-15 に作った）

    python scripts/reach.py            # 取れたぶんを出す（無ければ「まだ」と言う）
    python scripts/reach.py --setup    # 収集ジョブを作る（1回だけでよい）

## なぜ要るか

`docs/FOR_OWNER.md` の1番目は「Studio のインプレッションとクリック率を教えてください」
でした。**オーナーの手が要る計画は、読まれなければゼロです**（目標本文）。
そして 2026-08-15 にオーナーから来た問いはこれです:

> **studioは自分で確認する方法ないの？ あと、どこから見たらいいかわかんない。**

**ありました。** これまで「API では取れない」と書いていたのは、
**YouTube Analytics API しか試していなかった**からです（`metrics="impressions"` は
`Unknown identifier` で 400 が返る。これは事実）。

**別の API があります。YouTube Reporting API です。**
`reportTypes.list()` を叩いたら、**`channel_reach_basic_a1` と
`channel_reach_combined_a1`** が返りました。**Studio の「リーチ」タブと同じ名前**です。

    scopes は既存のまま（yt-analytics.readonly）。**再認証は要りませんでした。**

## 仕組み（Analytics API と作りが違う）

Reporting API は**その場で数字を返しません。** ジョブを作ると、YouTube が
**1日1回 CSV を生成**して置いていきます。**作った時点から最大30日ぶんを遡って**
埋めてくれるので、**待てば過去ぶんも入ります。**

    1. jobs.create（`--setup`。**2026-08-15 08:58 JST に実行済み**）
    2. 翌日以降、jobs.reports.list に CSV が並ぶ
    3. downloadUrl を取って解析（この道具がやる）

**だから初回は「まだ何も無い」が正常です。** 24〜48時間後の回で取れます。

## 取れたら何が変わるか

いま「再生数が伸びない」の原因を**切り分けられていません**:

    インプレッションが少ない  → **見せられていない**（題材・投稿頻度の問題）
    CTR が低い                → **見せたのに押されない**（サムネと題の問題）

**直す場所が正反対です。** サムネを作り直す作業に意味があるかどうかは、
この2つが分かって初めて判定できます。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.discovery import build  # noqa: E402

from src import reach_split  # noqa: E402
from src.auth import credentials  # noqa: E402

REPORT_TYPES = ("channel_reach_basic_a1",)
STORE = Path(__file__).resolve().parent.parent / "data" / "reach.jsonl"


def _api():
    return build("youtubereporting", "v1", credentials=credentials(),
                 cache_discovery=False)


def setup() -> int:
    """収集ジョブを作る。**冪等**（同じ report type が既にあれば作らない）。"""
    rep = _api()
    jobs = rep.jobs().list().execute().get("jobs", [])
    have = {j.get("reportTypeId") for j in jobs}
    for rt in REPORT_TYPES:
        if rt in have:
            print(f"[reach] 既にあります: {rt}")
            continue
        j = rep.jobs().create(body={"reportTypeId": rt, "name": f"reach {rt}"}).execute()
        print(f"[reach] 作りました: {j['id']} ({rt}) {j['createTime']}")
    print("[reach] **最初の CSV が並ぶまで24〜48時間かかります。**"
          " 過去ぶんは最大30日さかのぼって埋まります。")
    return 0


def _download(rep, url: str) -> str:
    return rep._http.request(url)[1].decode("utf-8")  # noqa: SLF001


def seen_report_ids(path: Path | None = None) -> set[str]:
    """**もう積んだ報告のID。**（2026-08-20 21:3x に足した）

    ここが無いあいだ、この道具は **`reports[-3:]` の3本しか落としていません**でした。
    ジョブは**作った時点から最大30日ぶんを遡って**日ごとの CSV を置くので、
    **在るのに一度も読んでいない日**が残ります（実測: 8/20 時点で 3日ぶんだけ積まれ、
    それより前は1行も無し）。**古い日が要るのは、伸び率をそこからしか出せないから**です。

    そして `STORE` は**追記しかしません。** 同じ報告を2度落とすと、
    同じ日が二重に積まれます（`src.reach_split.dedupe` が読む側でも潰しますが、
    **書く側で止めるほうが安い**）。
    """
    p = path or STORE
    if not p.exists():
        return set()
    out: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = row.get("_report_id")
        if rid:
            out.add(str(rid))
    return out


def show(limit: int | None = None) -> int:
    rep = _api()
    jobs = [j for j in rep.jobs().list().execute().get("jobs", [])
            if j.get("reportTypeId") in REPORT_TYPES]
    if not jobs:
        print("[reach] **ジョブがありません。** `python scripts/reach.py --setup` を先に。")
        return 1

    rows_all: list[dict] = []
    seen = seen_report_ids()
    skipped = 0
    for job in jobs:
        reports = rep.jobs().reports().list(jobId=job["id"]).execute().get("reports", [])
        if not reports:
            print(f"[reach] {job['reportTypeId']}: **まだ CSV が1本もありません。**")
            print(f"        ジョブを作ったのは {job['createTime']}。"
                  " **24〜48時間かかります。** 次の回でまた見ること。")
            continue
        reports.sort(key=lambda r: r.get("endTime", ""))
        # **まだ積んでいない報告は、全部落とすこと。**`limit` は明示したときだけ効きます
        # （既定で切ると、遡って埋まったぶんが永久に読まれません）。
        todo = [r for r in reports if str(r.get("id", "")) not in seen]
        skipped += len(reports) - len(todo)
        if limit is not None:
            todo = todo[-limit:]
        print(f"[reach] {job['reportTypeId']}: 報告 {len(reports)}本"
              f" / 未読 {len(todo)}本 を落とします")
        for r in todo:
            text = _download(rep, r["downloadUrl"])
            for row in csv.DictReader(io.StringIO(text)):
                row["_report_end"] = r.get("endTime", "")
                row["_report_id"] = str(r.get("id", ""))
                rows_all.append(row)

    if not rows_all:
        print(f"[reach] **新しい報告はありません**（積み済み {skipped}本）。"
              " 積んである分から出します。")
        print()
        print(reach_split.render(reach_split.load_rows()))
        return 0

    STORE.parent.mkdir(parents=True, exist_ok=True)
    with STORE.open("a", encoding="utf-8") as fh:
        for row in rows_all:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[reach] {len(rows_all)} 行を {STORE.name} に積みました")

    # **列名は実物に合わせる。** 想像で書かないこと（まだ実物を見ていない）。
    cols = list(rows_all[0].keys())
    print("[reach] 列:", ", ".join(cols))

    imp_col = next((c for c in cols if "impression" in c.lower()
                    and "ctr" not in c.lower()), None)
    ctr_col = next((c for c in cols if "ctr" in c.lower()
                    or "click_through" in c.lower()), None)
    vid_col = next((c for c in cols if c.lower() in ("video_id", "video")), None)
    if not (imp_col and vid_col):
        print("[reach] **インプレッションの列が見つかりません。**"
              " 上の列名を見て、この道具を直すこと。")
        return 1

    per = defaultdict(lambda: [0.0, 0.0])
    for row in rows_all:
        try:
            imp = float(row.get(imp_col) or 0)
        except ValueError:
            continue
        clicks = 0.0
        if ctr_col:
            try:
                # **この列は「割合」で、百分率ではありません**（`src.reach_split._clicks`
                # に実物の裏取り）。`/ 100` していたあいだ、クリックは100分の1に見えて
                # いました（CTR 1.3% が 0.013% と出る）。
                clicks = imp * float(row.get(ctr_col) or 0)
            except ValueError:
                clicks = 0.0
        acc = per[row[vid_col]]
        acc[0] += imp
        acc[1] += clicks

    print("\n  動画            インプレッション    CTR")
    for vid, (imp, clicks) in sorted(per.items(), key=lambda kv: -kv[1][0])[:15]:
        ctr = (clicks / imp * 100) if imp else 0.0
        print(f"  {vid:<14} {imp:>14,.0f} {ctr:>7.2f}%")
    print("\n  **少ないのがインプレッションなら、直すのは題材と本数。**")
    print("  **CTR が低いなら、直すのはサムネと題。** 逆をやっても動きません。")

    # **形で割ること**（2026-08-20 21:3x）。全体の一覧だけでは、
    # 段4（長尺で月50万再生）の前提が立っているかを言えません。
    print()
    print(reach_split.render(reach_split.load_rows()))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--setup", action="store_true", help="収集ジョブを作る（冪等）")
    ap.add_argument("--limit", type=int, default=None,
                    help="落とす報告の本数（既定は**未読を全部**）")
    args = ap.parse_args(argv)
    return setup() if args.setup else show(args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
