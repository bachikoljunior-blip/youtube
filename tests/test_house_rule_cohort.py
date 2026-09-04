"""**すでに組み上がっている母集団を、「これから公開する本」と読まないこと。**

`src/house_rule.needs_beyond_rule()` は要件の本文の `N本` を **全部
「これから 1日1本 で公開する本」**と読んでいました。ところが台帳には、
**もう組み上がっている母集団**を名指しする要件があります:

    「**掃いた 36本**（`data/sub_ask_sweep.jsonl`・2026-09-04 に説明欄の
      先頭だけを変えた本）の、掃いた後 14日 の合計再生が 3,000」

その 36本 は **09/04 に実際に掃き終わっている既存の本**（帳面に 39件）で、
**新しく1本も公開しなくても揃っています。** それを
「09/18 までに規則が許すのは 14本 → 22日 足りません」と読んでいました。

**実測 2026-09-04 12:xx: `scripts/deadline_check.py` の
「規則の下では期日までに満ちない要件」はこの1件だけで、その1件が誤報でした。**
その節は「**ここが詰まると到達日が止まります**」と書いてあるので、
誤報は「毎周 到達日が止まって見える」ということです（`lever: sub_rate`）。

## この検査が押さえているのは、直した所より**黙らせないほう**です

`cohort_done()` の門は2つで、どちらも**警報を残す側**へ倒してあります:

  (1) `needs[]` が `data_file:` で名乗っている帳面（＝ **測る道具**）は数えない
  (2) `data_file:` を名乗っていない要件は、そもそも数えない

**(1) が無いと本物の警報が消えます** —— 台帳で本数と帳面の両方を書いている
`needs` 5件 のうち **4件は名指しの帳面が `data_file:` そのもの**で、
`data/views.jsonl`（全 257本 の観測）を母集団と読むと
「09/03〜09/23 に 1日1本 で連続公開した本 10本以上」が黙ります。
"""
from __future__ import annotations

import json

import pytest

from src import house_rule


#: **鳴る本数を、規則から作ること**（2026-09-05 に書き替えた）。
#:
#: ここは「36本」「40本」をべた書きし、`PUBLISH_PER_DAY = 1` の下で
#: 「規則では届かないから鳴る」を見ていました。規則が 10本/日 になると
#: 14日 で 140本・19日 で 190本 入るので、**どちらも届いてしまい**、
#: 「鳴る側」の検査2件が、鳴らない場面を測る形へ化けます（実際に赤くなりました）。
#: **覆る条件**: `needs_beyond_rule` が「日数 × 上限」以外の式になったとき。
_DAYS_SWEPT = 14                                        # 2026-09-04 → 2026-09-18
_NAMED_SWEPT = _DAYS_SWEPT * house_rule.PUBLISH_PER_DAY + 8
_DAYS_ROW = 19                                          # 2026-09-04 → 2026-09-23
_NAMED_ROW = _DAYS_ROW * house_rule.PUBLISH_PER_DAY + 8

_SWEPT = (f"**掃いた {_NAMED_SWEPT}本**（`data/sub_ask_sweep.jsonl`・2026-09-04 に"
          "説明欄の先頭だけを変えた本）の、掃いた後 14日 の合計再生が 3,000")


def _ledger(tmp_path, rel: str, ids) -> None:
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("w", encoding="utf-8") as fh:
        for i in ids:
            fh.write(json.dumps({"id": i, "where": "description_head"}) + "\n")


def test_掃きずみの母集団は足りているので鳴らない(tmp_path):
    _ledger(tmp_path, "data/sub_ask_sweep.jsonl",
            [f"v{i}" for i in range(_NAMED_SWEPT + 3)])
    hit = house_rule.needs_beyond_rule(
        _SWEPT, "2026-09-18", today="2026-09-04",
        data_file="data/shorts_subs.json", root=tmp_path,
        tracked=lambda rel: True)
    assert hit is None


def test_同じ要件は帳面が無ければ前のまま鳴る(tmp_path):
    # 帳面が枝に乗っていない（＝ 次の回のコンテナに無い）なら数えない。
    hit = house_rule.needs_beyond_rule(
        _SWEPT, "2026-09-18", today="2026-09-04",
        data_file="data/shorts_subs.json", root=tmp_path,
        tracked=lambda rel: False)
    assert hit is not None
    assert hit["named"] == _NAMED_SWEPT


def test_計器そのものを母集団と読まない(tmp_path):
    """**本物の警報を黙らせないこと。** `data_file:` と同じ帳面は数えない。"""
    _ledger(tmp_path, "data/views.jsonl", [f"v{i}" for i in range(257)])
    what = (f"09/03〜09/23 に **連続公開した本 {_NAMED_ROW}本以上**の、"
            "齢をそろえた読み（`data/views.jsonl`）")
    hit = house_rule.needs_beyond_rule(
        what, "2026-09-23", today="2026-09-04",
        data_file="data/views.jsonl", root=tmp_path,
        tracked=lambda rel: True)
    assert hit is not None, "計器 257本 を母集団と読んで黙ってはいけない"
    assert hit["named"] == _NAMED_ROW


def test_計器を名乗っていない要件は数えない(tmp_path):
    _ledger(tmp_path, "data/sub_ask_sweep.jsonl", [f"v{i}" for i in range(39)])
    assert house_rule.cohort_done(_SWEPT, data_file=None, root=tmp_path,
                                  tracked=lambda rel: True) is None


def test_cohort_done_は別々の件数を数える(tmp_path):
    # 同じ本が2行 在っても 1件。
    _ledger(tmp_path, "data/sub_ask_sweep.jsonl", ["a", "b", "b", "c"])
    assert house_rule.cohort_done(_SWEPT, data_file="data/shorts_subs.json",
                                  root=tmp_path, tracked=lambda rel: True) == 3


def test_実物の台帳で誤報が0件になっている():
    """**実物で撃つこと。** 直した先が実物で黙っていなければ意味がありません。"""
    yaml = pytest.importorskip("yaml")
    from src import config

    doc = yaml.safe_load((config.ROOT / "config" / "hypotheses.yaml")
                         .read_text(encoding="utf-8"))
    rows = doc.get("hypotheses") if isinstance(doc, dict) else doc
    bad = house_rule.unreachable_needs(rows)
    assert bad == [], f"規則の下で満ちない要件が残っています: {bad}"
