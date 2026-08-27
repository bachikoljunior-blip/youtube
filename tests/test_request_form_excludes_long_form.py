"""`request_form` の群を、2つの道具が同じ数で言うこと（2026-08-27 に踏んだ）。

## なぜ要るか

`src/ab_split.split_counts()` と `src/judgeable._members_by_request_form()` は、
**同じ実験の同じ群を、3〜4本 ちがう数で言っていました**（同じ日・同じ枝・API 0単位）::

    scripts/ab_split.py --outlook   途中あり **15本** ／ 終端のみ **18本**
    scripts/queue_lag.py            途中あり   12本  ／ 終端のみ   14本

差の正体は**長尺**でした。`Experiment.split`（＝ `script_writer.request_form()`）は
テーマIDのハッシュだけを見るので、長尺にも `途中あり` / `終端のみ` を返します。
`judgeable` 側は控えの `duration_s` で長尺を落としており、そちらが正しい ——
**長尺は登録の依頼を1文字も書かないから**です（`src/script_writer.ROLE`）。

`src/ab_split.py` の註は 2026-08-27 まで
「**長尺は `request_form` が `"長尺"` を返し、どちらの群にも入りません**」と
言っていましたが、**そんな枝は関数にありません。** 註だけが正しく、
実装が黙って長尺を 7本 数えていました。

**混ぜると何が起きるか。** 床（片群 72本）に届く前に「あと N本」の N が
小さく見え、次の回が「もう埋まる」と読みます。`falsified_if` は
「上回らなければ外れ（**同点も外れ**）」で、`next_if_false` は腕ごと畳むので、
**見分けられなかっただけの実験が、効かない実験として閉じます**
（`src/ab_split.floor_of()` の註と同じ壊れ方の5件目）。

## 覆る条件

長尺にも依頼を書くようになったら（`src/script_writer.ROLE` を変えたら）、
`EXPERIMENTS["request_form"].eligible` を外すこと。**このファイルも同時に。**
"""

from __future__ import annotations

from src import ab_split, judgeable


def test_split_counts_と_judgeable_が同じ数を言う() -> None:
    """**実物の控えで**、2つの道具の群の大きさが一致すること。"""
    exp = ab_split.EXPERIMENTS["request_form"]
    counts = ab_split.split_counts(exp)
    members = judgeable.members("request_form")

    for group in (exp.treated, exp.control):
        assert counts.treated_all[group] == len(members[group]), (
            f"{group}: split_counts {counts.treated_all[group]}本 と "
            f"judgeable {len(members[group])}本 が食い違っています。"
            "**数え方を2つ並べて残さないこと** —— 次の回がまた両方読みます"
        )


def test_長尺は_どちらの群にも入らない() -> None:
    """控えで 3分超と分かっている本が、群に1本も混ざらないこと。"""
    exp = ab_split.EXPERIMENTS["request_form"]
    shorts = judgeable._short_topics()
    builds = ab_split.build_times()

    long_form = [
        topic for topic, built in builds.items()
        if built >= exp.landed and topic not in shorts
    ]
    assert long_form, (
        "指示が入って以降に作った長尺が1本もありません —— "
        "**この検査が何も見ていない状態**です。控えの読みを疑うこと"
    )

    allowed = exp.eligible() if exp.eligible is not None else None
    assert allowed is not None, (
        "`EXPERIMENTS['request_form'].eligible` が外れています。"
        "外したのなら `src/script_writer.ROLE` が長尺にも依頼を書くはずです —— "
        "書いていないなら、長尺が黙って群に入ります"
    )
    for topic in long_form:
        assert topic not in allowed, f"長尺 {topic} が群に入っています"


def test_絞り込みの無い実験は_今までどおり全部数える() -> None:
    """`eligible` を持たない実験の数え方を変えていないこと。"""
    for name, exp in ab_split.EXPERIMENTS.items():
        if name == "request_form":
            continue
        assert exp.eligible is None, (
            f"{name} に絞り込みが付いています。付けるなら、"
            "**なぜその本が永久に処置群へ入らないか**を `eligible` の関数に書くこと"
        )
