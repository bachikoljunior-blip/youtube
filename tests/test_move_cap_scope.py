"""**`MOVE_CAP` が数えるのは「予約を動かした」回だけであること**（2026-08-28）。

同じ日の2周目に `note_quota_ok` を全部の書き込みの口へ足しました。**正しい直し**で、
そうしないと門（`reserve_hold`）は自分が通した単位の 2/3 を知りません。

**ところが `videos.update` を書く口は3つあり、意味が3つとも違います**:

    scripts/reschedule.py    公開時刻を動かす      ← `MOVE_CAP` はこれを数えたい
    scripts/link_longform.py 説明欄に導線を入れる  ← 予約は動いていない
    scripts/retitle.py       タイトルを直す        ← 予約は動いていない

`src.upload_cap.moves_in_window()` は `videos.update <vid>` で**終わる**行を数えます。
印を付けないと、**導線を入れただけで、その本の入れ替えの持ち手が 2回ぶん消えます** ——
`scripts/queue_lag.py` の「もう予約に在る本を入れ替えるだけで **33日** 早まる」は
その持ち手で撃つ手なので、**到達日に直接 掛かります。**

`unit_cost` は前方一致なので、印を付けても **50単位 のまま**です。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import upload_cap  # noqa: E402


def test_予約を動かさない書き込みには印が付いていること():
    """`videos.update` を書く口のうち、予約を動かさないものを名指しで見る。

    ここが落ちたら、`link_longform` か `retitle` の `detail` から
    末尾の印が消えています。**消すと `MOVE_CAP` が誤爆します。**
    """
    bad = []
    for name in ("scripts/link_longform.py", "scripts/retitle.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for line in text.splitlines():
            if "note_quota_ok(detail=" not in line or "videos.update" not in line:
                continue
            # 印 ＝ `{...}` のあとに1語ある
            if line.rstrip().rstrip('")').endswith("}"):
                bad.append(f"{name}: {line.strip()}")
    assert not bad, (
        "**予約を動かさない `videos.update` に印がありません**:\n  "
        + "\n  ".join(bad)
        + "\n\n`moves_in_window()` は `videos.update <vid>` で終わる行を"
          "「その本を動かした」と数えます。印が無いと、説明欄やタイトルを"
          "直しただけで `MOVE_CAP`（1本 2回/窓）の持ち手を奪います。")


def test_印を付けても値段は_50単位のまま():
    """`unit_cost` は前方一致。印は値段を変えません。"""
    assert upload_cap.unit_cost("videos.update abc123") == 50
    assert upload_cap.unit_cost("videos.update abc123 link") == 50
    assert upload_cap.unit_cost("videos.update abc123 retitle") == 50


def test_印の付いた行は_その本を動かした回に数えない(tmp_path, monkeypatch):
    """帳面を作って、実際に数え方を確かめる。

    `moves_in_window` は本物の repo を指しているあいだ、検査からは 0 を返します
    （`_write_path` の対。残骸で赤くならないため）。だから `_root()` を
    tmp へ差し替えます —— 差し替え先は `_REPO` と違うので、普通に数えます。
    """
    import json
    from datetime import timedelta

    monkeypatch.setattr(upload_cap, "_root", lambda: tmp_path)
    (tmp_path / "data").mkdir()
    mid = upload_cap.window_start() + timedelta(hours=1)
    rows = [
        {"at": (mid + timedelta(minutes=i)).isoformat(), "ok": True, "detail": d}
        for i, d in enumerate(("videos.update vidA",
                               "videos.update vidA link",
                               "videos.update vidA retitle"))
    ]
    (tmp_path / upload_cap.DAY_QUOTA_HITS).write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    assert upload_cap.moves_in_window("vidA") == 1, (
        "印の付いた行まで数えています —— 導線とタイトルで持ち手が消えます")
