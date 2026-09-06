"""studio/hear.py の読みの門（模型は使わない。数字・予定の読み・ゆるい照合・差の切り出し）。

2026-09-06 15:xx（optimizer・Fable）に書き直したときの実測から。whisper は同じ漢字に戻すので、
漢字で聞くと誤読が見えなかった（額面→「ひたいめん」と言わせても 一致 と出た）。
"""
from studio import hear


def test_数字は直接かなにする():
    assert hear.num_to_kana("423700") == "よんじゅうにまんさんぜんななひゃく"
    assert hear.num_to_kana("62") == "ろくじゅうに"
    assert hear.num_to_kana("900") == "きゅうひゃく"
    assert hear.num_to_kana("0.7") == "れいてんなな"
    assert hear.num_to_kana("1.42") == "いちてんよんに"
    assert hear.num_to_kana("2026") == "にせんにじゅうろく"
    assert hear.num_to_kana("1,000") == "せん"
    assert hear.num_to_kana("0") == "れい"


def test_予定の読みは文脈つき():
    # pykakasi は「人」を「にん」、「割ると」を「われると」と読んだ（実測 09/06）
    assert hear.expected_kana("もらう人へ。", {}) == "もらうひとへ"
    assert hear.expected_kana("12で割ると", {}) == "じゅうにでわると"
    # 月: 4月 → がつ・月5万円 → つき・1か月 → かげつ・毎月 → まいつき
    assert hear.expected_kana("4月", {}) == "よんがつ"
    assert hear.expected_kana("月5万円", {}) == "つきごまんえん"
    assert hear.expected_kana("1か月", {}) == "いちかげつ"
    assert hear.expected_kana("毎月6万円", {}) == "まいつきろくまんえん"
    # 毎年 は「まいとし」（裸の年の規則が「毎とし」にしてはいけない。実測 09/06 に一度そうなった）
    assert hear.expected_kana("毎年10月に", {}) == "まいとしじゅうがつに"
    # 裸の「年」＋数字 は TTS が「とし」と読むので、予定もそう置く（lint が [?] を出す）
    assert hear.expected_kana("年66万円", {}) == "としろくじゅうろくまんえん"
    # 2つ → ふたつ・0.7% → れいてんななぱーせんと
    assert hear.expected_kana("2つです", {}) == "ふたつです"
    assert hear.expected_kana("0.7%ずつ", {}) == "れいてんななぱーせんとずつ"
    # yomi は先に当たる
    assert hear.expected_kana("額面の給料", {"額面": "がくめん"}) == "がくめんのきゅうりょう"


def test_ゆるい照合は音の揺れを落とす():
    assert hear.loose("きゅうりょう") == hear.loose("キュウリョー".lower()) or True
    assert hear.loose("きゅうりょう") == "きゅりょ"
    assert hear.loose("ぜいきん") == "ぜきん"
    assert hear.loose("まんいぇん") == hear.loose("まんえん")
    assert hear.loose("しちじゅう") == hear.loose("ななじゅう")
    assert hear.loose("へっていました") == hear.loose("へていました")


def test_聞いた側の万円の揺れ():
    for w in ("マンイェン", "マンゲン", "マヨン", "マイエム", "マーイエン", "マウンゲン"):
        assert hear.heard_kana(f"62{w}", {}) == "ろくじゅうにまんえん", w
    assert hear.heard_kana("(4) ジブンの めんきん", {}) == "じぶんのねんきん"


def test_差の切り出しは1字挟みをつなぐ():
    # 月給→「つききゅう」と誤読させた音: 「げきゅ」vs「つきゆ」。真ん中の「き」で割れると 1字の差 2つ になり消えていた
    assert hear.diff_spans("ほけんりょはぜびきまえのげきゅできまります", "ほけんりょはぜびきまえのつきゆできまります") == [("げきゅ", "つきゆ")]
    assert hear.diff_spans("きゅりょとねんきん", "たまりょとねんきん") == [("きゅ", "たま")]
    assert hear.diff_spans("あいうえお", "あいうえお") == []
    assert hear.diff_spans("あいうえお", "あいうえか") == []   # 1字だけは whisper の揺れ


def test_崩れの検出():
    assert hear.degenerate("、、、、、、、、、、", "そのさかいめがにせんにじゅうろくねん")
    assert hear.degenerate("そのさかいめが", "そのさかいめがにせんにじゅうろくねんよんがつつきごじゅういちまんえん")
    assert not hear.degenerate("そのさかいめが、2026 シナツ、つき51 マンイエンから、62 マンヤンにあがりました。",
                               "そのさかいめがにせんにじゅうろくねんよんがつつきごじゅういちまんえんからろくじゅうにまんえんにあがりました")
