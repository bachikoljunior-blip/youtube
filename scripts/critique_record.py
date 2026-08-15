#!/usr/bin/env python3
"""独立評価（M13）のスコアを積み、評価器そのものを反証にかける。

**手順は `docs/CRITIQUE.md`、掛け算と採用理由は `docs/MEANS.md` の M13。**

この道具の役目は2つだけ。

    積む    python scripts/critique_record.py <動画ID> <s1> <s2> <s3> [--note "..."]
    調べる  python scripts/critique_record.py --check

**なぜ積むのか。** ゲート（中央値6未満なら作り直す）を入れただけでは、
それが効いているかを誰も知りません。予測しないスコアで作り直しを命じれば、
**1本あたりの生成費を増やしながら何も改善しません。
測れない検査は、検査ではなく儀式です。**

だから `config/hypotheses.yaml` に反証条件を置いてあります。

    評価付きのショートが6本たまった時点で、
    中央値スコアと engaged 比率の順位相関が **+0.4 に届かない** → **ゲートを外す**

`--check` はその判定に必要な数字を出すだけで、勝手にゲートを外しません。
**外すのは人（次の回のセッション）の判断で、JOURNAL に理由を書いてから。**
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scan import _spearman  # noqa: E402  順位相関は既にあるものを使う

JST = timezone(timedelta(hours=9))
LEDGER = Path(__file__).resolve().parent.parent / "data" / "critique.jsonl"

# **判定に要る本数。** hypotheses.yaml の反証条件と同じ数にしてあります。
# ここだけ変えると条件と食い違うので、変えるなら両方直すこと。
NEEDED = 6
THRESHOLD = 0.4


def _load() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def record(video_id: str, scores: list[float], note: str = "") -> None:
    if len(scores) < 3:
        # **3体でないと中央値が意味を持ちません。**2体だと平均になり、
        # 1体が外れ値を出したときにそのまま通ります。
        print(f"[critique] 3体ぶん要ります（いま {len(scores)}件）", file=sys.stderr)
        raise SystemExit(1)

    median = statistics.median(scores)
    row = {
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "video": video_id,
        "scores": scores,
        "median": median,
        "note": note,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # **較正期間なので、ここで生産を止めません**（2026-08-15、`docs/CRITIQUE.md`）。
    # ここは 8/15 まで「中央値6未満 → **作り直す**」と出していました。
    # ところが同じ日に、その門は**自分を検証できない作り**だと分かっています——
    # engaged は公開しないと付かないのに、門は低い点を公開させないので、
    # **低い点の engaged が原理的に手に入らず、順位相関が永久に出せません。**
    # 実績も通過率0%（中央値 3・5・4・4）で、**未検証の計器が M14 を塞いでいました。**
    #
    # 文書だけ較正期間に変えて**この出力を直し忘れると**、次に来た側は
    # 画面の「作り直す」に従い、同じ塞ぎ方が戻ります。**基準は下げていません**
    # （下の「本来の決め方」は `docs/CRITIQUE.md` にそのまま残してあります）。
    if median < 6:
        print(f"[critique] {video_id} スコア {scores} → 中央値 {median} "
              "→ **較正期間なので公開は止めない**（点は必ず記録する）")
        print("  基準を下げたのではありません。`docs/CRITIQUE.md` の"
              "「本来の決め方」（中央値6未満は作り直す）は保留中です。")
        print("  低い点のものを公開しないと、**低い点が本当に伸びないのかが分かりません。**")
    else:
        print(f"[critique] {video_id} スコア {scores} → 中央値 {median} "
              "→ そのまま投稿してよい")


def check() -> None:
    rows = _load()
    print(f"=== 独立評価の記録（{LEDGER}）===")
    if not rows:
        print("  まだ1件もありません。手順は docs/CRITIQUE.md")
        print(f"  **判定には {NEEDED}本 要ります。**")
        return

    for r in rows:
        print(f"  {r['at'][:16]}  {r['video']:12s} {r['scores']} → 中央値 {r['median']}")

    try:
        from src.analytics import fetch_report
        perf = {r["video"]: r for r in fetch_report(days=28)}
    except Exception as exc:                      # 資格情報が無い回でも記録は読める
        print(f"  [!] 実績を取れませんでした（{exc}）。積んだぶんだけ出しました。")
        return

    # **記録はテーマID、Analytics は動画ID。**そのまま `perf.get()` すると
    # 必ず None になり、突き合わせが**永久に0件**のまま
    # 「2〜3日遅れます」と出続けます（2026-08-15 に発覚。詳細は
    # `src/history.py` の `topic_video_map`）。ここで橋を掛けます。
    try:
        from src.history import topic_video_map
        topic_to_video = topic_video_map()
    except Exception as exc:
        print(f"  [!] テーマ→動画の対応を引けませんでした（{exc}）。"
              "テーマIDで積んだぶんは突き合わせられません。")
        topic_to_video = {}

    # **同じ動画が2回入っていることがあります。** `critique_queue.py` の
    # `_scored()` が `video_id` というキーを読んでいて（積む側は `video`）、
    # **点を付けても待ち行列から消えなかった**ため、同じものに3体を投げ直した回が
    # あります（`s-kojo-4` と `s-iryohi-2` が2回ずつ）。
    # 実績は動画ごとに1つなので、**そのまま並べると同じ点が2票ぶん効きます。**
    # 待ち行列のほうは直しましたが、**既に積まれた行は消せません**
    # （記録を書き換えないこと）。ここで**動画ごとに最後の1件だけ**を使います。
    latest = {r["video"]: r for r in sorted(rows, key=lambda r: r["at"])}
    if len(latest) < len(rows):
        print(f"  [注] 同じ動画の記録が {len(rows) - len(latest)} 件ありました。"
              "**動画ごとに最後の1件だけ**を突き合わせに使います")

    xs, ys, used = [], [], []
    unresolved: list[str] = []
    for r in latest.values():
        key = r["video"]
        if key not in perf and key in topic_to_video:
            key = topic_to_video[key]             # テーマID → 動画ID
        p = perf.get(key)
        if not p:
            unresolved.append(r["video"])
            continue
        views = p.get("views", 0)
        # **30再生未満は入れない。**分母が小さいと比率が壊れます
        # （`src/scan.py` が同じ理由で同じ線を引いています）。
        if views < 30:
            continue
        engaged = p.get("engagedViews", 0) / views * 100
        xs.append(r["median"])
        ys.append(engaged)
        used.append((r["video"], r["median"], engaged, views))

    print()
    print(f"  engaged と突き合わせられたもの {len(used)}件 / 必要 {NEEDED}件")
    for vid, med, eng, views in used:
        print(f"    {vid:12s} 中央値 {med:4.1f}  engaged {eng:5.1f}%  ({views}再生)")

    if unresolved:
        # **「まだ来ていない」と「そもそも結びつかない」を混ぜないこと。**
        # 混ぜていたせいで、構造的な穴が「待てば埋まる」に見えていました。
        print(f"  突き合わせられなかったもの {len(unresolved)}件: "
              f"{', '.join(sorted(set(unresolved)))}")
        print("    未公開・30再生未満・Analytics 未到着のどれかです。"
              "**テーマIDが引けないのが理由なら、それは待っても埋まりません。**")

    if len(used) < NEEDED:
        print(f"  **まだ判定できません。**あと {NEEDED - len(used)}本。")
        print("  （公開直後は Analytics に行が出ません。2〜3日遅れます）")
        return

    rho = _spearman(xs, ys)
    if rho is None:
        print("  順位相関が出せませんでした（値が全部同じ、など）")
        return

    print(f"  **順位相関 {rho:+.2f}**（しきい値 {THRESHOLD:+.2f}）")
    if rho < THRESHOLD:
        print("  → **外れ。ゲートを外すこと。**"
              "スコアは engaged を予測していません。")
        print("    `config/hypotheses.yaml` の該当項目に verdict を書き、"
              "`docs/CRITIQUE.md` の決め方を消してから外すこと。")
    else:
        print("  → 反証されていません。ゲートは続けてよい。")
        print("    **ただし「効いている」の証明ではありません。**"
              "n が小さいので、1本で反転しうる段階です。")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="独立評価（M13）のスコアを積む／調べる")
    ap.add_argument("video", nargs="?", help="動画ID")
    ap.add_argument("scores", nargs="*", type=float, help="3体ぶんのスコア（0〜10）")
    ap.add_argument("--note", default="", help="書き換えた点など")
    ap.add_argument("--check", action="store_true", help="いまの本数と順位相関を出す")
    args = ap.parse_args(argv)

    if args.check or not args.video:
        check()
        return 0

    record(args.video, args.scores, args.note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
