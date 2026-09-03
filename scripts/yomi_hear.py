#!/usr/bin/env python3
"""**完成音声を最初から最後まで聞き取り、予定の読みと全文で照合する**（2026-09-03）。

    # 焼き上がった本を、完成した mp4 の音で照合する（`verify` が撃つのと同じ道）
    python scripts/yomi_hear.py --work build/2026-09-04

    # 台本しか残っていない本（公開ずみ）を、同じ声で焼き直して照合する
    python scripts/yomi_hear.py --script data/critique_queue/1huadpEk6HY.script.json

    # 誤読を台帳へ入れる（次の合成から `src/yomi.to_speech()` が直す）
    python scripts/yomi_hear.py --script ... --apply

    # 直したあとの**もう一度の全文照合**（--apply のあとに、同じ本をもう一度）
    python scripts/yomi_hear.py --script ... --again

なぜ要るかと、判定の作り方は `src/yomi_hear.py` の docstring に全部あります。
ここはその口です。**判定の規則をここに書かないこと**（2か所に分かれると静かにずれます）。

## **(c) わざと寝かせてある —— 毎本の照合は `src/verify.py`（`_check_yomi_heard`）が回します。ここは**手で当てる口**です**（2026-09-03 に決めた）

**どこからも撃たれていないのが正しい形です。**（`scripts/retro.py` の三択を、この回が (c) で倒しました。**やり直さないこと**）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import yomi_hear as H          # noqa: E402
from src.yomi import to_speech          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _lines(script: dict) -> list[str]:
    return [str(s.get("narration") or "") for s in script.get("segments", [])
            if str(s.get("narration") or "").strip()]


def from_work(work: Path, limit: int) -> tuple[list[str], list[Path], str]:
    """焼き上がった仕事場から。**完成した mp4 の音**を刻んで聞く。"""
    script = json.loads((work / "script.json").read_text(encoding="utf-8"))
    lines = _lines(script)[:limit] if limit else _lines(script)
    final = work / "final.mp4"
    segs = sorted((work / "audio").glob("seg_*.wav"))
    if not segs:
        raise SystemExit(f"{work}/audio に音がありません")
    durations = [H.probe_duration(p) for p in segs][:len(lines)]
    if final.exists():
        total_final = H.probe_duration(final)
        total_seg = sum(H.probe_duration(p) for p in segs)
        if abs(total_final - total_seg) > 1.0:
            print(f"[hear] 注意: 完成 {total_final:.1f}秒 とコマの合計 {total_seg:.1f}秒 が"
                  f"食い違う（繋ぎのどこかが落ちている可能性）")
        return lines, H.slice_final(final, durations, work / "heard"), "完成した mp4"
    return lines, segs[:len(lines)], "コマの wav（final.mp4 がまだ無い）"


def from_script(path: Path, limit: int, out: Path) -> tuple[list[str], list[Path], str]:
    """台本から。**本番と同じ声で焼き直して**聞く（公開ずみの本を当てるときの道）。"""
    script = json.loads(path.read_text(encoding="utf-8"))
    lines = _lines(script)
    if limit:
        lines = lines[:limit]
    out.mkdir(parents=True, exist_ok=True)
    wavs = []
    for i, line in enumerate(lines):
        wav = out / f"seg_{i:03d}.wav"
        if not wav.exists():
            H._synth(to_speech(line), wav)
        wavs.append(wav)
    return lines, wavs, "台本から焼き直した音"


def recompare(path: Path, out: Path | None) -> int:
    """**聞き取りの結果を貯めてあるので、照合だけ引き直せる。**

    門の目盛り（`WINDOW`・畳む表・門1b）を動かしたときに、
    **同じ音・同じ書き起こしで**空振りが何件 変わったかを、
    API も模型も撃たずに数えるための道。**1本 15分 の聞き取りを何度もやり直さないこと。**
    """
    blob = json.loads(path.read_text(encoding="utf-8"))
    texts = blob.get("heard_text") or []
    if not texts:
        print("[hear] この控えには聞き取りの文が入っていません（古い版）")
        return 2
    lines: dict[int, str] = {}
    for row in blob.get("hits", []):
        lines[row["seg"]] = row["sentence"]
    rows = []
    for i, heard in enumerate(texts):
        line = lines.get(i)
        if line is None:
            continue                            # 割れが1件も無かったコマは文が残っていない
        spoken = to_speech(line)
        for hit in H.compare(spoken, heard):
            hit.update({"seg": i, "sentence": line, "spoken": spoken})
            rows.append(hit)
    rows = H.judge(rows, confirm_hits=False)
    print(f"[hear] 引き直し: 割れ {blob.get('split', '?')}件 → {len(rows)}件")
    for row in rows:
        print(f"    セグメント{row['seg'] + 1} 「{row['surface']}」"
              f" 予定 {row['pron']} / 聞いた {row['heard'] or '－'}")
    if out:
        blob["hits"], blob["split"] = rows, len(rows)
        out.write_text(json.dumps(blob, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, help="焼き上がった仕事場（script.json と audio/ がある）")
    ap.add_argument("--script", type=Path, help="台本 json（公開ずみの本を当てるとき）")
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "yomi_hear",
                    help="--script のとき、焼き直した音を置く所")
    ap.add_argument("--limit", type=int, default=0, help="先頭 N コマだけ（試すとき）")
    ap.add_argument("--apply", action="store_true",
                    help="misread を台帳へ・unclear を待ち行列へ入れる")
    ap.add_argument("--again", action="store_true",
                    help="直したあとの**もう一度の全文照合**（音を焼き直してから聞く）")
    ap.add_argument("--json", type=Path, help="結果をここに書く")
    ap.add_argument("--recompare", type=Path,
                    help="前に書いた --json を読み、**聞き取りをやり直さずに**照合だけ引き直す"
                         "（門の目盛りを動かしたときの検算。API も模型も撃たない）")
    args = ap.parse_args(argv)

    if args.recompare:
        return recompare(args.recompare, args.json)
    if not H.available():
        print("[hear] 聞き取れる環境ではありません"
              " （pip install faster-whisper / open-jtalk のどちらかが無い）")
        return 2
    if not (args.work or args.script):
        ap.error("--work か --script のどちらかが要ります")

    if args.work:
        lines, wavs, how = from_work(args.work, args.limit)
    else:
        out = args.out / args.script.stem
        if args.again:
            for old in out.glob("seg_*.wav"):
                old.unlink()                    # 直した読みで焼き直す
        lines, wavs, how = from_script(args.script, args.limit, out)

    audio = sum(H.probe_duration(p) for p in wavs)
    print(f"[hear] {how}: {len(lines)}行 / {audio / 60:.1f}分 / 模型 {H.MODEL_NAME}")
    t0 = time.time()
    report = H.hear(lines, wavs)
    took = time.time() - t0
    kinds = {}
    for row in report["hits"]:
        kinds[row["verdict"]] = kinds.get(row["verdict"], 0) + 1
    print(f"[hear] {report['lines']}行 / 漢字の語 {report['words']}語 を照合"
          f" → 割れ {report['split']}件"
          f"（{'・'.join(f'{k} {v}' for k, v in sorted(kinds.items())) or 'なし'}）"
          f" / {took:.0f}秒（音の {took / max(audio, 1):.2f}倍）")
    for row in report["hits"]:
        mark = "**" if row["verdict"] == "misread" else "  "
        print(f" {mark} セグメント{row['seg'] + 1} 「{row['surface']}」"
              f" 予定 {row['pron']} / 聞いた {row['heard'] or '－'} → {row['verdict']}")

    if args.apply:
        fixed = H.record(report)
        print(f"[hear] 台帳に入れた誤読 {len(fixed)}語"
              f"{'（' + '・'.join(f'{w}→{k}' for w, k in fixed.items()) + '）' if fixed else ''}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    misread = sum(1 for r in report["hits"] if r["verdict"] == "misread")
    return 1 if misread else 0


if __name__ == "__main__":
    raise SystemExit(main())
