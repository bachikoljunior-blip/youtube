"""**作り置きと、帯の外の本は、A/B の標本ではありません。**（2026-08-31 に足した）

## なぜ要るか —— 同じ実験を、2つの経路が別々に数えていた

実測 2026-08-31（この検査を足す前の `python scripts/ab_split.py`）:

    title_form  問い **49本** / 断定 **36本**  → **判定できます**（床 16本）
    hook_form   問い **73本** / 条件 **58本**  → **判定できます**

同じ日の `src/judgeable.py`（`config/hypotheses.yaml` の `watch` / `needs` が
読むほう）は、**同じ実験について「まだ足りない」**と言っていました。
**割れていたのは実験ではなく、数える側**です。差は2つ:

    1. **作り置き**（規則2・`src/house_rule.is_stockpile`）を標本に数えていた
       —— 未来の予約 **269本**（作り置き **293行**）。**1本も公開されません。**
    2. **帯の外の本**（`src/day_cap.live_ids` が 0再生 と言う本）を数えていた
       —— `judgeable.members()` は 2026-08-26 からこれを落としています。

**足りない標本は、そのまま『外れ』に化けます** —— `falsified_if` は
「上回らなければ外れ（同点も外れ）」で、`next_if_false` は腕ごと畳むからです。

絞ったあとの実測（同じ日）:

    title_form  問い 23本 / 断定 19本  → 判定できます
    hook_form   問い **11本** / 条件 18本  → **まだ判定しない**  ← 判定が引っくり返る

**しきい値（床）は1つも触っていません。** 直したのは分母のほうです。
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import ab_split, house_rule  # noqa: E402
from src.ab_split import Experiment, build_times, published, split_counts  # noqa: E402


def _exp(**kw) -> Experiment:
    base = dict(
        name="t",
        split=lambda tid: "問い" if tid.endswith("a") else "断定",
        treated="問い",
        control="断定",
        landed=datetime.fromisoformat("2026-08-19T16:50:00+09:00"),
        deadline=date(2026, 9, 12),
    )
    base.update(kw)
    return Experiment(**base)


def _write(tmp_path: Path, rows: list[dict]) -> tuple[Path, Path]:
    batch = tmp_path / "b.jsonl"
    batch.write_text("\n".join(
        json.dumps({"at": "2026-08-19T20:00:00+09:00",
                    "results": [{"topic": r["topic"], "video_id": r["video_id"], "error": ""}]})
        for r in rows), encoding="utf-8")
    ledger = tmp_path / "u.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return batch, ledger


def test_published_は作り置きに札を付けるが_落とさない(tmp_path):
    """**落とすのは数える側だけ。**

    `published()` は `judgeable._live_ids()` と `scripts/queue_lag.py` も読み、
    あちらは**上限の観測**（その日の何本目か）に使うので予約の実物が要ります。
    """
    rows = [
        {"topic": "old-a", "video_id": "v1", "at": "2026-09-20T00:00:00Z",
         "uploaded_at": "2026-08-20T00:00:00Z"},          # 規則より前に作った ＝ 作り置き
        {"topic": "new-a", "video_id": "v2", "at": "2026-09-20T01:00:00Z",
         "uploaded_at": "2026-09-01T00:00:00Z"},          # 規則の下で作った ＝ 供給
    ]
    _, ledger = _write(tmp_path, rows)
    got = published(ledger, today="2026-08-31")
    assert len(got) == 2, "published() は1本も落とさないこと"
    by = {r["video_id"]: r for r in got}
    assert by["v1"]["stockpile"] is True
    assert by["v2"]["stockpile"] is False


def test_作り置きは標本に数えない(tmp_path):
    """**これがこの検査の本体です。**"""
    rows = [
        {"topic": f"s{i}-a", "video_id": f"s{i}", "at": f"2026-09-0{i + 1}T0{i}:00:00Z",
         "uploaded_at": "2026-08-20T00:00:00Z"} for i in range(3)
    ]
    b, ledger = _write(tmp_path, rows)
    led = published(ledger, today="2026-08-31")
    c = split_counts(_exp(), builds=build_times(b), ledger=led)
    assert c.treated_ready["問い"] == 0, "作り置きは1本も標本に入らないこと"


def test_規則の下で作った本は標本に入る(tmp_path):
    rows = [
        {"topic": "n-a", "video_id": "n1", "at": "2026-09-01T00:00:00Z",
         "uploaded_at": "2026-09-01T00:00:00Z"},
    ]
    b, ledger = _write(tmp_path, rows)
    led = published(ledger, today="2026-08-31")
    c = split_counts(_exp(), builds=build_times(b), ledger=led)
    assert c.treated_ready["問い"] == 1


def test_同じ分に並べた本は_帯に生きている1本しか数えない(tmp_path):
    """`src/day_cap.MIN_GAP_MIN`（30分）。**詰めた本は 0再生**という実測。

    仕込みが実物とかけ離れていると、**16本 置いた群が「16本」に見えます。**
    """
    rows = [
        {"topic": f"g{i}-a", "video_id": f"g{i}", "at": "2026-08-25T00:00:00Z",
         "uploaded_at": "2026-08-20T00:00:00Z"} for i in range(8)
    ]
    b, ledger = _write(tmp_path, rows)
    led = published(ledger, today="2026-08-31")
    c = split_counts(_exp(), builds=build_times(b), ledger=led)
    assert c.treated_ready["問い"] == 1, "同じ分に置いた8本のうち、生きるのは1本"


def test_帯の絞りが読めない回は絞らない(tmp_path, monkeypatch):
    """**観測していないものを、無いことにしない。**

    控えが読めないだけで群が空になると、`ready` が消えて期限が壊れます。
    """
    monkeypatch.setattr(ab_split, "live_video_ids", lambda rows=None: None)
    rows = [
        {"topic": f"h{i}-a", "video_id": f"h{i}", "at": "2026-08-25T00:00:00Z",
         "uploaded_at": "2026-08-20T00:00:00Z"} for i in range(8)
    ]
    b, ledger = _write(tmp_path, rows)
    led = published(ledger, today="2026-08-31")
    c = split_counts(_exp(), builds=build_times(b), ledger=led)
    assert c.treated_ready["問い"] == 8


def test_公開日の無い行は_帯の絞りより先に数える(tmp_path):
    """順を逆にすると `unknown_publish` が黙って 0 になります（1回 踏んだ）。"""
    rows = [{"topic": "x-a", "video_id": "vx", "at": None,
             "uploaded_at": "2026-08-20T00:00:00Z"}]
    b, ledger = _write(tmp_path, rows)
    led = published(ledger, today="2026-08-31")
    c = split_counts(_exp(), builds=build_times(b), ledger=led)
    assert c.unknown_publish == 1
    assert c.treated_ready["問い"] == 0


def test_judgeable_と_ab_split_が同じ絞りを読む():
    """**同じ絞りを2か所に書かないこと。** 割れると本数が2倍ちがいます。"""
    from src import judgeable
    assert judgeable._live_ids() == ab_split.live_video_ids()


def test_規則が外れたら作り置きの札も消える(monkeypatch):
    """`house_rule.STOCKPILE_IS_SUPPLY` を読んでいること。"""
    row = {"at": "2026-09-20T00:00:00Z", "uploaded_at": "2026-08-20T00:00:00Z"}
    assert house_rule.is_stockpile(row, today="2026-08-31") is True
    monkeypatch.setattr(house_rule, "STOCKPILE_IS_SUPPLY", True)
    assert house_rule.is_stockpile(row, today="2026-08-31") is False
