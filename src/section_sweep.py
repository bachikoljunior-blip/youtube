"""**節を「人が思いつく」のをやめる。** `src/calc/` の関数を機械で掃引して、
崖・頭打ち・逆転・不変を拾う。

    python -m src.section_sweep                 # 全部の表から、形の出たものを並べる
    python -m src.section_sweep --calc kyugyo   # 1本だけ詳しく
    python -m src.section_sweep --shape 不変     # 形で絞る

## なぜ要るか（2026-08-17 に足した）

`src/section_depth.py` が **(A) 新しい表を書く / (B) 既にある表に節を足す** の
2つを出すようにしたのが前の回です。**どちらも「人が中身を思いつく」ところが律速**で、
`scripts/retro.py` が §6 (a2) の問い1を縦に並べると、
**直近8回のうち7回で、いちばん時間を食ったのが「表の中身を決めるところ」**でした
（20〜25分＝1周の半分。`docs/JOURNAL.md` 2026-08-17）。

そして (B) は**桁を変えません** —— 全部の表を上位四分位まで掘って +53節、
(A) の10回ぶんです（`docs/MEANS.md` M17 の最後の項）。
**1日8本を1日97本にはしません。**

前の回の申し送りは、そこで**掘る先ではなく、思いつき方そのもの**を疑いました。

> 桁を変えるなら、節を「人が思いつく」形そのものを疑うこと ——
> `src/calc/` の関数を機械で掃引して、**崖・逆転・一致点を自動で拾う**。
> この回の4節のうち3節は、実際にそういう形で出ています。**掃引で拾える形です。**

**この回の3節も、3つともそうでした**（`src/calc/kyugyo.py`）——
「境目は週4.2日で**動かない**」（不変）、「時給制と月給制で**逆転する**」（逆転）、
「率は月給では**動かない**」（不変）。**人が探したのは形ではなく、
まだ印字していない引数のほうです。形は、引数を動かした後に目で見えました。**

**目で見えるなら、機械にも見えます。**

## 何を拾い、何を拾わないか

拾うのは**引数を1つ動かしたときの、返り値の形**だけです。

    不変   動かしても値が1円も変わらない          → 「約分で消える」節になる
    頭打ち 途中から動かなくなる                  → 「◯◯から上は同じ」節になる
    崖     1点だけ跳ぶ（中央の段差の5倍以上）      → 「1円こえると◯◯円」節になる
    逆転   最大・最小が端ではなく途中にある        → 「いちばん得なのは端ではない」節になる
    帯     途中の一続きだけ値が違い、両端は同じ    → 「◯◯から◯◯までだけ」の節になる

**拾わないもの**（この道具は候補を出すだけで、節にはしません）:

- **意味**。`不変` が出ても、それが動画になる主張かは人が決めます。
  分母がたまたま定数だっただけ、ということもあります
- **正しさ**。掃引は `check_tables()` を通しません。
  節にするなら、そのとき検査を書くこと（**この道具の出力を数字の出どころにしない**）
- **返りが `list` の関数**。行数が引数で変わるので、同じ土俵に載りません
  （`shift_grid` のような表は、いまは対象外です）
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import importlib
import inspect
import io
import math
import pkgutil
import re
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from statistics import median
from typing import Any, Callable, Iterable

from src import calc_axes

# 掃引で使う点の数。**増やすほど遅くなり、形の出方は変わりません**（実測 9 で十分）
GRID = 9
# 崖と呼ぶ段差。**中央の段差の何倍か**。5倍は 2026-08-17 に実物で合わせた値で、
# 3倍だと「なだらかな曲線」が全部崖になり、10倍だと `jidou` の本物を落とします
CLIFF_RATIO = 5.0
# 「動かない」と呼ぶ相対差。円未満の切り捨てがあるので、完全一致では拾えません
FLAT_TOL = 1e-4
# 「意味のある動き」の下限（全体の幅に対する割合）。**丸めの屑を落とすため**。
# 1% は 2026-08-17 に実物で合わせた値（`ratio_span` の 0.08% の山が消え、
# `jidou` の本物の崖は残る）
MEANINGFUL = 0.01

#: 「逆転」の頂上が平らかを見る帯の幅（端からの高さに対する割合）。
#: **この帯に他の内点が入るなら、その x は名指しに耐えません** ——
#: 目盛りを細かくすると同じ高さが他にも出てくるからです（2026-08-18 に実測）。
#: 1/4 なのは、`worst_gap` の実測（端との差 4・頂上の差 1）を通し、
#: かつ `shitsugyo.double_boundary` のような**本物の逆転**を落とさない幅だから。
FLAT_TOP_BAND = 0.25

#: `倍率` の形を採る下限（いちばん高い段 ÷ いちばん低い段）。
#: **2倍を切る比は「少し違う」であって、節にはなりません。**
RATIO_MIN = 2.0

#: **形を足したら、必ずここに足すこと。**`status.py` の内訳も `--shape` の
#: 選択肢も、`tests/test_section_sweep.py` の全形テストも、ここを正本にしています。
#: 2026-08-18 に `倍率` を足したとき、**分類は返るのに一覧に載っていませんでした** ——
#: `--shape 倍率` が「そんな形は無い」と弾き、拾いにいった当の候補を絞れません
#: （`status.py` は「載っていない形は末尾に回す」ので、そこだけは出ていました）。
SHAPES = ("不変", "帯", "頭打ち", "崖", "逆転", "片効き", "倍率")

#: **一覧の中で、いちばん後ろに回す形。**（2026-08-24 に足した）
#:
#: `src/supply.py` の `SWEEP_YIELD` の註が、**この修正を名指しで予約していました** ——
#:
#: > **覆る条件 / 次に測ること**: `片効き` と `不変` は、いまも他の形と同じ重みで
#: > 族の先頭に並びます。**この2つを候補から落とすか、順番を最後に回せば、
#: > 族の先頭6件の歩留りは机上で 5/18 ≒ 0.28 まで上がります**（14件が抜けるので）。
#:
#: 実測（2026-08-20 に32枠を目で読んだときの内訳）:
#:
#:     片効き 10件 ＋ 不変 4件 = **14/32（44%）**  ← どれも「X は Y に依らない」の自明
#:     書ける                                        5件
#:
#: **一覧は6件で切ります。**だから、この2つが先頭に混ざるぶんだけ、
#: 書ける候補が `…ほか N件` の中に沈みます。**落とすのではなく後ろへ回す** ——
#: `不変` は本物の節になったことがあり（「上限は片方の帯にしか効かない」）、
#: 落とすと形ごと消えます（`table_constants` の註と同じ理由）。
#:
#: **もう1つ、この2つだけが持つ性質があります**（2026-08-24 に測って足した）。
#: `_hit_points` は `不変` に空を返し、`片効き` は x の欄そのものを持ちません。
#: つまり既出の判定は `_hit_outcome`（結果の値）だけが頼りで、その値が
#: **1000未満なら `_point_printed` は `None`（判定できない）を返します**
#: （`_LONE_NUMBER_MIN`）。`is_covered` はそこで `False` ＝「まだ誰も言っていない」を
#: 返すので、**倍率・年齢・パーセントのような小さい値の候補は、
#: 本文に書いてあっても必ず「新しい」に数えられます。**
#: 実例: `nenkin.birth_gap_ratio … 1.25 のまま` は「新しい」と出ますが、
#: 節は **「0.5% ÷ 0.4% ＝ 1.25倍で、1か月でも60か月でも同じです」**と
#: 既に印字しています。**この2つは「新しいと分かった」のではなく
#: 「判定できないので新しいことにした」**ぶんを多く含みます。
#:
#: **覆る条件**: この2つから節が2件以上書けたら、後ろへ回すのをやめること。
SHAPE_LAST = ("片効き", "不変")

#: `詳しく` のうち、**x 軸の値**を持つ欄。行を歩く掃引では、ここだけを
#: 行番号から見出しに直します。**形を足したら、ここに足すこと。**
#:
#: **一度「名前に `x` を含む欄」で拾おうとして外しました**（2026-08-18）。
#: `帯` の欄は `帯の入口` / `帯の出口` で、**`x` の字が入っていません** ——
#: 規約で拾うつもりが、既にある形1つを取りこぼしていました。
#: だから並びは1つに集約して、**読む側を2か所とも、ここから引きます**
#: （`_hit_points` と、`sweep_rows` の見出し直し）。
X_KEYS = ("止まる x", "x", "x の手前", "x の先", "帯の入口", "帯の出口", "並ぶ x",
          "いちばん低い", "いちばん高い",
          "細かく刻んだ手前", "細かく刻んだ先",
          # 頭打ちを刻み直した結果（`_refine_plateau`。2026-08-27）
          "止まる x の手前", "細かくした止まる x", "細かくした止まる x の手前",
          # 帯を刻み直した結果（`_refine_band`。2026-08-27）
          "帯の入口の手前", "帯の出口の先",
          "細かくした帯の入口", "細かくした帯の入口の外",
          "細かくした帯の出口", "細かくした帯の出口の外")

#: そのうち「**この候補を名指ししている**点」。同点の一覧は、名指しの点ではない
#: （既出の判定を厳しくすると意味が変わるので、`_hit_points` からは外す）。
#:
#: **崖を刻み直した区間も外します**（2026-08-27。`_refine_cliff`）。
#: あれは元の `x の手前 → x の先` を**狭めたもの**で、別の主張ではありません。
#: 入れると「粗い x と細かい x の両方が印字されていなければ既出でない」になり、
#: **刻み直した候補だけ既出の判定が厳しくなります** —— `並ぶ x` と同じ理由。
NAMING_X_KEYS = tuple(k for k in X_KEYS
                      if k not in ("並ぶ x", "細かく刻んだ手前", "細かく刻んだ先",
                                   # `頭打ち` を刻み直した区間も、元の
                                   # `止まる x` を**狭めたもの**で別の主張ではない
                                   "止まる x の手前", "細かくした止まる x",
                                   "細かくした止まる x の手前",
                                   # `帯` も同じ（`_refine_band`。2026-08-27）——
                                   # 刻み直しは `帯の入口 / 帯の出口` を**広げ直した
                                   # もの**で、別の主張ではない。入れると
                                   # 「粗い x と細かい x の両方が印字されていなければ
                                   # 既出でない」になり、刻み直した候補だけ
                                   # 既出の判定が厳しくなる
                                   "帯の入口の手前", "帯の出口の先",
                                   "細かくした帯の入口", "細かくした帯の入口の外",
                                   "細かくした帯の出口", "細かくした帯の出口の外"))

#: `詳しく` のうち、**y（結果の値）や註**を持つ欄。x でも y でもない欄が出たら、
#: `tests/test_section_sweep.py` が止めます —— **形を足した回に、その欄が
#: x なのか y なのかを宣言させるため**（宣言しないと、行番号のまま印字されます）。
Y_KEYS = ("止まった値", "値", "跳ぶ幅", "動かない値", "帯の中", "帯の外",
          "端では", "差", "中央の段差", "並ぶ点", "数え上げ", "動く", "動かない",
          "どこ", "倍率", "並び",
          # 崖を刻み直した結果（`_refine_cliff`。2026-08-27）
          "細かくすると崖ではない", "細かくした最大の段差",
          "細かくしたほかの段差の平均", "細かく刻めなかった",
          # 頭打ちを刻み直した結果（`_refine_plateau`。2026-08-27）
          "止まり際を刻めなかった",
          # 帯を刻み直した結果（`_refine_band`。2026-08-27）
          "帯の入口を刻めなかった", "帯の出口を刻めなかった")


def _family(fn: Callable) -> str:
    """関数の族名（`src.calc.ikuji` → `ikuji`）。取れなければ空文字。"""
    return getattr(fn, "__module__", "").rsplit(".", 1)[-1]


def _linspace(lo: float, hi: float) -> list[float]:
    """`lo`〜`hi` に GRID 点を等間隔で置く。**丸めの桁は刻みから決める。**

    固定の桁で丸めないこと —— `koyouhoken` の率は 0.0055 なので、
    2桁で丸めると **9点が全部 0.01 になって**掃引に足りなくなります
    （`len(xs) < 4` で関数ごと落ちる）。刻みより2桁細かく丸めれば、
    どの桁の率でも点が潰れません。
    """
    step = (hi - lo) / (GRID - 1)
    if step <= 0:
        return [lo]
    digits = max(2, 2 - math.floor(math.log10(step)))
    out: list[float] = []
    for i in range(GRID):
        x = round(lo + step * i, digits)
        if not out or x > out[-1]:
            out.append(x)
    return out


def _rate_grid(default: float, param: str = "", family: str = "") -> list[float]:
    """率（0 < x < 1）を、**実在する幅**で振る（2026-08-20 に直した）。

    ここは長らく **一律 0.1〜0.9** でした。`social_rate` を 0.7〜0.9 まで
    振れば住民税は 0 になり、`rate`（所得税率）0.9 の崖も出ます ——
    **どちらも実在しない世界の話**なので、節には書けません。
    8/20 に歩留りを初めて測ったところ **0.156**（5/32）で、
    **落ちた27件の過半がこれ**でした（`supply.SWEEP_YIELD` の註）。

    引くのは2段です:

        1. `calc_axes.RATE_BAND` に名前があれば、その幅（`族.引数名` が先）
        2. 無ければ **既定値の 0.5倍〜2倍**（上は 0.99 で止める）

    2 が効くのは、**既定値そのものが「その関数を書いた側の置いた実在の1点」**
    だからです。まわりを ±倍で取れば、桁は必ず実在の側に残ります。
    **幅を狭めるほど候補の件数は減る**ので、直したら
    `python -m src.supply --measure` で **歩留り × 件数**を見ること。
    """
    band = calc_axes.RATE_BAND.get(f"{family}.{param}") or calc_axes.RATE_BAND.get(param)
    if band is not None:
        return _linspace(band[0], band[1])
    lo = max(default * 0.5, 1e-9)
    hi = min(default * 2.0, 0.99)
    if hi <= lo:
        hi = min(default * 1.5, 0.99)
    return _linspace(lo, hi)


def _grid(default: float, param: str = "", family: str = "") -> list[float]:
    """既定値のまわりに点を置く。**桁で置き方を変える。**

    - 率（0 < x < 1）      → `_rate_grid`（**実在する幅**。名前で引く）
    - 小さい整数（〜200）   → 既定の半分〜2倍を整数で
    - 金額（それ以上）      → 既定の 0.5〜4倍を対数で
    """
    if isinstance(default, float) and 0 < default < 1:
        return _rate_grid(default, param, family)
    if abs(default) <= 200:
        lo = max(1, int(default * 0.5))
        hi = max(lo + GRID, int(default * 2))
        step = max(1, (hi - lo) // (GRID - 1))
        return [lo + step * i for i in range(GRID)]
    lo, hi = default * 0.5, default * 4
    ratio = (hi / lo) ** (1 / (GRID - 1))
    return [int(lo * ratio ** i) for i in range(GRID)]


#: **数字を文字列で持っている欄**を拾うための形（2026-08-17）。
#: `f"{x:.1f}%"` / `f"{x:,}円"` / `"16.7年"` のように、**印字のために
#: 単位を付けた瞬間、掃引から消えていました。** `src/calc/` にいくつもあります。
_NUMERIC_TEXT = re.compile(r"^\s*[-+]?[\d,]+(?:\.\d+)?\s*(?:%|円|年|か月|日|倍|人|回)?\s*$")


def _as_number(v: Any) -> float | None:
    """数値、または**単位つきの文字列**なら float にする。それ以外は None。

    **文字列を拾うのは、率がそこにしか無い表があるから**です ——
    `furusato.bracket_jumps` の `はね上がる率` は `f"{...:.1f}%"` で、
    2026-08-17 の回はこの欄に**いちばん深い崖**があったのに、
    掃引は1件も見ていませんでした（人が手で並べて気づいた）。

    **単位は落とすだけで、換算はしません。** `%` を 0.01 倍したりすると、
    同じ欄の中で単位が混ざったときに黙って桁が狂います。
    掃引が見るのは**形（崖・逆転・頭打ち）だけ**なので、
    **1つの欄の中で単位が揃っていれば、換算は要りません。**

    ## `Decimal` と `Fraction`（2026-08-19 09:0x に足した）

    ここは長らく `isinstance(v, (int, float))` だけを見ていました。
    ところが `src/calc/` は **float の丸め落ちを直すたびに厳密な型へ移って**います
    （8/18 23:0x `Decimal`・8/18 22:1x `Fraction`。いま7本）。
    **移した瞬間、その欄は掃引から消えます** —— 例外も警告も出ません。

        koyouhoken.worker_rate("一般の事業") → Decimal("0.0055")

    これで `worker_rate` / `employer_rate` / `total_rate` の3本が
    **「呼べなかった関数」に落ちていました**（数字を返しているのに、
    数字と認められない）。`koteishisan.bands` の `小規模`（`Fraction`）と
    `shobyo.daily_exact` / `rounding_gain` は、**関数は通るのに欄だけが消える**
    ほうの落ち方です。**直す先は表ではなく、読む側です。**
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal, Fraction)):
        return float(v)
    if isinstance(v, str) and _NUMERIC_TEXT.match(v):
        body = re.sub(r"[,\s%円年倍人回]|か月|日", "", v)
        try:
            return float(body)
        except ValueError:
            return None
    return None


def _scalars(value: Any) -> dict[str, float]:
    """返り値から、掃引で比べられる数字だけ取り出す。

    ## 組（tuple / list）を足した理由（2026-08-19 09:0x。**無音で消えていた**）

    ここは `dict` と裸の数値しか見ていませんでした。**返りが組の関数は、
    欄が1つも取れないので掃引に1件も出ません** —— そして
    `_scalars` が `{}` を返すだけなので、**「呼べなかった関数」にも載りません。**
    例外が出ないので、どこにも記録が残らない側の落ち方です。実測:

        掃引は通るのに欄0本  7本（fuka.payback_age・izoku.widow_age_range・
                              jutaku.resident_cap_of・kokuho.parts_for・
                              seimeihoken.marginal_levels・tsukin.grade_widths・
                              yukyu.table_for）
        そのせいで丸ごと落ちた  2本（kogaku.tier・nenkinmenjo.kind）
                              ＝ `_enum_axis` が「数字を返さない」と読んで軸を捨てる

    欄の名前は **`NamedTuple` なら欄名、ふつうの組なら位置**（`[0]` `[1]` …）です。
    位置は読みにくい名前ですが、**この一覧は候補であって節ではありません**
    （意味は人が表を開いて決めます）。名前を手で並べる道は採りません ——
    表を足した回が必ず書き忘れる形になるからです（`noise_tokens` と同じ穴）。

    **`ENUM_MAX`（12）より長い並びは読みません。** これは数え上げの軸と同じ線で、
    **それより長いものは「記録」ではなく「表そのもの」**です
    （表は `sweep_rows` の側が行として歩きます。1つの表に2度当てない）。
    """
    if isinstance(value, bool):
        return {}
    if isinstance(value, (int, float, Decimal, Fraction)):
        return {"": float(value)}
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            n = _as_number(v)
            if n is not None:
                out[str(k)] = n
        return out
    if isinstance(value, (tuple, list)) and 2 <= len(value) <= ENUM_MAX:
        fields = getattr(value, "_fields", None)          # NamedTuple なら欄名がある
        out = {}
        for i, v in enumerate(value):
            n = _as_number(v)
            if n is not None:
                out[str(fields[i]) if fields else f"[{i}]"] = n
        return out
    return {}


def _sweepable_params(fn: Callable,
                      skip: Iterable[str] = ()) -> list[tuple[str, float]]:
    """既定値が数値で、他の引数を触らずに動かせるものだけ返す。

    `skip` は**こちらが値を埋める引数**（数え上げの軸。`_enum_params`）。
    既定値が無くても呼べるので、**そこで降りないこと** —— 降りていたために
    `koteishisan.unit_tax` のような関数が丸ごと対象外でした。
    """
    skip = set(skip)
    out = []
    for name, p in calc_axes.real_params(fn):
        if name in skip:
            continue
        if p.default is inspect.Parameter.empty:
            fill = _axis_fill(name, _family(fn))
            if fill is None:
                return []      # 埋めようのない引数は、そのまま呼べない
            out.append((name, fill))
            continue
        if isinstance(p.default, bool) or not isinstance(p.default, (int, float)):
            continue
        out.append((name, float(p.default)))
    return out


def _axis_fill(param: str, family: str = "") -> float | None:
    """既定値の無い数値の引数に置く代表値。寄せられなければ `None`。

    **正本は `calc_axes`**（2026-08-19 に `pair_sweep` から移した）。
    ここで写しを持たないこと —— 次に軸を足した回が、片方だけ書きます。

    引くのは4つ。**この順です**（2026-08-19 に3つで足し、2026-08-20 に1つ増えた）:

        `PARAM_FILL` の `族.引数名`   **同じ名前が族によって桁の変わるもの**
                       （`shokibo.monthly` は共催の掛金・`rousai.monthly` は月給）
        `EXACT_FILL`   **名前が完全に一致したときだけ**引く表。
                       部分一致に置けない短い名前（`i` / `n` / `step`）はここ
        `PARAM_FILL`   名前ごとの値。**軸の代表値では桁が合わない引数**
                       （`estate` を所得の 3,000,000 で埋めると税額が全行 0）
        `SEMANTIC_AXES` → `AXIS_FILL`   意味の軸の代表値
        `FILL_ONLY`    **埋めるためだけの語彙**。`axis_of` からは見えないので、
                       `pair_sweep` の組は増えません（`grade` などの格子のつまみ）

    **`FILL_ONLY` を `SEMANTIC_AXES` に足して済ませないこと。** あちらは
    表どうしを繋ぐ軸で、つまみを入れると母数だけが膨らみます。
    """
    qualified = calc_axes.PARAM_FILL.get(f"{family}.{param}")
    if qualified is not None:
        return float(qualified)
    exact = calc_axes.EXACT_FILL.get(param)
    if exact is not None:
        return float(exact)
    for name, value in calc_axes.PARAM_FILL.items():
        if "." in name:
            continue           # 族つきは上で完全一致だけ引く（部分一致に混ぜない）
        if name == param or name in param:
            return float(value)
    axis = calc_axes.axis_of(param)
    if axis is not None:
        return calc_axes.AXIS_FILL.get(axis)
    for name, value in calc_axes.FILL_ONLY.items():
        if name == param or name in param:
            return float(value)
    return None


#: **呼べなかった関数**（表名, 関数名, 埋められなかった引数）。
#: `sweep_all` が回すたびに積み直します。**計器です** ——
#: この族は3回続けて「呼べる形が狭くて、いちばん深い表が丸ごと消える」で
#: 穴を出しました（08/18 14:1x の部分集合・08/19 06:1x の `_sweepable_params`・
#: 08/19 07:1x の `_enum_axis`）。**どれも「候補が何件出たか」しか出ないので、
#: 消えたことに気づけませんでした。** 件数が出ていれば、3回とも最初に見えます。
UNCALLABLE: list[tuple[str, str, str]] = []


def dataclass_view(fn: Callable) -> Callable | None:
    """引数に**データ組**（dataclass）を取る関数を、その欄で呼べる形に開く。

    開けなければ `None`（＝もとの関数をそのまま使う）。

    ## なぜ要るか（2026-08-19 に足した）

    `furusato.limit(p: Person)` は、`p` を埋めようがないので
    **「呼べなかった関数」**に落ちていました。同じ形で
    `resident_tax_income_levy` と `taxable_income` も落ちており、
    **ふるさと納税の表は、本体3本がまるごと掃引の外**でした。

    **語彙では直りません。** `PARAM_FILL` に `p` を足すと、
    `Person` の代わりに数を渡すことになります。要るのは代表値ではなく、
    **組み立てること**です —— そして欄（`income` / `social_rate` …）は
    1つずつ寄せられるので、**組を開いて欄を引数にすれば、そのまま振れます。**

    返すのは、欄をキーワード引数に取る包みです。署名を作り直してあるので、
    `_sweepable_params` も `_enum_params` も `unreachable` も、
    **中を知らないまま今までどおり効きます。**
    """
    hints = getattr(fn, "__annotations__", {})
    mod = sys.modules.get(getattr(fn, "__module__", ""))
    news: list[inspect.Parameter] = []
    plan: dict[str, tuple[type, list[tuple[str, str, Any]]]] = {}
    taken = {n for n, _ in calc_axes.real_params(fn)}
    for pname, p in calc_axes.real_params(fn):
        anno = hints.get(pname)
        if isinstance(anno, str) and mod is not None:
            anno = getattr(mod, anno, None)
        if not (dataclasses.is_dataclass(anno) and isinstance(anno, type)
                and p.default is inspect.Parameter.empty):
            news.append(p.replace(kind=inspect.Parameter.KEYWORD_ONLY))
            continue
        fields: list[tuple[str, str, Any]] = []
        for f in dataclasses.fields(anno):
            nn = f.name if f.name not in taken else f"{pname}_{f.name}"
            taken.add(nn)
            default = (inspect.Parameter.empty
                       if f.default is dataclasses.MISSING else f.default)
            news.append(inspect.Parameter(nn, inspect.Parameter.KEYWORD_ONLY,
                                          default=default, annotation=f.type))
            fields.append((nn, f.name, default))
        plan[pname] = (anno, fields)
    if not plan:
        return None

    def view(**kw):
        args = dict(kw)
        for oname, (cls, fields) in plan.items():
            made = {}
            for nn, fname, default in fields:
                if nn in args:
                    made[fname] = args.pop(nn)
                elif default is not inspect.Parameter.empty:
                    made[fname] = default
            args[oname] = cls(**made)
        return fn(**args)

    view.__name__ = getattr(fn, "__name__", "view")
    view.__doc__ = fn.__doc__
    view.__module__ = getattr(fn, "__module__", "")
    view.__signature__ = inspect.Signature(news)
    return view


def unreachable(fn: Callable, *, calc: str = "", name: str = "") -> str:
    """`fn` を掃引できない理由（引数名）。掃引できるなら空文字。

    見るのは1点だけ —— **既定値が無く、数え上げにも意味の軸にも寄らない引数**。
    そこが1つでもあれば、この関数はどう呼んでも落ちます。
    """
    try:
        inspect.signature(fn)
    except (TypeError, ValueError):
        return "(signature)"
    enums = {pn for pn, _ in _enum_params(fn)}
    for pname, p in calc_axes.real_params(fn):
        if pname in enums or p.default is not inspect.Parameter.empty:
            continue
        if _axis_fill(pname, _family(fn)) is None:
            return pname
    return ""


#: 数え上げの軸として振る候補の、要素数の上限。**これより多い並びは軸ではなく
#: 表そのもの**なので、`sweep_rows` の側で歩きます（1つの表に2度当てない）。
ENUM_MAX = 12

#: 数え上げの軸として通すのに要る、**実際に数字を返した要素の数と割合**。
#: 2026-08-21 に足した（`_enum_axis` の docstring「全部通ることを要求していた頃の穴」）。
#: **割合のほうが本体です** —— 件数だけだと、要素の多い無関係な入れ物が
#: 2つ通っただけで軸になります。
ENUM_MIN_ITEMS = 2
ENUM_MIN_SHARE = 0.6

#: **場合分けの名前の長さの上限**（2026-08-21）。これより長い要素を含む並びは、
#: 場合分けの名前ではなく**文**なので、入れ物の候補から外します。
#:
#: **名前で外していないこと**が肝です（`_enum_containers` の「語彙で弾くと、
#: 表を足した回が書き忘れて黙って落ちる」）。ここで見ているのは**形**です ——
#: `src/calc/` の全56本を測ると、40字を超える並びは**51本すべてが
#: `ASSUMPTIONS`（前提の文）**で、本物の場合分けでいちばん長いのは
#: `tokurou.COHORTS` の **30字**（「昭和28年4月2日〜昭和30年4月1日（女性は5年おくれ）」）。
#: **10字ぶん空けてあります。**
#:
#: **なぜ外すか**: 前提の文は全56本にあり、`_enum_axis` は要素を1つずつ
#: 実際に呼んで捨てます。**関数 × 引数 × 要素**の呼び出しがまるごと無駄で、
#: 2026-08-21 の実測では、外すと1周が **107秒 → 76秒**（-29%）。
#:
#: **覆る条件**: 40字を超える場合分けを持つ表を書いたとき。
#: `tests/test_section_sweep.py::test_場合分けの名前は文の長さに達しない` が
#: そのとき落ちます（黙って消えないように、検査のほうで見張っています）。
ENUM_NAME_MAX = 40

#: **一部の要素だけで振った場合分け**（表名, 関数名, 引数, 入れ物名, 振った数, 全体）。
#: `sweep_all` が回すたびに積み直します。**計器です** ——
#: 一部だけ振ったことが見えないと、節を書く側が「全区分のうちいちばん高いのは」と
#: 書いてしまいます（2026-08-18 に `kyoiku` で実際に書いた形）。
#: **落とした要素は「たまたま落ちた」のではなく、その関数がそこで
#: 数字を返さない＝制度の側に無い**という意味です。
PARTIAL_ENUM: list[tuple[str, str, str, str, int, int]] = []


def _note_partial(fn: Callable, pname: str, cname: str,
                  items: list[str], good: list[str]) -> None:
    """一部だけ振れた場合分けを計器に積む（同じ組は1度だけ）。"""
    row = (_family(fn), getattr(fn, "__name__", "?"), pname,
           cname, len(good), len(items))
    if row not in PARTIAL_ENUM:
        PARTIAL_ENUM.append(row)


def _enum_containers(fn: Callable) -> list[tuple[str, list[str]]]:
    """`fn` から見える、**文字列を並べた入れ物**を返す。

    `list` / `tuple` の要素、または `dict` の鍵です。`fn.__module__` から引くので、
    **手で語彙を並べません**（次に表を足した回が書き忘れる形を作らないため）。

    ## 隣の表も見る理由（2026-08-19 10:5x。**入れ物が別の表にありました**）

    ここは長らく `fn.__module__` の中だけを見ていて、
    「同じモジュールに入れ物が無い ＝ この引数は数え上げの軸ではない」と
    読んでいました。**`iryohi` がその読みを外します** ——
    `low_income_grid(tier_name)` と `deduction_start_cost(tier_name, …)` の
    区分名（ア〜オ）は `iryohi` にはありません。高額療養費の区分表は
    `kogaku.TIERS` にあり、`iryohi` は `from . import kogaku` で読んでいます。

    **制度は、そもそも別の制度の区分を借ります。** 医療費控除が高額療養費の
    区分を使うように、表が別の表の場合分けを引くのは普通の形なので、
    ここは「たまたま1件」ではありません。

    ありかは import の側から引けるので、**語彙を手で並べる直しは採りません** ——
    `vars(mod)` に入っている `src.calc.*` のモジュールを1段だけ辿ります
    （辿るのは1段。表どうしが輪で import し合う形は `src/calc/` にありません）。
    間違った入れ物を拾う心配は要りません。`_enum_axis` が
    **全要素を実際に入れて呼び、全部が数字を返すものだけ**通すからです。
    """
    mod = sys.modules.get(getattr(fn, "__module__", ""))
    if mod is None:
        return []
    out: list[tuple[str, list[str]]] = []
    for m in _container_sources(mod):
        for cname, v in vars(m).items():
            if cname.startswith("_"):
                continue
            if isinstance(v, (list, tuple, dict)):
                items = _names_of(list(v))
            else:
                continue
            if items is None or not (2 <= len(items) <= ENUM_MAX):
                continue
            if max(len(x) for x in items) > ENUM_NAME_MAX:
                continue           # 場合分けの名前ではなく文（`ENUM_NAME_MAX`）
            out.append((cname, items))
    return out


def _container_sources(mod: ModuleType) -> list[ModuleType]:
    """入れ物を探す先。**自分の表と、そこから import している表**（1段だけ）。"""
    out = [mod]
    for cname, v in vars(mod).items():
        if cname.startswith("_") or not isinstance(v, ModuleType):
            continue
        if getattr(v, "__name__", "").startswith("src.calc.") and v is not mod:
            out.append(v)
    return out


def _names_of(items: list) -> list[str] | None:
    """入れ物の要素から、**軸として振る文字列**を取り出す。無ければ `None`。

    受けるのは2つの形です。

        ["小規模", "一般", "特例なし"]                    → そのまま
        [("一般", 0.20, 100_000), ("特定一般", ...), …]   → **各行の先頭**

    ## 2つめを足した理由（2026-08-18。**黙って間違った答えを出していた**）

    制度の表は「名前と値を1行にまとめた並び」で持つのが普通です
    （`kyoiku.PROGRAMS` は `(名前, 給付率, 上限額)` の6行）。ところがここは
    **要素が全部 `str` の入れ物しか見ていなかった**ので、その6つの名前は
    **軸の候補にすら入りませんでした。**

    落ちる先が「振られない」なら、ただの取りこぼしです。**そうではありません** ——
    同じモジュールに `FLOOR_PROGRAMS`（下限のある3つだけを並べた**部分集合**）が
    あり、`_enum_axis` が**先に通ったほうを返す**ので、`kyoiku.cap_of` は
    **6つ中3つだけを振った結果**を候補として出していました:

        いちばん高い: 特定一般＋資格取得・就職 ／ 倍率 2.5   ← **嘘**
        実際は        専門実践＋賃金5パーセント上昇 ／ 倍率 6.4

    **節に書けば、そのまま動画の中の誤りになります。** 取りこぼしではなく
    誤答なので、`_enum_axis` の選び方（いちばん広い入れ物を採る）と対で直しています。
    """
    if not items:
        return None
    if all(isinstance(e, str) for e in items):
        return list(items)
    if all(isinstance(e, (list, tuple)) and e and isinstance(e[0], str)
           for e in items):
        names = [e[0] for e in items]
        # 同じ名前が2度出る並びは、行の見出しではない（軸にならない）
        return names if len(set(names)) == len(names) else None
    return None


def _required_others(fn: Callable, pname: str) -> dict[str, Any] | None:
    """`pname` 以外の**既定値の無い引数**を埋めた辞書。埋まらなければ `None`。

    ## なぜ要るか（2026-08-19 07:3x に足した。**この族の穴の4件目**）

    `_enum_axis` は候補を `fn(**{pname: e})` と、**その引数だけで**呼んで
    試していました。**他にも必須の引数がある関数では、必ず TypeError です**:

        kogaku.limit(name, cost)                  → limit(name='ウ') は落ちる
        kaigo.pay(level, used_units, rate, cap=…) → pay(level='要介護3') も落ちる

    落ちると数え上げの軸が見つからず、`_sweepable_params` も `skip` が空のまま
    必須引数に当たるので、**この2本は掃引から丸ごと消えていました。**
    そしてその2本が、`gassan`（7節）の元になった表です ——
    **いちばん深い表ほど、引数が多くて消えやすい**という向きの穴です。

    `pair_sweep._enum_with` が同じ穴を先に塞いでいます（08/19 06:5x）。
    **あちらは `sweep` の軸を一緒に渡す形なので、そのままは持ってこられません。**
    共通なのは埋め方（`calc_axes.AXIS_FILL`）のほうなので、そちらを正本にしました。
    """
    out: dict[str, Any] = {}
    for name, p in calc_axes.real_params(fn):
        if name == pname or p.default is not inspect.Parameter.empty:
            continue
        fill = _axis_fill(name, _family(fn))
        if fill is None:
            return None        # 文字列の場合分けが2つある形。まだ見ていない
        out[name] = fill
    return out


def _enum_axis(fn: Callable, pname: str, default: Any) -> list[str]:
    """`pname` を**数え上げの軸**として振れるなら、その並びを返す。

    ## なぜ要るか（2026-08-18 に足した。**4回続けて申し送りに載っていた**）

    `_sweepable_params` は「既定値が数値」の引数しか見ません。ところが
    `src/calc/` には **文字列で場合分けする引数**があり、そこがいちばん深い節に
    なっていました ——

        koteishisan.unit_tax(part: str, unit: float = LAND_UNIT)
            PARTS = ["小規模", "一般", "特例なし"] で **1㎡単価が 1:2:6**

    この `part` には**既定値がありません**。`_sweepable_params` は既定値の無い
    引数を1つでも見つけると `[]` を返して降りるので、**この関数は丸ごと掃引の
    対象外**でした（`unit` すら振られていない）。`invoice.kind`・
    `tsukin.CAR_BANDS` に続く**3族目**で、申し送りは4回とも同じことを言っています。

    **選び方は名前ではなく、実際に呼べるかどうかで決めます。** 名前で選ぶと、
    表を足した回が語彙を書き忘れたときに黙って落ちます（`noise_tokens` と
    同じ形の穴）。ここでやるのは:

    1. 既定値が文字列なら、**その値を含む入れ物**を先に試す
    2. 入れ物の要素を入れてみて、**数字を返す要素だけ**を軸にする。
       ただし通った要素が **2つ未満**か、**全体の 6割未満**なら、その入れ物は捨てる

    **2 が本体です。** 関係のない入れ物（たとえば見出しの並び）は、
    ほとんどの要素で落ちるか、数字を返しません。

    ## 「全部通ること」を要求していた頃の穴（2026-08-21 に直した）

    ここは長らく **「入れ物の要素が1つでも落ちたら、その入れ物ごと捨てる」**
    でした。関係のない入れ物を弾くにはそれで足りるのですが、
    **制度の表は、正しい入れ物でも一部の値で「無い」を返します**:

        inshi.edges('17号')                        → 段が1つしかなく、境目が無い
        iryohi.deduction_start_cost('エ' / 'オ')   → 返りの型からして `int | None`

    どちらも **5区分のうち4つ／3つは正しく数字を返します。** それでも
    「全部」を要求していたので、**この2関数は丸ごと掃引の外**でした
    （`UNCALLABLE` に「埋められなかった引数 kind / tier_name」として出ていた）。
    **語彙の不足ではありません。** 場合分けの軸は見つかっていて、
    **一部が定義されていないという、制度の側の普通の形**で落ちていました。

    **6割の線が守っているもの。** 関係のない入れ物（`ASSUMPTIONS`・
    別の表の見出し）は、実測では**全要素で落ちます** —— 部分一致で
    たまたま数個通る形は `src/calc/` に見当たりません。一方 `kyoiku` の
    部分集合（`FLOOR_PROGRAMS` 3件 ⊂ `PROGRAMS` 6件）は、
    `min_cost_paid` では 3/6 ＝ 0.5 で**この線に届かず落ちます** ——
    2026-08-18 に直した「6つ中3つだけを振って倍率を嘘に書いた」形は、
    **この線と、下の「全部通ったほうを先に採る」の2つで塞いであります。**

    **覆る条件**: 無関係な入れ物が6割通る例が出たとき（候補の `x の幅` に
    その表と関係のない語が出ます）。出たら線を上げるのではなく、
    **引数名との一致**で選び直すこと。
    """
    conts = _enum_containers(fn)
    if not conts:
        return []
    rest = _required_others(fn, pname)
    if rest is None:
        return []
    if isinstance(default, str):
        conts.sort(key=lambda kv: default not in kv[1])
    passed: list[tuple[int, int, list[str]]] = []
    for cname, items in conts:
        # **落ちてよい数を先に決めて、超えたらそこで降りる。**
        # ここは以前「1つでも落ちたら break」で、無関係な入れ物は
        # 1回の呼び出しで捨てられていました。全要素を必ず呼ぶ形に変えると、
        # **入れ物1つあたりの呼び出しが要素数ぶんに増えます** —— 掃引は
        # 関数 × 引数 × 入れ物 で回るので、そのまま1周の時間に乗ります。
        # 6割の線に届かないと確定した時点で、残りを呼ぶ意味はありません。
        budget = len(items) - math.ceil(len(items) * ENUM_MIN_SHARE)
        good: list[str] = []
        for e in items:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    value = fn(**{pname: e}, **rest)
                ok = _readable(value)
            except Exception:
                ok = False
            if ok:
                good.append(e)
                continue
            budget -= 1
            if budget < 0:
                break
        if len(good) < ENUM_MIN_ITEMS or len(good) < len(items) * ENUM_MIN_SHARE:
            continue
        whole = len(good) == len(items)
        if not whole:
            _note_partial(fn, pname, cname, items, good)
        passed.append((1 if whole else 0, len(good), good))
    if not passed:
        return []
    # **いちばん広い入れ物を採る**（2026-08-18 に直した）。
    #
    # ここは長らく「先に通ったほうを返す」でした。**部分集合が先に来ると、
    # 半分だけ振った結果を候補として出します** —— `kyoiku` は
    # `PROGRAMS`（6つ）と `FLOOR_PROGRAMS`（下限のある3つ）を両方持っていて、
    # `cap_of` の倍率を **2.5倍（実際は 6.4倍）**と報告していました。
    #
    # 広いほうが常に正しいわけではありません。**「全部が例外なく数字を返す」を
    # 通った入れ物どうし**の比較なので、通らない値を含む並びは既に落ちています ——
    # `min_cost_paid` は下限のある3つでしか定義されていないので、6つの並びは
    # ここに来ません（`FLOOR_PROGRAMS` が残り、正しく3点で振られます）。
    #
    # **覆る条件**: 関係のない入れ物が「たまたま全部通る」ほうが広かったとき。
    # そのときは候補の `x の幅` に、その表と関係のない語が出ます。
    # 出たら、広さではなく**引数名との一致**で選び直すこと。
    #
    # **2026-08-21 に、鍵の先頭へ「全部通ったか」を足しました。** 一部だけ
    # 通る入れ物を採るようにしたので、広さだけで比べると
    # **「半分落ちる広い入れ物」が「全部通る狭い入れ物」に勝ちます**
    # （`kyoiku` で嘘を書いたのと同じ形が、別の入口から戻る）。
    # **全部通ったほうが先。同点なら広いほう。**
    passed.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return passed[0][2]


#: `_enum_params` の答え。**同じ関数を1周で4回聞かれます**
#: （`unreachable` / `sweep_function` / `_row_call_cases` / `sweep_enums`）。
#: 中身は入れ物の要素を1つずつ実際に呼んで確かめるので、**4回とも同じ計算を
#: やり直していました。**表の中身が変わらない限り答えも変わらないので、
#: 1周のあいだだけ覚えておきます（`sweep_all` の頭で捨てる）。
#: 値に関数そのものを持たせています。**`id()` を鍵に混ぜているので、
#: 持たせないと回収された関数の id を別の関数が使い回します**（`dataclass_view`
#: は呼ぶたびに新しい包みを作るので、実際に起こりうる形です）。
_ENUM_CACHE: dict[Any, tuple[Callable, list[tuple[str, list[str]]]]] = {}


def _enum_params(fn: Callable) -> list[tuple[str, list[str]]]:
    """**数え上げの軸として振れる引数**を、`(名前, 並び)` で返す。

    対象は「既定値が文字列」と「既定値が無く、文字列を入れると通る」の2つ。
    **後者を入れているのが、この直しの本体です**（`_enum_axis` の docstring）。
    """
    key = (getattr(fn, "__module__", ""), getattr(fn, "__qualname__", ""), id(fn))
    if key in _ENUM_CACHE:
        return _ENUM_CACHE[key][1]

    out = []
    for name, p in calc_axes.real_params(fn):
        default = p.default
        if default is not inspect.Parameter.empty and not isinstance(default, str):
            continue
        items = _enum_axis(fn, name, default)
        if items:
            out.append((name, items))
    _ENUM_CACHE[key] = (fn, out)
    return out


def _level_runs(ys: list[float], scale: float) -> list[tuple[int, int, float]]:
    """並びを**平らな区間**に切って `(始まり, 終わり, その値)` で返す。

    隣どうしの差が `FLAT_TOL` 以下なら同じ段とみなします。
    段が3つで、1つめと3つめの値が同じなら **帯**（`_classify`）。
    """
    runs: list[tuple[int, int, float]] = []
    start = 0
    for i in range(1, len(ys)):
        if abs(ys[i] - ys[start]) / scale > FLAT_TOL:
            runs.append((start, i - 1, ys[start]))
            start = i
    runs.append((start, len(ys) - 1, ys[start]))
    return runs


def _classify(xs: list[float], ys: list[float],
              *, enumerated: bool = False,
              min_points: int = 4,
              ratio: bool = False) -> tuple[str, dict] | None:
    """点の並びから形を1つ決める。**当てはまらなければ None。**

    `enumerated` は **x 軸が数え上げか**（＝表の行を歩いている）。
    連続量をこちらが選んだ目盛りで刻んだ掃引と、**同点の意味が逆になります**
    （理由は下の「逆転」の節）。
    """
    if len(ys) < min_points or any(map(lambda v: math.isnan(v) or math.isinf(v), ys)):
        return None
    lo, hi = min(ys), max(ys)
    scale = max(abs(lo), abs(hi))
    if scale == 0:
        return None
    if (hi - lo) / scale <= FLAT_TOL:
        return "不変", {"値": ys[0]}

    steps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    moving = [abs(s) for s in steps if abs(s) / scale > FLAT_TOL]

    # 帯: **途中の一続きだけ値が違い、両端は同じ値に戻る**（2026-08-18 に足した）
    #
    # **この形が無かったので、`kokuho.keigen_cliff` の `age` は「頭打ち」として
    # 出ていました** —— 後ろの3分の1が平らで、動く段が2つあるので条件に当たります。
    # 右端だけを見れば確かに止まって見えますが、**左端も同じ値**でした。
    # 本当の形は「70歳から上は 13,200円 で止まる」ではなく
    # **「40〜64歳だけ 16,520円 で、その前後は 13,200円」**です
    # （介護納付金分の均等割が乗る帯）。
    #
    # **頭打ちより先に見ること。** 帯は頭打ちの条件も満たすので、順番が本体です。
    # 逆転（最大が途中にある）にも当たりますが、そちらはもっと後ろにあります。
    runs = _level_runs(ys, scale)
    if len(runs) == 3:
        (_, _, outer), (b0, b1, inner), (_, _, back) = runs
        if (abs(outer - back) / scale <= FLAT_TOL
                and abs(inner - outer) / scale >= MEANINGFUL):
            # **両端の外側の点も返します**（`_refine_band` が刻み直す相手。2026-08-27）。
            # `帯の入口` は「帯の中に入った**最初の格子点**」であって、
            # 帯が始まった点ではありません。本当の入口は
            # `(入口の手前, 入口]`、出口は `[出口, 出口の先)` のどこかにあります。
            out = {"帯の入口": xs[b0], "帯の出口": xs[b1],
                   "帯の中": inner, "帯の外": outer,
                   "差": inner - outer}
            if b0 > 0:
                out["帯の入口の手前"] = xs[b0 - 1]
            if b1 + 1 < len(xs):
                out["帯の出口の先"] = xs[b1 + 1]
            return "帯", out

    # 頭打ち: 後ろの3分の1が動かない（前は動いている）
    tail = ys[-max(3, len(ys) // 3):]
    if (max(tail) - min(tail)) / scale <= FLAT_TOL and len(moving) >= 2:
        start = len(ys) - len(tail)
        # **平らの始まりまで左へ伸ばします**（2026-08-27）。
        #
        # ここは長らく `start = 後ろ3分の1の先頭` のままでした。**そこは
        # 「平らが始まった点」ではなく、「平らを判定するのに使った窓の左端」**です。
        # 平らが窓より左から始まっていれば、`止まる x` はそのぶん右へずれます。
        #
        # 実物: `jutaku.relief_room（住民税から引ける上限）` は
        # 「`taxable` が **7,135,242** から上は 97,500」と出ていました。
        # **本当の境目は 1,950,000円**（97,500 ÷ 5%）で、**3.7倍 のずれ**です。
        # 同じ 7,135,242 は `keihi` の掃引にも出ます —— **同じ数が別の表に出るなら、
        # それは制度の境目ではなく格子の点**という合図でした。
        while start > 0 and abs(ys[start - 1] - ys[-1]) / scale <= FLAT_TOL:
            start -= 1
        # **手前の点も返します**（`_refine_plateau` が刻み直す相手）。
        # 格子の点である以上、本当の止まり際は `(手前, 止まる x]` のどこかです。
        out = {"止まる x": xs[start], "止まった値": ys[-1]}
        if start > 0:
            out["止まる x の手前"] = xs[start - 1]
        return "頭打ち", out

    # 逆転: 最大か最小が端ではなく途中にある。
    # **端との差が MEANINGFUL 未満なら採らない** —— 円未満の切り捨てだけで
    # 山ができ、`ratio_span` の「率の倍率」が 1.2516 対 1.2515 で
    # 「逆転」として出ました（2026-08-17 の1回目）。**丸めの屑です。**
    top, bottom = ys.index(hi), ys.index(lo)
    for idx, kind, edge in ((top, "いちばん高い", max(ys[0], ys[-1])),
                            (bottom, "いちばん低い", min(ys[0], ys[-1]))):
        if 0 < idx < len(ys) - 1 and abs(ys[idx] - edge) / scale >= MEANINGFUL:
            # **極値が一意とは限りません**（2026-08-18 に踏んだ）。`ys.index()` は
            # 最初の1点を返すので、同じ高さが他にもあっても x を1つ名指しします。
            # `nenkin.worst_gap` は 189 と 276 が同点(32か月)で、素直に節にすると
            # **追試すると再現しない数字**を画面に出すことになりました。
            # 採否は変えません（形は形として正しい）。**読む側に印だけ渡します。**
            # **完全一致だけを見ても足りません**（同じ日に測って直した）。
            # `worst_gap` の掃引は 189 で 32、その隣 4点が 31 ——
            # 完全一致は無いのに、**端との差 4 に対して頂上の差は 1** です。
            # 1万きざみで回すと 276 も 32 になる ＝ **粗い目盛りが一意に見せていた**。
            # だから見るのは一致ではなく **頂上の平らさ**: 端からの高さの
            # 1/4 以内に他の内点が並んでいたら、その x は名指しに耐えません。
            #
            # **ただし「名指しに耐えない」のは連続量の軸だけです**（2026-08-18）。
            # 前の回はこの印を全部の軸に出し、**`shitsugyo.double_boundary`
            # （既に節になっている本物）にも「節は書けません」と鳴りました。**
            # 同点の意味が、軸によって逆になります:
            #
            #   連続量（引数を刻んだ掃引） 同点 ＝ **目盛りが粗いだけ**かもしれない。
            #       `nenkin.worst_gap` の 189万は 1万きざみに直すと 276万でも同値で、
            #       **細かくすると頂上そのものが動きます。名指しは追試で壊れます。**
            #   数え上げ（表の行を歩く） 同点 ＝ **それが全部**。行の集合は完全なので、
            #       細かくする余地がありません。**壊れるのは「1つだけ」と言うこと**で、
            #       同点の行を全部挙げれば、その節は追試に耐えます。
            #
            # だから止めるのではなく、**書くべき文のほうを変えます。**
            band = abs(ys[idx] - edge) * FLAT_TOP_BAND
            flat = [x for j, (x, y) in enumerate(zip(xs, ys))
                    if 0 < j < len(ys) - 1 and abs(y - ys[idx]) <= band]
            return "逆転", {"どこ": kind, "x": xs[idx], "値": ys[idx],
                          "端では": edge, "並ぶ点": len(flat),
                          "数え上げ": enumerated,
                          "並ぶ x": flat if len(flat) > 1 else []}

    # 崖: 1つの段差だけが中央の5倍以上（**跳ぶ幅そのものが屑でないこと**）
    if len(moving) >= 3:
        mid = median(moving)
        biggest = max(moving)
        if mid > 0 and biggest / mid >= CLIFF_RATIO and biggest / scale >= MEANINGFUL:
            i = [abs(s) for s in steps].index(biggest)
            return "崖", {"x の手前": xs[i], "x の先": xs[i + 1],
                         "跳ぶ幅": steps[i], "中央の段差": mid}

    # 倍率: **段どうしの比そのものが節**（2026-08-18 に足した。**軸を開けた直後**）
    #
    # 同じ日に `sweep_enums` で文字列の軸を開けたところ、**16関数ぶんの軸に対して
    # 候補は +1件**でした。理由は形の語彙のほうにありました —— 3点の数え上げで
    # 鳴りうるのは「帯」と「逆転」だけで（頭打ちは tail が全体になり、崖は段が
    # 2つしかないので構造上あり得ない）、**単調に増えるだけの並びは、どの形にも
    # 当たりません。** ところが `koteishisan.unit_tax` の
    #
    #     小規模 116.67 ／ 一般 233.33 ／ 特例なし 700.0  ＝ **1 : 2 : 6**
    #
    # は、その回いちばんの発見でした。**数え上げの軸では、比が形です。**
    #
    # **`ratio` は `sweep_enums` だけが渡します。** `sweep_rows`（表の行）にも
    # 掛けると、単調な表がほぼ全部ここに落ちて**候補が一覧ごと膨らみます**
    # （`src/alerts.py` の「一覧が当たりを含まないまま育つ」の5件目になる）。
    # **場合分けの軸は要素が数個で、比を「1:2:6」と読み上げられる**ところが違います。
    # **広げるなら、先に当たり率を測ること**（手順 §4）。
    if ratio and lo > 0 and hi / lo >= RATIO_MIN:
        return "倍率", {"いちばん低い": xs[ys.index(lo)],
                      "いちばん高い": xs[ys.index(hi)],
                      "倍率": hi / lo, "値": lo,
                      "並び": [round(y / lo, 3) for y in ys]}
    return None


def _is_echo(value: float, defaults: list[float], xs: list[float]) -> bool:
    """**入力がそのまま返ってきているだけ**の欄か。

    表は前提を返りに入れ直します（`{"月給": monthly, "休んだ日数": days_off, …}`）。
    その欄は「動かしていない引数を動かしても変わらない」ので、
    **必ず `不変` として拾われます。しかも1つも面白くありません** ——
    2026-08-17 の1回目は、`kyugyo` の13件のうち**6件がこれ**でした。
    """
    if any(abs(value - d) < FLAT_TOL * max(1.0, abs(d)) for d in defaults):
        return True
    return any(abs(value - x) < FLAT_TOL * max(1.0, abs(x)) for x in xs)


def _moves(ys: list[float]) -> bool:
    """その欄は、この掃引で少しでも動いたか。"""
    lo, hi = min(ys), max(ys)
    scale = max(abs(lo), abs(hi))
    return scale != 0 and (hi - lo) / scale > FLAT_TOL


def table_constants(swept: list[tuple[str, list[float], list[dict]]]) -> set[str]:
    """**どの引数を動かしても1度も動かなかった欄** ＝ その表の定数。

    ## なぜ要るか（2026-08-18。**申し送りに名指しで残っていた**）

    `_is_echo` が落とすのは**入力の再掲**だけです（`{"月給": monthly}` のように
    引数がそのまま返りに入っている欄）。**表の中の定数は落としていません。**
    前の回が「新しい」と数えた中身を実際に並べると、そこが屑で埋まっていました:

        片効き  kokuho.keigen_cliff … members を動かしても 境目での軽減 は **20 のまま**
        片効き  kyugyo.calendar_span_cost … 不利な暦日・暦日の差・有利な暦日 は **92 のまま**

    **`20` は2割軽減の 20、`92` は3か月の暦日**で、どちらも引数ではないので
    `_is_echo` を素通りします。**kyugyo は「新しい5件」のうち4件がこれ**でした。

    **判定は意味ではなく構造でやります** —— その関数の**掃引できる引数を
    全部動かしてもなお動かない**なら、それは関係ではなく定数です。
    1本の列だけ見ていては区別がつかず（`不変` として正しく出てしまう）、
    **横に並べて初めて「これは定数だ」と言えます。**

    **引数が1つしかない関数には掛けません。** そのときは「動かない」と
    「定数」が同じものになり、**`不変` の形を丸ごと消してしまいます**
    （`不変` は本物の節になったことがあります ——「上限は片方の帯にしか効かない」）。
    **落とす向きの誤りは黙って効くので、区別がつかない場面では落とさないこと。**
    """
    if len(swept) < 2:
        return set()
    seen: set[str] = set()
    moved: set[str] = set()
    for _pname, _xs, rows in swept:
        for key in rows[0]:
            if any(key not in r for r in rows):
                continue
            seen.add(key)
            if _moves([r[key] for r in rows]):
                moved.add(key)
    return seen - moved


def sweep_function(fn: Callable, *, name: str = "") -> list[dict]:
    """1つの関数を掃引して、出た形を並べる。"""
    found = []
    enums = _enum_params(fn)
    base = {pn: items[0] for pn, items in enums}
    params = _sweepable_params(fn, skip=base)
    defaults = [d for _, d in params]
    # **振っていない引数にも値を渡すこと**（2026-08-19）。`params` には
    # 既定値の無い引数（`kogaku.limit(cost)` など）が入るようになったので、
    # 「渡さなければ既定値が入る」がもう成り立ちません。同じ値を明示的に
    # 渡すだけなので、既定値のある引数にとっては何も変わりません。
    base = {**{pn: d for pn, d in params}, **base}

    # **先に全部の引数を掃引します**（`table_constants` が横に並べて見るため）。
    #
    # **`default` を各行に持たせること**（2026-08-27 に直した）。ここは長らく
    # `(pname, xs, rows)` の3つ組で、下の刻み直しは**上の for が抜けたあとに
    # 残っている `default`**（＝ `params` の最後の引数の既定値）を渡していました。
    # `_cast` は「既定値が int なら int で渡す」ので、**最後の引数が int で、
    # いま刻んでいる引数が率（float）なら、刻み直しの点が全部 0 か 1 に潰れます。**
    # 症状は「刻むと1つも動きません」＝ 未判定で、**当たっている崖ほど黙って落ちます。**
    swept: list[tuple[str, float, list[float], list[dict]]] = []
    for pname, default in params:
        xs, rows = [], []
        for x in _grid(default, pname, _family(fn)):
            try:
                value = fn(**{**base, pname: _cast(default, x)})
            except Exception:
                continue
            scal = _scalars(value)
            if not scal:
                break
            xs.append(x)
            rows.append(scal)
        if len(xs) < 4:
            continue
        swept.append((pname, default, xs, rows))

    consts = table_constants([(p, x, r) for p, _d, x, r in swept])
    for pname, default, xs, rows in swept:
        keys = set(rows[0])
        for r in rows[1:]:
            keys &= set(r)
        for key in sorted(keys):
            ys = [r[key] for r in rows]
            hit = _classify(xs, ys)
            if hit:
                shape, detail = hit
                if shape == "崖":
                    detail = {**detail,
                              **_refine_cliff(fn, base, pname, default, key,
                                              detail)}
                if shape == "頭打ち":
                    detail = {**detail,
                              **_refine_plateau(fn, base, pname, default, key,
                                                detail)}
                if shape == "帯":
                    detail = {**detail,
                              **_refine_band(fn, base, pname, default, key,
                                             detail)}
                if shape == "不変" and (key in consts
                                      or _is_echo(ys[0], defaults, xs)):
                    continue
                found.append({"関数": name or getattr(fn, "__name__", "?"),
                              "動かした引数": pname, "見た値": key or "返り値",
                              "形": shape, "詳しく": detail,
                              "x の幅": (xs[0], xs[-1])})
        found.extend(_one_sided(xs, rows, sorted(keys), defaults,
                                name or getattr(fn, "__name__", "?"), pname,
                                consts))
    return found


#: 崖を細かく刻み直すときの分割数。**8 は「1周ぶんの時間を足さない」側で決めた値**
#: （関数を 7回 余分に呼ぶだけ。実測 `nenkin` 全体で +0.4秒）。
#: 大きくすると本物の崖の位置がより細く出ますが、掃引そのものが遅くなります。
CLIFF_REFINE_STEPS = 8


def _fine_xs(x_a: float, x_b: float, steps: int) -> list[float]:
    """`x_a` → `x_b` を刻む点。**行のあいだに点を置かないこと。**

    ## なぜ要るか（2026-08-27 に踏んだ。**刻み直し3つに共通の穴**）

    刻み直しは「粗い格子のせいで境目がずれる」を直す道具です。ところが
    **等分した点をそのまま渡すと、整数の軸に小数を渡します。**

    実物: `keihi.care_age_gap（young）` の帯を等分すると 64.5歳 が出ます。
    `_sweepable_params` は既定値を **`39.0`（float）**で返すので `_cast` は
    小数のまま渡し、**64.5歳 は「介護保険が乗らない」側に落ちます**
    （介護は 40〜64歳）。刻み直した出口は **63.625** と出ました ——
    **粗い格子を直しにいって、行のあいだの数を作っています。**
    そのまま節にすれば「63.625歳から」と画面に出る種類の誤りで、
    これは 08/26 の「帯 age 46〜62」と**同じ誤情報**です。

    ## やること

    両端がどちらも整数なら、**整数だけを返します**（重複は畳む）。
    そうでなければ従来どおり等分します。**新しいしきい値は持ち込みません** ——
    見ているのは「軸が整数か」だけです。

    ## 覆る条件

    整数の軸に小数の意味がある表が出てきたら（0.5人・0.5か月など）、
    ここは軸の刻み幅を表側から受け取る形に変えること。
    いまの `src/calc/` に、そういう軸はありません。
    """
    span = x_b - x_a
    if float(x_a).is_integer() and float(x_b).is_integer() and abs(span) >= 1:
        out: list[float] = []
        for i in range(steps + 1):
            x = float(round(x_a + span * i / steps))
            if not out or x != out[-1]:
                out.append(x)
        return out
    return [x_a + span * i / steps for i in range(steps + 1)]


def _refine_cliff(fn, base: dict, pname: str, default: float, key: str,
                  detail: dict, steps: int = CLIFF_REFINE_STEPS) -> dict:
    """**その「崖」は、細かく刻んでも崖か。** 連続量の軸だけに掛けます。

    ## なぜ要るか（2026-08-27 に踏んだ。**同じ形を2周 続けて踏んでいます**）

    `_classify` の崖は「**隣り合う2点の段差が、中央の段差の5倍以上**」です。
    x が数え上げ（表の行）ならそれで正しい —— 行と行のあいだには何もありません。
    **連続量では違います。** 格子が粗いと、**傾きが急なところから
    平らなところへ移るだけの滑らかな曲線が、必ず崖に見えます。**

    実物（2026-08-27）: `nenkin.assumption_flip（余裕_倍）` は
    「`base_annual_man` が 90→123 で -0.3692 跳ぶ（ふだんの段差は 0.0043）」
    と出ました。**格子は 33万きざみ**です。1万きざみで引き直すと
    0.706 → 0.674 → 0.653 …… と**1本の滑らかな坂**で、崖はありません。
    段差の比 86倍 は、曲線の左半分が急で右半分が平ら、というだけでした。

    **同じ形は 2026-08-26 の回も踏んでいます**（`keihi` の「帯 age 46〜62」——
    介護保険は実際には 40〜64歳 で、46〜62 は掃引の目盛りが粗いだけ）。
    手順の側には「**1件ずつ当たり直すこと**」と書いてあり、
    **書いてあるのに2周とも踏みました。** `逆転` は同じ問題に
    `[並 N点]` の印を付けて一覧の後ろへ回しています ——
    **崖にだけ、その印がありませんでした。**

    ## やること

    崖と言われた区間 `[x の手前, x の先]` を `steps` 等分して引き直し、
    **段差がまだ1つに集まっているか**を見ます。

        集まっている → 本物。**崖の位置が細く出る**ので、それも返す
        散らばった   → 傾きです。`細かくすると崖ではない` を立てる

    ## 中央ではなく「**ほかの段差の平均**」で割る理由（2026-08-27 に検査が捕まえた）

    最初は `_classify` と同じ「最大 ÷ **中央**」で書きました。**本物の崖で落ちます** ——
    きれいな階段を8等分すると、動く段は**1つだけ**で残り7つは 0 です。
    0 を除くと標本が1つになり、「刻んでも段が3つ未満です」＝ 未判定に化けます。
    **いちばん確かな崖が、いちばん判定できない**という逆立ちでした。

    だから割る相手を「**最大を除いた段差の平均**」にします。

        きれいな階段  ほかが全部 0 → 割る相手が 0 ＝ **崖**（∞倍）
        一様な坂      最大 ≒ ほかの平均 ＝ 1倍 → **坂**
        実物の坂      0.055 ÷ 0.046 ＝ 1.2倍 → **坂**（`assumption_flip`）

    倍率のしきい値は `CLIFF_RATIO` を使い回します。
    **新しいしきい値を持ち込まないこと** —— 2つの物差しが別々に古びます。

    返り: 元の `詳しく` に足す欄だけ。`fn` が呼べなければ
    `{"細かく刻めなかった": 理由}` を返し、**黙って通しません**
    （呼べなかったことと、崖でなかったことは別です）。
    """
    x0, x1 = detail.get("x の手前"), detail.get("x の先")
    if x0 is None or x1 is None or x1 == x0:
        return {"細かく刻めなかった": "区間が取れません"}
    fine_x, fine_y = [], []
    for i in range(steps + 1):
        x = x0 + (x1 - x0) * i / steps
        try:
            value = fn(**{**base, pname: _cast(default, x)})
        except Exception as exc:                       # noqa: BLE001
            return {"細かく刻めなかった": f"{type(exc).__name__}"}
        scal = _scalars(value)
        if key not in scal:
            return {"細かく刻めなかった": "同じ欄が出ませんでした"}
        fine_x.append(x)
        fine_y.append(scal[key])
    diffs = [abs(b - a) for a, b in zip(fine_y, fine_y[1:])]
    if len(diffs) < 3:
        return {"細かく刻めなかった": "刻んでも段が3つ未満です"}
    biggest = max(diffs)
    if biggest == 0:
        return {"細かく刻めなかった": "刻むと1つも動きません"}
    others = sorted(diffs)[:-1]
    rest = sum(others) / len(others)
    survives = bool(rest == 0 or biggest / rest >= CLIFF_RATIO)
    out = {"細かくすると崖ではない": not survives,
           "細かくしたほかの段差の平均": rest, "細かくした最大の段差": biggest}
    if survives:
        j = diffs.index(biggest)
        out["細かく刻んだ手前"] = fine_x[j]
        out["細かく刻んだ先"] = fine_x[j + 1]
    return out


def _refine_plateau(fn, base: dict, pname: str, default: float, key: str,
                    detail: dict, steps: int = CLIFF_REFINE_STEPS) -> dict:
    """**その「◯◯から上は同じ」の◯◯は、掃引の格子の点です。**

    ## なぜ要るか（2026-08-27 に踏んだ。**同じ形を3周 続けて踏んでいます**）

    `_classify` の頭打ちは「**後ろの3分の1が動かない**」で、返す `止まる x` は
    **その3分の1の先頭にある格子の点**です。本当の止まり際は
    `(手前の格子点, その点]` のどこかにあり、**格子が粗いほど右へずれます。**

    実物（2026-08-27）: `jutaku.relief_room（住民税から引ける上限）` は
    「`taxable` が **7,135,242** から上は 97,500 で止まる」と出ました。
    **本当の境目は 1,950,000円**です（住民税からの控除上限は
    課税総所得の5% と 97,500円 の低いほう ＝ 97,500 ÷ 0.05）。**3.7倍 ずれています。**

    そして **7,135,242 は `keihi` の掃引にも同じ数で出ます**
    （`keihi.aoiro_vs_keihi（事業税の差）… profit 7,135,242 から上は 22,500`）。
    **同じ数が別々の表に出るなら、それは制度の境目ではなく格子の点です。**

    **同じ形は 2回 直っています** —— `崖` は 2026-08-27 に `_refine_cliff`、
    `帯` は 08/26 の「帯 age 46〜62（介護保険は実際には 40〜64歳）」で
    名指しされました。**`頭打ち` にだけ、その刻み直しがありませんでした。**

    ## やること

    `(手前, 止まる x]` を `steps` 等分して引き直し、
    **止まった値と同じになる、いちばん左の点**を返します。

        細かくした止まる x        そこから上は同じ（狭めた位置）
        細かくした止まる x の手前  まだ動いている最後の点

    **狭めるだけで、頭打ちかどうかの判定は変えません** —— 崖と違い、
    「後ろが平ら」であること自体は格子が粗くても正しいからです
    （粗い格子は止まり際を**右へ**ずらすだけで、平らを作りはしません）。

    ## 覆る条件

    `手前` が無い（1点目から平ら）ときは刻めません。そのときは
    `止まり際を刻めなかった` を立てて、**黙って通しません** ——
    刻めなかったことと、格子が正しかったことは別です。
    """
    x_stop = detail.get("止まる x")
    x_prev = detail.get("止まる x の手前")
    y_stop = detail.get("止まった値")
    if x_prev is None or x_stop is None or x_stop == x_prev:
        return {"止まり際を刻めなかった": "手前の点がありません（1点目から平ら）"}
    scale = max(abs(y_stop), 1.0)
    fine: list[tuple[float, float]] = []
    for i in range(steps + 1):
        x = x_prev + (x_stop - x_prev) * i / steps
        try:
            value = fn(**{**base, pname: _cast(default, x)})
        except Exception as exc:                       # noqa: BLE001
            return {"止まり際を刻めなかった": f"{type(exc).__name__}"}
        scal = _scalars(value)
        if key not in scal:
            return {"止まり際を刻めなかった": "同じ欄が出ませんでした"}
        fine.append((x, scal[key]))
    # **末尾から見て、平らが続いているあいだ左へ伸ばします。**
    # 途中で1点だけ一致するような並びに引きずられないため
    # （左端まで一致してしまう回は、そもそも頭打ちの始まりが手前より左にある）。
    idx = len(fine) - 1
    while idx > 0 and abs(fine[idx - 1][1] - y_stop) / scale <= FLAT_TOL:
        idx -= 1
    if idx == 0:
        return {"止まり際を刻めなかった": "手前の点からもう平らです（格子より左に始まり）"}
    return {"細かくした止まる x": fine[idx][0],
            "細かくした止まる x の手前": fine[idx - 1][0]}


def _refine_band(fn, base: dict, pname: str, default: float, key: str,
                 detail: dict, steps: int = CLIFF_REFINE_STEPS) -> dict:
    """**その帯の両端は、掃引の格子の点です。**

    ## なぜ要るか（**同じ形を、この輪は3つの形で踏んでいます**）

    `_classify` の帯は「途中の一続きだけ値が違い、両端は同じ値に戻る」で、
    返す `帯の入口` は **帯の中に入った最初の格子点**、`帯の出口` は
    **まだ帯の中にある最後の格子点**です。本当の境目は
    `(入口の手前, 入口]` と `[出口, 出口の先)` のどこかにあり、
    **格子が粗いほど帯は内側へ縮んで見えます。**

    実物（2026-08-26 に踏んだ）: `keihi` の掃引が
    「**帯 age 46〜62**」と出しました。**介護保険は実際には 40〜64歳**です。
    46〜62 は目盛りが粗いだけで、**そのまま節にすると誤情報になります**
    （`docs/JOURNAL.md` 2026-08-26／その回の申し送りが名指ししています）。

    **同じ形は 2回 直っています** —— `崖` は `_refine_cliff`（2026-08-27）、
    `頭打ち` は `_refine_plateau`（同日）。**`帯` にだけ刻み直しがなく、
    08/26・08/27 03:0x・08/27 04:4x と 3周 続けて申し送りに残っていました。**

    ## やること

    両端の外側の1区間ずつを `steps` 等分して引き直し、
    **帯の中と同じ値になる、いちばん外側の点**を返します。

        細かくした帯の入口      そこから帯の中（＝ 左へ広がる）
        細かくした帯の入口の外  まだ帯の外にある最後の点
        細かくした帯の出口      そこまで帯の中（＝ 右へ広がる）
        細かくした帯の出口の外  もう帯の外にある最初の点

    **帯かどうかの判定は変えません。** 崖と違い、「途中だけ値が違う」こと自体は
    格子が粗くても正しく、粗い格子は**帯を内側へ縮めて見せるだけ**だからです。

    ## 覆る条件

    **連続量の軸だけに掛けること。** x が数え上げ（表の行）なら行と行のあいだに
    何も無いので、刻み直す余地はありません —— この関数は `sweep_function`
    （連続量の掃引）からしか呼ばれません（`sweep_rows` / `sweep_enums` は
    `_classify(..., enumerated=True)` を通り、ここへは来ない）。
    外側の点が無い（帯が掃引の端から始まっている）ときは刻めません。
    そのときは `帯の端を刻めなかった` を立てて、**黙って通しません** ——
    刻めなかったことと、格子が正しかったことは別です。
    """
    inner, outer = detail.get("帯の中"), detail.get("帯の外")
    if inner is None or outer is None:
        return {"帯の端を刻めなかった": "帯の値が取れません"}
    scale = max(abs(inner), abs(outer), 1.0)

    def _walk(x_out: float, x_in: float) -> tuple[list[float], list[float]] | str:
        """`x_out`（帯の外）→ `x_in`（帯の中）を steps 等分して値を引く。"""
        fx, fy = [], []
        for x in _fine_xs(x_out, x_in, steps):
            try:
                value = fn(**{**base, pname: _cast(default, x)})
            except Exception as exc:                   # noqa: BLE001
                return f"{type(exc).__name__}"
            scal = _scalars(value)
            if key not in scal:
                return "同じ欄が出ませんでした"
            fx.append(x)
            fy.append(scal[key])
        return fx, fy

    out: dict = {}
    pairs = (("入口", detail.get("帯の入口の手前"), detail.get("帯の入口")),
             ("出口", detail.get("帯の出口の先"), detail.get("帯の出口")))
    for side, x_out, x_in in pairs:
        if x_out is None or x_in is None or x_out == x_in:
            out[f"帯の{side}を刻めなかった"] = "外側の点がありません（掃引の端）"
            continue
        walked = _walk(float(x_out), float(x_in))
        if isinstance(walked, str):
            out[f"帯の{side}を刻めなかった"] = walked
            continue
        fx, fy = walked
        # **帯の中の端（i = steps）から外へ向かって、帯の中が続くあいだ伸ばします。**
        idx = len(fy) - 1
        while idx > 0 and abs(fy[idx - 1] - inner) / scale <= FLAT_TOL:
            idx -= 1
        if idx == 0:
            # 外側の格子点そのものが帯の中でした。`_classify` の段の切り方と
            # 食い違っているので、**狭めずに合図だけ返します。**
            out[f"帯の{side}を刻めなかった"] = "外側の点からもう帯の中です"
            continue
        out[f"細かくした帯の{side}"] = fx[idx]
        out[f"細かくした帯の{side}の外"] = fx[idx - 1]
    return out


def _one_sided(xs: list[float], rows: list[dict], keys: list[str],
               defaults: list[float], name: str, pname: str,
               consts: set[str] | None = None) -> list[dict]:
    """**同じ引数が、隣り合う欄の片方だけを動かしている**ところを拾う。

    ## なぜ要るか（2026-08-17 22:4x。**3回続けて申し送りに載っていた**）

    ここまでの4つの形（崖・逆転・頭打ち・不変）は、**1本の列の中の値の並び**しか
    見ていません。ところが 21:3x の回の5節は**1つも掃引から出ておらず**、
    その回の主題はこうでした ——

    > **調整支給率が、式の2つの項のうち片方にしか掛からない**

    **これはどの行にも、数として現れません。** 現れるのは
    「`x` を動かすと A は動くのに B は1円も動かない」という**欄どうしの対比**で、
    列を1本ずつ見ているかぎり、B は「不変」として単独で出るだけです。
    **単独の「不変」は退屈で、対比になって初めて節になります**
    （8/17 の実物: `koureikoyou` の「上限は片方の帯にしか効かない」、
    `kyoiku` の「下限4,000円は定額で逆向き」も同じ形）。

    **`不変` を消していないこと。** 片方だけが動かない事実は残るので、
    **対比のほうを1件足しています**（形が2つ出るのは重複ではなく、
    「B は動かない」と「x は A だけを動かす」が別の主張だからです）。
    """
    if len(keys) < 2:
        return []
    moving, frozen = [], []
    for key in keys:
        ys = [r[key] for r in rows]
        lo, hi = min(ys), max(ys)
        scale = max(abs(lo), abs(hi))
        if scale == 0:
            continue
        if (hi - lo) / scale <= FLAT_TOL:
            # **入力の再掲は数えない**（`_is_echo` と同じ理由。動かないのは当たり前）
            # **表の定数も数えない**（`table_constants`。どの引数でも動かない欄は
            # 関係ではなく定数で、「片効き」の対比が成り立ちません）
            if key not in (consts or set()) and not _is_echo(ys[0], defaults, xs):
                frozen.append(key)
        elif (hi - lo) / scale >= MEANINGFUL:
            # **動く側の再掲も数えないこと**（検査が捕まえた。**両側に要ります**）。
            # 掃引しているのが `months` なら、返りの `months` 欄は当然そのまま動きます。
            # それを「動く」に数えると **「months を動かすと months が動く」**という
            # 同語反復が出ます（17:5x の `_row_label` と同じ形。**片方だけの11件目**）。
            if all(abs(y - x) < FLAT_TOL * max(1.0, abs(x))
                   for y, x in zip(ys, xs)):
                continue
            moving.append(key)
    if not moving or not frozen:
        return []
    return [{"関数": name, "動かした引数": pname,
             "見た値": "／".join(frozen),
             "形": "片効き",
             "詳しく": {"動く": moving, "動かない": frozen,
                     "動かない値": rows[0][frozen[0]]},
             "x の幅": (xs[0], xs[-1])}]


def _rows(value: Any) -> list[dict] | None:
    """返りが「行の並び」ならそれを返す。**中身が dict の list だけ。**"""
    if isinstance(value, list) and value and all(isinstance(r, dict) for r in value):
        return value
    return None


def _readable(value: Any) -> bool:
    """掃引が**何かの数字として読める返り**か。

    ここは長らく `_scalars(value)` そのものでした。`_scalars` は
    「1つの返りから欄を取り出す」道具なので、**行の並び（`list[dict]`）には
    `{}` を返します** —— 表を返す関数は、行の側に数字を持っているからです。

    そのため `_enum_axis` は「この引数を入れても数字が返らない」と読み、
    **表を返す関数の場合分けの引数を、軸として1件も見つけられませんでした**
    （`iryohi.low_income_grid` はそれで丸ごと落ちていた）。
    行として歩けるものは `sweep_rows` が読むので、ここでも読めると数えます。
    """
    if _scalars(value):
        return True
    rows = _rows(value)
    return bool(rows) and len(rows) >= 2 and bool(_common_number_keys(rows))


def _common_number_keys(rows: list[dict]) -> set[str]:
    """**全部の行にあって、全部の行で数字**の欄。行を歩けるかの下限です。"""
    keys = set(_scalars(rows[0]))
    for r in rows[1:]:
        keys &= set(_scalars(r))
    return keys


def sweep_rows(fn: Callable, *, name: str = "") -> list[dict]:
    """**表そのものの中を歩く。**引数ではなく、行の並びを x にする。

    `season_grid()` や `ratio_to_monthly()` のように `list[dict]` を返す関数は、
    **その表の中に既に x 軸を持っています**（算定期間・労働日数・所得の帯）。
    引数を動かす掃引はここに入れないので、**表の8割が対象外**でした
    （2026-08-17 の1回目は 37本中5本しか出ませんでした）。

    行を歩けば、**崖・頭打ち・逆転が表の中で見えます** ——
    そしてこの回の3節のうち2節は、実際にそういう形でした。

    ## 場合分けを受け取る表は、場合ごとに歩く（2026-08-19 10:5x）

    引数を1つ埋めて先頭の場合だけ歩くと、**当たりを取り逃します。**
    `iryohi.low_income_grid` は区分ア〜オで6行の表を返しますが、
    崖が出るのは**区分ウだけ**です（控除の出る医療費が
    266,667円 → 2,257,000円。区分アでは1件も出ません）。
    **場合ごとに別の表**なので、1つの表に2度当てたことにはなりません。

    引数によらない欄は、同じ当たりが場合の数だけ出ます。
    **同じ（欄・形・詳しく）は1度だけ**にして、
    **場合によって変わったものにだけ**「固定した引数」を付けます。
    """
    cases = _row_call_cases(fn)
    if cases is None:
        return []
    found: list[dict] = []
    seen: set[tuple] = set()
    for fixed in cases:
        for hit in _rows_of_case(fn, name, fixed, tag=len(cases) > 1):
            sig = (hit["見た値"], hit["形"], repr(hit["詳しく"]))
            if sig in seen:
                continue
            seen.add(sig)
            found.append(hit)
    return found


def _rows_of_case(fn: Callable, name: str, fixed: dict,
                  *, tag: bool) -> list[dict]:
    """`fixed` で1回だけ呼んで、その表の行を歩く。"""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rows = _rows(fn(**fixed))
    except Exception:
        return []
    if not rows or len(rows) < 4:
        return []
    keys = _common_number_keys(rows)
    label_keys = _label_keys(rows)
    label_key = label_keys[0] if label_keys else None
    axis = _axis_keys(rows, keys)
    keys -= axis
    # 行を名指す欄そのものは、見た値にしない。**同語反復にしかなりません** ——
    # 「いちばん低い跳びは、跳びが 6,000 の行」。2026-08-17 に 12件ありました。
    label_col = (None if label_key
                 else next((k for k in rows[0] if k in (axis or keys)), None))
    found = []
    for key in sorted(keys):
        if key == label_col:
            continue
        ys = [_as_number(r[key]) for r in rows]
        if any(y is None for y in ys):
            continue          # 途中の行だけ単位がちがう欄。**混ぜて比べない**
        hit = _classify(list(range(len(rows))), ys, enumerated=True)
        if not hit:
            continue
        shape, detail = hit
        if shape == "不変":
            continue          # 表の中で動かない欄は、たいてい前提の再掲

        def _label(i: int) -> str:
            return (_join_label(rows[i], label_keys) if label_keys
                    else _row_label(rows[i], axis or keys)) or f"{i}行目"

        # 行番号を、読める見出しに直す。
        #
        # **ここは長らく `("止まる x", "x", "x の手前", "x の先")` という
        # 手書きの並びでした。** 前の回が `並ぶ x` を足したとき、この並びのほうを
        # 書き忘れ、同じ軸なのに名指した x は `30歳未満`、同点のほうは `7・8` と
        # **行番号のまま**出ていました（読む側には、その 7 が何の 7 か分かりません）。
        # 「形を足すと写し先を忘れる」（8/18 00:4x に3か所）の4か所目です。
        # **手書きの並びである限り、次に x のキーを足す回も同じことをします。**
        # **一度「名前に `x` を含む欄」で拾おうとして、それも外しました** ——
        # `帯` の欄は `帯の入口` / `帯の出口` で、**`x` の字が入っていません。**
        # 規約で拾うつもりが、既にある形を1つ取りこぼしていました。
        # 並びは `X_KEYS` 1つに集約し、**`_hit_points` とここの2か所が同じ並びを
        # 読みます。**（`Y_KEYS` と合わせて全部の欄を覆うことを検査が見ています）
        for k in X_KEYS:
            if k not in detail:
                continue
            v = detail[k]
            if isinstance(v, list):
                detail[k] = [_label(int(i)) for i in v]
            else:
                detail[k] = _label(int(v))
        hit_row = {"関数": name or getattr(fn, "__name__", "?"),
                   "動かした引数": "（表の行）", "見た値": key,
                   "形": shape, "詳しく": detail,
                   "x の幅": (0, len(rows) - 1)}
        if fixed and tag:
            # **埋めた引数は前提そのものです。**「どの区分の表か」が消えると、
            # 画面に出せる節になりません（`docs/CONSTRAINTS.md` の「前提を全部出す」）。
            hit_row["固定した引数"] = dict(fixed)
        found.append(hit_row)
    return found


def _row_call_cases(fn: Callable) -> list[dict[str, Any]] | None:
    """`fn()` を**行の並びとして呼ぶ場合の並び**。埋まらなければ `None`。

    ## なぜ要るか（2026-08-19 10:5x。**3つの掃引から同時に外れる形**）

    ここは長らく `fn()` と、**引数なしでしか**呼んでいませんでした。
    「表を返す関数は引数を取らない」という読みですが、`src/calc/` には
    **場合分けを1つ受けてから表を返す**関数があります ——
    `iryohi.low_income_grid(tier_name)` は区分ごとに6行の表を返します。

    そういう関数は、**3つの掃引の全部から同時に落ちます**:

        sweep_function  数値の引数しか振らない（`tier_name` は文字列）
        sweep_rows      `fn()` が TypeError（この節の穴）
        sweep_enums     返りが行の並びなので `_scalars` が `{}`

    **例外はどこにも出ません。** `unreachable` が「埋められなかった引数」として
    名前を出すだけで、理由は「入れ物が無い」と読めてしまいます。

    埋め方は既にあるものを使います —— 数え上げの軸なら**その並びの全部**、
    数の軸なら `calc_axes` の代表値（`_required_others` と同じ道）。
    数え上げの軸を全部まわすのは、**場合ごとに別の表**だからです
    （`sweep_rows` の docstring。区分ウにしか無い崖を取り逃さないため）。

    引数の要らない関数は `[{}]` を返すので、**今までどおり1回だけ**歩きます。
    """
    need = [n for n, p in calc_axes.real_params(fn)
            if p.default is inspect.Parameter.empty]
    if not need:
        return [{}]
    enums = dict(_enum_params(fn))
    base: dict[str, Any] = {}
    spread: tuple[str, list[str]] | None = None
    for n in need:
        if n in enums:
            # **振るのは1つだけ**（2つ以上あれば、残りは先頭で固定する。
            # 掛け合わせは `sweep_enums` の仕事で、ここは行のほうを見ています）
            if spread is None:
                spread = (n, enums[n])
            else:
                base[n] = enums[n][0]
            continue
        fill = _axis_fill(n, _family(fn))
        if fill is None:
            return None
        base[n] = fill
    if spread is None:
        return [base]
    pname, items = spread
    return [{**base, pname: e} for e in items]


def _axis_keys(rows: list[dict], keys: set[str]) -> set[str]:
    """**その表自身の x 軸**の欄を外す。

    表は「振った値」を先頭の欄に入れます（`{"total_income": 3_000_000, …}`）。
    行を歩くと、その欄は**必ず単調**で、点の置き方がまばらなら**必ず崖**になります ——
    2026-08-17 の row モード1回目は、`iryohi.floor_grid` の
    「`total_income` が 300万→500万 で 200万 跳ぶ」を候補として出しました。
    **跳んでいるのは制度ではなく、こちらが選んだ目盛りです。**

    外すのは**先頭の数値欄が単調なとき、その1つだけ**です
    （2つめ以降は結果の欄なので、単調でも外しません）。
    """
    first = next((k for k in rows[0] if k in keys), None)
    if first is None:
        return set()
    xs = [_as_number(r[first]) for r in rows]
    if any(x is None for x in xs):
        return set()
    up = all(b > a for a, b in zip(xs, xs[1:]))
    down = all(b < a for a, b in zip(xs, xs[1:]))
    return {first} if (up or down) else set()


def _label_keys(rows: list[dict]) -> list[str]:
    """行を**一意に**名指すのに要る、文字の欄の組。

    ## なぜ1欄では足りないか（2026-08-18 に実物で踏んだ）

    ここは長らく **`next(k for k, v in rows[0].items() if isinstance(v, str))`** ——
    **最初の文字の欄を1つ**でした。`shitsugyo.double_boundary` の行は
    `age_before / age_after / tenure_before / tenure_after` の**4つ組**で決まるのに、
    名前は `age_before` だけから作られ、**12行のうち4行が `30歳未満` になっていました。**

    実害は「読みにくい」ではありません。**印字が嘘になります** ——

        崖 … （表の行）が **30歳未満→45歳以上60歳未満** で -552,300 跳ぶ

    これは行8→行9で、実際には
    `(30歳未満・1年未満→1年以上5年未満)` から `(45歳以上60歳未満・1年以上5年未満→5年以上10年未満)`
    への跳びです。**年齢だけが動いたように読めますが、勤続のほうも動いています。**
    この行から節を書けば、**画面に出る数字の説明が事実と違う**ことになります。

    見つかったのは、同点の一覧（`並ぶ x`）を行の見出しに直した直後です ——
    **同じ名前が2つ並んで初めて、名前が行を指していないと分かりました。**
    1点しか印字しないあいだは、**壊れていても壊れて見えません。**

    欄は**少ないほうが読みやすい**ので、順に足して**一意になった時点で止めます**
    （足しても重なりが減らない欄は飛ばす）。それでも一意にならなければ、
    取れる全部を返します（`_join_label` が最後に行番号を付けます）。
    """
    str_keys = [k for k, v in rows[0].items()
                if isinstance(v, str) and all(isinstance(r.get(k), str) for r in rows)]
    chosen: list[str] = []
    for k in str_keys:
        if len({_join_label(r, chosen) for r in rows}) == len(rows):
            break
        before = len({_join_label(r, chosen) for r in rows})
        if len({_join_label(r, chosen + [k]) for r in rows}) > before:
            chosen.append(k)
    return chosen


def _join_label(row: dict, keys: list[str]) -> str:
    """行の見出しを1つの言葉にする。**欄が複数なら「・」で繋ぐ。**"""
    return "・".join(str(row.get(k, "")).strip() for k in keys)


def _row_label(row: dict, numeric_keys: set[str]) -> str | None:
    """文字の見出しが無い表で、行を指す言葉を作る。**最初の数値欄を使う。**

    **単位つきの文字列は、そのまま見せること**（`所得税率=33%`）。
    `float` に落として `_fmt` に通すと `33` になり、**単位が消えます。**
    """
    for k, v in row.items():
        if k not in numeric_keys:
            continue
        if isinstance(v, str):
            return f"{k}={v.strip()}"
        n = _as_number(v)
        return f"{k}={_fmt(n)}" if n is not None else None
    return None


def _cast(default: float, x: float) -> Any:
    """既定値が int なら int で渡す。**float を渡すと桁が変わる表がある。**"""
    return x if isinstance(default, float) else int(x)


#: 出す順。**珍しいほど前**（崖と逆転は、そのまま節の主題になります）
SHAPE_ORDER = {"崖": 0, "帯": 1, "片効き": 2, "逆転": 3, "頭打ち": 4, "不変": 5, "読めない": 6}


def dedupe(hits: list[dict]) -> list[dict]:
    """同じ欄が、引数を変えるたびに同じ形で出るのをまとめる。

    `不変` はとくに増えます —— 3つの引数を持つ関数なら、
    **同じ欄が3回**「動かしても変わらない」として出ます。
    """
    seen: dict[tuple, dict] = {}
    for h in hits:
        key = (h["表"], h["関数"], h["見た値"], h["形"])
        if key in seen:
            seen[key].setdefault("ほかの引数", []).append(h["動かした引数"])
            continue
        seen[key] = h
    return sorted(seen.values(),
                  key=lambda h: (SHAPE_ORDER.get(h["形"], 9), h["表"], h["関数"]))


def calc_modules() -> list[str]:
    """`src/calc/` の表の名前。**`_` 始まりは道具なので外す。**"""
    from src import calc
    return sorted(m.name for m in pkgutil.iter_modules(calc.__path__)
                  if not m.name.startswith("_"))


def sweep_enums(fn: Callable, *, name: str = "") -> list[dict]:
    """**文字列の軸を歩く。**`part` / `kind` のような場合分けを x にする。

    x は数え上げ（表の行と同じ）なので `enumerated=True` です。
    **`min_points=3` を渡しているのがここだけである理由**:
    連続量は目盛りをこちらが選ぶので3点は少なすぎますが、
    **数え上げの軸は「それが全部」**です（`PARTS` は3つしかありません）。
    4点を要求すると、**3つの帯で場合分けする制度が1件も出ません** ——
    そしてそれが、この直しが拾いにきた当のものでした
    （`koteishisan` の 1㎡単価 1:2:6）。

    **他の掃引の下限は動かしていません。** `sweep_rows` は4点のままです
    （表の行が3つしかない表は、まだ実物にありません）。
    """
    found = []
    enums = _enum_params(fn)
    if not enums:
        return []
    for pname, items in enums:
        # 他の数え上げの軸は、先頭で固定する（1度に1つだけ動かす）
        base = {pn: v[0] for pn, v in enums if pn != pname}
        rest = _required_others(fn, pname)
        if rest is None:
            continue
        base = {**rest, **base}
        rows: list[dict] = []
        labels: list[str] = []
        for e in items:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    value = fn(**base, **{pname: e})
            except Exception:
                continue
            scal = _scalars(value)
            if not scal:
                continue
            rows.append(scal)
            labels.append(e)
        if len(rows) < 3:
            continue
        keys = set(rows[0])
        for r in rows[1:]:
            keys &= set(r)
        for key in sorted(keys):
            ys = [r[key] for r in rows]
            hit = _classify(list(range(len(rows))), ys,
                            enumerated=True, min_points=3, ratio=True)
            if not hit:
                continue
            shape, detail = hit
            if shape == "不変":
                continue      # 場合分けで動かない欄は、たいてい前提の再掲
            # 行番号を、読める見出しに直す（`sweep_rows` と同じ `X_KEYS` を読む）
            for k in X_KEYS:
                if k not in detail:
                    continue
                v = detail[k]
                if isinstance(v, list):
                    detail[k] = [labels[int(i)] for i in v]
                else:
                    detail[k] = labels[int(v)]
            found.append({"関数": name or getattr(fn, "__name__", "?"),
                          "動かした引数": pname, "見た値": key or "返り値",
                          "形": shape, "詳しく": detail,
                          "x の幅": (labels[0], labels[-1])})
    return found


def sweep_calc(name: str) -> list[dict]:
    """1本の表を丸ごと掃引する。"""
    mod = importlib.import_module(f"src.calc.{name}")
    out = []
    for fname, fn in vars(mod).items():
        if fname.startswith("_") or fname in ("check_tables", "main"):
            continue
        if not callable(fn) or getattr(fn, "__module__", "") != mod.__name__:
            continue
        if not inspect.isfunction(fn):
            continue
        # **データ組を引数に取る関数は、欄で呼べる形に開いてから掃引する。**
        # 開けなければ `None` が返るので、そのままの関数を使う
        fn = dataclass_view(fn) or fn
        why = unreachable(fn)
        if why:
            UNCALLABLE.append((name, fname, why))
        # **掃引中は stdout を捨てる。**表の中には説明を print する関数があり、
        # そのまま流すと候補の一覧が本文で埋まります（2026-08-17 に踏んだ）
        with contextlib.redirect_stdout(io.StringIO()):
            hits = (sweep_function(fn, name=fname) + sweep_rows(fn, name=fname)
                    + sweep_enums(fn, name=fname))
        for hit in hits:
            hit["表"] = name
            out.append(hit)
    return dedupe(out)


def sweep_all(names: Iterable[str] | None = None) -> list[dict]:
    out = []
    UNCALLABLE.clear()
    PARTIAL_ENUM.clear()
    _ENUM_CACHE.clear()
    for name in (names if names is not None else calc_modules()):
        try:
            out.extend(sweep_calc(name))
        except Exception as exc:                      # 表1本の壊れで全体を止めない
            out.append({"表": name, "関数": "?", "動かした引数": "?", "見た値": "?",
                        "形": "読めない", "詳しく": {"理由": str(exc)[:80]},
                        "x の幅": (0, 0)})
    return out


# --- 既に節が言っている候補を落とす（2026-08-17 20:5x に足した） -------------
#
# **候補の件数は、`src/section_depth.py` の同点破りに使われています**（(B) の1位）。
# ところが数えていたのは**拾えた形の数**で、**まだ誰も言っていない形の数**では
# ありませんでした。前の回の実測（申し送りの1件目）:
#
#     ideco  掃引 3件 → **3件とも既存の節がもう言っていること**。それでも (B) の1位
#
# **1位は「掘れば節が出る表」のつもりで読まれます**（手順 §4 の既定）。
# 既出で水増しされた数で破ると、**掘っても0節の表を1位に出します** ——
# `critique_queue --next` → 同点のモジュール名 に続く、**同じ形の3度目**です。
#
# 判定は**節の本文にその点が印字されているか**だけで見ます（意味は読みません）。
# 落とす向きに外れると候補が過小に出るので、**確実な形だけ**を既出と呼びます:
#
#     1. 点の表記がそのまま出てくる（`40%` / `年収=11,100,000` の右辺）
#     2. 軸の名前が出ている行に、その数が出てくる（桁区切りの有無は問わない）
#     3. 同じ行に印字された帯（`6,500,000〜6,800,000`）が、その点を含む
#
# 3 が要るのは、節が**点ではなく帯**で書かれることがあるからです（実測:
# ideco の `grid` は 6,600,000 で止まり、節は「帯 年収 6,500,000〜6,800,000円」）。
# **`不変` は x を持たない**ので、止まっている値そのもので見ます。
_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_RANGE_RE = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)\s*[〜~ー–—-]\s*(-?\d[\d,]*(?:\.\d+)?)")
# 印字は円未満を切り捨てるので、完全一致では拾えません（`_classify` と同じ考え）。
_COVER_TOL = 1e-6


def _to_number(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _point_of(raw: Any) -> tuple[str | None, str, float | None]:
    """掃引の点を (軸の名前, 表記, 数) に割る。**`年収=11,100,000` の形。**"""
    if isinstance(raw, str):
        axis, _, rest = raw.partition("=")
        if rest:
            return axis.strip(), rest.strip(), _to_number(_NUM_RE.search(rest).group()
                                                          if _NUM_RE.search(rest) else "")
        m = _NUM_RE.search(raw)
        return None, raw.strip(), _to_number(m.group()) if m else None
    if isinstance(raw, (int, float)):
        return None, _fmt(float(raw)), float(raw)
    return None, str(raw), None


def _near(a: float, b: float) -> bool:
    return abs(a - b) <= _COVER_TOL * max(1.0, abs(a), abs(b))


# 軸の名前が本文に1度も出てこない点で、「数だけ」で既出と呼んでよい下限。
# **`years=1` や `等級=3` を既出と呼ばないため**（2026-08-17 20:5x に踏んだ）。
# 入れた直後の実測は 94件→新しい6件で、中を見ると `years=1` が既出でした ——
# 節の本文に `years` は1度も出てきません（引数名は英語、節は日本語）。
# 当たっていたのは**表記の `1` が、どこかの行に含まれる**という照合です。
# **短い数は、どの表の本文にも必ず出てきます。**
_LONE_NUMBER_MIN = 1000


def _written_forms(num: float) -> list[float]:
    """**同じ量を、節が書きうる形**に開く（2026-08-18。実測で3つ出た）。

    照合が外れていた候補を追跡すると、値そのものは**印字されているのに
    書き方だけが違う**、という形が2つありました。

        跳ぶ幅 **-800,000**  ← 節は「1年のばすと浮く額 **800,000円**」
        所得税率 **0.33**    ← 節は「**33%**へ」

    **どちらも「まだ誰も言っていない」に倒れます。** 符号は「どちらから見た差か」
    でしかなく、率は書き方の流儀でしかないので、**別の事実ではありません。**
    """
    out = [num, -num] if num else [num]
    if 0 < abs(num) < 1:                      # 率は百分率でも書かれる
        out += [num * 100, -num * 100]
    return out


def _found_in(num: float | None, lines: list[str]) -> bool:
    """その数が、渡した行のどれかに印字されているか（帯に入っていてもよい）。"""
    if num is None:
        return False
    wanted = _written_forms(num)
    for ln in lines:
        for m in _NUM_RE.finditer(ln):
            got = _to_number(m.group())
            if got is not None and any(_near(got, w) for w in wanted):
                return True
        for lo, hi in _RANGE_RE.findall(ln):
            a, b = _to_number(lo), _to_number(hi)
            if a is not None and b is not None and min(a, b) <= num <= max(a, b):
                return True
    return False


def _point_printed(raw: Any, lines: list[str]) -> bool | None:
    """その1点が、節の本文に印字されているか。**`None` は「判定できない」。**

    **軸の名前が本文にある点だけを、その行の中で照合します。**
    軸が本文に1度も出てこない（＝引数名が英語・節は日本語）点は、
    **その行に絞れないので照合できません** —— 小さい数は本文のどこかに
    必ず出てくるので、`True` と読むと全部が既出になります。
    そこは `False`（新しい）でもなく **`None`（判定不能）** を返し、
    呼ぶ側が**結果の値のほうで**見ます（`is_covered`）。
    """
    axis, shown, num = _point_of(raw)
    axis_lines = [ln for ln in lines if axis and axis in ln] if axis else []
    if axis and axis_lines:
        if _found_in(num, axis_lines):
            return True
        # **軸と値が同じ行に並ぶのは、散文の節だけです**（2026-08-18）。
        # 節の多くは**表**で、そこでは軸は見出し行・値は行データにあり、
        # **構造上いちども同じ行に来ません**:
        #
        #     ...  月給       標準報酬月額   保険料の増(年) ...   ← 軸はここ
        #     3   104,000円   101,000円      6,588円        ← 値はここ
        #
        # ここは長らく、その場合に `False`（＝**まだ誰も言っていない**）を
        # 返していました。`is_covered` は `False` を見た時点で打ち切るので、
        # **結果の値のほうを見にいく控えの道に、一度も入れません。**
        # 実測（8/18）: 「新しい」と数えられた `shahoken` の6件は6件とも
        # **値が本文に印字されていました**（`月給=101,000` は3か所）。
        #
        # **軸が本文にあるのに、その行では見つからない**は、
        # 「無い」ではなく**「この見方では言えない」**です。`None` を返して
        # 控えの道へ渡します（**判定できないものを断定しない**）。
        return None
    # **行の見出しが複数の欄でできているとき**（`30歳未満・1年未満`）は、
    # まるごとの文字列では照合できません（2026-08-18）。節はその4つ組を
    # 「30歳未満で勤続1年未満なら」と散文で書くので、**繋いだ形は本文に出ません。**
    #
    # `_label_keys` を入れて見出しを一意にした直後、`shitsugyo` の
    # **6件が6件とも「新しい」に化けました** —— 節はどれも前からあります。
    # ここを直さないと、(B) の同点破りが**見出しを長くした表だけ**を上位に上げます。
    #
    # 部品ごとに見て、**全部あれば既出・1つも無ければ新しい・途中なら判定しない。**
    # 途中を `False` にしないのは、`is_covered` が `False` で打ち切るからです
    # （結果の値を見る控えの道に、一度も入れなくなる。すぐ上の註と同じ穴）。
    if shown and "・" in shown:
        parts = [p for p in shown.split("・") if p.strip()]
        hits = sum(any(p in ln for ln in lines) for p in parts)
        return True if hits == len(parts) else (False if hits == 0 else None)
    # 単位つきの表記（`40%` など）は、そのまま出ていれば既出
    if shown and shown.strip("-0123456789.,"):
        return any(shown in ln for ln in lines)
    if num is not None and abs(num) >= _LONE_NUMBER_MIN:
        return _found_in(num, lines)
    return None


def _hit_points(hit: dict) -> list[Any]:
    """その候補を名指ししている **x の点**。**無ければ空**（判定しない）。"""
    d = hit.get("詳しく") or {}
    if hit.get("形") == "不変":
        return []
    return [d[k] for k in NAMING_X_KEYS if k in d]


def _hit_outcome(hit: dict) -> Any:
    """その候補が言っている **結果の値**（x が照合できないときの控え）。

    **`片効き` を足したときに、ここも足すのを忘れかけました**（2026-08-17 22:5x）。
    `片効き` は `x の点`（`_hit_points`）も、上の3つの欄も持たないので、
    **`is_covered` が構造上いつも False ＝「まだ誰も言っていない」を返します。**
    `status.py` は `novel_counts` で (B) の同点を破るので、**新しい形を足した表だけが、
    中身と無関係に上位へ上がる**ことになります（実際、足した直後の実測は
    juminzei 1・kokuho 2・kyugyo 2 が**全部「新しい」**でした）。

    **これは「一覧が当たりを含まないまま育つ」と同じ壊れ方**で、向きだけが逆です ——
    育つのではなく、**判定できないものを「当たり」に数えていました。**
    `片効き` が言っているのは「この欄は動かない」なので、**動かない値**を
    結果として渡します（x が無いときの控えの道は、もう書いてあります）。

    **`帯` を足した回（2026-08-18）は、この註を読んだうえで踏みました。**
    足した直後の掃引で `kokuho.cliff_by_age` の4件が全部「新しい」と出ています ——
    **その表は、その回に書いた節そのもの**です。註が名指ししているのは
    `片効き` 1件だけなので、**「自分の形も同じ穴に落ちる」とは読まれませんでした。**
    形を足すときは、**`_hit_points` と `_hit_outcome` の両方に欄を足すこと。**
    `tests/test_section_sweep.py` が、`SHAPES` の全部について
    **どちらか一方は必ず埋まる**ことを見ています。
    """
    d = hit.get("詳しく") or {}
    for k in ("止まった値", "値", "跳ぶ幅", "動かない値", "帯の中"):
        if k in d:
            return d[k]
    return None


#: 本文に書かれた比。**`7.2倍` と `1:2:6` の2つの書き方だけを見ます。**
#: 素の数（`_found_in`）で見ないのは、**小さい数はどの節にも出てくる**からです
#: （`6` は「6分の1」でも当たってしまう）。
_RATIO_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*倍")
_COLON_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?(?::[0-9]+(?:\.[0-9]+)?)+")


def _normalized(seq: list[float]) -> list[float] | None:
    """いちばん小さい段を 1 にそろえた並び。**0 や負が混じれば `None`。**"""
    if not seq or min(seq) <= 0:
        return None
    lo = min(seq)
    return sorted(v / lo for v in seq)


def _ratio_printed(hit: dict, lines: list[str]) -> bool:
    """その比が、節の本文に書かれているか。

    **割り引いて読むこと**（2026-08-18 に、直した本人が気づいた）:
    ここは本文のどこに出てくる `N倍` でも当てます。**何の比かは見ていません。**
    `koteishisan` の節は「面積を2倍にしたときの倍率」として
    `2.00倍` `3.0倍` `2.25倍` `4.33倍` を並べているので、
    **倍率がその近くの値の候補は、別の話題でも既出と読まれます。**

    いまそれで困っていません（11件のうち当たっているのは `6倍` と `5.1倍` で、
    どちらも**同じことを言っている行**でした）。**覆る条件**: 既出と出た候補を
    追って、**本文が言っているのは別の比だった**が1件でも出たら、
    `N倍` の行に**端の名前が同居していること**を足すこと
    （`_point_printed` が軸の名前でやっているのと同じ絞り方です）。
    """
    d = hit.get("詳しく") or {}
    ratio = d.get("倍率")
    seq = _normalized([float(v) for v in d.get("並び") or []])
    for ln in lines:
        for m in _RATIO_RE.finditer(ln):
            got = _to_number(m.group(1))
            if got is not None and ratio is not None and _near(got, float(ratio)):
                return True
        if seq is None:
            continue
        for m in _COLON_RE.finditer(ln):
            written = _normalized([float(x) for x in m.group().split(":")])
            if written is not None and len(written) == len(seq) \
                    and all(_near(a, b) for a, b in zip(written, seq)):
                return True
    return False


def is_covered(hit: dict, sections: dict[str, str] | None) -> bool:
    """その候補を、いまの節がもう言っているか。

    **意味は読みません。**「この点は、もう画面に出ている」だけを見ます。

    - x の点が1つでも**印字されていない**と分かったら → **新しい**
    - x の点が照合できて、全部印字されていれば → **既出**
    - x が1つも照合できない（軸の名前が本文に無い）ときだけ、
      **結果の値**が印字されているかで見ます（`kokuho.cliff_by_members` の
      「6人で 92,570円」は、軸 `被保険者数` が本文に無く、額は出ている）
    """
    if not sections:
        return False
    lines = [ln for body in sections.values() for ln in str(body).splitlines()]
    if hit.get("形") == "倍率":
        # **`倍率` が言っているのは比そのものです。端の名前ではありません。**
        #
        # 2026-08-18 に足した形で、既定の道を通すと **11件が11件とも既出**でした ——
        # `いちばん低い` / `いちばん高い` は `要支援1` `要介護5` のような**区分の名前**で、
        # どの節にも普通に出てくるからです。**「7.2倍」はどこにも書いていないのに、
        # 端の名前が出ているというだけで既出**になります。
        #
        # 落ちる先は `status.py` の「新しい M件」で、**この形を足した意味が消えます**
        # （(B) の同点破りも、`倍率` からは1件も入りません）。
        # だから比の側で見ます —— **`7.2倍` か `1:2:6` が本文にあるか。**
        return _ratio_printed(hit, lines)
    judged = [_point_printed(p, lines) for p in _hit_points(hit)]
    if any(v is False for v in judged):
        return False
    if any(v is True for v in judged):
        return True
    out = _hit_outcome(hit)
    return _point_printed(out, lines) is True if out is not None else False


def unnameable(hit: dict) -> bool:
    """**その候補は、この目盛りのままでは節にできない**（`[並 N点]` の側）。

    `逆転` は「いちばん高いのは端ではなく x のとき」と言いますが、
    **同じ高さが他にもあると、その x を名指しできません** ——
    印字の側も「細かく刻み直すまで、この x を名指しする節は書けません」と
    言っています。**言っているのに、一覧の並び順には入っていませんでした**
    （2026-08-26 に測って足した。`逆転` の 12件中7件 ＝ 58%）。

    **`数え上げ` の同点は別です。** 行が数え上げなので同点が「それが全部」＝
    「1つだけ名指さず、N件を全部書くこと」で**節になります。** 沈めません。

    **崖の `[坂]` も同じ側です**（2026-08-27。`_refine_cliff`）。
    細かく引き直して段が1つに集まらなかった候補は、**その x を名指しできません** ——
    `逆転` の `[並 N点]` とまったく同じ理由です。
    **`[崖◎]`（細かくしても崖）は沈めません** —— あちらは位置がより細く出た側で、
    むしろ書きやすくなっています。
    """
    d = hit.get("詳しく") or {}
    if d.get("細かくすると崖ではない"):
        return True
    return bool(d.get("並ぶ点", 1) > 1 and not d.get("数え上げ"))


def undecided(hit: dict, sections: dict[str, str] | None) -> bool:
    """その候補は「**新しいと分かった**」のか、「**判定できなかった**」のか。

    `is_covered` が `False` を返す道は2本あります。**混ぜてはいけません。**

        (1) x の点、または結果の値が **印字されていないと分かった** → 本当に新しい
        (2) x も結果も **照合できなかった**（`_point_printed` が `None`）
            → `is_covered` は `False` を返すが、**分かったのではない**

    (2) が起きるのは、`_LONE_NUMBER_MIN`（1000）未満の裸の数だけを結果に持つ
    候補です。**倍率・年齢・パーセントは、ここに全部落ちます。**
    実例（2026-08-24）: `nenkin.birth_gap_ratio … 1.25 のまま` は「新しい」と
    出ますが、節は「0.5% ÷ 0.4% ＝ 1.25倍で、1か月でも60か月でも同じです」と
    **もう印字しています。**

    **実測 2026-08-24**: 新しい 568件のうち **203件（36%）が (2)**
    （不変 79・頭打ち 48・逆転 34・片効き 24・崖 9・帯 9）。
    `src/supply.py` はこの「新しい」を在庫に数えるので、**その36%は
    「あるかどうか分からないもの」を在庫に積んでいます。**

    **消さずに、別に数えて印字する**のがここの答えです ——
    落とすと在庫が過小に振れ、黙って足すと過大に振れます。
    **どちらへ倒すかを決めるには、まず幅が見えていること。**
    """
    if is_covered(hit, sections):
        return False
    if not sections:
        return False          # 節そのものが読めない回。**この道具の欠陥ではない**
    lines = [ln for body in sections.values() for ln in str(body).splitlines()]
    if hit.get("形") == "倍率":
        # `_ratio_printed` は True/False しか返さないので、判定はいつも付きます。
        # **ただし比を1つも持たない候補は、照合するものがありません。**
        d = hit.get("詳しく") or {}
        return d.get("倍率") is None and not d.get("並び")
    judged = [_point_printed(p, lines) for p in _hit_points(hit)]
    if any(v is False for v in judged):
        return False
    out = _hit_outcome(hit)
    return out is None or _point_printed(out, lines) is None


def novel_counts(hits: list[dict],
                 all_sections: dict[str, dict[str, str]] | None,
                 ) -> tuple[dict[str, int], dict[str, int]]:
    """表ごとの (拾えた件数, まだ誰も言っていない件数) を返す。

    **同点を破るのに使うのは2つめ**です（`src/section_depth.py`）。
    1つめも返すのは、**行に両方出して人が検算できるようにするため** ——
    落とす向きの誤りは「候補が少なく見える」なので、**黙って落とさないこと。**
    """
    total: dict[str, int] = {}
    novel: dict[str, int] = {}
    for hit in dedupe(hits):
        name = hit.get("表", "?")
        total[name] = total.get(name, 0) + 1
        if not is_covered(hit, (all_sections or {}).get(name)):
            novel[name] = novel.get(name, 0) + 1
    for name in total:
        novel.setdefault(name, 0)
    return total, novel


def _fmt(v: float) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, float) and abs(v - round(v)) > 1e-9:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{round(v):,}"


def line_of(hit: dict) -> str:
    d = hit["詳しく"]
    if hit["形"] == "不変":
        tail = (f"{hit['動かした引数']} を {_fmt(hit['x の幅'][0])}→"
                f"{_fmt(hit['x の幅'][1])} と動かしても {_fmt(d['値'])} のまま")
    elif hit["形"] == "帯":
        tail = (f"{hit['動かした引数']} が {_fmt(d['帯の入口'])}〜{_fmt(d['帯の出口'])} "
                f"のあいだだけ {_fmt(d['帯の中'])}、その前後は {_fmt(d['帯の外'])}"
                f"（差 {_fmt(d['差'])}）")
    elif hit["形"] == "頭打ち":
        tail = (f"{hit['動かした引数']} が {_fmt(d['止まる x'])} から上は "
                f"{_fmt(d['止まった値'])} で止まる")
        # **頭打ちの `止まる x` は掃引の格子の点です**（2026-08-27。`_refine_plateau`）。
        # 崖の `[坂]` と同じ扱い —— 印字で言い、名指しできる幅まで狭めます。
        if d.get("細かくした止まる x") is not None:
            tail += (f"  **[止◎]** {CLIFF_REFINE_STEPS}等分して引き直すと、"
                     f"止まるのは **{_fmt(d['細かくした止まる x'])} から上**"
                     f"（まだ動いている最後は {_fmt(d['細かくした止まる x の手前'])}）"
                     f" —— **節に書くのはこちらの x です**")
        elif d.get("止まり際を刻めなかった"):
            tail += (f"  **[未刻]** 止まり際を引き直せませんでした"
                     f"（{d['止まり際を刻めなかった']}）—— "
                     f"**この x は格子の点です。そのまま節に書かないこと**")
    elif hit["形"] == "崖":
        tail = (f"{hit['動かした引数']} が {_fmt(d['x の手前'])}→{_fmt(d['x の先'])} で "
                f"{_fmt(d['跳ぶ幅'])} 跳ぶ（ふだんの段差は {_fmt(d['中央の段差'])}）")
        # **崖にも「目盛りが粗いだけ」があります**（2026-08-27。`_refine_cliff`）。
        # `逆転` の `[並 N点]` と同じ扱い —— 印字で言い、一覧の後ろへ回します。
        if d.get("細かくすると崖ではない"):
            tail += (f"  **[坂]** {CLIFF_REFINE_STEPS}等分して引き直すと、"
                     f"最大の段差 {_fmt(d['細かくした最大の段差'])} に対して"
                     f"ほかの段差の平均が {_fmt(d['細かくしたほかの段差の平均'])} —— "
                     f"**段が1つに集まりません。崖ではなく傾きです。**"
                     f"この x を名指しする節は書けません")
        elif d.get("細かく刻んだ手前") is not None:
            tail += (f"  **[崖◎]** {CLIFF_REFINE_STEPS}等分しても段は1つ —— "
                     f"**跳ぶのは {_fmt(d['細かく刻んだ手前'])}→"
                     f"{_fmt(d['細かく刻んだ先'])} のあいだ**（ここまで細く言えます）")
        elif d.get("細かく刻めなかった"):
            tail += (f"  **[未刻]** 細かく引き直せませんでした"
                     f"（{d['細かく刻めなかった']}）—— **崖かどうかは未判定です**")
    elif hit["形"] == "逆転":
        tail = (f"{d['どこ']}のは端ではなく {hit['動かした引数']}="
                f"{_fmt(d['x'])} のとき（{_fmt(d['値'])}／端では {_fmt(d['端では'])}）")
        if d.get("並ぶ点", 1) > 1:
            # **区切りは `／`。`・` にしないこと**（2026-08-18）。
            # 行の見出しそのものが `30歳未満・1年未満` と `・` で繋がっているので、
            # 一覧まで `・` で繋ぐと **2件なのか4件なのか読めません。**
            xs_txt = "／".join(_fmt(x) for x in d["並ぶ x"][:4])
            more = "ほか" if len(d["並ぶ x"]) > 4 else ""
            if d.get("数え上げ"):
                # 行は数え上げなので、同点は「それが全部」。**節は書けます。**
                tail += (f"  **[並 {d['並ぶ点']}点]** 同じ高さが {xs_txt}{more} にもあります"
                         f" —— **1つだけ名指さず、{d['並ぶ点']}件を全部書くこと**")
            else:
                tail += (f"  **[並 {d['並ぶ点']}点]** 同じ高さが {xs_txt}{more} にもあります"
                         f" —— **目盛りが粗いだけかもしれません。"
                         f"細かく刻み直すまで、この x を名指しする節は書けません**")
    elif hit["形"] == "片効き":
        tail = (f"{hit['動かした引数']} は {'・'.join(d['動く'])} を動かすのに "
                f"{'・'.join(d['動かない'])} は {_fmt(d['動かない値'])} のまま")
    else:
        tail = str(d)
    fixed = hit.get("固定した引数")
    if fixed:
        # **前提が読む側に届かないと、節は書けません**（2026-08-19 10:5x）。
        # 場合分けを受け取る表は「どの場合の表か」で当たりが変わります ——
        # `iryohi.low_income_grid` の崖は**区分ウにしか無い**ので、
        # ここを落とすと「低所得の表に崖がある」としか読めなくなります。
        tail += "（" + "・".join(f"{k}={_fmt(v)}" for k, v in fixed.items()) + " のとき）"
    return (f"  {hit['形']:<4} {hit['表']}.{hit['関数']}"
            f"（{hit['見た値']}）… {tail}")


#: 直前の `_covered_map` で「**判定できなかった**」候補の id。
#: `report_lines` が件数を出すためだけの控えです（`undecided()` の註）。
_UNDECIDED: set[int] = set()


def _covered_map(hits: list[dict]) -> dict[int, bool]:
    """候補ごとに「もう節が言っているか」。**読めなければ空**（印は出さない）。

    ## なぜ要るか（2026-08-17 23:5x に、**自分が誤読してから**足した）

    ここは長らく**候補を全部並べる**だけで、**どれが既出かを1文字も出していませんでした。**
    ところが `novel_counts()` は同じ候補を既出／新しいに分けており、
    **`status.py` はその「新しい M件」のほうで (B) の順番を決めています。**

    **一覧と、数えた数が、別のものを見せていました。**

    23:5x の回は `--calc kokuho` の上から6件を読み、`config/topics.yaml` に
    対応するテーマがあることを確かめて **「新しいと数えた6件が6件とも既出だ」**と
    書きました。**計器はその6件を「新しい」とは一度も言っていません**
    （追跡すると `is_covered` は `True` を返していた）。
    **突き合わせずに、計器のせいにする向きへ倒れています。**

    **人はこの一覧を見て節を選びます。**だから印を出すほうを直します。

    ## **印が1つも出ない回がありました**（2026-08-18。**入れた次の回に見つけた**）

    ここは `import_module("topic_forge")` だけでした。`topic_forge` は
    **`scripts/` の中**にあるので、`sys.path` にそこが入っている呼び方
    （`scripts/status.py` は自分で入れます）でしか読めません。

        python -m src.section_sweep --calc kokuho   → ModuleNotFoundError → **{} → 印ゼロ**

    **この道具の一覧は、人が読むためのものです。** つまり
    **人が読む唯一の経路でだけ、印が出ていませんでした**（`status.py` の
    「新しい M件」は同じ判定で正しく出ているので、**数字と一覧がまた別のものを
    見せている** —— 直したはずの形の、そのままの再発です）。
    **`except` が黙って握りつぶすので、緑のまま気づけません。**
    だから `scripts/` を自分で通し、**読めなかったことは `report_lines` が言います。**
    """
    try:
        import importlib

        scripts = Path(__file__).resolve().parent.parent / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        sections: dict[str, dict[str, str]] = {}
        forge = importlib.import_module("topic_forge")
        sections, _free, _known = forge.survey()
    except Exception:
        return {}
    out: dict[int, bool] = {}
    for hit in hits:
        try:
            out[id(hit)] = is_covered(hit, sections.get(hit.get("表", "?")))
        except Exception:
            pass
    _UNDECIDED.clear()
    for hit in hits:
        try:
            if undecided(hit, sections.get(hit.get("表", "?"))):
                _UNDECIDED.add(id(hit))
        except Exception:
            pass
    return out


def report_lines(hits: list[dict], *, top: int = 40) -> list[str]:
    """族の順番の値で並べて出す。**浅い順でも、出た順でもない。**"""
    try:
        from src import family_perf
        order = family_perf.combined_map()
    except Exception:
        order = {}
    hits = dedupe(hits)
    covered = _covered_map(hits)
    by_calc: dict[str, list[dict]] = {}
    for h in hits:
        by_calc.setdefault(h["表"], []).append(h)
    ranked = sorted(by_calc.items(),
                    key=lambda kv: (-order.get(kv[0], 0.0), -len(kv[1]), kv[0]))
    n_new = sum(1 for h in hits if covered.get(id(h)) is False) if covered else None
    n_und = sum(1 for h in hits if id(h) in _UNDECIDED) if covered else None
    head = f"=== 機械が拾った節の候補 {len(hits)}件 / 表 {len(by_calc)}本 ==="
    if n_new is not None:
        head += f"（うち **まだ節が言っていない {n_new}件**）"
    lines = [head,
             "  **候補です。節ではありません。**意味と正しさは人が決めること"
             "（数字の出どころにしない）。"]
    if UNCALLABLE:
        # **消えた側を出す**（2026-08-19 07:3x に足した）。この一覧は長らく
        # 「拾えた件数」しか言わず、**呼べずに丸ごと落ちた関数は無音**でした。
        # そのせいで同じ穴を3回踏んでいます（部分集合・`_sweepable_params`・
        # `_enum_axis`）。**件数が出ていれば、3回とも最初に見えます。**
        by_arg: dict[str, int] = {}
        for _c, _f, why in UNCALLABLE:
            by_arg[why] = by_arg.get(why, 0) + 1
        worst = ", ".join(f"{a}({n})" for a, n
                          in sorted(by_arg.items(), key=lambda kv: -kv[1])[:6])
        lines.append(f"  [!] **呼べなかった関数 {len(UNCALLABLE)}件**"
                     f"（この一覧には最初から入っていません）。"
                     f"**埋められなかった引数**: {worst}"
                     f"  → **意味のある量なら `calc_axes.SEMANTIC_AXES`**"
                     f"（組にも効く）、**格子のつまみなら `calc_axes.FILL_ONLY`**"
                     f"（埋めるだけ・組は増えない）、"
                     f"**軸の代表値では桁が合わないなら `calc_axes.PARAM_FILL`**")
    if PARTIAL_ENUM:
        # **一部だけ振ったことを黙らせないこと**（2026-08-21）。
        # 落ちた要素は「その関数がそこで数字を返さない」＝制度の側に無い、
        # という意味です。**見えないまま節を書くと「全区分のうち」と書きます。**
        worst_p = ", ".join(
            f"{c}.{f}({a}) {g}/{n}"
            for c, f, a, _cn, g, n
            in sorted(PARTIAL_ENUM, key=lambda r: (r[4] / r[5], -r[5]))[:5])
        lines.append(f"  [!] **一部の要素だけで振った場合分け {len(PARTIAL_ENUM)}件**"
                     f"（落ちた要素は、その関数が数字を返さない値です）: {worst_p}"
                     f"  → **節に「全区分のうち」と書かないこと。**"
                     f"振った値は各行の `x の幅` に出ています")
    if covered:
        lines.append("  **[既]** は、いまの節がもう言っているもの"
                     "（`status.py` の「新しい M件」はこれを除いた数です）。"
                     "**印の無いほうから選ぶこと。**")
        # **「新しい」の中身を割ること**（2026-08-24。`undecided()` の註）。
        # ここは長らく「新しい N件」だけを出していました。その N には
        # **「印字されていないと分かった」ものと「照合できなかった」ものが
        # 混ざっています。** 後者は結果の値が 1000未満の裸の数だけ持つ候補で、
        # **本文に書いてあっても必ず「新しい」に落ちます。**
        # `src/supply.py` はこの N を在庫に数えるので、**割らないと
        # 「あるかどうか分からないもの」を在庫に積んだままになります。**
        if n_und:
            pct = 100.0 * n_und / n_new if n_new else 0.0
            lines.append(f"  [!] 「新しい {n_new}件」のうち **{n_und}件（{pct:.0f}%）は"
                         f"判定できていません** —— 印字されていないと分かったのではなく、"
                         f"**照合できる点が無い**（結果が1000未満の裸の数だけ）。"
                         f"**在庫として数える前に、ここを引くか、引かない理由を書くこと**"
                         f"（`src/supply.py` の `SWEEP_YIELD`）。"
                         f"**[未]** の印が付いています")
        lines.append("  **[片効き]・[不変] は一覧の最後に回しています**"
                     "（`SHAPE_LAST`。実測 32枠中14枠を占めて、そこから書けた節は0件）。")
    else:
        # **黙って印を消さないこと**（2026-08-18）。印が無い一覧は
        # 「全部が新しい」に見えます。**読めなかったと言うほうが安全です。**
        lines.append("  [!] **既出の印は出せません**（節を読めませんでした）。"
                     "**この一覧には既出が混ざっています。**"
                     "「新しい M件」は `python scripts/status.py` のほうで見ること。")
    # **1つの表に絞ったときは、その表を全部出します。**
    # ここは長らく `group[:6]` の決め打ちで、`--calc <表>` でも6件で切れたまま
    # 「`--calc <表>` で全文」と案内していました（**行き先が自分自身**）。
    per_group = top if len(ranked) == 1 else 6
    shown = 0
    for name, group in ranked:
        if shown >= top:
            lines.append(f"  …ほか {len(hits) - shown}件（`--calc <表>` で全文）")
            break
        n_new_here = (sum(1 for h in group if covered.get(id(h)) is False)
                      if covered else None)
        tail = f"・**新しい {n_new_here}件**" if n_new_here is not None else ""
        lines.append(f"  --- {name}（{len(group)}件{tail}・族の順番の値 "
                     f"{order.get(name, 0.0):.1f}）---")
        # **印の無いほうを先に出すこと**（2026-08-18）。表ごとに6件で切るので、
        # 並べ替えないと**「新しい」が `…ほか N件` の中に隠れます** ——
        # すぐ上の行で「印の無いほうから選べ」と言いながら、選べる所に
        # 出していませんでした（実測: 新しい8件のうち4件が隠れていた）。
        # **自明な形を後ろへ回すこと**（2026-08-24。`SHAPE_LAST` の註）。
        # 表ごとに6件で切るので、`片効き`・`不変` が先頭に混ざるぶんだけ
        # 書ける候補が `…ほか N件` に沈みます（実測 14/32 ＝ 44%）。
        # **既出かどうかが先**（既出は何をしても書けない）、その中で自明を後ろへ。
        # **`[並 N点]` も後ろへ回すこと**（2026-08-26。`SHAPE_LAST` と同じ理由）。
        # あの印が付いた候補は、道具自身が
        # 「**細かく刻み直すまで、この x を名指しする節は書けません**」と
        # 印字しています ＝ **その回では書けません。**
        # それが `逆転` の 12件中7件（58%）に付いていて、
        # **書ける候補を `…ほか N件` に沈めていました。**
        # `数え上げ` の同点は「それが全部」なので**書けます** —— 沈めません。
        if covered:
            group = sorted(group, key=lambda h: (covered.get(id(h)) is not False,
                                                 h.get("形") in SHAPE_LAST,
                                                 unnameable(h)))
        else:
            group = sorted(group, key=lambda h: (h.get("形") in SHAPE_LAST,
                                                 unnameable(h)))
        for hit in group[:per_group]:
            mark = ("[既]" if covered.get(id(hit))
                    else ("[未]" if id(hit) in _UNDECIDED else "   "))
            lines.append(f"{mark}{line_of(hit)}" if covered else line_of(hit))
            shown += 1
        if len(group) > per_group:
            lines.append(f"    …ほか {len(group) - per_group}件")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--calc", help="1本だけ掃引する（既定は全部）")
    ap.add_argument("--shape", choices=SHAPES, help="形で絞る")
    ap.add_argument("--top", type=int, default=40, help="出す行数（既定 40）")
    args = ap.parse_args()

    hits = sweep_all([args.calc] if args.calc else None)
    if args.shape:
        hits = [h for h in hits if h["形"] == args.shape]
    for line in report_lines(hits, top=args.top if not args.calc else 10_000):
        print(line)


if __name__ == "__main__":
    main()
