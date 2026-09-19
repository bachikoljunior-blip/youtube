"""**案件を差し替えた日に、入れ直しの口が静かに落ちないこと**（2026-09-20 03:xx・optimizer・Opus 5）。

**なぜ足したか**: `cli asp --published N` は `asp.has_block` で見送りを決めていました。
**`has_block` は「何か塊が在るか」しか見ません** ＝ **古い案件の塊を持つ本も
「もう入っています」に見えます。** ふだんは 2つ の答えが同じなので気づけません ——
**割れるのは、案件を差し替えた日だけ**で、それが
**オーナーの窓【2026-09-20 09:00〜10:00】（お墓・終活 の 2案件 への提携申請）**です。

**落ち方が静かなのが、この穴のたちの悪い所**です: 印字は「もう入っています」で正常、
台帳も鳴らず、**いちばん配られている本ほど古い案件のまま**になります
（入れ直しは再生の多い順）。
"""
from __future__ import annotations

import pytest

from studio import asp


@pytest.fixture()
def two_offers(monkeypatch):
    """案件 2つ（いまの `OFFERS` と同じ形）を、file に依らず置く。"""
    monkeypatch.setattr(asp, "offers", lambda: [
        ("https://af.moshimo.com/af/c/click?a_id=NEW1", "お墓のことを相談する"),
        ("https://af.moshimo.com/af/c/click?a_id=NEW2", "墓じまいの資料を取り寄せる"),
    ])
    return asp.block()


OLD = ("【PR】この動画は一般的な例です。自分の場合いくらになるかを相談したい方へ\n"
       "スマホのショートではこのURLは押せません。チャンネルのアイコンをタップ → 「リンク」から開けます。\n"
       "・老後のお金と保険を、専門家（FP）に無料で相談できます\n"
       "https://af.moshimo.com/af/c/click?a_id=OLD1\n"
       "・保険を売らない中立のFPに相談したい方はこちら（無料）\n"
       "https://af.moshimo.com/af/c/click?a_id=OLD2\n"
       "※上の2つは広告（アフィリエイト）です。")
BODY = "年金の手取りの回です。\n\n【前提】\n・65歳から受け取る人\n\n【出どころ】\n・日本年金機構"


def test_古い塊でも_has_block_は_True(two_offers):
    """**これが穴そのものです。** `has_block` は正しく動いていて、問いが違いました。"""
    assert asp.has_block(OLD + "\n\n" + BODY) is True


def test_古い塊は_block_is_current_で_False(two_offers):
    assert asp.block_is_current(OLD + "\n\n" + BODY) is False


def test_いまの塊は_block_is_current_で_True(two_offers):
    assert asp.block_is_current(two_offers + "\n\n" + BODY) is True


def test_塊が片方しか無ければ_False(two_offers):
    half = two_offers.replace("a_id=NEW2", "a_id=GONE")
    assert asp.has_block(half + "\n\n" + BODY) is True
    assert asp.block_is_current(half + "\n\n" + BODY) is False


def test_案件が一本も無い日は_True(monkeypatch):
    """直す先が無い日は、見送りが正しい（`compose` も素通し）。"""
    monkeypatch.setattr(asp, "offers", lambda: [])
    assert asp.block_is_current(OLD + "\n\n" + BODY) is True
    assert asp.block_is_current(None) is True


# --------------------------------------------------------------- strip_block

def test_頭の塊を外す():
    assert asp.strip_block(OLD + "\n\n" + BODY) == BODY


def test_尻の塊を外す():
    assert asp.strip_block(BODY + "\n\n" + OLD) == BODY


def test_塊が無ければ_None():
    assert asp.strip_block(BODY) is None
    assert asp.strip_block("") is None
    assert asp.strip_block(None) is None


def test_印だけで_host_が無い字は外さない():
    """**本文を切らないための門。** 「【PR】」は台本の側にも書けます。"""
    fake = "【PR】この回は広告ではありません\n\n" + BODY
    assert asp.strip_block(fake) is None


def test_外してから_compose_すると_いまの案件になる(two_offers):
    """**これが差し替えの日に通る道です。**"""
    live = OLD + "\n\n" + BODY
    assert asp.compose(live) == live, "古い塊が在ると `compose` は素通し（冪等の側）"
    stripped = asp.strip_block(live)
    got = asp.compose(stripped)
    assert asp.block_is_current(got)
    assert "a_id=OLD1" not in got and "a_id=OLD2" not in got
    assert BODY in got, "本文は 1字 も落ちないこと"


def test_外すのは一つだけ(two_offers):
    """2つ 入っている本が在れば、この file の外で何かが壊れています。
    **黙って全部 消すと、その壊れが見えなくなります。**"""
    doubled = OLD + "\n\n" + OLD + "\n\n" + BODY
    once = asp.strip_block(doubled)
    assert once == OLD + "\n\n" + BODY
    assert asp.has_block(once)


def test_compose_は本文を落とさない(two_offers):
    got = asp.compose(BODY)
    assert BODY in got and asp.block_is_current(got)
