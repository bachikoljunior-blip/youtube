"""**`update_meta` の 1回目 が 403 で落ち、30秒 後の 2回目 が通ったとき、その返りで読み返すこと**
（2026-09-17 23:2x・optimizer・Fable 5.1・ultracode が踏んだ）。

実物: `49Wa5jNNzOk`（09/18 15:00）—— insert の直後に tags が落ち、`update_meta` の 1回目 が 403、
2回目 は通って tags 9語 が入った（`readiness` で確かめた）。**なのに `verify_meta` は
UnboundLocalError（`back`）で落ち、台帳 `meta_repaired` が書かれなかった** —— 撃ち直しの枝が
返りを `back` に受けていなかった。`tests/test_studio_schedule_verify_meta.py` は「2回目 も落ちる」側しか見ていなかった。
"""
import json

import pytest
from googleapiclient.errors import HttpError

from studio import cli, script


@pytest.fixture
def s(tmp_path, monkeypatch):
    d = {"id": "2026-09-18-x", "date": "2026-09-18", "title": "題A #Shorts", "takeaway": "t",
         "description": "説明欄A", "tags": ["年金", "手取り"],
         "segments": [{"say": "あ", "show": "あ", "sub": "あ"}], "notes": "n"}
    (tmp_path / "2026-09-18-x.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(script, "SCRIPTS", tmp_path)
    return script.load("2026-09-18-x")


class _Resp:
    status = 403
    reason = "forbidden"


def test_1回目が403で2回目が通ったら_その返りで一致を見て台帳に残す(s, monkeypatch):
    rows = []
    calls = []

    def _readiness(vid):
        return {"ok": True, "title": s.title, "description": s.description, "tags": []}   # tags が落ちている

    def _update_meta(vid, title, description, tags):
        calls.append(vid)
        if len(calls) == 1:
            raise HttpError(_Resp(), b'{"error": {"message": "forbidden"}}')
        return {"title": title, "description": description, "tags": list(tags), "ok": True}

    monkeypatch.setattr(cli.yt, "readiness", _readiness)
    monkeypatch.setattr(cli.yt, "update_meta", _update_meta)
    monkeypatch.setattr(cli, "ledger", lambda ev, sid, **kw: rows.append((ev, sid, kw)))
    monkeypatch.setattr(cli.time, "sleep", lambda sec: rows.append(("sleep", sec)))

    assert cli.verify_meta("VID", s) == []          # 2回目 の返りが台本どおり ＝ 残る食い違いは無い
    assert calls == ["VID", "VID"]
    done = [r for r in rows if r[0] == "meta_repaired"]
    assert len(done) == 1 and done[0][2]["left"] is None and done[0][2]["fields"] == "tags"
