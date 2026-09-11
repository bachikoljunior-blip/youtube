"""**掃き直すかは、余裕ではなく `per_lap` が決める。** 印字と覆る条件の食い違いを閉じた。

2026-09-11 11:2x・optimizer・Opus。

**踏んだ形**: この回に余裕の列が **2.985** で門（3.0倍）を切り、道具は
「**切った周: 09-11T10:46 2.985** ＝ 掃き直すこと」と印字しました。
ところが `ceiling_rate()` の覆る条件 (1) は **`per_lap` の側が主語**で、こう書いてあります:

    (1-a) 余裕が門を切り、**かつ** `per_lap` が 1.0% を越えていたら 掃き直す
          （軽いままなら **08:5x の掃きの行を読むだけでよい** ＝ 余裕は着地を順序づけません）
    (1-b) `per_lap` が 1.0% を越えた回は、**余裕の数に関わらず 1度 掃く**

この回の `per_lap` は **0.552%**（門の半分）＝ **掃き直さなくてよい回**でした。
＝ 道具は **要らない回に「掃け」と言い、(1-b) の要る回には黙っていました**。
掃きは 144点 の盤で、次の回の手を丸ごと1つ食います。

**陽性対照**（壊したら落ちるまで撃つ・METHOD §5 の教訓の形3つ目）:
**撃って落とした**（この回・`.pyc` を消してから ＝ METHOD §5 教訓の形 6つ目）:
`sweep_verdict` から `per_lap` の枝を外す（余裕だけで決める）と **4件**／
門の数を関数の中へ焼き込むと **1件**／`margin_line` が `sweep_words` を通らない形に戻すと **1件**。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quota  # noqa: E402


def test_門を切っても_per_lap_が軽ければ掃かない():
    """**この回に実際に踏んだ組**（余裕 2.985・`per_lap` 0.552%）。"""
    v = quota.sweep_verdict(2.985, 0.552)
    assert v["sweep"] is False and v["why"] == "gate_light"
    w = quota.sweep_words(2.985, 0.552)
    assert "掃き直さなくてよい" in w and "掃き直すこと" not in w


def test_門を切って_per_lap_が重ければ掃く():
    v = quota.sweep_verdict(2.985, 1.4)
    assert v["sweep"] is True and v["why"] == "heavy"
    assert "掃き直すこと" in quota.sweep_words(2.985, 1.4)


def test_門の上でも_per_lap_が重ければ掃く():
    """**(1-b) —— それまで印字に1度も出ていなかった枝。**

    重い側は 余裕 3倍 でも 97% に着きます（`ceiling_rate()` の掃き・09/11 08:5x）。
    ＝ **門の上だから安心、とは言えません。**
    """
    v = quota.sweep_verdict(3.4, 1.2)
    assert v["sweep"] is True and v["why"] == "heavy"
    assert "掃き直すこと" in quota.sweep_words(3.4, 1.2)


def test_門の上で_per_lap_も軽ければ何も足さない():
    assert quota.sweep_verdict(3.4, 0.552) == {"sweep": False, "why": "none"}
    assert quota.sweep_words(3.4, 0.552) == ""


def test_per_lap_が読めない回は掃く側に倒すこと():
    """`margin_line(n)` を `per_lap` 無しで呼ぶ古い口は、いままでどおりの文になること。"""
    v = quota.sweep_verdict(2.985, None)
    assert v["sweep"] is True and v["why"] == "unknown"
    assert "掃き直すこと" in quota.sweep_words(2.985, None)


def test_門の数は_1か所(monkeypatch):
    """**2か所に持たないこと**（`CEILING_MARGIN_GATE` が 07:5x に踏んだのと同じ形）。"""
    monkeypatch.setattr(quota, "SWEEP_PER_LAP_GATE", 0.4)
    assert quota.sweep_verdict(2.985, 0.552)["why"] == "heavy", \
        "門を動かしたら、同じ `per_lap` の判定も動くこと"
    src = (Path(__file__).resolve().parents[1] / "scripts" / "quota.py").read_text(encoding="utf-8")
    assert src.count("per_lap) > 1.0") == 0, "生の 1.0 を関数の中に焼き込まないこと"


def test_印字の口は_margin_line_と_pace_の両方を通ること(tmp_path, monkeypatch):
    """**同じ問いに 2つ の答えを出さないこと** —— どちらも `sweep_words` を通す。"""
    f = tmp_path / "model_choice.jsonl"
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in [
        {"at": "2026-09-11T10:00:39+09:00", "work_kind": "hourly:leverage",
         "model": "fable", "reach_ceiling_margin": 3.011},
        {"at": "2026-09-11T10:46:39+09:00", "work_kind": "hourly:leverage",
         "model": "opus", "reach_ceiling_margin": 2.985},
    ]), encoding="utf-8")
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", f)
    monkeypatch.setattr(quota, "ROUNDS_LOG", tmp_path / "no-rounds.jsonl")

    light = quota.margin_line(per_lap=0.552)
    assert "**切った周: 09-11T10:46 2.985**" in light
    assert "掃き直さなくてよい" in light
    heavy = quota.margin_line(per_lap=1.4)
    assert "掃き直すこと" in heavy
    bare = quota.margin_line()
    assert "掃き直すこと" in bare, "`per_lap` を渡さない呼びは、いままでどおり"

    src = (Path(__file__).resolve().parents[1] / "scripts" / "quota.py").read_text(encoding="utf-8")
    assert "着地を信じずに掃き直すこと" not in src, \
        "`pace_report` が余裕だけで「掃き直すこと」と言う形を残さないこと"
    assert src.count("margin_line(per_lap=") == 1, "`--pace` は `per_lap` を渡して呼ぶこと"
