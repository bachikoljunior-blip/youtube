"""**焼き直しの兄弟が公開されたら、残った下書きは池から外れること。**

## なぜ要るか（2026-09-05・最適化の回）

規則3 の焼き直しは同じ題材の下書きを池に置いていきます（消さない・規則の4）。
そのうち1本が公開されると、**残りは二度と出せません** —— 出せば同じ題が2本 並びます。
実測 2026-09-05 05:11: `data/daily_pick.jsonl` の「09/05 の1本」は
`OBJdXEr6gLg`（09-02 の下書き）で、その焼き直し `9zkfjEH48PY` は **09/03 に公開ずみ**、
**題は1文字も違いませんでした**。規則は1日1本なので、その日の取り分は 0 になります。

**覆る条件**: 焼き直しが古い下書きを消すようになったら、池に兄弟は残らないので不要。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import daily_pick as dp  # noqa: E402


def _write(p: Path, rows: list[dict]) -> Path:
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_公開ずみの題材の兄弟は池に出ない(tmp_path):
    up = _write(tmp_path / "uploaded.jsonl", [
        # 焼き直しの元（下書き・予約なし・観測なし）
        {"video_id": "draft1", "topic": "s-t1", "title": "同じ題 #Shorts",
         "at": None, "uploaded_at": "2026-09-02T11:37:00+00:00", "duration_s": 26.0},
        # その焼き直し。**公開ずみ**（控えに観測が在る）
        {"video_id": "pub1", "topic": "s-t1", "title": "同じ題 #Shorts",
         "at": "2026-09-03T00:00:00Z", "uploaded_at": "2026-09-02T15:09:00+00:00",
         "duration_s": 26.0},
        # 別の題材の下書き。**これは残ること**
        {"video_id": "draft2", "topic": "s-t2", "title": "別の題 #Shorts",
         "at": None, "uploaded_at": "2026-09-02T12:00:00+00:00", "duration_s": 27.0},
    ])
    views = _write(tmp_path / "views.jsonl", [
        {"at": "2026-09-04T00:00:00Z", "id": "pub1", "hours": 24.0, "views": 60},
    ])

    assert dp.published_topics(uploaded_path=up, views_path=views) == {"s-t1"}

    got = dp.pool_candidates("ショート", fams=[], uploaded_path=up, rows=[],
                             by_id={}, known=set(), views_path=views)
    ids = {r["video_id"] for r in got}
    assert "draft1" not in ids, "**公開ずみの題材の兄弟が池に残っています**"
    assert "draft2" in ids, "関係のない下書きまで落としています"
