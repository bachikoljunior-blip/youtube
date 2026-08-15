#!/usr/bin/env python3
"""**使用量の計器。** CCR の MCP の返りに入っている枠情報を、時系列に積む。

## なぜ作り直したか（2026-08-14）

これまでの正本は `-chatgpt-usage-monitorPrivate` の `state/claude-usage.json` で、
あれは唯一「%」を返してくれる口だった。**もう死んでいる。**

- 8/11 から OAuth が切れて `reauthentication_required` しか返さない
- 8/12 09:39 JST から向こうの GitHub Actions ごと止まっている
- **直すにはオーナーがブラウザで認証し直すしかない。** A1 は「私側への指示を
  してもいいが、必ず読むとは限らない」と言っている。**人待ちの計器は計器ではない**

そのあいだ `docs/trigger_main.md` §2 は毎回 `add_repo` → Actions → clone を
踏ませていた。**3つとも失敗する経路に、毎回3〜4分と数千トークンを捨てていた。**

## 代わりに読むもの

**CCR の MCP の返りそのもの。** `list_sessions` / `get_session` /
`create_session` の `external_metadata` に、2種類の値が入っている。

    "rate_limit_info": {"rateLimitType":"seven_day",
                        "resetsAt":1786744800, "status":"rejected"}

    "usage": {"cache_read_tokens":767141, "cache_write_tokens":142437,
              "input_tokens":19, "output_tokens":3072}

`add_repo` も Actions も要らない。**遅れもない。**

## この計器が答えられること・答えられないこと

**答えられる。** いまどちらの枠が効いているか。警告帯に入っているか。
枠が閉じているか。いつリセットされるか。**判断に要るのはほぼこれで足りる。**

**答えられない。** 「残り何%か」。**返り値に%は入っていない。**
分母（何トークンで閉じるか）も返ってこない。

**だから積む。** `status` が切り替わった時刻と、そこまでに見えた消費量を
枠ごとに記録し続ければ、目盛りは後から決まる。**1点では決まらない。
積み始めなければ永久に決まらない。**

## 分かっている穴（読むときに割り引くこと）

- **`usage` は全部の行には入らない。** 8/14 の時点で、eta-loop の子と親には
  入っていて、youtube の子と cookie の子には入っていなかった。
  **規則は特定できていない。** だから消費量の合計は**必ず過小**で、
  この計器は「少なくともこれだけは使った」しか言わない。下限として読むこと
- **5時間枠と7日枠は別物。** 混ぜないこと。`rateLimitType` は
  「いま効いている（先に閉じそうな）ほうの枠」を指しているらしい
- **消費の時刻は、そのセッションが最後に動いた時刻で代表させている。**
  長く走ったセッションのぶんは、実際より後ろに寄る

## 使い方

    # MCP の返り（list_sessions か get_session）を保存してから食わせる
    python scripts/quota.py --ingest <file.json>
    python scripts/quota.py --ingest -        # 標準入力でもよい

    python scripts/quota.py                   # いまの姿を出す

**`--ingest` は MCP を叩けない。** シェルからは資格情報に届かないので、
呼び出し側（あなた）が `list_sessions` を叩いて、その返りをここに渡すこと。
`list_sessions` は1回で25件ぶん返す。**その25行がそのまま25点の時系列になる。**
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "quota.jsonl"

# 枠の長さ。`resetsAt` から逆算して「枠のどのへんにいるか」を出すのに使う。
WINDOW_SPAN = {"five_hour": timedelta(hours=5), "seven_day": timedelta(days=7)}

# **外から入る「%」の置き場**（2026-08-15）。
# `rate_limit_info` に % は入らないので、この計器だけでは「速すぎるか」を言えない。
# オーナーが手で測った値をここに積み、**誕生数で割って目盛りにする。**
USAGE_LOG = ROOT / "data" / "usage.jsonl"

# 週枠を均して使い切る速さ。**これが「速すぎる／遅すぎる」の基準線。**
WEEK_HOURS = 168.0
SUSTAIN_PCT_PER_HOUR = 100.0 / WEEK_HOURS      # ＝ 0.595 %/時

# 間隔の下限に置く上下の歯止め。**計器が壊れても鎖を止めない／暴走させない。**
FLOOR_MIN_CLAMP, FLOOR_MAX_CLAMP = 10.0, 90.0

# 弱いほうから順に。遷移の向きを判定するのに使う。
STATUS_ORDER = ["allowed", "allowed_warning", "rejected"]

STATUS_JA = {
    "allowed": "余裕あり",
    "allowed_warning": "**警告帯**",
    "rejected": "**閉じている**",
}


# --------------------------------------------------------------------------
# 取り込み
# --------------------------------------------------------------------------

def _iter_sessions(blob):
    """MCP の返りから、セッションの dict を1件ずつ取り出す。

    `list_sessions` は `{"ccr":{"data":[...]}}`、`get_session` と
    `create_session` は `{"ccr":{...}}`。**どちらも黙って受ける。**
    """
    if isinstance(blob, list):
        for item in blob:
            yield from _iter_sessions(item)
        return
    if not isinstance(blob, dict):
        return
    inner = blob.get("ccr", blob)
    if isinstance(inner, dict) and isinstance(inner.get("data"), list):
        for row in inner["data"]:
            if isinstance(row, dict):
                yield row
    elif isinstance(inner, dict) and inner.get("id"):
        yield inner


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _normalize(sess: dict):
    """セッション1件を、記録する形にする。読める情報が無ければ None。"""
    meta = sess.get("external_metadata") or {}
    rli = meta.get("rate_limit_info") or {}
    usage = meta.get("usage") or {}
    seen = _parse_iso(sess.get("updated_at"))
    if not seen:
        return None
    window = rli.get("rateLimitType")
    resets = rli.get("resetsAt")
    if not window and not usage:
        # 枠も消費量も無い行は、積んでも何も言わない。
        return None
    born = _parse_iso(sess.get("created_at"))
    row = {
        "seen_at": seen.astimezone(timezone.utc).isoformat(),
        "born_at": born.astimezone(timezone.utc).isoformat() if born else None,
        "session_id": sess.get("id"),
        "title": sess.get("title") or "",
        "tags": sess.get("tags") or [],
        "window": window,
        "status": rli.get("status"),
        "resets_at": (datetime.fromtimestamp(resets, timezone.utc).isoformat()
                      if isinstance(resets, (int, float)) else None),
    }
    if usage:
        row["tokens"] = {k: usage.get(k, 0) for k in
                         ("input_tokens", "output_tokens",
                          "cache_read_tokens", "cache_write_tokens")}
    return row


def _load() -> list[dict]:
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue                  # 壊れた行は捨てる。積むほうを止めない
    return out


def _key(row: dict):
    """同じ観測かどうかの鍵。**セッションと、その最終更新時刻。**

    同じセッションが後で `usage` を持って出てくることがある（消費量は
    あとから入る行がある）。そのときは**上書きして埋める**。
    """
    return (row.get("session_id"), row.get("seen_at"))


def _merge(old: dict, new: dict) -> dict:
    """同じ鍵の2行を1行にする。**情報が増える方向にだけ動かす。**"""
    merged = dict(old)
    for k, v in new.items():
        if v in (None, "", [], {}):
            continue
        merged[k] = v
    if old.get("tokens") and not new.get("tokens"):
        merged["tokens"] = old["tokens"]
    return merged


def ingest(text: str) -> tuple[int, int]:
    """MCP の返りを読んで `data/quota.jsonl` に足す。(新規, 更新) を返す。"""
    blob = None
    try:
        blob = json.loads(text)
    except Exception:
        # ツールの返りが前後に文字を連れてくることがある。JSON の塊を拾う。
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                blob = json.loads(m.group(0))
            except Exception:
                blob = None
    if blob is None:
        raise SystemExit("JSON として読めませんでした。MCP の返りをそのまま渡すこと。")

    table = {_key(r): r for r in _load()}
    added = updated = 0
    for sess in _iter_sessions(blob):
        row = _normalize(sess)
        if not row:
            continue
        k = _key(row)
        if k in table:
            before = json.dumps(table[k], sort_keys=True)
            table[k] = _merge(table[k], row)
            if json.dumps(table[k], sort_keys=True) != before:
                updated += 1
        else:
            table[k] = row
            added += 1

    rows = sorted(table.values(), key=lambda r: (r.get("seen_at") or ""))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    return added, updated


# --------------------------------------------------------------------------
# 読み出し
# --------------------------------------------------------------------------

def _periods(rows: list[dict]) -> dict:
    """`(枠, リセット時刻)` ごとにまとめる。**これが「枠1回ぶん」の単位。**"""
    out = {}
    for r in rows:
        if not r.get("window") or not r.get("resets_at"):
            continue
        out.setdefault((r["window"], r["resets_at"]), []).append(r)
    for v in out.values():
        v.sort(key=lambda r: r["seen_at"])
    return out


def _tokens_upto(rows: list[dict], start: datetime | None, until_iso: str):
    """枠の始まりから `until_iso` までに見えた消費量。

    `(出力, 総計, 消費量が読めなかった行数, 枠をまたぐので除いたセッション数)`。

    **枠に属するかは、その行自身の `window` ではなく時刻で決める**（2026-08-14）。
    `rate_limit_info` が付いていない行にも `usage` は入っていることがあり、
    枠で絞ると**そのぶんが丸ごと落ちる**。落ちれば合計はさらに過小になる。

    **セッションごとに最大値を採る。** 同じセッションが何度も出てくるが、
    `usage` は**そのセッションの通算値**なので、足すと二重に数える。

    同じ理由で、**枠の始まりより前に生まれたセッションは除く。**
    親セッションは 8/3 から生きていて 8,400万トークンを抱えている。
    これを1つの枠に押し込むと、枠の消費量が桁で狂う。
    除いたことは呼び出し側に返して、必ず表に出すこと。
    """
    best, blind, spanning = {}, 0, set()
    for r in rows:
        if r["seen_at"] > until_iso:
            continue
        if start and r["seen_at"] < start.isoformat():
            continue
        tok = r.get("tokens")
        if not tok:
            blind += 1
            continue
        sid = r.get("session_id")
        born = _parse_iso(r.get("born_at"))
        if start and born and born < start:
            spanning.add(sid)         # 枠をまたぐ。**どこまでが今回ぶんか分からない**
            continue
        total = sum(tok.values())
        if total > sum(best.get(sid, {}).values() or [0]):
            best[sid] = tok
    out_tok = sum(t.get("output_tokens", 0) for t in best.values())
    all_tok = sum(sum(t.values()) for t in best.values())
    return out_tok, all_tok, blind, len(spanning)


def _fmt_span(delta: timedelta) -> str:
    hrs = delta.total_seconds() / 3600
    if abs(hrs) >= 24:
        return f"{hrs / 24:.1f}日"
    if abs(hrs) >= 1:
        return f"{hrs:.0f}時間"
    return f"{hrs * 60:.0f}分"


# --------------------------------------------------------------------------
# 速さ（2026-08-15）
# --------------------------------------------------------------------------
# **なぜ要るか。** `rate_limit_info` は「閉じたか」しか言わない。閉じてから
# 気づくのでは遅い —— 8/12〜8/14 はそれで58時間止まった。**先に使い切ると、
# リセットまで1回も起きられない。** 読むのは残量ではなく「尽きる時刻」。
#
# **どう測るか。** %は外からしか入らない（`data/usage.jsonl`）。だが
# **誕生数はこちらで数えられる。** 1点でも%が入れば `% ÷ 誕生数` で
# 「1周いくら」が出て、そこから**持続できる間隔**が決まる。
#
# **穴**（読むときに割り引くこと）:
#   - 1周の重さは一定ではない。記録だけの回と、生成まで回した回が混ざる。
#     **出るのは平均**で、生成回だけを見れば1周はもっと高い
#   - `quota.jsonl` に積んでいない誕生は数に入らない。数え落とせば
#     「1周いくら」は**過大**に出て、間隔は**安全側（長め）**に振れる
#   - 他のループ（eta改善・クッキー）が混ざれば、その消費もこちらの
#     誕生数で割られる。**「ほぼこの作業だけ」と言える日の点だけを使うこと**


def _anchors() -> list[dict]:
    """外から入った「%」の点。新しい順。"""
    if not USAGE_LOG.exists():
        return []
    out = []
    for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("used_percent") is None or not row.get("fetched_at"):
            continue
        if row.get("window_id") != "seven_day":
            continue
        out.append(row)
    out.sort(key=lambda r: r.get("fetched_at") or "", reverse=True)
    return out


def _births_between(rows: list[dict], start: datetime, end: datetime) -> int:
    """`start`〜`end` に生まれたセッションの数。**セッションごとに1回だけ数える。**"""
    seen = {}
    for r in rows:
        sid, born = r.get("session_id"), _parse_iso(r.get("born_at"))
        if sid and born and sid not in seen:
            seen[sid] = born
    return sum(1 for b in seen.values() if start <= b <= end)


def pace(now: datetime | None = None) -> dict | None:
    """いまの速さと、持続できる1周の間隔。目盛りが無ければ None。"""
    now = now or datetime.now(timezone.utc)
    anchors = _anchors()
    if not anchors:
        return None
    a = anchors[0]
    resets = _parse_iso(a.get("resets_at_iso"))
    at = _parse_iso(a.get("fetched_at"))
    if not resets or not at:
        return None
    start = resets - WINDOW_SPAN["seven_day"]
    hours = (at - start).total_seconds() / 3600
    if hours <= 0:
        return None
    used = float(a["used_percent"])
    rows = _load()
    births = _births_between(rows, start, at)

    rate = used / hours                       # %/時（実測）
    per_lap = used / births if births else None
    floor = None
    if per_lap:
        floor = max(FLOOR_MIN_CLAMP,
                    min(FLOOR_MAX_CLAMP, per_lap / SUSTAIN_PCT_PER_HOUR * 60))
    exhaust = start + timedelta(hours=100.0 / rate) if rate > 0 else None
    return {
        "anchor_at": at, "anchor_used": used, "anchor_source": a.get("source", ""),
        "window_start": start, "window_reset": resets,
        "hours": hours, "births": births,
        "rate": rate, "per_lap": per_lap, "floor_min": floor,
        "exhaust_at": exhaust,
        "dead_hours": ((resets - exhaust).total_seconds() / 3600
                       if exhaust and exhaust < resets else 0.0),
        "over": rate / SUSTAIN_PCT_PER_HOUR - 1.0,
        "stale_hours": (now - at).total_seconds() / 3600,
    }


def recommended_floor_minutes(now: datetime | None = None) -> float | None:
    """次の子を立ててよくなるまでの、誕生から誕生までの最短間隔（分）。

    **`sibling_check.py` がこれを読んで §6 (f) を止める。**
    目盛りが無ければ None を返す —— **そのときは止めない。**
    測れないことを理由に鎖を止めるのは、8/12 の58時間と同じ損失になる。
    """
    p = pace(now)
    return p["floor_min"] if p else None


def pace_report(now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    p = pace(now)
    print("  **速さ**（尽きる時刻で読む。残量では読まない）")
    if not p:
        print("    **目盛りがありません。** `data/usage.jsonl` に %の点が要ります。")
        print("    `rate_limit_info` に % は入らないので、**外から入れるしかない**。")
        print("    形式: {\"fetched_at\":ISO,\"window_id\":\"seven_day\","
              "\"used_percent\":N,\"resets_at_iso\":ISO}")
        return
    print(f"    目盛り: {p['anchor_at'].astimezone(JST):%m/%d %H:%M} JST で "
          f"**{p['anchor_used']:.0f}%**"
          f"{'（' + p['anchor_source'] + '）' if p['anchor_source'] else ''}")
    if p["stale_hours"] > 24:
        print(f"    [!] **この目盛りは {p['stale_hours'] / 24:.1f}日前です。**"
              "新しい%が入るまで、下の数字は古い前提で動いています")
    print(f"    枠: {p['window_start'].astimezone(JST):%m/%d %H:%M} → "
          f"{p['window_reset'].astimezone(JST):%m/%d %H:%M} JST")
    print(f"    実測 {p['rate']:.3f} %/時   持続できる速さ "
          f"{SUSTAIN_PCT_PER_HOUR:.3f} %/時   → **{p['over']:+.0%}**")
    if p["births"]:
        print(f"    {p['hours']:.1f}時間で誕生 {p['births']} 件 "
              f"→ **1周 {p['per_lap']:.3f}%**")
        print(f"    持続できる間隔（誕生から誕生）: **{p['floor_min']:.0f}分**")
    else:
        print("    **誕生を1件も数えられていません。**`quota.jsonl` が薄すぎます")
    if p["exhaust_at"]:
        if p["dead_hours"] > 0:
            print(f"    このままなら 100% は "
                  f"{p['exhaust_at'].astimezone(JST):%m/%d %H:%M} JST"
                  f" → **リセットまで {p['dead_hours']:.0f}時間、鎖が止まります**")
        else:
            print(f"    このままならリセットまで届きます"
                  f"（100% 到達は {p['exhaust_at'].astimezone(JST):%m/%d %H:%M} JST）")


def report(now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    rows = _load()
    if not rows:
        print("  **まだ1点も積んでいません。** 使用量は見えていません。")
        print("  取り方: `list_sessions` を叩いて、返りを保存してから")
        print("          `python scripts/quota.py --ingest <file>`")
        print("  **空欄を「余裕がある」と読まないこと。**")
        return

    periods = _periods(rows)

    # --- いまの姿 -------------------------------------------------------
    live = [r for r in rows if r.get("status")]
    latest = max(live, key=lambda r: r["seen_at"]) if live else None
    if latest:
        seen = _parse_iso(latest["seen_at"])
        age = now - seen
        resets = _parse_iso(latest.get("resets_at"))
        print(f"  **いま効いている枠: {latest['window']} "
              f"／ {STATUS_JA.get(latest['status'], latest['status'])}**")
        if resets:
            left = resets - now
            if left.total_seconds() > 0:
                print(f"    リセットまで {_fmt_span(left)}"
                      f"（{resets.astimezone(JST):%m/%d %H:%M} JST）")
            else:
                print(f"    **この読みの枠はもうリセット済み**"
                      f"（{resets.astimezone(JST):%m/%d %H:%M} JST）。取り直すこと")
        print(f"    この読みは {_fmt_span(age)}前の観測"
              f"（{seen.astimezone(JST):%m/%d %H:%M} JST）")
        if age > timedelta(hours=2):
            print("    [!] **古い読みです。**`list_sessions` を叩いて取り直すこと")

    # --- 枠ごとの遷移 ---------------------------------------------------
    # **残量%が取れない以上、目盛りはここにしかない。**
    # 「いつ警告帯に入り、いつ閉じたか」を枠1回ぶんずつ残す。
    print("\n  **枠ごとの遷移**（%が取れないので、これが目盛りになる）")
    shown = 0
    for (window, resets_iso), items in sorted(
            periods.items(), key=lambda kv: kv[0][1], reverse=True):
        if shown >= 6:
            break
        shown += 1
        resets = _parse_iso(resets_iso)
        span = WINDOW_SPAN.get(window)
        start = resets - span if (resets and span) else None
        tail = "（進行中）" if resets and resets > now else ""
        print(f"    {window} → {resets.astimezone(JST):%m/%d %H:%M} JST{tail}")

        first_seen = {}
        for r in items:
            st = r.get("status")
            if st and st not in first_seen:
                first_seen[st] = r["seen_at"]
        if not first_seen:
            print("      （状態の読みなし）")
            continue
        for st in STATUS_ORDER:
            if st not in first_seen:
                continue
            at_iso = first_seen[st]
            at = _parse_iso(at_iso)
            frac = ""
            if start and span:
                pct = (at - start).total_seconds() / span.total_seconds() * 100
                frac = f" ／ 枠の {pct:.0f}% 経過時点"
            print(f"      {STATUS_JA.get(st, st)} 初出 "
                  f"{at.astimezone(JST):%m/%d %H:%M}{frac}")
            out_tok, all_tok, blind, spanning = _tokens_upto(rows, start, at_iso)
            if all_tok:
                note = []
                if blind:
                    note.append(f"{blind}行は消費量なし")
                if spanning:
                    note.append(f"{spanning}セッションは枠をまたぐので除外")
                tail = f"（{'／'.join(note)}）" if note else ""
                print(f"        そこまでに見えた消費: 出力 {out_tok:,} "
                      f"／ 総計 {all_tok:,}{tail}")

    # --- 目盛りが決まったか ---------------------------------------------
    closed = [(w, r) for (w, r), items in periods.items()
              if any(i.get("status") == "rejected" for i in items)]
    print()
    if closed:
        print(f"  **閉じた枠を {len(closed)} 回ぶん観測しています。**")
        print("    ここが増えるほど「どれだけ使うと閉じるか」の下限が絞れる。")
    else:
        print("  **まだ閉じた枠を観測していません。** 分母は不明のまま。")
        print("    `rejected` を1回でも捕まえるまで、目盛りは決まりません。")

    blind_rows = sum(1 for r in rows if not r.get("tokens"))
    print(f"  積んだ点: {len(rows)} 件"
          f"（うち消費量が入っていない行 {blind_rows} 件）")
    if blind_rows:
        print("    **`usage` は全部の行には入りません。**"
              "消費量の合計は必ず過小。下限として読むこと。")

    print()
    pace_report(now)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ingest", metavar="FILE",
                    help="MCP の返り（list_sessions / get_session）を読んで積む。- で標準入力")
    ap.add_argument("--pace", action="store_true",
                    help="速さだけを出す（§6 (f) の間隔を決めるとき）")
    args = ap.parse_args()

    if args.pace and not args.ingest:
        pace_report()
        return 0

    if args.ingest:
        text = (sys.stdin.read() if args.ingest == "-"
                else Path(args.ingest).read_text(encoding="utf-8"))
        added, updated = ingest(text)
        print(f"積みました: 新規 {added} 件 / 更新 {updated} 件 → {LOG}")
        print()

    report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
