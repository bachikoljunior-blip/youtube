#!/usr/bin/env python3
"""読みの検査。**API キーも音声ファイルも要らない。**

`src/yomi.py` の直しが効いているかを、open-jtalk の形態素解析（`-ot`）で検算する。
open-jtalk は音を出す前に「どう読むつもりか」をテキストで吐くので、
**耳を使わずに読みを固定できる**。

    python scripts/check_yomi.py                 # 直しの回帰検査
    python scripts/check_yomi.py <script.json>   # 台本1本ぶんを通す

## **【2026-09-02】ここは「置換の回帰検査」であって、読みの門ではありません**

**この道具は、オーナーが実際に踏んだ誤読を再現できません。** その回に撃って確かめた:
**open-jtalk は「実際の額は賃金日額で決まります。」を ガク と読みます** ——
Google が ヒタイ と読んだ、まさにその文です。ここが「合格」と言うのは
`to_speech()` が先に仮名へ置換しているからで、**門が誤りを見つけたのではありません。**

**全語を見る門は別に在ります**（オーナー原文「漢字の読み方**全部**正しくして」）:

    src/yomi_gate.py        読み上げの漢字を全部 形態素解析にかけ、危ない形を名指し
                            （`src/verify._check_yomi` から毎回 撃たれます）
    scripts/yomi_audit.py   公開ずみ全文で「文脈で読みが割れる語」を実測
    scripts/yomi_ear.py     本番の Google と open-jtalk の一致を測り、向きまで決める

**ここに語を足していく形に戻らないこと。** `FIXES` は種であって、一覧ではありません。

見ているのは3つ。

  1. `cases` の文を `to_speech()` に通したあと、目的の語が `expect` の読みになるか
  2. `untouched` の複合語を巻き込んでいないか（控除額を「こうじょがく」に壊していないか）
  3. `to_speech()` のあとに、既知の壊れる形が残っていないか

**なぜ open-jtalk で Google の誤読を検算できるのか。** できない。だから直し方を
「TTS に渡す文字列から漢字ごと消す」ことにしてある。渡す文字列に「額」が
1文字も無ければ、Google は「ひたい」と読みようがない。ここで確かめているのは
**その置換が本当に意図した読みになっているか**で、Google 側の実測は
`scripts/probe_yomi.py`（耳のほう）の担当。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.yomi import FIXES, remaining_risks, to_speech  # noqa: E402

DICT = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE = "/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice"


def readings(text: str) -> list[tuple[str, str]]:
    """(表層形, カタカナ読み) の並びを返す。open-jtalk が無ければ空。"""
    with tempfile.TemporaryDirectory() as td:
        trace = Path(td) / "trace.txt"
        proc = subprocess.run(
            ["open_jtalk", "-x", DICT, "-m", VOICE,
             "-ot", str(trace), "-ow", str(Path(td) / "o.wav")],
            input=text.encode("utf-8"), capture_output=True,
        )
        if proc.returncode != 0 or not trace.exists():
            raise RuntimeError(f"open_jtalk 失敗: {proc.stderr.decode('utf-8', 'ignore')[:200]}")
        out = []
        for line in trace.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                break  # 空行から先は音響パラメータなので読まない
            fields = line.split(",")
            if len(fields) >= 10:
                out.append((fields[0], fields[9]))
        return out


def available() -> bool:
    return bool(shutil.which("open_jtalk")) and Path(DICT).exists() and Path(VOICE).exists()


def check_fixes() -> list[str]:
    problems: list[str] = []
    for fix in FIXES:
        for case in fix.cases:
            spoken = to_speech(case)
            if spoken == case:
                problems.append(f"[{fix.name}] 置換が効いていない: {case}")
                continue
            got = readings(spoken)
            kana = "".join(y for _, y in got).replace("’", "")
            if fix.expect not in kana:
                problems.append(
                    f"[{fix.name}] 読みが {fix.expect} にならない: {case}\n"
                    f"      → {spoken}\n      → {' '.join(f'{s}[{y}]' for s, y in got)}"
                )
        for word in fix.untouched:
            if to_speech(word) != word:
                problems.append(f"[{fix.name}] 触ってはいけない語を書き換えた: {word} → {to_speech(word)}")
            kana = "".join(y for _, y in readings(word)).replace("’", "")
            if fix.expect not in kana:
                problems.append(f"[{fix.name}] 複合語の読みがそもそも違う: {word} → {kana}")
    return problems


def check_script(path: Path) -> list[str]:
    script = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    for i, seg in enumerate(script.get("segments", [])):
        text = str(seg.get("narration") or "")
        for why in remaining_risks(text):
            problems.append(f"segment {i}: {why}: {text[:40]}")
    return problems


def main() -> int:
    if not available():
        print("[yomi] open-jtalk が無いので読みの検算は飛ばします "
              "（bash scripts/setup.sh で入ります）")
        return 0
    problems = check_fixes()
    for arg in sys.argv[1:]:
        problems += check_script(Path(arg))
    if problems:
        print("[yomi] 読みの検査に落ちました:")
        for p in problems:
            print("  - " + p)
        return 1
    n = sum(len(f.cases) for f in FIXES)
    print(f"[yomi] 合格: 直し {len(FIXES)}件 / 実測した文 {n}件、複合語の巻き込み無し")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
