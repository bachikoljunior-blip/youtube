"""ナレーションの音声合成。

エンジンは2つ。
  open-jtalk … apt で入る。APIキーも課金設定も不要。声はやや機械的。
  google     … Cloud Text-to-Speech。APIキーが1つ要るが、声は明確に自然。

既定は google で、キーが無ければ黙って open-jtalk に落ちる。
鍵ゼロでも動く一方、視聴維持率は声で変わり、維持率は広告収益に直結するので、
キーを1つ足せば上げられる、という関係にしてある。
"""
from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path

from . import config
from .util import probe_duration, run
from .yomi import to_speech

GOOGLE_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
GOOGLE_MAX_BYTES = 4800  # API 上限は 5000 バイト

# Ubuntu の open-jtalk パッケージが置く場所
OPEN_JTALK_DICT = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
OPEN_JTALK_VOICE = "/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice"


def choose_engine(tts_cfg: dict) -> str:
    """設定と鍵の有無から、実際に使うエンジンを決める。"""
    requested = tts_cfg.get("engine", "google")
    if requested == "google" and not config.env("GOOGLE_TTS_API_KEY", required=False):
        print("[tts] GOOGLE_TTS_API_KEY が無いので open-jtalk を使います（声は機械的になります）")
        return "open-jtalk"
    return requested


def _google(text: str, dest: Path, cfg: dict) -> None:
    import requests

    if len(text.encode("utf-8")) > GOOGLE_MAX_BYTES:
        raise RuntimeError("セグメントが長すぎます（TTSの1リクエスト上限を超過）")

    response = requests.post(
        GOOGLE_ENDPOINT,
        params={"key": config.env("GOOGLE_TTS_API_KEY")},
        json={
            "input": {"text": text},
            "voice": {"languageCode": "ja-JP", "name": cfg.get("voice", "ja-JP-Neural2-D")},
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": 24000,
                "speakingRate": float(cfg.get("speaking_rate", 1.0)),
                "pitch": float(cfg.get("pitch", 0.0)),
            },
        },
        timeout=90,
    )
    if response.status_code != 200:
        raise RuntimeError(f"TTS 失敗 (HTTP {response.status_code}): {response.text[:400]}")
    dest.write_bytes(base64.b64decode(response.json()["audioContent"]))


def _open_jtalk(text: str, dest: Path, cfg: dict) -> None:
    if not shutil.which("open_jtalk"):
        raise RuntimeError(
            "open_jtalk が見つかりません。\n"
            "  sudo apt-get install -y open-jtalk open-jtalk-mecab-naist-jdic "
            "hts-voice-nitech-jp-atr503-m001"
        )
    for path, what in ((OPEN_JTALK_DICT, "辞書"), (OPEN_JTALK_VOICE, "音声モデル")):
        if not Path(path).exists():
            raise RuntimeError(f"open-jtalk の{what}が見つかりません: {path}")

    raw = dest.with_suffix(".raw.wav")
    proc = subprocess.run(
        [
            "open_jtalk",
            "-x", OPEN_JTALK_DICT,
            "-m", OPEN_JTALK_VOICE,
            "-r", str(cfg.get("speaking_rate", 1.0)),
            "-fm", str(cfg.get("pitch", 0.0)),
            "-ow", str(raw),
        ],
        input=text.encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0 or not raw.exists():
        raise RuntimeError(f"open_jtalk 失敗: {proc.stderr.decode('utf-8', 'ignore')[:300]}")

    # 48kHz モノラルで出てくるので、google 側と同じ 24kHz に揃える。
    # 揃えておかないと後段の concat が使えない。
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-ar", "24000", "-ac", "1", str(dest)])
    raw.unlink(missing_ok=True)


def synthesize_segments(narrations: list[str], tts_cfg: dict, out_dir: Path,
                        *, allow_fallback: bool = True) -> list[tuple[Path, float]]:
    """セグメントごとに音声を作り、(ファイル, 秒数) を返す。

    google が途中で失敗したら open-jtalk に切り替えて全部作り直す。
    無人で毎日回るので、声が少し落ちることより、その日1本落ちるほうが損。

    **`allow_fallback=False` のときは切り替えず、google の失敗をそのまま上げる**
    （2026-09-03 05:xx JST・最適化の回）。理由: 外の作りを写した長尺
    （`topics.yaml` の `style: outside_long`・19〜20分・60コマ超）は、`eta.py` が
    「引けるのは `per_video` だけ」と名指しする腕の**唯一の試験**に出る本で、
    `scripts/ahead_sweep.rebake_today` が**背景で誰も見ずに**焼き直す。60コマのどれか
    1つで google が一度でも落ちると、**20分まるごと open-jtalk の機械音声**に化けて、
    そのまま `--replaces` で差し替わる（log に1行 出るだけ・`verify` は音を見ない）。
    その本の 48h が 100回 以下でも、外れたのは「作り方」ではなく「声」になり、
    前提（`config/hypotheses.yaml` の「外の作り方を写した長尺」）が読めなくなる。
    上の「1本落ちるより声が落ちるほうが得」は、1日 10本 以上 出していた頃の損得で、
    規則（1日1本・出る瞬間まで良くする）の下では逆 —— 落ちたら焼き直せばよい
    （`rebake_today` は死んだ印を拾い直す）。ショートと従来の長尺は今までどおり。

    **覆る条件**: google が日をまたいで落ち続け、その日の1本が出せなくなったら
    （`data/rebake.jsonl` に `rc != 0` が 3件 続く）、そのときはここを `True` に戻すより
    先に鍵・請求先を直すこと（この註の上の3行が言っている当のもの）。
    請求先の紐付け漏れ・APIキーの制限ミス・無料枠超過は、どれもここに出る。

    声は途中で変えない。1本の中で話者が変わるのは、機械的な声より不快。

    読みの直しは **ここだけ** に効く（`src/yomi.py`）。字幕・画面・説明欄は
    元の narration をそのまま使うので、画面の文字は変わらない。
    """
    engine = choose_engine(tts_cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    spoken = [to_speech(text) for text in narrations]

    for attempt_engine in (engine, "open-jtalk"):
        synth = _google if attempt_engine == "google" else _open_jtalk
        results: list[tuple[Path, float]] = []
        try:
            for i, text in enumerate(spoken):
                path = out_dir / f"seg_{i:03d}.wav"
                synth(text, path, tts_cfg)
                duration = probe_duration(path)
                results.append((path, duration))
                print(f"[tts:{attempt_engine}] {i + 1}/{len(narrations)} {duration:5.2f}s  {text[:26]}…")
            return results
        except Exception as exc:
            if attempt_engine != "google":
                raise
            print(f"[tts] google が失敗しました: {str(exc)[:300]}")
            if not allow_fallback:
                raise RuntimeError(
                    "google の音声が落ちました。この本（外の作りを写した長尺）は open-jtalk へ"
                    " 倒しません —— 焼き直すこと（`synthesize_segments` の docstring）: "
                    + str(exc)[:200]
                ) from exc
            print("[tts] open-jtalk に切り替えて作り直します（声は機械的になります）")

    raise RuntimeError("unreachable")
