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

**72時間 で、判定は動かなくなります。** 7日 待って増えるものは、この標本にはありません。

## 2つの数がある理由（**同じ量ですが、外し方の向きが逆です**）

    MATURE_HOURS = 48    **標本に入れてよい年齢**（`eta.py` の1本あたり再生の平均）
                         早すぎる本を混ぜると平均が下振れする。48h で中央値100%・
                         下位10% 96.6% なので、数%の下振れと引き換えに標本数を取る
    SETTLE_DAYS  = 3     **判定を待つ日数**（A/B の勝ち負け）
                         こちらは1本でも順位が入れ替わると結論が変わるので、
                         **最小値**が 99.3% になる 72h まで待つ

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
MATURE_HOURS = 48

#: **判定を待つ日数**（勝ち負けに使う側）。上の表の「72h」＝ 3日。
#: **7日 から下げました（2026-08-26）。緩めたのではありません** ——
#: `falsified_if` のしきい値は1文字も動かしていません。動かしたのは待つ時間だけで、
#: 実測が「72時間で判定は入れ替わらない」と言っているぶんを削りました。
SETTLE_DAYS = math.ceil(72 / 24)


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
    try:
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        last = max(r["last_day"] for r in rows)
        today = as_of or datetime.now(timezone(timedelta(hours=9))).date()
        return max(0, (today - date.fromisoformat(last)).days)
    except Exception:                                          # noqa: BLE001
        return ANALYTICS_LAG_FALLBACK


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
                min_views: float = 30.0, path: Path | None = None) -> dict[float, dict]:
    """**年齢ごとに「伸びきった値の何割か」**。`data/views.jsonl` だけを読む（API 0単位）。

    標本は「最後の観測が `full_at` 時間以降」かつ「その時点で `min_views` 超え」の本。
    薄い本を入れると 0/0 や 1再生の本が比を暴れさせます。
    """
    series = _series(path)
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
            out[age] = {"n": len(shares), "median": statistics.median(shares),
                        "p10": shares[max(0, int(len(shares) * 0.1))], "min": min(shares)}
    return out


def engaged_curve(ages: tuple[float, ...] = (60, 72, 96), *, full_at: float = 120.0,
                  min_views: float = 30.0) -> dict[float, dict]:
    """**engaged 比率が、確定値からどれだけ離れているか**（pt）。`data/scan.jsonl` を読む。

    判定がじっさいに使うのはこちらの値です。`scan.jsonl` は 08/19 からなので、
    **若い本ほど標本に入りません**（覆っている帯は 60h〜120h）。
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
                     f"下位10% {row['p10']*100:6.1f}%  最小 {row['min']*100:6.1f}%  n={row['n']}")
    eng = engaged_curve((60, 72, 84, 96))
    if eng:
        lines.append("  --- engaged 比率（120時間の値との差・pt）---")
        for age, row in sorted(eng.items()):
            lines.append(f"    {age:>5.0f}h  中央値 {row['median']*100:5.2f}pt  "
                         f"最大 {row['max']*100:5.2f}pt  n={row['n']}")
    hit = curve.get(float(SETTLE_DAYS * 24))
    if hit:
        lines.append(f"  → {SETTLE_DAYS*24}時間 の時点で、いちばん遅い本でも "
                     f"**{hit['min']*100:.1f}%** まで来ています")
        if hit["min"] < 0.95:
            lines.append("  [!] **最小が 95% を割りました。後から拾われる本が出ています** —— "
                         "`SETTLE_DAYS` を上げ直すこと（上の「覆る条件」）")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    print(report())
