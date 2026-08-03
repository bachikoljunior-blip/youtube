"""Google Cloud Text-to-Speech（REST + APIキー）でナレーションを合成する。

サービスアカウントJSONではなく API キーを使うのは、GitHub secrets に1行で入るから。
"""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from . import config
from .util import probe_duration

ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
MAX_BYTES = 4800  # API 上限は 5000 バイト


def synthesize_segments(narrations: list[str], voice_cfg: dict, out_dir: Path) -> list[tuple[Path, float]]:
    """セグメントごとに音声を作り、(ファイル, 秒数) を返す。"""
    api_key = config.env("GOOGLE_TTS_API_KEY")
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[Path, float]] = []

    for i, text in enumerate(narrations):
        if len(text.encode("utf-8")) > MAX_BYTES:
            raise RuntimeError(f"セグメント{i}が長すぎます（TTSの1リクエスト上限を超過）")

        response = requests.post(
            ENDPOINT,
            params={"key": api_key},
            json={
                "input": {"text": text},
                "voice": {"languageCode": "ja-JP", "name": voice_cfg["voice"]},
                "audioConfig": {
                    "audioEncoding": "LINEAR16",
                    "sampleRateHertz": 24000,
                    "speakingRate": float(voice_cfg.get("speaking_rate", 1.0)),
                    "pitch": float(voice_cfg.get("pitch", 0.0)),
                },
            },
            timeout=90,
        )
        if response.status_code != 200:
            raise RuntimeError(f"TTS 失敗 (HTTP {response.status_code}): {response.text[:400]}")

        path = out_dir / f"seg_{i:03d}.wav"
        path.write_bytes(base64.b64decode(response.json()["audioContent"]))
        duration = probe_duration(path)
        results.append((path, duration))
        print(f"[tts] {i + 1}/{len(narrations)} {duration:5.2f}s  {text[:28]}…")

    return results
