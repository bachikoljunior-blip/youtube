"""**待ちの条件を、機械が見張る。**

## なぜ要るか（2026-08-20 に、実物で踏んだ）

`scripts/retention.py` は 8/10 から、こう印字していました。

    [!] **この検定は今回効きません。**尺が 47〜56秒に固まっていて …
        **30秒設計の3本（8/16〜18）が出れば、ここで測れるようになります。**

**その3本は 8/16〜18 に出ています。** 条件は 8/18 に満ちていたのに、
**満ちたことに気づいた回が1つもありません**（気づいたのはオーナーで、10日後）。
道具は正しく「いつ測れるようになるか」を書いていました。**書いた先が、
誰も毎回は読まない場所（その道具を走らせた回の出力）だった**だけです。

**同じ壊れ方は「待ち」がある限り何度でも起きます。** 待ちを書いた回と、
条件が満ちる回は、別の回です。**あいだを繋ぐのは記憶ではなく機械です。**

## この道具がやること

`config/watches.yaml` に「何を待っているか」と「満ちる条件」を**数で**書き、
毎回の `scripts/status.py` がそれを**評価して**出します。

    [!] **満ちました** …  → 走らせるコマンド
    あと N …            → まだのものは、残りを数で

**外の口を1つも叩きません**（手元の `data/*.jsonl` だけ）。日枠が閉じている
回でも、待ちは必ず見えます。

## 満ちたものを黙らせる唯一の方法は、答えを書くこと

満ちた待ちは `answered:` に1行（日付と答え）を入れるまで鳴り続けます。
**「見た」では消えません。** 消すには判定するしかない、という形にしてあります。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

CONFIG = ROOT / "config" / "watches.yaml"
SCAN = ROOT / "data" / "scan.jsonl"
UPLOADED = ROOT / "data" / "uploaded.jsonl"
LAG = ROOT / "data" / "analytics_lag.jsonl"
CRITIQUE = ROOT / "data" / "critique.jsonl"


@dataclass
class Gauge:
    """**いまの値と、要る値。** 単位はそのまま画面に出す。"""

    now: float
    need: float
    unit: str = ""
    note: str = ""
    err: str = ""

    @property
    def met(self) -> bool:
        return not self.err and self.now >= self.need

    @property
    def left(self) -> float:
        return max(0.0, self.need - self.now)


@dataclass
class Watch:
    id: str
    what: str
    cond: str
    then: str
    source: str
    kind: str
    params: dict = field(default_factory=dict)
    answered: str = ""

    def gauge(self) -> Gauge:
        fn = KINDS.get(self.kind)
        if fn is None:
            return Gauge(0, 1, err=f"kind `{self.kind}` は実装がありません")
        try:
            return fn(self.params)
        except Exception as exc:                               # noqa: BLE001
            # **計器が落ちても回は止めない。** ただし黙らない（err を出す）。
            return Gauge(0, 1, err=f"{type(exc).__name__}: {str(exc)[:90]}")


# ---------------------------------------------------------------- 手元の材料

def _last_scan() -> dict[str, dict]:
    """走査の最後の一枚から、動画べつの指標を組み立てる。"""
    rows: dict[str, dict] = {}
    lines = [l for l in SCAN.read_text(encoding="utf-8").splitlines() if l.strip()]
    for k, v in json.loads(lines[-1])["values"].items():
        if k.startswith("動画.") and k.count(".") >= 2:
            _, vid, metric = k.split(".", 2)
            rows.setdefault(vid, {})[metric] = v
    return rows


def _uploaded() -> list[dict]:
    if not UPLOADED.exists():
        return []
    out = []
    for line in UPLOADED.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _publish_dates() -> dict[str, date]:
    """動画ID → 公開日（JST）。**予約ぶんも入ります**（`at` は予約時刻）。

    控えは 8/16 以降しかありません。それより前の本は入りません ——
    いま見張っている待ちは全部それより後の窓なので、足りています。
    **前を数える待ちを足すときは、`data/views.jsonl` からの復元
    （`scripts/per_day_views.published_at`）に替えること。**
    """
    out: dict[str, date] = {}
    for r in _uploaded():
        at = r.get("at") or r.get("uploaded_at")
        vid = r.get("video_id")
        if not at or not vid:
            continue
        try:
            out[vid] = datetime.fromisoformat(
                str(at).replace("Z", "+00:00")).astimezone(JST).date()
        except ValueError:
            continue
    return out


def analytics_last_day() -> date | None:
    """**実データがどこまで届いているか**（`status.py` が毎回積んでいる点）。

    公開しただけでは判定できません。**Analytics の日次は3日遅れる**ので、
    「本が出たか」ではなく「**その本の日に行が立ったか**」で数える待ちが要ります。
    """
    try:
        rows = [json.loads(x) for x in LAG.read_text(encoding="utf-8").splitlines()
                if x.strip()]
        return date.fromisoformat(max(r["last_day"] for r in rows))
    except Exception:                                          # noqa: BLE001
        return None


def _cv(xs: list[float]) -> float:
    """変動係数（ばらつき ÷ 平均）。単位の違うものを比べるので平均で割る。"""
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    if not m:
        return 0.0
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5 / m


def _day(s: str) -> date:
    return date.fromisoformat(str(s))


# ---------------------------------------------------------------- 条件の種類

def _k_length_spread(p: dict) -> Gauge:
    """尺のばらつき。**そろっていると、秒の軸と割合の軸が同じものになる。**"""
    scan = _last_scan()
    lens = [v["尺"] for v in scan.values()
            if v.get("尺") and v.get("views", 0) >= p.get("min_views", 1)]
    if len(lens) < 2:
        return Gauge(0, p["need"], "ばらつき", err="尺の読める本が2本ありません")
    return Gauge(_cv(lens), float(p["need"]), "ばらつき",
                 f"{len(lens)}本・{min(lens):.0f}〜{max(lens):.0f}秒")


def _k_published_count(p: dict) -> Gauge:
    """窓のなかに公開した本数。`data_ready: true` なら**実データの来た本だけ**。"""
    dates = _publish_dates()
    since, until = _day(p["since"]), (_day(p["until"]) if p.get("until") else None)
    last = analytics_last_day()
    if p.get("data_ready") and last is None:
        return Gauge(0, float(p["need"]), "本", err="実データの最終日が読めません")
    n = 0
    for d in dates.values():
        if d < since or (until and d > until):
            continue
        if p.get("data_ready") and last and d > last:
            continue
        n += 1
    note = f"{since}〜{until or '以降'}"
    if p.get("data_ready") and last:
        note += f" / 実データは {last} まで"
    return Gauge(n, float(p["need"]), "本", note)


def _k_scan_sum(p: dict) -> Gauge:
    """走査の最後の一枚で、条件に合う本の指標を合計する（再生・登録など）。"""
    scan = _last_scan()
    dates = _publish_dates()
    metric = p.get("metric", "views")
    since = _day(p["published_since"]) if p.get("published_since") else None
    total, n = 0.0, 0
    for vid, v in scan.items():
        length = v.get("尺") or 0
        if p.get("min_length") and length < p["min_length"]:
            continue
        if p.get("max_length") and length > p["max_length"]:
            continue
        if since and (vid not in dates or dates[vid] < since):
            continue
        total += float(v.get(metric, 0) or 0)
        n += 1
    return Gauge(total, float(p["need"]), p.get("unit", metric), f"{n}本の合計")


def _k_days_with_min_videos(p: dict) -> Gauge:
    """**「その本数で置いた日」が何日たまったか。** 若い日は数えない。"""
    counts: dict[date, int] = {}
    for d in _publish_dates().values():
        counts[d] = counts.get(d, 0) + 1
    today = datetime.now(JST).date()
    age = int(p.get("min_age_days", 0))
    days = [d for d, c in counts.items()
            if c >= int(p["per_day"]) and (today - d).days >= age]
    note = f"{len(days)}日（{int(p['per_day'])}本以上・公開から{age}日以上）"
    if days:
        note += f" 直近 {max(days)}"
    return Gauge(len(days), float(p["need"]), "日", note)


def _k_scored_pairs(p: dict) -> Gauge:
    """**点を付けた本のうち、実績と突き合わせられるもの。**

    `scripts/critique_record.py --check` の突き合わせを、外の口を叩かずに
    数えます（あちらは Analytics、こちらは走査の最後の一枚）。
    """
    if not CRITIQUE.exists():
        return Gauge(0, float(p["need"]), "本", err="critique.jsonl がありません")
    scan = _last_scan()
    topic_to_video = {r["topic"]: r["video_id"] for r in _uploaded()
                      if r.get("topic") and r.get("video_id")}
    seen: set[str] = set()
    for line in CRITIQUE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            key = json.loads(line).get("video", "")
        except ValueError:
            continue
        vid = key if key in scan else topic_to_video.get(key, "")
        if vid and scan.get(vid, {}).get("views", 0) >= p.get("min_views", 30):
            seen.add(vid)
    return Gauge(len(seen), float(p["need"]), "本",
                 f"{p.get('min_views', 30)}再生以上で突き合わせ可能")


KINDS = {
    "length_spread": _k_length_spread,
    "published_count": _k_published_count,
    "scan_sum": _k_scan_sum,
    "days_with_min_videos": _k_days_with_min_videos,
    "scored_pairs": _k_scored_pairs,
}


# ---------------------------------------------------------------- 読み・出し

def load(path: Path = CONFIG) -> list[Watch]:
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for row in doc.get("watches") or []:
        row = dict(row)
        out.append(Watch(
            id=row.pop("id"), what=row.pop("what"), cond=row.pop("cond"),
            then=row.pop("then"), source=row.pop("source"),
            kind=row.pop("kind"), answered=row.pop("answered", "") or "",
            params=row,
        ))
    return out


def exempt(path: Path = CONFIG) -> dict[str, str]:
    """**見張らない**と決めたファイルと、その理由（検査が読みます）。"""
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(doc.get("exempt") or {})


def _fmt(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".") if x % 1 else f"{x:,.0f}"


def render(watches: list[Watch] | None = None) -> str:
    """`status.py` が毎回出す節。**満ちたものを上に、大きく。**"""
    try:
        ws = watches if watches is not None else load()
    except Exception as exc:                                   # noqa: BLE001
        return f"\n=== 待ちの条件 ===\n  読めませんでした（続行）: {str(exc)[:90]}"

    lines = ["\n=== 待ちの条件（**満ちたらここに出ます。コメントに書くだけにしない**）==="]
    rung, waiting, done, broken = [], [], [], []
    for w in ws:
        g = w.gauge()
        if g.err:
            broken.append((w, g))
        elif g.met and not w.answered:
            rung.append((w, g))
        elif g.met:
            done.append((w, g))
        else:
            waiting.append((w, g))

    for w, g in rung:
        lines.append(f"  [!] **満ちました** {w.id} —— {w.what}")
        lines.append(f"      {w.cond}: いま **{_fmt(g.now)}{g.unit}**"
                     f"（要る {_fmt(g.need)}{g.unit}）"
                     + (f" / {g.note}" if g.note else ""))
        lines.append(f"      → **{w.then}**")
        lines.append(f"      答えが出たら `config/watches.yaml` の "
                     f"`{w.id}` に `answered:` を1行。**それまで毎回鳴ります。**")
    for w, g in waiting:
        lines.append(f"  あと **{_fmt(g.left)}{g.unit}**  {w.id}"
                     f"（いま {_fmt(g.now)} / 要る {_fmt(g.need)}）"
                     + (f"  {g.note}" if g.note else ""))
    for w, g in broken:
        lines.append(f"  [!] 読めません {w.id}: {g.err}")
    for w, _g in done:
        lines.append(f"  済 {w.id}: {w.answered}")
    if not ws:
        lines.append("  （ありません）")
    if rung:
        lines.append("  **満ちた待ちは、この回で判定すること。**"
                     "待ちは、書いた回と満ちる回が別なので、記憶では繋がりません。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
