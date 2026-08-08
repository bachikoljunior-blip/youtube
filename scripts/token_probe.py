#!/usr/bin/env python3
"""1時間ごとに「実メーターの%」と「自分の使用トークン」を並べて記録する。

    python scripts/token_probe.py

## なぜ要るか

**%あたりのトークン数を知りたいが、実メーターはアカウント全体の値**で、
どのセッションがどれだけ食ったかは分からない。

2026-08-08 に過去の git 履歴から推定しようとして失敗した。
**私が0トークンの区間でも週%が増えていた**＝他のセッションが動いていたため。
オーナーの指摘どおり、**過去に遡っても分離できない。**

分離できるのは**動いているセッションが全部記録している時間帯だけ。**
2026-08-08 23:00 から、動くのは2つだけになる:

    このセッション（youtube）  … claude-opus-5      → ここで記録
    ELDRIA のセッション（J）   … claude-fable-5     → J のリポジトリで記録

**2つ足せばアカウント全体になる。** 実メーターの増分と突き合わせれば、
%あたりのトークン数が出る。

## 記録するもの

モデルごとに、**出力・入力・キャッシュ書き込み・キャッシュ読み込みを分ける。**
どれが%を動かしているかは分かっていないので、**混ぜずに全部残す。**
（混ぜたせいで一度失敗している。8/6 に重み付き和を勝手に決めて外した。）
"""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "token_probe.jsonl"
METER = Path("/workspace/-chatgpt-usage-monitorprivate")
TRANSCRIPTS = Path.home() / ".claude" / "projects"

FIELDS = ("output_tokens", "input_tokens",
          "cache_creation_input_tokens", "cache_read_input_tokens")


def meter_now() -> dict | None:
    """実メーターの最新値。**git pull してから読む。**

    `show-usage.mjs` は**表示するだけで取り直さない**（2026-08-08 に確認。
    「40 min old」と言うだけだった）。実際に更新しているのは
    `-chatgpt-usage-monitorPrivate` の GitHub Actions（毎時）で、
    **ローカルのクローンは pull しないと古いまま。**
    古い値で区間を区切ると、増分が別の時間帯のものになる。
    """
    try:
        subprocess.run(["git", "-C", str(METER), "pull", "-q", "--ff-only"],
                       capture_output=True, text=True, timeout=180)
    except Exception:
        pass                                  # 取り直せなくても、あるものを読む
    path = METER / "state" / "claude-usage.json"
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {
        "fetched_at": d.get("fetched_at"),
        "windows": {w["window_id"]: w["used_percent"] for w in d.get("quota_windows", [])},
    }


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
                        per[model][k] += u.get(k, 0)
        except OSError:
            continue
    return {m: {**dict(v), "replies": replies[m]} for m, v in per.items()}


def last_record() -> dict | None:
    if not OUT.exists():
        return None
    lines = [l for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def main() -> int:
    now = datetime.now(timezone.utc)
    prev = last_record()
    since = (datetime.fromisoformat(prev["at"].replace("Z", "+00:00"))
             if prev else now - timedelta(hours=1))

    m = meter_now()
    rec = {
        "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meter": m,
        "mine": my_tokens(since, now),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"記録: {since:%m/%d %H:%M} → {now:%H:%M} UTC")
    if m:
        w = m["windows"]
        print(f"  実メーター（{m['fetched_at'][:16]}）: 週 {w.get('seven_day')}% / 5h {w.get('five_hour')}%")
        if prev and prev.get("meter"):
            pw = prev["meter"]["windows"]
            print(f"  前回からの増分: 週 +{w.get('seven_day',0) - pw.get('seven_day',0)}%"
                  f" / 5h {w.get('five_hour',0) - pw.get('five_hour',0):+d}%")
    else:
        print("  [!] 実メーターが読めません。**区間が繋がらなくなる。**")

    if not rec["mine"]:
        print("  自分の使用: なし")
    for model, v in sorted(rec["mine"].items()):
        print(f"  {model}: {v['replies']}応答"
              f" / 出力 {v['output_tokens']:,}"
              f" / 入力 {v['input_tokens']:,}"
              f" / ｷｬｯｼｭ書 {v['cache_creation_input_tokens']:,}"
              f" / ｷｬｯｼｭ読 {v['cache_read_input_tokens']:,}")
    print()
    print("  **J 側の記録と足してはじめてアカウント全体になる。**")
    print("  片方だけでは%との対応は出せない（2026-08-08 にそれで一度外した）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
