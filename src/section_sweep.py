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

SHAPES = ("不変", "頭打ち", "崖", "逆転")


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


def _sweepable_params(fn: Callable) -> list[tuple[str, float]]:
    """既定値が数値で、他の引数を触らずに動かせるものだけ返す。"""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    out = []
    for name, p in sig.parameters.items():
        if p.default is inspect.Parameter.empty:
            return []          # 既定値の無い引数があると、そのまま呼べない
        if isinstance(p.default, bool) or not isinstance(p.default, (int, float)):
            continue
        out.append((name, float(p.default)))
    return out


def _classify(xs: list[float], ys: list[float]) -> tuple[str, dict] | None:
    """点の並びから形を1つ決める。**当てはまらなければ None。**"""
    if len(ys) < 4 or any(map(lambda v: math.isnan(v) or math.isinf(v), ys)):
        return None
    lo, hi = min(ys), max(ys)
    scale = max(abs(lo), abs(hi))
    if scale == 0:
        return None
    if (hi - lo) / scale <= FLAT_TOL:
        return "不変", {"値": ys[0]}

    steps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    moving = [abs(s) for s in steps if abs(s) / scale > FLAT_TOL]

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
            return "逆転", {"どこ": kind, "x": xs[idx], "値": ys[idx],
                          "端では": edge}

    # 崖: 1つの段差だけが中央の5倍以上（**跳ぶ幅そのものが屑でないこと**）
    if len(moving) >= 3:
        mid = median(moving)
        biggest = max(moving)
        if mid > 0 and biggest / mid >= CLIFF_RATIO and biggest / scale >= MEANINGFUL:
            i = [abs(s) for s in steps].index(biggest)
            return "崖", {"x の手前": xs[i], "x の先": xs[i + 1],
                         "跳ぶ幅": steps[i], "中央の段差": mid}
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


def sweep_function(fn: Callable, *, name: str = "") -> list[dict]:
    """1つの関数を掃引して、出た形を並べる。"""
    found = []
    params = _sweepable_params(fn)
    defaults = [d for _, d in params]
    for pname, default in params:
        xs, rows = [], []
        for x in _grid(default):
            try:
                value = fn(**{pname: _cast(default, x)})
            except Exception:
                continue
            scal = _scalars(value)
            if not scal:
                break
            xs.append(x)
            rows.append(scal)
        if len(xs) < 4:
            continue
        keys = set(rows[0])
        for r in rows[1:]:
            keys &= set(r)
        for key in sorted(keys):
            ys = [r[key] for r in rows]
            hit = _classify(xs, ys)
            if hit:
                shape, detail = hit
                if shape == "不変" and _is_echo(ys[0], defaults, xs):
                    continue
                found.append({"関数": name or getattr(fn, "__name__", "?"),
                              "動かした引数": pname, "見た値": key or "返り値",
                              "形": shape, "詳しく": detail,
                              "x の幅": (xs[0], xs[-1])})
    return found


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
    label_key = next((k for k, v in rows[0].items()
                      if isinstance(v, str)), None)
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
        hit = _classify(list(range(len(rows))), ys)
        if not hit:
            continue
        shape, detail = hit
        if shape == "不変":
            continue          # 表の中で動かない欄は、たいてい前提の再掲
        for k in ("止まる x", "x", "x の手前", "x の先"):
            if k in detail:                       # 行番号を、読める見出しに直す
                i = int(detail[k])
                detail[k] = (rows[i].get(label_key) if label_key
                             else _row_label(rows[i], axis or keys)) or f"{i}行目"
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
SHAPE_ORDER = {"崖": 0, "逆転": 1, "頭打ち": 2, "不変": 3, "読めない": 4}


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
            hits = sweep_function(fn, name=fname) + sweep_rows(fn, name=fname)
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
    elif hit["形"] == "頭打ち":
        tail = (f"{hit['動かした引数']} が {_fmt(d['止まる x'])} から上は "
                f"{_fmt(d['止まった値'])} で止まる")
    elif hit["形"] == "崖":
        tail = (f"{hit['動かした引数']} が {_fmt(d['x の手前'])}→{_fmt(d['x の先'])} で "
                f"{_fmt(d['跳ぶ幅'])} 跳ぶ（ふだんの段差は {_fmt(d['中央の段差'])}）")
    elif hit["形"] == "逆転":
        tail = (f"{d['どこ']}のは端ではなく {hit['動かした引数']}="
                f"{_fmt(d['x'])} のとき（{_fmt(d['値'])}／端では {_fmt(d['端では'])}）")
    else:
        tail = str(d)
    return (f"  {hit['形']:<4} {hit['表']}.{hit['関数']}"
            f"（{hit['見た値']}）… {tail}")


def report_lines(hits: list[dict], *, top: int = 40) -> list[str]:
    """族の順番の値で並べて出す。**浅い順でも、出た順でもない。**"""
    try:
        from src import family_perf
        order = family_perf.combined_map()
    except Exception:
        order = {}
    hits = dedupe(hits)
    by_calc: dict[str, list[dict]] = {}
    for h in hits:
        by_calc.setdefault(h["表"], []).append(h)
    ranked = sorted(by_calc.items(),
                    key=lambda kv: (-order.get(kv[0], 0.0), -len(kv[1]), kv[0]))
    lines = [f"=== 機械が拾った節の候補 {len(hits)}件 / 表 {len(by_calc)}本 ===",
             "  **候補です。節ではありません。**意味と正しさは人が決めること"
             "（数字の出どころにしない）。"]
    shown = 0
    for name, group in ranked:
        if shown >= top:
            lines.append(f"  …ほか {len(hits) - shown}件（`--calc <表>` で全文）")
            break
        lines.append(f"  --- {name}（{len(group)}件・族の順番の値 "
                     f"{order.get(name, 0.0):.1f}）---")
        for hit in group[:6]:
            lines.append(line_of(hit))
            shown += 1
        if len(group) > 6:
            lines.append(f"    …ほか {len(group) - 6}件")
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
