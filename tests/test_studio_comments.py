"""`studio.yt.viewer_comments()` は「視聴者が書いた分だけ」を返す。

2026-09-07 20:4x（optimizer・Opus）に足した。**このチャンネルのコメント 21件 のうち 18件 は自分**
（旧 `src/` の pipeline が上げる時に置いた自動コメント）で、視聴者は 3件 しか居ない。
自分の分を落とし損ねると、**唯一の批評「ＡＩナレーショングダグダ」が 18件 の自作自演に埋もれる。**
落とす鍵は `authorChannelId`（表示名ではない —— 表示名は視聴者が同じ名前に変えられる）。
"""
from __future__ import annotations

import studio.yt as yt

CID = "UChTXZzwkIJHqyL7L_fEtuqQ"


def _sn(author, cid, text, at, likes=0):
    return {"authorDisplayName": author, "authorChannelId": {"value": cid},
            "publishedAt": at, "likeCount": likes, "textDisplay": text}


def _thread(tid, author, cid, text, at, video="v1", likes=0, replies=(), total=None):
    """`replies` は (id, 表示名, チャンネルID, 本文, 時刻) の並び。`total` は API の `totalReplyCount`
    （載っている数より多いと、`comments.list` を足で引く側に入る）。"""
    rs = [{"id": r[0], "snippet": _sn(r[1], r[2], r[3], r[4])} for r in replies]
    t = {"id": tid, "snippet": {"videoId": video, "totalReplyCount": len(rs) if total is None else total,
                                "topLevelComment": {"snippet": _sn(author, cid, text, at, likes)}}}
    if rs:
        t["replies"] = {"comments": rs}
    return t


class _Svc:
    """`channels().list()` と `commentThreads().list()` だけを持つ贋物。

    `moderationStatus` の列ごとに別のページの束を返す（`published` は既定で `pages`、
    `heldForReview` と `likelySpam` は既定で空）。**本物の API と同じで、列を訊かなければ
    published しか返らない** —— それが 2026-09-08 15:0x まで見えていなかった穴。
    """

    def __init__(self, pages, held=None, spam=None, fail=(), extra=None):
        self.by_col = {"published": pages,
                       "heldForReview": held or [{"items": []}],
                       "likelySpam": spam or [{"items": []}]}
        self.fail = set(fail)
        self.asked = []
        # スレッド ID → `comments.list` が返す items（5件 を越えるスレッドの足での引き直し）
        self.extra = extra or {}
        self._in_comments = False

    def channels(self):
        return self

    def commentThreads(self):  # noqa: N802
        self._in_comments = False
        return self

    def comments(self):
        self._in_comments = True
        return self

    def list(self, **kw):
        self.asked.append(kw)
        if self._in_comments:
            if "comments.list" in self.fail:
                raise RuntimeError("引けない")
            return _Exec({"items": self.extra.get(kw["parentId"], [])})
        if "mine" in kw:
            return _Exec({"items": [{"id": CID, "snippet": {"title": "t"},
                                     "statistics": {"subscriberCount": "26"},
                                     "contentDetails": {"relatedPlaylists": {"uploads": "UU"}}}]})
        col = kw.get("moderationStatus", "published")
        if col in self.fail:
            raise RuntimeError(f"{col} は引けない")
        tok = kw.get("pageToken")
        idx = 0 if tok is None else int(tok)
        return _Exec(self.by_col[col][idx])


class _Exec:
    def __init__(self, v):
        self.v = v

    def execute(self):
        return self.v


def _install(monkeypatch, pages, held=None, spam=None, fail=(), extra=None):
    svc = _Svc(pages, held=held, spam=spam, fail=fail, extra=extra)
    monkeypatch.setattr(yt, "svc", lambda: svc)
    return svc


def test_自分のコメントは落ちる(monkeypatch):
    _install(monkeypatch, [{"items": [
        _thread("t1", "@お金と仕事の教科書", CID, "この計算は毎日1本ずつ出しています。", "2026-09-05T07:01:00Z"),
        _thread("t2", "@viewer", "UC_other", "ＡＩナレーショングダグダ", "2026-08-29T10:08:00Z"),
    ]}])
    got = yt.viewer_comments()
    assert [c["id"] for c in got] == ["t2"]
    assert got[0]["text"] == "ＡＩナレーショングダグダ"
    assert got[0]["author"] == "@viewer"


def test_表示名が同じでも_チャンネルIDで見分ける(monkeypatch):
    """視聴者がチャンネルと同じ表示名を名乗っても、ID が違えば視聴者として残す。"""
    _install(monkeypatch, [{"items": [
        _thread("t1", "@お金と仕事の教科書", "UC_impostor", "なりすまし", "2026-09-01T00:00:00Z"),
        _thread("t2", "@お金と仕事の教科書", CID, "自分", "2026-09-02T00:00:00Z"),
    ]}])
    assert [c["id"] for c in yt.viewer_comments()] == ["t1"]


def test_新しい順(monkeypatch):
    _install(monkeypatch, [{"items": [
        _thread("old", "@a", "UC_a", "ふるい", "2026-08-21T05:48:00Z"),
        _thread("new", "@b", "UC_b", "あたらしい", "2026-08-29T10:08:00Z"),
    ]}])
    assert [c["id"] for c in yt.viewer_comments()] == ["new", "old"]


def test_ページを最後までたどる(monkeypatch):
    _install(monkeypatch, [
        {"items": [_thread("a", "@a", "UC_a", "1", "2026-08-01T00:00:00Z")], "nextPageToken": "1"},
        {"items": [_thread("b", "@b", "UC_b", "2", "2026-08-02T00:00:00Z")]},
    ])
    assert [c["id"] for c in yt.viewer_comments()] == ["b", "a"]


def test_チャンネル全部を1度に引く(monkeypatch):
    """本ごとに引くと 227単位。`allThreadsRelatedToChannelId` なら 列ごとに 1単位 ＝ 3単位。"""
    svc = _install(monkeypatch, [{"items": []}])
    yt.viewer_comments()
    asked = [k for k in svc.asked if "mine" not in k]
    assert len(asked) == 3
    assert [k["moderationStatus"] for k in asked] == ["published", "heldForReview", "likelySpam"]
    for k in asked:
        assert k["allThreadsRelatedToChannelId"] == CID
        assert "videoId" not in k


def test_保留と迷惑の列も引く(monkeypatch):
    """**これが 2026-09-08 15:0x に塞いだ穴**（`yt.viewer_comments()` の註）。

    `moderationStatus` を省くと API は `published` しか返さない。省いていたので、
    保留・迷惑に落ちたコメントは道具から1件も見えず、しかも「新着 0件」と
    published と同じ顔で印字されていた。視聴者の「コメントしたのに消えた」に答えられない。
    """
    _install(monkeypatch, [{"items": [
        _thread("p1", "@a", "UC_a", "出ている", "2026-09-01T00:00:00Z")]}],
        held=[{"items": [_thread("h1", "@b", "UC_b", "保留された", "2026-09-02T00:00:00Z")]}],
        spam=[{"items": [_thread("s1", "@c", "UC_c", "迷惑あつかい", "2026-09-03T00:00:00Z")]}])
    got = yt.viewer_comments()
    assert [c["id"] for c in got] == ["s1", "h1", "p1"]
    assert {c["id"]: c["status"] for c in got} == {
        "p1": "published", "h1": "heldForReview", "s1": "likelySpam"}


def test_保留の列でも自分のコメントは落ちる(monkeypatch):
    _install(monkeypatch, [{"items": []}],
             held=[{"items": [
                 _thread("h1", "@自分", CID, "自動コメント", "2026-09-02T00:00:00Z"),
                 _thread("h2", "@b", "UC_b", "視聴者", "2026-09-02T00:01:00Z")]}])
    assert [c["id"] for c in yt.viewer_comments()] == ["h2"]


def test_保留の列が引けなくても_published_は返る(monkeypatch):
    """保留・迷惑は権限や仕様で落ちうる。**そこで published まで失うと、退化する。**"""
    _install(monkeypatch, [{"items": [
        _thread("p1", "@a", "UC_a", "出ている", "2026-09-01T00:00:00Z")]}],
        fail=("heldForReview", "likelySpam"))
    got = yt.viewer_comments()
    assert [c["id"] for c in got] == ["p1"]
    assert got[0]["status"] == "published"


def test_published_が引けなければ_黙って握り潰さない(monkeypatch):
    """published が落ちたら例外を上げる（`status` の except が「引けなかった」と印字する）。"""
    import pytest
    _install(monkeypatch, [{"items": []}], fail=("published",))
    with pytest.raises(RuntimeError):
        yt.viewer_comments()


def test_with_moderation_False_なら_published_だけ(monkeypatch):
    svc = _install(monkeypatch, [{"items": []}])
    yt.viewer_comments(with_moderation=False)
    assert len([k for k in svc.asked if "mine" not in k]) == 1


def test_コメントが無くても落ちない(monkeypatch):
    _install(monkeypatch, [{"items": []}])
    assert yt.viewer_comments() == []


def test_row_にコメント数が入る():
    """`measure` が台帳へ書く数に commentCount を混ぜるため（`_row`）。"""
    v = {"id": "x", "snippet": {"title": "t", "publishedAt": "2026-09-01T00:00:00Z"},
         "status": {"privacyStatus": "public"},
         "statistics": {"viewCount": "0", "likeCount": "0", "commentCount": "1"}}
    assert yt._row(v)["comments"] == 1
    v["statistics"] = {}
    assert yt._row(v)["comments"] == 0


# ---------------------------------------------------------------------------
# スレッドの中の返信（2026-09-09 04:2x JST・optimizer・Opus）
#
# `part="snippet"` だけだと最上位コメントしか返らない ＝ **こちらが返信したあとの続きが見えない。**
# 実測（この回に API を直に撃った。スレッド Ugxalw5necUowSfrP1t4AaABAg）:
#   09/08 03:38Z 視聴者「65歳までに死んだら…」→ 08:10Z こちら → **09:41Z 視聴者「遺族年金は必ず受給できますか？」** → 11:29Z こちら
# 台帳に 2問目の `viewer_comment` は 1行 も無く（`grep '遺族年金は必ず' ＝ 0件`）、`replied` だけが在った。
# ＝ **答えは残っているのに問いが残っていない。** `status` は 6周 続けて「新着 0件」と言っていた。
# ---------------------------------------------------------------------------


def test_スレッドの返信も返る_自分の返信は落ちる(monkeypatch):
    _install(monkeypatch, [{"items": [
        _thread("t1", "@viewer", "UC_v", "65歳までに死んだら…", "2026-09-08T03:38:00Z", replies=[
            ("t1.r1", "@お金と仕事の教科書", CID, "はい、そのとおりです。", "2026-09-08T08:10:00Z"),
            ("t1.r2", "@viewer", "UC_v", "遺族年金は必ず受給できますか？", "2026-09-08T09:41:00Z"),
            ("t1.r3", "@お金と仕事の教科書", CID, "必ずではありません。", "2026-09-08T11:29:00Z"),
        ])]}])
    got = yt.viewer_comments()
    assert [c["id"] for c in got] == ["t1.r2", "t1"]        # 新しい順・自分の 2件 は落ちる
    r = got[0]
    assert r["reply"] is True and r["parent_id"] == "t1"     # 撃つ先はスレッド ID
    assert r["video_id"] == "v1" and r["text"] == "遺族年金は必ず受給できますか？"
    assert got[1]["reply"] is False and got[1]["parent_id"] == "t1"


def test_最上位が自分のスレッドでも_視聴者の返信は落ちない(monkeypatch):
    """**同じ穴の大きいほう。** 旧 pipeline の自動コメントが最上位のスレッドは 18本 在り、
    前は `continue` でスレッドごと落としていた ＝ そこへ視聴者が返信しても永久に見えない。"""
    _install(monkeypatch, [{"items": [
        _thread("t9", "@お金と仕事の教科書", CID, "この計算は毎日1本ずつ出しています。", "2026-09-05T07:01:00Z",
                replies=[("t9.r1", "@viewer", "UC_v", "ここが分からない", "2026-09-06T00:00:00Z")])]}])
    got = yt.viewer_comments()
    assert [c["id"] for c in got] == ["t9.r1"]
    assert got[0]["parent_id"] == "t9" and got[0]["reply"] is True


def test_repliesを引いている_snippetだけに戻すと落ちる(monkeypatch):
    """陽性対照: `part` から `replies` が抜けたら、この検査が落ちる。"""
    svc = _install(monkeypatch, [{"items": []}])
    yt.viewer_comments()
    for k in [k for k in svc.asked if "allThreadsRelatedToChannelId" in k]:
        assert k["part"] == "snippet,replies"


def test_返信が5件を越えたら足で引く_単位はそのスレッドだけ(monkeypatch):
    """`commentThreads` は返信を最大 5件 しか載せない。`totalReplyCount` が多いときだけ
    `comments.list`（1単位／スレッド）を撃つ ＝ 少ないスレッドでは 0単位。"""
    load = [("t1.r%d" % i, "@お金と仕事の教科書", CID, "自分", "2026-09-08T0%d:00:00Z" % i) for i in range(5)]
    svc = _install(monkeypatch, [{"items": [
        _thread("t1", "@viewer", "UC_v", "問い", "2026-09-08T00:00:00Z", replies=load, total=7),
        _thread("t2", "@viewer", "UC_v", "返信なし", "2026-09-07T00:00:00Z"),
    ]}], extra={"t1": [
        {"id": "t1.r6", "snippet": _sn("@viewer", "UC_v", "6件目の続き", "2026-09-08T10:00:00Z")},
        {"id": "t1.r7", "snippet": _sn("@お金と仕事の教科書", CID, "自分", "2026-09-08T11:00:00Z")},
    ]})
    got = yt.viewer_comments()
    assert [c["id"] for c in got] == ["t1.r6", "t1", "t2"]
    asked = [k for k in svc.asked if "parentId" in k]
    assert [k["parentId"] for k in asked] == ["t1"]          # 返信なしのスレッドには撃たない


def test_足で引けなくても_載っていた返信は失わない(monkeypatch):
    _install(monkeypatch, [{"items": [
        _thread("t1", "@viewer", "UC_v", "問い", "2026-09-08T00:00:00Z", total=99,
                replies=[("t1.r1", "@viewer", "UC_v", "載っていた続き", "2026-09-08T09:41:00Z")])]}],
        fail=("comments.list",))
    assert [c["id"] for c in yt.viewer_comments()] == ["t1.r1", "t1"]
