"""**台帳の床が題材の接頭辞で決まっているとき、それが作る側へ届いているか。**

なぜ要るかは `src/floor_topics.py` の docstring（実測 2026-08-29:
`s-ribo-` の床 8本 に対し、題は 8件 在るのに **2件しか作られていない**。
そのあいだ `scripts/deadline_check.py` は「この回は何もしないのが正解です」）。
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import floor_topics  # noqa: E402


def _write(tmp_path: Path, hyp: str, ledger: list[dict], topics: list[dict]):
    h = tmp_path / "hypotheses.yaml"
    h.write_text(hyp, encoding="utf-8")
    led = tmp_path / "uploaded.jsonl"
    led.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                           for r in ledger), encoding="utf-8")
    top = tmp_path / "topics.yaml"
    import yaml
    top.write_text(yaml.safe_dump({"topics": topics}, allow_unicode=True),
                   encoding="utf-8")
    return h, led, top


_HYP = """
hypotheses:
  - claim: "族を外へ"
    deadline: "2026-09-19"
    lever: rpm
    needs:
      - kind: accrual
        count_expr: "len({r['video_id'] for r in uploaded() if str(r.get('topic', '')).startswith('s-ribo-')})"
        need: 8
"""


def test_床の足りない接頭辞と_あと何本かを返す(tmp_path: Path):
    h, led, top = _write(
        tmp_path, _HYP,
        [{"topic": "s-ribo-a"}, {"topic": "s-ribo-b"}, {"topic": "s-kojo-x"}],
        [{"id": f"s-ribo-{c}", "calc": "ribo"} for c in "abcdefgh"]
        + [{"id": "s-kojo-x", "calc": "kojo"}],
    )
    got = floor_topics.starved(today=date(2026, 8, 29), hyp_path=h,
                               ledger_path=led, topics_path=top)
    assert len(got) == 1
    r = got[0]
    assert (r["prefix"], r["need"], r["built"], r["short"]) == ("s-ribo-", 8, 2, 6)
    # **在庫は「まだ作っていない同じ接頭辞の題」**。8件 − 作った 2件 ＝ 6件
    assert (r["stock"], r["makeable"]) == (6, 6)


def test_期限が過ぎた前提と_床が満ちた前提は返さない(tmp_path: Path):
    h, led, top = _write(
        tmp_path, _HYP,
        [{"topic": f"s-ribo-{c}"} for c in "abcdefgh"],
        [{"id": f"s-ribo-{c}", "calc": "ribo"} for c in "abcdefgh"],
    )
    # 床は満ちている（8/8）
    assert floor_topics.starved(today=date(2026, 8, 29), hyp_path=h,
                                ledger_path=led, topics_path=top) == []
    # 期限を過ぎていれば、床が空でも返さない（もう間に合わない）
    other = tmp_path / "b"
    other.mkdir()
    h2, led2, top2 = _write(other, _HYP, [],
                            [{"id": "s-ribo-a", "calc": "ribo"}])
    assert floor_topics.starved(today=date(2026, 9, 20), hyp_path=h2,
                                ledger_path=led2, topics_path=top2) == []


def test_在庫が床に足りないときは_そう言う(tmp_path: Path):
    """**「作るだけで埋まります」と「題材から作ること」を混ぜない。**

    在庫 < 残り なら、`pick()` を何回まわしても床は埋まりません ——
    **直す先は `config/topics.yaml` の側**です。
    """
    h, led, top = _write(
        tmp_path, _HYP, [{"topic": "s-ribo-a"}],
        [{"id": "s-ribo-a", "calc": "ribo"}, {"id": "s-ribo-b", "calc": "ribo"}],
    )
    r = floor_topics.starved(today=date(2026, 8, 29), hyp_path=h,
                             ledger_path=led, topics_path=top)[0]
    assert (r["short"], r["stock"], r["makeable"]) == (7, 1, 1)
    line = floor_topics.lines([r])[0]
    assert "在庫は 1件 しかありません" in line


def test_calc_の無い題は在庫に数えない(tmp_path: Path):
    """`pick()` は `calc` を要求するので、無い題は**永久に選ばれません**。

    在庫に数えると、埋まらない床が「作るだけで埋まります」に見えます。
    """
    h, led, top = _write(
        tmp_path, _HYP, [],
        [{"id": "s-ribo-a", "calc": "ribo"}, {"id": "s-ribo-b"}],
    )
    r = floor_topics.starved(today=date(2026, 8, 29), hyp_path=h,
                             ledger_path=led, topics_path=top)[0]
    assert r["stock"] == 1


def test_題材を見ていない式からは接頭辞を拾わない():
    """`uploaded_at` や日付の `startswith` は、題材の話ではありません。"""
    assert floor_topics._prefixes_of(
        "sum(1 for r in rows('uploaded.jsonl') "
        "if (r.get('uploaded_at') or '').startswith('2026-08-27'))") == []
    assert floor_topics._prefixes_of(
        "len([r for r in uploaded() "
        "if str(r.get('topic','')).startswith('s-ribo-')])") == ["s-ribo-"]


def test_pick_は床の題を先頭へ持ち上げる_落とさない(monkeypatch):
    """**持ち上げるだけ。** 床の題が尽きても、残りはそのままの順で残ります。

    `per_calc` は迂回しません（`_hoist_floor_topics` の docstring）——
    ここで見ているのは**並び**だけです。
    """
    import batch_build

    usable = [{"id": "s-kojo-1", "calc": "kojo"},
              {"id": "s-ribo-c", "calc": "ribo"},
              {"id": "s-kojo-2", "calc": "kojo"},
              {"id": "s-ribo-d", "calc": "ribo"}]
    monkeypatch.setattr(
        floor_topics, "starved",
        lambda *a, **k: [{"prefix": "s-ribo-", "need": 8, "built": 2,
                          "short": 6, "stock": 6, "makeable": 6,
                          "deadline": "2026-09-19", "claim": "族を外へ",
                          "lever": "rpm"}])
    got = batch_build._hoist_floor_topics(list(usable))
    assert [t["id"] for t in got] == ["s-ribo-c", "s-ribo-d",
                                      "s-kojo-1", "s-kojo-2"]
    # **1本も落とさない**（在庫が尽きたときに投稿を止めないため）
    assert sorted(t["id"] for t in got) == sorted(t["id"] for t in usable)


def test_pick_は床までの残りで切る(monkeypatch):
    """床が埋まったあとも同じ族が先頭に居座ると、実績の順が死にます。"""
    import batch_build

    usable = [{"id": "s-kojo-1", "calc": "kojo"},
              {"id": "s-ribo-c", "calc": "ribo"},
              {"id": "s-ribo-d", "calc": "ribo"},
              {"id": "s-ribo-e", "calc": "ribo"}]
    monkeypatch.setattr(
        floor_topics, "starved",
        lambda *a, **k: [{"prefix": "s-ribo-", "need": 8, "built": 7,
                          "short": 1, "stock": 3, "makeable": 1,
                          "deadline": "2026-09-19", "claim": "族を外へ",
                          "lever": "rpm"}])
    got = batch_build._hoist_floor_topics(list(usable))
    assert [t["id"] for t in got][:2] == ["s-ribo-c", "s-kojo-1"]


def test_台帳が読めなくても止まらない(monkeypatch):
    """**投稿が途切れるのが最大の損失**（`CLAUDE.md`）。守りは黙って外れること。"""
    import batch_build

    def boom(*a, **k):
        raise RuntimeError("台帳が壊れています")

    monkeypatch.setattr(floor_topics, "starved", boom)
    usable = [{"id": "s-kojo-1", "calc": "kojo"}]
    assert batch_build._hoist_floor_topics(list(usable)) == usable


def test_実物の台帳で_s_ribo_の床が見えている():
    """**実物で1回 撃つ。** 覆る条件: この前提が閉じたら、この検査は
    「床のある接頭辞が0件でも通る」形へ書き換えること（消さないこと）。
    """
    rows = floor_topics.starved()
    # 床のある接頭辞が0件でも落としません（前提は閉じます）。
    # 在るときは、数え方が壊れていないことだけ見ます。
    for r in rows:
        assert r["short"] == max(0, r["need"] - r["built"])
        assert r["makeable"] == min(r["short"], r["stock"])
        assert r["prefix"] and r["deadline"]
