"""視聴者の1行に「**こちらが答えたか**」が付くこと（`studio.yt._mark_answered`）。

2026-09-09 17:2x JST（optimizer・Opus）に足した。**実物で1度 払った値段**:
`viewer_comments()` は自分の行を落とすので、`comments`／`status` は「答えた」を1度も出せず、
この回は `status` の「うちスレッドの返信 1件」を見て「未返信の質問が 30時間 放置」と読み、
API を別に 1単位 撃って **09/08 17:10 JST に答えていた**と分かりました。

**台帳では埋まりません**（実測: 同じスレッドに こちらの返信は 2件・台帳 `replied` は 1件）。
だから正本は API の側で、それは `part="snippet,replies"` で**もう引けています**（追加 0単位）。

**陽性対照つき**（下の 2件）: 印を付ける所を壊すと落ちること・
「時刻で見る」を「数で見る」に落とすと落ちることを、この検査が捕まえます。
"""
from __future__ import annotations

import studio.yt as yt
from tests.test_studio_comments import CID, _Svc, _thread

OTHER = "UCviewer00000000000000"


def _threads():
    """実物と同じ形（09/08 の `lQHX9LJ80Sg`）:
    03:38 視聴者の問い → 08:10 こちらの答え → 09:41 視聴者の次の問い → 11:29 こちらの答え。
    もう1つ、**まだ答えていない**スレッドを並べる。"""
    return [_thread("T1", "@viewer", OTHER, "65歳までに死んだら？", "2026-09-08T03:38:20Z", replies=(
        ("T1.a", "@ch", CID, "はい、そのとおりです。", "2026-09-08T08:10:46Z"),
        ("T1.b", "@viewer", OTHER, "遺族年金は必ず受給できますか？", "2026-09-08T09:41:41Z"),
        ("T1.c", "@ch", CID, "必ずではありません。", "2026-09-08T11:29:42Z"),
    )),
        _thread("T2", "@viewer2", OTHER, "まだ答えていない問い", "2026-09-09T02:00:00Z")]


def _rows(monkeypatch):
    svc = _Svc([{"items": _threads()}])
    monkeypatch.setattr(yt, "svc", lambda: svc)
    monkeypatch.setattr(yt, "channel", lambda: {"id": CID})
    return {r["id"]: r for r in yt.viewer_comments()}


def test_答えたスレッドの行は返信ずみになる(monkeypatch):
    r = _rows(monkeypatch)
    assert r["T1"]["answered"] is True
    assert r["T1"]["answered_at"] == "2026-09-08T08:10:46Z"


def test_答えのあとに来た問いも返信ずみになる(monkeypatch):
    """09:41 の次の問いには 11:29 の答えが付く（08:10 の答えを使い回さないこと）。"""
    r = _rows(monkeypatch)
    assert r["T1.b"]["answered"] is True
    assert r["T1.b"]["answered_at"] == "2026-09-08T11:29:42Z"


def test_答えていないスレッドは未返信のまま(monkeypatch):
    r = _rows(monkeypatch)
    assert r["T2"]["answered"] is False
    assert r["T2"]["answered_at"] is None


def test_自分の返信そのものは行として返らない(monkeypatch):
    """`answered` を足しても、自分の行を出す形にはしない（20:4x の「18件の自作自演に埋もれる」）。"""
    r = _rows(monkeypatch)
    assert "T1.a" not in r and "T1.c" not in r
    assert len(r) == 3


def test_陽性対照_印を付けないと落ちる(monkeypatch):
    """`_mark_answered` を素通しにすると、上の判定が全部 落ちること。"""
    monkeypatch.setattr(yt, "_mark_answered", lambda row, ours: row)
    r = _rows(monkeypatch)
    assert not r["T1"].get("answered") and not r["T1.b"].get("answered")


def test_陽性対照_数で見ると次の問いを取りこぼす():
    """「返信が1件でも在れば返信ずみ」に落とすと、**答えのあとに来た問い**が
    返信ずみに化ける ＝ 時刻で見ることが効いている証拠。"""
    later = yt._mark_answered({"at": "2026-09-08T09:41:41Z"}, ["2026-09-08T08:10:46Z"])
    assert later["answered"] is False, "自分より前の返信を『答え』と数えてはいけない"
