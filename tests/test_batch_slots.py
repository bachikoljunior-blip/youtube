"""「1日にN本」を置けるか、そして**測定の窓を踏まないか**を検査する。

M14（`docs/MEANS.md`）は本数の段を 2 → 4 → 8 と上げる手ですが、
`--hour` は「その時刻で最初に空いている**日**」を返すので、
8本ぶん呼ぶと **8日にばらけて 1日1本の実験になります。**
段を上げる道そのものが無かった、というのがここで塞いだ穴です。

窓の検査も一緒に置いてあります。「実験の窓を踏まないこと」は文書に3か所
書いてありましたが、**守っていたのは毎回こちらの記憶**でした。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.batch_build import check_window, ledger_hours, slots  # noqa: E402
from src.uploader import JST, next_publish_at  # noqa: E402


# --- slots: 1日にN本を置けるか -------------------------------------------
#
# **`taken=` を必ず渡すこと**（2026-08-17）。渡さないと `ledger_hours()` が
# `data/uploaded.jsonl` を読むので、**検査の答えが実物の予約で変わります。**
# 空き時刻を読む側そのものは、下の「控えから空きを読む」で別に検査しています。

def test_no_date_keeps_old_behaviour():
    """日付を渡さなければ従来どおり。全部同じ時刻＝1日ずつ後ろへ積まれる。"""
    assert slots(3, 9, None, []) == ["9", "9", "9"]


def test_date_spreads_hours_on_one_day():
    """日付を渡すと、**同じ日**の別々の時刻になる。これが8の段。"""
    assert slots(4, 10, "2026-08-24", [], taken=set()) == [
        "2026-08-24@10", "2026-08-24@11", "2026-08-24@12", "2026-08-24@13",
    ]


def test_explicit_hours_win():
    assert slots(2, 9, "2026-08-24", [14, 20], taken=set()) == [
        "2026-08-24@14", "2026-08-24@20",
    ]


def test_hours_are_trimmed_to_count():
    assert slots(2, 9, "2026-08-24", [1, 2, 3], taken=set()) == [
        "2026-08-24@1", "2026-08-24@2",
    ]


def test_too_few_hours_is_refused():
    with pytest.raises(SystemExit):
        slots(3, 9, "2026-08-24", [10, 11], taken=set())


def test_duplicate_hours_are_refused():
    """同じ時刻に2本置くと食い合う（`next_publish_at` の元の理由と同じ）。"""
    with pytest.raises(SystemExit):
        slots(2, 9, "2026-08-24", [10, 10], taken=set())


def test_hour_out_of_range_is_refused():
    """明示した時刻が 0〜23 の外。**自動で選ぶ側はもう外に出ません**（下）。"""
    with pytest.raises(SystemExit):
        slots(2, 9, "2026-08-24", [23, 24], taken=set())


# --- 控えから空きを読む（2026-08-17。**3回持ち越された穴**）----------------
#
# ここは `hour + i` で、**その日に何が置いてあるかを一度も見ていませんでした。**
# 埋まった時刻に当たると `upload_only.py` が「翌日へは送りません」で落ち、
# **作った1本がそのまま捨てられます**（`build/` はコンテナと一緒に消える）。
# 避ける道は「人が予約一覧を見て `--hours` に手で写す」だけで、
# 申し送りは3回とも「手写しである限り、ぶつけて1本捨てる回が出る」と言っていました。

def test_taken_hours_are_skipped():
    """埋まっている時刻を飛ばして、**その日の空きだけ**を返す。

    実物（2026-08-17 の控え）の 09-01 と同じ形: 9,10,12〜16 が埋まり → 空きは 11。
    既定の `hour + i` なら 9,10 とぶつけて**先頭2本を捨てていた**。
    """
    got = slots(1, 9, "2026-09-01", [], taken={9, 10, 12, 13, 14, 15, 16})
    assert got == ["2026-09-01@11"]


def test_taken_hours_skipped_for_several():
    got = slots(3, 9, "2026-08-24", [], taken={9, 11, 13})
    assert got == ["2026-08-24@10", "2026-08-24@12", "2026-08-24@14"]


def test_not_enough_free_hours_is_refused():
    """**足りないなら作る前に止める。** 作ってから落ちると1本まるごと捨てます。"""
    with pytest.raises(SystemExit):
        slots(3, 22, "2026-08-24", [], taken={23})


def test_explicit_hours_pass_through_a_clash(capsys):
    """明示した時刻は通す（控えは上限側で、取り消し済みの枠がある）。**ただし言う。**"""
    assert slots(1, 9, "2026-08-24", [10], taken={10}) == ["2026-08-24@10"]
    assert "控えでは埋まっています" in capsys.readouterr().out


def test_ledger_hours_reads_jst_hour_of_the_day(monkeypatch):
    """控えの `at` は UTC。**JST の時に直してから**その日のぶんだけ拾う。"""
    from scripts import batch_build as bb

    rows = [
        {"at": "2026-09-01T00:00:00Z"},   # JST 09-01 09:00  ← 拾う
        {"at": "2026-09-01T07:00:00Z"},   # JST 09-01 16:00  ← 拾う
        {"at": "2026-09-01T15:00:00Z"},   # JST 09-02 00:00  ← 別の日
        {"at": "2026-08-31T14:00:00Z"},   # JST 08-31 23:00  ← 別の日
        {"topic": "at が無い行"},          # ← 落とす
    ]
    monkeypatch.setattr(bb.dupes, "ledger_rows", lambda: rows)
    assert ledger_hours("2026-09-01") == {9, 16}


def test_ledger_failure_does_not_stop_the_round(monkeypatch, capsys):
    """**この道具のために回を止めない。** 読めなければ空集合＝従来どおりの動き。"""
    from scripts import batch_build as bb

    def boom():
        raise OSError("控えが壊れている")

    monkeypatch.setattr(bb.dupes, "ledger_rows", boom)
    assert ledger_hours("2026-09-01") == set()
    assert "続行" in capsys.readouterr().out


# --- check_window: 測定の窓を機械に持たせる -------------------------------

@pytest.mark.parametrize("date", ["2026-08-16", "2026-08-20", "2026-08-23"])
def test_window_blocks(date):
    with pytest.raises(SystemExit):
        check_window(date, force=False)


@pytest.mark.parametrize("date", ["2026-08-15", "2026-08-24", "2026-09-01"])
def test_outside_window_passes(date):
    check_window(date, force=False)


def test_force_window_passes():
    check_window("2026-08-20", force=True)


# --- next_publish_at: 日付の釘づけ ---------------------------------------

def _future_date(days: int) -> str:
    return (datetime.now(JST) + timedelta(days=days)).strftime("%Y-%m-%d")


def test_pinned_date_is_returned_as_is():
    day = _future_date(9)
    got = next_publish_at(10, 0, taken=set(), date_jst=day)
    want = datetime.strptime(f"{day} 10:00", "%Y-%m-%d %H:%M") \
        .replace(tzinfo=JST).astimezone(timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    assert got == want


def test_pinned_date_does_not_slide_when_taken():
    """**埋まっていても翌日へ送らない。** 送ると「1日8本」が7本+1本に化ける。"""
    day = _future_date(9)
    taken = {next_publish_at(10, 0, taken=set(), date_jst=day)}
    with pytest.raises(ValueError):
        next_publish_at(10, 0, taken=taken, date_jst=day)


def test_pinned_past_date_is_refused():
    with pytest.raises(ValueError):
        next_publish_at(10, 0, taken=set(), date_jst=_future_date(-1))


def test_pinned_bad_date_is_refused():
    with pytest.raises(ValueError):
        next_publish_at(10, 0, taken=set(), date_jst="8/24")


def test_unpinned_still_slides_a_day():
    """日付を渡さない側の動きは変えていない（作り置きが重ならない）。"""
    first = next_publish_at(10, 0, taken=set())
    second = next_publish_at(10, 0, taken={first})
    assert second != first
    a = datetime.strptime(first, "%Y-%m-%dT%H:%M:%SZ")
    b = datetime.strptime(second, "%Y-%m-%dT%H:%M:%SZ")
    assert (b - a) == timedelta(days=1)
