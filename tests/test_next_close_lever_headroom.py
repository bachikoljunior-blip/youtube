"""**「`verdict` で日付が動かせます」は、腕に引き代があるときだけ本当です。**

## なぜ在るか（2026-08-31・最適化の回に実測して足した）

`scripts/eta.py` は、期日の来た前提が在る回にこう印字します::

    **期日の来た前提があります**（2026-08-31・開いている前提 27件）→
    **この回は `verdict` で日付が動かせます** —— **いま判定できるのは**:
    **長尺は1日4本 作れる（…）**

実測（同日・`arm_speed.next_close()` を直接 叩いた）::

    判定できる前提  **1件**「長尺は1日4本 作れる」
    その `lever`    **density**

ところが `density` は、**同じ日にオーナーが 1本/日 に固定**しています
（`src/house_rule.py`・覆る条件なし）。`eta.physical_caps()` はその腕を
**×1.00（引き代なし）**と返し、同じ走りの `lever_days` も
「天井 ×1.00・`reachable_at_cap=False`」と出しています。

**引き代 ×1.00 の腕は、前提を閉じても到達日を1日も動かしません。**
つまりその回の「`verdict` で日付が動かせます」は、
**唯一 名指しできる1件について偽**でした ——
この repo で名前の付いている「**同じ出力の2か所が別々に言っている形**」です。

## ここで固定するもの

1. `next_close()` が、claim ごとの `lever` を返すこと（返さないと読む側が断れない）
2. 名指しした前提の腕に引き代が無い回は、`eta` が**同じ行でそう言うこと**
3. **腕を消さないこと** —— 判定は判定として値打ちがあるので、撃ってよい。
   言うのは「**閉じても上の日付は動かない**（`--moves` は 0日 が正しい）」だけ

## 覆る条件

オーナーが 1日1本 を外して `density` に引き代が戻ったら、この断りは自分で消えます
（数で見ているので、写しではありません）。そのとき 2 の検査は反対側の枝を見ます。
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_nclev_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

from src import arm_speed  # noqa: E402


def _doc(lever: str = "density") -> dict:
    return {"hypotheses": [
        {"claim": "長尺は1日4本 作れる", "deadline": "2026-08-31", "lever": lever},
        {"claim": "とっくに閉じた前提", "deadline": "2026-08-01",
         "lever": "rpm", "closed_on": "2026-08-02"},
    ]}


def test_next_close_が腕の名前も返す() -> None:
    """**日付は行き先を教えず、名前は教えます。** 腕はその名前の一部です。"""
    nc = arm_speed.next_close(doc=_doc(), today=date(2026, 8, 31))
    assert nc["claims"] == ["長尺は1日4本 作れる"]
    assert nc["claim_levers"] == {"長尺は1日4本 作れる": "density"}


def test_腕が無い前提は_claim_levers_に出ない() -> None:
    """`lever` を書いていない前提もあります。**黙って別の腕に寄せないこと。**"""
    doc = {"hypotheses": [{"claim": "腕を書いていない前提", "deadline": "2026-08-31"}]}
    nc = arm_speed.next_close(doc=doc, today=date(2026, 8, 31))
    assert nc["claims"] == ["腕を書いていない前提"]
    assert nc["claim_levers"] == {}


def test_判定できる前提が1件も無い回でも_claim_levers_は在る() -> None:
    """**キーそのものを落とさないこと**（読む側が `.get()` を書き忘れても落ちない）。"""
    nc = arm_speed.next_close(doc={"hypotheses": []}, today=date(2026, 8, 31))
    assert nc["claims"] == []
    assert nc["claim_levers"] == {}


# --- 2. `eta` が、引き代の無い腕をそう言うこと ------------------------------------

def _headline(monkeypatch, lever: str, factor: float, at_ceiling: bool) -> str:
    """`headline()` を、期日の来た前提1件・その腕の引き代を明示して撃つ。"""
    monkeypatch.setattr(
        eta.arm_speed, "next_close",
        lambda *a, **k: {"on": date(2026, 8, 31), "days": 0, "open": 27,
                         "source": "ready", "claims": ["長尺は1日4本 作れる"],
                         "claim_levers": {"長尺は1日4本 作れる": lever}})
    monkeypatch.setattr(eta, "_ready_by_claim", lambda *a, **k: {})
    monkeypatch.setattr(eta, "_unready_claims", lambda *a, **k: set())
    pl = {
        "days_to_target": eta.NEVER, "lever_hint": "rpm", "lever_days": [
            {"lever": lever, "factor": factor, "at_ceiling": at_ceiling,
             "reachable": False, "reachable_at_cap": not at_ceiling,
             "days": eta.NEVER, "date": date(2027, 1, 1), "gain_at_cap": 0.0},
        ],
        "arm_frozen_days": {}, "target": {}, "forms": {},
        "target_date": None, "binding": "再生数が天井に当たっている",
    }
    # **`tr` の `arms` に名指しの腕が居ないと、この段そのものに入りません**
    #     （`headline()` は `arms.get(pl["lever_hint"])` で括っています）。
    tr = {"arms": {"rpm": {"throughput": 0.77, "p": 0.19}}, "choice": []}
    return "\n".join(eta.headline(pl, tr=tr))


def test_引き代の無い腕は_日付が動かないと同じ行に出る(monkeypatch) -> None:
    """**この検査の値打ちそのもの。** 2026-08-31 の実物がこの形でした。"""
    out = _headline(monkeypatch, "density", 1.0, True)
    assert "期日の来た前提があります" in out
    assert "腕 `density`" in out, "どの腕の前提かが同じ行に出ていません"
    assert "腕に引き代がありません" in out, (
        "引き代 ×1.00 の腕を名指しして「`verdict` で日付が動かせます」とだけ"
        "言っています（**同じ走りの `lever_days` が ×1.00 と出しています**）")
    assert "`--moves` は 0日 が正しい" in out


def test_引き代のある腕なら_断りは出ない(monkeypatch) -> None:
    """**要らないときに出さないこと**（画面に嘘の宿題を積まない）。"""
    out = _headline(monkeypatch, "rpm", 12.0, False)
    assert "期日の来た前提があります" in out
    assert "腕 `rpm`" in out
    assert "腕に引き代がありません" not in out, (
        "引き代のある腕なのに「動きません」と印字しています")
