"""**その判定は、そもそも何かを見分けられたのか。**

    python -m src.verdict_power

## なぜ要るか（2026-08-24 に、登録の誘導を止めた判定を数え直して作った）

`config/hypotheses.yaml` の冒頭は、こう書いています。

    **しきい値は必ず掛け算してから置くこと。** 一度、登録率の検証しきい値を
    「100再生」と勘で置いた。登録率0.3%なら100再生の期待値は0.3人で、
    0人でも何も否定できない。**検出できない条件を反証条件にしてはいけない。**

**掛け算はされました。かける相手を間違えました。**

「ショートの最後でチャンネルの性格を言うと登録につながる」の反証条件は
`3000再生で0.1%未満なら外れ` で、note にこう書いてあります ——
「**3000再生なら期待9人なので、0人ならさすがに否定できる**」。
期待9人が出るのは **0.3%** を代入したときです。**0.3% は業界の一般値で、
このチャンネルが一度も出したことのない数字**でした。

実測は **0.0318%**（`data/scan.jsonl`）。同じ3000再生の期待値は **0.95人**で、
**0人はごく普通に起きます（P=0.39）。** つまりこの実験は、
効きがまったく無い場合と、効きがあった場合とを、**最初から見分けられません。**

にもかかわらず判定は `outcome: falsified` / `effect: 1.0`（＝動かなかった）で閉じ、
`src/script_writer.py` に「**チャンネル登録お願いしますとは書かない。
依頼しても取れないことは測って分かっている**」が入りました。
**測って分かってはいません。** 3回に1回は素で起きる目を、証拠として扱っています。

**これは1件の間違いではなく、型です。** だから機械で当てます:

    借りてきた率で n を決めると、自分の率では検出力ゼロの実験になる。

## 何を見るか

反証条件が「**N再生でX%を下回ったら外れ**」の形をしているとき、
**実測の率**を入れて次を数えます。

    期待値 λ = N × 実測の率
    P(0人 | 効きなし) = exp(-λ)      ← これが大きいと、0人は証拠になりません
    しきい値の倍率 = X% ÷ 実測の率    ← これが大きいと、生き残るほうが不可能です

`P(0人|効きなし) > 0.10` なら **検出できない実験**として挙げます。

**この道具は率（ポアソン）専用です。** 中央値の比べ合いは `src/ab_power.py`。
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "data" / "scan.jsonl"
HYP = ROOT / "config" / "hypotheses.yaml"

#: 「0人」が効きなしでも普通に起きる、とみなす確率。これを超えたら証拠にならない。
NOISE_P = 0.10


def baseline_rate() -> tuple[float, int, int]:
    """**実測の登録率**を返す（率, 再生, 登録）。借りてきた一般値は使わない。"""
    row = None
    with SCAN.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
    if not row:
        raise RuntimeError(f"{SCAN} が空です")
    v = row["values"]
    views = int(v.get("合計.views", 0) or 0)
    subs = int(v.get("合計.subscribersGained", 0) or 0)
    return (subs / views if views else 0.0), views, subs


def power(baseline: float, n: int, threshold: float | None = None) -> dict:
    """再生 `n` の標本が、実測の率 `baseline` に対して何を見分けられるか。"""
    lam = n * baseline
    out = {
        "n": n,
        "baseline": baseline,
        "expected": lam,
        "p_zero_if_no_effect": math.exp(-lam),
        # 0人という観測が否定できる率の上限（片側95%）
        "rules_out_above": 3.0 / n if n else float("inf"),
    }
    out["rules_out_multiple"] = (out["rules_out_above"] / baseline) if baseline else float("inf")
    out["detects_nothing"] = out["p_zero_if_no_effect"] > NOISE_P
    if threshold is not None:
        out["threshold"] = threshold
        out["threshold_multiple"] = threshold / baseline if baseline else float("inf")
    return out


def n_for(baseline: float, multiple: float, confidence: float = 0.95) -> int:
    """「0人」で `multiple` 倍の効きを棄却するのに要る再生数。"""
    if baseline <= 0 or multiple <= 1:
        return 0
    return math.ceil(-math.log(1 - confidence) / (baseline * (multiple - 1)))


_VIEWS = re.compile(r"([0-9][0-9,]{2,})\s*再生")
_PCT = re.compile(r"([0-9]*\.?[0-9]+)\s*%")
#: 「**14人未満**なら外れ」のように、**人数で置いた門**。率より優先して読む
#: （率で書くと、地の文にある実測の率を拾ってしまう。2026-08-24 に実際に誤読した）。
_COUNT = re.compile(r"\*{0,2}([0-9]+)\s*人\*{0,2}\s*(?:未満|を下回)")


def scan_hypotheses() -> list[dict]:
    """`falsified_if` が「N再生でX%」の形のものを拾い、検出力を数える。"""
    if not HYP.exists():
        return []
    text = HYP.read_text(encoding="utf-8")
    found = []
    # claim ごとに切って、その塊の falsified_if だけを見る
    for block in re.split(r"\n  - claim:", text)[1:]:
        claim = block.splitlines()[0].strip().strip('"\'')
        m = re.search(r"falsified_if:(.*?)(?=\n    [a-z_]+:)", block, re.S)
        if not m:
            continue
        cond = m.group(1)
        if "登録" not in cond and "登録" not in claim:
            continue
        vm = _VIEWS.search(cond)
        if not vm:
            continue
        n = int(vm.group(1).replace(",", ""))
        cm, pm = _COUNT.search(cond), _PCT.search(cond)
        if cm:                       # 人数で置いた門。**こちらが優先**
            threshold = int(cm.group(1)) / n
        elif pm:
            threshold = float(pm.group(1)) / 100.0
        else:
            continue
        found.append({
            "claim": claim,
            "n": n,
            "threshold": threshold,
            "gate": f"{cm.group(1)}人未満" if cm else f"{pm.group(1)}%未満",
            "outcome": (re.search(r"\n    outcome:\s*(\w+)", block) or [None, ""])[1],
        })
    return found


def main() -> int:
    base, views, subs = baseline_rate()
    print("=== その判定は、何かを見分けられたのか（登録率・ポアソン）===")
    print(f"  実測の登録率: **{base*100:.4f}%**  （{views:,}再生 → {subs}人・`data/scan.jsonl`）")
    print(f"  ＝ 再生 {1/base:,.0f} 回につき1人。**しきい値はこの数にかけること。**")
    print()

    rows = scan_hypotheses()
    if not rows:
        print("  （反証条件が「N再生でX%」の形の前提は見つかりませんでした）")
    bad = 0
    for r in rows:
        p = power(base, r["n"], r["threshold"])
        flag = "**検出できません**" if p["detects_nothing"] else "見分けられます"
        print(f"  [{r['outcome'] or '未判定'}] {r['claim'][:46]}")
        print(f"      n={r['n']:,}再生  期待値 {p['expected']:.2f}人  "
              f"P(0人|効きなし)={p['p_zero_if_no_effect']:.2f}  → {flag}")
        print(f"      門 {r.get('gate','')} ＝ 率 {r['threshold']*100:.4f}% は"
              f"実測の **{p['threshold_multiple']:.1f}倍**（生き残るには、これだけの効きが要る）")
        if p["detects_nothing"]:
            bad += 1
            print(f"      **0人はこの標本では証拠になりません。** "
                  f"1.5倍を棄却するだけでも {n_for(base,1.5):,}再生 要ります")
        print()

    print("=== 実測の率で引き直した必要数 ===")
    for mult in (1.5, 2.0, 3.0):
        print(f"  {mult}倍を「0人」で棄却する: **{n_for(base, mult):,}再生**")
    print()
    if bad:
        print(f"  → **検出できない反証条件が {bad} 件あります。**"
              " ここで閉じた前提は、証拠ではありません。**開け直すこと。**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
