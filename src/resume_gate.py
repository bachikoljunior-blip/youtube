"""**収益化の審査に受かる確率**を、この機械が読める形にする。

## なぜ要るか（2026-08-30・最適化の回が実測して足した）

`scripts/eta.py` は、止まっている間ずっと次を印字していました（自分の言葉で）。

    **固定してこの日付が出ています**: **収益化の審査に受かる確率を 1.0** に置いたまま
    …… **その項はまだこの機械に入っていません。**

**入っていないのは註ではなく、掛け算の項です。** 収益 ＝ 再生 ÷ 1000 × RPM は、
**審査に受かった世界でだけ**成り立ちます。受からなければ再生がいくつでも収入は 0 円
（`CLAUDE.md`「収益化されなければ、RPM がいくつでも収入はゼロです」）。
つまり `p_pass` は到達日に**掛かる**項で、腕（`per_video` / `rpm` / `density` /
`sub_rate`）はその内側にあります。**外側が 0 なら、内側を何倍にしても 0 です。**

### 実測（この回に自分で数えた・`data/runs.jsonl` 501行）

    08/26 → 08/30 の 4.1日で ship **359件**
    そのあいだ到達日は 2026-12-28 → 2027-01-10 ＝ **+13日 遠のいた**
    直近200件の種別: fix 145 ／ upload 34 ／ means 16 ／ **verdict 5**

`eta.py` 自身が「**軌跡の腕が動くのは前提を1件 閉じたときだけ**」と印字しているので、
**200件中 195件（97.5%）は、この機械の模型では到達日を動かせない種類**でした。
そして 08/30 の停止後は、**腕そのものが1つも引けません**（`src/pause_guard`）。
語彙に「引ける腕」しか無いので、停止中の回は `--lever none`（40件中 20件）へ落ちます。

**律速は腕ではなく、この門です。**

    腕を ∞ 倍にしても                到達日は動かない（生成が塞がっている）
    θ（前提が閉じる速さ）を ∞ にして  **-47日**（`eta.py` の実測）
    **`p_pass` を 0 → 1 にすると**    **「出ません」→ 有限**（＝ 上限なし）

## この模型が置いていること（**推測を数字で埋めないこと**）

**`p_pass` の値は、この機械からは測れません。** YouTube の審査に n 回 出して
何回 通ったかの実績が無いからです（0回）。だから**確率を捏造しません。**
代わりに、確率が 1.0 で**ない**ことだけを構造で言います。

    門が 6件 とも閉じている  → `p_pass` は「この機械の外」（審査の実物次第）
    1件でも開いている        → **`p_pass = 1.0` と置く根拠はどこにも無い**

**そして到達日は、門が閉じるまで始まりません** —— 停止中は本が1本も出ないので、
軌跡の 48日 は門が閉じた**後**から数え直しになります。これが床(d)です。

    (d) 門が閉じる日 ＋ 軌跡の日数

門が閉じる速さは、**閉じた実績からしか出しません**（`data/resume_gate.jsonl`）。
0件 閉じているうちは速さが測れないので、**0 とも ∞ とも書かず「測れていません」**と返します
（`docs/JOURNAL.md` 2026-08-30 の「覆る条件」4番:
 **測れないことを誤りゼロとして印字するのが、この仕掛けの最悪の壊れ方**）。

## 覆る条件

1. **`AUTOMATION_PAUSED.md` が消えたら、この module は黙ります**（`is_paused()` が偽）。
   停止が明けたのに門が縛り続ける形にしないこと
2. 門を 6件 閉じても審査に落ちたら、**この6件が十分条件でなかった**ということ。
   そのときは `AUTOMATION_PAUSED.md` の側を書き換える（ここは写しているだけ）
3. 条件の本文は**オーナーが push したファイルが正本**です。ここに書き写さないこと ——
   写した瞬間に、向こうを直しても効かなくなります
4. 閉じる速さが 3件 以上の実績で測れたら、`days_to_close()` の推定が立ちます。
   それまでは `None`（「測れていません」）を返し続けます
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAUSE_FILE = ROOT / "AUTOMATION_PAUSED.md"
LEDGER = ROOT / "data" / "resume_gate.jsonl"

#: 閉じた実績が何件たまれば「閉じる速さ」を口にしてよいか。
#: **1件で割ると、たまたま早かった1件が全部の予定になります。**
MIN_CLOSED_FOR_RATE = 3

_JST = timezone(timedelta(hours=9))


def is_paused() -> bool:
    return PAUSE_FILE.is_file()


def _pause_text() -> str:
    try:
        return PAUSE_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""


def paused_since(text: str | None = None) -> date | None:
    """`# AUTOMATION PAUSED — 2026-08-30` の日付。**見出しから読むこと。**

    ファイルの mtime は merge や clone で動くので使いません
    （この repo は worktree を毎回 作り直します）。
    """
    body = _pause_text() if text is None else text
    m = re.search(r"^#\s*AUTOMATION PAUSED\s*[—\-–]\s*(\d{4})-(\d{2})-(\d{2})", body, re.M)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def conditions(text: str | None = None) -> list[tuple[int, str]]:
    """`## Resume gate` の番号つき箇条書きを、そのまま返す。

    **本文をこの module に写さないこと**（覆る条件3）。オーナーが
    `AUTOMATION_PAUSED.md` を直したら、こちらは翌回から自動で追随します。
    """
    body = _pause_text() if text is None else text
    m = re.search(r"^##\s*Resume gate\s*$", body, re.M)
    if not m:
        return []
    tail = body[m.end():]
    nxt = re.search(r"^##\s", tail, re.M)
    block = tail[: nxt.start()] if nxt else tail
    out: list[tuple[int, str]] = []
    for ln in block.splitlines():
        mm = re.match(r"^\s*(\d+)\.\s+(.*\S)\s*$", ln)
        if mm:
            out.append((int(mm.group(1)), mm.group(2)))
    return out


#: **正本の側に付く「閉じた」の印。**（2026-08-30 に踏んで足した）
#:
#: 同じ日に2つの回が別々にここへ着きました。片方は `data/resume_gate.jsonl` に
#: 積み、もう片方は `AUTOMATION_PAUSED.md` の箇条書きに
#: **「← 2026-08-30 に閉じた」と直接 書き足しました。**
#: 合流した直後の実測 —— `eta.py` が
#:
#:     開いている 5件: **1** sensitive-topic AI persona を使わない
#:     **← 2026-08-30 に閉じた（下の「進捗」）** ／ …
#:
#: と印字しました。**同じ1行の中で「開いている」と「閉じた」を両方 言っています。**
#: 正本はオーナーが push したファイルなので、**そちらの印を勝たせます。**
_CLOSED_MARK = re.compile(r"←\s*[^／\n]*?閉じた|\*\*?closed\*\*?", re.I)


def _ledger_rows(path: Path | None = None) -> list[dict]:
    p = LEDGER if path is None else path
    if not p.is_file():
        return []
    rows = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows


def state(text: str | None = None, path: Path | None = None) -> list[dict]:
    """6件それぞれの、いまの姿。

    返すのは `{"n", "text", "closed", "closed_on", "evidence"}`。
    **台帳の最後の行が勝ちます**（追記だけで直せる形にするため）。
    **開き直しも書けます**（`state="open"` を後から積む）。
    """
    conds = conditions(text)
    last: dict[int, dict] = {}
    for r in _ledger_rows(path):
        try:
            n = int(r.get("n"))
        except (TypeError, ValueError):
            continue
        last[n] = r
    out = []
    for n, body in conds:
        r = last.get(n) or {}
        by_ledger = (r.get("state") == "closed")
        # **正本の印を勝たせる**（`_CLOSED_MARK` の註）。
        by_file = bool(_CLOSED_MARK.search(body))
        clean = _CLOSED_MARK.sub("", body).strip(" 　*")
        closed = by_ledger or by_file
        out.append({
            "n": n,
            "text": clean or body,
            "closed": closed,
            # **どちらが閉じたと言っているか。** 食い違いはここから読めます。
            "by_ledger": by_ledger,
            "by_file": by_file,
            # **正本が閉じたと言っているのに、根拠の1行が台帳に無い状態。**
            #     `AUTOMATION_PAUSED.md` は「次の全条件が**記録される**まで
            #     解除しない」と書いているので、これは未完了です。
            "unrecorded": by_file and not by_ledger,
            "closed_on": (r.get("at") or "")[:10] if by_ledger else None,
            "evidence": r.get("evidence") if by_ledger else None,
        })
    return out


def closed_count(text: str | None = None, path: Path | None = None) -> int:
    return sum(1 for r in state(text, path) if r["closed"])


def open_items(text: str | None = None, path: Path | None = None) -> list[dict]:
    return [r for r in state(text, path) if not r["closed"]]


def p_pass(text: str | None = None, path: Path | None = None) -> float | None:
    """**審査に受かる確率。値は返しません（`None`）。**

    返せる回は1つだけです —— 門が 6件 とも閉じていて、かつ実際に審査へ出して
    通った実績があるとき。**この機械にその実績は 0件** なので、いまは常に `None`。

    **`1.0` を返さないことが、この関数の仕事の全部です。**
    `eta.py` は長らく「受かる確率 1.0」を暗黙に置いて日付を出していました。
    """
    return None


def rate_per_day(text: str | None = None, path: Path | None = None,
                 today: date | None = None) -> float | None:
    """門が閉じる速さ（件/日）。**実績が薄い間は `None`。**"""
    rows = [r for r in state(text, path) if r["closed"] and r["closed_on"]]
    if len(rows) < MIN_CLOSED_FOR_RATE:
        return None
    start = paused_since(text)
    if start is None:
        return None
    day = today or datetime.now(_JST).date()
    span = (day - start).days
    if span <= 0:
        return None
    return len(rows) / span


def days_to_close(text: str | None = None, path: Path | None = None,
                  today: date | None = None) -> float | None:
    """門が全部 閉じるまでの日数。**測れなければ `None`**（0 ではありません）。"""
    rate = rate_per_day(text, path, today)
    if not rate:
        return None
    left = len(open_items(text, path))
    if left <= 0:
        return 0.0
    return left / rate


def cap(text: str | None = None, path: Path | None = None) -> float | None:
    """この腕の「天井までの倍率」。**`levers.LEVERS` に載せる条件**です。

    `src/levers.py` は「腕を増やすときは `eta.py` の側に **その腕を何倍にすれば
    いいか** が出ていること」と決めています。門の倍率は件数の比です。

        閉じた 0件 → 倍率は**定義できません**（0倍 では 6件 になりません）→ `None`
        閉じた k件 → **×(6/k)**
    """
    total = len(conditions(text))
    if not total:
        return None
    k = closed_count(text, path)
    if k <= 0:
        return None
    return total / k


def summary(text: str | None = None, path: Path | None = None,
            today: date | None = None) -> dict:
    """`eta.py` が印字に使う一式。**印字の文言はここに置かないこと。**"""
    conds = conditions(text)
    st = state(text, path)
    op = [r for r in st if not r["closed"]]
    return {
        "paused": is_paused(),
        "total": len(conds),
        "closed": len(st) - len(op),
        "open": len(op),
        "open_items": op,
        "since": paused_since(text),
        "p_pass": p_pass(text, path),
        "rate_per_day": rate_per_day(text, path, today),
        "days_to_close": days_to_close(text, path, today),
        "cap": cap(text, path),
        "min_closed_for_rate": MIN_CLOSED_FOR_RATE,
        # **正本が閉じたと言っているのに、根拠が台帳に無い件**（`state()` の註）。
        "unrecorded": [r for r in st if r.get("unrecorded")],
    }


def queue(path: Path | None = None, now: datetime | None = None) -> dict:
    """**停止しても、まだ公開され続ける本**を数える（API 0単位・実測 0.1秒）。

    ## なぜ門の隣に置くか（2026-08-30）

    `AUTOMATION_PAUSED.md` が止めたのは「**新しく作って足すこと**」で、
    **すでに YouTube 側へ入っている予約の列ではありません。**
    実測（`data/uploaded.jsonl` を `video_id` で重複排除・後の行が勝つ）:

        控えにある本            691本（`video_id` と `at` の両方を持つ行だけ。
                                 台帳の重複排除後は 735本 で、44本 は `at` を持たない
                                 —— **数えられないものを数えたことにしない**）
        **これから公開される     482本**（2026-08-30 11:00 〜 2026-10-09 23:00 JST）
        ペース                  **12.1本/日**

    **機械が1回も起きなくても公開されます。** その全部が、停止の理由になった
    旧 `persona` で作られています。つまり **`p_pass` は、こちらが何もしなくても
    毎日 下がりうる** —— 門は「開いている」だけでなく、**時計が回っています。**

    そして引っ込める道具（`reschedule.py`）は `src/pause_guard` の対象なので、
    **この機械からは止められません。** ここが出すのは数だけです。

    **覆る条件**: 予約が尽きる（`upcoming` が 0）か、停止が明けたら、この行は消えます。
    """
    p = (ROOT / "data" / "uploaded.jsonl") if path is None else path
    if not p.is_file():
        return {"held": 0, "upcoming": 0, "first": None, "last": None, "per_day": None}
    seen: dict[str, str] = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        vid, at = r.get("video_id"), r.get("at")
        if vid and at:
            seen[vid] = at  # **後の行が勝つ**（`retimed_at` で予定が動くため）
    ref = now or datetime.now(timezone.utc)
    future = []
    for at in seen.values():
        try:
            t = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if t > ref:
            future.append(t)
    future.sort()
    if not future:
        return {"held": len(seen), "upcoming": 0, "first": None, "last": None, "per_day": None}
    span = max((future[-1] - future[0]).days, 1)
    return {
        "held": len(seen),
        "upcoming": len(future),
        "first": future[0].astimezone(_JST),
        "last": future[-1].astimezone(_JST),
        "per_day": len(future) / span,
    }


def close(n: int, evidence: str, *, path: Path | None = None,
          at: datetime | None = None) -> dict:
    """門を1件 閉じる。**根拠の文が要ります**（空なら受け付けない）。

    閉じるのは「決めた」ではなく「**記録した**」ときです ——
    `AUTOMATION_PAUSED.md` が「次の全条件が**記録される**まで解除しない」と
    書いているので、根拠の所在（ファイル名・commit・実測）を必ず添えること。
    """
    if not evidence or not evidence.strip():
        raise ValueError("根拠の文が要ります（どこに何を記録したか）")
    valid = {num for num, _ in conditions()}
    if valid and n not in valid:
        raise ValueError(f"{n} は Resume gate の番号ではありません（{sorted(valid)}）")
    rec = {"at": (at or datetime.now(_JST)).isoformat(timespec="seconds"),
           "n": int(n), "state": "closed", "evidence": evidence.strip()}
    p = LEDGER if path is None else path
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
