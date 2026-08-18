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
import importlib
import inspect
import io
import math
import pkgutil
import re
import sys
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable

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

#: `詳しく` のうち、**x 軸の値**を持つ欄。行を歩く掃引では、ここだけを
#: 行番号から見出しに直します。**形を足したら、ここに足すこと。**
#:
#: **一度「名前に `x` を含む欄」で拾おうとして外しました**（2026-08-18）。
#: `帯` の欄は `帯の入口` / `帯の出口` で、**`x` の字が入っていません** ——
#: 規約で拾うつもりが、既にある形1つを取りこぼしていました。
#: だから並びは1つに集約して、**読む側を2か所とも、ここから引きます**
#: （`_hit_points` と、`sweep_rows` の見出し直し）。
X_KEYS = ("止まる x", "x", "x の手前", "x の先", "帯の入口", "帯の出口", "並ぶ x",
          "いちばん低い", "いちばん高い")

#: そのうち「**この候補を名指ししている**点」。同点の一覧は、名指しの点ではない
#: （既出の判定を厳しくすると意味が変わるので、`_hit_points` からは外す）。
NAMING_X_KEYS = tuple(k for k in X_KEYS if k != "並ぶ x")

#: `詳しく` のうち、**y（結果の値）や註**を持つ欄。x でも y でもない欄が出たら、
#: `tests/test_section_sweep.py` が止めます —— **形を足した回に、その欄が
#: x なのか y なのかを宣言させるため**（宣言しないと、行番号のまま印字されます）。
Y_KEYS = ("止まった値", "値", "跳ぶ幅", "動かない値", "帯の中", "帯の外",
          "端では", "差", "中央の段差", "並ぶ点", "数え上げ", "動く", "動かない",
          "どこ", "倍率", "並び")


def _grid(default: float) -> list[float]:
    """既定値のまわりに点を置く。**桁で置き方を変える。**

    - 率（0 < x < 1）      → 0.1 刻み
    - 小さい整数（〜200）   → 既定の半分〜2倍を整数で
    - 金額（それ以上）      → 既定の 0.5〜4倍を対数で
    """
    if isinstance(default, float) and 0 < default < 1:
        return [round(0.1 * i, 2) for i in range(1, GRID + 1)]
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
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and _NUMERIC_TEXT.match(v):
        body = re.sub(r"[,\s%円年倍人回]|か月|日", "", v)
        try:
            return float(body)
        except ValueError:
            return None
    return None


def _scalars(value: Any) -> dict[str, float]:
    """返り値から、掃引で比べられる数字だけ取り出す。"""
    if isinstance(value, bool):
        return {}
    if isinstance(value, (int, float)):
        return {"": float(value)}
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            n = _as_number(v)
            if n is not None:
                out[str(k)] = n
        return out
    return {}


def _sweepable_params(fn: Callable,
                      skip: Iterable[str] = ()) -> list[tuple[str, float]]:
    """既定値が数値で、他の引数を触らずに動かせるものだけ返す。

    `skip` は**こちらが値を埋める引数**（数え上げの軸。`_enum_params`）。
    既定値が無くても呼べるので、**そこで降りないこと** —— 降りていたために
    `koteishisan.unit_tax` のような関数が丸ごと対象外でした。
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    skip = set(skip)
    out = []
    for name, p in sig.parameters.items():
        if name in skip:
            continue
        if p.default is inspect.Parameter.empty:
            return []          # 既定値の無い引数があると、そのまま呼べない
        if isinstance(p.default, bool) or not isinstance(p.default, (int, float)):
            continue
        out.append((name, float(p.default)))
    return out


#: 数え上げの軸として振る候補の、要素数の上限。**これより多い並びは軸ではなく
#: 表そのもの**なので、`sweep_rows` の側で歩きます（1つの表に2度当てない）。
ENUM_MAX = 12


def _enum_containers(fn: Callable) -> list[tuple[str, list[str]]]:
    """`fn` と同じモジュールの中にある、**文字列を並べた入れ物**を返す。

    `list` / `tuple` の要素、または `dict` の鍵です。`fn.__module__` から引くので、
    **手で語彙を並べません**（次に表を足した回が書き忘れる形を作らないため）。
    """
    mod = sys.modules.get(getattr(fn, "__module__", ""))
    if mod is None:
        return []
    out: list[tuple[str, list[str]]] = []
    for cname, v in vars(mod).items():
        if cname.startswith("_"):
            continue
        if isinstance(v, (list, tuple)):
            items = _names_of(list(v))
        elif isinstance(v, dict):
            items = _names_of(list(v))
        else:
            continue
        if items is None or not (2 <= len(items) <= ENUM_MAX):
            continue
        out.append((cname, items))
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
    2. 入れ物の要素を全部入れてみて、**全部が例外なく数字を返す**ものだけ通す

    **2 が本体です。** 関係のない入れ物（たとえば見出しの並び）は、
    途中の要素で必ず落ちるか、数字を返しません。
    """
    conts = _enum_containers(fn)
    if not conts:
        return []
    if isinstance(default, str):
        conts.sort(key=lambda kv: default not in kv[1])
    passed: list[list[str]] = []
    for _cname, items in conts:
        ok = True
        for e in items:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    value = fn(**{pname: e})
            except Exception:
                ok = False
                break
            if not _scalars(value):
                ok = False
                break
        if ok:
            passed.append(items)
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
    passed.sort(key=len, reverse=True)
    return passed[0]


def _enum_params(fn: Callable) -> list[tuple[str, list[str]]]:
    """**数え上げの軸として振れる引数**を、`(名前, 並び)` で返す。

    対象は「既定値が文字列」と「既定値が無く、文字列を入れると通る」の2つ。
    **後者を入れているのが、この直しの本体です**（`_enum_axis` の docstring）。
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    out = []
    for name, p in sig.parameters.items():
        default = p.default
        if default is not inspect.Parameter.empty and not isinstance(default, str):
            continue
        items = _enum_axis(fn, name, default)
        if items:
            out.append((name, items))
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
            return "帯", {"帯の入口": xs[b0], "帯の出口": xs[b1],
                         "帯の中": inner, "帯の外": outer,
                         "差": inner - outer}

    # 頭打ち: 後ろの3分の1が動かない（前は動いている）
    tail = ys[-max(3, len(ys) // 3):]
    if (max(tail) - min(tail)) / scale <= FLAT_TOL and len(moving) >= 2:
        start = len(ys) - len(tail)
        return "頭打ち", {"止まる x": xs[start], "止まった値": ys[-1]}

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

    # **先に全部の引数を掃引します**（`table_constants` が横に並べて見るため）。
    swept: list[tuple[str, list[float], list[dict]]] = []
    for pname, default in params:
        xs, rows = [], []
        for x in _grid(default):
            try:
                value = fn(**base, **{pname: _cast(default, x)})
            except Exception:
                continue
            scal = _scalars(value)
            if not scal:
                break
            xs.append(x)
            rows.append(scal)
        if len(xs) < 4:
            continue
        swept.append((pname, xs, rows))

    consts = table_constants(swept)
    for pname, xs, rows in swept:
        keys = set(rows[0])
        for r in rows[1:]:
            keys &= set(r)
        for key in sorted(keys):
            ys = [r[key] for r in rows]
            hit = _classify(xs, ys)
            if hit:
                shape, detail = hit
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


def sweep_rows(fn: Callable, *, name: str = "") -> list[dict]:
    """**表そのものの中を歩く。**引数ではなく、行の並びを x にする。

    `season_grid()` や `ratio_to_monthly()` のように `list[dict]` を返す関数は、
    **その表の中に既に x 軸を持っています**（算定期間・労働日数・所得の帯）。
    引数を動かす掃引はここに入れないので、**表の8割が対象外**でした
    （2026-08-17 の1回目は 37本中5本しか出ませんでした）。

    行を歩けば、**崖・頭打ち・逆転が表の中で見えます** ——
    そしてこの回の3節のうち2節は、実際にそういう形でした。
    """
    try:
        rows = _rows(fn())
    except Exception:
        return []
    if not rows or len(rows) < 4:
        return []
    keys = set(_scalars(rows[0]))
    for r in rows[1:]:
        keys &= set(_scalars(r))
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
        found.append({"関数": name or getattr(fn, "__name__", "?"),
                      "動かした引数": "（表の行）", "見た値": key,
                      "形": shape, "詳しく": detail,
                      "x の幅": (0, len(rows) - 1)})
    return found


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
    """その比が、節の本文に書かれているか。"""
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
    elif hit["形"] == "崖":
        tail = (f"{hit['動かした引数']} が {_fmt(d['x の手前'])}→{_fmt(d['x の先'])} で "
                f"{_fmt(d['跳ぶ幅'])} 跳ぶ（ふだんの段差は {_fmt(d['中央の段差'])}）")
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
    return (f"  {hit['形']:<4} {hit['表']}.{hit['関数']}"
            f"（{hit['見た値']}）… {tail}")


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
    head = f"=== 機械が拾った節の候補 {len(hits)}件 / 表 {len(by_calc)}本 ==="
    if n_new is not None:
        head += f"（うち **まだ節が言っていない {n_new}件**）"
    lines = [head,
             "  **候補です。節ではありません。**意味と正しさは人が決めること"
             "（数字の出どころにしない）。"]
    if covered:
        lines.append("  **[既]** は、いまの節がもう言っているもの"
                     "（`status.py` の「新しい M件」はこれを除いた数です）。"
                     "**印の無いほうから選ぶこと。**")
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
        if covered:
            group = sorted(group, key=lambda h: covered.get(id(h)) is not False)
        for hit in group[:per_group]:
            mark = "[既]" if covered.get(id(hit)) else "   "
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
