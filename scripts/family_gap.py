#!/usr/bin/env python3
"""**題材の族で分けた2群の、1本あたり再生を突き合わせる。**（API は0単位）

    python scripts/family_gap.py --family ribo
    python scripts/family_gap.py --family ribo --age 24 --long

## なぜ要るか

`src/ab_split.py` の A/B は**テーマIDのハッシュで2群へ振り分ける**ので、
「族そのものを外へ振ったらどうなるか」は数えられません（族は ID で決まらない）。
そして 2026-08-29 まで、`src/calc/` の 63本 は**全部が税・年金・社会保険**でした。
つまり **「この題材の見込み客が尽きた」という原因の候補は、
一度も切り分けられる形になっていません**（`docs/JOURNAL.md` 2026-08-28 18:0x の申し送り）。

**中央値の大小だけで判定しないこと。** `src/ab_power.py` の実測で、
**効きが無くても 49% で「上回った」と出ます。** ここは同じ道具の
`rank_sum_rule`（中央値が上回り、かつ順位和の片側 p ≤ 0.20）を通します。

## 交絡（隠さないこと）

**これは A/B ではありません。** 族は無作為に割り当てられておらず、
族の外の本は「後から作った本」でもあります。**公開日が違えば配信の帯も違う**ので、
`--since` で窓を切って、同じ窓に公開された本だけを突き合わせること。
それでも「新しい族だから配信が試された」の側は残ります。
**言えるのは向きと桁まで**で、因果ではありません。
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import ab_power, dupes  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import per_video_why as pvw  # noqa: E402

#: 片群の床。`src/ab_split.floor_of` の既定と同じ 16本 は長尺には届かないので、
#: **呼ぶ側が指定する**。既定はショート向け。
FLOOR_DEFAULT = 8


def window_of(age: float | None) -> tuple[float, float]:
    """齢の窓。**既定は `per_video_why` と同じ 20〜120時間の最初の読み。**

    `--age` を書いた回だけ、その齢のまわり（0.85〜1.4倍）へ狭めます。
    **既定を狭めないこと** —— `data/views.jsonl` の読みは1日1〜2回で、
    狭い窓は「読みが無かった本」を丸ごと落とします
    （実測 2026-08-29: 齢20時間ちょうどに絞ると 65本・中央値 3、
    既定の窓なら 129本・中央値 219）。
    """
    if age is None:
        return pvw.AGE_LO, pvw.AGE_HI
    return age * 0.85, age * 1.4


def groups(family: str, *, age: float | None, since: str | None,
           long_form: bool) -> tuple[list[float], list[float]]:
    """(族の中, 族の外) の「齢をそろえた再生」。"""
    points = pvw.load_points()
    ledger = {r["id"]: r for r in dupes.ledger_rows() if r.get("topic")}
    lo, hi = window_of(age)
    cut = None
    if since:
        cut = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)

    inside: list[float] = []
    outside: list[float] = []
    for vid, rows in points.items():
        row = ledger.get(vid)
        if not row:
            continue
        topic = str(row["topic"])
        is_short = topic.startswith("s-")
        if is_short == long_form:          # --long なら s- を外す。既定はその逆
            continue
        views = pvw.aligned(rows, lo, hi)
        if views is None:
            continue
        if cut is not None:
            when = row.get("uploaded_at") or row.get("at")
            if not when:
                continue
            got = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
            if got.tzinfo is None:
                got = got.replace(tzinfo=timezone.utc)
            if got < cut:
                continue
        # 族は「テーマIDが族の名前で始まる」で決める（`s-` の有無を先に外す）
        stem = topic[2:] if is_short else topic
        (inside if stem.startswith(family + "-") else outside).append(float(views))
    return inside, outside


def report(family: str, *, age: float | None, since: str | None,
           long_form: bool, floor: int) -> str:
    inside, outside = groups(family, age=age, since=since, long_form=long_form)
    what = "長尺" if long_form else "ショート"
    lo, hi = window_of(age)
    out = [f"=== 族 `{family}` と、それ以外の{what}"
           f"（齢 {lo:.0f}〜{hi:.0f}時間の最初の読み）==="]
    if since:
        out.append(f"  窓: {since} 以降に投稿した本だけ")
    out.append(f"  族の中 **{len(inside)}本** ／ 族の外 **{len(outside)}本**"
               f"（床 片群 {floor}本）")
    if len(inside) < floor or len(outside) < floor:
        out.append("  **まだ判定できません。** 片群が床に届いていません —— "
                   "**期限だけ延ばして、条件は1文字も緩めないこと。**")
        if inside:
            out.append(f"  （参考・族の中の中央値 {st.median(inside):,.0f}）")
        if outside:
            out.append(f"  （参考・族の外の中央値 {st.median(outside):,.0f}）")
        return "\n".join(out)

    mi, mo = st.median(inside), st.median(outside)
    p = ab_power.rank_sum_p(inside, outside)
    hit = ab_power.rank_sum_rule(inside, outside)
    out.append(f"  中央値: 族の中 **{mi:,.0f}** ／ 族の外 **{mo:,.0f}**"
               f"（比 **{mi / mo:.2f}倍**）" if mo else
               f"  中央値: 族の中 **{mi:,.0f}** ／ 族の外 **{mo:,.0f}**")
    out.append(f"  順位和（片側・「族の中のほうが大きい」側）の p = **{p:.3f}**"
               f"（α = {ab_power.ALPHA}）")
    out.append(f"  → **{'上回った' if hit else '上回っていない'}**"
               "（中央値の大小だけでは、効きが無くても 49% で『上回った』と出ます）")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True, help="`src/calc/` の族の名前（例 ribo）")
    ap.add_argument("--age", type=float, default=None,
                    help="そろえる齢（時間）。書かなければ per_video_why と同じ窓")
    ap.add_argument("--since", help="この日以降に投稿した本だけ（YYYY-MM-DD）")
    ap.add_argument("--long", action="store_true", help="長尺の側を数える")
    ap.add_argument("--floor", type=int, default=FLOOR_DEFAULT, help="片群の床")
    a = ap.parse_args()
    print(report(a.family, age=a.age, since=a.since,
                 long_form=a.long, floor=a.floor))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
