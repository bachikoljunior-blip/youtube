"""`scripts/search_terms.py` —— **M4 の判定が、日枠の有無に左右されないこと。**

## この検査が固定している「当たり」（2026-09-01 に実際に踏んだ）

`by_video()` は公開ぶんの一覧を **Data API**（`channels.list` →
`playlistItems.list` → `videos.list`）から作っていました。**あれは日枠を使う口**です。

枠は毎日 尽きます（実測 2026-09-01: 13,352単位 / 枠 10,000・403 を 43回）。
そして落ち方が悪い —— その3本は `HttpError` をそのまま投げ、
**`FetchFailed` に包んでいませんでした。** `main()` の
「**この回は M4 を判定できません**」という断りは `FetchFailed` しか待っていないので、
**素の `HttpError` は横をすり抜けて traceback で死にます。**

残るのは、直前に印字ずみの語べつの節だけ ——
「**この数字だけで M4 を判定しないこと。下の動画べつを見ること**」と書いた直後に、
**その「下」が消える。** `FetchFailed` の docstring が言っている
「失敗と基準値を混ぜるな」と同じ穴が、**包み忘れ**で開いていました。

だからここで固定するのは2つです:

    1. **Data API（`youtube` v3）を1回も開かないこと** ← 枠と無関係になる
    2. 取れなかったときは **`FetchFailed`** で出ること   ← `main()` の断りに必ず入る

**実物の再生数で固定しないこと。** 数は毎日 動きます（`tests/test_doc_numbers.py` が
同じ壊れ方を何度も拾っています）。ここで固定するのは**道具の振る舞い**だけ。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "search_terms_under_test", ROOT / "scripts" / "search_terms.py")
assert _spec and _spec.loader
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "quotaExceeded"


class _Query:
    """`reports().query(...)` の返り。呼ばれた次元で何の問いかを見分ける。"""

    def __init__(self, kwargs: dict, rows_by_dim: dict) -> None:
        self._rows = rows_by_dim.get(kwargs.get("dimensions"), [])

    def execute(self) -> dict:
        if isinstance(self._rows, Exception):
            raise self._rows
        return {"rows": list(self._rows)}


class _Analytics:
    def __init__(self, rows_by_dim: dict) -> None:
        self._rows_by_dim = rows_by_dim

    def reports(self):
        return self

    def query(self, **kwargs):
        return _Query(kwargs, self._rows_by_dim)


def _patch_build(monkeypatch, rows_by_dim: dict) -> list[str]:
    """`build()` を差し替え、**開かれたサービス名を記録**して返す。"""
    opened: list[str] = []

    def fake_build(service, version, **_kw):
        opened.append(f"{service}:{version}")
        if service == "youtubeAnalytics":
            return _Analytics(rows_by_dim)
        raise AssertionError(f"日枠を使う口を開こうとしました: {service} {version}")

    monkeypatch.setattr(st, "build", fake_build)
    monkeypatch.setattr(st, "credentials", lambda: object())
    return opened


def _patch_local(monkeypatch, rows: list[dict], measured: dict) -> None:
    from src import dupes, forms
    monkeypatch.setattr(dupes, "ledger_rows", lambda *a, **k: list(rows))
    monkeypatch.setattr(forms, "measured_forms", lambda: dict(measured))


def test_動画べつは_Data_API_を1回も開かない(monkeypatch):
    """**これが本体。** 枠が尽きていても M4 が判定できる、の機械の側。"""
    opened = _patch_build(monkeypatch, {
        "video": [["vid_long", 40], ["vid_short", 9]],
        "insightTrafficSourceType": [["YT_SEARCH", 3, 1], ["SHORTS", 30, 2]],
    })
    _patch_local(monkeypatch,
                 [{"id": "vid_long", "title": "長尺のほう"},
                  {"id": "vid_short", "title": "ショートのほう #Shorts"}],
                 {"vid_long": "長尺", "vid_short": "ショート"})

    out = st.by_video(7)

    assert set(opened) == {"youtubeAnalytics:v2"}, opened
    # YT_SEARCH の行だけが残る（SHORTS は流入経路ちがい）
    assert [(r[0], r[2], r[3]) for r in out] == [
        ("vid_long", False, 3), ("vid_short", True, 3)]


def test_再生0の本は候補に入れない(monkeypatch):
    """総再生が 0 の本に `YT_SEARCH` の行は立たないので、照会しない。"""
    _patch_build(monkeypatch, {"video": [["a", 5], ["b", 0]]})
    assert st.candidate_ids(7) == ["a"]


def test_取れなかったら_FetchFailed_で出る(monkeypatch):
    """**素の `HttpError` で死なないこと** —— `main()` の断りは `FetchFailed` しか待っていない。"""
    from googleapiclient.errors import HttpError
    _patch_build(monkeypatch, {"video": HttpError(_Resp(403), b"quota")})
    with pytest.raises(st.FetchFailed):
        st.candidate_ids(7)


def test_一時的な500は待ち直す(monkeypatch):
    """121本を1本ずつ引くので、**1本の一時的な 500 で判定が丸ごと落ちていた**
    （2026-09-01 実測 `B3pgxY1Xi1w: 500`。直前の同じ問い合わせは通っている）。"""
    from googleapiclient.errors import HttpError
    monkeypatch.setattr(st.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise HttpError(_Resp(500), b"backend error")
        return {"rows": [["YT_SEARCH", 4, 1]]}

    got = st._retry(lambda: type("C", (), {"execute": staticmethod(flaky)})(), where="v")
    assert got == {"rows": [["YT_SEARCH", 4, 1]]}
    assert calls["n"] == 3


def test_待っても駄目なら数を捏造せず_FetchFailed(monkeypatch):
    """取れなかった本を 0再生 として足すと、**長尺の合計が基準値の下へ黙って動きます。**"""
    from googleapiclient.errors import HttpError
    monkeypatch.setattr(st.time, "sleep", lambda _s: None)

    def always_500():
        raise HttpError(_Resp(503), b"unavailable")

    with pytest.raises(st.FetchFailed):
        st._retry(lambda: type("C", (), {"execute": staticmethod(always_500)})(), where="v")


def test_403は待ち直さない(monkeypatch):
    """**尽きた枠は待っても戻りません。** 一時的な 5xx と混ぜないこと。"""
    from googleapiclient.errors import HttpError
    slept: list[int] = []
    monkeypatch.setattr(st.time, "sleep", lambda s: slept.append(s))

    def quota():
        raise HttpError(_Resp(403), b"quota")

    with pytest.raises(st.FetchFailed):
        st._retry(lambda: type("C", (), {"execute": staticmethod(quota)})(), where="v")
    assert slept == []


def test_台帳は数だけを積み_最後の1点を返す(tmp_path, monkeypatch):
    """`run_marker.py --write` はこの台帳しか読みません（**API 0単位**）。"""
    monkeypatch.setattr(st, "LEDGER", tmp_path / "search_terms.jsonl")
    st.record(7, [("a", "長尺", False, 6, 1), ("b", "ショート", True, 40, 2)])
    st.record(7, [("a", "長尺", False, 9, 1)])
    assert st.latest() == {**st.latest(), "long_views": 9, "short_views": 0, "videos": 1}
    # 壊れた行で印そのものを落とさないこと
    st.LEDGER.write_text('{"long_views": 3, "short_views": 0}\nこわれた行\n', encoding="utf-8")
    assert st.latest()["long_views"] == 3


def test_窓の違う点を_7日_の基準値と並べない(tmp_path, monkeypatch):
    """M4 の基準値は「**1再生/7日**」で、窓の長さと対。

    `--days 28` の点をそのまま並べると、**4倍 の窓の数を 7日 の基準値と比べる**ことになり、
    黙って「超えた」側へ倒れます。
    """
    monkeypatch.setattr(st, "LEDGER", tmp_path / "search_terms.jsonl")
    st.record(7, [("a", "長尺", False, 2, 0)])
    st.record(28, [("a", "長尺", False, 40, 0)])
    assert st.latest(7)["long_views"] == 2          # 28日 の点に引きずられない
    assert st.latest(28)["long_views"] == 40
    assert st.latest(90) is None


def test_台帳が無ければ_None(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "LEDGER", tmp_path / "nope.jsonl")
    assert st.latest() is None


def test_形は_src_forms_に決めさせる_題名の札に勝つ(monkeypatch):
    """`#Shorts` が付いていても、**実測が長尺と言えば長尺**（`src.forms` の決め方）。

    実物にこの本が居ます —— 「傷病手当金 … 半減か **#Shorts**」が `長尺`。
    札で決めると M4 の長尺ぶんから丸ごと落ちます。
    """
    _patch_build(monkeypatch, {})
    _patch_local(monkeypatch,
                 [{"id": "v1", "title": "札は付いているが長尺 #Shorts"}],
                 {"v1": "長尺"})
    assert st.local_meta(["v1"]) == {"v1": ("札は付いているが長尺 #Shorts", False)}


def test_題が手元に無い本は行ごと消さない(monkeypatch):
    """題が引けなくても**長尺かどうかは別に決まる**ので、動画IDを出して行は残す。"""
    _patch_build(monkeypatch, {})
    _patch_local(monkeypatch, [], {"orphan": "長尺"})
    assert st.local_meta(["orphan"]) == {"orphan": ("orphan", False)}
