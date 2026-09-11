"""**親の【枠】の行は、門に当てる側を名指しすること**（2026-09-11 13:2x・optimizer・Opus）。

**踏んだ形**: その行は「床に従えば **99.4%**・いまの間隔のまま **99.4%**（門は **98%**）」と
**2つ の数と門**を並べるだけで、**どちらに当てるかを1度も言っていません**でした。
2つ は 1周の重さ（`per_lap`）が動くと大きく割れます —— 床の側は 0.20 まで平ら、
間隔の側は比例して落ちる（盤は `quota.short_verdict` の註）。
＝ **サブが読む側を選べてしまう形**で、しかも「短く終わる」は 1周 を軽くする手そのものなので、
間隔の側で読むと **門は自分が許した手で下がる数を読む**ことになります。

**きょうの状態を不変条件として書かないこと**（METHOD §5 教訓の形 6つ目）＝
この検査は着地の数そのものを当てません（日が経てば門を渡る）。当てるのは
**行が側を名指ししているか**と、**`SHORT_LANDING_GATE` と同じ門を印字しているか**だけです。

**陽性対照**（`.pyc` を消してから撃った）: 名指しの句を消すと **1件**／
`blind` の枝ごと外すと **1件**。
**文言を言い換えただけでは落ちません**（1度 試した）—— この検査が当てているのは
**句が在るか**で、文の言い回しではありません。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402
import spawn_prompt  # noqa: E402


def _reset_line() -> str | None:
    for line in spawn_prompt._quota_block().splitlines():
        if "リセット時" in line and "床に従えば" in line:
            return line
    return None


def test_門に当てる側を名指しする() -> None:
    line = _reset_line()
    if line is None or "いまの間隔のまま" not in line:
        return                      # 目盛りが無い回は、この行そのものが出ません
    assert "当てるのは「床に従えば」の側" in line
    assert "short_verdict" in line


def test_門の数は_quota_の定数と同じ() -> None:
    """**2か所に持たないこと** —— METHOD §5 と `SHORT_LANDING_GATE` と この行で 3か所 になる。"""
    line = _reset_line()
    if line is None or "いまの間隔のまま" not in line:
        return
    assert f"門は **{quota.SHORT_LANDING_GATE:.0f}%**" in line


def test_窓が残りより長い回は_間隔の側で読むなと言う() -> None:
    """`short_verdict` の `blind` と**同じ問い**を、親の本文でも言うこと。"""
    block = spawn_prompt._quota_block()
    p = quota.pace()
    if not p or p.get("reach_carry") is None:
        return
    seg_h = (p.get("seg") or {}).get("hours")
    if seg_h is None or p.get("left_hours") is None:
        return
    blind = float(seg_h) > float(p["left_hours"])
    assert ("「いまの間隔のまま」では門を読まないこと" in block) is blind
