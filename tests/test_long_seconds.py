# -*- coding: utf-8 -*-
"""**長尺の尺を、見積りではなく実物で読むこと。**（2026-09-05 01:5x・毎時の回）

## この検査が守っているもの

`daily_pick.script_seconds()` は `pipeline.CHARS_PER_SECOND`（**5.2字/秒**）で割って、
**「コマの間合いは足していないので、実物はこれ以上になります（下限です）」**
と書いてありました。**実物を測ったら、逆でした。**

    `GFvAcxvDmYM`  台本 7,699字
      5.2字/秒 の見積り  1,481秒 ＝ **24.7分**
      実物 `duration_s`  1,361.1秒 ＝ **22.7分**   ← 見積りより **120秒 短い**

外の長尺 365本 の実測は 20〜25分 **823回/日** 対 25〜30分 **3,507回/日**（×4.3）で、
切れ目は **25分**（`OUTSIDE_LONG_KNEE_SEC`）。**24.7分 は「ほぼ境目」ですが、
22.7分 は帯の真ん中**です —— この 2分 は 09/07 の判定の読み方を変えます。

**推測の向き（「無音を足せば遅くなるはず」）が、そのまま『下限』と書かれていました。**
この検査は、その1行が戻ってこないことと、実物が在るなら実物を読むことを見ます。
"""
import json
from pathlib import Path

import pytest

from src import daily_pick as dp

ROOT = Path(__file__).resolve().parent.parent


def _measured_rates():
    """`duration_s` を持つ本と控えの台本を突き合わせた 字/秒。**API 0単位。**"""
    up = {}
    for line in (ROOT / "data" / "uploaded.jsonl").read_text(
            encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:                                          # noqa: BLE001
            continue
        if r.get("video_id") and r.get("duration_s"):
            up[r["video_id"]] = r
    out = []
    for f in (ROOT / "data" / "critique_queue").glob("*.script.json"):
        vid = f.name.split(".")[0]
        r = up.get(vid)
        if not r:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                          # noqa: BLE001
            continue
        n = sum(len(str(x.get("narration") or ""))
                for x in (d.get("segments") or []) if isinstance(x, dict))
        sec = float(r["duration_s"])
        if n >= 500 and sec > 0:
            out.append((vid, n, sec, n / sec))
    return out


def test_長尺の字_秒は実測とそろっていること():
    """**定数が実物から 5% 以上ずれたら赤にする。** 写した数を放置しないため。"""
    rows = _measured_rates()
    if len(rows) < 5:
        pytest.skip(f"突き合わせられた本が {len(rows)}本 —— 数える標本がありません")
    rates = sorted(r[3] for r in rows)
    med = rates[len(rates) // 2]
    got = dp.LONG_CHARS_PER_SECOND
    assert abs(got - med) / med < 0.05, (
        f"`LONG_CHARS_PER_SECOND` = {got} が実測の中央 {med:.2f}字/秒 から "
        f"{abs(got - med) / med:.1%} ずれています（n={len(rows)}）。"
        f"数え直して置き直すこと（この突き合わせは API 0単位）"
    )


def test_見積りは下限ではない():
    """**5.2字/秒 の見積りは、実物より長く出る。** 「下限」と呼ばないこと。"""
    rows = _measured_rates()
    if len(rows) < 5:
        pytest.skip("標本が足りません")
    from src.pipeline import CHARS_PER_SECOND
    over = [v for v, n, sec, _ in rows if n / CHARS_PER_SECOND > sec]
    assert len(over) >= len(rows) * 0.8, (
        "5.2字/秒 の見積りが実物より短い本が多数あります —— "
        "この検査の前提（見積りは上振れ）を数え直すこと"
    )


def test_公開ずみの本は実物の尺を返すこと():
    """`measured_seconds()` が `duration_s` を読むこと。"""
    assert dp.measured_seconds("GFvAcxvDmYM") == pytest.approx(1361.1, abs=0.5)
    assert dp.measured_seconds("そんな本はない") is None


def test_09_05の枠の本は帯の切れ目の下に在ること():
    """**09/07 の判定を読む回が、22.7分 を 24.7分 と読まないこと。**

    24.7分（旧・5.2字/秒 の見積り）だと切れ目 25分 の**手前 0.3分 ＝ ほぼ境目**で、
    台帳の註は「『手前だから効かないかもしれない』は**弱くなりました**」と書いていました。
    **実物 22.7分 では、その註は成り立ちません**（差 2.3分・帯の真ん中）。
    """
    sec = dp.measured_seconds("GFvAcxvDmYM")
    if sec is None:
        pytest.skip("この本の `duration_s` がまだ在りません")
    assert sec < dp.OUTSIDE_LONG_KNEE_SEC, (
        f"{sec}秒 が切れ目 {dp.OUTSIDE_LONG_KNEE_SEC}秒 の上に在ります —— "
        "台帳の註（帯の遅い側）を数え直すこと"
    )
    assert (dp.OUTSIDE_LONG_KNEE_SEC - sec) / 60 > 1.0, (
        "切れ目との差が 1分 未満 ＝ 「ほぼ境目」に戻っています。註を読み直すこと"
    )


def test_印字が下限だと言っていないこと():
    """**画面の1行に「下限」が残っていないこと。**"""
    lines = dp.draft_length_lines("GFvAcxvDmYM")
    assert lines, "尺の行が1行も出ていません"
    head = lines[0]
    assert "下限" not in head, f"見積りを「下限」と呼ぶ1行が残っています: {head}"
    assert "実物" in head, f"公開ずみなのに実物を読んでいません: {head}"


def test_台帳の註が実物の尺で書き直されていること():
    """**`config/hypotheses.yaml` に「実物はこれ以上」が残っていないこと。**"""
    text = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    bad = "コマの間合いは足していない\n      # ので、実物はこれ以上です。"
    assert bad not in text, (
        "「実物はこれ以上」が台帳に残っています —— 実測は逆（見積りのほうが長い）"
    )
