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

**順は `quota` が先**（06:3x に入れ替えた）。同じファイルは `quota` と `scripts.quota` の
**2つ の module object** になり、片方に当てた `monkeypatch` はもう片方に効きません ——
`scripts.quota` を先に返す形にしたら `tests/test_next_round_respawn_rounds.py` が **赤 1件**
（`quota.MODEL_CHOICE_FILE` を当てているのに、別の object を読む）。
＝ **落ち先を足すときは、いま在る呼び口と同じ object を返すことを先に確かめること。**

**陽性対照**（この回に撃って落とした・`.pyc` を消してから・§5 教訓の形 6つ目）:
  - `_quota_mod()` を裸の `import quota` **だけ**に戻すと 2件 とも落ちる
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


import contextlib


@contextlib.contextmanager
def _no_scripts_on_path():
    """**`scripts/` を `sys.path` から外し、`quota` を `sys.modules` から抜く。**

    **抜いたものは必ず戻すこと**（2026-09-12 06:4x）。`sys.modules["quota"]` を抜いたまま
    返すと、**次の検査の `import quota` が別の module object を作り**、その検査が
    `monkeypatch.setattr(quota, ...)` で当てていた分が黙って外れます
    （この回に実測: `tests/test_next_round_respawn_rounds.py` が **赤 1件**・
    単独では緑 ＝ §5 教訓の形 11つ目 を、この検査自身が作っていました）。
    """
    keep_path = list(sys.path)
    drop = Path(ROOT / "scripts").resolve()
    keep_mods = {n: sys.modules.get(n) for n in ("quota", "scripts.quota")}
    try:
        sys.path[:] = [p for p in sys.path if Path(p).resolve() != drop]
        for n in keep_mods:
            sys.modules.pop(n, None)
        yield list(sys.path)
    finally:
        sys.path[:] = keep_path
        for n, m in keep_mods.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m


def _load(path_at_load):
    spec = importlib.util.spec_from_file_location(
        "_nr_quota_import", ROOT / "scripts" / "next_round.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scripts_が_sys_path_に無くても_quota_を読める():
    with _no_scripts_on_path() as path_at_load:
        assert str(ROOT / "scripts") not in path_at_load
        got = _load(path_at_load)._quota_mod()
        assert hasattr(got, "round_marks"), "`quota.py` を読めていない"


def test_scripts_が_sys_path_に無くても_respawn_rounds_が答える():
    """`decide()` が通る道（`decide` → `gap_over_gate` → `respawn_rounds`）の当のもの。"""
    with _no_scripts_on_path() as path_at_load:
        got = _load(path_at_load).respawn_rounds(last=3)
    assert isinstance(got, list)


def test_この検査は_sys_modules_を_抜いたまま返さない():
    """**この検査自身が「走る順で色が変わる」を作らないこと**（§5 教訓の形 11つ目）。

    抜いたまま返すと、次の検査の `import quota` が**別の module object** を作り、
    その検査の `monkeypatch.setattr(quota, ...)` が黙って外れます
    （実測: `tests/test_next_round_respawn_rounds.py` が 赤 1件・単独では緑）。
    """
    import quota                                               # noqa: PLC0415
    before = sys.modules.get("quota")
    with _no_scripts_on_path():
        pass
    assert sys.modules.get("quota") is before is quota
