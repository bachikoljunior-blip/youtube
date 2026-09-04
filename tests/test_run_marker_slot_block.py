"""**きょう出る1本が、きょうの決めと違ううちは、回を閉じさせないこと。**

## なぜ要るか（2026-09-05 06:0x・最適化の回。**実物で踏んだ**）

09/05 の実測 —— 決めは同じ日のうちに **6回** 書き換わり、**枠は 0回** 動いた。
09:00 の枠に立っていたのは `GFvAcxvDmYM`（**22分42秒 の長尺**・見込み 齢48h **1回**）で、
決めは `TfetZ_qhS-E`（ショート・同 **164回**）。公開まで **3時間8分**。**164 対 1** ——
きょうチャンネルが出す唯一の1本。

決めを**書く**側には門が6つ（`daily_pick.record()` の `slot_cost` / `probe_hold` /
`path_form_hold` / `anyway_pays_hold` / `restated_pick_block` / `day_guard`）。
**押す**側には1つも無かった。書くほうは API 0単位・自分の手だけで終わり・commit になる。
押すほうは 100単位 掛かり、相手が居る。**門が片側にだけ生えたのは、その非対称のとおり。**

`slot_gate.mismatch_lines()` は 05:4x に**印字**として入った。その 12分後にも枠は同じ。
`run_marker` が自分の註に2度 書いているとおり ——
**「註や警告ではなく、通さないことだけが効いています」**。

**この検査は時計を読みません**（`tests/test_tests_are_clockless.py`）—— 判定の行は注入する。
"""

from __future__ import annotations

import datetime as _dt

import scripts.run_marker as rm
import scripts.slot_gate as sg

MISMATCH = ["**09/05（JST）は、決めと枠が食い違っています** —— 決め `A` ／ 枠に居るのは `B`"]


def _block(monkeypatch, lines):
    monkeypatch.setattr(rm, "_today_slot_block", lambda *a, **k: list(lines))


def test_mismatch_refuses_the_ship(monkeypatch, capsys):
    """食い違ったままの回は **通らない**（`return 2`）。"""
    _block(monkeypatch, MISMATCH)
    rc = rm.ship("枠を見ずに閉じようとした回", kind="fix", moves=0)
    out = capsys.readouterr().out
    assert rc == 2, "食い違いが在るのに通った"
    assert "断りました" in out and "決めと枠が食い違" in out
    # **撃てる手が文面に出ること**（印字だけの門に戻さないため）
    assert "reschedule.py" in out


def test_no_mismatch_does_not_block(monkeypatch, capsys):
    """合っている日は、この門は**何も言わない**（空振りで回を止めない）。"""
    _block(monkeypatch, [])
    rm.ship("ふつうの回", kind="fix", moves=0)
    assert "きょう出る1本が" not in capsys.readouterr().out


def test_helper_never_raises(monkeypatch):
    """判定側が壊れても、門は**黙る**（自分の事故で回を止めない）。"""
    monkeypatch.setattr(
        sg, "today_block", lambda *a, **k: (_ for _ in ()).throw(RuntimeError))
    assert rm._today_slot_block() == []


def test_today_block_is_today_only():
    """**きょうだけ**を見ること —— 明日ぶんで止めると、まだ押せる日の回まで止まる。"""
    today = _dt.date(2026, 9, 5)
    rows = [
        {"id": "B", "at": "2026-09-05T00:00:00+00:00", "topic": "t1", "title": ""},
        {"id": "D", "at": "2026-09-06T00:00:00+00:00", "topic": "t2", "title": ""},
    ]
    picked = {
        today: {"video_id": "A", "form": "ショート", "expected_48h": 164.0},
        today + _dt.timedelta(days=1): {"video_id": "C", "form": "ショート",
                                        "expected_48h": 164.0},
    }
    got = sg.today_block(rows=rows, today=today, picked=picked, published=set())
    assert any("09/05" in ln for ln in got), "きょうの食い違いを見落とした"
    assert not any("09/06" in ln for ln in got), "あすの食い違いまで拾っている"


def test_mark_is_one_source():
    """語は `slot_gate` の1か所から来ること（**写しを持たない**）。"""
    rm._today_slot_block()
    assert rm.SLOT_MISS_MARK == sg.SLOT_MISS_MARK


def test_mark_lets_it_through(monkeypatch, capsys):
    """押せない回は、印と理由を書けば**この門は**越えられる（**禁止ではない**）。

    先の門で止まるかどうかはここの担当ではないので、
    **この門の文面が出ないこと**だけを見る（控えには書かせない）。
    """
    _block(monkeypatch, MISMATCH)
    monkeypatch.setattr(rm, "_append", lambda rec: "")
    rm.ship(f"{rm.SLOT_MISS_MARK}: 日枠が尽きて 50単位 が撃てない", kind="fix", moves=0)
    assert "きょう出る1本が、きょうの決めと違います" not in capsys.readouterr().out
