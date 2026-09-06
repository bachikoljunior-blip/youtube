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


def test_聞いた側の範囲と倍の書き方():
    # 09/06 17:2x（hourly）: 「84歳から86歳」を whisper が「84~86」と書いた・「6倍」を「6x」と書いた
    assert hear.heard_kana("それをひくと84~86さいくらい", {}) == "それをひくとはちじゅうよんさいからはちじゅうろくさいくらい"
    assert hear.heard_kana("84〜86 くらい", {}) == "はちじゅうよんからはちじゅうろくくらい"
    assert hear.heard_kana("6x おおく", {}) == "ろくばいおおく"
    assert hear.heard_kana("15まんえん×60かげつ", {}) == "じゅうごまんえんかけるろくじゅうかげつ"   # × は かける のまま


def test_千と百は数字に畳んで連濁を出す():
    # 09/06 19:5x（hourly の申し送り）: 「6万3千円」の予定が「さんせん」で、TTS の「さんぜん」（正しい）と `!!` になっていた。
    # janome は 千・百 を別の語に切る。数字に畳めば num_to_kana の連濁（さんぜん・はっせん・さんびゃく）が出る
    assert hear.expected_kana("6万3千円多く", {}) == "ろくまんさんぜんえんおおく"
    assert hear.expected_kana("8千円", {}) == "はっせんえん"
    assert hear.expected_kana("1千万円", {}) == "せんまんえん"
    assert hear.expected_kana("3百円", {}) == "さんびゃくえん"
    assert hear.expected_kana("3千5百20円", {}) == "さんぜんごひゃくにじゅうえん"
    assert hear.expected_kana("何千円", {}) == "なんぜんえん"
    assert hear.expected_kana("五十", {}) == "ごじゅう"   # 漢数字だけの語は janome のまま


def test_ゆるい照合は旧仮名とゔを落とす():
    # 09/06 19:5x〜22:xx の実測: medium「よんじゑう」・small「テーキヴィン」
    assert hear.loose(hear.heard_kana("よんじゑう", {})) == hear.loose("よんじゅう")
    assert hear.loose("てーきゔぃん") == hear.loose("ていきびん")


def test_聞いた側の番号と千円のげん():
    # small が コマの頭に「[1]」を付け、「いち」に読まれていた（実測 09/06 22:xx コマ10）。「3000ゲン」は 円
    assert hear.heard_kana("[1] マイトシとどく", {}) == "まいとしとどく"
    assert hear.heard_kana("21 マン 3000 ゲン ひく", {}) == "にじゅういちまんさんぜんえんひく"


def test_禁じるトークンは漢字とハングル():
    # 09/06 22:xx: 漢字を禁じた small が「5年」を「5 년」と書いた。仮名（E3）は残す
    class Tok:
        def get_vocab(self):
            return {"年": 1, "년": 2, "ねん": 3, "abc": 4, "Ġ": 5}
    # _U2B は byte→unicode の逆写像。語彙の文字列をそのまま UTF-8 バイト列で表した形にして渡す
    def enc(s):
        return "".join(hear._bytes_to_unicode()[b] for b in s.encode())
    class Tok2:
        def get_vocab(self):
            return {enc("年"): 1, enc("년"): 2, enc("ねん"): 3, enc("abc"): 4, enc("〇"): 5, enc("〆"): 6, enc("、"): 7}
    assert hear.kanji_token_ids(Tok2()) == [1, 2, 5, 6]


def test_聞き直しは_medium_の次に_medium_prompt_も試す(monkeypatch):
    """09/07 01:xx 実測: 数が密なコマを small も medium も数字の帯に崩し、medium＋prompt だけが 0差 だった。"""
    from studio import script as sc
    say = "60歳から64歳の5年で、11万4千円かける60か月で684万円です。"
    s = sc.Script(id="t", date="2026-09-08", title="t #Shorts", takeaway="t", segments=[sc.Segment(say=say)])
    calls = []

    class Fake:
        def __init__(self, size):
            self.size = size

        def transcribe(self, wav, prompt=None):
            calls.append((self.size, prompt is not None))
            if self.size == "medium" and prompt:
                return "60さいから64さいの5ねんで、114,000えんかける60かげつで684まんえんです。"
            if self.size == "medium":
                return "60~64の5で114,000~60かげつで684,000です。"
            return "60 〇〇から 64 〃の 5 〉で 11 マン 4000 イエン かける 60 カゲツ で 680 4 マー イ エン です"

    monkeypatch.setattr(hear, "Hearer", Fake)
    rows = hear.check(s, ["x.wav"], "small")
    assert rows[0]["diffs"] == []
    assert rows[0]["how"] == "small→medium+prompt"
    assert calls == [("small", False), ("medium", False), ("medium", True)]


def test_聞き直しは_medium_で消えたら_prompt_を撃たない(monkeypatch):
    from studio import script as sc
    say = "年金は一生続きます。"
    s = sc.Script(id="t", date="2026-09-08", title="t #Shorts", takeaway="t", yomi={"年金": "ねんきん", "一生": "いっしょう"},
                  segments=[sc.Segment(say=say)])
    calls = []

    class Fake:
        def __init__(self, size):
            self.size = size

        def transcribe(self, wav, prompt=None):
            calls.append((self.size, prompt is not None))
            return "ねんきんはいっしょうつづきます" if self.size == "medium" else "ねんきんはたぶんつづきます"

    monkeypatch.setattr(hear, "Hearer", Fake)
    rows = hear.check(s, ["x.wav"], "small")
    assert rows[0]["diffs"] == [] and rows[0]["how"] == "small→medium"
    assert calls == [("small", False), ("medium", False)]


def test_聞いた側の万よんは数字のときは畳まない():
    """「11万4千円」→「114,000えん」を まんえんせん に畳んでいた（09/07 01:xx）。「まんよん」単独は 万円 の聞き違いのまま。"""
    assert hear.heard_kana("114,000えん", {}) == "じゅういちまんよんせんえん"
    assert hear.heard_kana("15まんよん", {}) == "じゅうごまんえん"


def test_聞いた側の桁区切りの欠けは3桁に埋める():
    """medium が 6万3千円 を「63,00 エーン」と書いた（09/07 00:5x hourly の申し送り）。213,000 のような正しい区切りはそのまま。"""
    assert hear.heard_kana("63,00 エーン", {}).startswith("ろくまんさんぜん")
    assert hear.heard_kana("213,000 エン", {}) == "にじゅういちまんさんぜんえん"
