"""**`--anyway` は、機械が自分で反証ずみの枠までは買えない**（`src.daily_pick.anyway_pays_hold`）。

2026-09-05 04:xx・最適化の回。実物の `data/daily_pick.jsonl` 09-05T01:48 は
`anyway: 枠の機会費用 1,049回 を下回るのは承知の上。買っているのは再生ではなく前提`
で `path_form_hold` を越えていました。**その「前提」の当たりの門を
`win_pays_for_slot()` が既に否定して印字していた**のに、`--anyway` の条件が
「数字を1つ含む1行」だけだったので通っています。
"""
from datetime import date, datetime, timezone

import pytest

from src import daily_pick as dp


def _short(*_a, **_k):
    return ("ショート", "道 ショート ＝ ×106・道 長尺 ＝ ×334")


def _none(*_a, **_k):
    return (None, "")


def _cannot_pay(_give_up):
    return ["[数] 当たりの門 100回 ＜ 譲る ショート の中央値 164回"]


def _can_pay(_give_up):
    return []


def test_門の算と違う形は_当たっても払えないなら止まる():
    msg = dp.anyway_pays_hold("長尺", form_call=_short, win_call=_cannot_pay)
    assert msg
    assert "`--anyway` では越えられません" in msg
    assert "ショート" in msg


def test_当たれば払える実験なら_anyway_は通る():
    """**門は緩めていません** —— 払える実験は `--anyway` で買ってよい。"""
    assert dp.anyway_pays_hold("長尺", form_call=_short, win_call=_can_pay) == ""


def test_門の算が指す形そのものは止めない():
    assert dp.anyway_pays_hold("ショート", form_call=_short, win_call=_cannot_pay) == ""


def test_比べる相手が無い回は止めない():
    """`data/shorts_subs.json` が立たず `and_path_form()` が `None` の回。**推測で止めない。**"""
    assert dp.anyway_pays_hold("長尺", form_call=_none, win_call=_cannot_pay) == ""


def test_形の名前を決め打ちしていない():
    """門の算が長尺を指す日が来たら、**ショートのほうを**止める。"""
    def _long(*_a, **_k):
        return ("長尺", "道 長尺 ＝ ×10・道 ショート ＝ ×99")

    assert dp.anyway_pays_hold("ショート", form_call=_long, win_call=_cannot_pay)
    assert dp.anyway_pays_hold("長尺", form_call=_long, win_call=_cannot_pay) == ""


def test_知らない形は止めない():
    assert dp.anyway_pays_hold("横長", form_call=_short, win_call=_cannot_pay) == ""


def test_算が例外でも止めない():
    def _boom(*_a, **_k):
        raise RuntimeError("読めない")

    assert dp.anyway_pays_hold("長尺", form_call=_boom, win_call=_cannot_pay) == ""
    assert dp.anyway_pays_hold("長尺", form_call=_short, win_call=_boom) == ""


def test_record_が_anyway_ごしに断る(monkeypatch, tmp_path):
    """**止めは `record()` の中で立つ** —— 印字ではなく `raise`。"""
    monkeypatch.setattr(dp, "anyway_pays_hold", lambda *a, **k: "止めた（数 100 ＜ 164）")
    monkeypatch.setattr(dp, "path_form_hold", lambda *a, **k: "")
    monkeypatch.setattr(dp, "probe_hold", lambda *a, **k: "")
    monkeypatch.setattr(dp, "restated_pick_block", lambda *a, **k: "")
    with pytest.raises(ValueError, match="止めた"):
        dp.record("長尺", "topic-x", "理由 1件",
                  day=date(2026, 9, 5), video_id="vid", expected=500,
                  anyway="機会費用 1,049回 は承知の上",
                  now=datetime(2026, 9, 5, 4, 0, tzinfo=timezone.utc))


def test_実物の_anyway_の文面では通らない():
    """**実物 09-05T01:48 の `anyway` は数字を含むが、それでは足りない。**"""
    real = "枠の機会費用 1,049回 を下回るのは承知の上。買っているのは再生ではなく前提"
    import re
    assert re.search(r"\d", real)            # 旧い口の条件は満たしている
    assert dp.anyway_pays_hold("長尺", form_call=_short, win_call=_cannot_pay)
