"""**動画の「作り」の特徴と、engaged／再生 を突き合わせる。**

## なぜ要るか（2026-08-19 15:5x）

`scripts/eta.py` が名指しする律速は **1本あたりの再生**です。天井の行は
「ショート 高（RPM ¥60）＝ 1本あたりを **1.4倍**（869回 → 1,208回）」で、
**本数を増やしても在庫を増やしても、この倍率は1ミリも動きません**（`docs/MEANS.md` M20/M21）。

そして `scripts/status.py` の実測では、再生数と同じ向きに動く率は
**engagedViews／再生 が +0.62 で最大**、平均視聴率（+0.13）と平均視聴秒（+0.03）は
無関係でした。**engaged の実測幅は 12.2%〜46.8% ＝ 3.8倍**で、
**要る 1.4倍より幅のほうが大きい。**

**足りなかったのは「どの作りが engaged 側に寄るか」で、これを測る道具が
このリポジトリに1つもありませんでした**（2026-08-19 15:1x の設計の見直し）。

## 鍵は手元にあります（**Data API は要りません**）

15:1x の回は「鍵（`video_id` → テーマID）を `data/uploaded.jsonl` から作る道は
**使えません** —— 直近28日に再生のあった28本のうち ledger に居たのは6本だけ」と
書き残しました。**測り直したら違いました** —— `data/scan.jsonl` の最新点で
**再生のある20本のうち19本が ledger にいます**（`tests/test_build_perf.py`）。

だから、この道具は**API を1単位も使いません**。読むのは3つとも手元のファイルです:

    data/scan.jsonl          動画べつの views / engagedViews（Analytics の写し）
    data/uploaded.jsonl      video_id → テーマID → 題
    data/published_bars.json テーマID → 図の枚数と棒の本数

## 割り引いて読むこと（**ここを外すと n=19 の雑音を設計にします**）

- **n は 20 前後です。** 出るのは仮説までで、当たりではありません
- **交絡が全部残っています** —— 公開時刻・族・配信の広さ・題材の人気。
  この道具が言えるのは「向き」だけで、**理由は言えません**
- **率の分母**: 再生 `MIN_VIEWS` 未満は落とします。ただし
  **落とした側が答えである可能性**は消えません（15:1x の床の件と同じ形）。
  だから落とした本数と、その内訳を必ず印字します
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from src.scan import _spearman

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "data" / "scan.jsonl"
LEDGER = ROOT / "data" / "uploaded.jsonl"
BARS = ROOT / "data" / "published_bars.json"

# 率の分母の下限。**これ未満は向きの計算に入れない**（分母が小さいと率が壊れる）。
MIN_VIEWS = 30

_SHORTS = re.compile(r"\s*#Shorts?\s*$", re.I)
_NUM = re.compile(r"[0-9０-９]+")


def _latest_scan() -> dict[str, Any]:
    last = None
    for line in SCAN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = line
    if last is None:
        raise RuntimeError(f"{SCAN} が空です")
    return json.loads(last)


def per_video(snap: dict[str, Any] | None = None) -> dict[str, dict[str, float]]:
    """`data/scan.jsonl` の最新点から、動画べつの数字を取り出す。"""
    snap = snap or _latest_scan()
    out: dict[str, dict[str, float]] = {}
    for key, val in snap.get("values", {}).items():
        parts = key.split(".")
        if len(parts) != 3 or parts[0] != "動画":
            continue
        out.setdefault(parts[1], {})[parts[2]] = val
    return out


def ledger() -> dict[str, dict[str, Any]]:
    """`video_id` → 投稿の控え。**同じIDが複数行にあるときは後の行が勝ちます。**"""
    out: dict[str, dict[str, Any]] = {}
    if not LEDGER.exists():
        return out
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("video_id"):
            out[row["video_id"]] = row
    return out


def _width(s: str) -> int:
    """全角を2、半角を1で数える。**字数は見た目の幅で効くはず**なので。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def features(topic: str, title: str, bars: dict[str, Any]) -> dict[str, float]:
    """1本ぶんの「作り」の特徴。**全部、公開前に決まっているものだけ。**

    公開後にしか分からないもの（再生・engaged）は特徴に入れません。
    入れると「よく回った本はよく回る」という同義反復が出ます。
    """
    plain = _SHORTS.sub("", title)
    nums = _NUM.findall(plain)
    charts = (bars.get(topic) or {}).get("charts") or []
    return {
        "図の枚数": float(len(charts)),
        "棒の本数": float(sum(len(c) for c in charts)),
        "題の幅": float(_width(plain)),
        "題の数字の桁": float(max((len(n) for n in nums), default=0)),
        "題の数字の個数": float(len(nums)),
    }


def collect() -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """測れた本と、落とした本（理由つき）を返す。"""
    stats = per_video()
    led = ledger()
    bars = json.loads(BARS.read_text(encoding="utf-8")) if BARS.exists() else {}

    rows: list[dict[str, Any]] = []
    dropped: list[tuple[str, str]] = []
    for vid, s in stats.items():
        views = s.get("views", 0)
        if not views:
            dropped.append((vid, "再生0"))
            continue
        entry = led.get(vid)
        if entry is None:
            dropped.append((vid, "控えに無い（鍵が引けない）"))
            continue
        if views < MIN_VIEWS:
            dropped.append((vid, f"再生{MIN_VIEWS}未満（分母が小さい）"))
            continue
        topic = entry.get("topic", "")
        f = features(topic, entry.get("title", ""), bars)
        rows.append(
            {
                "video_id": vid,
                "topic": topic,
                "title": entry.get("title", ""),
                "views": float(views),
                "engaged": float(s.get("engagedViews", 0)) / float(views),
                "subs": float(s.get("subscribersGained", 0)),
                "features": f,
            }
        )
    rows.sort(key=lambda r: -r["views"])
    return rows, dropped


def correlations(rows: list[dict[str, Any]]) -> list[tuple[str, float | None, float | None]]:
    """特徴ごとに、engaged との向きと 再生 との向き。**向きだけを読むこと。**"""
    if not rows:
        return []
    names = list(rows[0]["features"])
    out = []
    for name in names:
        xs = [r["features"][name] for r in rows]
        out.append(
            (
                name,
                _spearman(xs, [r["engaged"] for r in rows]),
                _spearman(xs, [r["views"] for r in rows]),
            )
        )
    out.sort(key=lambda t: -(abs(t[1]) if t[1] is not None else -1))
    return out
