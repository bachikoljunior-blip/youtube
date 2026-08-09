#!/usr/bin/env python3
"""**視界の外を、機械的に列挙する。**

    python scripts/audit.py            # 全部
    python scripts/audit.py --quick    # API を叩かない（速い）
    python scripts/audit.py --force    # 保存した測定を捨てて測り直す

## なぜ要るか

2026-08-09、1日のうちに同じ形の見落としが3つ出た。

    averageViewPercentage … **取得していたのに表示していなかった**
    他プラットフォーム     … **できるのに候補に挙げていなかった**
    週15%の予算           … **恒久指示から消えたのに守っていた**

どれも「検討して却下した」のではない。**視界に入っていなかった。**
そして視界の外にあるものは、意志では思い出せない。
JOURNAL に「気をつける」と書いても、次の回には視界の外に戻る。

**だから、視界の外を機械に数えさせる。**
ここが出すのは「答え」ではなく「まだ見ていないもの」の一覧。

## 何を数えるか

1. **持っているのに見ていない** … API が返す指標のうち、こちらが使っていないもの
2. **できるのに並べていない** … `docs/MEANS.md` の未着手
3. **根拠が消えたのに守っている** … `docs/CONSTRAINTS.md` の B項目で、長く見直していないもの
4. **期限が来たのに判定していない** … `config/hypotheses.yaml`

## いつ走らせるか

**週1回、または目標の数字が2週間動かなかったとき。**
`scripts/status.py` が前回からの経過を出す。
**走らせたら、必ず1件は手をつけること。** 数えるだけなら数えない方がまし
（「見た」という記録だけが残って、見落としが正当化される）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "audit.json"
# B項目をこれ以上ほうっておいたら、根拠を確かめ直す。
STALE_DAYS = 14

# **API に聞く候補。** discovery に列挙が無いので、実際に叩いて確かめる。
# ここに無いものは見つからないので、**思いついたら足すこと。**
CANDIDATE_METRICS = [
    "views", "redViews", "engagedViews", "comments", "likes", "dislikes", "shares",
    "videosAddedToPlaylists", "videosRemovedFromPlaylists",
    "estimatedMinutesWatched", "estimatedRedMinutesWatched",
    "averageViewDuration", "averageViewPercentage",
    "subscribersGained", "subscribersLost",
    "cardImpressions", "cardClickRate", "cardTeaserImpressions", "cardTeaserClickRate",
    "annotationImpressions", "annotationClickThroughRate", "annotationCloseRate",
    "estimatedRevenue", "estimatedAdRevenue", "grossRevenue", "cpm",
    "playbackBasedCpm", "adImpressions", "monetizedPlaybacks",
    "audienceWatchRatio", "relativeRetentionPerformance",
]
CANDIDATE_DIMENSIONS = [
    "day", "month", "video", "ageGroup", "gender", "country", "province",
    "deviceType", "operatingSystem", "subscribedStatus", "youtubeProduct",
    "insightTrafficSourceType", "insightTrafficSourceDetail",
    "insightPlaybackLocationType", "sharingService", "elapsedVideoTimeRatio",
    "liveOrOnDemand", "creatorContentType", "adType",
]


def _load() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _save(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _used_in_source() -> set[str]:
    """`src/` が実際に使っている指標・次元を、ソースから拾う。

    **記憶に頼らない。** 「使っているつもり」と「使っている」はずれる。
    """
    used: set[str] = set()
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'(?:metrics|dimensions)\s*=\s*"([^"]+)"', text):
            used |= {x.strip() for x in m.group(1).split(",") if x.strip()}
    return used


def probe_analytics(force: bool = False) -> dict:
    """**API に「これ使える?」と1つずつ聞く。** 結果は保存して使い回す。

    discovery に列挙が無いので、これが唯一の確かめ方。
    こちらが名前を知らない指標は見つからないが、**知っている名前について
    「使えるのに使っていない」は確実に出る。**
    """
    state = _load()
    cached = state.get("analytics")
    # **鍵が増えたら測り直す。** 2026-08-09 に `per_video_metrics` を足したとき、
    # 古いキャッシュがそのまま返って**新しい判定が一度も走らなかった。**
    # 「保存してあるから速い」は、保存の中身が古い形だと**ただの嘘**になる。
    if cached and not force and "per_video_metrics" in cached:
        return cached

    from googleapiclient.discovery import build

    from src.analytics import credentials

    api = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end, start = date.today(), date.today() - timedelta(days=28)

    def works(metrics: str, dimensions: str = "day") -> bool:
        try:
            api.reports().query(
                ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
                metrics=metrics, dimensions=dimensions, maxResults=1,
            ).execute()
            return True
        except Exception:
            return False

    print("API に問い合わせています（指標と次元を1つずつ）…")
    # **`day` で通っても `video` で通るとは限らない。**
    # 2026-08-09 に判明: `videosAddedToPlaylists`・`dislikes`・`redViews`・
    # card 系・annotation 系は **`day` では 200、`video` では 400**。
    # 以前はここを `day` だけで試して「使えるのに使っていない」と数えていたので、
    # **動画べつに使えないものを12件、毎回「見落とし」として並べていた。**
    # 棚卸しの数を水増しするだけでなく、**手をつけようとした回を1回無駄にする。**
    ok_metrics = [m for m in CANDIDATE_METRICS if works(m)]
    per_video = [m for m in ok_metrics if works(m, "video")]
    # 次元は views と組み合わせて試す
    ok_dims = [d for d in CANDIDATE_DIMENSIONS if works("views", d)]
    result = {
        "checked_at": datetime.now(JST).isoformat(timespec="seconds"),
        "metrics": ok_metrics, "dimensions": ok_dims,
        "per_video_metrics": per_video,
    }
    state["analytics"] = result
    _save(state)
    return result


def report_analytics(quick: bool, force: bool = False) -> list[str]:
    print("\n=== 1. 持っているのに見ていない（Analytics）===")
    if quick:
        cached = _load().get("analytics")
        if not cached:
            print("  未計測。`python scripts/audit.py`（--quick なし）で1度叩くこと")
            return []
        data = cached
        print(f"  （前回の計測 {data['checked_at'][:16]} を使用）")
    else:
        data = probe_analytics(force=force)

    used = _used_in_source()
    gaps = []
    for kind, key in (("指標", "metrics"), ("次元", "dimensions")):
        unused = [x for x in data[key] if x not in used]
        print(f"  {kind}: 使える {len(data[key])} / 使っている {len(set(data[key]) & used)}")
        if not unused:
            continue
        # **動画べつに取れないものは、別枠にして見落としに数えない。**
        # チャンネル日次でしか取れず（`dimensions=day`）、本ごとの比較に使えない。
        # 数えると毎回12件が居座り、**棚卸しの件数が意味を持たなくなる。**
        per_video = data.get("per_video_metrics")
        if key == "metrics" and per_video is not None:
            day_only = [x for x in unused if x not in per_video]
            unused = [x for x in unused if x in per_video]
            if day_only:
                print(f"    （チャンネル日次のみ・動画べつには 400 になる: {', '.join(day_only)}）")
        if unused:
            print(f"    **使っていない**: {', '.join(unused)}")
            gaps += [f"Analytics の{kind} `{x}` を使っていない" for x in unused]
    return gaps


def report_means() -> list[str]:
    print("\n=== 2. できるのに並べていない（手段）===")
    path = ROOT / "docs" / "MEANS.md"
    if not path.exists():
        print("  docs/MEANS.md がありません")
        return ["docs/MEANS.md が無い"]
    text = path.read_text(encoding="utf-8")
    entries = re.findall(r"^### (M\d+)\. (.+?)$\n(.*?)(?=^### |\Z)", text, re.M | re.S)
    gaps = []
    for code, name, body in entries:
        m = re.search(r"\*\*状態\*\*: (.+)", body)
        state = m.group(1).strip() if m else "?"
        if "未着手" in state or "未検討" in state:
            print(f"  {code} {name}")
            gaps.append(f"手段 {code}（{name}）が未着手")
    if not gaps:
        print("  未着手なし")
    return gaps


def report_constraints() -> list[str]:
    """**自分で決めた条件のうち、長く見直していないもの。**

    B項目は「いつでも見直してよい」と書いてあるのに、**書いた日から
    一度も見直していない**ものがある。2026-08-09 の時点で
    B11 は「6時間おき」のままだった（実際は1時間おき）。
    B8 は「公開は19:00」だが、ショートは09:00 に出している。
    **文書のほうが現実に追いついていない。**
    """
    print(f"\n=== 3. 根拠が消えたのに守っている（B項目・{STALE_DAYS}日以上）===")
    path = ROOT / "docs" / "CONSTRAINTS.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    entries = re.findall(r"^### (B\d+)\. (.+?)$\n(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
    today = datetime.now(JST).date()
    gaps = []
    for code, name, body in entries:
        m = re.search(r"最終確認:\s*(\d{4}-\d{2}-\d{2})", body)
        if not m:
            print(f"  {code} {name[:34]} … **最終確認の日付が無い**")
            gaps.append(f"{code} に最終確認の日付が無い")
            continue
        seen = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        age = (today - seen).days
        if age >= STALE_DAYS:
            print(f"  {code} {name[:34]} … {age}日前")
            gaps.append(f"{code}（{name[:24]}）を{age}日見直していない")
    if not gaps:
        print("  古いものなし")
    return gaps


def report_hypotheses() -> list[str]:
    print("\n=== 4. 期限が来たのに判定していない ===")
    import yaml

    path = ROOT / "config" / "hypotheses.yaml"
    items = yaml.safe_load(path.read_text(encoding="utf-8")).get("hypotheses", [])
    today = datetime.now(JST).date()
    gaps = []
    for h in items:
        if h.get("verdict"):
            continue
        try:
            due = datetime.strptime(str(h["deadline"]), "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        if due <= today:
            print(f"  {h['claim'][:50]}（期限 {due}）")
            gaps.append(f"仮説「{h['claim'][:30]}」の判定が済んでいない")
    if not gaps:
        print("  期限切れなし")
    return gaps


def main() -> int:
    quick = "--quick" in sys.argv
    # **測り直す道を残しておくこと。** 保存した結果は放っておくと永久に古い。
    force = "--force" in sys.argv
    print("=== 棚卸し: 視界の外にあるものを数える ===")
    print("**数えるだけで終わらせないこと。** 必ず1件は手をつける。")

    gaps = (report_analytics(quick, force) + report_means()
            + report_constraints() + report_hypotheses())

    print(f"\n=== 合計 {len(gaps)} 件 ===")
    if not gaps:
        print("  見落としは見つかりませんでした。**候補リストが短い可能性を疑うこと。**")
        print("  `CANDIDATE_METRICS` と `docs/MEANS.md` に足りないものは無いか。")
    else:
        for i, g in enumerate(gaps, 1):
            print(f"  {i:2d}. {g}")
        print("\n**この中から最低1件、いま手をつけること。**")
        print("却下するなら、`docs/MEANS.md` か該当ファイルに**数字で**理由を書く。")

    state = _load()
    state["last_run"] = datetime.now(JST).isoformat(timespec="seconds")
    state["last_gap_count"] = len(gaps)
    _save(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
