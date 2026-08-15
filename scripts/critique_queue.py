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

    # **`slides_plan.json` も一緒に残します**（2026-08-15。5回持ち越された項目）。
    #
    # ここには contact sheet と読み上げ文しか入っていませんでした。
    # **どちらも焼き上がった絵で、焼き直せません。** 描画を直したときに
    # 「直る前と後で絵がどう変わったか」を測るには、`visuals.render` に
    # 食わせられる入力そのもの（＝**割った後のコマの列**）が要ります。
    #
    # 実際に詰まりました。8/15 22:0x の回は「実質同じ絵か」を測るために
    # **動画を2本生成しています**（11分×2）。`slides_plan.json` さえあれば
    # `scripts/bake_slides.py --plan` で **30秒**、生成0回で済みました。
    # 材料が21本ぶん積んであったのに、**測れる形で積んでいなかった**ということです。
    #
    # **1本あたり数KB。** 独立評価の子には渡しません（渡してよいのは
    # contact sheet と読み上げ文の2つ＝`docs/CRITIQUE.md`）。これは
    # **こちら側が過去の本を焼き直すための入力**で、用途が別です。
    plan_src = work / "slides_plan.json"
    plan_kept = False
    if plan_src.exists():
        shutil.copy2(plan_src, STASH / f"{video_id}.plan.json")
        plan_kept = True

    (STASH / f"{video_id}.json").write_text(
        json.dumps(
            {
                "video_id": video_id,
                "topic": topic,
                "stashed_at": datetime.now(JST).isoformat(timespec="seconds"),
                "orientation": "縦" if script.get("short", True) else "横",
                "narration": [ln for ln in lines if ln],
                "slides_plan": plan_kept,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"[queue] 独立評価の材料を残しました: data/critique_queue/{video_id}.jpg")
    if plan_kept:
        print(f"[queue] 焼き直せる入力も残しました: data/critique_queue/{video_id}.plan.json")
    else:
        # **黙って落とさない。** 無いことに気づけないのが、この項目が5回持ち越された理由です。
        print(f"[queue] **{plan_src} がありません** —— この本は後から焼き直せません")
    return STASH / f"{video_id}.jpg"


def _scored() -> set[str]:
    """点の付いたもの（テーマID・動画IDのどちらでも）。

    **2026-08-15 まで、この関数は常に空集合と同じものを返していました。**
    `critique_record.py` が積む行のキーは **`video`** で、ここは `video_id` を
    読んでいました。**綴りが違うだけで、どの行にも当たりません。**

    結果、**一度点を付けたものが待ち行列から消えませんでした。**
    `data/critique.jsonl` に `s-kojo-4` と `s-iryohi-2` が2回ずつ入っているのは
    これです（同じ動画を2回評価して2回積んだ）。**待ちは減らないので、
    毎回おなじ動画に3体を投げ続け、点が二重に積まれます。**
    順位相関を出す側から見ると、同じ動画が2票ぶん効きます。

    **落ちも警告も出ません。**「待ちが3件ある」は正しく見えていました。
    `.get()` が黙って空を返す形で踏むのは、8/15 に入れた `stash()` の
    `scenes`/`segments` に続いて2回目です。**両方のキーを読むようにします。**
    """
    if not LEDGER.exists():
        return set()
    out = set()
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("video", "video_id", "topic"):
            if row.get(key):
                out.add(row[key])
    return out


def pending() -> list[dict]:
    if not STASH.exists():
        return []
    done = _scored()
    out = []
    for meta in sorted(STASH.glob("*.json")):
        # **`*.plan.json` を拾わないこと**（2026-08-15）。焼き直し用の入力を
        # 隣に置いた瞬間、この glob が**1本につき2件**返すようになります。
        # 中身は台本ではないので `video_id` が無く、`meta.stem` から
        # **`"<ID>.plan"` という架空の待ち**が生えます（点の付けようが無いので
        # 永久に消えない）。
        #
        # 名前と型の**両方**で弾いています。いま実際に効いているのは型のほう
        # （`slides_plan.json` は配列なので `isinstance` で落ちる）ですが、
        # **中身の形が変わった日に、名前のほうだけが残ります。**
        if meta.name.endswith(".plan.json"):
            continue
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
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
        plan = STASH / f"{vid}.plan.json"
        if plan.exists():
            # **独立評価の子に渡すものではありません**（渡してよいのは
            # contact sheet と読み上げ文の2つ）。こちらが絵を焼き直すための入力です。
            print(f"焼き直す入力  : {plan}")
            print(f"  python scripts/bake_slides.py --plan {plan}"
                  f"{' --short' if d['orientation'] == '縦' else ''}")
        else:
            print("焼き直す入力  : **ありません**（この本は絵を測り直せません）")
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
        # **焼き直せるかを一覧に出す。** 出さないと、次の回は「材料はある」と読み、
        # 焼き直せない本を測ろうとして**生成（11分）に戻ります。**
        bakeable = "焼直可" if (STASH / f"{d['video_id']}.plan.json").exists() else "焼直不可"
        print(f"  {d['video_id']}  {d['orientation']}  {len(d['narration'])}行  "
              f"{bakeable}  投稿 {d['stashed_at'][:16]}")
    n_bakeable = sum(1 for d in rows if (STASH / f"{d['video_id']}.plan.json").exists())
    print()
    print(f"  焼き直せるのは {n_bakeable}/{len(rows)} 本"
          f"（`slides_plan.json` を残し始めたのは 2026-08-15 23:xx から）")
    print("  手順は docs/CRITIQUE.md。材料の中身は:")
    print("    python scripts/critique_queue.py <動画ID>")
    print("  積むのは:")
    print("    python scripts/critique_record.py <動画ID> <s1> <s2> <s3>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
