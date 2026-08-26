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
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"
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


def ledger_deadline(watch_id: str) -> date | None:
    """`config/hypotheses.yaml` の `watch:` からその待ちの期限を引く。**正本はこちら。**

    待ちの `what:` に手で書いた「（期限 YYYY-MM-DD）」は、台帳の `deadline:` が
    動いた瞬間に古くなります。**実測（2026-08-26・3件とも本物）**:

        登録の依頼-30000再生      文面 2026-09-14  台帳 **2026-10-11**（27日）
        長尺-1000再生             文面 2026-09-15  台帳 **2026-11-22**（68日）
        族べつ登録率-15000再生     文面 2026-09-20  台帳 **2026-09-17**（−3日）

    `status.py` はずっと文面のほうを読んでいたので、**台帳ではまだ2か月 生きている
    前提を「期限に間に合いません」と印字していました。**

    これは「同じことを2か所が別々に言っていて、片方しか読まれていない」の型です
    （`scripts/retro.py` が「この形を探すのがいちばん当たる」と言っている型）。
    **消さずに、読む順を変えます** —— 台帳があればそちら、無ければ文面。

    **繋ぎは既にありました**（前提の側の `watch:`）。新しい欄を足していません ——
    足すと、その欄自体がまた片方だけ古くなります。
    """
    if not watch_id:
        return None
    try:
        import yaml

        doc = yaml.safe_load(HYPOTHESES.read_text(encoding="utf-8")) or {}
    except Exception:                                    # noqa: BLE001
        return None
    for h in doc.get("hypotheses") or []:
        if str(h.get("watch") or "") != watch_id:
            continue
        if h.get("closed_on"):
            return None
        raw = h.get("deadline")
        if isinstance(raw, date):
            return raw
        try:
            return date.fromisoformat(str(raw))
        except (TypeError, ValueError):
            return None
    return None


def deadline_of(watch: W.Watch) -> date | None:
    """待ちの期限。**台帳（前提の `watch:`）が正本で、文面は控え。**

    文面の形は2つ（`期限 2026-09-15` / `期限 09/05`）。
    """
    from_ledger = ledger_deadline(watch.id)
    if from_ledger is not None:
        return from_ledger
    text = f"{watch.what} {watch.cond}"
    m = re.search(r"期限\s*(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"期限\s*(\d{2})/(\d{2})", text)
    if m:
        return date(date.today().year, int(m[1]), int(m[2]))
    return None


@dataclass
class QueuePlan:
    """**予約の中に、その処置の本が何本あるか。** 走査の履歴ではなく控えから読む。

    `uploaded_since` で切る待ち（＝台本の作りを変えたときの窓）は、
    **処置の本がまだ1本も公開されていない間、走査の履歴からは何も出ません。**
    そこで履歴の伸びを外挿すると `0.00/日 → 届きません` になります ——
    **「まだ始まっていない」を「永久に届かない」と言う誤報**です。

    要る数はもう控えにあります（`data/uploaded.jsonl` の予約時刻）。
    **何本が期限までに公開されるか・そのうち何本が再生の付く枠に居るか**が分かれば、
    見込みの再生数と、**あと何本 足りないか**が出ます。
    """
    treated: int            # 処置の本（予約ぶんを含む）
    before_deadline: int    # 期限までに公開される本
    live: int               # そのうち再生が付く枠に居る本（`src/day_cap.py`）
    per_video: float        # 生きた枠の1本あたり再生（実測）
    est: float              # 期限までに積める見込み
    need: float
    started: bool           # 処置の本が1本でも公開済みか

    @property
    def short_videos(self) -> float:
        """あと何本ぶん（生きた枠で）足りないか。0以下なら足りている。"""
        if self.per_video <= 0:
            return 0.0
        return max(0.0, (self.need - self.est) / self.per_video)


def _treated_ids(watch: W.Watch) -> list[str]:
    """その待ちの処置に当たる動画ID（`uploaded_since` で切る）。"""
    raw = watch.params.get("uploaded_since")
    if not raw:
        return []
    cut = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return [v for v, u in W._uploaded_ats().items() if u >= cut]


def _per_video_views(watch: W.Watch) -> float:
    """**生きた枠に居る本の、1本あたり再生**（最後の走査の実測）。

    待ちの尺の条件（`min_length` / `max_length`）をそのまま当てます ——
    ショートを数える待ちに長尺の平均を掛けると、見込みが桁でずれます。
    """
    scan = W._last_scan()
    live = _live_ids()
    lo, hi = watch.params.get("min_length"), watch.params.get("max_length")
    vals = []
    for vid, v in scan.items():
        if live is not None and vid not in live:
            continue
        length = v.get("尺") or 0
        if lo and length < lo:
            continue
        if hi and length > hi:
            continue
        vals.append(float(v.get("views") or 0))
    return (sum(vals) / len(vals)) if vals else 0.0


def _live_ids() -> set[str] | None:
    """再生が付く枠の動画ID。読めなければ `None`（**絞らない**）。"""
    try:
        from src import day_cap
        from src.ab_split import published

        return day_cap.live_ids([r for r in published() if r.get("at")])
    except Exception:                                    # noqa: BLE001
        return None


def queue_plan(watch: W.Watch, deadline: date | None,
               today: date | None = None) -> QueuePlan | None:
    """`uploaded_since` の待ちについて、**控えから**見込みを出す（API 0単位）。"""
    ids = _treated_ids(watch)
    if not ids:
        return None
    pubs = W._publish_dates()
    days = {v: pubs[v] for v in ids if v in pubs}
    if not days:
        return None
    today = today or datetime.now(JST).date()
    live = _live_ids()
    before = [v for v, d in days.items() if deadline is None or d <= deadline]
    n_live = len([v for v in before if live is None or v in live])
    per = _per_video_views(watch)
    need = float(watch.params.get("need") or 0)
    return QueuePlan(
        treated=len(days), before_deadline=len(before), live=n_live,
        per_video=per, est=n_live * per, need=need,
        started=any(d <= today for d in days.values()),
    )


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
    # **`uploaded_since` にも同じ穴がありました**（2026-08-26 に測って足した）。
    #
    # あちらは「いつ公開されたか」で切るので、窓が未来なら上の1手で止まります。
    # こちらは**投稿時刻**で切る窓です —— 台本の作りを変えた瞬間から数え始めますが、
    # **その作りの本が公開されるのは、予約の順番待ちのぶんだけ後**です
    # （実測 2026-08-26: 依頼を入れたのは 08/24、いちばん早い公開は 08/26、
    #   いちばん遅い本は 10/05）。**その間、走査の伸びは定義として 0.00/日**で、
    # `status.py` は毎回「**届きません**」と印字していました。
    #
    # **1本も公開されていない待ちは、届かないのではなく、始まっていません。**
    # 判断に要る数は控え（`data/uploaded.jsonl`）に全部あるので、
    # ここでは判定を出さず、`queue_plan()` に見込みを言わせます。
    plan = queue_plan(watch, deadline_of(watch), today)
    if plan is not None and not plan.started:
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
        plan = queue_plan(w, f.deadline)
        if f.not_started:
            why = ("`published_since` が未来" if w.params.get("published_since")
                   else "処置の本が**まだ1本も公開されていません**（予約の順番待ち）")
            print(f"{head}  **数える窓がまだ来ていません**（{why}）"
                  + (f"（期限 {f.deadline}）" if f.deadline else ""))
            _print_plan(plan)
            continue
        if plan is not None and f.now <= 0:
            # **走査がまだ処置を1本も数えていないなら、伸びは処置について
            # 何も言っていません。** ここで「届きません」と印字すると、
            # 測っていないものについての判定になります（2026-08-26 に直した）。
            print(f"{head}  **走査の伸びからは出せません**"
                  f"（処置の本がまだ走査に入っていない。伸び {f.per_day:.2f}/日 は"
                  f"**処置の前の本の伸び**です）"
                  + (f"（期限 {f.deadline}）" if f.deadline else ""))
            _print_plan(plan)
            continue
        if f.fills_on is None:
            print(f"{head}  伸び {f.per_day:.2f}/日 → **届きません**"
                  + (f"（期限 {f.deadline}）" if f.deadline else ""))
            _print_plan(plan)
            continue
        mark = {True: "間に合う", False: "**期限に間に合いません**", None: "期限不明"}[f.in_time]
        print(f"{head}  伸び {f.per_day:.2f}/日 → 埋まるのは {f.fills_on}"
              + (f"（期限 {f.deadline}）" if f.deadline else "") + f" … {mark}")
        _print_plan(plan)


def _print_plan(plan: QueuePlan | None) -> None:  # pragma: no cover - 画面出力だけ
    """**「届きません」の下に、控えから読んだ数を並べる。**

    裸の「届きません」を出さないこと（`CLAUDE.md` の (イ) と同じ規則）。
    ここで言えるのは「何本 予約に在って、何本が生きた枠か」までで、
    **足りないぶんは本数で言います** —— そこが次の回の手になるからです。
    """
    if plan is None:
        return
    print(f"       予約の中の処置: {plan.treated}本 ／ 期限までに公開 {plan.before_deadline}本"
          f" ／ うち再生の付く枠 **{plan.live}本**"
          f"（1本あたり {plan.per_video:.0f}回・実測）")
    short = plan.short_videos
    if short <= 0:
        print(f"       → 見込み {plan.est:,.0f} / 要る {plan.need:,.0f} … **足りています**")
    else:
        print(f"       → 見込み **{plan.est:,.0f}** / 要る {plan.need:,.0f}"
              f" … **生きた枠で あと {short:.0f}本 足りません**"
              f"（死に枠の処置を入れ替えると縮みます: `python scripts/live_slots.py --plan --all`）")


if __name__ == "__main__":  # pragma: no cover
    main()
