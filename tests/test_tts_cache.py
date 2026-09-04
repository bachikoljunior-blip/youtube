"""**音の控え**（`src/tts.TTS_CACHE_DIR`）。クリップの控えと同じ穴。

`src/pipeline.py` は毎回 `rmtree(build/<題材>)` を撃つので、前の焼きの音は
次の焼きの1行目で消えます。実測 `data/rebake.jsonl`: 焼き 25回・`done` 3件・
本になったのは 1件・**`done` の無い `start` が 13件**。
`1huadpEk6HY` は 09/03 に 11回 起きて1回も焼き上がらず、そのたびに
60コマ 前後を Google TTS へ投げ直していました（**従量です**）。

ここで縛るのは:
  1. 鍵は「読み上げる字 ＋ 声・速さ・高さ・エンジン」で決まる
  2. **読み照合の輪が字を直したコマは、必ず作り直される**（鍵が変わる）
  3. 控えの置き場所が `rmtree(build/<題材>)` で消えない所に在る
  4. 壊れた控え（0バイト）を「在る」と読まない
"""
from __future__ import annotations

from pathlib import Path

from src import config, tts

CFG = {"voice": "ja-JP-Neural2-D", "speaking_rate": 1.0, "pitch": 0.0}


def test_鍵は入力ごとに変わる():
    k = tts.tts_cache_key("こんにちは", "google", CFG)
    assert k == tts.tts_cache_key("こんにちは", "google", CFG)
    assert k != tts.tts_cache_key("こんばんは", "google", CFG)
    assert k != tts.tts_cache_key("こんにちは", "open-jtalk", CFG)
    assert k != tts.tts_cache_key("こんにちは", "google", {**CFG, "voice": "ja-JP-Neural2-B"})
    assert k != tts.tts_cache_key("こんにちは", "google", {**CFG, "speaking_rate": 1.1})
    assert k != tts.tts_cache_key("こんにちは", "google", {**CFG, "pitch": -2.0})


def test_読みを直したコマは鍵が変わる():
    """オーナー指示の読み照合の輪は、誤読を見つけると**字を直します**。
    直したコマが控えから来たら、**誤読が永久に残ります。**"""
    before = tts.tts_cache_key("ヒタイメンは", "google", CFG)
    after = tts.tts_cache_key("ガクメンは", "google", CFG)
    assert before != after


def test_控えは題材の作業場の外に在る():
    cache = tts.DEFAULT_TTS_CACHE_DIR.resolve()
    assert cache.parent == Path(config.BUILD_DIR).resolve(), \
        "控えは build/ の直下に置くこと（build/<題材>/ の中は rmtree で消えます）"
    assert cache.name.startswith("."), "題材 id と衝突しない名前にすること"


def test_控えに置いて取り出せる(tmp_path):
    cache = tmp_path / "cache"
    src = tmp_path / "seg_000.wav"
    src.write_bytes(b"RIFF....WAVEfmt ")
    tts._tts_cache_put("k" * 64, src, cache)
    got = tmp_path / "out.wav"
    assert tts._tts_cache_get("k" * 64, got, cache) is True
    assert got.read_bytes() == src.read_bytes()


def test_0バイトの控えは無いものとして扱う(tmp_path):
    """空を「在る」と読むと、**無音のコマが本に入ります。**"""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / ("a" * 64 + ".wav")).write_bytes(b"")
    assert tts._tts_cache_get("a" * 64, tmp_path / "o.wav", cache) is False


def test_控えが無いときは静かに作る側へ倒す(tmp_path):
    assert tts._tts_cache_get("nope", tmp_path / "o.wav", tmp_path / "no-such") is False


def test_上限を超えたら古い順に捨てる(tmp_path):
    import os
    cache = tmp_path / "cache"
    cache.mkdir()
    made = []
    for i in range(5):
        p = cache / f"{i:064x}.wav"
        p.write_bytes(b"x" * 100)
        os.utime(p, (1_000_000 + i, 1_000_000 + i))
        made.append(p)
    assert tts.prune_tts_cache(cap=250, cache_dir=cache) == 3
    assert not made[0].exists() and made[4].exists()


def test_合成の輪が控えを通っている():
    """**控えを足しても、呼ぶ側が通っていなければ1ミリも変わりません。**"""
    import inspect
    src = inspect.getsource(tts.synthesize_segments)
    assert "_tts_cache_get" in src and "_tts_cache_put" in src
    assert "tts_cache_key" in src


def test_控えから来たコマも秒数を測り直す():
    """**秒数は字幕の位置とクリップの長さを決めます。**
    控えの秒数を憶えておく形にすると、そこがずれた瞬間に音と字がずれます。"""
    import inspect
    src = inspect.getsource(tts.synthesize_segments)
    body = src.split("_tts_cache_get", 1)[1][:400]
    assert "probe_duration" in body, "控えから来たコマの秒数を測っていません"
