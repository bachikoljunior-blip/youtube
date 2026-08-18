"""表**2本**を並走させて、単独の掃引では原理的に出ない形を拾う（M19 の2手目）。

## なぜ1手目ではここが重心なのか

1手目（`src/calc_axes.py`）は**入力の引数名を意味の軸へ寄せる**道具で、
母数（1,144組 / 1,378組）を作るところまでしかやりません。そして
**1,144 / 1,378 ＝ 83% です。8割が通るものは、ふるいではありません。**

さらに悪いことに、**この手段の唯一の実例が、その一覧に入っていません** ——
`gassan`（高額介護合算療養費・7節）の元になった2本は

    kogaku  {所得, 期間}
    kaigo   {率, 世帯, 帯}      ← **共有する軸はゼロ**

で、`gassan` が2本を繋いだのは入力ではなく**出力**です（同じ世帯が同じ1年に
払う「円」）。**入力の名前や軸で組を作るかぎり、既知の当たりは1件も入りません。**
（`tests/test_calc_axes.py` にその失敗が固定してあります。）

**だからこの道具は、出力の側で繋ぎます。**

## 繋ぎ方は2つ。**拾える形が違うので、混ぜないこと**

    (1) 出力の高さで繋ぐ   入力の軸は要らない。y（円など）の単位が同じで、
                           範囲が重なる並びどうし         → **崖の近さ**
    (2) 同じ x で並走      入力の意味の軸を共有する組だけ。x を順位で揃える
                           → **和の平坦** / **順序の逆転**

`gassan` の形は (1) です。**(2) しか実装しなければ、既知の当たりは出ません。**

## 拾う形は3つだけ（**単独の掃引では出ない形に限る**）

- **崖の近さ**: A のいちばん深い崖と、B のいちばん深い崖が、**同じ高さ（円）**で
  起きている。1% 以内なら「一致」、1〜5% なら「ニアミス（わざと外れている）」。
  *どちらも節になります* —— 一致は「2つの制度が同じ額で切り替わる」、
  ニアミスは「**ほとんど同じなのに、わずかにずれている**」
- **和の平坦**: A＋B が動かない区間（片方の増えが片方の減りで消える）
- **順序の逆転**: A＞B だった区間が、x のどこかで入れ替わる

## 割り引いて読むこと（**足す前に測ること**・`docs/trigger_main.md` §4）

- **候補です。意味と正しさは人が決めます。** 数字の出どころにしないこと
- **単位は推定を含みます。** 素の整数で桁が大きいものは「円」と見なしています。
  違う単位どうしを組にすると、崖の高さの一致は**偶然**になります
- **数え上げの引数（区分名・要介護度）は、いちばん最初の値に固定します。**
  振ると組の数が段数の積で膨らみ、母数が意味を失うためです
- **同じ組から2本以上の動画を出さないこと**（`docs/MEANS.md` M19）

    python -m src.pair_sweep                 # 全部
    python -m src.pair_sweep --calc kogaku   # その表を含む組だけ
    python -m src.pair_sweep --shape 崖の近さ
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import importlib
import inspect
import io
import itertools
from typing import Any, Callable

from src import calc_axes
from src.section_sweep import (GRID, _enum_containers, _grid, _scalars,
                               calc_modules)

#: 拾う形。**足したら、ここに足すこと**（`--shape` の選択肢もここを見ます）。
SHAPES = ("崖の近さ", "和の平坦", "順序の逆転")

#: 意味の軸 → **他の引数を埋めるときの代表値**。
#: **引数名ごとの表は作りません**（`calc_axes.SEMANTIC_AXES` が既に名前を
#: 軸へ寄せているので、そちらに1語足せば全部の表に効きます）。
#: 寄せられない引数を持つ関数は、**埋めずに降ります**（下の `_fill`）。
AXIS_FILL: dict[str, float] = {
    "所得": 3_000_000,
    "年齢": 65,
    "世帯": 2,
    "期間": 12,
    "率": 0.3,
    "面積": 100,
    "回数": 10_000,
    "帯": 44_400,
}

#: 欄の名前の**末尾** → 単位。**長いほうを先に見ます**（`倍率` は `率` ではない）。
#: 途中一致で引かないこと —— `1か月あたりの医療費` の「か月」は単位ではなく
#: 期間の言い方で、値は円です（`unit_of` の註）。
UNIT_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("倍率", "倍"), ("円", "円"), ("額", "円"), ("代", "円"), ("料", "円"),
    ("%", "%"), ("率", "%"), ("pt", "pt"), ("か月", "か月"), ("年", "年"),
    ("人", "人"), ("回", "回"), ("倍", "倍"),
)

#: 崖の高さが「一致した」と見なす相対差。
NEAR_CLIFF = 0.01
#: 「ニアミス（わざと外れている）」と見なす相対差の上限。
MISS_CLIFF = 0.05
#: 和が「平らだ」と見なす相対の振れ幅。
FLAT_SUM = 0.01
#: 片方だけでも、これだけは動いていること（動かない並びの和は自明に平ら）。
MOVES = 0.05
#: 素の整数を「円」と見なす下限。**これ未満は単位を推定しません。**
YEN_FLOOR = 1_000


def _fill(fn: Callable, sweep: str) -> dict[str, Any] | None:
    """`sweep` 以外の引数を埋めた辞書。埋められない引数が1つでもあれば `None`。

    **`section_sweep._sweepable_params` を使えません**（2026-08-19）。
    あちらは「既定値の無い引数が1つでもあれば `return []`」で、
    `kogaku.limit(name, cost)` も `kaigo.pay(level, used_units, rate)` も
    **丸ごと対象外**になります。**この2本こそが、この手段の唯一の実例**なので、
    そこで降りると既知の当たりが構造的に出ません。
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    out: dict[str, Any] = {}
    pending: list[str] = []
    for name, p in sig.parameters.items():
        if name == sweep:
            continue
        if p.default is not inspect.Parameter.empty:
            out[name] = p.default
            continue
        axis = calc_axes.axis_of(name)
        if axis is not None and axis in AXIS_FILL:
            out[name] = AXIS_FILL[axis]
        else:
            pending.append(name)            # 文字列の場合分けとみて、下で探す
    for name in pending:
        items = _enum_with(fn, name, out, sweep)
        if not items:
            return None
        out[name] = items[0]                # 数え上げは先頭に固定（上の註）
    return out


def _enum_with(fn: Callable, pname: str, base: dict[str, Any],
               sweep: str) -> list[str]:
    """`base` を埋めた状態で `pname` に入る**文字列の並び**を返す。

    **`section_sweep._enum_axis` をそのまま使えません**（2026-08-19 に踏んだ）。
    あちらは候補を `fn(**{pname: e})` と**その引数だけで**呼んで試すので、
    **他にも必須の引数がある関数では必ず TypeError で落ちます**:

        kogaku.limit(name, cost)                  → limit(name='ウ') は落ちる
        kaigo.pay(level, used_units, rate, cap=…) → pay(level='要介護3') も落ちる

    その2本が、**この手段の唯一の実例（`gassan`）の元になった表**です。
    「文字列の引数」と「数値の必須引数」を**同時に**持つ関数は、
    `section_sweep` からも `pair_sweep` からも丸ごと見えていませんでした。

    選び方は `_enum_axis` と同じ（**全要素が例外なく数字を返す入れ物のうち、
    いちばん広いもの**）。違うのは、呼ぶときに `base` と、振る軸の代表値を
    一緒に渡すところだけです。
    """
    x = _sweep_axis(fn, sweep)
    if not x:
        return []
    passed: list[list[str]] = []
    for _cname, items in _enum_containers(fn):
        ok = True
        for e in items:
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    value = fn(**{pname: e, sweep: x[len(x) // 2]}, **base)
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
    passed.sort(key=len, reverse=True)
    return passed[0]


def _sweep_axis(fn: Callable, name: str) -> list[float] | None:
    """`name` を振る目盛り。数値として扱えなければ `None`。"""
    try:
        p = inspect.signature(fn).parameters[name]
    except (TypeError, ValueError, KeyError):
        return None
    if isinstance(p.default, bool):
        return None
    if isinstance(p.default, (int, float)):
        return _grid(float(p.default))
    axis = calc_axes.axis_of(name)
    if axis is None or axis not in AXIS_FILL:
        return None
    return _grid(AXIS_FILL[axis])


def unit_of(key: str, ys: list[float]) -> str | None:
    """並びの単位。推定できなければ `None`（＝組にしない）。

    見るのは **欄の名前の末尾** → 無ければ **値の桁**、の順。
    `_as_number` が単位を落としてしまうので、ここは名前の側で拾います。

    **末尾でだけ引くこと**（2026-08-19 に踏んだ）。名前のどこでも引くと、
    `kogaku` の円の欄がほぼ全部よその単位に化けます ——
    `1か月あたりの医療費` は「か月」、`1年の合計` は「年」、`多数回の額` は「回」。
    **単位ではなく期間の言い方**で、値はどれも円です。そのせいで
    `kogaku` の円の並びは `円?` の組に1本も入らず、
    **この手段の唯一の実例（kogaku × kaigo）が構造的に出ませんでした。**
    """
    for suffix, unit in UNIT_SUFFIXES:
        if key.endswith(suffix):
            return unit
    if not ys:
        return None
    if all(float(y).is_integer() for y in ys) and max(abs(y) for y in ys) >= YEN_FLOOR:
        return "円?"          # **推定**。`?` を落とさないこと
    return None


def series_of(calc: str) -> list[dict]:
    """1つの表から、`(x を振ったときの y の並び)` を全部作る。"""
    mod = importlib.import_module(f"src.calc.{calc}")
    out: list[dict] = []
    for fname, fn in vars(mod).items():
        if fname.startswith("_") or not callable(fn):
            continue
        if getattr(fn, "__module__", "") != mod.__name__:
            continue
        try:
            params = list(inspect.signature(fn).parameters)
        except (TypeError, ValueError):
            continue
        for pname in params:
            xs = _sweep_axis(fn, pname)
            if not xs:
                continue
            rest = _fill(fn, pname)
            if rest is None:
                continue
            cols: dict[str, list[float]] = collections.defaultdict(list)
            good: list[float] = []
            for x in xs:
                try:
                    value = fn(**{pname: x}, **rest)
                except Exception:
                    break
                scal = _scalars(value)
                if not scal:
                    break
                for k, v in scal.items():
                    cols[k].append(v)
                good.append(x)
            if len(good) < GRID // 2:
                continue
            for key, ys in cols.items():
                if len(ys) != len(good):
                    continue
                if _echoes(good, ys):
                    continue
                unit = unit_of(key, ys)
                if unit is None:
                    continue
                out.append({"calc": calc, "fn": fname, "x": pname,
                            "key": key, "unit": unit, "xs": good, "ys": ys,
                            "axis": calc_axes.axis_of(pname)})
    return out


def _echoes(xs: list[float], ys: list[float]) -> bool:
    """`y` が `x` の写しなら True（**組にしない**）。

    **これが無いと、一覧の上位が丸ごと偽物になります**（2026-08-19 に実測）。
    埋める代表値は軸ごとに1つなので、所得の軸を持つ関数はどれも**同じ目盛り**で
    振られます。返り値に入力をそのまま入れている欄（`split_months` の `医療費`、
    `compare` の `monthly_pay` …）は、**表がちがっても並びが1文字も違わない**。
    崖の高さは当然0.00%で一致し、「一致」の見立てが**18件中8件**そこから出ていました。
    偶然ではなく、こちらが同じ数を2回配っただけです。
    """
    if len(xs) != len(ys):
        return False
    return all(abs(x - y) <= max(abs(x), 1.0) * 1e-9 for x, y in zip(xs, ys))


def _cliff(ys: list[float]) -> tuple[float, float] | None:
    """いちばん深い段差の `(高さ, 相対の深さ)`。段差が無ければ `None`。

    **高さは段差の前後の平均**です（「どの額で切り替わるか」を言うため）。
    """
    best = None
    for a, b in zip(ys, ys[1:]):
        scale = max(abs(a), abs(b))
        if scale == 0:
            continue
        depth = abs(b - a) / scale
        if best is None or depth > best[1]:
            best = ((abs(a) + abs(b)) / 2, depth)
    if best is None or best[1] < MOVES:
        return None
    return best


def _span(ys: list[float]) -> float:
    lo, hi = min(ys), max(ys)
    scale = max(abs(hi), abs(lo)) or 1.0
    return (hi - lo) / scale


def pair_hits(a: dict, b: dict) -> list[dict]:
    """並び2本から拾えた形。"""
    hits: list[dict] = []
    if a["unit"] == b["unit"]:
        ca, cb = _cliff(a["ys"]), _cliff(b["ys"])
        if ca and cb:
            scale = max(ca[0], cb[0])
            if scale > 0:
                gap = abs(ca[0] - cb[0]) / scale
                if gap <= MISS_CLIFF:
                    hits.append({
                        "形": "崖の近さ",
                        "詳しく": {
                            "A の崖": round(ca[0], 2), "B の崖": round(cb[0], 2),
                            "ずれ": f"{gap * 100:.2f}%",
                            "見立て": "一致" if gap <= NEAR_CLIFF else "ニアミス",
                        }})
    # ---- ここから下は「同じ x で並走」できる組だけ（上の註 (2)）----
    if a["axis"] and a["axis"] == b["axis"] and a["unit"] == b["unit"]:
        n = min(len(a["ys"]), len(b["ys"]))
        ya, yb = a["ys"][:n], b["ys"][:n]
        if n >= GRID // 2 and (_span(ya) >= MOVES or _span(yb) >= MOVES):
            sums = [p + q for p, q in zip(ya, yb)]
            if _span(sums) <= FLAT_SUM and _span(ya) >= MOVES and _span(yb) >= MOVES:
                hits.append({"形": "和の平坦",
                             "詳しく": {"和": round(sums[0], 2),
                                        "振れ": f"{_span(sums) * 100:.2f}%"}})
            signs = {p > q for p, q in zip(ya, yb) if p != q}
            if len(signs) == 2:
                for i, (p, q) in enumerate(zip(ya, yb)):
                    if i and (ya[i - 1] > yb[i - 1]) != (p > q):
                        hits.append({"形": "順序の逆転",
                                     "詳しく": {"入れ替わる x": a["xs"][i],
                                                "A": round(p, 2), "B": round(q, 2)}})
                        break
    return hits


def sweep_pairs(calcs: list[str] | None = None) -> list[dict]:
    """表の全組を並走させて、拾えた形を返す。**1組につき1件まで**（M19）。"""
    names = sorted(calcs or calc_modules())
    series = {n: series_of(n) for n in names}
    out: list[dict] = []
    for a, b in itertools.combinations(names, 2):
        got: list[dict] = []
        for sa in series[a]:
            for sb in series[b]:
                for hit in pair_hits(sa, sb):
                    hit["組"] = f"{a} × {b}"
                    hit["A"] = f"{sa['fn']}({sa['x']}) → {sa['key'] or '値'}"
                    hit["B"] = f"{sb['fn']}({sb['x']}) → {sb['key'] or '値'}"
                    hit["単位"] = sa["unit"]
                    got.append(hit)
        if got:
            got.sort(key=lambda h: SHAPES.index(h["形"]))
            out.append(got[0])
    return out


def _main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--calc", help="この表を含む組だけ")
    ap.add_argument("--shape", choices=SHAPES)
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    hits = sweep_pairs()
    if args.calc:
        hits = [h for h in hits if args.calc in h["組"].split(" × ")]
    if args.shape:
        hits = [h for h in hits if h["形"] == args.shape]

    tally = collections.Counter(h["形"] for h in hits)
    print(f"組から拾えた形: **{len(hits)}件**"
          + ("（" + " ・ ".join(f"{k} {v}" for k, v in tally.most_common()) + "）"
             if tally else ""))
    print("**候補です。意味と正しさは人が決めます。**"
          "組から2本以上の動画を出さないこと（docs/MEANS.md M19）\n")
    for h in hits[:args.limit]:
        print(f"  [{h['形']}] {h['組']}   単位 {h['単位']}")
        print(f"      A {h['A']}")
        print(f"      B {h['B']}")
        print("      " + " / ".join(f"{k} {v}" for k, v in h["詳しく"].items()))
    if len(hits) > args.limit:
        print(f"  … ほか {len(hits) - args.limit}件（`--limit` で伸ばす）")


if __name__ == "__main__":
    _main()
