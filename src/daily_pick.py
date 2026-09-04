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
import math
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
#: 焼いた本の台本の控え（`treated_count()` が「外の型を写したか」を実物で見る所）。
QUEUE = ROOT / "data" / "critique_queue"
JST = timezone(timedelta(hours=9))

FORMS = ("ショート", "長尺")

#: `data/daily_pick.jsonl` の行の種類（2026-09-04 19:0x に足した）。
#: `decide` ＝ **回が数で決めた行**。`carry` ＝ **焼き直しで動画IDだけ写した行**。
#: 数えるとき（`_standing_chain_len()`）も、理由を引くとき（`lines()`）も、
#: **`carry` は決めではありません** —— 回が1度も触っていない行だからです。
#: **欄の無い古い行は `decide` として読みます**（`pick_kind()`）。
PICK_KIND_DECIDE = "decide"
PICK_KIND_CARRY = "carry"
PICK_KINDS = (PICK_KIND_DECIDE, PICK_KIND_CARRY)


def pick_kind(row: dict) -> str:
    """その行が「決め」か「写し」か。**欄が無い古い行は「決め」**（2026-09-04 より前の行）。

    ただし欄の無い行でも、`replace_video()` が書いた古い形（`why` が
    「焼き直し: `<旧ID>` → 」で始まる）は **写し**として読みます ——
    **その形の行は 09-03〜09-04 に 11件 あり、全部「決め」として数えられていました。**
    """
    k = str((row or {}).get("kind") or "").strip()
    if k in PICK_KINDS:
        return k
    if str((row or {}).get("why") or "").startswith("焼き直し: `"):
        return PICK_KIND_CARRY
    return PICK_KIND_DECIDE


def last_decided(rows: list[dict]) -> dict | None:
    """**`at` がいちばん新しい「決め」の行**（写しを飛ばす）。無ければ None。

    ファイルの並びで見ないこと —— `_by_at()` の註（併合で行が入れ替わります）。
    """
    dec = _by_at([r for r in (rows or []) if pick_kind(r) == PICK_KIND_DECIDE])
    return dec[-1] if dec else None

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


def _by_at(rows):
    """`at` の古い順に並べる（読めない `at` はファイルの並びのまま後ろへ）。**安定**。

    ## なぜ要るか（2026-09-04 19:3x に踏んだ。**その日の1本が古い本に戻っていました**）

    `data/daily_pick.jsonl` は `merge=union` で、**同じ枝を複数の回が同時に走ります**。
    併合すると **行はファイルの中で時刻順に並びません。** 実測（この回の 19:3x）::

        19:30:50  carry   e6sLHLmPhrk   ← 焼き直しが差し替えた新しい本
        19:24:02  decide  XwB8nxtN5D8   ← 別の回が 6分前に書いた行（併合で後ろに来た）

    `current()` は「ファイルの最後の行」を返していたので、**差し替えたはずの
    古い本 `XwB8nxtN5D8` を「09/05 の1本」として返していました** ——
    `ahead_sweep._today_candidate` はその ID をそのまま枠へ置くので、
    **62分 かけて焼いた新しい本は池に眠り、直す前の本が公開されます。**
    これは `replace_video()` が塞いだはずの穴が、**併合の並びから開き直したもの**です。

    **覆る条件**: `data/daily_pick.jsonl` を1行1日の上書き（union ではない）にしたら、
    この並べ替えは要りません。
    """
    def key(pair):
        i, r = pair
        try:
            return (0, datetime.fromisoformat(str(r.get("at"))), i)
        except (TypeError, ValueError):
            return (1, datetime.min.replace(tzinfo=JST), i)
    return [r for _, r in sorted(enumerate(rows), key=key)]


def current(day: date, path: Path | None = None) -> dict | None:
    """その日の1本として**最後に**残した決定。無ければ `None`。

    **「最後」は `at` の新しさで見ます**（ファイルの並びではありません）——
    `_by_at()` の註。併合で行が入れ替わると、ファイルの最後は最新とはかぎりません。
    """
    rows = _by_at([r for r in _jsonl(path or PICKS)
                   if r.get("for_day") == day.isoformat()])
    return rows[-1] if rows else None


def probe_hold(form: str, day, *, now=None, topics: list[dict] | None = None,
               uploaded_path: Path | None = None) -> str:
    """**先読みの門がまだ読めないうちに、試す形が「次の未決の日」まで取るのを止める。**
    止めるなら理由の1行、止めないなら `""`。**API 0単位**（控えを読むだけ）。

    ## なぜ要るか（2026-09-04 21:5x・最適化の回。「最適化されてんの？」→ **いいえ** の理由を1つ潰す）

    `outside_long_readout()` は、試す本が 齢24h に届いていないとき、こう印字します ——
    **「24h の先読みの門 30回 まで待つ。次の未決の日は、それまで決めないこと」。**
    **散文です。誰も止めません。** 実測（`data/daily_pick.jsonl` を `at` で並べた）:

        09-03 02:03 長尺 …… 09-04 21:26 長尺   ＝ **17回 連続で同じ形**
        そのうち 09-05（＝ 次の未決の日）の決めは、試す本 `1huadpEk6HY` が
        齢 9h（門は 齢24h）のときに書かれています —— **門が開く前に、次の枠が埋まった。**

    同じ画面が、同じ回に、こうも印字していました:

        **試す形（長尺）が枠を 2日ぶん 取っています**（09-04〜09-05・既定の形は ショート）
        規則は 1本/日 なので、これは新しく出る本の **100%**
        そこから 48h の判定に届いた本: **0本／2本**
        [!] 取った枠から、まだ 1本も 48h の観測が出ていません —— **枠だけ減って、前提は 1件も進んでいません**

    ＝ 前提は 1本 で判る（`falsified_if` は 48h・100回・n=1）のに、枠は 2本 取られ、
    その 2本目 を取る根拠は「1本目 がまだ何も言っていないこと」でした。
    **答えが出ていないことが、同じ手をもう一度 引く理由になる形**です。だから鎖は切れません。
    実測の値: `data/eta.jsonl` の 再生/日(7d) は 6,299（08-25）→ **943**（09-04）＝ **-85%**。

    **止めるのは「次の未決の日」だけです** —— 試す本そのもの（同じ日）も、
    門が開いたあと（齢24h 以降）も、48h の判定も、**1つも動かしません**。
    前提は n=1 で判るので、門が開くまで待っても 期限（09-07）には間に合います。

    ## 通す口

    数字で上書きするのは自由です（オーナーの「固定は目標の本文だけ」）——
    `record(..., anyway="<数字を含む理由>")` ／ CLI は `--anyway "<理由>"`。
    **その行は `data/daily_pick.jsonl` に `anyway` として残り、次の回が実物と並べます。**

    ## 覆る条件

    - 前提「外の作り方を写した長尺」が閉じたら（当たっても外れても）、
      `style: outside_long` の本が出なくなるので、ここは自分で黙ります。
    - 規則1（1日1本）が外れて枠が 1日 2本以上 になったら、**枠の取り合いではなくなる**ので
      この止めは要りません（`house_rule` を見て落とすこと）。
    - `config` の題材に `style` が読めない回は `""`（止めない）—— **推測で止めないこと。**
    """
    if str(form) != "長尺":
        return ""
    t = (now or datetime.now(timezone.utc)).astimezone(JST)
    if isinstance(day, date):
        want = day
    else:
        try:
            want = date.fromisoformat(str(day))
        except (TypeError, ValueError):
            return ""
    tops = {str(x.get("id")): str(x.get("style") or "")
            for x in (topics if topics is not None else _topics())}
    if not tops:
        return ""
    best: tuple[datetime, str] | None = None
    for vid, r in _latest_uploaded(uploaded_path).items():
        if tops.get(str(r.get("topic") or "")) != "outside_long":
            continue
        pub = _parse(r.get("at"))
        if pub is None or pub > t:
            continue
        if (t - pub).total_seconds() / 3600 >= 24:   # 門は開いている（readout が読む）
            continue
        if want <= pub.astimezone(JST).date():
            continue                                 # 試す本そのものの日 ＝ 止めない
        # **札ではなく実物で選ぶ**（`treated_probe` の註・2026-09-04 22:2x）。
        # `style: outside_long` は「これから外の型で作るつもり」の札で、
        # 実物がその型に届いているとは限りません。実測 `1huadpEk6HY` は 4脚中 3脚 ✗ ＝
        # 前提「外の作り方を写した長尺」を閉じられない本でした。
        # **閉じられない本の 24h を待って、次の枠を止めない。**
        # 外すのは `"no"`（控えが読めた上で脚が✗）だけ —— `"unknown"`（控えが読めない）では
        # 外しません。閂を外すほうにも証拠が要ります（`treated_probe` の註）。
        if treated_probe(vid)[0] == "no":
            continue
        if best is None or pub > best[0]:
            best = (pub, str(vid))
    if best is None:
        return ""
    pub, vid = best
    opens = (pub + timedelta(hours=24)).astimezone(JST)
    obs = _latest_obs(vid) or {}
    seen = (f"齢 {float(obs.get('hours') or 0):.0f}h で {int(obs.get('views') or 0)}回"
            if obs else "控えに観測なし")
    return (f"{want} は「次の未決の日」で、試す形（長尺）の先読みの門がまだ読めません。"
            f"試す本 `{vid}`（{seen}）の 24h の門（{OUTSIDE_24H_GATE}回）は "
            f"{opens:%m/%d %H:%M} JST に開きます —— `outside_long_readout` の"
            f"「次の未決の日は、それまで決めないこと」を、ここで実際に止めています。"
            f"前提は n=1 で判ります（`falsified_if` 48h・{OUTSIDE_48H_GATE}回）。"
            f"数字で上書きするなら `--anyway \"<数字を含む理由>\"`")


#: **決めが言うべき数の既定値**（2026-09-04 22:5x・最適化の回）。
#: `record(kind="decide")` は `expected` が無いと通りません。機械の口
#: （`scripts/ahead_sweep`）は、選んだ形の**実測の齢48h 中央値**をそのまま宣言します。
def form_median_48h(form: str, *, cmp: dict | None = None,
                    rows: list[dict] | None = None) -> float | None:
    """**その形の、実測 齢48h の中央値**（`data/views.jsonl` だけ・**API 0単位**）。

    返りは `float`（測れなければ `None`）。`record()` の `expected` の既定と、
    `record()` が断るときの文面で「相手の形は何回か」を出すのに使います。
    """
    try:
        c = cmp if cmp is not None else compare(rows=rows)
        st = (c.get("all") or {}).get(str(form)) or {}
        m = st.get("median")
        return float(m) if m is not None else None
    except Exception:                                          # noqa: BLE001
        return None


def standing_days(video_id: str | None, *, path: Path | None = None) -> list[str]:
    """**その動画IDが「その日の1本」として立っている日**（`for_day` の一覧・古い順）。
    立っていなければ空。**API 0単位・`data/daily_pick.jsonl` だけを読みます。**

    `current()` と同じ「最後に残した決定」を、日ごとに引きます ——
    途中で別の本へ差し替えられた日は、ここには出ません。
    """
    vid = str(video_id or "").strip()
    if not vid:
        return []
    rows = _by_at(list(_jsonl(path or PICKS)))
    last: dict[str, str] = {}
    for r in rows:
        d = str(r.get("for_day") or "")
        if d:
            last[d] = str(r.get("video_id") or "").strip()
    return sorted(d for d, v in last.items() if v == vid)


def day_guard(video_id: str | None, day: date | None, *,
              path: Path | None = None, now: datetime | None = None) -> str:
    """**`--day` を省いた `--pick` が、別の日の決めを黙って書き換えるのを止める。**
    止めるなら理由の1行、通すなら `""`。**API 0単位。**

    ## なぜ要るか（2026-09-05 00:38 に踏んだ。**踏んでから 24秒 で気づけたのは偶然です**）

    この回は「09/05 の1本を据え置く」つもりで、`--day` を付けずにこう撃ちました::

        python -m src.daily_pick --pick 長尺 nenkin-... --video GFvAcxvDmYM --why "…09/05 の…"

    `for_day()` は **「きょうの枠が埋まっていれば あす」** を返します。09/05 の枠は
    00:01 にもう埋まっていたので、返ったのは **09-06**。結果、**27分前（00:27）に
    別の回が数で決めた 09/06 の1本（ショート `DtpnSVFDtAE`）が、
    長尺 `GFvAcxvDmYM` で上書きされました。**

    - **理由の本文は 09/05 の話をしています。** 行の `for_day` だけが 09-06 です ——
      つまり**読んでも食い違いに気づけない行**が1本 増えます
    - 上書きされた側は `merge=union` の追記なので**消えてはいません**。
      しかし `current()` は「最後の1行」を返すので、**次の回が読むのは上書きした側**です
    - `ahead_sweep._today_candidate` はその ID をそのまま枠へ置くので、
      **09/06 の枠に、09/05 に公開ずみの本が入りかけていました**

    ## 何で止めるか

    **`--video` が、別の日の「その日の1本」として立っているとき**だけ止めます。
    そのときの `--day` の省略は、ほぼ確実に「据え置きのつもり」です ——
    据え置きたい日は `--video` が立っている日のほうで、`for_day()` の返す
    「次の未決の日」ではありません。

    **止まったら `--day` を書くこと**（`--day` を明示した `--pick` は素通しです。
    本当に別の日へ移したい回は、そう書けます）。

    ## 覆る条件

    - `for_day()` が「引数の `--video` が立っている日」を先に見るようになったら、
      この門は要りません（そのとき `for_day` を直して、ここを消すこと）
    - `data/daily_pick.jsonl` が1日1行の上書きになったら、上書きは事故ではなく
      仕様になるので、止める理由が変わります
    """
    if day is not None:
        return ""
    vid = str(video_id or "").strip()
    if not vid:
        return ""
    days = standing_days(vid, path=path)
    if not days:
        return ""
    target = for_day(now).isoformat()
    if target in days:
        return ""
    return (
        f"`{vid}` は **{'／'.join(days)} の「その日の1本」として立っています**が、"
        f"`--day` を省いたので書き先は **{target}** です"
        f"（`for_day()` は『きょうの枠が埋まっていれば あす』を返します）。"
        f" そのまま書くと **{target} の決めを黙って上書きします**"
        f"（2026-09-05 00:38 に実際に踏み、27分前の別の回の決めを潰しました）。"
        f" 据え置きなら `--day {days[-1]}`、本当に {target} へ移すなら `--day {target}` と"
        f"**日付を書くこと**。"
    )


def restated_pick_block(form: str, topic: str, video_id: str | None, day: date,
                        *, expected: float | None = None,
                        path: Path | None = None) -> str:
    """**すでに立っている決めを、1文字も変えずにもう一度書くのを止める。**
    通れば `""`、止めるならその理由の1行。**API 0単位・`data/daily_pick.jsonl` だけ。**

    ## なぜ要るか（2026-09-05 02:0x・最適化の回に数で踏んだ）

    「最適化されてんの？（過去の実行に対して）」に、この回が実物で数えた ——

        `data/daily_pick.jsonl` の **09/05 の枠だけで決めが 24回**。
        うち **14回 は、直前の行と 形・題材・動画ID が完全に同じ**（＝ 何も変えていない）。
        最後の 8回（09-04T21:31 → 09-05T01:48）は **全部 `GFvAcxvDmYM` のまま**で、
        変わったのは `why` の長さだけ（約200字 → 約600字）。
        同じ 5日で `data/runs.jsonl` の ship は 240件、**測れた動きは 26件・そのうち
        到達日が動いたのは 0件**、再生/日(7d) は 6,299 → 943（**-85%**）。

    ＝ **回は「決め直し」を仕事として選び続け、決めは1度も変わっていません。**
    これは怠慢ではなく**構造**です: `--pick` は毎回 撃てて・安くて・長い `why` が付き・
    commit になり・ship の印が立つ。**止める門が無い限り、いちばん通りやすい手**です。

    既にある門は**中身**を見ます（`untreated_slot_block` は処置でない本を落とす、
    `probe_hold` は先読みの前に取るのを止める）。**繰り返しを見る門はありませんでした** ——
    実測: `untreated_slot_block`（09-04 19:5x）が入ったあとに、同じ本の決めが **8回** 書かれています。
    その註が自分で書いたとおり「**印字は選び直しを止めません**」——
    ここは**同じ決めの再掲**を止める側です。

    ## 何を通すか

    止めるのは「**決定も、反証できる数も、どちらも変わっていない**」行だけです。
    - 形・題材・動画ID のどれかが変われば **通ります**（本物の決め直し）。
    - それらが同じでも `--expected`（齢48h の見込み）が変われば **通ります** ——
      実測 09-05T01:17 は 8.0 → 1.0 の正直な訂正で、**次の回が実物と並べる数**が変わっています。
    - `kind="carry"`（焼き直しの写し）は決めではないので**見ません**。

    ## `--anyway` では越えられません

    `--anyway` は `probe_hold`（先読みの門）を数字で越えるための口です。
    こちらは越えられません —— **再掲が買うものは定義上 0** で、
    越える理由に書ける数が存在しないからです。理由が在るなら、それは
    `--expected` の数か、決定そのものの変更として出るはずです。

    ## 覆る条件

    - `data/daily_pick.jsonl` が1日1行の上書きになったら、再掲は事故ではなく上書きなので、
      この門は要りません。
    - 決めの `why` だけを差し替える口（`--rewhy` のような）が出来たら、
      「理由を直したい回」はそちらへ回るので、ここは決定と数だけを見れば足ります。
    - `expected` を必須にしている門（`record` の中）が外れたら、
      「数が変わったか」で通す判定が効かなくなります。そのときは決定だけを見ること。
    """
    cur = current(day, path)
    if not cur or pick_kind(cur) != PICK_KIND_DECIDE:
        return ""
    same = (str(cur.get("form") or "") == str(form)
            and str(cur.get("topic") or "") == str(topic)
            and str(cur.get("video_id") or "") == str(video_id or ""))
    if not same:
        return ""
    old_exp = cur.get("expected_48h")
    if (old_exp is None) != (expected is None):
        return ""
    if old_exp is not None and expected is not None and abs(float(old_exp) - float(expected)) > 1e-9:
        return ""
    rows = [r for r in _by_at(list(_jsonl(path or PICKS)))
            if str(r.get("for_day") or "") == day.isoformat()
            and pick_kind(r) == PICK_KIND_DECIDE]
    n = 0
    for r in reversed(rows):
        if (str(r.get("form") or "") == str(form)
                and str(r.get("topic") or "") == str(topic)
                and str(r.get("video_id") or "") == str(video_id or "")):
            n += 1
        else:
            break
    since = str((rows[len(rows) - n].get("at") if n and n <= len(rows) else cur.get("at")) or "")[:19]
    return (f"**その決めはもう立っています —— 形・題材・動画ID・見込み が1つも変わっていません**"
            f"（{day.isoformat()} = {form} / {topic} / {video_id or '—'} / 見込み {old_exp}。"
            f"同じ決めが すでに {n}回・{since} から）。**この回の ship は決めではありません。**\n"
            f"  実測（`scripts/optimized.py` 2026-09-05）: 直近5日の ship 240件 のうち"
            f" 到達日が動いたのは **0件**、種別べつの歩留りは `verdict` 7回中3件(43%) 対"
            f" それ以外 233回中3件(1.3%)。**決め直しは、この 1.3% の側です。**\n"
            f"  通す道は3つだけ: (1) 形・題材・動画ID のどれかを実際に変える"
            f"（＝ 本物の決め直し） (2) `--expected` を数で訂正する"
            f"（次の回が実物と並べる数が変わる） (3) **決めを触らず、期日の来た前提を1件 閉じる**"
            f"（`python scripts/deadline_check.py --fit` / `config/hypotheses.yaml`）。"
            f"`--anyway` では越えられません（再掲が買うものは 0 なので、越える理由に書く数が在りません）。")


def record(form: str, topic: str, why: str, *, day: date | None = None,
           now: datetime | None = None, path: Path | None = None,
           video_id: str | None = None, expected: float | None = None,
           kind: str = PICK_KIND_DECIDE, rebaked_from: str = "",
           anyway: str = "", topics: list[dict] | None = None,
           uploaded_path: Path | None = None) -> dict:
    """その日の1本を決めて残す（追記・`merge=union`）。

    `kind` は **その行が「決め」か「写し」か**。既定は `"decide"`（回が数で決めた行）で、
    `replace_video()` だけが `"carry"`（焼き直しで ID を写しただけの行）を書きます。
    **この欄が無かったとき、写しの行は決めと同じ重みで数えられていました** ——
    `_standing_chain_len()` の「N回 連続で同じ形」も、`lines()` の「理由」も、
    **回が1度も触っていない行を根拠に印字していました**（2026-09-04 19:0x に踏んだ）。
    """
    if form not in FORMS:
        raise ValueError(f"形は {FORMS} のどれか: {form!r}")
    if not (why or "").strip() or not re.search(r"\d", why):
        raise ValueError("`--why` は数字を含む1行が要ります（次の回が実物と並べます）")
    # **`--expected` は必須です**（2026-09-04 22:5x・最適化の回に門にした）。
    #
    # `expected_lines()` は 09-04 19:2x に「次に決める回は `--expected` を付けること」と
    # **印字する**形で入りました。**その直後の決め（22:24・09-05 の長尺）も null です。**
    # 実測 `data/daily_pick.jsonl` 31行 中 **`expected_48h` が入っているのは 4行**。
    # `run_marker.py` が同じことを自分の註に書いています ——
    # **「註や警告ではなく、通さないことだけが効いています」**。だから通さない側にしました。
    #
    # **なぜ、この欄だけ門にする価値があるか**（この回に撃って出た数）:
    # 齢48h の中央値は **ショート 168回（n=216）／長尺 1回（n=36）** で二桁 違います。
    # それでも 31件 の決めのうち **20件 が同じ（長尺・`nenkin-...-handan`）** で、
    # その題材は 6本 焼かれて **1本も公開されていません**（全部 private・0回）。
    # 数を言わない決めは**外れようがない**ので、散文だけで何度でも同じ形を選べます。
    # **番号を1つ置かせれば、次の回が `expected_lines()` で実物と並べます。**
    #
    # **覆る条件**: 宣言が 5件 たまっても実物との差が形を1度も入れ替えないなら、
    # この門は形の判断に効いていません（`expected_lines()` の覆る条件と同じ）。**そのときは外すこと。**
    if kind == PICK_KIND_DECIDE and not isinstance(expected, (int, float)):
        med = {f: form_median_48h(f) for f in FORMS}
        seen = "／".join(f"{f} {('%s回' % f'{med[f]:,.0f}') if med[f] is not None else '—'}"
                         for f in FORMS)
        raise ValueError(
            "`--expected <回>` が要ります（決めには 齢48h の見込みを数で置くこと）。"
            f" 実測の 齢48h 中央値: {seen}。"
            " **選んだ形が負けている側なら、その数を上回る見込みを、根拠と一緒に置くこと。**"
            " 外れてよい数です（`--moves` と同じ）—— 次の回が `expected_lines()` で実物と並べます。")
    # **その見込みが、食う枠のぶんを払えるか**（2026-09-05・最適化の回に門にした）。
    #
    # `--expected` の門（すぐ上）は 09-04 22:5x に入りましたが、**数を1つ置かせるだけ**で、
    # **その数が枠の機会費用に足りているかは、どこも見ていませんでした。**
    # 実測（この回に `data/daily_pick.jsonl` を読んだ）——
    # 09-05T00:38 の決めは **長尺・`expected_48h=8.0`・`anyway` 空**。
    # 同じ時刻の `src/slot_cost.slot_value()` は **1枠 ＝ 1,049回**（ショート・規則の密度・
    # 齢48h の中央値）。**8回 は その 1/131 です。** それでも門は通しました。
    #
    # `src/slot_cost.py` は 09-05 00:20 にこの比を計算して **印字**していました。
    # `run_marker.py` が自分の註に書いているとおり ——
    # **「註や警告ではなく、通さないことだけが効いています」**。だから通さない側にしました。
    #
    # **禁止ではありません。** `--anyway <数字を含む1行>` で越えられます（`probe_hold` と同じ口）。
    # 越えた行は `anyway` に残り、次の回が実物と並べます。
    #
    # **素振り（`path` を渡した回）では立ちません** —— 本番の控えを守る門なので、
    # `uploaded_path` の註と同じ切り分けにしています。CLI に `--path` はありません。
    #
    # **覆る条件**: どの形でも規則の密度の中央値が入れ替われば、`slot_value()` の勝者は
    # 自分で入れ替わり、この門はその形を通します（**形の禁止ではありません**）。
    # 標本が 0本 で機会費用が測れないときは、この門は立ちません。
    if (kind == PICK_KIND_DECIDE and path is None
            and not (anyway or "").strip()
            and isinstance(expected, (int, float))):
        try:
            from . import slot_cost                              # noqa: PLC0415
            _sv = slot_cost.verdict(float(expected), form=form, now=now)
        except Exception:                                        # noqa: BLE001
            _sv = None
        if _sv is not None and _sv.get("ok") is False:
            raise ValueError(
                f"`--expected {float(expected):,.0f}回` では、この1枠のぶんを払えません。"
                f" {_sv['why']}"
                f" **形を {_sv.get('best')} にするか、"
                f"`--anyway <数字を含む1行>` で越えること**"
                "（越えた行は控えに残り、次の回が実物と並べます）。")
    # **先読みの門が開く前に「次の未決の日」まで試す形が取るのを止める**（`probe_hold` の註）。
    # `kind="carry"`（焼き直しの写し）は決めではないので通します。
    #
    # **上げの控えは、決めの控えと同じ並びから読みます** —— `path` を別に渡した回
    # （試験・素振り）が、**本番の `data/uploaded.jsonl` で止められないため**。
    # これを書く前は、`path=tmp/picks.jsonl` の試験 9本 が本番の上げ帳を読んで赤くなりました。
    up = uploaded_path
    if up is None and path is not None:
        up = Path(path).parent / "uploaded.jsonl"
    # **`--day` を省いた決めが、別の日の決めを黙って上書きするのを止める**（`day_guard` の註）。
    if kind == PICK_KIND_DECIDE:
        _dg = day_guard(video_id, day, path=path, now=now)
        if _dg:
            raise ValueError(_dg)
    if kind == PICK_KIND_DECIDE and not (anyway or "").strip():
        hold = probe_hold(form, day or for_day(now), now=now, topics=topics,
                          uploaded_path=up)
        if hold:
            raise ValueError(hold)
    # **門の算が指す形と違う形で決めるのを止める**（`path_form_hold` の註・2026-09-05 02:xx）。
    # `kind="carry"`（焼き直しの写し）は決めではないので通します。
    #
    # **素振り（`path` を渡した回）では立ちません** —— 本番の控えを守る門なので、
    # すぐ上の `slot_cost` の門と同じ切り分けにしています（CLI に `--path` はありません）。
    if (kind == PICK_KIND_DECIDE and path is None
            and not (anyway or "").strip()):
        _pf = path_form_hold(form, now=now, uploaded_path=up)
        if _pf:
            raise ValueError(_pf)
    # **同じ決めの再掲を止める**（`restated_pick_block` の註・2026-09-05 02:0x）。
    # `--anyway` では越えられません（越える理由に書ける数が存在しないため）。
    if kind == PICK_KIND_DECIDE:
        _rs = restated_pick_block(form, topic, video_id, day or for_day(now),
                                  expected=expected, path=path)
        if _rs:
            raise ValueError(_rs)
    if (anyway or "").strip() and not re.search(r"\d", anyway):
        raise ValueError("`--anyway` も数字を含む1行が要ります（止めを越える理由は数で）")
    t = (now or datetime.now(timezone.utc)).astimezone(JST)
    row = {
        "at": t.isoformat(timespec="seconds"),
        "for_day": (day or for_day(now)).isoformat(),
        "form": form, "topic": topic, "video_id": video_id, "why": why.strip(),
        "expected_48h": expected,
        "kind": kind if kind in PICK_KINDS else PICK_KIND_DECIDE,
        "rebaked_from": str(rebaked_from or ""),
        #: 空でなければ **`probe_hold()` の止めを数字で越えた行**（次の回が実物と並べます）。
        "anyway": str(anyway or "").strip(),
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
    rows = _by_at(list(_jsonl(p)))
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
        # **決めの理由は、焼き直しでは1文字も変えません**（2026-09-04 19:0x に直した）。
        # ここは長らく `f"焼き直し: … 前の決め: {why[:140]}"` と**前置き＋140字で切って**
        # 書き直していました。実測（`data/daily_pick.jsonl` 09-04T18:06）——
        # 16:55 に回が数で書いた 約400字 の理由が **「…処置を落と」で切れて**残り、
        # 次の回の `[!!]` はそれを「**前の回の散文**（根拠にしない）」と正しく判定して、
        # **同じ議論をゼロからやり直しました**（18:2x の回で実測・約15分）。
        # 焼き直しは決めではないので、決めの欄（`why`）を触らず、
        # **写したことは別の欄**（`kind="carry"` / `rebaked_from`）に残します。
        why = str(cur.get("why") or "")
        record(str(cur.get("form") or FORMS[1]), str(cur.get("topic") or ""), why,
               day=day, now=now, path=p, video_id=new_id,
               expected=cur.get("expected_48h"),
               kind=PICK_KIND_CARRY, rebaked_from=old)
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
                       "secs_median": …, "n": …, "age_days": …}, "長尺": {…},
           "gap_best": 形（差がいちばん大きい）, "ev_best": 形（実測の見込みがいちばん高い）,
           "best": = `ev_best`}

    `x_p90` は「外の p90 を自分の中央値で割った数」＝ **差**（どれだけ離れているか）。
    自分の中央値が 0 の形は、1回 として割ります（0 で割らない・向きは変わらない）。

    ## **`best` を `x_p90` で選ばないこと**（2026-09-04 16:xx・最適化の回。実測でここを直した）

    2026-09-03 02:03 まで、`best` は `argmax(x_p90)` でした。**その分母は自分の実測です。**
    ＝ **その形が振るわないほど、この選び方はその形を強く推します。** 09/03 02:03 の決めは、
    まさにその数（`外 p90 624,772回 ÷ 自分の長尺 中央値 1回 ＝ ×624,772`）で
    **ショートの決めを上書き**し、以後 `data/daily_pick.jsonl` は **11回 連続で長尺**。
    09/04 の決めも同じ比（`÷ 自分の長尺 中央値 1回 ＝ ×647,526`）で追認しています。

    **その間に実際に起きたこと**（`data/eta.jsonl`・この回に撃った数）:

        再生/日(7d)   08-25 **6,299** → 09-04 **943**（**-85%**）
        登録/日        08-28 1.36 → 09-04 0.93

    **形べつの実測**（`aged_views()`・この回に撃った数）:

        齢 24h   ショート 中央 **153**（n=220）／ 長尺 中央 **1**（n=36）
        齢 48h   ショート 中央 **164**（n=216）／ 長尺 中央 **1**（n=36・36本の合計が 165回）
        齢168h   ショート 中央 **213**（n=173）／ 長尺 中央 **3**（n=23）

    比の分母が自分の失敗なので、この選び方は**止まりません** —— 長尺が 0.1回 になれば
    ×6,475,260 になり、**もっと強く推します。** 上の docstring が書いていた覆る条件
    「自分の長尺の中央値が外の p90 の 1/100 を超えたら書き換える」は、
    **降りる側へは一度も倒れない条件**でした。

    ## だから、選ぶのは **`ev_best`**（実測の見込み ＝ 自分の中央値）です

    1本の枠から実際に取れる数の、偏りのない推定は **自分の実測の中央値**です。
    外の帯は「作り方を写せたら届きうる上」＝ **上振れ**で、その確率は測っていません。
    **測っていない確率を 1.0 として掛けるのが、`x_p90` で選ぶということ**でした。

    `x_p90` は消しません —— **差は「試す理由」としては正しい。**
    ただし試す枠は**有限**で、そこは `explore_budget()` が持ちます
    （規則は 1本/日 なので、**枠は1日1つしかありません**）。

    **覆る条件**: 「外の作り方を写した長尺」が 48h で 100回 の門を越えたら、
    その時点の `own`（長尺の中央値）が上がるので **`ev_best` が自分で長尺へ倒れます。**
    ＝ この直しは長尺の禁止ではありません。**測った数で倒れるようにしただけ**です。
    倒れないなら、それは「まだ写せていない」という測定結果のほうです。
    """
    out: dict = {"best": None, "gap_best": None, "ev_best": None}
    try:
        import sys
        here = str(ROOT / "scripts")
        if here not in sys.path:
            sys.path.insert(0, here)
        import niche_ceiling as nc                                 # noqa: PLC0415
    except Exception:                                          # noqa: BLE001
        return out
    best_x = 0.0
    best_ev = -1.0
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
        # --- **齢で割った側**（2026-09-04 に足した）--------------------------
        #     上の `x_p90` は **外の生涯の累計 ÷ 自分の 48時間**です。公開日を埋めて
        #     数えたら、外の上位に **48時間 以内の本は 1本もありません**
        #     （長尺 齢 中央 203日／ショート 1,729日 ＝ 4.7年）。しかも撃つ窓が
        #     形ごとに違う（`niche_ceiling.SP_FILTERS`: ショート＝全期間・長尺＝今年）ので、
        #     **別々の窓で測った2つを横に並べて形を決めていました。**
        #     1日あたりに直すと、ショートは向きが変わります（自分 524回/日 対 外 18回/日）。
        #     **累計は消しません** —— 累計は「その題でどこまで積めるか」を言っている数で、
        #     1日あたりは「いま追い付けるか」を言っている数。**並べて読むこと。**
        rates = sorted(
            r for r in (
                (int(t.get("views") or 0) / a)
                for t, a in ((t, nc.age_days(t, now)) for t in (row.get("top") or [])
                             if t.get("form") == key)
                if a and int(t.get("views") or 0) > 0)
        )
        ages_d = sorted(
            a for a in (nc.age_days(t, now) for t in (row.get("top") or [])
                        if t.get("form") == key) if a)
        # --- **帯そのものを、齢で割った側**（2026-09-04 22:5x に足した）------
        #     上の `rates` は `row["top"]` ＝ **形ごと 15本**、すぐ上の累計の行
        #     （`x_p90` / `out_p90`）は `summary` ＝ **帯の全部（長尺 335本）**です。
        #     **別々の母集団を、「同じものを1日あたりで」と書いて横に並べていました。**
        #     この回に撃った実測（`niche_ceiling.corpus_rows`・API 0単位）::
        #
        #         ショート  top 15本 中央 18.5回/日  ／ 帯 132本 中央  0.7回/日  **×26.4**
        #         長尺     top 15本 中央 10,533回/日 ／ 帯 334本 中央 31.6回/日  **×333.4**
        #
        #     ＝ 「長尺は 1日あたりで ×21,068 離れている」は **上位15本の産物**で、
        #     帯そのものと比べると ×63 です。**どちらも消しません** —— 上位は
        #     「その題の天井」、帯は「その帯の普通の本」。**n を書いて並べること。**
        #     **覆る条件**: 帯の `published` の被覆が 90% を割ったら、帯の側は出しません
        #     （`niche_ceiling.corpus_published_cover`。埋め方は `--fill-corpus-published`）。
        band_rates: list[float] = []
        band_ages: list[float] = []
        cover = nc.corpus_published_cover().get(key) or {}
        if cover.get("all", 0) >= 30 and cover["have"] / max(1, cover["all"]) >= 0.9:
            for t in nc.corpus_rows(form=key):
                a = nc.age_days(t, now)
                v = int(t.get("views") or 0)
                if a and v > 0:
                    band_rates.append(v / a)
                    band_ages.append(a)
            band_rates.sort()
            band_ages.sort()
        own_rate = own_div / 2.0                      # 自分の中央値は **48時間** の数
        d = {"own": own, "out_p90": s.get("p90"), "out_max": s.get("max"),
             "x_p90": float(s.get("p90") or 0) / own_div,
             "x_max": float(s.get("max") or 0) / own_div,
             "secs_median": (statistics.median(secs) if secs else None),
             "n": s.get("n"), "age_days": age, "source": row.get("source", "api"),
             "n_dated": len(rates),
             "age_median": (ages_d[len(ages_d) // 2] if ages_d else None),
             "out_rate": (rates[len(rates) // 2] if len(rates) >= 3 else None),
             "own_rate": own_rate,
             "x_day": ((rates[len(rates) // 2] / own_rate) if len(rates) >= 3 else None),
             "n_band": len(band_rates),
             "band_age_median": (band_ages[len(band_ages) // 2] if band_ages else None),
             "band_rate": (band_rates[len(band_rates) // 2] if len(band_rates) >= 30 else None),
             "x_day_band": ((band_rates[len(band_rates) // 2] / own_rate)
                            if len(band_rates) >= 30 and own_rate else None)}
        out[form] = d
        # **差（gap）** —— 「試す理由」としては正しい。**選ぶのには使わない**（上の註）。
        if d["x_p90"] > best_x:
            best_x, out["gap_best"] = d["x_p90"], form
        # **見込み（EV）** —— 1本の枠から実際に取れる数の、偏りのない推定。
        #     `own` は 48時間 の中央値（`cmp`）。**測っていない上振れを掛けない。**
        if d["own"] is not None and float(d["own"]) > best_ev:
            best_ev, out["ev_best"] = float(d["own"]), form
    # **`best` は EV のほう。** `x_p90` で選ぶと、振るわない形ほど強く推されます。
    out["best"] = out["ev_best"] or out["gap_best"]
    return out


#: 「自分の長尺は何分か」を、控え（`data/uploaded.jsonl` の `duration_s`）から数える窓。
OWN_LONG_RECENT = 3


def own_long_secs(recent: int = OWN_LONG_RECENT, path: Path | None = None) -> dict:
    """**自分の長尺の尺**（秒）を控えから数える。`{n, median, recent_median, latest}`。API 0単位。

    ## なぜ要るか（2026-09-04 15:2x に踏んだ）

    すぐ下の行は、外の尺の中央（**測った数**）の隣に
    **「自分の長尺は 5分・計算1本・題に数字」と手で書いた字**を並べていました。
    この行の仕事は「だから外の作りを写す価値がある」と言うことなので、
    **写した結果が出たら、いちばん先に古くなる字**です。実測 09/04（`data/uploaded.jsonl`）:

        長尺 236本 の中央   **312.9秒（5.2分）**   ← 「5分」はこの数のこと。正しい
        直近の長尺 6本      1,104〜1,331秒（**18〜22分**） ← 外の作りを写した本。**もう 5分 ではない**

    ＝ 手で書いた字のほうは正しいのに、**画面が言おうとしている「差」はもう無い**。
    数えれば、次に来た回が「どこまで写せたか」をその場で読めます。

    **覆る条件**: 控えに `duration_s` が無い本しか無ければ（2026-08-25 より前の本）
    `n` は 0 で、呼ぶ側はこの括弧ごと出しません（**推測の数を出さない**）。
    """
    from .forms import SHORT_MAX_SECONDS                       # noqa: PLC0415
    p = path or UPLOADED
    secs: list[tuple[str, float]] = []
    try:
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except Exception:                                  # noqa: BLE001
                continue
            d = r.get("duration_s")
            if d is None:
                continue
            try:
                d = float(d)
            except (TypeError, ValueError):
                continue
            if d > SHORT_MAX_SECONDS:
                secs.append((str(r.get("uploaded_at") or ""), d))
    except OSError:
        return {"n": 0, "median": None, "recent_median": None, "latest": None}
    if not secs:
        return {"n": 0, "median": None, "recent_median": None, "latest": None}
    vals = [d for _at, d in secs]
    tail = [d for _at, d in secs[-max(1, recent):]]
    return {"n": len(vals), "median": statistics.median(vals),
            "recent_median": statistics.median(tail), "latest": secs[-1][1]}


#: **試す形が取ってよい枠の数**（日）。規則は 1本/日 なので、枠は1日1つしかありません
#: （`src/house_rule.py`）。48h の門を判定するのに要る本は 1〜2本 なので、既定は 2。
EXPLORE_SLOT_CAP = 2


def explore_budget(ev_best: str | None, gap_best: str | None, *,
                   picks_path: Path | None = None,
                   views_path: Path | None = None) -> list[str]:
    """**試す形が、枠を何日ぶん取ったか**を数えて出す。0単位・`data/` だけ。

    ## なぜ要るか（2026-09-04 16:xx・最適化の回。**この回に撃った数**）

    `theory_gap()` が `best` を `argmax(外 p90 ÷ 自分の中央値)` で選んでいたので、
    **いちばん振るわない形が毎回 選ばれ**、`data/daily_pick.jsonl` は
    09-03T02:03 以降 **11回 連続で長尺**。規則は 1本/日 なので、
    **これは「新しく出る本の 100%」がその形だったということ**です。

    差（gap）は「試す理由」としては正しい。**正しくないのは、それが枠を全部 取ること**でした。
    48h で 100回 の門を判定するのに要るのは 1〜2本 で、11日ぶんは要りません。

    そのあいだの実測（`data/eta.jsonl`）: 再生/日(7d) 6,299（08-25）→ **943**（09-04）＝ **-85%**。

    **覆る条件**: `ev_best` と `gap_best` が同じ形なら、試す形が既定と同じなので
    **1行も出しません**（分ける意味がない）。また、この行は**枠を止めません** ——
    止めるのは決める回のほうです。ここは**取った枠の数を出すだけ**。
    数が要らなくなったら（＝ 前提が閉じたら）この関数ごと消すこと。
    """
    if not gap_best or not ev_best or gap_best == ev_best:
        return []
    rows = list(_jsonl(picks_path or PICKS))
    if not rows:
        return []
    # **決めは日ごとに上書きされます**（同じ `for_day` に何度も書く）。
    #     枠は日で数えること —— 決めの行数で数えると、焼き直した回数まで枠に見えます。
    by_day: dict[str, dict] = {}
    for r in rows:
        d = str(r.get("for_day") or "")
        if d:
            by_day[d] = r
    days = sorted(by_day)
    streak = []
    for d in reversed(days):
        if str(by_day[d].get("form") or "") != gap_best:
            break
        streak.append(d)
    if not streak:
        return []
    streak.reverse()
    # **その枠から、判定に届いた本が何本 出たか。** 齢 48h の観測を持つ本だけを数えます。
    ids = {str(by_day[d].get("video_id") or "") for d in streak} - {""}
    measured = set()
    for r in _jsonl(views_path or VIEWS):
        if str(r.get("id") or "") in ids:
            try:
                if float(r.get("hours") or 0) >= 48.0:
                    measured.add(str(r["id"]))
            except (TypeError, ValueError):
                continue
    over = len(streak) > EXPLORE_SLOT_CAP
    head = ("     [!!] " if over else "     ")
    out = [
        f"{head}**試す形（{gap_best}）が枠を {len(streak)}日ぶん 取っています**"
        f"（{streak[0]}〜{streak[-1]}・既定の形は {ev_best}）。"
        f" **規則は 1本/日 なので、これは新しく出る本の 100% です。**"
        f" そこから 48h の判定に届いた本: **{len(measured)}本／{len(ids)}本**。",
    ]
    if over:
        out.append(
            f"       → **枠の目安 {EXPLORE_SLOT_CAP}日 を越えています。**"
            f" 判定に要るのは 1〜2本 で、{len(streak)}日ぶんは要りません。"
            f" **次の枠は既定の形（{ev_best}）へ戻すか、戻さない理由を"
            f"「この形で測れていない数」で言うこと**（前の決めの散文は根拠になりません）。")
    if ids and not measured:
        out.append(
            "       [!] **取った枠から、まだ 1本も 48h の観測が出ていません** ——"
            " 枠だけ減って、前提は 1件も進んでいません。"
            " **焼き直しで本を差し替えると齢が 0 に戻ります**（`data/views.jsonl` の `hours`）。")
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
    # **差（gap）で選ばないこと** —— 分母が自分の実測なので、振るわない形ほど強く推されます
    #     （`theory_gap()` の註。2026-09-03 02:03 の上書きが、この比で起きました）。
    gap_best = g.get("gap_best")
    ev_best = g.get("ev_best")
    if gap_best and ev_best and gap_best != ev_best:
        out.append(
            f"     [!] **上の ×N は「差」であって「見込み」ではありません** —— 分母は**自分の実測**です。"
            f" 差がいちばん大きい形は **{gap_best}**（×{g[gap_best]['x_p90']:,.0f}）ですが、"
            f"**それはその形がいちばん振るっていないという意味**でもあります"
            f"（自分の中央値 {_fmt(g[gap_best]['own'] or 0)} 対 {_fmt(g[ev_best]['own'] or 0)}）。"
            f" **枠は 1日1つ（`src/house_rule.py`）。埋めるなら実測の見込みで埋めること。**")
    best = ev_best or gap_best
    if best:
        d = g[best]
        ln = (f"     → **1本の枠の見込み（実測の中央値・48h）がいちばん高い形は {best}**"
              f"（{_fmt(d['own'] or 0)}）")
        if need:
            reach = [f for f in forms if g[f]["x_p90"] >= need]
            ln += (f"。〔差の側〕日付が出るのに要る ×{need:.1f} を外の p90 で越える形: "
                   + ("・".join(reach) if reach else "**無し**")
                   + "（**越えるのは差であって、届いた実績ではありません**）")
        if best == "長尺" and d.get("secs_median"):
            # **自分の側も数えること**（`own_long_secs()` の註。手で書いた「5分」は、
            # 写した本が出た日にいちばん先に古くなります）。
            own_s = own_long_secs()
            mine = ""
            if own_s.get("median"):
                mine = (f"（自分の長尺は 中央 **{own_s['median'] / 60:.0f}分**・{own_s['n']}本 ／ "
                        f"直近{OWN_LONG_RECENT}本 **{own_s['recent_median'] / 60:.0f}分**）")
            ln += f"。外の上位の尺の中央 **{d['secs_median'] / 60:.0f}分**{mine}"
        out.append(ln)
        out.append("       ＝ **既定はこの形です。** 外の作りを写した1本を別の形で試すのは"
                   "「差」が理由として正しく、**枠が空いているときだけ**"
                   "（前提は `config/hypotheses.yaml` の「外の作り方を写した長尺」）。")
        out.extend(explore_budget(ev_best=ev_best, gap_best=gap_best))
    # **同じ画面に、齢で割った側も並べること**（`theory_gap` の註・2026-09-04）。
    #     上の ×N は 外の生涯の累計 ÷ 自分の 48時間 で、外の上位に 48時間 以内の本は 0本。
    #     **片方だけだと、窓の差が結論を作ります。**
    day = [f for f in forms if g[f].get("x_day")]
    if day:
        cols = " ／ ".join(
            f"{f} **×{g[f]['x_day']:,.2f}**（外の上位の中央 {g[f]['out_rate']:,.0f}回/日"
            f"・齢 中央 {g[f]['age_median']:,.0f}日・n={g[f]['n_dated']}"
            f" ÷ 自分 {g[f]['own_rate']:,.1f}回/日）" for f in day)
        out.append("     **上位15本を1日あたりで**（上の ×N は **外の生涯の累計 ÷ 自分の 48時間** ——"
                   " 外の上位に 48時間 以内の本は 0本 です。**上の累計の行と母集団が違います**"
                   "・すぐ下の帯の行と並べて読むこと）: " + cols)
        band = [f for f in forms if g[f].get("x_day_band")]
        if band:
            bcols = " ／ ".join(
                f"{f} **×{g[f]['x_day_band']:,.4f}**（帯の中央 {g[f]['band_rate']:,.1f}回/日"
                f"・齢 中央 {g[f]['band_age_median']:,.0f}日・n={g[f]['n_band']}"
                f" ÷ 自分 {g[f]['own_rate']:,.1f}回/日）" for f in band)
            out.append("     **同じ母集団（帯そのもの）を1日あたりで**"
                       "（上の累計の行と同じ n・`niche_ceiling.corpus_rows`・API 0単位）: " + bcols)
            gaps = "・".join(
                f"{f} 上位15本 {g[f]['out_rate']:,.1f}回/日 対 帯 {g[f]['band_rate']:,.1f}回/日"
                f"（**×{g[f]['out_rate'] / g[f]['band_rate']:,.1f}**）"
                for f in band if g[f].get("out_rate"))
            if gaps:
                out.append("       [!] **上の2行は同じ数ではありません** —— " + gaps
                           + "。**上位は「その題の天井」、帯は「その帯の普通の本」。"
                             "どちらか片方を『外の帯』と呼ばないこと。**")
        near = min(day, key=lambda f: g[f]["x_day"])
        out.append(f"       → 1日あたりで見て、いちばん近い形は **{near}**"
                   f"（×{g[near]['x_day']:,.2f}）。**上の行と食い違ったら、"
                   "どちらか片方を根拠にしないこと** —— 累計は「その題でどこまで積めるか」、"
                   "1日あたりは「いま追い付けるか」。**撃つ窓も形ごとに違います**"
                   "（`niche_ceiling.SP_FILTERS`: ショート＝全期間・長尺＝今年）")
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


def and_path_form(cmp: dict | None = None, *, snapshot: dict | None = None,
                  topics: list[dict] | None = None, uploaded_path: Path | None = None,
                  cv: dict[str, list] | None = None,
                  now: datetime | None = None) -> tuple[str | None, str]:
    """**AND の道（門1 ＋（門2a ／ 門2b））で門に近い形**と、その根拠の1行。**API 0単位。**

    ## なぜ要るか（2026-09-04・最適化の回。**「最適化されてんの？」→ いいえ の理由を1つ潰した**）

    `outside_long_readout()` の 24h の先読みの門は、**門を割っても割らなくても
    「次の未決の日の1本は長尺」と印字していました**（`v >= OUTSIDE_24H_GATE` の枝と
    `else` の枝が、どちらも長尺）。**＝ 門が、それが門をしている決定を1度も変えられない。**
    毎周 数字が出て、毎周 同じ手が選ばれるので、回は「測って決めた」と読みます。
    実測: `data/daily_pick.jsonl` の決めは 09-04・09-05 とも長尺、`data/eta.jsonl` の
    再生/日(7d) は 6,299（08-25）→ 1,344（09-03）で **-79%**。

    そして**割ったときの言い分**（「ショートは 4,000時間 の門に 0時間」）は、
    **同じファイルの `gate_arithmetic()` が 40行 先で名指ししている誤りそのもの**です ——
    門2 だけで比べるのは **AND の片脚（門1）を落として比べること**で、
    落とした脚のほうが遠い（門1・長尺 ×314 対 門2a ×34）。
    `gate_arithmetic()["nearer"]` は 2026-09-03 夜にそこを直してあり、
    `fallback_form()` は既にこちらを読んでいます。**読んでいなかったのは
    `outside_long_*` の散文のほうだけ**でした —— そして回が従うのは散文です。

    ここはその `nearer` を、先読みの門を割った枝からも引けるようにするだけです。
    **形を決め打ちしません** —— 長尺の登録率の分母が桁で増えれば `nearer` は
    自分で長尺へ戻り、この行も一緒に戻ります。

    **覆る条件**: `gate_arithmetic()` が `path_x`（両形の脚）を出せない回
    （`data/shorts_subs.json` が読めない等）は `(None, 理由)` を返します。
    **推測で埋めないこと** —— 埋めると、必ず要る脚が推測になります。
    """
    try:
        c = compare(now=now) if cmp is None else cmp
        g = gate_arithmetic(c, snapshot=snapshot,
                            duration_min=_long_duration_min(None, uploaded_path, topics),
                            frac=long_watch_fraction(c.get("rows") or [], cv))
    except Exception as exc:                                       # noqa: BLE001
        return None, f"門の算がこの回は出せませんでした（{exc}）"
    px = g.get("path_x") or {}
    if not px or g.get("nearer") not in FORMS:
        return None, "門1 の脚が立たないので、道どうしは比べられません（`data/shorts_subs.json`）"
    body = "・".join(f"道 {k} ＝ ×{v:,.0f}" for k, v in sorted(px.items(), key=lambda kv: kv[1]))
    return str(g["nearer"]), f"AND の道でいちばん遠い脚どうし: {body}"


#: **立っている決めが名指している「その本」が、前提の脚を全部 通っているか。**
#: （2026-09-04 17:xx・最適化の回に足した。`treated_count` は**分母**を数える口で、
#:  **枠に入る1本そのもの**は、どこも数えていませんでした。）
OUTSIDE_LEGS: tuple[tuple[str, str], ...] = (
    ("(1) 冒頭", "outside_opening_problems"),
    ("(2) 章・締め", "outside_body_problems"),
    ("(4) 題・サムネ", "outside_title_problems"),
    ("(5) 間合い", "outside_pacing_problems"),
)


#: **焼き直さなくても直せる脚。**（2026-09-04 21:xx・最適化の回に実測で足した）
#:
#: ## なぜ要るか —— **輪が回り続けた理由は、ここ1つでした**
#:
#: 09-04 の ship は **65件**（`data/runs.jsonl`）。うち `fix` が **41件**、
#: `--moves` が 0 以外 は **0件**。同じ日の決めは **14回、全部 長尺**、
#: 焼き直しで動画IDが **4つ** 捨てられました
#: （`Ec-j1-W4nqw` → `O_lfBxB7S8Q` → `XwB8nxtN5D8` → `e6sLHLmPhrk`）。
#:
#: **4本とも、落ちた脚は `(4) 題・サムネ` の同じ2件です**（実測・API 0単位）::
#:
#:     題   【年金の受け取り方】…   ← 【 】が題材（相手でも場面でもない）
#:     kicker「75歳まで生きた場合・年180万円」全角17文字（門は11文字）
#:
#: 同じ時刻の**手元の台本**は `draft_legs()` = **[]**（4脚とも ○。題は
#: 【60歳以上の方へ】に直っている）。**直っているのに、門は言い続けます。**
#:
#: ## 算がそう言っています（意見ではありません）
#:
#:     焼き 1回     **55〜90分**（`ahead_sweep` の `REBAKE_LEAD` の註）
#:     直しが降る間隔  09-04 の commit で **21分 / 26分 / 30分 / 91分**
#:
#: **直しのほうが焼きより速いので、焼き上がった控えは必ず古い。**
#: `untreated_slot_block()` は控え（`pick_legs`）を見て「置くな・焼き直せ」と言い、
#: `ahead_sweep` はそれを `rebake_pending` に倒す。焼くあいだにまた直しが降る。
#: **`pick_legs` は `draft_legs` に永久に追いつけません。** ＝ 自分で自分を養う輪で、
#: 出口は「枠の直前に、直っていない本が落ちる」しかありませんでした
#: （09-04 の `1huadpEk6HY` が実物: 脚3本 ✗ のまま公開・齢12時間で **2回**）。
#:
#: ## 出口 —— **題とサムネは、焼き直しでしか直せないものではありません**
#:
#: `(4) 題・サムネ` が見るのは `title` と `thumbnail_kicker` / `thumbnail_line*` ——
#: **どれも動画の中身ではなく metadata** です。手は既に在りました::
#:
#:     python scripts/retitle.py <動画ID> "<題>"          50単位・数秒
#:     python scripts/refresh_thumbnail.py --rebuild <動画ID>   **API 0単位**
#:     python scripts/refresh_thumbnail.py --missing --video <動画ID>  50単位
#:
#: **20分の動画を4回 焼き直して直そうとしていたのは、題の文字列 1本 です。**
#: だからここで脚を2つに割り、metadata だけが落ちているときは
#: `untreated_slot_block()` は**焼き直しを命じません**（`ahead_sweep` の
#: `rebake_pending` に倒れない）。命じるのは「その場で直せ」のほうです。
#:
#: ## 覆る条件
#:
#: - `outside_title_problems` が `segments`（＝焼かないと変わらない所）も見るように
#:   なったら、`(4)` はここから外すこと。**いまは `title` と `thumbnail_*` だけです。**
#: - 前提「外の作り方を写した長尺」が閉じて `OUTSIDE_LONG_RULE` を使わなくなったら、
#:   `OUTSIDE_LEGS` ごと落とすこと（`config/hypotheses.yaml`）。
METADATA_LEGS: frozenset[str] = frozenset({"(4) 題・サムネ"})


def metadata_only(bad: list[str]) -> bool:
    """落ちた脚が **metadata だけ**か（＝焼き直さずに直せるか）。API 0単位。

    空（＝1本も落ちていない）は `False` —— 直すものが無いので「その場で直せ」でもない。
    """
    return bool(bad) and all(b in METADATA_LEGS for b in bad)


#: **metadata が落ちているときに撃つ手**（`untreated_slot_block()` が刷る）。
METADATA_FIX_HOWTO = (
    "焼き直しは要りません（題とサムネは metadata）: "
    "`python scripts/retitle.py <ID> \"<手元の台本の title>\"` と "
    "`python scripts/refresh_thumbnail.py --rebuild <ID>` "
    "→ 窓が戻ったら `--missing --video <ID>`。"
    "**そのあと `data/critique_queue/<ID>.script.json` の `title` / `thumbnail_*` を"
    "手元の台本に合わせること** —— 控えを直さないと門は言い続けます"
)


def pick_legs(video_id: str | None, *, queue: Path | None = None) -> tuple[list[str], str | None]:
    """`(通らなかった脚, 読めなかった理由)`。**API 0単位・実物の台本の控えだけ。**

    `data/critique_queue/<video_id>.script.json` を `src/script_writer` の
    4つの数える口に通します。控えが読めなければ `([], 理由)` ——
    **読めないものを「通った」に数えません**（`treated_count` と同じ向き）。
    """
    vid = str(video_id or "").strip()
    if not vid:
        return [], "決めが本を名指していません（`video_id` が空）"
    return legs_of_path((queue or QUEUE) / f"{vid}.script.json", what="台本の控え")


def treated_probe(video_id: str | None, *, queue: Path | None = None) -> tuple[str, str]:
    """**その本が「処置」か**。`("yes"|"no"|"unknown", 一行の理由)`。**API 0単位・実物の台本の控えだけ。**

    ## なぜ要るか（2026-09-04 22:2x に踏んだ）

    **「外の作りの長尺」には、口が2つ ありました。**

        `config/topics` の `style: outside_long`   ＝ **これから外の型で作るつもり**（意図の札）
        `pick_legs(vid) == ([], None)`            ＝ **実物の台本が4脚 全部 通った**（処置の実体）

    `treated_count()` は下（実物）で数えます。ところが `probe_hold()` と
    `outside_long_readout()` は **上（意図の札）だけ**で「試す本」を選んでいました。
    実測（2026-09-04 22:2x に撃った）:

        pick_legs('1huadpEk6HY') = ['(2) 章・締め', '(4) 題・サムネ', '(5) 間合い']   ← 4脚中 3脚 ✗
        draft_legs('zaishoku-2026-62man') = 同じ3脚 ✗   ← 手元の台本も外の型に上げていない
        treated_count('長尺') = (0, 36)                  ← 実物で数えると、処置は **1本も公開されていない**

    つまり `1huadpEk6HY` は **札だけの本**です。それが「試す本」として:

        - `outside_long_readout()` の 24h の先読みの門（30回）を握り、**次の日の形**を決め、
        - `probe_hold()` として、**次の未決の日**の決めを止めていました。

    **どちらも、前提を閉じられない本の数字を待っています。**
    前提「外の作り方を写した長尺」の `falsified_if` は「**その本**（題が上の型の本）」の
    齢48h で読む、と書いてあります —— 札ではなく型です。
    処置でない本をいくら待っても、その前提は 1件も進みません
    （同じ画面が「取った枠から、まだ 1本も 48h の観測が出ていません（0本／2本）」と刷っていたのは、
    枠が足りなかったからではなく、**出した2本が処置ではなかったから**です）。

    **これは marker が毎周 刷っている註と同じ向きです** ——
    「**処置 n=0 の分母で処置を落とさないこと**」。分母だけでなく、
    **門の分子（試す本）も、実物で選ぶこと。**

    ## 読めないときは `"unknown"`。**止めを外すのは `"no"` のときだけ**

    控えが読めない本は `"unknown"` で返ります。**呼ぶ側は `"unknown"` で止めを外さないこと** ——
    `probe_hold` は安全側の閂で、**外すには「この本は処置ではない」という実物の証拠が要ります**。
    「読めなかった」は証拠ではありません（`probe_hold` の docstring の
    **「推測で止めないこと」** の裏返しで、**推測で外さないこと**）。
    `1huadpEk6HY` は控えが読めた上で 3脚 ✗ ＝ `"no"` です。

    ## 覆る条件

    - `config` の札と実物の脚が**必ず一致する**ようになったら（作る側が札の本を
      4脚 通さないと出せなくなったら）、この関数は要りません。
      そのときは `probe_hold` / `outside_long_readout` を札だけに戻して、ここを消すこと。
    """
    bad, why = pick_legs(video_id, queue=queue)
    if why:
        return "unknown", why
    if bad:
        return "no", f"外の型の脚が {len(bad)}本 通っていません（{'・'.join(bad)}）"
    return "yes", "外の型の脚は 4本とも通っています"


def legs_of_path(path: Path, *, what: str = "台本") -> tuple[list[str], str | None]:
    """`(通らなかった脚, 読めなかった理由)`。**API 0単位・渡された台本だけ。**

    `pick_legs`（控え＝**実物に入っている台本**）と `draft_legs`（手元の台本＝
    **これから入る台本**）が、**同じ4つの口**を通るようにここに集めてあります。
    片方だけ別の数え方になると、「直したのに門が言い続ける」の見分けが付きません。
    """
    try:
        script = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:                           # noqa: BLE001
        return [], f"{what}が読めません（`{path}`・{str(exc)[:60]}）"
    try:
        from src import script_writer as _sw
    except Exception as exc:                                       # noqa: BLE001
        return [], f"`src.script_writer` が読めません（{str(exc)[:60]}）"
    bad: list[str] = []
    for label, fn in OUTSIDE_LEGS:
        f = getattr(_sw, fn, None)
        if f is None:
            continue
        try:
            if f(script):
                bad.append(label)
        except Exception:                                          # noqa: BLE001
            continue
    return bad, None


def draft_legs(topic: str | None) -> tuple[list[str], str | None]:
    """**手元の台本**（`data/scripts/<題材>.script.json`）で測った脚。

    控え（`pick_legs`）は「**いま実物に入っている台本**」で、こちらは
    「**次の焼きで入る台本**」です。**2つは焼きの 55〜90分 ぶんずれます。**
    """
    t = str(topic or "").strip()
    if not t:
        return [], "決めが題材を名指していません"
    return legs_of_path(ROOT / "data" / "scripts" / f"{t}.script.json", what="手元の台本")


def standing_pick_treatment(cur: dict | None, *, topics: list[dict] | None = None,
                            queue: Path | None = None) -> list[str]:
    """**立っている決めの本を、いまの脚で測り直した行。**（API 0単位）

    ## なぜ要るか（2026-09-04 17:xx・最適化の回に実物で踏んだ）

    規則1 は 1日1本（`src/house_rule.py`）。**その日に枠へ入る1本は、その日の供給の 100%** です。
    その1本を決めた `why` は**散文**で、こう名乗っていました（09-04T16:21 の決め）::

        O_lfBxB7S8Q は 5脚とも ○ の唯一の本

    **同じ回に、機械で測ると偽です** —— `outside_opening_problems` が (1) 冒頭 を落とします
    （脚 (1)b「知らない側がどうなるか」は 09-04 15:0x に足したので、
      その名乗りは**足す前の写し**でした）。同じ日に枠を取った `1huadpEk6HY` は
    (2)(4)(5) を落としたまま公開ずみで、齢6時間で **0回**。

    ＝ **前提「外の作り方を写した長尺」（期限 2026-09-07）のために枠を 2日ぶん 取りながら、
    その枠へ入れた本は 1本も処置になっていません。** 枠だけ減って、前提は 1件も進みません
    （`lines()` の「取った枠から、まだ 1本も 48h の観測が出ていません」と同じ穴の、**上流**）。

    `treated_count()` は**分母**（既に出た本）を数えます。ここは**これから出る1本**を数えます。
    **どちらも無いと、処置 0本 の試験が「試験ずみ」として枠を食い続けます。**

    ## 覆る条件

    - 前提「外の作り方を写した長尺」が閉じて `OUTSIDE_LONG_RULE` を使わなくなったら、
      この行ごと落とすこと（`config/hypotheses.yaml`）。
    - 決めの形が `outside_long` の型を持たない題材になったら、ここは黙ります
      （**型の無い題材に「写していない」と言わないこと**）。
    """
    if not cur:
        return []
    topic = str(cur.get("topic") or "")
    tops = {str(t.get("id")): str(t.get("style") or "")
            for t in (topics if topics is not None else _topics())}
    if tops.get(topic) != "outside_long":
        return []
    vid = cur.get("video_id")
    bad, why = pick_legs(vid, queue=queue)
    claim = "脚" in str(cur.get("why") or "") or "○" in str(cur.get("why") or "")
    if why:
        return [f"     [!] **決めの本 `{vid or '(無し)'}` の脚が、この回は測れませんでした** —— {why}。"
                f"**測れないものを「処置ずみ」に数えないこと。**"]
    if not bad:
        return [f"     [数] 決めの本 `{vid}` は **外の型の脚を全部 通っています**"
                f"（`src/daily_pick.pick_legs`・{len(OUTSIDE_LEGS)}脚・実物の台本の控え）。"]
    head = ("     [!!] **立っている決めの本が、前提の脚を通っていません** —— "
            f"`{vid}` は {len(bad)}/{len(OUTSIDE_LEGS)}脚 が ✗: **{'・'.join(bad)}**"
            "（`src/daily_pick.pick_legs`・実物の台本の控え・API 0単位）。")
    out = [head]
    if claim:
        out.append("     　 **決めの `why` は「脚は通っている」と名乗っています。"
                   "散文のほうが古い写しです** —— 脚は足されており"
                   "（(1)b 09-04 15:0x・(4) 12:5x・(5) 13:4x）、**名乗りは機械で毎周 測り直すこと。**")
    out.append("     　 規則1 は 1日1本（`src/house_rule.py`）＝ **この1本は、その日の供給の 100%** です。"
               "処置になっていない本をその枠へ入れると、**枠は減り、前提は 1件も進みません**"
               "（前提「外の作り方を写した長尺」・`config/hypotheses.yaml`）。"
               "実測: 同じ試験で先に出した `1huadpEk6HY` は (2)(4)(5) ✗ のまま公開され、齢6時間で 0回。")
    out.append("     　 **この回の `improve` は、この脚を通すことです**"
               "（オーナー規則3「次の枠までの時間は、その枠で出す1本を改善し続ける」）:")
    out.append(f"       python scripts/inspect_build.py {topic}"
               f"   # 脚を落としている段を見る（`src/script_writer.OUTSIDE_LONG_RULE`）")
    out.append(f"       python scripts/upload_only.py {topic} --draft --replaces {vid}"
               f"   # 直したら焼き直して差し替える（旧 ID は private のまま残す）")
    return out


def path_form_hold(form: str, *, now: datetime | None = None,
                   uploaded_path: Path | None = None, form_call=None) -> str:
    """**門の算（AND の道）が言う形と違う形で「その日の1本」を決めるのを、実際に止める。**
    止めるなら理由の1行、止めないなら `""`。**API 0単位。**

    ## なぜ要るか（2026-09-05 02:xx・最適化の回。「最適化されてんの？」→ **いいえ** の理由を1つ潰す）

    この回が自分で撃った数:

        and_path_form()              → **ショート**（道 ショート ×106・道 長尺 ×334）
        data/daily_pick.jsonl の決め → 39件中 **31件が長尺**
        その決めが自分で書いた見込み → 長尺 expected_48h の中央値 **8回**／ショート **368回**
        齢48h の実測（data/views.jsonl）→ 長尺 中央値 **1回**（n=36）／ショート **168回**（n=216）
        data/eta.jsonl 再生/日(7d)   → 6,299（08-25）→ **943**（09-04）＝ **-85%**

    ＝ **門の算も、自分で書いた見込みも、実測の中央値も、3つとも同じ形（ショート）を
    指しているのに、決めは長尺で立ち続けています。**

    理由は 1つです。`standing_form_conflict()`（2026-09-04 に足された）は
    **食い違いを印字するだけ**で、`record()` は CLI が渡した `form` を
    そのまま控えに書きます。**印字は止めではありません。** 実測 —— その行が
    印字されるようになった後の決め（09-05T00:38・01:17・01:48）は、**理由の中で
    「道の最遠脚 ショート x106 / 長尺 x334」と自分で引用したうえで、長尺に据え置いて**います。

    直前の最適化の回が足したものを並べると、`outside_long_readout`（散文）→
    `and_path_form`（算・印字）→ `standing_form_conflict`（食い違いの印字）——
    **3回とも「読み上げ」で、1度も `raise` していません。** ここが初めて止めます。

    ## 通す口

    数字で上書きするのは自由です（オーナーの「固定は目標の本文だけ」）——
    `record(..., anyway="<数字を含む理由>")` ／ CLI は `--anyway "<理由>"`。
    **止めは据え置きのたびに立ち直します** —— 31回 据え置くなら 31行 の `anyway` が
    控えに残り、`scripts/optimized.py` がそれを実物と並べます。
    （**1度 越えたら以後 黙る、にはしません。** 黙ると鎖はまた無料になります。）

    ## 覆る条件

    - `and_path_form()` が `None`（門1 の脚 `data/shorts_subs.json` が立たない）を返す回は
      **止めません**。比べる相手が無いので、**推測で止めないこと。**
    - 長尺の脚が近づけば `and_path_form()` は自分で長尺を返し、この止めは長尺を通して
      ショートのほうを止めます。**形を決め打ちしていません。**
    - `kind` が `decide` でない行（`carry` ＝ 焼き直しの写し）は決めではないので通します。
    """
    if str(form) not in FORMS:
        return ""
    call = and_path_form if form_call is None else form_call
    try:
        want, why = call(now=now, uploaded_path=uploaded_path)
    except Exception:                                              # noqa: BLE001
        return ""
    if not want or str(want) == str(form):
        return ""
    return (f"門の算（AND の道）は **{want}** を指しています —— {why}。"
            f" いま決めようとしている形は **{form}** です。"
            f" 齢{AGE_HOURS}h の実測の中央値: {_median_pair_line(str(form), str(want))}。"
            f" **印字ではなくここで止めています**（`standing_form_conflict` は"
            f"食い違いを刷るだけで、控えには渡した形がそのまま入っていました）。"
            f" 形を {want} にするか、`--anyway \"<数字を含む1行>\"` で越えること"
            f"（越えた行は `anyway` として控えに残り、次の回が実物と並べます）。")


def _median_pair_line(a: str, b: str, *, median_call=None) -> str:
    """**2つの形の、齢48h の中央値を並べた1行**（`form_median_48h` の実物・API 0単位）。

    `standing_form_conflict()` が「処置は両方 0本」と言う枝で使います。**そこでは
    処置の有無が形を選ばないので、残る測った量はこれだけ**になります。読めない側は
    「測れず」と書き、**推測で埋めません**（埋めると、比べている当の量が推測になる）。
    """
    call = form_median_48h if median_call is None else median_call
    out = []
    for f in (a, b):
        try:
            v = call(f)
        except Exception:                                          # noqa: BLE001
            v = None
        out.append(f"{f} {v:,.0f}回" if isinstance(v, (int, float)) else f"{f} 測れず")
    return "・".join(out)


def win_pays_for_slot(give_up: str, *, gate: float = OUTSIDE_48H_GATE,
                      median_call=None) -> list[str]:
    """**その実験は、当たっても枠の代金を払えるか。**（API 0単位）

    ## なぜ要るか（2026-09-04 23:5x・最適化の回。**2つ目の「いいえ」の理由**）

    枠は 1日 1本（規則1）なので、**試す本を1本 出すことは、別の形を1本 出さないこと**です。
    ところがこの repo は、前提の**当たりの門**を「自分の記録の何倍か」だけで置いてきました
    —— `OUTSIDE_48H_GATE` は「いまの長尺の中央値 1回 の ×100」＝ **100回**。
    **譲る側の実測と並べた回が、1度もありません。**

    この回に撃った数: `form_median_48h('ショート')` ＝ **164回**。
    ＝ **この前提は、当たっても（>100回）、譲ったショートの中央値（164回）に届きません。**
    「作り方を写せば桁が動く」の最小の門としては正しくても、
    **枠の値段としては、勝っても負けです。**

    これは前提を落とす理由ではありません（門は緩めも締めもしない）。
    **枠をどちらに使うかの理由**です —— 同じ実験は、**枠を食わない形**
    （既に公開ずみの本で測る・門を譲る側の中央値の上に置き直す）でも立てられます。

    **覆る条件**: 譲る側の中央値が門を下回ったら、この行は自分で消えます
    （＝ 当たれば枠の代金を払える）。読めない回は**1行も出しません**（推測で埋めない）。

    ## **同じ画面に、同じ言葉の別の数が並んでいました**（2026-09-05 03:0x に踏んだ）

    この行は「譲る ショート の齢48h の中央値 **164回**」と書きます。**そのすぐ下**で
    `slot_cost.win_band()` が、同じ「譲る ショート の実測」を **1,049回** として
    `paid` の境目に使っています。**6.4倍 ちがう2つの数が、同じ言葉で隣り合っていました。**
    読んだ回がどちらを拾うかで、門 100回 の比が **1/1.6** にも **1/10** にもなります。

    **どちらも本物で、母集団が違うだけです** —— こちらは `form_median_48h`（**全部の日**・
    n=216）、あちらは `slot_cost.slot_value()`（**規則の密度 ≤2本/日 の日だけ**・n=15）。
    `src/slot_cost.py` の冒頭は既に「**枠の機会費用は 164回 ではなく 1,049回**」と
    決めており、**この行だけが、決まる前の数を決まった言葉で出していました。**

    **結論は変わりません**（門 100回 は両方に負けます）。だから門も文面の向きも
    動かさず、**どちらの数で読んでも同じだと分かるように、2つとも名前つきで並べます。**
    片方が読めない回は、読めたほうだけを出します（推測で埋めない）。
    """
    call = form_median_48h if median_call is None else median_call
    try:
        alt = call(give_up)
    except Exception:                                              # noqa: BLE001
        return []
    # **`nan` は `<=` も `>` も False を返すので、大小だけの門を素通りします**
    # （2026-09-04 23:5x に検査が拾った）。**有限であることを先に見ること。**
    if not isinstance(alt, (int, float)) or isinstance(alt, bool):
        return []
    if not math.isfinite(alt) or alt <= 0:
        return []
    if gate is None or not math.isfinite(gate) or gate > alt:
        return []
    return [
        f"     　 [数] **その前提は、当たっても枠の代金を払えません。**"
        f" 当たりの門 **{gate:,.0f}回**（`src/daily_pick.OUTSIDE_48H_GATE`）＜"
        f" 譲る {give_up} の齢{AGE_HOURS}h の中央値 **{alt:,.0f}回**"
        f"（`form_median_48h`・**全部の日**）—— **枠は 1日 1本 なので、試す本を出すことは"
        f" {give_up} を1本 出さないこと**です。**当たりの門を、譲る側の実測の上に置き直すか、"
        f"枠を食わない形（公開ずみの本で測る）にすること。**" + _slot_cost_same_words(give_up),
    ]


def _slot_cost_same_words(give_up: str) -> str:
    """**すぐ下の `win_band` が同じ言葉で使っている数を、同じ行に並べる。**（API 0単位）

    片方しか読めない回は**空文字**を返します（推測で埋めない）。数は1つも書き換えません
    —— 出すのは母集団の名と、`slot_cost` 側の齢だけです（`slot_cost.slot_value()`）。
    """
    try:
        from . import slot_cost as _sc                             # noqa: PLC0415
        s = _sc.slot_value()
        v = (s.get("forms", {}).get(give_up) or {})
        rule_med, rule_n = v.get("median"), v.get("n", 0)
        age = v.get("sample_age_days")
    except Exception:                                              # noqa: BLE001
        return ""
    if not isinstance(rule_med, (int, float)) or isinstance(rule_med, bool):
        return ""
    if not math.isfinite(rule_med) or rule_med <= 0:
        return ""
    out = (f"　[数] **同じ「譲る {give_up} の実測」を、すぐ下の `slot_cost.win_band()` は"
           f" {rule_med:,.0f}回 として `paid` の境目に使っています** ——"
           f" 母集団が違うだけです（この行は**全部の日**・あちらは"
           f"**規則の密度 ≤{RULE_BAND_MULT}本/日 の日だけ**・n={rule_n}）。"
           f"**門 {OUTSIDE_48H_GATE:,.0f}回 はどちらにも負けるので、結論はどちらで読んでも同じです。**")
    if isinstance(age, int) and age > getattr(_sc, "STALE_DAYS", 7):
        out += f"（ただしあちらの標本は **{age}日前**で止まっています・`slot_cost.stale_lines`）"
    return out


def standing_form_conflict(cur: dict | None, *, now: datetime | None = None,
                           uploaded_path: Path | None = None,
                           form_call=None, picks_path: Path | None = None,
                           treated_call=None) -> list[str]:
    """**すでに立っている決めの形と、いま測った門の算の形が食い違うなら、そう言う行。**（API 0単位）

    ## なぜ要るか（2026-09-04・最適化の回。**「最適化されてんの？」→ いいえ の理由を1つ潰した**）

    `and_path_form()`（門の算・AND の道）は 2026-09-04 に足され、いま撃つと
    **ショート**（道 ショート ×106 対 道 長尺 ×314）を返します。ところが呼ばれる場所は
    `outside_long_readout()` が `"stop"` を返す枝の2か所だけで、その判定は
    **外の作りの長尺が 24h の観測を持っていること**が要ります。実測（この回に撃った）:
    6本（`6PKux5HNnUE` `1huadpEk6HY` `dRZnZrRy2Lw` `DfFyu8qZq3I` `Ec-j1-W4nqw` `O_lfBxB7S8Q`）
    の**どれも `data/views.jsonl` に観測が 0件**で、`outside_long_readout()` の判定は `None`。
    ＝ **門の算は、一度も印字されていません。**

    そのあいだ毎周 印字されていたのは、立っている決めの `why` ——
    つまり**前の回の散文**だけでした（`lines()` の「理由: …」）。実測:
    `data/daily_pick.jsonl` の 09-03T02:03 以降 **11回 連続で長尺**、`why` は
    「02:29 の決め…はそのまま」「04:38 の決めを…そのまま置く」「07:42 の決めを数字で追認」——
    **前の決めを引いて再確認する鎖**です。その鎖の根は 09-03T02:03 の
    「外の p90 624,772回 ÷ 自分の長尺の中央値 1回」で、これは
    **自分がその形で 0 に近いほど大きくなる比**＝ **いちばん下手な形を必ず選ぶ量**です。
    （09-03T00:31 の決めは、自分の実測でショートでした ——「48h 中央値 173回 対 1回」。
    それが 90分後に上の比で上書きされ、以後 戻っていません。）
    そのあいだの `data/eta.jsonl`: 再生/日(7d) 6,299（08-25）→ **943**（09-04）＝ **-85%**。

    ここは**形を決め打ちしません。** 立っている形と `and_path_form()` の形が
    **同じなら 1行も出しません**。違うときだけ、両方の数を並べて名指します。
    長尺の脚が近づけば `and_path_form()` は自分で長尺を返し、この行は自分で消えます。

    **覆る条件**: `and_path_form()` が `None`（門1 の脚が立たない）を返す回は、
    比べる相手が無いので 1行も出しません。**推測で埋めないこと。**
    """
    if not cur:
        return []
    have = str(cur.get("form") or "")
    if have not in FORMS:
        return []
    call = and_path_form if form_call is None else form_call
    try:
        want, why = call(now=now, uploaded_path=uploaded_path)
    except Exception as exc:                                       # noqa: BLE001
        return [f"     （門の算がこの回は出せませんでした: {str(exc)[:80]}）"]
    if not want or want == have:
        return []
    topic = str(cur.get("topic") or "<題材>")
    chain = _standing_chain_len(picks_path)
    # **どちらが正しいかは言えませんが、「門の算の分母が処置を測っているか」は数えられます。**
    counter = treated_count if treated_call is None else treated_call
    try:
        treated, total = counter(have, uploaded_path=uploaded_path)
    except Exception:                                              # noqa: BLE001
        treated, total = 0, 0
    # **相手側の分母も、同じ口で数えること**（2026-09-04 23:5x・最適化の回）。
    # ここが片側だけだったので、「処置 n=0 だから落とせない」が
    # **両形とも 0本 のときにも、立っている形の側にだけ**印字されていました。
    try:
        w_treated, w_total = counter(want, uploaded_path=uploaded_path)
    except Exception:                                              # noqa: BLE001
        w_treated, w_total = 0, 0
    if total and treated == 0 and w_total and w_treated == 0:
        base = (f"     　 [数] **「処置 n=0 の分母で処置は落とせない」は、この回は使えません"
                f" —— 両方の形が処置 0本 です。**"
                f" {have} ＝ 0本／{total}本・{want} ＝ 0本／{w_total}本"
                f"（`src/daily_pick.treated_count`・実物の台本の控え）。"
                f" **同じ事実が両側に立つので、この事実はどちらの形も選びません。**"
                f" 処置ずみが 0本 どうしなら、いま2つの形を分けている測った量は"
                f" **齢{AGE_HOURS}h の中央値だけ**です: {_median_pair_line(have, want)}。"
                f" **片側にだけ「処置 n=0」を当てて門の算を外さないこと。**")
    elif total and treated == 0:
        base = (f"     　 [数] **その門の算は、立っている決めの形（{have}）の分母 {total}本 で解いています。"
                f"そのうち、外の型を全部 写した本は 0本**（`src/daily_pick.treated_count`・実物の台本の控え）"
                f" —— **その脚が測っているのは「いまの作り方」で、処置ではありません。**"
                f" 一方 {want} の分母は {w_total}本 中 **{w_treated}本 が処置ずみ** ＝"
                f" **こちら側は処置を測っています**（`config/hypotheses.yaml`）。"
                f"**処置 n=0 の分母で処置を落とさないこと。**")
    elif total:
        base = (f"     　 [数] {have} の分母 {total}本 のうち、外の型を全部 写した本は **{treated}本**"
                f"（`src/daily_pick.treated_count`）—— **分母は処置を測っています。"
                f"門の算のほうを根拠にしてよい回です。**")
    else:
        base = (f"     　 [数] {have} の分母が数えられませんでした（0本）—— **推測で埋めないこと。**")
    return [
        f"     [!!] **立っている決め（{have}）と、いま測った門の算（{want}）が食い違います。**"
        f"　{why}",
        base,
        (f"     　 **この決めは、この回が書いたものです**"
         f"（`data/runs.jsonl` の最後の `start` より後）—— **もう一度 決め直さないこと。**"
         f" 鎖はいま {chain}回 連続で同じ形ですが、**その最後の1本は、この回が数で置いた行**です。"
         if decided_this_round(cur) else
         f"     　 立っている決めの「理由」は**前の回の散文**です —— **根拠にしないこと**"
         f"（`data/daily_pick.jsonl` の `why` は前の決めを引く鎖で、いま {chain}回 連続で同じ形）。"
         f"**この回の数で決め直すか、門の算がなぜ外れているかを数で言うこと。**"),
    ] + win_pays_for_slot(want) + ([] if decided_this_round(cur) else [
        "     　 決め直すなら（同じコマンドで上書き）:",
        f"       python -m src.daily_pick --pick {want} {topic} --why \"<いま撃った数で>\"",
    ])


#: **その形の齢48h の分母のうち、外の型を「全部」写した本が何本か**（2026-09-04 16:4x に足した）。
#: 見るのは `data/critique_queue/<video_id>.script.json`（その本を焼いた台本の控え）と、
#: `src/script_writer` の4つの数える口（冒頭・章・題とサムネ・間合い）。**API 0単位・実物だけ。**
def treated_count(form: str, *, hours: int = AGE_HOURS,
                  views_path: Path | None = None,
                  uploaded_path: Path | None = None,
                  topics: list[dict] | None = None) -> tuple[int, int]:
    """`(外の型を全部 写した本, その形の分母)` を返す。

    ## なぜ要るか（2026-09-04 16:4x に踏んだ）

    `[!!]`（立っている決めと門の算が食い違う）は、**どちらが正しいかを言いません。**
    実際に 09/04 16:2x の回は、この行を読んでから **20分** かけて
    `config/hypotheses.yaml` の5脚の表まで降りて、答えを出しました ——
    **門の算の負けている側（長尺）の分母 36本 に、外の型を全部 写した本が 0本**。
    ＝ その脚は「いまの作り方」を測っていて、**処置を1本も測っていません。**

    **その 0本 は、機械が数えられます。** 降りなくても済むように、ここで数えて
    `[!!]` の隣に出します（`data/daily_pick.jsonl` の `why` は 12回 続けて
    同じ形を引く鎖になっており、**降りた回だけが鎖を切れる**形でした）。

    **控えの読めない本を「写した」に数えません** —— 確かめられないものは外します
    （`house_rule.needs_beyond_rule()` の「読めないものは通す」とは**逆向き**です。
     こちらは「処置ずみ」を名乗る側なので、**証拠が要る**）。

    **覆る条件**: 前提「外の作り方を写した長尺」が閉じて `OUTSIDE_LONG_RULE` を
    使わなくなったら、この数は要りません（そのとき `[!!]` の [数] の行も落とすこと）。
    """
    rows = [r for r in aged_views(hours, views_path=views_path, uploaded_path=uploaded_path)
            if r.get("form") == form]
    total = len(rows)
    if not total:
        return 0, 0
    tops = {str(t.get("id")): str(t.get("style") or "")
            for t in (topics if topics is not None else _topics())}
    try:
        from src import script_writer as _sw
    except Exception:                                              # noqa: BLE001
        return 0, total
    checks = (_sw.outside_opening_problems, _sw.outside_body_problems,
              _sw.outside_title_problems, _sw.outside_pacing_problems)
    treated = 0
    for r in rows:
        # **型を持たない題材は、写しようがありません**（処置の外）。
        if tops.get(str(r.get("topic") or "")) != "outside_long":
            continue
        try:
            script = json.loads((QUEUE / f"{r['video_id']}.script.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if all(not f(script) for f in checks):
            treated += 1
    return treated, total


def expected_lines(now=None, *, picks_path=None, views_path=None,
                   uploaded_path=None, aged_call=None) -> list:
    """**決めが宣言した 齢48h の見込みを、実物と並べる**（0単位）。

    ## なぜ要るか（2026-09-04 19:2x に踏んだ）

    `record()` は最初から `expected_48h` という欄を書いています。**どこも読んでいませんでした**
    —— `grep expected` の当たりは `record()` の引数・書く行・`replace_video()` が写す行の
    **3か所だけ**で、実物と並べる口が1つもない。実測 `data/daily_pick.jsonl` 22行 の
    `expected_48h` は **全部 null** です。
    ＝ **欄の名前だけが「見込みを立てて後で答え合わせする」と言っていて、誰もしていませんでした。**
    この repo でいちばん多い壊れ方（言っている所と、している所が別）の、この欄ぶんです。

    形の決めは、いま「前の回の散文」の鎖になっています（`standing_form_conflict()` の註）。
    **鎖を切るのは新しい言葉ではなく、外れたと分かる数**です —— `CLAUDE.md` の `--moves` が
    同じ形で置かれています（「**先に言って、次の回が実際の差と並べます。外れてよい。
    外れたと分かるほうが、何も言わずに進むより速い**」）。

    **覆る条件**: 宣言が 5件 たまっても、実物との差が形を1度も入れ替えないなら、
    この欄は形の判断に効いていません。そのときは畳んで `--moves` だけに戻すこと。
    """
    all_rows = list(_jsonl(picks_path or PICKS))
    rows = [r for r in all_rows if pick_kind(r) == PICK_KIND_DECIDE]
    if not rows:
        return []
    last_by_day = {}
    for r in _by_at(rows):
        if r.get("for_day"):
            last_by_day[str(r["for_day"])] = r
    # **見込みは「決め」の行から、動画IDは「その日の最後の行」から**（2026-09-04 19:3x に直した）。
    # 焼き直しは決めを触らずに ID だけ写します（`kind="carry"`）。決めの行の ID を
    # そのまま引くと、**焼き直したあとは古い ID を探しにいって永久に「待ち」**になります
    # —— この節を書いた同じ回に、走っている焼きが `XwB8nxtN5D8` を差し替える寸前でした。
    now_id = {}
    for r in _by_at(all_rows):
        if r.get("for_day") and r.get("video_id"):
            now_id[str(r["for_day"])] = str(r["video_id"])
    # **あとの決めが黙っても、宣言は消えません**（2026-09-04 19:4x に、検査が拾った）。
    # `last_by_day`（その日のいちばん新しい決め）だけを見ると、**`--expected` を付けずに
    # 決め直した回が、前の回の宣言を黙って消せます** —— 実測 09-04: 18:39 に 8回 を宣言した
    # 決めを、19:24 の別の回が `--expected` 無しで上書きしました。
    # **数を消せるのは、別の数だけ**（`--moves` と同じ）。
    # ただし**形が変わったら、その宣言はもう別の話**なので落とします。
    said = {}
    for r in _by_at(rows):
        d = str(r.get("for_day") or "")
        if not d or not now_id.get(d):
            continue
        if isinstance(r.get("expected_48h"), (int, float)):
            said[d] = r
        elif d in said and str(r.get("form") or "") != str(said[d].get("form") or ""):
            said.pop(d)                      # 形を変えた決めは、前の見込みを引き継がない
    if not said:
        n = len(last_by_day)
        return [f"     [!] **決めが 齢48h の見込みを1件も言っていません**（{n}日 ぶん・"
                f"`expected_48h` は全部 null）—— **`--moves` と同じで、外れてよい数です。**"
                f" 次に決める回は `--expected <回>` を付けること —— "
                f"付けないと、形の決めは実物と並べられず、**散文の鎖のまま**になります。"]
    call = aged_views if aged_call is None else aged_call
    try:
        got_rows = call(AGE_HOURS, views_path=views_path, uploaded_path=uploaded_path)
        aged = {str(x.get("video_id")): x for x in got_rows}
    except Exception as exc:                                   # noqa: BLE001
        return [f"     （見込みと実物を並べられませんでした: {str(exc)[:70]}）"]
    out = []
    scored = []
    waiting = []
    for day_s in sorted(said):
        r = said[day_s]
        vid = now_id.get(day_s) or str(r.get("video_id"))
        exp = float(r.get("expected_48h"))
        got = aged.get(vid)
        if got is None:
            waiting.append(f"{day_s} {r.get('form')} 見込み {exp:,.0f}回"
                           f"（`{vid}` はまだ 齢48h ではありません）")
            continue
        real = int(got.get("views") or 0)
        scored.append((day_s, exp, real, (real / exp) if exp else 0.0))
    if scored:
        out.append(f"     **決めの見込みと実物（齢48h・{len(scored)}件）**"
                   f" —— **外れてよい。外れたと分かるほうが速い**（`--moves` と同じ形）:")
        for day_s, exp, real, ratio in scored:
            r = said[day_s]
            out.append(f"       {day_s} {r.get('form')} `{r.get('topic')}`"
                       f"  見込み {exp:,.0f}回 → 実物 {real:,}回  ＝ **×{ratio:.2f}**")
        med = sorted(x[3] for x in scored)[len(scored) // 2]
        tail = ("**見込みのほうが高い**（形の選びが甘い側へ寄っています）" if med < 1
                else "**実物のほうが高い**（見込みが辛い側へ寄っています）")
        out.append(f"       中央 **×{med:.2f}** —— {tail}")
    for w in waiting:
        out.append(f"     　 待ち: {w}")
    return out


#: この回が立った時刻（`data/runs.jsonl` の最後の `start`）。**回の中で決め直したかを見るため。**
RUNS = ROOT / "data" / "runs.jsonl"


def round_started_at(runs_path=None):
    """この回が立った時刻（`data/runs.jsonl` の最後の `start`）。読めなければ None。0単位。"""
    last = None
    for r in _jsonl(runs_path or RUNS):
        if r.get("kind") == "start" and r.get("at"):
            last = r
    if not last:
        return None
    try:
        return datetime.fromisoformat(str(last["at"]))
    except ValueError:
        return None


def decided_this_round(row, *, runs_path=None) -> bool:
    """その決めが、**いま走っている回**のものか。0単位。

    ## なぜ要るか（2026-09-04 18:4x に踏んだ）

    `standing_form_conflict()` は、立っている決めの理由をいつでも
    「**前の回の散文です —— 根拠にしないこと**」と呼びます。**決めた回にも同じ字で出ます。**
    実測: この回は 18:20 に数で決め直し、そのあと同じ画面を読んで
    **もう一度 同じ議論をやり直しかけました**（決めから 19分後）。

    **「前の回のものか」は数えられます** —— `data/runs.jsonl` の最後の `start` より
    後に書かれた決めは、この回のものです。**その回に「やり直せ」と言わないこと。**

    **覆る条件**: 1つの回が複数の `start` を書くようになったら（器の回収で並ぶ実測が在ります）、
    この判定は「最後の start 以降」になるので**同じ回の前半の決めを他の回のものと読みます**。
    そのときは `session` の欄で見分けること（`record()` が書いています）。
    """
    at = str((row or {}).get("at") or "")
    t0 = round_started_at(runs_path)
    if not at or t0 is None:
        return False
    try:
        return datetime.fromisoformat(at) >= t0
    except ValueError:
        return False


def _standing_chain_len(picks_path: Path | None = None) -> int:
    """`data/daily_pick.jsonl` の後ろから、同じ形が続いている**決め**の数。0単位。

    **写しの行（`kind="carry"`）は数えません**（2026-09-04 19:0x に直した）。
    焼き直しは動画IDを新しいほうへ写すだけで、**形も題材も理由も回は触っていません**。
    それを数に入れると、「N回 連続で同じ形」は**焼いた回数のぶん水増し**されます ——
    実測 09-04 の `data/daily_pick.jsonl`: 15行 のうち **4行 が写し**でした
    （＝ 画面の「15回 連続」は、決めの数では 11回）。
    **鎖の長さは「回が何回 追認したか」を言う数**なので、機械の写しは入りません。
    """
    rows = _by_at([r for r in _jsonl(picks_path or PICKS)
                   if pick_kind(r) == PICK_KIND_DECIDE])
    if not rows:
        return 0
    last = rows[-1].get("form")
    n = 0
    for r in reversed(rows):
        if r.get("form") != last:
            break
        n += 1
    return n


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
            # **その枠の代金**（2026-09-04 23:5x・最適化の回）。まだ出ていない本 ＝
            # **枠がまだ動かせる**ので、当たっても譲る側に届かないなら、いま言うこと。
            out += win_pays_for_slot("ショート")
            # 48h の数が返ってきたとき、**どこで意味が変わるか**を先に印字します。
            # 出た後に読むと、もうその枠は動かせません。
            try:
                from . import slot_cost as _sc
                _sv = _sc.slot_value()
                _c = (_sv.get("forms", {}).get("ショート") or {}).get("median")
            except Exception:                                       # noqa: BLE001
                _c = None
            if isinstance(_c, (int, float)) and not isinstance(_c, bool) and _c > 0:
                out.append(
                    f"     　 [数] **その 48h の数の読み方は、門2つで3帯です**（`slot_cost.win_band`）: "
                    f"**＜{OUTSIDE_48H_GATE}回 ＝ 外れ** ／ "
                    f"**{OUTSIDE_48H_GATE}〜{_c:,.0f}回 ＝ 作りは効いた／枠の代金は払えていない（この帯では形を長尺へ寄せないこと）** ／ "
                    f"**≥{_c:,.0f}回 ＝ 当たり、かつ枠のぶんを払えた（ここで初めて形を動かしてよい）**。 "
                    f"前提の門 {OUTSIDE_48H_GATE}回 は「いまの長尺の中央値 1回 の ×100」＝ **自分の記録だけの鏡**で、譲る側の数が入っていません")
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
        # **札ではなく実物で選ぶ**（`treated_probe` の註・2026-09-04 22:2x）。
        # `style: outside_long` は意図の札で、実物がその型に届いた証拠ではありません。
        # 型に届いていない本は、前提「外の作り方を写した長尺」を閉じられないので、
        # **その 24h で次の日の形を決めない・次の枠を止めない**。数字は出しますが、門は握らせません。
        _state, _why_not = treated_probe(vid)
        if _state == "no":
            out.append(line + f" —— [!] **この本は処置ではありません**（{_why_not}）。"
                              f"**札（`style: outside_long`）は「外の型で作るつもり」で、"
                              f"実物がその型に届いた証拠ではありません**（`treated_probe`）。"
                              f"前提「外の作り方を写した長尺」の `falsified_if` は"
                              f"**その型の本**を読むので、この本の 24h/48h では閉じられません ——"
                              f" **先読みの門も、次の未決の日の止めも、この本には握らせません。**"
                              f"（実物で数えた処置: `treated_count('長尺')` ＝ "
                              f"{treated_count('長尺')[0]}本／{treated_count('長尺')[1]}本）")
            continue
        if h < 24:
            line += (f" → 24h（{h24:%m/%d %H:%M} JST）の先読みの門 {OUTSIDE_24H_GATE}回 まで待つ。"
                     f"**次の未決の日は、それまで決めないこと** ——"
                     f" これは散文ではなく、`record()` が実際に止めます（`daily_pick.probe_hold`）。"
                     f"止まるのは**この本より後の日を長尺で決めるとき**だけで、"
                     f"ショート・この本の日・齢24h 以降は通ります。"
                     f"数字で越えるなら `--anyway \"<数字を含む理由>\"`")
        elif v >= OUTSIDE_24H_GATE:
            line += (f" **≥ 先読みの門 {OUTSIDE_24H_GATE}回 → 次の未決の日の1本も外の作りの長尺**"
                     f"（下書きが無ければ作る・下の行）")
            if verdict_at is None or pub > verdict_at:
                verdict, verdict_at = "go", pub
        else:
            # **門を割ったら、形は門の算に返す**（2026-09-04・最適化の回。`and_path_form()` の註）。
            # 2026-09-03 夜〜09-04 は、ここが「それでも長尺」と決め打ちしていました ——
            # 上の `v >= OUTSIDE_24H_GATE` の枝も長尺なので、**門が決定を1度も変えられない**。
            # そして言い分（「ショートは 4,000時間 の門に 0時間」）は 門2 だけの比較 ＝
            # `gate_arithmetic()` が名指しした **AND の片脚を落とす**誤りでした。
            # 前提の判定（48h・100回）は動かさない —— 動かすのは**次の未決の日の形**だけ。
            _af, _an = and_path_form(now=now, topics=None, uploaded_path=uploaded_path)
            if _af and _af != "長尺":
                line += (f" **＜ 先読みの門 {OUTSIDE_24H_GATE}回 → 次の未決の日の1本は "
                         f"{_af}**（{_an}）。**門2 だけで「長尺のまま」と言わないこと** ——"
                         f" 門1 は両方の道に要る AND で、長尺経由の脚のほうが遠い（`gate_lines`）。"
                         f"前提の判定そのものは 48h・{OUTSIDE_48H_GATE}回 のまま（`falsified_if`）")
            else:
                line += (f" **＜ 先読みの門 {OUTSIDE_24H_GATE}回 → 次の未決の日の1本は長尺のまま**"
                         f"（{_an}）。**同じ作りを繰り返さず、1つ変える**"
                         f"（題の型／絵／冒頭のどれか1つ・変えた点を `--why` に）。前提の判定そのものは "
                         f"48h・{OUTSIDE_48H_GATE}回 のまま（`falsified_if`）")
            if verdict_at is None or pub > verdict_at:
                verdict, verdict_at = "stop", pub
        if h >= 48:
            line += (f"（48h を過ぎている: 前提の判定は `verdict`・門 {OUTSIDE_48H_GATE}回・`deadline_check`）")
            # **門は2つ在ります**（2026-09-05 01:5x）—— 前提の門（100回・`falsified_if`）は
            # 「作りが効いたか」だけを見ます。**枠を長尺へ寄せてよいか**は別の門で、
            # そちらは**譲るショートの実測**（`slot_cost.slot_value()`）です。
            # 100回 は「いまの長尺の中央値 1回 の ×100」＝ **自分の記録だけの鏡**で、
            # 枠の値段が1度も入っていませんでした（`slot_cost.win_band` の註）。
            try:
                from . import slot_cost as _sc
                _b = _sc.win_band(v, gate=OUTSIDE_48H_GATE, give_up="ショート")
            except Exception:                                       # noqa: BLE001
                _b = None
            if _b and _b.get("line"):
                line += f" [数] {_b['line']}"
        out.append(line)
    return out, verdict


def _unbuilt_outside(tops: list[dict], uploaded_path: Path | None = None) -> list[dict]:
    """`style: outside_long` の題材のうち、まだ1本も上げていないもの（台帳の順）。0単位。"""
    made = {str(r.get("topic") or "") for r in _latest_uploaded(uploaded_path).values()}
    return [t for t in tops if str(t.get("id") or "") not in made]


#: **長尺の読み上げの実効の速さ（字/秒）。台本の字数 ÷ 実物の尺 の実測。**
#: 2026-09-05 01:5x に、`data/uploaded.jsonl` の `duration_s` を持つ本と
#: `data/critique_queue/*.script.json` を突き合わせて数えた（**n=11・API 0単位**）:
#:
#:     XwB8nxtN5D8  7,749字  1,369.0秒  22.8分  5.66字/秒
#:     GFvAcxvDmYM  7,699字  1,361.1秒  22.7分  5.66字/秒   ← 09/05 09:00 の枠
#:     e6sLHLmPhrk  7,686字  1,357.6秒  22.6分  5.66
#:     Ec-j1-W4nqw  7,495字  1,324.0秒  22.1分  5.66
#:     O_lfBxB7S8Q  7,495字  1,331.3秒  22.2分  5.63
#:     1huadpEk6HY  6,584字  1,192.0秒  19.9分  5.52
#:     6PKux5HNnUE  6,480字  1,174.4秒  19.6分  5.52
#:     DfFyu8qZq3I  6,458字  1,149.1秒  19.2分  5.62
#:     dRZnZrRy2Lw  6,193字  1,104.7秒  18.4分  5.61
#:     6GtzWaguZhg  1,688字    309.9秒   5.2分  5.45
#:     SD8zQU-x6y0  1,638字    301.1秒   5.0分  5.44
#:     中央 **5.62**・最小 5.44・最大 5.66（**幅 0.22 ＝ ほぼ一定**）
#:
#: **`src/pipeline.CHARS_PER_SECOND`（5.2）はここでは使いません。** 5.2 は
#: 2026-08-09 の「465文字が89秒」＝ **読み上げそのものの速さ**で、動画の尺ではありません。
#: 5.2 で割ると尺は **実物の 1.08倍**（8% 長く）出ます。
#:
#: **`script_writer.EFFECTIVE_CHARS_PER_SECOND`（4.63）も違います** —— あれは
#: 2026-08-09 に**ショート1本**（184字 39.7秒）から取った数で、コマ数が多く無音の比率が
#: 高いショート専用です（`SHORT_TOTAL_CHARS` を引くのにだけ使われています）。
#: 長尺に当てると尺は実物の **1.21倍** に出ます。
#:
#: **覆る条件**: この表は 11本 です。長尺の作り（コマ数・間合い）を変えたら
#: 数え直すこと —— 上の突き合わせは `data/uploaded.jsonl` の `duration_s` と
#: 台本の字数を割るだけで、**API を1単位も使いません。**
LONG_CHARS_PER_SECOND = 5.62


def script_seconds(video_id: str) -> float | None:
    """**控えの台本から引いた尺（秒）。**読めなければ `None`。API 0単位。

    ## 2026-09-05 01:5x に直した —— **この関数は「下限」ではありませんでした**

    ここは `src/pipeline.CHARS_PER_SECOND`（**5.2字/秒**）で割って、
    **「コマの間合いは足していないので、実物はこれ以上になります（下限です）」**
    と書いてありました。**実物を測ったら、逆でした。**

        `GFvAcxvDmYM`  台本 7,699字
          5.2字/秒 で割った見積り  **1,481秒 ＝ 24.7分**
          実物（`data/uploaded.jsonl` の `duration_s`）  **1,361.1秒 ＝ 22.7分**
          ＝ 見積りは実物より **120秒 長い**（**下限ではなく上振れ**）

    n=11 で数えると実効は **5.62字/秒**（最小 5.44・最大 5.66）で、5.2 ではありません。
    **5.2 は読み上げそのものの速さで、動画の尺の速さではない** ——
    無音を足せば遅くなるはずだ、という向きの推測が、そのまま「下限」と書かれていました。
    **実測は逆を向いています**（コマの切り替えで読み上げが詰まるぶんが勝っている）。

    ## なぜ 2分 が効くのか

    `OUTSIDE_LONG_KNEE_SEC` ＝ **25分**。外の長尺 365本 の実測は
    20〜25分 **823回/日** 対 25〜30分 **3,507回/日**（**×4.3**）。
    24.7分 なら「切れ目の手前 0.3分 ＝ ほぼ境目」ですが、
    **22.7分 は帯の真ん中**です。**この2分の違いは、09/07 の判定の読み方を変えます。**

    **覆る条件**: `LONG_CHARS_PER_SECOND` の表を数え直して中央が動いたら、
    この関数の数も一緒に動きます。**公開ずみの本は、見積りではなく
    `data/uploaded.jsonl` の `duration_s`（実物）を見ること** ——
    `measured_seconds()` がそれを返します。
    """
    path = ROOT / "data" / "critique_queue" / f"{video_id}.script.json"
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None
    segs = d.get("segments") or []
    chars = sum(len(str(x.get("narration") or "")) for x in segs if isinstance(x, dict))
    return chars / LONG_CHARS_PER_SECOND if chars else None


def measured_seconds(video_id: str, uploaded_path: Path | None = None) -> float | None:
    """**実物の尺（秒）。**`data/uploaded.jsonl` の `duration_s` の最後の行。API 0単位。

    **見積り（`script_seconds`）より、こちらが在るならこちらを見ること。**
    上げた後の本には必ず在ります（`duration_s` を持つ本は 2026-09-05 時点で 258本）。
    """
    out = None
    for r in _jsonl(uploaded_path or (ROOT / "data" / "uploaded.jsonl")):
        if r.get("video_id") == video_id and r.get("duration_s"):
            try:
                out = float(r["duration_s"])
            except (TypeError, ValueError):
                continue
    return out


#: 外の帯の長尺を、尺の帯ごとに「1日あたり再生の中央値」で並べた実測
#: （2026-09-04 23:5x・`data/niche_corpus.jsonl` の長尺 365本 を齢で割った）。
#: **切れ目は 25分**: 20〜25分 n=37 823回/日 対 25〜30分 n=34 **3,507回/日**（×4.3）。
#: チャンネルの大きさの交絡を止めても向きは同じ —— 25分をまたいで両方を持つ
#: チャンネル 12件 中 **9件** で 25分以上のほうが速く、チャンネル内の比の中央 **×2.89**
#: （符号検定 片側 p=0.073・n=12）。**p は 0.05 を割っていません。目安として読むこと。**
#:
#: **覆る条件**: `data/niche_corpus.jsonl` が入れ替わったら数え直すこと
#: （**ここに写した数を信じないで、毎周 数え直すのが本筋**です —— この定数は
#: 「どこで切れるか」の目印で、倍率そのものは帯が変われば動きます）。
OUTSIDE_LONG_KNEE_SEC = 1500


def draft_length_lines(video_id: str) -> list[str]:
    """**その下書きの尺は、外の帯の切れ目のどちら側か。**（API 0単位）

    ## なぜ要るか（2026-09-04 23:5x に自分で踏んだ）

    この回、同じ本の尺を **20.7分** と書いて `premise` を1件 出しました。
    **違いました。** 字数を **6.2字/秒** で割ったのが誤りでした。
    **台本に秒数の欄が無く**（`segments` は `narration` と `visual` だけ）、
    `data/views.jsonl` にも `secs` が無いので、**見積もるしかありません** ——
    そのとき repo の実測を探さずに頭の中の数を使うと、40分後に自分で訂正することになります。

    **だから、ここが数えて印字します。** 次の回は割り算をしません。

    ## 2026-09-05 01:5x —— **訂正した数も、まだ違っていました**

    上の段は「正本は **5.2字/秒**（`src/pipeline.CHARS_PER_SECOND`）＝ **24.7分**」と
    直して終わっていました。**それも違います。実物は 22.7分 です。**

        `GFvAcxvDmYM`   6.2字/秒 → 20.7分（1回目の誤り）
                        5.2字/秒 → 24.7分（1回目の訂正・**これも誤り**）
                        **実物  → 22.7分**（`data/uploaded.jsonl` の `duration_s` 1,361.1秒）

    **5.2 は読み上げそのものの速さ**（2026-08-09「465文字が89秒」）で、
    **動画の尺の速さではありません。** 実効は **5.62字/秒**
    （`LONG_CHARS_PER_SECOND`・`duration_s` を持つ本 11本 の中央）。

    そして上の段は「**公開後は…間合いのぶん長くなります**」と書いていました ——
    **逆でした。** 見積り 1,481秒 に対して実物 1,361.1秒 ＝ **見積りのほうが 120秒 長い**。
    **「無音を足せば遅くなるはずだ」という推測の向きが、2回とも数の代わりに置かれていました。**

    **いまは推測しません** —— `measured_seconds()` が `duration_s` を返し、
    公開ずみの本ではそちらを印字します。**見積りを使うのは、まだ上げていない本だけ**です。

    **公開後は、この見積りではなく実物（`duration_s`）を見ること。**
    """
    # **公開ずみなら、見積りではなく実物を見ること**（2026-09-05 01:5x に直した）。
    # ここは 5.2字/秒 の見積りを「下限」と呼んでいましたが、実測は逆で
    # **見積りのほうが 8% 長く出ます**（`LONG_CHARS_PER_SECOND` の表）。
    real = measured_seconds(video_id)
    sec = real if real else script_seconds(video_id)
    if not sec:
        return []
    knee = OUTSIDE_LONG_KNEE_SEC
    side = "**上（帯のいちばん速い側）**" if sec >= knee else "**下**"
    gap = abs(sec - knee) / 60.0
    if real:
        src_note = (f"{int(sec)}秒 ＝ **実物**（`data/uploaded.jsonl` の `duration_s`）。"
                    f"**見積りではありません**")
    else:
        src_note = (f"{int(sec)}秒 ＝ 台本の字数 ÷ {LONG_CHARS_PER_SECOND}字/秒"
                    f"・`daily_pick.LONG_CHARS_PER_SECOND`（実物 11本 から数えた中央）。"
                    f"**`pipeline.CHARS_PER_SECOND`（5.2）で割ると 8% 長く出ます** ——"
                    f"5.2 は読み上げの速さで、動画の尺の速さではありません")
    return [
        f"     この下書きの**尺 {sec / 60:.1f}分**（{src_note}）——"
        f" 外の帯の切れ目 {knee // 60}分 の {side}・差 {gap:.1f}分",
        f"       外の長尺 365本 を齢で割った実測: 20〜25分 n=37 **823回/日** 対"
        f" 25〜30分 n=34 **3,507回/日**（×4.3）。"
        f"チャンネルの大きさを止めても 12件中 9件 で 25分以上が速く、中央 ×2.89"
        f"（符号検定 片側 p=0.073 ＝ **0.05 を割っていません。目安**）",
    ]


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
                   f"手で撃つなら（同じ物）—— **先に `python scripts/ahead_sweep.py --dry-run` の `[rebake]` を見ること**: "
                   f"「一度 焼いた（印）」と出ていれば機械がいま焼いている。**そのとき手で撃つと同じ本が2本 上がる**"
                   f"（2026-09-03 05:0x に実測: 手の bake 中に `--rebake-run` が同じ sha で起きた・片方を kill）:")
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
    # **ほかの日の決め（最後の行）が名指ししている本 → その日**（2026-09-03 05:0x に足した。
    # 下の「ほかの日に決めてある下書きの冒頭」で使う）
    taken_day: dict[str, str] = {}
    try:
        last_by_day: dict[str, dict] = {}
        for r in _jsonl(PICKS):
            if r.get("for_day") != day.isoformat() and r.get("video_id"):
                taken.add(str(r["video_id"]))
            if r.get("for_day"):
                last_by_day[str(r["for_day"])] = r
        for d_s, r in last_by_day.items():
            if d_s != day.isoformat() and r.get("video_id"):
                taken_day[str(r["video_id"])] = d_s
    except Exception:                                          # noqa: BLE001
        pass
    if ro == "stop":
        # **門を割った回は、形を門の算（AND の道）に返す**（2026-09-04・最適化の回・`and_path_form()` の註）。
        # 2026-09-03 夜のここは「ショートへは倒さない」と決め打ちで、`ro` が `"go"` でも `"stop"` でも
        # 長尺になっていました ＝ **先読みの門が、それが門をしている決定を1度も変えられない。**
        # 前提「外の作り方を写した長尺」の判定（48h・100回）は、この行では動かしません。
        _af, _an = and_path_form(now=now, uploaded_path=uploaded_path)
        if _af and _af != "長尺":
            out.append(f"     → **{day:%m/%d} の1本は {_af}**（1本目が 24h で先読みの門の下・{_an}）。"
                       f"**門2 だけで「長尺のまま」と言わないこと** —— 門1 は両方の道に要る AND です"
                       f"（`gate_lines`）。前提「外の作り方を写した長尺」の判定は 48h・"
                       f"{OUTSIDE_48H_GATE}回（期限 {dl}）で別 —— **形を戻しても前提は生きています**")
        else:
            out.append(f"     → **{day:%m/%d} の1本も長尺のまま**（1本目が 24h で門の下・{_an}）。"
                       f"**次の1本は同じ作りを繰り返さず 1つ変える**（題の型／絵／冒頭のどれか1つ・"
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
            out.extend(draft_length_lines(vid))
            if not cur or str(cur.get("video_id") or "") != vid:
                out.append(f"     → **{day:%m/%d} の1本はこれにすること**（`by_form()` の長尺 1回 は"
                           f"『5分・計算1本』の数で、この本の数ではない。外の長尺 p90 は自分の中央値の ×624,772・"
                           f"`outside_lines`）:")
                out.append(f"       python -m src.daily_pick --pick 長尺 {d.get('topic')} --video {vid}"
                           f" --day {day:%Y-%m-%d} --why \"外の作りを写した長尺の1本目（前提の判定・期限 {dl}）。"
                           f"外の長尺 p90 ÷ 自分の中央値 1回\"")
            # **ほかの日に決めてある外の作りの下書きも、冒頭を数えて見せる**（2026-09-03 05:0x に踏んだ）。
            #     この画面は決めた日の1本（上の `d`）の冒頭しか数えておらず、09/05 の決め `dRZnZrRy2Lw`
            #     （02:29 に決めた・冒頭 4件 型の外）は 04:2x の回の申し送りでしか見えなかった。
            #     `rebake_today` は `for_day` の本しか焼き直さないので、**先の日の本は台本を直す回が要る** ——
            #     台本の直しは 0単位で、その日が来れば機械が焼く。見えなければ、その回は来ない
            #     （`retro.py`: 3周 以上 運ばれて実物に当たったのが 1回 以下 ＝ 道具の側を疑え）。
            for x in have:
                xv = str(x.get("video_id") or "")
                if not xv or xv == vid or xv not in taken_day:
                    continue
                xl = outside_opening_lines(xv, str(x.get("topic") or ""))
                if xl:
                    out.append(f"     ほかの日（{taken_day[xv][5:].replace('-', '/')}）に決めてある外の作りの下書き "
                               f"`{xv}` `{x.get('topic')}`:")
                    out.extend(xl)
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


def _subs_rates(path: Path | None = None) -> dict:
    """**形べつの「千再生あたり何人 登録するか」**を、`data/shorts_subs.json` から読む。API 0単位。

    出どころは `scripts/shorts_subs.py` が積んだ最後の実測
    （`creatorContentType`。**題名の札ではなく YouTube が数えた形**）。
    返り: `{"ショート": {"per_1000": 0.237, "views": 88434, "subs": 21, "ci": [lo, hi]}, ...}`。
    **読めなければ空の dict**（呼ぶ側は行を出さないこと。推測で埋めないこと）。
    """
    try:
        raw = json.loads((path or (ROOT / "data" / "shorts_subs.json")).read_text("utf-8"))
    except Exception:                                          # noqa: BLE001
        return {}
    out: dict = {}
    for form, d in (raw.get("forms") or {}).items():
        if form not in ("ショート", "長尺"):
            continue
        try:
            out[form] = {"per_1000": (None if d.get("subs_per_1000") is None
                                      else float(d["subs_per_1000"])),
                         "views": float(d.get("views") or 0.0),
                         "subs": int(d.get("subs_net") or 0),
                         "ci": d.get("ci_per_1000")}
        except (TypeError, ValueError):
            continue
    out["at"] = raw.get("at")
    return out


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
    # --- **門1（登録者1,000人）。両方の道に要る脚**（2026-09-03 夜・最適化の回）---
    #     ここは長らく `{"have": 25, "need": 1000}` の2つの数だけで、
    #     **倍率にも `nearer` にも入っていませんでした。** 門1 は 門2a/門2b の
    #     どちらの道でも **AND** で要ります（`scripts/shorts_subs.py` §4 が
    #     公表ページから引いている）。つまり `nearer` は「**OR の2脚のうち
    #     どちらが近いか**」しか答えていないのに、画面はそれを
    #     「門に近い形」と印字し、`fallback_form()` はそれで**その日の1本の形**を
    #     決めていました。**必ず要る脚が、形の比較から抜けていた**ということです。
    #
    #     この回に自分で撃った数（`data/shorts_subs.json`・API 0単位）:
    #
    #         形      本数  再生     登録  登録/千再生   95%区間
    #         ショート  186  80,957   21    0.237      [0.147 〜 0.363]
    #         長尺      28     470    1     2.128      [0.054 〜 11.855]  ← 分母 470再生
    #
    #     **率では決まりません**（区間が重なる・長尺の分母は 470再生）。決まるのは
    #     **1本あたりに直したとき**です —— 率 × その形の1本あたり再生:
    #
    #         ショート  0.237/千 × 中央値 213回 = **0.051人/本**
    #         長尺      2.128/千 × 中央値   4回 = **0.009人/本**
    #
    #     要るのは 975人 ÷ 365日 ÷ 1本/日 ＝ **2.67人/本**。→ ショート ×53・長尺 ×313。
    #     **どちらも 門2 の脚より遠い。** 門1 が縛っている脚です。
    #
    #     **覆る条件**: 長尺の分母（470再生）が桁で増えたら率が測り直され、
    #     この2つの倍率は自分で入れ替わりえます（定数は持ちません）。
    #     `data/shorts_subs.json` が無い回は、この脚は `None` で出ません
    #     （**推測で埋めないこと** —— 埋めると、必ず要る脚が推測になります）。
    rates = _subs_rates()
    have_subs = float(s.get("subs_net") or 0)
    left_subs = max(float(c["subs"]) - have_subs, 0.0)
    need_subs_per_video = left_subs / float(c["window_days"])       # 1本/日 → 1本あたり
    subs_leg: dict = {"have": s.get("subs_net"), "need": c["subs"],
                      "left": left_subs, "need_per_video": need_subs_per_video,
                      "at": rates.get("at"), "forms": {}}
    _own_med = {"ショート": ((cmp.get("rule") or {}).get("ショート") or {}).get("median"),
                "長尺": ((cmp.get("life") or {}).get("長尺") or {}).get("median")}
    for _f in ("ショート", "長尺"):
        _r = rates.get(_f) or {}
        _p1000, _med = _r.get("per_1000"), _own_med.get(_f)
        if _p1000 is None or _med is None:
            continue
        _per_video = float(_p1000) / 1000.0 * float(_med)
        subs_leg["forms"][_f] = {
            "per_1000": float(_p1000), "median_views": float(_med),
            "subs_per_video": _per_video, "sample_views": _r.get("views"),
            "sample_subs": _r.get("subs"), "ci_per_1000": _r.get("ci"),
            "x": (need_subs_per_video / _per_video) if _per_video > 0 else float("inf"),
        }
    out["subs"] = subs_leg
    xs, xl = out["shorts"]["x_median"], out["long"]["x_median"]
    out["nearer_or"] = "長尺" if xl <= xs else "ショート"
    _sf = subs_leg["forms"]
    if len(_sf) == 2:
        out["nearer_subs"] = min(_sf, key=lambda k: _sf[k]["x"])
        out["gate1_binds"] = (min(v["x"] for v in _sf.values()) > min(xs, xl))
    # --- **道は AND です。近さは、その道の いちばん遠い脚で決まります** ---
    #     （2026-09-03 夜・最適化の回。**`nearer` の中身を、ここで直しました**）
    #
    #     公表の条件は「**登録者1,000人 ＋（長尺4,000時間 ／ ショート1,000万回）**」。
    #     つまり道は2本 あり、**どちらの道でも 門1 が要ります**:
    #
    #         道A（長尺）    門1 ＋ 門2a      道B（ショート）  門1 ＋ 門2b
    #
    #     `nearer` は 2026-09-03 夜まで **門2a と 門2b だけを比べて**いました。
    #     **AND の片脚を落として比べていた**ということです。この回に撃った数:
    #
    #         脚                          倍率
    #         門2a  長尺の視聴4,000時間     **×34**
    #         門2b  ショート90日1,000万回     ×106
    #         門1   登録・ショート経由        **×11**   ← 盤の上でいちばん近い脚
    #         門1   登録・長尺経由            ×314   ← 盤の上でいちばん遠い脚
    #
    #     門2 だけで比べると「近い形は **長尺**（×34 < ×106）」。
    #     **道ごとに、いちばん遠い脚（＝その道の律速）で比べると逆です**:
    #
    #         道A 全部 長尺   max(×314, ×34)  ＝ **×314**
    #         道B 全部 ショート max(×11, ×106) ＝ **×106**
    #
    #     ×314 の道を「近い」と名乗り、`fallback_form()` がその形を選んでいました。
    #     **鎖の長さは、いちばん弱い環で決まります。** 落とした脚（門1・長尺 ×314）は
    #     残した脚（門2a ×34）より **9倍 遠い**ので、落とし方が結論を作っていました。
    #
    #     ## 覆る条件
    #
    #     - 長尺の登録率の分母は **470再生・登録1人**（区間 0.054〜11.855/千）。
    #       **桁で増えたら ×314 は動きます。** そのとき `nearer` は自分で入れ替わります。
    #     - `data/shorts_subs.json` が読めない回は 門1 の脚が立たないので、
    #       `nearer` は**元どおり門2 だけの答え**（`nearer_or`）に落ちます。
    #       **推測で埋めないこと** —— 埋めると、必ず要る脚が推測になります。
    #     - オーナーが 1日1本 を外して両形を同じ日に出せるなら、道は排他ではなくなり、
    #       この比較の主語（「その日の1本の形」）そのものが変わります。
    if len(_sf) == 2:
        _path = {"長尺": max(xl, _sf["長尺"]["x"]),
                 "ショート": max(xs, _sf["ショート"]["x"])}
        out["path_x"] = _path
        out["nearer"] = min(_path, key=lambda k: _path[k])
        out["nearer_flipped"] = (out["nearer"] != out["nearer_or"])
    else:
        out["path_x"] = {}
        out["nearer"] = out["nearer_or"]
        out["nearer_flipped"] = False
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
        f"     → 門2 だけで近い形は **{g.get('nearer_or')}**（要る倍率の小さい側）。"
        f"登録 {int(g['subs']['have'] or 0):,}/{c['subs']:,}人。"
        f" **48時間の再生（上の表）で形を決めないこと** —— あれは門の数ではない。"
        f"ショートへ戻す判定は、この行の倍率が入れ替わった回にだけ出す",
    ]
    # --- **門1（登録者）の脚を、同じ物差しで並べる**（2026-09-03 夜・最適化の回）---
    #     上の `nearer` は 門2a と 門2b の **OR** のうち近いほうです。
    #     **門1 は、その どちらの道でも AND で要ります。** 抜けていました。
    _sl = g.get("subs") or {}
    _sf = _sl.get("forms") or {}
    if _sf:
        _parts = []
        for _f in ("長尺", "ショート"):
            _d = _sf.get(_f)
            if not _d:
                continue
            _parts.append(
                f"{_f} {_d['per_1000']:.3f}人/千再生 × 中央値 {_d['median_views']:,.0f}回"
                f" ＝ {_d['subs_per_video']:.3f}人/本（要る ×{_d['x']:,.0f}"
                f"・標本 {int(_d['sample_subs'] or 0)}人/{int(_d['sample_views'] or 0):,}再生）")
        out.append(
            f"       登録　　 門1 {c['subs']:,}人（**両方の道に要る AND**）"
            f" → あと {_sl['left']:,.0f}人 ＝ 1本/日 で **{_sl['need_per_video']:.2f}人/本** ／ "
            + "・".join(_parts))
        _px = g.get("path_x") or {}
        if _px:
            out.append(
                "     → **道は AND です**（門1 ＋（門2a ／ 門2b））。"
                "**その道の いちばん遠い脚**で比べる: "
                + "・".join(f"道 {k} ＝ ×{v:,.0f}" for k, v in
                            sorted(_px.items(), key=lambda kv: kv[1]))
                + f" → **門に近い形は {g['nearer']}**")
            if g.get("nearer_flipped"):
                out.append(
                    f"     [!] **門2 だけなら {g['nearer_or']}・門1 を足すと "
                    f"{g['nearer']}。** 2026-09-03 夜まで、ここは 門2 だけで"
                    "比べていました（＝ AND の片脚を落として比べていた）。"
                    "落とした脚のほうが遠いので、**落とし方が結論を作っていました**")
        if g.get("gate1_binds"):
            out.append(
                "     [!] **どちらの形でも、門1 の倍率が門2 の倍率より大きい"
                "（＝門1 が縛っている脚）。** その回に引く腕は `sub_rate` か "
                "`per_video`（登録は 再生 × 率）で、`density` は規則で固定"
                "（`src/house_rule.py`）")
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
    # --- **枠の機会費用を、両方の形を同じ物差しで並べて出すこと**（2026-09-05・最適化の回）---
    #
    #     **この回に `compare()` を撃って見つけた欠陥**: すぐ上の形べつの行は、
    #     `c["rule"]`（規則の密度 ≤2本/日 の日だけ）を **ショートにだけ**印字し、
    #     長尺には**生涯**を印字していました。`c["rule"]["長尺"]` は計算ずみで
    #     （実測 n=7・中央値 1回・p90 3回・**最大 4回**）、**どこにも出ていません。**
    #     ＝ **2つの形が、同じ物差しで並んだことが1度もありませんでした。**
    #
    #     そのあいだ形を決めていたのは密度を混ぜた数（ショート **164回**）で、
    #     これは規則がもう禁じている 8本以上/日 の日の本 201本 に引かれた数です
    #     （その帯だけなら 131回）。**規則の下で1枠が実際に何回 だったかは 1,049回。**
    #     ＝ **枠の値を ×6.4 小さく見ていました。**
    #
    #     その小さい数の上で、前提「外の作り方を写した長尺」は**当たりの門を 100回**に
    #     置いて 09/04・09/05 の枠を取りました。**100回 は枠の機会費用 1,049回 の 1/10**
    #     ＝ 全部うまくいっても捨てた枠より小さい試しです（同じ検査で、開いている
    #     もう1つの前提「外の作り方を写したショート」は門 10,000回 で **通ります**）。
    #
    #     **禁止ではありません。** 数を毎周この位置に出すだけです。
    #     **覆る条件**: どの形でも規則の密度の中央値が上がれば `slot_value()` の
    #     勝者はその形に自分で入れ替わり、この門はその形を自分で通します。
    try:
        from . import slot_cost                                    # noqa: PLC0415
        out.extend(slot_cost.lines(c, now=now))
        for _e in slot_cost.open_slot_experiments():
            if _e.get("win") is None:
                continue
            _v = slot_cost.verdict(_e["win"], form=_e.get("form"), cmp=c)
            if _v.get("ok") is False:
                out.append(f"       **枠を食う前提が、枠のぶんを払えません**"
                           f"（{_e.get('form') or '?'}・門 {_e['win']:,.0f}回）: {_v['why']}"
                           f" —— **枠をこの試しに使う前に、門を機会費用まで上げるか、"
                           f"この試しを枠の外（既存本の差し替え）へ移すこと。**")
                # **実際に枠を取った言い分に、その場で数で答えること**（`slot_cost.OVERRIDES`）。
                #     09/04 の3回の決めは、この2つの言い分だけで枠を取っています
                #     （`data/daily_pick.jsonl` の `why`）。門を置いても、
                #     言い分に答えが無ければ次の回がまた同じ手で通します。
                out.extend(slot_cost.override_notes(_e["win"], cmp=c))
    except Exception as exc:                                       # noqa: BLE001
        out.append(f"     （枠の機会費用の行は出せませんでした: {exc}）")
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
        # **理由は「決め」の行から引くこと**（2026-09-04 19:0x に直した）。
        # ここは `cur`（＝ 最後の行）の `why` を引いていました。焼き直しの写しが最後に来た日は、
        # それが**機械の書いた前置き**で、決めた回の数はその中で 140字 に切られていました
        # （実測 09-04T18:06 「…処置を落と」で切断）。
        # いまは写しを飛ばして、**回が最後に数で書いた行**を引きます。
        dec = last_decided(_jsonl(picks_path or PICKS)) or cur
        carried = pick_kind(cur) == PICK_KIND_CARRY
        out.append(f"     **{day:%m/%d} の1本: {cur.get('form')} `{cur.get('topic')}`"
                   f"{' ＝ `' + str(vid) + '`' if vid else ''}**"
                   f"（{str(dec.get('at'))[11:16]} JST に決めた"
                   + (f"・いまの ID は {str(cur.get('at'))[11:16]} の焼き直しが"
                      f"`{cur.get('rebaked_from') or '旧ID'}` から写したもの" if carried else "")
                   + ("・**この回が数で置いた行**（決め直さないこと）: "
                      if decided_this_round(dec)
                      else "・**前の回の散文**（根拠にしない）: ")
                   + f"{str(dec.get('why'))[:90]}）。**変えるなら、数字で上書きすること**"
                   f"（同じコマンドをもう一度）。")
        # **立っている決めを、毎周 いまの門の算と突き合わせる**（2026-09-04・最適化の回・
        # `standing_form_conflict()` の註）。ここまでは、立っている決めの `why`＝前の回の散文だけが
        # 印字され、`and_path_form()` は `outside_long_readout()` が `"stop"` を返す枝でしか
        # 呼ばれていませんでした（その判定はこの回 `None`＝長尺6本の観測が 0件）。
        # ＝ **回は前の決めしか読めず、09-03T02:03 から 11回 連続で同じ形を追認した。**
        out.extend(standing_form_conflict(cur, now=now, picks_path=picks_path))
        # **立っている決めの「その本」を、毎周 脚で測り直す**（2026-09-04 17:xx・
        # `standing_pick_treatment()` の註）。ここまでは、枠に入る1本が処置に
        # なっているかを**どこも数えておらず**、散文の名乗り（「5脚とも ○」）だけが
        # 引き継がれていました。実測でその名乗りは偽（(1) 冒頭 が ✗）。
        out.extend(standing_pick_treatment(cur))
        # **宣言した見込みと実物を並べる**（2026-09-04 19:2x・`expected_lines()` の註）。
        # `expected_48h` は最初から書かれていて、**どこも読んでいませんでした**（実物 22行 全部 null）。
        out.extend(expected_lines(now=now, picks_path=picks_path))
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
    ap.add_argument("--expected", type=float, default=None, metavar="回",
                    help="その形で見込む 齢48h の再生（次の回が実物と並べます。"
                         "`--moves` と同じ形 —— 外れてよい・言わないほうが困る）")
    ap.add_argument("--anyway", default="", metavar="理由",
                    help="`probe_hold()` の止め（先読みの門が開く前に次の未決の日を取る）を"
                         "数字で越える。理由は行に残り、次の回が実物と並べます")
    args = ap.parse_args(argv)
    if args.pick:
        form, topic = args.pick
        day = date.fromisoformat(args.day) if args.day else None
        try:
            row = record(form, topic, args.why, day=day, video_id=args.video,
                         expected=args.expected, anyway=args.anyway)
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


def untreated_slot_block(cur: dict | None, *, topics: list[dict] | None = None,
                         queue: Path | None = None) -> str:
    """**その決めの本を、きょうの枠へ入れて良いか。**良ければ `""`、駄目ならその理由の1行。
    **API 0単位・実物の台本の控えだけ。**

    ## なぜ要るか（2026-09-04 19:5x・最適化の回に数で踏んだ）

    規則1 は 1日1本（`src/house_rule.py`）＝ **その日の枠は、その日の供給の 100%**。
    前提「外の作り方を写した長尺」（`config/hypotheses.yaml`・期限 2026-09-07）は
    その枠を **09-04 と 09-05 の 2日ぶん** 取っています。実物はこうでした ——

        `daily_pick.treated_count("長尺")` → **(0, 36)**  処置ずみ 0本／測れた 36本
        09-04 の枠に入った `1huadpEk6HY` の脚 → **(2) 章・締め／(4) 題・サムネ／(5) 間合い が ✗**
                                                そのまま公開・齢6時間で **0回**

    ＝ **前提のために枠を取りながら、入れた本が前提の処置になっていません。**
    枠は減り（供給 100% が 1日 消える）、前提は 1件も進みません（分母は 0/36 のまま）。
    そして分母が 0 のあいだ「**処置 n=0 の分母で処置は落とせない**」が成り立つので、
    **次の回も同じ形を選び直します** —— 09-04 だけで決めが 14回、全部 長尺、
    形は 1度も変わっていません（`data/daily_pick.jsonl`）。**自分で自分を養う輪**です。

    `standing_pick_treatment()`（09-04 17:xx）は同じ穴を見つけて**刷りました**。
    刷ったあと決めが 6回 あり、**6回とも 長尺のまま**でした。
    ＝ **印字は選び直しを止めません。** ここは止める側です。

    ## 止まりっぱなしにはなりません

    返した理由は `scripts/ahead_sweep` が `rebake_pending` と同じ枝へ渡します
    （「**焼き直しが先。置くのは後**」）。あの枝は枠まで `REBAKE_LEAD` を切ると
    自分で開くので、**永久に置かれない は構造上 起きません** ——
    直せば置く・直さなければ枠の直前に置く、のどちらかです。
    要求は1つだけ: **枠までに、その本を処置にすること**
    （＝ オーナーの固定「次の投稿予定までにそこで投稿する動画を改善し続ける」）。

    ## 覆る条件

    - 前提「外の作り方を写した長尺」が閉じたら、この門ごと落とすこと。
    - `treated_count("長尺")` の処置ずみが 1本以上 になったら、
      「前提のために枠を取りながら処置が 0本」は偽になります。**そのとき自分で黙ります**
      （分母が出来たので、次の回は数で形を落とせる）。
    - 脚が読めない（控えが無い）ときは**止めません**。読めないものを ✗ に数えないのは
      `pick_legs` と同じ向きです。
    """
    if not cur:
        return ""
    topic = str(cur.get("topic") or "")
    tops = {str(t.get("id")): str(t.get("style") or "")
            for t in (topics if topics is not None else _topics())}
    if tops.get(topic) != "outside_long":
        return ""
    vid = str(cur.get("video_id") or "").strip()
    bad, why = pick_legs(vid, queue=queue)
    if why or not bad:
        return ""
    try:
        done, seen = treated_count("長尺")
    except Exception:                                          # noqa: BLE001
        return ""
    if done:
        return ""
    head = (f"`{vid}` は前提「外の作り方を写した長尺」の脚が {len(bad)}本 ✗"
            f"（{'／'.join(bad)}）。処置ずみは {done}/{seen}本 なので、この本を入れると"
            f"**枠は減って前提は進みません**（09-04 の `1huadpEk6HY` と同じ形・齢12時間で 2回）。")
    if metadata_only(bad):
        # **焼き直しでは直りません**（`METADATA_LEGS` の註に実測）。
        return head + METADATA_FIX_HOWTO
    return head + "枠までに脚を通してから置きます"


def metadata_fix_plan(cur: dict | None, *, topics: list[dict] | None = None,
                      queue: Path | None = None) -> dict | None:
    """**焼き直さずに直せるときの、直す中身。**無ければ `None`。API 0単位。

    返す: `{"video_id", "title", "thumbnail_kicker", "thumbnail_line1",
            "thumbnail_line2", "bad", "topic"}` —— 値は**手元の台本**から取ります。

    ## 出す条件は3つ全部（1つでも欠けたら `None`）

        1. 控え（`pick_legs`）が落としている脚が **metadata だけ**
        2. 手元の台本（`draft_legs`）は **4脚とも ○** —— 直った先が在ること
        3. 決めが本と題材を名指していること

    **2 が要る理由**: 手元も落ちているなら、写す先が無いので直しになりません
    （そのときは焼き直しでもなく、**台本を直す**のが先）。
    """
    if not cur:
        return None
    topic = str(cur.get("topic") or "").strip()
    vid = str(cur.get("video_id") or "").strip()
    if not topic or not vid:
        return None
    tops = {str(t.get("id")): str(t.get("style") or "")
            for t in (topics if topics is not None else _topics())}
    if tops.get(topic) != "outside_long":
        return None
    bad, why = pick_legs(vid, queue=queue)
    if why or not metadata_only(bad):
        return None
    dbad, dwhy = draft_legs(topic)
    if dwhy or dbad:
        return None
    try:
        draft = json.loads((ROOT / "data" / "scripts" / f"{topic}.script.json")
                           .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    out = {"video_id": vid, "topic": topic, "bad": list(bad)}
    for k in ("title", "thumbnail_kicker", "thumbnail_line1", "thumbnail_line2"):
        out[k] = draft.get(k)
    if not out.get("title"):
        return None
    return out


if __name__ == "__main__":
    raise SystemExit(main())
