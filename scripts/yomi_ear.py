#!/usr/bin/env python3
"""耳の門 —— **候補を人が書かずに、本番エンジンの誤読を名指しする**（2026-09-02）。

    python scripts/yomi_ear.py --limit 40        # 危ない語の上から40語を耳で判定
    python scripts/yomi_ear.py --word 額         # 1語だけ
    python scripts/yomi_ear.py --report          # 台帳を読むだけ（API を撃たない）

## `probe_yomi.py` と何が違うか（**ここが「1語ずつ」をやめる所**）

`scripts/probe_yomi.py` は **候補の読みを人が渡す**（`--candidates がく ひたい`）。
だから **1語 直すのに人が1回 考える**。オーナーの「全部正しくして」は、
その形をやめろという意味（`CLAUDE.md` 固定その3）。

ここは候補を要らなくする。測るのは**2つのエンジンが一致しているか**だけ:

    A: その文をそのまま Google TTS で合成（＝本番の音）
    B: 同じ文の、その語だけを **open-jtalk の読み（カタカナ）** に置換して合成

**B は「open-jtalk がそう読むつもりの音」そのもの**なので、
A と B が近ければ2つのエンジンは一致、離れていれば**割れている**。
割れている語は、どちらが正しいかに関わらず**本番で何を読むか誰も知らない語**なので、
門で止める。候補は1つも書かない。

## 目盛りをどこに置くか（**推測しない**）

距離の絶対値には意味が無いので、**同じ回に測った全語の分布**を目盛りにする。
`--limit N` で N語 測り、中央値と MAD（中央絶対偏差）を出して、
**中央値 + 3×MAD** を超えた語を `misread` にする。基準は `data/yomi_ledger.json`
に一緒に書き込むので、後の回が同じ目盛りで読める。

## 目盛りの検算（2026-09-02 に**実際に撃った数**。写しではない）

    危ない語 17語の分布         中央値 0.256 / MAD 0.035 → 目盛り 0.361
    額（既知の誤読・raw）        **0.489**  ← 目盛りの上。**予測どおり外れ値に落ちた**
    賃金（正しく読めている）      0.373     ← わずかに上（**取りこぼしではなく空振り**）
    実際（正しく読めている）      0.303     ← 下

同じ文を旧 `probe_yomi.py`（候補つき）で測ると
**ひたい 0.319 対 がく 0.463** —— **2026-09-02 のいまも Google は「ひたい」と読む。**
つまりこの誤読は 2026-08-16 の置換で**隠してあるだけ**で、消えてはいない。

**空振りの側は安い**（その語が耳の待ち行列に1つ増えるだけ）が、
**取りこぼしは動画に残る**。オーナーは「読みの誤りは1つも許されません」と言っている
（`CLAUDE.md` 固定その3）。だから既定は**拾いすぎる側**（3×MAD）に置いてある。

**覆る条件**:
  - `misread` にした語を `probe_yomi.py --text ... --candidates ...` で
    追試して、9割が正しく読めていた → 目盛りが厳しすぎる（`--sigma` を上げる）。
  - 逆に、耳で誤読と分かった語がここの目盛りの下に居た → 距離の作り方
    （`probe_yomi.feats`）が読みの違いに反応していない。帯域数を変えて測り直すこと。

## **距離は「割れている」までしか言わない。どちらが正しいかは言わない**

2026-09-02 の実測で両方向が出た:

    額  open-jtalk ガク が正しく、Google の ヒタイ が誤り
    年  open-jtalk トシ が誤りで、Google の ネン が正しい（「年15万円」の文脈）

**だから `verdict: misread` だけでは自動置換しない。**
向きを確かめて `correct` の欄を埋めた語だけが `src/yomi.to_speech()` に載る
（`src/yomi_gate.corrections()`）。向きの確認は
`probe_yomi.py --text <文> --word <語> --candidates <読み> <読み>`。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import yomi_gate as G  # noqa: E402
from src.yomi import to_speech  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STASH = ROOT / "data" / "critique_queue"
LEDGER = G.LEDGER_PATH
KANJI = re.compile(f"[{G.KANJI}]")


def sentences_for(word: str, cap: int = 1) -> list[str]:
    """その語が実際に出てくる**公開ずみの文**を拾う。作った文では測らない。"""
    out = []
    for path in sorted(STASH.glob("*.json")):
        if path.name.endswith(".plan.json"):
            continue
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for line in meta.get("narration") or []:
            s = str(line)
            if word in s and 8 <= len(s) <= 60:
                out.append(s)
                if len(out) >= cap:
                    return out
    return out


def distance(sentence: str, word: str, kana: str, raw: bool = False) -> float:
    """A（そのまま）と B（その語だけ open-jtalk の読みに置換）の音の距離。

    `raw=True` は `to_speech()` の置換を通さない。**目盛りの検算専用** ——
    既に直っている語（「額」）を、直す前の姿で測って外れ値に落ちるか見るため。
    """
    from scripts.probe_yomi import dtw, feats, synth

    spoken = sentence if raw else to_speech(sentence)
    if word not in spoken:
        raise LookupError(word)
    swapped = spoken.replace(word, kana, 1)
    return dtw(feats(synth(spoken)), feats(synth(swapped)))


def _median(xs: list[float]) -> float:
    ys = sorted(xs)
    n = len(ys)
    return ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--word")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--sigma", type=float, default=3.0, help="中央値 + この数×MAD で切る")
    ap.add_argument("--raw", action="store_true", help="to_speech() を通さずに測る（目盛りの検算用）")
    ap.add_argument("--dry", action="store_true", help="台帳に書かない")
    args = ap.parse_args()

    if args.report:
        blob = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
        words = blob.get("words", {})
        bad = {k: v for k, v in words.items() if v.get("verdict") == "misread"}
        print(f"[ear] {blob.get('at', '?')} / 測った語 {len(words)} / "
              f"**割れていた語 {len(bad)}** / 目盛り {blob.get('cut', '?')}")
        for k, v in sorted(bad.items(), key=lambda kv: -kv[1].get("dist", 0)):
            print(f"   {k:<8} 距離 {v.get('dist'):.3f}  読み {v.get('kana')}  {v.get('sentence', '')[:34]}")
        return 0

    if not os.environ.get("GOOGLE_TTS_API_KEY"):
        print("[ear] GOOGLE_TTS_API_KEY が無いので測れません")
        return 2
    if not G.available():
        print("[ear] open-jtalk が無いので読みが取れません")
        return 2

    risk = G.load_risk()
    words = [args.word] if args.word else sorted(risk, key=lambda w: (-len(risk[w]), -len(w)))
    words = [w for w in words if w][:args.limit]

    rows: list[dict] = []
    for w in words:
        sents = sentences_for(w)
        if not sents:
            continue
        sent = sents[0]
        try:
            toks = G.analyze(sent if args.raw else to_speech(sent))
        except RuntimeError:
            continue
        kana = next((t["pron"] for t in toks if t["surface"] == w and t["pron"] not in G._SILENT), "")
        if not kana:
            continue
        try:
            d = distance(sent, w, kana, raw=args.raw)
        except Exception as exc:            # 通信・音の失敗はその語を飛ばす（黙って通さない）
            print(f"   -- {w}: 測れず {type(exc).__name__}", flush=True)
            continue
        rows.append({"word": w, "kana": kana, "dist": round(d, 4), "sentence": sent})
        print(f"   {w:<8} {d:.3f}  ({kana})  {sent[:30]}", flush=True)

    if not rows:
        print("[ear] 測れた語が 0。data/yomi_risk.json を先に作ること（scripts/yomi_audit.py）")
        return 1

    ds = [r["dist"] for r in rows]
    med = _median(ds)
    mad = _median([abs(d - med) for d in ds]) or 1e-6
    cut = med + args.sigma * mad
    if args.dry:
        print(f"\n[ear] --dry: 台帳に書きません（中央値 {med:.3f} / MAD {mad:.3f} / 目盛り {cut:.3f}）")
        return 0
    prev = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
    store = prev.get("words", {})
    for r in rows:
        r["verdict"] = "misread" if r["dist"] > cut else "safe"
        r["by"] = "ear"
        store[r["word"]] = r
    LEDGER.write_text(json.dumps(
        {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cut": round(cut, 4),
         "median": round(med, 4), "mad": round(mad, 4), "sigma": args.sigma,
         "words": store}, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in rows if r["verdict"] == "misread"]
    print(f"\n[ear] 測った語 {len(rows)} / 中央値 {med:.3f} / MAD {mad:.3f} / "
          f"目盛り {cut:.3f} → **割れていた語 {len(bad)}**: "
          f"{', '.join(r['word'] for r in bad) or 'なし'}  → {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
