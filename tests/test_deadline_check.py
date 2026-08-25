"""`scripts/deadline_check.py` —— **期限が、データの来る日より前に置かれていないか。**

なぜこの検査が要るか（2026-08-25）。この道具が無かったあいだ、
**判定できないと最初から決まっている期限**が並んでいました:

    「量産テンプレート判定を避けられる」  期限 09/01・条件は「収益化の審査に落ちる」
                                          申請には登録者1,000人 → あと 999人
    「冒頭の stat は前提を先」            期限 09/05・処置群の16本目の公開は 09/01
                                          落ち着く7日 ＋ 遅れ3日 → 判定できるのは 09/11

**期限が来た日に「まだ分からない」と言うことが、置いた時点で決まっていました。**
`scripts/drift.py` が出す「直近20回の verdict 0件」は、その帰結です。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as J  # noqa: E402


def _open_items() -> list[dict]:
    items = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    return [h for h in items["hypotheses"] if not h.get("closed_on") and not h.get("verdict")]


def test_開いている前提には全部_needs_が書いてある():
    """**`needs:` の無い前提を足さないこと。**

    期限は、置いた回の勘では決められません。「その日までにデータが在るか」を
    書かずに置くと、**判定できない期限が黙って積みます**（実測: 16件中16件）。
    """
    missing = [h["claim"][:40] for h in _open_items() if not h.get("needs")]
    assert not missing, f"`needs:` が無い前提: {missing}"


def test_期限が_判定できる日より前に置かれていない():
    """**この検査が落ちたら、期限を延ばすこと。`falsified_if` は緩めないこと。**

    緩めると、外れない条件になります（このファイルが防ごうとしているのは
    「判定しないまま持ち越す」ほうで、「甘く判定する」ほうではありません）。
    """
    vs = J.check(_open_items())
    slips = [f"{v.claim[:32]} 期限 {v.deadline} < 判定できる日 {v.ready}"
             for v in vs if v.slips]
    assert not slips, "期限が早すぎる前提: " + " / ".join(slips)


def test_yaml_の_on_を_真偽値として読ませない():
    """**YAML 1.1 は `on:` を `True` として読みます。**

    最初この欄を `on:` にして、値がまるごと消えました（`需要 needs` の4件が
    `on が読めません` になった）。**同じ形の穴です** ——
    書いた欄と、読まれる欄が違いました。
    """
    raw = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    assert "\n        on: " not in raw, "`on:` は YAML で True になります。`on_date:` にすること"
    parsed = yaml.safe_load(raw)
    for h in parsed["hypotheses"]:
        for n in h.get("needs") or []:
            assert True not in n, f"`on:` が真偽値の鍵になっています: {h['claim'][:30]}"


def test_遅れを必ず足す():
    """**「公開から7日」に Analytics の遅れを足さないと、4日ぶんで判定します。**"""
    a = J._ans_published_group(
        {"created_after": "1970-01-01", "count": 1, "settle_days": 7}, date(2026, 8, 25), lag=3)
    b = J._ans_published_group(
        {"created_after": "1970-01-01", "count": 1, "settle_days": 7}, date(2026, 8, 25), lag=0)
    assert a.ready is not None and b.ready is not None
    assert a.ready - b.ready == timedelta(days=3)


def test_遅れが読めないときは_0_に倒れない():
    """**遅れを 0 と言い切るのが、いちばん危ない側です。**"""
    assert J.FALLBACK_LAG_DAYS > 0


def test_外の出来事は_判定できる日を出さない():
    a = J.answer({"kind": "external", "what": "収益化の審査"}, date(2026, 8, 25), 3)
    assert a.ready is None and a.unreachable


def test_0本のまま来ないのは_宣言したときだけ():
    """まだ公開していない本の再生は、いま 0 でも後から積みます。
    **`zero_means_never` を書いたときだけ**「来ません」と言うこと。"""
    base = {"kind": "accrual", "count_expr": "0", "need": 8, "since": "2026-08-23"}
    assert not J.answer(dict(base), date(2026, 8, 25), 3).unreachable
    assert J.answer({**base, "zero_means_never": True}, date(2026, 8, 25), 3).unreachable


@pytest.mark.parametrize("kind", ["now", "external", "accrual", "published_group",
                                  "after", "group_key"])
def test_知っている_kind_は落ちない(kind: str):
    """**状態を見る道具が、状態のせいで死んではいけない。**"""
    a = J.answer({"kind": kind}, date(2026, 8, 25), 3)
    assert isinstance(a, J.Answer)


def test_count_expr_は台帳を読める():
    a = J.answer({"kind": "accrual", "count_expr": "len(uploaded())",
                  "need": 1, "since": "2026-08-01"}, date(2026, 8, 25), 3)
    assert a.ready is not None, a.why
