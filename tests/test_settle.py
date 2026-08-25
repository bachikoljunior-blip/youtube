"""**待つ日数が、実測から離れていないか。**（2026-08-26 に作った）

なぜ要るか。`SETTLE_DAYS = 7` は**一度も測っていない勘**で、4か月ぶん残りました。
その間に `scripts/eta.py` は同じ量を `MATURE_HOURS = 48` として**実測つきで**持ち、
`config/hypotheses.yaml` は 2026-08-21 に測って1件だけ 24時間 に直しています。
**3つが別々の数を持ち、判定の門はいちばん遅い数だけを読んでいました。**

この検査は「7 に戻っていないか」を見るのではありません。
**その時点の実データが、いま使っている数を支えているか**を見ます。
支えなくなったら（後から拾われる本が出たら）、ここが落ちて次の回に知らせます。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from src import settle

ROOT = Path(__file__).resolve().parent.parent


def test_待つ日数は実データに支えられている():
    """`SETTLE_DAYS` の時点で、**いちばん遅い本**が伸びきっているか。"""
    curve = settle.views_curve((float(settle.SETTLE_DAYS * 24),))
    row = curve.get(float(settle.SETTLE_DAYS * 24))
    if not row or row["n"] < 10:
        pytest.skip(f"標本が薄い（n={row['n'] if row else 0}）—— 判定しない")
    assert row["median"] >= 0.99, (
        f"{settle.SETTLE_DAYS*24}時間 で中央値 {row['median']:.3f} —— "
        "**待つ日数が短すぎます。** `src/settle.py` の「覆る条件」を読んで上げ直すこと"
    )
    assert row["min"] >= 0.95, (
        f"{settle.SETTLE_DAYS*24}時間 でいちばん遅い本が {row['min']:.3f} —— "
        "**後から拾われる本が出ています。** `SETTLE_DAYS` を上げ直すこと"
    )


def test_engaged_比率もその時点で確定している():
    """判定がじっさいに使うのは engaged 比率のほう。**確定値との差が 2pt 未満か。**"""
    eng = settle.engaged_curve((float(settle.SETTLE_DAYS * 24),))
    row = eng.get(float(settle.SETTLE_DAYS * 24))
    if not row or row["n"] < 10:
        pytest.skip("scan の標本が薄い —— 判定しない")
    assert row["max"] < 0.02, (
        f"engaged 比率が確定値から最大 {row['max']*100:.2f}pt ずれています —— "
        "**この年齢では判定が入れ替わります。**`SETTLE_DAYS` を上げ直すこと"
    )


def test_同じ数を他所で定義していない():
    """**このファイルの外に数を書かないこと。** 8件みつかった壊れ方の再発を止める。"""
    for rel in ("src/ab_split.py", "scripts/eta.py", "scripts/deadline_check.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        body = "\n".join(l for l in text.splitlines()
                         if not l.lstrip().startswith("#") and not l.lstrip().startswith("#:"))
        assert not re.search(r"^\s*SETTLE_DAYS\s*=\s*\d", body, re.M), \
            f"{rel} が `SETTLE_DAYS` を自分で定義しています（`src/settle.py` から読むこと）"
        assert not re.search(r'settle_days"\s*,\s*\d', body), \
            f"{rel} が `settle_days` の既定を直に書いています（`src/settle.py` から読むこと）"


def test_yaml_の_settle_days_も同じ数を使っている():
    """前提ごとに別の待ち日数が残っていないか。**0 は「待たない」で意図的**。"""
    data = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    for h in data["hypotheses"]:
        for need in h.get("needs") or []:
            if "settle_days" not in need:
                continue
            got = int(need["settle_days"])
            assert got in (0, settle.SETTLE_DAYS), (
                f"「{str(h.get('claim'))[:30]}」の settle_days が {got} —— "
                f"いまの実測は {settle.SETTLE_DAYS}日 です。**長く待つ理由があるなら、"
                "その理由を `src/settle.py` に書いてからこの検査を直すこと**"
            )


# ---- 遅れの帯（2026-08-26）----------------------------------------------

def test_遅れの帯は実測から出る():
    """**遅れは点ではありません。1日の中で動きます。**

    Analytics は日の途中で新しい日を出すので、**同じ日でも早い時刻に走った回は
    4日、遅い時刻の回は 3日**を見ます。実測 438観測で 3日が 381・4日が 57、
    **1日のうちに両方を観測した日が 6日**（08/18〜08/22・08/26）。

    この幅を `scripts/deadline_check.py` が帯として使い、
    **「期限が1日 ずれています」という churn を止めます。**
    """
    b = settle.analytics_lag_band()
    assert set(b) >= {"lag", "lo", "hi", "band", "n"}
    assert b["lo"] <= b["lag"] <= b["hi"] or b["n"] < 2
    assert b["band"] == b["hi"] - b["lo"] >= 0


def test_観測が足りない回は帯を主張しない(tmp_path):
    """**黙って広げないこと。** 帯が広いほど「ずれ」を見逃すので、根拠が要ります。"""
    空 = tmp_path / "からっぽ.jsonl"
    空.write_text("", encoding="utf-8")
    assert settle.analytics_lag_band(path=空)["band"] == 0


def test_窓の外の観測は帯に入れない(tmp_path):
    """古い遅れを混ぜると、**もう起きない幅**で今日の判定を黙らせます。"""
    import json
    p = tmp_path / "lag.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"at": "2020-01-01T00:00:00+09:00", "last_day": "2019-12-01"},   # 31日 遅れ・窓の外
        {"at": "2026-08-26T02:00:00+09:00", "last_day": "2026-08-22"},   # 4日
        {"at": "2026-08-26T06:00:00+09:00", "last_day": "2026-08-23"},   # 3日
    ]), encoding="utf-8")
    b = settle.analytics_lag_band(window_days=10**6, path=p)
    assert b["hi"] == 31 and b["band"] == 28, "窓を広げれば入る（この検査じしんの前提の確認）"

    b = settle.analytics_lag_band(window_days=14, path=p)
    assert b["hi"] == 4 and b["lo"] == 3, "窓の中に残るのは 08/26 の2件だけ"
    assert b["band"] == 1, ("古い 31日 を混ぜて帯を 28日 にしないこと —— "
                            "**もう起きない幅で今日の判定を黙らせる**ことになります")
