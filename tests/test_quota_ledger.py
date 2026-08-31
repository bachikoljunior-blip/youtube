"""**通った呼び出しも帳面に残すこと。**（2026-08-31 に踏んだ）

投稿0本の日に `python -m src.descriptions --refresh` が `quotaExceeded` で
0/735本。**何が枠を使ったかを言える道具が1つもありませんでした。**
`data/day_quota.jsonl` が書くのは「403 に当たった」と
「`videos.update` が通った」の2つだけで、**読み取りは1行も残りません**
（実測: 08/30・08/31 の `ok` 行は 0件）。

この検査が守るのは4つ:

  1. 単価を**動作から当てられる**こと（`search.list` は list なのに 100単位）
  2. Analytics を Data API の枠に**混ぜない**こと（別枠。混ぜると理由が読めない）
  3. `install()` の包みが **`execute` を通った呼び出しを記録する**こと
  4. **包みの中で何が起きても、本体を止めない**こと
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import config, quota_ledger, upload_cap

DATA = "https://youtube.googleapis.com/youtube/v3/videos?part=snippet&id=a"
SEARCH = "https://youtube.googleapis.com/youtube/v3/search?part=id&forMine=true"
THUMB = "https://youtube.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=a"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports?ids=channel%3D%3DMINE"


# ---------------------------------------------------------------- 単価の側

@pytest.mark.parametrize(("uri", "verb", "api", "method"), [
    (DATA, "GET", "data", "videos.list"),
    (DATA, "PUT", "data", "videos.update"),
    (SEARCH, "GET", "data", "search.list"),
    (THUMB, "POST", "data", "thumbnails.set"),
    (ANALYTICS, "GET", "analytics", "reports.query"),
])
def test_道と動作から手の名前が出ること(uri, verb, api, method) -> None:
    assert quota_ledger.method_of(uri, verb) == (api, method)


def test_検索は_list_でも100単位であること() -> None:
    """**`search.list` は 100単位**。`_scan(cap=400)` は 8ページ ＝ 800単位／回。"""
    assert quota_ledger.cost_of("data", "search.list", "GET") == 100
    assert quota_ledger.cost_of("data", "videos.list", "GET") == 1
    assert quota_ledger.cost_of("data", "videos.insert", "POST") == 1600


def test_知らない手を0単位で埋めないこと() -> None:
    """0 で埋めると、**知らない呼び出しほど安く見えます。**"""
    assert quota_ledger.cost_of("data", "somethingNew.list", "GET") >= 1
    assert quota_ledger.cost_of("data", "somethingNew.insert", "POST") >= 50


def test_Analyticsを日枠に混ぜないこと() -> None:
    """Analytics は別枠。混ぜると「尽きた理由」が読めなくなります。"""
    assert quota_ledger.cost_of("analytics", "reports.query", "GET") == 0


# ---------------------------------------------------------------- 包みの側

@pytest.fixture()
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """帳面を tmp へ逃がす（**本物の台帳に書かないこと** ——`conftest.py` の約束）。"""
    monkeypatch.setattr(config, "ROOT", tmp_path, raising=False)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    def _read() -> list[dict]:
        p = tmp_path / quota_ledger.LEDGER
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

    return _read


def _wrap(monkeypatch: pytest.MonkeyPatch, inner):
    """本物の `execute` を差し替えてから `install()` を掛ける。"""
    from googleapiclient.http import HttpRequest

    monkeypatch.setattr(HttpRequest, "execute", inner, raising=False)
    monkeypatch.setattr(quota_ledger, "_installed", False, raising=False)
    assert quota_ledger.install() is True
    return HttpRequest


class _Req:
    def __init__(self, uri: str, method: str = "GET") -> None:
        self.uri = uri
        self.method = method


def test_通った呼び出しが帳面に残ること(ledger, monkeypatch) -> None:
    cls = _wrap(monkeypatch, lambda self, *a, **k: {"items": []})
    cls.execute(_Req(SEARCH))
    rows = ledger()
    assert len(rows) == 1, rows
    assert rows[0]["method"] == "search.list"
    assert rows[0]["units"] == 100
    assert rows[0]["ok"] is True


def test_落ちた呼び出しも残ること(ledger, monkeypatch) -> None:
    """**403 に当たった側だけを書くのが、いままでの帳面でした。**両方 残すこと。"""
    def boom(self, *a, **k):
        raise RuntimeError("403")

    cls = _wrap(monkeypatch, boom)
    with pytest.raises(RuntimeError):
        cls.execute(_Req(DATA))
    rows = ledger()
    assert len(rows) == 1 and rows[0]["ok"] is False, rows


def test_帳面が書けなくても本体を止めないこと(ledger, monkeypatch) -> None:
    """記録は**おまけ**です。落ちたら黙って通すこと。"""
    cls = _wrap(monkeypatch, lambda self, *a, **k: "ok")

    def die(*a, **k):
        raise OSError("書けません")

    monkeypatch.setattr(quota_ledger, "note", die)
    assert cls.execute(_Req(DATA)) == "ok"


def test_二重に包まないこと(ledger, monkeypatch) -> None:
    """`credentials()` は1周に何度も呼ばれます。**単価が二重に積まれないこと。**"""
    cls = _wrap(monkeypatch, lambda self, *a, **k: None)
    assert quota_ledger.install() is True          # 2回目
    cls.execute(_Req(DATA))
    assert len(ledger()) == 1, ledger()


def test_撃った側の名前が残ること(ledger, monkeypatch) -> None:
    """**どの道具が撃ったか**が無いと、次の回は候補を推測で潰します。"""
    cls = _wrap(monkeypatch, lambda self, *a, **k: None)

    def caller():
        cls.execute(_Req(SEARCH))

    caller()
    assert ledger()[0].get("by", "").endswith(":caller"), ledger()


def test_窓の中だけを数えること(ledger, monkeypatch) -> None:
    """窓は `upload_cap.window_start/end`（太平洋時間の0時）と**同じもの**。"""
    cls = _wrap(monkeypatch, lambda self, *a, **k: None)
    cls.execute(_Req(SEARCH))
    cls.execute(_Req(DATA))
    got = quota_ledger.spent()
    assert got["data"] == 101, got
    assert got["method"]["search.list"] == 100


def test_認証が帳面のせいで落ちないこと(monkeypatch) -> None:
    """`credentials()` は包みが掛からなくても返すこと。"""
    from src import auth

    monkeypatch.setattr(quota_ledger, "install", lambda: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setenv("YT_REFRESH_TOKEN", "x")
    monkeypatch.setenv("YT_CLIENT_ID", "y")
    monkeypatch.setenv("YT_CLIENT_SECRET", "z")
    assert auth.credentials() is not None


def test_帳面は本物の台帳を指していたら書かないこと() -> None:
    """`upload_cap._write_path` の門を**そのまま**使っていること。"""
    assert upload_cap._write_path(quota_ledger.LEDGER) is None
