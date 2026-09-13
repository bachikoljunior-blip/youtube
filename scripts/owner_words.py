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

    返り: `{"words", "last", "run", "gate", "drawn", "prev_runs", "complaint_gate", "books"}`。
    `prev_runs` は**指摘と指摘のあいだに出た本の数**（＝ 前の連が何本で切れたか）。
    """
    pub = books(now=now) if pub is None else pub
    words = [r for r in rows if r.get("id") in YOMI_IDS]
    if not words:
        run = len(pub)
        return {"words": [], "last": None, "run": run, "gate": YOMI_GATE_BOOKS,
                "drawn": run >= YOMI_GATE_BOOKS, "prev_runs": [],
                "complaint_gate": YOMI_COMPLAINT_GATE_BOOKS, "books": pub, "after": []}
    marks = [datetime.fromisoformat(r["at"]).astimezone(JST) for r in words]
    after = [b for b in pub if b[0] > marks[-1]]
    prev = [{"from": words[i]["id"], "to": words[i + 1]["id"],
             "books": len([b for b in pub if marks[i] < b[0] <= marks[i + 1]])}
            for i in range(len(words) - 1)]
    return {"words": words, "last": words[-1], "run": len(after), "gate": YOMI_GATE_BOOKS,
            "drawn": len(after) >= YOMI_GATE_BOOKS, "prev_runs": prev,
            "complaint_gate": YOMI_COMPLAINT_GATE_BOOKS, "books": pub, "after": after}


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

    札は 3つ（`CLARITY_IDS`・`YOMI_IDS`・`OTHER_IDS`）で、**1つの言葉に 2つ 付くことがあります**
    （`3f4ef885` は 分かりにくさ と 読み の両方）。ここで落とすのは「どこにも札が無い」ものだけ
    —— そうしないと、族が 2つ になった時点で、片方の族の言葉が もう片方で毎周 並びます。
    """
    ids = CLARITY_IDS if ids is None else ids
    known = set(CLARITY_IDS) | set(YOMI_IDS) | set(OTHER_IDS)
    last = None
    for r in rows:
        if r.get("id") in ids:
            last = r["at"]
    out = [r for r in rows if r.get("id") not in known]
    return out if last is None else [r for r in out if r["at"] > last]


def run(days_back: int = 21, path: Path | None = None, ledger: Path | None = None) -> dict:
    rows = owner_rows(path)
    cut = (datetime.now(JST) - timedelta(days=days_back)).isoformat()
    recent = [r for r in rows if r["at"] >= cut]
    res: dict = {"rows": rows, "recent": recent, "unclassified": unclassified(rows),
                 "yomi": yomi_streak(rows, books(ledger)),
                 "yomi_unclassified": unclassified(rows, YOMI_IDS),
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
        tail += [f"    {r['at'][:16]} `{r.get('id')}` {r.get('text','')[:60]}" for r in res["unclassified"]]
    else:
        tail.append("  まだ札の無い、より新しいオーナーの言葉: **0件**")
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
    tail = [
        f"  **§2 の 声 の覆る条件 (2)（{y['complaint_gate']}本 続けて出しても指摘が続いたら、"
        "残っているのは抑揚の側 ＝ Chirp3-HD へ戻すかをオーナーに訊く）は、"
        "この連が門に届いているときに次の指摘が来た回です**",
        "  **09/11 より前の連を、その分子に数えないこと** —— §2 の (1)(2)(3)（語そのものを書き換える）は "
        "**2026-09-11 13:0x の決め**で、それより前の本は「書き換えて出した本」ではありません（判定は `hourly`）",
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
