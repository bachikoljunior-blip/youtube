"""**締切のある道具に、撃つ側が居ること。**

## なぜこの検査があるか（2026-09-01）

実測 `grep -c pool_drain docs/trigger_main.md` → **0**。

`scripts/pool_drain.py` は 2026-08-31 から在り、`--apply` まで実装されていて、
**印字は締切まで出します**:

    [!] **規則1 が最初に破れるのは 2026-09-12**（11日後）。そこから **26日ぶん・238本 多い**
        外しきるのに **最低 2日ぶんの枠**が要ります。**1回では終わりません**

**それでも、撃つ側がどこにも書かれていませんでした。**

**同じ形を、この repo は 2026-08-30 に一度 踏んでいます** ——
`scripts/deadline_check.py` が「道具は 08-25 から在り、`--shrink` / `--extend` /
`--fit` まで実装されていて、**撃つ側がどこにも書かれていなかった**」。
そのとき溜まっていたのは **到達日がまるごと止まっていた 50日** でした
（`docs/trigger_main.md` §2.6）。

**この検査が守っているのは、`pool_drain` という名前ではありません** ——
「**締切のある仕事が、毎周の手順から名指しされていること**」です。
規則1（1日1本）は `CLAUDE.md` の固定の与件で、
**池化が終わらないと 09/12 から 26日ぶん・238本 それを破ります。**

**覆る条件**: 池化が終わって `pool_drain` が
「外すものはありません」しか言わなくなり、かつ**作り置きが二度と積まれない**
と言い切れるようになったとき。そのときは、この検査ごと外してよい
（**そのときは `scripts/pool_drain.py` も要りません**）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "trigger_main.md"
TOOL = ROOT / "scripts" / "pool_drain.py"


@pytest.mark.skipif(not TOOL.is_file(), reason="道具そのものが無い回")
def test_毎周の手順が_pool_drain_を名指ししている():
    """**道具が在るなら、撃つ側が手順に居ること。**"""
    body = DOC.read_text(encoding="utf-8")
    assert "pool_drain" in body, (
        "`scripts/pool_drain.py` は在るのに、`docs/trigger_main.md` が"
        "**1度も名指ししていません**。"
        " 2026-08-30 の `deadline_check` と同じ形です ——"
        " **道具が在って、撃つ側が居ない。**"
        " §2.6（予測の3行）に `python scripts/pool_drain.py` を入れること"
        "（**引数なしは API 0単位**なので、毎周 撃って構いません）"
    )


@pytest.mark.skipif(not TOOL.is_file(), reason="道具そのものが無い回")
def test_手順が_引数なしは_API_0単位_だと言っている():
    """**「毎周 撃ってよい」の根拠を、手順の側に置くこと。**

    ここが無いと、次に来た回は「API を使う道具だ」と読んで飛ばします
    （枠が尽きている回ほど飛ばすので、**いちばん要る回に読まれません**）。
    """
    body = DOC.read_text(encoding="utf-8")
    i = body.find("pool_drain")
    near = body[max(0, i - 400):i + 2500]
    assert "0単位" in near, (
        "`pool_drain` の近くに「**API 0単位**」が書かれていません。"
        " 引数なしが 0単位 だと言わないと、枠を気にする回が飛ばします"
    )


@pytest.mark.skipif(not TOOL.is_file(), reason="道具そのものが無い回")
def test_道具の側が_締切を印字する形のままであること():
    """**数だけ言う形へ戻さないこと。**

    `first_breach()` の docstring に、そう読めてしまった実測が残っています ——
    「09/01・09/02・09/04 は 1本/日 で規則どおりなので、
    **数だけ見ていると『進んでいる』と読めてしまう**」。
    """
    src = TOOL.read_text(encoding="utf-8")
    assert "def first_breach(" in src, (
        "`pool_drain.first_breach()` が消えています。"
        " **本数だけ言う形へ戻すと、後回しにしてよい仕事に見えます**"
    )
    assert "1回では終わりません" in src, (
        "「**1回では終わりません**」の印字が消えています。"
        " 1.4日ぶんの枠が要る仕事を、1回の回で終わると読ませないこと"
    )
