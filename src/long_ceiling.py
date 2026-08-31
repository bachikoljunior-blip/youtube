"""**長尺の1本あたり再生の「中央値」が、あと何本 積めば覆りうるか。**

    python -m src.long_ceiling      # **API 0単位**（`data/eta.jsonl` の最後の点を読む）

## なぜ要るか（2026-08-31 に足した）

`config/hypotheses.yaml` の **`長尺1本あたり-30本`** は、こう書いてあります ——

    **齢 24〜72時間 の読みがある長尺が 30本以上 そろったうえで**、
    その1本あたり再生の**中央値が 80回 に届かない**なら外れ

そして `scripts/deadline_check.py` は毎回 **「要 30 ／ いま 14 → あと 3日」**
とだけ出します。**「あと3日 待てば分かる」と読めます。**

**そこが読み違いでした**（2026-08-31 に実測）。判定が読む側の数
（`long_videos_28d`）は **21本**で、その中央値は **4回**。**分布はこうです**:

    1 1 1 1 1 2 2 3 3 3 4 4 4 4 6 7 8 15 48 82 133

**あと9本 を、このチャンネルが今までに出した最良の長尺（133回）で
埋めても、30本の中央値は 6.5 にしかなりません** —— 門は 80 です。
**待っても、この前提はこの標本からは覆りません。**

**「判定するな」と言っているのではありません。** `falsified_if` は
「30本に満たなければ判定せず、期限だけ延ばすこと」と書いてあり、
**その一文は1文字も緩めません。** ここが出すのは**上限**です ——
「あと何本 積んでも、いまの標本のままなら中央値はここまで」。

## **平均だけが印字されていました**（この回に見つけた欠陥）

`scripts/eta.py` は `long_median_per_video` を**測って `data/eta.jsonl` に
積んでいながら、1行も印字していません。** 印字しているのは平均のほうで、
実測は **平均 16回 に対し 中央値 4回（4倍）**。

**判定に使うのは中央値のほう**です。この repo が「いちばん当たる」と言っている形
（同じことを2か所が別々に言っていて、**読まれるのは判定に使わないほう**）でした。

## **覆る条件 —— 標本は入れ替わります**

判定が読むのは **直近28日**の窓です。**古い本は窓から落ちます。**
だから上の上限は「**いまの21本が窓に残っているかぎり**」の話です。

実測 2026-08-31 の 21本のうち **7本 は 08/12 より前の公開**で、
09/09 の判定日には窓から落ちています。落ちたぶんを新しい本が埋めれば、
中央値は上に動きえます。**動くために要る本数は `rescue_needed()` が出します。**

**いまの実測でその確率を見積もる材料**: 21本のうち 80回 に届いたのは **2本
（9.5%）**。**30本のうち15本 を 80回 以上にする**必要があるので、
その率が 3〜4倍 に変わらないかぎり届きません。

**この推定が覆る条件**: 9.5% は**登録者 500人 未満・面が 1,368回/日**の
チャンネルで測った率です。**面が桁で増えたら、測り直すこと**
（`src/rpm_mix.surface_ceiling` の分子）。

## 何を読むか

`data/eta.jsonl` の最後の点の **`long_values_28d`**（昇順の実測）。
**`scripts/eta.py` を1回 撃つまで、この鍵は積まれません** ——
無ければ「測っていない」と出します。**「0本だった」ではありません。**
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ETA_LOG = ROOT / "data" / "eta.jsonl"
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"

#: 判定の門（`config/hypotheses.yaml` の `長尺1本あたり-30本` の `falsified_if`）。
#: **2か所に書いています。** 片方だけ動くのを止めるのは
#: `tests/test_long_ceiling.py::test_門の数は仮説と同じ` です。
MEDIAN_GATE = 80

#: 判定に要る本数（同じ `falsified_if` の `need`）。
N_TARGET = 30

#: 判定が読む窓（日）。`scripts/eta.py::_measure()` の `q(28, ...)` と同じ。
WINDOW_DAYS = 28


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
    **`len(values)` を返したら、標本を全部 入れ替えても届かない**という意味です
    （`n_target` が標本より小さいときに起きます）。
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


def lines(row: dict) -> list[str]:
    """印字する行。**`long_values_28d` が無い点では「測っていない」と出します。**"""
    vals = row.get("long_values_28d")
    n_have = row.get("long_videos_28d")
    if not isinstance(vals, list) or not vals:
        return [
            "=== 長尺の中央値は、あと何本 積めば覆りうるか ===",
            "  **測っていません** —— `data/eta.jsonl` の最後の点に "
            "`long_values_28d` がありません（`scripts/eta.py` を1回 撃つと積まれます）。"
            f"**「長尺が0本だった」ではありません**（同じ点の `long_videos_28d` は "
            f"{n_have if n_have is not None else '不明'}）。",
        ]
    vals = sorted(vals)
    med = median(vals)
    bound = best_case_median(vals)
    rate = share_at_or_above(vals)
    need = rescue_needed(vals)
    out = [
        "=== 長尺の中央値は、あと何本 積めば覆りうるか"
        f"（`長尺1本あたり-30本` の門 {MEDIAN_GATE}回）===",
        f"  いま **{len(vals)}本** ／ 中央値 **{med:g}回** ／ 平均 "
        f"{sum(vals) / len(vals):.1f}回（**判定に使うのは中央値のほう**）",
        f"  実測（昇順）: {' '.join(str(x) for x in vals)}",
    ]
    if len(vals) >= N_TARGET:
        out.append(f"  **{N_TARGET}本 に届いています。判定できます**"
                   f"（`config/hypotheses.yaml` の `falsified_if` を読むこと）。")
    else:
        out.append(
            f"  残り **{N_TARGET - len(vals)}本** を、**このチャンネルの最良の長尺"
            f"（{vals[-1]}回）**で埋めても、{N_TARGET}本の中央値は **{bound:g}回**"
            f" —— 門は {MEDIAN_GATE}回 です。"
            + ("**待っても、いまの標本のままでは届きません。**"
               if bound < MEDIAN_GATE else
               "**届きえます。** 待つこと。"))
    out.append(
        f"  門に届いた本: **{sum(1 for x in vals if x >= MEDIAN_GATE)} / {len(vals)}本"
        f"（{rate * 100:.1f}%）** —— {N_TARGET}本 の中央値を門に載せるには"
        f" **半分**が要ります。")
    if need:
        out.append(
            f"  [!] **覆るのは「待つ」ではなく「入れ替わる」ほうです** —— 判定は"
            f"**直近{WINDOW_DAYS}日**の窓なので、古い本は落ちます。"
            f"いまの標本のうち**低いほうから {need}本 が窓から落ちて**、"
            f"そのぶんが門以上の本で埋まれば、中央値は門に届きえます。")
    out.append(
        "  **これは判定ではありません。** `falsified_if` の"
        f"「{N_TARGET}本 に満たなければ判定せず、期限だけ延ばすこと」は"
        "1文字も緩めていません —— ここが出しているのは**上限**です。")
    return out


def report(path: Path | None = None) -> str:
    return "\n".join(lines(latest(path)))


def main() -> None:
    print(report())


if __name__ == "__main__":
    main()
