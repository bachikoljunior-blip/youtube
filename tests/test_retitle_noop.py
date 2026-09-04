"""`scripts/retitle.py` —— **実物ともう同じ字なら、50単位 を撃たないこと。**

2026-09-05 04:4x に数えて足しました。50単位 を撃つ道具は4つあり、
**3つは「もう同じ値か」を必ず見ています**（`reschedule._update` の `"same"`・
`sub_ask.apply_to_video` の `after == before`・`refresh_thumbnail` は控えから作り直す）。
**`retitle.py` だけが、`videos.list` で読んだ字と書く字を1度も比べていませんでした。**

実物（`data/retitled.jsonl`）::

    18:12:17Z  DtpnSVFDtAE → 【小規模企業共済】…の境目で59万7200円動く
    18:12:27Z  DtpnSVFDtAE → 【小規模企業共済】…でいくら違う？      ← 10秒前の字へ戻した

**往復で 100単位・差し引き 0**（`retitle.py` の全消費 350単位 の 29%）。
戻す側は**止めません**（誤った題を今すぐ直す道を塞ぐことになる）——
止めるのは「もう同じ字」の側だけです。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import retitles  # noqa: E402
from src import upload_cap  # noqa: E402


def _mod():
    spec = importlib.util.spec_from_file_location(
        "retitle_under_test", ROOT / "scripts" / "retitle.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["retitle_under_test"] = mod
    spec.loader.exec_module(mod)                    # type: ignore[union-attr]
    return mod


class _Videos:
    def __init__(self, title: str, updates: list):
        self._title = title
        self._updates = updates

    def list(self, **_kw):
        title = self._title
        return type("R", (), {"execute": staticmethod(
            lambda: {"items": [{"snippet": {"title": title,
                                            "categoryId": "27"}}]})})()

    def update(self, **kw):
        self._updates.append(kw)
        return type("R", (), {"execute": staticmethod(lambda: {})})()


class _Svc:
    def __init__(self, title: str, updates: list):
        self._v = _Videos(title, updates)

    def videos(self):
        return self._v


@pytest.fixture()
def rt(tmp_path, monkeypatch):
    mod = _mod()
    monkeypatch.setattr(retitles, "LEDGER", tmp_path / "retitled.jsonl")
    monkeypatch.setattr(upload_cap, "reserve_hold", lambda *a, **k: "")
    monkeypatch.setattr(upload_cap, "note_quota_ok", lambda *a, **k: None)
    return mod


def test_同じ字なら_updateを撃たない(rt, monkeypatch):
    updates: list = []
    monkeypatch.setattr(rt, "_service", lambda: _Svc("いまの題", updates))
    assert rt.main("abc", "いまの題") == 0
    assert updates == []                      # **50単位 を撃っていない**


def test_同じ字のときは_控えを実物へ寄せる(rt, monkeypatch):
    updates: list = []
    monkeypatch.setattr(rt, "_service", lambda: _Svc("いまの題", updates))
    rt.main("abc", "いまの題")
    assert retitles.latest().get("abc") == "いまの題"
    # 2回目は控えがもう合っているので、行は増えない
    n = len(retitles.history("abc"))
    rt.main("abc", "いまの題")
    assert len(retitles.history("abc")) == n


def test_違う字なら_これまでどおり撃つ(rt, monkeypatch):
    updates: list = []
    monkeypatch.setattr(rt, "_service", lambda: _Svc("ふるい題", updates))
    assert rt.main("abc", "あたらしい題") == 0
    assert len(updates) == 1                  # **撃っている**
    assert retitles.latest().get("abc") == "あたらしい題"


def test_前に名乗った字へ戻すのは_止めない(rt, monkeypatch, capsys):
    """**戻す道を塞がないこと** —— 塞ぐと『誤解を与える題を今すぐ直す』道が消えます。"""
    retitles.record("abc", "A", prev="")
    retitles.record("abc", "B", prev="A")
    updates: list = []
    monkeypatch.setattr(rt, "_service", lambda: _Svc("B", updates))
    assert rt.main("abc", "A") == 0
    assert len(updates) == 1                  # 止めていない
    assert "にも名乗っています" in capsys.readouterr().out


def test_seen_before_は_その本の跡だけを見る():
    assert retitles.seen_before("", "なんでも") == []
