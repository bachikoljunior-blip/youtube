"""**親の【枠】の判定は、`quota.short_words()` の1行をそのまま運ぶこと**
（2026-09-11 13:2x に足し、**17:0x に当て直した**・optimizer・Opus）。

**13:2x に踏んだ形**: その行は「床に従えば **99.4%**・いまの間隔のまま **99.4%**（門は **98%**）」と
**2つ の数と門**を並べるだけで、**どちらに当てるかを1度も言っていません**でした。
2つ は 1周の重さ（`per_lap`）が動くと大きく割れます —— 床の側は 0.20 まで平ら、
間隔の側は比例して落ちる（盤は `quota.short_verdict` の註）。

**17:0x に踏んだ形（この検査が見ていなかった側）**: 段は**側を名指しした**あとも、
**判定そのもの（引かれたか）を印字していません**でした ＝ サブは毎周 99.4 と 98 を**手で**引き比べます。
13:1x の決めはその逆（「引き比べは `short_verdict` が毎周 印字する ＝ 手で当てないこと」）で、
しかも**門 98% は段の中に literal で**持たれており（`SHORT_LANDING_GATE` と 2か所 ＝
`short_verdict` の覆る条件 (3) が「2か所に持たない」と書いている側）、
`blind` の述語（区間の窓 ＞ 残り）も段が別に書き直していました。

**いま固定するのは 1つ**: 【枠】の段に出る判定の字は、**`quota.short_words()` が出す字そのもの**であること
（2つ の口が違うことを言わない・`trend.channel_line_short` の覆る条件 (2) と同じ族）。
**きょうの状態は当てません**（着地の数も、引かれたかも・§5 教訓の形 6つ目）。

**陽性対照**（`.pyc` を消してから撃った）: 段の側で門を literal に書き戻すと **1件**
（`短く終わってよい` の行が `short_words` の字と食い違う）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402
import spawn_prompt  # noqa: E402


def _block_and_words() -> tuple[str, str] | None:
    """段と、`--pace` が同じ数で出す判定の行。読めない回は None。"""
    p = quota.pace()
    if not p or p.get("reach_floor") is None:
        return None
    # **床が歯止めに当たったかも同じ入力で渡すこと**（2026-09-12 00:5x）——
    # 段の側は渡しているので、ここで落とすと「段だけが出す行」が生まれ、
    # **この検査がその行を見ないまま緑になります**（§5 教訓の形 6つ目の裏）。
    words = quota.short_words(p.get("reach_floor"), p.get("reach_carry"),
                              (p.get("seg") or {}).get("hours"), p.get("left_hours"),
                              p.get("floor_clipped"))
    return spawn_prompt._quota_block(), words


def test_判定の行は_short_words_の字そのもの() -> None:
    got = _block_and_words()
    if got is None:
        return                      # 目盛りが無い回は、この行そのものが出ません
    block, words = got
    for ln in words.splitlines():
        if ln.strip():
            assert ln.strip() in block, f"段が `short_words` と違う字を出しています: {ln.strip()[:120]}"


def test_門の数を段の中で書き直さないこと() -> None:
    """**2か所に持たないこと** —— METHOD §5 と `SHORT_LANDING_GATE` と この段で 3か所 になる。

    段に出てよい門の字は `short_words` が作ったものだけ ＝ **段の側の literal は 0個**。
    """
    got = _block_and_words()
    if got is None:
        return
    block, words = got
    gate = f"{quota.SHORT_LANDING_GATE:.0f}%"
    # 段に出る「門 …%」の数は、`short_words` の行の中にしか無いこと。
    rest = block
    for ln in words.splitlines():
        rest = rest.replace(ln.strip(), "", 1)
    assert f"門は **{gate}**" not in rest
    assert f"門 {gate}" not in rest


def test_窓が残りより長い回は_間隔の側で読むなと言う() -> None:
    """`short_verdict` の `blind` と**同じ問い**を、親の段でも言うこと。

    **述語は段で書き直さない** —— `blind` を出すのは `short_verdict` の 1か所。
    """
    got = _block_and_words()
    if got is None:
        return
    block, _ = got
    p = quota.pace()
    seg_h = (p.get("seg") or {}).get("hours")
    if seg_h is None or p.get("left_hours") is None:
        return
    blind = bool(quota.short_verdict(p.get("reach_floor"), p.get("reach_carry"),
                                     seg_h, p.get("left_hours"))["blind"])
    assert ("「いまの間隔のまま」では読まないこと" in block) is blind
