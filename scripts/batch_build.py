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

**【2026-08-15 22:3x】この「11分」は、もう本当ではありません。**
実測は **1本 1.7分**（同時1）／**2.7分**（同時6）です。11.4分だったのは
8/15 18:xx の7本で、**そのあと台本の作り方が変わりました。**
この数字は文書に3回引用され、**誰も測り直していませんでした。**
**上の掛け算は当時の記録として残しますが、根拠に使わないこと。**
いまの値は `python scripts/batch_build.py --report` が出します。

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
- **かかった時間も残す**（2026-08-15 22:3x に足した。下の節が理由）

## 「`--jobs` の上限を測る」が4回持ち越された理由（2026-08-15 22:3x）

`retro.py` の持ち越しで **`--jobs` が4回**（19:0x / 19:2x / 20:5x / 22:0x）出ています。
**4回とも「次の回で測る」と書かれ、4回とも測られませんでした。**
「忙しかったから」ではありません。**測れなかったからです。**

    data/batch_runs.jsonl に入っていたもの   at / hour / date / slots / results[topic,calc,video_id,error]
    入っていなかったもの                     **`jobs` も、かかった秒数も**

**この台帳を後から読んでも、何本ずつ走らせたのかすら分かりません。**
19:0x の「6本を4.7分」は**その回の画面にしか無く**、次の回には残っていない。
だから毎回「まず測り直すところから」になり、10分かかるので後回しになる ——
**それが4回くり返されました。**

そして、持ち越しの文言が**測り方そのものを高くしていました。**
「`--jobs` の上限」を **jobs=3 の回と jobs=6 の回を別々に走らせて比べる**と読むと、
1回10分の生成が2回要り、**しかも題材が違うので条件が揃いません**（台本の長さも
落ちる本数も毎回ちがう）。**1周に収まらない測定は、永久に後回しになります。**

**1本ずつの所要時間を記録すれば、1回の走りで答えが出ます。**

    直列に要る時間 ＝ 1本ずつの秒数の合計
    実際にかかった時間 ＝ 壁時計
    **速くなった倍率 ＝ 合計 ÷ 壁時計**（jobs に近ければ、待ち時間は素直に重なっている）

    **1本あたりの秒数が jobs を上げるほど伸びていたら、そこが上限です**
    （待ち時間ではなく、こちらの CPU かメモリを取り合い始めている）

**上限は「速くならなくなる点」ではなく「1本あたりが太り始める点」で出ます。**
前者は本数と題材に左右されますが、後者は**同じ走りの中で比べられます。**

    python scripts/batch_build.py --report    # 台帳を jobs 別に並べる（生成しない・数秒）

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

from src import auth, config, dupes, history, measure_window, upload_cap  # noqa: E402

JST = timezone(timedelta(hours=9))
LOG = ROOT / "data" / "batch_runs.jsonl"

# **M14 の比較の窓**（`docs/MEANS.md` M14）。8/16 が4本・8/17〜8/23 が各1本で、
# 「1日あたりの本数」を測っています。**ここへ足すと測定そのものが壊れます。**
#
# 文書には「実験の窓を踏まないこと」と3か所に書いてありましたが、
# **守るのは毎回こちらの記憶でした。** 8/15 の日誌が4回続けて言っている
# 「人が見れば一目で分かる欠陥を、機械検査が素通りさせた」と同じ形なので、
# **窓を機械に持たせます。**
#
# **正本は `src/measure_window.py` に移しました**（2026-08-18）。ここに
# 置いてあったあいだ、門は**この道具の `--date` を渡した時にしか**効かず、
# `--hour` も `upload_only.py` も `reschedule.py` も素通りでした。
# ここは別名です。**窓を終わらせるときは `src/measure_window.py` を直すこと。**
M14_WINDOW = measure_window.WINDOW

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


def _posted_including_ledger() -> set[str]:
    """投稿済みのテーマIDを、**チャンネルと手元の控えの和**で返す（2026-08-16 07:5x）。

    ## 何が起きていたか（この回が2回踏み、2本ぶんの生成を捨てた）

    `pick` はチャンネルの説明欄からだけ「投稿済み」を復元していました。
    ところが復元の口は**両方とも欠けます** —— uploads プレイリストは予約中を落とし、
    `search` は**この日1日枠を使い切っています**（HTTP 429。`src/history.py` の実測）。
    欠けたぶんは**未投稿として選び直され**、11分かけて動画を作った後、
    投稿の直前の門（`src/dupes.blocking`）が止めます。

        s-furusato-5   作った → 却下（既にある b3ZewNvalXc と同じテーマID）
        s-shitsugyo-6  作った → 却下（既にある 8PMLfjjCe4w と同じテーマID）

    **この回に作った8本のうち2本、25%が捨てになりました。**
    **門は正しく働いています。**間違っていたのは、**門の位置ではなく選ぶ側**です。

    ## なぜ控えを混ぜてよいか（前は、意図してやっていませんでした）

    `src/dupes.ledger_rows` はこう書いています ——「どのテーマを次に作るか（`pick`）は
    **今もチャンネルから決めます**。動画を消したときにファイルが嘘になるからです」。

    **その心配は、いまのこちらには当たりません。** 動画を消す道が1本もないからです
    （`docs/FOR_OWNER.md` の済み3。`videos().delete` も、private に落とす
    `videos().update` も、環境の判定に弾かれます）。**控えは増えるだけで、
    嘘になる経路が存在しません。** 一方、混ぜない費用は**実測で生成の25%**です。

    **覆る条件**: 動画を消せるようになったら、ここは生存確認（`videos.list`）を
    通すか、チャンネルだけに戻すこと。**消した動画のテーマが永久に選べなくなります。**
    """
    posted = set(history.posted_topic_ids())
    from src import dupes

    extra = {r["topic"] for r in dupes.ledger_rows() if r.get("topic")} - posted
    if extra:
        # **黙って足さないこと。** 差は「口が欠けた量」そのもので、読める唯一の場所です。
        print(f"[pick] 控えにしか無い投稿済みテーマ {len(extra)}件を足しました"
              f"（口が欠けたぶん）: {', '.join(sorted(extra)[:6])}"
              f"{' …' if len(extra) > 6 else ''}")
    return posted | extra


def _drop_doomed(usable: list[dict], pool: list[dict]) -> list[dict]:
    """**投稿の門が必ず止めるテーマを、作る前に外す**（2026-08-17 に足した）。

    `s-menjo-hangaku-10200` は3回続けて申し送りに出ています ——
    `pick` が上位で返し、11分かけて作り、`upload_only.py` の
    `dupes.blocking()` が **毎回** 止める。**作った1本はそのたび捨てになります。**
    そのあいだ手順は `--topics` で手で避けていましたが、
    **手で避けている限り、避け忘れた回が必ず出ます。**

    ここで見るのは**控え（`data/` のローカル）だけ**で、API は1単位も使いません
    （`dupes.blocking(title, id, [], topics)` は videos が空でも控えを読みます）。
    見ているのは `title_seed` なので、門と同じではありません:

    - **同じテーマID**（`same-topic`）は、これで確実に当たります
    - **金額の入れ子**（`same-yen`）は、種に主役の数字が出ていれば当たります。
      台本が別の数字を主役にしたら当たりません。**そのぶんは門が受けます**

    逆に「門は通すのに、ここで落とす」ことはあり得ます（種にだけ数字がある場合）。
    **だから落としたものは必ず名前を出し**、`--topics` で明示すれば
    この関門は通りません（`explicit` は上で先に返っています）。
    """
    from src import dupes

    # **投稿済みのぶんも含めて、テーマ全部の calc を渡すこと。**
    # 控えの1行は「どの calc の本か」をテーマID経由でしか知りません。
    # 未投稿ぶんだけ渡すと、**既にある本の calc が空になり、`same-yen` が
    # 1組も当たりません**（最初にそう書いて、s-menjo-hangaku-10200 が素通りしました）。
    topics_calc = {t["id"]: t.get("calc", "") for t in pool}
    kept, dropped = [], []
    for t in usable:
        seed = t.get("title_seed") or ""
        hits = dupes.blocking(seed, t["id"], [], topics_calc) if seed else []
        if hits:
            dropped.append((t["id"], hits[0]["why"]))
        else:
            kept.append(t)
    for tid, why in dropped:
        print(f"[pick] **門が必ず止めるので外します**: {tid} — {why}")
    return kept


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

    posted = _posted_including_ledger()
    usable = [t for t in pool if t["id"] not in posted and t.get("calc")]
    usable = _drop_doomed(usable, pool)

    # **順番は実績で決める**（2026-08-16 に測って変えた。それまでは手書きの
    # `score` だけで、実績を1つも見ていませんでした ＝ 91件中64件が `1.0`）。
    # 族ごとの engaged 比率は実物で **4倍ちがい**、登録も上位の族からしか
    # 入っていません（`src/family_perf.py` に測り方と割り引き方）。
    # 手書きの見立ては捨てず、**掛ける**（実績は事前分布、`score` は狙い）。
    # 測っていない族は全体平均になるので、**真ん中の順位から試されます。**
    from src import family_perf

    try:
        family_score = family_perf.scorer()
    except Exception as exc:              # 実績が読めなくても止めない
        print(f"[pick] 実績が読めませんでした（手書きの score だけで並べます）: {exc}")
        family_score = lambda calc: 1.0   # noqa: E731
    usable.sort(key=lambda t: -float(t.get("score", 1.0)) * family_score(t["calc"]))

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


def ledger_hours(date_jst: str) -> set[int]:
    """その日に**もう置いてある**時刻（JST の時）を、手元の控えから読む。

    読むのは `data/uploaded.jsonl`（`src.dupes.ledger_rows`）で、**API は叩きません。**
    予約の一覧を口から取ると channels + playlistItems + videos で数単位かかるうえ、
    **Data API の日枠が切れている回では、そもそも読めません**
    （日枠が戻るのは JST 16:00。それ以前の回はここが唯一の手がかりです）。

    **控えは上限側の見積りです**（`scripts/status.py` の「予約の先」と同じ性質）。
    取り消した本の行も残るので、**空いているのに「埋まっている」と読むことがあります。**
    外す向きは安全です —— 空き枠を1つ余計に飛ばすだけで、**ぶつけて1本捨てるより安い。**
    逆向き（埋まっているのに空きと読む）は起きません。控えは投稿した本人が書くので、
    **置いた本が控えから落ちることはない**からです。

    読めなかったら空集合を返します。**この道具のために回を止めないこと。**
    """
    try:
        rows = [r for r in dupes.ledger_rows() if r.get("at")]
    except Exception as exc:                                  # noqa: BLE001
        print(f"[batch] 控えが読めませんでした（続行）: {str(exc)[:80]}", flush=True)
        return set()
    taken: set[int] = set()
    for row in rows:
        try:
            when = datetime.fromisoformat(str(row["at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        when = when.astimezone(JST)
        if when.strftime("%Y-%m-%d") == date_jst:
            taken.add(when.hour)
    return taken


def ledger_minutes(date_jst: str) -> set[int]:
    """その日に埋まっている時刻を**0時からの分**で返す（API 0単位）。

    `ledger_hours()` は同じ控えを**時だけ**に落として読んでいました。
    落とすと 10:00 の1本が 10:30 まで塞ぎます —— **1時間に1本しか置けない**
    のは制度でも枠でもなく、**この読み方**でした（2026-08-18 に測った:
    予約262本の分は**全部 :00**、公開は 1日6.4本、置ける枠は 9〜19時の11個）。

    投稿の本数枠は1日92本あります。**律速は置く場所のほうです。**
    """
    try:
        rows = [r for r in dupes.ledger_rows() if r.get("at")]
    except Exception as exc:                                  # noqa: BLE001
        print(f"[batch] 控えが読めませんでした（続行）: {str(exc)[:80]}", flush=True)
        return set()
    taken: set[int] = set()
    for row in rows:
        try:
            when = datetime.fromisoformat(str(row["at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        when = when.astimezone(JST)
        if when.strftime("%Y-%m-%d") == date_jst:
            taken.add(when.hour * 60 + when.minute)
    return taken


def _show_slot(spec: str) -> str:
    """`slots()` が返した指定を、人が読む `H:MM` にする。

    `2026-08-24@10` → `10:00` ／ `2026-08-24@10:30` → `10:30`
    """
    text = spec.partition("@")[2] or spec
    return text if ":" in text else f"{text}:00"


def _slots_fine(count: int, hour: int, date_jst: str, hours: list[int],
                step_min: int, taken: set[int] | None,
                taken_min: set[int] | None) -> list[str]:
    """`step_min` が 60 未満のときの割り当て（0時からの分で数える）。

    **`slots()` から呼ばれる前提**です。単体で呼ばないこと（`date_jst` を必須にしてある）。
    """
    if not 1 <= step_min < 60 or 60 % step_min:
        raise SystemExit(
            f"--step-min は 60 の約数で 1〜59 のどれか: {step_min}\n"
            "        （1時間を割り切らないと、日をまたぐ所で目盛りがずれます）"
        )
    if hours:
        raise SystemExit(
            "--hours と --step-min は同時に使えません。\n"
            "        `--hours` は**時だけ**の指定なので、分の目盛りを打ち消します。"
        )
    if taken_min is None:
        if taken is not None:
            raise SystemExit(
                "step_min が 60 未満のときは taken（時）ではなく taken_min"
                "（0時からの分）を渡すこと。\n"
                "        時に落として読むと 10:00 の1本が 10:30 まで塞ぎます —— "
                "**それがこの目盛りの相手そのもの**です。"
            )
        taken_min = ledger_minutes(date_jst)
    grid = [m for m in range(hour * 60, 24 * 60, step_min) if m not in taken_min]
    if len(grid) < count:
        busy = sorted(f"{m // 60}:{m % 60:02d}" for m in taken_min)
        raise SystemExit(
            f"{date_jst} は {hour}時以降の空きが {len(grid)} 個しかありません"
            f"（{count} 本ぶん要ります／{step_min}分きざみ／控えでの埋まり {busy}）。\n"
            "        **別の日にするか、--hour を早めるか、--step-min を細かくすること。**"
        )
    picked = grid[:count]
    if picked != list(range(hour * 60, hour * 60 + step_min * count, step_min)):
        shown = ", ".join(f"{m // 60}:{m % 60:02d}" for m in picked)
        print(f"[batch] {date_jst} の埋まりを避けて {shown} に置きます"
              "（控えから。API 0単位）", flush=True)
    return [f"{date_jst}@{m // 60}:{m % 60:02d}" for m in picked]


def slots(count: int, hour: int, date_jst: str | None, hours: list[int],
          taken: set[int] | None = None, step_min: int = 60,
          taken_min: set[int] | None = None) -> list[str]:
    """各本の予約時刻の指定を返す（`upload_only.py` の第3引数の形）。

    `date_jst` が無ければ従来どおり全部同じ時刻 —— `next_publish_at` が
    埋まった日を飛ばすので、**結果として1日ずつ後ろに積まれます**（1日1本）。

    `date_jst` があると**その日に釘づけ**して、時刻のほうをずらします。
    これが「1日にN本」です。M14 の 8 の段はこの道が無くて止まっていました。

    ## 空き時刻を自分で読みます（2026-08-17。**3回持ち越された穴**）

    ここは長らく `hour + i` で、**その日に何が置いてあるかを一度も見ていませんでした。**
    埋まっている時刻に当たると `upload_only.py` が
    「すでに埋まっています。**翌日へは送りません**」で落ちるので、
    **作った1本がそのまま捨てられます**（`build/` はコンテナと一緒に消えるため）。

    避ける道は「**人が予約一覧を見て `--hours` に手で写す**」しかありませんでした。
    申し送りは3回とも同じことを言っています ——
    「手で `--hours` を写している限り、埋まっている時刻とぶつけて1本捨てる回が出る」。
    **人の記憶と手写しに依存する門は、この輪では毎回落ちる側**です。

    `taken` を渡さなければ `ledger_hours()` が控えから読みます（**API 0単位**）。
    実測（2026-08-17 の控え）: 09-01 は 9,10,12〜16 が埋まりで **空きは 11 だけ** ——
    前の回が API を叩いて手で出した答えと一致しました。
    既定の `hour + i` なら 9,10 とぶつけて**先頭2本を捨てていた**ところです。

    `--hours` を明示したときは**そちらを通します**（控えは上限側なので、
    取り消し済みの枠へ置き直す道を塞がない）。ただし**重なっていれば必ず言います。**

    ## `step_min` を足した理由（2026-08-18。**律速は投稿でも作りでもなかった**）

    ここは長らく**時の目盛りしか持っていませんでした**（`range(hour, 24)`）。
    だから1日に置けるのは最大24枠、実際に使う 9〜19時では **11枠**です。
    ところが投稿の本数枠は **1日92本**あり、作る側も1日118本まで出ています。
    **4倍以上足りないのは、置く場所の目盛りのほうでした**（予約262本の分は全部 `:00`）。

    実測（2026-08-18 の控え）: 予約257本が **09/27 まで40日ぶん**に伸びていて、
    公開は **1日6.4本**。同じ在庫を 30分きざみ（1日22枠）で置けば
    **13日ぶん**に縮みます。**追加の生成も、追加の投稿枠も要りません。**

    `next_publish_at` は最初から分を受け取ります（`minute_jst`）。
    **受け取る側はできていて、渡す側が時しか持っていなかった**だけです。

    **控えを時に落として読まないこと**（`ledger_minutes`）。落とすと
    10:00 の1本が 10:30 まで塞ぎ、目盛りを細かくした意味が消えます。
    だから `step_min < 60` では `taken`（時）を受け取りません ——
    **黙って粗く読むより、止まるほうがよい**（この輪では「片方だけ」が7回起きています）。

    **効きは前提として登録済みです**（`config/hypotheses.yaml`・9/05 判定）。
    1本あたりの再生が半分未満に落ちるなら、この道は間違いです。
    """
    if not date_jst:
        return [str(hour)] * count
    if step_min != 60:
        return _slots_fine(count, hour, date_jst, hours, step_min, taken, taken_min)
    if taken is None:
        taken = ledger_hours(date_jst)
    if hours:
        picked = hours
        clash = sorted(set(hours[:count]) & taken)
        if clash:
            print(f"[batch] **{date_jst} の {clash} は控えでは埋まっています。**"
                  " --hours が明示されているので続けますが、"
                  "取り消し済みの枠でなければ `upload_only.py` が落とします。",
                  flush=True)
    else:
        picked = [h for h in range(hour, 24) if h not in taken]
        if len(picked) < count:
            raise SystemExit(
                f"{date_jst} は {hour}時以降の空きが {len(picked)} 個しかありません"
                f"（{count} 本ぶん要ります／控えでの埋まり {sorted(taken)}）。\n"
                "        **別の日にするか、--hour を早めるか、本数を減らすこと。**\n"
                "        控えは上限側の見積りなので、取り消した本の枠も埋まりに数えます。\n"
                "        そこへ置き直すなら --hours で明示すること。"
            )
        if picked[:count] != list(range(hour, hour + count)):
            print(f"[batch] {date_jst} の埋まり {sorted(taken)} を避けて"
                  f" {picked[:count]} 時に置きます（控えから。API 0単位）", flush=True)
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
    """M14 の比較の窓に置こうとしていないかを見る。**記憶に任せない。**

    中身は `src/measure_window.check` です。**窓を読むのは呼ばれた時**なので、
    検査が `M14_WINDOW` を差し替える手はそのまま効きます。
    """
    measure_window.check(date_jst, force=force, tool="batch_build.py --date",
                         window=M14_WINDOW)


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

    # **1本ぶんの秒数を残す。** これが無かったので「`--jobs` の上限」が
    # 4回持ち越されました（上の節）。**落ちた本も測ります** ——
    # 落ちるまでに使った時間も、他の本を待たせているからです。
    started = datetime.now(JST)
    cmd = [sys.executable, "-m", "src.pipeline", "--topic", tid, "--dry-run"]
    if not long_form:
        cmd.append("--short")
    code, _ = run(cmd, BUILD_TIMEOUT, tid)
    row["build_sec"] = round((datetime.now(JST) - started).total_seconds(), 1)
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
    row["make_sec"] = round((datetime.now(JST) - started).total_seconds(), 1)
    return row


def video_id_of(out: str) -> str:
    for line in reversed(out.splitlines()):
        if line.startswith("VIDEO_ID "):
            return line.split(None, 1)[1].strip()
    return ""


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def report() -> int:
    """台帳を `jobs` 別に並べる。**生成しません**（数秒で終わります）。

    見るのは2つだけ。

        速くなった倍率   直列の合計 ÷ 壁時計。**jobs に近いほど、待ち時間が素直に重なっている**
        1本あたりの中央値 **jobs を上げるほど伸びていたら、そこが上限**

    倍率だけでは上限が出ません（本数と題材で動くので）。
    **太り始めたかどうかが、同じ走りの中で比べられる唯一の量**です。
    """
    if not LOG.exists():
        print("まだ1回も走っていません（data/batch_runs.jsonl が空）。")
        return 1
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    timed = [r for r in rows if r.get("jobs") and r.get("wall_sec")]
    print(f"=== batch の走り {len(rows)} 回（うち時間が入っているのは {len(timed)} 回）===")
    if not timed:
        print("\n  **時間の入った走りがまだありません。**")
        print("  2026-08-15 22:3x より前の走りには `jobs` も秒数も入っていません")
        print("  （入れていなかったので、`--jobs` の上限が4回持ち越されました）。")
        print("  次に `batch_build.py` を走らせた回から、ここに並びます。")
        return 1

    by_jobs: dict[int, list[float]] = {}
    print("\n  日時              同時 本数  壁時計   直列なら  倍率  1本あたりの中央値")
    for r in timed:
        per = [float(x["build_sec"]) for x in r.get("results", [])
               if x.get("build_sec")]
        med = _median(per)
        by_jobs.setdefault(int(r["jobs"]), []).extend(per)
        print(f"  {r['at'][5:16]:<16} {r['jobs']:>3} {r.get('count', len(per)):>4}"
              f" {r['wall_sec']/60:>7.1f}分 {(r.get('serial_sec') or 0)/60:>8.1f}分"
              f" {str(r.get('speedup') or '—'):>5}  {med/60:>6.1f}分")

    # **1回の走りの中で出した「倍率」は、自分に甘い。**
    #
    # `speedup` は「1本ずつの秒数の合計 ÷ 壁時計」ですが、その1本ずつの秒数は
    # **既に混雑で太った後の値**です。太るほど分子も大きくなるので、
    # **混雑しているときほど倍率が良く見えます**（8/15 22:3x の実測で 4.2倍と出た。
    # 本当は 2.6倍）。**割る相手は、いちばん空いている走りの1本あたり**です。
    per_run_thru = {}
    for r in timed:
        per = [float(x["build_sec"]) for x in r.get("results", []) if x.get("build_sec")]
        if per and r.get("wall_sec"):
            per_run_thru.setdefault(int(r["jobs"]), []).append(
                len(per) / float(r["wall_sec"]))

    js = sorted(by_jobs)
    base = _median(by_jobs[js[0]])
    base_thru = max(per_run_thru.get(js[0], [0.0]))

    print("\n  **jobs 別**（1本あたりが太り始めた点と、実際に出た本数）")
    print("    同時  本数  1本あたり  太り方   1時間あたり  空いているときの何倍")
    for j in js:
        med = _median(by_jobs[j])
        swell = med / base if base else 0.0
        thru = max(per_run_thru.get(j, [0.0])) * 3600.0
        gain = (thru / (base_thru * 3600.0)) if base_thru else 0.0
        print(f"    {j:>3} {len(by_jobs[j]):>5}本 {med/60:>8.1f}分 {swell:>7.2f}倍"
              f" {thru:>10.1f}本 {gain:>13.2f}倍")

    if len(js) < 2:
        print("\n  **まだ1種類の `jobs` しか走っていません。** 上限は言えません。")
        print("  別の `--jobs` で1回走らせると、上の行が2行になって比べられます。")
        return 0

    top = max(js, key=lambda j: max(per_run_thru.get(j, [0.0])))
    worst = max(js, key=lambda j: _median(by_jobs[j]))
    swell = _median(by_jobs[worst]) / base if base else 0.0

    if swell >= 1.3:
        print(f"\n  **同時 {worst} で1本あたりが {swell:.2f}倍に太っています。**"
              " 待ち時間だけでなく、こちらの資源も取り合い始めています。")
    else:
        print(f"\n  1本あたりは最大でも {swell:.2f}倍で、**まだ太っていません。**")

    # **太り始めた ≠ 上限。** 1本あたりが遅くなっても、同時に走る本数が
    # それ以上に増えていれば、**1時間あたりに出る本数は増え続けます。**
    # 止めるのは「太ったから」ではなく「**出る本数が増えなくなったから**」。
    if top == max(js):
        print(f"  それでも**いちばん出たのは同時 {top}**です"
              f"（1時間あたり {max(per_run_thru[top])*3600:.1f}本）。"
              " **太り始めた点は上限ではありません。**")
        print(f"  まだ上げられます。次は同時 {max(js)*2} を1回。"
              " **出る本数が増えなくなったところが上限**です。")
    else:
        print(f"  **出る本数がいちばん多いのは同時 {top}** で、それより上げると"
              "減っています。**そこが上限です。**")
    return 0


def _push_thumbnails_first() -> None:
    """溜まったサムネイルを、**この回の投稿が単位を使い切る前に**押す。

    **落ちても投稿は続けます。** ここで止めると、サムネイル（あれば良いもの）の
    ために投稿（途切れるのが最大の損失）を止めることになります。**順番が逆です。**
    """
    try:
        import refresh_thumbnail

        if not upload_cap.day_quota().open:
            return                      # 観測済みで閉じている。撃つだけ無駄
        refresh_thumbnail.push_missing()
    except Exception as exc:                                   # noqa: BLE001
        print(f"[batch] サムネイルの押し直しは飛ばします: {str(exc)[:120]}", flush=True)


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
    ap.add_argument("--step-min", type=int, default=60,
                    help="--date と一緒に使う。予約の間隔（分・60の約数）。"
                         "既定の60は1日11枠まで（9〜19時）＝投稿枠92本の1/8。"
                         "30 にすると1日22枠。--hours とは併用できません")
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
    ap.add_argument("--report", action="store_true",
                    help="台帳を jobs 別に並べるだけ（**生成も予約もしません**・数秒）")
    args = ap.parse_args(argv)

    if args.report:
        return report()

    # ---- 0. **撃つ前に、1日の投稿本数の枠を見る**（2026-08-17 に足した）----
    #
    # 下の「2. 予約する」には、429 に当たったら止まる門が既にあります。
    # **あれは作り終えたあとにしか効きません。** 10:5x の回は6本を作ってから当たり、
    # **6本とも `build/` ごと捨てました**（コンテナが畳まれると消えます）。
    #
    # ここは **API を1単位も使いません**（控えと観測の記録だけ）。だから
    # **Data API の日枠が切れている回でも効きます** —— そういう回は1日13時間あり、
    # 撃てるかどうかを口に訊く道がそもそもありません。
    explicit = [i.strip() for i in args.topics.split(",") if i.strip()]
    if not args.skip_upload:
        cap = upload_cap.state()
        print(f"[batch] {cap.line}", flush=True)
        if cap.remaining <= 0:
            print("[batch] **作りません。**（予約せずに作るだけなら "
                  "`--skip-upload`。枠が戻ってから "
                  '`upload_only.py <ID> "" <日付>@<時>` で打てます）', flush=True)
            return 1
        want = len(explicit) if explicit else args.count
        if cap.remaining < want:
            print(f"[batch] 要求 {want} 本を **{cap.remaining} 本に縮めます**"
                  "（残りは作っても撃てず、`build/` ごと消えるだけなので）。",
                  flush=True)
            if explicit:
                explicit = explicit[:cap.remaining]
            else:
                args.count = cap.remaining

    # ---- 0.5 **溜まったサムネイルを、投稿より先に押す**（2026-08-17 22:4x に足した）--
    #
    # **順番がすべてです。** Data API の単位枠は 10,000単位で、
    # `videos.insert` は 1本 1,600単位 —— **7本で 11,200単位**。1周で7〜8本
    # 上げているので、**窓が開いた直後の1周が、その窓の単位を丸ごと使い切ります。**
    # `thumbnails.set` は 50単位しか要らないのに、**いつも投稿の後ろに並んでいた**ので
    # 一度も順番が回ってきませんでした。
    #
    #     待ち行列は 8/17 の1日で 28 → 33本にふえ、
    #     `missing_thumbnail` は **15回鳴って当たり2回**
    #
    # 一覧が悪いのではありません。**押せる時刻に、押す手順が無かった**だけです。
    # 5本ぶんで 250単位（投稿0.16本ぶん）なので、**投稿の本数は減りません。**
    _push_thumbnails_first()

    topics = pick(args.count if not explicit else len(explicit), explicit,
                  per_calc=args.per_calc)
    if not topics:
        print("[batch] 作れるテーマがありません。config/topics.yaml を足すこと。")
        return 1

    if args.date:
        check_window(args.date, args.force_window)
    hours = [int(h) for h in args.hours.split(",") if h.strip()]
    when = slots(len(topics), args.hour, args.date or None, hours,
                 step_min=args.step_min)

    if args.date:
        # **`+ ':00'` と書かないこと**（2026-08-18 に直した）。`--step-min` を
        # 足すまで時しか無かったので足していましたが、いまは `10:30` が来ます。
        shown = ", ".join(_show_slot(w) for w in when)
        print(f"[batch] {len(topics)} 本を **{args.date} の1日に**入れます"
              f"（{shown} JST）")
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
    wall_sec = round((datetime.now(JST) - began).total_seconds(), 1)
    spent = wall_sec / 60
    print(f"\n[batch] 作れたのは {built} / {len(topics)} 本（{spent:.1f}分・同時 {jobs}）",
          flush=True)

    # **重なりを、その場で出す。** 台帳に残すだけだと誰も読みません
    # （`--jobs` が4回持ち越されたのは、まさにそれです）。
    serial_sec = round(sum(float(r.get("make_sec") or r.get("build_sec") or 0.0)
                           for r in results), 1)
    speedup = round(serial_sec / wall_sec, 2) if wall_sec > 0 else None
    per_book = [float(r["build_sec"]) for r in results if r.get("build_sec")]
    if per_book and jobs > 1:
        mean = sum(per_book) / len(per_book)
        print(f"[batch] 直列なら {serial_sec/60:.1f}分 → **{speedup} 倍**"
              f"（同時 {jobs}）／1本あたり {mean/60:.1f}分", flush=True)
        print("[batch] **1本あたりが jobs を上げるほど伸びていたら、そこが上限です**"
              "（`--report` で並べて見ること）", flush=True)

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

        # **1日の投稿本数の枠に当たったら、そこで止めること**（2026-08-17 に踏んだ）。
        #
        # この枠は Data API の10,000単位とは別で、**当たったら残り全部が必ず落ちます。**
        # ところがここは1本ずつ独立に撃つので、**6本を撃って6本とも同じ429**で捨てました。
        # `--stop-on-error` は既定で off なので、旗に頼ると次も同じことが起きます。
        # **「次も必ず落ちる」と分かっている失敗だけは、旗によらず止めます。**
        if not vid and auth.is_upload_cap(RuntimeError(out)):
            # **観測は `src/uploader._note_cap` が既に残しています**（2026-08-17）。
            # ここで重ねて書かないこと —— 予約は `upload_only.py` を**子プロセス**で
            # 叩くので、向こうの中で `videos.insert` が落ちた時点で記録されています。
            # 両方で書くと、1回の 429 が「2回観測した」に見えます。
            rest = [r["topic"] for r in results[n:] if r.get("built")]
            print(f"[batch] **1日の投稿本数の枠に当たりました**（HTTP 429・"
                  "Data API の10,000単位とは別の枠）。"
                  "**残りを撃っても全部落ちるので、ここで止めます。**", flush=True)
            print(f"[batch] 戻るのは **JST 16:00 ごろ**（太平洋時間の0時）。", flush=True)
            if rest:
                print(f"[batch] **作ってあるのに predicate できていない本が {len(rest)}本**"
                      "。`build/` に残っているので、枠の戻った回に打ち直せます:", flush=True)
                for tid in rest:
                    print(f"[batch]     python scripts/upload_only.py {tid} "
                          f'"" <日付>@<時>', flush=True)
            for r in results[n:]:
                if r.get("built") and not r.get("video_id"):
                    r["error"] = "投稿本数の枠で撃っていません（build/ に残っています）"
            break

        if code != 0 and not vid and args.stop_on_error:
            break

    for row in results:
        row.pop("built", None)

    stamp = datetime.now(JST).isoformat(timespec="seconds")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"at": stamp, "hour": args.hour, "date": args.date or None,
             "slots": when,
             # **`jobs` と秒数は、この台帳にしか残りません。**
             # `build/` もセッションの画面も、次の回には無い。
             "jobs": jobs, "count": len(topics),
             "wall_sec": wall_sec, "serial_sec": serial_sec, "speedup": speedup,
             "long": bool(args.long),
             "results": results},
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
