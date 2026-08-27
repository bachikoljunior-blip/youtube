"""**`day_cap` の切り分けの対照日を、手で写さずに守る**（`split_day_window()`）。

## なぜ要るか（2026-08-27 に足した）

`src/day_cap.py` は毎回 自分で切り分けの日を選んで印字します
（`booked_split_day()`）。`scripts/eta.py` の出力にはこう出ます:

    **その日はもう予約されています: 2026-09-02**（10本・うち 2本 が 08:59 より前）
    [!] **答えが返るまで、他の日の本数を増やさないこと** ——その日が対照です。

**守る仕掛けは `src/measure_window.py` にありました。繋がっていませんでした。**
`reschedule --spread/--compact` ／ `live_slots --apply` ／ `batch_build` の
`live_plan()` は、どれも `inside()` を見て避けます —— **`WINDOWS` に
手で書いてある日だけを。**

**同じ形で 08/24 に壊れています**（`WINDOWS` の 08-27 の項に実測）——
`reschedule --spread` が 08/27 を「上限超え」と読んで本を後ろへ送り、
窓に残ったのは **1本だけ**でした。そのときの直しは「この一覧に入れておけば
どの旗で撃っても止まる」でしたが、**入れるのが手だったので、
次の切り分けの日には引き継がれませんでした。**

**この検査が守るのは4つ**です:

1. **選んでいる側に聞くこと** —— 日付を写さない（写した瞬間に腐る）
2. **切り分いたら消えること** —— 対照日を守り続けると枠が死んだままになる
3. **読み終わったら消えること**（`until` ＝ 生きた本数を読める日）
4. **`day_cap` が読めない回は守らないこと** —— 黙って全部を守る側に倒すと
   置き先が消えて投稿が止まります
"""
from __future__ import annotations

import pytest

from src import measure_window


@pytest.fixture(autouse=True)
def _clear_cache():
    """**旗を降ろして見張ります。**

    `tests/conftest.py` は動的な窓を検査のあいだ止めています
    （適当な未来の日を定数に使う検査を巻き添えにしないため）。
    **この検査だけは、その旗を降ろして本体を見ます。**
    """
    keep = measure_window.DISABLE_DYNAMIC
    measure_window.DISABLE_DYNAMIC = False
    measure_window._SPLIT_CACHE.clear()
    yield
    measure_window._SPLIT_CACHE.clear()
    measure_window.DISABLE_DYNAMIC = keep


class _FakeDayCap:
    def __init__(self, verdict=None, first_pub="08:59", booked=None):
        self._verdict = verdict
        self._first_pub = first_pub
        self._booked = booked

    def window(self):
        return {"verdict": self._verdict, "first_pub": self._first_pub}

    def booked_split_day(self, first_pub):
        assert first_pub == self._first_pub
        return self._booked


BOOKED = {"day": "2026-09-02", "before": 2, "total": 10, "answer": "2026-09-07"}


def _install(monkeypatch, fake):
    import src

    monkeypatch.setattr(src, "day_cap", fake, raising=False)
    import sys

    monkeypatch.setitem(sys.modules, "src.day_cap", fake)


def test_選んでいる側に聞いて日付を写さないこと(monkeypatch):
    _install(monkeypatch, _FakeDayCap(booked=BOOKED))
    w = measure_window.split_day_window(today="2026-08-27")
    assert w is not None
    assert w["from"] == w["to"] == "2026-09-02"
    assert w["until"] == "2026-09-07"
    assert w["label"] == "day_cap_split"
    assert "2026-09-02" not in str(measure_window.WINDOWS), (
        "**対照日が手の一覧へ写されています。** 写した瞬間に腐ります ——"
        "次の切り分けの日は別の日です")


def test_findが動的な窓も見ること(monkeypatch):
    _install(monkeypatch, _FakeDayCap(booked=BOOKED))
    assert measure_window.find("2026-09-02", today="2026-08-27")["label"] == "day_cap_split"
    assert measure_window.inside("2026-09-02", today="2026-08-27")
    assert not measure_window.inside("2026-09-03", today="2026-08-27"), (
        "対照日の隣まで守っています。**置き先が要らぬところで減ります**")


def test_切り分いたら消えること(monkeypatch):
    """守り続けると、対照日のぶんだけ枠が死んだままになります。"""
    _install(monkeypatch, _FakeDayCap(verdict="count", booked=BOOKED))
    assert measure_window.split_day_window(today="2026-08-27") is None
    assert not measure_window.inside("2026-09-02", today="2026-08-27")


def test_読み終わったら消えること(monkeypatch):
    """`until` は「生きた本数を読める日」。**手で消す作業を残さないこと。**"""
    _install(monkeypatch, _FakeDayCap(booked=BOOKED))
    assert measure_window.split_day_window(today="2026-09-07") is not None
    measure_window._SPLIT_CACHE.clear()
    assert measure_window.split_day_window(today="2026-09-08") is None


def test_day_capが読めない回は守らないこと(monkeypatch):
    """**黙って全部を守る側に倒さないこと** —— 置き先が消えると投稿が止まります。"""

    class _Broken:
        def window(self):
            raise RuntimeError("帳面が読めません")

    _install(monkeypatch, _Broken())
    assert measure_window.split_day_window(today="2026-08-27") is None
    assert not measure_window.inside("2026-09-02", today="2026-08-27")


def test_対照日が無ければ窓を作らないこと(monkeypatch):
    _install(monkeypatch, _FakeDayCap(booked=None))
    assert measure_window.split_day_window(today="2026-08-27") is None


def test_理由に本数と時刻が入っていること(monkeypatch):
    """**止められた側が、なぜ止まったかを読めること。**"""
    _install(monkeypatch, _FakeDayCap(booked=BOOKED))
    why = measure_window.split_day_window(today="2026-08-27")["why"]
    assert "10本" in why and "2本" in why and "08:59" in why, (
        f"止めた理由に実測が入っていません: {why}")
    assert "2026-09-07" in why, "読める日が書かれていません"


def test_手の一覧のほうが先に当たること(monkeypatch):
    """**同じ日に両方が当たったら、理由の細かい手の一覧を返すこと。**"""
    _install(monkeypatch, _FakeDayCap(
        booked={**BOOKED, "day": measure_window.WINDOWS[0]["from"]}))
    hit = measure_window.find(measure_window.WINDOWS[0]["from"],
                              today=measure_window.WINDOWS[0]["from"])
    assert hit["label"] == measure_window.WINDOWS[0]["label"]
