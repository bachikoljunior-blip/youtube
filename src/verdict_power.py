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

#: 取り違え率の上限。**alpha と beta の両方**がこれ以下でないと、門は見分けられない。
MAX_ERR = 0.20


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


def _pois_le(k: int, lam: float) -> float:
    """P(X <= k) —— ポアソン。"""
    if k < 0:
        return 0.0
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def power(baseline: float, n: int, gate: int, target: float = 2.0) -> dict:
    """門「再生 `n` で `gate` 人以上なら生き残る」の、**両側の取り違え率**。

    `alpha` 効きがまったく無いのに生き残ってしまう率
    `beta`  `target` 倍の効きがあるのに外してしまう率

    **片側だけ見ないこと。** 2026-08-08 の判定は alpha=0.07 と小さい一方、
    beta=0.43 —— **主張どおりの効きがあっても、4割は「外れ」と出る門**でした。
    """
    lam0, lam1 = n * baseline, n * baseline * target
    alpha = 1.0 - _pois_le(gate - 1, lam0)
    beta = _pois_le(gate - 1, lam1)
    return {
        "n": n, "gate": gate, "baseline": baseline, "target": target,
        "expected_null": lam0, "expected_target": lam1,
        "alpha": alpha, "beta": beta,
        "p_zero_if_no_effect": math.exp(-lam0),
        "detects_nothing": alpha > MAX_ERR or beta > MAX_ERR,
    }


def zero_means(baseline: float, n: int) -> dict:
    """**0人という観測が、何を言っているか。** 閉じた判定の見直しに使う。"""
    return {
        "n": n,
        "p_zero_if_no_effect": math.exp(-n * baseline),
        "rules_out_above": (3.0 / n) if n else float("inf"),
        "rules_out_multiple": ((3.0 / n) / baseline) if (n and baseline) else float("inf"),
    }


def gate_for(baseline: float, n: int, target: float = 2.0) -> int | None:
    """**いまの n のまま、見分けられる門はあるか。** 無ければ `None`。

    `power()` は「この門は駄目だ」しか言いません。**駄目なのが n なのか
    門の置き場所なのかを、一度も切り分けていませんでした**（2026-08-28 に踏んだ）。
    実測では、**駄目な門 4件 のうち 3件 は n が足りていて、門だけが外れて**いました:

        チャンネルのホーム   n=22,549  門 8人 → alpha 43%   **門 10人 なら 19%/9%**
        途中の依頼          n=30,000  門 10人 → alpha 48%  **門 14人 なら 10%/10%**
        族べつの登録率       n=13,015  門 5人 → alpha 40%   **どの門でも駄目**（n が足りない）

    **門が null の期待値のすぐ上に置かれると、alpha はほぼ 50% になります。**
    「効きなし」の半分が生き残るので、**その前提は、効かない処置を通します。**
    上の2件は率（`0.0355%` / `0.0318%`）で門を書いており、
    **その率が実測の率とほぼ同じ**でした ＝ 門を「平均どおり」に置いた形です。

    **同じ n=30,000 の隣の前提は `14人未満` と人数で書いてあり、通っています。**
    答えは、最初から1件 隣に在りました。
    """
    if baseline <= 0 or n <= 0:
        return None
    for gate in range(1, int(n * baseline * max(target, 1.0) * 4) + 12):
        q = power(baseline, n, gate, target)
        if not q["detects_nothing"]:
            return gate
    return None


def n_for_gate(baseline: float, target: float = 2.0, start: int = 0,
               cap: int = 2_000_000) -> int | None:
    """**門で棄却する設計**が成り立ちはじめる n。無ければ `None`。

    `n_for()` は「**0人**が出たら棄却する」ための数です。ここの前提は
    どれも **人数の門**で棄却するので、**答えるべき問いが違います。**
    実測では `n_for()` のほうが小さく出るため、**既に持っている再生数より
    小さい数を「要ります」と印字**していました（15,000 持っている前提に
    「9,425再生 要ります」）。**それを読んだ回は、待てば直ると考えます。**

    実測（登録率 0.0318%・2倍を見分ける）: `n_for()` **9,425** に対し、
    **門で見分けられるようになるのは 20,000 前後**。**2倍 以上ちがいます。**

    **`start` より大きい n しか返しません。** 返り値が「いま持っている数」以下だと、
    読んだ回は「もう足りている」と読み、**実際には見分けられないまま判定します。**

    **飛び石になります**（ポアソンは整数の門しか置けない）。実測 2026-08-28:
    **n=14,293 では門 7人 が通る**（alpha 17% ／ beta **19.94%**）のに、
    **n=15,000 では通りません**（門 7人 の alpha が 20.3%・門 8人 の beta が 26.5%）。
    **増やしたのに見分けられなくなります。** 崖の上を答えにしないため、
    **n と n×1.05 の両方で門が立つところ**まで進みます。
    """
    if baseline <= 0 or target <= 1:
        return None
    n = max(start + 1, int(1 / baseline))
    step = max(1, n // 200)
    while n <= cap:
        if (gate_for(baseline, n, target) is not None
                and gate_for(baseline, int(n * 1.05), target) is not None):
            return n
        n += step
    return None


def n_for(baseline: float, multiple: float, confidence: float = 0.95) -> int:
    """「0人」で `multiple` 倍の効きを棄却するのに要る再生数。"""
    if baseline <= 0 or multiple <= 1:
        return 0
    return math.ceil(-math.log(1 - confidence) / (baseline * (multiple - 1)))


_VIEWS = re.compile(r"([0-9][0-9,]{2,})\s*再生")
#: **括弧の中は、その前提の標本ではありません。**（2026-08-28 に踏んだ）
#: `falsified_if` は「いくつ集まったら判定するか」と並べて、
#: **比べる相手の出どころ**を括弧で書きます:
#:
#:     合計再生が 15,000 に達した時点で … **0.0355%（… 22,549再生 → 8人）を上回らなければ**
#:
#: 素直に「最初の N再生」を取ると **22,549**（＝ 2026-05-01〜08-17 の参照母集団）を
#: 標本の大きさだと読みます。**実際の標本は 15,000。** 1.5倍 ちがい、
#: そこから出す門は 10人 対 7人 で**別の数**になります。
#: 診断だけの頃は「N再生 要ります」が少しずれるだけでしたが、
#: **門の数字を名指しするようになった以上、ここがずれると嘘を出します。**
_PARENS = re.compile(r"[（(][^（()）]*[）)]")
_PCT = re.compile(r"([0-9]*\.?[0-9]+)\s*%")
#: 「**14人未満**なら外れ」のように、**人数で置いた門**。率より優先して読む
#: （率で書くと、地の文にある実測の率を拾ってしまう。2026-08-24 に実際に誤読した）。
_COUNT = re.compile(r"\*{0,2}([0-9]+)\s*人\*{0,2}\s*(?:未満|を下回)")
#: **その前提が「何倍を狙っている」と言っているか。** 既定は2倍。
#: 10倍を狙う門を2倍の物差しで測ると、まともな設計を「見分けられない」と誤って挙げる
#: （2026-08-24、「長尺の登録率は1桁以上高い」で実際に誤判定した）。
_TARGET = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*倍")
_ORDER = re.compile(r"1\s*桁以上|一桁以上")


def claimed_target(claim: str, cond: str) -> float:
    """claim/反証条件が名乗っている倍率。無ければ 2.0。"""
    if _ORDER.search(claim) or _ORDER.search(cond):
        return 10.0
    m = _TARGET.search(claim)
    return float(m.group(1)) if m else 2.0


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
        # **括弧を落としてから標本を探す**（`_PARENS` の註）。
        # 落とした側で見つからないときだけ、元の文へ戻る。
        bare = _PARENS.sub("", cond)
        vm = _VIEWS.search(bare) or _VIEWS.search(cond)
        if not vm:
            continue
        n = int(vm.group(1).replace(",", ""))
        cm, pm = _COUNT.search(cond), _PCT.search(cond)
        if cm:                       # 人数で置いた門。**こちらが優先**
            gate, label = int(cm.group(1)), f"{cm.group(1)}人未満"
        elif pm:
            rate = float(pm.group(1)) / 100.0
            gate, label = max(1, round(rate * n)), f"{pm.group(1)}%未満"
        else:
            continue
        found.append({
            "claim": claim,
            "n": n,
            "gate": gate,
            "gate_label": label,
            "target": claimed_target(claim, cond),
            "outcome": (re.search(r"\n    outcome:\s*(\w+)", block) or [None, ""])[1],
        })
    return found


def main() -> int:
    base, views, subs = baseline_rate()
    print("=== その判定は、何かを見分けられたのか（登録率・ポアソン）===")
    print(f"  実測の登録率: **{base*100:.4f}%**  （{views:,}再生 → {subs}人・`data/scan.jsonl`）")
    print(f"  ＝ 再生 {1/base:,.0f} 回につき1人。**しきい値はこの数にかけること。**")
    print(f"  門は「効きなしで生き残る率」と「**その前提が名乗った倍率**があるのに外す率」の"
          f"**両方**が {MAX_ERR:.0%} 以下でないと、見分けられません。")
    print()

    rows = scan_hypotheses()
    if not rows:
        print("  （反証条件が「N再生でX%／N人未満」の形の前提は見つかりませんでした）")
    bad = 0
    fixable = 0
    for r in rows:
        q = power(base, r["n"], r["gate"], r["target"])
        ok = "見分けられます" if not q["detects_nothing"] else "**見分けられません**"
        print(f"  [{r['outcome'] or '未判定'}] {r['claim'][:44]}")
        print(f"      n={r['n']:,}再生・門 {r['gate_label']}  "
              f"（効きなしなら {q['expected_null']:.1f}人／"
              f"{r['target']:g}倍なら {q['expected_target']:.1f}人）")
        print(f"      効きなしで生き残る **{q['alpha']:.0%}** ／ "
              f"{r['target']:g}倍あるのに外す **{q['beta']:.0%}**"
              f"  → {ok}")
        if q["detects_nothing"]:
            bad += 1
            z = zero_means(base, r["n"])
            # **n が足りないのか、門の置き場所が悪いのかを切り分ける**（2026-08-28）。
            # ここは長らく「N再生 要ります」しか出しておらず、**実測 3/4 件で
            # 既に持っている再生数より小さい数**を「要ります」と言っていました
            # （22,549 持っている前提に「9,425再生 要ります」）。
            # `n_for()` は「**0人**で棄却する」ための数で、
            # **人数の門で棄却するこの前提とは、別の問い**です。
            g = gate_for(base, r["n"], r["target"])
            if g is not None:
                qg = power(base, r["n"], g, r["target"])
                fixable += 1
                print(f"      → **n は足りています。門の置き場所が外れています。**"
                      f" **門を {g}人未満 に直せば見分けられます**"
                      f"（効きなしで生き残る {qg['alpha']:.0%} ／ "
                      f"{r['target']:g}倍あるのに外す {qg['beta']:.0%}）")
                if r["gate_label"].endswith("%未満"):
                    print(f"         いまは率（{r['gate_label']}）で書いてあり、"
                          f"**実測の率 {base*100:.4f}% とほぼ同じ ＝ 門を「平均どおり」に置いた形**です。"
                          f" **人数で書き直すこと。**")
            else:
                need = n_for_gate(base, r["target"], start=r["n"])
                # **`n_for()` を出さないこと。**あれは「0人で棄却する」ための数で、
                # 人数の門で棄却するこの前提には小さすぎます
                # （実測: 15,000 持っている前提に「9,425 要ります」と出していた）。
                more = f"**あと {need - r['n']:,}再生**" if need and need > r["n"] else "**さらに**"
                tail = (f"**門で見分けられるようになるのは {need:,}再生 から**（{more}）"
                        if need else "**この倍率は、現実的な n では門で見分けられません**")
                print(f"      0人が出ても、否定できるのは実測の **{z['rules_out_multiple']:.1f}倍超**まで。"
                      f" **どの門に置いても、この n では見分けられません** —— {tail}")
        print()

    print("=== 実測の率で引き直した必要数（「0人」で棄却する場合）===")
    for mult in (1.5, 2.0, 3.0):
        print(f"  {mult}倍: **{n_for(base, mult):,}再生**")
    print()
    if bad:
        print(f"  → **見分けられない門が {bad} 件あります。**"
              " ここで閉じた前提は証拠ではありません。**開け直すこと。**")
        if fixable:
            print(f"  → **うち {fixable} 件は、再生を1回も足さずに直せます**"
                  " —— 門の数字を上の行のとおりに書き換えるだけ"
                  "（`config/hypotheses.yaml` の `falsified_if`）。"
                  " **待つ必要はありません。**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
