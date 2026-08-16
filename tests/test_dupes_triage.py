"""`src/dupes.triage` の検査（2026-08-16）。

**故障注入つき。** ここで守りたいのは1点だけです ——
**黙らせた組が、復活したときに必ず鳴り直すこと。**

実測（この回・実物22組）:

    予約 + 外し    11組
    公開 + 外し     6組
    公開 + 公開     3組
    外し + 外し     2組
    **予約 + 予約    0組 ／ 予約 + 公開    0組 ＝ 当たり0件**

22組を毎回並べて、そのどれにも `--unschedule` できる相手がいませんでした。
`status.py` 自身が「毎回鳴る警告は無視されるようになる」と書いており、
8/16 08:2x の「予約し忘れ」に続く**2件目**です。

**見つける側（`find`）は変えていません。** 変えたのは並べ方だけなので、
`blocking()` と `why_stranded()` は素通りします（下でそれも見ます）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import dupes  # noqa: E402

TOPICS = {"a1": "tedori", "a2": "tedori"}


def _v(vid: str, title: str, topic: str, at: str | None, public: bool) -> dict:
    """`at=None` かつ `public=False` ＝ 予約の無い private ＝「外し」。"""
    status: dict = {"privacyStatus": "public" if public else "private"}
    if at and not public:
        status["publishAt"] = at
    return {
        "id": vid,
        "snippet": {"title": title,
                    "description": f"本文\n[t:{topic}]",
                    "publishedAt": at or "2026-08-01T00:00:00Z"},
        "status": status,
    }


def _sched(vid: str, topic: str = "a1") -> dict:
    return _v(vid, "手取りは35万9318円", topic, "2026-08-25T00:00:00Z", public=False)


def _public(vid: str, topic: str = "a1") -> dict:
    return _v(vid, "手取りは35万9318円", topic, "2026-08-05T00:00:00Z", public=True)


def _parked(vid: str, topic: str = "a1") -> dict:
    return _v(vid, "手取りは35万9318円", topic, None, public=False)


def _triage(videos: list[dict]) -> dict[str, list[dict]]:
    issues = dupes.find(dupes.rows_from_videos(videos, TOPICS))
    return dupes.triage([i for i in issues if i["strong"]])


def _pairs(videos: list[dict]) -> dict[str, set[tuple[str, str]]]:
    """**組は「動画の対」で数えます。**

    1つの対が `same-topic` と `same-yen` の**両方**で鳴ることがあり
    （題が同じなら金額も同じなので、実物でも普通に起きます）、
    `issues` の件数で数えると対の数と食い違います。
    """
    return {k: {tuple(sorted((i["a"]["id"], i["b"]["id"]))) for i in v}
            for k, v in _triage(videos).items()}


# ------------------------------------------------------------------ 3つの向き

def test_予約どうしは止められる():
    got = _pairs([_sched("x"), _sched("y")])
    assert got["actionable"] == {("x", "y")}, "両方これから公開される ＝ 外せる"
    assert not got["parked"] and not got["already"]


def test_予約と公開済みは止められる():
    """公開済みの繰り返しを、これから**もう1本**出そうとしている形。"""
    got = _pairs([_public("x"), _sched("y")])
    assert got["actionable"] == {("x", "y")}
    assert not got["parked"]


def test_相手が外れていれば黙る():
    got = _pairs([_sched("x"), _parked("y")])
    assert not got["actionable"], "外れている相手に --unschedule はできない"
    assert got["parked"] == {("x", "y")}


def test_公開済みどうしは取り消せない():
    got = _pairs([_public("x"), _public("y")])
    assert not got["actionable"], "もう出てしまっている。手は無い"
    assert got["already"] == {("x", "y")}


def test_両方とも外れていれば黙る():
    got = _pairs([_parked("x"), _parked("y")])
    assert not got["actionable"]
    assert got["parked"] == {("x", "y")}


# ------------------------------------------------------- 故障注入（**本命**）

def test_外した側が予約し直されたら鳴り直す():
    """**黙らせたぶんが戻ってくることを見る検査。**

    件数を消すのではなく分類を変えているだけなので、
    `parked` の側に `publishAt` が戻れば `actionable` へ移ります。
    ここが動かないなら、この直しは「警告を消しただけ」です。
    """
    before = _pairs([_sched("x"), _parked("y")])
    assert not before["actionable"] and before["parked"] == {("x", "y")}

    after = _pairs([_sched("x"), _sched("y")])   # y に予約が戻った
    assert after["actionable"] == {("x", "y")}, "復活した組は必ず鳴ること"
    assert not after["parked"]


def test_組を1つも捨てていない():
    """**分類は分けるだけ。** 合計は `find` の強い組と必ず一致すること。"""
    videos = [_sched("x"), _parked("y"), _public("z")]
    strong = [i for i in dupes.find(dupes.rows_from_videos(videos, TOPICS))
              if i["strong"]]
    got = _triage(videos)
    assert len(got["actionable"]) + len(got["parked"]) + len(got["already"]) \
        == len(strong) > 0


# --------------------------------------------- 見つける側は素通りであること

def test_blocking_は影響を受けない():
    """`blocking` の「これから上げる本」は `at=None` なので、
    **分類でいえば「外し」**です。`triage` を通していたら黙ってしまいます。
    通していないことを、ここで固定します。"""
    hits = dupes.blocking("手取りは35万9318円", "a1", [_public("z")], TOPICS)
    assert hits, "公開済みと重なる本は、投稿の直前に止まること"


def test_why_stranded_は影響を受けない():
    dark = _parked("y")
    got = dupes.why_stranded(dark, [_public("z")], TOPICS)
    assert got and got["other"]["id"] == "z", \
        "暗い本に理由を付ける側は、分類を通らないこと"
