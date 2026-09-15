"""`yomi` が声に届いていない本を名指しする（2026-09-16 04:4x）。

**踏んだ形**: 9本目 は `yomi` に「扶養親族等申告書 → ふようしんぞくとうしんこくしょ」と書いてあるのに、
コマ2（フック）が **「ふようしんぞく〈など〉しんこくしょ」**と鳴っていた。
`customPronunciations` が効くのは Chirp3 系だけで、**Neural2 は 200 で受けて無視する**
（`studio/tts.py` 冒頭の実測）。台帳の 20本 のうち **18本 が Neural2・17本 の `kana_in_voice` が空**で、
いちばん多い本で **221語** が音に 1ミリも効いていなかった。

**読みが正しいことはオーナーの固定**（固定その3・2026-09-02「ナレーションの漢字の読み方全部正しくして」）。
**止めません**（`problems()` に入れると焼けなくなる）—— 読んで決めるのは書き手。

**陽性対照 3つ**:
 (1) 声を Chirp3-HD にすると黙る（あちらは効くので）。
 (2) `kana_in_voice` に全語を入れると黙る。
 (3) `yomi` が空なら黙る。
"""
from studio import script


def _s(voice="ja-JP-Neural2-D", yomi=None, kana=None):
    return script.Script(
        id="2026-09-30-test", date="2026-09-30", title="て", takeaway="て",
        description="て", tags=["て"], voice=voice, rate=1.0,
        yomi=yomi if yomi is not None else {"扶養親族等申告書": "ふようしんぞくとうしんこくしょ"},
        kana_in_voice=kana or [],
        segments=[script.Segment(say="てすとです。", show="て")],
    )


def _warn(s):
    return [w for w in s.warnings() if "音に効いていません" in w]


def test_Neural2で_yomi_が在れば名指しする():
    got = _warn(_s())
    assert len(got) == 1
    assert "1語 が音に効いていません" in got[0]
    assert "ja-JP-Neural2-D" in got[0]
    assert "扶養親族等申告書" in got[0]


def test_Chirp3なら黙る():
    """**陽性対照 1**: あちらは `customPronunciations` が効く。"""
    assert _warn(_s(voice="ja-JP-Chirp3-HD-Charon")) == []


def test_kana_in_voiceに入れたら黙る():
    """**陽性対照 2**: 入れた語は `tts.voice_text` が文の中で仮名に置き換える。"""
    assert _warn(_s(kana=["扶養親族等申告書"])) == []


def test_yomiが空なら黙る():
    """**陽性対照 3**: 効かせる物が無い本で鳴らさない。"""
    assert _warn(_s(yomi={})) == []


def test_一部だけ入れたら残りを数える():
    s = _s(yomi={"甲": "こう", "乙": "おつ", "丙": "へい"}, kana=["甲"])
    got = _warn(s)
    assert len(got) == 1 and "2語 が音に効いていません" in got[0]
    assert "いま 1語" in got[0]


def test_止めない():
    """`problems()` に入れないこと —— `cmd_build` は `problems()` が 1行でも在ると焼く前に止まる。"""
    assert not [p for p in _s().problems() if "音に効いていません" in p]
