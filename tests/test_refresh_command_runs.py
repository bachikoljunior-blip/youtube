"""**`refresh:` に、走らせても何も起きない命令を書かないこと。**（2026-08-27）

`config/hypotheses.yaml` の `needs.refresh` は、門（`scripts/deadline_check.py` →
`scripts/drift.py`）が**そのまま次の回に渡す命令**です。渡す以上、
**撃てば実際にそのデータが増えるもの**でなければ意味がありません。

**書いた30分後に踏みました。** 最初に書いたのは `python scripts/snapshot.py` ——
あれは `record()` を持つだけの**部品**で、`__main__` がありません。
直に走らせると **exit 0 で1行も書かずに終わります。**
`data/views.jsonl` へ実際に書くのは `scripts/status.py` の側です。

**門が「これを撃て」と言い、撃っても何も起きず、次の回がまた同じ行を読む** ——
この repo が何度も踏んでいる形（印字と、その印字が根拠にする所の食い違い）の、
いちばん安い版です。ここで縛ります。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _refresh_commands() -> list[tuple[str, str]]:
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    out = []
    for h in doc["hypotheses"]:
        if any(k in h for k in ("verdict", "closed_on", "outcome")):
            continue
        for n in h.get("needs") or []:
            cmd = str(n.get("refresh") or "").strip()
            if cmd:
                out.append((str(h.get("claim"))[:40], cmd))
    return out


def test_refresh_の指す入口が実在する():
    """`python scripts/x.py` なら `__main__` を、`python -m src.x` なら module を持つこと。"""
    bad = []
    for claim, cmd in _refresh_commands():
        m = re.match(r"python\s+(-m\s+)?(\S+)", cmd)
        if not m:
            bad.append((claim, cmd, "形が読めません"))
            continue
        as_module, target = bool(m.group(1)), m.group(2)
        path = (ROOT / (target.replace(".", "/") + ".py")) if as_module else (ROOT / target)
        if not path.exists():
            bad.append((claim, cmd, f"{path.name} が在りません"))
            continue
        src = path.read_text(encoding="utf-8")
        if not as_module and "__main__" not in src:
            # **部品を名指ししています。** 走らせても exit 0 で何も起きません。
            bad.append((claim, cmd, f"{path.name} に `__main__` が無い（部品です）"))
    assert not bad, f"撃っても何も起きない `refresh:`: {bad}"


def test_refresh_を書くのは_data_file_を書いた要件だけ():
    """**手の無い所に手を渡さないこと**（`refresh` は `data_file` の相棒）。"""
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    bad = []
    for h in doc["hypotheses"]:
        for n in h.get("needs") or []:
            if n.get("refresh") and not n.get("data_file"):
                bad.append(str(h.get("claim"))[:40])
    assert not bad, f"`data_file` なしで `refresh` を書いている前提: {bad}"
