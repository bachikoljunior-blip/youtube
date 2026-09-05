"""Google Cloud TTS（Chirp3-HD）。コマごとに1ファイル。読みは customPronunciations で固定する。

実測 2026-09-05: v1beta1 の `customPronunciations`（JAPANESE_YOMIGANA）は漢字だけの語は通る。
送り仮名を含む語（「繰下げ」）は INVALID_ARGUMENT で全体が落ちる → 送り仮名を含む語は
台本側でひらがなに書き換える（`yomi` に入れず、`say` を直す）。
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

import requests

from .common import env, probe_duration, run
from .script import Script

ENDPOINT = "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
PAD_SEC = 0.35   # コマの間の息


def _key(text: str, voice: str, rate: float, yomi: dict[str, str]) -> str:
    h = hashlib.sha1(json.dumps([text, voice, rate, sorted(yomi.items())], ensure_ascii=False).encode()).hexdigest()
    return h[:16]


def synth_segment(text: str, voice: str, rate: float, yomi: dict[str, str], out_dir: Path) -> tuple[Path, float]:
    """mp3 を作り（キャッシュあり）、末尾に PAD_SEC の無音を足した wav を返す。"""
    used = {k: v for k, v in yomi.items() if k in text and re.fullmatch(r"[一-龥々]+", k)}
    key = _key(text, voice, rate, used)
    mp3 = out_dir / f"seg-{key}.mp3"
    wav = out_dir / f"seg-{key}.wav"
    if not wav.exists():
        body = {
            "input": {"text": text},
            "voice": {"languageCode": "ja-JP", "name": voice},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate, "sampleRateHertz": 24000},
        }
        if used:
            body["input"]["customPronunciations"] = {"pronunciations": [
                {"phrase": k, "phoneticEncoding": "PHONETIC_ENCODING_JAPANESE_YOMIGANA", "pronunciation": v}
                for k, v in used.items()]}
        r = requests.post(ENDPOINT, params={"key": env("GOOGLE_TTS_API_KEY")}, json=body, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"TTS {r.status_code}: {r.text[:300]}")
        mp3.write_bytes(base64.b64decode(r.json()["audioContent"]))
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
             "-af", f"apad=pad_dur={PAD_SEC}", "-ar", "24000", "-ac", "1", str(wav)])
    return wav, probe_duration(wav)


def synth_script(s: Script, out_dir: Path) -> list[tuple[Path, float]]:
    return [synth_segment(seg.say, s.voice, s.rate, s.yomi, out_dir) for seg in s.segments]


def concat(wavs: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{w.resolve()}'\n" for w in wavs), encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out
