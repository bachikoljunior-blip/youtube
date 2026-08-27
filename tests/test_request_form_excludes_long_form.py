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

## **このファイルは 2026-08-27 から 2026-08-28 まで、2件とも赤で居座っていました**

最適化の回（08-28 06:3x）が実物を読んで割りました。**片方は本物・片方は偽**で、
**偽のほうが、本物のほうを見えなくしていました。**

    偽  `split_counts` と `judgeable.members()` が同じ数を言うこと
        → **この2つは、わざと別のものを数えています。**`members()` は
          `_live_ids()` で**再生の付かない枠の本を落とします**（あちらの docstring）。
          `split_counts` は落としません。**1本でも死んだ枠に落ちれば赤**で、
          構造的に緑にできません。実測 08-28: 終端のみ **25 対 24**（差は死んだ枠1本）。
          → 突き合わせる相手を **`MEMBER_SOURCES[key]` の素の群**（枠で落とす前）
            に直しました。長尺の混入を見るのが目的なら、そちらが正しい相手です

    本物 `request_form` **以外**に `eligible` が付いていないこと
        → 2026-08-27 に `slide_pace` へ `eligible=_shorts_only` が入り、
          **その日からこの検査は赤**でした。**警報は鳴っていました。**
          鳴っていたものが本物で、`src/judgeable._members_by_split()` は
          `eligible` を**読んでいませんでした** —— 長尺3本が `slide_pace` の群に
          入り、`deadline_check` が「**期限を 23日 延ばせ**」と印字していました。
          → 名前の白名簿をやめ、**「`eligible` を宣言した実験は、両方の数え方で
            守られていること」**という、実装を見る門に直しました

**教訓は「赤を放置するな」ではありません。**（放置していたのは、
毎周この検査を撃っていなかったからではなく、**撃つと必ず赤だったから**です。）
**恒久的に赤い検査を1つ置くと、同じファイルの本物の警報が読まれなくなります。**
偽の警報は、消すか、緑にできる形へ直すこと —— **残してよい赤はありません。**
"""

from __future__ import annotations

from src import ab_split, judgeable


def _topic_of(video_id: str) -> str | None:
    """`video_id` → テーマID（`judgeable` と同じ走査・同じ勝ち方）。"""
    if not video_id:
        return None
    return {v: t for t, v in judgeable._video_by_topic().items() if v}.get(video_id)


def test_split_counts_と_判定の群が_同じ本を数える() -> None:
    """**実物の控えで**、2つの道具が同じ本を群に入れていること。

    突き合わせる相手は `judgeable.members()` **ではなく**
    `MEMBER_SOURCES[key]` の素の群です —— `members()` は `_live_ids()` で
    **再生の付かない枠の本を落とす**ので、`split_counts` と数が合わないのが正常です
    （このファイルの冒頭「偽」の節）。ここが見たいのは**長尺の混入**だけ。

    `split_counts` は `pub <= exp.deadline` の本しか数えないので、
    こちらも同じ窓に切ってから比べます。
    """
    for name, exp in ab_split.EXPERIMENTS.items():
        counts = ab_split.split_counts(exp)
        make, _ = judgeable.MEMBER_SOURCES[name]
        raw = make()
        for group in (exp.treated, exp.control):
            mine = sum(1 for d, _v in raw[group] if d <= exp.deadline)
            assert counts.treated_all[group] == mine, (
                f"{name}/{group}: split_counts {counts.treated_all[group]}本 と "
                f"judgeable の素の群 {mine}本 が食い違っています。"
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


def test_eligible_を宣言した実験は_判定の群でも守られる() -> None:
    """**宣言した絞り込みが、群を作る側でも効いていること。**

    これが 2026-08-27 から赤だった検査です（当時は「`request_form` 以外に
    `eligible` を付けるな」という名前の白名簿でした）。
    **名前で見ると、正しく足した回が赤を出します** —— 実際 `slide_pace` に
    `eligible=_shorts_only` を足した回がそうなり、
    **本当の欠陥（`_members_by_split()` が `eligible` を読まない）は
    その赤に紛れて 1日 読まれませんでした。**

    だから見るのは名前ではなく**実装の結果**です。
    """
    for name, exp in ab_split.EXPERIMENTS.items():
        if exp.eligible is None:
            continue
        allowed = exp.eligible()
        make, _ = judgeable.MEMBER_SOURCES[name]
        for group, ms in make().items():
            for _day, vid in ms:
                topic = _topic_of(vid)
                if topic is None:
                    continue
                assert topic in allowed, (
                    f"{name}/{group}: {topic}（{vid}）は `eligible` の外なのに"
                    " 群に入っています。**`Experiment.eligible` を読まない"
                    "数え方が、どこかに残っています**"
                )


def test_絞り込みを足すときは_理由を関数に書く() -> None:
    """`eligible` は関数で渡すこと（**なぜ永久に処置群へ入らないか**を書く場所）。"""
    for name, exp in ab_split.EXPERIMENTS.items():
        if exp.eligible is None:
            continue
        assert callable(exp.eligible) and (exp.eligible.__doc__ or "").strip(), (
            f"{name} の `eligible` に説明がありません。"
            "**なぜその本が永久に処置群へ入らないか**を関数の docstring に書くこと"
        )


def test_slide_pace_は_標本から見てもショートだけ() -> None:
    """宣言ではなく**中身**から見て、ショートだけになっていること。

    `judgeable.shorts_only()` は「宣言を写さず、標本から見ます」と書かれた
    別解きです。2026-08-28 まで、あれは `slide_pace` を返しませんでした ——
    **道具は正しく鳴っていて、誰も訊いていなかった**だけです。
    """
    got = judgeable.shorts_only(["slide_pace", "request_form"])
    assert "slide_pace" in got, (
        "`slide_pace` の群に、ショート以外が混ざっています。"
        "長尺は `reveal_variants` を1度も通らないので、刻みの処置が入っていません"
    )
