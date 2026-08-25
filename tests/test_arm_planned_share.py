"""**軌跡が前提にしている配分を、台帳の実物と突き合わせているか。**

## 何を守っているか（2026-08-26・最適化の回）

`eta.py` の到達日は `rate = focus_rate × share` で解いていて、`share` は
**閉じた前提の腕べつの割合 ＝ 過去にどう振ってきたか**でした。

**未来の配分を決めているのは、過去ではなく「いま開いている前提」のほう**です ——
16本作って2週間待たないと1件も閉じないので、これから2週間に閉じるのは
台帳に開いている分だけ。**そこに `per_video` の前提が1件も無ければ、
実績が何%であろうと `per_video` の腕は動きません。**

実測 2026-08-26（埋める前）::

    実績（閉じた21件）  per_video 60% ／ density 25% ／ sub_rate 10% ／ rpm  5%  → 2026-12-28
    台帳（開いた 5件）  per_video  0% ／ density 20% ／ sub_rate 20% ／ rpm 60%  → 2027-01-16

**+19日。** どちらの数もこの機械が持っていて、照らし合わせる所がありませんでした
（`docs/JOURNAL.md`「同じことを2か所が別々に言っていて、片方しか読まれていない」）。

## `lever` の空欄は、黙って全部の腕を遅くします

`closed()` は `lever` か `effect` の無い行を `continue` で飛ばします。
飛ばされた分は `throughput()`（＝ θ）にも入らないので、
`rate = p · log(g) · θ` により**1件落とすたびに腕の速さが全部いっしょに下がります。**

実測 2026-08-26: 閉じた21件は全部埋まっていたのに、
**開いた15件のうち 10件（67%）が空**でした ＝ 閉じるときに書き足す運用。
`config/hypotheses.yaml` の書式一覧に `lever` が**一度も書かれていなかった**のが元です。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
import sys                                                       # noqa: E402

sys.path.insert(0, str(ROOT))
from src import arm_speed                                        # noqa: E402

spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eta)


DOC = {
    "hypotheses": [
        # 開いている（`outcome` が無い）
        {"claim": "a", "lever": "rpm"},
        {"claim": "b", "lever": "rpm"},
        {"claim": "c", "lever": "sub_rate"},
        {"claim": "d", "lever": "none"},        # 腕を動かさない宣言 → 分母から外す
        {"claim": "e"},                          # **空欄**
        {"claim": "f", "lever": ""},             # **空欄**
        # 閉じている（`outcome` あり）→ `planned` は見ない
        {"claim": "g", "lever": "per_video", "outcome": "falsified",
         "closed_on": "2026-08-01", "effect": 1.5},
    ],
    "confirmed": [
        {"claim": "h", "lever": "per_video", "confirmed_on": "2026-08-02", "effect": 2.0},
    ],
}


def test_planned_は開いた前提だけを数える():
    got = arm_speed.planned(DOC)
    assert got["by_lever"] == {"rpm": 2, "sub_rate": 1}, got
    assert got["n"] == 3
    assert got["share"]["rpm"] == pytest.approx(2 / 3)
    assert got["share"]["sub_rate"] == pytest.approx(1 / 3)
    # **0% の腕も返すこと。** 0 が本体です —— 「実績 60% の腕に、台帳が1件も
    # 用意していない」が言えなくなります。
    assert got["share"]["per_video"] == 0.0
    assert got["share"]["density"] == 0.0


def test_planned_は空欄を数えて出す():
    """**空欄は「腕が無い」ではなく「読めない」。** 黙って落とさないこと。"""
    got = arm_speed.planned(DOC)
    assert got["unassigned"] == 2, got
    assert got["total"] == 6, got          # 開いている6件（`none` を含む）


def test_none_は分母から外れる():
    """`none` は「この前提は腕を動かさない」と**宣言した側**。空欄とは別物。"""
    got = arm_speed.planned(DOC)
    assert got["n"] == 3                    # d（none）は入らない
    assert got["unassigned"] == 2           # d は空欄にも数えない


def test_closed_は_lever_の無い行を飛ばす_という前提が生きていること():
    """**この検査の理由そのもの。** ここが変わったら上の警告文が嘘になります。"""
    doc = {"hypotheses": [
        {"claim": "x", "closed_on": "2026-08-01", "effect": 1.5},          # lever 無し
        {"claim": "y", "closed_on": "2026-08-01", "effect": 1.5, "lever": "rpm"},
    ]}
    rows = arm_speed.closed(doc)
    assert [r["claim"] for r in rows] == ["y"], \
        "`lever` の無い行が通るようになったなら、`planned()` と status.py の警告文を書き直すこと"


def test_realloc_arms_は配分だけを差し替える():
    """`focus_rate`（全部振ったときの速さ）は配分に依らないこと。"""
    arms = {"per_video": {"focus_rate": 0.10, "rate": 0.06, "share": 0.6, "cap": 3.0},
            "rpm": {"focus_rate": 0.20, "rate": 0.01, "share": 0.05, "cap": 70.0}}
    got = eta._realloc_arms(arms, {"per_video": 0.25, "rpm": 0.75})
    assert got["per_video"]["share"] == 0.25
    assert got["per_video"]["rate"] == pytest.approx(0.10 * 0.25)
    assert got["rpm"]["rate"] == pytest.approx(0.20 * 0.75)
    # 天井も `focus_rate` もそのまま
    assert got["rpm"]["cap"] == 70.0 and got["rpm"]["focus_rate"] == 0.20


def test_台帳の開いた前提に腕の名前が入っていること():
    """**実物の台帳**。空欄が戻ったら、ここで落とす。

    空欄1件につき、閉じたときに `closed()` がその行ごと飛ばし、
    **θ が下がって全部の腕の速さが同時に落ちます。**
    """
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    blank = [str(h.get("claim"))[:40] for h in doc.get("hypotheses") or []
             if isinstance(h, dict) and h.get("outcome") is None and not h.get("lever")]
    assert not blank, (
        "開いた前提に `lever` がありません（閉じたときに arm_speed が丸ごと飛ばします）: "
        + " / ".join(blank))
