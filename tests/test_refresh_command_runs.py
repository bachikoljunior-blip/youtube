"""**`refresh:` に書いた行が、撃てる道具であること**（2026-08-27 に足した）。

`config/hypotheses.yaml` の `needs[].refresh` は、`scripts/deadline_check.py` が
「判定できない前提」の隣に**そのまま印字する行**です。次の回はそれを撃ちます。

実測 2026-08-27: `refresh: "python scripts/snapshot.py"` と書いてありましたが、
**`scripts/snapshot.py` に `__main__` がありませんでした** ——
撃つと**黙って何もせず、終了コード0**で返ります。次の回は
「撃ったのに読みが増えない」を見て、原因を道具のほうに探しに行きます。

**「無い道具」より、「在るように見えて何もしない道具」のほうが高くつきます。**
`docs/JOURNAL.md` の同じ形: `| tail` が終了コードを隠して「緑だったとも赤だったとも
言えない返りが、成功の顔をして来る」（2026-08-20 01:4x）。

**覆る条件**: `refresh` に `python -m src.x` や複合コマンドを書きたくなったら、
ここの読み方を足すこと（**書式を狭くするために在る検査ではありません**）。
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _refresh_commands() -> list[str]:
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    out: list[str] = []
    for h in doc["hypotheses"]:
        for need in h.get("needs") or []:
            cmd = str((need or {}).get("refresh") or "").strip()
            if cmd:
                out.append(cmd)
    return out


def test_refreshの指す道具が単体で撃てること():
    missing: list[str] = []
    for cmd in _refresh_commands():
        m = re.search(r"python\s+(scripts/[\w./-]+\.py)", cmd)
        if not m:
            continue                       # `-m` や複合コマンドは、いまは見ない
        path = ROOT / m.group(1)
        if not path.exists():
            missing.append(f"{cmd} → ファイルが在りません")
            continue
        src = path.read_text(encoding="utf-8")
        if "__main__" not in src:
            missing.append(f"{cmd} → `__main__` が無い ＝ **黙って何もしません**")
    assert not missing, "\n".join(missing)


def test_snapshotは控えからIDを読む():
    """**Data API 0単位でIDを揃えること**（`playlistItems` は日枠で落ちます）。"""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import snapshot

    ids = snapshot._ids_from_ledger()
    assert len(ids) > 100, f"控えから読めた video_id が {len(ids)}件"
    assert len(ids) == len(set(ids)), "同じIDを2度 数えています（控えは足すだけの帳面）"
