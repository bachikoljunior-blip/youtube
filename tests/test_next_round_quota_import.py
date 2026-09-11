# -*- coding: utf-8 -*-
"""**`next_round` は、呼ばれ方に関係なく `quota.py` を読めること**（2026-09-12 06:1x・optimizer・Opus）。

**なぜ**: `respawn_rounds` だけが裸の `import quota` で、**`scripts/` が `sys.path` に
居る呼ばれ方でしか動きませんでした**。親は `python scripts/next_round.py` で撃つので
本番は通りますが、`import scripts.next_round` で読んだ側は `decide()` が
`ModuleNotFoundError` で落ちます（`decide` → `gap_over_gate` → `respawn_rounds`）。

**実測**: `tests/test_parent_round_gaps.py` は **同じ日に緑にも赤にもなります** ——
`scripts/` を `sys.path` に挿す別の検査が先に走った回だけ緑。
この回の 2度の全検査で、**片方だけが赤 1件**でした（＝ 赤の出どころは走る順）。
**赤が走る順で出る道具は、次の回に「直したのに赤い」と読まれます。**

**陽性対照**（この回に撃って落とした・`.pyc` を消してから・§5 教訓の形 6つ目）:
  - `_quota_mod()` を裸の `import quota` に戻すと 2件 とも落ちる
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mod_without_scripts_on_path():
    """**`scripts/` を `sys.path` から外して** `next_round.py` を読み込む。"""
    keep = [p for p in sys.path]
    drop = str(ROOT / "scripts")
    try:
        sys.path[:] = [p for p in sys.path if Path(p).resolve() != Path(drop).resolve()]
        sys.modules.pop("quota", None)
        spec = importlib.util.spec_from_file_location(
            "_nr_quota_import", ROOT / "scripts" / "next_round.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, list(sys.path)
    finally:
        sys.path[:] = keep


def test_scripts_が_sys_path_に無くても_quota_を読める():
    mod, path_at_load = _mod_without_scripts_on_path()
    assert str(ROOT / "scripts") not in path_at_load
    keep = list(sys.path)
    try:
        sys.path[:] = path_at_load
        sys.modules.pop("quota", None)
        got = mod._quota_mod()
    finally:
        sys.path[:] = keep
    assert hasattr(got, "round_marks"), "`quota.py` を読めていない"


def test_scripts_が_sys_path_に無くても_respawn_rounds_が答える():
    """`decide()` が通る道（`decide` → `gap_over_gate` → `respawn_rounds`）の当のもの。"""
    mod, path_at_load = _mod_without_scripts_on_path()
    keep = list(sys.path)
    try:
        sys.path[:] = path_at_load
        sys.modules.pop("quota", None)
        got = mod.respawn_rounds(last=3)
    finally:
        sys.path[:] = keep
    assert isinstance(got, list)
