#!/usr/bin/env python3
"""statusLine フックとして走り、**サブスクの使用量を横取りして保存する。**

Claude Code は statusLine スクリプトの標準入力に、そのセッションの状態を
JSON で渡してくる。そこに **`/usage` と同じ値**が入っている。

    "rate_limits": {
      "five_hour": {"used_percentage": 23.5, "resets_at": 1738425600},
      "seven_day": {"used_percentage": 41.2, "resets_at": 1738857600}
    }

なぜ要るか。**使用量はこれまでオーナーに教えてもらうしかなかった。**
`scripts/usage.py` はセッション記録からトークンを数えて%に換算しているが、
**換算そのものが推測**で、実測点2つの幅が1.7倍ある（1% は 11M〜19M）。
2026-08-06 には換算のずれだけで自動実行を日次へ降格し、同日中に戻した。
**往復が無駄で、その間ずっと判断も鈍る。**

`A1` は「私側への指示をしてもいいが、必ず読むとは限らない」と言っている。
**教えてもらう前提の設計は、そこに反する。**

他の道は全部ふさがっていた（2026-08-08 に調べた）:

- `claude` に usage サブコマンドは無い。`auth status --json` にも入らない
- Admin API（`/v1/organizations/usage_report/...`）は**API従量課金ぶんだけ**で、
  そもそも個人アカウントでは Admin キーを作れない
- `/api/oauth/usage` は非公式。issue は not planned で閉じられ、429 が張り付く

**statusLine だけが公式仕様で、しかもオーナーの作業が要らない。**

## 制約

- **セッションが動いているあいだしか更新されない。** 最後に見た値が残る
- **最初の API 応答が返るまで出てこない。** 起動直後は空
- サブスク契約者のみ。各窓（5時間 / 7日）は独立に欠けることがある

だから `scripts/usage.py` の換算は**残す**。こちらが取れないときの予備。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
OUT = Path(__file__).resolve().parent.parent / "data" / "rate_limits.json"


def save(payload: dict) -> dict | None:
    """rate_limits があれば保存して返す。無ければ None。"""
    limits = payload.get("rate_limits")
    if not isinstance(limits, dict) or not limits:
        return None
    record = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rate_limits": limits,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # **上書きで持つ。** 履歴は要らない（欲しいのは「いまいくら使ったか」）。
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return record


def line(payload: dict, record: dict | None) -> str:
    """画面に出す1行。**取れなかったことも見えるようにする。**"""
    model = (payload.get("model") or {}).get("display_name", "?")
    if not record:
        return f"{model} | 使用量: まだ取れていません"
    parts = []
    for key, label in (("seven_day", "週"), ("five_hour", "5時間")):
        w = record["rate_limits"].get(key) or {}
        pct = w.get("used_percentage")
        if pct is None:
            continue
        left = ""
        if w.get("resets_at"):
            hrs = (datetime.fromtimestamp(w["resets_at"], JST) - datetime.now(JST)).total_seconds() / 3600
            left = f"／あと{hrs:.0f}h" if hrs > 0 else ""
        parts.append(f"{label} {pct:.1f}%{left}")
    return f"{model} | " + "  ".join(parts) if parts else f"{model} | 使用量: 窓が空"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("使用量: 入力を読めません")
        return 0
    try:
        record = save(payload)
    except Exception:
        record = None
    print(line(payload, record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
