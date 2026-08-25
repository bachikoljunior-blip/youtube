"""`pick` が「門が必ず止めるテーマ」を返さないこと（2026-08-17）。

3回続けて申し送りに出た形です —— `pick` が上位で返し、生成に数分かけ、
`upload_only.py` の `dupes.blocking()` が毎回止める。**作った1本は毎回捨て。**
手順は `--topics` で手で避けていましたが、**手で避けるものは避け忘れます。**

故障注入は両向き（落とす側と、落としてはいけない側）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import batch_build            # noqa: E402
from src import dupes                      # noqa: E402

POOL = [
    {"id": "s-menjo-x", "calc": "nenkinmenjo",
     "title_seed": "半額免除で残りを納めないと年1万200円を捨てる"},
    {"id": "s-menjo-posted", "calc": "nenkinmenjo",
     "title_seed": "国民年金 全額免除でも年1万200円増える"},
    {"id": "s-clean", "calc": "yukyu",
     "title_seed": "有給の出勤率8割を7回目に切ると生涯20日減る"},
]


def _ledger(topics=None):
    """投稿済みの1本（既に上げてある `s-menjo-posted`）だけを持つ控え。"""
    return [{"id": "vid00000001", "title": "国民年金 全額免除でも年1万200円増える",
             "topic": "s-menjo-posted", "calc": (topics or {}).get("s-menjo-posted", ""),
             "at": "2026-08-28T04:00:00Z", "scheduled": True}]


def test_金額が入れ子のテーマは作る前に外れる(monkeypatch):
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    kept = batch_build._drop_doomed([POOL[0], POOL[2]], POOL)
    assert [t["id"] for t in kept] == ["s-clean"]


def test_同じテーマIDも外れる(monkeypatch):
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    same = {"id": "s-menjo-posted", "calc": "nenkinmenjo", "title_seed": "まったく別の題"}
    assert batch_build._drop_doomed([same], POOL) == []


def test_控えのcalcは投稿済みぶんも渡さないと当たらない(monkeypatch):
    """**最初にここを間違えました。** 未投稿ぶんだけ渡すと `same-yen` が1組も当たりません。

    控えの行は「どの calc の本か」をテーマID経由でしか知らないためです。
    """
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    only_unposted = [POOL[0], POOL[2]]          # 投稿済みの s-menjo-posted を含めない
    assert [t["id"] for t in batch_build._drop_doomed(only_unposted, only_unposted)] \
        == ["s-menjo-x", "s-clean"]             # 素通りする（＝この引数の渡し方は誤り）


def test_重ならないテーマは落とさない(monkeypatch):
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    assert [t["id"] for t in batch_build._drop_doomed([POOL[2]], POOL)] == ["s-clean"]


def test_種が空でも落とさない(monkeypatch):
    """`title_seed` の無い古いテーマは、判断材料が無いので門に任せる。"""
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    bare = {"id": "s-bare", "calc": "nenkinmenjo"}
    assert [t["id"] for t in batch_build._drop_doomed([bare], POOL)] == ["s-bare"]
