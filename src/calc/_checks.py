"""`check_tables()` が毎回書いている形を、名前のついた検査にまとめる。

**なぜこれを作ったか（2026-08-16。6回持ち越された宿題）**

`src/calc` を1本書くのに20分かかっていて、その大半が `check_tables()` でした
（`docs/JOURNAL.md` 2026-08-15 の §6 (a2) 見直し3）。在庫の律速は calc の本数なので
（`docs/MEANS.md` M14）、**ここが遅いと1日8本の段に乗れません。**

12本を並べて読むと、書いているものは毎回ほぼ同じ4つでした。

    1. 速算表が昇順で、境目で税額が飛ばないこと     ← 5本が別々に手で書いていた
    2. 法令が名指ししている値と一致すること
    3. 単調性（X が増えれば Y も増える／減る）
    4. 範囲（率が 0〜1 のあいだ・大小関係・重複の無いこと）

**値そのものは、ここには置きません。** 制度の値を機械に発明させないのが
`CLAUDE.md` の歯止めなので、**この道具が持つのは「形」だけ**で、
何と一致すべきかは呼ぶ側が条文を見て書きます。

---

## 5つめを足しました —— **ラベルと値の対応**

`taishoku.py` の最初の表は、5年とびの行に「**1年あたり**の伸び」という見出しを付けて、
**前の行との差そのもの**を出していました（200万円/年に見える）。
`check_tables()` は素通りしています —— **計算は合っていて、嘘をついていたのは見出し**でした。

これは 2026-08-15 に4回続いた「人が見れば一目で分かる欠陥を、機械検査が素通りさせた」と
同じ種類です。**機械が見ているのは値で、見出しと値の対応は誰も見ていませんでした。**

`per_unit_steps()` は、**見出しが「1年あたり」と言っているなら、実際に年で割ります。**
割るのを忘れる余地が無くなるので、同じ間違いは書けません。
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Sequence


class TableError(ValueError):
    """制度の値か、計算の向きが壊れている。**壊れた数字で台本を書かせない。**"""


# ---------------------------------------------------------------- 法令の値

def statutory(actual: float, expected: float, name: str, *,
              source: str = "", tol: float = 1e-12) -> None:
    """法令が名指ししている値と一致すること。

    `source` には条文か公表資料の名前を書くこと。**外れたときに、
    どちらを直せばよいかが分からないと、次に来た側が値のほうを合わせにいきます。**
    """
    if abs(actual - expected) > tol:
        where = f"（{source}）" if source else ""
        raise TableError(f"{name} が {actual}。法定の値は {expected}{where}")


def ratio(value: float, name: str) -> None:
    """率が 0 と 1 のあいだにあること。桁の取り違え（5% を 5 と書く）を弾く。"""
    if not 0 < value < 1:
        raise TableError(f"{name} が {value}。率は 0 と 1 のあいだのはず（桁の取り違え）")


def digits(value: float, low: float, high: float, name: str) -> None:
    """万円と円の取り違えを弾く。**幅は呼ぶ側が制度から決めること。**"""
    if not low <= value <= high:
        raise TableError(f"{name} が {value:,}。{low:,}〜{high:,} の外（桁の取り違え）")


# ---------------------------------------------------------------- 並びと向き

def ascending(values: Sequence[float], what: str, *, strict: bool = False) -> None:
    """昇順に並んでいること。"""
    ok = all(a < b for a, b in zip(values, values[1:])) if strict else \
        list(values) == sorted(values)
    if not ok:
        raise TableError(f"{what} が昇順に並んでいない: {list(values)}")


def greater(a: float, b: float, what: str) -> None:
    """a が b より大きいこと。`what` は「大きいほうが先」の語順で書くこと。"""
    if not a > b:
        raise TableError(f"{what}（{a:,} ≦ {b:,}）")


def increases_with(fn: Callable[[Any], float], xs: Iterable[Any], what: str) -> None:
    """x が増えれば fn(x) も増えること（同値は許さない）。"""
    xs = list(xs)
    ys = [fn(x) for x in xs]
    for (xa, ya), (xb, yb) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if not yb > ya:
            raise TableError(f"{what}: {xa} → {xb} で {ya:,} → {yb:,} と増えていない")


def never_decreases(fn: Callable[[Any], float], xs: Iterable[Any], what: str) -> None:
    """x が増えて fn(x) が減らないこと（頭打ちのある式はこちら）。"""
    xs = list(xs)
    ys = [fn(x) for x in xs]
    for (xa, ya), (xb, yb) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if yb < ya:
            raise TableError(f"{what}: {xa} → {xb} で {ya:,} → {yb:,} と減っている")


def decreases_with(fn: Callable[[Any], float], xs: Iterable[Any], what: str) -> None:
    """x が増えれば fn(x) は減ること。"""
    xs = list(xs)
    ys = [fn(x) for x in xs]
    for (xa, ya), (xb, yb) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if not yb < ya:
            raise TableError(f"{what}: {xa} → {xb} で {ya:,} → {yb:,} と減っていない")


def unique_by(rows: Iterable[Any], key: Callable[[Any], Any], what: str) -> None:
    """同じものが2行入っていないこと。表の書き写しで実際に起きる。"""
    seen: set[Any] = set()
    for row in rows:
        k = key(row)
        if k in seen:
            raise TableError(f"{what}: {k} が重複している")
        seen.add(k)


# ---------------------------------------------------------------- 速算表

def bracket_table(rows: Sequence[tuple[Any, float, float]],
                  tax_of: Callable[[float], float], *,
                  name: str = "速算表", tol: float = 1.0,
                  open_top: bool = True) -> None:
    """速算表 `(区分の上限, 税率, 控除額)` を、形と連続性で確かめる。

    **控除額は、区分の境目で税額を連続させるために置かれています。**
    だから境目の前後で税額が飛んだら、飛んだぶんがそのまま写し間違いの量です。
    列ずれ・桁落ちは目で読み直しても見つからないので、ここで止めます。

    `open_top` は「最上段に上限が無い」こと。上限を `None` で書いても、
    `10**12` のような番人の値で書いてもよい（`jutaku.py` は後者）。
    **番人でも、それが最大であることは確かめます。**
    """
    if len(rows) < 2:
        raise TableError(f"{name} の段が {len(rows)} 段しかない")

    caps = [c for c, _, _ in rows]
    rates = [r for _, r, _ in rows]
    subs = [s for _, _, s in rows]

    ascending(rates, f"{name} の税率")
    ascending(subs, f"{name} の控除額")
    for r in rates:
        ratio(r, f"{name} の税率")

    top = caps[-1]
    if open_top:
        if top is not None and top != max(c for c in caps if c is not None):
            raise TableError(f"{name} の最上段の上限 {top:,} が最大でない")
    finite = [c for c in caps[:-1] if c is not None]
    if len(finite) != len(caps) - 1:
        raise TableError(f"{name} の途中の段に上限の無い行がある")
    ascending(finite, f"{name} の区分", strict=True)

    # 境目で税額が飛ばないこと。**ここが控除額の存在理由そのものです。**
    for cap in finite:
        below, above = tax_of(cap), tax_of(cap + 1)
        if not below <= above <= below + tol:
            raise TableError(
                f"{name} の境目 {cap:,} で税額が飛んでいる: "
                f"{below:,} → {above:,}（控除額の写し間違いを疑うこと）")

    # 表の全体で、課税所得が増えれば税額も増えること
    probe = [c for c in finite]
    probe += [c + 1 for c in finite] + [0, finite[-1] * 2]
    never_decreases(tax_of, sorted(set(probe)), f"{name} の税額")


# ---------------------------------------------------------------- 丸め

def rounding(got: float, want: float, what: str) -> None:
    """丸めの順番が効いていること。**順番を入れ替えても近い数字が出るので、
    値そのものを固定するしかありません。**"""
    if got != want:
        raise TableError(f"{what}: {got:,} になった。{want:,} のはず（丸めの順番）")


# ---------------------------------------------------------- ラベルと値の対応

_PER_UNIT = re.compile(r"1\s*([^\sあ]{1,3}?)\s*あたり")


def declared_unit(label: str) -> str | None:
    """見出しが「1〇〇あたり」と言っているなら、その〇〇を返す。"""
    m = _PER_UNIT.search(label)
    return m.group(1) if m else None


def per_unit_steps(rows: Sequence[dict], x_key: str, v_key: str, *,
                   label: str, x_unit: str) -> list[float | None]:
    """隣り合う行の差を、**見出しが宣言した単位で**返す。

    `taishoku.py` の表は5年とびの行に「1年あたりの伸び」と付けて、
    **前の行との差そのもの**を出していました。値は合っていて、嘘は見出しの側です。
    `check_tables()` は値しか見ないので素通りしました。

    ここでは見出しの単位と x 軸の単位を突き合わせ、**合っていたら実際に割ります。**
    割り忘れる余地が無いので、同じ間違いは書けません。

    先頭の行には差が無いので `None` を返します（表では「—」を出すこと）。
    """
    unit = declared_unit(label)
    if unit is None:
        raise TableError(
            f"見出し「{label}」が「1{x_unit}あたり」の形になっていない。"
            f"1行ぶんの差を出すなら、見出しにも単位を書くこと")
    if unit != x_unit:
        raise TableError(
            f"見出しは「1{unit}あたり」と言っているのに、"
            f"表の刻みは {x_unit} で並んでいる（{x_key}）")

    out: list[float | None] = [None]
    for prev, row in zip(rows, rows[1:]):
        span = row[x_key] - prev[x_key]
        if span <= 0:
            raise TableError(f"{x_key} が {prev[x_key]} → {row[x_key]} と増えていない")
        out.append((row[v_key] - prev[v_key]) / span)
    return out
