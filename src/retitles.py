"""**題を差し替えた記録**（`data/retitled.jsonl`）と、控えの題への上書き。**API 0単位。**

## なぜ要るか（2026-09-05 00:2x に踏んだ。**同じ題を3つの回が追いかけた跡**）

`data/uploaded.jsonl` は「**上げたときに書いた行**」で、`title` はその時刻の字です。
`scripts/retitle.py` は YouTube の題を差し替えますが、**この帳面には1文字も書きません。**
＝ 題を直した瞬間から、帳面の `title` は**実物と違う字**になります。
帳面は追記専用（`.gitattributes` の `merge=union`）なので、**行を書き換える逃げ方は使えません**
（併合が両方の行を残し、同じ本が2つの題で並びます。実測: 同じ `video_id` の重なりが
すでに 85件 在ります）。

実測 —— `GFvAcxvDmYM`（09/05 09:00 JST の枠の本）::

    23:03:51  `retitle.py` が YouTube を差し替え（`videos.update` 50単位）
              → 実物 `【60歳以上の方へ】75歳までなら総額2052万円差 損が最小は69歳7か月`
    00:07     きょうだいが `data/scripts/<題材>.script.json` を追いつかせた
    00:2x     `data/uploaded.jsonl` だけ **古い題のまま**
              → `[次の枠]`（`src/next_slot.py`）が毎周いちばん上に古い題を刷っていた

**この字は、その回がいちばん先に読む1行です。** 3つの回（23:04・00:07・00:2x）が
同じ題を追いかけ、**どの回も帳面を見ていません** —— 帳面は「上げた記録」の顔をしているので、
古いことが症状として出ません（**外れていても もっともらしく見えます**）。

## 形

追記専用の別ファイルに1行 足し（`record()`）、読む側が**上から重ねます**（`overlay()`）。
帳面そのものは触りません ——「上げたときの字」は記録として正しいので、残します。

    {"at": ISO8601, "video_id": str, "title": <新しい題>, "prev": <前の題>}

## 覆る条件

- `data/uploaded.jsonl` が追記専用でなくなったら（`.gitattributes` から `merge=union` が
  外れたら）、行を書き換える手が使えるので、この重ねは要らなくなります。
- YouTube の metadata を毎周 引き直す道ができたら（`videos.list` は 1単位）、
  実物のほうが安いので、そちらを正本にしてここを落とすこと。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src import config

LEDGER = Path(config.ROOT) / "data" / "retitled.jsonl"


def _rows(path: Path | None = None) -> list[dict]:
    p = Path(path or LEDGER)
    if not p.exists():
        return []
    out: list[dict] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def record(video_id: str, title: str, *, prev: str | None = None,
           at: datetime | None = None, path: Path | None = None) -> dict:
    """**差し替えを1行 足す。**（追記のみ・API 0単位）返りは足した行。"""
    vid = str(video_id or "").strip()
    if not vid:
        raise ValueError("video_id が空です")
    row = {
        "at": (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
              .isoformat().replace("+00:00", "Z"),
        "video_id": vid,
        "title": str(title or ""),
        "prev": str(prev or ""),
    }
    p = Path(path or LEDGER)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def latest(path: Path | None = None) -> dict[str, str]:
    """`video_id → いまの題`。**同じ本が何度 差し替わっても、いちばん新しい `at` を採ります**
    （併合で並びが崩れるので、**最後の行 ＝ 最新 と読まないこと**）。"""
    best: dict[str, tuple[str, str]] = {}
    for r in _rows(path):
        vid = str(r.get("video_id") or "").strip()
        title = str(r.get("title") or "")
        if not vid or not title:
            continue
        at = str(r.get("at") or "")
        prev = best.get(vid)
        if prev is None or at >= prev[0]:
            best[vid] = (at, title)
    return {k: v[1] for k, v in best.items()}


def current_title(video_id: str, ledger_title: str | None = None,
                  *, path: Path | None = None) -> str:
    """**その本がいま名乗っている題。** 差し替えの記録が無ければ帳面の字をそのまま返します。"""
    return latest(path).get(str(video_id or "").strip(), str(ledger_title or ""))


def overlay(rows: list[dict], *, path: Path | None = None) -> list[dict]:
    """**帳面の行に、差し替え後の題を重ねて返す**（元の list は触りません）。

    重ねた行には `title_at_upload`（上げたときの字）を残します —— 題の形を
    測っている側が「上げたときの字」を要るときのためです。
    """
    now = latest(path)
    if not now:
        return rows
    out: list[dict] = []
    for r in rows:
        vid = str(r.get("video_id") or "").strip()
        new = now.get(vid)
        if new and new != str(r.get("title") or ""):
            r = dict(r)
            r["title_at_upload"] = r.get("title") or ""
            r["title"] = new
        out.append(r)
    return out
