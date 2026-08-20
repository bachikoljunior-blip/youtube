#!/usr/bin/env python3
"""**インプレッションを「長尺」と「ショート」で割る。**（2026-08-20 21:3x に作った）

`scripts/reach.py` が積む `data/reach.jsonl`（YouTube Reporting API の
`channel_reach_basic_a1`）を読んで、**面に載っている本数**を形べつに出す。
**API は1単位も叩きません**（積んである CSV を読むだけ）。

## なぜ要るか（この道具が出た日の実測）

`reach.py` は 2026-08-15 に作られ、**8/20 21:2x に初めて叩かれました**（5日ぶん放置）。
そして出た数字には、**欠陥が2つ**ありました。

1. **報告を新しい3本しか落としていませんでした**（`reports[-3:]`）。ジョブは
   **作った時点から30日ぶん遡って**日ごとの CSV を置きます。全部落としたら
   **3日 → 34日**（165行 → 540行）。**在るのに読んでいなかっただけ**です
2. **CTR の列を百分率として読んでいました**（`/ 100`）。実物は**割合**です
   （`_clicks()` に裏取り）。**クリック数が100分の1に見えていました**

直したうえで、形で割るとこうです（2026-07-15〜2026-08-17・34日）:

    ショート  インプレッション 1,339  クリック 18   CTR **1.34%**
    長尺 6本  インプレッション 1,278  クリック  3   CTR **0.23%**

**長尺は「見せられていない」のではありませんでした。**
1,278回 見せて、押されたのが3回です。そして**見せる量そのものが落ちています** ——
08/09 の **346/日** から 08/15〜17 は **5/日**。**試されて、外された**形です。

**段取り（`scripts/eta.py` の段2・段4）は、長尺で月50万再生を立てています。**
直近の面は 1日5回。**CTR を100%にしても月150回**で、要る数の3,300分の1。
`status.py` の実測では再生の **99.9% が SHORTS_FEED**、WATCH は28日で13再生 ——
**この34日で、サムネの面が生んだ再生は合計21回**です。数字が合います。

## 読み方（**インプレッションと CTR は、直す場所が正反対**）

    インプレッションが少ない  → 見せられていない（**題材・本数・面そのもの**）
    CTR が低い                → 見せたのに押されない（**サムネと題**）

**ショートのフィードは、この報告のインプレッションに入りません**（スワイプは
サムネのクリックではない）。だから**ショートの再生数と、ここの数字は別物**です。
ここに出るのは「**サムネを見せた面**」＝ ブラウズ・検索・関連動画の合計です。
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "reach.jsonl"
LEDGER = ROOT / "data" / "uploaded.jsonl"
PAIRS = ROOT / "config" / "pairs.yaml"

#: 段4（月20万）が長尺に置いている月あたり再生数。`scripts/eta.py` の
#: `TARGET_YEN 200,000` ÷ `RPM_SCENARIOS["長尺 お金 低"] 400` × 1000。
#: **写しではなく計算で出すこと**（片方だけ動くと、この道具が古い数字で断じます）。
def plan_views_month(target_yen: int = 200_000, rpm: int = 400) -> float:
    return target_yen * 1000 / rpm


def load_rows(path: Path | None = None) -> list[dict]:
    """`data/reach.jsonl` を読む。**無ければ空**（この道具は API を叩かない）。"""
    p = path or STORE
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def dedupe(rows: list[dict]) -> list[dict]:
    """同じ `(date, video_id)` は**最後に積んだ行**を残す。

    報告は日ごとに作り直されることがあり、`reach.py` は追記しかしません。
    **積み直した日が二重に数えられる**ので、読む側で潰します。
    """
    keep: dict[tuple[str, str], dict] = {}
    for r in rows:
        keep[(str(r.get("date", "")), str(r.get("video_id", "")))] = r
    return list(keep.values())


def long_ids(pairs_path: Path | None = None) -> set[str]:
    """長尺の動画ID。`config/pairs.yaml` が正本（`src/m8_funnel.py` と同じ口）。"""
    p = pairs_path or PAIRS
    if not p.exists():
        return set()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return set(dict(raw.get("pairs", {})).values())


def _imp(row: dict) -> float:
    try:
        return float(row.get("video_thumbnail_impressions") or 0)
    except (TypeError, ValueError):
        return 0.0


def _clicks(row: dict) -> float:
    """クリック数 ＝ インプレッション × CTR。**CTR の列は「割合」です。**

    2026-08-20 21:4x に実物で確かめました。`scripts/reach.py` は長らく
    **`/ 100` して**いましたが、この列は百分率ではありません:

        impressions 148 / ctr 0.0067567567567567571  ＝ **1/148**（クリック1）
        impressions 112 / ctr 0.0089285714285714281  ＝ **1/112**（クリック1）
        impressions   1 / ctr 1                      ＝ **1/1**（クリック1）

    **逆数がぴったり出ます。** 百分率なら 0.0067% ＝ 1万回に1回で、
    1本の動画に 148回しか見せていない日には出ようがない数です。
    裏取りがもう1つあります —— 2026-08-15 にオーナーが Studio の画面で読んだ
    **CTR 1.3%** は、この直し方でショートの実測（1.34%）と一致します
    （`/100` のままだと 0.013% で、100倍ずれます）。
    """
    try:
        return _imp(row) * float(row.get("video_thumbnail_impressions_ctr") or 0)
    except (TypeError, ValueError):
        return 0.0


def tail(rows: list[dict], days: int) -> list[dict]:
    """**直近 N 日ぶんだけ**返す（日付の実物で切る。今日から数えない）。

    平均は burst をならしてしまいます —— 長尺は 08/09 に 346回 見せられ、
    08/17 には 5回です。**段取りが乗るのは、いま見せられている量のほう。**
    """
    dates = sorted({str(r.get("date", "")) for r in rows if r.get("date")})[-days:]
    keep = set(dates)
    return [r for r in rows if str(r.get("date", "")) in keep]


def summary(rows: list[dict], longs: set[str]) -> dict:
    """形べつに集計する。

    返り: `{"長尺": {...}, "ショート": {...}, "days": n, "dates": [...]}`。
    **「ショート」は「長尺でないもの」**です（控えに無い本もこちらへ入れる ——
    分母を大きく見せる側に倒すため。長尺の側を大きく見せない）。
    """
    rows = dedupe(rows)
    dates = sorted({str(r.get("date", "")) for r in rows if r.get("date")})
    out: dict[str, dict] = {}
    for key in ("長尺", "ショート"):
        out[key] = {"impressions": 0.0, "clicks": 0.0, "videos": set()}
    for r in rows:
        key = "長尺" if str(r.get("video_id")) in longs else "ショート"
        out[key]["impressions"] += _imp(r)
        out[key]["clicks"] += _clicks(r)
        out[key]["videos"].add(str(r.get("video_id")))
    days = len(dates)
    for key, v in out.items():
        v["videos"] = len(v["videos"])
        v["per_day"] = v["impressions"] / days if days else 0.0
        v["ctr"] = (v["clicks"] / v["impressions"] * 100) if v["impressions"] else 0.0
    return {"長尺": out["長尺"], "ショート": out["ショート"], "days": days, "dates": dates}


def gap(sm: dict, need_views_month: float | None = None) -> dict:
    """**長尺の面が、段4の要求に対して何倍足りないか。**

    上限は「**CTR 100%**」で置きます（サムネと題を極限まで直した先）。
    ここでも足りないなら、**直す先はサムネではなく面そのもの**です。
    """
    need = plan_views_month() if need_views_month is None else need_views_month
    per_day = sm["長尺"]["per_day"]
    ceiling_month = per_day * 30            # CTR 100% の上限
    now_month = ceiling_month * sm["長尺"]["ctr"] / 100
    return {
        "need_views_month": need,
        "impressions_per_day": per_day,
        "ceiling_views_month": ceiling_month,
        "now_views_month": now_month,
        "short_by": (need / ceiling_month) if ceiling_month else float("inf"),
    }


RECENT_DAYS = 7


def render(rows: list[dict], longs: set[str] | None = None) -> str:
    """毎回の状態に出す短い節（**6行**）。**判断に使うのは直近のほう。**"""
    longs = long_ids() if longs is None else longs
    rows = dedupe(rows)
    sm = summary(rows, longs)
    if not sm["days"]:
        return ("=== サムネを見せた面（Reporting API）===\n"
                "  **まだ1行もありません。** `python scripts/reach.py` を叩くこと"
                "（ジョブが無ければ `--setup`）。")
    rc = summary(tail(rows, RECENT_DAYS), longs)
    g = gap(rc)
    lines = [
        "=== サムネを見せた面（Reporting API・**ショートのフィードは入りません**）===",
        f"  実測 {sm['days']}日ぶん（{sm['dates'][0]}〜{sm['dates'][-1]}）"
        f"／ 直近 {rc['days']}日で見ます",
        f"  ショート  全期間 {sm['ショート']['impressions']:>7,.0f}回"
        f"  CTR {sm['ショート']['ctr']:.2f}%"
        f"  ／ 直近 **1日 {rc['ショート']['per_day']:.1f}回**"
        f"  CTR {rc['ショート']['ctr']:.2f}%",
        f"  長尺      全期間 {sm['長尺']['impressions']:>7,.0f}回"
        f"  CTR {sm['長尺']['ctr']:.2f}%"
        f"  ／ 直近 **1日 {rc['長尺']['per_day']:.1f}回**"
        f"  CTR {rc['長尺']['ctr']:.2f}%",
    ]
    if g["short_by"] == float("inf") or g["short_by"] > 1:
        lines += [
            f"  [!] 段4は長尺で **月 {g['need_views_month']:,.0f}再生** を立てています。"
            f"いまの面は **CTR 100% でも月 {g['ceiling_views_month']:,.0f}回**"
            f" ＝ **{g['short_by']:,.0f}倍 足りません**",
            "      **足りないのはインプレッションです。**"
            "サムネと題（CTR）をいくら直しても、この面は動きません",
        ]
    else:
        lines.append("  面は足りています。**足りないなら CTR のほう**（サムネと題）")
    return "\n".join(lines)
