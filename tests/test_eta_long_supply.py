"""**段2 の合格点は、この機械が一度も出していない本数で割られていました。**（2026-08-24）

`scripts/eta.py` の段2（門2a・長尺4,000時間）は、合格点を

    長尺1本あたり再生 ＝ 要る視聴分 ÷ (**1日L本** × 門1までの日数 × 1再生の視聴分)

で解きます。この **L** が `max(LONG_PER_DAY_SCENARIOS)` ＝ **4本/日** の決め打ちでした。
合格点はLに反比例するので、出していない本数で割ると**そのぶん甘く**出ます。

実測（`data/batch_runs.jsonl`・直近7日）:

    08/19  1本 試して **0本**      08/22  6本 試して **1本**（5本が生成失敗）
    08/20  8本 試して  7本         08/23  0本
    08/21  0本                     08/24  5本 試して  4本
    → **15本 試して 8本 ＝ 1日 1.14本**（長尺の生成失敗率 **47%**）

    合格点  L=4本/日 → **47回/本**   ／   L=1.14本/日（実測）→ **163回/本**

**しかもこの数は、`plan()` が「この段取りを止めている、まだ測っていない入力は1つ」と
名指ししている当のもの**です ——「これを測れ」と言っている的が、3.5倍 ずれていました。

## 同じ形の失敗が、すでに1回あります

2026-08-20 16:0x・オーナー（原文）「**25は物理的に不可ならそれを予測に使うのはどうなの？**」
—— このとき直したのは `solve_gate1()`（段1）だけで、**段2 の側は決め打ちのまま**でした。
`_long_break_even()` は今日まで `a["days_subs_at"][PLAN_PUBLISH_PER_DAY]` ＝ **25本/日** を
読み続けています（いまは `day_cap` が両方を丸めるので同じ数ですが、上限が動いた日に黙って割れる）。

**この検査が守るのは、次の3つです。**

1. Lは実測から来ること（決め打ちに戻ったら落とす）
2. 数えるのは**成功した本**だけ（`count` は失敗も含む）
3. 門1 までの日数は、段1 が解いた日と**同じもの**を使えること
"""
from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_long_supply_mod",
                                               ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

TODAY = date(2026, 8, 24)


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "batch_runs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def _run(at: str, *, long: bool, ok: int, ng: int = 0) -> dict:
    res = [{"video_id": f"v{i}"} for i in range(ok)]
    res += [{"video_id": "", "error": "生成が失敗（exit 1）"} for _ in range(ng)]
    return {"at": at, "long": long, "count": ok + ng, "results": res}


# ======================================================================
# 1. 実測そのもの
# ======================================================================

def test_数えるのは成功した本だけ(tmp_path):
    """`count` は失敗も含みます。**そちらで数えると供給が水増しになります。**

    実測 08/22 は「6本 試して 1本」——`count` で数えると 6本 作れたことになり、
    段2 の合格点が 6倍 甘くなります。
    """
    p = _ledger(tmp_path, [_run("2026-08-22T10:00:00+09:00", long=True, ok=1, ng=5)])
    s = eta.long_supply_per_day(p, today=TODAY, window_days=7)
    assert s["built"] == 1, "失敗した本を作れたことにしています"
    assert s["attempts"] == 6
    assert s["fail_rate"] == pytest.approx(5 / 6)
    assert s["rate"] == pytest.approx(1 / 7)


def test_ショートの回は長尺の供給に数えない(tmp_path):
    p = _ledger(tmp_path, [
        _run("2026-08-22T10:00:00+09:00", long=False, ok=30),
        _run("2026-08-22T12:00:00+09:00", long=True, ok=2),
    ])
    s = eta.long_supply_per_day(p, today=TODAY, window_days=7)
    assert s["built"] == 2, "ショートが長尺の供給に混ざっています"


def test_今日は数えない(tmp_path):
    """**途中の日を混ぜると必ず下振れします。** 丸1日そろった日だけを数えること。"""
    p = _ledger(tmp_path, [_run("2026-08-24T10:00:00+09:00", long=True, ok=4)])
    s = eta.long_supply_per_day(p, today=TODAY, window_days=7)
    assert s["built"] == 0
    assert s["measured"] is False, "今日1日だけで『測った』と言っています"


def test_窓の外は数えない(tmp_path):
    p = _ledger(tmp_path, [_run("2026-07-01T10:00:00+09:00", long=True, ok=99)])
    assert eta.long_supply_per_day(p, today=TODAY, window_days=7)["built"] == 0


def test_1本も試していない窓は測っていない扱い(tmp_path):
    """**0本/日 を実測として通さないこと。**

    通すと段2 の合格点が無限大になり、画面には「届きません」だけが残ります ——
    **何を固定してそうなったかが消えます**（`CLAUDE.md`「裸の『届きません』を出さないこと」）。
    """
    s = eta.long_supply_per_day(tmp_path / "no-such-file.jsonl", today=TODAY)
    assert s["measured"] is False
    assert s["rate"] == 0.0


# ======================================================================
# 2. 合格点が、Lに反比例して動くこと
# ======================================================================

def _row(per_view: float = 2.8) -> dict:
    return {"label": "尺7分・維持40%", "min_per_view": per_view}


def test_合格点はLに反比例する():
    a = {"long_minutes_needed": 240_000.0}
    at1 = eta._gate2_bar(a, _row(), 1.0, 466.0)
    at4 = eta._gate2_bar(a, _row(), 4.0, 466.0)
    assert at4 == pytest.approx(at1 / 4)
    # **だから「出していない本数で割る」ことが、そのまま甘さになります。**
    assert at1 > at4


def test_供給が薄いほど合格点は高くなる():
    """実測 1.14本/日 の合格点が、決め打ち 4本/日 のそれより**高い**こと。

    ここが逆転したら、Lを実測から取っていません。
    """
    a = {"long_minutes_needed": 240_000.0}
    measured = eta._gate2_bar(a, _row(), 1.14, 466.0)
    hardcoded = eta._gate2_bar(a, _row(), float(max(eta.LONG_PER_DAY_SCENARIOS)), 466.0)
    assert measured > hardcoded * 3, "実測の供給で解き直した合格点が甘すぎます"


# ======================================================================
# 3. 門1 までの日数は、段1 と同じものを差せること
# ======================================================================

def test_門1までの日数は呼ぶ側から差せる():
    """段2 が `PLAN_PUBLISH_PER_DAY`（25本/日）を自前で読みに行かないこと。

    段1 は 2026-08-20 16:0x に `solve_gate1()` の実測へ移りました。
    **段2 だけが 25 を読み続けると、上限が動いた日に黙って割れます。**
    """
    a = {"long_minutes_needed": 240_000.0,
         "days_subs_at": {eta.PLAN_PUBLISH_PER_DAY: 100.0}}
    near = eta._long_break_even(a, days=100.0)
    far = eta._long_break_even(a, days=400.0)
    assert far[0]["views"][1] == pytest.approx(near[0]["views"][1] / 4), \
        "門1 までの日数が合格点に効いていません（差した日数を無視している）"


# ======================================================================
# 4. 段取りの側（配線が戻っていないこと）
# ======================================================================

def _measured(**over):
    base = dict(
        at="2026-08-19T02:30:00+00:00", subs_net=9, views_all=27_484,
        views_7d=11_002, views_28d=20_010, views_90d=22_241,
        subs_gained_28d=9, subs_gained_90d=11, long_hours_365=0.1,
        shorts_views_90d=22_222, median_views_per_video=1_092,
        videos_with_views_28d=20,
    )
    base.update(over)
    return base


def test_段2は実測の供給で立つ(monkeypatch, tmp_path):
    """**この検査が本体です。**

    決め打ちの 4本/日 に戻ったら、段2 の合格点（＝ `blocking` が「測れ」と
    名指ししている数）がそのぶん甘くなり、**落ちます。**
    """
    m = _measured()
    a = eta.analyse(m)

    def _thin(*_a, **_k):
        return {"rate": 1.0, "built": 7, "attempts": 15, "window_days": 7,
                "fail_rate": 8 / 15, "measured": True}

    def _plan_rate(*_a, **_k):
        return {"rate": 4.0, "built": 28, "attempts": 28, "window_days": 7,
                "fail_rate": 0.0, "measured": True}

    monkeypatch.setattr(eta, "long_supply_per_day", _thin)
    pl_thin = eta.plan(m, a, view_cap=25.0, mix={})
    monkeypatch.setattr(eta, "long_supply_per_day", _plan_rate)
    pl_full = eta.plan(m, a, view_cap=25.0, mix={})

    s_thin = next(s for s in pl_thin["stages"] if s["no"] == 2)
    s_full = next(s for s in pl_full["stages"] if s["no"] == 2)

    assert s_thin["long_per_day"] == pytest.approx(1.0)
    assert s_full["long_per_day"] == pytest.approx(4.0)
    # 供給が 1/4 なら、合格点は 4倍
    assert pl_thin["blocking"]["need"] != pl_full["blocking"]["need"], \
        "段2 の合格点が供給で動いていません（決め打ちに戻っています）"
    # **画面に出どころが並んでいること**（`CLAUDE.md`「何を固定したせいでそう
    #   出たのかを同じ行に並べる」）
    assert "計画は 4本/日" in s_thin["bar"], "合格点の脇に、計画と実測が並んでいません"
    assert "15本 試して" in s_thin["bar"]


def test_供給が測れない回は未検証の前提と断る(monkeypatch):
    m = _measured()
    a = eta.analyse(m)
    monkeypatch.setattr(eta, "long_supply_per_day",
                        lambda *_a, **_k: {"rate": 0.0, "built": 0, "attempts": 0,
                                           "window_days": 7, "fail_rate": None,
                                           "measured": False})
    pl = eta.plan(m, a, view_cap=25.0, mix={})
    s2 = next(s for s in pl["stages"] if s["no"] == 2)
    assert s2["long_per_day"] == pytest.approx(float(max(eta.LONG_PER_DAY_SCENARIOS)))
    assert "未検証の前提" in s2["bar"], "測れていないのに、実測のような顔で出しています"
