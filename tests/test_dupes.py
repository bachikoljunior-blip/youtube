"""`src/dupes.py` の検査。

**故障注入つき**（`tests/test_chart_base.py` と同じ作り）。
「重なりを見つける」だけでなく、**見つけてはいけないものを見つけない**ことを
同じだけ調べます。実測でいちばん高かった誤りは**後者**で、
最初の実装は `fukugyo` の6本を「副業20万円ルール」という制度名の数字で
全部つなぎ、**32組のうち15組が偽物**でした。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import dupes  # noqa: E402


def _v(vid: str, title: str, topic: str = "", at: str | None = None,
       public: bool = False) -> dict:
    status: dict = {"privacyStatus": "public" if public else "private"}
    if at and not public:
        status["publishAt"] = at
    return {
        "id": vid,
        "snippet": {"title": title,
                    "description": f"本文\n[t:{topic}]" if topic else "本文",
                    "publishedAt": at or "2026-08-01T00:00:00Z"},
        "status": status,
    }


TOPICS = {"a1": "tedori", "a2": "tedori", "b1": "fukugyo", "b2": "fukugyo",
          "c1": "zangyo", "c2": "zangyo", "d1": "iryohi", "d2": "iryohi",
          "e1": "shitsugyo", "e2": "shitsugyo", "n1": "nenkin", "n2": "nenkin"}


def _find(videos: list[dict]) -> list[dict]:
    return dupes.find(dupes.rows_from_videos(videos, TOPICS))


def _kinds(videos: list[dict]) -> set[str]:
    return {i["kind"] for i in _find(videos)}


def _strong(videos: list[dict]) -> list[dict]:
    return [i for i in _find(videos) if i["strong"]]


# ---------------------------------------------------------------- 数の読み取り

def test_numbers_reads_japanese_scale():
    """`35万9318円` は **1つの数**。`35` と `9318` に割らない。"""
    assert (359318.0, "円") in dupes.numbers("手取りは35万9318円")


def test_numbers_does_not_join_equal_scales():
    """`年収500万から50万アップ` は 500万 と 50万 の2つ。5,500,000 ではない。"""
    vals = [v for v, u in dupes.numbers("年収500万から50万アップ")]
    assert 5_000_000.0 in vals and 500_000.0 in vals
    assert 5_500_000.0 not in vals


def test_numbers_reads_truncated_form():
    """`61万9千円` ＝ 619,000。**題は丸めて書かれる。**"""
    assert (619000.0, "円") in dupes.numbers("3年で61万9千円")


def test_numbers_reads_comma_and_units():
    got = dict((u, v) for v, u in dupes.numbers("2,143,480円増 546日で31か月 46.8%"))
    assert got["円"] == 2143480.0
    assert got["日"] == 546.0
    assert got["か月"] == 31.0
    assert got["%"] == 46.8


def test_numbers_reads_twenty_man_ichi_en():
    """`20万1円` ＝ 200,001。制度のしきい値を1円こえた形（実物の題）。"""
    assert (200001.0, "円") in dupes.numbers("副業20万1円で手取り15万9581円")


def test_sigdigits():
    assert dupes.sigdigits(200000) == 1
    assert dupes.sigdigits(1_600_000) == 2
    assert dupes.sigdigits(619000) == 3
    assert dupes.sigdigits(359318) == 6


# ---------------------------------------------------------------- 見つけるべき

def test_same_topic_id_is_strong():
    got = _strong([_v("x", "題A", "a1"), _v("y", "題B", "a1")])
    assert any(i["kind"] == "same-topic" for i in got)


def test_same_amount_different_topic_is_strong():
    """**この検査が無かったせいで残っていた組**（実物 `_4zhMy-VIyg` / `a1b2Nm6jN_0`）。"""
    got = _strong([
        _v("x", "年収500万から50万アップで手取りは35万9318円", "a1"),
        _v("y", "社会保険料率で手取り増は35万9318円", "a2"),
    ])
    assert any(i["kind"] == "same-yen" for i in got)


def test_rounded_title_still_matches():
    """`61万9898円` と `61万9千円` は同じ本の言い直し（差 0.14%）。"""
    got = _strong([
        _v("x", "一律手当と残業代 3年で61万9898円", "c1"),
        _v("y", "残業代 一律手当の除外 3年で61万9千円", "c2", public=True),
    ])
    assert any(i["kind"] == "same-yen" for i in got)


def test_two_shared_amounts_is_strong_even_if_round():
    """前提と答えの**両方**が一致するなら、丸くても重なり（実物 `iryohi`）。"""
    got = _strong([
        _v("x", "医療費控除の足切りは10万円ではない 総所得160万で8万円", "d1"),
        _v("y", "医療費控除 総所得160万なら足切りは8万円", "d2"),
    ])
    assert any(i["kind"] == "same-yen" for i in got)


# ------------------------------------------------------- 見つけてはいけない（故障注入）

def test_institution_name_number_does_not_link_everything():
    """**最初の実装が落ちたところ。** `20万円ルール` は制度の名前であって答えではない。

    6本が全部 `20万` を持つので、素朴に「1つでも一致」で見ると
    **15組が偽物**になり、本当の重なりが埋もれます。
    """
    vids = [
        _v("b1", "副業20万円 1円こえて手取り139,161円", "b1"),
        _v("b2", "副業20万1円で手取り15万9581円", "b2"),
    ]
    assert not any(i["kind"] == "same-yen" for i in _strong(vids))


def test_round_single_match_is_weak_only():
    """題の数字が `20万円` **だけ**の本は、`20万1円` の本すべてとは組にしない。"""
    vids = [
        _v("b1", "副業20万円ルールは経費を含む 売上ではなく所得で判定", "b1", public=True),
        _v("b2", "副業20万1円で税額は4万6966円増える", "b2"),
    ]
    assert not _strong(vids)
    assert "same-yen-loose" in _kinds(vids)


def test_different_calc_never_links():
    """calc が違えば、金額が偶然合っても重なりではない（別の制度の話）。"""
    vids = [_v("x", "手取りは35万9318円", "a1"), _v("y", "残業代は35万9318円", "c1")]
    assert not _find(vids)


def test_small_amounts_are_ignored():
    """1万円未満は前提側の端数。ここを見ると `1円` `3日` で全部つながる。"""
    vids = [_v("x", "最初の3日で2万1円出ない", "a1"), _v("y", "1日6667円", "a2")]
    assert not any(i["kind"] == "same-yen" for i in _find(vids))


def test_unrelated_titles_are_clean():
    vids = [
        _v("x", "傷病手当金546日で手元は286万7592円", "a1"),
        _v("y", "傷病手当金 手元は46.8% 40歳以上", "a2"),
    ]
    assert not _strong(vids)


# ------------------------------------------------------------------ 弱いほう

def test_same_answer_number_is_weak():
    vids = [
        _v("x", "自己都合と会社都合で給付日数90日差", "e1"),
        _v("y", "60歳以上の失業手当 離職理由で90日ちがう", "e2"),
    ]
    assert "same-answer" in _kinds(vids)
    assert not _strong(vids)


def test_age_is_not_an_answer_number():
    """`45歳` `勤続10年` は条件であって、その本が出した答えではない。"""
    vids = [_v("x", "45歳の失業給付", "e1"), _v("y", "45歳の年金", "n1")]
    assert not _find(vids)


def test_same_calc_same_day_is_weak():
    vids = [
        _v("x", "45歳以上 解雇なら勤続1年で給付日数が90日増える", "e1",
           at="2026-08-31T02:00:00Z"),
        _v("y", "60歳以上 勤続1年で給付60日増える", "e2", at="2026-08-31T08:00:00Z"),
    ]
    assert "same-day" in _kinds(vids)


def test_same_calc_different_day_is_not_same_day():
    vids = [
        _v("x", "45歳以上 解雇なら勤続1年で給付日数が180日増える", "e1",
           at="2026-08-30T02:00:00Z"),
        _v("y", "60歳以上 勤続1年で給付60日増える", "e2", at="2026-08-31T08:00:00Z"),
    ]
    assert "same-day" not in _kinds(vids)


def test_no_marker_no_pairing():
    """説明欄に `[t:...]` が無い動画は、テーマも calc も分からないので黙って通す。"""
    vids = [_v("x", "手取りは35万9318円"), _v("y", "手取りは35万9318円")]
    assert not _find(vids)


def test_report_survives_empty():
    assert dupes.report([], TOPICS) == []


# ------------------------------------------------- 投稿の直前に止める（blocking）

def test_blocking_stops_a_repeat():
    """**これから上げる本**が、既にある本と同じ金額なら止める。"""
    existing = [_v("old", "年収500万から50万アップで手取りは35万9318円", "a1")]
    hits = dupes.blocking("社会保険料率で手取り増は35万9318円", "a2", existing, TOPICS)
    assert hits and hits[0]["kind"] == "same-yen"


def test_blocking_stops_same_topic():
    existing = [_v("old", "まったく別の題", "a1")]
    assert dupes.blocking("別の題2", "a1", existing, TOPICS)


def test_blocking_passes_a_new_one():
    existing = [_v("old", "年収500万から50万アップで手取りは35万9318円", "a1")]
    assert not dupes.blocking("年収700万から50万アップで手取りは28万4102円",
                              "a2", existing, TOPICS)


def test_blocking_ignores_pairs_that_do_not_involve_me():
    """既にある本どうしの重なりで、新しい本を止めないこと（**止まると投稿が途切れる**）。"""
    existing = [
        _v("o1", "年収500万から50万アップで手取りは35万9318円", "a1"),
        _v("o2", "社会保険料率で手取り増は35万9318円", "a2"),
    ]
    assert not dupes.blocking("残業代 一律手当で3年61万9898円", "c1", existing, TOPICS)


def test_blocking_uses_the_local_ledger(tmp_path, monkeypatch):
    """**口が落としても、手元の控えで止まること**（2026-08-16 に実際にすり抜けた）。

    同じ `s-fukugyo-2` を5分の間に「止めて、そのあと通して」います。
    落ちていたのは実在する予約済みの本で、uploads プレイリストが落とし、
    `search` は当日の API 枠を使い切っていました。**videos を空で渡しても止まること。**
    """
    from src import config

    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    dupes.remember("old1", "a1", "年収500万から50万アップで手取りは35万9318円", None)
    assert dupes.blocking("社会保険料率で手取り増は35万9318円", "a2", [], TOPICS)
    assert not dupes.blocking("年収700万で手取りは28万4102円", "a2", [], TOPICS)


def test_ledger_ignores_broken_lines(tmp_path, monkeypatch):
    from src import config

    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / dupes.LEDGER).write_text(
        '{"video_id":"a","topic":"a1","title":"題"}\nこわれた行\n\n', encoding="utf-8")
    assert [r["id"] for r in dupes.ledger_rows(TOPICS)] == ["a"]
