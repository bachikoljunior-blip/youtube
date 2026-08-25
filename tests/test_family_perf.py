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


# --- 登録率を順番に掛ける（2026-08-16 に足した。**門は登録者なので**）---
#
# ここで守りたいのは4つで、どれも「入れた当日にすり抜けうる」形です:
#
#   1. **登録が1件も無いあいだは、倍率を掛けない**（信号が無いのに順番が動く）
#   2. **登録0の族が、順番から消えない**（探索を殺す向き）
#   3. **1人だけ入った族が、順番を独占しない**（n=1 で決まる向き）
#   4. **engaged と登録で順番が食い違うとき、登録の側が効く**（掛けていない向き）


def test_no_multiplier_while_no_subscriber_has_been_measured():
    """**登録0件のあいだは倍率を全部 1.0 に。** 信号が無いのに順番を動かさない。"""
    scan = _scan({"a": (2000, 1000, 0), "b": (2000, 200, 0)})
    rows = fp.families(scan, {"a": "good", "b": "bad"})
    assert fp.sub_baseline(rows) == 0.0
    assert set(fp.sub_multiplier_map(rows).values()) == {1.0}
    # 順番の値は engaged そのもの（掛ける前と同じ）
    assert fp.combined_map(rows) == fp.score_map(rows)


def test_zero_subscriber_family_is_not_erased():
    """**登録0は「悪い」ではなく「まだ出ていない」。** 下限で守る。"""
    scan = _scan({"a": (2000, 800, 4), "b": (8000, 3200, 0)})
    rows = fp.families(scan, {"a": "converts", "b": "never"})
    mult = fp.sub_multiplier_map(rows)
    assert mult["never"] == fp.SUB_MULT_MIN      # 0人でも 0 にはしない
    assert fp.combined_map(rows)["never"] > 0


def test_one_subscriber_on_a_tiny_family_is_capped():
    """**n=1 の跳ね上がりを、上限で止める。** 事象が数件しかないため。"""
    scan = _scan({"a": (40, 20, 1), "b": (20000, 8000, 1)})
    rows = fp.families(scan, {"a": "lucky", "b": "big"})
    assert fp.sub_multiplier_map(rows)["lucky"] == fp.SUB_MULT_MAX


def test_subscriber_rate_can_outrank_engaged():
    """**engaged と登録が食い違うとき、登録の側が順番を動かす。**

    これが 8/16 の実物の形です（`iryohi` は engaged 6位・登録3位）。
    掛けていなければ、この検査は落ちます。
    """
    scan = _scan({"a": (2000, 900, 0),     # engaged 45% ・登録0
                  "b": (2000, 600, 4)})    # engaged 30% ・登録4人
    rows = fp.families(scan, {"a": "showy", "b": "converts"})
    assert fp.score_map(rows)["showy"] > fp.score_map(rows)["converts"]
    score = fp.scorer(rows)
    assert score("converts") > score("showy")


def test_unknown_family_still_scores_at_the_engaged_mean():
    """未知の族の倍率は 1.0 ＝ **engaged の全体平均そのもの**（探索を殺さない）。"""
    scan = _scan({"a": (2000, 900, 3), "b": (2000, 600, 0)})
    rows = fp.families(scan, {"a": "converts", "b": "never"})
    score = fp.scorer(rows)
    assert abs(score("never-seen") - fp.baseline(rows)) < 1e-12
    assert score("never") < score("never-seen") < score("converts")
