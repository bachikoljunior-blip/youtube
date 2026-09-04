"""**形は「差」で選ばない** —— 分母が自分の実測なので、振るわない形ほど強く推されます。

## 実測（2026-09-04 16:xx・最適化の回）

`theory_gap()` の `best` は `argmax(外の p90 ÷ 自分の中央値)` でした。**分母が自分の実測**なので、
その形で 0 に近いほど比が大きくなり、**いちばん下手な形が必ず選ばれます。**

2026-09-03 02:03、その比（`外 p90 624,772回 ÷ 自分の長尺 中央値 1回 ＝ ×624,772`）が
ショートの決めを上書きし、`data/daily_pick.jsonl` は以後 長尺のまま。
規則は 1本/日（`src/house_rule.py`）なので、**新しく出る本の 100% が長尺**になりました。

  形べつの実測（`aged_views()`）  齢24h ショート 中央 153（n=220）／ 長尺 中央 1（n=36）
  そのあいだの `data/eta.jsonl`   再生/日(7d) 6,299（08-25）→ 943（09-04）＝ **-85%**

差は「試す理由」としては正しい。**枠を全部 取ることが正しくない。**
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src import daily_pick as dp

NOW = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)


def _ledger(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)

    def top(form: str, views: list[int]) -> list[dict]:
        return [{"id": f"{form}{i}", "form": form, "views": v,
                 "secs": 60 if form == "short" else 1500,
                 "published": (NOW - timedelta(days=100)).isoformat().replace("+00:00", "Z")}
                for i, v in enumerate(views)]

    row = {"at": NOW.isoformat(), "queries": ["q"], "form": "any", "source": "free",
           "summary": {"short": {"n": 3, "max": 20000, "p90": 10000, "median": 8000,
                                 "channels": 3},
                       "long": {"n": 3, "max": 900000, "p90": 600000, "median": 500000,
                                "channels": 3}},
           "top": top("short", [6000, 8000, 10000]) + top("long", [400000, 500000, 600000])}
    p = tmp_path / "niche_ceiling.jsonl"
    p.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


#: 実物と同じ向き: ショートは出ている（1,049回）、長尺は出ていない（1回）。
CMP = {"rule": {"ショート": {"median": 1049}, "長尺": {"median": 1}},
       "all": {"ショート": {"median": 1049}, "長尺": {"median": 1}}}


def test_差がいちばん大きい形は長尺のまま(tmp_path) -> None:
    """**差そのものは消しません。** 消すのは「差で選ぶ」ほうだけ。"""
    g = dp.theory_gap(CMP, ledger=_ledger(tmp_path), now=NOW)
    assert g["gap_best"] == "長尺"                     # 600,000 ÷ 1 = ×600,000
    assert g["長尺"]["x_p90"] > g["ショート"]["x_p90"]


def test_bestは実測の見込みで選ぶ(tmp_path) -> None:
    """**ここが 2026-09-03 02:03 に長尺を選んだ場所です。**"""
    g = dp.theory_gap(CMP, ledger=_ledger(tmp_path), now=NOW)
    assert g["ev_best"] == "ショート"
    assert g["best"] == "ショート"
    assert g["best"] != g["gap_best"]


def test_振るわないほど推されるという向きが消えている(tmp_path) -> None:
    """長尺をさらに落としても、`best` は動かない（前は もっと強く推されました）。"""
    led = _ledger(tmp_path)
    worse = {"rule": {"ショート": {"median": 1049}, "長尺": {"median": 0}},
             "all": {"ショート": {"median": 1049}, "長尺": {"median": 0}}}
    g0 = dp.theory_gap(CMP, ledger=led, now=NOW)
    g1 = dp.theory_gap(worse, ledger=led, now=NOW)
    assert g1["長尺"]["x_p90"] >= g0["長尺"]["x_p90"]   # 差は大きくなる（＝ 前はここで勝った）
    assert g1["best"] == "ショート"                     # **それでも選ばれない**


def test_画面が差と見込みを分けて言う(tmp_path) -> None:
    out = "\n".join(dp.theory_lines(CMP, ledger=_ledger(tmp_path), now=NOW, need=None))
    assert "「差」であって「見込み」ではありません" in out
    assert "1本の枠の見込み" in out
    assert "がいちばん高い形は ショート" in out


def test_試す形が取った枠を日で数える(tmp_path) -> None:
    """**行数ではなく日で数えること** —— 焼き直した回数まで枠に見えます。"""
    picks = tmp_path / "daily_pick.jsonl"
    rows = [
        {"at": "2026-09-02T19:24", "for_day": "2026-09-03", "form": "ショート", "video_id": "s1"},
        {"at": "2026-09-03T02:03", "for_day": "2026-09-04", "form": "長尺", "video_id": "L1"},
        {"at": "2026-09-03T04:38", "for_day": "2026-09-04", "form": "長尺", "video_id": "L2"},
        {"at": "2026-09-03T13:16", "for_day": "2026-09-04", "form": "長尺", "video_id": "L2"},
        {"at": "2026-09-04T14:42", "for_day": "2026-09-05", "form": "長尺", "video_id": "L3"},
    ]
    picks.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                     encoding="utf-8")
    views = tmp_path / "views.jsonl"
    views.write_text("", encoding="utf-8")
    out = "\n".join(dp.explore_budget("ショート", "長尺", picks_path=picks, views_path=views))
    assert "枠を 2日ぶん 取っています" in out            # 決めは 4行 でも、枠は 2日
    assert "0本／" in out
    assert "まだ 1本も 48h の観測が出ていません" in out


def test_既定と試す形が同じなら1行も出さない() -> None:
    assert dp.explore_budget("長尺", "長尺") == []
    assert dp.explore_budget(None, "長尺") == []


def test_枠の目安を越えたら名指しする(tmp_path) -> None:
    picks = tmp_path / "daily_pick.jsonl"
    rows = [{"at": f"2026-09-0{d}T00:00", "for_day": f"2026-09-0{d}", "form": "長尺",
             "video_id": f"L{d}"} for d in range(1, 6)]
    picks.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                     encoding="utf-8")
    views = tmp_path / "views.jsonl"
    views.write_text(json.dumps({"id": "L1", "hours": 72, "views": 3}) + "\n", encoding="utf-8")
    out = "\n".join(dp.explore_budget("ショート", "長尺", picks_path=picks, views_path=views))
    assert "枠を 5日ぶん 取っています" in out
    assert f"枠の目安 {dp.EXPLORE_SLOT_CAP}日 を越えています" in out
    assert "1本／5本" in out                            # 1本だけ 48h に届いた
