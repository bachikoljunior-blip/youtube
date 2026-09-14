#!/usr/bin/env python3
"""オーナーの「分かりにくい」の**連を数える**（API 0単位・`data/inbox.jsonl` の字だけ）。

    python scripts/owner_words.py            # いまの連と、言葉の並び
    python scripts/owner_words.py --days 21  # さかのぼって見る日数（既定 21）

**なぜ置いたか**（2026-09-13 14:0x JST・optimizer・Opus）:
オーナーは **2026-09-10 から 4日 続けて**「説明が分かりにくい／話がつかめない」と言っています。
その 3回（09/10・09/11・09/12）に対して、こちらは**毎回 `docs/METHOD.md` §3 に規則を 1つ 足して**
います（09/10 → 7-b 板と札／09/11 → 7-c しくみ／09/12 → 12 順）。
**それでも翌日、同じ族の言葉が来ています（3/3）。**
オーナー自身が 09/11 19:2x に **「今回だけ教えてもまたおんなじことになるだろ」**（`10f70f79`）と
言っており、**この手が効いているかどうかを数える口が、どこにもありませんでした**
＝ この repo でいちばん多い壊れ方（**「N回 続いたら」と書いて N を数える物が無い**）の族です
（`trend.views_streak`・`late_run`・`blind_run`・`reporting_empty_run`・`outside_runs`・
`feature_cohorts`・`shape_run`・`turf_run` …）。derivation は `docs/JOURNAL.md` 09/13 14:0x。

**この道具は判定しません。** 数を並べるだけです ——
**「形を変えるか」の判定は台本を持つ `hourly` とオーナー**（`docs/METHOD.md` §5・§7）。

**数え方**（変えるときは、この註と一緒に検査 `tests/test_owner_words.py` も直すこと）:

    札           `CLARITY_IDS`（下）に挙げた受け取り帳の id だけを「分かりにくさの言葉」として数える。
                 **語では拾いません** —— 実測: 「説明が」で引くと `f3edb61f`（説明した方が）と
                 `3f4ef885`（説明の解釈）が落ち、「説明」だけで引くと道具の話（分かりやすさループ）まで
                 拾います。**分類は判断なので、字ではなく id で置く**（オーナーの言葉は 38件 しかない）。
    日           JST の日付。**オーナーが 1言も言わなかった日は、連を伸ばしも切りもしません**
                 —— 沈黙は「分かりやすかった」の証拠ではないからです（`voice_runs` と同じ規則）。
    連           いちばん新しくオーナーが言った日から さかのぼって、**言った日のうち**
                 分かりにくさの言葉が在った日が何日 続いているか。
    未分類        いちばん新しい分かりにくさの言葉より**後**のオーナーの言葉。
                 **毎周 ここを読むこと** —— 新しい言葉が族に入るなら `CLARITY_IDS` に足す
                 （足さないと、この連は黙って古くなります ＝ §5 教訓の形 7つ目・17つ目）。

**門: 3日**（＝ 手を打った翌日に同じ族が来た回が 3回 続いたら、その手はこの口では効いていない）。
**引かれたときの当て先は §3 の規則ではありません** —— 規則を足す手そのものが分子だからです。

**覆る条件**:
 (1) 連が切れたら（オーナーが言った日に分かりにくさの言葉が 0件）、**その日に何を変えたか**を
     JOURNAL に書くこと。切れた回が 2回 出たら、この門は「効く手が在る」を示せた ＝ 門を 5日 へ上げてよい。
 (2) `CLARITY_IDS` に足すか迷う言葉が 2件 続いたら、族の切り方が粗い
     ＝ 「読み（TTS）」「画面」「言い回し」で札を割ること（いまは 1つ の族）。
 (3) オーナーが「もう分かりやすい」と言ったら、その言葉が正本 ＝ この道具ごと畳んでよい。
 (4) この連が引かれたまま **7日** 動かなかったら、数えているのは手の効きではなく
     **オーナーが毎日 見ている**という事実のほう ＝ 分母を「日」から「本」へ移すこと。
 (5) `NOT_OWNER_IDS` に足すか迷う行が出たら、それは受け取り帳の側の欠陥
     （`source: "owner"` の欄に親やサブの申し送りが入る）＝ 受け取り帳に「誰の字か」の欄を
     足すこと（書くのは親・`docs/trigger_parent.md`）。**そのときは id の一覧を畳めます。**

**2つ目の族 —— 「読みが変」（2026-09-13 15:0x・optimizer・Opus が足した）**

**分母は「日」ではなく「本」**（`yomi_streak`・門は `YOMI_GATE_BOOKS` と
`YOMI_COMPLAINT_GATE_BOOKS`）。数えているのは 2つ の覆る条件で、**どちらも
「N本」と書いてあるのに N を数える口がありませんでした**（この族の 14例目）:

    §3 の 9        全語固定の本を **7本** 出して、オーナーの「読みが変」が 0 なら この形で正しい
    §2 の 声 (2)   (1) の書き換えを **3本** 続けて出しても指摘が続いたら、残っているのは抑揚の側
                   ＝ Chirp3-HD へ戻すかをオーナーに訊く

**読みは「その本の音」に乗るので、オーナーが黙っていた日は分子になりません**
（分かりにくさの側は日で数える ＝ **同じ受け取り帳でも、族ごとに分母が違います**）。

**覆る条件**:
 (y-1) 連が門（7本）に届いたら、§3 の 9 は「この形で正しい」＝ その回に §3 の 9 の
     覆る条件を閉じ、この分母ごと畳んでよい（**判定は `hourly`**）。
 (y-2) 指摘が来て連が切れたら、**その回に「連が何本だったか」を JOURNAL に書くこと**
     （切れた連が 2回 とも 3本 以上 なら §2 の 声 の覆る条件 (2) の側）。
 (y-3) **声を変えた回は、この連を 0 から数え直すこと** —— 声が変われば読みの機構ごと
     変わります（Chirp3-HD は `customPronunciations`・Neural2-D は仮名だけ・`studio/tts.py`）。
     **声を変えた刻を持つ台帳はいま在りません**（`data/model_choice.jsonl` は模型の話）
     ＝ 手で数え直すこと。3度目に声が動いたら、そのときこそ刻の口を作ること。
 (y-4) `YOMI_IDS` と `CLARITY_IDS` の両方に載る言葉が **3件** になったら、族の切り方が
     言葉の粒に合っていない（いま 1件 ＝ `3f4ef885`）＝ 言葉ではなく**指摘ごと**に札を割ること。
 (y-5) **2つ の門は同じ連に掛かるので、印字は 2つ とも verdict を出します**
     （2026-09-13 16:0x・optimizer・Opus。15:0x は `complaint_gate` を返り値に持ちながら
     **7本 の側の verdict しか印字していませんでした** ＝ §5 教訓の形 7つ目・17つ目）。
     **引き方が逆向きです**: §3 の 9 は「**届いた回**」に引かれ、§2 の 声 (2) は
     「**届いているときに次の指摘が来た回**」に引かれます。
     **覆る条件**: 3つ目の門が同じ連に掛かったら、`yomi_line` の tail ではなく
     **門ごとの 1行**（門・分子・引き方・判定者）を並べる形へ変えること。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox.jsonl"
LEDGER = ROOT / "data" / "studio" / "ledger.jsonl"
JST = timezone(timedelta(hours=9))

#: 門（日）。§5 の「N回目」と同じ形 —— 引かれたら JOURNAL に刻むこと。
GATE = 3

#: **分かりにくさの言葉**（受け取り帳の id → 一言）。
#: 足すときの線: **その本を見た人が「話が追えない」と言っている**もの。
#: 道具・枠・模型・読み（TTS の誤読）そのものの話は入れない（(2) の覆る条件で割る）。
CLARITY_IDS: dict[str, str] = {
    "7a024c76": "2026-08-27 まず何言ってるか分かんない（旧作り）",
    "dd918e3f": "2026-09-05 何言ってるかわかんない動画ばっか → METHOD をゼロから組み直した",
    "0bd45ff7": "2026-09-06 ナレーションも文脈が全然追えない",
    "552fadf1": "2026-09-10 事実なのか前提なのか分かるように → §3 7-b（札）",
    "52f141fa": "2026-09-10 画面を有効活用できてない・整理しながら理解するのむずい → §3 7-b（板）",
    "3f4ef885": "2026-09-11 説明の解釈が誤解されないように → §2 の直す順・§4 (2)",
    "f3edb61f": "2026-09-11 制度の仕組みは説明した方が良くない？ → §3 7-c（しくみ）",
    "b8dab27b": "2026-09-12 説明が全体を通して分かりづらい → §3 12（順）",
    "2e87f87e": "2026-09-13 説明不足があると思うな。話がつかめない",
}

#: オーナー自身が、この輪について言った言葉（分子には数えない・読む側の材料）。
LOOP_ID = "10f70f79"

#: **読み（TTS）の言葉**（受け取り帳の id → 一言）。**分母は「日」ではなく「本」**（下の `yomi_streak`）。
#: 足すときの線: **読み方（音）が変だと言っている**もの。**声そのものの話は入れない**
#: （`9d0a9422`「ナレーション前の音声の方が良かった」は §2 の「声はオーナーの言葉で決める」の側で、
#:  読みの機構（`kana_in_voice`・言い換え）とは別の問い）。
YOMI_IDS: dict[str, str] = {
    "bf127653": "2026-09-06 漢字の読み変なのいっぱいだよ。今後一個も出ないように考えて → §3 の 9（全語 `yomi` 固定）",
    "3f4ef885": "2026-09-11 まだ読みがおかしいのがあるよ。ひらがなも漢字もあった → §2 の直す順 (1)(2)(3)",
}

#: 読みの門（**本**）。§3 の 9 の覆る条件「全語固定の本を **7本** 出して、
#: オーナーの『読みが変』が 0 なら、この形で正しい」。
YOMI_GATE_BOOKS = 7

#: 指摘が続く側の門（**本**）。§2 の 声 の覆る条件 (2)
#: 「(1) の書き換えを **3本** 続けて出してもオーナーの指摘が続いたら、残っているのは抑揚の側」。
YOMI_COMPLAINT_GATE_BOOKS = 3

#: **(1)（語そのものを書き換える）を決めた刻**（METHOD §2 の直す順・2026-09-11 13:0x・hourly・Opus）。
#: §2 の 声 の覆る条件 (2) の分子は「**書き換えて出した本**」なので、この刻より前の本は数えません
#: （`yomi_line` がその字を毎周 印字しているのに、**数える側はその絞りを持っていませんでした**）。
#: **覆る条件**: §2 の (1)(2)(3) の順が書き直されたら、この刻も一緒に直すこと（刻は METHOD §2 の本文）。
REWRITE_DECIDED_AT = datetime(2026, 9, 11, 13, 0, tzinfo=JST)

#: **オーナーの言葉だが、上の 2族 のどちらでもないもの**（id → 一言）。
#: これが在るので「まだ札の無い、より新しい言葉」は**族ごとに**正確に出せます
#: （族が 2つ になると、片方に札が在る言葉が もう片方では「札が無い」に見えるため）。
OTHER_IDS: dict[str, str] = {
    "33699957": "2026-08-19 収益の予測を毎回すること",
    "7a94167a": "2026-08-21 使用状況の画面",
    "cdac898a": "2026-08-21 届かないと言うなら軌跡を予測しろ",
    "cbdba976": "2026-08-28 前より再生数が少ないのはなんで？",
    "1e2faa92": "2026-09-05 手法をまっさらにして作り直せ",
    "089a3d1e": "2026-09-06 お前が判断すんじゃなくて、サブが判断する",
    "5559b2d2": "2026-09-06 今後全てで考えた方がいいと思うならそうしろ",
    "ef27930d": "2026-09-07 他モデル活用しないの？",
    "9d0a9422": "2026-09-07 ナレーション前の音声の方が良かった（**声そのもの** ＝ 読みの族ではない・§2）",
    "811902bc": "2026-09-08 AIですかと聞かれたら何で答えるの？",
    "62e77b34": "2026-09-08 何で答えると思う？",
    "dd9aa62f": "2026-09-09 Fable のみの半分が全てに加算される",
    "a936dc8c": "2026-09-09 全てのモデル100％いきそう？",
    "f55cd784": "2026-09-09 どうすんの？",
    "6c38a70e": "2026-09-09 その視点ないんだったら視点だけ与えなよ",
    "10f70f79": "2026-09-11 今回だけ教えてもまたおんなじことになるだろ（この輪について）",
    "c2d075b2": "2026-09-11 リセットされたら fable にするよな？",
    "06fec2ad": "2026-09-11 ずっと使えるように調整すんの？",
}

#: **別の所で札が付いたオーナーの言葉**（id → 一言 ＋ **札の在り処**）。
#: `OTHER_IDS`（どちらの族でもない ＝ 黙って落とす）と違い、**ここは毎周 1行 で在り処を言います**
#: —— 次の回が「この言葉はどこで決まったのか」を repo から探し直さなくてよいように。
#:
#: **なぜ足したか**（2026-09-14 03:4x JST・optimizer・Opus。03:2x の `hourly` の申し送り）:
#: `6a67e8e7`・`95e92b1e`（達成期限3ヶ月）は `docs/GOAL.md` の達成期限の節・`trend.REV_DEADLINE`・
#: 09/13 21:0x の判定 という札を持っていますが、`CLARITY_IDS` にも `YOMI_IDS` にも入らないので、
#: **清潔さの族と読みの族の 両方**が「まだ札の無い言葉」として毎周 並べていました
#: ＝ **毎周 2体 が同じ 2件 を読み直して、毎周 同じ「どちらの族でもない」に着く**
#: （§5 教訓の形 7つ目 —— 註と印字が食い違えば、読まれるのは印字のほう）。
#: **`OTHER_IDS` へ入れるだけでは足りません** —— それは黙って落とすだけで、
#: **在り処がどこにも印字されないまま**になります（§7「いまの数」がその代わりを持っていた）。
#:
#: **覆る条件**:
#:  (f-1) ここに入れた言葉が **2件 続けて**「実は族の言葉だった」と分かったら、
#:        分けるのは一覧ではなく**族の切り方**（上の 覆る条件 (2)）。
#:  (f-2) この一覧が **5件** を越えたら、印字は 1行（件数と在り処の名）だけにして、
#:        中身は在り処の側に読みに行かせること（毎周 読む字を増やさない）。
#:  (f-3) 在り処に挙げた節が消えたら、その id は `OTHER_IDS` へ落とすこと
#:        （**在り処の無い `FILED_IDS` は `OTHER_IDS` と同じ物**）。
FILED_IDS: dict[str, str] = {
    "6a67e8e7": ("2026-09-13 YouTube月収20万の達成期限3ヶ月にして"
                 " → 札: `docs/GOAL.md` の達成期限の節（09/13 21:0x・`hourly` の判定）"
                 "・`trend.REV_DEADLINE` / `rev_deadline`"),
    "95e92b1e": ("2026-09-13 達成期限3ヶ月だよ。それが目標"
                 " → 札: 同上（`6a67e8e7` と同じ決めの言い直し）"),
    "313b446d": ("2026-09-14 とっくの前にはずしていいと言った"
                 " → 札: `docs/GOAL.md` の固定その2 の節（06:1x の塊）と 達成期限の節 (4-a)"
                 "（09/14 06:2x・optimizer が読んだ）・台帳 `data/owner_ask.jsonl` の `fix2_lift`"
                 " ＝ **固定その2 の 1（1日1本）と 2（作り置きなし）は床ではなく既定値へ**"
                 "・**形をどう変えるかの判定は `hourly` とオーナー**"),
    "600115fe": ("2026-09-14 クッキーストラテジャーってチャンネルも使える。自由にしていいよ"
                 " → 札: 同上（達成期限の節 (4-a)）・台帳の `second_channel`"
                 " ＝ **許しは出た・口はまだ開いていない**（`channels.list(mine=true)` の items 1件）"
                 "・残りは `second_channel_token`（`YT_REFRESH_TOKEN` の取り直し）"),
    "3c564336": ("2026-09-14 クラウド環境にあるっつってんだろ"
                 " → 札: `docs/GOAL.md` の達成期限の節 (4-e)（09/14 07:2x・`hourly` の判定）"
                 "・台帳 `data/owner_ask.jsonl` の `second_channel_token` ＝ **返事ずみ**"
                 " ＝ **手渡しはしない・口は環境変数の側**（`docs/KICKOFF.md` 1）"),
    "0caa916e": ("2026-09-14 一括つってんだろ"
                 " → 札: 同上（`3c564336` と同じ決めの言い直し ＝ **2度 言われました**）"),
    "b8328f62": ("2026-09-14 目標以外の制約はない。自由にしろ"
                 " → 札: `docs/GOAL.md` の達成期限の節 (4-f)（09/14 09:4x・`hourly` の判定）"
                 " ＝ 09/04「目標以外全部外して良いよ」の言い直し ＋ 「口はサブの手の外」を制約として置かないこと"),
    "d5c7b271": ("2026-09-14 あとできないというな。そう思うならやり方が間違ってることを疑えよ"
                 " → 札: 同上 (4-f)。**間違っていたのは読み**: 07:4x が「一括」を副詞（まとめて）と読んだが、"
                 "**「一括」は環境の名**（`list_environments` に「一括」が在る・JOURNAL 08/23 にも同じ名）"
                 " ＝ 手渡しの話ではなく「その環境で立てろ」"),
    "efc96bd9": ("2026-09-14 上書き後のはクッキーストラテジャーというチャンネルの方のトークン"
                 " → 札: 同上 (4-f)・`cli.channel_switch_line`（口が変わったら `status` が名指しする）"
                 " ＝ **環境の値は上書きずみ・いま走っている親（05:25 起動）には届かない・次の起動から届く**"),
}

#: **受け取り帳で `source: "owner"` と記録されているが、オーナーの言葉ではない行**（id → 一言）。
#: 親やサブが「次の回へ」と積んだ申し送りが、同じ欄に入っています（受け取り帳を書くのは親）。
#: **これを落とさないと、分母（オーナーが言った日）が申し送りの日ぶん膨らみ、
#: 申し送りだけの日が族の連を偽で切ります**（2026-09-13 15:0x に踏んだ・derivation は JOURNAL 15:0x）。
NOT_OWNER_IDS: dict[str, str] = {
    "8b9cf423": "2026-08-17 運ばれてきた依頼（前の回の申し送り）",
    "0137737a": "2026-08-17 親からの申し送り",
    "7ec843a0": "2026-08-23 新しい親から・いま動かしているもの",
    "f0997bf6": "2026-08-23 飛行中の測定・次の親が拾うこと",
    "c23c90a9": "2026-08-24 親からの申し送り",
    "e95ec56c": "2026-08-26 この回から・日枠が戻る回へ",
    "69440f12": "2026-08-31 この回から・日枠が戻る回へ",
    "4a5bcdff": "2026-08-31 サブから次の回へ",
    "b7235460": "2026-08-31 日枠が戻ったら、上から順に",
    "d51815bb": "2026-08-31 次の回へ・API 0単位で確かめられます",
}


def owner_rows(path: Path | None = None) -> list[dict]:
    """受け取り帳のうち **オーナーの言葉**の行（古い順）。

    `source == "owner"` から、さらに `NOT_OWNER_IDS`（親やサブの申し送り）を落とします
    —— **同じ欄に両方が入っている**ので、落とさないと「オーナーが言った日」が申し送りの日ぶん
    膨らみます（実測 2026-09-13: 18日 → **13日**）。
    """
    p = path or INBOX
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("source") != "owner" or not r.get("at"):
            continue
        if r.get("id") in NOT_OWNER_IDS:
            continue
        out.append(r)
    out.sort(key=lambda r: r["at"])
    return out


def books(path: Path | None = None, now: datetime | None = None) -> list[tuple[datetime, str]]:
    """**公開ずみのこちらの本**（公開の刻, 台本の id）を古い順に。API 0単位・台帳の字だけ。

    出どころは `data/studio/ledger.jsonl` の `scheduled`（`cli.cmd_schedule` が置く）。
    **2つの形が在ります** —— 古い行は `at` が公開の刻そのもの・新しい行は `publish_at`
    （`at` は「いつ予約したか」）。**差し替えの行は同じ台本 id で2回 出る**ので、id で畳みます。
    """
    p = path or LEDGER
    now = now or datetime.now(JST)
    if not p.exists():
        return []
    when: dict[str, datetime] = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("event") != "scheduled" or not r.get("id"):
            continue
        raw = r.get("publish_at") or r.get("at")
        if not raw:
            continue
        try:
            t = datetime.fromisoformat(raw).astimezone(JST)
        except ValueError:
            continue
        when[r["id"]] = t
    return sorted(((t, i) for i, t in when.items() if t <= now), key=lambda x: x[0])


def yomi_streak(rows: list[dict], pub: list[tuple[datetime, str]] | None = None,
                now: datetime | None = None) -> dict:
    """読みの連（**単位は「本」**）。いちばん新しい「読みが変」より後に公開された本の数。

    **なぜ本か**（オーナーの「分かりにくい」の連は日で数えます）: 読みは**その本の音**に乗るので、
    オーナーが黙っていた日を数えても分子になりません。§3 の 9 も §2 の 声 の覆る条件 (2) も、
    数えているのは**本**です（「7本 出して 0 なら」「3本 続けて出しても」）。

    **同じ連に門が 2つ 掛かります**（2026-09-13 16:0x・optimizer・Opus が 2つ目を数え始めた）:

        §3 の 9       門 **7本**・「0 なら この形で正しい」 ＝ **連が門に届いた回**に引かれる
        §2 の 声 (2)  門 **3本**・「3本 続けて出しても指摘が続いたら」 ＝ **門に届いているときに
                      次の指摘が来た回**に引かれる（届いた回そのものでは引かれません）

    15:0x はこの 2つ を 1つ の `run` で数え、**印字は 7本 の側の verdict しか出していません**でした
    （`complaint_gate` は返り値に在るのに、`yomi_line` は字で触れるだけ）＝ 読む側は
    「まだ引けません（門 7本）」だけを見ます（§5 教訓の形 7つ目 ＝ 註と印字が食い違えば読まれるのは印字）。
    **2つ目の分子は 1つ目より速く、いま 2/3本 です。**

    **2つ目の分母は「書き換えて出した本」**（`REWRITE_DECIDED_AT` より後に公開した本だけ）——
    §2 の (1) を決める前の本は「書き換えて出した本」ではありません。`yomi_line` はその字を
    15:0x から印字していましたが、**数える側は絞りを持っていませんでした**。

    返り: `{"words", "last", "run", "gate", "drawn", "prev_runs", "complaint_gate",
    "complaint_run", "complaint_ready", "broken_after", "books", "after"}`。
    `prev_runs` は**指摘と指摘のあいだに出た本の数**（＝ 前の連が何本で切れたか）。
    `broken_after` は `REWRITE_DECIDED_AT` より後に**切れた**連だけ（覆る条件 (y-2) の分子）。
    """
    pub = books(now=now) if pub is None else pub
    words = [r for r in rows if r.get("id") in YOMI_IDS]
    if not words:
        run = len(pub)
        after_all = [b for b in pub if b[0] > REWRITE_DECIDED_AT]
        return {"words": [], "last": None, "run": run, "gate": YOMI_GATE_BOOKS,
                "drawn": run >= YOMI_GATE_BOOKS, "prev_runs": [],
                "complaint_gate": YOMI_COMPLAINT_GATE_BOOKS,
                "complaint_run": len(after_all),
                "complaint_ready": len(after_all) >= YOMI_COMPLAINT_GATE_BOOKS,
                "broken_after": [], "books": pub, "after": []}
    marks = [datetime.fromisoformat(r["at"]).astimezone(JST) for r in words]
    after = [b for b in pub if b[0] > marks[-1]]
    prev = [{"from": words[i]["id"], "to": words[i + 1]["id"], "at": marks[i + 1],
             "books": len([b for b in pub if marks[i] < b[0] <= marks[i + 1]])}
            for i in range(len(words) - 1)]
    # **2つ目の門の分子**: いちばん新しい指摘より後 **かつ** (1) を決めた刻より後 の本だけ。
    c_after = [b for b in after if b[0] > REWRITE_DECIDED_AT]
    # **切れた連**（(y-2) の分子）も同じ絞りで —— 連を切った指摘が決めより後のものだけ。
    broken = [p for p in prev if p["at"] > REWRITE_DECIDED_AT]
    return {"words": words, "last": words[-1], "run": len(after), "gate": YOMI_GATE_BOOKS,
            "drawn": len(after) >= YOMI_GATE_BOOKS, "prev_runs": prev,
            "complaint_gate": YOMI_COMPLAINT_GATE_BOOKS,
            "complaint_run": len(c_after),
            "complaint_ready": len(c_after) >= YOMI_COMPLAINT_GATE_BOOKS,
            "broken_after": broken, "books": pub, "after": after}


def _day(row: dict) -> str:
    return datetime.fromisoformat(row["at"]).astimezone(JST).strftime("%Y-%m-%d")


def days(rows: list[dict]) -> list[tuple[str, list[dict], list[dict]]]:
    """(日, その日のオーナーの言葉, そのうち分かりにくさの言葉) を古い順に。"""
    order: list[str] = []
    byday: dict[str, list[dict]] = {}
    for r in rows:
        d = _day(r)
        if d not in byday:
            byday[d] = []
            order.append(d)
        byday[d].append(r)
    return [(d, byday[d], [r for r in byday[d] if r.get("id") in CLARITY_IDS]) for d in order]


def streak(rows: list[dict]) -> dict:
    """連（オーナーが言った日だけを数える。沈黙の日は伸ばしも切りもしない）。"""
    ds = days(rows)
    run = 0
    for _d, _all, hits in reversed(ds):
        if not hits:
            break
        run += 1
    silent = 0
    if run:
        first = datetime.strptime(ds[-run][0], "%Y-%m-%d")
        last = datetime.strptime(ds[-1][0], "%Y-%m-%d")
        silent = (last - first).days + 1 - run
    return {
        "run": run,
        "gate": GATE,
        "drawn": run >= GATE,
        "silent_in_run": silent,
        "spoke_days": len(ds),
        "clarity_days": sum(1 for _d, _a, h in ds if h),
    }


def unclassified(rows: list[dict], ids: dict[str, str] | None = None) -> list[dict]:
    """いちばん新しいその族の言葉より後の、**どの札も付いていない**オーナーの言葉。

    札は 4つ（`CLARITY_IDS`・`YOMI_IDS`・`OTHER_IDS`・`FILED_IDS`）で、**1つの言葉に 2つ 付くことがあります**
    （`3f4ef885` は 分かりにくさ と 読み の両方）。ここで落とすのは「どこにも札が無い」ものだけ
    —— そうしないと、族が 2つ になった時点で、片方の族の言葉が もう片方で毎周 並びます。
    """
    ids = CLARITY_IDS if ids is None else ids
    known = set(CLARITY_IDS) | set(YOMI_IDS) | set(OTHER_IDS) | set(FILED_IDS)
    last = None
    for r in rows:
        if r.get("id") in ids:
            last = r["at"]
    out = [r for r in rows if r.get("id") not in known]
    return out if last is None else [r for r in out if r["at"] > last]


#: **札の無いオーナーの言葉が、まだ `hourly` の物である周の数**（門）。
#: **2 なのは、周の窓の構造そのものです**（2026-09-14 07:5x・optimizer・Opus。**この回に踏んだ**）:
#: `docs/METHOD.md` §5「オーナーの言葉が周の途中で届いたとき、どちらが取るか」の覆る条件は
#: 「`hourly` が取りこぼした周が出たら（**次の周の窓に、その言葉の commit が無い**）、`optimizer` が引き取る」
#: ですが、**その窓は周のはじめに撃つもの**で、§5 自身が「相手のその回の最初の押しは**周の 3分後**」
#: 「開始時の窓には相手のその回の押しが構造的に出ない」と書いています
#: ＝ **前の周に届いた言葉は、次の周の開始時の窓では必ず「取りこぼし」に見えます。**
#: 実測 2026-09-14: オーナーの言葉は 06:56／06:57（＝ 06:2x の周の最中）に届き、
#: 07:1x の周の optimizer が 07:2x の窓で「commit が無い」と読んで取り、
#: **同じ周の `hourly` が 07:4x に同じ言葉を取りました**（**7回目の二重**・
#: `data/owner_ask.jsonl` の `second_channel_env` は取り下げ・derivation は JOURNAL 07:5x）。
#: ＝ **1周 では足りません。言葉が「丸ごと 1周 を札なしで越えた」ことが要ります。**
#:
#: **数え方**: その言葉を**丸ごと 札なしで越えた周**（`laps_crossed`）が `TURF_GATE_LAPS` 以上 あって、
#: まだ札が無ければ `optimizer` が引き取ってよい。**「刻より後に記録された周の数」ではありません**
#: （2026-09-14 13:1x・optimizer・Opus に直した）—— **親は周を記録してから サブを立てる**ので
#: （`docs/trigger_parent.md` 第1節・検査 `tests/test_parent_record_before_spawn.py`）、
#: いちばん新しい周は**いま走っている周**で、その `hourly` はまだ札を付ける途中です。
#: 生の数（`laps_since`）で門を読むと、**門が 1周 早く開き**、上の 7回目の二重と同じ形
#: （同じ周の 2体 が同じ言葉を取る）が 2周 の門でも通ります。
#: 実物: 言葉 `8e695b8e`（09/14 11:30）は 12:0x の周だけを丸ごと越えており（＝ 1周）、
#: 13:0x の周の `hourly` はまだ走っていました。生の数は 2周 と言い、門を開けていました。
#:
#: **覆る条件**:
#:  (t-0) この道具を**周の外**（親が畳んだあと・サブが 0体 の刻）で撃つ回が要るようになったら、
#:        いちばん新しい周は「いま走っている周」ではないので、この -1 は 1周 の取りこぼしを足します
#:        ＝ そのときは「いま走っている周が在るか」を `data/parent_wakes.jsonl` から見て引くこと。
#:  (t-1) この門が 2周 でも二重が起きたら、足りないのは周の数ではなく**取り分の切り方**
#:        （§5 の「オーナーの言葉が…どちらが取るか」の表）＝ そのとき表のほうを直すこと。
#:  (t-2) `hourly` が 2周 越えても取らなかった言葉が **2件** 出たら、門は 1周 へ下げてよい
#:        （＝ 取りこぼしのほうが二重より高く付いている）。
#:  (t-3) 親が 1周に 1体 しか立てない形になったら、`scripts/owner_ask.py` の「2体 で 1周」と
#:        一緒にここも直すこと。
TURF_GATE_LAPS = 2

#: 周の台帳（`scripts/owner_ask.py` と同じ物を、同じ数え方で読む）。
ROUNDS = ROOT / "data" / "rounds.jsonl"


def round_rows(path: Path | None = None) -> list[dict]:
    """周の台帳を素で読む（**`owner_rows` を使わないこと** —— あちらは `source == "owner"` で
    絞るので、周の台帳を渡すと **0件** を返します。2026-09-14 07:5x にその形で1度 踏んだ）。"""
    p = path or ROUNDS
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def laps_since(at: str, rounds: list[dict] | None = None) -> int:
    """その刻より後に記録された周の数（重複なし・**役では数えない** ＝ 2体 で 1周）。"""
    if rounds is None:
        rounds = round_rows()
    t = datetime.fromisoformat(at).astimezone(JST)
    keys = {r.get("round") or r.get("at") for r in rounds if r.get("round") or r.get("at")}
    return sum(1 for k in keys
               if datetime.fromisoformat(k).astimezone(JST) > t)


def laps_crossed(at: str, rounds: list[dict] | None = None) -> int:
    """その言葉が**丸ごと 札なしで越えた周**の数（`TURF_GATE_LAPS` の註が言う数え方）。

    `laps_since` から**いま走っている周を 1つ 引いたもの**です —— 親は周を記録してから
    サブを立てるので、いちばん新しい周のサブはまだ走っています（その周の `hourly` を
    「取りこぼした」と数えないこと）。**門を読むのはこちら。**
    """
    return max(0, laps_since(at, rounds) - 1)


def turf_line(at: str, rounds: list[dict] | None = None) -> str:
    """その言葉を**いまどちらの役が取ってよいか**を 1行 で言う（`TURF_GATE_LAPS` の註）。"""
    n = laps_crossed(at, rounds)
    raw = laps_since(at, rounds)
    tail = f"（記録された周 {raw} のうち、いま走っている周 1つ は数えません）"
    if n >= TURF_GATE_LAPS:
        return (f"**{n}周 丸ごと 札なし（門 {TURF_GATE_LAPS}周）＝ `optimizer` が引き取ってよい** —— "
                f"そのときは**申し送りに「取った」と書いてから**触ること（METHOD §5）{tail}")
    return (f"**{n}周 丸ごと 札なし（門 {TURF_GATE_LAPS}周）＝ まだ `hourly` の持ち場です** —— "
            "**開始時の窓に相手の押しが無いのは、取りこぼしの印ではありません**"
            f"（相手の押しは周の 3分後・§5）{tail}")


def run(days_back: int = 21, path: Path | None = None, ledger: Path | None = None) -> dict:
    rows = owner_rows(path)
    cut = (datetime.now(JST) - timedelta(days=days_back)).isoformat()
    recent = [r for r in rows if r["at"] >= cut]
    res: dict = {"rows": rows, "recent": recent, "unclassified": unclassified(rows),
                 "yomi": yomi_streak(rows, books(ledger)),
                 "yomi_unclassified": unclassified(rows, YOMI_IDS),
                 "filed": [r for r in rows if r.get("id") in FILED_IDS],
                 **streak(rows)}
    res["quiet_h"] = (
        (datetime.now(JST) - datetime.fromisoformat(rows[-1]["at"]).astimezone(JST)).total_seconds() / 3600
        if rows else None
    )
    return res


def line(res: dict | None = None) -> str:
    res = run() if res is None else res
    head = (
        "オーナーの「分かりにくい」の連: "
        f"**{res['run']}日**（門 {res['gate']}日・**オーナーが言った日だけを数える**）"
        f" ＝ **{'引かれました' if res['drawn'] else 'まだ引けません'}**"
        f"（言った日 {res['spoke_days']}日 のうち この族が在った日 {res['clarity_days']}日・"
        f"連の中の沈黙 {res['silent_in_run']}日）"
    )
    body = [
        f"  {CLARITY_IDS[r['id']]}  `{r['id']}`"
        for r in res["rows"] if r.get("id") in CLARITY_IDS
    ]
    tail = []
    if res["unclassified"]:
        tail.append("  **まだ札の無い、より新しいオーナーの言葉**（族に入るなら `CLARITY_IDS` に足すこと）:")
        for r in res["unclassified"]:
            tail.append(f"    {r['at'][:16]} `{r.get('id')}` {r.get('text','')[:60]}")
            tail.append("      " + turf_line(r.get("at", "")))
    else:
        tail.append("  まだ札の無い、より新しいオーナーの言葉: **0件**")
    if res.get("filed"):
        tail.append(
            f"  **別の所で札が付いた言葉: {len(res['filed'])}件**"
            "（どちらの族の分子でもありません ＝ **毎周 読み直さないこと**・`FILED_IDS`）:"
        )
        tail += [f"    `{r.get('id')}` {FILED_IDS[r['id']]}" for r in res["filed"]]
    if res["quiet_h"] is not None:
        tail.append(f"  いちばん新しいオーナーの言葉から **{res['quiet_h']:.1f}時間**"
                    "（**沈黙は「分かりやすかった」ではありません** ＝ 連は動きません）")
    tail.append(
        "  **この道具は判定しません** —— 数を並べるまでです。**「形を変えるか」の判定は "
        "`hourly` とオーナー**（METHOD §5・§7）。**引かれたときの当て先は §3 の規則ではありません** "
        "—— 規則を足す手そのものが分子です（この道具の註）"
    )
    return "\n".join([head, *body, *tail, "", yomi_line(res)])


def yomi_line(res: dict | None = None) -> str:
    """読みの連（**単位は「本」**）を並べる。§3 の 9 と §2 の 声 の覆る条件 (2) の分母。"""
    res = run() if res is None else res
    y = res["yomi"]
    head = (
        "オーナーの「読みが変」の連: "
        f"**{y['run']}本**（門 {y['gate']}本・**単位は「本」＝ 公開ずみのこちらの本**）"
        f" ＝ **{'引かれました' if y['drawn'] else 'まだ引けません'}**"
        "（§3 の 9 の覆る条件「全語固定の本を 7本 出して、読みが変が 0 なら この形で正しい」）"
    )
    body = [f"  {YOMI_IDS[r['id']]}  `{r['id']}`" for r in y["words"]]
    if y["after"]:
        body.append("  いちばん新しい指摘のあとに公開した本: " + "・".join(i for _t, i in y["after"]))
    else:
        body.append("  いちばん新しい指摘のあとに公開した本: **0本**")
    for p in y["prev_runs"]:
        body.append(f"  前の連（指摘と指摘のあいだに出た本）: `{p['from']}` → `{p['to']}` ＝ **{p['books']}本**")
    c_run, c_gate = y["complaint_run"], y["complaint_gate"]
    if y["complaint_ready"]:
        c_verdict = (f"**門に届いています（{c_run}/{c_gate}本）** ＝ **次の「読みが変」が来た回に引かれます**"
                     "（そのときは Chirp3-HD へ戻すかをオーナーに訊く番・**判定は `hourly` とオーナー**）")
    else:
        c_verdict = (f"**まだ届いていません（{c_run}/{c_gate}本・あと {c_gate - c_run}本）** ＝ "
                     "いま指摘が来ても引かれません（連が 0 に戻るだけ）")
    tail = [
        f"  **§2 の 声 の覆る条件 (2)** —— 書き換えて出した本 **{c_run}本**（門 {c_gate}本）: {c_verdict}。"
        "**引かれるのは門に届いた回ではなく、届いているときに次の指摘が来た回です**（§3 の 9 と逆）",
        f"  **同じ連に門が 2つ 掛かっています**（上の verdict は §3 の 9 の 門 {y['gate']}本 の側）——"
        f"**2つ目のほうが速い**（いま {c_run}/{c_gate}本 対 {y['run']}/{y['gate']}本）。"
        "**片方だけを読んで「まだ引けません」と書かないこと**（2026-09-13 16:0x に足した）",
        f"  切れた連（(y-2) の分子・決めより後だけ）: **{len(y['broken_after'])}件**"
        + ("（2件 とも 3本 以上 なら §2 の 声 の覆る条件 (2) の側）" if len(y["broken_after"]) < 2
           else "・" + "・".join(f"`{p['to']}` ＝ {p['books']}本" for p in y["broken_after"])),
        "  **09/11 より前の連を、その分子に数えないこと** —— §2 の (1)(2)(3)（語そのものを書き換える）は "
        "**2026-09-11 13:0x の決め**で、それより前の本は「書き換えて出した本」ではありません（判定は `hourly`）"
        "。**この絞りは字ではなく `REWRITE_DECIDED_AT` が持っています**",
    ]
    if res["yomi_unclassified"]:
        tail.append("  **まだ札の無い、より新しいオーナーの言葉**（読みの族なら `YOMI_IDS` に足すこと）:")
        tail += [f"    {r['at'][:16]} `{r.get('id')}` {r.get('text','')[:60]}"
                 for r in res["yomi_unclassified"]]
    else:
        tail.append("  まだ札の無い、より新しいオーナーの言葉: **0件**")
    tail.append(
        "  **この道具は判定しません** —— 数を並べるまでです（**声そのものを変えるのは "
        "オーナーの言葉があったときだけ**・METHOD §2）"
    )
    return "\n".join([head, *body, *tail])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=21)
    a = ap.parse_args()
    print(line(run(a.days)))
