#!/usr/bin/env python3
"""実メーターの%が、トークン何個ぶんなのかを出す。

    python scripts/token_probe.py           # 1時間ごとの記録（保険）
    python scripts/token_probe.py --solve   # J 側の記録と突き合わせて換算を出す

## なぜ要るか

**残量は%でしか見えないが、こちらが数えられるのはトークンしかない。**
換算が無いと「あと何回動けるか」が分からない。

## なぜ一度失敗したか

2026-08-08、過去の git 履歴から推定しようとして外した。
**私が0トークンの区間でも週%が増えていた**＝他のセッションが動いていたため。
オーナーの指摘どおり、**過去に遡っても分離できない。**

    05:36→05:38  週+2%   自分の出力 0
    08:01→09:03  週+3%   自分の出力 0

分離できるのは**動いているセッションが全部記録している時間帯だけ。**
**2026-08-08 23:00 JST から**、動くのは2つだけになった:

    このセッション（youtube）  … claude-opus-5    → ここ
    ELDRIA のセッション（J）   … claude-fable-5   → J の token-usage-log ブランチ

**23:00 は基準スナップショットなので、その時点の記録はまだ無い**（オーナー確認済み）。
最初の使える区間は 23:00〜00:00 で、00:00 に J 側へ書かれる。

## 突き合わせの考え方

**時計を合わせる必要はない。**
自分のトークンは `~/.claude/projects/**/*.jsonl` に時刻つきで残っているので、
**あとから任意の区間について数え直せる。** 実メーターも
`-chatgpt-usage-monitorPrivate` の git 履歴に毎時のコミットが残っている。

だから J 側の区切り（毎正時）をそのまま使い、その区間について
**自分のトークン**と**メーターの増分**を後から取りに行く。
こちらの記録の刻みを J に合わせにいく必要はない。

## 混ぜないこと

出力・入力・キャッシュ書き・キャッシュ読みは**別々に持つ。**
どれが%を動かしているかは分かっていない。
2026-08-06 に重み付き和を勝手に決めて外している。**重みは置かない。**

## **(c) わざと寝かせてある —— 外の repo が2つとも無い**（2026-09-01 に決めた）

**この道具は、いまのコンテナからは配線できません。** `retro.py` の
「どこからも撃たれていない道具」に **5周 続けて**載り、5回とも
(a) 配線する／(b) 消す の二択のまま持ち越されていました。**決めます。**

**両端が両方 無い**（この回に実際に撃って確かめた・API 0単位）:

    /workspace/-chatgpt-usage-monitorprivate   実メーター  → **ディレクトリが無い**
    /workspace/bachikoljunior-blip/j           J 側の記録  → **ディレクトリが無い**

    python scripts/token_probe.py --solve
    → 「J 側の記録がまだありません」「**両端にメーターの観測がありません。下限も出せません**」

    python scripts/token_probe.py
    → 「[!] 実メーターが読めません。**区間が繋がらなくなる。**」

**上の『突き合わせの考え方』が要求している条件が、もう成立していません** ——
あれは「**動いているセッションが全部記録している時間帯**」でしか分離できず、
その相手（ELDRIA の J・`claude-fable-5`）はここからは見えません。
`data/token_probe.jsonl` の最後の観測は **2026-08-08 20:29Z** で、
それ以後の行はメーターが `null` になります（この回に1行 出して、戻しました）。

**(b) 消さないのは、上の『なぜ一度失敗したか』が実測だからです** ——
「私が0トークンの区間でも週%が増えていた ＝ 過去に遡っても分離できない」。
**消すと、次に同じことを思いついた回が同じ2日を使い直します。**

**(a) 配線しないのは、撃っても `meter: null` の行が増えるだけだからです。**
`data/token_probe.jsonl` に「区間」として積まれますが、
**この回の実測では `since` が 23日 前で、印字は `HH:MM` しか出さないので
30分の区間に見えます。** 積むほど帳面が嘘になります。

**代わりに使うもの**: オーナーの画面の数字（`python scripts/quota.py --gauge <週%>
--at "MM/DD HH:MM"`。手順 §2 が毎周 名指ししています）。**%のまま使う**ので、
トークンへの換算は要りません。

**覆る条件**（起こすのはこの2つが**両方**戻ったとき。片方では足りません）:

1. `/workspace/-chatgpt-usage-monitorprivate` がこのコンテナから読めること
2. **同じ時間帯を全部 記録している相手**が、もう一度いること
   （1人しか記録していない区間は、上の実測どおり分離できません）

**そのときは `--solve` をそのまま撃てます。** 中身は直さなくて済むように残してあります。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "token_probe.jsonl"
METER = Path("/workspace/-chatgpt-usage-monitorprivate")
JREPO = Path("/workspace/bachikoljunior-blip/j")
JBRANCH = "origin/token-usage-log"
JLOG = "token_usage.md"
TRANSCRIPTS = Path.home() / ".claude" / "projects"

# **これより前の区間は使えない。** 他のセッションが動いていて分離できない。
EPOCH = datetime(2026, 8, 8, 23, 0, tzinfo=JST)

# 通しでこれだけ週%が動くまで、割り算の結果を出さない。
# 週%は整数なので両端の丸めで ±1 乗る。+15% なら誤差は約7%。
MIN_SPAN_PCT = 15

FIELDS = ("output_tokens", "input_tokens",
          "cache_creation_input_tokens", "cache_read_input_tokens")
# J 側の表の見出し → こちらの呼び名
JCOLS = ("input_tokens", "output_tokens",
         "cache_creation_input_tokens", "cache_read_input_tokens")


def _git(repo: Path, *args: str, timeout: int = 180) -> str:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


# ---------------------------------------------------------------- 実メーター

def meter_now() -> dict | None:
    """実メーターの最新値。**git pull してから読む。**

    `show-usage.mjs` は**表示するだけで取り直さない**（2026-08-08 に確認。
    「40 min old」と言うだけだった）。実際に更新しているのは
    `-chatgpt-usage-monitorPrivate` の GitHub Actions（毎時）で、
    **ローカルのクローンは pull しないと古いまま。**
    """
    _git(METER, "pull", "-q", "--ff-only")
    path = METER / "state" / "claude-usage.json"
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {"fetched_at": d.get("fetched_at"),
            "windows": {w["window_id"]: w["used_percent"]
                        for w in d.get("quota_windows", [])}}


def meter_history() -> list[tuple[datetime, dict]]:
    """メーターの過去の値を git 履歴から復元する（時刻順）。

    毎時コミットされているので、任意の時刻の**直近の観測**が取れる。
    """
    _git(METER, "pull", "-q", "--ff-only")
    log = _git(METER, "log", "--format=%H %cI", "--", "state/claude-usage.json")
    out = []
    for line in log.splitlines():
        sha, _, iso = line.partition(" ")
        if not sha:
            continue
        blob = _git(METER, "show", f"{sha}:state/claude-usage.json")
        if not blob:
            continue
        try:
            d = json.loads(blob)
            at = datetime.fromisoformat(
                (d.get("fetched_at") or iso).replace("Z", "+00:00"))
            out.append((at, {w["window_id"]: w["used_percent"]
                             for w in d.get("quota_windows", [])}))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def meter_at(history, when: datetime) -> tuple[datetime, dict] | None:
    """when の時点で最も近い観測。**前後1時間を超えたら使わない。**

    離れた観測で区間を切ると、増分が別の時間帯のものになる。
    """
    best = None
    for at, w in history:
        gap = abs((at - when).total_seconds())
        if gap <= 3600 and (best is None or gap < best[0]):
            best = (gap, at, w)
    return (best[1], best[2]) if best else None


# ------------------------------------------------------------ 自分のトークン

def my_tokens(since: datetime, until: datetime) -> dict:
    """since〜until に自分が使ったトークン。**モデル別・種類別に分ける。**"""
    per = defaultdict(lambda: defaultdict(int))
    replies = defaultdict(int)
    if not TRANSCRIPTS.exists():
        return {}
    for path in TRANSCRIPTS.rglob("*.jsonl"):
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = d.get("message") or {}
                    u, ts = msg.get("usage"), d.get("timestamp")
                    if not u or not ts:
                        continue
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if not (since <= t < until):
                        continue
                    model = msg.get("model") or "?"
                    replies[model] += 1
                    for k in FIELDS:
                        per[model][k] += u.get(k, 0) or 0
        except OSError:
            continue
    return {m: {**dict(v), "replies": replies[m]} for m, v in per.items()}


# --------------------------------------------------------------- J 側の記録

_JHEAD = re.compile(r"^##\s*(.+?)\s*〜\s*(.+?)\s*$")
_JROW = re.compile(r"^\|\s*([^|]+?)\s*\|" + r"\s*([\d,]+)\s*\|" * 4 + r"\s*$")


def _jtime(label: str) -> datetime | None:
    """「2026-08-08 23:00 JST」を時刻にする。"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", label.strip())
    if not m:
        return None
    y, mo, d, h, mi = (int(x) for x in m.groups())
    return datetime(y, mo, d, h, mi, tzinfo=JST)


def j_windows() -> list[dict]:
    """J の token_usage.md を読んで、区間ごとのトークンにする。

    **無くても落ちない。** 23:00 は基準スナップショットで、
    最初の記録が書かれるのは 00:00（オーナー確認済み）。
    """
    _git(JREPO, "fetch", "-q", "origin", "+refs/heads/*:refs/remotes/origin/*")
    text = _git(JREPO, "show", f"{JBRANCH}:{JLOG}")
    if not text:
        return []
    windows, cur = [], None
    for line in text.splitlines():
        head = _JHEAD.match(line)
        if head:
            start, end = _jtime(head.group(1)), _jtime(head.group(2))
            cur = {"start": start, "end": end, "models": {}}
            if start and end:
                windows.append(cur)
            continue
        row = _JROW.match(line)
        if row and cur is not None:
            name = row.group(1).strip()
            if name in ("モデル", "---") or name.startswith("("):
                continue
            vals = [int(row.group(i + 2).replace(",", "")) for i in range(4)]
            cur["models"][name] = dict(zip(JCOLS, vals))
    return [w for w in windows if w["start"] and w["end"]]


# ------------------------------------------------------------------ 記録する

def last_record() -> dict | None:
    if not OUT.exists():
        return None
    lines = [l for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    for line in reversed(lines):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def record() -> int:
    now = datetime.now(timezone.utc)
    prev = last_record()
    since = (datetime.fromisoformat(prev["at"].replace("Z", "+00:00"))
             if prev else now - timedelta(hours=1))

    m = meter_now()
    rec = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "meter": m, "mine": my_tokens(since, now)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"記録: {since:%m/%d %H:%M} → {now:%H:%M} UTC")
    if m:
        w = m["windows"]
        print(f"  実メーター（{m['fetched_at'][:16]}）: "
              f"週 {w.get('seven_day')}% / 5h {w.get('five_hour')}%")
    else:
        print("  [!] 実メーターが読めません。**区間が繋がらなくなる。**")
    for model, v in sorted(rec["mine"].items()):
        print(f"  {model}: {v['replies']}応答 / 出力 {v['output_tokens']:,}"
              f" / 入力 {v['input_tokens']:,}"
              f" / ｷｬｯｼｭ書 {v['cache_creation_input_tokens']:,}"
              f" / ｷｬｯｼｭ読 {v['cache_read_input_tokens']:,}")
    print("\n  換算を出すには --solve（J 側の記録と突き合わせる）")
    return 0


# ------------------------------------------------------------------ 換算する

def lower_bound() -> int:
    """**J が無くても言えること。** 自分のトークンだけで下限を出す。

    総使用 ＝ 自分 ＋ J なので、**自分だけで割ると必ず小さく出る**:

        %あたりのトークン = (自分 + J) / Δ%  ≧  自分 / Δ%

    つまりこれは**下限**。そして下限は**安全な向き**に外れる。
    %あたりのトークンを小さく見積もる ＝ 同じ作業量が食う%を**多めに**見る、
    ということなので、残量を使い切る側の事故が起きない。

    2026-08-06 に逆をやって外した。あのときの 47M/% は消費を**少なく**見せる
    向きで、残量を倍近く多く見ていた。**向きを取り違えないこと。**

    J の記録が来たら `solve()` が本物の値を出す。それまではこれを使う。
    """
    hist = meter_history()
    recs = []
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if len(recs) < 2:
        print("自分の記録がまだ2件ありません。")
        return 0

    # 記録の並びから、EPOCH 以降の連続した区間をつなぐ。
    start = None
    tot = {k: 0 for k in FIELDS}
    for r in recs:
        at = datetime.fromisoformat(r["at"].replace("Z", "+00:00"))
        if at.astimezone(JST) < EPOCH:
            continue
        if start is None:
            start = datetime.fromisoformat(r["since"].replace("Z", "+00:00"))
        for v in (r.get("mine") or {}).values():
            for k in FIELDS:
                tot[k] += v.get(k, 0) or 0
        end = at
    if start is None:
        print(f"{EPOCH:%m/%d %H:%M} JST 以降の記録がまだありません。")
        return 0

    a, b = meter_at(hist, start), meter_at(hist, end)
    if not (a and b):
        print("**両端にメーターの観測がありません。** 下限も出せません。")
        return 0
    d_week = b[1].get("seven_day", 0) - a[1].get("seven_day", 0)

    hours = (end - start).total_seconds() / 3600
    print(f"J 抜きの**下限**（{start.astimezone(JST):%m/%d %H:%M} 〜 "
          f"{end.astimezone(JST):%m/%d %H:%M} JST・{hours:.1f}時間）")
    print(f"  週 {a[1].get('seven_day')}% → {b[1].get('seven_day')}%  （+{d_week}）")
    if d_week < MIN_SPAN_PCT:
        print(f"  **まだ出しません。** +{d_week}% では丸め（±1）が効きすぎます"
              f"（+{MIN_SPAN_PCT}% から）。")
        return 0
    print("  総使用 = 自分 + J なので、自分だけで割った値は**必ず小さく出ます**。")
    print("  小さく出るのは**安全な向き**（同じ作業が食う%を多めに見る）。")
    for k in FIELDS:
        print(f"  {k:<30} ≧ {tot[k] / d_week:>14,.0f} /%")
    return 0


def solve() -> int:
    """J の区間ごとに、メーター増分と（自分＋J）のトークンを並べる。"""
    jw = j_windows()
    if not jw:
        print("J 側の記録がまだありません。")
        print(f"  {JREPO} の {JBRANCH}:{JLOG}")
        last = _git(JREPO, "log", "--format=%cI", "-1", JBRANCH).strip()
        if last:
            print(f"  ブランチの最終コミット: {last}")
        print()
        return lower_bound()

    hist = meter_history()
    print(f"J の区間 {len(jw)}件 / メーターの観測 {len(hist)}件\n")

    rows = []
    for w in jw:
        if w["start"] < EPOCH:
            continue                       # 分離できない時間帯は捨てる
        a, b = meter_at(hist, w["start"]), meter_at(hist, w["end"])
        mine = my_tokens(w["start"].astimezone(timezone.utc),
                         w["end"].astimezone(timezone.utc))
        tot = {k: 0 for k in FIELDS}
        for v in list(mine.values()) + list(w["models"].values()):
            for k in FIELDS:
                tot[k] += v.get(k, 0) or 0
        row = {"start": w["start"], "end": w["end"], "tokens": tot,
               "models": sorted(set(list(mine) + list(w["models"])))}
        if a and b:
            row["d_week"] = b[1].get("seven_day", 0) - a[1].get("seven_day", 0)
            row["d_5h"] = b[1].get("five_hour", 0) - a[1].get("five_hour", 0)
        rows.append(row)

    if not rows:
        print(f"{EPOCH:%m/%d %H:%M} JST 以降の区間がまだありません。")
        return 0

    print(f"{'区間':<14}{'週Δ':>5}{'5hΔ':>6}{'出力':>10}{'入力':>9}"
          f"{'ｷｬｯｼｭ書':>11}{'ｷｬｯｼｭ読':>13}")
    usable = []
    for r in rows:
        t = r["tokens"]
        dw = r.get("d_week")
        d5 = r.get("d_5h")
        mark = "" if dw is not None else "  ← メーター欠測"
        if d5 is not None and d5 < 0:
            mark = "  ← 5hの枠が更新された"     # 5時間枠は5時間ごとに0へ戻る
        cw = f"{dw:+d}" if dw is not None else "?"
        c5 = f"{d5:+d}" if d5 is not None else "?"
        print(f"{r['start']:%m/%d %H:%M}{cw:>6}{c5:>6}"
              f"{t['output_tokens']:>10,}{t['input_tokens']:>9,}"
              f"{t['cache_creation_input_tokens']:>11,}"
              f"{t['cache_read_input_tokens']:>13,}{mark}")
        if dw is not None and dw > 0:
            usable.append(r)

    print()
    # **1時間ごとに割り算してはいけない。**
    # 週%は整数なので、両端の丸めで増分に ±1 が乗る。1時間の増分は 2〜4% なので、
    # **1区間だけだと誤差が3割**。区間を5つ集めて平均しても、丸めは独立でないので
    # そこまで縮まらない。
    #
    # **長い1回の測定のほうが強い。** 端から端まで通しで測れば、
    # 丸めは全体で ±1 のまま。15%動いた span なら誤差は7%まで落ちる。
    # だから割り算は**通し**でやり、1時間ごとの表は見張り用に出すだけにする。
    span = [r for r in rows if r.get("d_week") is not None]
    print(f"メーターの取れた区間 {len(span)}件 / 増分の出た区間 {len(usable)}件")
    if not span:
        print("**メーターの観測が区間の端に無い。** 換算は出せません。")
        return 0

    # 連続していない区間が混ざると通しで測れないので、隣り合うものだけ繋ぐ。
    span.sort(key=lambda r: r["start"])
    runs: list[list[dict]] = [[span[0]]]
    for prev, r in zip(span, span[1:]):
        if r["start"] == prev["end"]:
            runs[-1].append(r)
        else:
            runs.append([r])            # 穴が空いたら別の通しにする
    best = max(runs, key=lambda run: run[-1]["end"] - run[0]["start"])

    hours = (best[-1]["end"] - best[0]["start"]).total_seconds() / 3600
    a = meter_at(hist, best[0]["start"])
    b = meter_at(hist, best[-1]["end"])
    if not (a and b):
        print("**通しの両端にメーターがありません。**")
        return 0
    d_week = b[1].get("seven_day", 0) - a[1].get("seven_day", 0)
    tot = {k: sum(r["tokens"][k] for r in best) for k in FIELDS}

    print(f"\n通しで測る: {best[0]['start']:%m/%d %H:%M} 〜 {best[-1]['end']:%m/%d %H:%M} JST"
          f"（{hours:.0f}時間・{len(best)}区間）")
    print(f"  週 {a[1].get('seven_day')}% → {b[1].get('seven_day')}%  （+{d_week}）")

    # **週の枠が更新されると%が戻る。** そこを跨ぐと増分が負になる。
    # 負の増分で割ると符号ごと間違えるので、跨いだ通しは捨てる。
    if d_week < 0:
        print(f"\n**この通しは週の枠の更新を跨いでいます**"
              f"（{a[1].get('seven_day')}% → {b[1].get('seven_day')}%）。使えません。")
        print("  更新後の区間がたまるのを待つこと。")
        return 0

    # 丸めの効く幅。**この幅の外は言わないこと。**
    if d_week < MIN_SPAN_PCT:
        print(f"\n**まだ換算を出しません。** 通しで +{d_week}% では、"
              "整数の丸め（±1）が結果を大きく動かします。")
        print(f"  +{MIN_SPAN_PCT}% 以上たまってから出すこと"
              f"（誤差が {100 / MIN_SPAN_PCT:.0f}% まで落ちる）。")
        return 0

    print(f"\n%あたりのトークン（種類ごと。**足し合わせない**）")
    print(f"  丸め ±1 を見込んだ幅で出す（+{d_week}% に対し ±1）")
    for k in FIELDS:
        lo, hi = tot[k] / (d_week + 1), tot[k] / max(d_week - 1, 1)
        print(f"  {k:<30} {tot[k] / d_week:>14,.0f}  （{lo:,.0f}〜{hi:,.0f}）")
    print("\n**どれが%を動かしているかは、まだ分からない。**")
    print("種類ごとに出しているのは、重み付き和を勝手に決めて一度外したから"
          "（2026-08-06）。**重みは置かない。**")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--solve", action="store_true",
                    help="J 側の記録と突き合わせて換算を出す")
    args = ap.parse_args()
    return solve() if args.solve else record()


if __name__ == "__main__":
    raise SystemExit(main())
