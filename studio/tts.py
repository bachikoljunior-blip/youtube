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

**もう1つの口（SSML `<sub alias>`）も測ってあります。使っていません**
（2026-09-07 14:3x・optimizer・Opus が同じ周に別々に撃った ＝ 上の hourly の実測と同じ結論に別の道で着いた）:

    ja-JP-Neural2-D   plain 44d9ecbea9 / customPronunciations 44d9ecbea9（同じ音 ＝ 無視）
                      plain 44d9ecbea9 / SSML <sub alias>    bde60721b0（効く）
    ja-JP-Chirp3-HD   plain 0fe1ca3a58 / customPronunciations 98bb59a423（効く）

`<sub>` は **customPronunciations より強い**: Chirp3 が無視した語（`script.YOMI_IGNORED` の 年金・額・市場・十分）を
5/5 とも置き換えた（わざと「年金 → としかね」と読ませて whisper で聞いた。Chirp3 は同じ指示を無視して「ねんきん」と読む）。
送り仮名つきの語（「長生き」）も `<sub>` は受ける（customPronunciations は phrase ごと拒む）。

**それでも上の `voice_text`（文中で仮名に置換）を残したのは、`<sub>` に勝ち目が無いからです** ——
`<sub alias="かな">漢字</alias>` は **alias のほうを読む** ので、出てくる音は仮名に置き換えたのと同じで、
「辞書に無い仮名の並びは抑揚が崩れる」も**同じだけ起きます**。SSML の逃がし（`&` `<`）とキャッシュの鍵が増えるだけ。
**＝ `<sub>` へ「強いから」と乗り換えないこと。強さの差は `FORCE_ALL_KANA` で同じだけ出せます。**
~~**覆る条件**: 抑揚を保ったまま読みだけ変える口が要るなら、`<sub>` ではなく SSML の `<phoneme>`（アクセント指定つき）を測ること。~~

**【2026-09-11 13:0x・hourly・Opus】その覆る条件を引きました。`<phoneme>` は ja-JP-Neural2-D に効きません。**
オーナー 12:4x「**まだ読みがおかしいのがあるよ。ひらがなも漢字もあった。**説明の解釈が誤解されないようにするようにして」
（受け取り帳 `3f4ef885`）を受けて撃った（TTS 9回・whisper 9回・Data API 0単位）。
**同じ文・同じ語（年数）に、わざと違う読み（としかず）を入れて比べた**:

    plain      md5 874cd9929a  2.760秒
    sub_wrong  md5 **a9cded90a2**  2.832秒   ← `<sub alias="としかず">` ＝ **効く**（この probe の中の陽性対照）
    ph_xsampa  md5 874cd9929a  2.760秒       ← `<phoneme alphabet="x-sampa" ph="toSikazu">` ＝ **200 で受けて無視**
    ph_ipa     md5 874cd9929a  2.760秒       ← `alphabet="ipa"` も同じ
    ph_accent  md5 874cd9929a  2.760秒       ← 強勢記号つきも同じ

**SSML そのものは届いています**（別の陽性対照: `<break time="2s"/>` で 2.760 → **4.776秒**）。

**1回目の probe は、これを取り違えました**（§5 の教訓 3つ目の当のもの）——
退職金 → `alias="たいしょくきん"` / `ph="taiSokukiN"` と、**もともと正しい読み**を渡したので
4つ とも音が同じになり、「`<sub>` も効かない」と読みかけました。
**落ちなければ疑うのは道具ではなく検査のデータ。** わざと違う読みに変えたら、その場で分かれました。

**＝ この声で音を変えられる口は 2つ だけで、どちらも「仮名で書く」と同じものです**:
`say` の字を仮名にする（`voice_text`）／`<sub alias="かな">`（alias のほうを読む）。
**読みだけ直して抑揚を保つ口は、いまの声には在りません。**

**だからオーナーの「ひらがなも漢字も」は、2つの不具合ではなく 1つの機構の両端です** ——
漢字を直す唯一の手が「仮名で書く」で、その仮名が辞書に無い並びだと抑揚が崩れる。
**手は 3つ しかありません**: (1) 語そのものを、読みの割れない語に**書き換える**（抑揚もそのまま ＝ いちばん安い）・
(2) 声を Chirp3-HD へ戻す（`customPronunciations` が効く。**ただしオーナー 09/07 13:3x で戻した当のもの**なので、
声を動かすのはオーナーの言葉があったときだけ・§2）・(3) 仮名で書く（抑揚を捨てる）。
**`FORCE_ALL_KANA` は (3) を全部の語に当てるものなので、いまは上げないこと**（§2 の覆る条件を書き直した）。
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
    """TTS に渡す文。Neural2 系は `kana_in_voice` の語（FORCE_ALL_KANA なら yomi の全語）を仮名に置き換える。画面の字は変えない。

    **この置換も素の `replace` です**（語の境目を見ない）＝ `hear.expected_kana` が
    2026-09-11 01:3x に閉じた穴の、**2つ目の口**（§5 の教訓の形2つ目）。
    **この回に撃って、空でした。** 実物 6本・77コマ に `FORCE_ALL_KANA = True` を当てると、
    **TTS へ渡る字は 23コマ で変わり、読みが変わるコマは 0** ——
    §3 の 9（声の漢字は全部 `yomi`）が複合語に長い鍵を作らせるので、1字 の鍵が単独で当たる所は
    どれも助数詞の読みと `yomi` の値が一致していました（20年→20ねん・10月分→10がつぶん）。
    `kana_in_voice` の側も、いまの台本 6本 で **1字の漢字は 0個**。
    **＝ ここは直しません**（壊れていない物を直さない・09/10 04:5x）。

    **覆る条件**: (1) `kana_in_voice` か `yomi` に、**同じ字の助数詞と読みが違う 1字の鍵**を入れたら
    （日→ひ で「1日」・月→つき で「6か月」・人→ひと で「3人」）、そのときは**音が割れます** ——
    `hear._apply_one_kanji_yomi` と同じ形をここにも当てること。
    (2) `FORCE_ALL_KANA` を True にする回は、その前にこの数を撃ち直すこと（API 0単位・焼かない）。
    """
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
