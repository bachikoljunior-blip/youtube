"""**書いた返りで読み返すこと。別の `list` で読み返さないこと**（2026-09-17 17:2x・optimizer）。

**実測（この回の実物・`9WdbGJaI2hU`）**: `videos.update` で本の題を打った**直後**の
`videos.list` は **旧の題**を返し、**45秒 後**の同じ引きは **新しい題**を返した。
＝ `list` は遅れた複製から返るので、**直後の読み返しは「落ちた」の偽陰性を作る。**
`settle_stats`（09/09 19:1x・再生が 637 と 823 の 2つの複製から返った）と同じ口。

陽性対照つき（**遅れた複製を返す `list`** を実物で作って測る）。
"""
import types

from studio import yt


class _Exec:
    def __init__(self, val):
        self._val = val

    def execute(self):
        return self._val


class _Videos:
    """`update` は**打った物**を返し、`list` は**遅れた複製**（旧の題）を返す。"""

    def __init__(self, old_title):
        self.old_title = old_title
        self.list_calls = 0

    def update(self, part, body):
        return _Exec({"id": body["id"], "snippet": dict(body["snippet"])})

    def list(self, part, id=None, **kw):
        self.list_calls += 1
        return _Exec({"items": [{"id": id, "snippet": {"title": self.old_title}}]})


class _Channels:
    def __init__(self, old_title):
        self.old_title = old_title
        self.list_calls = 0

    def list(self, part, mine=None, **kw):
        self.list_calls += 1
        return _Exec({"items": [{"id": "UC_x", "brandingSettings": {
            "channel": {"title": self.old_title, "keywords": "年金 給付金",
                        "description": "説明", "unsubscribedTrailer": "CdX2oIb7BG8"}}}]})

    def update(self, part, body):
        return _Exec({"id": body["id"], "brandingSettings": body["brandingSettings"]})


def _svc(videos=None, channels=None):
    s = types.SimpleNamespace()
    s.videos = lambda: videos
    s.channels = lambda: channels
    return s


def test_update_metaは返りで読む_遅れた複製を踏まない(monkeypatch):
    v = _Videos(old_title="旧の題")
    monkeypatch.setattr(yt, "svc", lambda: _svc(videos=v))
    got = yt.update_meta("9WdbGJaI2hU", "新しい題", "説明", ["年金"])
    assert got["ok"] is True, "打った題が返りに在るのに ok が False ＝ 偽陰性"
    assert got["title"] == "新しい題"
    # **1単位 も余計に撃たないこと**
    assert v.list_calls == 0, f"`videos.list` を {v.list_calls}回 撃っている（返りで足りる ＝ 0単位）"


def test_陽性対照_遅れた複製で読むと落ちたと読み違える(monkeypatch):
    """**この検査が本物であることの測り**: 同じ口を `list` で読むと ok は False になる。"""
    v = _Videos(old_title="旧の題")
    monkeypatch.setattr(yt, "svc", lambda: _svc(videos=v))
    yt.update_meta("9WdbGJaI2hU", "新しい題", "説明", ["年金"])
    stale = v.list(part="snippet", id="9WdbGJaI2hU").execute()["items"][0]["snippet"]["title"]
    assert stale == "旧の題", "遅れた複製の実物が作れていない ＝ 上の検査は何も測っていない"
    assert (stale == "新しい題") is False


def test_set_channel_titleは返りで読む(monkeypatch):
    c = _Channels(old_title="お金と仕事の教科書")
    monkeypatch.setattr(yt, "svc", lambda: _svc(channels=c))
    got = yt.set_channel_title("カワウソの年金計算室")
    assert got["before"] == "お金と仕事の教科書"
    assert got["after"] == "カワウソの年金計算室"
    assert got["ok"] is True, "通った書き込みを「落ちた」と読んでいる（偽陰性）"
    # 読む側の `list` は **1回だけ**（書く前の `brandingSettings` を丸ごと拾うため）。
    assert c.list_calls == 1, f"`channels.list` が {c.list_calls}回（読み返しの分は要らない ＝ 1単位 安い）"


def test_brandingSettingsの他の欄を消さない(monkeypatch):
    """`channels.update` は渡した部を**丸ごと置き換える** ＝ 読んでから書くこと。"""
    c = _Channels(old_title="お金と仕事の教科書")
    seen = {}
    real_update = c.update

    def spy(part, body):
        seen.update(body["brandingSettings"]["channel"])
        return real_update(part, body)

    c.update = spy
    monkeypatch.setattr(yt, "svc", lambda: _svc(channels=c))
    yt.set_channel_title("カワウソの年金計算室")
    assert seen.get("keywords") == "年金 給付金"
    assert seen.get("unsubscribedTrailer") == "CdX2oIb7BG8", \
        "紹介動画が黙って消える（転換 2.07/1,000 の面・GOAL (4-p) 3 (a)）"
