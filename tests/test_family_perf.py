"""族べつの実績（`src/family_perf.py`）と、それが `pick` の順番に効くこと。

**故障注入を先に置いています。** ここで守りたいのは2つで、どちらも
「入れた当日にすり抜けた」形のものです:

1. **n=1 の族が、その1本だけで順番を決めない**（縮めるのが効いているか）
2. **測っていない族が、順番から消えない**（探索を殺していないか）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import family_perf as fp  # noqa: E402


def _scan(rows: dict[str, tuple[int, int, int]]) -> dict[str, dict]:
    return {vid: {"views": v, "engagedViews": e, "subscribersGained": s}
            for vid, (v, e, s) in rows.items()}


def test_families_groups_by_calc():
    scan = _scan({"a": (1000, 500, 1), "b": (1000, 300, 0), "c": (500, 100, 0)})
    vc = {"a": "nenkin", "b": "nenkin", "c": "kojo"}
    rows = {f.calc: f for f in fp.families(scan, vc)}
    assert rows["nenkin"].videos == 2
    assert rows["nenkin"].views == 2000
    assert rows["nenkin"].engaged == 800
    assert rows["nenkin"].subs == 1
    assert abs(rows["kojo"].raw_rate - 0.2) < 1e-9


def test_small_denominators_are_dropped():
    """再生が少ない本は率が壊れるので数えない（`status.py` と同じ線）。"""
    scan = _scan({"a": (10, 10, 0)})
    assert fp.families(scan, {"a": "nenkin"}) == []


def test_shrink_pulls_a_single_video_toward_the_mean():
    """**1本しか無い族が、その1本で順番を決めない。**

    生 100% の族でも、縮めた値は全体平均と生のあいだに入る。
    """
    scan = _scan({"a": (100, 100, 0), "b": (5000, 1500, 0)})
    vc = {"a": "lucky", "b": "big"}
    rows = fp.families(scan, vc)
    base = fp.baseline(rows)
    table = fp.score_map(rows)
    assert base < table["lucky"] < 1.0
    # 100再生では、全体平均からほとんど動かない（動いたら縮めが弱すぎる）
    assert table["lucky"] - base < 0.05


def test_unmeasured_family_scores_at_the_mean():
    """**測っていない族は「悪い」ではない。** 真ん中の順位から試される。"""
    scan = _scan({"a": (2000, 1000, 0), "b": (2000, 200, 0)})
    rows = fp.families(scan, {"a": "good", "b": "bad"})
    score = fp.scorer(rows)
    assert score("bad") < score("never-seen") < score("good")


def test_old_topics_still_map_to_a_calc():
    """台帳から消えた古いテーマを落とすと、いちばん実績のある本が消える。"""
    known = {"shitsugyo", "nenkin"}
    assert fp._calc_of_topic("shitsugyo-kyufu", {}, known) == "shitsugyo"
    assert fp._calc_of_topic("s-nenkin-3", {}, known) == "nenkin"
    assert fp._calc_of_topic("nenmatsu-chosei", {}, known) == ""


def test_report_points_at_starved_top_families():
    """実績が上位なのに未使用の節が0なら、そこに節を書けと言う。"""
    scan = _scan({"a": (2000, 1000, 0), "b": (2000, 200, 0)})
    rows = fp.families(scan, {"a": "good", "b": "bad"})
    text = "\n".join(fp.report_lines(rows, unused={"good": 0, "bad": 5}))
    assert "次に節を書くならここ" in text
    assert "good" in text.split("次に節を書くならここ")[1]


def test_pick_orders_by_measured_family(monkeypatch):
    """**実績が `pick` の順番に本当に効いているか**（掛け算の向き）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import batch_build

    pool = [
        {"id": "t-bad", "calc": "bad", "score": 1.0, "calc_sections": ["x"]},
        {"id": "t-good", "calc": "good", "score": 1.0, "calc_sections": ["y"]},
    ]
    monkeypatch.setattr(batch_build.config, "load_topics", lambda: {"topics": pool})
    monkeypatch.setattr(batch_build, "_posted_including_ledger", lambda: set())
    rows = fp.families(_scan({"a": (2000, 1000, 0), "b": (2000, 200, 0)}),
                       {"a": "good", "b": "bad"})
    monkeypatch.setattr(fp, "families", lambda *a, **k: rows)
    got = [t["id"] for t in batch_build.pick(2, [])]
    assert got == ["t-good", "t-bad"]


def test_pick_keeps_the_hand_written_score(monkeypatch):
    """**手書きの `score` を捨てない。** 実績は事前分布、`score` は狙い。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import batch_build

    pool = [
        {"id": "t-bad-2x", "calc": "bad", "score": 2.0, "calc_sections": ["x"]},
        {"id": "t-good-1x", "calc": "good", "score": 1.0, "calc_sections": ["y"]},
    ]
    monkeypatch.setattr(batch_build.config, "load_topics", lambda: {"topics": pool})
    monkeypatch.setattr(batch_build, "_posted_including_ledger", lambda: set())
    # **実物と同じ開き方にしてあります**（2026-08-16 の実測で、縮めたあとの
    # 上位と下位は 41.8% 対 31.0% ＝ 1.35倍）。実績だけで並べたい族の差より、
    # 手で 2.0 を付けた狙いのほうが強い、という向きをここで固定します。
    rows = fp.families(_scan({"a": (2000, 840, 0), "b": (2000, 620, 0)}),
                       {"a": "good", "b": "bad"})
    monkeypatch.setattr(fp, "families", lambda *a, **k: rows)
    got = [t["id"] for t in batch_build.pick(2, [])]
    assert got == ["t-bad-2x", "t-good-1x"]


def test_pick_survives_missing_history(monkeypatch):
    """実績が読めない回に `pick` が止まらないこと（投稿が途切れるほうが高い）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import batch_build

    pool = [{"id": "t-a", "calc": "a", "score": 1.0, "calc_sections": ["x"]}]
    monkeypatch.setattr(batch_build.config, "load_topics", lambda: {"topics": pool})
    monkeypatch.setattr(batch_build, "_posted_including_ledger", lambda: set())

    def boom(*a, **k):
        raise RuntimeError("scan.jsonl が読めない")

    monkeypatch.setattr(fp, "scorer", boom)
    assert [t["id"] for t in batch_build.pick(1, [])] == ["t-a"]
