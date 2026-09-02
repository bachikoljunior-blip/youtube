"""**きょう作る1本を、どの形（ショート／長尺）・どの族で出すか —— 形と族ごとの1本あたり再生を、いまの控えから数えて並べる。**（**API 0単位**）

    python -m src.daily_pick                                   # 画面（`run_marker.py --write` の `[きょうの1本]` と同じ）
    python -m src.daily_pick --pick ショート <題材> --why "<数字で>"            # その日の1本を決めて残す（これから作る）
    python -m src.daily_pick --pick ショート <題材> --video <ID> --why "<数字で>" # 池に在る本を、その日の1本にする

## なぜ要るか（2026-09-02 夜・最適化の回。「最適化されてんの？」への答えの1つ）

規則（`src/house_rule.py`）は **1日1本** です。つまり毎日の1本が、目標に触れる
**唯一の出力**です。ところが**その1本がどの形・どの族かを、誰も数字で決めていませんでした**:

    09/01 22:00  長尺（変動金利）   improve 5件（計算の表・内訳・追い越し表）→ 20時間で **1再生**
    09/02 13:00  長尺（後期高齢者） 作り置きの消化                            → 6時間で **0再生**
    09/03 の下書き 長尺（介護）     improve 2件（読みの直し）                 ← 池の順で選ばれた

**同じ日に、この控え（`data/views.jsonl`・齢48時間でそろえた）はこう言っています**:

    ショート  n=197  中央値 136回  p90 1,066回  最大 1,864回
    長尺      n=21   中央値   1回  p90    15回  最大    73回     ← **1/136**

`scripts/eta.py` は毎周「引ける腕は `per_video`（1本あたり再生）だけ」と印字します。
**その腕を、いちばん大きく動かす手は「形」で、値段は 0単位** ——
なのに `improve` の当てどころ（`src/next_slot.py`）は「題・サムネ・台本・計算」の
**中身の側だけ**を名指しし、形は選択肢に出ていませんでした
（`docs/trigger_main.md` §4 は「配信の側は中身の側の 10倍 当たる」と書きながら、
`[次の枠]` の画面には出ていない。**同じ5択に並べても、探す手間が違えば選ばれません**）。

**1回 の形の本を 5回 磨いても、1回 は 1回 です。** 無限大にしても到達日は 0日 —— 律速ではない。

## この道具が言うこと・言わないこと

- **言うこと**: 形ごと・族（`calc`）ごとの 48時間 再生（同じ齢でそろえた・API 0単位）、
  規則の密度（≤ `RULE_BAND_MULT` 本/日）の日だけのショート、**その日の1本に使える候補**
  （池に在る private のショート／まだ作っていない `s-` の題材）、**その日の1本が決まっているか**。
- **言わないこと**: 「長尺という形が効かない」。外の同じ帯には 129,261回 の長尺が在ります
  （`scripts/niche_ceiling.py`）。**それは別の作り方の長尺の数**で、いまの作り方の長尺は 1回 です。
  **作り方を変えた長尺が出来たら、その本の数がここに入って、順位は自分で入れ替わります。**
- **決めるのは回です。** ここは数を並べ、決めた印を残すだけ（`data/daily_pick.jsonl`）。
  数字に逆らって選ぶのは自由 —— **理由を数字で `--why` に書くこと。** 次の回が、それと実物を並べます。

## 覆る条件

- 長尺の 48時間 中央値がショートの 1/3 を超えたら、この画面の向きは自分で変わります
  （定数はありません。毎周 数え直します）。
- `data/video_forms.json`（Analytics の札）と控えの秒数のどちらも無い本は、題名の
  `#Shorts` で決めます（`src/forms.classify()` の3段）。**新しい本ほど推測側**です。
- 族の中央値は **n が小さい**（族あたり 2〜20本）。順位の上下 1つは雑音です ——
  **上位の帯と下位の帯**として読むこと。
- オーナーが 1日1本 を外したら、「その日の1本」という主語が変わります。
  そのときは `for_day()` を主語に合わせて直すこと（画面の数はそのまま使えます）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"
UPLOADED = ROOT / "data" / "uploaded.jsonl"
PICKS = ROOT / "data" / "daily_pick.jsonl"
JST = timezone(timedelta(hours=9))

FORMS = ("ショート", "長尺")

#: 同じ齢でそろえる時間。ショートは 48時間 で伸びきる（`src/settle.py` 実測 96%）。
#: 長尺は伸びきりませんが（同 25%）、**比べるのに使うのは「同じ齢」**です ——
#: 伸びきった長尺で比べても 1/136 が 1/49（×2.75・`long_censor`）になるだけで、向きは変わりません。
AGE_HOURS = 48

#: 「規則と同じ密度」と見なす 1日の本数（`src/rule_per_video.RULE_BAND_MULT` と同じ）。
try:
    from .rule_per_video import RULE_BAND_MULT as _RBM
except Exception:                                              # noqa: BLE001
    _RBM = 2
RULE_BAND_MULT = _RBM

#: 族の中央値を出すのに要る最小の本数（これ未満は「測っていない」と出す）。
FAMILY_MIN_N = 2


def _jsonl(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _parse(ts) -> datetime | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _latest_uploaded(path: Path | None = None) -> dict[str, dict]:
    """`video_id` ごとにいちばん後ろの行（予約の書き戻しで同じ本が何度も出る）。"""
    out: dict[str, dict] = {}
    for r in _jsonl(path or UPLOADED):
        vid = r.get("video_id")
        if vid:
            out[vid] = r
    return out


def _form_of(row: dict, measured: dict[str, str]) -> tuple[str, str]:
    """`(形, どこで決めたか)`。`src.forms.classify()` の3段（実測 → 秒数 → 題名）。"""
    try:
        from . import forms as _forms
        is_short, how = _forms.classify(row, measured)
    except Exception:                                          # noqa: BLE001
        dur = row.get("duration_s")
        try:
            is_short = dur is not None and float(dur) <= 180.0
        except (TypeError, ValueError):
            is_short = "#Shorts" in str(row.get("title") or "")
        how = "fallback"
    return ("ショート" if is_short else "長尺"), how


def _measured_forms() -> dict[str, str]:
    try:
        from . import forms as _forms
        return _forms.measured_forms()
    except Exception:                                          # noqa: BLE001
        return {}


#: `config/topics.yaml` は 725件・読むのに 0.5秒。**プロセスの間だけ**持ちます
#: （1本ごとに読み直すと 325本 の池で 160秒 かかった —— 2026-09-02 に踏んだ）。
_TOPICS_CACHE: list[dict] | None = None


def _topics() -> list[dict]:
    global _TOPICS_CACHE
    if _TOPICS_CACHE is None:
        try:
            from . import config
            _TOPICS_CACHE = list(config.load_topics().get("topics", []))
        except Exception:                                      # noqa: BLE001
            _TOPICS_CACHE = []
    return _TOPICS_CACHE


def _topic_calc_map(topics: list[dict] | None = None) -> dict[str, str]:
    topics = _topics() if topics is None else topics
    return {t.get("id"): t.get("calc") for t in topics if t.get("id") and t.get("calc")}


def _known_calcs() -> set[str]:
    try:
        from . import family_perf
        return family_perf.known_calcs()
    except Exception:                                          # noqa: BLE001
        return {p.stem for p in (ROOT / "src" / "calc").glob("*.py")
                if not p.stem.startswith("_")}


def family_of(topic: str | None, by_id: dict[str, str] | None = None,
              known: set[str] | None = None) -> str:
    """題材ID → 族（`calc`）。台帳から消えた古い題材は、先頭の語で当てる
    （`src/family_perf._calc_of_topic()` と同じ決め方）。"""
    if not topic:
        return ""
    by_id = _topic_calc_map() if by_id is None else by_id
    if topic in by_id:
        return by_id[topic]
    known = _known_calcs() if known is None else known
    stem = re.sub(r"^s-", "", topic)
    head = re.split(r"[-_]", stem)[0] if stem else ""
    return head if head in known else ""


def aged_views(hours: int = AGE_HOURS, *, views_path: Path | None = None,
               uploaded_path: Path | None = None,
               measured: dict[str, str] | None = None,
               by_id: dict[str, str] | None = None,
               known: set[str] | None = None) -> list[dict]:
    """公開ずみの本ごとに、**齢 `hours` 時間 に最初に読んだ再生**を返す。API 0単位。

    公開時刻は **控えの観測から**（最初の観測の時刻 − その齢。`src/rule_per_video._settled()`
    と同じ）。控え（`data/uploaded.jsonl`）に `at` が無い古い本も、そのぶん入ります。

    返す行: `video_id` / `form` / `how` / `topic` / `family` / `title` / `pub`（JST の日付）/
    `views`（齢 ≥ hours の最初の観測）/ `life`（観測した最大）/ `age_h`（最後の観測の齢）/
    `day_count`（同じ日に公開した本数。形を問わない）。
    齢 `hours` に届いていない本は**入りません**（伸びきる前の数で比べないため）。
    """
    up = _latest_uploaded(uploaded_path)
    fm = _measured_forms() if measured is None else measured
    by_id = _topic_calc_map() if by_id is None else by_id
    known = _known_calcs() if known is None else known
    series: dict[str, list[tuple[float, int, str]]] = defaultdict(list)
    for r in _jsonl(views_path or VIEWS):
        vid, h, v, at = r.get("id"), r.get("hours"), r.get("views"), r.get("at")
        if vid is None or h is None or v is None or at is None:
            continue
        try:
            series[vid].append((float(h), int(v), str(at)))
        except (TypeError, ValueError):
            continue
    pub_of: dict[str, date] = {}
    for vid, s in series.items():
        s.sort()
        h0, _, at0 = s[0]
        t0 = _parse(at0)
        if t0 is None:
            continue
        pub_of[vid] = (t0 - timedelta(hours=h0)).astimezone(JST).date()
    per_day: dict[date, int] = defaultdict(int)
    for d in pub_of.values():
        per_day[d] += 1
    out = []
    for vid, s in series.items():
        if vid not in pub_of:
            continue
        ripe = [x for x in s if x[0] >= hours]
        if not ripe:
            continue
        r = up.get(vid) or {"video_id": vid}
        form, how = _form_of(r, fm)
        out.append({
            "video_id": vid, "form": form, "how": how,
            "topic": r.get("topic"), "family": family_of(r.get("topic"), by_id, known),
            "title": r.get("title"),
            "pub": pub_of[vid], "views": ripe[0][1],
            "life": max(v for _, v, _ in s), "age_h": s[-1][0],
            "day_count": per_day[pub_of[vid]],
        })
    _attach_residual(out)
    out.sort(key=lambda x: (x["pub"], x["form"], x["video_id"]))
    return out


def _attach_residual(rows: list[dict]) -> None:
    """各行に `day_median`（**同じ日・同じ形**の 48時間 再生の中央値）と
    `res`（＝ (views+1)/(day_median+1)・**その日の中でどれだけ抜けたか**）を足す。

    ## なぜ要るか（2026-09-03 00:xx・最適化の回。**族の順位が当たっていなかった**）

    族の順位は「生の 48時間 再生の中央値」で付けていました。**その順位は、次の1本を
    当てません** —— 1本を抜いて残りの族の中央値でその1本を当てる（LOO）と
    **ρ = −0.005（n=169・ショート）**。ゼロです。
    再生を決めているのは**その日に何本 出したか**（`day_count` との ρ = −0.39、
    その日の中央値との ρ = +0.45）で、族の中央値は「その族の本がたまたま良い日に出たか」を
    写していただけでした（`shokibo` 1,036回・n=4 も、`kokuho` 1,035回・n=3 も、その形）。
    **日で割った残差**で同じ LOO をやると **ρ = +0.17（n=169・門 0.15・3本以上の日だけ）**、
    1本の日も入れると **+0.10（n=185・門 0.14）** —— どちらも門の上か下かの縁で、
    日の中の順位（percentile）なら **−0.02**。**＝ 族は当たりません。** どの割り方でも。
    だから画面は「族の順位」の前に、その順位が当たるかの ρ を**毎周 数え直して**出し、
    両方が門の下なら「族で時間を使うな」と書きます（`_loo_lines`）。
    残差で並べるのは、生で並べるより**外れ方がましなだけ**（1,036回・n=4 の族が、
    たまたま良い日に出た族でないことを、少なくとも日で割って確かめてある）。

    **覆る条件**: `family_loo()` の残差の ρ が門を下回り、生のほうが上回る日が来たら
    （＝ 密度が規則で揃って日の差が消え、生の再生がそのまま当たるようになったら）、
    `by_family` の既定の `key` を `views` に戻すこと。定数は無い —— 毎周 `compare()` が数え直す。
    """
    by_key: dict[tuple, list[int]] = defaultdict(list)
    for r in rows:
        by_key[(r["pub"], r["form"])].append(int(r["views"]))
    med = {k: statistics.median(v) for k, v in by_key.items()}
    for r in rows:
        m = med[(r["pub"], r["form"])]
        r["day_median"] = m
        r["res"] = (int(r["views"]) + 1) / (m + 1)


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None

    def rank(vals: list[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        rk = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            for k in range(i, j + 1):
                rk[order[k]] = (i + j) / 2
            i = j + 1
        return rk
    ra, rb = rank(xs), rank(ys)
    n = len(xs)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((a - ma) * (b - mb) for a, b in zip(ra, rb))
    den = (sum((a - ma) ** 2 for a in ra) * sum((b - mb) ** 2 for b in rb)) ** 0.5
    return num / den if den else None


def family_loo(rows: list[dict], form: str = "ショート", key: str = "res",
               min_others: int = 2) -> dict:
    """**族の順位が、次の1本を当てるか**（leave-one-out の Spearman ρ・API 0単位）。

    各本を1本 抜き、残りの同じ族の `key` の中央値で、抜いた本の `key` を当てる。
    返り: `{"rho": ρ | None, "n": 本数, "gate": 両側5%の門 (1.96/√n)}`。
    `rho` が `gate` を越えなければ、族の順位は**雑音**です（画面はそう出す）。
    """
    fam: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("form") == form and r.get("family") and r.get(key) is not None:
            fam[r["family"]].append(r)
    xs: list[float] = []
    ys: list[float] = []
    for members in fam.values():
        for r in members:
            others = [float(t[key]) for t in members if t is not r]
            if len(others) >= min_others:
                xs.append(statistics.median(others))
                ys.append(float(r[key]))
    n = len(xs)
    return {"rho": _spearman(xs, ys), "n": n, "gate": (1.96 / n ** 0.5) if n else None}


def _observed_ids(views_path: Path | None = None) -> set[str]:
    """控え（`data/views.jsonl`）に観測が1行でも在る本 ＝ 公開したことのある本。"""
    return {r.get("id") for r in _jsonl(views_path or VIEWS) if r.get("id")}


def _stats(vals: list[int]) -> dict:
    if not vals:
        return {"n": 0, "median": None, "p90": None, "max": None}
    s = sorted(vals)
    return {"n": len(s), "median": statistics.median(s),
            "p90": s[min(len(s) - 1, int(round(0.9 * (len(s) - 1))))], "max": s[-1]}


def by_form(rows: list[dict], *, since: date | None = None,
            max_per_day: int | None = None, key: str = "views") -> dict[str, dict]:
    """形ごとの `n` / 中央値 / p90 / 最大。`since` 以降だけ・その日の本数が
    `max_per_day` 以下の日だけ、に絞れます。"""
    vals: dict[str, list[int]] = {f: [] for f in FORMS}
    for r in rows:
        if since is not None and r["pub"] < since:
            continue
        if max_per_day is not None and r["day_count"] > max_per_day:
            continue
        vals.setdefault(r["form"], []).append(int(r[key]))
    return {f: _stats(v) for f, v in vals.items()}


def by_family(rows: list[dict], form: str = "ショート",
              min_n: int = FAMILY_MIN_N, key: str = "res") -> list[dict]:
    """族（`calc`）ごとの 48時間 再生（その形だけ）。**`key` の中央値の高い順**。

    既定の `key` は `res`（日で割った残差・`_attach_residual`）。生の再生の中央値は
    `views_median` に残す（画面はどちらも出す）。`res` の無い行（古い呼び出し・検査）は
    `views` で並べる。
    """
    vals: dict[str, list[float]] = defaultdict(list)
    raw: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r["form"] != form or not r.get("family"):
            continue
        raw[r["family"]].append(int(r["views"]))
        vals[r["family"]].append(float(r[key]) if r.get(key) is not None else float(r["views"]))
    out = []
    for fam, v in vals.items():
        st = _stats(v)
        st["family"] = fam
        st["views_median"] = statistics.median(raw[fam])
        st["enough"] = st["n"] >= min_n
        out.append(st)
    out.sort(key=lambda x: (-(x["median"] or 0), -x["n"], x["family"]))
    return out


def family_rank(fams: list[dict], family: str) -> tuple[int | None, dict | None]:
    for i, f in enumerate(fams, 1):
        if f["family"] == family:
            return i, f
    return None, None


def compare(now: datetime | None = None, rows: list[dict] | None = None,
            recent_days: int = 14) -> dict:
    """画面に要る数を1つの dict に。`all` / `recent` / `rule`（ショートの規則の密度）/ `families`。"""
    t = (now or datetime.now(timezone.utc)).astimezone(JST)
    rows = aged_views() if rows is None else rows
    since = (t - timedelta(days=recent_days)).date()
    return {
        "all": by_form(rows),
        "recent": by_form(rows, since=since),
        "rule": by_form(rows, max_per_day=RULE_BAND_MULT),
        "life": by_form([r for r in rows if r["age_h"] >= 24 * 7], key="life"),
        "families": by_family(rows),
        "family_loo": {k: family_loo(rows, key=k) for k in ("views", "res")},
        "recent_days": recent_days,
        "n_rows": len(rows),
        "rows": rows,
    }


def posted_topics(uploaded_path: Path | None = None) -> set[str]:
    """控えに在る題材ID（＝ もう作った題材。上げただけの本も含む）。"""
    return {r.get("topic") for r in _jsonl(uploaded_path or UPLOADED) if r.get("topic")}


def other_form_topic(topic: str | None, topics: set[str] | None = None,
                     posted: set[str] | None = None) -> str | None:
    """同じ題材が**もう一方の形**で台帳に在り、**まだ作っていなければ**その ID（`s-x` ⇄ `x`）。"""
    if not topic:
        return None
    if topics is None:
        topics = {t.get("id") for t in _topics()}
        if not topics:
            return None
    cand = topic[2:] if topic.startswith("s-") else f"s-{topic}"
    if cand not in topics:
        return None
    if cand in (posted_topics() if posted is None else posted):
        return None
    return cand


def pool_candidates(form: str = "ショート", fams: list[dict] | None = None,
                    uploaded_path: Path | None = None, rows: list[dict] | None = None,
                    exclude: str | None = None, by_id: dict[str, str] | None = None,
                    known: set[str] | None = None,
                    views_path: Path | None = None) -> list[dict]:
    """**池に在る private の本**（予約なし・上げてはある）を、その形だけ、族の中央値の高い順に。
    公開したことのある本（控えの観測が在る本）は**除く**（もう一度 出せません）。"""
    up = _latest_uploaded(uploaded_path)
    fm = _measured_forms()
    fams = fams if fams is not None else by_family(aged_views() if rows is None else rows, form)
    # **一度でも公開した本は除く**（齢 48時間 に届かずに池へ戻った本も。控えの観測が
    #     1行でも在れば公開したことがある —— 実測 `Z0tBNDpr60o`: 5行・149再生・private）。
    seen = {r["video_id"] for r in (rows or [])} | _observed_ids(views_path)
    by_id = _topic_calc_map() if by_id is None else by_id
    known = _known_calcs() if known is None else known
    out = []
    for vid, r in up.items():
        if vid == exclude or r.get("at") or not r.get("uploaded_at") or vid in seen:
            continue
        f, _ = _form_of(r, fm)
        if f != form:
            continue
        fam = family_of(r.get("topic"), by_id, known)
        _, st = family_rank(fams, fam)
        out.append({"video_id": vid, "topic": r.get("topic"), "family": fam,
                    "title": r.get("title"),
                    "fam_res": (st or {}).get("median"),
                    "fam_median": (st or {}).get("views_median", (st or {}).get("median")),
                    "fam_n": (st or {}).get("n", 0),
                    "draft": r.get("retimed_at") is None})
    out.sort(key=lambda x: (-(x["fam_res"] or -1), -x["fam_n"], x["video_id"]))
    return out


def unposted_topics(form: str = "ショート", fams: list[dict] | None = None,
                    topics: list[dict] | None = None, posted: set[str] | None = None,
                    rows: list[dict] | None = None) -> list[dict]:
    """**まだ作っていない題材**（`calc` の在るものだけ。無いと台本が止まる）。族の中央値の高い順。"""
    topics = _topics() if topics is None else topics
    posted = posted_topics() if posted is None else posted
    fams = fams if fams is not None else by_family(aged_views() if rows is None else rows, form)
    by_id = _topic_calc_map(topics)
    out = []
    for t in topics:
        tid = t.get("id")
        if not tid or tid in posted or not t.get("calc"):
            continue
        is_s = tid.startswith("s-")
        if (form == "ショート") != is_s:
            continue
        fam = family_of(tid, by_id)
        _, st = family_rank(fams, fam)
        out.append({"topic": tid, "family": fam, "title": t.get("title_seed"),
                    "fam_res": (st or {}).get("median"),
                    "fam_median": (st or {}).get("views_median", (st or {}).get("median")),
                    "fam_n": (st or {}).get("n", 0)})
    out.sort(key=lambda x: (-(x["fam_res"] or -1), -x["fam_n"], x["topic"]))
    return out


def for_day(now: datetime | None = None) -> date:
    """「その日の1本」の日付（JST）。きょうの枠が埋まっていれば**あす**。"""
    t = (now or datetime.now(timezone.utc)).astimezone(JST)
    try:
        from . import next_slot
        full = next_slot.today_full(now=now)
    except Exception:                                          # noqa: BLE001
        full = False
    return (t + timedelta(days=1)).date() if full else t.date()


def current(day: date, path: Path | None = None) -> dict | None:
    """その日の1本として**最後に**残した決定。無ければ `None`。"""
    last = None
    for r in _jsonl(path or PICKS):
        if r.get("for_day") == day.isoformat():
            last = r
    return last


def record(form: str, topic: str, why: str, *, day: date | None = None,
           now: datetime | None = None, path: Path | None = None,
           video_id: str | None = None, expected: float | None = None) -> dict:
    """その日の1本を決めて残す（追記・`merge=union`）。"""
    if form not in FORMS:
        raise ValueError(f"形は {FORMS} のどれか: {form!r}")
    if not (why or "").strip() or not re.search(r"\d", why):
        raise ValueError("`--why` は数字を含む1行が要ります（次の回が実物と並べます）")
    t = (now or datetime.now(timezone.utc)).astimezone(JST)
    row = {
        "at": t.isoformat(timespec="seconds"),
        "for_day": (day or for_day(now)).isoformat(),
        "form": form, "topic": topic, "video_id": video_id, "why": why.strip(),
        "expected_48h": expected,
        "session": os.environ.get("CLAUDE_SESSION_ID") or "",
    }
    p = path or PICKS
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def replace_video(old_ids, new_id: str, *, why_note: str = "",
                  now: datetime | None = None, path: Path | None = None) -> list[str]:
    """**焼き直しで下書きの ID が変わったら、その本を名指ししている決めを新しい ID へ写す。**
    返りは写した `for_day` の一覧（無ければ空）。**API 0単位。**

    ## なぜ要るか（2026-09-03 05:xx・最適化の回に踏んだ穴）

    `[きょうの1本]` の決め（`record`）は **`video_id` で本を名指し**し、
    `scripts/ahead_sweep._today_candidate` はその ID をそのまま枠へ置きます。
    ところが規則3 の焼き直し（`upload_only.py <題材> --draft --replaces <旧ID>`）は
    **新しい ID の下書きを作り、旧 ID は private のまま残す**（消さない・固定その2の4）。
    ＝ 決めを写さないと、**置かれるのは冒頭を直す前の旧 ID** で、直した本は池に眠ります。
    09/04 の試験の本 `6PKux5HNnUE`（唯一の腕 `per_video` の前提）がまさにその形でした ——
    画面は「16:00 以降に焼き直して差し替える」と刷り、差し替えたあと枠に入るのは旧 ID。

    **覆る条件**: `_today_candidate` が ID ではなく題材で本を引くようになったら、ここは要りません。
    """
    olds = {str(x).strip() for x in (old_ids or []) if str(x).strip()}
    new_id = str(new_id or "").strip()
    if not olds or not new_id or new_id in olds:
        return []
    p = path or PICKS
    rows = _jsonl(p)
    last_by_day: dict[str, dict] = {}
    for r in rows:
        if r.get("for_day"):
            last_by_day[str(r["for_day"])] = r
    done: list[str] = []
    for day_s in sorted(last_by_day):
        cur = last_by_day[day_s]
        if str(cur.get("video_id") or "") not in olds:
            continue
        try:
            day = date.fromisoformat(day_s)
        except ValueError:
            continue
        old = str(cur.get("video_id"))
        why = (f"焼き直し: `{old}` → `{new_id}`（1本・{why_note or 'upload_only --replaces'}）。"
               f"前の決め: {str(cur.get('why') or '')[:140]}")
        record(str(cur.get("form") or FORMS[1]), str(cur.get("topic") or ""), why,
               day=day, now=now, path=p, video_id=new_id,
               expected=cur.get("expected_48h"))
        done.append(day_s)
    return done


def _need_over_cap(path: Path | None = None) -> float | None:
    """`data/eta.jsonl` 最終行の `lever_need_over_cap`（日付が出るのに天井を何倍 上げる要るか）。0単位。"""
    rows = _jsonl(path or (ROOT / "data" / "eta.jsonl"))
    for r in reversed(rows):
        v = r.get("lever_need_over_cap")
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


def theory_gap(cmp: dict, ledger: Path | None = None, now: datetime | None = None) -> dict:
    """**形ごとに「外の帯 ÷ 自分の中央値」を数える**（純関数寄り・API 0単位）。

    返り: {"ショート": {"own": …, "out_p90": …, "out_max": …, "x_p90": …, "x_max": …,
                       "secs_median": …, "n": …, "age_days": …}, "長尺": {…}, "best": 形 or None}
    `x_p90` は「外の p90 を自分の中央値で割った数」。**理論値がどの形に在るか**はこれで決まります。
    自分の中央値が 0 の形は、1回 として割ります（0 で割らない・向きは変わらない）。
    """
    out: dict = {"best": None}
    try:
        import sys
        here = str(ROOT / "scripts")
        if here not in sys.path:
            sys.path.insert(0, here)
        import niche_ceiling as nc                                 # noqa: PLC0415
    except Exception:                                          # noqa: BLE001
        return out
    best_x = 0.0
    for form, key in (("ショート", "short"), ("長尺", "long")):
        row = nc.latest(ledger, form=key)
        if not row:
            continue
        s = (row.get("summary") or {}).get(key) or {}
        if not s.get("n"):
            continue
        src = cmp.get("rule") if form == "ショート" else cmp.get("all")
        own = ((src or {}).get(form) or {}).get("median")
        if own is None:
            own = ((cmp.get("all") or {}).get(form) or {}).get("median")
        own_div = max(float(own or 0), 1.0)
        secs = sorted(int(t.get("secs") or 0) for t in (row.get("top") or [])
                      if t.get("form") == key and t.get("secs"))
        try:
            age = ((now or datetime.now(timezone.utc))
                   - datetime.fromisoformat(str(row["at"]))).days
        except Exception:                                      # noqa: BLE001
            age = 0
        d = {"own": own, "out_p90": s.get("p90"), "out_max": s.get("max"),
             "x_p90": float(s.get("p90") or 0) / own_div,
             "x_max": float(s.get("max") or 0) / own_div,
             "secs_median": (statistics.median(secs) if secs else None),
             "n": s.get("n"), "age_days": age, "source": row.get("source", "api")}
        out[form] = d
        if d["x_p90"] > best_x:
            best_x, out["best"] = d["x_p90"], form
    return out


def theory_lines(cmp: dict, ledger: Path | None = None, now: datetime | None = None,
                 need: float | None = None) -> list[str]:
    """**理論値がどの形に在るか**を、外の帯（0単位）÷ 自分の中央値 で毎周 出す。

    ## なぜ要るか（2026-09-03 02:xx JST・最適化の回。「最適化されてんの？（過去の実行に対して）」→ いいえ）

    `data/runs.jsonl` の ship 290件（08-29〜）で到達日が動いた回は 0回、`data/eta.jsonl` は 08-21 から
    「出ません」のまま。この画面は形を「自分の控えどうし」（ショート 173回 対 長尺 1回）で決めていたので、
    **次の1本は毎日ショート**、長尺は「いまの作り方の長尺」しか無いので永久に 1回 —— 鏡の中で回っていた。
    同じ日に 0単位 で撃った外（`niche_ceiling.py --source free`・486本）:

        ショート  外の p90 10,283回 ／ 最大   220,089回   ← 自分（規則の密度）173回 の ×59
        長尺      外の p90 624,772回 ／ 最大 5,049,657回   ← 自分 1回 の ×624,772（今年 伸びた本・尺の中央 25分）

    目標本文の「原理的に最大の理論値」は、**同じ帯の外が今年 実際に取っている数**のほうに近い。
    `eta.py` が要ると言う ×21.88 は、ショートの p90 でも ×59 で越え、長尺なら桁が4つ違う。
    **形は自分の控えで決めない。理論値の在る形と、その形で外が実際にやっている作り方で決める。**

    **覆る条件**: 帳面が 30日 より古い／その形が 0本 なら、その形の行は出ない（`theory_gap`）。
    自分の長尺の中央値が外の p90 の 1/100 を超えたら（＝ 作り方を写した長尺が実際に伸びたら）、
    この行は「差」ではなく「追い付き」を言う行に書き換えること。
    """
    g = theory_gap(cmp, ledger=ledger, now=now)
    forms = [f for f in FORMS if f in g]
    if not forms:
        return []
    need = need if need is not None else _need_over_cap()
    parts = []
    for f in forms:
        d = g[f]
        parts.append(f"{f} ×{d['x_p90']:,.0f}（外の p90 {_fmt(d['out_p90'])} ÷ 自分の中央値 "
                     f"{_fmt(d['own'] if d['own'] is not None else 0)}・最大は ×{d['x_max']:,.0f}）")
    out = ["     **理論値の在りか**（外の帯 ÷ 自分・0単位・毎周 数え直し）: " + " ／ ".join(parts)]
    best = g.get("best")
    if best:
        d = g[best]
        ln = f"     → 理論値が在る形は **{best}**"
        if need:
            reach = [f for f in forms if g[f]["x_p90"] >= need]
            ln += (f"。日付が出るのに要る ×{need:.1f} を外の p90 で越える形: "
                   + ("・".join(reach) if reach else "**無し**"))
        if best == "長尺" and d.get("secs_median"):
            ln += (f"。外の上位の尺の中央 **{d['secs_median'] / 60:.0f}分**（自分の長尺は 5分・計算1本・題に数字）")
        out.append(ln)
        out.append("       ＝ 形を自分の控え（ショート 対 長尺 の中央値）で決めないこと。**外の上位の題と尺を写した1本**を"
                   "その形で出して、48時間の数をこの画面に入れる（前提は `config/hypotheses.yaml` の「外の作り方を写した長尺」）。")
    return out


def outside_lines(cmp: dict, form: str = "ショート", now: datetime | None = None,
                  ledger: Path | None = None) -> list[str]:
    """**外の帯の、同じ形の数**を `[きょうの1本]` に並べる（`scripts/niche_ceiling.py` の帳面・API 0単位）。

    ## なぜ要るか（2026-09-02 夜・最適化の回）

    この画面の数は**全部 自分の控え**でした（族の中央値は n=2〜6）。同じ日の昼に外を撃った
    帳面（`data/niche_ceiling.jsonl`）は `eta.py` の1行にしか出ず、しかも
    **長尺 25本／ショート 0本** —— 毎日 出している形の外の数は、どの画面にも無かった。
    自分の記録（最大 1,864回）を天井と呼ぶ限り、同じ作り方の外へは出られません。

    **帳面にその形が無いときは、撃つ手を1行 出します**（`--form short`・100単位/語）。
    09/02 23:1x に撃ったら 5語 全部 429（`Search Queries per day`）だったので、
    **戻る時刻（16:00 JST）も一緒に出します** —— 出ない手は撃たれません。

    **覆る条件**: 帳面にその形が 1本以上 在れば、この行は数と上位の題に置き換わります
    （`niche_ceiling.top_lines()`）。30日 超えたら消えて、撃つ手に戻ります。
    """
    try:
        import sys
        here = str(ROOT / "scripts")
        if here not in sys.path:
            sys.path.insert(0, here)
        import niche_ceiling as nc                                 # noqa: PLC0415
    except Exception:                                          # noqa: BLE001
        return []
    key = "short" if form == "ショート" else "long"
    own = ((cmp.get("rule") if form == "ショート" else cmp.get("all")) or {}).get(form, {}) \
        .get("median") or (cmp.get("all") or {}).get(form, {}).get("median")
    try:
        got = nc.top_lines(key, path=ledger, now=now, own_median=own)
    except Exception:                                          # noqa: BLE001
        got = []
    if got:
        # **もう一方の形の外の帯も同じ画面に**（2026-09-03 02:xx・最適化の回）。
        #   ここまでは「次に出る本の形（ショート）」の外だけを出していた。形を決める画面なのに、
        #   形の比較は**自分の控えどうし**（ショート 173回 対 長尺 1回）だけ ＝ 鏡と鏡の比較。
        #   0単位で撃った同じ日の外（`--source free`）: ショート p90 10,283回／長尺（今年）p90 624,772回。
        #   自分の中央値で割ると ×59 対 ×624,772 —— **理論値（目標本文の「原理的に最大」）が
        #   どちらの形に在るかは、この2つの数で決まります。** 自分の控えの比較では永久に見えない。
        other_key = "long" if key == "short" else "short"
        other_form = "長尺" if other_key == "long" else "ショート"
        other_own = (cmp.get("all") or {}).get(other_form, {}).get("median")
        try:
            got += nc.top_lines(other_key, path=ledger, now=now, own_median=other_own)
        except Exception:                                      # noqa: BLE001
            pass
        got += theory_lines(cmp, ledger=ledger, now=now)
        return got
    return [
        f"     外の帯の{form}: **まだ 1本も撃てていません**（帳面 `data/niche_ceiling.jsonl` に"
        f" {form} 0本）。自分の記録を天井と呼ぶ限り、同じ作り方の外へ出られません —— "
        f"撃つこと（100単位/語・`Search Queries per day` は {getattr(nc, 'SEARCH_RESET_JST', '16:00 JST')} に戻る）:",
        f"       python scripts/niche_ceiling.py --form short --queries 5",
    ]


def _loo_lines(loo: dict) -> list[str]:
    """族の順位が当たるかを、生と残差の両方で1行に。門を越えない側は「雑音」と書く。"""
    def one(k: str, label: str) -> str:
        d = loo.get(k) or {}
        rho, n, gate = d.get("rho"), d.get("n", 0), d.get("gate")
        if rho is None or not n:
            return f"{label} —（n={n}）"
        mark = "門を越えた" if gate is not None and abs(rho) > gate else "**雑音**"
        return f"{label} ρ={rho:+.2f}（n={n}・門 {gate:.2f}・{mark}）"
    def noise(k: str) -> bool:
        d = loo.get(k) or {}
        return d.get("rho") is None or d.get("gate") is None or abs(d["rho"]) <= d["gate"]
    ln = ("     族の順位が次の1本を当てるか（1本 抜いて残りの族で当てる・Spearman）: "
          + one("views", "生の再生") + " ／ " + one("res", "日で割った残差"))
    if noise("views") and noise("res"):
        ln += ("\n     → **族は当たりません。族の順位で `improve` の時間を使わないこと** —— "
               "下の順は参考で、決め手は 形（ショート）と 密度（1本/日）。**族より先に外の帯**"
               "（`niche_ceiling.py --form short`）で「同じ帯の上位は何を出しているか」を見ること")
    else:
        ln += " —— **雑音の側で族を選ばないこと**（族は弱い手掛かり。決め手は形と密度）"
    return [ln]


def _fmt(v) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}回"


def _fmtx(v) -> str:
    """残差（日の中央値に対する比）の表示。`_fmt` は「回」を付けるので別にする。"""
    if v is None:
        return "—"
    return f"×{v:,.1f}"


def _ratio_line(cmp: dict, draft_form: str) -> str | None:
    other = "長尺" if draft_form == "ショート" else "ショート"
    a = cmp["all"].get(draft_form, {}).get("median")
    b = cmp["all"].get(other, {}).get("median")
    if a is None or b is None or (b <= 0 and a <= 0):
        return None
    if a <= 0:
        return (f"     ＝ 次に出る本の形（{draft_form}）の中央値は 0回。もう一方（{other}）は "
                f"{_fmt(b)}。")
    r = b / a
    if r >= 1:
        return (f"     ＝ 次に出る本の形（{draft_form}）は、もう一方の形（{other}）の "
                f"**1/{r:,.0f}**（中央値どうし）。")
    return (f"     ＝ 次に出る本の形（{draft_form}）は、もう一方の形（{other}）の "
            f"**×{1 / r:,.1f}**（中央値どうし）。")


def _hour_default(day: date | None = None) -> int:
    """機械が実際に置く時刻 —— **掃く側**（`publish_hour.sweep_hour(その日)`）が先、
    根拠が無ければ `config/channel.yaml` の `publish_hour_jst`（`scripts/ahead_sweep.place_hour`
    と同じ順。2026-09-03 に揃えた —— 画面が 9時 と言い、機械が 17時 に置く形にしないため）。"""
    # 正本は `publish_hour.place_hour`（2026-09-03 02:5x に寄せた。順をここに書き直さないこと）
    try:
        from . import publish_hour
        return int(publish_hour.place_hour(day or for_day()))
    except Exception:                                          # noqa: BLE001
        return 9


def _outside_long_deadline() -> str:
    """前提「外の作り方を写した長尺」の期限（`config/hypotheses.yaml`）。無ければ空。0単位。"""
    try:
        import yaml                                            # noqa: PLC0415
        data = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
        items = data.get("hypotheses") if isinstance(data, dict) else data
        for h in items or []:
            claim = str((h or {}).get("claim") or "")
            if "写した長尺" in claim and not (h.get("closed_on") or h.get("verdict")):
                return str(h.get("deadline") or "")
    except Exception:                                          # noqa: BLE001
        pass
    return ""


#: **24時間の先読みの門**（2026-09-03 03:xx・最適化の回。「最適化されてんの？」への答えの1つ）。
#:
#: 前提「外の作り方を写した長尺」の判定は **48h・100回**（`config/hypotheses.yaml`）で、それは動かしません。
#: ここは別の門です —— **次の未決の日の1本をどちらの形にするか**を、24h の数で**先に決めておく**門。
#:
#: ## なぜ要るか
#:
#: 1日1本（`src/house_rule.py`）の下で、最初の外の作りの長尺（09/04 17:00）の 48h は 09/06 17:00 ——
#: **09/06 の枠と同じ時刻**です。つまり 09/04・09/05・09/06 の3枠は、**1本目の結果を見ずに決まる**。
#: 09/06 の1本を「見てから」決められるのは、24h の数だけです。**その数の読み方を決めていないと、
#: 09/05 の回は 1本目の数を見ても動けず、09/06 は池の順で決まります**（09/03 の下書きがそうでした）。
#:
#: ## 門の高さ（この回に撃って出た数・`data/views.jsonl`）
#:
#: いまの作り方の長尺は 齢6h で **0回**（`8hJnwkC8NU0`）・齢20h で **1回**（`ICmIBsZRYFE`）。
#: 48h の門 100回 の **3割 ＝ 30回** を 24h で越えていれば、48h で門を越える側に居る
#: （ショートの中央カーブは 24h で 48h の約8割。長尺は未測定 —— だから半分より低い3割に置く）。
#:
#: **覆る条件**: 外の作りの長尺が3本以上 測れたら、その本の 24h/48h の比で置き直すこと
#: （`aged_views(hours=24)` と `aged_views(hours=48)` を同じ本で並べれば出ます）。
OUTSIDE_24H_GATE = 30
OUTSIDE_48H_GATE = 100


def _latest_obs(video_id: str, views_path: Path | None = None) -> dict | None:
    """控え（`data/views.jsonl`）の、その本のいちばん後ろの観測。無ければ `None`。0単位。"""
    last = None
    for r in _jsonl(views_path or VIEWS):
        if r.get("id") == video_id:
            last = r
    return last


def outside_long_readout(now: datetime | None = None, *, topics: list[dict] | None = None,
                         uploaded_path: Path | None = None,
                         views_path: Path | None = None) -> tuple[list[str], str | None]:
    """**公開ずみ／予約ずみの外の作りの長尺の、いまの再生と 24h の先読みの門。**（API 0単位）

    返り: `(行, 判定)`。判定は `"go"`（24h で門の上）／ `"stop"`（24h で門の下）／ `None`（まだ読めない）。
    複数の本が読めるときは、**いちばん新しく 24h を越えた本**の判定。
    """
    tops = {t["id"] for t in (topics if topics is not None else _topics())
            if str(t.get("style") or "") == "outside_long"}
    if not tops:
        return [], None
    t = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    out: list[str] = []
    verdict: str | None = None
    verdict_at: datetime | None = None
    rows = sorted(((vid, r) for vid, r in _latest_uploaded(uploaded_path).items()
                   if str(r.get("topic") or "") in tops and r.get("at")),
                  key=lambda x: str(x[1].get("at")))
    for vid, r in rows:
        try:
            pub = datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        h24 = (pub + timedelta(hours=24)).astimezone(JST)
        h48 = (pub + timedelta(hours=48)).astimezone(JST)
        if pub > t:
            out.append(f"     外の作りの長尺 `{vid}` は {pub.astimezone(JST):%m/%d %H:%M} JST に出ます → "
                       f"24h の先読み（門 {OUTSIDE_24H_GATE}回）は {h24:%m/%d %H:%M} JST・"
                       f"48h の判定（門 {OUTSIDE_48H_GATE}回）は {h48:%m/%d %H:%M} JST")
            continue
        age = (t - pub).total_seconds() / 3600
        obs = _latest_obs(vid, views_path)
        if obs is None:
            out.append(f"     外の作りの長尺 `{vid}`（齢 {age:.0f}h）: 控えに観測が無い → "
                       f"`python scripts/snapshot.py`（Analytics・日枠の外）で読むこと")
            continue
        v = int(obs.get("views") or 0)
        h = float(obs.get("hours") or age)
        line = (f"     外の作りの長尺 `{vid}`: 齢 {h:.0f}h で **{v}回**"
                f"（いまの作り方の長尺は 齢20h で 1回・齢48h の中央値 1回）")
        if h < 24:
            line += (f" → 24h（{h24:%m/%d %H:%M} JST）の先読みの門 {OUTSIDE_24H_GATE}回 まで待つ。"
                     f"**次の未決の日は、それまで決めないこと**")
        elif v >= OUTSIDE_24H_GATE:
            line += (f" **≥ 先読みの門 {OUTSIDE_24H_GATE}回 → 次の未決の日の1本も外の作りの長尺**"
                     f"（下書きが無ければ作る・下の行）")
            if verdict_at is None or pub > verdict_at:
                verdict, verdict_at = "go", pub
        else:
            # **門の下でも形はショートへ戻さない**（2026-09-03 夜・最適化の回）。ショートの視聴時間は
            # 門2a（4,000時間）に 0 入り、門2b は 1本/日 なら 111,111回/本（`gate_arithmetic`）。
            # 戻す先は「長尺のまま、作りを1つ変える」。前提の判定（48h・100回）は動かさない。
            line += (f" **＜ 先読みの門 {OUTSIDE_24H_GATE}回 → それでも次の未決の日の1本は長尺**"
                     f"（ショートは 4,000時間 の門に 0時間・`gate_lines` の倍率）。**同じ作りを繰り返さず、"
                     f"1つ変える**（題の型／絵／冒頭のどれか1つ・変えた点を `--why` に）。前提の判定そのものは "
                     f"48h・{OUTSIDE_48H_GATE}回 のまま（`falsified_if`）")
            if verdict_at is None or pub > verdict_at:
                verdict, verdict_at = "stop", pub
        if h >= 48:
            line += f"（48h を過ぎている: 前提の判定は `verdict`・門 {OUTSIDE_48H_GATE}回・`deadline_check`）"
        out.append(line)
    return out, verdict


def _unbuilt_outside(tops: list[dict], uploaded_path: Path | None = None) -> list[dict]:
    """`style: outside_long` の題材のうち、まだ1本も上げていないもの（台帳の順）。0単位。"""
    made = {str(r.get("topic") or "") for r in _latest_uploaded(uploaded_path).values()}
    return [t for t in tops if str(t.get("id") or "") not in made]


def outside_opening_lines(vid: str, topic: str, root: Path | None = None,
                          reset_hm: str = "16:00") -> list[str]:
    """**外の作りの長尺の下書きの「冒頭」が、外の上位4本の型になっているか**を、控えと台本で数えて出す（0単位）。

    ## なぜ要るか（2026-09-03 05:xx・最適化の回）

    09/04 の本 `6PKux5HNnUE` は題・尺・絵を外の上位に写して、**冒頭は写していなかった**
    （最初の 4コマ: 名乗り 0・問い 0・「皆さん／あなた」0・「最後まで」0 ＝ 3人称の解説）。外の上位4本は
    `data/niche_thumbs/<id>.opening.txt`（自動字幕・0単位）で 4/4 が 結論の額 → 知らない側の損 → 名乗り →
    問い 2〜3 → 「最後まで」の順。自分の長尺は 15〜30% でいちばん去る（`retention_lines`）。
    **画面がこれを言わないと、規則3 の `improve` は「読みの直し」に流れる**（`hold_lines` が雑音と印字する側）。

    見るのは2つ: 上がっている本の控え `data/critique_queue/<id>.script.json`（`script_writer.outside_opening_problems`）と
    `data/scripts/<題材>.script.json`（焼き直す台本）。控えが型の外で台本が型の中なら**焼き直す手**（`videos.insert`・
    **いま撃てる**）を、両方 型の外なら**台本を直す手**を出す。控えが型の中なら1行で済む。

    **「16:00 JST 以降（日枠が戻る）に」と書かないこと**（2026-09-03 04:5x に直した）。この行は 05:xx の版で
    「`videos.insert` 1,600単位・日枠が戻る 16:00 JST 以降」と印字しており、**次の周が 11時間 待つ手に見えていました**。
    `videos.insert` は日枠を使いません —— `src/auth.py`（08/17 05:2x・insert が通るのに update が 403）、08/27 の
    枠が尽きた 16:47 JST の後に通った 3本、`tests/test_insert_never_marked_ok.py`、そして同じ日の 02:14 JST に
    帳面 10,000 超で通った `6PKux5HNnUE` 自身。`docs/trigger_main.md` §4 の表も「upload: 日枠を使いません」。
    焼き直しの手で日枠が要るのは**その日の枠へ `--move` する 50単位 だけ**で、それは `place_today` が当日に撃つ。
    `reset_hm` は互換のために残してあるが、この関数はもう印字しない。

    **覆る条件**: 前提「外の作り方を写した長尺」が閉じたら `outside_long_lines` ごと消える。冒頭を型にした本と
    しない本の 48h が同じなら（次の2本で分かる）、この行は `[!]` を出さず「型の中／外」の1行だけにする。
    """
    try:
        from . import script_writer as sw                          # noqa: PLC0415
        from .script_writer import VideoScript                     # noqa: PLC0415
    except Exception:                                              # noqa: BLE001
        return []
    root = root or ROOT
    stash = root / "data" / "critique_queue" / f"{vid}.script.json"
    draft = root / "data" / "scripts" / f"{topic}.script.json"

    def _problems(f: Path) -> list[str] | None:
        try:
            return sw.outside_opening_problems(VideoScript.model_validate_json(f.read_text(encoding="utf-8")))
        except Exception:                                          # noqa: BLE001
            return None

    ps = _problems(stash) if stash.exists() else None
    pd = _problems(draft) if draft.exists() else None
    if ps is None and pd is None:
        return []
    out: list[str] = []
    if ps is not None and not ps:
        out.append(f"     冒頭（最初の 4コマ）: 控え `{stash.relative_to(root)}` は**外の上位4本の型の中**"
                   f"（名乗り・問い 2つ・皆さん／あなた・最後まで。`script_writer.outside_opening_problems`）")
        return out
    if ps is not None:
        out.append(f"     [!] **上がっている本 `{vid}` の冒頭は、外の上位4本の型の外**（{len(ps)}件: "
                   + "／".join(x.split("（")[0] for x in ps) + f"）。外の 4/4 は 結論の額 → 知らない側の損 → 名乗り → "
                   f"問い 2〜3 → 「最後まで」の順（実物 `data/niche_thumbs/<id>.opening.txt`）。長尺は 15〜30% でいちばん去る")
    if pd is not None and not pd:
        out.append(f"     → 台本 `{draft.relative_to(root)}` は**もう型の中**。**焼き直しは機械が撃ちます**"
                   f"（`scripts/ahead_sweep.rebake_today`・毎周の `kick` から・台本が控えと違い commit 済みなら背景で "
                   f"`videos.insert`（日枠を使わない・TTS 64コマ 約4分＋合成）→ 決めを新 ID へ写す。"
                   f"帳面 `data/rebake.jsonl`・log `data/rebake.log`。日枠が要るのは当日の `--move` 50単位 だけ）。"
                   f"手で撃つなら（同じ物・いま撃ってよい）:")
        out.append(f"       python -m src.pipeline --script {draft.relative_to(root)} --topic {topic} --dry-run"
                   f" && python scripts/upload_only.py {topic} --draft --replaces {vid}")
    elif pd is not None:
        out.append(f"     → 台本 `{draft.relative_to(root)}` も型の外（{len(pd)}件）。先に台本の冒頭 4コマ を直す"
                   f"（`data/scripts/{topic}.build.py` が在ればそれを直して撃つ・0単位）→ 上の焼き直し")
    else:
        out.append(f"     → 焼き直す台本 `data/scripts/{topic}.script.json` が無い。控えを写して冒頭 4コマ を型に直し"
                   f"（`script_writer.OUTSIDE_LONG_RULE` (1) a〜e）、`--script` で焼き直す（`videos.insert` は日枠を使わない）")
    return out


def outside_long_lines(day: date, cur: dict | None, now: datetime | None = None,
                       topics: list[dict] | None = None,
                       drafts: list[dict] | None = None,
                       readout: tuple[list[str], str | None] | None = None,
                       uploaded_path: Path | None = None) -> list[str]:
    """**外の作りを写した長尺**（`topics.yaml` の `style: outside_long`）が、池に在るか・
    その日の1本になっているかを1〜3行で出す。**API 0単位。**

    ## なぜ要るか（2026-09-03 02:xx・最適化の回）

    前の最適化の回（01:5x）は「理論値が在る形は長尺」を画面に出し、前提
    「外の作り方を写した長尺」（48h で 100回）を立てて、こう書き残した ——
    **「主実行が 09-09 までに長尺を1本も作らなかったら、この回の手は画面を1つ増やしただけ。
    そのときは `--pick` の既定を理論値の在る形に倒すこと」**。その1時間後の主実行は `fix` を出し、
    09/03・09/04 の1本はどちらもショートに決まっていた（`data/daily_pick.jsonl`）。
    **画面が「長尺」と言っても、決める行は「ショート 173回 対 長尺 1回」の数で書かれる** ——
    その 1回 は「いまの作り方の長尺」の数で、外の作りの長尺はまだ 1本も測っていない。
    測っていない形を、測った数で落とすのが鏡の中の回り方だった。

    だからここは、**外の作りの長尺の下書きが池に在る日は、その日の1本をそれにする行**を出す
    （在るのに別の本を決めていたら名指しする。無ければ作る手を出す）。決めるのは回のままだが、
    「数字で上書きする」の数字は、この行が渡す（外の p90 ÷ 自分の中央値・前提の期限）。

    ## 24h の先読み（2026-09-03 03:xx・同じ回の続き）

    `outside_long_readout()` の判定を先に読みます。**`"stop"`（24h で門の下）なら、
    池に下書きが残っていても「その日の1本はこれに」とは言わず、作る手も出しません**
    （その日はショート —— `pool_candidates("ショート")`）。`"go"` で未割当の下書きが無ければ、
    次の未着手の題材（`_unbuilt_outside`）を作る手を出します。判定が無い（まだ 24h 前）あいだは
    前と同じ —— 在る下書きをその日の1本に。**3本目を先に作らないこと**（作り置きの規則2）。

    **覆る条件**: 前提が閉じたら（当たり・外れどちらでも）この行は要らない —— 当たりなら
    `by_form()` の長尺の中央値が自分で上がって順位が入れ替わる。外れなら `next_if_false`
    （ショートの p90 ×10 を先に取る）へ。`_outside_long_deadline()` が空を返した日から消えます。
    """
    dl = _outside_long_deadline()
    if not dl:
        return []
    tops = [t for t in (topics if topics is not None else _topics())
            if str(t.get("style") or "") == "outside_long"]
    if not tops:
        return []
    ids = {t["id"] for t in tops}
    if drafts is None:
        try:
            from . import next_slot                                # noqa: PLC0415
            drafts = next_slot.drafts(now)
        except Exception:                                          # noqa: BLE001
            drafts = []
    have = [d for d in drafts if str(d.get("topic") or "") in ids]
    ro_lines, ro = (readout if readout is not None
                    else outside_long_readout(now, topics=tops, uploaded_path=uploaded_path))
    out: list[str] = list(ro_lines)
    cur_id = str((cur or {}).get("video_id") or "")
    taken = set()
    try:
        for r in _jsonl(PICKS):
            if r.get("for_day") != day.isoformat() and r.get("video_id"):
                taken.add(str(r["video_id"]))
    except Exception:                                          # noqa: BLE001
        pass
    if ro == "stop":
        # **ショートへは倒さない**（2026-09-03 夜。理由は `gate_arithmetic` の註 —— ショートの視聴時間は
        # 門2a に 0 入る）。門の下は「形を戻せ」ではなく「作りを1つ変えろ」。下の行はそのまま下書き／次の題材を名指しする。
        out.append(f"     → **{day:%m/%d} の1本も長尺のまま**（1本目が 24h で門の下。ショートは 4,000時間 の門に 0時間・"
                   f"`gate_lines`）。**次の1本は同じ作りを繰り返さず 1つ変える**（題の型／絵／冒頭のどれか1つ・"
                   f"変えた点を `--why` に）。前提「外の作り方を写した長尺」の判定は 48h・{OUTSIDE_48H_GATE}回（期限 {dl}）で別")
    if have:
        # **どの下書きを名指しするか**（2026-09-03 02:3x に踏んだ）: 同じ枝の2つの回が同じ夜に
        # 1本ずつ上げ（`6PKux5HNnUE`・`dRZnZrRy2Lw`）、`have[0]` は決めた本と別の本を指した。
        # その日に決めてある本ならそれ、無ければ**ほかの日にまだ決められていない**下書きの先頭。
        free = [x for x in have if str(x.get("video_id") or "") not in taken]
        d = (next((x for x in have if str(x.get("video_id") or "") == cur_id), None)
             or (free[0] if free else None))
        if d is not None:
            vid = str(d.get("video_id") or "")
            out.append(f"     **外の作りを写した長尺の下書きが池に在ります**: `{vid}` `{d.get('topic')}`"
                       f"（前提「外の作り方を写した長尺」期限 {dl}・48h で {OUTSIDE_48H_GATE}回 が門。"
                       f"**測っていない形を、いまの作り方の長尺の 1回 で落とさないこと**）")
            out.extend(outside_opening_lines(vid, str(d.get("topic") or "")))
            if not cur or str(cur.get("video_id") or "") != vid:
                out.append(f"     → **{day:%m/%d} の1本はこれにすること**（`by_form()` の長尺 1回 は"
                           f"『5分・計算1本』の数で、この本の数ではない。外の長尺 p90 は自分の中央値の ×624,772・"
                           f"`outside_lines`）:")
                out.append(f"       python -m src.daily_pick --pick 長尺 {d.get('topic')} --video {vid}"
                           f" --day {day:%Y-%m-%d} --why \"外の作りを写した長尺の1本目（前提の判定・期限 {dl}）。"
                           f"外の長尺 p90 ÷ 自分の中央値 1回\"")
            return out
        # 下書きは全部ほかの日に割り当てずみ → 次を作るかは先読みの判定で
        out.append(f"     外の作りの長尺の下書きは全部 ほかの日に決めてあります"
                   f"（{'・'.join('`' + str(x.get('video_id')) + '`' for x in have)}）")
    nxt = _unbuilt_outside(tops, uploaded_path)
    if ro in ("go", "stop") and nxt:
        t0 = nxt[0]
        why = ("24h の先読みが門の上なので" if ro == "go"
               else "24h の先読みは門の下だが 形は長尺のまま（作りを1つ変えて）")
        out.append(f"     → **{why}、{day:%m/%d} の1本は外の作りの長尺の次の1本**"
                   f"（題材 `{t0['id']}`・作るのは 0単位・上げるのは `videos.insert`＝日枠の外）:")
        out.append(f"       python -m src.pipeline --topic {t0['id']} --dry-run"
                   f" && python scripts/inspect_build.py {t0['id']}"
                   f" && python scripts/upload_only.py {t0['id']} --draft")
    elif ro in ("go", "stop") and not nxt:
        out.append(f"     [!] **24h の先読みが出たのに、`style: outside_long` の未着手の題材が"
                   f" `config/topics.yaml` に1件も残っていません** —— 外の上位の題（`outside_lines`）から"
                   f" 1件 足すこと（`calc` は `src/calc/` に在るもの・`minutes: 20`・`style: outside_long`）")
    elif not have and ro is None:
        out.append(f"     [!] **外の作りを写した長尺は、まだ池に1本も在りません**（題材 "
                   + "・".join(f"`{t['id']}`" for t in tops[:3])
                   + f"・前提の期限 {dl}）。作るのは 0単位・上げるのは `videos.insert`＝日枠の外:")
        t0 = (nxt or tops)[0]
        out.append(f"       python -m src.pipeline --topic {t0['id']} --dry-run"
                   f" && python scripts/inspect_build.py {t0['id']}"
                   f" && python scripts/upload_only.py {t0['id']} --draft")
    elif have and ro is None:
        out.append(f"     → **{day:%m/%d} の1本は、まだ決めないこと**（1本目の 24h の先読みを待つ。"
                   f"それまでに3本目を作らない ＝ 作り置きの規則2）")
    return out

#: 長尺の維持率カーブが1本も無い日に、視聴分を出すために置く仮の「平均して見られる割合」。
#: **測れた日から使われません**（`long_watch_fraction()` が n≥1 なら実測を返す）。
ASSUMED_LONG_FRAC = 0.3


def _gate_constants() -> dict:
    """収益化の門の数。**正本は `scripts/eta.py`**（読めない回だけ公表値を置く）。"""
    try:
        import sys
        here = str(ROOT / "scripts")
        if here not in sys.path:
            sys.path.insert(0, here)
        import eta as _eta                                         # noqa: PLC0415
        return {"subs": int(_eta.SUBS_GATE), "long_hours": float(_eta.LONG_HOURS_GATE),
                "window_days": float(_eta.LONG_HOURS_WINDOW_DAYS),
                "shorts_views": float(_eta.SHORTS_VIEWS_GATE), "shorts_days": 90.0}
    except Exception:                                          # noqa: BLE001
        return {"subs": 1000, "long_hours": 4000.0, "window_days": 365.0,
                "shorts_views": 10_000_000.0, "shorts_days": 90.0}


def _eta_snapshot(path: Path | None = None) -> dict:
    """`data/eta.jsonl` の、門の分子（`long_hours_365` / `shorts_views_90d` / `subs_net`）を持つ最後の行。0単位。"""
    for r in reversed(_jsonl(path or (ROOT / "data" / "eta.jsonl"))):
        if "long_hours_365" in r:
            return r
    return {}


def long_watch_fraction(rows: list[dict], cv: dict[str, list] | None = None) -> tuple[float | None, int]:
    """長尺の本が**平均して何割 見られたか**（`data/retention.json` の `audienceWatchRatio` の平均）と、その本数。0単位。"""
    if cv is None:
        try:
            from . import hold                                     # noqa: PLC0415
            cv = hold.curves()
        except Exception:                                          # noqa: BLE001
            cv = {}
    vals: list[float] = []
    for r in rows:
        if r.get("form") != "長尺":
            continue
        curve = (cv or {}).get(str(r.get("video_id")))
        if not curve:
            continue
        try:
            vals.append(statistics.mean(float(p[1]) for p in curve))
        except (TypeError, ValueError, IndexError, statistics.StatisticsError):
            continue
    if not vals:
        return None, 0
    return statistics.mean(vals), len(vals)


def _long_duration_min(next_row: dict | None = None, uploaded_path: Path | None = None,
                       topics: list[dict] | None = None) -> float:
    """次の長尺の尺（分）。外の作りの本（`style: outside_long`）が上がっていればその中央、
    無ければ次に出る本、それも無ければ 20分（外の上位の尺の下端）。"""
    tops = {t["id"] for t in (topics if topics is not None else _topics())
            if str(t.get("style") or "") == "outside_long"}
    secs = []
    for r in _latest_uploaded(uploaded_path).values():
        if str(r.get("topic") or "") in tops and r.get("duration_s"):
            try:
                secs.append(float(r["duration_s"]))
            except (TypeError, ValueError):
                continue
    if secs:
        return statistics.median(secs) / 60.0
    try:
        d = float((next_row or {}).get("duration_s") or 0)
        if d > 180:
            return d / 60.0
    except (TypeError, ValueError):
        pass
    return 20.0


def gate_arithmetic(cmp: dict, *, snapshot: dict | None = None, duration_min: float | None = None,
                    frac: tuple[float | None, int] | None = None, consts: dict | None = None) -> dict:
    """**収益化の門に、どちらの形が近いか**を、規則（1日1本）の下で 1本あたりに直して数える。純関数・API 0単位。

    ## なぜ要るか（2026-09-03 夜・最適化の回。「最適化されてんの？」→ いいえ の理由を1つ潰す）

    この画面は形を **齢48時間の再生**（ショート 173回 対 長尺 1回）で並べ、外の作りの長尺の
    24h の先読みが門の下なら「その日の1本は規則の密度のショート」へ倒していた。
    **その 48時間の再生は、目標の門の数ではない。** 門（`scripts/eta.py`）はこう数える:

        門2a  長尺の視聴 4,000時間／直近12か月     ← **ショートの視聴時間は 0 入る**
        門2b  ショートの再生 1,000万回／直近90日   ← 1日1本 なら **111,111回/本**

    自分の数（この回に撃った・`data/eta.jsonl` 09/02）: 長尺の視聴 **3.1時間**、ショート 83k回/90日、
    登録 25人。ショートは 400本 出して 8万回 —— 門2b の 0.8%。規則の密度の中央値 1,049回 でも
    **×106**、直近14日の中央値 110回 なら **×1,010**。長尺は 20分 の本が 16% 見られる（実測 n=1）として
    1日 11時間 ＝ **約 200回/日**、自分の長尺の生涯 中央値 4回 → **×50**・記録 196回 → **×1.0**。
    **ショートは、いくら伸びても 4,000時間 に 1分も入らない。** 形をショートへ戻す判定は、
    この数を見てから出すこと（`eta.py` は 08-31 に「門2a は門2b の 473倍 近い」と数えていたが、
    この画面には 1行も出ていなかった —— 言っている所と、している所が別）。

    返り: `{"shorts": {...}, "long": {...}, "nearer": "長尺"|"ショート"|None, "consts": {...}}`。
    倍率は「要る数 ÷ 自分の中央値」（中央値 0 は 1 で割る）。**小さいほうが門に近い**。

    ## 覆る条件

    - YouTube が門の数を変えたら `scripts/eta.py` の定数を直す（ここは読むだけ・写しを持たない）。
    - 長尺の維持率カーブが 3本 以上 貯まったら `ASSUMED_LONG_FRAC` は使われない（`long_watch_fraction`）。
    - 自分のショートの中央値が 門2b の要る数の 1/10 を越えたら（＝ 11,111回/本）、この行の向きは
      数で自分に入れ替わる（定数は無い）。
    """
    c = consts or _gate_constants()
    s = snapshot if snapshot is not None else _eta_snapshot()
    out: dict = {"consts": c, "nearer": None}
    # --- 門2b: ショート ---
    need_s = c["shorts_views"] / c["shorts_days"]                 # 1日1本 → 1本あたり
    own_s = ((cmp.get("rule") or {}).get("ショート") or {}).get("median")
    own_s_all = ((cmp.get("recent") or {}).get("ショート") or {}).get("median")
    own_s_max = ((cmp.get("all") or {}).get("ショート") or {}).get("max")
    out["shorts"] = {
        "need_per_video": need_s, "own_median_rule": own_s, "own_median_recent": own_s_all,
        "own_max": own_s_max, "have_90d": s.get("shorts_views_90d"),
        "x_median": need_s / max(float(own_s or 0), 1.0), "x_max": need_s / max(float(own_s_max or 0), 1.0),
        "hours_to_gate2a": 0.0,
    }
    # --- 門2a: 長尺 ---
    have_h = float(s.get("long_hours_365") or 0.0)
    left_h = max(c["long_hours"] - have_h, 0.0)
    per_day_h = left_h / c["window_days"]
    dur = float(duration_min if duration_min is not None else 20.0)
    fr, fr_n = frac if frac is not None else (None, 0)
    use_fr = fr if (fr is not None and fr > 0) else ASSUMED_LONG_FRAC
    min_per_view = max(dur * use_fr, 0.05)
    need_l = per_day_h * 60.0 / min_per_view                       # 1日に要る再生（1日1本 → 1本あたりの目安）
    lf = (cmp.get("life") or {}).get("長尺") or {}
    own_l = lf.get("median")
    own_l_max = lf.get("max")
    out["long"] = {
        "have_hours": have_h, "left_hours": left_h, "per_day_hours": per_day_h,
        "duration_min": dur, "frac": use_fr, "frac_measured": fr is not None and fr > 0, "frac_n": fr_n,
        "need_per_video": need_l, "own_median_life": own_l, "own_max_life": own_l_max,
        "x_median": need_l / max(float(own_l or 0), 1.0), "x_max": need_l / max(float(own_l_max or 0), 1.0),
    }
    out["subs"] = {"have": s.get("subs_net"), "need": c["subs"]}
    xs, xl = out["shorts"]["x_median"], out["long"]["x_median"]
    out["nearer"] = "長尺" if xl <= xs else "ショート"
    return out


def gate_lines(cmp: dict, next_row: dict | None = None, *, snapshot: dict | None = None,
               uploaded_path: Path | None = None, topics: list[dict] | None = None,
               cv: dict[str, list] | None = None) -> list[str]:
    """`gate_arithmetic()` を `[きょうの1本]` の3行にする。**前提が閉じても消えない行**（門の数は前提ではない）。"""
    try:
        fr = long_watch_fraction(cmp.get("rows") or [], cv)
        dur = _long_duration_min(next_row, uploaded_path, topics)
        g = gate_arithmetic(cmp, snapshot=snapshot, duration_min=dur, frac=fr)
    except Exception as exc:                                       # noqa: BLE001
        return [f"     （収益化の門の行は出せませんでした: {exc}）"]
    s, l, c = g["shorts"], g["long"], g["consts"]
    fr_note = (f"実測 n={l['frac_n']}" if l["frac_measured"] else f"仮 `ASSUMED_LONG_FRAC`・長尺のカーブ 0本")
    out = [
        f"     **収益化の門で数える**（`scripts/eta.py` の門・規則 1本/日 で 1本あたりに直す・0単位・毎周 数え直し）:",
        f"       長尺　　 門2a {c['long_hours']:,.0f}時間/{c['window_days']:.0f}日 に対して いま {l['have_hours']:.1f}時間"
        f" → 要る {l['per_day_hours']:.1f}時間/日 ＝ {l['duration_min']:.0f}分の本が {l['frac']:.0%} 見られて（{fr_note}）"
        f" **{l['need_per_video']:,.0f}回/日** ／ 自分の長尺の生涯 中央値 {_fmt(l['own_median_life'])}"
        f"（要る ×{l['x_median']:,.0f}）・最大 {_fmt(l['own_max_life'])}（×{l['x_max']:,.1f}）",
        f"       ショート 門2b {c['shorts_views']:,.0f}回/{c['shorts_days']:.0f}日 → **{s['need_per_video']:,.0f}回/本**"
        f" ／ 自分の規則の密度の中央値 {_fmt(s['own_median_rule'])}（要る ×{s['x_median']:,.0f}）・最大 {_fmt(s['own_max'])}"
        f"（×{s['x_max']:,.0f}）・いま {int(s['have_90d'] or 0):,}回/90日。**ショートの視聴時間は 門2a に 0 入る**",
        f"     → 門に近い形は **{g['nearer']}**（要る倍率の小さい側）。登録 {int(g['subs']['have'] or 0):,}/{c['subs']:,}人。"
        f" **48時間の再生（上の表）で形を決めないこと** —— あれは門の数ではない。"
        f"ショートへ戻す判定は、この行の倍率が入れ替わった回にだけ出す",
    ]
    return out


def fallback_form(cmp: dict, *, snapshot: dict | None = None, topics: list[dict] | None = None,
                  uploaded_path: Path | None = None, cv: dict[str, list] | None = None) -> str:
    """**決めていない日に機械が選ぶ形**（`scripts/ahead_sweep._today_candidate`）。
    2026-09-03 夜まで「齢48h の中央値の大きい形」＝ 毎日ショート。いまは `gate_arithmetic()` の
    門に近い側。読めない回だけ 48h の中央値へ落ちる。"""
    try:
        g = gate_arithmetic(cmp, snapshot=snapshot,
                            duration_min=_long_duration_min(None, uploaded_path, topics),
                            frac=long_watch_fraction(cmp.get("rows") or [], cv))
        if g.get("nearer") in FORMS:
            return str(g["nearer"])
    except Exception:                                          # noqa: BLE001
        pass
    forms = cmp.get("all") or {}
    return max(FORMS, key=lambda f: ((forms.get(f) or {}).get("median") or 0,
                                     (forms.get(f) or {}).get("n") or 0))


def outside_first(pool: list[dict], topics: list[dict] | None = None) -> list[dict]:
    """池の候補のうち `style: outside_long` の題材を先頭へ（順は保つ）。"""
    tops = {str(t.get("id")) for t in (topics if topics is not None else _topics())
            if str(t.get("style") or "") == "outside_long"}
    return sorted(pool, key=lambda p: 0 if str(p.get("topic") or "") in tops else 1)


def lines(next_row: dict | None, now: datetime | None = None,
          cmp: dict | None = None, picks_path: Path | None = None,
          topics: set[str] | None = None, cands: list[dict] | None = None,
          untried: list[dict] | None = None) -> list[str]:
    """`run_marker.py --write` の `[次の枠]` の直後に出る塊。API 0単位。"""
    c = compare(now=now) if cmp is None else cmp
    day = for_day(now)
    out = [
        "[きょうの1本] **形（ショート／長尺）と族を、いまの数で決めてから `improve` に入ること**"
        "（規則3 は「次の枠で出る1本」を良くする規則で、**その1本がどの形かは規則が決めていません**。"
        "形は `per_video` を 0単位 で動かす、いちばん大きい手です）",
    ]
    draft_form = None
    draft_fam = ""
    if next_row:
        draft_form, how = _form_of(next_row, _measured_forms())
        draft_fam = family_of(next_row.get("topic"))
        out.append(f"     次に出る本 `{next_row.get('video_id')}` は **{draft_form}**"
                   f"（題材 `{next_row.get('topic')}`・族 `{draft_fam or '?'}`・形の決め方 {how}）")
    rd = c.get("recent_days", 14)
    out.append(f"     齢 {AGE_HOURS}時間 でそろえた1本あたり再生（`data/views.jsonl`・API 0単位・"
               f"{c.get('n_rows', 0)}本）:")
    for f in FORMS:
        a, r, ru, lf = (c["all"].get(f, {}), c["recent"].get(f, {}),
                        c["rule"].get(f, {}), c["life"].get(f, {}))
        ln = (f"       {f:　<4} n={a.get('n', 0):<4} 中央値 {_fmt(a.get('median')):>8}  "
              f"p90 {_fmt(a.get('p90')):>8}  最大 {_fmt(a.get('max')):>8}"
              f" ／ 直近{rd}日 n={r.get('n', 0)} 中央値 {_fmt(r.get('median'))}")
        if f == "ショート":
            ln += (f" ／ 規則の密度（≤{RULE_BAND_MULT}本/日）の日 n={ru.get('n', 0)} "
                   f"中央値 {_fmt(ru.get('median'))}")
        else:
            ln += (f" ／ 7日以上たった本の生涯 n={lf.get('n', 0)} "
                   f"中央値 {_fmt(lf.get('median'))} 最大 {_fmt(lf.get('max'))}")
        out.append(ln)
    if draft_form:
        rl = _ratio_line(c, draft_form)
        if rl:
            out.append(rl)
    # **門の数は前提ではないので、前提が閉じても消えない**（2026-09-03 夜・`gate_arithmetic` の註）。
    out.extend(gate_lines(c, next_row))
    out.extend(outside_lines(c, "ショート", now=now))
    fams = c.get("families") or []
    if fams:
        out.extend(_loo_lines(c.get("family_loo") or {}))
        # **中身の側に当てる数字が在るか**（維持率・日の揺れ）を、族の行のすぐ下に（2026-09-03・`src/hold.py`）。
        #     族が雑音なら次に見るのは「中身のどこか」ではなく「中身に当てる数字が在るか」で、
        #     無いなら残りの時間は日の側（配信）へ向ける —— その判定を毎周 数え直して出す。
        #     貯めの補充（Analytics）は実物の呼び出し（`cmp is None`）のときだけ。
        try:
            from . import hold                                     # noqa: PLC0415
            out.extend(hold.lines(c.get("rows") or [], next_row,
                                  fetch=(cmp is None and picks_path is None)))
        except Exception as exc:                                   # noqa: BLE001
            out.append(f"     （維持率の行は出せませんでした: {exc}）")
        top = [f for f in fams if f["enough"]][:6]
        out.append("     族（`calc`）ごとのショートの **日で割った残差**（上位・n≥%d・括弧は生の 48時間 中央値）: "
                   % FAMILY_MIN_N
                   + " ／ ".join(f"`{f['family']}` {_fmtx(f['median'])}"
                                 f"({_fmt(f.get('views_median'))}・n={f['n']})" for f in top))
        if draft_fam:
            rk, st = family_rank(fams, draft_fam)
            if st:
                out.append(f"     次に出る本の族 `{draft_fam}` は {rk}位／{len(fams)}族"
                           f"（残差 {_fmtx(st['median'])}・生 {_fmt(st.get('views_median'))}・n={st['n']}）")
            else:
                out.append(f"     次に出る本の族 `{draft_fam or '?'}` は、ショートで測ったことがありません")
    rows_all = c.get("rows") or []
    pool = pool_candidates(fams=fams, exclude=(next_row or {}).get("video_id"),
                           rows=rows_all) if cands is None else cands
    if pool:
        out.append(f"     池に在る private のショート {len(pool)}本（作らずに、その日の枠へ "
                   f"`--move` できる・50単位）—— 族の残差（日で割った）の高い順:")
        for p in pool[:5]:
            out.append(f"       `{p['video_id']}`  {str(p['title'] or '')[:36]}"
                       f"　族 `{p['family'] or '?'}` {_fmtx(p.get('fam_res'))}"
                       f"({_fmt(p['fam_median'])}・n={p['fam_n']})")
    un = unposted_topics(fams=fams, rows=rows_all) if untried is None else untried
    if un:
        out.append(f"     まだ作っていない `s-` の題材（`calc` 在り）{len(un)}件 —— 族の残差（日で割った）の高い順:")
        for u in un[:4]:
            out.append(f"       `{u['topic']}`  {str(u['title'] or '')[:36]}"
                       f"　族 `{u['family'] or '?'}` {_fmtx(u.get('fam_res'))}"
                       f"({_fmt(u['fam_median'])}・n={u['fam_n']})")
    if draft_form:
        oth = other_form_topic(next_row.get("topic") if next_row else None, topics)
        if oth:
            other = "長尺" if draft_form == "ショート" else "ショート"
            flag = " --short" if other == "ショート" else ""
            out.append(f"     [!] **同じ題材が、もう一方の形（{other}）で台帳に在り、まだ作っていません**: "
                       f"`{oth}`（作るのは 0単位・上げるのは `videos.insert`＝日枠の外）:")
            out.append(f"       python -m src.pipeline --topic {oth}{flag} --dry-run"
                       f" && python scripts/inspect_build.py {oth}"
                       f" && python scripts/upload_only.py {oth} --draft")
    cur = current(day, picks_path)
    hour = _hour_default(day)
    if cmp is None and picks_path is None:
        out.extend(outside_long_lines(day, cur, now=now))
    if cur:
        vid = cur.get("video_id")
        out.append(f"     **{day:%m/%d} の1本: {cur.get('form')} `{cur.get('topic')}`"
                   f"{' ＝ `' + str(vid) + '`' if vid else ''}**"
                   f"（{str(cur.get('at'))[11:16]} JST に決めた・理由: "
                   f"{str(cur.get('why'))[:90]}）。**変えるなら、数字で上書きすること**"
                   f"（同じコマンドをもう一度）。")
        if vid:
            out.append(f"     → **{day:%m/%d}（JST）になってから**、この本を その日の枠へ"
                       f"（1本 50単位・先の日付には置かない）:")
            out.append(f"       python scripts/reschedule.py --move {vid} {day:%Y-%m-%d}T{hour:02d}:00")
            if next_row and next_row.get("video_id") and next_row.get("video_id") != vid:
                out.append(f"     　 次に出る本 `{next_row.get('video_id')}` は**消さない**"
                           f"（private のまま池に残す。決めた本が出せなくなった日の代わり）。")
        elif draft_form and cur.get("form") and cur.get("form") != draft_form:
            out.append(f"     [!] **決めた形（{cur.get('form')}）と、次に出る本の形（{draft_form}）が"
                       f"違います** —— 決めた題材を作って `--draft` で上げること"
                       f"（上げた最新の下書きが `[次の枠]` になります）。")
    else:
        pick_form = draft_form or "ショート"
        pick_topic = (next_row or {}).get("topic") or "<題材>"
        out.append(f"     **{day:%m/%d} の1本は、まだ決めていません。** 決めるまで `improve` に"
                   f"入らないこと（磨く相手を先に決める）:")
        out.append(f"       python -m src.daily_pick --pick {pick_form} {pick_topic}"
                   f" --why \"<上の数字で>\"        # これから作る／下書きのまま出す")
        if pool:
            out.append(f"       python -m src.daily_pick --pick ショート {pool[0]['topic']}"
                       f" --video {pool[0]['video_id']} --why \"<上の数字で>\"   # 池の本を使う")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pick", nargs=2, metavar=("形", "題材"),
                    help="その日の1本を決めて残す（ショート／長尺 と 題材ID）")
    ap.add_argument("--video", default=None, help="池に在る本を使うなら、その動画ID")
    ap.add_argument("--why", default="", help="理由（数字で1行。--pick に必須）")
    ap.add_argument("--day", default=None, help="YYYY-MM-DD（省略時は for_day()）")
    args = ap.parse_args(argv)
    if args.pick:
        form, topic = args.pick
        day = date.fromisoformat(args.day) if args.day else None
        try:
            row = record(form, topic, args.why, day=day, video_id=args.video)
        except ValueError as exc:
            print(f"[daily_pick] {exc}")
            return 2
        print(f"[daily_pick] 決めました: {json.dumps(row, ensure_ascii=False)}")
        return 0
    try:
        from . import next_slot
        nxt = next_slot.next_video()
        if nxt is None:
            got = next_slot.drafts()
            nxt = got[0] if got else None
    except Exception:                                          # noqa: BLE001
        nxt = None
    for ln in lines(nxt):
        print(ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
