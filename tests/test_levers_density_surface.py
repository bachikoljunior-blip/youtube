"""**`density` の「天井」が、どの面の話かを名乗ること。**（2026-08-26 に足した）

`scripts/eta.py` の `physical_caps` は `density` の天井を
`day_cap.cap()`（＝**ショートの面**で1日に再生が付く本数）で立てています。
**長尺はその枠を1つも使いません**し、**4,000時間の門に入るのは長尺だけ**です。

だから「密度は天井 ×1.00 ＝ 引き代なし」は、**唯一開いている門について
何も言っていません。** それでも `levers.py` はこれを見て `density` を
「死んだ腕」に入れるので、**長尺を増やす作業が `none` に見えていました。**

**数字は足しません**（長尺の面の上限は未測定なので、足せば推測を実測に
見せることになります）。**名前だけ正します。**
"""
from __future__ import annotations

from src import levers


def _row(density_cap: float = 1.0) -> dict:
    return {"arm_caps": {"per_video": 2.9, "density": density_cap},
            "arm_reaches": {"per_video": True, "density": True},
            "lever_hint": "per_video"}


def test_密度の天井はショートの面だと名乗る():
    st = levers.arm_state(_row())
    why = st["dead_why"].get("density")
    assert why, "density が死んだ腕に入っていません（前提が変わりました）"
    assert "ショートの面" in why
    assert "長尺の面は未測定" in why


def test_天井が生きている腕には付かない():
    st = levers.arm_state(_row(density_cap=3.0))
    assert "density" not in st["dead_why"]


def test_密度を選んだ回に長尺の断りが出る():
    st = levers.arm_state(_row())
    text = "\n".join(levers.lever_notes("density", st))
    assert "長尺はその枠を1つも使いません" in text
    assert "4,000時間の門に入るのは長尺だけ" in text
    assert "`none` へ落とさないこと" in text


def test_ほかの腕には長尺の断りが出ない():
    st = levers.arm_state({"arm_caps": {"rpm": 1.0}, "arm_reaches": {"rpm": True}})
    text = "\n".join(levers.lever_notes("rpm", st))
    assert "長尺" not in text, "density 以外にも長尺の話が漏れています"


def test_読めないときは未測定の側へ倒す(monkeypatch):
    """**分からないときは、分からないと言う側へ。**

    ここで True に倒すと、測っていないものを「天井」として黙らせることになります。
    """
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if name == "src" and a and "day_cap" in (a[2] or ()):
            raise ImportError("読めない環境")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", boom)
    assert levers._long_surface_measured() is False


def test_実物でも未測定のまま():
    """長尺の面の上限を測ったと言い出したら、この検査が落ちます。

    落ちたのが**本当に測れたから**なら、`src/day_cap.long_form()` の
    `measured` を見直したうえで、この検査ごと書き換えること。
    """
    assert levers._long_surface_measured() is False
