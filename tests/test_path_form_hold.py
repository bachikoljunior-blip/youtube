"""**門の算（AND の道）と違う形の決めが、印字ではなく実際に止まること。**

2026-09-05 02:xx・最適化の回。「最適化されてんの？」→ **いいえ** の理由を1つ潰した検査。
実測（`scripts/optimized.py` と `data/daily_pick.jsonl`）: 決め 39件中 **31件が長尺**、
`and_path_form()` はこの回に撃って **ショート**（道 ×106 対 ×334）、齢48h の中央値は
**長尺 1回 ／ ショート 168回**。`standing_form_conflict()` はその食い違いを
2026-09-04 から印字していましたが、**`record()` は渡された形をそのまま書いていました**。
"""
from __future__ import annotations

import datetime
import json

import pytest

from src import daily_pick as dp
from src import slot_cost

WHY = "この回に撃った数 1件"


def _short(**_kw):
    return "ショート", "AND の道: 道 ショート ＝ ×106・道 長尺 ＝ ×334"


def test_算と違う形は止まる():
    hold = dp.path_form_hold("長尺", form_call=_short)
    assert hold
    assert "ショート" in hold and "長尺" in hold


def test_算と同じ形は止めない():
    assert dp.path_form_hold("ショート", form_call=_short) == ""


def test_算が出せない回は止めない():
    """**推測で止めないこと。** 門1 の脚が立たない回は比べる相手が居ません。"""
    assert dp.path_form_hold("長尺", form_call=lambda **_k: (None, "脚が立たない")) == ""
    assert dp.path_form_hold("長尺", form_call=lambda **_k: (_ for _ in ()).throw(RuntimeError())) == ""


def test_形を決め打ちしていない():
    """長尺の脚が近づけば、止まるのはショートのほうです。"""
    long_call = lambda **_k: ("長尺", "道 長尺 ＝ ×10・道 ショート ＝ ×99")  # noqa: E731
    assert dp.path_form_hold("長尺", form_call=long_call) == ""
    assert dp.path_form_hold("ショート", form_call=long_call)


def _live(tmp_path, monkeypatch):
    """**本番の口**（`path` を渡さない ＝ CLI と同じ）を、控えだけ差し替えて使う。

    門は `path is None` の回にだけ立ちます（素振りでは立てない・`slot_cost` の門と同じ
    切り分け）。だから**呼び方まで本番と同じにしないと、この検査は門を通りません。**
    """
    p = tmp_path / "picks.jsonl"
    monkeypatch.setattr(dp, "PICKS", p)
    monkeypatch.setattr(dp, "and_path_form", _short)
    monkeypatch.setattr(dp, "day_guard", lambda *a, **k: "")
    monkeypatch.setattr(dp, "probe_hold", lambda *a, **k: "")
    monkeypatch.setattr(dp, "restated_pick_block", lambda *a, **k: "")
    monkeypatch.setattr(slot_cost, "verdict", lambda *a, **k: {"ok": True, "why": ""})
    # **`--anyway` の口は「当たれば枠の代金を払える実験」のときだけ開きます**
    # （`anyway_pays_hold`・2026-09-05 04:xx）。この file が試すのは
    # `path_form_hold` の口なので、**払える側に置いてから**呼びます。
    # 払えない側は `tests/test_anyway_pays_hold.py` が持ちます。
    monkeypatch.setattr(dp, "win_pays_for_slot", lambda *a, **k: [])
    return p


def test_record_が実際に止める(tmp_path, monkeypatch):
    p = _live(tmp_path, monkeypatch)
    with pytest.raises(ValueError) as e:
        dp.record("長尺", "topic", WHY, video_id="V1", expected=1.0,
                  day=datetime.date(2026, 9, 9))
    assert "門の算" in str(e.value)
    assert not p.exists() or not p.read_text(encoding="utf-8").strip()


def test_anyway_で越えられる(tmp_path, monkeypatch):
    """**固定は目標の本文だけ**（09/04 17:3x）。数字で越えた行は控えに残ります。"""
    p = _live(tmp_path, monkeypatch)
    r = dp.record("長尺", "topic", WHY, video_id="V1", expected=1.0,
                  day=datetime.date(2026, 9, 9), anyway="実測 1回 でも前提の判定を買う")
    assert r["form"] == "長尺"
    assert json.loads(p.read_text(encoding="utf-8").splitlines()[0])["anyway"]


def test_写し_carry_は通る(tmp_path, monkeypatch):
    """焼き直しの写しは決めではないので、形の門を立てません。"""
    _live(tmp_path, monkeypatch)
    r = dp.record("長尺", "topic", WHY, video_id="V2", expected=1.0,
                  day=datetime.date(2026, 9, 9), kind=dp.PICK_KIND_CARRY)
    assert r["form"] == "長尺"


def test_素振りでは立たない(tmp_path, monkeypatch):
    """`path` を渡した回（試験・素振り）は、本番の控えを守る門の外です。"""
    monkeypatch.setattr(dp, "and_path_form", _short)
    r = dp.record("長尺", "topic", WHY, path=tmp_path / "picks.jsonl",
                  video_id="V1", expected=1.0, day=datetime.date(2026, 9, 9))
    assert r["form"] == "長尺"


def test_据え置きのたびに立ち直す(tmp_path, monkeypatch):
    """**1度 越えたら以後 黙る、にはしません。** 黙ると鎖はまた無料になります。"""
    _live(tmp_path, monkeypatch)
    dp.record("長尺", "topic", WHY, video_id="V1", expected=1.0,
              day=datetime.date(2026, 9, 9), anyway="実測 1回 を承知で 1件 買う")
    with pytest.raises(ValueError):
        dp.record("長尺", "topic", WHY + "2", video_id="V1", expected=1.0,
                  day=datetime.date(2026, 9, 10))
