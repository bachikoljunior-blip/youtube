"""**完成音声を最初から最後まで機械で聞き取り、予定していた読みと照合する層**（2026-09-03）。

## なぜ要るか（オーナー原文・`CLAUDE.md` 冒頭・**一字も変えないこと**）

> **「Google TTSで生成した完成音声の最初から最後までを機械で聞き取り、
> 予定していた読みと照合し、誤読があれば修正・再生成して、もう一度全文照合する」**
> **「やるようにして。」**

**「やるようにして」＝ 1回やって終わりではなく、毎本 機械がそうする形にすること。**

## ここまでに在った道と、そこに空いていた穴

    src/yomi.py          TTS に渡す文字列の中でだけ仮名に置き換える（直しの当て所）
    src/yomi_gate.py     読み上げの漢字を全部 形態素解析にかけ、危ない形を名指し（R0〜R3）
    scripts/yomi_audit.py 公開ずみ全文で「文脈で読みが割れる語」を実測
    scripts/yomi_ear.py  **語ごと**に、Google TTS と open-jtalk の音の距離を測る

**どれも音を「1語ずつ」しか見ていません。** `yomi_ear` は語を切り出して2回 合成し、
距離を測る —— **本番に出て行く音そのものは、誰も最初から最後まで聞いていなかった。**
2026-08-16 の「額 → ひたい」が6日 残ったのは、その形だったからです。

ここが足すのは**完成音声の全文**です。台本の1コマずつではなく、
**焼き上がった `final.mp4` の音**を頭から終わりまで刻んで聞き取ります。

## 何と何を突き合わせるか（**カナで**突き合わせる。ここが要）

    予定していた読み   `src/yomi.to_speech(narration)` を open-jtalk の形態素解析に通した発音
                       （＝ **Google に渡した文字列を、こう読むつもりだった**というカナ）
    聞き取った読み     完成音声を音声認識にかけた文字列を、同じ解析に通した発音

**漢字どうしで比べてはいけません。** 音声認識は言語模型を持っているので、
ヒタイ と読まれた「額」を、文脈から「額」と書き戻してしまうことがある ——
**表記で比べると誤読が消えます。** カナで比べれば、
「賃金日額」を「賃金に違く」と書き違えても **チンギンニチガク で一致**し
（＝ 聞き取りの誤りは同音なので消える）、
「額」を ヒタイ と読んだ音は **ガク 対 ヒタイ で割れます**（＝ 読みの誤りだけが残る）。

**2026-09-03 に撃って確かめた**（本番の声 ja-JP-Neural2-D・faster-whisper medium）:

    送った  実際の額は賃金日額で決まります。      （`to_speech` を通さない生の姿）
    聞いた  実際の飛体は賃金日額で決まります。     ← **ヒタイ が表記に出た**
    送った  実際のがくは賃金日額で決まります。      （`to_speech` 済み ＝ いまの本番）
    聞いた  実際の額は賃金日額で決まります。       ← ガクで一致

## 聞き取りの誤りと、読みの誤りを混同しない形（**2回 撃つ**）

カナで比べてもなお、音声認識そのものが外します。だから**名指しの手前に門を3つ**置いた。

    門1  **その語に漢字が無ければ落とす。** 直す当てが無いので名指しに意味が無い
         （実測: 「そのあとは」を認識器が「その後は」と書き、アト 対 ゴ で割れた。
           送った文の側は仮名なので、これは聞き取りの誤り以外ではありえない）
    門1b **活用語の、末尾1モーラだけの違いは落とす。** 動詞・形容詞の末尾は送り仮名 ＝
         **漢字の読みではない**（実測: 認識器が「受け取る」を「受け取り」と書き、
         ウケトル 対 ウケトリ で割れた。頭の ウケトr は一致している）
    門2  **正書法のゆれを畳む**（ハ→ワ・ヘ→エ・ヲ→オ・ヂ→ジ・ヅ→ズ）。
         助詞「は」を open-jtalk は文脈で ワ とも ハ とも読む。読みの誤りではない
    門3  **2回目を撃つ**（`confirm()`）。割れた語を、**予定の読みのカナに置き換えた文**で
         もう一度 合成して聞かせる:

             1回目（漢字のまま）で予定の読みが聞こえた       → 割れは隣の語の巻き添え ＝ **noise**
             1回目では聞こえず、2回目（カナ）で聞こえた      → **Google がその漢字を別に読んでいる ＝ misread**
             どちらでも聞こえない                          → 認識器が届いていない ＝ **unclear**

**misread と出た語だけ**が `data/yomi_ledger.json` に `correct`（＝予定の読み）付きで入り、
`src/yomi_gate.corrections()` → `src/yomi.to_speech()` が次の合成から仮名に置き換えます。
**unclear は止めません**（止めると認識器の弱さで投稿が止まる）。`data/yomi_queue.json` に積んで
耳（`scripts/yomi_ear.py`）に回します。

## 実測（2026-09-03・`data/critique_queue/1huadpEk6HY.script.json` の先頭8コマ・190秒）

    カナの句読点を落とす前   small 87件 / medium 45件 が割れた（**ほぼ全部が「、」の位置**）
    落としたあと            small  9件 / medium  5件
    速さ                    small 音の 0.25倍 / medium 音の 0.54倍（CPU 4本・int8）

**medium を既定にした。** small は「年」を モエ と4回 聞き違えた（＝ 空振りが 2倍近い）。
空振りは2回目を撃つぶん**時間**を食い、取りこぼしは**動画に残る**ので、
`yomi_ear` と同じく拾いすぎる側に置く。

**覆る条件**:
  - 1本 25分の音を 0.54倍で2周すると **27分** 足されます。ここが毎日の投稿を
    遅らせていると実測で分かったら、1周目を `small` にして
    **2回目の確認（`confirm`）だけ medium** にすること（空振りは confirm が落とすので、
    1周目の感度を上げても最終の判定は変わらない）。
  - `misread` と出た語をオーナーが耳で「正しく読めている」と言ったら、
    門2の畳み方（正書法）が足りていない。畳む表を増やすこと。
  - `unclear` が語の1割を超えたら、認識器がこの声に届いていない。
    模型を `large-v3` に上げて測り直すこと。
"""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import yomi_gate as G
from .yomi import to_speech

ROOT = Path(__file__).resolve().parent.parent

#: 音声認識の模型。`YOMI_HEAR_MODEL` で差し替えられる（上の「覆る条件」）。
MODEL_NAME = os.environ.get("YOMI_HEAR_MODEL", "medium")

#: **正書法のゆれ**（門2）。読みの誤りではないので畳む。
_FOLD = str.maketrans({"ヲ": "オ", "ヂ": "ジ", "ヅ": "ズ", "ヰ": "イ", "ヱ": "エ",
                       "ハ": "ワ", "ヘ": "エ"})
#: カタカナと長音符**以外**は全部 落とす（「、」「。」「？」「’」・空白・英数）。
_NOT_KANA = re.compile(r"[^ァ-ヶー]")

_KANJI_RE = re.compile(f"[{G.KANJI}]")

_MODEL = None


def norm(pron: str) -> str:
    """発音カナを、**比べてよい形**にする（門2）。"""
    return _NOT_KANA.sub("", pron or "").translate(_FOLD)


def available() -> bool:
    """聞き取れる環境か。**模型が無い所で投稿を止めないため**に、呼ぶ側が先に見る。"""
    try:
        import faster_whisper  # noqa: F401
    except Exception:                                          # noqa: BLE001
        return False
    return G.available()


def model():
    """認識器を1つだけ立てて使い回す（読み込みに medium で 17秒 かかる）。"""
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel                # noqa: PLC0415
        _MODEL = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8",
                              cpu_threads=int(os.environ.get("YOMI_HEAR_THREADS", "4")))
    return _MODEL


def transcribe(wav: Path) -> str:
    """音を1つ聞き取って、書き起こしの文字列を返す。

    `condition_on_previous_text=False` にしてある —— 既定の True は前のコマの文を
    次のコマの手掛かりにするので、**誤読を「文脈で正しい漢字に直して」しまいます。**
    ここで欲しいのは言語模型の推測ではなく、**その音が何と聞こえたか**です。
    """
    segments, _ = model().transcribe(
        str(wav), language="ja", beam_size=5, vad_filter=False,
        condition_on_previous_text=False,
    )
    return "".join(s.text for s in segments).strip()


def kana_map(text: str) -> tuple[str, list[dict]]:
    """テキストを (畳んだカナ全文, トークンの表) にする。

    トークンは `{"surface","pos","char","k0","k1","pron"}`。
    `char` は元テキストの文字位置、`k0:k1` はカナ全文の中の範囲。
    """
    kana = ""
    out: list[dict] = []
    cursor = 0
    for tok in G.analyze(text):
        surface = tok["surface"]
        at = text.find(surface, cursor)
        if at < 0:
            at = cursor
        pron = norm(tok["pron"])
        out.append({"surface": surface, "pos": tok["pos"], "char": at,
                    "k0": len(kana), "k1": len(kana) + len(pron), "pron": pron})
        kana += pron
        cursor = at + len(surface)
    return kana, out


def _heard_slice(ref: str, heard: str, k0: int, k1: int) -> str:
    """予定カナの `[k0,k1)` に、聞き取りカナの**どこが対応したか**を返す。"""
    sm = difflib.SequenceMatcher(None, ref, heard, autojunk=False)
    lo = hi = None
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if i2 <= k0 or i1 >= k1:
            continue
        # 予定側の [k0,k1) が、この塊のどこに落ちるか
        if tag == "equal":
            a = j1 + max(0, k0 - i1)
            b = j1 + min(i2 - i1, k1 - i1)
        else:
            a, b = j1, j2
        lo = a if lo is None else min(lo, a)
        hi = b if hi is None else max(hi, b)
    return heard[lo:hi] if lo is not None else ""


def compare(spoken: str, heard: str) -> list[dict]:
    """**渡した文字列**と**聞き取った文字列**をカナで突き合わせ、割れた語を名指しする。

    返すのは `{"surface","pron","heard","k0","k1","pos"}` の並び。
    門1（漢字を含まない語は落とす）はここで当たっています。
    """
    ref, toks = kana_map(spoken)
    got, _ = kana_map(heard)
    if not ref:
        return []
    sm = difflib.SequenceMatcher(None, ref, got, autojunk=False)
    bad: list[tuple[int, int]] = [(i1, i2) for tag, i1, i2, _j1, _j2
                                  in sm.get_opcodes() if tag != "equal"]
    hits: list[dict] = []
    seen: set[int] = set()
    for i1, i2 in bad:
        lo, hi = i1, max(i2, i1 + 1)          # 差し込み（i1==i2）は隣の語に当てる
        for n, tok in enumerate(toks):
            if n in seen or tok["k1"] <= lo or tok["k0"] >= hi:
                continue
            if not _KANJI_RE.search(tok["surface"]):
                continue                       # 門1: 直す当ての無い語
            seen.add(n)
            got_here = _heard_slice(ref, got, tok["k0"], tok["k1"])
            if _tail_only(tok, got_here):
                continue                       # 門1b: 送り仮名の差
            hits.append({"surface": tok["surface"], "pron": tok["pron"], "pos": tok["pos"],
                         "k0": tok["k0"], "k1": tok["k1"], "heard": got_here})
    return hits


#: 活用する品詞。末尾のモーラは**送り仮名**で、漢字の読みではない（門1b）。
_INFLECTS = ("動詞", "形容詞", "助動詞")


def _tail_only(tok: dict, heard: str) -> bool:
    """活用語で、**末尾1モーラだけ**が違うか（＝ 送り仮名の書き違い）。

    **覆る条件**: 1文字の動詞（「観る」「経る」）で頭が1モーラしかない語は、
    ここが「末尾だけ」を「全部」と取り違えます。だから
    **予定の読みが2モーラ以上あるときだけ**当てています。
    そこを外した誤読が出たら、この門を品詞ではなく
    「表層の末尾が仮名かどうか」で切り直すこと。
    """
    want = tok["pron"]
    if tok["pos"] not in _INFLECTS or len(want) < 2:
        return False
    return len(heard) == len(want) and heard[:-1] == want[:-1]


# ---------------------------------------------------------------- 2回目を撃つ

def _synth(text: str, dest: Path, tts_cfg: dict | None = None) -> None:
    """**本番と同じ口**で合成する（`src/tts._google`）。"""
    from . import tts                                          # noqa: PLC0415
    cfg = dict(tts_cfg or {})
    cfg.setdefault("voice", "ja-JP-Neural2-D")
    tts._google(text, dest, cfg)


def confirm(spoken: str, hit: dict, tts_cfg: dict | None = None) -> str:
    """割れた語を**もう1回 撃って**、聞き取りの誤りと読みの誤りを分ける（門3）。

    返すのは `"noise"` / `"misread"` / `"unclear"`。判定の表は module の docstring。
    """
    want = hit["pron"]
    if not want:
        return "unclear"
    if hit["heard"] == want:
        return "noise"                         # 割れは隣の語の巻き添えだった
    # 予定の読みのカナに差し替えた文を作る（その1か所だけ）
    idx = spoken.find(hit["surface"])
    if idx < 0:
        return "unclear"
    swapped = spoken[:idx] + want + spoken[idx + len(hit["surface"]):]
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "b.wav"
        try:
            _synth(swapped, wav, tts_cfg)
            heard_b = transcribe(wav)
        except Exception:                                      # noqa: BLE001
            return "unclear"                   # 鍵が無い・網が落ちた ＝ 止めない
    ref_b, toks_b = kana_map(swapped)
    span = next(((t["k0"], t["k1"]) for t in toks_b
                 if t["char"] <= idx < t["char"] + len(t["surface"])), None)
    if span is None:
        return "unclear"
    got_b = _heard_slice(ref_b, kana_map(heard_b)[0], *span)
    return "misread" if got_b == want else "unclear"


# ---------------------------------------------------------------- 全文を聞く

def hear(lines: list[str], wavs: list[Path], *, tts_cfg: dict | None = None,
         confirm_hits: bool = True, log=print) -> dict:
    """**読み上げの全文**を聞いて、割れた語を判定した表を返す。

    `lines` は台本の読み上げ（漢字のまま）、`wavs` はそのコマの**完成音声**。
    数が違えば「全文」を名乗れないので、そこで落とす。
    """
    if len(lines) != len(wavs):
        raise ValueError(f"行 {len(lines)} と音 {len(wavs)} の数が違う（全文にならない）")
    rows: list[dict] = []
    words = 0
    for i, (line, wav) in enumerate(zip(lines, wavs)):
        spoken = to_speech(str(line))
        _ref, toks = kana_map(spoken)
        words += sum(1 for t in toks if _KANJI_RE.search(t["surface"]))
        try:
            heard = transcribe(Path(wav))
        except Exception as exc:                               # noqa: BLE001
            raise RuntimeError(f"セグメント{i + 1} を聞き取れない: {type(exc).__name__}") from exc
        for hit in compare(spoken, heard):
            hit.update({"seg": i, "sentence": line, "spoken": spoken})
            rows.append(hit)
    # **同じ語は1回だけ確かめる**（2回目は合成と認識で1語 数秒かかる）
    verdicts: dict[tuple[str, str], str] = {}
    for row in rows:
        key = (row["surface"], row["pron"])
        if not confirm_hits:
            row["verdict"] = "unclear"
            continue
        if key not in verdicts:
            verdicts[key] = confirm(row["spoken"], row, tts_cfg)
            log(f"   -- {row['surface']}（予定 {row['pron']} / 聞いた {row['heard'] or '－'}）"
                f" → {verdicts[key]}")
        row["verdict"] = verdicts[key]
    return {"lines": len(lines), "words": words, "split": len(rows), "hits": rows}


def record(report: dict) -> dict:
    """`misread` を台帳に入れ、`unclear` を待ち行列に積む。

    台帳に `correct`（＝予定の読み）まで入るので、次の合成から
    `src/yomi.to_speech()` が自動で仮名に置き換えます（`yomi_gate.corrections()`）。
    **1文字の語は `corrections()` が弾く**ので（活用語幹を巻き込むため）、
    ここでも台帳には入れますが直りません —— そのぶんは `src/yomi.FIXES` に
    文脈つきで入れること（`yomi_gate.corrections()` の docstring）。
    """
    blob = G._load(G.LEDGER_PATH)
    store = dict(blob.get("words", {}))
    fixed: dict[str, str] = {}
    for row in report["hits"]:
        if row.get("verdict") != "misread":
            continue
        word, want = row["surface"], row["pron"]
        store[word] = {"word": word, "kana": want, "sentence": row["sentence"],
                       "verdict": "misread", "correct": want, "heard": row["heard"],
                       "settled": True, "by": "hear"}
        fixed[word] = want
    if fixed:
        blob["words"] = store
        blob.setdefault("at", G._now())
        blob["at"] = G._now()
        tmp = G.LEDGER_PATH.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(blob, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(G.LEDGER_PATH)
    unclear = [{"code": "H1", "surface": r["surface"],
                "why": f"完成音声で読みが割れたが、聞き取りでは決められなかった"
                       f"（予定 {r['pron']} / 聞いた {r['heard'] or '－'}）。"}
               for r in report["hits"] if r.get("verdict") == "unclear"]
    if unclear:
        G.queue(unclear)
    return fixed


# ---------------------------------------------------------------- 毎本の門

#: 仕事場に残す照合の控え。`src/verify._check_yomi_heard()` がこれを見て門にする。
REPORT_NAME = "yomi_hear.json"


def fingerprint(lines: list[str]) -> str:
    """読み上げ全文の指紋。**控えが本当にこの本のものか**を verify が確かめるのに使う。"""
    import hashlib
    body = "\n".join(str(x) for x in lines).encode("utf-8")
    return hashlib.sha256(body).hexdigest()[:16]


def audit(lines: list[str], wavs: list[Path], work: Path, *, tts_cfg: dict | None = None,
          resynth=None, log=print) -> dict:
    """**毎本これを撃つ。** オーナーの1文をそのまま形にしたもの。

        1. 完成音声の最初から最後までを機械で聞き取る       （`hear()`）
        2. 予定していた読みと照合する                     （カナで・門1〜門3）
        3. 誤読があれば修正（台帳）・再生成（`resynth()`）
        4. **もう一度 全文照合する**                      （`hear()` をもう1周）

    `resynth()` が無ければ 3・4 は飛ばして、誤読を控えに残すだけ（`verify` が落とす）。
    **1周しか直しません** —— 2周目でまだ誤読が残るなら、それは仮名置換で直らない形
    （熟語の中の1字など。`yomi_gate.corrections()` の docstring）なので、
    機械が直せないことを名指しして止めるほうが正しい。
    """
    report = hear(lines, wavs, tts_cfg=tts_cfg, log=log)
    report["passes"] = 1
    misread = [r for r in report["hits"] if r["verdict"] == "misread"]
    fixed = record(report)
    if misread and resynth is not None and fixed:
        log(f"[hear] 誤読 {len(misread)}件 を直して焼き直します"
            f"（{'・'.join(f'{w}→{k}' for w, k in fixed.items())}）")
        wavs = resynth()
        report = hear(lines, wavs, tts_cfg=tts_cfg, log=log)
        report["passes"] = 2
        report["fixed"] = fixed
        record(report)
    report["at"] = G._now()
    report["model"] = MODEL_NAME
    report["fingerprint"] = fingerprint(lines)
    report["misread"] = sum(1 for r in report["hits"] if r["verdict"] == "misread")
    work.mkdir(parents=True, exist_ok=True)
    (work / REPORT_NAME).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    log(f"[hear] {report['lines']}行 / 漢字の語 {report['words']}語 を照合 "
        f"→ 割れ {report['split']}件・誤読 {report['misread']}件"
        f"（{report['passes']}周目）")
    return report


def say(row: dict) -> str:
    """門が落とすときの1行。"""
    return (f"セグメント{row['seg'] + 1} の「{row['surface']}」を、"
            f"完成音声では {row['heard'] or '別の音'} と読んでいる"
            f"（予定は {row['pron']}）")


# ---------------------------------------------------------------- 完成音声を刻む

def probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True)
    try:
        return float(out.stdout.decode().strip())
    except ValueError:
        return 0.0


def slice_final(video: Path, durations: list[float], out_dir: Path) -> list[Path]:
    """**完成した動画の音**を、コマの秒数で刻んで wav にする。

    セグメントの wav をそのまま聞くのではなく、ここを通すのは
    オーナーの言葉が「**完成音声**の最初から最後まで」だからです ——
    `src/renderer.build_video()` は concat のあと `loudnorm` を掛け AAC に落とすので、
    **出て行く音はセグメントの wav そのものではありません**。
    音量の正規化と符号化は読みを変えませんが、**繋ぎ間違い・欠け・入れ替わりは変えます。**
    ここを通せば、その3つも一緒に見えます。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    start = 0.0
    for i, dur in enumerate(durations):
        dest = out_dir / f"heard_{i:03d}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
             "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(dest)],
            check=True, capture_output=True,
        )
        paths.append(dest)
        start += dur
    return paths
