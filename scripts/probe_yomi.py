#!/usr/bin/env python3
"""耳のほう。**本番の Google TTS が実際に何と読んだか**を、音を比べて特定する。

2026-08-16 まで、この仕組みには音を見る検査が1つも無かった。だから
「額」が「ひたい」と読まれていることに6日間気づかず、オーナーが動画を聞いて
見つけるまで直らなかった。**同じ理由で次も見つからない**ので、機械が聞けるように
してある。

## 仕組み

音声認識は要らない。**同じ文の、漢字版と読み仮名版を両方合成して、音を比べる**。

    額が増えます。   ← 調べたい文
    がくが増えます。 ← 候補1
    ひたいが増えます。← 候補2

対数スペクトルの DTW 距離が小さいほうが、実際の読み。上の例では
ひたい 0.320 / がく 0.731 と、倍以上ひらく（迷う余地が無い）。

## 使い方

    python scripts/probe_yomi.py --text "実際の額は賃金日額で決まります。" --word 額 \
        --candidates がく ひたい
    python scripts/probe_yomi.py --corpus            # 公開済みの台本を総当たりする
    python scripts/probe_yomi.py --check             # src/yomi.py の cases を実測で確かめる

`GOOGLE_TTS_API_KEY` が要る（本番と同じ声で測らないと意味が無い）。
合成結果は `build/yomi_cache/` に貯めるので、2回目からは課金されない。

**新しい読み違いを src/yomi.py に足すときは、必ずこれで実測してから足すこと。**
推測で置換表を増やすと、直っていない語が直った顔をして残る。
"""
from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import os
import re
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CACHE = Path("build/yomi_cache")
VOICE = "ja-JP-Neural2-D"
RATE = 1.08  # config/channel.yaml の tts.speaking_rate と揃えること
KANJI = r"[一-鿿々]"


def synth(text: str, voice: str = VOICE) -> "list[float]":
    import numpy as np
    import requests

    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{voice}|{RATE}|{text}".encode()).hexdigest()[:16]
    path = CACHE / f"{key}.wav"
    if not path.exists():
        response = requests.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            params={"key": os.environ["GOOGLE_TTS_API_KEY"]},
            json={
                "input": {"text": text},
                "voice": {"languageCode": "ja-JP", "name": voice},
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000,
                                "speakingRate": RATE, "pitch": 0.0},
            },
            timeout=90,
        )
        if response.status_code != 200:
            raise RuntimeError(f"TTS 失敗 (HTTP {response.status_code}): {response.text[:300]}")
        path.write_bytes(base64.b64decode(response.json()["audioContent"]))
    with wave.open(str(path)) as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def feats(wave_data, win: int = 512, hop: int = 240):
    """対数スペクトルを24帯域に畳んで、フレームごとに正規化する。

    声の高さや音量ではなく「どの音が並んでいるか」だけを見たいので、
    帯域は対数間隔で取り、時間方向に平均と分散をそろえてある。
    """
    import numpy as np

    if len(wave_data) < win:
        return np.zeros((1, 24))
    n = 1 + (len(wave_data) - win) // hop
    frames = np.lib.stride_tricks.as_strided(
        wave_data, (n, win), (wave_data.strides[0] * hop, wave_data.strides[0])).copy()
    frames *= np.hanning(win)
    spec = np.abs(np.fft.rfft(frames, axis=1))
    edges = np.unique(np.floor(np.logspace(np.log10(2), np.log10(spec.shape[1] - 1), 25)).astype(int))
    bands = np.stack([spec[:, edges[i]:edges[i + 1] + 1].mean(1) for i in range(len(edges) - 1)], 1)
    out = np.log(bands + 1e-8)
    out -= out.mean(0)
    out /= out.std(0) + 1e-8
    return out


def dtw(a, b) -> float:
    import numpy as np

    dist = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1))
    n, m = dist.shape
    acc = np.full((n + 1, m + 1), np.inf)
    acc[0, 0] = 0
    for i in range(1, n + 1):
        acc[i, 1:] = dist[i - 1]
        row, prev = acc[i], acc[i - 1]
        for j in range(1, m + 1):
            row[j] += min(prev[j], row[j - 1], prev[j - 1])
    return float(acc[n, m] / (n + m))


def probe(sentence: str, word: str, candidates: list[str], at: int | None = None):
    """`sentence` の中の `word` が、候補のどれで読まれているかを返す。"""
    index = sentence.index(word) if at is None else at
    template = sentence[:index] + "{}" + sentence[index + len(word):]
    ref = feats(synth(template.format(word)))
    scored = sorted((dtw(ref, feats(synth(template.format(c)))), c) for c in candidates)
    return scored


def corpus_sentences(word: str = "額"):
    """公開済みの台本から、裸の（複合語でない）その字を含む文を拾う。"""
    for path in sorted(glob.glob("data/critique_queue/*.json")):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for line in data.get("narration") or []:
            if not isinstance(line, str):
                continue
            for m in re.finditer(re.escape(word), line):
                i = m.start()
                before, after = line[i - 1:i], line[i + len(word):i + len(word) + 1]
                if re.match(KANJI, before or " ") or re.match(KANJI, after or " "):
                    continue
                yield data.get("video_id", path), line, i


def report(scored, label: str, wrong: set[str]) -> bool:
    best, second = scored[0], scored[1]
    ng = best[1] in wrong
    gap = second[0] - best[0]
    flag = "NG" if ng else "ok"
    thin = "  ※差が小さい" if gap < 0.05 else ""
    print(f"{flag}  {best[1]:5s} ({best[0]:.3f} vs {second[1]} {second[0]:.3f}){thin}  {label}")
    return ng


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--word", default="額")
    ap.add_argument("--candidates", nargs="+", default=["がく", "ひたい"])
    ap.add_argument("--wrong", nargs="*", default=["ひたい"], help="出たら NG にする読み")
    ap.add_argument("--corpus", action="store_true", help="公開済みの台本を総当たりする")
    ap.add_argument("--check", action="store_true", help="src/yomi.py の cases を実測する")
    args = ap.parse_args()

    if not os.environ.get("GOOGLE_TTS_API_KEY"):
        print("[probe] GOOGLE_TTS_API_KEY が無いので測れません（本番と同じ声で測る必要があります）")
        return 2

    wrong = set(args.wrong)
    bad = 0
    if args.text:
        bad += report(probe(args.text, args.word, args.candidates), args.text, wrong)
    if args.corpus:
        hit = set()
        for video_id, line, i in corpus_sentences(args.word):
            if report(probe(line, args.word, args.candidates, at=i), f"{video_id}  {line[:34]}", wrong):
                hit.add(video_id)
        print(f"\n誤読が入った動画: {len(hit)} 本  {sorted(hit)}")
    if args.check:
        # 置換後の文を測っても意味が無い（仮名を仮名と比べるだけで距離は必ず0になる）。
        # ここで確かめるのは2つ:
        #   1. 置換で漢字がエンジンに届かなくなったか  ← これが誤読しない理由そのもの
        #   2. 表に載っている文が「いまも実際に誤読される」か
        #      再現しなくなっていたら、その行はもう要らない（＝表を減らせる合図）
        from src.yomi import FIXES, remaining_risks

        for fix in FIXES:
            print(f"--- {fix.name} ---")
            for case in fix.cases:
                # 「額」が残っていること自体は問題ない（複合語の額はそのまま読める）。
                # 見るのは、壊れる形＝裸の字が残っていないか。
                if remaining_risks(case):
                    print(f"NG  置換が効かず、壊れる形のまま「{fix.name}」がエンジンに届く: {case}")
                    bad += 1
                    continue
                match = fix.regex.search(case)
                if not match:
                    print(f"NG  表の case が壊れる形を含んでいない（例が古い）: {case}")
                    bad += 1
                    continue
                index = match.start()
                scored = probe(case, fix.name, args.candidates, at=index)
                still = scored[0][1] in wrong
                print(f"{'再現' if still else '再現せず'}  "
                      f"{scored[0][1]:5s} ({scored[0][0]:.3f} vs {scored[1][1]} {scored[1][0]:.3f})"
                      f"  直す前: {case[:34]}")
                if not still:
                    print("      ↑ いま測ると誤読しない。エンジン側が変わったなら、"
                          "この行は表から外してよい（外す前にもう一度測ること）")
    if not (args.text or args.corpus or args.check):
        ap.error("--text か --corpus か --check のどれかを指定してください")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
