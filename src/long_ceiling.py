"""**長尺の1本あたり再生は、天井なのか。いま判定できるのか。**

    python -m src.long_ceiling      # **API 0単位**（手元の控えだけを読む）

## なぜ要るか（2026-08-31 に作り、2026-09-01 に測り直した）

`config/hypotheses.yaml` の **`長尺1本あたり-13本`** が、`scripts/eta.py` の
言う「**未測定の1つ**」です —— `per_video` の天井 1,891 は
**ショート39本の実測**で、長尺には掛かりません。そして eta は
「月20万に届く帯は、**長尺がショート並み（673回/本）に伸びた**側だけ」と印字します。
**つまりこの1件が、目標に届く道が在るかどうかを決めています。**

## **2026-09-01 に、この前提は永久に閉じない形でした**（直した）

前の版の反証条件は「**齢 24〜72時間** の読みがある長尺が **30本以上**」。
**その2つが、どちらも判定を止めていました。**

**(1) 30本 は窓に入りません。** 判定が読むのは直近28日で、規則1（1日1本）の下で
その窓に入りうるのは **最大 28本**。**30 > 28。** しかも `falsified_if` 自身が
「満たなければ**期限だけ延ばすこと**」と書いており、
`src/house_rule.needs_beyond_rule()` は**期日で解く**ので延ばすと黙ります ——
**指示と検査が同じ向きに壊れていました**
（いまは `house_rule.window_unreachable()` が窓の側で見ます）。

**(2) 齢 24〜72時間 は、長尺の熟れる前です。** この repo 自身の
`src/settle.mature_hours('長尺')` は **96時間**と答えます（ショートは 48時間）。
`settle.settles_at('長尺')` に至っては **どの地平でも伸びきらない**
（`supported: False`）。**実測 2026-09-01**:

    齢 24〜72時間   n=19  中央値 **1.0回**   ← 前の版が読んでいた所
    齢 96時間 以上  n=22  中央値 **4.0回**   ← ×4

**前の版は、長尺を熟れる前に読んで「1回」と数えていました。**

## 判定の形（符号検定。**効き目の 80回 は1文字も緩めていません**）

「中央値が 80回」が真なら、各本が 80回 を超える確率は 0.5。だから

    n=13 で 80回超が **3本以下** → p=0.046（片側）で棄却 ＝ **外れ**

**30本 は過剰でした。** 13本 なら窓（28本）に入り、同じ効き目を同じ厳しさで
判定できます。**下げたのは本数だけで、門ではありません。**

## 数える集合が2つあること（**どちらも消さないこと**）

    `scripts/deadline_check.long_ids()`   `data/batch_runs.jsonl` の `long: true` だけ
                                          → **必ず少なめ**。`needs` の見張りはこちら
    `src/reach_split.long_ids()`          そこに `config/pairs.yaml` を足した側
                                          → **判定はこちら**（2026-08-24 に
                                            「天井の分母が半分だった」と直した集合）

**実測 2026-09-01 で 13本 と 22本。** 母集団が違うので一致しません。
`needs` が下振れの見張り、判定が実測 —— **役が別です。**

## 覆る条件

- **オーナーが規則を外したら**（`house_rule.PUBLISH_PER_DAY` が上がる）、
  窓に入る本数が増えるので `N_TARGET` を上げ直してよい
- **`settle.mature_hours('長尺')` が動いたら**、`mature_hours()` は自動で追います
  —— 96 は**この関数が読めなかったときの控え**でしかありません
- **長尺が熟れきる地平が見つかったら**（いまは `supported: False`）、
  そこまで待った読みで測り直すこと。**96時間 は下限であって、確定ではありません**
"""
from __future__ import annotations

import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ETA_LOG = ROOT / "data" / "eta.jsonl"
VIEWS = ROOT / "data" / "views.jsonl"
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"

#: 判定の門（`config/hypotheses.yaml` の `長尺1本あたり-13本` の `falsified_if`）。
#: **2か所に書いています。** 片方だけ動くのを止めるのは
#: `tests/test_long_ceiling.py::test_門の数は仮説と同じ` です。
MEDIAN_GATE = 80

#: 判定に要る本数（同じ前提の `need`）。**窓（28本）に入る数**であること。
N_TARGET = 13

#: `N_TARGET` 本のうち、門を超えた本がこれ以下なら「中央値 80回」を棄却する。
#: **`sign_reject_at(N_TARGET)` の答えを写したもの**（検査で突き合わせます）。
ABOVE_MAX = 3

#: 判定が読む窓（日）。`scripts/eta.py::_measure()` の `q(28, ...)` と同じ。
WINDOW_DAYS = 28

#: `src/settle.mature_hours('長尺')` が読めなかったときの控え。**確定値ではありません。**
MATURE_HOURS_FALLBACK = 96


def mature_hours() -> int:
    """**長尺が熟れる齢。** `src/settle.py` に訊き、読めなければ控えを返す。

    **写さないこと** —— 実測が動いたら、ここも動くべきなので。
    """
    try:
        from src import settle                              # noqa: PLC0415
        h = settle.mature_hours("長尺")
        if h:
            return int(h)
    except Exception:                                        # noqa: BLE001
        pass
    return MATURE_HOURS_FALLBACK


# --- 符号検定 ---------------------------------------------------------------

def sign_p(n: int, above: int) -> float:
    """**「中央値が門」が真なら、門超えが `above` 本以下になる確率**（片側）。

    各本が門を超えるかは表裏（p=0.5）。だから二項の下側累積です。
    """
    if n <= 0:
        return 1.0
    above = max(0, min(int(above), int(n)))
    return sum(comb(n, i) for i in range(above + 1)) / 2 ** n


def sign_reject_at(n: int, alpha: float = 0.05) -> int | None:
    """n 本で「中央値が門」を棄却できる**門超えの本数の上限**。無ければ `None`。

    **これが `ABOVE_MAX` の出どころです。** 事前に決める棄却域であって、
    出てきた標本から選ぶものではありません。
    """
    best = None
    for k in range(n + 1):
        if sign_p(n, k) < alpha:
            best = k
        else:
            break
    return best


# --- 標本（**判定が読む側**） -----------------------------------------------

def band_by_id(lo: float, hi: float,
               path: Path | None = None) -> dict[str, float]:
    """`data/views.jsonl` から、**齢が `lo`〜`hi` の、いちばん新しい読み**を本ごとに。

    **帯で切ること**（「以上」だけにしない）—— 長尺を熟れる前に読むと
    ×4 低く出るので、比べるときは同じ帯どうしで並べる必要があります。
    """
    p = VIEWS if path is None else path
    if not p.is_file():
        return {}
    best: dict[str, tuple[float, float]] = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue                                  # 壊れた行で回を止めない
        vid = r.get("id")
        if not vid:
            continue
        try:
            hours = float(r.get("hours") or 0)
            views = float(r.get("views") or 0)
        except (TypeError, ValueError):
            continue
        if not (lo <= hours <= hi):
            continue
        if vid not in best or hours > best[vid][0]:
            best[vid] = (hours, views)
    return {k: v[1] for k, v in best.items()}


def long_id_set() -> set[str]:
    """判定が使う長尺の集合（`pairs.yaml` を足した側）。読めなければ空。"""
    try:
        from src import reach_split                          # noqa: PLC0415
        return reach_split.long_ids()
    except Exception:                                        # noqa: BLE001
        return set()


def sample_in_band(lo: float, hi: float,
                   path: Path | None = None) -> list[float]:
    """その齢の帯での、長尺の1本あたり再生（昇順）。"""
    ids = long_id_set()
    if not ids:
        return []
    return sorted(v for k, v in band_by_id(lo, hi, path).items() if k in ids)


def mature_sample(min_hours: float | None = None,
                  path: Path | None = None) -> list[float]:
    """**判定に使う標本** —— 熟れた長尺の、1本あたり再生（昇順）。

    長尺の集合は `src/reach_split.long_ids()`（`pairs.yaml` を足した側）。
    **読めなければ空を返します** —— 回を止めないこと。
    """
    h = mature_hours() if min_hours is None else min_hours
    return sample_in_band(h, float("inf"), path)


def verdict(values: list[float] | None = None) -> dict:
    """**いま判定できるか。できるなら、どちらか。**

    返すのは `{"n", "above", "need", "above_max", "p", "decidable", "falsified"}`。
    **`decidable` が偽なら、`falsified` は読まないこと**（まだ判定していません）。
    """
    v = sorted(mature_sample() if values is None else values)
    n = len(v)
    above = sum(1 for x in v if x > MEDIAN_GATE)
    decidable = n >= N_TARGET
    limit = sign_reject_at(n) if n else None
    return {"n": n, "above": above, "need": N_TARGET, "above_max": ABOVE_MAX,
            "median": median(v), "p": sign_p(n, above) if n else 1.0,
            "reject_at": limit, "decidable": decidable,
            "falsified": bool(decidable and limit is not None and above <= limit)}


# --- 一般の道具（**天井の上限を読む側**。判定そのものではありません） -------

def median(values: list[int | float]) -> float:
    """昇順に並べた中央値。**空なら 0.0**（呼ぶ側が `n` を見ること）。"""
    v = sorted(values)
    if not v:
        return 0.0
    mid = len(v) // 2
    if len(v) % 2:
        return float(v[mid])
    return (v[mid - 1] + v[mid]) / 2.0


def best_case_median(values: list[int | float], n_target: int = N_TARGET,
                     optimistic: float | None = None) -> float:
    """**あと (n_target − len(values)) 本を `optimistic` で埋めたときの中央値。**

    `optimistic` を省くと**いまの標本の最大値**を使います —— つまり
    「**残り全部が、このチャンネルの最良の長尺と同じだけ回ったら**」。

    **`float('inf')` を既定にしないこと**（2026-08-31 に書きかけて止めた）。
    無限を入れると上限が `inf` になり、「まだ分からない」に見えます。
    **実測の最大値なら、上限は実測で裏の取れる数になります。**
    """
    v = sorted(values)
    if len(v) >= n_target:
        return median(v)
    if not v:
        return 0.0
    fill = v[-1] if optimistic is None else optimistic
    return median(v + [fill] * (n_target - len(v)))


def share_at_or_above(values: list[int | float], gate: float = MEDIAN_GATE) -> float:
    """**門に届いた本の割合**（標本が空なら 0.0）。"""
    if not values:
        return 0.0
    return sum(1 for x in values if x >= gate) / len(values)


def rescue_needed(values: list[int | float], n_target: int = N_TARGET,
                  gate: float = MEDIAN_GATE) -> int:
    """**いまの標本のうち、何本が窓から落ちれば中央値が門に届きうるか。**

    小さいほうから順に落とし、残りを `gate` で埋めた中央値が門に届く
    最小の本数を返します。**0 なら、落とさなくても届きえます。**
    """
    v = sorted(values)
    for k in range(len(v) + 1):
        kept = v[k:]
        if best_case_median(kept, n_target, optimistic=gate) >= gate:
            return k
    return len(v)


def latest(path: Path | None = None) -> dict:
    """`data/eta.jsonl` の**最後の点**。壊れた行は飛ばします（回を止めない）。"""
    p = ETA_LOG if path is None else path
    if not p.is_file():
        return {}
    out: dict = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out = json.loads(ln)
        except json.JSONDecodeError:
            continue
    return out


# --- 印字 -------------------------------------------------------------------

def lines() -> list[str]:
    """判定の行。**API 0単位**（`data/views.jsonl` だけを読みます）。"""
    h = mature_hours()
    v = mature_sample()
    d = verdict(v)
    out = [f"=== 長尺の1本あたり再生は天井か（`長尺1本あたり-13本` の門 "
           f"{MEDIAN_GATE}回・齢 {h}時間 以上）==="]
    if not v:
        out.append("  **測っていません** —— `data/views.jsonl` に、齢 "
                   f"{h}時間 以上の長尺の読みが1件もありません。"
                   "**「長尺が0本だった」ではありません。**")
        return out
    out += [
        f"  いま **{d['n']}本** ／ 中央値 **{d['median']:g}回** ／ "
        f"門（{MEDIAN_GATE}回）を超えた本 **{d['above']}本**",
        f"  実測（昇順）: {' '.join(f'{x:g}' for x in v)}",
    ]
    # **熟れる前に読むと、いくつに見えるか。** ここが 2026-09-01 の直しの中身です。
    young = sample_in_band(24, 72)
    if young:
        out.append(f"  **齢 24〜72時間 で読むと 中央値 {median(young):g}回・n={len(young)}**"
                   f" —— 熟れてから読むと {d['median']:g}回 です"
                   f"（**前の版はここを読んでいました**）。"
                   f"`src/settle.settles_at('長尺')` は**どの地平でも伸びきらない**"
                   f"と出ているので、**この {h}時間 も下限です。**")
    if not d["decidable"]:
        out.append(f"  **まだ判定できません** —— {N_TARGET}本 に "
                   f"{N_TARGET - d['n']}本 足りません。**判定せず、期限を延ばすこと。**")
        return out
    lim = d["reject_at"]
    if d["falsified"]:
        out.append(f"  → **判定できます。外れです**（`falsified`）—— "
                   f"「中央値が {MEDIAN_GATE}回」が真なら門超えは半分 期待されるのに、"
                   f"**{d['n']}本中 {d['above']}本**。符号検定 **p={d['p']:.4f}**"
                   f"（棄却域は {lim}本以下）。"
                   f"**＝ {MEDIAN_GATE}回 は本数のせいではなく、長尺そのものの天井。**")
        out.append("  **`next_if_false` を読むこと** —— この前提が外れると、"
                   "`scripts/eta.py` の天井の表で『届く』と出る帯が"
                   "**長尺がショート並みに伸びた側だけ**になります。")
    else:
        out.append(f"  → **判定できます。外れていません**（`survived`）—— "
                   f"{d['n']}本中 {d['above']}本 が門超えで、棄却域"
                   f"（{lim}本以下）に入りません。p={d['p']:.4f}。")
    return out


def report() -> str:
    return "\n".join(lines())


def main() -> None:
    print(report())


if __name__ == "__main__":
    main()
