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
    out.sort(key=lambda x: (x["pub"], x["form"], x["video_id"]))
    return out


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
              min_n: int = FAMILY_MIN_N) -> list[dict]:
    """族（`calc`）ごとの 48時間 再生（その形だけ）。中央値の高い順。"""
    vals: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r["form"] != form or not r.get("family"):
            continue
        vals[r["family"]].append(int(r["views"]))
    out = []
    for fam, v in vals.items():
        st = _stats(v)
        st["family"] = fam
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
                    "fam_median": (st or {}).get("median"), "fam_n": (st or {}).get("n", 0),
                    "draft": r.get("retimed_at") is None})
    out.sort(key=lambda x: (-(x["fam_median"] or -1), -x["fam_n"], x["video_id"]))
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
                    "fam_median": (st or {}).get("median"), "fam_n": (st or {}).get("n", 0)})
    out.sort(key=lambda x: (-(x["fam_median"] or -1), -x["fam_n"], x["topic"]))
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


def _fmt(v) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}回"


def _ratio_line(cmp: dict, draft_form: str) -> str | None:
    other = "長尺" if draft_form == "ショート" else "ショート"
    a = cmp["all"].get(draft_form, {}).get("median")
    b = cmp["all"].get(other, {}).get("median")
    if a is None or b is None or (b <= 0 and a <= 0):
        return None
    if a <= 0:
        return (f"     ＝ 下書きの形（{draft_form}）の中央値は 0回。もう一方（{other}）は "
                f"{_fmt(b)}。")
    r = b / a
    if r >= 1:
        return (f"     ＝ 下書きの形（{draft_form}）は、もう一方の形（{other}）の "
                f"**1/{r:,.0f}**（中央値どうし）。")
    return (f"     ＝ 下書きの形（{draft_form}）は、もう一方の形（{other}）の "
            f"**×{1 / r:,.1f}**（中央値どうし）。")


def _hour_default() -> int:
    """機械が実際に置く時刻（`config/channel.yaml` の `publish_hour_jst`）。"""
    try:
        from . import publish_hour
        h = publish_hour.config_hour()
        return int(h) if h is not None else 9
    except Exception:                                          # noqa: BLE001
        return 9


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
        out.append(f"     下書き `{next_row.get('video_id')}` は **{draft_form}**"
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
    fams = c.get("families") or []
    if fams:
        top = [f for f in fams if f["enough"]][:6]
        out.append("     族（`calc`）ごとのショートの 48時間 中央値（上位・n≥%d）: " % FAMILY_MIN_N
                   + " ／ ".join(f"`{f['family']}` {_fmt(f['median'])}(n={f['n']})" for f in top))
        if draft_fam:
            rk, st = family_rank(fams, draft_fam)
            if st:
                out.append(f"     下書きの族 `{draft_fam}` は {rk}位／{len(fams)}族"
                           f"（ショート 中央値 {_fmt(st['median'])}・n={st['n']}）")
            else:
                out.append(f"     下書きの族 `{draft_fam or '?'}` は、ショートで測ったことがありません")
    rows_all = c.get("rows") or []
    pool = pool_candidates(fams=fams, exclude=(next_row or {}).get("video_id"),
                           rows=rows_all) if cands is None else cands
    if pool:
        out.append(f"     池に在る private のショート {len(pool)}本（作らずに、その日の枠へ "
                   f"`--move` できる・50単位）—— 族の中央値の高い順:")
        for p in pool[:5]:
            out.append(f"       `{p['video_id']}`  {str(p['title'] or '')[:36]}"
                       f"　族 `{p['family'] or '?'}` {_fmt(p['fam_median'])}(n={p['fam_n']})")
    un = unposted_topics(fams=fams, rows=rows_all) if untried is None else untried
    if un:
        out.append(f"     まだ作っていない `s-` の題材（`calc` 在り）{len(un)}件 —— 族の中央値の高い順:")
        for u in un[:4]:
            out.append(f"       `{u['topic']}`  {str(u['title'] or '')[:36]}"
                       f"　族 `{u['family'] or '?'}` {_fmt(u['fam_median'])}(n={u['fam_n']})")
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
    hour = _hour_default()
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
                out.append(f"     　 下書き `{next_row.get('video_id')}` は**消さない**"
                           f"（private のまま池に残す。決めた本が出せなくなった日の代わり）。")
        elif draft_form and cur.get("form") and cur.get("form") != draft_form:
            out.append(f"     [!] **決めた形（{cur.get('form')}）と、下書きの形（{draft_form}）が"
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
