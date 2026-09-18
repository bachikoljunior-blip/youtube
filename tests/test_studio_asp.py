"""`studio/asp.py`（成果報酬のリンクを説明欄に入れる一点）の検査。

2026-09-18 20:3x・optimizer。**何を守っているか**:
 (1) **冪等** —— 2度 通しても塊は 1つ（`verify_meta` は同じ本に何度も `update_meta` を撃つ）
 (2) **表示の決まり**（ステマ規制）—— `【PR】` と「アフィリエイト」の 2語 が必ず出る
 (3) **口の側に入っていること** —— `yt.upload` と `yt.update_meta` が `asp.compose` を通す
     （通さない口が 1つ でも在れば、その本だけ分子が 0 になります）
 (4) **比べる側も同じ字を見ていること** —— `cli.drift_fields` が生の台本と比べると、
     上がっている本が毎周「食い違い」に見えて 50単位 が空撃ちされます
 (5) 案件が 0本 のときは素通し（`asp_links.json` が無い環境でも道具は止まらない）
"""
from __future__ import annotations

import inspect

from studio import asp, cli, yt


def test_塊には広告の表示が在る():
    b = asp.block()
    assert b, "案件が 0本（data/studio/asp_links.json）"
    assert "【PR】" in b
    assert "アフィリエイト" in b
    assert "af.moshimo.com" in b


def test_冪等():
    once = asp.compose("本文")
    assert asp.compose(once) == once
    assert once.count("【PR】") == 1


def test_上に入る():
    out = asp.compose("本文です")
    assert out.startswith("【PR】")
    assert out.endswith("本文です")


def test_下にも置ける():
    out = asp.compose("本文です", top=False)
    assert out.startswith("本文です")
    assert "【PR】" in out


def test_案件が0本なら素通し(monkeypatch):
    monkeypatch.setattr(asp, "OFFERS", [])
    assert asp.compose("本文") == "本文"
    assert asp.block() == ""


def test_youtube_okがfalseの案件は出さない(monkeypatch):
    bad = {k: {**v, "youtube_ok": False} for k, v in asp.links().items()}
    monkeypatch.setattr(asp, "links", lambda: bad)
    assert asp.offers() == []


def test_口の両方がcomposeを通している():
    for fn in (yt.upload, yt.update_meta):
        src = inspect.getsource(fn)
        assert "asp.compose(description)" in src, f"{fn.__name__} が塊を通していません"


def test_比べる側もcomposeを通している():
    for fn in (cli.drift_fields, cli.desc_appended):
        assert "asp.compose(" in inspect.getsource(fn), f"{fn.__name__} が生の台本と比べています"


def test_食い違いは塊を入れた字で判定される():
    class S:
        title = "題"
        description = "本文"
        tags = ["a"]

    live = {"title": "題", "description": asp.compose("本文"), "tags": ["a"]}
    assert cli.drift_fields(live, S()) == []
    assert cli.drift_fields({**live, "description": "本文"}, S()) == ["説明欄"]


def test_後ろに足された橋は食い違いにならない():
    class S:
        title = "題"
        description = "本文"
        tags = ["a"]

    live = {"description": asp.compose("本文") + "\n\n【くわしい計算（長尺）】\nhttps://youtu.be/x"}
    assert cli.desc_appended(live, S()).startswith("【くわしい計算")


def test_上限を越えたら台本の側を落とす():
    """**塊は落とさない**（落とすと、その本だけ分子が 0 になる）。"""
    long = "あ" * 6000
    out = asp.compose(long)
    assert len(out) <= asp.LIMIT
    assert out.startswith("【PR】")
    assert "af.moshimo.com" in out
    assert out.endswith("…")


def test_上限の中なら1字も落とさない():
    d = "本文\n" * 100
    out = asp.compose(d)
    assert d.strip() in out


def test_入れ直しの蓋は実測で取る():
    """推計（`budget.spent`）は台帳に `units` を書かない口を数えず、**必ず小さく出ます**。

    2026-09-18 の実測: 推計 8,756 対 実測 9,126（差 370単位 ＝ 7本ぶん）。
    推計だけで蓋を取ると「12本 撃てる」と出て、日枠を使い切ります
    （`budget` の覆る条件 (1)「この行を信じて枠を使い切らないこと」）。
    """
    src = inspect.getsource(cli.cmd_asp)
    assert "meter.spent(" in src
    assert "max(est, real)" in src


def test_入れ直しは台帳に印を残す():
    """説明欄を**前に足す**形は前方一致では引けない（`cli.desc_appended` の覆る条件 (1)）。"""
    assert '"redescribed"' in inspect.getsource(cli.cmd_asp)
