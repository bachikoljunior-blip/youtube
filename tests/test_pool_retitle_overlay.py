"""池の一覧が、**差し替え後の題**を出すこと。

## なぜ要るか（2026-09-05 03:3x〜03:4x JST に、100単位 を払って踏んだ）

`data/uploaded.jsonl` は「**上げたときの行**」で、`scripts/retitle.py` が実物の題を
差し替えても 1文字も変わりません。差し替えは `data/retitled.jsonl` に在り、
`src/retitles.overlay()` が重ねます。`src/next_slot.py` は 09-05 00:2x にそれを
入れましたが、**池の一覧（`daily_pick.pool_candidates`）と齢そろえの行（`aged_views`）は
素の帳面のまま**でした —— そして池の一覧は「**次の枠の1本を選ぶ画面**」です。

実測::

    marker が刷った字  小規模企業共済 1か月で59万7200円動く #Shorts
    実物              【小規模企業共済】11か月と12か月でいくら違う？ #Shorts

刷られた字に `【】` が無かったので、その回は「いちばん厚い升で空いている特徴は
`【】`（×5.52・n=55対77）」と読んで `retitle.py` を撃ちました。**実物にはもう在り**、
しかも実物は `【】` の中で ×11.29 の「いくら」と ×1.95 の疑問形も持っていました
＝ **改善のつもりで、測れる範囲では劣る題へ差し替えた**（戻すのにもう1回）。
払ったのは `videos.update` ×2 ＝ **100単位**。

**覆る条件**: `daily_pick._latest_uploaded()` 自身が差し替えを取り込むようになったら、
この検査は「重ねが二重でないこと」だけを見る形へ書き直すこと（**先に消さないこと**）。
"""
from __future__ import annotations

import json
from pathlib import Path

from src import daily_pick, retitles


def _write(p: Path, rows: list[dict]) -> Path:
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    return p


def _pool(tmp_path, up):
    views = tmp_path / "views.jsonl"
    views.write_text("", encoding="utf-8")
    return daily_pick.pool_candidates(form="ショート", uploaded_path=up, rows=[],
                           views_path=views, fams=[])


def test_池の一覧は差し替え後の題を出す(tmp_path, monkeypatch):
    up = _write(tmp_path / "uploaded.jsonl", [
        {"video_id": "VID1", "topic": "s-x", "title": "上げたときの字 #Shorts",
         "at": None, "uploaded_at": "2026-08-19T00:00:00+00:00",
         "retimed_at": "2026-09-02T00:00:00+00:00"},
    ])
    ret = _write(tmp_path / "retitled.jsonl", [
        {"at": "2026-09-05T00:20:00+09:00", "video_id": "VID1",
         "title": "【差し替え後】いくら違う？ #Shorts", "prev": "上げたときの字 #Shorts"},
    ])
    monkeypatch.setattr(retitles, "LEDGER", ret, raising=False)

    got = [r for r in _pool(tmp_path, up) if r["video_id"] == "VID1"]
    assert got, "池に居るはずの本が落ちています"
    assert got[0]["title"] == "【差し替え後】いくら違う？ #Shorts", (
        "池の一覧が**上げたときの字**を出しています —— "
        "その字を根拠に題を触ると、もう直した題をもう一度 直します（実測 100単位）")
    assert got[0].get("title_at_upload") == "上げたときの字 #Shorts", (
        "上げたときの字は `title_at_upload` に残すこと（題の形を測る側が要ります）")


def test_差し替えが無ければ帳面の字のまま(tmp_path, monkeypatch):
    up = _write(tmp_path / "uploaded.jsonl", [
        {"video_id": "VID2", "topic": "s-y", "title": "そのままの字 #Shorts",
         "at": None, "uploaded_at": "2026-08-19T00:00:00+00:00",
         "retimed_at": "2026-09-02T00:00:00+00:00"},
    ])
    monkeypatch.setattr(retitles, "LEDGER", _write(tmp_path / "retitled.jsonl", []),
                        raising=False)

    got = [r for r in _pool(tmp_path, up) if r["video_id"] == "VID2"]
    assert got and got[0]["title"] == "そのままの字 #Shorts"
    assert "title_at_upload" not in got[0], "重ねていない行に余分な欄を足さないこと"
