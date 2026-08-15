"""`usage` は**後から片方向に入る**。その前提で計器が壊れないことを固定する。

**なぜ要るか（2026-08-16）。** 「`usage` が入る条件」は**9回の申し送りに載り続け**、
そのたび「42分説」として運ばれていました。159点で測ったら外れです
（詳しくは `scripts/quota.py` の docstring）。実測で分かったのは**条件ではなく形**で、

    2回以上見た42セッション → **「無 → 有」11件・「有 → 無」0件**

つまり `usage` は**片方向**で、**「入っていない」は「使っていない」ではありません。**
（**ただの遅れでもありません** —— 4〜5回・13時間見続けても入らない子が多数います。
**規則そのものは不明のままで、それでよいと決めました。**）

答えそのものは行動を変えないので、これ以上測りません。**代わりに、
遅れが害にならない理由のほうを機械に持たせます。** 壊れ方は2つあり、
どちらも**静かに**壊れます（数字は出るが、間隔の判断だけが狂う）。

  1. **足し算してしまう** —— `usage` はそのセッションの**通算値**なので、
     同じセッションを何度も見て足すと消費量が水増しされ、**間隔を無用に延ばす**
  2. **遅れて来たぶんを落とす** —— 先に見た「無」で後の「有」を上書きすると、
     消費量が過小になり、**間隔を詰めすぎて枠を閉じる**（8/12〜8/14 の58時間）
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402

UTC = timezone.utc
START = datetime(2026, 8, 15, 22, 0, tzinfo=UTC)


def _row(sid: str, seen: str, born: str, tokens: dict | None) -> dict:
    row = {
        "seen_at": f"2026-08-15T{seen}:00+00:00",
        "born_at": f"2026-08-15T{born}:00+00:00",
        "session_id": sid,
    }
    if tokens is not None:
        row["tokens"] = tokens
    return row


TOK = {"input_tokens": 10, "output_tokens": 1000,
       "cache_read_tokens": 5000, "cache_write_tokens": 100}
TOK_LATER = {"input_tokens": 20, "output_tokens": 2000,
             "cache_read_tokens": 9000, "cache_write_tokens": 200}


def test_同じセッションを何度見ても足さない():
    """実物では 42セッションのうち1件が **10行**まで積まれています。"""
    rows = [
        _row("a", "22:10", "22:05", TOK),
        _row("a", "22:40", "22:05", TOK),
        _row("a", "23:10", "22:05", TOK),
    ]
    out, total, blind, spanning = quota._tokens_upto(rows, START, "2026-08-16T00:00:00+00:00")
    assert out == 1000, "同じセッションの通算値を足している（消費量が水増しされる）"
    assert total == sum(TOK.values())
    assert spanning == 0


def test_遅れて増えたぶんは大きいほうを採る():
    rows = [
        _row("a", "22:10", "22:05", TOK),
        _row("a", "22:50", "22:05", TOK_LATER),
    ]
    out, _, _, _ = quota._tokens_upto(rows, START, "2026-08-16T00:00:00+00:00")
    assert out == 2000, "後から増えたぶんが落ちている"


def test_まだ見えない行は0ではなく別に数える():
    """**0 と『まだ見えない』は違う。** 0 と読むと消費量が過小になり、間隔を詰めすぎる。"""
    rows = [
        _row("a", "22:10", "22:05", None),
        _row("b", "22:20", "22:05", TOK),
    ]
    out, _, blind, _ = quota._tokens_upto(rows, START, "2026-08-16T00:00:00+00:00")
    assert out == 1000
    assert blind == 1, "見えなかった行を数え落としている（過小であることを表に出せない）"


def test_無が有を上書きしない():
    """`_merge` は情報が増える向きにしか動かない。**片方向であることの機械側の担保。**"""
    old = _row("a", "22:10", "22:05", TOK)
    new = _row("a", "22:10", "22:05", None)
    assert quota._merge(old, new).get("tokens") == TOK, \
        "遅れて来た『無』が、先に見えていた消費量を消している"


def test_有は無を上書きする():
    old = _row("a", "22:10", "22:05", None)
    new = _row("a", "22:10", "22:05", TOK)
    assert quota._merge(old, new).get("tokens") == TOK


def test_枠より前に生まれたセッションは除いて呼び出し側に返す():
    """親は 8/3 から生きていて8,400万トークンを抱えています（枠が桁で狂う）。"""
    rows = [
        _row("oya", "22:30", "20:00", TOK_LATER),
        _row("ko", "22:30", "22:05", TOK),
    ]
    out, _, _, spanning = quota._tokens_upto(rows, START, "2026-08-16T00:00:00+00:00")
    assert out == 1000, "枠をまたぐセッションを枠の中に数えている"
    assert spanning == 1, "除いたことを呼び出し側に返していない（表に出せない）"


def test_実データで有から無へ戻った行が無いこと():
    """**この形が壊れたら、上の3件の前提ごと崩れます。** 実物で見張ること。"""
    import json

    path = ROOT / "data" / "quota.jsonl"
    if not path.exists():        # まっさらなコンテナでは無いことがある
        return
    seen: dict[str, int] = {}
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for row in sorted(rows, key=lambda r: r.get("seen_at", "")):
        sid = row.get("session_id")
        tok = row.get("tokens")
        total = sum(tok.values()) if tok else 0
        if sid in seen and total and total < seen[sid]:
            raise AssertionError(
                f"{sid} の消費量が減っています（{seen[sid]} → {total}）。"
                "**片方向という前提が外れました。**`quota.py` の docstring ごと測り直すこと"
            )
        seen[sid] = max(seen.get(sid, 0), total)
