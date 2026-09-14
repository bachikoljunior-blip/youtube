"""whisper が「3 つ」と空白を挟んで書いても、聞いた側は みっつ になる（2026-09-15・optimizer・Fable。実物: 長尺 2本目 コマ44 が さんつ で `!!`）。"""
from studio.hear import heard_kana, expected_kana


def test_空白つきの数つは和語で読む():
    assert "みっつ" in heard_kana("3 つのみち", {})
    assert "さんつ" not in heard_kana("3 つのみち", {})


def test_予定の側と同じ字になる():
    assert heard_kana("3 つのみちです", {}) == expected_kana("3つの道です", {})
