#!/usr/bin/env python3
"""1回のセッションで、複数本をまとめて作って予約する。

    python scripts/batch_build.py --count 2                 # 既定は 09:00 の空き枠へ
    python scripts/batch_build.py --count 3 --hour 11
    python scripts/batch_build.py --topics s-fukugyo-3,s-iryohi-3
    python scripts/batch_build.py --count 2 --skip-upload   # 作るだけ（予約しない）
    python scripts/batch_build.py --count 8 --date 2026-08-30 --jobs 3   # 同時に3本ずつ

## 律速は「作る速さ」でした（2026-08-15 に測って直した）

8/15 に7本を通したとき **80分＝1本11分**でした。この11分がどこに行っているかを
`ps` で見たら、**生成中の python は CPU を 2〜4% しか使っていません。**
内訳はほぼ全部が `claude -p`（`src/claude_cli.py`）の**待ち時間**です。
台本を書かせるのが一番高い工程で、そこは**こちらの CPU では何も起きていない。**

**待ち時間は重ねられます。** 直列で待っていたのは、そう書いてあったからで、
理由はありませんでした。`--jobs`（既定 3）で同時に走らせます。

    直列   8本 × 11分 = 88分   ← 1周に収まらない
    同時3  8本 ÷ 3 × 11分 ≒ 30分

**予約だけは直列のまま**です（`upload_only.py` は `next_publish_at` と
待ち行列という共有の状態を触るので、同時に走らせると予約時刻がぶつかる）。
段を分けてあるのはそのためで、**作る段と予約の段を混ぜないこと。**

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
from concurrent.futures import ThreadPoolExecutor
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

# **同時に走らせる本数の既定**（2026-08-15 に足した。理由は下）。
#
# 1本11分の内訳は、ほぼ全部が `claude -p`（`src/claude_cli.py`）の**待ち時間**です。
# 生成中の python は **CPU 2〜4%** しか使っていません（実測、`ps` で確認）。
# **CPU が空いているのに直列で待っていた**ので、ここは待ち時間を重ねるだけで縮みます。
#
# 4 にしていないのは、レンダリング（ffmpeg・open-jtalk）だけは CPU を使うからで、
# 4コアに対して 3 なら、山が重なっても 1コア残ります。**`--jobs` で変えられます。**
DEFAULT_JOBS = 3

# 1つの `calc` から、1回の batch で取ってよい本数。
#
# **天井の話です**（2026-08-15 19:5x）。それまでは「calc が全部ちがう」＝実質 1 で、
# `calc` は11本しかないので **1回 11本が上限**でした。M14 の段はその先を狙う手なのに、
# 上限がどこにも書いてありません。**節（`calc_sections`）で見れば 54 件あります。**
# 2 にしているのは、同じ制度の本が並ぶと題も似て「繰り返しのように感じられる」側に
# 寄るからで、**根拠のあるぶんだけ（11 → 22）上げています。**
DEFAULT_PER_CALC = 2


def _section_key(topic: dict) -> tuple:
    """その本が**実際に見せる計算**を指す鍵。

    テーマは `calc`（モジュール）と `calc_sections`（その中のどの節を出すか）を
    持ちます。**画面に出る数字も棒の形も決めているのは節のほう**なので、
    「同じものが続くか」を見るときに見るべきなのはここです。

    節の指定が無い古いテーマは**モジュール全体**を指しているとみなします
    （どの節とも重なるので、その calc を1本で使い切る扱い）。
    """
    sections = tuple(sorted(topic.get("calc_sections") or ()))
    return (topic["calc"], sections)


def pick(count: int, explicit: list[str], per_calc: int = DEFAULT_PER_CALC) -> list[dict]:
    """未投稿・`calc` あり・**計算の節が全部ちがう** テーマを score の高い順に取る。

    ## ここが 2026-08-15 19:5x に変わりました（天井の測り違い）

    それまでの規則は「**calc が全部ちがう**」でした。`calc` は11本しかないので、
    **1回の batch は最大11本**です。M14（本数の段）は 8 → その先を狙う手なのに、
    **11 で頭打ちになることが、どこにも書いてありませんでした。**

    実測（この回）: 未投稿テーマ7件のうち calc は5種類で、`pick(8)` は
    **5件しか返しませんでした。** 前の回が次の宿題に置いた「`--jobs` の上限を測る」は、
    **`pick` が5件しか返さない状態では意味がありません**（同時に作る相手がいない）。
    **律速は並列度ではなく、取れるテーマの数のほうでした。**

    節で見ると 54 件あります。**節がちがえば、前提も数字も棒の形もちがう** ——
    `calc_sections` は「モジュールのどの節を出すか」を指していて、
    画面に出るものを決めているのはこちらです。つまり
    **「同じ計算を2回出さない」を守ったまま、天井は 11 から上げられます。**

    ただし**節だけにはしません。** 同じ制度の本が1日に何本も並ぶと、
    題も似るので「繰り返しのように感じられる」側に寄ります（収益化の条件）。
    だから **1つの calc から取るのは既定で2本まで**（`per_calc`）。
    天井は 11 → 22 で、**根拠のあるぶんだけ上げています。**

    **覆る条件**: 同じ calc の2本を並べた日の engaged 比率の中央値が、
    全部ちがう calc の日を下回ったら、`per_calc` を 1 に戻すこと。
    """
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

    if per_calc < 1:
        raise SystemExit(f"--per-calc は1以上です: {per_calc}")

    chosen: list[dict] = []
    used_sections: set[tuple] = set()
    per_calc_taken: dict[str, int] = {}
    whole_module: set[str] = set()   # 節の指定が無いテーマを取った calc

    for topic in usable:
        calc = topic["calc"]
        key = _section_key(topic)
        sections = key[1]

        if key in used_sections:
            continue                      # **同じ計算は2回出さない**
        if per_calc_taken.get(calc, 0) >= per_calc:
            continue                      # 同じ制度が並びすぎないように
        if calc in whole_module:
            continue                      # モジュール全体のテーマと必ず重なる
        if not sections and per_calc_taken.get(calc, 0):
            continue                      # 逆向きも同じ

        chosen.append(topic)
        used_sections.add(key)
        per_calc_taken[calc] = per_calc_taken.get(calc, 0) + 1
        if not sections:
            whole_module.add(calc)
        if len(chosen) == count:
            break

    if len(chosen) < count:
        print(
            f"[batch] **計算の節がちがう未投稿テーマが {len(chosen)} 件しかありません**"
            f"（要求 {count} 件 / 1つの calc から最大 {per_calc} 本）。"
            f"在庫のほうが先に尽きています。",
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


def run(cmd: list[str], timeout: int, label: str = "") -> tuple[int, str]:
    """出力をそのまま流しながら、末尾も返す（VIDEO_ID を拾うため）。

    **並列で呼ばれます。** 途中経過を流すと複数本の行が混ざって読めなくなるので、
    1本ぶんを**1回の `print` にまとめて**出す（行の途中で割り込まれない）。
    """
    tag = f"[{label}] " if label else ""
    print(f"[batch] {tag}$ {' '.join(cmd)}", flush=True)
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, timeout=timeout,
            capture_output=True, text=True,
        )
    except subprocess.TimeoutExpired:
        print(f"[batch] {tag}**{timeout}秒を超えたので打ち切りました**", flush=True)
        return 124, f"{timeout}秒を超えたので打ち切りました"
    out = (proc.stdout or "") + (proc.stderr or "")
    body = "\n".join(f"{tag}{line}" for line in out[-4000:].splitlines())
    print(body, flush=True)
    return proc.returncode, out


def build_one(topic: dict, long_form: bool) -> dict:
    """**作るところまで**を1本ぶん。予約はしない（呼ぶ側が直列でやる）。

    ここが並列に走る部分です。**予約を混ぜないこと** —— `upload_only.py` は
    `next_publish_at` と待ち行列（`critique_queue`）という**共有の状態**を触るので、
    同時に走らせると予約時刻がぶつかります（8/15 03:48 の二重起動と同じ壊れ方）。
    """
    tid = topic["id"]
    row: dict = {"topic": tid, "calc": topic["calc"], "video_id": "", "error": ""}

    cmd = [sys.executable, "-m", "src.pipeline", "--topic", tid, "--dry-run"]
    if not long_form:
        cmd.append("--short")
    code, _ = run(cmd, BUILD_TIMEOUT, tid)
    if code != 0:
        row["error"] = f"生成が失敗（exit {code}）"
        row["built"] = False
        return row

    # **contact sheet は投稿の前に作る。**
    #
    # 最初に書いたときここを飛ばしていて、**1本目の投稿でそのまま踏みました**
    # （2026-08-15、`H28qfOxuJF0`）。`critique_queue.stash()` は
    # `inspect.jpg` が無いと材料を残さないので、**その動画は独立評価を
    # 永久に回せなくなります**（`build/` はコンテナと一緒に消える）。
    # `docs/CRITIQUE.md` が「投稿の時点から残る」と書いているのはこの1枚のことです。
    code, _ = run([sys.executable, "scripts/inspect_build.py", tid], UPLOAD_TIMEOUT, tid)
    if code != 0:
        # **止めません。**contact sheet は評価の材料で、動画そのものではない。
        # 投稿が途切れるほうが損なので、印だけ残して先へ進みます。
        row["error"] = "contact sheet を作れず、独立評価の材料が残りません"
    row["built"] = True
    return row


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
    ap.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                    help=f"同時に作る本数（既定 {DEFAULT_JOBS}）。**予約はいつも1本ずつ**")
    ap.add_argument("--per-calc", type=int, default=DEFAULT_PER_CALC,
                    help=f"1つの calc から取ってよい本数（既定 {DEFAULT_PER_CALC}）。"
                         "**節はいつも全部ちがいます。**1 にすると昔の"
                         "「calc が全部ちがう」に戻り、1回の上限が calc の本数になります")
    ap.add_argument("--stop-on-error", action="store_true",
                    help="1本落ちたらそこで止める（**予約の段だけ**。"
                         "作る段は並列なので、落ちた1本の巻き添えで他を捨てません）")
    args = ap.parse_args(argv)

    explicit = [i.strip() for i in args.topics.split(",") if i.strip()]
    topics = pick(args.count if not explicit else len(explicit), explicit,
                  per_calc=args.per_calc)
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

    # ---- 1. 作る（**ここだけ並列**）----------------------------------------
    #
    # 1本の11分は、ほぼ全部が `claude -p` の待ち時間です（生成中の CPU は 2〜4%）。
    # **待ち時間は重ねられます。** 直列だと 8本で90分、3本ずつなら30分台。
    # M14 が測ろうとしている「1日あたりの本数」は、ここが律速でした。
    jobs = max(1, min(args.jobs, len(topics)))
    began = datetime.now(JST)
    if jobs > 1:
        print(f"\n[batch] **{jobs} 本ずつ同時に作ります**"
              f"（待ち時間を重ねるだけなので、予約は下で1本ずつやります）", flush=True)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda t: build_one(t, args.long), topics))
    built = sum(1 for r in results if r.get("built"))
    spent = (datetime.now(JST) - began).total_seconds() / 60
    print(f"\n[batch] 作れたのは {built} / {len(topics)} 本（{spent:.1f}分・同時 {jobs}）",
          flush=True)

    # ---- 2. 予約する（**必ず直列**）----------------------------------------
    #
    # `upload_only.py` は `next_publish_at` と待ち行列という共有の状態を触るので、
    # 同時に走らせると予約時刻がぶつかります。**ここを並列にしないこと。**
    # 順番も `topics` のまま＝`when[n-1]` の対応が崩れません。
    for n, row in enumerate(results, 1):
        tid = row["topic"]
        if not row.get("built"):
            print(f"[batch] **{tid} は作れませんでした。** 予約しません。", flush=True)
            continue
        if args.skip_upload:
            row["error"] = (row["error"] + " / " if row["error"] else "") \
                + "予約していません（--skip-upload）"
            continue

        code, out = run(
            [sys.executable, "scripts/upload_only.py", tid, "", when[n - 1]],
            UPLOAD_TIMEOUT, tid,
        )
        vid = video_id_of(out)
        row["video_id"] = vid
        if not vid:
            row["error"] = f"予約が失敗（exit {code}）"
        elif code != 0:
            # 投稿は済んでいるが材料を残せなかった場合（upload_only.py の 1）。
            row["error"] = "投稿済み。ただし独立評価の材料を残せていない"
        if code != 0 and not vid and args.stop_on_error:
            break

    for row in results:
        row.pop("built", None)

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
