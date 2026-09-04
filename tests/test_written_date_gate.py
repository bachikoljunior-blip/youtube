"""`kind: after` の `on_date` を、いまの伸び率で数え直す（`deadline_check._written_date_gate`）。

## なぜ要るか（2026-09-05 06:3x。**2つの道具が、同じ前提に正反対の指図を出していた**）

    deadline_check  → 判定できるのは 03-03。**期限 03-04 はその帯の中です —— 書き換えないこと**
    eta.py          → 治療群は 64再生/日 → 片群 14,085再生 まで **218日**。
                      期限まで 181日 しかないので **37日 足りません**

**そして「触るな」と言っているほう（`deadline_check`）が、写しを読んでいました。**
`on_date: 2027-02-28` の根拠は、その前提の `note:` に残っています ——
「2026-08-26 以降に公開した 228本 が 合計 2,636回 ＝ **329.5再生/日（両群）** → 182日」。
**228本／31日 ＝ 7.4本/日 の供給の上の数**で、規則1（1日1本）ではもう出ません。
`kind: accrual` の側には同じ補正（「伸び率を規則（1日1本）で押さえています」）が
既に当たっており、**`kind: after` にだけ当たっていませんでした。**

## この検査が固定するもの

1. **数えるのは `views_target:` を書いた要件だけ**（推測で全件を遅らせない）
2. **遅らせる向きにしか使わない**（書いた日が余裕を見た日のことがあり、縮めると早撃ち）
3. **速さが読めない回は黙る**（推測で遅らせない）

**覆る条件**: 規則1 が外れて 1日 2本以上 になったら、`PUBLISH_PER_DAY` 経由で
自動的に速くなります（この検査は倍率を固定していません）。
`_settled_view_rate()` が別の所から速さを引くようになったら、下の差し替え口を直すこと。
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import deadline_check as dc  # noqa: E402


@pytest.fixture()
def 速さ(monkeypatch):
    """規則 1本/日 × 落ち着いた1本の中央値 129回 ＝ 129再生/日（2026-09-05 の実測）。"""
    monkeypatch.setattr(dc, "_settled_view_rate", lambda: (205, 129.0, 129.0))


def test_書いた日が伸び率に追いつかなければ_後ろの日を返すこと(速さ):
    """30,000再生 ÷ 129再生/日 ＝ 233日 → 2026-09-04 ＋ 233日 ＝ 2027-04-25。"""
    need = {"views_target": 30000, "views_since": "2026-09-04"}
    ans = dc._written_date_gate(need, date(2027, 2, 28), "その日のデータ")
    assert ans is not None, "書いた日（02-28）より後になるはず"
    assert ans.ready == date(2027, 4, 25)
    assert "129再生/日" in ans.why
    assert "233日" in ans.why


def test_書いた日のほうが後なら_何も言わないこと(速さ):
    """**早める向きには使いません。** 書いた日は余裕を見た日のことがあり、
    縮めると早撃ちになります（`_ans_after` が 2026-08-27 00:22 に踏んだ形）。"""
    need = {"views_target": 30000, "views_since": "2026-09-04"}
    assert dc._written_date_gate(need, date(2028, 1, 1), "x") is None


def test_数を書いていない要件は_いままでどおり時計だけであること(速さ):
    """**全件に足そうとしないこと** —— 「公開から48時間」のような要件は時計が正本です。"""
    for need in ({}, {"views_target": None}, {"views_target": 0}, {"views_target": "abc"}):
        assert dc._written_date_gate(need, date(2027, 2, 28), "x") is None


def test_速さが読めない回は黙ること(monkeypatch):
    """**推測で遅らせないこと。**"""
    monkeypatch.setattr(dc, "_settled_view_rate", lambda: None)
    need = {"views_target": 30000, "views_since": "2026-09-04"}
    assert dc._written_date_gate(need, date(2027, 2, 28), "x") is None


def test_台帳のその前提が_数え直す形で書いてあること():
    """**写しに戻っていないこと。** `on_date` を手で書き直すと、また古くなります。"""
    import yaml
    doc = yaml.safe_load((Path(dc.ROOT) / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    rows = doc if isinstance(doc, list) else (doc.get("hypotheses") or doc.get("items") or [])
    hit = [h for h in rows
           if isinstance(h, dict) and "登録の依頼を画面" in str(h.get("claim") or "")]
    assert hit, "前提が見つかりません（claim が変わったら、この検査も直すこと）"
    needs = hit[0].get("needs") or []
    after = [n for n in needs if str(n.get("kind")) == "after"]
    assert after, "`kind: after` の要件が在るはず"
    assert int(after[0].get("views_target") or 0) == 30000
    assert str(after[0].get("views_since")) == "2026-09-04"


def test_after_の枝から呼ばれていること():
    """**測るだけでは1件も動きません。**"""
    import inspect
    assert "_written_date_gate(" in inspect.getsource(dc._ans_after)
