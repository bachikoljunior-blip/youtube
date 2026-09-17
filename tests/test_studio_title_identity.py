"""**題の身元 ＝ 名前 × 制度名**（`peers.title_identity` / `yt.set_channel_title` /
`cli.cmd_rename_channel`・2026-09-17 02:xx・optimizer・Fable 5.1・ultracode）。

**陽性対照を先に置いてあります** —— 「鳴らない」だけの検査は、口を外しても通るので。
"""
from __future__ import annotations

import pytest

from studio import peers


# ---- 印そのもの（字面の読み分け）--------------------------------------------

@pytest.mark.parametrize("title,named,topic", [
    ("お金と仕事の教科書", False, False),          # うち ＝ 広い語だけ・名乗る人が居ない
    ("タヌキの年金相談室", True, True),
    ("としこの年金相談所", True, True),
    ("きな子のシニアお金ゼミ", True, True),
    ("年金・給付金完全攻略チャンネル", False, True),
    ("サラダのお金相談所", True, False),           # 名前は在るが制度名が無い
    ("サンデーマネーチャンネル", False, False),
])
def test_升の割り振りは題の字面で決まる(title, named, topic):
    assert bool(peers.PERSONA_RE.match(title)) is named
    assert bool(peers.TOPIC_NARROW_RE.search(title)) is topic


def test_陽性対照_広い語は制度名に数えない():
    """**`お金`/`マネー` を制度名に数えると、うちが `plain_topic` の升へ入ります。**
    その混ぜが、この口の答えを丸ごと変える所です。"""
    assert peers.TOPIC_BROAD_RE.search("お金と仕事の教科書")
    assert not peers.TOPIC_NARROW_RE.search("お金と仕事の教科書")


def test_陽性対照_肩書きの口は升から外れている():
    """うちに閉じている腕（`CRED_RE`）が升に混ざると、取れない効きを取れる効きとして読みます。"""
    for t in ("元ハローワーク職員ケンの退職サポート", "あき姉 元銀行員FPが教える資産形成術"):
        assert peers.CRED_RE.search(t)


# ---- 2×2 そのもの -----------------------------------------------------------

def test_4つの升が出て_うちの升がいちばん低い():
    p = peers.title_identity()
    if not p.get("n"):
        pytest.skip("corpus が在りません")
    c = p["cells"]
    assert set(c) == {"named_topic", "named_plain", "plain_topic", "plain_plain"}
    spd = {k: v.get("spd") for k, v in c.items() if v.get("spd") is not None}
    assert "plain_plain" in spd, "うちの居る升が床（CELL_MIN_CH）を下回っています"
    assert min(spd, key=spd.get) == "plain_plain", "うちの升がいちばん低くないなら、この節の前提が覆っています"


def test_床を下回る升は数を出さない():
    p = peers.title_identity()
    if not p.get("n"):
        pytest.skip("corpus が在りません")
    for v in p["cells"].values():
        if v["n"] < peers.CELL_MIN_CH:
            assert "spd" not in v


def test_行は門の倍率を出す():
    line = peers.title_identity_line("お金と仕事の教科書", need_spd=11.1)
    assert "plain_plain" in line and "11.1人/日" in line and "倍 足りません" in line


def test_陽性対照_目当ての升の題では倍率の行が出ない():
    """升の外に居ることを言う行なので、**入ったら消えなければなりません**。"""
    line = peers.title_identity_line("タヌキの年金相談室", need_spd=11.1)
    assert "named_topic" in line and "倍 足りません" not in line


# ---- 撃つ側（`--dry-run` は 0単位）-------------------------------------------

def test_肩書きの題は撃つ前に止まる():
    from studio import cli
    a = type("A", (), {"title": "元社労士ゆきの年金相談室", "dry_run": True, "anyway": False})()
    assert cli.cmd_rename_channel(a) == 1


def test_升の外の題は_anyway_なしでは撃たない():
    from studio import cli
    a = type("A", (), {"title": "お金と仕事の教科書2", "dry_run": True, "anyway": False})()
    assert cli.cmd_rename_channel(a) == 1


def test_升の中の題は_dry_run_で通る():
    from studio import cli
    a = type("A", (), {"title": "カワウソの年金計算室", "dry_run": True, "anyway": False})()
    assert cli.cmd_rename_channel(a) == 0


def test_題を書く口は読んでから書き_書いた返りで読み返す():
    """`channels.update` は渡した部を**丸ごと置き換えます** ——
    読まずに書くと `keywords` と `unsubscribedTrailer`（紹介動画）が黙って消えます。

    **2026-09-17 17:2x（optimizer・Fable 5.1・ultracode）に、読み返しの口を替えました。**
    ここは **`channels().list` が 2回**（書く前 ＋ 読み返し）であることを見ていましたが、
    **その 2回目 は遅れた複製から返ります** —— 実測（この回の実物・`9WdbGJaI2hU`）:
    `videos.update` の直後の `videos.list` は **旧の題**、**45秒 後**は新しい題。
    ＝ **直後の読み返しは「落ちた」の偽陰性**で、`list` の回数は正しさの印ではありません。
    いまは `update` の**返り**で読み返します（**1単位 安く、複製の遅れを踏まない**）。
    中身の検査は `tests/test_studio_readback_from_response.py`（陽性対照つき）。
    """
    import inspect

    from studio import yt
    src = inspect.getsource(yt.set_channel_title)
    assert 'part="brandingSettings", mine=True' in src, "読まずに書いています"
    assert src.count("channels().list") == 1, \
        "`channels.list` が 2回 ＝ 読み返しを遅れた複製から引いています（1単位 も無駄）"
    assert "resp = svc().channels().update(" in src, "書いた返りを受け取っていません"
    assert "resp.get(\"brandingSettings\")" in src, "読み返しが `update` の返りから出ていません"
    assert '"ok": after == title' in src


# ---- config の題 対 YouTube 側の題（`trend.channel_title_drift_line`・API 0単位）----

def _ch(at: str, title=None):
    r = {"event": "channel", "id": "UC1", "at": at, "subs": 1, "views": 1, "videos": 1}
    if title is not None:
        r["title"] = title
    return r


def test_題を持つ行が無ければ_まだ数えられないと言う():
    from studio import trend
    line = trend.channel_title_drift_line([_ch("2026-09-16T21:00:00+09:00")], "お金と仕事の教科書")
    assert "まだ数えられません" in line and "ずれ" not in line


def test_一致していれば一致と言う():
    from studio import trend
    rows = [_ch("2026-09-17T03:00:00+09:00", "お金と仕事の教科書")]
    assert "**一致**" in trend.channel_title_drift_line(rows, "お金と仕事の教科書")


def test_陽性対照_ずれたら鳴る():
    """**鳴らない側だけの検査は、口を外しても通ります。**"""
    from studio import trend
    rows = [_ch("2026-09-17T03:00:00+09:00", "カワウソの年金計算室")]
    line = trend.channel_title_drift_line(rows, "お金と仕事の教科書")
    assert line.startswith("!!") and "うちではない題" in line


def test_いちばん新しい行を読む():
    from studio import trend
    rows = [_ch("2026-09-17T03:00:00+09:00", "むかしの題"),
            _ch("2026-09-17T05:00:00+09:00", "いまの題")]
    assert "いまの題" in trend.channel_title_drift_line(rows, "いまの題")


def test_台帳に題を残している_追加0単位():
    """`yt.channel()` が既に返している欄なので、残すのに単位は増えません。"""
    import inspect

    from studio import cli, yt
    assert '"title": ch["snippet"]["title"]' in inspect.getsource(yt.channel)
    assert 'title=ch.get("title")' in inspect.getsource(cli.record_channel)
