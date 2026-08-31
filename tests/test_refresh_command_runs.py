"""**`refresh:` に、走らせても何も起きない命令を書かないこと。**（2026-08-27）

`config/hypotheses.yaml` の `needs[].refresh` は、門（`scripts/deadline_check.py` →
`scripts/drift.py`）が「判定できない前提」の隣に**そのまま印字する行**です。
次の回はそれを撃ちます。渡す以上、**撃てば実際にそのデータが増えるもの**でなければ
意味がありません。

**書いた30分後に踏みました。** 最初に書いたのは `python scripts/snapshot.py` ——
当時あれは `record()` を持つだけの**部品**で `__main__` が無く、
撃つと**黙って何もせず、終了コード0**で返りました。次の回は
「撃ったのに読みが増えない」を見て、原因を道具のほうに探しに行きます。

**「無い道具」より、「在るように見えて何もしない道具」のほうが高くつきます。**
`docs/JOURNAL.md` の同じ形: `| tail` が終了コードを隠して「緑だったとも赤だったとも
言えない返りが、成功の顔をして来る」（2026-08-20 01:4x）。

**この検査は、同じ周の2つの回が別々に書きました**（最適化のサブと主実行のサブ）。
合流させたのがこのファイルです —— **どちらの見方も落としていません。**

**覆る条件**: `refresh` に複合コマンド（`&&` でつなぐ等）を書きたくなったら、
ここの読み方を足すこと。**書式を狭くするために在る検査ではありません。**
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _refresh_commands() -> list[tuple[str, str]]:
    """（前提の claim, `refresh` の行）。**開いた前提だけ**を見ます。"""
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []
    for h in doc["hypotheses"]:
        if any(k in h for k in ("verdict", "closed_on", "outcome")):
            continue
        for need in h.get("needs") or []:
            cmd = str((need or {}).get("refresh") or "").strip()
            if cmd:
                out.append((str(h.get("claim"))[:40], cmd))
    return out


def test_refreshの指す道具が単体で撃てること():
    """`python scripts/x.py` なら `__main__` を、`python -m src.x` なら module を持つこと。"""
    bad: list[str] = []
    for claim, cmd in _refresh_commands():
        m = re.match(r"python\s+(-m\s+)?(\S+)", cmd)
        if not m:
            bad.append(f"{claim}: {cmd} → 形が読めません")
            continue
        as_module, target = bool(m.group(1)), m.group(2)
        path = (ROOT / (target.replace(".", "/") + ".py")) if as_module else (ROOT / target)
        if not path.exists():
            bad.append(f"{claim}: {cmd} → ファイルが在りません")
            continue
        src = path.read_text(encoding="utf-8")
        if not as_module and "__main__" not in src:
            # **部品を名指ししています。** 走らせても exit 0 で何も起きません。
            bad.append(f"{claim}: {cmd} → `__main__` が無い ＝ **黙って何もしません**")
    assert not bad, "\n".join(bad)


def test_refresh_を書くのは_data_file_を書いた要件だけ():
    """**手の無い所に手を渡さないこと**（`refresh` は `data_file` の相棒）。"""
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    bad = []
    for h in doc["hypotheses"]:
        for n in h.get("needs") or []:
            if n.get("refresh") and not n.get("data_file"):
                bad.append(str(h.get("claim"))[:40])
    assert not bad, f"`data_file` なしで `refresh` を書いている前提: {bad}"


def test_snapshotは控えからIDを読む():
    """**Data API 0単位でIDを揃えること**（`playlistItems` は日枠で落ちます）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import snapshot

    ids = snapshot._ids_from_ledger()
    assert len(ids) > 100, f"控えから読めた video_id が {len(ids)}件"
    assert len(ids) == len(set(ids)), "同じIDを2度 数えています（控えは足すだけの帳面）"
