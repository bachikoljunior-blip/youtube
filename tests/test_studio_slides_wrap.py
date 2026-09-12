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


def test_分数は1語():
    # 実測 09/09 15:5x（hourly・Fable）: 09/10 の本のコマ4 が「夫の厚生年金の4分の\n3です」と折れた（sheet.png）
    assert "4分の3です。" in slides._chunks("夫の厚生年金の4分の3です。")
    for ln in _no_loss("夫が亡くなりました。のこされた妻のくらしをささえるのが遺族厚生年金で、夫の厚生年金の4分の3です。", 16):
        assert not ln.endswith("分の")


def test_制度名の複合語は1語():
    # janome は 遺族/厚生/年金 と3語に割る → 「遺族厚生\n年金」と折れていた（同じコマ）
    ch = slides._chunks("ささえるのが遺族厚生年金で、夫の厚生年金の4分の3です。毎年6月の年金額改定通知書を見る")
    assert "遺族厚生年金で、" in ch and "厚生年金の" in ch and "年金額改定通知書を" in ch


def test_暦の月は1語():
    # 実測 09/10 01:2x（optimizer・Opus）: 09/11 の本のコマ8 が
    # 「はたらいているあいだに、毎年10\n月分の年金から足されます。」と折れた（sheet.png）。
    # 接尾の一覧に「か月」は在るのに、裸の「月」が無かった。
    assert slides._tokens("毎年10月分の")[:1] == ["毎年10月分"]
    assert slides._tokens("12月です")[:1] == ["12月"]
    say = "ふえた分は、70歳になってから受け取るのではありません。はたらいているあいだに、毎年10月分の年金から足されます。"
    for ln in _no_loss(say, 16):
        assert not ln.endswith("毎年10"), ln
        assert not ln.startswith("月分"), ln


def test_暦の月を1語にしても_既存のかたまりは割れない():
    # 01:2x の直し（接尾に「月分?」を足した）で、09/06・09/09 に足したかたまりが割れていないこと。
    # **これは順番の検査ではありません** —— 「月分?」を「か月」より前へ動かす陽性対照を撃ったら
    # 12件とも通りました（`月` は「か」に当たれないので、そこで必ず `か月` へ落ちる）。
    # 註に「か月 より後ろでないと割れる」と書きかけて、対照が落ちなかったので消しています（§5 の教訓の形3つ目）。
    assert slides._tokens("12か月はたらくと")[:1] == ["12か月"]
    assert slides._tokens("6か月で")[:1] == ["6か月"]
    # 09/06・09/09 に足した既存のかたまりが、この直しで割れていないこと
    assert slides._tokens("毎月15万円の")[:1] == ["毎月15万円"]
    assert slides._tokens("約5万5千円です")[:1] == ["約5万5千円"]
    assert slides._tokens("4分の3です")[:1] == ["4分の3"]


def test_国民年金と付加年金も1語():
    # 実測 09/12 12:5x（hourly・Fable）: 09/13 の本の字幕で コマ1「国民\n年金だけの人へ」・コマ10「国民\n年金のうえに」と折れた（sheet.png）。
    # janome は 国民/年金 と割る。国民年金基金 は 国民年金＋基金 に割れないよう、長い順に置く
    ch = slides._chunks("自営業やフリーランスで、国民年金だけの人へ。国民年金基金という別の上乗せに入っている人は、はらえません。付加年金が用意されました。")
    assert "国民年金だけの" in ch and "国民年金基金という" in ch and "付加年金が" in ch
    for ln in _no_loss("自営業やフリーランスで、国民年金だけの人へ。毎月400円で年金がいくらふえて、何年でもとがとれるか計算します。", 16):
        assert not ln.endswith("国民")
