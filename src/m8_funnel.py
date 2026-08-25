"""**M8（説明欄の導線）の判定に要る母集団を、Data API 抜きで決める。**

## なぜ要るか（2026-08-20 08:2x に踏んだ）

`config/hypotheses.yaml` の「ショートを見た人は、説明欄の導線があれば
同じ題材の長尺へ移る」は **期限 2026-08-21**、つまり明日です。
判定に使う唯一の道具は `scripts/watch_source.py` ですが、
**この回（08:1x JST）に叩いたら1行も出ずに落ちました。**

    HttpError 403 … youtube/v3/channels?part=contentDetails&mine=true
    quotaExceeded

**落ちた場所が問題です。** 落ちたのは `_videos()` ——
**「どの動画IDを Analytics に訊くか」を決めるためだけ**に Data API を叩く所で、
測定そのもの（`youtubeAnalytics.reports.query`）は**別枠で生きています**
（この回、`status.py` は Analytics の数字を全部出しています）。

    測りたいもの  … Analytics。**枠は生きている**
    落ちた所      … Data API。**IDの一覧を取るだけ**

Data API の日枠は太平洋時間の0時（JST 16:00）に戻り、そこから数時間で尽きます
（実測 08/17=97本・08/19=28本で閉）。**つまり1日のうち16時間、この判定は
構造的に下せません。** 期限は明日で、`--date` の窓（16:00〜）は
生成と投稿の取り合いになる時間帯です。

## 代わりに何を読むか

**この判定の母集団は、チャンネル全体ではありません。**
`falsified_if` が名指しているのは

    導線を入れたショート **8本** … `config/pairs.yaml` の鍵
    対応する長尺       **6本** … 同じ表の値（重複を除くと6本）

の2つで、**どちらも手元の設定ファイルに書いてあります。**
ショート側のIDは `data/uploaded.jsonl`（テーマID → 動画ID）から引けます。

`watch_source.py` の `_videos()` は「公開済みの全動画を長短に分ける」もので、
**M8 が要る母集団より広い**です。残りを全長尺で数えると、
**導線を入れていない長尺の流入まで M8 の成績に混ざります。**
ここを分けるのが、この道具の本体です。

## 分けられないもの

説明欄のクリック数そのものは API に無い（Studio 専用）ので、
成績は「**他の経路で説明できない残り**」としてしか読めません。
**0 は「効いていない」ではなく「効いている証拠が無い」**です。
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PAIRS = ROOT / "config" / "pairs.yaml"
LEDGER = ROOT / "data" / "uploaded.jsonl"

# 他の手段で説明がつく経路。M8 の成績から差し引く。
#   RELATED_VIDEO … 関連動画（M12・推薦面）
#   YT_SEARCH     … 検索（M4）
#   YT_CHANNEL    … チャンネルページ経由
#   EXT_URL       … 外部リンク（M10・GitHub Pages）
ATTRIBUTED = ("RELATED_VIDEO", "YT_SEARCH", "YT_CHANNEL", "EXT_URL")

# `falsified_if` に書いてある数。**設定と claim を離さないため、ここに置く。**
CLAIMED_SHORTS = 8
CLAIMED_LONGS = 6
TRIGGER_VIEWS = 3000   # ショート側がこれに達して初めて判定に入る
BASELINE = 0           # 2026-08-15 実測の残り
NEED = 5               # 基準からの上げ幅


def load_pairs(path: Path | None = None) -> dict[str, str]:
    """`config/pairs.yaml` の対応表（ショートのテーマID → 長尺の動画ID）。"""
    raw = yaml.safe_load((path or PAIRS).read_text(encoding="utf-8"))
    return dict(raw["pairs"])


def load_ledger(path: Path | None = None) -> list[dict]:
    """`data/uploaded.jsonl` を素で返す。**API を叩かない。**"""
    lines = (path or LEDGER).read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def populations(
    pairs: dict[str, str], ledger: list[dict]
) -> tuple[dict[str, list[str]], list[str]]:
    """判定の母集団を返す。

    返りは `(ショート: テーマID → 動画IDの一覧, 長尺: 動画IDの一覧)`。

    **ショートは1テーマに複数の動画IDが付きます。** 同じテーマを撮り直した
    回があるためで（実測4テーマ）、どれが導線入りかは控えからは決まりません。
    **決めずに全部返します** —— 呼ぶ側が Analytics の再生数で選べます
    （公開していない本は Analytics に行が立たないので、そこで落ちます）。
    """
    by_topic: dict[str, list[str]] = {}
    for row in ledger:
        by_topic.setdefault(row["topic"], []).append(row["video_id"])
    shorts = {topic: list(by_topic.get(topic, [])) for topic in pairs}
    longs: list[str] = []
    for vid in pairs.values():
        if vid not in longs:
            longs.append(vid)
    return shorts, longs


def residual(sources: dict[str, int], attributed: tuple[str, ...] = ATTRIBUTED) -> int:
    """流入元の内訳から、**他の手段で説明できない残り**を出す。"""
    return sum(v for k, v in sources.items() if k not in attributed)


def verdict(short_views: int, resid: int) -> dict:
    """反証条件をそのまま当てる。

    条件（`config/hypotheses.yaml`・2026-08-15 に直した版）:

        導線を入れたショート8本が **計3,000再生** に達した時点で、
        対応する長尺6本の残りが **基準0から5に届かない** なら外れ。

    返りの `state` は3つだけです。

        "not_yet"    … ショートがまだ3,000再生に届いていない（判定しない）
        "falsified"  … 届いていて、残りが5未満（**外れ**）
        "held"       … 届いていて、残りが5以上（**保つ**）
    """
    if short_views < TRIGGER_VIEWS:
        return {
            "state": "not_yet",
            "short_views": short_views,
            "residual": resid,
            "line": f"ショート {short_views}再生 < {TRIGGER_VIEWS} ＝ **まだ判定しない**",
        }
    gained = resid - BASELINE
    if gained < NEED:
        return {
            "state": "falsified",
            "short_views": short_views,
            "residual": resid,
            "line": (
                f"ショート {short_views}再生 ≥ {TRIGGER_VIEWS}／"
                f"残り {resid}（基準 {BASELINE} から +{gained}）< {NEED} ＝ **外れ**"
            ),
        }
    return {
        "state": "held",
        "short_views": short_views,
        "residual": resid,
        "line": (
            f"ショート {short_views}再生 ≥ {TRIGGER_VIEWS}／"
            f"残り {resid}（基準 {BASELINE} から +{gained}）≥ {NEED} ＝ **保つ**"
        ),
    }
