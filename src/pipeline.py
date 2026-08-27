"""1本ぶんの動画を作って投稿する。

流れ:
  チャンネルから投稿済みを読む → テーマを選ぶ → 台本 → 音声 → 図解 → 合成
  → 検査 → 投稿 → テーマが減っていれば補充
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
from pathlib import Path

from . import bars, config, history, subtitles, thumbnail, uploader, verify, visuals
from .renderer import build_narration, build_video, segment_timeline
from .script_writer import (SHORT_SEGMENT_CHARS, VideoScript, generate,
                            short_script_problems)
from .tts import synthesize_segments
from .util import fmt_timestamp

LOW_WATER_MARK = 6
EXPLORE_RATE = 0.3


def pick_topic(pool: dict, posted: set[str], topic_id: str = "") -> dict:
    """次に作るテーマを選ぶ。

    基本はスコア最大。ただし3割の確率で、未投稿のものから無作為に選ぶ。
    スコアはあくまで推測なので、常に最大を取ると、推測が外れていたときに
    そこから抜け出せない。たまに違うものを試して確かめる。
    """
    if topic_id:
        for topic in pool["topics"]:
            if topic["id"] == topic_id:
                return topic
        if topic_id.startswith("s-"):
            # ショートは長尺のテーマ枠を消費しない。s- で始まるIDは
            # topics.yaml に置かず、その場で作る。長尺のプールを汚さないため。
            #
            # ただし calc は引き継ぐ。引き継がないと台本を書く側に数字が渡らず、
            # **発明するしかなくなる**。
            #
            # `s-<計算モジュール名>-<連番>` と名付ける。s-nenkin-1 なら src/calc/nenkin.py。
            # これまで実際にそう名付けてきた（s-zangyo-1 / s-kojo-1 / s-shitsugyo-1）ので、
            # 規則を後から合わせるのではなく、その規則をそのまま使う。
            stem = topic_id[2:].rsplit("-", 1)[0]
            calc = stem if (config.ROOT / "src" / "calc" / f"{stem}.py").exists() else ""
            if not calc:
                base = next(
                    (t for t in pool["topics"] if t["id"].startswith(stem) and t.get("calc")), None
                )
                calc = base["calc"] if base else ""
            return {
                "id": topic_id, "title_seed": topic_id, "angle": "ショート", "score": 1.0,
                **({"calc": calc} if calc else {}),
            }
        raise RuntimeError(
            f"テーマ '{topic_id}' が config/topics.yaml にありません。"
            f"使えるID: {', '.join(t['id'] for t in pool['topics'][:20])}"
        )

    candidates = [t for t in pool["topics"] if t["id"] not in posted]
    if not candidates:
        raise RuntimeError(
            "未投稿のテーマがありません。config/topics.yaml に追加するか、"
            "「3. テーマを実績から入れ替える」を実行してください。"
        )

    if len(candidates) > 1 and random.random() < EXPLORE_RATE:
        topic = random.choice(candidates)
        print(f"[pipeline] 探索: 無作為に選びました（{int(EXPLORE_RATE * 100)}%の確率）")
        return topic
    return max(candidates, key=lambda t: float(t.get("score", 1.0)))


def pick_thumbnail_slide(script: VideoScript) -> int:
    """サムネイルの背景に使うスライドの番号を返す。

    1枚目は使わない。冒頭の結論——サムネに重ねるのと同じ数字——が書いてあるため。
    「真ん中を取る」にしたら真ん中が stat（巨大な数字1つ）に当たって、また
    同じ数字が背後に透けた。位置で選ぶかぎり運任せになる。

    だから**種類で選ぶ**。chart と table は細かい要素が散っていて、潰したときに
    色の面として残る。stat は要素が1つしかないので、何をしても形が残る。
    """
    for wanted in ("chart", "table", "steps", "compare"):
        for i, seg in enumerate(script.segments):
            if i > 0 and seg.visual.kind == wanted:
                return i
    return min(len(script.segments) - 1, max(1, len(script.segments) // 2))


def build_description(script: VideoScript, spans: list[tuple[float, float]],
                      channel: dict, topic_id: str) -> str:
    parts = [script.description_body.strip(), "", "▼ 目次"]

    lines = []
    for chapter in sorted(script.chapters, key=lambda c: c.segment_index):
        index = max(0, min(chapter.segment_index, len(spans) - 1))
        start = 0.0 if not lines else spans[index][0]
        lines.append(f"{fmt_timestamp(start)} {chapter.label}")
    if not lines:
        lines = ["0:00 はじめに"]
    parts += lines

    parts.append(channel["publish"]["footer"].rstrip())
    # 投稿済みの印。次回このテーマが選ばれないための唯一の記録で、
    # 動画を消せばこの記録も一緒に消える（＝また作れるようになる）。
    parts += ["", history.marker(topic_id)]
    return "\n".join(parts)


def refill_topics_if_low(posted: set[str]) -> None:
    """未投稿のテーマが減ってきたら補充する。投稿自体は失敗させない。"""
    unused = [t for t in config.load_topics()["topics"] if t["id"] not in posted]
    if len(unused) > LOW_WATER_MARK:
        print(f"[pipeline] 未投稿テーマ {len(unused)} 件。補充は不要。")
        return

    print(f"[pipeline] 未投稿テーマが {len(unused)} 件まで減ったので補充します。")
    try:
        from . import analytics

        analytics.optimize(posted)
    except Exception as exc:
        print(f"[pipeline] テーマの補充に失敗しました（投稿は成功しています）: {exc}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="動画を1本作って投稿する")
    parser.add_argument(
        "--script",
        help="台本JSONのパス。渡すと台本生成を飛ばす。"
             "常駐セッションが自分で書いた台本を使うときはこれ",
    )
    parser.add_argument("--topic", help="テーマID。--script を使うときは必須")
    parser.add_argument(
        "--calc",
        help="使う計算モジュール名（src/calc/<名前>.py）。テーマ側の calc を上書きする。"
             "台本を書く側にはここで出た数字しか渡らない",
    )
    parser.add_argument("--visibility", choices=["private", "unlisted", "public"])
    parser.add_argument("--dry-run", action="store_true", help="投稿せず build/ に出すだけ")
    parser.add_argument(
        "--short", action="store_true",
        help="ショート（縦1080x1920・60秒以内）として作る。長尺の尺の下限は適用しない",
    )
    return parser.parse_args(argv)


# 読み上げの速さ（文字/秒）。2026-08-09 実測: 465文字が89秒。
CHARS_PER_SECOND = 5.2
# 1枚の絵が止まってよい秒数。`src/verify.py` が同じ値で最終検査する。
MAX_SLIDE_SECONDS = verify.MAX_SECONDS_PER_SLIDE
# **同じ値を2か所に書かない。** 生成側（script_writer）が守るべき上限と、
# ここで落とす上限がずれたら、片方が通したものをもう片方が落とす。
# 「片方だけ直す」形は 2026-08-08〜09 に5回やっている。**import で1つにする。**
MAX_SHORT_SEGMENT_CHARS = SHORT_SEGMENT_CHARS

# ショートで、絵1枚が画面に残ってよい秒数。**文の長さではなく絵の話。**
# 独立評価が繰り返し指摘してきたのは「1〜2秒ごとの視覚変化」なので、
# その上限側に置いた。1文（5〜6秒）はこれで2〜3枚に割れる。
SHORT_SLIDE_SECONDS = 2.5

#: **遅い側の秒数**（2026-08-27・オーナー指摘で足した A/B の片方）。
#:
#: 上の 2.5 は **M13（独立評価）の言い分だけ**で決まっています —— `MEANS.md` の
#: M13 は**終わった**手段で、そこから来た数は**視聴者の実データで一度も
#: 確かめられていません。**`CLAUDE.md` A14「昔そう決まったから」は理由になりません。**
SHORT_SLIDE_SECONDS_SLOW = 4.5

#: 遅い側に振る割合。**0 にすると振り分けが止まります**（`hook_form` と同じ）。
SLOW_PACE_SHARE = 0.5


def slide_pace(topic_id: str, share: float = SLOW_PACE_SHARE) -> float:
    """ショートの絵1枚が画面に残る秒数。**テーマIDで決まります。**

    ## なぜ置いたか（2026-08-27 21:0x・オーナー指摘）

    オーナー原文:

    > 「動画についてまず何言ってるか分かんないね。音声だけで理解できない説明なのに
    > **画面はすぐ切り替わるし。**説明を理解するにはかなり視聴者側の推論が必要だと思う」

    実測（`data/critique_queue/` の控え **502本**）:

        ショート（コマ>文）439本  尺 26.3秒 ／ 13.0コマ
                                 → **1コマ 2.06秒**（中央値）
                                 **3秒 未満が 100%・2秒 未満が 30%**
        長尺  （コマ=文） 63本   尺 322.9秒 ／ 17.0コマ → 1コマ 19.5秒

    **そして再生の 99.8% は `SHORTS_FEED`、1再生あたり 20秒**（`status.py`）。
    **視聴者が見ている20秒のあいだに、画面は約10回 変わります。**

    ## なぜ「直す」ではなく「振り分ける」のか

    **2.5 は理由があって置かれた数**です（上の註 —— 独立評価3体が
    「同じ絵が2コマ続く」「実質4〜5画面」と書き、中央値4で落ちた）。
    **片方の言い分だけで戻すと、同じ間違いを向きだけ変えてやり直します。**

    そして**その3体は視聴者ではありません。** `docs/MEANS.md` の M13 は
    **終わった**手段で、ここから来た 2.5 は**実データで一度も確かめられていません。**
    向きを知る道は1つしかなく、**違う値の本を作って出すこと**です
    （`hook_form` / `title_form` / `request_form` と同じ形）。

    ## 割り振り（`hook_form` を写しています。**塩だけ変えてあります**）

    - **乱数にしない**（作り直しで群が移ると比較が壊れる）
    - **日付や順番にしない**（`batch_build` は1日ぶんをまとめて撃つので題材と混ざる）
    - **塩を他の実験と変えること。** 同じにすると2つが完全に重なり、
      どちらが効いたのか永久に分かりません
    - **テーマIDだけの純関数**なので、**控えに何も記録しなくても
      後から群を数え直せます**（`config/hypotheses.yaml` の判定がそうします）

    ## この実験が触らないもの（**対照を汚さないこと**）

    読み上げ・台本・字幕・見出し・サムネイル・公開時刻は**1文字も変えません。**
    変わるのは「同じ絵を何枚に割るか」だけです
    （`visuals.reveal_variants` の `want`）。字幕は文の側（`segment_timeline`）に
    付くので、**枚数を変えても字幕はずれません。**

    ## 覆る条件

    - 判定は `config/hypotheses.yaml`（`ショートの刻み-engaged`）。
      **遅い側の engaged が速い側を上回らなければ、2.5 が正しかった**ので
      `SLOW_PACE_SHARE` を 0 にして振り分けを止めること（**定数は消さない** ——
      消すと、次に同じ話が出たときに測り直しになります）
    - 逆に遅い側が勝ったら、`SHORT_SLIDE_SECONDS` を勝った値にして
      振り分けを止めること
    - **どちらも 4.5 と 2.5 の2点しか見ていません。** 勝ったほうの側で
      さらに刻むかは、そのとき別に立てること
    """
    if share <= 0:
        return SHORT_SLIDE_SECONDS
    if share >= 1:
        return SHORT_SLIDE_SECONDS_SLOW
    # **塩 `pace:`**。他の実験と同じ塩にしないこと（docstring の割り振りの項）。
    h = hashlib.sha1(("pace:" + str(topic_id)).encode("utf-8")).digest()
    slow = (int.from_bytes(h[:4], "big") % 10_000) < share * 10_000
    return SHORT_SLIDE_SECONDS_SLOW if slow else SHORT_SLIDE_SECONDS


#: **めくりの途中の1コマが止まる秒数**（2026-08-27 に足した）。
#: `docs/JOURNAL.md` の `opening_motion` が「絵そのものの動き」に使っている
#: 0.9秒 と同じ値です。**新しく思いついた数ではありません** ——
#: この企画が既に「見ている側が変化に気づく長さ」として使っている唯一の実測値。
REVEAL_STEP_SECONDS = 0.9


def reveal_durations(dur: float, n: int) -> list[float]:
    """1文の尺 `dur` を、めくりの `n` コマへ割る。**等分しないこと。**

    ## なぜ等分をやめたか（2026-08-27。オーナーの指摘）

    オーナー原文:

    > **「動画についてまず何言ってるか分かんないね。音声だけで理解できない
    > 説明なのに画面はすぐ切り替わるし。説明を理解するにはかなり視聴者側の
    > 推論が必要だと思う。」**

    ここは 2026-08-15 から `dur / len(parts)` の**等分**でした。
    `reveal_variants` は図を**要素を1つずつ足していく**形に割るので、
    **完成した図はいちばん最後のコマにしかありません。** 等分だと、
    その完成形が画面に居るのは**文の最後の 1/n** です:

        6.0秒 の文 → want=ceil(6.0/2.5)=3コマ → **完成形は最後の 2.0秒 だけ**

    つまり**文がその図を説明しているあいだ、画面に完成形はありません。**
    読み上げは「21万2027円 と 31万9677円 の差が…」と言っているのに、
    画面はまだ棒1本目です。**「かなり視聴者側の推論が必要」はこれです。**

    そして**この向きに押していたのは検査のほうです。** `verify.py` の
    `_check_slide_hold` / `_check_short_pace` は**どちらも上限しか持たず**
    （`MAX_SECONDS_PER_PICTURE=5.0` / `MAX_SECONDS_PER_SLIDE=12.0`）、
    落ちたときの文言は「**セグメントを増やして画を動かすこと**」です。
    **下限は1つもありませんでした** —— 0.3秒 のコマも全部 通ります。

    ## 割り方

    途中のコマは `REVEAL_STEP_SECONDS`（0.9秒）ずつ。**残りは全部 完成形へ。**
    合計は `dur` のまま変えません（音とずれるので）。

    - 完成形が `SHORT_SLIDE_SECONDS`（2.5秒）に満たないなら、**コマを減らします**
      （減らす先は**頭のほう** ＝ いちばん中身の少ないコマ）
    - 完成形が `MAX_SECONDS_PER_PICTURE`（5.0秒）を超えるなら、**途中のコマを
      伸ばして**引き取ります（止まって見える側に落ちないため）

    **覆る条件**: 完成形を長く置くほうが `engaged` を下げると実測で出たとき。
    それを測る前提が `config/hypotheses.yaml` の `reveal_hold` です。
    """
    if n <= 1 or dur <= 0:
        return [dur] * max(1, n)
    # 完成形が 2.5秒 に届くところまで、頭のコマを落とす
    while n > 1 and dur - REVEAL_STEP_SECONDS * (n - 1) < SHORT_SLIDE_SECONDS:
        n -= 1
    if n <= 1:
        return [dur]
    step = REVEAL_STEP_SECONDS
    last = dur - step * (n - 1)
    if last > verify.MAX_SECONDS_PER_PICTURE:
        # 完成形が長すぎる。**余りは途中のコマが引き取る**（等分に戻さない）
        step = (dur - verify.MAX_SECONDS_PER_PICTURE) / (n - 1)
        last = verify.MAX_SECONDS_PER_PICTURE
    return [step] * (n - 1) + [last]


def _check_short_script(script, topic_id: str = "") -> None:
    """ショートの台本を、**音声合成の前に**落とす。

    2026-08-09、6セグメントのショートが合計465文字＝89秒になり、
    1枚15秒で `verify` に落ちた。**落ちたのはレンダリングまで終わったあと**で、
    15分ぶんの合成と描画が捨てになった。

    **同じことを、始まる前に judge できる。** 読み上げの速さは実測で
    1秒あたり約5.2文字なので、文字数を見れば秒数が分かる。
    `verify` を弱めるのではなく、**同じ条件を前倒しで当てる。**
    """
    problems = [f"  {p}" for p in short_script_problems(script, topic_id)]
    if problems:
        raise RuntimeError(
            "ショートの台本が条件を満たしていません（音声合成の前に止めました）:\n"
            + "\n".join(problems)
            + "\n**テーマの angle を短く刻むよう直すか、そのまま再実行してください。**"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    channel = config.load_channel()
    pool = config.load_topics()
    dry = args.dry_run or config.dry_run()

    # ショートは縦画面で、尺の下限も別。長尺の 8.5 分はミッドロール広告のための
    # 下限なので、ショートには意味がない。
    if args.short:
        channel["video"] = dict(channel["video"])
        channel["video"]["resolution"] = [1080, 1920]
        channel["video"]["min_minutes"] = 0.25
        # 尺の上限も渡さないと、台本を書く側が長尺の分量で書いてくる。
        # target_minutes だけ据え置くと上限が「目標＋1.5分」のままになり、
        # 60秒のつもりが1.4分で出てくる（実際に起きた）。
        # **2026-08-09、50秒 → 30秒に縮めた。** engaged 比率（すぐスワイプ
        # されなかった再生の割合）が配信の駆動輪だと分かったため。
        # 実測の engaged は 11.8〜44.2%、中央値34.8%。競合調査でも
        # 「25〜35秒に圧縮」「1画面1情報」と指摘された。
        # **これは実験。** `config/hypotheses.yaml` に反証条件を書いてある。
        channel["video"]["target_minutes"] = 0.50   # 約30秒（140文字 ÷ 4.63文字/秒）
        channel["video"]["max_minutes"] = 0.60      # 36秒。無音込みの実効速度で引いた
        print("[pipeline] ショートとして作ります（1080x1920・約30秒・上限36秒）")

    override = args.visibility or config.env("VISIBILITY", required=False)
    if override:
        channel["publish"]["visibility"] = override
        print(f"[pipeline] 公開設定を {override} で上書き")

    # 投稿済みはチャンネルから読む。ファイルには持たない。
    # --dry-run でも本数だけは実際に数える。配色を投稿済み本数で回しているので、
    # ここを 0 にすると dry-run と本番で色が変わってしまう。
    # dry-run で作った final.mp4 をそのまま投稿する運用（scripts/upload_only.py）
    # なので、dry-run 側が本番の色でなければ意味がない。
    already = history.posted_topic_ids()
    posted: set[str] = set() if dry else already
    theme_index = len(already)
    topic_id = args.topic or config.env("TOPIC_ID", required=False)
    if args.script and not topic_id:
        raise RuntimeError("--script を使うときは --topic でテーマIDを指定してください")
    topic = pick_topic(pool, posted, topic_id)
    if args.calc:
        topic = {**topic, "calc": args.calc}
    print(f"=== テーマ: {topic['title_seed']} ({topic['id']}) ===")
    if not args.script and not topic.get("calc"):
        # 台本を生成させるのに計算が無いと、数字を発明させることになる。
        # 「裏の取れない数字は動画に入れない」はここで守らないと守れない。
        raise RuntimeError(
            f"テーマ {topic['id']} に calc がありません。"
            "config/topics.yaml に calc: <モジュール名> を書くか、--calc で渡すか、"
            "--script で自分の書いた台本を渡してください"
        )

    work = config.BUILD_DIR / topic["id"]

    # **作業ディレクトリを消す前に台本を読む。**
    # 2026-08-08、`--script build/iryohi-kojo/script.json` を渡したら、
    # `rmtree` が**その台本ごと消してから**読みに行って落ちた。
    # 前回の生成物を作り直すのは普通の使い方で、置き場所も build/ の中。
    # **自分の入力を消す作りになっていた。** 順序を入れ替えれば起きない。
    raw = Path(args.script).read_text(encoding="utf-8") if args.script else None

    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    # 1. 台本。セッションが自分で書いたものがあればそれを使い、無ければ生成する。
    if raw is not None:
        script = VideoScript.model_validate_json(raw)
        print(f"[pipeline] 台本を読み込みました: {args.script}")
        (work / "script.json").write_text(raw, encoding="utf-8")
    else:
        script = generate(channel, topic)
        # **生成した直後に置く。** 台本を書かせるのが一番高い工程なのに、
        # これまで `script.json` を書くのは動画を作り終えた後（下の 6.）だけだった。
        # レンダリングや検査で落ちると**台本ごと消えて、また書かせ直していた。**
        # `used_bars()` もこのファイルを読むので、落ちた回の数値は
        # 「使用済み」として数えられず、次の回が同じ棒を選びうる。
        (work / "script.json").write_text(
            json.dumps(script.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"[pipeline] タイトル: {script.title}")

    if args.short:
        _check_short_script(script, topic["id"])

    # **「同じ図」は台本だけで分かる。動画を作り終えてから見るのは遅い。**
    #
    # `verify._check_not_repeat` は chart の `display` しか見ていないのに、
    # 呼ばれるのは音声合成と全スライドのレンダリングが終わったあと（下の 7.）。
    # 2026-08-09、`tenshoku-nenshu` が `s-tedori-1` と 71.9%・62.2% で重なり、
    # **15分かけて作ってから落ちるところだった**（気づいたのは手で照合したから）。
    #
    # `short_script_problems` に書いた原則と同じ:
    # **台本だけで判定できるものは、全部ここに集める。**
    repeats = verify._check_not_repeat(work, script.model_dump())
    if repeats:
        raise RuntimeError(
            "台本の時点で過去の図と重なっています（レンダリング前に止めました）: "
            + " / ".join(repeats)
        )

    # 2. 音声（ここで各セグメントの実尺が確定する）
    audios = synthesize_segments(
        [s.narration for s in script.segments],
        channel["generation"]["tts"],
        work / "audio",
    )
    if not audios:
        raise RuntimeError("台本のセグメントが空でした。テーマを変えて再実行してください。")

    segment_paths = [p for p, _ in audios]
    durations = [d for _, d in audios]
    spans = segment_timeline(durations)
    print(f"[pipeline] 想定尺: {spans[-1][1] / 60:.1f} 分")

    # 3. 図解を自前で描いて撮る
    # 配色は投稿済みの本数から順番に回す。連続する回が同じ色にならないように。
    # **1つの読み上げ文に、絵を複数枚あてる**（2026-08-15。ショートだけ）。
    #
    # ここは長く「1文＝1枚」でした。ショートは1文が5〜6秒あるので、
    # **その間ずっと画面が止まります。** 独立評価（M13）は3体そろって
    # 「同じ絵が2コマ続く」「実質4〜5画面しかない」と書き、中央値4で落ちました。
    #
    # 文を短くする道は 2026-08-09 に潰れています（140文字÷8枚＝17文字で文にならない）。
    # **だから割るのは絵のほう。** 字幕は `spans`（文の側）から作るので、
    # ここで絵を増やしても**字幕はずれません。**
    plan = [s.visual.model_dump() for s in script.segments]
    if args.short:
        expanded: list[dict] = []
        expanded_durations: list[float] = []
        slide_index_of_segment: list[int] = []
        # **1コマの秒数は、テーマIDで2つに振り分けます**（2026-08-27・オーナー指摘）。
        # 理由と実測は `slide_pace()` の docstring。**ここ以外は1文字も変えません。**
        pace = slide_pace(args.topic or "")
        print(f"[pipeline] ショートの刻み: **1コマ {pace}秒**"
              f"（テーマIDで決まる。遅い側の割合 {SLOW_PACE_SHARE:.0%}）")
        for visual, dur in zip(plan, durations):
            want = max(1, math.ceil(dur / pace))
            parts = visuals.reveal_variants(visual, want)
            secs = reveal_durations(dur, len(parts))
            # **落とすのは頭のコマ**（要素を1つずつ足す形なので、頭がいちばん空）。
            # `reveal_durations` が「完成形に 2.5秒 が要る」と言って減らした分。
            if len(secs) < len(parts):
                parts = parts[len(parts) - len(secs):]
            expanded.extend(parts)
            # **その文の「全部出ている」コマを指す**（2026-08-15 22:2x に先頭から変更）。
            #
            # ここは長く「その文の**先頭**のコマ」でした。めくりが
            # 「要素を1つずつ足していく」形だったので、先頭は**いちばん中身が少ない**
            # コマです。使い道はサムネ1つ（下の `thumbnail.create`）で、
            # **サムネにいちばん空の絵を渡していました。**
            #
            # 同じ回に `reveal_variants` の stat を「前提を先・数字を後」に変えたので、
            # 先頭のままだと**サムネから数字が消えます。**（気づいたのは、
            # この行を読んだからです。実物を作る前に見つかりました）
            slide_index_of_segment.append(len(expanded) - 1)
            # **等分をやめました**（2026-08-27。理由は `reveal_durations`）。
            expanded_durations.extend(secs)
        held = max(d for d in expanded_durations)
        print(f"[pipeline] 絵を {len(plan)} 枚 → {len(expanded)} 枚に割りました"
              f"（1枚の最長 {held:.1f}秒 / 目標 {SHORT_SLIDE_SECONDS}秒）")
        plan, durations = expanded, expanded_durations
        # **1枚あたり何秒かは、ここでしか分かりません。**
        # `verify.py` は script.json（＝文の数）しか持っていないので、
        # `尺 ÷ 文の数` という**平均**でしか見られず、割れなかった1枚が
        # 平均に埋もれます（2026-08-15、stat の1枚が 5.8秒 止まっていたのに
        # 平均 5.0秒 で上限12秒を通った）。**実際の割り当てを渡す。**
        (work / "slide_seconds.json").write_text(
            json.dumps([round(d, 3) for d in durations]), encoding="utf-8"
        )
        # **どのコマが「完成形」かも渡すこと**（2026-08-27）。
        # 秒数の並びだけでは、`verify` は「短い1コマ」がめくりの途中なのか
        # 説明の相手なのかを見分けられません。**下限を当てる先はここです。**
        (work / "slide_complete.json").write_text(
            json.dumps(slide_index_of_segment), encoding="utf-8"
        )
    else:
        slide_index_of_segment = list(range(len(plan)))

    # **画面に出る側を、そのまま残す**（2026-08-15 20:5x）。
    #
    # `verify.py` は script.json（＝文の側）しか持っていませんでした。
    # ところが独立評価の3体が見ているのは**割った後のコマ**で、
    # 「見出しが同じで表の行数だけ増える」は**割った後にしか存在しません。**
    # だから「隣り合う2枚が同じ」の検査を script に足しても**永久に0件**で、
    # 同じ指摘が3回持ち越されました（`docs/JOURNAL.md`「見た層と直す層のずれ」）。
    #
    # **見る層を、見られている層に合わせる。** これがその1行です。
    (work / "slides_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False), encoding="utf-8"
    )

    slides = visuals.render(
        plan, work / "slides", topic["id"],
        theme_index=theme_index, portrait=args.short,
    )

    # 4. 字幕
    ass_path = subtitles.build(
        [
            {"narration": seg.narration, "start": start, "end": end}
            for seg, (start, end) in zip(script.segments, spans)
        ],
        work / "subtitles.ass",
        portrait=args.short,
    )

    # 5. 合成
    narration = build_narration(segment_paths, work)
    video_path = build_video(
        slides, durations, narration, ass_path,
        work / "final.mp4", work, channel["video"],
    )

    # 6. サムネイル
    theme = visuals.theme_for(topic["id"], theme_index)
    accent = tuple(int(theme["accent"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    thumb_path = thumbnail.create(
        # **絵を割ったので、文の番号をそのまま使えません。**
        # 割る前の番号を、割ったあとの先頭の番号へ引き直す。
        slides[slide_index_of_segment[pick_thumbnail_slide(script)]],
        script.thumbnail_line1, script.thumbnail_line2,
        work / "thumbnail.jpg", work, accent=accent,
    )

    description = build_description(script, spans, channel, topic["id"])

    (work / "title.txt").write_text(
        script.title + "\n\n[別案]\n" + "\n".join(script.title_alternatives) + "\n",
        encoding="utf-8",
    )
    (work / "description.txt").write_text(description + "\n", encoding="utf-8")
    (work / "script.json").write_text(
        json.dumps(script.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 7. 投稿前の検査。ここで落ちたら投稿しない。
    verify.check(video_path, channel["video"], float(channel["video"]["min_minutes"]), work, topic)

    if dry:
        print("[pipeline] DRY_RUN のためアップロードしません。")
        print(f"  動画: {video_path}\n  サムネ: {thumb_path}")
        print(f"\n  タイトル: {script.title}\n  説明欄:\n{description}")
        return 0

    # 8. 投稿。最初のコメントは台本と一緒に生成させたものを使う。
    channel["publish"]["first_comment"] = script.first_comment
    video_id = uploader.upload(
        video_path, thumb_path, script.title, description,
        script.tags, channel["publish"],
    )

    # 公開した棒を残す。`build/` は .gitignore なので、これをやらないと
    # 次のコンテナで「同じ図」検査の比較対象がゼロになる（`src/bars.py`）。
    bars.record(topic["id"], video_id, script.model_dump())

    refill_topics_if_low(posted | {topic["id"]})
    print("=== 完了 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
