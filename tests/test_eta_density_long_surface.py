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
2. **それが「未測定」を名乗ること**（`measured is False`）——
   長尺の面が崩れるところは一度も観測していないので、
   `sub_rate` と同じ**定義上の上限**です。実測の顔をさせないこと
3. **`LEVERS` に入れないこと** —— 入れると `_capped_arms` が
   この未測定の天井で軌跡を歩かせます（08/21 に `UPLOAD_CAP_PER_DAY`
   そのままで歩かせて「×3.7 引けるのに1日も縮まない」を踏んだのと同じ形）
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


def test_長尺の面は未測定を名乗る():
    """**測っていないものに実測の顔をさせないこと。**"""
    caps = _caps()
    assert caps["density_long"]["measured"] is False
    assert "定義上の上限" in caps["density_long"]["why"]
    assert "測った天井ではありません" in caps["density_long"]["why"]


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
