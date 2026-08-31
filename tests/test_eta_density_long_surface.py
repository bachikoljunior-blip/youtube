"""`scripts/eta.py` —— **`density` の天井を、面ごとに割って持つこと。**（2026-08-26）

## なぜ要るか（**3回続けて申し送られ、3回とも実行されなかった**）

`physical_caps` の `density` は `min(UPLOAD_CAP_PER_DAY, day_cap.cap())` ——
**ショートの面**で1日に再生が付く本数です。**長尺は `SHORTS_FEED` の枠を
1つも使いません**し、**4,000時間の門に入るのは長尺だけ**なので、
この「引き代なし ×1.00」は**唯一開いている門について何も言っていません。**

8/26 の最初の版は `src/levers.py` で**名前を正すだけ**でした。
名前を正しても `density` は「死んだ腕」に入ったままなので、
**長尺を増やす作業はやはり `none` に落ちます。**

## ここで固定するもの

1. **長尺の面が、別の欄として出ること**（`density_long`）
2. **その天井が、いま測れているほうを名乗ること**
   （`day_cap.long_form()` が `measured` なら実測の上限、でなければ定義上の上限）

   **【2026-08-29 に、ここを書き換えました】** ここには長らく
   「**それが『未測定』を名乗ること**（`measured is False`）—— 長尺の面が
   崩れるところは一度も観測していないので、`sub_rate` と同じ**定義上の上限**です」
   と書いてあり、検査も `measured is False` を**べた書き**していました。

   **崩れは、もう観測されています** —— `data/views.jsonl` の齢 48時間 の読みで
   **2026-08-21 に長尺 7本 を出して、生存 5本**。
   `day_cap.long_form()` は `collapsed: True` / `most: 7` / `measured: True` を返し、
   `day_cap.long_form_lines()` は「**7本/日 で崩れました → 上限は 6本/日**」、
   `batch_build._long_ring()` も `most - 1` で落としています。
   **`eta.py` だけが「一度も観測していない」と言い続けていました**
   （定義上の上限 82本/日 ＝ ×118 対 実測 6本/日 ＝ ×8.7。**14倍**）。

   **検査が事実をべた書きしていたので、実物が動いても赤くなりませんでした。**
   ここが固定するのは「どちらを名乗るか」ではなく
   **「`day_cap` が測れていると言っているほうを名乗ること」**です。
3. **`LEVERS` に入れないこと** —— **理由は 2026-08-29 に置き直しました。**
   もう「未測定だから」ではありません（測れています）。
   **段1（`PLAN_PUBLISH_PER_DAY`）がショートの面の上で解かれているから**です。
   割らずに腕だけ足すと、ショートの段の上を長尺の天井で歩きます
   （08/21 に `UPLOAD_CAP_PER_DAY` そのままで歩かせて
   「×3.7 引けるのに1日も縮まない」を踏んだのと同じ形）。
   **覆る条件**: 段1 が面ごとに割れたら、ここへ入れること
4. **ショートの面が、それはショートの話だと名乗ること**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_long_surface_mod",
                                               ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

from src import levers  # noqa: E402


def _caps():
    return eta.physical_caps({"sub_rate": 0.0003},
                             supply={"sustained_rate_per_day": 16.8})


def test_長尺の面が別の欄として出る():
    caps = _caps()
    assert "density_long" in caps, "長尺の面がまだ `density` に呑まれています"
    assert caps["density_long"]["surface"] == "長尺"
    assert caps["density"]["surface"] == "ショート"


def test_長尺の面は_day_cap_が測れているほうを名乗る():
    """**測っていないものに実測の顔をさせない。測れているものを未測定と言わない。**

    **事実をべた書きしないこと**（2026-08-29 に踏んだ）。ここは長らく
    `measured is False` を直に書いていて、`day_cap.long_form()` が
    `measured: True` を返すようになっても**赤くなりませんでした。**
    見るのは `day_cap` の返りとの**一致**です。
    """
    caps = _caps()
    m = eta.day_cap.long_form()
    d = caps["density_long"]
    assert d["measured"] is bool(m["measured"]), (
        "`day_cap.long_form()` の `measured` と食い違っています "
        f"（day_cap={m['measured']} / eta={d['measured']}）")
    if m["measured"]:
        # 崩れた日の1本 手前 ＝ `long_form_lines()` と同じ式
        assert "測った天井です" in d["why"]
        assert "定義上の上限" not in d["why"]
        cap = max(1, int(m["most"]) - 1)
        assert f"{cap}本/日" in d["why"], d["why"]
        if d["now_per_day"] > 0:
            assert abs(d["factor"] - cap / d["now_per_day"]) < 1e-6
    else:
        assert "定義上の上限" in d["why"]
        assert "測った天井ではありません" in d["why"]


def test_長尺の天井は口の日枠より低いこと():
    """**測れているのに定義上の上限へ戻ったら、ここが止めます。**

    92本/日 は API の日枠で、`physical_caps` の註が
    「**測った天井ではありません**」と自分で書いている数です。
    測れている窓でその数へ戻ると、×118 の「偽の緑」が復活します。
    """
    m = eta.day_cap.long_form()
    if not m["measured"]:
        return
    d = _caps()["density_long"]
    now = d["now_per_day"]
    if now <= 0:
        return
    loose = (eta.UPLOAD_CAP_PER_DAY - eta._view_cap_per_day()) / now
    assert d["factor"] < loose, (
        "測れているのに定義上の上限（口の日枠 − ショートの面）へ戻っています")


def test_長尺の面を軌跡に歩かせない():
    """`LEVERS` に入れると、`_capped_arms` が未測定の天井で外挿します。"""
    assert "density_long" not in levers.LEVERS
    arms = eta._capped_arms({"sub_rate": 0.0003, "per_video_now": 4.0},
                            supply={"sustained_rate_per_day": 16.8})
    assert "density_long" not in arms


def test_ショートの面が天井でも長尺の面は開いている():
    """いまの実測ではこうなります。**逆転したら、この検査ごと読み直すこと。**"""
    caps = _caps()
    assert caps["density"]["at_ceiling"] is True
    assert caps["density_long"]["at_ceiling"] is False


def test_いま出している長尺の本数は出していない日も割る():
    """`per_day` は「出した日」しか持ちません。**その日数で割ると密度が水増しされます。**"""
    per_day = eta.day_cap.long_form().get("per_day") or {}
    rate = eta._long_form_per_day()
    if not per_day:
        assert rate == 0.0
        return
    assert 0 < rate <= max(per_day.values())
    assert rate < sum(per_day.values()) / len(per_day) or len(per_day) == 1
