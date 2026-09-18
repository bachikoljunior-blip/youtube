"""**ショートの配りを決めている数（見られた割合・長さ）** を毎周 印字すること。

**足した理由**（2026-09-18 12:4x・optimizer・Opus）:
前の周（11:1x）が **面 12回/本** を見つけ、盤に置きました。その口は正しいのですが、
**自分で「ショートの配りを見ません」と書いています**（`channel_reach` の註・面 ÷ 再生 11.3%）。
**うちの流入は SHORTS 93.9%** です ＝ **再生のほぼ全部を決めている側について、
盤は数を 1つ も持っていませんでした。**

しかも、その数は**ずっと台帳の中に在りました** ——`channel_basic_a3` の行の
`watch_time_minutes` と `average_view_duration_percentage`。
`studio/` の中の参照を数えると **0件**（この回に `grep` した）。

実測（窓 20260811〜20260912・168本）:
    見られた割合の中央 **51%**・長さの中央 **8秒**
    割合 26% の本は平均 **114回**、62% の本は平均 **669回** ＝ **5.9倍**
    長さ 5.3秒 の本は平均 196回、11.1秒 の本は平均 **863回** ＝ **4.4倍**
＝ **前の周の「ショートの配りは籤」は外れ**（籤ではなく、測れる変数が 2つ）。

この検査が守るのは 4つ:
  (1) 割合は **views で重みを付ける**（行は国・登録の有無で割れており、
      1回 の行と 900回 の行を等しく平均すると国の数のほうへ寄る）。
  (2) 100% を越える行（再視聴）を**落とさない**——上の段へ上がる印そのもの。
  (3) `status` と `trend` の**両方**に行が在る（固定2 は `status` で最初に答える問い）。
  (4) 数えられない回に**黙らない**（「0」と「無い」を同じ字にしない族）。
"""
import json

from studio import reporting as R


def row(vid, views, pct, wmin, created="2026-09-13T00:00:00Z", **kw):
    return {"date": "20260901", "video_id": vid, "views": str(views),
            "average_view_duration_percentage": str(pct),
            "watch_time_minutes": str(wmin), "_created": created, **kw}


def _forms(tmp_path, monkeypatch, mapping):
    """`_forms` の出どころ（`data/uploaded.jsonl`）を tmp へ差し替える。"""
    up = tmp_path / "uploaded.jsonl"
    up.write_text("".join(json.dumps({"video_id": v, "title": t}, ensure_ascii=False) + "\n"
                          for v, t in mapping.items()), encoding="utf-8")
    monkeypatch.setattr(R, "_UPLOADED", up)


def test_割合はviewsで重みを付ける(tmp_path, monkeypatch):
    """**1回 の行と 900回 の行を等しく平均しないこと。**

    本物の形（`latest_rows` の註）: 1本1日 が 国・登録の有無 で **6行** に割れます。
    素の平均だと、**再生 1回 の ZZ の行**が **900回 の JP の行**と同じ重さになり、
    割合が「国の数」のほうへ寄ります（＝ 手の選び方を変える向きに外れる）。
    """
    _forms(tmp_path, monkeypatch, {"a": "x #Shorts"})
    rows = [row("a", 900, 60.0, 90.0, country_code="JP"),
            row("a", 1, 5.0, 0.01, country_code="ZZ")]
    d = R.watched(rows, min_views=1)
    # views 加重 = (60*900 + 5*1) / 901 ≒ 59.94。素の平均なら 32.5。
    assert 59.0 < d["watched_median"] < 60.5, d["watched_median"]


def test_再視聴の100超を落とさない(tmp_path, monkeypatch):
    """ショートの **100% 超（再視聴）は、次の段へ上がる印そのもの**（`watched` の覆る条件 (3)）。

    ここで捨てると、**いちばん見たい本だけが盤から消えます。**
    """
    _forms(tmp_path, monkeypatch, {"a": "x #Shorts", "b": "y #Shorts",
                                   "c": "z #Shorts"})
    rows = [row("a", 100, 150.0, 25.0), row("b", 100, 40.0, 6.7),
            row("c", 100, 50.0, 8.3)]
    d = R.watched(rows, min_views=1)
    assert d["n_short"] == 3
    # 3本 の割合は 150 / 40 / 50 ＝ **中央 50**。150 を落としていたら中央は 45 になります。
    assert abs(d["watched_median"] - 50.0) < 0.5, d["watched_median"]
    # いちばん上の段が**平均には残る**こと（五分位を作れない小ささなので直に確かめる）。
    assert d["len_median"] > 0


def test_ショートと長尺を分ける(tmp_path, monkeypatch):
    """題の `#Shorts` で分けます（`_forms` の覆る条件 (4)）。**混ぜると 8秒 と 200秒 が
    同じ中央値に入り、どちらの手も選べません。**"""
    _forms(tmp_path, monkeypatch, {"s1": "a #Shorts", "s2": "b #Shorts",
                                   "L1": "【長尺】c"})
    rows = [row("s1", 100, 50.0, 8.3), row("s2", 100, 50.0, 8.3),
            row("L1", 100, 50.0, 250.0)]
    d = R.watched(rows, min_views=1)
    assert d["n_short"] == 2 and d["n_long"] == 1
    assert d["len_median"] < 30            # ショート側に長尺が混ざっていない


def test_数えられない回に黙らない():
    """**「0本」と「読めなかった」を同じ字にしないこと**（この repo で何度も踏んだ族）。

    `watched_line` は空でも 1行 返し、`watched_short` は空文字（`status` の行を増やさない）。
    """
    d = R.watched([])
    assert d["n_short"] == 0
    assert "1本も在りません" in R.watched_line([])
    assert R.watched_short([]) == ""


def test_statusと_trendの両方に行が在る():
    """**固定2 は `status` で最初に答える問い** ＝ `trend` にしか無い行は間に合いません。

    `trial_reach_short` と同じ理由（そちらの検査と対）。
    """
    src = (R.Path("studio/cli.py")).read_text(encoding="utf-8")
    assert "watched_short()" in src      # status の側
    assert "watched_line()" in src       # trend の側


def test_天井の数は1か所(tmp_path, monkeypatch):
    """**歴代の天井（1,891回）は写しです** ——破られた回に、この 1か所 だけを直すこと。

    印字の中に数を直に書くと、**破られても字が残ります**（この repo の「凍る盤」族）。
    """
    _forms(tmp_path, monkeypatch, {"a": "x #Shorts", "b": "y #Shorts",
                                   "c": "z #Shorts"})
    rows = [row("a", 100, 50.0, 8.3), row("b", 200, 60.0, 20.0),
            row("c", 300, 40.0, 20.0)]
    monkeypatch.setattr(R, "CEILING_VIEWS", 4242)
    assert "4242" in R.watched_short(rows)
    assert "4242" in R.watched_line(rows)
