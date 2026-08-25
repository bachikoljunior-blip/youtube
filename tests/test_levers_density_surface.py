"""**`density` の「天井」が、どの面の話かを名乗り、面ごとに割れること。**

`scripts/eta.py` の `physical_caps` は `density` の天井を
`day_cap.cap()`（＝**ショートの面**で1日に再生が付く本数）で立てています。
**長尺はその枠を1つも使いません**し、**4,000時間の門に入るのは長尺だけ**です。

だから「密度は天井 ×1.00 ＝ 引き代なし」は、**唯一開いている門について
何も言っていません。**

## 2026-08-26 に、ここが1段すすみました（**3回続けて申し送られていた**）

**8/26 の最初の版は「名前だけ正す」でした。** `dead_why["density"]` の文言を
「天井（ショートの面だけ…）」に替えただけで、**`density` は「死んだ腕」に
入ったまま**です。だから `--ship --lever density` はいまも叱られ、
**長尺を増やした回が `none` を選び直す**形が3周つづきました
（`retro.py` の持ち越し `physical_caps` / `density`）。

いまは `scripts/eta.py` が `density_surfaces`（面ごとの `at_ceiling`）を
`data/eta.jsonl` に積み、**長尺の面が開いているあいだ `density` を殺しません。**
**数は作っていません** —— 長尺の側の天井は `sub_rate` と同じ
**定義上の上限**で、`measured: False` のまま `LEVERS` にも入れていません
（軌跡に歩かせない）。
"""
from __future__ import annotations

from src import levers


def _row(density_cap: float = 1.0, *, surfaces: dict | None = None) -> dict:
    row = {"arm_caps": {"per_video": 2.9, "density": density_cap},
           "arm_reaches": {"per_video": True, "density": True},
           "lever_hint": "per_video"}
    if surfaces is not None:
        row["density_surfaces"] = surfaces
    return row


CLOSED = {"short": {"at_ceiling": True, "measured": True},
          "long": {"at_ceiling": True, "measured": True}}
OPEN = {"short": {"at_ceiling": True, "measured": True},
        "long": {"at_ceiling": False, "measured": False}}


def test_両方の面が閉じたときだけ死んだ腕に入る():
    st = levers.arm_state(_row(surfaces=CLOSED))
    why = st["dead_why"].get("density")
    assert why, "両方の面が天井なのに density が生きています"
    assert "ショートの面" in why
    assert "density" in st["dead"]


def test_長尺の面が開いていれば死んだ腕から外れる():
    st = levers.arm_state(_row(surfaces=OPEN))
    assert "density" not in st["dead_why"], "長尺の面が開いているのに殺しています"
    assert "density" not in st["dead"]
    assert "長尺の面は開いています" in st["open_why"]["density"]


def test_面の欄が無い古い行は前のまま():
    """**済んだ回の判定を、あとから足した欄で塗り替えないこと。**

    ここを「開いている」に倒すと `drift.dead_arm_report` の
    「到達日を動かせない腕を選んだ回」がさかのぼって書き換わります。
    新しい行は毎回この欄を持つので、次の `eta.py` で直ります。
    """
    st = levers.arm_state(_row())
    assert "density" in st["dead"]
    assert "ショートの面" in st["dead_why"]["density"]
    assert not st["open_why"]


def test_天井が生きている腕には付かない():
    st = levers.arm_state(_row(density_cap=3.0, surfaces=CLOSED))
    assert "density" not in st["dead_why"]
    assert not st["open_why"]


def test_密度を選んだ回に長尺の断りが出る():
    st = levers.arm_state(_row(surfaces=OPEN))
    text = "\n".join(levers.lever_notes("density", st))
    assert "長尺は `SHORTS_FEED` の枠を1つも使わず" in text
    assert "4,000時間の門に入るのは長尺だけ" in text
    assert "`none` へ落とさないこと" in text


def test_面が割れている回に引いても動かないを出さない():
    """**同じ回に「引いてよい」と「引いても動かない」を両方出さないこと。**"""
    st = levers.arm_state(_row(surfaces=OPEN))
    text = "\n".join(levers.lever_notes("density", st))
    assert "引いても到達日は動きません" not in text


def test_両方の面が閉じた回は今までどおり叱る():
    st = levers.arm_state(_row(surfaces=CLOSED))
    text = "\n".join(levers.lever_notes("density", st))
    assert "引いても到達日は動きません" in text


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
