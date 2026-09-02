#!/usr/bin/env python3
"""**1本あたり再生の天井を、このチャンネルの外で測る。**（2026-09-02・最適化の回）

    python scripts/niche_ceiling.py            # 既定（search.list 4回 ＝ 400単位）
    python scripts/niche_ceiling.py --dry-run  # 撃たずに、何を撃つかだけ出す
    python scripts/niche_ceiling.py --queries 6

## なぜ要るか（**この回に数えて分かったこと**）

`scripts/eta.py` は毎回こう言います ——

> `per_video` は **×4.49 が天井**（実測 4,229）…… 日付が出はじめるのは **×98.16**、
> つまり **天井そのものを ×21.88 上げないと、この腕でも出ません。**
> ＝ この回に立てるべき前提は「**その天井は天井ではない**」

**その 4,229 は、どこから来ているか。** `src/rule_per_video.ceiling_at_rule()` ——
**このチャンネルが出した 600本 の最大（1,891回・NHKylqsNfTw）**を、
公開密度で1段 外挿した数です。**外の数は1つも入っていません。**

**＝ 天井は鏡です。** 自分が作った本の最大を自分の上限と呼んでいるので、
**同じ作り方を続けるかぎり、この天井は原理的に超えられません**
（超えた本が出たときだけ天井が上がる ＝ 定義上いつも「いま届かない」）。

目標の本文はこう言っています ——

> **最短とは、原理的に最大の理論値で、その理論値は空想のものであり、
> つねに発見、達成はできていないものと考えられます。**

**自分の記録は「原理的に最大の理論値」ではありません。** 同じニッチ・同じ形で
**外の誰かが実際に取っている数**のほうが、理論値にずっと近い下限です。
この道具は、それを撃って取ります。

## 何を返すか

同じ帯（日本語・お金／年金／税／住宅ローンの計算）の本を `search.list` で
再生数順に引き、**自分のチャンネルを除いて**、`videos.list` で実数を取ります。
尺で `short`（60秒以下）と `long` に分け、それぞれの **最大・p90・中央値**を返し、
`ceiling_at_rule()` の 4,229 と比べた**倍率**を出します。

    倍率 ≥ 21.88  → **天井は鏡だった。** `eta.py` の「出ません」は形のせいではない
    倍率 < 1      → **ニッチのほうが天井。** 変えるのは本の作り方ではなくニッチ
                    （`CLAUDE.md`「ニッチも尺も形式も頻度もチャンネルも、変えてよい対象です」）

## 覆る条件

- `search.list order=viewCount` は**関連度で絞ったうえでの再生数順**なので、
  帯の真の最大ではなく**下限**です。倍率が小さく出たときに「ニッチの天井だ」と
  読むには、**語を変えて2回以上**撃つこと（`--queries` を増やす）。
- 語が外れていれば帯が違います。`QUERIES` は `data/uploaded.jsonl` の実題から
  採ってあります。**題の傾向が変わったら、ここも変えること。**
- 外の本は**公開からの齢がばらばら**です。`--days` で窓を切っていますが、
  伸びきりの補正はしていません（自分の側の 4,229 は伸びきり補正ずみ）。
  **つまりこの比較は、外の側に不利**（少なく出る）側に倒れています。
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: **帯の語**（`data/uploaded.jsonl` の実題から採った。推測ではない）。
QUERIES = [
    "遺族年金 いくら 計算",
    "変動金利 5年ルール 未払利息",
    "再就職手当 計算",
    "不動産取得税 計算",
    "加給年金 いくら",
    "標準報酬月額 計算",
]

LEDGER = ROOT / "data" / "niche_ceiling.jsonl"

#: `scripts/eta.py` の `lever_need_over_cap`（天井をいくつ上げれば日付が出るか）。
#: **この数は動きます。** 判定に使う前に `data/eta.jsonl` の最後の行を見ること。
NEED_OVER_CAP = 21.88


def _iso8601_seconds(text: str) -> int:
    """`PT1M30S` → 90。**尺で short/long を分けるのに要る。**"""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text or "")
    if not m:
        return 0
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _own_channel(youtube) -> str:
    try:
        r = youtube.channels().list(part="id", mine=True).execute()
        return (r.get("items") or [{}])[0].get("id", "")
    except Exception:                                          # noqa: BLE001
        return ""


def probe(queries: list[str], days: int = 365, per_query: int = 25) -> dict:
    """撃って、外の本の再生数を返す。**`search.list` は1回100単位。**"""
    from googleapiclient.discovery import build

    from src import quota_ledger
    from src.auth import credentials

    try:
        quota_ledger.install()
    except Exception:                                          # noqa: BLE001
        pass
    youtube = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
    own = _own_channel(youtube)

    after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(
        timespec="seconds").replace("+00:00", "Z")

    ids: dict[str, str] = {}                    # video_id -> 引いた語
    for q in queries:
        try:
            r = youtube.search().list(
                part="id", q=q, type="video", order="viewCount",
                maxResults=per_query, regionCode="JP", relevanceLanguage="ja",
                publishedAfter=after).execute()
        except Exception as exc:                               # noqa: BLE001
            print(f"[niche] search.list 失敗（{q}）: {exc}", file=sys.stderr)
            continue
        for it in r.get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                ids.setdefault(vid, q)

    rows: list[dict] = []
    keys = list(ids)
    for i in range(0, len(keys), 50):
        chunk = keys[i:i + 50]
        try:
            r = youtube.videos().list(
                part="statistics,contentDetails,snippet",
                id=",".join(chunk)).execute()
        except Exception as exc:                               # noqa: BLE001
            print(f"[niche] videos.list 失敗: {exc}", file=sys.stderr)
            continue
        for it in r.get("items", []):
            sn = it.get("snippet", {})
            st = it.get("statistics", {})
            cd = it.get("contentDetails", {})
            ch = sn.get("channelId", "")
            if own and ch == own:
                continue                        # **自分は数えない**（鏡を外すのが目的）
            secs = _iso8601_seconds(cd.get("duration", ""))
            rows.append({
                "id": it.get("id"), "views": int(st.get("viewCount", 0) or 0),
                "secs": secs, "form": "short" if 0 < secs <= 60 else "long",
                "channel": ch, "title": sn.get("title", ""),
                "published": sn.get("publishedAt", ""),
                "q": ids.get(it.get("id"), ""),
            })
    return {"rows": rows, "own": own, "queries": queries, "days": days}


def summarize(rows: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for form in ("short", "long"):
        vals = sorted(r["views"] for r in rows if r["form"] == form)
        if not vals:
            out[form] = {"n": 0}
            continue
        out[form] = {
            "n": len(vals), "max": vals[-1],
            "p90": vals[int(0.9 * (len(vals) - 1))],
            "median": int(statistics.median(vals)),
            "channels": len({r["channel"] for r in rows if r["form"] == form}),
        }
    return out


def own_ceiling() -> float | None:
    """`src/rule_per_video.ceiling_at_rule()` の値（**比べる相手**）。"""
    try:
        from src import rule_per_video
        c = rule_per_video.ceiling_at_rule()
        return float(c.get("value")) if c else None
    except Exception:                                          # noqa: BLE001
        return None


def verdict(best: float, own: float, need: float = NEED_OVER_CAP) -> tuple[str, str]:
    """**外の最大と自分の天井から、次の手を1つに決める。**（純関数・撃たない）

    返り `(code, line)`。`code` は `mirror` / `niche_short` / `niche_wall`。
    """
    ratio = (best / own) if own else 0.0
    if ratio >= need:
        return "mirror", (
            f"[!] **外の最大は自分の天井の ×{ratio:.1f} で、要る ×{need:.2f} を超えています。**"
            f" ＝ **{own:,.0f}回 は帯の天井ではなく、この作り方の天井です。**"
            " `eta.py` の「出ません」は、形ではなく**作り方**のせい ——"
            " 次の手は `improve`（1本の作り方を変える）です")
    if ratio >= 1.0:
        return "niche_short", (
            f"[!] **外の最大は自分の天井の ×{ratio:.1f}。要る ×{need:.2f} には届きません。**"
            " ＝ 作り方で天井を上げても足りない。**帯（ニッチ）を変える手が要ります**"
            "（`CLAUDE.md`「ニッチも尺も形式も頻度もチャンネルも、変えてよい対象です」）")
    return "niche_wall", (
        f"[!] **外の最大でも自分の天井の ×{ratio:.1f} —— 帯そのものが天井です。**"
        " **本の作り方をいくら直しても届きません。ニッチを変えること。**")


def latest(path: Path | None = None) -> dict | None:
    """**帳面の最後の1件**（`data/niche_ceiling.jsonl`）。**撃ちません・API 0単位。**

    `scripts/eta.py` が毎回これを読みます —— **撃った数が主実行に届く口**です。
    """
    p = path or LEDGER
    row = None
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:                              # noqa: BLE001
                    continue
    except FileNotFoundError:
        return None
    return row


def eta_line(need_over_cap: float | None = None, path: Path | None = None,
             now: datetime | None = None) -> str | None:
    """**`eta.py` の「天井そのものを ×N 上げないと」の直後に出す1行。**

    ## なぜ要るか（2026-09-02・最適化の回）

    `eta.py` はずっと「**この回に立てるべき前提は『その天井は天井ではない』**」
    と書いていました。**書いてあるだけで、確かめる口がありませんでした** ——
    天井 4,229 は `ceiling_at_rule()` ＝ **自分の記録**から作った数で、
    「天井ではない」と言うための**外の数**がどこにも無かったからです。

    この行は、`niche_ceiling.py` が実際に撃って取った**外の最大**を、
    要る倍率（`lever_need_over_cap`）と**同じ画面**に並べます。
    **並ばないかぎり、撃った数は主実行に届きません。**

    **覆る条件**: 帳面が空／古い（30日超）なら `None` を返して1行も出しません
    —— **出ない行は、読む側の手順を増やしません。**
    """
    row = latest(path)
    if not row:
        return None
    own = row.get("own_ceiling")
    s = row.get("summary") or {}
    best = max((int((s.get(f) or {}).get("max", 0) or 0) for f in ("short", "long")),
               default=0)
    if not own or not best:
        return None
    age = ""
    try:
        at = datetime.fromisoformat(str(row["at"]))
        d = ((now or datetime.now(timezone.utc)) - at).days
        if d > 30:
            return None
        age = f"{d}日前"
    except Exception:                                          # noqa: BLE001
        pass
    need = need_over_cap if isinstance(need_over_cap, (int, float)) and need_over_cap \
        else NEED_OVER_CAP
    code, line = verdict(best, own, need)
    forms = " ／ ".join(
        f"{'ショート' if f == 'short' else '長尺'} 最大 {int(d['max']):,}回（n={d['n']}）"
        for f, d in s.items() if (d or {}).get("n"))
    return (f"   {line} —— **外の実測**（`scripts/niche_ceiling.py`・{age}）: {forms}。"
            f" 自分の天井 {own:,.0f}回 は `ceiling_at_rule()` ＝ **自分の記録**から作った数です。"
            " **取り直す手**: `python scripts/niche_ceiling.py`"
            "（`search.list` 100単位/語。**日枠が尽きていたら 429 で 0本**）")


def render(res: dict) -> list[str]:
    rows = res["rows"]
    s = summarize(rows)
    own = own_ceiling()
    L = ["=== 帯の天井を、チャンネルの外で測る（`search.list`・外の本だけ）===",
         f"  語 {len(res['queries'])}件 ／ 窓 {res['days']}日 ／ 拾えた外の本 **{len(rows)}本**"]
    if own:
        L.append(f"  自分の天井（`ceiling_at_rule()`）: **{own:,.0f}回**"
                 "　← これは**自分の記録**から作った数です")
    for form, label in (("short", "ショート"), ("long", "長尺")):
        d = s.get(form) or {"n": 0}
        if not d["n"]:
            L.append(f"  {label}: 拾えませんでした（語か窓を変えること）")
            continue
        line = (f"  {label}: n={d['n']}本／{d['channels']}チャンネル　"
                f"最大 **{d['max']:,}回** ／ p90 {d['p90']:,}回 ／ 中央 {d['median']:,}回")
        if own:
            line += (f"　→ 自分の天井の **×{d['max'] / own:.1f}**"
                     f"（p90 で ×{d['p90'] / own:.1f}）")
        L.append(line)
    if own:
        best = max((s[f].get("max", 0) for f in ("short", "long")), default=0)
        L.append("  " + verdict(best, own)[1])
    top = sorted(rows, key=lambda r: -r["views"])[:8]
    if top:
        L.append("  外の上位8本（**この帯で実際に取れている数**）:")
        for r in top:
            L.append(f"    {r['views']:>9,}回  {r['form']:<5} {r['title'][:44]}")
    return L


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", type=int, default=4)
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    qs = QUERIES[:max(1, a.queries)]
    if a.dry_run:
        print(f"[niche] 撃つ語 {len(qs)}件 ＝ search.list {len(qs)}回 ＝ {100 * len(qs)}単位")
        for q in qs:
            print("   ", q)
        return 0
    res = probe(qs, days=a.days)
    for line in render(res):
        print(line)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "queries": qs, "days": a.days, "n": len(res["rows"]),
            "summary": summarize(res["rows"]), "own_ceiling": own_ceiling(),
        }, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
