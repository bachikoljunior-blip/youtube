"""**1日N本の与件が変わったら、床の間に合う／間に合わないが反転すること。**

## なぜ要るか（2026-08-31・最適化の回）

与件が足されました —— **公開は1日1本・作り置きはしない。**
処置は `batch_build.cap_by_density()`（＝**これから作る本**の置き方）に入りますが、
`scripts/queue_lag.py` の床の節は `batch_build.live_plan()`（帯 10枠/日）で
数えていたので、**上限が 10 から 1 に変わっても印字が1文字も動きませんでした。**

実測（足した回・`request_form` あと 96本・締切 2026-09-29）:

    上限 13本/日 → 最後の1本 2026-09-09  **間に合います**（余り 20日）
    上限  1本/日 → 最後の1本 2026-12-23  **85日 越えます**

**この検査が見ているのは、その反転が起きること**だけです。日付や日数は
毎日 動くので**写しません**（写すと、本が1本 増えるたびに赤くなります）。

**覆る条件**: `rate_lines()` が `publish_cap()` 以外から上限を取るようになったら、
差し替えが効かなくなるので、ここは赤くなります。**そのとき直すのは本体のほう**
—— 上限を2か所から読む形に戻っています。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.queue_lag as ql  # noqa: E402


def _lines(cap: int, monkeypatch) -> list[str]:
    monkeypatch.setattr(ql, "publish_cap", lambda: cap)
    rows = ql.scheduled()
    short = ql.answering(rows)[2]
    return ql.rate_lines(short, rows)


def test_上限を写していない(monkeypatch):
    """**`rate_lines()` は上限を `publish_cap()` からしか取らないこと。**"""
    out = "\n".join(_lines(7, monkeypatch))
    assert "**7本/日**" in out, out[:400]


def test_上限が1本になると床の答えが反転する(monkeypatch):
    """床が足りているとき、この検査は**何も主張しません**（空振り）。"""
    wide = "\n".join(_lines(13, monkeypatch))
    if "床の足りない群はありません" in wide or "どの前提も期限までに埋まります" not in wide:
        return                      # 足りない群が無い日は、比べるものがありません
    tight = "\n".join(_lines(1, monkeypatch))
    assert "越えます" in tight, tight[:600]
    assert "間に合わない前提" in tight, tight[:600]


def test_上限が読めない回は答えを出さない(monkeypatch):
    """**既定へ落として印字しないこと** —— 10倍 楽観な日付が出ます。"""
    monkeypatch.setattr(ql, "publish_cap", lambda: 0)
    out = "\n".join(ql.rate_lines([], None))
    assert "答えを出しません" in out, out
    assert "越えます" not in out


def test_作り置きが上限を超えていれば鳴る(monkeypatch):
    """予約に在る本は `cap_by_density()` を通っていないので、別に数えること。"""
    out = "\n".join(_lines(1, monkeypatch))
    rows = ql.scheduled()
    if not rows:
        return
    assert "作り置きが、この上限を超えています" in out, out[:600]
