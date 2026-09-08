"""`status` は、上がっている本の 題・説明欄・tags が台本と食い違っていたら名指しで言うこと（2026-09-09 01:5x・hourly・Fable）。

「処理 済」だけでは、説明欄を予約の後に直した回の分が古いまま 10:00 に出る。同じ 1単位 の `snippet` で見える。
tags は YouTube が並べ替えて返す（実測 09/09 01:4x `gv1u7n_pCAQ`）ので集合で比べる。
"""
import json

from studio import cli, script, yt


class _Svc:
    def __init__(self, items):
        self._items = items

    def videos(self):
        return self

    def list(self, **kw):
        assert "snippet" in kw["part"] and "processingDetails" in kw["part"]
        return self

    def execute(self):
        return {"items": self._items}


def _script(tmp_path, monkeypatch, desc="説明欄A"):
    d = {"id": "2026-09-09-x", "date": "2026-09-09", "title": "題A #Shorts", "takeaway": "t", "description": desc,
         "tags": ["年金", "加給年金"], "segments": [{"say": "あ", "show": "あ", "sub": "あ"}], "notes": "n"}
    (tmp_path / "2026-09-09-x.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(script, "SCRIPTS", tmp_path)
    return d


ROWS = [{"event": "scheduled", "id": "2026-09-09-x", "video_id": "VID"}]


def _rd(title="題A #Shorts", desc="説明欄A", tags=("加給年金", "年金")):
    return {"ok": True, "title": title, "description": desc, "tags": list(tags)}


def test_readinessは_snippetも返す(monkeypatch):
    monkeypatch.setattr(yt, "svc", lambda: _Svc([{"id": "A", "snippet": {"title": "T", "description": "D", "tags": ["a"]},
                                                  "status": {"uploadStatus": "processed"},
                                                  "processingDetails": {"processingStatus": "succeeded"}}]))
    r = yt.readiness("A")
    assert r["ok"] and r["title"] == "T" and r["description"] == "D" and r["tags"] == ["a"]


def test_一致なら空_tagsは並びを見ない(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)
    assert cli.meta_drift("VID", _rd(), ROWS) == []
    assert "一致" in cli.meta_mark([])


def test_説明欄が違えば名指し(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch, desc="説明欄B（予約の後に直した）")
    d = cli.meta_drift("VID", _rd(), ROWS)
    assert d == ["説明欄"]
    m = cli.meta_mark(d)
    assert "!!" in m and "説明欄" in m and "update_meta" in m


def test_題とtagsも見る(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)
    assert cli.meta_drift("VID", _rd(title="題B", tags=("年金",)), ROWS) == ["題", "tags"]


def test_台帳に無い本は比べない(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)
    assert cli.meta_drift("OLD", _rd(), ROWS) is None
    assert cli.meta_mark(None) == ""
