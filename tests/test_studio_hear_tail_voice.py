"""`hear.tail_voice`（音の終わり − 聞き取りが止まった時刻）の検査。

**この手は `hourly` の申し送りで足した**（2026-09-09 10:4x・METHOD §4 (2)）——
その回、`tail_probe` と `tail_rate` が **2つとも「TTS 側を疑え」と答えて、2つとも外れました**。
だから 3つ目は「元の2つと違う物を見ているか」が要点で、**片側（音のエネルギー）が模型を通らない**ことが
その当のものです。陽性対照（音が本当に在る／無い）を両方 置きます。
"""
import subprocess
from pathlib import Path

import pytest

from studio import hear


def _wav(tmp_path: Path, parts: list[tuple[float, float, int]], name: str = "a.wav") -> Path:
    """(長さ秒, 振幅, ヘルツ) を並べた wav を作る（振幅 0 は無音）。"""
    outs = []
    for i, (sec, vol, hz) in enumerate(parts):
        p = tmp_path / f"p{i}.wav"
        src = f"sine=frequency={hz}:duration={sec}" if vol else f"anullsrc=r=16000:cl=mono"
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", src]
        if not vol:
            cmd += ["-t", str(sec)]
        cmd += ["-ar", "16000", "-ac", "1"]
        if vol:
            cmd += ["-filter:a", f"volume={vol}"]
        subprocess.run(cmd + [str(p)], check=True)
        outs.append(p)
    lst = tmp_path / "l.txt"
    lst.write_text("".join(f"file '{o}'\n" for o in outs))
    out = tmp_path / name
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-ar", "16000", "-ac", "1", str(out)], check=True)
    return out


def test_無音の尻尾は音の終わりに数えない(tmp_path):
    """陰性対照: 1秒 鳴って 1秒 黙る wav の「音の終わり」は 2.0秒 ではなく 1.0秒。"""
    w = _wav(tmp_path, [(1.0, 1.0, 440), (1.0, 0, 0)])
    assert hear.energy_end(w) == pytest.approx(1.0, abs=0.1)


def test_間の無音をまたいで最後の音を見る(tmp_path):
    """陽性対照: 黙ったあとにもう一度 鳴れば、そちらが終わり（＝ 最初の無音で止まらない）。"""
    w = _wav(tmp_path, [(1.0, 1.0, 440), (0.5, 0, 0), (0.5, 1.0, 440)])
    assert hear.energy_end(w) == pytest.approx(2.0, abs=0.15)


def test_閾より小さい尻尾は音に数えない(tmp_path):
    """陰性対照: 大きい音の 1% しかない尻尾は、無音の側（閾 5%）。"""
    w = _wav(tmp_path, [(1.0, 1.0, 440), (1.0, 0.01, 440)])
    assert hear.energy_end(w) == pytest.approx(1.0, abs=0.1)


class _Stub:
    """語の終わりの時刻だけを返す聞き手（模型を読み込まない）。"""

    def __init__(self, end):
        self.end = end

    def transcribe_words(self, wav, prompt=None):
        return [("として", self.end - 0.4, self.end)]


def test_音が在るときは切ったのはwhisperと答える(tmp_path, monkeypatch):
    """陽性対照 —— hourly が 09/10 の本 コマ7 で手で撃った実測そのもの
    （音のエネルギー 8.10秒・仮名モードの最後の語の終わり 7.58秒 ＝ 0.52秒 空く）。"""
    monkeypatch.setattr(hear, "energy_end", lambda *a, **k: 8.10)
    v = hear.tail_voice(_Stub(7.58), tmp_path / "x.wav")
    assert v["gap"] == pytest.approx(0.52, abs=0.01)
    assert v["verdict"] == "音は在る"


def test_音が無いときはTTS側に付く(tmp_path, monkeypatch):
    """陽性対照の逆側: 聞き取りが止まった所で音も終わっていれば、末尾は本当に鳴っていない。"""
    monkeypatch.setattr(hear, "energy_end", lambda *a, **k: 7.60)
    assert hear.tail_voice(_Stub(7.58), tmp_path / "x.wav")["verdict"] == "音が無い"


def test_あいだは分けないと答える(tmp_path, monkeypatch):
    """**在るほうへ丸めないこと** —— 5モーラ に足りない差は、この手の分解能の外。"""
    monkeypatch.setattr(hear, "energy_end", lambda *a, **k: 7.88)
    assert hear.tail_voice(_Stub(7.58), tmp_path / "x.wav")["verdict"] == "分けられない"


def test_語が1つも取れなければ音の終わりがそのまま差になる(tmp_path, monkeypatch):
    """聞き取りが空の回（崩れた回）でも落ちない ＝ 差は音の終わりそのもの。"""
    monkeypatch.setattr(hear, "energy_end", lambda *a, **k: 9.0)

    class _Empty(_Stub):
        def transcribe_words(self, wav, prompt=None):
            return []

    v = hear.tail_voice(_Empty(0), tmp_path / "x.wav")
    assert v["word_end"] == 0.0 and v["verdict"] == "音は在る"
