"""**`src/hold.py` —— 中身の側に「次の1本を当てる数字」が在るかを、毎周 数え直して画面に出す口が生きているか。**

## なぜ要るか（2026-09-03・最適化の回）

`improve` 15件 が全部「読み・題・段の説明」で、どれも再生を当てる数字を持っていなかった。
この検査が守るのは3つ:

    1. 維持率 × 日で割った残差の ρ が、同じ日に2本以上の本だけで数えられること
    2. 門の上なら「当てどころはこの区間」、門の下なら「中身に当てる数字が無い → 日の側へ」と画面が言うこと
    3. `daily_pick.lines()` の族の行の直後に、この塊が出ること（`run_marker --write` が読む所）
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src import daily_pick, hold


def _curve(p15: float, p50: float) -> list:
    out = []
    for i in range(1, 100):
        x = i / 100
        y = 1.2 if x < 0.15 else (p15 if x < 0.3 else (p50 if x < 0.7 else p50 * 0.6))
        out.append([x, y, 0.5])
    return out


def _rows(n_days: int = 6, per_day: int = 5, predictive: bool = True) -> tuple[list[dict], dict]:
    rows, cv = [], {}
    for d in range(n_days):
        day = date(2026, 8, 10 + d)
        for k in range(per_day):
            vid = f"V{d}{k}"
            views = 100 * (d + 1) + 40 * k
            rows.append({"video_id": vid, "form": "ショート", "pub": day, "views": views,
                         "family": "f", "topic": f"s-f-{d}{k}", "title": vid, "life": views,
                         "age_h": 60, "day_count": per_day})
            hold_v = (0.5 + 0.1 * k) if predictive else (0.5 + 0.1 * ((k * 7 + d) % 4))
            cv[vid] = _curve(hold_v + 0.3, hold_v)
    daily_pick._attach_residual(rows)
    return rows, cv


def test_predictor_uses_only_days_with_two_or_more_and_finds_the_signal() -> None:
    rows, cv = _rows(predictive=True)
    rows.append({"video_id": "LONE", "form": "ショート", "pub": date(2026, 9, 1), "views": 5,
                 "family": "f", "topic": "s-f-x", "title": "x", "life": 5, "age_h": 60, "day_count": 1})
    daily_pick._attach_residual(rows)
    cv["LONE"] = _curve(0.9, 0.9)
    pr = hold.predictor(rows, cv)
    assert pr[0.15]["n"] == 30                                   # LONE（1本の日）は入らない
    assert pr[0.15]["rho"] > pr[0.15]["gate"]


def test_lines_point_at_the_drop_window_when_significant_and_at_the_day_side_when_not(tmp_path: Path) -> None:
    q = tmp_path / "q"
    q.mkdir()
    (q / "NEXT.json").write_text(json.dumps({"narration": ["一", "二", "三", "四", "五"]}), encoding="utf-8")
    nxt = {"video_id": "NEXT", "topic": "s-f-next"}
    rows, cv = _rows(predictive=True)
    text = "\n".join(hold.lines(rows, nxt, cv=cv, queue=q))
    assert "**有意**" in text and "当てどころは、この区間" in text
    assert "`NEXT`（5段）" in text
    assert "×" in text and "日の中央値" in text
    rows, cv = _rows(predictive=False)
    text = "\n".join(hold.lines(rows, nxt, cv=cv, queue=q))
    assert "**雑音**" in text and "当てる数字がありません" in text and "日の側へ" in text


def test_daily_pick_lines_carry_the_hold_block(monkeypatch, tmp_path: Path) -> None:
    rows, cv = _rows(predictive=False)
    monkeypatch.setattr(hold, "curves", lambda path=None: cv)
    cmp = daily_pick.compare(rows=rows)
    text = "\n".join(daily_pick.lines(None, cmp=cmp, picks_path=tmp_path / "p.jsonl",
                                      topics=set(), cands=[], untried=[]))
    assert "何が次の1本を当てるか" in text
    assert text.index("族の順位が次の1本を当てるか") < text.index("何が次の1本を当てるか")


def test_refresh_adds_only_missing_recent_and_writes_the_cache(tmp_path: Path) -> None:
    rows, cv = _rows(n_days=2, per_day=2)
    del cv["V11"]
    calls = []

    def fake(vid):
        calls.append(vid)
        return [(0.5, 0.4, 0.5)]
    added = hold.refresh(rows, cv, path=tmp_path / "r.json", fetch=fake)
    assert added == 1 and calls == ["V11"]
    assert "V11" in json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
