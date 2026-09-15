# -*- coding: utf-8 -*-
"""`hear.plain_probe` —— **漢字を禁じた聞き取りの切り落としを、禁じない側で裏取りする**
（2026-09-15 19:4x・optimizer）。derivation と覆る条件は `studio/hear.py` の同名の段。

**陽性対照 2つ**:
  (A) 禁じない側にも落ちた所が無ければ `ok` は立たない（＝ この口は何でも「在る」と言わない）
  (B) 門（`cover`）を 1.0 に上げると、同じ音で `ok` が消える
"""
from pathlib import Path

from studio import hear


class FakeHearer:
    """`transcribe_plain` だけを持つ替え玉（模型も音も要らない ＝ API 0単位）。"""

    def __init__(self, plain: str):
        self._plain = plain

    def transcribe_plain(self, wav):
        return self._plain


WAV = Path("dummy.wav")
YOMI: dict[str, str] = {}


def test_落ちた所が禁じない側に在れば_ok():
    """実物: コマ37 の「登録しておくと、あすの分がとどきます」が、禁じる側で空・禁じない側で全部。"""
    h = FakeHearer("年金と税金のこういう計算を毎日出しています 登録しておくと明日の分が届きます")
    r = hear.plain_probe(h, WAV, "とうろくしておくとあすのぶんがとどきます", YOMI)
    assert r["ok"] and r["cover"] >= 0.7


def test_陽性対照A_禁じない側にも無ければ_okは立たない():
    h = FakeHearer("年金と税金のこういう計算を毎日出しています")
    r = hear.plain_probe(h, WAV, "とうろくしておくとあすのぶんがとどきます", YOMI)
    assert not r["ok"]


def test_陽性対照B_門を1にすると消える():
    h = FakeHearer("年金と税金のこういう計算を毎日出しています 登録しておくと明日の分が届きます")
    loose_ok = hear.plain_probe(h, WAV, "とうろくしておくとあすのぶんがとどきます", YOMI)
    strict = hear.plain_probe(h, WAV, "とうろくしておくとあすのぶんがとどきます", YOMI, cover=1.0)
    assert loose_ok["ok"] and not strict["ok"]


def test_落ちた所が空なら_okは立たない():
    h = FakeHearer("なんでもよい")
    r = hear.plain_probe(h, WAV, "", YOMI)
    assert not r["ok"] and r["cover"] == 0.0


def test_一致の数は変えない():
    """この口は印字だけ —— `check` の `diffs` に触っていないこと（決めるのは Fable・§4 (2)）。"""
    import inspect
    src = inspect.getsource(hear.check)
    assert 'row["plain"] = plain_probe(' in src
    # plain の結果で diffs を書き換えていない
    assert "diffs = plain" not in src and 'row["diffs"] = ' not in src
