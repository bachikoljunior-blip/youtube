"""**帳面の「尽きた」と、Google の側の実物を、窓ごとに突き合わせる**（API 0単位）。

    python -m src.quota_refute            直近の窓を、越えた時刻・その後の読み書き・403 で並べる

## なぜ要るか（2026-09-03 05:5x に実測した）

`src/quota_ledger.py` の註は最初からこう言っています ——
「`units` は**公表の単価**であって、Google が実際に引いた数ではありません。
**符合するかは、尽きた時刻とこの帳面の累計を突き合わせて確かめること。**
ずれたら単価表のほうを直します」。**その突き合わせをする道具が無く、
`_ledger_hold` は帳面の数だけを 10,000 と比べて止めていました。**

窓 09/02 16:00 JST〜 の実物:

    帳面の通った単位が 10,000 を越えた時刻   **16:07 JST**（窓が開いて 7分・
                                              `videos.update` 131回 ＋ `search.list` 51回）
    その後に通った Data API の読み           **videos.list 680回・channels.list 61回**
                                              最後は 05:38 JST ＝ 越えてから **13.5時間**
    その後に試した書き込み                   **0回**（門が全部 止めた）
    この窓の 403 quotaExceeded              **0件**（`data/day_quota.jsonl`）

`upload_cap.RESERVE_UNITS` の註が実測で書いているとおり、**尽きた窓では読みのほうが
先に 403 を返します**（08/28 の 403 の出どころは 30回・16回・6回 とも読み）。
読みが 13時間 通り続けた窓は、Google の帳面では尽きていません。**帳面と実物が
5,600単位 以上 ずれています** —— どちらが正しいかは、この道具ではなく
**越えた後の書き込み 1回**が言います（403 は単位を使わないので、外した損は 1回ぶん）。

`search.list` の 429（`niche_ceiling.py`）は**数えません** —— あれは 403 ではなく、
同じ窓で `videos.list` が通っている以上、日枠の尽きではありません（別の枠）。

## 何を出すか（窓ごと）

    crossed_at    帳面の通った単位が `DAY_UNITS` に届いた時刻（届いていなければ None）
    reads_after   越えた後に通った読み（`*.list`）の回数と、最後の時刻
    writes_after  越えた後に**試した**書き込み（`*.list` 以外・`videos.insert` を除く）の
                  通った回数／落ちた回数
    hits_403      その窓で観測した 403 quotaExceeded の件数
    verdict       下の5つのどれか

    未達          帳面が枠に届いていない窓（突き合わせるものが無い）
    尽きた        403 を観測した（帳面と実物が一致・または帳面のほうが低い）
    帳面が外れ    越えた後に書き込みが**通った**（帳面のほうが高い ＝ 単価か枠が違う）
    読みだけ通る  越えた後に読みは通っているが、書き込みを1回も試していない（**判定できる材料が無い**）
    不明          越えた後の呼び出しそのものが無い

**`videos.insert` は別の枠から出ています**（`upload_cap.day_quota()` の註・実測 3度）。
書き込みの試行に数えると「通った」が嘘になります。

## 覆る条件

- `premise`「帳面の 10,000 は Google の枠ではない」（`config/hypotheses.yaml`）が閉じたら、
  当たりなら `quota_ledger.DAY_UNITS` か単価表を実測で直し、外れなら `_ledger_hold` は
  いまのままでよい。**どちらでも、この道具の表は残す**（次に単価が変わった日に同じ形で読む）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config, quota_ledger, upload_cap

#: 「越えた後の読みが通っている」と言うのに要る回数と時間（同じ分に束で通った読みを
#: 証拠にしないため —— 16:07 の `search.list` 33回 がそれ）
MIN_READS = 10
MIN_HOURS = 1.0

#: 書き込みの試行に数えない手（別の枠。`upload_cap.day_quota()` の註）
NOT_A_WRITE = ("videos.insert",)


def _read_jsonl(rel: str) -> list[dict]:
    path = Path(config.ROOT) / rel
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _ledger_rows() -> list[dict]:
    return _read_jsonl(quota_ledger.LEDGER)


def _hit_rows() -> list[dict]:
    return _read_jsonl(upload_cap.DAY_QUOTA_HITS)


def _is_write(method: str) -> bool:
    return not method.endswith(".list") and method not in NOT_A_WRITE


def windows(rows: list[dict] | None = None, hits: list[dict] | None = None,
            cap: int | None = None) -> list[dict]:
    """窓ごとの突き合わせ。古い順。**API 0単位。**"""
    cap = int(quota_ledger.DAY_UNITS if cap is None else cap)
    rows = _ledger_rows() if rows is None else rows
    hits = _hit_rows() if hits is None else hits
    by_window: dict[datetime, list[tuple[datetime, dict]]] = {}
    for r in rows:
        if str(r.get("api")) != "data":
            continue
        when = upload_cap._parse(r.get("at"))                  # noqa: SLF001
        if not when:
            continue
        by_window.setdefault(upload_cap.window_start(when), []).append((when, r))
    hits_by_window: dict[datetime, int] = {}
    for h in hits:
        if h.get("ok"):
            continue
        when = upload_cap._parse(h.get("at"))                  # noqa: SLF001
        if not when:
            continue
        key = upload_cap.window_start(when)
        hits_by_window[key] = hits_by_window.get(key, 0) + 1

    out: list[dict] = []
    for start in sorted(by_window):
        items = sorted(by_window[start], key=lambda t: t[0])
        used, crossed = 0, None
        reads_after, last_read = 0, None
        writes_ok, writes_failed, last_write = 0, 0, None
        for when, r in items:
            method = str(r.get("method") or "")
            ok = bool(r.get("ok"))
            if ok:
                used += int(r.get("units") or 0)
            if crossed is None:
                if used >= cap:
                    crossed = when
                continue
            if not _is_write(method):
                if ok:
                    reads_after += 1
                    last_read = when
                continue
            if ok:
                writes_ok += 1
            else:
                writes_failed += 1
            last_write = when
        hours = ((last_read - crossed).total_seconds() / 3600.0
                 if crossed and last_read else 0.0)
        n403 = hits_by_window.get(start, 0)
        if crossed is None:
            verdict = "未達"
        elif n403:
            verdict = "尽きた"
        elif writes_ok:
            verdict = "帳面が外れ"
        elif writes_failed:
            verdict = "不明"           # 落ちたが 403 ではない（別の理由）
        elif reads_after >= MIN_READS and hours >= MIN_HOURS:
            verdict = "読みだけ通る"
        else:
            verdict = "不明"
        out.append({
            "window_start": start, "used": used, "cap": cap,
            "crossed_at": crossed, "reads_after": reads_after,
            "last_read_at": last_read, "hours_after": hours,
            "writes_ok": writes_ok, "writes_failed": writes_failed,
            "last_write_at": last_write, "hits_403": n403,
            "verdict": verdict,
        })
    return out


def probed_windows(rows: list[dict] | None = None, hits: list[dict] | None = None) -> int:
    """**判定の材料がある窓の数** —— 帳面が枠を越え、その後に書き込みを試したか 403 を
    観測した窓。`config/hypotheses.yaml` の `count_expr` がこれを数えます。"""
    return sum(1 for w in windows(rows, hits)
               if w["crossed_at"] and (w["writes_ok"] or w["writes_failed"] or w["hits_403"]))


def _jst(when: datetime | None) -> str:
    if not when:
        return "—"
    return when.astimezone(upload_cap.JST).strftime("%m/%d %H:%M")


def render(rows: list[dict] | None = None, hits: list[dict] | None = None,
           last: int = 7) -> str:
    ws = windows(rows, hits)[-last:]
    lines = ["帳面の「尽きた」と実物の突き合わせ（窓 ＝ 16:00 JST〜・API 0単位）",
             "  窓         通った単位  越えた時刻   越えた後の読み            越えた後の書き込み  403  判定"]
    for w in ws:
        reads = (f"{w['reads_after']:>4}回 〜{_jst(w['last_read_at'])[6:]}"
                 f"（{w['hours_after']:.1f}h）" if w["crossed_at"] else "—")
        writes = (f"通 {w['writes_ok']} 落 {w['writes_failed']}" if w["crossed_at"] else "—")
        lines.append(f"  {_jst(w['window_start'])[:5]}      {w['used']:>7,}   "
                     f"{_jst(w['crossed_at'])[6:] if w['crossed_at'] else '   —  ':>6}      "
                     f"{reads:<24}  {writes:<16}  {w['hits_403']:>3}  {w['verdict']}")
    probed = probed_windows(rows, hits)
    lines.append(f"  判定の材料がある窓（越えた後に書き込みを試した・または 403）: **{probed}**")
    if ws and ws[-1]["verdict"] == "読みだけ通る":
        lines.append("  → いまの窓は**読みだけ通っています**。帳面が正しいか外れかは、"
                     "越えた後の書き込み 1回（`improve`・50単位）だけが言います"
                     "（403 は単位を使わない）。束では試さないこと。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    last = 7
    if "--last" in argv:
        try:
            last = int(argv[argv.index("--last") + 1])
        except (IndexError, ValueError):
            pass
    print(render(last=last))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
