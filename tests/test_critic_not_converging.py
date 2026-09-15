# -*- coding: utf-8 -*-
"""`critic.not_converging` —— **輪が閉じない側の門**（2026-09-15 19:1x・optimizer）。
derivation と覆る条件は `studio/critic.py` の同名の段。

**陽性対照 2つ**（この検査が本当に門を見ているかを見る口）:
  (A) 門を 99 へ上げると、同じ台帳で「閉じてよい」が消える
  (B) 1番目が `nitpick` の周には、何回 積んでも立たない（`loop_done` の側が先に閉じる）
"""
from studio import critic


def _rows(vid, sigs, where="コマ1"):
    return [{"event": "critique", "id": vid, "sig": s,
             "wheres": [{"where": where, "sev": "real"}, {"where": "コマ9", "sev": "nitpick"}]}
            for s in sigs]


def _c(where="コマ1", sev="real"):
    return {"items": [{"where": where, "severity": sev}, {"where": "コマ9", "severity": "nitpick"}]}


def test_同じ所が別々の本文で門の数だけ立ったら閉じてよい():
    rows = _rows("v", ["2:aaa", "2:bbb", "2:ccc"])
    ok, why = critic.not_converging("v", _c(), rows)
    assert ok and "3つ" in why


def test_同じ本文で何度_立っても閉じない():
    """指紋が同じ ＝ 直していない ＝ 同じ所が挙がるのは当たり前（閉じない理由にならない）。"""
    rows = _rows("v", ["2:aaa"] * 9)
    ok, _ = critic.not_converging("v", _c(), rows)
    assert not ok


def test_門の手前では閉じない():
    rows = _rows("v", ["2:aaa", "2:bbb"])
    ok, _ = critic.not_converging("v", _c(), rows)
    assert not ok


def test_別の所が立った周には門は当たらない():
    rows = _rows("v", ["2:aaa", "2:bbb", "2:ccc"], where="コマ1")
    ok, _ = critic.not_converging("v", _c("コマ22"), rows)
    assert not ok


def test_他の本の行は数えない():
    rows = _rows("other", ["2:aaa", "2:bbb", "2:ccc"])
    ok, _ = critic.not_converging("v", _c(), rows)
    assert not ok


def test_書き方の違う_where_は同じコマへ畳む():
    rows = (_rows("v", ["2:aaa"], "コマ1〜3（全体の構造）")
            + _rows("v", ["2:bbb"], "コマ1-2")
            + _rows("v", ["2:ccc"], "コマ1冒頭"))
    ok, _ = critic.not_converging("v", _c(), rows)
    assert ok


def test_陽性対照A_門を上げると閉じない(monkeypatch):
    rows = _rows("v", ["2:aaa", "2:bbb", "2:ccc"])
    monkeypatch.setattr(critic, "REPEAT_GATE", 99)
    ok, _ = critic.not_converging("v", _c(), rows)
    assert not ok


def test_陽性対照B_1番目が言いがかりの周は門の外():
    rows = _rows("v", ["2:aaa", "2:bbb", "2:ccc"])
    ok, _ = critic.not_converging("v", _c(sev="nitpick"), rows)
    assert not ok
    assert critic.loop_done(_c(sev="nitpick"))


def test_比べる2つの問いは在るときに挙げさせない():
    """09/15 15:0x に足した字が **在るものを「無い」と挙げさせていた**（7周 閉じなかった当のもの）。"""
    import inspect

    from studio import script
    s = script.load("2026-09-16-65sai-hokenryo-moto")
    src = inspect.getsource(critic.critique)
    assert "言われている場合は、この項目を挙げないでください" in src
    assert "65歳でやめる人と、70歳まではたらく人を比べます" in s.segments[0].say
