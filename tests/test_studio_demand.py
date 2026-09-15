"""`studio/demand.py` —— 人が打っている語（検索窓の補完・**日枠 0単位**）。

**陽性対照を 2つ 置いてあります**（`tests/test_studio_peers.py` と同じ形）——
「関係がありませんでした」は、計器が死んでいても同じ字で出るので、
**門を動かすと落ちること**を先に確かめます。
"""
from studio import demand


def _fake(table):
    def get(q):
        return table.get(q, [])
    return get


def test_harvest_は親と順位を覚える():
    got = demand.harvest(["年金"], tails=["", " か"],
                         get=_fake({"年金": ["年金 手取り", "年金 いくら"],
                                    "年金 か": ["年金 加給年金", "年金 手取り"]}),
                         sleep=0)
    assert got["年金 手取り"] == [("年金", 0), ("年金 か", 1)]
    assert got["年金 加給年金"] == [("年金 か", 0)]


def test_harvest_は種そのものを数に入れない():
    got = demand.harvest(["年金"], tails=[""],
                         get=_fake({"年金": ["年金", "年金 手取り"]}), sleep=0)
    assert "年金" not in got
    assert "年金 手取り" in got


def test_harvest_は1回こけても止まらない():
    def get(q):
        if q == "年金":
            raise RuntimeError("429")
        return ["失業保険 金額"]
    got = demand.harvest(["年金", "失業保険"], tails=[""], get=get, sleep=0)
    assert "失業保険 金額" in got


def test_score_は広い語を上に置く():
    ranked = demand.score({"広": [("a", 3), ("b", 3)], "狭": [("a", 0)]})
    assert [r["q"] for r in ranked] == ["広", "狭"]
    assert ranked[0]["n"] == 2 and ranked[0]["best"] == 3


def test_score_は同じ広さなら上位に出た側を上に置く():
    ranked = demand.score({"下": [("a", 5)], "上": [("a", 1)]})
    assert [r["q"] for r in ranked] == ["上", "下"]


def test_gaps_はうちが持っている語を落とす():
    ranked = [{"q": "年金 手取り", "n": 3, "best": 0, "mean": 0.0},
              {"q": "失業保険 バイト", "n": 3, "best": 0, "mean": 0.0}]
    got = demand.gaps(ranked, ["年金が毎月15万円の人の手取りはいくら"])
    assert [r["q"] for r in got] == ["失業保険 バイト"]


def test_gaps_の門を上げると持っている語も残る():
    """**陽性対照 1**: `need` を上げると、落ちていた側が残る ＝ 門が効いている。"""
    ranked = [{"q": "年金 手取り", "n": 3, "best": 0, "mean": 0.0}]
    assert demand.gaps(ranked, ["年金が毎月15万円の人の手取りはいくら"]) == []
    assert len(demand.gaps(ranked, ["年金が毎月15万円の人の手取りはいくら"], need=1.01)) == 1


def test_gaps_の門を0にすると1語も残らない():
    """**陽性対照 2**: `need` を 0 にすると、どの語も「持っている」側へ倒れる。"""
    ranked = [{"q": "失業保険 バイト", "n": 3, "best": 0, "mean": 0.0}]
    assert demand.gaps(ranked, [], need=0.0) == []


def test_covered_は予約と題の直しから題を拾う():
    rows = [{"event": "scheduled", "title": "あ", "id": "い"},
            {"event": "retitled", "new_title": "う", "old_title": "え"},
            {"event": "measured", "title": "お"}]
    got = demand.covered(rows)
    assert "あ" in got and "う" in got and "え" in got
    assert "お" not in got


def test_lines_は単位が0だと字で言う():
    row = {"at": "2026-09-16T04:00:00+09:00", "units": 0, "pulls": 10, "seeds": ["年金"],
           "top": [{"q": "年金 手取り", "n": 3, "best": 0, "mean": 0.5}],
           "gaps": [{"q": "失業保険 バイト", "n": 3, "best": 0, "mean": 0.5, "share": 0.1}]}
    out = "\n".join(demand.lines(row))
    assert "0単位" in out
    assert "年金 手取り" in out and "失業保険 バイト" in out
    # **量ではないと、印字のたびに言うこと**（`studio/demand.py` の註）
    assert "量ではありません" in out


def test_種は失業保険の族を持っている():
    """`peers` の上位 36本 のうち 9本 が失業保険／ハローワークで、うちは 0本（SEEDS の註）。"""
    assert "失業保険" in demand.SEEDS and "ハローワーク" in demand.SEEDS


def test_fetchはoeとieにutf8を渡す(monkeypatch):
    """**2026-09-16 03:4x に踏んだ**: `oe` を渡さないと口は Shift_JIS を返し、658回 の引きが丸ごと化けた。

    化けた語は うちの題と 1文字も重ならないので、`gaps` の重なりが**全部 0.0** になり、
    **「うちは 1本 も持っていない」が 40語 すべてに出ます** ＝ 壊れても、もっともらしい字で出る族。
    """
    seen = {}

    class _R:
        headers = type("H", (), {"get_content_charset": staticmethod(lambda: "utf-8")})()

        @staticmethod
        def read():
            return '["\u5e74\u91d1",["\u5e74\u91d1 \u624b\u53d6\u308a"]]'.encode("utf-8")

    def _open(url, timeout=None):
        seen["url"] = url
        return _R()

    monkeypatch.setattr(demand.urllib.request, "urlopen", _open)
    assert demand.fetch("\u5e74\u91d1") == ["\u5e74\u91d1 \u624b\u53d6\u308a"]
    assert "oe=utf-8" in seen["url"] and "ie=utf-8" in seen["url"]


def test_fetchはヘッダのcharsetで読む(monkeypatch):
    """**陽性対照 3**: header が Shift_JIS だと言ったら、そちらで読むこと（渡した `oe` より header が本当）。"""
    class _R:
        headers = type("H", (), {"get_content_charset": staticmethod(lambda: "shift_jis")})()

        @staticmethod
        def read():
            return '["\u5e74\u91d1",["\u5e74\u91d1 \u624b\u53d6\u308a"]]'.encode("shift_jis")

    monkeypatch.setattr(demand.urllib.request, "urlopen", lambda url, timeout=None: _R())
    assert demand.fetch("\u5e74\u91d1") == ["\u5e74\u91d1 \u624b\u53d6\u308a"]
