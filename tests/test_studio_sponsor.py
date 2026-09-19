"""`studio/sponsor.py` の検査（**API 0単位**・台帳だけ）。

**この file が守るのは 3つ**:
 (1) **写しを持たないこと** —— 単価の帯も 本/日 の天井も `studio/trend` の 1か所から来る。
     写した日に、帯が動いても追わなくなる（`trend.sponsor_daily_cap_videos` が
     2026-09-18 に踏んだ穴と同じ形）。**規則の数を検査に写さないこと**も同じ向きで、
     ここは値ではなく **`trend` と一致するか** だけを見る（JOURNAL 2026-09-20 §11）。
 (2) **測っていない物を売りにしないこと** —— 相手の齢が `measured: False` の周は、
     媒体資料から年齢の行が落ちる（`sponsor` の覆る条件 (3)）。**陽性対照つき**。
 (3) **口を読んでいない相手を、読んだ側に混ぜないこと**（`checked_targets`）。
"""
from __future__ import annotations

import pytest

from studio import sponsor, trend


# --- (1) 写しを持たない -------------------------------------------------------

def _rows():
    from studio.cli import ledger_rows
    return ledger_rows()


def test_帯は_trend_の_1か所から来る():
    k = sponsor.kit(_rows())
    assert tuple(k["band"]) == tuple(trend.SPONSOR_YEN_PER_VIEW_BAND)


def test_本日の天井は_trend_の_1か所から来る():
    k = sponsor.kit(_rows())
    assert k["per_day_cap"] == trend.sponsor_daily_cap_videos()


def test_月額は_再生月_かける_帯_そのもの():
    """**式を写さない**: 3段 とも `views_month × band` と一致すること。"""
    k = sponsor.kit(_rows())
    for lv, b in zip(trend.YEN_LEVELS, k["band"]):
        assert k["price"][lv]["now"] == pytest.approx(k["views_month"] * b)
        assert k["price"][lv]["cap"] == pytest.approx(k["views_month_cap"] * b)


def test_帯が動いたら月額も動く_陽性対照(monkeypatch):
    """**写しを持っていたら、ここで止まります。**"""
    before = sponsor.kit(_rows())["price"]["中"]["cap"]
    monkeypatch.setattr(trend, "SPONSOR_YEN_PER_VIEW_BAND", (1.0, 3.0, 6.0))
    after = sponsor.kit(_rows())["price"]["中"]["cap"]
    assert after == pytest.approx(before * 2.0)


def test_再生月と天井は_ungated_yen_と同じ数():
    rows = _rows()
    d = trend.ungated_yen(rows)
    k = sponsor.kit(rows)
    assert k["views_month"] == pytest.approx(d["views_month"])
    assert k["views_month_cap"] == pytest.approx(d["cap"]["views_month"])


# --- (2) 測っていない物を売りにしない ------------------------------------------

def test_齢が測れていない周は媒体資料から年齢の行が落ちる(monkeypatch):
    monkeypatch.setattr(trend, "audience_split", lambda *a, **k: {"measured": False})
    s = sponsor.sheet(_rows())
    assert "65歳以上" not in s
    assert "載せていません" in s


def test_齢が測れている周は年齢の行が出る_陽性対照():
    """上の検査が『いつも落ちる』で通っていないことを確かめる側。"""
    a = trend.audience_split(_rows()) or {}
    if not a.get("measured"):
        pytest.skip("この台帳では齢が測れていない（陽性対照は張れない）")
    s = sponsor.sheet(_rows())
    assert "65歳以上" in s


def test_文面はmdではなくメールの本文(monkeypatch):
    """`**` が混じると、貼った先でそのまま字として出ます。"""
    body = sponsor.letter(_rows())
    assert "**" not in body


def test_文面は値段を書かない():
    """1通目に値段を出さない（`letter` の註）。"""
    k = sponsor.kit(_rows())
    body = sponsor.letter(_rows())
    for lv in trend.YEN_LEVELS:
        assert f"{k['price'][lv]['cap']:,.0f}" not in body


def test_媒体資料と文面はどちらもPRの表示を持つ():
    """景表法・ステマ規制（`sponsor` の覆る条件 (5)・`studio/asp.py` と同じ向き）。"""
    rows = _rows()
    assert "【PR】" in sponsor.sheet(rows)
    assert "【PR】" in sponsor.letter(rows)


# --- (3) 口を読んでいない相手を混ぜない ----------------------------------------

def test_読んだ相手だけがchecked_targetsに入る():
    got = sponsor.checked_targets()
    assert got, "口を読んだ相手が 0社 なら、オーナーに出せる行が 1つ もありません"
    assert all(t["checked"] for t in got)
    assert len(got) <= len(sponsor.TARGETS)


def test_読んだと書いた相手は出どころに日付を持つ():
    for t in sponsor.checked_targets():
        assert t["src"] != "未読"
        assert "2026-" in t["src"], f"{t['name']} の出どころに読んだ日がありません"


def test_読んでいない相手は宛先に未確認の札を立てる():
    for t in sponsor.TARGETS:
        if not t["checked"]:
            assert "未確認" in t["route"]


def test_短い行は_まだ送っていないことを言う():
    line = sponsor.short(_rows())
    assert line
    assert "0社" in line or "まだ 1社 も送っていません" in line
