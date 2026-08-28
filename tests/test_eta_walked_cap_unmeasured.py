"""**軌跡が「測っていない天井」の上を歩いたら、その行で名指しする。**（2026-08-28）

## なぜ要るか（実測。`sub_rate` が 1年ぶん この形で通っていた）

`_report_trajectory` の末尾には、もともと同じ趣旨の `[!]` がありました。
**ただし見ているのは `choice` の1位（＝この回に振る腕）だけ**です。

    → **この回に振る腕は `per_video`。**
      [!] `per_video` の天井 ×… は**測った天井ではありません。**

`sub_rate` は「**全部振っても出ません**」なので、**1位になりません。**
ところが軌跡の内訳は、その腕を **×10.36** まで歩いていました ——
天井が「登録率 100%」（＝ ×3,153.91）で、**どんな倍率でも下に入る**からです。

    内訳: 腕を 56日ぶん動かして（… `sub_rate` ×10.36 …）、そこから 76日 で届く

**1位でない腕は、誰も測っていないまま日付を押していました。**
だから見る対象を「振る腕」から**「実際に歩いた腕」**へ変えます。

2026-08-28 に `sub_rate` を実測へ替えて4本とも `measured` になりましたが、
**同じ形は腕を足すたびに戻ります** —— `physical_caps()` の既定が
「定義上の上限」に落ちる形なので、**静かに再発する**種類の欠陥です。
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_walked_cap_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _arm(cap: float, measured: bool, **kw) -> dict:
    a = {"rate": 0.02, "cap": cap, "cap_why": "（作りもの）", "cap_measured": measured,
         "hits": 1, "n": 3, "p": 0.2, "gain": 1.5, "share": 0.25,
         "source": "自前", "missing": [], "throughput": 0.7}
    a.update(kw)
    return a


def _tr(factors: dict, arms: dict) -> dict:
    return {
        "base": {"date": date(2027, 1, 7), "days": 132.0, "t_work": 56,
                 "factors": factors, "plan_days": 76.0,
                 "binding": "収益化の門＋その後の30日", "blocking": []},
        "band": {"k": 4, "n": 17, "lo": 0.09, "hi": 0.41},
        "streak": {"n": 0, "expected_gap": 4.0, "unusual": False},
        "arms": arms, "unread": 0, "fast": None, "slow": None, "choice": [],
    }


def _say(tr: dict) -> str:
    return "\n".join(eta._report_trajectory(tr, {}))


def test_歩いた腕の天井が測っていないなら名指しする():
    """**1位でなくても名指しすること。** これが `sub_rate` で抜けていた形。"""
    tr = _tr({"per_video": 3.35, "sub_rate": 10.36},
             {"per_video": _arm(3.35, True), "sub_rate": _arm(3153.91, False)})
    say = _say(tr)
    assert "`sub_rate` ×10.36 は、測っていない天井の上を歩いています" in say
    assert "×3,153.91" in say
    assert "`per_video` ×3.35 は、測っていない" not in say, "測ってある腕を名指ししないこと"


def test_測ってある天井なら黙る():
    tr = _tr({"per_video": 3.35, "sub_rate": 6.52},
             {"per_video": _arm(3.35, True), "sub_rate": _arm(6.52, True)})
    assert "測っていない天井の上を歩いています" not in _say(tr)


def test_歩いていない腕は名指ししない():
    """**倍率 1.00 の腕は、天井が作り話でも日付を押していません。**

    ここで鳴らすと、`density`（×1.00・引き代なし）が毎回 並びます ——
    **名指しの一覧は、鳴りっぱなしになると読まれなくなります。**
    """
    tr = _tr({"per_video": 3.35, "density": 1.00},
             {"per_video": _arm(3.35, True), "density": _arm(1.0, False)})
    assert "測っていない天井の上を歩いています" not in _say(tr)


def test_到達日が出ない回でも落ちない():
    """`base["date"] is None` の枝（塞いでいるものを並べる側）を通すこと。"""
    tr = _tr({"sub_rate": 10.36}, {"sub_rate": _arm(3153.91, False)})
    tr["base"]["date"] = None
    tr["base"]["blocking"] = ["天井が足りない"]
    say = _say(tr)
    assert "塞いでいるのは次のものです" in say
