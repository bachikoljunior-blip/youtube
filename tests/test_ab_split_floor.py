"""A/B の床を、実験ごとに引いているか（`ab_split.floor_of`）。

## この検査が生まれた1件（2026-08-27）

`request_form`（腕 `sub_rate`）の床は **片群 72本**です ——
測っているのが engaged ではなく**登録**だから
（登録率の実測 0.0318% ＝ 3,066再生に1人。片群 16本 ＝ 約 6,700再生では
期待 2.1人 で、効きが2倍でも見分けられません）。理由ごと
`src/judgeable.MEMBER_SOURCES` に書いてあります。

**ところが `scripts/ab_split.py` は全部に 16 を当てていました。** 実測:

    scripts/ab_split.py    途中あり 12本 → **まだ判定しない（あと4本）**
    deadline_check.py      途中あり  9本 → **あと 63本**（床 72）

`config/hypotheses.yaml` の `falsified_if` は、数える道具として
**`scripts/ab_split.py` を名指し**しています。その道具が「あと4本」と言えば、
次の回は「もう埋まる」と読んで別の腕へ移り、6,700再生で登録率を比べる標本のまま
「判定できます」が出ます。`falsified_if` は「上回らなければ外れ（同点も外れ）」なので、
**見分けられなかっただけの実験が、効かない実験として閉じます**
（`next_if_false` は腕ごと畳みます）。

同じ穴は `src/watches.py` が 2026-08-26 22:5x に踏んで直しています
（`tests/test_watch_ab_floor.py`）。**直ったのはあちらの1か所だけでした。**
"""
from datetime import date

import pytest

from src import ab_split, judgeable


def test_床は_judgeable_の台帳から引く():
    """**同じ数を2箇所で持たないこと。**"""
    for name, (_fn, need) in judgeable.MEMBER_SOURCES.items():
        assert ab_split.floor_of(name) == need, name


def test_request_form_の床は_16本ではない():
    """**この検査が生まれた1件。**（`MIN_PER_GROUP` を写すと落ちる）"""
    assert ab_split.floor_of("request_form") == 72
    assert ab_split.floor_of("request_form") != ab_split.MIN_PER_GROUP


def test_台帳に無い実験は既定の床に落ちる():
    assert ab_split.floor_of("そんな実験はない") == ab_split.MIN_PER_GROUP


def _counts(name: str, **ready: int) -> ab_split.Counts:
    return ab_split.Counts(experiment=name, treated_ready=dict(ready),
                           floor=ab_split.floor_of(name))


def test_床に届いていない群を判定できるとは言わない():
    c = _counts("request_form", 終端のみ=17, 途中あり=12)
    assert c.judgeable is False
    assert "床 片群 72本" in c.short(), c.short()
    assert "あと60本" in c.short(), c.short()


def test_16本の実験はそのまま():
    c = _counts("title_form", 問い=16, 断定=16)
    assert c.judgeable is True, c.short()


def test_床を1本でも欠けば判定しない():
    c = _counts("title_form", 問い=16, 断定=15)
    assert c.judgeable is False
    assert "断定 あと1本" in c.short(), c.short()


def test_足りない本数も実験ごとの床で数える():
    """`outlook.need` が `MIN_PER_GROUP` を写していないこと。"""
    o = ab_split.outlook(ab_split.EXPERIMENTS["request_form"],
                         {"終端のみ": 0, "途中あり": 0},
                         as_of=date(2026, 10, 6),
                         counts=_counts("request_form", 終端のみ=17, 途中あり=12))
    assert o.need["途中あり"] == 60, o.need
    assert o.need["終端のみ"] == 55, o.need


@pytest.mark.parametrize("name", sorted(ab_split.EXPERIMENTS))
def test_数えた結果にも床が載っている(name):
    """`split_counts` が床を落とさないこと（既定の 16 に戻らない）。"""
    c = ab_split.split_counts(ab_split.EXPERIMENTS[name],
                              as_of=date(2026, 8, 27),
                              builds={}, ledger=[])
    assert c.floor == ab_split.floor_of(name), name
