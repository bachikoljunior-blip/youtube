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

---

## 6つめを足しました —— **前提そのものに値が入っているか**（2026-08-16。8回持ち越し）

`src/verify.py` の `_check_assumption_value_shown` は、**画面に前提の値が出ているか**を
見ます。2026-08-16 01:3x に入れて、独立評価が2本続けて指した欠けを塞ぎました。

**塞がっていませんでした。** その回の申し送りが、同じ文をそのまま8回運んでいます ——

> **`ASSUMPTIONS` そのものに値が無い calc がある**（`nenkin` の手取り率）。
> 画面に出せと言われても、**calc 側が値を持っていない**ものは書きようがありません。

実物（`src/calc/nenkin.py`）はこうでした。

    "手取り率は制度の値ではなく、この計算での仮定です。額が上がるほど下がるものとして置いています"

**率が何%なのかが、どこにも書いてありません。** モジュールの中には
`NET_RATE_POINTS` という表があって、実際にその値で計算しています。
つまり**値は在るのに、前提の文が持っていない。** 台本の書き手に渡るのは
`ASSUMPTIONS` の文だけなので（`src/script_writer.py`）、書き手にできることは
2つしかありません —— **黙って落とす**か、**自分で数字を作る**か。
前者は `verify` が落として1本まるごと捨て、後者は
**裏の取れない数字が動画に入る**（`CLAUDE.md` がいちばん強く禁じている形）。

**これは「画面に出す側」の欠陥ではありませんでした。渡す側が空でした。**
片方だけ直したので、8回運ばれても閉じなかったわけです。

`assumption_values()` は `verify` と**同じ語彙・同じ近さの規則**を、
一段手前（calc）に当てます。ここを通った前提は、画面に出せる形になっています。
**語彙を1か所に置いてあるのは、片方だけ足すと差が開くから**です
（`verify` は `_checks` から輸入します。定義を2つ持たないこと）。
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
    値そのものを固定するしかありません。**

    **円の額に使うこと。**率や比には `close()` のほうを使います（下）。
    """
    if got != want:
        raise TableError(f"{what}: {got:,} になった。{want:,} のはず（丸めの順番）"
                         + _float_hint(got, want))


def _float_hint(got: float, want: float) -> str:
    """**浮動小数の最後の1桁で落ちたなら、そう言うこと。**

    2026-08-17 に足しました。`koureikoyou.py` を書いた回が
    `0.6535714285714285 になった。0.6535714285714286 のはず` を3回読み、
    **計算のほうを疑って約6分を溶かしています。** 落としていたのは道具でした。
    **メッセージが「丸めの順番」としか言わないので、そう読むしかありません。**
    """
    if got == want or not isinstance(got, float) or not isinstance(want, float):
        return ""
    scale = max(abs(got), abs(want))
    if scale == 0 or abs(got - want) > scale * 1e-9:
        return ""
    return ("\n    **差は浮動小数の最後の1桁だけです。計算は合っています。**"
            "\n    率や比を突き合わせているなら、`rounding` ではなく "
            "`_checks.close(got, want, what)` を使うこと。")


def close(got: float, want: float, what: str, *, tol: float = 1e-9) -> None:
    """**率・比・係数が、独立に出したもう1つの値と一致すること。**

    `rounding()` は `!=` で見るので、円の額には効きますが
    **率には使えません** —— `0.15 * 0.61 / 0.14` と `183/280` は
    数学的に同じでも、浮動小数の最後の1桁が違います。

    2026-08-17 に足しました。`koureikoyou.py` を書いた回が、
    **1本の中で3回これに当たっています**（0.6535714285714285 対 …86 など）。
    どれも計算は合っていて、落としていたのは比較の道具のほうでした。
    **`rounding` を緩めると円の額の検査まで緩む**ので、別の名前にしてあります。

    使いどころは「同じ数を2通りで出して突き合わせる」ときです。
    公表されている係数と、率と境目から導いた係数が一致するか —— のような形。
    """
    if abs(got - want) > tol:
        raise TableError(f"{what}: {got:,} になった。{want:,} のはず（差 {got - want:.3g}）")


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


# ------------------------------------------- 前提そのものに値が入っているか

#: 「量」を指す語の**語尾**。前に付く語は問わない（`手取り率` `支給率` `保険料率`）。
#: 語そのものの一覧にしないのは、次に出てくる量を数え上げられないから。
#: **語尾なら、まだ書かれていない calc の量にも当たります。**
#: **`src/verify.py` はこれを輸入します。定義を2つ持たないこと**
#: （片方だけ足すと、calc で通ったものが画面で落ちる／その逆が起きます）。
QUANTITY_TAILS = ("率", "割合", "単価", "日数", "月数", "年数", "上限", "下限", "係数")

#: 「これは前提だ」と名乗っている印。ここに当たった**文**だけを見る。
#: 全部に当てると、量の名前を出しただけの行まで拾ってしまう
#: （実測。文単位にする前は 22件のうち 16件が「入れていません」の類でした）。
ASSUMPTION_MARKERS = ("仮定", "前提", "として置", "としています", "とみなし", "と置い")

#: 量の名前と数字が、どれだけ離れていたら「その量の値ではない」とみなすか（文字数）。
#: `手取り率は85パーセント` は 4字、`手取り率　85%` は 1字。
#: 離すほど通りやすくなるので、**同じ行の中に収まる程度**に置く。
VALUE_NEAR_CHARS = 14

#: 量の名前の**手前で切る**字。助詞なので、ここより前は別の語。
#: 2026-08-16 の初回生成で `前提は所得税率` と拾い、直し方の例が
#: 『前提は所得税率 ＝ 〇〇』という日本語にならない形で出た。
#: **落とす判定は当たっていたが、渡す直し方が壊れていた。**
_PARTICLES = "はがをにでもとやのへか、。 　"

_QUANTITY_RE = re.compile(
    r"[一-龥ぁ-んァ-ヶー]{1,8}?(?:" + "|".join(QUANTITY_TAILS) + ")")


def trim_particles(word: str) -> str:
    """`前提は所得税率` → `所得税率`。最後の助詞より後ろだけを残す。"""
    cut = max((word.rfind(p) for p in _PARTICLES), default=-1)
    tail = word[cut + 1:] if cut >= 0 else word
    return tail if tail.endswith(QUANTITY_TAILS) else word


def named_quantities(text: str) -> list[str]:
    """その文が名前を出している「量」を、出てきた順に返す。"""
    out: list[str] = []
    for m in _QUANTITY_RE.finditer(text):
        word = trim_particles(m.group(0))
        if word not in out:
            out.append(word)
    return out


def value_near(text: str, word: str) -> bool:
    """`word` の近く（前後 `VALUE_NEAR_CHARS` 字）に数字があるか。

    **`verify` が画面に対してやっている判定と同じ規則**です。
    ここを通った前提は、そのまま画面に出せば向こうも通ります。
    """
    for m in re.finditer(re.escape(word), text):
        near = text[max(0, m.start() - VALUE_NEAR_CHARS):m.end() + VALUE_NEAR_CHARS]
        if re.search(r"[0-9０-９]", near):
            return True
    return False


def assumption_values(assumptions: Iterable[str], *, name: str = "") -> None:
    """**「これは仮定です」と名乗った量に、値が書いてあること。**

    **名乗りと量を拾うのは文単位**（`。` で割る）、**値が在るかを見るのは行ぜんたい**です。
    非対称なのには理由が2つあります。

    - 文単位で拾うのは、前提を名乗った文と、量の名前が出てくる文が別のときに
      拾ってしまうから（実測: `yukyu` の「古いほうから使う前提です。…消える日数は…」）
    - 行ぜんたいで見るのは、**画面へ渡る単位が行だから**です。
      1行が1つの箇条書きとして書き手に届くので、
      「〇〇は仮定です。値は△△です」と2文に分けた書き方を落とす理由がありません

    **`verify` の近さの規則（前後14字）は、ここでは使いません。** 向こうが近さを
    見るのは、画面が別々のコマの文字を全部つないだものだからです。
    こちらの1行は**前提そのもの**なので、行の中の数字はその前提の値です。
    実測でも、緩めたことで落ちる件数は変わりませんでした（本物の4件は
    **数字が1つも無い行**で、近さの話ではなかった）。
    `nenkin` を直した文が「近すぎない」だけで落ちたのが、緩めた理由です。

    **射程の外**（承知のうえ）:

    - 量の名前を出さずに置かれた仮定（`賞与は無いものとしています`）。
      名前が無いと、画面に何を出せばよいかも決まりません
    - 値が表にしか無く、前提の文が表を指しているだけの形。
      **それでも文に代表値を1つ書くこと** —— 台本の書き手に渡るのは
      `ASSUMPTIONS` の文だけで、表は渡りません（`src/script_writer.py`）
    """
    where = f"src/calc/{name}.py の " if name else ""
    for line in assumptions:
        line = str(line)
        for sentence in line.split("。"):
            if not any(m in sentence for m in ASSUMPTION_MARKERS):
                continue
            for word in named_quantities(sentence):
                if re.search(r"[0-9０-９]", line):
                    continue
                raise TableError(
                    f"{where}ASSUMPTIONS が『{word}』を仮定だと名乗っているのに、"
                    f"**その値が書いてありません**。\n"
                    f"    → {sentence}\n"
                    "  台本の書き手に渡るのは ASSUMPTIONS の文だけです（表は渡りません）。"
                    "値が無いと、書き手は**黙って落とす**か**自分で数字を作る**しかなく、"
                    "前者は verify が1本まるごと捨て、後者は裏の取れない数字が動画に入ります。\n"
                    f"  この計算で実際に使っている値を、文の中に書くこと"
                    f"（例: 『{word}は〇〇として置いています』）。"
                )
