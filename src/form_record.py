"""**形ごとの「これまでの最高」1本あたり再生**（2026-08-31・最適化の回）。**API 0単位。**

## この道具が答える1つの問い

> **規則が「1日1本」に固定された以上、到達日を決めるのは
> 「その1本が何回 回るか」の1点だけです。**
> では **この機械が実際に出した最高**は、目標に要る数の何分の1か。

`scripts/eta.py` はこの問いに **平均**で答えていました（`per_video_ratio`）。
平均で割ると、いちばん近い帯は `ショート 高` の **×196.3**。
**最高で割ると、いちばん近い帯は `長尺 お金 高` の ×21.4 になります**
（この回に自分で数えた実測。下の「実測」）。**9.2分の1**で、**帯そのものが入れ替わります。**

## なぜ平均ではなく最高で見る節が要るか

`scripts/eta.py` の `nearest` の註が、自分でその欠陥を書いています ——

    **ほぼ 0 の分母で割ると、倍率は無限に大きく出ます** ——
    倍率だけで選ぶと、`nearest` は**いつまでもショートを指し続けます。**

長尺の分母 **16.0回/本** は「登録者 22人 のチャンネルに出した 21本 の平均」で、
`docs/MEANS.md` M20 が「**長尺の実力ではない**」と書いている数そのものです。
**最高（156回）は、この機械が実際に1本で取った数**なので、分母として同じ壊れ方をしません。
「平均を N倍 にする」より「**もう1回 最高を出し、それを N倍 にする**」ほうが、
規則3（次の1本を出る瞬間まで良くし続ける）の言い換えとして素直です。

## **形をまたがないこと**（この道具のもう半分の役目）

`config/hypotheses.yaml` の `ceiling.value: 1891` は
**形で絞らずに数えた最大**です（`tests/test_per_video_ceiling.py` の
`measured_max_24h()` に form の条件が1つもありません）。実物は**ショートの本**で、
`src/arm_speed.arm()` はそれを**ショートの平均 566回**で割って `per_video` の天井
**×3.34** を作ります。ところが `scripts/eta.py` の段3・段4 は、その 566回 を
**長尺の RPM（¥400・¥2,000）**と掛けます（`eta.py` 自身が
「**物差しはショートの実測 566回/本**」と印字しています）。

**その組み合わせを作れる形は、1つもありません。** ショートは ¥400 を稼がず、
長尺は 566回 回っていません。**この道具は、形をまたがない最大だけを出します。**

## 実測（2026-08-31・`data/views.jsonl` 22,442点 ＋ `data/video_forms.json`）

    形        本数   これまでの最高    規則1本/日×30日 の最大の月収
    ショート  156    1,891 回/本      RPM ¥60  →  ¥3,404/月（目標の 1.7%）
    長尺       22      156 回/本      RPM ¥2,000 → ¥9,360/月（目標の 4.7%）

**ショートの 1,891 は `config/hypotheses.yaml` の `ceiling.value` と一致します。**
別の数え方で同じ数に着いたので、**長尺の 156 も同じ確からしさ**です
（長尺の最高がどこにも数えられていなかったのは、数えにくいからではなく、
 **誰も数えていなかったから**です）。

## 覆る条件

- **記録が更新されたら、数は自動で動きます**（定数を持ちません）。
  `tests/test_form_record.py` が、ショートの最高と `hypotheses.yaml` の
  `ceiling.value` がずれたら落とします —— **ずれたらどちらかが古い。**
- `data/video_forms.json` は**公開済みだけ**を持ちます。形の分からない本
  （この回で 70本・最高 897回）は**どの形にも足しません。**
  足すと、形をまたがない、というこの道具の唯一の役目が消えます。
- **「最高で割った倍率」を到達日に入れないこと。** 到達日は平均で解きます
  （毎日 記録が出る前提の日付は、記録の定義に反します）。
  ここが出すのは**距離の目盛り**であって、予測ではありません。
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

from . import forms as _forms

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"


def per_video_best(views_path: Path | None = None,
                   forms: dict[str, str] | None = None) -> dict[str, dict]:
    """形ごとの **1本あたり再生の最高**（`{"ショート": {...}, "長尺": {...}}`）。

    採るのは**その本について観測した最大の再生数**（＝生涯）です。
    24時間ふきんに絞りません —— 稼ぐのは生涯の再生で、
    `hypotheses.yaml` の `ceiling.value: 1891` とも一致します
    （`tests/test_form_record.py`）。

    返り（形ごと）::

        best   これまでの最高（回/本）
        id     その本のID
        n      数えた本数（**形が実測で分かっている本だけ**）
        mean   平均
        median 中央値

    **形の分からない本は1本も入りません**（`data/video_forms.json` は公開済みだけ）。
    """
    path = views_path or VIEWS
    forms = _forms.measured_forms() if forms is None else forms
    if not path.exists():
        return {}

    lifetime: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid, v = r.get("id"), r.get("views")
        if not vid or v is None:
            continue
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        if v > lifetime.get(vid, -1):
            lifetime[vid] = v

    by: dict[str, list[tuple[int, str]]] = {}
    for vid, v in lifetime.items():
        form = forms.get(vid)
        if form not in ("ショート", "長尺"):
            continue
        by.setdefault(form, []).append((v, vid))

    out: dict[str, dict] = {}
    for form, rows in by.items():
        rows.sort(reverse=True)
        vals = [v for v, _ in rows]
        n = len(vals)
        out[form] = {
            "best": vals[0],
            "id": rows[0][1],
            "n": n,
            "mean": sum(vals) / n,
            "median": (vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2),
            # **その記録は伸びきった本のものか**（2026-08-31・最適化の回に足した）。
            #     偽 ＝ **記録は下限**で、`gaps()` の `ratio` は隔たりの**上限**です。
            #     出どころは `src.settle.mature_hours_supported`（実測・API 0単位）。
            #     実測 2026-08-31: ショート **真**（地平 480h でも 48h で 100%）／
            #     長尺 **偽**（地平を 336h へ延ばすと、240h で伸びきった本は 0本）。
            "settled": _settled(form),
        }
    return out


@functools.lru_cache(maxsize=None)
def _settled(form: str) -> bool:
    """`src.settle` に訊く。**訊けなければ「伸びきっていない」側に倒す。**

    **1プロセスのあいだ憶えます**（`lru_cache`）。`settles_at()` は
    `data/views.jsonl`（2MB・22,000行）を**地平4つ ぶん**読み直すので 0.25秒/形 かかり、
    `scripts/eta.py` は1回の走りで `per_video_best()` を何度も呼びます。
    **憶えないと、同じ答えのために同じファイルを 6〜8回 読みます。**

    **憶えてよい理由**: この道具を呼ぶのは短命な CLI（`eta.py` / `pipeline.py`）で、
    1回の走りのあいだに `data/views.jsonl` は増えません。
    **長く生きるプロセスから呼ぶことになったら、ここを外すこと。**
    測り直したい側（検査・道具）は `settle.settles_at()` を直接 呼べば、
    **こちらの憶えは通りません。**

    倒す向きを偽にしているのは、**偽は「記録は下限」という弱い主張**で、
    真は「この記録が上限」という強い主張だからです。
    道具が落ちたときに強いほうへ倒れると、**黙って「届きません」が固まります。**
    """
    try:
        from . import settle as _settle
        return bool(_settle.mature_hours_supported(form))
    except Exception:                                          # noqa: BLE001
        return False


def unknown_form(views_path: Path | None = None,
                 forms: dict[str, str] | None = None) -> int:
    """**形が実測で分かっていない本の数。**（この道具が数えなかったぶん）

    黙って落とすと「156本 しか出していない」に見えます。**数だけ残します。**
    """
    path = views_path or VIEWS
    forms = _forms.measured_forms() if forms is None else forms
    if not path.exists():
        return 0
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid = r.get("id")
        if vid and forms.get(vid) not in ("ショート", "長尺"):
            seen.add(vid)
    return len(seen)


def ceiling_yen(best: float, rpm: float, per_day: float, days: int = 30) -> float:
    """**その形の記録を毎日 出し続けたときの月収**（円）。

    `best × per_day × days / 1000 × rpm`。**`per_day` は規則の 1本/日**
    （`src.house_rule.PUBLISH_PER_DAY`）。**形をまたがないこと** ——
    `best` と `rpm` は同じ形のものだけを渡すこと。
    """
    return best * per_day * days / 1000.0 * rpm


def gaps(rpm_scenarios: dict[str, float], per_video_needed: dict[str, float],
         *, per_day: float, target_yen: float,
         records: dict[str, dict] | None = None) -> list[dict]:
    """**帯ごとに「記録の何倍 要るか」**を並べる（`per_video_needed` は `eta.analyse()` の値）。

    帯の名前の頭で形を決めます（`長尺…` → 長尺・それ以外 → ショート）。
    **形の記録が無い帯は返しません**（作れない組み合わせを並べないため）。

    返りの各行::

        band   帯の名前         form   形        record  その形の記録（回/本）
        need   要る1本あたり     ratio  need / record   yen  記録を毎日 出したときの月収
        share  yen / target_yen（目標の何割か）
    """
    recs = per_video_best() if records is None else records
    out: list[dict] = []
    for band, rpm in rpm_scenarios.items():
        form = "長尺" if str(band).startswith("長尺") else "ショート"
        rec = recs.get(form)
        if not rec or not rec.get("best"):
            continue
        need = per_video_needed.get(band)
        if not need:
            continue
        yen = ceiling_yen(rec["best"], rpm, per_day)
        out.append({"band": band, "form": form, "rpm": rpm,
                    "record": rec["best"], "record_id": rec["id"], "n": rec["n"],
                    "need": need, "ratio": need / rec["best"],
                    # **記録が伸びきっていない形では、`ratio` は隔たりの上限です**
                    #     （分母が下限なので、比は必ず上振れします）。
                    "settled": bool(rec.get("settled", False)),
                    "yen": yen, "share": (yen / target_yen) if target_yen else 0.0})
    out.sort(key=lambda r: r["ratio"])
    return out
