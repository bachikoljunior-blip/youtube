"""`src/retitles.py` —— **題を差し替えた後、帳面の題が実物と食い違わないこと。**

2026-09-05 00:2x に踏んだ穴の検査（実測は `src/retitles.py` の docstring）:
`scripts/retitle.py` が YouTube の題を差し替えても `data/uploaded.jsonl` は
上げたときの字のままで、`[次の枠]` がその古い字を毎周いちばん上に刷っていた。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src import retitles

JST = timezone(timedelta(hours=9))


def test_記録が無ければ帳面の題をそのまま返す(tmp_path):
    p = tmp_path / "retitled.jsonl"
    assert retitles.current_title("abc", "もとの題", path=p) == "もとの題"
    assert retitles.latest(p) == {}


def test_差し替えを足すと_いまの題が返る(tmp_path):
    p = tmp_path / "retitled.jsonl"
    retitles.record("abc", "あたらしい題", prev="もとの題", path=p)
    assert retitles.current_title("abc", "もとの題", path=p) == "あたらしい題"


def test_何度_差し替えても_いちばん新しい_at_を採る(tmp_path):
    """**最後の行 ＝ 最新 と読まないこと**（併合で並びが崩れる）。"""
    p = tmp_path / "retitled.jsonl"
    retitles.record("abc", "2番目", path=p,
                    at=datetime(2026, 9, 4, 23, 0, tzinfo=JST))
    # 併合で古い行が後ろに来た形をそのまま作る
    retitles.record("abc", "1番目", path=p,
                    at=datetime(2026, 9, 4, 12, 0, tzinfo=JST))
    assert retitles.current_title("abc", "もとの題", path=p) == "2番目"


def test_重ねると_上げたときの字が残る(tmp_path):
    p = tmp_path / "retitled.jsonl"
    retitles.record("abc", "あたらしい題", prev="もとの題", path=p)
    rows = [{"video_id": "abc", "title": "もとの題"},
            {"video_id": "zzz", "title": "触らない題"}]
    out = retitles.overlay(rows, path=p)
    assert out[0]["title"] == "あたらしい題"
    assert out[0]["title_at_upload"] == "もとの題"
    assert out[1] == {"video_id": "zzz", "title": "触らない題"}
    # 元の list は触らない
    assert rows[0]["title"] == "もとの題"


def test_壊れた行は飛ばす(tmp_path):
    p = tmp_path / "retitled.jsonl"
    p.write_text("こわれた\n" + json.dumps(
        {"at": "2026-09-04T14:03:51Z", "video_id": "abc", "title": "生きた題"},
        ensure_ascii=False) + "\n", encoding="utf-8")
    assert retitles.current_title("abc", "もとの題", path=p) == "生きた題"


def test_next_slot_の帳面読みが差し替えを重ねている():
    """**配線の検査。** 外れたらここが赤になる（`_rows()` が `overlay()` を通すこと）。"""
    from src import next_slot

    src = (next_slot.__file__ and open(next_slot.__file__, encoding="utf-8").read()) or ""
    assert "retitles.overlay(" in src, "next_slot._rows() が差し替えを重ねていない"


def test_retitle_スクリプトが記録を足している():
    """`scripts/retitle.py` が `retitles.record()` を撃つこと（撃たないと帳面が古びる）。"""
    from pathlib import Path

    from src import config

    src = (Path(config.ROOT) / "scripts" / "retitle.py").read_text(encoding="utf-8")
    assert "retitles.record(" in src, "retitle.py が差し替えを記録していない"
