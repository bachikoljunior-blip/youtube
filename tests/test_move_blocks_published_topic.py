"""**公開ずみの題材の本を、`--move` が枠へ入れないこと。**

## なぜ要るか（2026-09-05・最適化の回）

`dupes.blocking()` は同じことを見るが、**投稿（`upload_only.py`）の側**に立っている。
池から選ぶ道は**すでに上げてある本**を使うのでその門を通らず、`--move` が枠へ入れる
最後の1か所として素通りだった。実測 2026-09-05 05:11 `data/daily_pick.jsonl`:

    09/05 の1本 = OBJdXEr6gLg 「小規模企業共済を11か月でやめるといくらか #Shorts」
    09/06 の1本 = DtpnSVFDtAE （同じ題材）
    09/03 に公開 = 9zkfjEH48PY 「小規模企業共済を11か月でやめるといくらか #Shorts」

**2日つづけて、その日の唯一の枠が公開ずみと同じ字**だった。

**覆る条件**: 焼き直しが古い下書きを消すようになったら、池に兄弟は残らないので空振りになる。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load():
    spec = importlib.util.spec_from_file_location("_rs", ROOT / "scripts" / "reschedule.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_公開ずみの題材は枠へ入れない(monkeypatch):
    rs = _load()
    from src import daily_pick as dp

    up = {
        "draft1": {"video_id": "draft1", "topic": "s-t1", "title": "同じ題 #Shorts"},
        "pub1": {"video_id": "pub1", "topic": "s-t1", "title": "同じ題 #Shorts"},
        "draft2": {"video_id": "draft2", "topic": "s-t2", "title": "別の題 #Shorts"},
    }
    monkeypatch.setattr(dp, "_latest_uploaded", lambda *a, **k: up)
    monkeypatch.setattr(dp, "_observed_ids", lambda *a, **k: {"pub1"})
    # 規則1（1日1本）の側は空にして、この門だけを見る
    monkeypatch.setattr(rs, "_day_holders", lambda day, exclude=None: [])

    blocked = rs._rule_blocks_move("draft1", "2026-09-05T09:00")
    assert blocked, "**公開ずみの題材の兄弟が枠へ入れます**"
    assert "s-t1" in blocked[0] and "pub1" in blocked[0]

    assert rs._rule_blocks_move("draft2", "2026-09-05T09:00") == [], \
        "関係のない本まで止めています"


def test_控えが読めない回は止めない(monkeypatch):
    """門は増やすが、道は塞がない（読めない回は素通りさせる）。"""
    rs = _load()
    from src import daily_pick as dp

    def _boom(*a, **k):
        raise RuntimeError("控えが読めない")

    monkeypatch.setattr(dp, "_latest_uploaded", _boom)
    monkeypatch.setattr(rs, "_day_holders", lambda day, exclude=None: [])
    assert rs._rule_blocks_move("whatever", "2026-09-05T09:00") == []
