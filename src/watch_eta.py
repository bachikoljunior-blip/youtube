"""**その待ちは、期限までに埋まるのか。** 走査の履歴から埋まる日を出す。

## なぜ要るか（2026-08-23 に測って作った）

`config/watches.yaml` の待ちは「満ちたら鳴る」ので、**満ちない待ちは永久に黙ります。**
黙っている待ちと、埋まりようがない待ちが、**画面上でまったく同じに見えます。**

実測（2026-08-23）:

    長尺-1000再生   need 1000 ／ いま 17（直近28日の長尺の合計再生）
                    長尺の伸びは 1日あたり 0.6回 ＝ **埋まるのは 1,600日後**
                    期限は 2026-09-15。**70倍 足りない**

この待ちが守っている前提は「**長尺の登録率はショートより1桁以上高い**（律速の登録者は
長尺でしか動かない）」で、**門そのものに関わる判断**です。それが
「満ちるのを待つ」形で置かれているかぎり、**判定は永久に来ません。**

**放置できる設計にするなら、ここが要ります** —— 人が気づいて数えるのではなく、
機械が「この待ちは届きません」と毎回言うこと。

## どう出すか

走査（`data/scan.jsonl`）は一枚ごとに全本の指標を持っています。**同じ計器を
古い一枚で計算し直せば、その間の増え方が出ます。**（API は1単位も使いません）

    いま     最後の一枚で計った値
    前       `--days` 日前に最も近い一枚で計った値
    速さ     (いま − 前) ÷ 実際に空いた日数
    埋まる日  今日 ＋ (need − いま) ÷ 速さ     速さ ≤ 0 なら **届かない**

**`scan_sum` の待ちだけを出します。** `published_count` は予約表で決まるので
別の見方（`status.py` の予約一覧）で足り、混ぜると読み違えます。

## 覆る条件

- **走査が1日1枚も積まれない期間が続くと、速さは実際より遅く出ます**（分母は実日数）。
  走査が止まっているときは、この道具ではなく走査のほうを直すこと
- 長尺の配信を意図的に増やした回の直後は、**過去の速さが未来を過小に言います**。
  手を打った直後は `--days` を短くして測り直すこと
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src import watches as W

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "data" / "scan.jsonl"
JST = timezone(timedelta(hours=9))

#: 既定の測る幅。短すぎると雑音、長すぎると昔の運転が混ざる。
DEFAULT_DAYS = 14


def _lines() -> list[str]:
    return [l for l in SCAN.read_text(encoding="utf-8").splitlines() if l.strip()]


def _at(line: str) -> date:
    """走査の一枚が積まれた日（JST）。"""
    raw = json.loads(line).get("at") or json.loads(line).get("時刻") or ""
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(JST).date()


def pick_older(lines: list[str], days: int) -> tuple[str, date] | None:
    """`days` 日前に**最も近い**一枚。無ければ最古の一枚。1枚しか無ければ None。"""
    if len(lines) < 2:
        return None
    target = _at(lines[-1]) - timedelta(days=days)
    best, best_gap = None, None
    for line in lines[:-1]:
        d = _at(line)
        gap = abs((d - target).days)
        if best_gap is None or gap < best_gap:
            best, best_gap = (line, d), gap
    return best


def gauge_with(line: str, watch: W.Watch) -> W.Gauge:
    """**その一枚を「最後の一枚」に見立てて**計器を計算する（純関数・API 0単位）。"""
    rows = W._row_metrics(line)
    for mt in W.IMMUTABLE_METRICS:                      # 尺は動かないので今の一枚から補う
        if not any(mt in v for v in rows.values()):
            for vid, v in W._last_scan().items():
                if mt in v and vid in rows:
                    rows[vid].setdefault(mt, v[mt])
    real = W._last_scan
    W._last_scan = lambda: rows                          # type: ignore[assignment]
    try:
        return watch.gauge()
    finally:
        W._last_scan = real                              # type: ignore[assignment]


def deadline_of(watch: W.Watch) -> date | None:
    """待ちの文面から期限を拾う（`期限 2026-09-15` / `期限 09/05` の2形）。"""
    text = f"{watch.what} {watch.cond}"
    m = re.search(r"期限\s*(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"期限\s*(\d{2})/(\d{2})", text)
    if m:
        return date(date.today().year, int(m[1]), int(m[2]))
    return None


@dataclass
class Forecast:
    watch_id: str
    now: float
    need: float
    per_day: float
    fills_on: date | None      # None ＝ 届かない
    deadline: date | None
    not_started: bool = False  # 数える窓がまだ来ていない（**「届かない」ではない**）

    @property
    def in_time(self) -> bool | None:
        if self.not_started:
            return None
        if self.now >= self.need:
            return True
        if self.fills_on is None:
            return False
        if self.deadline is None:
            return None
        return self.fills_on <= self.deadline


def forecast(watch: W.Watch, days: int = DEFAULT_DAYS, today: date | None = None) -> Forecast | None:
    """`scan_sum` の待ちだけ。速さが出せなければ None。"""
    if watch.kind != "scan_sum":
        return None
    lines = _lines()
    older = pick_older(lines, days)
    now = watch.gauge()
    if older is None or now.err:
        return None
    today = today or _at(lines[-1])
    since = watch.params.get("published_since")
    if since and W._day(since) > (today or _at(lines[-1])):
        # **数える窓がまだ来ていない。** 0件を「伸びが0」と読むと、
        # 始まってすらいない待ちに「届きません」と出ます（**誤報**）。
        return Forecast(watch.id, now.now, now.need, 0.0, None,
                        deadline_of(watch), not_started=True)
    then = gauge_with(older[0], watch)
    span = max(1, (_at(lines[-1]) - older[1]).days)
    per_day = (now.now - then.now) / span
    fills = None
    if per_day > 0 and now.left > 0:
        fills = today + timedelta(days=int(now.left / per_day) + 1)
    elif now.left <= 0:
        fills = today
    return Forecast(watch.id, now.now, now.need, per_day, fills, deadline_of(watch))


def main() -> None:  # pragma: no cover - 画面出力だけ
    print("=== その待ちは期限までに埋まるか（走査の履歴から。**API 0単位**）===")
    # **`W.unanswered()` ではありません** —— あれは「満ちたのに答えていない待ち」で、
    # ここで見たいのは**まだ満ちていない待ち**（満ちない待ちほど黙っている）。
    for w in [x for x in W.load() if not x.answered]:
        f = forecast(w)
        if f is None:
            print(f"  −  {w.id}: `{w.kind}` は この道具の対象外（予約表で決まる待ち）")
            continue
        head = f"  {w.id}: {f.now:.0f} / {f.need:.0f}"
        if f.not_started:
            print(f"{head}  **数える窓がまだ来ていません**（`published_since` が未来）"
                  + (f"（期限 {f.deadline}）" if f.deadline else ""))
            continue
        if f.fills_on is None:
            print(f"{head}  伸び {f.per_day:.2f}/日 → **届きません**"
                  + (f"（期限 {f.deadline}）" if f.deadline else ""))
            continue
        mark = {True: "間に合う", False: "**期限に間に合いません**", None: "期限不明"}[f.in_time]
        print(f"{head}  伸び {f.per_day:.2f}/日 → 埋まるのは {f.fills_on}"
              + (f"（期限 {f.deadline}）" if f.deadline else "") + f" … {mark}")


if __name__ == "__main__":  # pragma: no cover
    main()
