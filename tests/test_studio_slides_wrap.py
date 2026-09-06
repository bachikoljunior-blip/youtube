"""studio/slides.py の字幕の折り（語の途中で折らない）。

実測 09/06 17:3x（hourly・Fable）: 16字で機械的に折ると「国の決\nまりで」と語の途中で折れた。
09/06 19:xx に janome で語を切り、助詞・助動詞・句読点・接尾・非自立は前の語に、接頭詞は次の語に
くっつけて折るようにした。数字のかたまり（15万円・11か月）は前からのとおり1語。
"""
from studio import slides


def _no_loss(say: str, n: int):
    lines = slides.wrap(say, n)
    assert "".join(lines) == say
    assert all(len(ln) <= n for ln in lines)
    return lines


def test_語の途中で折らない():
    lines = _no_loss("70歳まで5年おくらせると国の決まりで42%増えます。", 16)
    assert lines == ["70歳まで5年おくらせると国の", "決まりで42%増えます。"]


def test_助詞は行頭に来ない():
    for ln in _no_loss("65歳からの年金を70歳までおくらせるか迷う人へ。何歳まで生きれば得か計算します。", 16)[1:]:
        assert ln[0] not in "はがをにでとのもへか、。"


def test_数字の直後の助詞は数字にくっつく():
    # 数字の後の「で」「なら」は文脈が無いと接続詞に見えて、行頭に来ていた
    assert "1年で" in slides._chunks("違いは月5万5千円、1年で66万円です。")
    assert "12万円なら" in slides._chunks("厚生年金12万円なら合計52万円。")


def test_仮の数字が次の語を食わない():
    # 「3」を仮に置いて切ると「3多く」が1語になった → 字を落とさない
    lines = _no_loss("70歳からは21万3千円ひく15万円で毎月6万3千円多くもらえます。", 16)
    assert any("多く" in ln for ln in lines)


def test_ねんきん定期便は1語():
    assert "ねんきん定期便の" in slides._chunks("毎年届くねんきん定期便の65歳の金額に")


def test_もらい続けたは1語():
    assert "もらい続けた" in slides._chunks("65歳からもらい続けた人と")


def test_長すぎるかたまりは字で折る():
    lines = _no_loss("あ" * 40, 16)
    assert len(lines) == 3


def test_字で折るときも句読点で行が_n字を越えない():
    # 09/06 19:5x（optimizer）: 旧の _hang は行頭の「。」を前の行に足して 17字 の行を作っていた（60字 の字幕）
    say = "4月より前の51万円なら、同じ人は月10万5千円減っていました。今は5万円です。違いは月5万5千円、1年で66万円です。"
    for n in (16, 18):
        lines = slides._wrap_chars(say, n)
        assert "".join(lines) == say
        assert all(len(ln) <= n for ln in lines), lines
        assert all(ln[0] not in "、。" for ln in lines), lines
        assert all(ln[0] not in "、。" for ln in slides.wrap(say, n))
