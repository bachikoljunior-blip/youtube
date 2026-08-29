"""`headline()` —— **「別の腕を引くこと」に、腕の名前が付いているか。**

## なぜ要るか（2026-08-30 05:5x・最適化の回に測った）

`scripts/eta.py` の頭の3行は、名指しした腕の測定が予約済みの本で埋まっている回に
こう出していました（**この1行がぜんぶです**）:

    ### **その `per_video` の測定は、予約済みの本が 2026-08-31 に答えます**
        → **この回は別の腕を引くこと。**

**「別の腕」に名前がありません。** 名前が無い所は、回の側が
「いまやれること」の中から埋めます。実測 2026-08-30 05:5x、`data/runs.jsonl` の
**ship 358件（7日ぶん・これが台帳の全部）**:

    lever_hint  per_video **358件（全部）**   ← 名指しは 7日間 1本も変わっていない
    lever       none 152 ／ density 106 ／ per_video 46 ／ rpm 29 ／ sub_rate 25
    lever_followed  False **312件（87%）**

`density` の 106件 は **`lever_cap` が全件 1.0**（＝引き代なし）で記録されています。
`none` と合わせて **258件（72%）**が、この機械が自分で「到達日を動かさない」と
測った側に振られていました。**そのあいだ到達予測は +20日 遠のいています**
（2026-12-21 → 2027-01-10・`traj_trend()`）。

ところが**同じ回の同じプログラム**が、`pl["lever_days"]` でこう出しています:

    per_video  天井 ×2.87  reachable_at_cap **True**
    rpm        天井 ×61.35 reachable_at_cap **True**
    sub_rate   天井 ×6.53  reachable_at_cap False
    density    天井 ×1.00  reachable_at_cap False ／ **凍らせても 0.0日**

`arm_frozen_days["density"] == 0.0` は「その腕を丸ごと凍らせても到達日は
1日も動かない」という、**この機械が自分で解いた数**です。
`arm_share` の側も同じ向きで、過去の配分は `density` **35%** ／ `rpm` **5%** ——
天井まで引いて日付が出る2本のうち片方が、いちばん薄い帯です。

**これは怠けではなく、名指しが空欄だったことの帰結です。**
`lever_hint` は一度 同じ形を直しています（`plan()` の註:
「同じ見出しに2つの腕が並ぶと、読み手はどちらでも選べてしまい、
**後から理由を付ける**側に戻ります」）。空欄は、2つ並ぶより弱い形です。

## ここで固定するもの

1. **名指しが覆われた回は、代わりの腕を1本 名指しする**
   （`reachable_at_cap` が真・`at_ceiling` でない・`gain_at_cap` が最大）
2. **凍らせても 1日 未満の腕は、同じ行で名指しして塞ぐ**
   （代わりを出すだけでは、既定は残ります）
3. **候補が1本も無い回は、そう言う**（黙って消えると 1 が効いたのか
   候補が無かったのか、読む側から区別できません）

## 覆る条件

`reachable_at_cap` の真な腕が名指しの1本しか無くなったら、この行は消えます
（`elif` の側が出ます）。そのときは腕を選ぶ回ではなく、天井を測り直す回です。
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "eta_covered_sub_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _row(lever, cap, reach, at_ceiling=False, gain=0.0, days=200.0, th=None):
    return {
        "lever": lever, "label": lever, "factor": 2.0,
        "days": days, "date": date(2027, 1, 10), "gain": 0.0,
        "reachable": reach, "cap": cap, "at_ceiling": at_ceiling,
        "days_at_cap": days, "date_at_cap": date(2027, 1, 10) if reach else None,
        "gain_at_cap": gain, "reachable_at_cap": reach, "threshold": th,
    }


def _plan(**kw) -> dict:
    """**実測の並びをそのまま写した `pl`**（2026-08-30 の点）。"""
    pl = {
        "binding": "再生数が天井に当たっている",
        "lever_hint": "per_video",
        "lever_hint_covered": "2026-08-31",
        "target_date": None,
        "days_to_target": eta.NEVER,
        "lever_days": [
            _row("per_video", 2.87, True, gain=9e8, days=190.0, th=2.54),
            _row("rpm", 61.35, True, gain=8e8, days=260.0, th=2.65),
            _row("sub_rate", 6.53, False),
            _row("density", 1.00, False, at_ceiling=True),
        ],
        "arm_frozen_days": {"sub_rate": 107.2, "density": 0.0},
    }
    pl.update(kw)
    return pl


def _head(pl) -> str:
    return "\n".join(eta.headline(pl, None, None, []))


def test_覆われた回は代わりの腕を名指しする():
    out = _head(_plan())
    assert "この回は別の腕を引くこと" in out, "元の行そのものが消えている"
    # **名前が出ること。** `per_video` は覆われているので、残る唯一の
    # `reachable_at_cap` は `rpm`。
    assert "`rpm`" in out
    assert "その「別の腕」は `rpm` です" in out


def test_凍らせても0日の腕を同じ行で塞ぐ():
    out = _head(_plan())
    # `density` は `arm_frozen_days` が 0.0 ＝ 引いても到達日は動かない。
    # **代わりを出すだけでは既定は残る**ので、名指しで塞ぐところまでが1手。
    line = [l for l in out.splitlines() if "その「別の腕」は" in l][0]
    assert "`density`" in line
    assert "`--lever` にしないこと" in line
    # 107日 の `sub_rate` は塞がない（0日 ではない）。
    assert "`sub_rate`" not in line


def test_候補が1本も無い回はそう言う():
    pl = _plan(lever_days=[
        _row("per_video", 2.87, True, gain=9e8, days=190.0, th=2.54),
        _row("rpm", 1.00, False, at_ceiling=True),
        _row("sub_rate", 6.53, False),
        _row("density", 1.00, False, at_ceiling=True),
    ], arm_frozen_days={"rpm": 0.0, "sub_rate": 107.2, "density": 0.0})
    out = _head(pl)
    assert "その「別の腕」がありません" in out
    assert "天井そのものを測り直す回です" in out
    # **黙って消えないこと。** 代わりの名指しは出ない。
    assert "その「別の腕」は" not in out


def test_覆われていない回は何も足さない():
    pl = _plan()
    pl.pop("lever_hint_covered")
    out = _head(pl)
    assert "その「別の腕」" not in out
