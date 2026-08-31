"""`lever_days` —— **腕を「同じ倍率」だけで並べると、答えが「出ません」に固定される。**

## なぜ要るか（2026-08-25 の実測）

`scripts/eta.py` の `lever_days()` は、腕を1つずつ **`LEVER_FACTOR`（＝×2）**
にして予測を解き直し、`plan()` がその最大値で `lever_hint`（＝**その回に引く腕**）を
上書きする作りでした。上書きの条件は `if best["gain"] > 0:` です。

**その分岐は、書かれた 8/20 から 8/25 まで一度も走っていません。**

    合格点は ×2.61 足りない（1本あたり 638回 → 要る 1,667回）
    → 2.0 < 2.61 なので、**どの腕を ×2 にしても「届きません」**
    → `gain` は4本とも 0.0 → 上書きは起きない

つまり表は**構造として肯定的な答えを返せません**でした。毎周
`それでも出ません` を4行印字して、読み手に「どの腕でも届かない」という
**誤った印象**を渡していました。実際は、同じファイルの `physical_caps()` が
腕ごとの天井を計算していて、そこまで引けば届きます:

    per_video  天井 ×2.96     → 212日（届く）／日付が出はじめるのは ×2.62 から
    rpm        天井 ×70.20    → 510日（届く）／同上
    sub_rate   天井 ×2,923.79 → **届かない**（再生の天井に触らない腕）
    density    天井 ×1.00     → **引き代なし**（すでに上限を 1.3倍 超えて出している）

**天井は同じファイルの中にありました。この関数が読んでいなかっただけです。**

## ここで固定するもの

1. **同じ倍率が届かない回でも、天井の側は答えを出す**（表が沈黙しない）
2. **天井に着いている腕（×1.00）は、選ばれない**
3. **`threshold`（日付が出はじめる倍率）は `cap` とも `factor` とも別の数**
4. **天井が1つも測れていない回は、同じ倍率の差へ落ちる**（上書きごと消さない）
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_lever_cap_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

import _eta_pin  # noqa: E402


@pytest.fixture(autouse=True)
def _天井は主題ではない(monkeypatch):
    """**実測から来る天井は止める。** ここの主題は「天井を読むかどうか」で、
    天井の値そのものではありません（`tests/_eta_pin.py`）。"""
    _eta_pin.pin_ceilings(monkeypatch, eta.UPLOAD_CAP_PER_DAY, eta)


def _metrics(**kw) -> dict:
    m = {
        "views_7d": 8_800, "views_28d": 20_300,
        "subs_gained_28d": 9, "subs_net": 9,
        "long_hours_365": 0.1, "shorts_views_90d": 22_515,
        "views_per_video": 923, "median_views_per_video": 1_041,
        "long_per_video": 2, "long_videos_28d": 5, "long_views_28d": 11,
    }
    m.update(kw)
    return m


def _supply(rate: float = 13.0) -> dict:
    return {"stock": 37, "novel": 494, "rate_per_day": rate,
            "rate": {"per_day": rate, "thin": False}, "measured": True,
            "sweep_age_hours": 1.0}


def _rows(caps, factor=eta.LEVER_FACTOR):
    m = _metrics()
    a = eta.analyse(m)
    pl0 = eta.plan(m, a, supply=_supply(), sensitivity=False)
    return pl0, eta.lever_days(m, a, pl0=pl0, supply=_supply(),
                               factor=factor, caps=caps)


CAPS = {"per_video": 3.0, "rpm": 70.0, "sub_rate": 2_900.0, "density": 1.0}


def test_同じ倍率が届かない回でも天井の側は答えを出す():
    """**これが 8/20〜8/25 に起きていたことです。**

    倍率を「日付が出はじめる境目」より下に置くと、同じ倍率の側は4本とも 0 ——
    旧実装はここで沈黙し、`plan()` の上書きも走りませんでした。
    **境目は実測から取ります**（定数で書くと、次に天井が動いた回に嘘になる）。
    """
    _, rows = _rows(CAPS)
    thr = [r["threshold"] for r in rows if r["threshold"]]
    assert thr, "天井まで引いても1本も届かないなら、この検査の前提が崩れています"
    below = min(thr) * 0.9        # **境目のすぐ下**

    _, rows2 = _rows(CAPS, factor=below)
    assert all(r["gain"] == 0.0 for r in rows2), (
        "同じ倍率の側は、この倍率では1本も届かないはず"
        f"（倍率 {below:.3f} / 境目 {min(thr):.3f}）")
    assert any(r["gain_at_cap"] > 0.0 for r in rows2), (
        "**天井の側まで黙ったら、表は何も言っていません。**"
        " `physical_caps` が同じファイルにあるのに読んでいない状態です")


def test_天井に着いている腕は選ばれない():
    """`density` の天井 ×1.00 ＝ **すでに上限を超えて出している**（引き代なし）。
    ここに前提を置いても到達日は1日も動きません。**先頭に来てはいけません。**"""
    _, rows = _rows(CAPS)
    d = next(r for r in rows if r["lever"] == "density")
    assert d["at_ceiling"] is True
    assert d["gain_at_cap"] == 0.0
    assert d["days_at_cap"] >= eta.NEVER
    assert rows[0]["lever"] != "density", "引き代のない腕が先頭に来ています"


def test_日付が出はじめる倍率は天井とも同じ倍率とも別の数():
    """**3つ目の数が要る理由。** 「天井まで引けば届く」と「あと何倍で景色が変わるか」は
    別の問いです。`threshold` が無いと、読み手は天井（×70）を見て
    「遠い」と読みますが、実際に要るのはその **1/38**（×1.8）だったりします。"""
    _, rows = _rows(CAPS)
    r = next(r for r in rows if r["lever"] == "rpm")
    assert r["reachable_at_cap"]
    thr = r["threshold"]
    assert thr is not None
    assert 1.0 < thr <= r["cap"]
    # **境目の下では出ず、上では出ること。**（挟み込みが本物であること）
    m, a = _metrics(), None
    a = eta.analyse(m)
    pl0 = eta.plan(m, a, supply=_supply(), sensitivity=False)

    def days(f):
        a2 = eta.analyse(m, points=None, scale={"rpm": f})
        return eta.plan(m, a2, supply=_supply(), sensitivity=False
                        ).get("days_to_target", eta.NEVER)

    assert days(thr * 1.05) < eta.NEVER
    assert days(thr * 0.90) >= eta.NEVER
    del pl0


def test_天井が測れていない回は同じ倍率の差へ落ちる():
    """**上書きごと消さないこと。** `gain_at_cap` が全部 0 になった環境で
    黙って上書きを止めると、`lever_hint` は床の名前（＝診断）に戻ります ——
    それは 8/20 に直したはずの状態です。"""
    m = _metrics()
    a = eta.analyse(m)
    pl = eta.plan(m, a, supply=_supply(), sensitivity=True)
    assert pl["lever_chosen_by"] in ("gain_at_cap", "gain")
    assert pl["lever_hint"] == max(pl["lever_days"],
                                   key=lambda r: r[pl["lever_chosen_by"]])["lever"]

    # 天井を1つも渡さない ＝ 測れていない回
    pl0 = eta.plan(m, a, supply=_supply(), sensitivity=False)
    rows = eta.lever_days(m, a, pl0=pl0, supply=_supply(),
                          caps={k: None for k in eta.LEVERS})
    assert all(r["gain_at_cap"] == 0.0 for r in rows)
    assert all(r["cap"] is None for r in rows)
    # 同じ倍率の差が残っていること（＝落ちる先がある）
    assert any(r["gain"] > 0.0 for r in rows) or pl0["days_to_target"] < eta.NEVER


def test_表に天井の行が出る():
    """**印字まで届いていること。** 計算しても出さなければ、選ぶ側には届きません
    （8/24 の `drift.py` の註「この数は eta.py の stdout にしか無く、
    選ぶ側に届いていません」と同じ壊れ方を、こちら側で作らない）。"""
    m = _metrics()
    a = eta.analyse(m)
    pl = eta.plan(m, a, supply=_supply(), sensitivity=True)
    text = "\n".join(eta._report_levers(pl))
    assert "天井" in text
    dead = [r for r in pl["lever_days"]
            if r.get("cap") is not None and not r.get("reachable_at_cap")]
    if dead:
        # **ここは長らく「上の日付を動かせない腕」と主張していました**（2026-08-26 に直した）。
        #     その文言は偽です —— 同じ日・同じ点で `eta.py --alloc` が
        #     「**次の1件は `sub_rate` に置くのが最短**（3日 早い）」と出しており、
        #     実測でも `sub_rate` を凍らせると軌跡は **+120日**（＝必要な腕）。
        #     **十分でないことは、要らないことではありません。**
        assert "だけ**を天井まで引いても届かない腕" in text
        assert "「ここに前提を置いても動かない」ではありません" in text
        # **凍らせた線が無い回は、「要らない」と読ませないこと。**
        assert "『要らない』と読まないこと" in text


def test_凍らせた線があれば_必要な腕と要らない腕を言い分ける():
    """**判別は、測ればつきます**（`frozen_days`）。実測 2026-08-26:

        `sub_rate` を凍らせる → 軌跡 **+120日** ＝ 必要
        `density`  を凍らせる → 軌跡 **+0日**   ＝ 要らない

    **同じ1行にまとめて「動きません」と書いていたのが誤り**でした ——
    片方については偽、もう片方については真です。
    """
    m = _metrics()
    a = eta.analyse(m)
    pl = eta.plan(m, a, supply=_supply(), sensitivity=True)
    dead = [r["lever"] for r in pl["lever_days"]
            if r.get("cap") is not None and not r.get("reachable_at_cap")]
    if not dead:
        return
    pl["arm_frozen_days"] = {dead[0]: 120.0}
    if len(dead) > 1:
        pl["arm_frozen_days"][dead[1]] = 0.0
    text = "\n".join(eta._report_levers(pl))
    assert "+120日" in text and "必要な腕です" in text
    if len(dead) > 1:
        assert "この腕は要りません" in text
