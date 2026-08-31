"""**判定の規則そのものが、どれだけ当てられるかを測る。**

## なぜ要るか（2026-08-20 05:2x に測って作った）

`config/hypotheses.yaml` の走っている A/B は2件とも、判定をこう書いています。

    問いの群の engaged 比率の**中央値**が、条件の群の中央値を
    **上回っていない**（同点も外れとみなす）。どちらの群も 8本に満たなければ判定しない。
    （engaged の実測幅は 12.2%〜46.8% ＝ 3.8倍。**8対8 なら、中央値の
     入れ替わりで倍半分の差は見分けられます。**）

**括弧の中は、一度も確かめられていませんでした。** 実データの engaged 比率
（`data/scan.jsonl` の最新点・再生30以上の 21本）から取り直して数えると:

    効きが**まったく無い**とき（倍率 1.0）に「上回った」と出る率
      n=8対8   **49%**
      n=30対30 **47%**   ← **本数を増やしても下がりません**

**規則に閾値が無いので、これは構造的です。** 差がゼロなら中央値の大小は
コイン投げで、**n をいくら積んでも 50% のままです。**
「倍半分なら見分けられる」のほうは当たっていました（倍率 2.0 で 98%）。
**外れていたのは「効きが無いときに何と言うか」のほう**です。

そして `next_if_false` は「題も冒頭も空振りなら題材の側」＝ M20 へ進みます。
`scripts/eta.py` が名指しする**唯一の近い帯**（ショート高・1本あたり **1.3倍**）を、
**コイン投げで畳むか続けるかが決まる**形でした。

## 直し方（この回で入れたもの）

**順位和検定（片側・Mann–Whitney）を門に足す。** 同じ実データで測り直すと、
空振り率は n によらず α に張り付き、検出力は n とともに上がります:

    α=0.20    n=8   空振り 18%  ／ 1.3倍を当てる率 **64%**
              n=16  空振り 20%  ／ 1.3倍を当てる率 **82%**   ← 床をここへ
              n=25  空振り 20%  ／ 1.3倍を当てる率 91%

**床を 8 → 16 に上げました**（`ab_split.MIN_PER_GROUP`）。
理由は「厳しくしたい」ではなく、**狙っている 1.3倍を 8本では見分けられない**からです。
まだ1本も判定していない時点で直しています（結果を見てから動かしたのではありません）。

## 割り引いて読むこと

- **標本は 21本しかありません。** ここから作った当てっこは、
  21個の値の外側を知りません。**本数が増えたら測り直すこと**（数は毎回この場で取り直します）
- engaged 比率は上が 100% で頭打ちなので、倍率をかけた側は 100 で止めています。
  **大きい倍率ほど、ここで押し潰されて検出力が過小に出ます**（安全側）
- 「倍率」は engaged 比率にかける数で、**再生数の倍率ではありません。**
  再生との順位相関は +0.66（`status.py`）で、**1対1ではありません**
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "data" / "scan.jsonl"

#: 率が壊れる本を落とす床（`status.py` の順位相関と同じ数）。
MIN_VIEWS = 30

#: 空振り（効きが無いのに「上回った」と出る）を、ここまでに抑える。
ALPHA = 0.20

#: 「当てられる」と呼ぶ率。
TARGET_POWER = 0.80

#: 当てたい効きの大きさ。`scripts/eta.py` のいちばん近い帯（ショート高）が
#: 要求する **1本あたり 1.3倍** から取っています。**eta が動いたらここも動かすこと。**
TARGET_RATIO = 1.3

#: 撃つ回数。増やすほど細かくなりますが、**種は固定**なので返りは毎回同じです。
TRIALS = 4000
SEED = 20260820


def observed_ratios(path: Path | None = None) -> list[float]:
    """実データの engaged 比率（%）を、動画べつに。**API を1単位も使いません。**

    `data/scan.jsonl` の**最後の行**（＝いちばん新しい全走査）から引きます。
    再生 `MIN_VIEWS` 未満は落とします —— 分母が小さいと率が壊れるからで、
    `status.py` の順位相関が使っている床と同じ数です。
    """
    src = path or SCAN
    if not src.exists():
        return []
    last: dict[str, object] = {}
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            last = json.loads(line)
        except ValueError:
            continue
    values = last.get("values") or {}
    if not isinstance(values, dict):
        return []
    views: dict[str, float] = {}
    engaged: dict[str, float] = {}
    for key, val in values.items():
        parts = str(key).split(".")
        if len(parts) != 3 or parts[0] != "動画":
            continue
        try:
            num = float(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if parts[2] == "views":
            views[parts[1]] = num
        elif parts[2] == "engagedViews":
            engaged[parts[1]] = num
    out: list[float] = []
    for vid, n in views.items():
        if n < MIN_VIEWS or vid not in engaged:
            continue
        out.append(100.0 * engaged[vid] / n)
    return sorted(out)


def rank_sum_p(treated: list[float], control: list[float]) -> float:
    """片側の順位和検定（Mann–Whitney U）の p。**「treated のほうが大きい」側**。

    正規近似（連続修正つき・同点は 0.5 で数える）。n=8対8 でも、
    実測の空振り率は α に張り付きます（`tests/test_ab_power.py`）。
    **標本が小さいので、これは近似です** —— 使うのは門としてだけで、
    論文に出す数ではありません。
    """
    n1, n2 = len(treated), len(control)
    if n1 == 0 or n2 == 0:
        return 1.0
    u = 0.0
    for a in treated:
        for b in control:
            if a > b:
                u += 1.0
            elif a == b:
                u += 0.5
    mu = n1 * n2 / 2.0
    sd = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
    if sd == 0:
        return 1.0
    z = (u - mu - 0.5) / sd
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def median_rule(treated: list[float], control: list[float]) -> bool:
    """**いま yaml に書いてある規則**。中央値が上回るか（同点は外れ）。"""
    if not treated or not control:
        return False
    return median(treated) > median(control)


def rank_sum_rule(treated: list[float], control: list[float], alpha: float = ALPHA) -> bool:
    """**この回で足した規則**。中央値が上回り、かつ順位和の片側 p が α 以下。"""
    return median_rule(treated, control) and rank_sum_p(treated, control) <= alpha


def hit_rate(
    values: list[float],
    n: int,
    ratio: float,
    *,
    rule=rank_sum_rule,
    trials: int = TRIALS,
    seed: int = SEED,
    cap: float = 100.0,
) -> float:
    """`values` から n本ずつ引いて、`rule` が「上回った」と言う率。

    `ratio` は treated 側にかける倍率。**1.0 なら空振り率**（効きが無いときに
    当たりと言う率）で、**そこが規則の弱点**です。
    """
    if not values or n <= 0:
        return 0.0
    rng = random.Random(seed)
    hits = 0
    for _ in range(trials):
        treated = [min(cap, rng.choice(values) * ratio) for _ in range(n)]
        control = [rng.choice(values) for _ in range(n)]
        if rule(treated, control):
            hits += 1
    return hits / trials


def needed_n(
    values: list[float],
    ratio: float = TARGET_RATIO,
    *,
    rule=rank_sum_rule,
    target: float = TARGET_POWER,
    candidates: tuple[int, ...] = (8, 12, 16, 20, 25, 32, 40, 60, 80, 120),
    trials: int = TRIALS,
    seed: int = SEED,
) -> int | None:
    """`ratio` を `target` の率で当てるのに要る、**片群あたりの本数**。

    届かなければ `None`（＝候補の上限まで積んでも足りない）。
    """
    for n in candidates:
        if hit_rate(values, n, ratio, rule=rule, trials=trials, seed=seed) >= target:
            return n
    return None


@dataclass(frozen=True)
class Verdict:
    """1つの実験の判定規則が、**どれだけ当てられるか**。"""

    sample: int
    n_per_group: int
    ratio: float
    #: 効きが無いときに「上回った」と出る率（いまの規則）
    null_median: float
    #: 効きが無いときに「上回った」と出る率（順位和を足した規則）
    null_ranksum: float
    #: `ratio` を当てる率（順位和を足した規則）
    power: float
    #: `ratio` を `TARGET_POWER` で当てるのに要る片群の本数
    need_n: int | None
    #: **その実験が比べている値**（2026-08-27）。`"engaged"` 以外は、
    #: この当てっこが当たりません（下の `lines()` の註）。
    metric: str = "engaged"

    def lines(self) -> list[str]:
        # --- **engaged で測っていない実験に、この数を出さないこと**（2026-08-27） ---
        #     ここの当てっこは、**実データ 90本の engaged 比率**をブートストラップ
        #     して作っています。`request_form` は**登録**で測るので、当たりません。
        #
        #     実測 2026-08-27、`request_form`（床 72本）にこう出ていました::
        #
        #         片群 72本で 1.3倍は当てられます（**要る本数は 25本**）
        #
        #     床 72本 は登録率 0.0318%（3,066再生に1人）から引いた数です。
        #     25本 ＝ 約 10,500再生 ＝ **期待 3.3人** で、効きが2倍でも
        #     見分けられません。**「72は過剰、25でよい」と読めるこの1行は、
        #     `falsified_if`（上回らなければ外れ・同点も外れ）を通って
        #     `next_if_false` に届き、腕ごと畳みます** —— その腕は `sub_rate` で、
        #     `scripts/eta.py --alloc` が3回 続けて「次の1件はここ」と
        #     名指ししている腕です。**黙って数だけ出さないこと。**
        if self.metric != "engaged":
            return [
                f"  判定の当てっこ: **出しません**（この実験が比べているのは"
                f"**{self.metric}**で、engaged ではありません）",
                f"    `src/ab_power.py` は**実データ {self.sample}本の engaged 比率**から"
                "作った当てっこです。**別の値に当てると、要る本数が嘘になります。**",
                f"    床 {self.n_per_group}本 の出どころは `src/judgeable.MEMBER_SOURCES`"
                "（そこに理由ごと書いてあります）。**床を下げるなら、"
                f"{self.metric}で検出力を引き直してから**下げること —— "
                "`falsified_if` は「上回らなければ外れ」なので、"
                "**見分けられなかっただけの実験が、効かない実験として閉じます**"
                "（`next_if_false` が腕ごと畳みます）。",
            ]
        out = [
            f"  判定の当てっこ（実データ {self.sample}本の engaged 比率から・API 0単位）",
            f"    いまの規則（中央値だけ）: 効きが無くても **{self.null_median:.0%}** で「上回った」と出ます"
            "  ← **コイン投げ。本数を増やしても下がりません**",
            f"    順位和を足すと:           効きが無いとき {self.null_ranksum:.0%}"
            f"（α={ALPHA:.0%}）／ {self.ratio:.1f}倍を当てる率 **{self.power:.0%}**"
            f"（片群 {self.n_per_group}本）",
        ]
        if self.need_n is None:
            out.append(
                f"    [!] **{self.ratio:.1f}倍は、片群120本まで積んでも {TARGET_POWER:.0%} に届きません。**"
                "狙う差のほうを大きく取り直すこと"
            )
        elif self.need_n > self.n_per_group:
            out.append(
                f"    [!] **{self.ratio:.1f}倍を {TARGET_POWER:.0%} で当てるには片群 {self.need_n}本**"
                f"（＝両群で {self.need_n * 2}本）**要ります。**いまの床は {self.n_per_group}本です"
            )
        else:
            out.append(
                f"    片群 {self.n_per_group}本で {self.ratio:.1f}倍は当てられます"
                f"（要る本数は {self.need_n}本）"
            )
        return out


def verdict(
    n_per_group: int,
    *,
    values: list[float] | None = None,
    ratio: float = TARGET_RATIO,
    trials: int = TRIALS,
    seed: int = SEED,
    metric: str = "engaged",
) -> Verdict | None:
    """実データで測った、判定規則の当てっこ。標本が取れなければ `None`。

    `metric` は**その実験が比べている値**（既定 `"engaged"`）。
    ここの当てっこは engaged 比率のブートストラップなので、
    **別の値の実験に数を出さないこと** —— `Verdict.lines()` の註。
    """
    vals = observed_ratios() if values is None else values
    if len(vals) < 5:
        return None
    return Verdict(
        sample=len(vals),
        n_per_group=n_per_group,
        ratio=ratio,
        metric=metric,
        null_median=hit_rate(vals, n_per_group, 1.0, rule=median_rule, trials=trials, seed=seed),
        null_ranksum=hit_rate(vals, n_per_group, 1.0, trials=trials, seed=seed),
        power=hit_rate(vals, n_per_group, ratio, trials=trials, seed=seed),
        need_n=needed_n(vals, ratio, trials=trials, seed=seed),
    )


def table(values: list[float] | None = None, *, trials: int = TRIALS) -> str:
    """人が読む表。`scripts/ab_split.py --power` が出します。"""
    vals = observed_ratios() if values is None else values
    if len(vals) < 5:
        return "**標本が足りません**（engaged 比率の読める本が 5本未満）。`data/scan.jsonl` を見ること。"
    lines = [
        f"=== 判定規則の当てっこ（実データ {len(vals)}本・再生{MIN_VIEWS}以上・種 {SEED} で固定）===",
        f"  中央値 {median(vals):.1f}%  幅 {min(vals):.1f}%〜{max(vals):.1f}%"
        f"（{max(vals) / max(min(vals), 1e-9):.1f}倍）",
        "",
        "  片群  いまの規則（中央値だけ）      順位和を足した規則",
        "         効き無し  2.0倍          効き無し  1.3倍  1.5倍  2.0倍",
    ]
    for n in (8, 12, 16, 25, 40):
        m0 = hit_rate(vals, n, 1.0, rule=median_rule, trials=trials)
        m2 = hit_rate(vals, n, 2.0, rule=median_rule, trials=trials)
        r0 = hit_rate(vals, n, 1.0, trials=trials)
        r13 = hit_rate(vals, n, 1.3, trials=trials)
        r15 = hit_rate(vals, n, 1.5, trials=trials)
        r2 = hit_rate(vals, n, 2.0, trials=trials)
        lines.append(
            f"  {n:4d}    {m0:7.0%}  {m2:5.0%}           {r0:7.0%}  {r13:5.0%}  {r15:5.0%}  {r2:5.0%}"
        )
    need = needed_n(vals, TARGET_RATIO, trials=trials)
    lines += [
        "",
        "  **いまの規則の「効き無し」の列を見ること。** n を増やしても下がりません ——",
        "  閾値が無いので、差がゼロなら中央値の大小は**コイン投げ**です。",
        f"  `eta.py` のいちばん近い帯が要る **{TARGET_RATIO:.1f}倍** を {TARGET_POWER:.0%} で当てるには、"
        + (f"**片群 {need}本**（両群 {need * 2}本）。" if need else "**片群120本でも届きません。**"),
    ]
    return "\n".join(lines)
