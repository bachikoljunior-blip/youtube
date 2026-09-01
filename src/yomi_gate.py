"""読みの門 —— **語を1つずつ直す形をやめるための層**（2026-09-02）。

## なぜ要るか（オーナー原文・`CLAUDE.md` 固定その3）

> **「ナレーションの漢字の読み方全部正しくして」**

2026-08-16、オーナーが耳で「額」が「ひたい」と読まれているのを見つけた。
そのとき直したのは**裸の「額」1語だけ**（`src/yomi.FIXES`）。

**この回に数えた: 公開ずみ 694本・読み上げ 6,206行・漢字のかたまり 異なり 3,514語。
そのうち `src/verify._check_yomi` が見ていた語は 1語（0.03%）。**
残り 3,513語 は**誰も見ていない**。「全部正しくして」に対して 0.03% は最適化ではない。

## この層が変えること —— 既定を反転する

古い形: **既知の壊れる語を並べて、それが残っていたら落とす**（`BROKEN_SHAPES`）。
        → 並べていない語は**無検査で通る**。語を足すまで直らない。

この層: **読み上げに出る漢字を全部 形態素解析にかけ、危ない形を機械が名指しする**。
        → 語の一覧は要らない。**危ない条件のほうを書く。**

## 危ない条件（語の一覧ではなく、形で決めている）

    R0 落ちる   漢字なのに発音が空 or 「、」 ＝ **その字は音から消える**（無条件で落とす）
    R1 割れる   同じ表層が文脈で別の発音になる ＝ **エンジン間でも割れうる**
    R2 刻まれる 漢字の連なりが1文字トークンに刻まれている ＝ 辞書に無い並び
    R3 台帳     `data/yomi_ledger.json` が `misread` と判定した語が漢字のまま残っている

R1 の「割れる」は**この repo の読み上げ 6,206行を実際に通して測った**もので
（`scripts/yomi_audit.py` → `data/yomi_risk.json`）、推測ではない。

## 何が確かめられて、何が確かめられないか（**ここを混ぜないこと**）

open-jtalk は**本番のエンジンではない**。本番は Google Cloud TTS。
この回に撃って確かめた: **open-jtalk は「実際の額は…」を ガク と読む** ——
つまり**オーナーが実際に踏んだ誤読を、open-jtalk は再現できない。**
`scripts/check_yomi.py` が「合格」と言っていたのは、`to_speech()` が先に仮名へ
置換していたからで、**門が誤りを見つけたのではない。**

だから**判定するのは耳のほう**（`scripts/probe_yomi.py`）。この層は
**耳に何を聞かせるかを決める**（＝候補を全語から漏れなく作る）役で、
最終判定は `data/yomi_ledger.json` に入る。

**覆る条件**: R1/R2 で名指しした語のうち、耳で測って `safe` の割合が
9割を超えたら、その条件は候補として粗すぎる（絞り込みを足すこと）。
逆に耳が `misread` と言った語が R0〜R2 のどれにも掛からなかったら、
**条件が足りていない**（その形を足すこと）。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICT = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE = "/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice"

RISK_PATH = ROOT / "data" / "yomi_risk.json"
LEDGER_PATH = ROOT / "data" / "yomi_ledger.json"

KANJI = r"一-鿿々〇"
_KANJI_RE = re.compile(f"[{KANJI}]")
_KANJI_RUN = re.compile(f"[{KANJI}]+")

#: 発音の欄がこれなら「音にならなかった」。open-jtalk は読めない字を記号にして落とす。
_SILENT = {"", "、", "*", "。"}


def available() -> bool:
    return bool(shutil.which("open_jtalk")) and Path(DICT).exists() and Path(VOICE).exists()


def analyze(text: str) -> list[dict]:
    """1行を形態素解析して、トークンごとの (表層, 品詞, 読み, 発音) を返す。

    **open-jtalk は入力の1行目しか解析しない**（この回に実測）。改行を含む
    文字列を渡すと2行目から先が黙って落ちるので、ここで改行を潰しておく。
    """
    one = " ".join(text.splitlines()).strip()
    if not one:
        return []
    with tempfile.TemporaryDirectory() as td:
        trace = Path(td) / "trace.txt"
        proc = subprocess.run(
            ["open_jtalk", "-x", DICT, "-m", VOICE,
             "-ot", str(trace), "-ow", str(Path(td) / "o.wav")],
            input=one.encode("utf-8"), capture_output=True,
        )
        if proc.returncode != 0 or not trace.exists():
            raise RuntimeError(
                f"open_jtalk 失敗: {proc.stderr.decode('utf-8', 'ignore')[:200]}")
        out: list[dict] = []
        for line in trace.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                break                      # 空行から先は音響パラメータ
            f = line.split(",")
            if len(f) < 10:
                continue                   # "[Text analysis result]" の見出し
            out.append({"surface": f[0], "pos": f[1], "pos2": f[2],
                        "base": f[7], "yomi": f[8], "pron": f[9].replace("’", "")})
        return out


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_risk() -> dict:
    """`scripts/yomi_audit.py` が公開ずみ全文から作った「割れる語」の表。"""
    return _load(RISK_PATH).get("split", {})


def load_ledger() -> dict:
    """耳（`scripts/probe_yomi.py`）が出した語ごとの判定。"""
    return _load(LEDGER_PATH).get("words", {})


def inspect(text: str, risk: dict | None = None, ledger: dict | None = None) -> list[dict]:
    """1行ぶんの危ない形を返す。**語の一覧ではなく、形で決めている。**

    返すのは `{"code","surface","pron","why"}` の並び。空なら危ない形は無い。
    """
    risk = load_risk() if risk is None else risk
    ledger = load_ledger() if ledger is None else ledger
    toks = analyze(text)
    found: list[dict] = []
    named: set[str] = set()
    for t in toks:
        s = t["surface"]
        if not _KANJI_RE.search(s):
            continue
        pron = t["pron"]
        if pron in _SILENT:
            found.append({"code": "R0", "surface": s, "pron": pron,
                          "why": f"「{s}」が音にならない（発音の欄が空）"})
            named.add(s)
            continue
        entry = ledger.get(s) or {}
        if entry.get("verdict") == "misread":
            found.append({"code": "R3", "surface": s, "pron": pron,
                          "why": f"「{s}」は耳の実測で誤読（{entry.get('heard', '?')}）。"
                                 f"仮名に置き換えること"})
            named.add(s)
            continue
        if entry.get("verdict") == "safe":
            continue                        # 耳が通した語はここで終わり
        prons = risk.get(s)
        if prons and len(prons) > 1:
            found.append({"code": "R1", "surface": s, "pron": pron,
                          "why": f"「{s}」は文脈で読みが割れる（実測 {'/'.join(sorted(prons))}）。"
                                 f"耳で判定するまで通せない"})
            named.add(s)
    # R2: 漢字の連なりが1文字トークンに刻まれている（辞書に無い並び）
    singles = {t["surface"] for t in toks
               if len(t["surface"]) == 1 and _KANJI_RE.search(t["surface"])}
    joined = "".join(t["surface"] for t in toks)
    for run in _KANJI_RUN.findall(joined):
        if len(run) < 3 or run in named:
            continue
        inside = sorted(c for c in singles if c in run)
        if inside:
            found.append({"code": "R2", "surface": run, "pron": "",
                          "why": f"「{run}」が1文字に刻まれている（{'・'.join(inside)}）。"
                                 f"辞書に無い並びで、エンジンごとに読みが変わる"})
            named.add(run)
    return found


def problems(script: dict, spoken_of=None) -> list[str]:
    """台本1本ぶん。**読み上げに渡る文字列**（`to_speech()` 済み）を見る。"""
    if not available():
        return []
    from .yomi import to_speech
    spoken_of = spoken_of or to_speech
    risk, ledger = load_risk(), load_ledger()
    out: list[str] = []
    for i, seg in enumerate(script.get("segments", []) or []):
        text = str(seg.get("narration") or "")
        if not text.strip():
            continue
        try:
            hits = inspect(spoken_of(text), risk, ledger)
        except RuntimeError:
            return []                       # 解析器が動かない環境では黙って通す
        for h in hits:
            out.append(f"セグメント{i + 1} {h['code']}: {h['why']}")
    return out
