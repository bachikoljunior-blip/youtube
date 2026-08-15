#!/usr/bin/env python3
"""1回のセッションで、複数本をまとめて作って予約する。

    python scripts/batch_build.py --count 2                 # 既定は 09:00 の空き枠へ
    python scripts/batch_build.py --count 3 --hour 11
    python scripts/batch_build.py --topics s-fukugyo-3,s-iryohi-3
    python scripts/batch_build.py --count 2 --skip-upload   # 作るだけ（予約しない）

## なぜ要るか（2026-08-15）

門は **「90日で1000万ショート再生」の一本**に縮みました（`docs/MEANS.md`
「M4 の土台が崩れた」）。1本あたりは 1777 が天井と確定済みなので、
**残っている変数は1日あたりの本数だけ**です。1000万/90日 ＝ 1日11.1万再生、
1本1200再生なら **1日92本**。

ところが、この輪は **1セッション＝1本**でした（`docs/trigger_main.md` §4 の
「最低1件」を、そのまま上限として運用していた）。1周は実測15〜45分なので、
**丸1日回しても十数本が上限**です。M14 が測ろうとしている 4 → 8 の段を、
**手段のほうが先に支えられません。**

だから、律速は「テーマ在庫」でも「配信」でもなく、**1回の起動で作れる本数**でした。
ここを機械化しないと、M14 は 8 の段で必ず止まります。

## この道具が守っていること

- **1本落ちても、残りは作る。** 例外は握って次のテーマへ進む（`--stop-on-error` で従来動作）
- **calc は全部ばらす。** 同じ計算を並べると量産判定に当たる（`CLAUDE.md`「この作りの根幹」）
- **`--dry-run` で作ってから `upload_only.py` で予約する。** 既存の2段構えのまま。
  検査（`src/verify.py`）も独立評価の材料保存も、そちらに入ったままです
- **予約時刻は `next_publish_at` に任せる。** 同じ時刻が埋まっていれば翌日へ送るので、
  連続で呼ぶと1日ずつ後ろに積まれます。**実験の窓を踏まないよう、時刻で選ぶこと**
- **結果は `data/batch_runs.jsonl` に残す。** `build/` は gitignore なので、
  セッションが畳まれた後に「何が出て何が落ちたか」を読めるのはここだけです

## この道具が答えないこと

**目視も独立評価もやりません**（`docs/trigger_main.md` §5・`docs/CRITIQUE.md`）。
機械検査は「指示どおり折ったか」しか見ておらず、**指示した位置そのものが悪い場合は
素通りします**。まとめて作ったぶんは、**投稿後に `scripts/critique_queue.py` の
待ち行列に積まれます。** そこを消化するのは呼んだ側の仕事です。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, history  # noqa: E402

JST = timezone(timedelta(hours=9))
LOG = ROOT / "data" / "batch_runs.jsonl"

# **M14 の比較の窓**（`docs/MEANS.md` M14）。8/16 が4本・8/17〜8/23 が各1本で、
# 「1日あたりの本数」を測っています。**ここへ足すと測定そのものが壊れます。**
#
# 文書には「実験の窓を踏まないこと」と3か所に書いてありましたが、
# **守るのは毎回こちらの記憶でした。** 8/15 の日誌が4回続けて言っている
# 「人が見れば一目で分かる欠陥を、機械検査が素通りさせた」と同じ形なので、
# **窓を機械に持たせます。** 窓が終わったらこの2行を消すこと（判定は M14 に書く）。
M14_WINDOW = ("2026-08-16", "2026-08-23")

# 台本生成〜レンダリングの実測は5〜10分。倍を上限に取る（無限には待たない）。
BUILD_TIMEOUT = 1800
UPLOAD_TIMEOUT = 600


def pick(count: int, explicit: list[str]) -> list[dict]:
    """未投稿・`calc` あり・**calc が全部ちがう** テーマを score の高い順に取る。"""
    pool = config.load_topics()["topics"]
    by_id = {t["id"]: t for t in pool}

    if explicit:
        missing = [i for i in explicit if i not in by_id]
        if missing:
            raise SystemExit(f"config/topics.yaml に無いテーマ: {', '.join(missing)}")
        chosen = [by_id[i] for i in explicit]
        no_calc = [t["id"] for t in chosen if not t.get("calc")]
        if no_calc:
            raise SystemExit(
                f"calc の無いテーマは台本生成が止まります: {', '.join(no_calc)}"
            )
        return chosen

    posted = history.posted_topic_ids()
    usable = [t for t in pool if t["id"] not in posted and t.get("calc")]
    usable.sort(key=lambda t: -float(t.get("score", 1.0)))

    chosen: list[dict] = []
    used_calc: set[str] = set()
    for topic in usable:
        if topic["calc"] in used_calc:
            continue
        chosen.append(topic)
        used_calc.add(topic["calc"])
        if len(chosen) == count:
            break

    if len(chosen) < count:
        print(
            f"[batch] **calc のちがう未投稿テーマが {len(chosen)} 件しかありません**"
            f"（要求 {count} 件）。在庫のほうが先に尽きています。",
            flush=True,
        )
    return chosen


def slots(count: int, hour: int, date_jst: str | None, hours: list[int]) -> list[str]:
    """各本の予約時刻の指定を返す（`upload_only.py` の第3引数の形）。

    `date_jst` が無ければ従来どおり全部同じ時刻 —— `next_publish_at` が
    埋まった日を飛ばすので、**結果として1日ずつ後ろに積まれます**（1日1本）。

    `date_jst` があると**その日に釘づけ**して、時刻のほうをずらします。
    これが「1日にN本」です。M14 の 8 の段はこの道が無くて止まっていました。
    """
    if not date_jst:
        return [str(hour)] * count
    if hours:
        picked = hours
    else:
        picked = [hour + i for i in range(count)]
    if len(picked) < count:
        raise SystemExit(
            f"--hours が {len(picked)} 個しかありません（{count} 本ぶん要ります）"
        )
    bad = [h for h in picked[:count] if not 0 <= h <= 23]
    if bad:
        raise SystemExit(f"時刻が 0〜23 の外です: {bad}")
    if len(set(picked[:count])) != count:
        raise SystemExit(f"同じ時刻が2本以上あります: {picked[:count]}")
    return [f"{date_jst}@{h}" for h in picked[:count]]


def check_window(date_jst: str, force: bool) -> None:
    """M14 の比較の窓に置こうとしていないかを見る。**記憶に任せない。**"""
    lo, hi = M14_WINDOW
    if not (lo <= date_jst <= hi):
        return
    if force:
        print(f"[batch] **{date_jst} は M14 の比較の窓（{lo}〜{hi}）です。**"
              " --force-window が付いているので続けます。", flush=True)
        return
    raise SystemExit(
        f"[batch] **{date_jst} は M14 の比較の窓（{lo}〜{hi}）です。**\n"
        "        ここは「8/16 が4本・8/17〜8/23 が各1本」で1日あたりの本数を\n"
        "        測っている最中で、足すと測定そのものが壊れます。\n"
        "        窓の外（8/24 以降）へ置くか、窓が終わったなら\n"
        "        scripts/batch_build.py の M14_WINDOW を消すこと。\n"
        "        どうしても足すなら --force-window。"
    )


def run(cmd: list[str], timeout: int) -> tuple[int, str]:
    """出力をそのまま流しながら、末尾も返す（VIDEO_ID を拾うため）。"""
    print(f"[batch] $ {' '.join(cmd)}", flush=True)
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, timeout=timeout,
            capture_output=True, text=True,
        )
    except subprocess.TimeoutExpired:
        return 124, f"{timeout}秒を超えたので打ち切りました"
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out[-4000:], flush=True)
    return proc.returncode, out


def video_id_of(out: str) -> str:
    for line in reversed(out.splitlines()):
        if line.startswith("VIDEO_ID "):
            return line.split(None, 1)[1].strip()
    return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="複数本をまとめて作って予約する")
    ap.add_argument("--count", type=int, default=2, help="作る本数（既定 2）")
    ap.add_argument("--hour", type=int, default=9,
                    help="予約時刻（JST の時。既定 9）。埋まっていれば翌日へ送られる")
    ap.add_argument("--date", default="",
                    help="YYYY-MM-DD。**その日に釘づけして時刻をずらす**＝1日にN本。"
                         "無ければ従来どおり1日ずつ後ろへ積む（1日1本）")
    ap.add_argument("--hours", default="",
                    help="--date と一緒に使う。時刻をカンマ区切りで明示"
                         "（既定は --hour から1時間ずつ）")
    ap.add_argument("--force-window", action="store_true",
                    help="M14 の比較の窓に置くことを承知で続ける（測定が壊れます）")
    ap.add_argument("--topics", default="",
                    help="テーマIDをカンマ区切りで明示する（--count より優先）")
    ap.add_argument("--long", action="store_true",
                    help="長尺で作る（既定はショート）")
    ap.add_argument("--skip-upload", action="store_true",
                    help="作るだけで予約しない。**この場合コンテナと一緒に消えます**")
    ap.add_argument("--stop-on-error", action="store_true",
                    help="1本落ちたらそこで止める（既定は次のテーマへ進む）")
    args = ap.parse_args(argv)

    explicit = [i.strip() for i in args.topics.split(",") if i.strip()]
    topics = pick(args.count if not explicit else len(explicit), explicit)
    if not topics:
        print("[batch] 作れるテーマがありません。config/topics.yaml を足すこと。")
        return 1

    if args.date:
        check_window(args.date, args.force_window)
    hours = [int(h) for h in args.hours.split(",") if h.strip()]
    when = slots(len(topics), args.hour, args.date or None, hours)

    if args.date:
        print(f"[batch] {len(topics)} 本を **{args.date} の1日に**入れます"
              f"（{', '.join(w.split('@')[1] + ':00' for w in when)} JST）")
    else:
        print(f"[batch] {len(topics)} 本を作ります（予約は {args.hour}:00 JST の空き枠へ）")
    for t in topics:
        print(f"        {t['id']}  calc={t['calc']}  {t['title_seed'][:38]}")

    results: list[dict] = []
    for n, topic in enumerate(topics, 1):
        tid = topic["id"]
        print(f"\n=== [{n}/{len(topics)}] {tid} ===", flush=True)
        row: dict = {"topic": tid, "calc": topic["calc"], "video_id": "", "error": ""}

        cmd = [sys.executable, "-m", "src.pipeline", "--topic", tid, "--dry-run"]
        if not args.long:
            cmd.append("--short")
        code, out = run(cmd, BUILD_TIMEOUT)
        if code != 0:
            row["error"] = f"生成が失敗（exit {code}）"
            results.append(row)
            print(f"[batch] **{tid} は作れませんでした。** 次へ進みます。", flush=True)
            if args.stop_on_error:
                break
            continue

        # **contact sheet は投稿の前に作る。**
        #
        # 最初に書いたときここを飛ばしていて、**1本目の投稿でそのまま踏みました**
        # （2026-08-15、`H28qfOxuJF0`）。`critique_queue.stash()` は
        # `inspect.jpg` が無いと材料を残さないので、**その動画は独立評価を
        # 永久に回せなくなります**（`build/` はコンテナと一緒に消える）。
        # `docs/CRITIQUE.md` が「投稿の時点から残る」と書いているのはこの1枚のことです。
        code, _ = run([sys.executable, "scripts/inspect_build.py", tid], UPLOAD_TIMEOUT)
        if code != 0:
            # **止めません。**contact sheet は評価の材料で、動画そのものではない。
            # 投稿が途切れるほうが損なので、印だけ残して先へ進みます。
            row["error"] = "contact sheet を作れず、独立評価の材料が残りません"

        if args.skip_upload:
            row["error"] = (row["error"] + " / " if row["error"] else "") \
                + "予約していません（--skip-upload）"
            results.append(row)
            continue

        code, out = run(
            [sys.executable, "scripts/upload_only.py", tid, "", when[n - 1]],
            UPLOAD_TIMEOUT,
        )
        vid = video_id_of(out)
        row["video_id"] = vid
        if not vid:
            row["error"] = f"予約が失敗（exit {code}）"
        elif code != 0:
            # 投稿は済んでいるが材料を残せなかった場合（upload_only.py の 1）。
            row["error"] = "投稿済み。ただし独立評価の材料を残せていない"
        results.append(row)
        if code != 0 and not vid and args.stop_on_error:
            break

    stamp = datetime.now(JST).isoformat(timespec="seconds")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"at": stamp, "hour": args.hour, "date": args.date or None,
             "slots": when, "results": results},
            ensure_ascii=False) + "\n")

    ok = [r for r in results if r["video_id"]]
    print("\n=== まとめ ===")
    for r in results:
        mark = "✓" if r["video_id"] else "✗"
        print(f"  {mark} {r['topic']:<18} {r['video_id'] or '—':<12} {r['error']}")
    print(f"  予約できたのは {len(ok)} / {len(topics)} 本")
    print(f"  記録: {LOG.relative_to(ROOT)}")
    if ok:
        print("  **独立評価が待ち行列に積まれています**: python scripts/critique_queue.py")
    return 0 if ok or args.skip_upload else 1


if __name__ == "__main__":
    raise SystemExit(main())
