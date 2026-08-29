"""`pick()` の天井は「calc の本数」ではなく「計算の節の数」だと決めた検査。

## なぜ要るか（2026-08-15 19:5x）

それまでの `pick()` は「**calc が全部ちがう**」でした。`calc` は11本しかないので、
**1回の batch は最大11本**です。M14（本数の段）は 8 の先を狙う手なのに、
**11 で頭打ちになることが、どこにも書いてありませんでした。**

前の回は次の宿題に「`--jobs` の上限を測る（6→8と上げて落ちる割合を見る）」と
置きました。**その回の実測では `pick(8)` が5件しか返しません**（未投稿テーマ7件・
calc は5種類）。**同時に作る相手がいない状態で並列度だけ測っても意味がありません。**
律速は並列度ではなく、**取れるテーマの数**のほうでした。

だからここでは「何本取れるか」を検査します。**速さは測っていません。**

節（`calc_sections`）がちがえば前提も数字も棒の形もちがうので、
「同じ計算を2回出さない」は守ったまま天井を上げられます。ただし節だけにはせず、
**1つの calc から取るのは既定2本まで**（同じ制度が並ぶと題も似て、
「繰り返しのように感じられる」側に寄る＝収益化の条件）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import batch_build  # noqa: E402
from src import family_perf  # noqa: E402


def _topic(tid: str, calc: str, section: str | None, score: float = 1.0) -> dict:
    t = {"id": tid, "calc": calc, "score": score}
    if section is not None:
        t["calc_sections"] = [section]
    return t


@pytest.fixture
def pool(monkeypatch):
    """`config.load_topics` と「投稿済み」を差し替えて、pick だけを見る。"""
    holder: dict = {"topics": []}

    def _install(topics, posted=()):
        holder["topics"] = topics
        monkeypatch.setattr(batch_build.config, "load_topics",
                            lambda: {"topics": holder["topics"]})
        monkeypatch.setattr(batch_build.history, "posted_topic_ids",
                            lambda: set(posted))
        # **族べつの実績を平らにしてから測ること**（2026-08-16 に足した）。
        # `pick` は 2026-08-16 から順番を実績で決めます（`src/family_perf.py`）。
        # ここで見たいのは**何本取れるか（天井）**であって順番ではないので、
        # 実データが入ると `nenkin` が先に来るだけで落ちます ——
        # **実際に落ちました**（`a`, `c` を期待して `c`, `a`）。
        # 順番のほうは `tests/test_family_perf.py` が別に見ています。
        monkeypatch.setattr(family_perf, "scorer", lambda *a, **k: (lambda calc: 1.0))

        # **節の見出しも、作り物どうしでそろえること**（2026-08-30 に足した）。
        #
        # 2026-08-30 01:19 に `pick()` へ門が1つ入りました ——
        # 「`calc_sections` が実物の見出しに1つも当たらないテーマは、作る前に外す」
        # （`script_writer` が当たる節無しで `RuntimeError` を投げるため。正しい門です）。
        #
        # **この検査の題は全部 作り物**（`節1` `勤続年数の境界`）なので、
        # 実物の `src/calc/` の見出しには当たりません。**15件中13件が赤**になり、
        # 門が入った回から**この検査は何も測っていませんでした。**
        #
        # **門を消しません。** 見出しの側を、この検査の作り物にそろえます ——
        # ここが見ているのは `pick()` の**天井**（何本 取れるか）であって、
        # 見出しが実在するかではありません。あちらは
        # `tests/test_calc_sections_still_hit.py` が実データで見ています。
        heads: dict[str, list[str]] = {}
        for t in holder["topics"]:
            for w in (t.get("calc_sections") or []):
                heads.setdefault(t.get("calc") or "", []).append(f"=== {w} ===")
        monkeypatch.setattr(
            batch_build, "_calc_sections_cached",
            lambda calc: [(h, "") for h in heads.get(calc, [])])

    return _install


# --- 天井そのもの ---------------------------------------------------------

def test_same_calc_different_sections_are_both_taken(pool):
    """**これが今回の主眼。** 同じ calc でも節がちがえば2本取れる（昔は1本）。"""
    pool([
        _topic("a", "shitsugyo", "勤続年数の境界"),
        _topic("b", "shitsugyo", "離職理由の境界"),
    ])
    assert [t["id"] for t in batch_build.pick(2, [])] == ["a", "b"]


def test_per_calc_caps_at_two_by_default(pool):
    """節が3つあっても、既定では同じ calc から3本目は取らない。"""
    pool([
        _topic("a", "shobyo", "節1"),
        _topic("b", "shobyo", "節2"),
        _topic("c", "shobyo", "節3"),
    ])
    assert [t["id"] for t in batch_build.pick(3, [])] == ["a", "b"]


def test_per_calc_one_reproduces_the_old_rule(pool):
    """`--per-calc 1` は昔の「calc が全部ちがう」と同じ。**戻せることを見ておく。**"""
    pool([
        _topic("a", "shobyo", "節1"),
        _topic("b", "shobyo", "節2"),
        _topic("c", "nenkin", "節1"),
    ])
    got = [t["id"] for t in batch_build.pick(3, [], per_calc=1)]
    assert got == ["a", "c"]


def test_ceiling_is_sections_not_modules(pool):
    """calc 3本・節2つずつ ＝ 6本取れる。**昔の規則なら3本で止まっていました。**"""
    topics = [
        _topic(f"{c}-{i}", c, f"節{i}")
        for c in ("shitsugyo", "shobyo", "taishoku")
        for i in (1, 2)
    ]
    pool(topics)
    assert len(batch_build.pick(6, [])) == 6
    assert len(batch_build.pick(6, [], per_calc=1)) == 3


# --- 守っているもの -------------------------------------------------------

def test_identical_section_is_never_taken_twice(pool):
    """**同じ計算は2回出さない。** ここは緩めていません。"""
    pool([
        _topic("a", "kojo", "同じ節"),
        _topic("b", "kojo", "同じ節"),
    ])
    assert [t["id"] for t in batch_build.pick(2, [])] == ["a"]


def test_topic_without_sections_uses_the_whole_module(pool):
    """節の指定が無いテーマは**モジュール全体**。どの節とも重なるので、両方は取りません。

    **2026-08-18 に、勝つ側を入れ替えました。** ここは長らく `["whole"]` を
    期待していて、それが**直近8回で書いた5本の表を1本ずつに絞っていた**原因です
    （`scripts/batch_build.pick` の `has_sections` の節を読むこと）。
    **どちらも取れないのは変わりません。取るほうが逆になりました。**
    """
    pool([
        _topic("whole", "iryohi", None),
        _topic("part", "iryohi", "節1"),
    ])
    assert [t["id"] for t in batch_build.pick(2, [])] == ["part"]


def test_whole_module_is_skipped_when_a_section_came_first(pool):
    """逆順でも同じ。先に節を取っていたら、モジュール全体のほうを飛ばす。"""
    pool([
        _topic("part", "iryohi", "節1", score=2.0),
        _topic("whole", "iryohi", None, score=1.0),
    ])
    assert [t["id"] for t in batch_build.pick(2, [])] == ["part"]


def test_posted_topics_are_excluded(pool):
    pool([_topic("a", "kojo", "節1"), _topic("b", "kojo", "節2")], posted=["a"])
    assert [t["id"] for t in batch_build.pick(2, [])] == ["b"]


def test_topics_without_calc_are_excluded(pool):
    pool([{"id": "nocalc", "score": 9.0}, _topic("a", "kojo", "節1")])
    assert [t["id"] for t in batch_build.pick(2, [])] == ["a"]


def test_score_order_is_kept(pool):
    pool([
        _topic("low", "kojo", "節1", score=0.5),
        _topic("high", "nenkin", "節1", score=5.0),
    ])
    assert [t["id"] for t in batch_build.pick(2, [])] == ["high", "low"]


def test_per_calc_zero_is_rejected(pool):
    """0 を許すと1本も返らないまま「在庫が尽きた」と読めてしまう。"""
    pool([_topic("a", "kojo", "節1")])
    with pytest.raises(SystemExit):
        batch_build.pick(1, [], per_calc=0)


# --- 節を指定しない「題材」のテーマが、族ごと飲み込んでいた -----------------
# 2026-08-18 に測って足した。**直近8回で書いた5本の表が、どれも1本ずつしか
# 出していませんでした**（節は6件ずつあるのに）。`calc:` を繋いだ時点から
# 「表を書くと決めた回の題材」も未投稿テーマとして残り、
# **それが `whole_module` を立てて、同じ族の節べつのテーマを全部止めていた**ためです。
# `pick(30)` の返りは **14本 → 19本**（per_calc=2）。

def test_節がある族では題材のテーマを取らない(pool):
    """**題材（`calc_sections` の無いテーマ）は、節があるあいだ取りません。**"""
    pool([
        {"id": "seed", "calc": "shokibo", "score": 1.0},   # 節の指定が無い
        _topic("a", "shokibo", "節1"),
        _topic("b", "shokibo", "節2"),
    ])
    assert [t["id"] for t in batch_build.pick(3, [])] == ["a", "b"]


def test_節が1つも無い族なら題材のテーマを取る(pool):
    """**外す向きは「節があるとき」だけ。** 表を書く前の族は今までどおり。"""
    pool([
        {"id": "seed", "calc": "kotei", "score": 1.0},
        _topic("a", "shokibo", "節1"),
    ])
    assert sorted(t["id"] for t in batch_build.pick(3, [])) == ["a", "seed"]


def test_題材が先頭でも節べつのほうが残る(pool):
    """**並び順まかせだったのが、この検査の要点です。**

    `score` で題材が先頭に来ても、節べつのテーマが全部止まらないこと
    （前は `whole_module` が立って、以降の同じ族が全部 `continue` していた）。
    """
    pool([
        {"id": "seed", "calc": "shokibo", "score": 9.0},   # わざと最上位
        _topic("a", "shokibo", "節1"),
        _topic("b", "shokibo", "節2"),
    ])
    got = [t["id"] for t in batch_build.pick(3, [])]
    assert "seed" not in got
    assert got == ["a", "b"]


def test_族が5つあると返りが5本ふえる(pool):
    """**実測の形をそのまま検査に**（5族 × 1本 ＝ 14本 → 19本）。"""
    topics: list[dict] = []
    for calc in ("shokibo", "invoice", "rousai", "tsukin", "seimeihoken"):
        topics.append({"id": f"seed-{calc}", "calc": calc, "score": 1.0})
        for i in (1, 2, 3):
            topics.append(_topic(f"{calc}-{i}", calc, f"節{i}"))
    pool(topics)
    got = batch_build.pick(30, [])
    assert len(got) == 10          # 5族 × per_calc 2本
    assert not any(t["id"].startswith("seed-") for t in got)
