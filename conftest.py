"""`live` の印を、集めるときに機械で付ける（2026-09-08 06:5x・optimizer・Opus）。

**どれが live かは `studio/livetests.py` が1か所で決めます**（理由と覆る条件はあちらの docstring）。
ここは印を付けるだけ。**検査ファイルの側には `pytestmark` を1行も書きません** ——
書く形にすると、14個目の検査を書いた回が忘れ、`pytest -m live` から黙って落ちます
（`test_script_yomi_ignored.py` が `test_studio_*` から落ちていたのと同じ形）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio import livetests  # noqa: E402


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    for item in items:
        try:
            path = Path(str(item.fspath))
        except Exception:  # noqa: BLE001 - 集めるのを止めないこと
            continue
        if livetests.is_live(path):
            item.add_marker("live")
