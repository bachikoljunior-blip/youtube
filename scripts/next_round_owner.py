#!/usr/bin/env python3
"""親の ``next_round`` を、Fable週間枠の公式メーター意味で起動する。

Anthropic の公式仕様では、対象プラン内のFable利用は通常の週間上限の50%分まで。
画面の「Fable のみ」は、その50%分を0〜100%へ正規化した内訳メーターなので、
**切替点は Fableのみ 100%**。50%ではない。

既存 ``scripts.quota.sub_model()`` には次の2つの誤りがあるため、このラッパーで
即時補正する。

1. ``fable_percent`` を50と比較している。
2. Fable専用目盛りを、他模型も含む全モデル消費速度で外挿している。

このファイルは利用可能性の門だけを補正する。仕事ごとの模型選択は
``docs/OWNER_INSTRUCTION_GATE.md`` の目標効果／使用量で行うこと。
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import quota  # noqa: E402

# 公式仕様: Fableに使える量は通常の全モデル週間上限の50%分。
OFFICIAL_FABLE_SHARE_OF_REGULAR_WEEK = 0.50

# UIの「Fable のみ」は上の50%分を0〜100%で表す。
FABLE_ONLY_GAUGE_FULL_PCT = 100.0


def corrected_sub_model(now: datetime | None = None) -> tuple[str, str]:
    """Fableの**利用可能性**を正しい目盛りで返す。

    仕事にFableを使うべきかは、ここでは決めない。これは枠が残っているかだけ。
    専用目盛りの増加率を測れていないため、全モデル速度での外挿はしない。
    """
    now = now or datetime.now(timezone.utc)
    gauge = quota.fable_gauge()
    if not gauge or not gauge.get("at"):
        return (
            "fable",
            "『Fable のみ』の目盛りがまだ無い。公式上限判定は未観測"
            "（画面が来たら --fable で積む）",
        )

    reset_at = gauge.get("resets")
    if reset_at and reset_at <= now:
        return (
            "fable",
            f"『Fable のみ』は {reset_at.astimezone(quota.JST):%m/%d %H:%M} JST に戻った"
            "（前の目盛りは切替判定に使わない）",
        )

    pct = float(gauge.get("pct", 0.0))
    seen = gauge["at"].astimezone(quota.JST)

    # **目盛りは人手でしか入らないので、必ず古くなります。** 古いぶんは
    # 「Fable のみ」**自身の速さ**で運ぶ（`quota.fable_rate()`・同じ枠の2点で測る。
    # 点が1つなら 全モデルの速さ ÷ 0.5 ＝ 公式仕様の比）。
    # 2026-09-03 03:5x に踏んだ: ここは運ばず、`quota.sub_model` は全モデルの速さで
    # 運んでいた（公式の比の 1/2）。どちらも、目盛りが実際に 100% に届いたあと
    # **1日 `fable` を返し続け**、その間に立てたサブは落ちる（A10 が破れる）。
    # 「全モデルの速度でFable専用目盛りを外挿しない」（docstring）は、
    # **比を掛けずに外挿するな**の意味で守る —— 比を掛けた外挿は公式仕様そのもの。
    est = quota.fable_estimate(now, gauge=gauge) or {}
    est_pct = float(est.get("est", pct))
    exhaust = est.get("exhaust_at")
    tail = ""
    if est.get("rate_source") in ("measured", "official"):
        tail = (f"。いま推定 {est_pct:.0f}%（{quota._fable_rate_words(est)}"
                + (f"・100% は {exhaust.astimezone(quota.JST):%m/%d %H:%M} JST" if exhaust else "")
                + "）")
    if max(pct, est_pct) >= FABLE_ONLY_GAUGE_FULL_PCT:
        return (
            "opus",
            f"『Fable のみ』{pct:.0f}%（{seen:%m/%d %H:%M} JST）"
            "＝公式のFable内訳上限100%に到達"
            "（通常の全モデル週間上限の50%分）" + tail
            + "。**新しい画面が来るまで Opus**",
        )

    return (
        "fable",
        f"『Fable のみ』{pct:.0f}%（{seen:%m/%d %H:%M} JST）"
        f"＜ 内訳上限{FABLE_ONLY_GAUGE_FULL_PCT:.0f}%"
        "（100%が通常の全モデル週間上限の50%分。50%では止めない）" + tail,
    )


def main() -> int:
    # next_round.main() は実行時に ``from scripts.quota import sub_model`` するため、
    # モジュール上の関数を差し替えれば同じ親の呼び全体へ効く。
    quota.FABLE_CAP_PCT = FABLE_ONLY_GAUGE_FULL_PCT
    quota.sub_model = corrected_sub_model

    from scripts import next_round  # noqa: E402, PLC0415

    return int(next_round.main())


if __name__ == "__main__":
    raise SystemExit(main())
