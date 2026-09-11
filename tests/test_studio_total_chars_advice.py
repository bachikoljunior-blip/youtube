"""`MAX_TOTAL_CHARS` の助言文が、門の本当の理由を言っていること（2026-09-11 11:2x・hourly・Opus）。

門（480字）は **build が測る秒数の上限（`cli.MAX_SECONDS` ＝ 95秒）の代理**です。
助言文は 09/11 まで「**60秒に収まらない**」と言っており、`docs/METHOD.md` §2 の
「60秒を越えてよい理由: 分かる説明に要る長さを削らない」と**逆を向いていました**。

`docs/METHOD.md` §3 の 9 に同じ族の実測が在ります —— `BARE_YEAR` の regex は正しく、
**`lint` の助言文だけ**が「『年に』に書き換えろ」と言い、書き手はそのとおり書いて hear 5/11 で落ちた。
**書き手は助言に従うので、門を直しても助言が古ければ同じ本がまた出ます。**
だから助言文の側にも検査を置きます（`tests/test_studio_bare_year_ni.py` と同じ形）。
"""
from studio import cli, script


def _script(total_chars: int) -> script.Script:
    """say の合計が total_chars ちょうどの本を作る（1コマ MAX_SAY 以下に割る）。"""
    segs, left = [], total_chars
    while left > 0:
        n = min(script.MAX_SAY, left)
        segs.append(script.Segment(say="あ" * n, show="x", sub=""))
        left -= n
    return script.Script(id="t-1", date="2026-09-11", title="t #Shorts",
                         takeaway="t", segments=segs)


def _advice(total_chars: int) -> str:
    got = [p for p in _script(total_chars).problems() if "合計" in p]
    assert len(got) == 1, got
    return got[0]


def test_門を越えたら鳴る():
    assert _advice(script.MAX_TOTAL_CHARS + 1)


def test_門ちょうどは鳴らない():
    assert not [p for p in _script(script.MAX_TOTAL_CHARS).problems() if "合計" in p]


def test_助言は60秒を門だと言わない():
    """**この検査が本体です。** 「60秒」を門として名指すと、書き手は 95秒 の本を半分に削ります。"""
    a = _advice(script.MAX_TOTAL_CHARS + 1)
    assert "60秒に収まらない" not in a
    assert "60秒の門ではありません" in a


def test_助言が本当の出どころを名指す():
    a = _advice(script.MAX_TOTAL_CHARS + 1)
    assert "MAX_SECONDS" in a          # 秒数の上限が在る所
    assert "60〜95秒" in a              # §2 の帯


def test_助言に実際の字数と門が両方出る():
    a = _advice(script.MAX_TOTAL_CHARS + 3)
    assert str(script.MAX_TOTAL_CHARS + 3) in a
    assert str(script.MAX_TOTAL_CHARS) in a


def test_門は秒数の上限の代理である():
    """480字 が 95秒 の域に在ること（`MAX_TOTAL_CHARS` の註の数）。

    実測の帯は 4.82〜5.16 字/秒（§2・09/05 と 09/07）。門の字数をこの帯で割った秒数が、
    `MAX_SECONDS` をまたいでいれば「代理」として成り立っています。
    ここが外れたら、直すのは助言文ではなく `MAX_TOTAL_CHARS` のほうです。
    """
    fast, slow = 5.16, 4.82        # 字/秒
    assert script.MAX_TOTAL_CHARS / fast <= cli.MAX_SECONDS <= script.MAX_TOTAL_CHARS / slow


def test_陽性対照_助言を60秒へ戻すと落ちる(monkeypatch):
    """**壊したら落ちる**ことを撃つ（§5 の教訓の形 3つ目）。"""
    orig = script.Script.problems

    def broken(self):
        return [p.replace("60秒の門ではありません", "60秒に収まらない") for p in orig(self)]

    monkeypatch.setattr(script.Script, "problems", broken)
    a = _advice(script.MAX_TOTAL_CHARS + 1)
    assert "60秒に収まらない" in a and "60秒の門ではありません" not in a
