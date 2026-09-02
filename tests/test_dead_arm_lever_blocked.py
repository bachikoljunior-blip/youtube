"""**覆らない死に方の腕は、`--ship --lever` で記録できないこと。**（2026-09-02・最適化の回）

`src/levers.lever_notes()` は 2026-08-24 からこの2つを**叱って**いました。
その docstring は「**どちらも門ではありません**」と言っており、
**一般の `cap <= DEAD_CAP` については、その判断はいまも正しい**
（前提が未判定なら覆るため）。ここが門にするのは**覆らない2つだけ**です。

**なぜ門にしたか —— 註が効いていないことの実測**（`data/runs.jsonl` の ship 308件・
2026-09-02 12:4x にこの回が撃った数）::

    density  を宣言した ship            76件
      うち 規則が乗った 08/31 以降       **12件**（moves 0 が 9・**-1 が 3**）
      そのうち kind=verdict             ** 4件**  ← **軌跡を動かす唯一の通貨**
    sub_rate を宣言した ship            ** 8件**（moves 0 が 7・**-4 が 1**）

**20件 通り、うち 4件 は「この腕で到達日が早まる」と宣言**しています。
`density` はオーナーが固定した 1日1本（`src/house_rule.py`・**覆る条件なし**）、
`sub_rate` は `×10^9` まで引いても 0日（オーナー規則2）。**どちらも動きません。**

**覆る条件**: オーナーが 1日1本 を外せば `density` は自動で外れます
（`arm_state` が `RULE_DEAD` を名乗らなくなるだけで、この file は変えなくてよい）。
`dead_at_inf` は `eta.py` が毎回 測り直します。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import levers  # noqa: E402

RULE_STATE = {
    "caps": {"density": 1.0, "per_video": 4.35},
    "dead_why": {"density": levers.RULE_DEAD + "（**オーナーが固定した 1日1本**）"},
    "hint": "per_video",
    "binding": "再生数が天井に当たっている",
}
INF_STATE = {
    "caps": {"sub_rate": 6.62, "per_video": 4.35},
    "dead_at_inf": ("sub_rate",),
    "hint": "per_video",
    "binding": "再生数が天井に当たっている",
}


def test_rule_dead_arm_is_refused():
    """規則で死んだ腕（`density`）は断る。"""
    out = levers.blocked("density", RULE_STATE)
    assert out, "規則で死んだ腕が通っています"
    assert "断りました" in out[0]


def test_dead_at_infinity_arm_is_refused():
    """無限大でも 0日 の腕（`sub_rate`）は断る。"""
    out = levers.blocked("sub_rate", INF_STATE)
    assert out, "無限大でも 0日 の腕が通っています"


def test_refusal_names_a_way_through():
    """**仕事を捨てさせないこと。** 断る文面は、選び直せる腕を必ず名指しする。

    これが無いと、断られた回は「では何を書けばいいのか」で止まります ——
    そのとき次に来るのは、**黙って腕を外す**か、**嘘の腕を書く**かのどちらかです。
    """
    for state, lever in ((RULE_STATE, "density"), (INF_STATE, "sub_rate")):
        text = "\n".join(levers.blocked(lever, state))
        assert "--lever none" in text
        assert "--lever per_video" in text, "名指しされている腕が文面に出ていません"
        assert "捨てろとは言っていません" in text


def test_live_arms_and_plain_cap_ceiling_still_pass():
    """**一般の `cap <= DEAD_CAP` は断らないこと**（`lever_notes` の判断を残す）。

    生きた腕はもちろん、**天井 ×1.00 でも「規則」でなければ通します** ——
    観測の天井は測り直せば動くからです（`arm_state` の註）。
    """
    assert levers.blocked("per_video", RULE_STATE) == []
    assert levers.blocked("none", RULE_STATE) == []
    assert levers.blocked(None, RULE_STATE) == []
    observed = {"caps": {"density": 1.0}, "dead_why": {"density": "天井"}}
    assert levers.blocked("density", observed) == [], \
        "観測の天井まで断ると、測り直して覆る腕を永久に締め出します"


def test_unreadable_state_blocks_nothing():
    """**「読めない」と「死んだ腕は無い」は別**（`arm_state` の約束）。"""
    assert levers.blocked("density", {}) == []
    assert levers.blocked("sub_rate", {}) == []


def test_ship_refuses_and_writes_nothing(tmp_path, monkeypatch):
    """`--ship` は、断った回に**1行も書かないこと**。"""
    import scripts.run_marker as rm

    log = tmp_path / "runs.jsonl"
    monkeypatch.setattr(rm, "LOG", log, raising=False)
    monkeypatch.setattr(rm.levers, "latest_arm_state",
                        lambda _p: dict(RULE_STATE), raising=False)
    rc = rm.ship("fix: 暦を詰めた", lever="density", moves=-1, reflect=False)
    assert rc != 0, "断られた回が成功を返しています"
    assert not log.exists() or log.read_text(encoding="utf-8").strip() == "", \
        "断った回が台帳に行を残しています"


def test_density_refusal_answers_the_floor_argument():
    """**同じ日に実際に出された反論に、断り文が答えていること。**（commit a0538dcd）

    別の回が `--lever density` で ship し、日誌にこう書きました ——
    「鳴っているのは『規則より上へ出せ』の話で、この回がやったのは
    **規則に届いていない実物（0.05本/日）を規則まで戻す手**だ」。

    **その反論は正しい。腕の名前としては正しくありません** ——
    `drift.dead_arm_report` は `data/runs.jsonl` の `lever:` しか数えず、
    **日誌の註は台帳の行を数え直しません。** だから断り文が行き先を示します。
    """
    text = "\n".join(levers.blocked("density", RULE_STATE))
    assert "床に戻す手" in text, "実際に出された反論に、断り文が答えていません"
    assert "at_rule_mean" in text, "行き先（規則日を増やす手）が名指しされていません"
    assert "註では数え直りません" in text
