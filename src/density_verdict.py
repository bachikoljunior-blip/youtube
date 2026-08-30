"""**「1日の本数を増やすと、1本あたりの再生は落ちるのか」を、API 0単位で判定する。**

## 何を判定するか（`config/hypotheses.yaml`）

    claim         予約の間隔を1時間より詰めても、1本あたりの再生は落ちない
                  （＝1日の公開本数の上限は、枠の作りのほうにある）
    falsified_if  詰めた日（1日16本以上）の**1本あたり再生の中央値**が、
                  1時間きざみの日（8〜13本）の中央値の**半分未満**
    next_if_false 1日あたりの本数はチャンネル側で頭打ちと確定させ、
                  `docs/MEANS.md` M14 の「1日92本」を到達不能として畳む

**この前提は `density` の腕そのものです。** `scripts/eta.py` は
`PLAN_PUBLISH_PER_DAY` 本／日の上に段1〜4 が全部乗っているので、
**ここが外れると到達日の土台が入れ替わります。** それでも 2026-08-21 まで、
この判定を下せる道具は1つもありませんでした（`length_verdict` は尺、
`endcard_verdict` は終わり方で、**本数を見るものが無い**）。

## **年齢をそろえて比べること**（2026-08-21 に踏んだ）

素朴に「公開日ごとの再生の中央値」を出すと、**新しい日ほど低く出ます** ——
若い本はまだ伸びていないからです。実測（`data/views.jsonl`）:

    08/20 公開ぶん・年齢 9.6〜38.4時間 の中央値   246回
    08/20 公開ぶん・年齢 12〜18時間 だけ の中央値 352回

**同じ日の同じ本で、100回ちがいます。** だから群は「公開日」で切り、
**値は年齢の帯で取り直します**（`AGE_LO`〜`AGE_HI`）。

## **若い観測の 0 は「0回」ではありません**（同上）

`data/views.jsonl` は Data API の `videos.statistics.viewCount` の写しで、
**公開から数時間は 0 のまま**です。実測（08/20 公開ぶん・観測は 08/20 16:16）:

    年齢  9h→1111回 ／ 10h→0回 ／ 9h→0回 ／ 8h→1回 ／ 7h→3回 ／ 6h→0回

**7〜10時間の帯に「0」と「1111」が同居しています。** 数え落としではなく、
**まだ出ていない**だけです。ここを平均に入れると、詰めた日が実際より
悪く見えます（＝**前提を外れの側へ倒す**）。だから `AGE_LO` より若い観測は
**捨てます。落とした本数は必ず印字します。**

## **7日も待つ必要はありません**（2026-08-21 に測って、`falsified_if` の熟成を書き換えた）

もとの条件は「比べる日は、どちらも公開から**7日以上**たっていること」でした。
**実測はそうなっていません。** 同じ本の 12〜18時間と 30〜44時間を突き合わせると
（n=13・両方の帯に観測がある本すべて）:

    倍率の中央値 **0.999**   ＝ 12時間の時点で、もう伸びきっている
    13本中11本が ±2% 以内。伸びたのは2本（+11%・+36%）

判定済みの前提「**ショートには長い尾が無い。配信は公開から48時間以内に
完全に止まり、二度と再開しない**」（survived）とも向きが一致します。
だから熟成は **24時間**（`RIPE_H`）に置きました —— 12時間の実測に、
上振れ2本ぶんの余裕を足した値です。**7日で待つと、判定が5日おそくなります。**

## 読むのは手元の2つだけ（**Data API も Analytics も要りません**）

    data/views.jsonl      観測（id / at / hours / views）。公開時刻は `at - hours`
    data/uploaded.jsonl   予約した公開時刻（まだ観測が1度も無い本の年齢はここから）

復元は `scripts/eta.py: published_at()` をそのまま使います（**同じ復元を
2か所に書かない**）。

## 割り引いて読むこと

- **n は日ごとに1桁**です。出るのは向きまでで、理由は言えません
- **交絡が残っています** —— 詰めた日は題材も作りも別の群（08/20 は「問い」の
  10本を含む）。**本数だけを動かした実験ではありません**
- **いちばん大きい交絡は上限のほうです**（2026-08-25 に足した）。`src/day_cap.py` の
  実測では **1日に再生が付くのは 10本**で、11本目から先は 0〜3再生。つまり
  「詰めた日（16本以上）」の中央値は、**間隔ではなく、上限の外に出た本の 0 を
  中央値が拾っているだけ**かもしれません。1時間きざみの日（8〜12本）は
  上限の内側なので、そちらには 0 が入りません。**`×0.00` は、そう出て当たり前です。**
  そこで `live_band()` で**両群とも上限の内側だけ**にそろえて数え直し、
  `cap` の側として並べて出します。**2つの倍率が違う向きに出たら、この前提は
  間隔について何も言っていません**（言っているのは上限のこと）。
- `data/views.jsonl` は Data API で作られるので、**日枠が閉じた窓では更新が
  止まります**（JST 16:00 に戻る）。最後の観測が古い回は、そう印字します
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # pragma: no cover - 実行の入口ぶん
    sys.path.insert(0, str(ROOT))

JST = timezone(timedelta(hours=9))

#: 値を取る年齢の帯（時間）。**下は「まだ出ていない 0」を捨てる床**、
#: 上は「もう伸びきっている」ことを実測した帯の外側。
AGE_LO, AGE_HI = 12.0, 48.0

#: **熟成**（この時間を過ぎた本だけを群に入れる）。上の節の実測から 24時間。
RIPE_H = 24.0

#: `falsified_if` の群わけ。**写しではなく条件の本文と同じ数字**。
TIGHT_MIN = 16          # 「詰めた日」＝1日16本以上
HOUR_LO, HOUR_HI = 8, 13  # 「1時間きざみの日」＝8〜13本
TIGHT_DAYS_MIN = 3      # 詰めた日が3日そろうまで判定しない
RATIO_FALSIFIED = 0.5   # 半分未満なら外れ（同値は外れとみなさない）


def _rows(views_path: Path | None = None) -> list[dict[str, Any]]:
    path = views_path or (ROOT / "data" / "views.jsonl")
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def observations(views_path: Path | None = None) -> dict[str, list[tuple[float, int]]]:
    """`video_id` → [(公開からの時間, 再生), ...]。**若い観測も落としません。**

    捨てるのは `banded()` の側です（何本捨てたかを数えるため）。
    """
    obs: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for row in _rows(views_path):
        vid = row.get("id") or row.get("video_id")
        hours, views = row.get("hours"), row.get("views")
        if not vid or hours is None or views is None:
            continue
        try:
            obs[vid].append((float(hours), int(views)))
        except (TypeError, ValueError):
            continue
    return dict(obs)


def banded(obs: dict[str, list[tuple[float, int]]],
           lo: float = AGE_LO, hi: float = AGE_HI) -> tuple[dict[str, int], int]:
    """帯の中の**いちばん大きい**再生。返り: (本ごとの値, 帯に届かず捨てた本数)。

    最大を取るのは、`viewCount` が**減らない**からです（減って見えたら
    それは観測のほうの揺れ）。
    """
    out: dict[str, int] = {}
    dropped = 0
    for vid, xs in obs.items():
        vals = [v for h, v in xs if lo <= h <= hi]
        if vals:
            out[vid] = max(vals)
        else:
            dropped += 1
    return out, dropped


def freeze_ratio(obs: dict[str, list[tuple[float, int]]]) -> dict[str, Any]:
    """**12〜18時間の値は、30〜44時間の値と同じか。** 熟成 `RIPE_H` の根拠。

    同じ本で突き合わせます（群どうしの中央値を比べると、群のちがいが混ざる）。
    """
    ratios: list[float] = []
    for vid, xs in obs.items():
        early = [v for h, v in xs if 12.0 <= h <= 18.0]
        late = [v for h, v in xs if 30.0 <= h <= 44.0]
        if early and late and max(early) > 0:
            ratios.append(max(late) / max(early))
    if not ratios:
        return {"n": 0, "median": None, "grew": 0}
    return {
        "n": len(ratios),
        "median": statistics.median(ratios),
        "grew": sum(1 for r in ratios if r > 1.10),
        "max": max(ratios),
    }


def by_day(published: dict[str, datetime],
           values: dict[str, int]) -> dict[str, list[int]]:
    """公開日（**JST の暦日**）→ その日の本ごとの再生。"""
    out: dict[str, list[int]] = defaultdict(list)
    for vid, when in published.items():
        if vid in values:
            out[when.astimezone(JST).date().isoformat()].append(values[vid])
    return {k: sorted(v) for k, v in out.items()}


def day_counts(published: dict[str, datetime], now: datetime | None = None) -> dict[str, int]:
    """公開日 → **その日に公開した本数**（予約ぶんを含む。観測は要らない）。"""
    now = now or datetime.now(timezone.utc)
    out: dict[str, int] = defaultdict(int)
    for when in published.values():
        if when <= now:
            out[when.astimezone(JST).date().isoformat()] += 1
    return dict(out)


def ripe_days(published: dict[str, datetime], now: datetime | None = None,
              ripe_h: float = RIPE_H) -> set[str]:
    """**その日の最後の1本が熟成しきった日**だけを返す。"""
    now = now or datetime.now(timezone.utc)
    last: dict[str, datetime] = {}
    for when in published.values():
        key = when.astimezone(JST).date().isoformat()
        if key not in last or when > last[key]:
            last[key] = when
    return {k for k, v in last.items()
            if (now - v) >= timedelta(hours=ripe_h)}


def live_band(published: dict[str, datetime], values: dict[str, int],
              cap_n: int | None = None,
              gap_min: float | None = None) -> dict[str, list[int]]:
    """`by_day()` と同じ形。ただし**その日の「生きる帯」の本だけ**を返す。

    帯の作り方は `src/day_cap.py` と同じ2段です:

      1. 公開時刻の早い順に見て、**前に残した本から `gap_min` 未満**のものは落とす
      2. 残ったうちの**先頭 `cap_n` 本**（既定は `day_cap.cap()` ＝ 実測の上限）

    **なぜ要るか**: 上の docstring「いちばん大きい交絡は上限のほう」。
    16本以上出した日の中央値は、上限の外に出た本の `0` を中央値が拾います。
    ここでそろえると、**残るのは間隔のちがいだけ**になります
    （帯の中はどちらの群も30分以上あいているので、厳密には
    「上限を外したときに、まだ差が残るか」を見ています）。

    **2つの既定は、どちらも `src/day_cap.py` から引きます**（2026-08-26 に直した）。
    `gap_min` はここに **`30.0` と写してありました** —— 一致しているのは
    **いまの `day_cap.MIN_GAP_MIN` が 30.0 だから**であって、
    向こうは**実測から動く数**です（`cap()` と同じ）。
    動いた日に、**この判定だけが古い帯で数え続けます** ——
    しかも同じ字で「`day_cap.py` と同じ2段です」と書いてあるので、
    **読んでも気づけません。** `cap_n` は既に引いていたので、`gap_min` もそろえました。
    """
    if cap_n is None or gap_min is None:
        try:
            from . import day_cap
            cap_n = day_cap.cap() if cap_n is None else cap_n
            gap_min = day_cap.MIN_GAP_MIN if gap_min is None else gap_min
        except Exception:                                    # noqa: BLE001
            cap_n = 10 if cap_n is None else cap_n
            gap_min = 30.0 if gap_min is None else gap_min
    days: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    for vid, when in published.items():
        if vid in values:
            jst = when.astimezone(JST)
            days[jst.date().isoformat()].append((jst, values[vid]))
    out: dict[str, list[int]] = {}
    for day, rows in days.items():
        kept: list[tuple[datetime, int]] = []
        for when, val in sorted(rows):
            if not kept or (when - kept[-1][0]).total_seconds() / 60.0 >= gap_min - 1.0:
                kept.append((when, val))
        out[day] = sorted(v for _w, v in kept[:cap_n])
    return out


def verdict(counts: dict[str, int], per_day: dict[str, list[int]],
            ripe: set[str]) -> dict[str, Any]:
    """`falsified_if` をそのまま当てる。**条件は緩めません。**

    返り: `outcome` は "falsified" / "survived" / "undecided"。
    `undecided` のときは `why` に、**あと何が足りないか**が入ります。
    """
    tight = {d: v for d, v in per_day.items()
             if counts.get(d, 0) >= TIGHT_MIN and d in ripe and v}
    hourly = {d: v for d, v in per_day.items()
              if HOUR_LO <= counts.get(d, 0) <= HOUR_HI and d in ripe and v}
    res: dict[str, Any] = {
        "tight_days": sorted(tight), "hourly_days": sorted(hourly),
        "tight_n": sum(len(v) for v in tight.values()),
        "hourly_n": sum(len(v) for v in hourly.values()),
    }
    if tight:
        res["tight_median"] = statistics.median(
            [x for v in tight.values() for x in v])
    if hourly:
        res["hourly_median"] = statistics.median(
            [x for v in hourly.values() for x in v])
    if len(tight) < TIGHT_DAYS_MIN:
        res["outcome"] = "undecided"
        res["why"] = (f"詰めた日（{TIGHT_MIN}本以上・熟成ずみ）が "
                      f"{len(tight)}日 しかありません（要 {TIGHT_DAYS_MIN}日）")
        return res
    if not hourly:
        res["outcome"] = "undecided"
        res["why"] = f"1時間きざみの日（{HOUR_LO}〜{HOUR_HI}本・熟成ずみ）がありません"
        return res
    ratio = res["tight_median"] / res["hourly_median"] if res["hourly_median"] else None
    res["ratio"] = ratio
    res["outcome"] = ("falsified" if ratio is not None and ratio < RATIO_FALSIFIED
                      else "survived")
    return res


def report(now: datetime | None = None, views_path: Path | None = None,
           uploaded_path: Path | None = None) -> dict[str, Any]:
    from scripts.eta import published_at  # 循環を避けるため、ここで読む

    now = now or datetime.now(timezone.utc)
    published = published_at(views_path, uploaded_path)
    obs = observations(views_path)
    values, dropped = banded(obs)
    counts = day_counts(published, now)
    per_day = by_day(published, values)
    ripe = ripe_days(published, now)
    latest = max((r.get("at") for r in _rows(views_path) if r.get("at")), default=None)
    per_day_live = live_band(published, values)
    return {
        "counts": counts, "per_day": per_day, "ripe": ripe,
        "dropped": dropped, "freeze": freeze_ratio(obs),
        "verdict": verdict(counts, per_day, ripe),
        # **上限を外した側**（`live_band`）。生の側と向きが違えば、この前提は
        # 間隔について何も言っていません（module docstring「割り引いて読むこと」）。
        "cap_free": verdict(counts, per_day_live, ripe),
        "latest_obs": latest, "tracked": len(values),
    }


def next_settle(counts: dict[str, int], published: dict[str, datetime],
                now: datetime | None = None) -> date | None:
    """**判定できるようになる日**（予約ぶんを数に入れて先を読む）。

    「詰めた日」が `TIGHT_DAYS_MIN` 日そろい、そのどれもが熟成しきる日。
    予約が入っている先の日も 1日16本以上なら数えます（**予約は実行される**）。
    """
    now = now or datetime.now(timezone.utc)
    per_day_last: dict[str, datetime] = {}
    per_day_n: dict[str, int] = defaultdict(int)
    for when in published.values():
        key = when.astimezone(JST).date().isoformat()
        per_day_n[key] += 1
        if key not in per_day_last or when > per_day_last[key]:
            per_day_last[key] = when
    tight = sorted(d for d, n in per_day_n.items() if n >= TIGHT_MIN)
    if len(tight) < TIGHT_DAYS_MIN:
        return None
    third = tight[TIGHT_DAYS_MIN - 1]
    return (per_day_last[third] + timedelta(hours=RIPE_H)).astimezone(JST).date()


def cap_lines(rep: dict[str, Any]) -> list[str]:
    """**上限を外した側**（`cap_free`）を読む行。**空を返すことがあります。**

    ## なぜ関数にしたか（2026-08-30 夜に実測して切り出した）

    この節は `render()` の中にだけ書いてあり、**`main()` には無いままでした。**
    つまり `python -m src.density_verdict` は、

        倍率 0.003（0.5 未満なら外れ）
        **falsified**

    とだけ印字していました。**同じ台帳で上限を外すと ×0.26 です**
    （実測 2026-08-30: 生 2/716 ＝ ×0.003 ／ 外した側 217/850 ＝ ×0.26。**91倍 ちがう**）。
    モジュール冒頭の「割り引いて読むこと」は、まさにこの2つを**並べて**読めと
    書いてあります —— 片方だけを見た人は、**間隔のせいにできない差まで
    間隔のせいにします。**

    **この差は、いま効いている所に効きます。** `AUTOMATION_PAUSED.md` と
    `scripts/eta.py --gate` は「解除した最初の1周で `python -m src.density_verdict`
    を撃ち直すこと」と名指ししており、**その撃ち直しが読むのは `main()` の側**です。
    解除条件4で入れた機械の上限（`batch_build.cap_by_density()`）も、
    ここの `HOUR_HI` を読んでいます。

    **だから2か所に書かないこと。** 片方だけ増えると、静かにずれます
    （`tests/test_density_verdict_cap_side.py` が、その日に赤くなります）。
    """
    cf = rep.get("cap_free") or {}
    v = rep.get("verdict") or {}
    if cf.get("ratio") is None:
        return []
    try:
        from . import day_cap
        cap_n = day_cap.cap()
    except Exception:                                        # noqa: BLE001
        cap_n = 10
    out = [f"  **上限（1日{cap_n}本）を外して数え直すと ×{cf['ratio']:.2f}"
           f"（{cf['outcome']}）** —— 中央値 詰めた日 {cf['tight_median']:.0f}"
           f" 対 1時間きざみ {cf['hourly_median']:.0f}"]
    if cf["outcome"] != v.get("outcome"):
        out.append("      [!] **生の側と向きが違います。この前提は、間隔について"
                   "何も言っていません** —— 出ているのは上限のほうです"
                   "（16本以上の日は、上限の外に出た本の 0 を中央値が拾う）。"
                   "**これを理由に1日の本数を減らさないこと。**")
    elif v.get("ratio") is not None and cf["ratio"] >= v["ratio"] * 2:
        out.append(f"      [!] **生の ×{v['ratio']:.2f} は、ほとんどが上限のぶんです**"
                   f"（上限を外すと ×{cf['ratio']:.2f}）。"
                   "**間隔のせいにできるのは、外した側の差だけ。**")
    near = abs(cf["ratio"] - RATIO_FALSIFIED) / RATIO_FALSIFIED
    if near <= 0.25:
        out.append(f"      [!] **外した側は線（{RATIO_FALSIFIED}）から {near:.0%} しか"
                   "離れていません。**群のちがい（題材・時期）で裏返る幅です。"
                   "**外れとして手を打つ前に、上限そのものを切り分けること。**")
    out.append("      上限が「1日N本」なのか「13:30 までの窓」なのかは"
               " 2026-08-27 に切り分けます（`src/day_cap.window()`）。"
               " **窓のほうなら、本数を減らすのは逆向きの手です。**")
    return out


def render(rep: dict[str, Any] | None = None) -> str:
    """`scripts/status.py` の1節ぶん。**前提のすぐ上に置きます。**

    上（`print_hypotheses`）は「期限が来たか」を日付で言い、ここは
    **「判定できるだけの日がそろったか」を数で言います。** 片方だけでは
    §4 の `verdict` を選べません（`src/watches.py` と同じ形）。
    """
    rep = rep or report()
    v = rep["verdict"]
    out = ["\n=== 1日の本数と、1本あたりの再生（腕 `density` の前提・API 0単位）==="]
    fz = rep["freeze"]
    if fz["n"]:
        out.append(f"  伸びきる時刻: 12〜18h → 30〜44h の倍率 中央値 {fz['median']:.3f}"
                   f"（n={fz['n']}）→ **熟成 {RIPE_H:.0f}時間で判定できる**")
    ripe_tight = [d for d in sorted(rep["per_day"], reverse=True)
                  if rep["counts"].get(d, 0) >= TIGHT_MIN and d in rep["ripe"]]
    out.append(f"  詰めた日（{TIGHT_MIN}本以上）で熟成ずみ: **{len(ripe_tight)}日** / 要 {TIGHT_DAYS_MIN}日")
    if "tight_median" in v and "hourly_median" in v and v.get("ratio") is not None:
        out.append(f"  中央値 詰めた日 {v['tight_median']:.0f} 対 1時間きざみ {v['hourly_median']:.0f}"
                   f" ＝ **×{v['ratio']:.2f}**（{RATIO_FALSIFIED} 未満で外れ）")
    out.append(f"  **{v['outcome']}**" + (f" —— {v['why']}" if v.get("why") else ""))
    out += cap_lines(rep)
    if v["outcome"] == "undecided":
        from scripts.eta import published_at
        when = next_settle(rep["counts"], published_at())
        if when:
            out.append(f"  **判定できる日: {when.isoformat()}** —— その日は `verdict` が選べます"
                       "（`python -m src.density_verdict`）")
    out.append("  **本数は下限です** —— 控えに公開時刻の無い本は数に入りません"
               "（`data/uploaded.jsonl` の古い行は `at` を持たない）。"
               "**群わけを疑うときは、まずここ。**")
    return "\n".join(out)


def main() -> None:  # pragma: no cover - 画面出力だけ
    rep = report()
    v = rep["verdict"]
    print("=== 1日の本数と、1本あたりの再生（API 0単位・手元の2ファイルだけ）===")
    print(f"  年齢 {AGE_LO:.0f}〜{AGE_HI:.0f}時間 の観測がある本: {rep['tracked']}本"
          f"（帯に届かず落とした本: {rep['dropped']}本）")
    fz = rep["freeze"]
    if fz["n"]:
        print(f"  **伸びきる時刻**: 12〜18h → 30〜44h の倍率 中央値 {fz['median']:.3f}"
              f"（n={fz['n']}・+10%超は {fz['grew']}本）→ 熟成 {RIPE_H:.0f}時間 で判定できる")
    if rep["latest_obs"]:
        print(f"  最後の観測: {rep['latest_obs']}（Data API の日枠が閉じている窓では止まります）")
    print("  --- 公開日ごと（熟成ずみの日だけ値を出す）---")
    for day in sorted(rep["per_day"], reverse=True)[:8]:
        xs = rep["per_day"][day]
        n = rep["counts"].get(day, len(xs))
        mark = "熟成" if day in rep["ripe"] else "**まだ若い**"
        med = statistics.median(xs)
        print(f"    {day}  公開 {n:3d}本 / 値のある本 {len(xs):3d}本"
              f"  中央値 {med:7.0f}  合計 {sum(xs):7d}  {mark}")
    print("  --- 判定 ---")
    if "tight_median" in v and "hourly_median" in v:
        print(f"    詰めた日（{TIGHT_MIN}本以上）  中央値 {v['tight_median']:.0f}"
              f"（{len(v['tight_days'])}日・{v['tight_n']}本）")
        print(f"    1時間きざみの日        中央値 {v['hourly_median']:.0f}"
              f"（{len(v['hourly_days'])}日・{v['hourly_n']}本）")
    if v.get("ratio") is not None:
        print(f"    倍率 {v['ratio']:.3f}（{RATIO_FALSIFIED} 未満なら外れ）")
    print(f"    **{v['outcome']}**" + (f" —— {v['why']}" if v.get("why") else ""))
    # **上限を外した側を、必ず並べて出す**（`cap_lines()` の docstring）。
    # ここが無い間、この画面は生の ×0.003 だけを出していました。
    for line in cap_lines(rep):
        print(line)
    if v["outcome"] == "undecided":
        from scripts.eta import published_at
        when = next_settle(rep["counts"], published_at())
        if when:
            print(f"    **判定できる日: {when.isoformat()}**"
                  "（`config/hypotheses.yaml` の `settle_by`）")


if __name__ == "__main__":  # pragma: no cover
    main()
