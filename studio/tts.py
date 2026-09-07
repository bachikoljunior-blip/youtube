"""Google Cloud TTS。コマごとに1ファイル。読みの固定は声で口が違う。

- Chirp3-HD（09/05〜09/07 の3本）: `customPronunciations` で固定する。
  実測 2026-09-05: v1beta1 の `customPronunciations`（JAPANESE_YOMIGANA）は漢字だけの語は通る。
  送り仮名を含む語（「繰下げ」）は INVALID_ARGUMENT で全体が落ちる → 送り仮名を含む語は
  台本側でひらがなに書き換える（`yomi` に入れず、`say` を直す）。
- Neural2-D（09/04 までの 24本・**09/08 から戻した**。オーナー 09/07 13:3x「ナレーション前の音声の方が良かった」）:
  実測 2026-09-07 14:3x（hourly・Fable）: `customPronunciations` を **200 で受けて無視する**
  （年金→「としかね」と頼んでも「ねんきん」・音の長さも 4.296秒 で同じ）。文の中の仮名は読む（旧 `src/yomi.py` と同じ形）。
  → Neural2 系は漢字をそのまま読ませ（前の 24本と同じ音）、hear（漢字を禁じた聞き取り）で誤読が出た語だけ
  `kana_in_voice` に挙げて **TTS に渡す文の中で仮名に置き換える**。全部を仮名にしない理由: 辞書に無い仮名の並びは
  抑揚が崩れる（probe で「としかね」が引用符つきに聞こえた）。**覆る条件**: hear で捕まらなかった誤読をオーナーが耳で
  見つけたら、`yomi` の語を全部 置換する形へ（`FORCE_ALL_KANA`）。
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
FORCE_ALL_KANA = False   # True にすると Neural2 系でも `yomi` の語を全部 文中で仮名にする（覆る条件は冒頭）


def uses_custom_pronunciations(voice: str) -> bool:
    """customPronunciations が効く声か（実測: Chirp3-HD は効く・Neural2 は 200 で受けて無視）。"""
    return "Chirp3-HD" in voice


def voice_text(text: str, voice: str, yomi: dict[str, str], kana_in_voice: list[str] = ()) -> str:
    """TTS に渡す文。Neural2 系は `kana_in_voice` の語（FORCE_ALL_KANA なら yomi の全語）を仮名に置き換える。画面の字は変えない。"""
    if uses_custom_pronunciations(voice):
        return text
    words = list(yomi) if FORCE_ALL_KANA else [w for w in kana_in_voice if w in yomi]
    for w in sorted(words, key=len, reverse=True):
        text = text.replace(w, yomi[w])
    return text


def _key(text: str, voice: str, rate: float, yomi: dict[str, str]) -> str:
    h = hashlib.sha1(json.dumps([text, voice, rate, sorted(yomi.items())], ensure_ascii=False).encode()).hexdigest()
    return h[:16]


def synth_segment(text: str, voice: str, rate: float, yomi: dict[str, str], out_dir: Path,
                  kana_in_voice: list[str] = ()) -> tuple[Path, float]:
    """mp3 を作り（キャッシュあり）、末尾に PAD_SEC の無音を足した wav を返す。"""
    custom = uses_custom_pronunciations(voice)
    used = {k: v for k, v in yomi.items() if k in text and re.fullmatch(r"[一-龥々]+", k)} if custom else {}
    spoken = voice_text(text, voice, yomi, kana_in_voice)
    key = _key(spoken, voice, rate, used)
    mp3 = out_dir / f"seg-{key}.mp3"
    wav = out_dir / f"seg-{key}.wav"
    if not wav.exists():
        body = {
            "input": {"text": spoken},
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
    return [synth_segment(seg.say, s.voice, s.rate, s.yomi, out_dir, s.kana_in_voice) for seg in s.segments]


def concat(wavs: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{w.resolve()}'\n" for w in wavs), encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    return out
