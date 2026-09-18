"""**`update_meta` の 1回目 が 403 で落ち、30秒 後の 2回目 が通ったとき、その返りで読み返すこと**
（2026-09-17 23:2x・optimizer・Fable 5.1・ultracode が踏んだ）。

実物: `49Wa5jNNzOk`（09/18 15:00）—— insert の直後に tags が落ち、`update_meta` の 1回目 が 403、
2回目 は通って tags 9語 が入った（`readiness` で確かめた）。**なのに `verify_meta` は
UnboundLocalError（`back`）で落ち、台帳 `meta_repaired` が書かれなかった** —— 撃ち直しの枝が
返りを `back` に受けていなかった。`tests/test_studio_schedule_verify_meta.py` は「2回目 も落ちる」側しか見ていなかった。

**【2026-09-19 01:xx・optimizer・opus】偽物が本物から遅れて、この検査は 1日 赤のままでした。**
2026-09-18 20:3x に `studio/asp.py` が入り、**本物の `yt.update_meta` は
`description = asp.compose(description)` を通してから打つ**ようになりました
（`studio/yt.py`）。ところが下の `_update_meta`／`_readiness` は**素の字を返したまま**で、
`cli.drift_fields` が `asp.compose(s.description)` と比べるので **説明欄 が永久に食い違い**ます。
＝ **道具は正しく、遅れていたのは偽物のほう**でした。両方に `asp.compose` を通します。
**覆る条件**: `yt.update_meta` が `compose` を通すのをやめたら、ここも戻すこと
（**偽物は本物の側をなぞる** ＝ この検査が見たいのは「403 の次の返りで読み返すか」だけで、
説明欄の作り方ではありません）。
"""
import json

import pytest
from googleapiclient.errors import HttpError

from studio import asp, cli, script


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
        # **本物と同じく、上がっている説明欄は `asp.compose` を通った字**（上の 2026-09-19 の註）。
        return {"ok": True, "title": s.title, "description": asp.compose(s.description),
                "tags": []}   # tags だけが落ちている

    def _update_meta(vid, title, description, tags):
        calls.append(vid)
        if len(calls) == 1:
            raise HttpError(_Resp(), b'{"error": {"message": "forbidden"}}')
        # 本物（`studio/yt.update_meta`）は打つ前に `asp.compose` を通す。
        return {"title": title, "description": asp.compose(description),
                "tags": list(tags), "ok": True}

    monkeypatch.setattr(cli.yt, "readiness", _readiness)
    monkeypatch.setattr(cli.yt, "update_meta", _update_meta)
    monkeypatch.setattr(cli, "ledger", lambda ev, sid, **kw: rows.append((ev, sid, kw)))
    monkeypatch.setattr(cli.time, "sleep", lambda sec: rows.append(("sleep", sec)))

    assert cli.verify_meta("VID", s) == []          # 2回目 の返りが台本どおり ＝ 残る食い違いは無い
    assert calls == ["VID", "VID"]
    done = [r for r in rows if r[0] == "meta_repaired"]
    assert len(done) == 1 and done[0][2]["left"] is None and done[0][2]["fields"] == "tags"
