"""**「切っている物のほうを見ろ」と言う行は、切っている物を名指しすること。**

## なぜ要るか（2026-09-01 夕・最適化の回に測って足した）

`headline()` の「`×10^9` が腕まで届いていない腕が N本 あります」は、
そのすぐ後で **「見るのは腕ではなく、切っている物のほうです」** と命じます。
**が、答えが書いてあったのは `density` の側だけ**でした。
`rpm` の側は名前が無く、指示に従った回は**そこから探し始めます**
（この回がそうでした）。

**撃って出た答え**（`physical_caps()['rpm']` と `plan()` を並べた・2026-09-01）::

    caps['rpm'].factor  ×36.72  ＝ **実効の混ざり方** ¥21.0 → ¥769
    sc['rpm'] が掛かる先        ＝ **帯** RPM_SCENARIOS['長尺 お金 低'] ¥400
    → 模型を動かす最大の倍率    ＝ 769 / 400 ＝ **×1.82**（実測の頭打ちと一致）

    rpm ×1.82 / ×5 / ×36.72 / ×10^9 は、**どれも need_month 274,807 で同じ**

**倍率の分母が2か所で別**（混ざり方 ¥21 と 帯 ¥400 で 19倍）。数そのものは
`min(band_rpm, rpm_cap)` が救っているので `days_at_cap` は正しく、
**印字される ×36.72 だけが 20倍 大きい側**です。そして `rpm_cap` を作るのは
`rpm_mix.rule_capped()` ＝ **オーナーが固定した 1本/日**（`src/house_rule.py`）。
**切られている2本は、どちらも同じ規則で切られています。**

この検査が止めるのは1つ: **`cap_why`（＝ その天井がなぜその値か）が
`lever_days()` の中で捨てられて、`headline()` から読めなくなること。**

**覆る条件**: `caps['rpm'].factor` が帯の単位へ揃ったら
（＝ `rpm_max / RPM_SCENARIOS[PLAN_BAND_BY_FORM['長尺 お金']]`）、
印字と実効が一致するので、この検査の後半は要りません。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("_eta_for_test", ROOT / "scripts" / "eta.py")
assert _spec and _spec.loader
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def test_腕の行が天井の理由を運ぶこと() -> None:
    """`lever_days()` の行に `cap_why` があること。

    **`caps` を `{腕: 倍率}` に絞ると、理由はそこで消えます。**
    消えると `headline()` は「切っている物」を名指しできず、
    毎回「自分で探すところから」に戻ります。
    """
    import inspect
    src = inspect.getsource(eta.lever_days)
    assert '"cap_why"' in src, (
        "`lever_days()` の行が `cap_why` を運んでいません —— "
        "`headline()` は切っている物を名指しできなくなります"
    )
    assert "cap_whys" in src, (
        "`caps` から倍率だけを取り出して理由を捨てています"
        "（`_capped_arms()` の `cap_why` を並べて運ぶこと）"
    )


def test_rpmが切られている回は切っている物を名指しすること() -> None:
    """`headline()` が `rpm` の切り所に触れていること（本文の側）。"""
    import inspect
    src = inspect.getsource(eta.headline)
    assert "rpm_mix.rule_capped()" in src, (
        "`rpm` の切り所（`rpm_mix.rule_capped()` ＝ 規則 1本/日）が"
        "頭の行に名指しされていません"
    )
    assert '"rpm" in _clipped' in src, (
        "`rpm` が切られた回にだけ出す形になっていません"
        "（切られていない回に出すと、読む側の手順が増えます）"
    )
