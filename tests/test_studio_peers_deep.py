"""corpus を**深く**する口（`studio/peers.deep_pull`）と、門の先の距離（`peers.capacity`）。

2026-09-16 11:xx・optimizer・Fable 5.1（ultracode）。

**なぜ要るか**: `peers.title_shape` が出す生の比（最大 54.4倍）は、**同じチャンネルの中で比べると消えます**。
消える理由は corpus が **1チャンネル 1.5本** しか無いことなので、深さを買う口をこの回に足しました。
理由と覆る条件は `studio/peers.py` の `deep_pull` の註・`docs/GOAL.md` (4-m)・JOURNAL 2026-09-16 11:xx。

**陽性対照**（撃って落とした）: `deep_pull` の蓋（`units + 2 > max_units`）を外すと
`test_蓋に当たったら止まる` が落ち、`title_shape` の `paired` を生の比に差し替えると
`test_同じch内の比は生の比と別に出る` が落ちる。
"""
import datetime as dt
import json

import pytest

from studio import peers

JST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 9, 16, 11, 0, tzinfo=JST)


class _FakeReq:
    def __init__(self, payload):
        self._p = payload

    def execute(self):
        return self._p


class _FakeSvc:
    """`channels`→`playlistItems`→`videos` の 3段 を、撃った回数ごと数える偽の口。"""

    def __init__(self, n_videos=3):
        self.calls = {"channels": 0, "playlistItems": 0, "videos": 0}
        self.n_videos = n_videos

    def channels(self):
        self.calls["channels"] += 1
        return self

    def playlistItems(self):
        self.calls["playlistItems"] += 1
        return self

    def videos(self):
        self.calls["videos"] += 1
        return self

    def list(self, **kw):
        if "playlistId" in kw:
            return _FakeReq({"items": [{"contentDetails": {"videoId": f"v{i}"}}
                                       for i in range(self.n_videos)]})
        if kw.get("part", "").startswith("snippet,statistics,contentDetails"):
            ids = kw["id"].split(",")
            return _FakeReq({"items": [
                {"id": v, "snippet": {"title": f"【題】{v}が損しない方法！", "publishedAt": "2026-01-01T00:00:00Z"},
                 "statistics": {"viewCount": "1000", "likeCount": "10"},
                 "contentDetails": {"duration": "PT20M"}} for v in ids]})
        return _FakeReq({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})


def test_1チャンネルは_2単位から():
    """`channels`(1) ＋ `playlistItems`(1) ＋ `videos`(1) ＝ 3単位/ch（50本 まで 1ページ）。

    **`search.list` なら 1回 100単位** なので、同じ深さを search で買うと 30倍 以上 かかります。
    """
    svc = _FakeSvc()
    got = peers.deep_pull(svc, ["UC1"], per_channel=50, max_units=500, now=NOW)
    assert got["channels"] == 1
    assert got["videos"] == 3
    assert got["units"] == 3


def test_蓋に当たったら止まる():
    """`DEEP_MAX_UNITS` は日枠を食い切らないための蓋（`deep_pull` の覆る条件 (4)）。

    蓋を外すと この検査が落ちる（陽性対照）。
    """
    svc = _FakeSvc()
    got = peers.deep_pull(svc, [f"UC{i}" for i in range(50)], per_channel=50, max_units=6, now=NOW)
    assert got["units"] <= 6
    assert got["channels"] < 50


def test_180秒を境に長短を分ける():
    svc = _FakeSvc()
    got = peers.deep_pull(svc, ["UC1"], per_channel=50, max_units=500, now=NOW)
    assert {r["form"] for r in got["rows"]} == {"long"}      # PT20M ＝ 1200秒 > 180
    assert all(r["channel"] == "UC1" and r["q"] == "deep" for r in got["rows"])


def test_転んでも止めない():
    """1チャンネルで例外が出ても、集まった分は次の周が使えます。"""
    class _Boom(_FakeSvc):
        def list(self, **kw):
            if kw.get("id") == "UCBAD":
                raise RuntimeError("403")
            return super().list(**kw)

    got = peers.deep_pull(_Boom(), ["UCBAD", "UC1"], per_channel=50, max_units=500, now=NOW)
    assert got["channels"] == 1 and got["videos"] == 3


def test_同じch内の比は生の比と別に出る():
    """**この検査が、この回の当のものです** —— 生の比が大きくても、同じch内では消え得ること。

    `title_shape` の `paired` を生の比に差し替えると落ちる（陽性対照）。
    """
    rows = (
        # 大きいチャンネル: 全部 `【】` つき・再生は大きい（型と大きさが完全に重なる）
        [{"id": f"a{i}", "views": 100000, "channel": "BIG", "title": "【年金】損しない方法", "form": "long"}
         for i in range(4)]
        # 小さいチャンネル: `【】` の在る側と無い側が同じ数・再生は同じ
        + [{"id": f"b{i}", "views": 100, "channel": "SML", "title": "【年金】損しない方法", "form": "long"}
           for i in range(2)]
        + [{"id": f"c{i}", "views": 100, "channel": "SML", "title": "年金で損しない方法", "form": "long"}
           for i in range(2)]
    )
    d = peers.title_shape(rows)["【】"]
    assert d["raw"] > 100                 # 生は 1000倍 の桁（大きいチャンネルが全部 型を持つ）
    assert d["paired"] == pytest.approx(1.0, abs=0.01)   # 同じch内では 1.0 ＝ 効いていない


def test_門の先の距離は_RPM_の帯で出る():
    rows = [{"id": f"v{i}", "views": v, "channel": f"C{i}", "title": "x", "form": "long"}
            for i, v in enumerate([100, 60_000, 200_000, 500_000])]
    c = peers.capacity(rows)
    assert c["need"][1000.0] == 200_000               # 20万円 ÷ RPM1000 × 1000
    assert c["over"][1000.0] == 2                     # 200,000 と 500,000
    assert c["over_gate"] == 3                        # 60,000 以上（扉(b)）
    assert "月20万" in peers.capacity_line(rows)


def test_族ごとに天井がちがう():
    """ニッチは 1つ ではありません —— `q` で割ると中央値が桁で変わります。"""
    rows = ([{"id": f"a{i}", "views": 600_000, "channel": f"A{i}", "title": "x", "form": "long",
              "q": "年金 手取り いくら"} for i in range(12)]
            + [{"id": f"b{i}", "views": 200, "channel": f"B{i}", "title": "x", "form": "long",
                "q": "医療費控除 いくら戻る"} for i in range(12)])
    fs = peers.families(rows)
    assert fs[0]["q"] == "年金 手取り いくら" and fs[0]["median"] == 600_000
    assert fs[-1]["q"] == "医療費控除 いくら戻る"
    assert "3,000倍" in peers.family_line(rows)


def test_n_が門より少ない族は印字しない():
    """本数が少ない族の中央値は読まないこと（`FAMILY_MIN_N`・覆る条件 (3)）。"""
    rows = [{"id": f"a{i}", "views": 9_000_000, "channel": f"A{i}", "title": "x", "form": "long",
             "q": "うすい族"} for i in range(peers.FAMILY_MIN_N - 1)]
    assert peers.family_line(rows) == ""


def test_当たり前の語では族に入れない(tmp_path):
    """**「年金」1語 で入れると、族の表が「どの族も全部 持っている」と嘘をつきます。**

    `FAMILY_STOPWORDS` を空にするか `all(...)` を `any(...)` にすると落ちる（陽性対照）。
    """
    (tmp_path / "a.json").write_text(json.dumps(
        {"id": "a", "form": "long", "title": "年金を60歳から早くもらった人が失うもの3つ", "tags": ["年金"]},
        ensure_ascii=False), encoding="utf-8")
    got = peers.mine_by_family(tmp_path)
    assert got.get("年金 手取り いくら") == []          # 「手取り」が無いので入らない
