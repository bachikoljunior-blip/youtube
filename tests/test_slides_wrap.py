"""studio/slides.py の字幕の折り返し（語の切れ目で折る。09/06 19:5x・optimizer）。

実測 09/06 17:3x（hourly）: 字幕「国の決\\nまりで」が語の途中で折れた。09/05 の形は数字のかたまりだけを守っていた。
"""
from studio import slides


def _ok(lines, n):
    assert all(len(ln) <= n for ln in lines), lines
    assert all(ln[0] not in "、。」）" for ln in lines), lines


def test_語の途中で折らない():
    got = slides.wrap("70歳まで5年おくらせると国の決まりで42%増えます。", 16)
    _ok(got, 16)
    assert "".join(got) == "70歳まで5年おくらせると国の決まりで42%増えます。"
    assert not any(ln.endswith("決") for ln in got)


def test_数字のかたまりと助詞は前の語につく():
    got = slides.wrap("税金を引く前の金額で、65歳から毎月15万円の人を例にすると70歳からは42%増えて毎月21万3千円です。", 16)
    _ok(got, 16)
    assert not any(ln.endswith(("毎", "毎月", "1", "15万")) for ln in got)
    for ln in got:
        assert not ln.startswith(("の", "を", "は", "で", "に"))


def test_複合名詞と非自立は切らない():
    got = slides.wrap("自分の場合は毎年届くねんきん定期便の65歳の金額に42%を足すと70歳からの金額です。", 16)
    _ok(got, 16)
    assert not any(ln.endswith(("定期", "ねんきん")) for ln in got)
    got = slides.wrap("70歳の11年11か月あとは81歳11か月で65歳からもらい続けた人と合計が同じです。税金を引く前の話です。", 16)
    _ok(got, 16)
    assert not any(ln.endswith("もらい") for ln in got)


def test_句読点は行頭にも_n字を越えても置かない():
    say = "4月より前の51万円なら、同じ人は月10万5千円減っていました。今は5万円です。違いは月5万5千円、1年で66万円です。"
    for n in (16, 18):
        _ok(slides.wrap_chars(say, n), n)   # 旧の形は 17字 の行を作っていた
        _ok(slides.wrap(say, n), n)


def test_行数の上限で字の折りに落ちる():
    say = "あ" * 70
    assert len(slides.wrap(say, 18, max_lines=4)) == 4
    assert slides.wrap("大きい字\n二行目", 16) == ["大きい字", "二行目"]
