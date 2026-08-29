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

## 2026-08-29 —— **`measured` を「天井」と読まないこと**

上の段落は**もう古い**です。`day_cap.long_form()` は 08/21 の実測
（長尺 7本 を出して生存 5本）から `measured: True` を返し、
`scripts/eta.physical_caps` はその日から**実測の上限 6本/日**を使います。

そのとき `levers.arm_state` は、同じ出力の中で2つの逆のことを言っていました:

    dead_why["density"]  「ショートの面の数。**長尺の面も測って天井**」   ← 偽
    open_why["density"]  「長尺の面は**開いています（未測定）**」          ← 「未測定」が偽

**`measured` と `at_ceiling` は別の量です** ——
前者は「崩れる所を**見たか**」、後者は「**いま**その天井に当たっているか」。
実物は **measured=True かつ at_ceiling=False**（6本/日 に対し 0.69本/日）。
**下の2件が、この取り違えを止めます。**
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


def test_実物の値は_day_capのcollapsedをそのまま映す():
    """**値をべた書きしない。関係のほうを縛る。**（2026-08-26 夜に書き換えた）

    もとは `assert levers._long_surface_measured() is False` でした。
    docstring は「落ちたのが**本当に測れたから**なら書き換えること」と
    断ってあり、**実際にそうなりました**:

        4af0005（08-25 23:38）  day_cap が長尺を齢48時間でそろえて数え直し、
                                08/21 の **7本（生きた 5本）** を拾って
                                `collapsed` を True にした
        1b601a8（08-25 23:44・6分後）
                                levers 側の docstring を直したが、
                                **「値は False のまま」と書いた** ——
                                6分前に True になっていた
        → この検査は **20時間 赤いまま**残り、
          `dead_why["density"]` から「ショートの面」の名前が消えたことも
          道連れで隠れていました（同じファイルの2件）

    **べた書きは、その日の姿を検査に焼き付けます。** 焼き付けた値は
    データが動いた日に落ち、落ちた検査は「実装が壊れた」と読まれます。
    ここが本当に守りたいのは **`levers` が `day_cap` の答えをそのまま映すこと**なので、
    それを縛ります。**この検査は、データが動いても落ちません。**

    **覆る条件**: `_long_surface_measured()` が `collapsed` 以外のものを
    見るようになったら（例: 日数の下限を足す）、ここもその定義に合わせること。
    """
    from src import day_cap
    assert levers._long_surface_measured() is bool(day_cap.long_form().get("collapsed"))


MEASURED_OPEN = {"short": {"at_ceiling": True, "measured": True},
                 "long": {"at_ceiling": False, "measured": True}}


def test_測ってあっても開いていれば天井と言わない(monkeypatch):
    """**`measured` は「天井」ではありません**（2026-08-29 に踏んだ）。

    `day_cap.long_form()` が `measured: True` を返した瞬間、
    `dead_why["density"]` が「**長尺の面も測って天井**」に化けていました。
    見るべきなのは `at_ceiling` のほうです。
    """
    monkeypatch.setattr(levers, "_long_surface_measured", lambda: True)
    st = levers.arm_state(_row(surfaces=MEASURED_OPEN))
    # 開いているので、そもそも死んだ腕から外れる
    assert "density" not in st["dead"]
    why = st["open_why"]["density"]
    assert "長尺の面は開いています" in why
    assert "未測定" not in why, "測ってあるのに『未測定』と言っています: " + why


def test_測ってあって天井に当たっているときだけ天井と言う(monkeypatch):
    monkeypatch.setattr(levers, "_long_surface_measured", lambda: True)
    st = levers.arm_state(_row(surfaces=CLOSED))
    why = st["dead_why"]["density"]
    assert "長尺の面も実測して天井" in why, why


def test_測っていなければ未測定と名乗る(monkeypatch):
    monkeypatch.setattr(levers, "_long_surface_measured", lambda: False)
    st = levers.arm_state(_row(surfaces=CLOSED))
    assert "長尺の面は未測定" in st["dead_why"]["density"]
