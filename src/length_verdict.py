"""**「尺を30秒に縮めると engaged 比率が上がる」の判定を、Data API 抜きで下す。**

## 何を判定するか

`config/hypotheses.yaml`:

    claim         尺を30秒に縮めると engaged 比率（すぐスワイプされなかった再生の割合）が上がる
    deadline      2026-08-22
    falsified_if  30秒設計で作った3本（8/16〜18）の engaged 比率の中央値が、
                  旧設計11本（8/4〜8/15）の中央値を上回らない

## **この前提だけは「期限 −3日」を引かないこと**（2026-08-20 12:2x に測って書いた）

他の前提は `deadline` から Analytics の遅れ3日を引いた日が実効の期限です
（`docs/trigger_main.md` §4）。**この1件は引きません。**
`note` が「遅れが4日なら 8/18 公開ぶんが届くのは 8/22 ごろ。だから 8/22」と
書いていて、**遅れはすでに `deadline` の側に入っている**からです。
もう一度引くと**二重に引く**ことになり、まだ存在しない日のデータで判定します。

**代わりに、届いている日で判定できるかを機械が言います**（`verdict()`）——
届いていない本を**上限（比率1.0）と下限（0.0）の両方に置いて**中央値を出し、
**どちらでも同じ答えになったときだけ「判定できる」**と言います。
片方でしか出ないなら `undecided` を返し、**期限は延ばさず、条件も変えません。**

## なぜ Data API を使わないか（08/20 08:2x の M8・10:2x の endcard と同じ形）

母集団を決めるのに `playlistItems` と `videos.list` を叩くと、**日枠**
（JST 16:00 に戻り、数時間で尽きる）に乗ります。**1日のうち16時間、
この判定は構造的に下せません。** 公開時刻は手元の `data/views.jsonl`
（`at - hours`）と `data/uploaded.jsonl` から復元できます
（`scripts/eta.py: published_at()`。**同じ復元をここでも使う**）。

読むのは **YouTube Analytics だけ**（`views` / `engagedViews`）で、
これは Data API とは**別枠**です。

## 群は「日付」で切ります。**本数は写しません**

`falsified_if` の「3本」「11本」は書いた日の実測で、**いまは合いません**
（実測: 8/16〜18 は **6本**・8/4〜8/15 は **26本**）。
**条件の効いている部分は日付の範囲**なので、そちらで切り、
**本数は数え直した実測を印字**します（写しは古くなる）。
"""
from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

#: 旧設計（8/4〜8/15）と 30秒設計（8/16〜18）。**JST の暦日で切る。**
OLD_FROM, OLD_TO = date(2026, 8, 4), date(2026, 8, 15)
NEW_FROM, NEW_TO = date(2026, 8, 16), date(2026, 8, 18)

#: **率を出してよい下限の再生数**（2026-08-20 12:3x に実測して置いた）。
#: 1 にすると、旧設計に **再生1〜4回の本が5本**混ざり、その5本が
#: **5本とも engaged 比率 100.0%**（`engagedViews == views`）になります。
#: 旧設計の中央値は 34.7% → **39.0%** に持ち上がり、**比べる相手が偽物になる**。
#: 30 は `src/ab_power.py` が実データの標本に使っている線と同じです。
MIN_VIEWS = 30


def _published() -> dict[str, datetime]:
    """`scripts/eta.py` の `published_at()` をそのまま借りる（**API 0単位**）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_eta", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.published_at()


def groups(published: dict[str, datetime] | None = None) -> tuple[list[str], list[str]]:
    """公開時刻から、旧設計の群と 30秒設計の群を返す。**純関数（API 0単位）。**"""
    published = published if published is not None else _published()
    old, new = [], []
    for vid, born in published.items():
        d = born.astimezone(JST).date()
        if OLD_FROM <= d <= OLD_TO:
            old.append(vid)
        elif NEW_FROM <= d <= NEW_TO:
            new.append(vid)
    return sorted(old), sorted(new)


def fetch_engaged(ids: Iterable[str], start: date, end: date) -> list[dict[str, Any]]:
    """動画べつの `views` / `engagedViews`。**YouTube Analytics だけを叩く。**

    `filters=video==a,b,c` は1回に 500 本まで渡せる。**Data API は叩かない**ので、
    日枠が閉じている時間帯でも通る。
    """
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    from .auth import credentials

    ids = list(ids)
    if not ids:
        return []
    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    rows: list[dict[str, Any]] = []
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        try:
            resp = analytics.reports().query(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics="views,engagedViews",
                dimensions="video",
                filters="video==" + ",".join(chunk),
                maxResults=500,
            ).execute()
        except HttpError as exc:
            print(f"[length_verdict] Analytics が返しませんでした: {exc.resp.status}")
            return []
        headers = [h["name"] for h in resp.get("columnHeaders", [])]
        rows.extend(dict(zip(headers, r)) for r in resp.get("rows", []) or [])
    return rows


def ratios(rows: Iterable[dict[str, Any]], min_views: int = MIN_VIEWS) -> dict[str, float]:
    """`engagedViews / views`。**再生が `min_views` 未満の本は落とす**（率が壊れる）。

    落とす理由は `MIN_VIEWS` の節にある実測です —— 再生1回の本は
    `engagedViews` も 1 になり、**比率 100% として中央値を持ち上げます。**
    """
    out: dict[str, float] = {}
    for row in rows:
        vid = row.get("video")
        views = row.get("views") or 0
        if not vid or views < min_views:
            continue
        out[vid] = (row.get("engagedViews") or 0) / views
    return out


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def verdict(old: list[float], new: list[float], missing: int = 0) -> dict[str, Any]:
    """**上回ったか**を返す。届いていない本は上限1.0・下限0.0の両方に置いて挟む。

    `falsified_if` は「30秒設計の中央値が旧設計の中央値を**上回らない**」。
    だから `upheld` は **厳密に上回った**とき（`>`）だけ真になる。
    """
    med_old = _median(old)
    if med_old is None or (not new and missing == 0):
        return {"decided": False, "why": "片方の群に測れる本が1つもありません",
                "median_old": med_old, "median_new": _median(new)}
    lo = _median(sorted(new + [0.0] * missing))
    hi = _median(sorted(new + [1.0] * missing))
    up_lo, up_hi = lo > med_old, hi > med_old
    return {
        "decided": up_lo == up_hi,
        "upheld": up_lo if up_lo == up_hi else None,
        "median_old": med_old,
        "median_new": _median(new),
        "median_new_low": lo,
        "median_new_high": hi,
        "missing": missing,
        "n_old": len(old),
        "n_new": len(new),
    }


def sweep(rows: list[dict[str, Any]], old_ids: list[str], new_ids: list[str],
          thresholds: Iterable[int] = (1, 10, 30, 50)) -> list[dict[str, Any]]:
    """**下限の再生数を振って、答えが変わらないかを見る。**

    1つの線で出した答えは、その線の産物かもしれません。**振って同じなら、線のせいではない。**
    """
    out = []
    for mv in thresholds:
        r = ratios(rows, min_views=mv)
        o = [r[v] for v in old_ids if v in r]
        n = [r[v] for v in new_ids if v in r]
        out.append({"min_views": mv, "n_old": len(o), "n_new": len(n),
                    "median_old": _median(o), "median_new": _median(n),
                    "upheld": bool(o and n and _median(n) > _median(o))})
    return out


def reverse_p(old: list[float], new: list[float]) -> float:
    """**「旧設計のほうが高い」側の片側 p。** 外れたときに「では逆か」を言わせないため。

    `falsified_if` が言えるのは「上回らなかった」までです。**逆に悪い**と言うには
    別の証拠が要ります（`src/ab_power.py` の順位和。α は同じ 0.20）。
    """
    from .ab_power import rank_sum_p

    return rank_sum_p(old, new)


def report(today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(JST).date()
    old_ids, new_ids = groups()
    rows = fetch_engaged(old_ids + new_ids, OLD_FROM, today)
    r = ratios(rows)
    old = [r[v] for v in old_ids if v in r]
    new = [r[v] for v in new_ids if v in r]
    out = verdict(old, new, missing=len(new_ids) - len(new))
    out["ids_old"], out["ids_new"] = old_ids, new_ids
    out["per_video_new"] = {v: (ratios(rows, min_views=1)).get(v) for v in new_ids}
    out["sweep"] = sweep(rows, old_ids, new_ids)
    out["reverse_p"] = reverse_p(old, new)
    # **順に並べた窓は、密度と共線になります**（2026-08-26。`src/density_confound.py`）。
    # この判定の「外れ」は、**尺を縮めたせいか、その日の本数が増えたせいか**を分けていません。
    from .density_confound import line as _density_line, overlap as _density_overlap

    pub = _published()
    out["density"] = _density_overlap(old_ids, new_ids, pub)
    out["density_line"] = _density_line(old_ids, new_ids, pub)
    return out


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def main() -> None:  # pragma: no cover - 画面出力だけ
    out = report()
    print("=" * 66)
    print("### 尺を30秒に縮めると engaged 比率が上がる —— 判定")
    print("=" * 66)
    print(f"  母集団（日付で切った実測）: 旧設計 {len(out['ids_old'])}本 "
          f"／ 30秒設計 {len(out['ids_new'])}本")
    print(f"    ＊`falsified_if` の「11本」「3本」は書いた日の数です。**条件は日付のほう。**")
    print(f"  測れた本: 旧 {out.get('n_old')}本 ／ 新 {out.get('n_new')}本"
          f"（再生0で落ちた新設計 {out.get('missing')}本）")
    print()
    print(f"  旧設計の中央値   {_pct(out.get('median_old'))}")
    print(f"  30秒設計の中央値 {_pct(out.get('median_new'))}"
          f"   （届いていない本を含めた幅 {_pct(out.get('median_new_low'))}"
          f" 〜 {_pct(out.get('median_new_high'))}）")
    print()
    for vid, v in (out.get("per_video_new") or {}).items():
        print(f"    {vid}  {_pct(v)}" + ("" if v is not None else "  ← 再生0（まだ届いていない）"))
    print()
    print("  **下限の再生数を振っても答えが変わらないか**（変われば、答えは線の産物です）")
    for row in out.get("sweep") or []:
        print(f"    再生{row['min_views']:>3}以上  旧 {row['n_old']:2}本 {_pct(row['median_old'])}"
              f"  ／ 新 {row['n_new']:2}本 {_pct(row['median_new'])}"
              f"   → {'上回った' if row['upheld'] else '**上回らない**'}")
    print()
    print("  **交絡（`src/density_confound.py`）**")
    print(out.get("density_line", ""))
    if (out.get("density") or {}).get("confounded"):
        print("    **この判定は、尺の効果と公開密度の効果を分けられていません。**")
        print("    engaged は密度と逆向きに動きます（1〜2本/日 34.8% 対 9本以上/日 19.4%・片側 p=0.057）。")
        print("    **`next_if_false` の連鎖を引く前に、`hypotheses.yaml` の"
              "「engaged はその日の本数が増えると下がる」（期限 2026-10-02）を待つこと。**")
    print()
    if not out.get("decided"):
        print("  **判定できません。** 届いていない本の置き方で答えが変わります。")
        print("  **期限は延ばさず、条件も変えません**（`config/hypotheses.yaml` の規則）。")
    elif out.get("upheld"):
        print("  → **当たり。** 30秒設計の中央値が旧設計を上回りました。")
    else:
        print("  → **外れ。** 30秒設計の中央値は旧設計を上回っていません。")
        print("     `next_if_false`: ①尺ではなく冒頭の作りを疑う ②形式そのものを疑う（M5 / M2）")
        p = out.get("reverse_p")
        if p is not None:
            print()
            if p <= 0.20:
                print(f"  **逆向きは立ちます**（旧設計のほうが高い側の片側 p ＝ {p:.3f} ≦ 0.20）。")
                print("     ＝ 30秒に縮めたことが **engaged を下げた**側の証拠です。**尺を戻す手が要ります。**")
            else:
                print(f"  ただし**逆向きは立ちません**（旧設計のほうが高い側の片側 p ＝ {p:.3f} > 0.20）。")
                print("     **「30秒が悪い」とは言えません。** 言えるのは「上がらなかった」までです ——")
                print("     **尺を戻す作業に賭けないこと。** 次に引くのは `next_if_false` ①（冒頭の作り）です。")


if __name__ == "__main__":  # pragma: no cover
    main()
