#!/usr/bin/env python3
"""独立評価（M13）の材料を、コンテナが消えても残す。

    残す    scripts/upload_only.py が投稿の直後に self.stash() を呼ぶ
    探す    python scripts/critique_queue.py            ← 未評価のものを出す
    見る    python scripts/critique_queue.py <動画ID>   ← 材料の置き場所を出す

**なぜ要るか（2026-08-15 に実測で見つけた穴）。**

`docs/CRITIQUE.md` は「contact sheet ができた後、投稿の前」に評価しろと言い、
`docs/trigger_main.md` は「回せなかった回は次の回に回させる」と言っています。
**この2つは両立しません。**

`build/` は `.gitignore` で、いまは1周ごとにセッションを畳みます。
**畳んだ瞬間にコンテナごと消えるので、「次の回に回す」先には何も残っていません。**
台本はその回のセッションが書いたもので、作り直しても同じ文にはなりません
（`src.script_writer` は схема を出すだけで、本文は毎回書き下ろし）。
だから**投稿済みの動画は、あとから評価できませんでした。**

8/15 の3回は「サブエージェントが使えないから回せなかった」と書いて終えましたが、
**仮に使えても回せませんでした。** 材料のほうが先に消えているからです。
`src/bars.py` が「公開した棒」を同じ理由で残しているのと、まったく同じ穴です。

**投稿の時点で材料を確定させて、リポジトリに残す。** そうすれば評価は
「投稿の前」に縛られず、次の回でもその次でもできます。
評価が基準未満なら、**予約は外せます**（公開までの猶予がそのまま持ち時間）。
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STASH = ROOT / "data" / "critique_queue"
LEDGER = ROOT / "data" / "critique.jsonl"
JST = timezone(timedelta(hours=9))


def stash(topic: str, video_id: str, script: dict, work: Path) -> Path | None:
    """contact sheet と読み上げ文を、動画IDで引ける場所へ写す。

    **contact sheet が無ければ何もしません。** `inspect_build.py` を通していない
    投稿は評価の材料が無く、無い材料の空箱を積んでも次の回を惑わせるだけです。
    """
    sheet = work / "inspect.jpg"
    if not sheet.exists():
        print("[queue] inspect.jpg が無いので材料を残せません（inspect_build.py を通してください）")
        return None

    # 読み上げ文だけを取る。**題材も狙いも渡さない**のが独立評価の条件なので、
    # ここで topic 名や calc の種類まで書くと、次の回がそのまま子に渡してしまう。
    #
    # **鍵は `segments` です。`scenes` ではありません**（2026-08-15 に直した）。
    # 8/15 に材料を残す仕組みを入れたとき、ここを `scenes` と書いていました。
    # 台本にその鍵は無いので **`.get()` が黙って空を返し、読み上げ文が
    # 毎回0行で積まれていました**（`NHKylqsNfTw` `CdX2oIb7BG8` の2本が実際にそれ）。
    # `docs/CRITIQUE.md` は「渡してよいものは contact sheet と読み上げ文の2つ」と
    # 書いているので、**材料が半分だけ残る = 検査が半分死ぬ**形でした。
    # 落ちずに空で通るのが最悪なので、**取れなかったら声を上げます。**
    segments = script.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError(
            "台本に `segments` がありません（読み上げ文を残せません）。"
            f" 実際の鍵: {sorted(script)}"
        )
    lines = [str(s.get("narration", "")).strip() for s in segments]
    if not any(lines):
        raise ValueError("`segments` はありますが `narration` が全部空です。")

    # **確かめてから写す。** 先に写すと、上で上げたときに
    # 相方の json が無い .jpg だけが残ります。
    STASH.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sheet, STASH / f"{video_id}.jpg")
    (STASH / f"{video_id}.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "topic": topic,
                "stashed_at": datetime.now(JST).isoformat(timespec="seconds"),
                "orientation": "縦" if script.get("short", True) else "横",
                "narration": [ln for ln in lines if ln],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"[queue] 独立評価の材料を残しました: data/critique_queue/{video_id}.jpg")
    return STASH / f"{video_id}.jpg"


def _scored() -> set[str]:
    if not LEDGER.exists():
        return set()
    out = set()
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.add(json.loads(line).get("video_id", ""))
        except json.JSONDecodeError:
            continue
    return out


def pending() -> list[dict]:
    if not STASH.exists():
        return []
    done = _scored()
    out = []
    for meta in sorted(STASH.glob("*.json")):
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        vid = d.get("video_id", meta.stem)
        # `critique_record.py` は topic でも動画IDでも積めるので、両方で照合する。
        if vid in done or d.get("topic", "") in done:
            continue
        if not (STASH / f"{vid}.jpg").exists():
            continue
        out.append(d)
    return out


def main(argv: list[str]) -> int:
    if argv:
        vid = argv[0]
        sheet, meta = STASH / f"{vid}.jpg", STASH / f"{vid}.json"
        if not sheet.exists():
            print(f"{vid} の材料はありません（投稿より前に投稿したものは残っていません）")
            return 1
        d = json.loads(meta.read_text(encoding="utf-8"))
        print(f"contact sheet : {sheet}")
        print(f"動画の向き    : {d['orientation']}")
        print("読み上げ文:")
        for ln in d["narration"]:
            print(f"  {ln}")
        return 0

    rows = pending()
    print(f"=== 独立評価の待ち（data/critique_queue）===")
    if not rows:
        print("  待ちはありません。")
        print("  **これは「全部評価した」とは限りません。**材料が残る前に投稿したものは、")
        print("  ここに出ません（2026-08-15 より前の投稿が全部そうです）。")
        return 0
    for d in rows:
        print(f"  {d['video_id']}  {d['orientation']}  {len(d['narration'])}行  投稿 {d['stashed_at'][:16]}")
    print()
    print("  手順は docs/CRITIQUE.md。材料の中身は:")
    print("    python scripts/critique_queue.py <動画ID>")
    print("  積むのは:")
    print("    python scripts/critique_record.py <動画ID> <s1> <s2> <s3>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
