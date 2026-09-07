"""声で読みの固定の口が違う（studio/tts.py 冒頭。実測 2026-09-07 14:3x）。

Chirp3-HD は customPronunciations が効く。Neural2-D は 200 で受けて無視するので、
Neural2 系は `kana_in_voice` の語だけ TTS に渡す文の中で仮名に置き換える（画面の字は変えない）。
"""
from studio import tts

YOMI = {"年金": "ねんきん", "金額": "きんがく", "額": "がく"}


def test_chirp_は_customPronunciations_の口():
    assert tts.uses_custom_pronunciations("ja-JP-Chirp3-HD-Charon")
    assert not tts.uses_custom_pronunciations("ja-JP-Neural2-D")


def test_chirp_は_文を変えない():
    assert tts.voice_text("年金の金額", "ja-JP-Chirp3-HD-Charon", YOMI, ["年金"]) == "年金の金額"


def test_neural2_は_挙げた語だけ仮名にする():
    assert tts.voice_text("年金の金額", "ja-JP-Neural2-D", YOMI, ["年金"]) == "ねんきんの金額"
    assert tts.voice_text("年金の金額", "ja-JP-Neural2-D", YOMI, []) == "年金の金額"


def test_neural2_は_長い語から置き換える():
    # 「金額」を挙げたとき、中の「額」が先に置き換わって「金がく」にならない
    assert tts.voice_text("金額と額", "ja-JP-Neural2-D", YOMI, ["額", "金額"]) == "きんがくとがく"


def test_yomi_に無い語は挙げても何もしない():
    assert tts.voice_text("年金", "ja-JP-Neural2-D", YOMI, ["繰上げ"]) == "年金"


def test_force_all_kana_は_yomi_の全語(monkeypatch):
    monkeypatch.setattr(tts, "FORCE_ALL_KANA", True)
    assert tts.voice_text("年金の金額", "ja-JP-Neural2-D", YOMI, []) == "ねんきんのきんがく"
