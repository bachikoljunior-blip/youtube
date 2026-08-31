#!/usr/bin/env python3
"""公開済み動画の再生数を、公開からの経過時間つきで1行ずつ残す。

なぜ要るか。**「いつ伸びたか」を一度も記録していなかった。**

2026-08-06、m74wgCTi2n0 が 1245（公開12時間後）→ 1257（24時間後）で止まった。
バーストが一度きりなのは分かったが、**FSAN9tjIX10 が同じ形かを比べる基準が無い。**
公開13分後の0回が良いのか悪いのかも判断できない。総再生数だけ見ていると、
**当たり外れが決まる最初の数時間が丸ごと抜ける。**

律速は「1本あたりの当たり率」なので、そこが見えないのは致命的。
`status.py` から毎回自動で呼ぶ。人が思い出す前提にしない。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "data" / "views.jsonl"


def record(videos: list[dict]) -> int:
    """公開済み動画の現在値を追記する。追記した本数を返す。"""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    rows = []
    for v in videos:
        if v["status"]["privacyStatus"] != "public":
            continue
        published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        rows.append({
            "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "id": v["id"],
            "hours": round((now - published).total_seconds() / 3600, 2),
            "views": int(v["statistics"].get("viewCount", 0)),
            "likes": int(v["statistics"].get("likeCount", 0)),
        })
    with LOG.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def history(video_id: str) -> list[dict]:
    """1本の時系列を古い順に返す。"""
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("id") == video_id:
            out.append(d)
    return sorted(out, key=lambda d: d["hours"])


def print_curves(ids: list[str], titles: dict[str, str]) -> None:
    """公開から48時間以内の動画について、伸び方を並べる。

    **横に並べないと比べられない。** 1本ずつ見ていると「多いか少ないか」の
    感覚だけが残り、前の1本と比較できない。
    """
    rows = [(i, history(i)) for i in ids]
    rows = [(i, h) for i, h in rows if h and h[-1]["hours"] <= 48]
    if not rows:
        return
    print("\n=== 公開後の伸び方（48時間以内）===")
    for vid, h in sorted(rows, key=lambda r: r[1][-1]["hours"]):
        点 = "  ".join(f"{d['hours']:.0f}h:{d['views']}" for d in h[-6:])
        print(f"  {titles.get(vid, vid)[:26]:28s} {点}")


# --- **単体で撃てるようにする**（2026-08-27 に足した） ----------------------
#
# `config/hypotheses.yaml` の `needs[].refresh` は **`python scripts/snapshot.py`**
# と書いてありました（`scripts/deadline_check.py` が「判定できない前提」に対して
# **そのまま印字する**行です）。**このファイルには `__main__` がありませんでした** ——
# 撃っても**黙って何もせず終了コード0**を返し、次の回はもう1度
# 「読みが足りない」を見ます。**手順が名指ししている道具が、無いのと同じ**でした。
#
# `scripts/status.py` は同じことをしていますが、あれは Analytics も棚卸しも回すので
# **40〜60秒**かかります。ここは `videos.list` だけで、
# **571本 なら 12組 ＝ 12単位**（日枠は10,000単位）。
#
# **切り分けの日（`src/day_cap.booked_split_day()`）を読むのに要るのはこれだけ**です ——
# その日の最後の本が 齢 `MIN_AGE_H`（6時間）を過ぎた後に1回 撃てば、
# `day_cap.window()` が (A)/(B) を決めます。
def _ids_from_ledger() -> list[str]:
    """`data/uploaded.jsonl` の video_id（**Data API 0単位**）。"""
    led = LOG.parent / "uploaded.jsonl"
    if not led.exists():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for line in led.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            vid = str(json.loads(line).get("video_id") or "")
        except json.JSONDecodeError:
            continue
        if vid and vid not in seen:
            seen.add(vid)
            out.append(vid)
    return out


def main() -> int:
    import sys
    from pathlib import Path as _P

    sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
    from googleapiclient.discovery import build

    from src import auth

    ids = _ids_from_ledger()
    if not ids:
        print("[snapshot] `data/uploaded.jsonl` に video_id がありません")
        return 1
    youtube = build("youtube", "v3", credentials=auth.credentials())
    videos: list[dict] = []
    for i in range(0, len(ids), 50):
        try:
            videos += youtube.videos().list(
                part="snippet,status,statistics",
                id=",".join(ids[i:i + 50]),
            ).execute()["items"]
        except Exception as exc:                     # noqa: BLE001
            auth.note_day_quota(exc, "videos.list snapshot")
            print(f"[snapshot] {i // 50 + 1}組目が取れませんでした: {str(exc)[:90]}")
            break
    if not videos:
        print("[snapshot] 1本も読めませんでした（日枠は JST 16:00 に戻ります）")
        return 1
    n = record(videos)
    newest = max((json.loads(x)["at"] for x in
                  LOG.read_text(encoding="utf-8").splitlines() if x.strip()),
                 default="?")
    print(f"[snapshot] {n}本 積みました（{len(videos)}本 読んだ / いちばん新しい点 {newest}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
