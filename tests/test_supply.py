"""`src/supply.py` —— **その密度を、在庫が支えられるか**の検査。

**物差しは手で作った行に置いてあります**（2026-08-20 02:1x の教訓）。
実データ側に固定してよいのは「**まだ測れていない**」ことのほうなので、
最後の1件だけ実データを見て、そこには「**緑でなくなったら進歩**」と書いてあります。
"""
from __future__ import annotations

from datetime import date

import pytest

from src import supply


# ---------------------------------------------------------------- 算数（手で作った行）

def test_足りないときは日数と1周あたりの本数を出す():
    """**既知の当たり**（2026-08-20 13:4x に手で確かめた）。

        在庫 36本 ＋ 掃引の候補 491件 = 527本
        25本/日 × 157日 = 3,925本 要る  → 足りないのは 3,398本
        3,398 ÷ 157 = 21.6本/日 → 1周60分（1日24周）なら **0.9本/周**
    """
    sp = supply.supply(25, stock_n=36, novel=491, horizon_days=157,
                       run_minutes=60, today=date(2026, 8, 20))
    assert sp["supply_total"] == 527
    assert sp["holds"] is False
    assert sp["need_total"] == pytest.approx(3925)
    assert sp["shortfall"] == pytest.approx(3398)
    assert sp["days_covered"] == pytest.approx(527 / 25)
    assert sp["sections_per_day_needed"] == pytest.approx(3398 / 157)
    # **1周あたりが、この回に持って帰る数です**（1日21.6本は誰の仕事でもない）
    assert sp["sections_per_run_needed"] == pytest.approx(3398 / 157 / 24, rel=1e-6)


def test_足りているときは要求本数を0にする():
    sp = supply.supply(2, stock_n=100, novel=100, horizon_days=10, today=date(2026, 8, 20))
    assert sp["holds"] is True
    assert sp["shortfall"] == 0
    assert sp["sections_per_day_needed"] == 0
    assert sp["sections_per_run_needed"] == 0


def test_実効の密度は在庫を期日で割ったもの():
    """**25本/日 と印字しても、在庫がそれを出せるとは限りません。**"""
    sp = supply.supply(25, stock_n=36, novel=491, horizon_days=157,
                       today=date(2026, 8, 20))
    assert sp["density_supported"] == pytest.approx(527 / 157)
    assert sp["density_supported"] < sp["density"]


def test_尽きる日は在庫を密度で割った日():
    sp = supply.supply(10, stock_n=20, novel=30, horizon_days=None,
                       today=date(2026, 8, 20))
    assert sp["days_covered"] == pytest.approx(5.0)
    assert sp["dry_date"] == date(2026, 8, 25)


def test_密度が0なら尽きない():
    sp = supply.supply(0, stock_n=5, novel=0, today=date(2026, 8, 20))
    assert sp["days_covered"] == float("inf")
    assert sp["dry_date"] is None


def test_測っていない掃引は0と区別する():
    """**`None` は「一度も測っていない」。0 は「余地が尽きた」。別のことです。**"""
    unmeasured = supply.supply(25, stock_n=36, novel=None, horizon_days=157)
    dry = supply.supply(25, stock_n=36, novel=0, horizon_days=157)
    assert unmeasured["measured"] is False
    assert dry["measured"] is True
    assert unmeasured["supply_total"] == dry["supply_total"] == 36


def test_歩留りを下げると日数は短くなる側にしか動かない(monkeypatch):
    """`SWEEP_YIELD` は 1.0（上限側）。下げたら**必ず短くなる**こと。"""
    high = supply.supply(25, stock_n=36, novel=491, horizon_days=157)
    monkeypatch.setattr(supply, "SWEEP_YIELD", 0.5)
    low = supply.supply(25, stock_n=36, novel=491, horizon_days=157)
    assert low["days_covered"] < high["days_covered"]
    assert low["sections_per_day_needed"] > high["sections_per_day_needed"]


# ---------------------------------------------------------------- 印字

def test_足りないときは1周あたりの本数を必ず印字する():
    """**読まれるのはこの1行だけ**なので、消えたら分かるようにしておく。"""
    sp = supply.supply(25, stock_n=36, novel=491, horizon_days=157, run_minutes=65)
    text = "\n".join(supply.lines(sp))
    assert "保ちません" in text
    assert "1周（65分）あたり" in text
    assert "実効の密度" in text


def test_測っていないときはそう言う():
    text = "\n".join(supply.lines(supply.supply(25, stock_n=36, novel=None)))
    assert "一度も測っていません" in text


# ---------------------------------------------------------------- 実データ側

def test_既知の当たり_いま在るものだけでは25本日を到達日まで保てない():
    """**緑でなくなったら、それは進歩です。**

    在庫と掃引の候補を足しても、`PLAN_PUBLISH_PER_DAY` × 到達予測までの日数には
    届きません（2026-08-20 の実測: 527本 対 3,925本）。
    **ここが赤くなるのは、節を書く手が supply に追いついたときだけ**なので、
    そのときは検査ごと書き換えること（消さずに向きを変える）。

    掃引は約47秒かかるので、**台帳の点を読みます**（`--measure` で積んだもの）。
    点が1つも無い回は飛ばします —— 無いことは失敗ではありません。
    """
    sw = supply.sweep_novel()
    if sw["novel"] is None:
        pytest.skip("data/supply.jsonl に掃引の点がありません（`--measure` で積む）")
    sp = supply.supply(25, novel=sw["novel"], horizon_days=157)
    assert sp["holds"] is False, (
        f"在庫{sp['stock']}本＋候補{sw['novel']}件で 25本/日×157日 が保てています。"
        "**この検査を書き換えること**（supply が律速でなくなりました）"
    )


def test_在庫の数え方はAPIを叩かない():
    """日枠が閉じている窓（1日16時間前後）でも、この数は必ず出ること。"""
    assert supply.stock() >= 0


# ---------------------------------------------------------------- eta への配線

def test_etaの段取りの節に_supplyの行が入る():
    """**配線の検査。** `_report_plan` から呼ばれないと、この節は誰も読みません。

    `plan()` を通すと Analytics を叩くので、ここは `_report_supply` を
    手で作った `pl` で直接叩きます（**API 0単位**）。
    """
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("_eta_for_test", root / "scripts" / "eta.py")
    eta = importlib.util.module_from_spec(spec)
    sys.modules["_eta_for_test"] = eta
    spec.loader.exec_module(eta)

    lines = eta._report_supply({"density": 25, "days_to_target": 157})
    text = "\n".join(lines)
    assert "在庫が支えられるか" in text, text
    # 到達予測の日数を渡しているので、保つ／保たないの判定まで出ること
    assert ("保ちません" in text) or ("保ちます" in text), text


def test_到達日が出ていない回でも_supplyの節は落ちない():
    """届かない帯（`days_to_target` が NEVER）でも、在庫の行だけは出すこと。"""
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("_eta_for_test2", root / "scripts" / "eta.py")
    eta = importlib.util.module_from_spec(spec)
    sys.modules["_eta_for_test2"] = eta
    spec.loader.exec_module(eta)

    lines = eta._report_supply({"density": 25, "days_to_target": eta.NEVER})
    text = "\n".join(lines)
    assert "在庫が支えられるか" in text
    assert "到達予測まで" not in text
