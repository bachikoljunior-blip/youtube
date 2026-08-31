"""**「動かせる側」と言うなら、その側の天井も同じ行に出すこと。**

`scripts/eta.py` の段2 は、長尺の再生が合格点に届かないとき
「同じ不足を面の側で閉じるなら…**そちらは動かせる側です**（族の数）」と印字します。
**同じ走りの下のほう**には `src/day_cap.long_form()` の実測が出ています ——
「長尺の面: 7本/日 で崩れました → **上限は 6本/日**」。

実測 2026-08-30: 要る **34.5本/日** 対 天井 **6本/日** ＝ **5.75倍**。
**2行は同じ出力の中にあり、どこにも繋がっていませんでした。**
そして直近の ship は2件とも長尺の族と長尺の予約でした
（`data/runs.jsonl` 08/30 01:58／02:12）。

**天井は動かせます**（`day_cap.long_form()` の覆る条件）。
だから断りは「無理」ではなく「先に天井を測り直す前提が要る」です。

**覆る条件**: 天井が要る本数を上回ったら、この断りは自分で消えます。
~~そのとき**この検査も落ちる**ので、そこで畳むこと。~~

**2026-08-31: その条件が満ちました。畳まずに、両向きにしました。**

実測（同日・`python scripts/eta.py`）: 要る面 **987回/日** ÷ 公開1本あたり
**320.6回** ＝ **3.08本/日**。測った天井は **6本/日** なので、
`need_pub > _cap_long` が偽になり、**断りは正しく消えています**
（2026-08-30 は 要る 34.5本/日 対 天井 6本/日 ＝ 5.75倍 でした。面が動いた）。

**「落ちたから畳む」にすると、断りが要る側に戻ったときに黙って通ります。**
だから条件を数で計算して、**要るなら在ること／要らないなら無いこと**の
両方を見ます。これなら天井と要る本数がどちらへ動いても、検査が主題を持ち続けます。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CAVEAT = "その「動かせる側」にも、測った天井があります"


def test_族の数と天井が同じ行に並ぶ() -> None:
    out = subprocess.run([sys.executable, "scripts/eta.py"],
                         cwd=ROOT, capture_output=True, text=True, timeout=900).stdout
    if "そちらは動かせる側です" not in out:
        return          # その段に入らない回（面が足りている／CTR が縛っている）
    from src import day_cap
    lf = day_cap.long_form()
    if not lf.get("collapsed"):
        return          # まだ崩れを観測していない ＝ 天井が測れていない

    cap_long = float(lf.get("most") or 0) - 1
    # **要る本数は、印字されている行から読み直します**（`eta.py` の計算に乗らない）。
    mt = re.search(r"\*\*長尺 ([\d,.]+)本/日\*\*（", out)
    assert mt, ("「そちらは動かせる側です」は出ているのに、要る長尺の本数が"
                "同じ行に数で出ていません（読む側が倍率を出せません）")
    need_pub = float(mt.group(1).replace(",", ""))

    if need_pub > cap_long:
        assert CAVEAT in out, (
            f"要る {need_pub:,.1f}本/日 が測った天井 {cap_long:,.0f}本/日 を"
            "超えているのに、`day_cap.long_form()` の上限が同じ行に出ていません。"
            "**2か所が別々に言っている形です。**")
        assert "族を増やしても、この段は族では閉じません" in out
    else:
        # **天井のほうが上回った回**（2026-08-31 に初めて起きた）。
        # 断りは要りません。**出ていたら、それは嘘の宿題です。**
        assert CAVEAT not in out, (
            f"要る {need_pub:,.1f}本/日 は測った天井 {cap_long:,.0f}本/日 の"
            "**下**なのに、「天井が足りない」と印字しています"
            "（画面に嘘の宿題を積んでいます）")
