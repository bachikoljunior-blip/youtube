"""`scripts/niche_ceiling.py` が**撃った帯を1本残らず**残すこと。

## なぜ要るか（2026-09-04 22:4x に測って足した）

`[きょうの1本]` の readout は、中身の側に残った唯一の手をこう名指しします ——
「**外の帯の上位と作りが違う点を1つ、次の1本に入れる**」。
その手は「上位」と「残り」を比べないと撃てませんが、書き出す所（`top_rows()`）は
**形ごと 15本** しか残さず、残りを題ごと捨てていました:

    撃って測った本  long 334本 / short 131本（`summary.n`・2026-09-03）
    手元に在る実物  long **16本** / short **15本**

実測 2026-09-04: その 16本 で「題に損得の方向語が在るか」を当てたら
中央値 2,265,650回 対 1,596,753回（×1.42・n=9 対 7）—— **この n では何も言えません。**

**戻したら、この検査が赤くなります。**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import niche_ceiling as nc  # noqa: E402


def _band(n: int) -> list[dict]:
    return [{"id": f"v{i}", "views": i, "secs": 900, "form": "long",
             "channel": "c", "title": f"題{i}", "q": "語"} for i in range(n)]


def test_帯は上位だけでなく全部が残る(tmp_path):
    rows = _band(40)
    out = tmp_path / "corpus.jsonl"
    assert nc.corpus_write(rows, "2026-09-04T00:00:00+00:00", path=out) == 40
    got = nc.corpus_rows(path=out)
    # `top_rows()` は形ごと 15本。**帯はそれより多く残っていること。**
    assert len(nc.top_rows(rows)) == nc.TOP_KEEP
    assert len(got) == 40, "帯を top_rows の数まで削らないこと"


def test_同じ本は新しいほうの再生が残る(tmp_path):
    out = tmp_path / "corpus.jsonl"
    nc.corpus_write([{"id": "a", "views": 10, "form": "long"}],
                    "2026-09-01T00:00:00+00:00", path=out)
    nc.corpus_write([{"id": "a", "views": 99, "form": "long"}],
                    "2026-09-04T00:00:00+00:00", path=out)
    got = nc.corpus_rows(path=out)
    assert [r["views"] for r in got] == [99], "古い行で帯の中央値を出さないこと"


def test_形で絞れる(tmp_path):
    out = tmp_path / "corpus.jsonl"
    nc.corpus_write([{"id": "a", "views": 1, "form": "long"},
                     {"id": "b", "views": 2, "form": "short"}],
                    "2026-09-04T00:00:00+00:00", path=out)
    assert [r["id"] for r in nc.corpus_rows("short", path=out)] == ["b"]
    assert [r["id"] for r in nc.corpus_rows("long", path=out)] == ["a"]


def test_無い_file_は空で返る(tmp_path):
    assert nc.corpus_rows(path=tmp_path / "none.jsonl") == []


def test_id_の無い行は残さない(tmp_path):
    out = tmp_path / "corpus.jsonl"
    assert nc.corpus_write([{"views": 5, "form": "long"}],
                           "2026-09-04T00:00:00+00:00", path=out) == 0


def test_書き出す欄は_top_rows_と同じ(tmp_path):
    """読む側が形を覚え直さなくて済むこと。"""
    out = tmp_path / "corpus.jsonl"
    nc.corpus_write([{"id": "a", "views": 1, "secs": 2, "form": "long", "channel": "c",
                      "title": "t", "published": "2026-01-01", "q": "語"}],
                    "2026-09-04T00:00:00+00:00", path=out)
    row = json.loads(out.read_text(encoding="utf-8").strip())
    assert set(row) == {"at", *nc.CORPUS_FIELDS}


def test_実物の帯が空でないこと():
    """**帳面の `top` から埋め戻した 31本** が手元に在ること（2026-09-04）。"""
    if not nc.CORPUS.is_file():
        return
    assert len(nc.corpus_rows()) >= 31
