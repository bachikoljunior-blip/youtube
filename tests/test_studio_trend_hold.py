"""`trend.hold` —— 「齢 Nh までに、いまの再生の何%が付いていたか」（2026-09-09 23:2x・optimizer・Opus）。

§7 の「90秒の上限」の行は 09/05 から **`measured` の 6時間再生／48時間再生の比**を見ろと書いているのに、
その比を出す道具が 4日 のあいだ無く、1度も数えられていなかった。この検査はその比を機械に留める。
"""
import datetime as dt

import studio.trend as tr


def _rows(points, vid="AAA", start="2026-09-08T10:00:00+09:00", scheduled=True):
    """(齢h, 生の再生) の並びから measured 行を作る。"""
    pub = dt.datetime.fromisoformat(start)
    out = []
    if scheduled:
        out.append({"event": "scheduled", "video_id": vid, "at": start})
    for age, views in points:
        out.append({
            "event": "measured", "id": vid, "age_h": age, "views": views,
            "at": (pub + dt.timedelta(hours=age)).isoformat(),
        })
    return out


def test_pct_is_share_of_now():
    rows = _rows([(1.0, 10), (6.0, 40), (30.0, 100)])
    six = tr.hold(rows)[0]["at"][6.0]
    assert six["views"] == 40 and round(six["pct"]) == 40


def test_both_ends_are_read_from_the_envelope_not_the_raw_point():
    """**分子も分母も、遅れている複製に落ちてはいけない**（`envelope` の註 ＝ 最大 28% 下に外す）。

    分子: 6h の直前に高い点が在れば、6h の生の点が低くてもその高い側を採る。
    分母: 最後の点が遅れた複製でも、いまの再生はそれまでの最大。
    """
    rows = _rows([(1.0, 10), (5.0, 80), (6.0, 20), (30.0, 100), (31.0, 72)])
    got = tr.hold(rows)[0]
    assert got["views"] == 100                    # 分母 —— 生の 72 で終わらない
    assert got["at"][6.0]["views"] == 80          # 分子 —— 生の 20 に落ちない
    assert round(got["at"][6.0]["pct"]) == 80


def test_no_point_yet_is_none_not_zero():
    """齢が届いていない所は **None**（0% ではない）。13h の本を「24h で 100%」と読ませない。"""
    rows = _rows([(1.0, 10), (6.0, 40), (13.0, 90)])
    got = tr.hold(rows)[0]
    assert got["at"][12.0] is not None
    assert got["at"][24.0] is None
    assert "24h   -" in "\n".join(tr.hold_lines(rows))


def test_growing_book_is_marked_because_its_share_is_an_upper_bound():
    growing = tr.hold(_rows([(1.0, 10), (6.0, 40), (30.0, 100)]))[0]
    assert growing["growing"] is True
    settled_rows = _rows([(1.0, 10), (6.0, 40), (60.0, 100), (61.0, 100)])
    assert tr.hold(settled_rows)[0]["growing"] is False
    assert "確定" in "\n".join(tr.hold_lines(settled_rows))


def test_band_count_is_derived_from_the_numbers_not_a_copy():
    """**印字の `n/m` は数から作る**（§7 が 7周 踏んだ「写しを持たない」）。"""
    inside = _rows([(1.0, 10), (6.0, 80), (60.0, 100), (61.0, 100)], vid="IN")
    assert "**1/1**" in "\n".join(tr.hold_lines(inside))
    outside = _rows([(1.0, 10), (6.0, 40), (60.0, 100), (61.0, 100)], vid="OUT")
    assert "**0/1**" in "\n".join(tr.hold_lines(outside))
    assert "**1/2**" in "\n".join(tr.hold_lines(inside + outside))


def test_only_our_books():
    """旧作りの本（`scheduled` の無い id）は出さない —— §1 の帯はこちらの作りの話。"""
    old = _rows([(1.0, 10), (6.0, 40), (60.0, 100)], vid="OLD", scheduled=False)
    assert tr.hold(old) == []


def test_ledger_now_answers_the_question_section7_asked():
    """実物の台帳で 6h の割合が出ること（4日 間 出ていなかった数）。"""
    got = tr.hold(tr.ledger_rows())
    six = [r for r in got if r["at"][6.0]]
    assert len(six) >= 4
    assert all(0 < r["at"][6.0]["pct"] <= 100 for r in six)
