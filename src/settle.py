"""**動画の数字は、公開から何時間で確定するか。**（API は 0単位。読むのは手元の控えだけ）

## なぜこのファイルがあるか（2026-08-26・最適化の回に作った）

同じ「いつ確定するか」を、**3か所が別々の数で持っていました。**

    scripts/eta.py      `MATURE_HOURS = 48`   実測つき（n=9・「48時間で伸びが終わります」）
    src/ab_split.py     `SETTLE_DAYS = 7`     **勘**（「初速だけを見ないための日数」）
    config/hypotheses.yaml 「7日以上たっていること」 ×5か所 ／ `settle_days: 7` ×3件

しかも `config/hypotheses.yaml` の密度の前提は、**2026-08-21 に同じことを測って
7日 → 24時間 に書き換えており**、そこにこう書いてあります ——

> **7日で待つと、判定が5日おそくなります。** 腕は閉じた前提でしか動かないので
> （`src/arm_speed.py`）、**5日待つことは、到達日を5日おくらせることと同じです。**

**その1件だけが直り、判定の門そのもの（`SETTLE_DAYS`）は 7日 のまま残っていました。**
`src/judgeable.py` の `ready`（＝すべての前提の「判定できる日」）はこの 7 を足しており、
`eta.py` が毎回「軌跡の腕が動くのは前提を1件閉じたときだけ」と印字している、
その **θ（腕の動く速さ）を 7日 が直接縛っています。**

## 実測（2026-08-26・`data/views.jsonl` と `data/scan.jsonl`）

**再生数**（168時間の値を 100% として。最後の観測が168h以降・168h時点で30再生以上の 21本）:

     6h 中央値  85.7%（最小  9.4%）    48h 中央値 100.0%（最小 81.5%）
    12h 中央値  99.5%（最小 19.7%）    72h 中央値 100.0%（**最小 99.3%**）
    24h 中央値  99.9%（最小 40.3%）   120h 中央値 100.0%（最小 99.9%）

**engaged 比率**（＝判定がじっさいに使う値。`data/scan.jsonl` の 120時間の値との差・20本）:

    60h 中央値 0.38pt（最大 1.02pt）   ρ=0.997    84h 中央値 0.12pt（最大 0.32pt）  ρ=1.000
    72h 中央値 0.16pt（最大 0.64pt）   ρ=0.999    96h 中央値 0.00pt（最大 0.19pt）  ρ=1.000

**「値が動かない」だけでは足りません。判定が入れ替わらないことを直接測りました** ——
標本を無作為に2群へ割り、**t時点の判定と 168h（engaged は 120h）の判定が一致する率**:

    再生（順位和）      24h 86.7%   48h 92.5%   **72h 96.5%**（残りはほぼ引き分け絡み）
    engaged（中央値）   60h 94.8%   **72h 100.0%**   84h 100.0%   96h 100.0%

**96時間 で、判定は動かなくなります。** 7日 待って増えるものは、この標本にはありません。

> **2026-08-28 に 72 → 96 に上げました。** 下の表の「72h」は再生数の話で、
> **判定がじっさいに使う engaged 比率は、72h でまだ 2.63pt 動きます**
> （門は 2pt）。理由と実測は `SETTLE_DAYS` の註に。

## 2つの数がある理由（**同じ量ですが、外し方の向きが逆です**）

    MATURE_HOURS = 48    **標本に入れてよい年齢**（`eta.py` の1本あたり再生の平均）
                         早すぎる本を混ぜると平均が下振れする。48h で中央値100%・
                         下位10% 96.6% なので、数%の下振れと引き換えに標本数を取る
    SETTLE_DAYS  = 4     **判定を待つ日数**（A/B の勝ち負け）
                         こちらは1本でも順位が入れ替わると結論が変わるので、
                         **engaged 比率の最大のずれ**が門（2pt）の内側に入る
                         96h まで待つ（72h は 2.63pt で外）

**片方を触るときは、必ずもう片方を見ること。** 別々のファイルに置いてあったせいで
5日ぶんの待ちが4か月ぶん残りました。

## 覆る条件

- **後から拾われる本が出たら外れ。** この標本（21本）は全部「公開日に立ち上がって
  48時間で止まる」形です。`data/views.jsonl` に **72h 以降で 5% 以上伸びた本**が
  出たら、`SETTLE_DAYS` を上げ直すこと（`views_curve()` が毎回数え直します）
- **長尺には当てていません。** 長尺は1本 4.0回 で標本にならないので、
  ここの数はショートの形です。長尺で判定する前提を置くときは測り直すこと
- **engaged の標本は 24h 未満を覆っていません**（`data/scan.jsonl` は 08/19 から）。
  60h より手前を縮めたいなら、若い本の scan がたまるまで待つこと
"""
from __future__ import annotations

import json
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"
SCAN = ROOT / "data" / "scan.jsonl"

#: **標本に入れてよい年齢**（平均に使う側）。上の表の「48h」。
#:
#: **これはショートの数です**（2026-08-31 に、形で割って測った ——
#: `views_curve(form=...)` の docstring に実測）。**長尺には当たりません。**
#: 形が分かっているときは `mature_hours(form)` を通すこと。
MATURE_HOURS = 48

#: **形ごとの「標本に入れてよい年齢」**（2026-08-31・最適化の回に測って足した）。
#:
#: `MATURE_HOURS = 48` の覆る条件には、はじめからこう書いてありました ——
#: 「**長尺には当てていません。**…長尺で判定する前提を置くときは測り直すこと」。
#: **測り直した結果がこれです**（`views_curve(form=...)` の docstring に全文）::
#:
#:     48h で「伸びきった本」の割合   ショート **96.2%** ／ 長尺 **25.0%**
#:     96h で                        ショート 100.0%   ／ 長尺 **62.5%**
#:
#: **48時間の長尺は、一生ぶんではなく 4〜7割ぶんを持って標本に入ります。**
#: 下振れした長尺の1本あたり再生は、`scripts/eta.py` の `長尺 お金 高` を
#: 実際より遠くに出します —— **その帯は、ショートの天井（`ceiling.value: 1891`）
#: から出る唯一の逃げ道**です（`config/hypotheses.yaml` の `escape_note`）。
#:
#: **96 は下限です。** 168時間を「伸びきった」と置いた上での数で、
#: 長尺 15本は齢 249〜649時間 のあいだに 48h から中央値 ×2.8 伸びています。
#: **標本が増えたら上げ直すこと**（いまの長尺は n=8・`min_views>1`）。
#:
#: **覆る条件**: 長尺の標本が 20本 を超えたとき／`full_at` を 168h より
#: 後ろへ延ばしたとき。どちらもこの数を**上げる**向きにしか動きません。
MATURE_HOURS_BY_FORM: dict[str, int] = {"ショート": 48, "長尺": 96}


def mature_hours(form: str | None = None) -> int:
    """**その形の「標本に入れてよい年齢」**（時間）。

    形が分からなければ `MATURE_HOURS`（＝ショートの数）へ落ちます。
    **落とす先をショートにしているのは、この機械が出している本の大半が
    ショートだから**で、正しいからではありません ——
    形が分かる本は、必ず形を渡すこと。
    """
    if form in MATURE_HOURS_BY_FORM:
        return MATURE_HOURS_BY_FORM[form]
    return MATURE_HOURS

#: **判定を待つ日数**（勝ち負けに使う側）。
#:
#: **2026-08-26 に 7日 → 3日（72h）へ下げ、2026-08-28 に 4日（96h）へ戻しました。**
#: どちらも `falsified_if` のしきい値は1文字も触っていません。
#:
#: ## なぜ 72h では足りなかったか —— **測った量と、守っている量が違いました**
#:
#: 72h を選んだ根拠は上の docstring の
#: 「1本でも順位が入れ替わると結論が変わるので、**最小値**が 99.3% になる
#: 72h まで待つ」でした。**その最小値は再生数のものです。**
#: ところが `tests/test_settle.py` 自身が
#: 「**判定がじっさいに使うのは engaged 比率のほう**」と書いており、
#: `src/ab_split.py` の勝ち負けもそちらで決まります。
#: **守っている量に対して、一度も割っていませんでした。**
#:
#: 実測 2026-08-28（`python -m src.settle`・API 0単位）:
#:
#:     engaged 比率（120h の値との差）
#:        60h  中央値 0.15pt  **最大 3.06pt**  n=17
#:        72h  中央値 0.10pt  **最大 2.63pt**  n=18   ← ここで判定していた
#:        84h  中央値 0.08pt  **最大 2.63pt**  n=28
#:        96h  中央値 0.00pt  **最大 1.01pt**  n=29   ← ここまで待つ
#:
#: 門は「確定値との差が **2pt 未満**」です（`tests/test_settle.py`）。
#: **72h は 2.63pt で、その門を超えています** ——
#: つまり 3日 で出した A/B の勝ち負けは、**入れ替わりえました。**
#:
#: **上げるのは、閉じるのを 1日 遅らせます。** それでも上げるのは、
#: 入れ替わる判定が軌跡に入るほうが高いからです ——
#: `eta.py` は「軌跡の腕が動くのは前提を1件 閉じたときだけ」なので、
#: **間違って閉じた1件は、間違った向きに軌跡を動かして、そのまま残ります。**
#:
#: ## 再生数の側の根拠も、書いた日から動いています
#:
#: docstring の「72h で最小値 99.3%」は 21本 のときの数です。
#: いま（n=39）は **72h で最小 97.6% ／ 120h で 99.3%** ——
#: **数のほうが動いたのであって、書いた回が間違えたのではありません。**
#: **だから毎回 測り直します**（`views_curve()` / `engaged_curve()`）。
#:
#: ## 覆る条件
#:
#: `tests/test_settle.py` の2件が緑のあいだは、この数で足ります。
#: **落ちたら上げること。下げるのは、96h より手前の行が
#: 2回 続けて門の内側に入ったときだけ**（1回で下げると、標本が増えた
#: 次の回にまた上げることになります —— 08/26→08/28 がその形でした）。
SETTLE_DAYS = math.ceil(96 / 24)

#: **形ごとの「判定を待つ日数」**（2026-08-31・最適化の回に測って足した）。
#:
#: `SETTLE_DAYS` は `engaged_curve()` を**形を混ぜて**測った数でした。
#: 混ぜた最大は 17.08pt（門は 2pt）ですが、**そのずれは全部 長尺のもの**です ——
#: 実測（齢 96h ／ 確定 120h）::
#:
#:     ショート  n=49   最大 **1.01pt**   中央 0.00pt   門超え **0本**
#:     長尺      n= 2   最大 17.08pt     中央 9.19pt   門超え  1本
#:
#: **ショートは 96時間 で確定しています。** 長尺は確定しません
#: （`settles_at("長尺")`: どの地平でも伸びきる年齢が出ない）。
#:
#: **長尺をここに載せていないのは、載せる数が無いからです。**
#: `settle_days(None)` / `settle_days("長尺")` は `SETTLE_DAYS` へ落ちます ——
#: **「長尺は 4日 で確定する」という意味ではありません。**
#: 意味は「**長尺で A/B を判定してよい日数は、まだ測れていない**」です。
#: 長尺で判定する前提を置くときは、`settles_at("長尺")` を先に見ること。
SETTLE_DAYS_BY_FORM: dict[str, int] = {"ショート": SETTLE_DAYS}


def settle_days(form: str | None = None) -> int:
    """**その形の「判定を待つ日数」**。

    形が分からなければ `SETTLE_DAYS`（＝ショートの数）へ落ちます。
    **落とす先をショートにしているのは、この機械が出している本の大半が
    ショートだから**で、正しいからではありません（`mature_hours()` と同じ扱い）。
    """
    if form in SETTLE_DAYS_BY_FORM:
        return SETTLE_DAYS_BY_FORM[form]
    return SETTLE_DAYS


#: Analytics の遅れが読めなかったときの控え。**0 にしないこと** ——
#: 0 は「遅れは無い」と言い切ることで、いちばん危ない側へ倒れます。
ANALYTICS_LAG_FALLBACK = 3


def analytics_lag_days(as_of: date | None = None) -> int:
    """**実データ（Analytics）が何日 遅れているか。**`data/analytics_lag.jsonl` の実測。

    **ここにも同じ穴がありました（2026-08-26）。**

        scripts/deadline_check.py  実測（`analytics_lag.jsonl` の最終日から数える）→ **4日**
        src/judgeable.py           `ANALYTICS_LAG_DAYS = 3` の**べた書き**   → **3日**

    そして A/B 4件の判定日を出すのは `judgeable` のほうなので、
    **A/B だけ1日 楽観**に出ていました。楽観のほうへ期限を寄せると、
    **その日にはまだ来ていないデータで判定する**ことになります
    （`falsified_if` は「上回らなければ外れ」なので、**外れ側に倒れます**）。
    """
    path = ROOT / "data" / "analytics_lag.jsonl"
    today = as_of or datetime.now(timezone(timedelta(hours=9))).date()
    try:
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        # **過去の日を訊かれたら、その日に見えていた分だけで答えること**
        # （2026-08-29・最適化の回に踏んだ）。
        #
        # ここは長らく `max(last_day)` を**台帳ぜんたい**から採っていました。
        # 台帳には毎周 行が積まれるので、**過去の `as_of` を渡すと、その日には
        # まだ存在しなかった観測まで混ざります。**
        # 実測: `analytics_lag_days(date(2026,8,26))` → **0日**
        # （台帳の最新 `last_day` が 08/26 なので、08/26 − 08/26 ＝ 0）。
        # **「遅れは無い」と言い切る形**で、`ANALYTICS_LAG_FALLBACK` の註が
        # 「**0 にしないこと** —— いちばん危ない側へ倒れます」と禁じている、
        # その値そのものです。
        #
        # 何が壊れるか: `readable_by(as_of, s)` が
        # `as_of - (settle + lag)` なので、**lag が 0 に落ちると
        # 判定の締切が 3日 うしろへ伸びます** —— つまり
        # **まだ読めていないデータで判定する**側へ倒れます。
        # このファイル自身が「A/B だけ**1日 楽観**に出ていました。
        # 楽観のほうへ期限を寄せると、その日にはまだ来ていないデータで
        # 判定することになります（`falsified_if` は「上回らなければ外れ」なので、
        # **外れ側に倒れます**）」と書いている、その 3日 版です。
        #
        # **覆る条件**: 台帳の行から `at` が消えたら、この絞り込みは効きません
        # （そのときは `ANALYTICS_LAG_FALLBACK` へ落ちます。0 にはしないこと）。
        seen = [r for r in rows
                if str(r.get("at", ""))[:10] and date.fromisoformat(str(r["at"])[:10]) <= today]
        use = seen or ([] if as_of is not None else rows)
        if not use:
            return ANALYTICS_LAG_FALLBACK
        last = max(r["last_day"] for r in use)
        return max(0, (today - date.fromisoformat(last)).days)
    except Exception:                                          # noqa: BLE001
        return ANALYTICS_LAG_FALLBACK


#: 遅れの帯を測る窓（日）。**短すぎると段差をまたがず、幅 0 に見えます。**
LAG_BAND_WINDOW_DAYS = 14


def analytics_lag_band(window_days: int = LAG_BAND_WINDOW_DAYS,
                       path: Path | None = None) -> dict:
    """**遅れは1日の中で動きます。その幅（日）を実測で返す。**（2026-08-26）

    `analytics_lag_days()` は「いま何日 遅れているか」の**点**を返します。
    ところが Analytics は日の途中で新しい日を出すので、**同じ日でも
    早い時刻に走った回は 4日、遅い時刻の回は 3日**を見ます。

    実測（`data/analytics_lag.jsonl` 438観測）: **3日が 381・4日が 57**。
    **1日のうちに 3 と 4 の両方を観測した日が 6日**あります
    （08/18・08/19・08/20・08/21・08/22・08/26）。

    **これは誤差ではなく段差です。** そして `scripts/deadline_check.py` の
    判定日は、この遅れをそのまま足して作られています。だから

        02時に走った回  → 判定できるのは **09-02**
        06時に走った回  → 判定できるのは **09-01**

    と出て、**どちらの回も「期限が1日 ずれています。書き換えること」と言います。**
    書き換えると、次の回が逆向きに書き換えます。

    **`Answer.slack` は、まさにこれを止めるために置かれた欄です**
    （docstring: 「3回ぶんの `fix` は、到達日を1日も動かしていない churn です」）。
    ただし置かれた先は伸び率の推定（`accrual`）だけで、
    **遅れを足す側（`after` / `published_group` / `group_key`）には
    掛かっていませんでした。** 帯を出すのがこの関数です。

    返すのは `{"lag": いまの点, "lo": 最小, "hi": 最大, "band": hi-lo, "n": 観測数}`。
    観測が足りない回は `band=0`（＝帯を主張しない。**黙って広げないこと**）。
    """
    p = path or (ROOT / "data" / "analytics_lag.jsonl")
    now = datetime.now(timezone(timedelta(hours=9))).date()
    lags: list[int] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            at = date.fromisoformat(str(r["at"])[:10])
            if (now - at).days > window_days:
                continue
            lags.append(max(0, (at - date.fromisoformat(r["last_day"])).days))
    except Exception:                                          # noqa: BLE001
        lags = []
    if len(lags) < 2:
        return {"lag": analytics_lag_days(), "lo": 0, "hi": 0, "band": 0, "n": len(lags)}
    lo, hi = min(lags), max(lags)
    return {"lag": analytics_lag_days(), "lo": lo, "hi": hi, "band": hi - lo, "n": len(lags)}


def _publish_times(path: Path | None = None) -> dict[str, float]:
    """`video_id` → 公開時刻（epoch秒）。`data/views.jsonl` の `at - hours` から。"""
    seen: dict[str, list[float]] = {}
    text = (path or VIEWS).read_text(encoding="utf-8") if (path or VIEWS).exists() else ""
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            at = datetime.fromisoformat(str(row["at"]).replace("Z", "+00:00"))
            seen.setdefault(row["id"], []).append(at.timestamp() - float(row["hours"]) * 3600)
        except (ValueError, KeyError, TypeError):
            continue
    return {k: statistics.median(v) for k, v in seen.items()}


def _series(path: Path | None = None) -> dict[str, list[tuple[float, float]]]:
    """`video_id` → [(年齢h, 再生数)]。壊れた行は落とす（読みの事故で判定を止めない）。"""
    out: dict[str, list[tuple[float, float]]] = {}
    src = path or VIEWS
    if not src.exists():
        return out
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            out.setdefault(row["id"], []).append((float(row["hours"]), float(row["views"])))
        except (ValueError, KeyError, TypeError):
            continue
    return out


def value_at(obs: list[tuple[float, ...]], hours: float) -> tuple[float, ...] | None:
    """年齢 `hours` の値（前後の観測から線形補間）。**覆っていなければ None。**

    読みは1本ずつ時刻がずれるので、ちょうどの点はありません。**外挿はしません** ——
    最後の観測より後ろを埋めると、伸びていないのに伸びたことになります。
    """
    pts = sorted(obs)
    if not pts or pts[0][0] > hours or pts[-1][0] < hours:
        return None
    prev = pts[0]
    for pt in pts:
        if pt[0] >= hours:
            if pt[0] == prev[0]:
                return tuple(pt[1:])
            f = (hours - prev[0]) / (pt[0] - prev[0])
            return tuple(p + f * (c - p) for p, c in zip(prev[1:], pt[1:]))
        prev = pt
    return tuple(pts[-1][1:])


def views_curve(ages: tuple[float, ...] = (24, 48, 72, 168), *, full_at: float = 168.0,
                min_views: float = 30.0, path: Path | None = None,
                form: str | None = None) -> dict[float, dict]:
    """**年齢ごとに「伸びきった値の何割か」**。`data/views.jsonl` だけを読む（API 0単位）。

    標本は「最後の観測が `full_at` 時間以降」かつ「その時点で `min_views` 超え」の本。
    薄い本を入れると 0/0 や 1再生の本が比を暴れさせます。

    `form` に `"ショート"` / `"長尺"` を渡すと、**その形の本だけ**で数え直します
    （`data/video_forms.json` の実測。形の分からない本は**どちらにも入りません**）。
    **渡さなければ、これまでどおり形を混ぜます** —— 既定を変えていないのは、
    `tests/test_settle.py` の門がその混ぜた数の上に立っているからです。

    ## **なぜ形で割れるようにしたか**（2026-08-31・最適化の回に測った）

    このファイルの冒頭は `MATURE_HOURS = 48` に「48時間で伸びが終わります」と
    書き、**覆る条件に「長尺には当てていません…長尺で判定する前提を置くときは
    測り直すこと」**と書いてあります。**測り直していませんでした。**

    **実測（`min_views` を落として形で割った。API 0単位）**::

        48h の時点で「伸びきった本」の割合
          ショート  **96.2%**（n=79・min_views>30）  ／ 中央値 100.1%
          長尺      **25.0%**（n=8 ・min_views>1 ）  ／ 中央値  73.2%
        96h の時点
          ショート  100.0%                            長尺  **62.5%** ／ 中央値 100.0%

    **48時間は、ショートの数です。** 長尺に当てると、その本は
    **一生ぶんではなく 4〜7割ぶん**を持って標本に入ります。

    ## **`SETTLED_SHARE_FLOOR` の註が「外れ1本」と呼んでいる本の正体**

    下の註は `_Mz5rg6jQ_A`（96h で 51.1%）を
    「**48再生 の本の比です。分母が小さいので**」と、標本の薄さのせいにしています。
    **その本は、この標本にいる唯一の長尺です**（`min_views>30` の長尺は n=1）。
    **薄さではなく、形です。** 同じファイルの2か所が別のことを言っていて、
    **打ち消すほうが勝っていました** —— この repo がいちばんよく踏む形。

    ## **これは効き目のある所です**

    長尺の1本あたり再生を下振れさせると、`scripts/eta.py` の
    `長尺 お金 高` の帯が実際より遠くに出ます。**その帯は、ショートの天井
    （`ceiling.value: 1891`）から出る唯一の逃げ道**です
    （同じ `ceiling:` の `escape_note`）。**逃げ道を、合わない物差しで測っている**形。

    ## 覆る条件

    - 長尺の標本が 20本 を超えたら数え直すこと（いまは **n=8**・`min_views>1`）。
      **`min_views` を落として数えていること自体が弱点**です —— 長尺の絶対数が
      小さいので 30 では n=1 になります
    - **168時間 を「伸びきった」と置いているのも、長尺には短い**見込みです
      （齢 249〜649時間 の長尺 15本は、48h から中央値 ×2.8 伸びています）。
      **ここが伸びるほど、上の割合はさらに下がります**
    """
    series = _series(path)
    if form is not None:
        try:
            from . import forms as _forms
            known = _forms.measured_forms()
        except Exception:                                      # noqa: BLE001
            known = {}
        series = {k: v for k, v in series.items() if known.get(k) == form}
    sample = {k: v for k, v in series.items()
              if v and max(h for h, _ in v) >= full_at
              and (value_at(v, full_at) or (0,))[0] > min_views}
    out: dict[float, dict] = {}
    for age in ages:
        shares = []
        for obs in sample.values():
            now, full = value_at(obs, age), value_at(obs, full_at)
            if now is None or full is None or full[0] <= 0:
                continue
            shares.append(now[0] / full[0])
        if shares:
            shares.sort()
            settled = sum(1 for x in shares if x >= SETTLED_SHARE_FLOOR)
            out[age] = {"n": len(shares), "median": statistics.median(shares),
                        "p10": shares[max(0, int(len(shares) * 0.1))], "min": min(shares),
                        # **`min` を門にしないための欄**（2026-08-29 に足した。下の註）
                        "share_settled": settled / len(shares),
                        "n_unsettled": len(shares) - settled}
    return out


#: **「伸びきった」と呼ぶ割合。** `share_settled` の分子の条件。
SETTLED_SHARE_FLOOR = 0.95


#: `settles_at()` が `full_at` に当てていく地平（時間）。**短い順**。
#:
#: **なぜ1つではないか**（2026-08-31・最適化の回に測って足した）。
#: `views_curve` の既定 `full_at=168.0` は「168時間で伸びきった」と**置いた**数です。
#: 同じ関数の覆る条件が、自分でこう書いています ——
#:
#: > **168時間 を「伸びきった」と置いているのも、長尺には短い**見込みです。
#: > **ここが伸びるほど、上の割合はさらに下がります**
#:
#: **地平を延ばして当ててみるまで、その「置いた」が効いているか分かりません。**
#: 下の `settles_at()` は、地平ごとに当て直して**答えが変わるかどうか**を見ます。
SETTLE_HORIZONS: tuple[float, ...] = (168.0, 240.0, 336.0, 480.0)

#: `settles_at()` が当てる年齢（時間）。**短い順**。
SETTLE_AGES: tuple[float, ...] = (24.0, 48.0, 72.0, 96.0, 120.0, 168.0, 240.0, 336.0)


def settles_at(form: str | None = None, *, min_views: float = 1.0,
               floor: float = SETTLED_SHARE_FLOOR,
               horizons: tuple[float, ...] = SETTLE_HORIZONS,
               path: Path | None = None) -> dict:
    """**その形は、何時間で伸びきるか。地平を延ばしても同じ答えか。**（API 0単位）

    `views_curve` を `full_at` を変えながら当て直し、**地平ごとに
    「`share_settled` が `floor` を超える最小の年齢」**を出します。

    返り::

        by_horizon  {地平: {"hours": 年齢 or None, "n": 本数}}
        hours       **いちばん長い地平**で出た年齢（`None` ＝ そこでは伸びきらない）
        supported   `hours` が `None` でなく、**どの地平でも同じ**か
        stable      地平をまたいで答えが動かなかったか

    ## なぜ「いちばん長い地平」を採るか

    地平が年齢より短いと、比の分母が**まだ伸びている途中の値**になり、
    割合は**必ず上振れ**します（分母が小さいので）。
    **地平を延ばすほど、割合は下がるか、そのまま**です。
    だからいちばん長い地平の答えが、いちばん甘くない答えです。

    ## 実測（2026-08-31・`data/views.jsonl` 22,442点。**API 0単位**）

    `share_settled`（＝ `floor` を超えた本の割合）::

        地平    形        24h   48h   72h   96h  120h  168h  240h  336h    n
        168h  ショート    61%   81%   89%   91%   92%  100%  100%  100%   99
        168h  長尺        12%   25%   38%   62%   62%  100%  100%  100%    8
        240h  長尺         0%   12%   25%   50%   50%   50%  100%  100%    8
        336h  長尺         0%    0%    0%    0%    0%    0%    0%  100%    5
        480h  長尺         0%    0%    0%    0%    0%    0%    0%    0%    5
        480h  ショート    57%  100%  100%  100%  100%  100%  100%  100%    9

    **ショートは、どの地平でも 72時間 で 100% です**（地平を延ばしても動きません）。
    **長尺は、地平を延ばすと答えが消えます** —— 336時間 を「伸びきった」と置くと、
    **240時間 の時点で伸びきっている長尺は 0本**。480時間 なら 336時間 でも 0本。

    **`MATURE_HOURS_BY_FORM["長尺"] = 96` は、`full_at=168` からだけ出る数**でした。
    168 は長尺の伸びの**途中**なので、その 62% は分母が小さいぶんの上振れです。
    **地平を延ばすと 50% → 0% と消えます。この標本に、長尺が伸びきる年齢はありません。**

    ## これが効く所

    `scripts/eta.py` は `drop_unripe` で **齢 96時間 の長尺を「一生ぶん」として
    標本に入れ**、`long_per_video`（いま 16.0回/本）と長尺の記録（156回/本）を作ります。
    その2つが `長尺 お金 高` の帯を作り、**`src/form_record` の ×21.4 ——
    この機械が持っている「形をまたがない」いちばん小さい隔たり**になります。
    **上の表は、その ×21.4 の分母が伸びきっていないことを示します** ——
    ×21.4 は隔たりの**上限**であって、実測の隔たりではありません。

    ## 覆る条件

    - **長尺が伸びきる年齢が1つでも出たら。** そのとき `hours` が `None` でなくなり、
      `supported` が真になります。**この関数は定数を持たないので、自動で追います**
    - 長尺の標本が増えたとき（いま n=5〜8）。`min_views` を上げられるようになります
    - **`data/views.jsonl` が古い長尺を観測しなくなったら、この関数は黙って
      「地平が足りない」側へ倒れます。** 齢 649時間 の長尺がまだ積まれていることが前提

    ## **言えないこと —— 「形のせい」だとは、まだ言えません**

    **2026-08-31 に、再生数をそろえて比べようとして できませんでした。**
    地平 240時間 の本を「240h 時点の再生数」の帯で割ると、**重なりがありません**::

        帯（240hの再生）   ショート n   96h 中央    長尺 n   96h 中央
          60〜150              **0**       —          1      **30%**
         150〜400               16      **100%**   **0**       —
         400〜2000              33      **100%**   **0**       —

    **ショートは 150回 以上にしか居らず、長尺は 150回 未満にしか居ません。**
    だから「**長尺だから伸びきらない**」のか「**再生数が小さいから伸びきらない**」のかを、
    このデータでは**分離できません**（少ない再生では 1回 増えるだけで割合が大きく動きます）。

    **数のある1本だけは、その言い訳が効きません** ——
    `_Mz5rg6jQ_A`（240h で **132回**）は **24h 0% ／ 96h 30% ／ 168h 62%**。
    同じ 150〜400回 のショート 16本 は **96h で 100%** です。
    **n=1 なので、これは示唆であって証拠ではありません。**

    **それでも、この関数が返す `supported=False` は正しいまま**です ——
    理由が形であれ再生数の小ささであれ、**長尺の1本あたり再生が
    打ち切られている（一生ぶんではない）ことは変わりません。**
    分からないのは**なぜか**のほうで、`scripts/eta.py` が使うのは
    「その数を天井として信じてよいか」だけです。

    **分離できるようになる条件**: 150回 を超える長尺が 2本 出たとき。
    そのとき同じ帯でショートと並べられます。**それまで「形のせい」と書かないこと。**
    """
    by_horizon: dict[float, dict] = {}
    for full_at in horizons:
        ages = tuple(a for a in SETTLE_AGES if a <= full_at)
        if not ages:
            continue
        try:
            c = views_curve(ages, full_at=full_at, min_views=min_views,
                            path=path, form=form)
        except Exception:                                      # noqa: BLE001
            continue
        if not c:
            continue
        hit = next((a for a in ages
                    if a in c and c[a]["share_settled"] >= floor), None)
        by_horizon[full_at] = {"hours": hit,
                               "n": max(v["n"] for v in c.values())}
    if not by_horizon:
        return {"by_horizon": {}, "hours": None, "supported": False, "stable": False}
    longest = max(by_horizon)
    hours = by_horizon[longest]["hours"]
    answers = {v["hours"] for v in by_horizon.values()}
    return {"by_horizon": by_horizon, "hours": hours,
            "supported": hours is not None,
            "stable": len(answers) == 1}


def mature_hours_supported(form: str | None = None, **kw) -> bool:
    """**`mature_hours(form)` が実測で裏づいているか。**（API 0単位）

    真 ＝ その形は、いちばん長い地平でも `mature_hours(form)` までに伸びきっている。
    **偽 ＝ その形の1本あたり再生は、打ち切られた下限です**（一生ぶんではない）。

    実測 2026-08-31: **ショート 真（72h で 100%）／ 長尺 偽**。
    """
    s = settles_at(form, **kw)
    if not s["supported"]:
        return False
    return s["hours"] is not None and s["hours"] <= mature_hours(form)

#: **`min` を門にしないこと**（2026-08-29・最適化の回に測って足した）。
#:
#: `tests/test_settle.py` は長らく `row["min"] >= 0.95` を門にしていました。
#: **標本が増えるほど、この門は勝手に厳しくなります** —— `min` は n が増えれば
#: 単調に下がるので、**何も悪くなっていない回でも、いつか必ず落ちます。**
#:
#: 実測 2026-08-29（n=60・96h）::
#:
#:     中央値 1.0000   p10 0.9967   **min 0.5105**
#:     0.95 を下回る本  **1本 / 60本（1.7%）**
#:     その1本 `_Mz5rg6jQ_A` …… 96h で **48再生** → 168h で 94再生
#:
#: **48再生 の本の比です。** 分母が小さいので、あと数十再生 拾われただけで
#: 比が半分になります。
#:
#: > **【2026-08-31 の訂正】薄さではありません。形です。**
#: > `_Mz5rg6jQ_A` は **長尺**で、`min_views>30` の標本にいる**唯一の長尺**です
#: > （`data/video_forms.json` の実測）。同じ標本のショート 79本 は 48h で
#: > **96.2%** が伸びきっており、長尺は 96h でも **62.5%**（n=8）。
#: > **「外れ1本」ではなく、長尺そのものの形**でした ——
#: > `MATURE_HOURS` の覆る条件が最初からそう書いています
#: > （「長尺には当てていません」）。**打ち消す側の註が勝っていた**形で、
#: > この repo がいちばんよく踏むもの（同じファイルの2か所が別のことを言い、
#: > 片方しか読まれない）。数え直す口は `views_curve(form=...)`、
#: > 形ごとの年齢は `MATURE_HOURS_BY_FORM` / `mature_hours(form)`。
#: > **上の「`min` を門にしないこと」自体は、いまも正しい**（理由が入れ替わった
#: > だけで、`min` が n とともに単調に下がるのは変わりません）。
#:
#: **その1本のために `SETTLE_DAYS` を 4 → 7 に上げると、
#: 開いている前提 27件 の判定日が全部 +3日 動きます** ——
#: このファイル自身が「**5日待つことは、到達日を5日おくらせることと同じ**」と
#: 書いている、その 3日 ぶんです。
#:
#: 同じ日に `scripts/trajectory.py` でも同じ形を1つ直しました
#: （後ろカタログの門が、4読みしかない尾の1バケツで赤くなっていた）。
#: **どちらも「極値を、増える標本の門にした」形です。**
#:
#: ## だから門は3つに割ります（**どれも隠さず印字する**）
#:
#:     median          全体が伸びきっているか        ≥ 0.99
#:     p10             下位10% でも伸びきっているか   ≥ 0.95
#:     share_settled   0.95 以上の本が何割か          ≥ 0.95（＝外れは 5% まで）
#:
#: **`min` は今までどおり出します。** 門から外すのと、見えなくするのは別です。
#:
#: ## 覆る条件
#:
#: - **`share_settled` が 0.95 を割ったら、それは本物**（外れが 3本/60本 を超えた）。
#:   そのときは `SETTLE_DAYS` を上げること
#: - `min` が下がっただけの回は上げないこと。**まず何本 外れているかを数える**
#: - engaged 側の門（`engaged_curve()` の `max`）は**そのまま `max` で置きます** ——
#:   あちらは pt 差（絶対値）なので、分母の小ささで暴れません


def engaged_curve(ages: tuple[float, ...] = (60, 72, 96), *, full_at: float = 120.0,
                  min_views: float = 30.0,
                  form: str | None = None) -> dict[float, dict]:
    """**engaged 比率が、確定値からどれだけ離れているか**（pt）。`data/scan.jsonl` を読む。

    判定がじっさいに使うのはこちらの値です。`scan.jsonl` は 08/19 からなので、
    **若い本ほど標本に入りません**（覆っている帯は 60h〜120h）。

    `form` に `"ショート"` / `"長尺"` を渡すと、**その形の本だけ**で数え直します
    （`views_curve(form=...)` と同じ形。形の分からない本はどちらにも入りません）。
    **渡さなければ、これまでどおり形を混ぜます。**

    ## **なぜ形で割れるようにしたか**（2026-08-31・最適化の回に測った）

    `tests/test_settle.py::test_engaged_比率もその時点で確定している` が
    **落ちていました** —— 「確定値から最大 **17.08pt** ずれています ——
    この年齢では判定が入れ替わります。**`SETTLE_DAYS` を上げ直すこと**」。

    **上げてはいけません。** 形で割ると、そのずれは全部 長尺のものです
    （実測 2026-08-31・齢 96h ／ 確定 120h・門 2.00pt）::

        形        n    最大ずれ   中央    門(2pt)超え
        ショート  49    1.01pt   0.00pt      **0本**
        長尺       2   17.08pt   9.19pt        1本

    外れの正体は `13TynquQzQU`（長尺）で、**96h → 120h のあいだに再生が
    30 → 82 に増えています**（判定の窓の中で 2.7倍）。同じ本は
    `views.jsonl` でも齢 117時間 で 16 → 121回（×7.56）と伸び続けており、
    `settles_at("長尺")` が「**どの地平でも伸びきらない**」と出す本そのものです。

    ## **上げると、到達日が遠のきます**

    `SETTLE_DAYS` は「判定を待つ日数」で、`src/judgeable.py` の
    「判定できる日」に足されます。`scripts/eta.py` は毎回
    **「軌跡の腕が動くのは、前提を1件 閉じたときだけ」**と印字するので、
    **待つ日数はそのまま θ（腕の動く速さ）の分母**です。

    **長尺2本のために上げると、ショートの A/B 49本ぶんが道連れで遅くなります。**
    このファイルの冒頭が 2026-08-26 に書いたのと同じ形 ——
    「**5日待つことは、到達日を5日おくらせることと同じです**」。

    **落ちていた検査が言っていたのは「上げろ」ではなく「形で割れ」でした。**

    ## 覆る条件

    - **ショートのずれが 2pt を超えたとき。** そのときは本当に上げること
    - 長尺の標本が増えたとき（いま n=2）。**2本で門を動かさないこと**
    """
    pub = _publish_times()
    if not SCAN.exists():
        return {}
    series: dict[str, list[tuple[float, float, float]]] = {}
    for line in SCAN.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            at = datetime.fromisoformat(row["at"]).timestamp()
            vals = row["values"]
        except (ValueError, KeyError, TypeError):
            continue
        for key in vals:
            if not key.startswith("動画.") or not key.endswith(".engagedViews"):
                continue
            vid = key.split(".")[1]
            v = vals.get(f"動画.{vid}.views")
            if v is None or vid not in pub:
                continue
            age = (at - pub[vid]) / 3600
            if age >= 0:
                series.setdefault(vid, []).append((age, float(v), float(vals[key])))
    if form is not None:
        try:
            from . import forms as _forms
            known = _forms.measured_forms()
        except Exception:                                      # noqa: BLE001
            known = {}
        series = {k: v for k, v in series.items() if known.get(k) == form}
    sample = {k: v for k, v in series.items()
              if max(a for a, _, _ in v) >= full_at
              and (value_at(v, full_at) or (0,))[0] >= min_views}
    out: dict[float, dict] = {}
    for age in ages:
        diffs = []
        for obs in sample.values():
            now, full = value_at(obs, age), value_at(obs, full_at)
            if now is None or full is None or now[0] <= 0 or full[0] <= 0:
                continue
            diffs.append(abs(now[1] / now[0] - full[1] / full[0]))
        if diffs:
            out[age] = {"n": len(diffs), "median": statistics.median(diffs), "max": max(diffs)}
    return out


def report() -> str:
    """人が読む形。`python -m src.settle` で出ます（**次に来た側が測り直す口**）。"""
    lines = [f"=== 数字はいつ確定するか（実測・API 0単位）===",
             f"  いま使っている数: 標本に入れる年齢 {MATURE_HOURS}時間 ／ "
             f"判定を待つ日数 **{SETTLE_DAYS}日**（{SETTLE_DAYS * 24}時間）"]
    curve = views_curve((12, 24, 48, 72, 96, 120))
    lines.append("  --- 再生数（168時間の値を100%として）---")
    for age, row in sorted(curve.items()):
        lines.append(f"    {age:>5.0f}h  中央値 {row['median']*100:6.1f}%  "
                     f"下位10% {row['p10']*100:6.1f}%  最小 {row['min']*100:6.1f}%  "
                     f"伸びきった本 {row['share_settled']*100:5.1f}%"
                     f"（外れ {row['n_unsettled']}本）  n={row['n']}")
    # --- **形で割る**（2026-08-31）。上の1本の表は、形を混ぜた数です ---
    #     混ぜた表は n の大半がショートなので、**長尺の形が1本も見えません。**
    #     「外れ 1本」として下に消えていたのが、標本にいる唯一の長尺でした。
    lines.append("  --- **同じ表を、形で割ったもの**（`data/video_forms.json` の実測）---")
    for form, mv in (("ショート", 30.0), ("長尺", 1.0)):
        c = views_curve((24, 48, 72, 96), min_views=mv, form=form)
        head = (f"    {form}（{mv:.0f}再生 超えの本だけ・"
                f"いま当てている年齢 **{mature_hours(form)}時間**）")
        if not c:
            lines.append(head + " …… **標本がありません**")
            continue
        lines.append(head)
        for age, row in sorted(c.items()):
            lines.append(f"      {age:>4.0f}h  中央値 {row['median']*100:6.1f}%  "
                         f"伸びきった本 {row['share_settled']*100:5.1f}%  n={row['n']}")
    lines.append("    [!] **48時間は「ショートの数」です。** 長尺に当てると、その本は"
                 "**一生ぶんではなく4〜7割ぶん**を持って標本に入り、"
                 "**1本あたり再生が下振れ**します —— `scripts/eta.py` の"
                 " `長尺 お金 高` は、ショートの天井から出る**唯一の逃げ道**なので、"
                 "そこを合わない物差しで測ることになります"
                 "（出どころは `MATURE_HOURS_BY_FORM`・`mature_hours(form)`）。")
    lines.append("    **長尺の 96時間 は下限です** —— 168時間 を「伸びきった」と"
                 "置いた上での数で、齢 249〜649時間 の長尺 15本は"
                 " 48h から中央値 **×2.8** 伸びています。**標本が増えたら上げ直すこと。**")
    eng = engaged_curve((60, 72, 84, 96))
    if eng:
        lines.append("  --- engaged 比率（120時間の値との差・pt）---")
        for age, row in sorted(eng.items()):
            lines.append(f"    {age:>5.0f}h  中央値 {row['median']*100:5.2f}pt  "
                         f"最大 {row['max']*100:5.2f}pt  n={row['n']}")
        # --- **その「最大」が、どの形のものか**（2026-08-31・最適化の回に足した）---
        #     上の行は形を混ぜています。混ぜた最大を見て `SETTLE_DAYS` を上げると、
        #     **長尺 数本のために ショートの A/B 数十本ぶんが道連れで遅くなります。**
        #     `SETTLE_DAYS` は `src/judgeable.py` の「判定できる日」に足され、
        #     `scripts/eta.py` は毎回「軌跡の腕が動くのは前提を1件 閉じたときだけ」と
        #     印字するので、**待つ日数はそのまま θ の分母**です。
        #     （`tests/test_settle.py::test_engaged_比率もその時点で確定している` が
        #       まさにその文面で赤になっていた。**上げるのではなく形で割るのが答え**でした）
        _age = float(SETTLE_DAYS * 24)
        _by = {}
        for _f in ("ショート", "長尺"):
            try:
                _r = engaged_curve((_age,), form=_f).get(_age)
            except Exception:                                  # noqa: BLE001
                _r = None
            if _r:
                _by[_f] = _r
        if _by:
            lines.append(f"    **その最大が どの形のものか**（{_age:.0f}h・門 2.00pt）:")
            for _f, _r in _by.items():
                _over = "**門超え**" if _r["max"] >= 0.02 else "門の内側"
                lines.append(f"      {_f:<4} n={_r['n']:>3}  最大 {_r['max']*100:6.2f}pt  "
                             f"中央 {_r['median']*100:5.2f}pt  {_over}")
            _sh = _by.get("ショート")
            if _sh and _sh["max"] < 0.02:
                lines.append("    [!] **ショートは門の内側です。混ぜた最大で "
                             "`SETTLE_DAYS` を上げないこと** —— 上げると"
                             "ショートの A/B が長尺の道連れで遅くなり、**θ が下がります**"
                             "（`SETTLE_DAYS_BY_FORM` / `settle_days(form)` を使うこと）。")
    hit = curve.get(float(SETTLE_DAYS * 24))
    if hit:
        # **門と同じ量を印字すること**（2026-08-29 に直した）。
        #   ここは長らく `min` だけを見て「上げ直すこと」を出しており、
        #   **門（`tests/test_settle.py`）も `min` でした** ——
        #   標本が増えれば必ず落ちる形です。いまは3つ並べます。
        lines.append(f"  → {SETTLE_DAYS*24}時間 の時点で: 中央値 "
                     f"**{hit['median']*100:.1f}%** ／ 下位10% **{hit['p10']*100:.1f}%** ／ "
                     f"伸びきった本 **{hit['share_settled']*100:.1f}%**"
                     f"（外れ {hit['n_unsettled']}本 / {hit['n']}本）")
        lines.append(f"     （いちばん遅い本は {hit['min']*100:.1f}% ですが、"
                     "**`min` は門ではありません** —— 標本が増えれば単調に下がるので、"
                     "何も悪くなっていない回でも必ずいつか割ります。"
                     "`SETTLED_SHARE_FLOOR` の註に実測）")
        if hit["p10"] < 0.95 or hit["share_settled"] < 0.95:
            lines.append("  [!] **後から拾われる本が出ています**（下位10% か 外れの割合が門を割った）"
                         " —— `SETTLE_DAYS` を上げ直すこと（上の「覆る条件」）")
        else:
            lines.append("  → **この日数で足ります。**（中央値・下位10%・外れの割合とも門の内側）")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    print(report())
