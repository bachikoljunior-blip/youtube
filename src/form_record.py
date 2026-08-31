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

import copy
import functools
import json
from datetime import datetime, timedelta
from pathlib import Path

from . import forms as _forms

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"


#: **憶えの鍵**（2026-08-31）。**「既定の引数で呼んだか」ではなく「同じファイルか」。**
#: 中身が1バイトでも動けば鍵が変わるので、**測り直す側は憶えに当たりません。**
def _file_key(path: Path) -> tuple:
    try:
        st = path.stat()
        return (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        return (str(path), None, None)


def _forms_key(forms: dict[str, str] | None) -> int:
    """`forms` は dict（**ハッシュできない**）なので、中身から鍵を作ります。"""
    if forms is None:
        return 0
    return hash(tuple(sorted(forms.items())))


#: `per_video_best()` の憶え。**捨てるのは `censor_memo_clear()` 1か所**。
_BEST_MEMO: dict[tuple, dict] = {}


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

    ## **憶えます**（2026-08-31・最適化の回に足した。**答えは1つも変わりません**）

    この関数は `data/views.jsonl`（2MB・22,667行）と `data/video_forms.json` の
    **純関数**です。ところが呼ばれる場所が悪い ——
    `scripts/eta.py` の `_gate_legs()` から呼ばれ、`_gate_legs()` は `analyse()`
    から、`analyse()` は `trajectory()` の **1日ずつの探索ループの中**から呼ばれます。

    **実測（2026-08-31・この回に撃った）**::

        per_video_best()  1回 **345ms**（暖まった後。初回 1,180ms）
          内訳 = views.jsonl を **3回** 読む
                 （自分で1回 ＋ `censor_factor` が形ごとに1回ずつ ＝ 2回）
        `python scripts/eta.py --offline` は **5分 走っても終わりません**
          （faulthandler の背骨は 100% ここ: `_gate_legs` → `per_video_best`
            → `censor_factor` → `json.loads`）

    下の `_CENSOR_MEMO` は、この形を**塞いだつもりで塞げていませんでした** ——
    憶える条件が `views_path is None and forms is None` なのに、
    `per_video_best()` は **常に `views_path=path, forms=forms` を渡す**ので、
    **一度も当たりません**（この回に撃って確かめた）。
    さらにその註の「1回の走りで 6〜8回」は**外れ**です。実際は探索の深さぶん、
    百〜千の桁で呼ばれます。

    **だから憶える鍵を「既定の引数で呼んだか」から「ファイルが同じか」に替えます** ——
    `(道, mtime_ns, 大きさ, forms の中身)`。ファイルが1バイトでも動けば鍵が変わるので、
    **測り直したい側が憶えに邪魔される道はありません**（検査が別の道を渡す形も同じ）。
    それでも捨てたい側のために `censor_memo_clear()` が両方を捨てます。
    """
    path = views_path or VIEWS
    forms = _forms.measured_forms() if forms is None else forms
    if not path.exists():
        return {}

    key = ("best", _file_key(path), _forms_key(forms))
    if key in _BEST_MEMO:
        return copy.deepcopy(_BEST_MEMO[key])

    lifetime: dict[str, int] = {}
    #: **その本が世に出た時刻の推定** ＝ いちばん古い観測の時刻 − そのときの年齢。
    #:     `data/views.jsonl` だけから出ます（**API 0単位・別のファイルを読みません**）。
    #:     使い道は下の `tested_by`（記録が何本の反証に耐えたか）1つだけです。
    born: dict[str, str] = {}
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
        at, h = r.get("at"), r.get("hours")
        if at and h is not None:
            try:
                t = (datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ")
                     - timedelta(hours=float(h))).isoformat()
            except (TypeError, ValueError):
                continue
            if vid not in born or t < born[vid]:
                born[vid] = t

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
        out[form].update(_tested_by(rows, born))
        # --- **打ち切りぶんを、実測で埋める**（2026-08-31・最適化の回の第2手）---
        #     `settled` は「記録は下限だ」と**言うだけ**で、この回まで
        #     **誰もその下限を補正していませんでした。** `gaps()` も
        #     `eta.residual_gap()` も、下限をそのまま分母にして
        #     「×21.4・どの帯でも届きません」を印字していました。
        #     ここで、その倍率を**実測で**（定数なしで）足します。下の `censor_factor`。
        cf = censor_factor(form, views_path=path, forms=forms)
        out[form]["censor"] = cf
        out[form]["best_settled"] = out[form]["best"] * cf["factor"]
    _BEST_MEMO[key] = copy.deepcopy(out)
    return out


def _tested_by(rows: list[tuple[int, str]], born: dict[str, str]) -> dict:
    """**その記録は、何本の反証に耐えたか。**（2026-08-31・最適化の回に足した）

    ## なぜ要るか

    `scripts/eta.py` の「届きません」は、突き詰めると**2つの定数**が作っています
    （`residual_gap()` が自分でそう書いています）——
    `per_video` の天井 **1,891** と `RPM_SCENARIOS` の上端 **¥2,000**。

    そして 1,891 は「**39本のショートの実測の最大**」です。
    **標本の最大を「天井」と呼ぶのは、ふつうは誤り**です ——
    裾の重い分布では、最大は本数と一緒に伸び続けるので、
    「まだ大きいのを引いていない」だけのことがあります。

    **だから測ります。** 記録が立ったのが何本目で、そのあと何本が挑んで抜けなかったか。
    **この数は、天井の確からしさそのもの**です。0本 なら「最後に引いたのが最大」＝
    ただの標本の最大。139本 なら、**その天井は139回 反証にかけられて生き残っています。**

    ## 実測（2026-08-31・この回に自分で撃った・`data/views.jsonl` だけ・API 0単位）

        ショート  n=156  記録 1,891（`NHKylqsNfTw`）
                  記録は **17本目**（11%地点）。**そのあと 139本 出して更新 0回**
                  記録の更新は全部で 6回・上位5本 = 1510/1557/1777/1857/1891（**固まっている**）
                  上位10%（15本）が持つ再生の割合 **29.0%**（裾は重くない）
        長尺      n=22   記録 156（`_Mz5rg6jQ_A`）
                  記録は **13本目**（59%地点）。そのあと **9本**だけ
                  上位10%（2本）が持つ再生の割合 **67.6%**（**裾が重い**）・中央値は **4**

    **読み**: ショートの天井 1,891 は、139本 の反証に耐えています ——
    **「標本の最大にすぎない」という反論は、ショートには効きません。**
    長尺は逆で、**9本 しか挑んでいない**うえに上位2本が3分の2を持っています ——
    **長尺にはまだ天井が立っていません。** `残り ×1.76` を閉じられるとしたら
    そちら側です（そして `¥2,000` の帯は長尺の側です）。

    ## 覆る条件

    - **公開時刻は推定です** —— いちばん古い観測の時刻 − そのときの年齢。
      `data/views.jsonl` に古い本の観測しか無い場合、順は前後します。
      **順が1〜2本 ずれても、139 と 9 の差は動きません。**
    - **記録が更新されたら `tested_by` は 0 に戻ります**（定数を持ちません）。
      戻った回は、**その天井は一度も反証にかかっていない**ということです。
    """
    if not rows:
        return {}
    best_id = rows[0][1]
    ordered = [vid for _v, vid in rows if vid in born]
    ordered.sort(key=lambda v: born[v])
    if best_id not in born or not ordered:
        return {"record_rank": None, "tested_by": None,
                "why_untested": "公開の順が出せません（`hours` の付いた観測がありません）"}
    rank = ordered.index(best_id) + 1
    return {
        "record_rank": rank,
        "record_of": len(ordered),
        # **記録のあとに世に出た本の数** ＝ その天井が受けた反証の回数
        "tested_by": len(ordered) - rank,
    }


def _nearest(series: list[tuple[float, int]], hours: float,
             *, tol: float = 0.35, floor_h: float = 12.0) -> int | None:
    """`hours` にいちばん近い観測。**遠すぎれば `None`**（無い所を埋めないこと）。"""
    if not series or hours <= 0:
        return None
    d, _, v = min((abs(x - hours), x, v) for x, v in series)
    return None if d > hours * tol + floor_h else v


#: **打ち切り補正を出すのに要る、最低の本数。** これを割ったら補正しません
#: （n=1〜2 の中央値で記録を2倍にしないこと。**埋めないほうが安全側**です）。
CENSOR_MIN_N = 5

#: 補正を測る地平（時間）。`src.settle.SETTLE_HORIZONS` より先まで見ます ——
#: **実測 2026-08-31: 長尺は 480時間 で平らになります**（480/600/720 が同じ ×2.00）。
#: `settle.SETTLE_HORIZONS` は 480 で終わっており、**その先を見ていませんでした。**
CENSOR_HORIZONS: tuple[float, ...] = (336.0, 480.0, 600.0, 720.0)


#: **鍵は「同じファイルか」**（2026-08-31 に替えた。前は「既定の引数で呼んだか」）。
#:
#: **前の版の註は 2か所 外れていました**（どちらもこの回に撃って確かめた）:
#:
#:   1. 「1回の走りで **6〜8回**」 → 実測 **623回 で、まだ終わっていない**
#:      （`python scripts/eta.py --offline` を 150秒 で切った時点の数）。
#:      呼ばれる場所は `eta._gate_legs()` で、そこは `analyse()` の中、
#:      `analyse()` は `trajectory()` の **1日ずつの探索ループの中**です。
#:   2. 「道を差した呼び方は通しません」 → **唯一の呼び手が道を差していました。**
#:      `per_video_best()` は常に `views_path=path, forms=forms` を渡すので、
#:      **この憶えは一度も当たっていませんでした。**
#:
#: 実測: 150秒 のうち **139.4秒（93%）**が `per_video_best()` の中。
#:
#: `lru_cache` を使わないのは、`forms` が dict（**ハッシュできない**）だからです。
#: 代わりに `_file_key()`（道・mtime_ns・大きさ）と `_forms_key()`（中身）で鍵を作ります ——
#: **ファイルが1バイトでも動けば鍵が変わる**ので、測り直す側は憶えに当たりません。
#: 捨てたい側は `censor_memo_clear()`（`_BEST_MEMO` と `_settled` も一緒に捨てます）。
_CENSOR_MEMO: dict[tuple, dict] = {}


def censor_memo_clear() -> None:
    """**憶えを捨てる。** 測り直す側（検査・道具）が呼びます。

    `_settled` の `lru_cache` と対で使うこと —— 片方だけ捨てると、
    **片方の古い答えの上で測り直す**ことになります。
    """
    _CENSOR_MEMO.clear()
    _BEST_MEMO.clear()
    _settled.cache_clear()


def censor_factor(form: str, *, views_path: Path | None = None,
                  forms: dict[str, str] | None = None,
                  min_n: int = CENSOR_MIN_N) -> dict:
    """**記録が打ち切られているぶんの倍率**（実測・API 0単位・**定数を持ちません**）。

    ## この関数が答える問い

    `per_video_best()` の記録は「**観測が止まった時点**の再生数」です。
    伸びきった本ならそれが生涯ですが、**伸びている途中で観測が止まった本では下限**です。
    では **その本は、あと何倍 回ったか。**

    ## 数え方（**その記録の本の年齢から**測ること）

    形ぜんぶの平均ではありません。**記録の本が最後に観測された年齢 A** を取り、
    同じ形の本で「A の読み」と「もっと後の地平 T の読み」が**両方ある**ものだけを集め、
    **同じ本どうしの比 `T/A` の中央値**を返します（対応のある比。
    横断で年齢べつの中央値を並べると、**古い本ほど別の群**なので交絡します ——
    実測 2026-08-31: 横断だとショートが 274→1092 と 4倍 伸びて見えますが、
    **対応のある比では ×1.00** です）。

    `T` は **n が `min_n` 以上ある中でいちばん遠い地平**を採ります。
    どの地平も届かなければ **`factor 1.0`**（＝補正しない）を返します
    —— **埋めないほうが安全側**です（記録は下限のまま）。

    ## 実測（2026-08-31・`data/views.jsonl` 22,667点）

        形        記録の本          A      T       n   中央値   平均
        ショート  NHKylqsNfTw     372h   720h    10   ×1.00   ×1.00   ← 伸びきっている
        長尺      _Mz5rg6jQ_A     246h   720h     5   ×2.00   ×2.53   ← **下限だった**

    **ショートの記録の本は 366h〜372h のあいだ 1863 で平ら**です。
    **長尺の記録の本は 174h→246h で 97→131→156**（+61%）—— **登りながら観測が切れています。**
    だから長尺の記録 156 は **312**（×2.00）が実測に近く、
    `gaps()` の隔たりは **×21.4 ではなく ×10.7** です。

    ## 覆る条件

    - **`data/views.jsonl` が伸びれば自動で動きます**（定数を持ちません）。
      長尺の n=5 は薄いので、**本が増えたら倍率は動きます。**
    - 中央値ではなく平均を採ると長尺は ×2.53 になります。**中央値のほうが低い**ので、
      **こちらのほうが安全側**です（隔たりを小さく言い過ぎない）。
    - **`settled` では門を作っていません**（下の長い註）。伸びきった形は、
      測れば自分で ×1.00 を出します（ショート 実測 ×1.000・n=22）。
      門にすると、`MATURE_HOURS_BY_FORM` を正しく直した回に**補正が黙って消えます。**
    """
    zero = {"factor": 1.0, "n": 0, "from_hours": None, "to_hours": None,
            "median": 1.0, "mean": 1.0, "why": "測れていません（補正しません）"}

    # --- **憶えの鍵は「同じファイルか」**（2026-08-31・最適化の回に替えた）---
    #
    #     前の版は `views_path is None and forms is None` ＝ **既定の引数で呼んだときだけ**
    #     憶えていました。ところが唯一の呼び手 `per_video_best()` は
    #     **常に `views_path=path, forms=forms` を渡します** ——
    #     **この憶えは一度も当たっていませんでした**（この回に撃って確かめた）。
    #     実測: `python scripts/eta.py --offline` の 150秒 のうち **139.4秒（93%）**が
    #     `per_video_best()` の中（**623回** 呼ばれて、まだ終わっていない）。
    #
    #     鍵をファイルの同一性（道・mtime_ns・大きさ・`forms` の中身・`min_n`）に
    #     替えます。**中身が動けば鍵が変わる**ので、測り直す側は憶えに当たりません。
    #     **鍵は解いた後の値で作ります** —— `censor_factor("長尺")` と
    #     `censor_factor("長尺", forms=measured_forms())` は**同じ答え**なので、
    #     同じ鍵に落ちること（解く前に作ると、同じ答えを2回 測ります）。

    # --- **`settled` で先に返さないこと**（2026-08-31・入れた同じ回に外した）---
    #
    #     最初の版はここに `if _settled(form): return ...` を置いていました。
    #     **黙って補正が消える道**になります:
    #
    #       `_settled()` は `settle.mature_hours_supported(form)` ＝
    #       「その形は **`mature_hours(form)` までに**伸びきるか」です。
    #       ところが打ち切りは形の性質ではなく、**その記録の本が何時間 観測されたか**です。
    #       長尺の記録 `_Mz5rg6jQ_A` は **246時間** までしか観測されていません。
    #       いっぽう長尺が平らになるのは **480時間**（この回の実測）。
    #       次に来た側が `SETTLE_HORIZONS` を延ばして
    #       `MATURE_HOURS_BY_FORM['長尺'] = 480` に直すと —— それは**正しい直し**です ——
    #       `_settled('長尺')` は真になり、**補正が 1.0 に落ちて隔たりが黙って 2倍 に戻ります。**
    #       正しい直しが、別の所を静かに壊す形。
    #
    #     **要りません。** 伸びきっている形は、測れば自分で ×1.00 を出します ——
    #     実測 2026-08-31（ショートの記録の本の年齢 372時間 から）::
    #
    #         372h → 480h  n=22  ×1.000      372h → 720h  n=10  ×1.000
    #         372h → 600h  n=15  ×1.000
    #
    #     **門を1つ減らして、測ったほうだけを残します。** `settled` は
    #     `per_video_best()` が別に返すので、読む側の情報は減りません。

    path = views_path or VIEWS
    forms = _forms.measured_forms() if forms is None else forms
    memo_key = (form, _file_key(path), _forms_key(forms), min_n)
    if memo_key in _CENSOR_MEMO:
        return dict(_CENSOR_MEMO[memo_key])
    if not path.exists():
        return zero

    series: dict[str, list[tuple[float, int]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid, v, h = r.get("id"), r.get("views"), r.get("hours")
        if not vid or v is None or h is None or forms.get(vid) != form:
            continue
        try:
            series.setdefault(vid, []).append((float(h), int(v)))
        except (TypeError, ValueError):
            continue
    if not series:
        return zero
    for s in series.values():
        s.sort()

    # 記録の本と、その本が最後に観測された年齢 A
    rec_id = max(series, key=lambda i: max(v for _, v in series[i]))
    a_hours = series[rec_id][-1][0]
    if a_hours <= 0:
        return zero

    best: dict | None = None
    for t in CENSOR_HORIZONS:
        if t <= a_hours:
            continue
        ratios = []
        for s in series.values():
            a = _nearest(s, a_hours)
            b = _nearest(s, t)
            if a is None or b is None or a <= 0:
                continue
            ratios.append(b / a)
        if len(ratios) < min_n:
            continue
        ratios.sort()
        m = len(ratios)
        best = {
            "factor": max(1.0, ratios[m // 2]),      # **1.0 を下回らせないこと**
            "n": m,
            "from_hours": a_hours,
            "to_hours": t,
            "record_id": rec_id,
            "median": ratios[m // 2],
            "mean": sum(ratios) / m,
            "max": ratios[-1],
            "why": f"{a_hours:.0f}時間（記録の本の最後の読み）→ {t:.0f}時間 の"
                   f"対応のある比・n={m}",
        }
    out = best or dict(zero, from_hours=a_hours, record_id=rec_id,
                       why=f"{a_hours:.0f}時間 より先に n≥{min_n} の地平がありません")
    _CENSOR_MEMO[memo_key] = dict(out)
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
        # **打ち切りを補正した記録で割ること**（2026-08-31・最適化の回の第2手）。
        #     この回まで、ここは `rec["best"]`（＝**下限**）で割っていました。
        #     すぐ下の `settled` で「これは下限です」と**印字だけ**していて、
        #     **補正は誰もしていませんでした**（`censor_factor` の docstring に実測）。
        #     実測 2026-08-31: 長尺 156 → **312**（×2.00）で、隔たりは ×21.4 → **×10.7**。
        #     `record_raw` に生の記録を残します —— **消さないこと**（何を足したかが辿れる）。
        rec_best = float(rec.get("best_settled") or rec["best"])
        cf = rec.get("censor") or {"factor": 1.0}
        yen = ceiling_yen(rec_best, rpm, per_day)
        out.append({"band": band, "form": form, "rpm": rpm,
                    "record": rec_best, "record_raw": rec["best"],
                    "censor_factor": float(cf.get("factor") or 1.0),
                    "censor_n": int(cf.get("n") or 0),
                    "censor_why": str(cf.get("why") or ""),
                    "record_id": rec["id"], "n": rec["n"],
                    "need": need, "ratio": need / rec_best,
                    # **記録が伸びきっていない形では、`ratio` は隔たりの上限です**
                    #     （分母が下限なので、比は必ず上振れします）。
                    "settled": bool(rec.get("settled", False)),
                    "yen": yen, "share": (yen / target_yen) if target_yen else 0.0})
    out.sort(key=lambda r: r["ratio"])
    return out
