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

**この「6本」が、2026-08-24 まで欠陥でした**（`long_ids` の docstring）。
長尺は同じ34日で **12本**あり、面は **1,278 → 1,456**（+13.9%）。
表の形は変わりません —— **見せて、押されていない**のはそのままです。

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

#: 「いま続いている量」を測る窓（日）。**平均でも最大でもない、段取りが乗る数。**
RECENT_DAYS = 7

#: **窓の中の1日が、この割合以上を占めていたら「平均」は使えません**（2026-08-26 に足した）。
#:
#: 実測（`data/reach.jsonl`・長尺・08/15〜08/21 の7日）:
#:
#:     4 / 8 / 5 / 7 / 8 / 17 / **1,285**   → 平均 190.6 ・ 中央値 **8**
#:
#: 08/21 の 1,285回 のうち **1,276回（99.3%）が、その日に公開した5本**に付いています。
#: 同じ日、それ以前の長尺6本に付いたのは **1〜3回ずつ**でした。
#: つまり長尺の面は「立っている面」ではなく、**公開日の立ち上がりだけ**です。
#: `tail()` の docstring は最初から「**平均は burst をならしてしまいます**」と
#: 書いていましたが、**`per_day_recent` は平均のままでした** ——
#: そして `scripts/eta.py` の段2 がその 190.6 を読んで
#: 「合格点 191回/日 と**ちょうど同じ（×1.00）**」と印字していました。
#: 続いている量は 8回/日 なので、実際は **24倍 足りません。**
#: **同じ帳面の読み手2つが逆を向いていた形の5件目**（4件目は `summary()` の docstring）。
BURST_SHARE = 0.5
STORE = ROOT / "data" / "reach.jsonl"
LEDGER = ROOT / "data" / "uploaded.jsonl"
PAIRS = ROOT / "config" / "pairs.yaml"
#: **YouTube 自身が「長尺」と数えた動画IDの控え**（`src/rpm_mix.py --record` が書く）。
#: この道具は API を叩かないので、**測った側が置いていったものを読みます。**
FORMS = ROOT / "data" / "video_forms.json"

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


def measured_long_ids(forms_path: Path | None = None) -> set[str]:
    """**YouTube 自身が長尺と数えた動画ID**（`data/video_forms.json`）。

    書くのは `src/rpm_mix.py --record`（Analytics の `creatorContentType` を
    `video` べつに1回引くだけ）。**ここでは API を叩きません** ——
    この道具の約束は「積んであるものを読むだけ」だからです。

    **無ければ空**を返します。呼ぶ側（`long_ids`）が `pairs.yaml` と足すので、
    控えがまだ無い機械でも、いままでと同じ答えになります。
    """
    p = forms_path or FORMS
    if not p.exists():
        return set()
    try:
        raw = json.loads(p.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        return set()
    forms = raw.get("forms") or {}
    return {vid for vid, form in forms.items() if form == "長尺"}


def long_ids(pairs_path: Path | None = None,
             forms_path: Path | None = None) -> set[str]:
    """長尺の動画ID ＝ **測った控え ∪ `config/pairs.yaml`**。

    ## なぜ足すのか（2026-08-24 に直した。**天井の分母が半分だった**）

    ここは長らく `config/pairs.yaml` **だけ**を読んでいました。ところが
    あの表は「**ショート → 同じ題材の長尺**」の対応表で、
    ファイルの頭にこう書いてあります —— 「**同じ題材の公開済み長尺が
    あるものだけ**」。つまり**対になっていない長尺は、初めから入りません。**

    実測（2026-08-24・Analytics の `creatorContentType`）:

        `pairs.yaml` が名指しする長尺   **6本**
        YouTube が長尺と数えた本        **12本**（直近90日に再生のあったもの）

    そして `src/rpm_mix.surface_ceiling()` は、この集合で
    **長尺のインプレッション（面）**を数え、それが `scripts/eta.py` の
    段2 の合格点を決めています ——

        [!] いまの面（長尺のインプレッション 37.6回/日）は、CTR 100% でも 38回/日。
            合格点の 187回/日 に **5.0倍 足りません**

    **その 37.6 が、半分の本で数えた数でした。**（足すと 42.8回/日 ＝ +13.9%）

    **もっと悪いのは向きのほうです。** `rpm_mix` は自分でこう印字します ——
    「**長尺を出せば面が増え、次の回の測り直しでこの天井は上がります**」。
    `pairs.yaml` は**手で書く表**なので、新しく出した長尺は入りません。
    **出しても天井が動かない** ＝ 腕 `rpm` を引いた回が、
    自分の効きを測れない形になっていました。

    **控えのほうを正本にしないのは**、再生が0本の長尺を Analytics が
    返さないからです（実測 `SSI1MVb12Ng`）。**足すと、どちらの穴も塞がります。**
    """
    out = measured_long_ids(forms_path)
    p = pairs_path or PAIRS
    if p.exists():
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out |= set(dict(raw.get("pairs", {})).values())
    return out


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


def _median(vals: list[float]) -> float:
    """**並べて真ん中**。空なら 0.0（呼ぶ側で「測れていない」に落とすため）。"""
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def summary(rows: list[dict], longs: set[str]) -> dict:
    """形べつに集計する。

    返り: `{"長尺": {...}, "ショート": {...}, "days": n, "dates": [...],
    "last_day": "20260821"}`。**`last_day` は「積んである最後の日」**で、
    今日ではありません（2026-08-24 に足した —— この帳面が4日ぶん止まったまま
    天井を作っていて、誰にも見えていませんでした）。
    **「ショート」は「長尺でないもの」**です（控えに無い本もこちらへ入れる ——
    分母を大きく見せる側に倒すため。長尺の側を大きく見せない）。

    ## `per_day` と `per_day_max` は、使い先が違います（2026-08-24 に分けた）

        per_day        全期間の平均。**いま出ている量**を言う（表示むき）
        per_day_max    いちばん大きかった1日。**天井**を言う（`surface_ceiling` むき）
        per_day_live   中身のある日だけの平均（立ち上がる前の 0日 を分母から外す）
        per_day_recent 直近 RECENT_DAYS 日の平均。**段取りが乗る量**（段2 むき）

    **この4つを取り違えると、答えが逆になります。** 2026-08-25 の実測:

        全期間の平均    73.0回/日   → 段2 の合格点 191回/日 に **2.6倍 足りない**
        直近7日の平均  190.6回/日   → 合格点と **ほぼ同じ（×1.0）**
        最大の1日    1,285.0回/日   → 合格点の **6.7倍**

    そして `scripts/eta.py` の段2 は、**最大の1日**を当てて
    「**面は足りています（6.7倍）** —— ここから先で効くのは CTR のほう」と
    印字していました。同じ回の `status.py` は同じ帳面から
    「**87倍 足りません。足りないのはインプレッションです**」と印字しています。
    **同じ帳面の読み手2つが、逆を向いていた**（この形は4件目）。
    段2 が問うているのは「450日 続けられるか」で、**38日でいちばん良かった1日は
    その答えになりません。** 天井（`rpm` が届きうるか）だけが最大の1日を使います。

    **平均を天井に使うと、天井が実測より下に出ます。** 実物（08/24）:
    38日の平均 **73.0回/日** に対し、最大の1日は **1,285回**（08/21・全期間の46%）。
    最初の20日は**面そのものが存在しない日**（長尺の公開前）で、平均はそれを分母に
    数えていました。**存在しなかった日を数えて上限を作っていた**ということです。
    この 73.0 が `rpm` の天井（¥287）→ 段4 の合格点（695,675回/月）→
    **「月20万には届きません」**まで、まっすぐ効いていました。
    """
    rows = dedupe(rows)
    dates = sorted({str(r.get("date", "")) for r in rows if r.get("date")})
    out: dict[str, dict] = {}
    per_day_of: dict[str, dict[str, float]] = {}
    for key in ("長尺", "ショート"):
        out[key] = {"impressions": 0.0, "clicks": 0.0, "videos": set()}
        per_day_of[key] = {d: 0.0 for d in dates}
    for r in rows:
        key = "長尺" if str(r.get("video_id")) in longs else "ショート"
        out[key]["impressions"] += _imp(r)
        out[key]["clicks"] += _clicks(r)
        out[key]["videos"].add(str(r.get("video_id")))
        d = str(r.get("date", ""))
        if d in per_day_of[key]:
            per_day_of[key][d] += _imp(r)
    days = len(dates)
    for key, v in out.items():
        v["videos"] = len(v["videos"])
        v["per_day"] = v["impressions"] / days if days else 0.0
        v["ctr"] = (v["clicks"] / v["impressions"] * 100) if v["impressions"] else 0.0
        # **いちばん大きかった1日**（2026-08-24 に足した）。`per_day` は平均で、
        # **天井の分母には使えません** —— 下の docstring 「天井は最大の1日で読む」。
        series = per_day_of[key]
        best = max(series.items(), key=lambda kv: kv[1], default=("", 0.0))
        v["per_day_max"] = best[1]
        v["per_day_max_on"] = best[0] or None
        v["per_day_series"] = series
        # 中身のある日だけの平均（面が立ち上がる前の 0日 を分母から外した数）
        live = [x for x in series.values() if x > 0]
        v["per_day_live"] = (sum(live) / len(live)) if live else 0.0
        v["live_days"] = len(live)
        # **いま続いている量**（直近 RECENT_DAYS 日の平均。2026-08-25 に足した）。
        #     上の `tail()` の docstring が「**段取りが乗るのは、いま見せられている
        #     量のほう**」と書いているのに、その数は `render()` の中で
        #     `summary(tail(rows, 7))` を組み直したときにしか出ませんでした。
        #     **`summary()` の返りだけを持って歩く呼び側（`rpm_mix.surface_ceiling`
        #     → `scripts/eta.py`）からは、平均か最大の2つしか見えていません。**
        #     どちらも段取りの分母には使えない数です（片方は存在しなかった日を
        #     数え、片方は38日でいちばん良かった1日）。ここで一緒に返します。
        recent = dates[-RECENT_DAYS:]
        v["per_day_recent"] = (
            (sum(series[d] for d in recent) / len(recent)) if recent else 0.0)
        v["recent_days"] = len(recent)
        # **その平均を、1日が丸ごと作っていないか**（2026-08-26 に足した。
        #     `BURST_SHARE` の docstring に実測）。**上の平均は残します** ——
        #     保存済みの点と比べられなくなるため。判断に使うのは下の
        #     `per_day_sustained` のほうです。
        vals = sorted(series[d] for d in recent)
        total_recent = sum(vals)
        top = vals[-1] if vals else 0.0
        v["per_day_recent_top"] = top
        v["per_day_recent_top_share"] = (top / total_recent) if total_recent else 0.0
        v["per_day_recent_median"] = _median(vals)
        if v["per_day_recent_top_share"] >= BURST_SHARE and len(vals) >= 3:
            v["per_day_sustained"] = v["per_day_recent_median"]
            v["per_day_sustained_basis"] = (
                f"直近{len(vals)}日の中央値"
                f"（平均 {v['per_day_recent']:,.1f} は"
                f" 1日で {v['per_day_recent_top_share'] * 100:.0f}% ＝ 立ち上がりの burst）")
        else:
            v["per_day_sustained"] = v["per_day_recent"]
            v["per_day_sustained_basis"] = f"直近{len(vals)}日の平均"
    return {"長尺": out["長尺"], "ショート": out["ショート"], "days": days,
            "dates": dates, "last_day": dates[-1] if dates else None}


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
