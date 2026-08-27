#!/usr/bin/env python3
"""**この輪が目標から外れていないかを、毎周ひとつの数で出す。**

## なぜ要るのか（2026-08-24。オーナー指摘「なんで実験そんな少ないの？」）

手で数えたら、こうでした:

    8/18以降の ship 240件   fix 115 ／ means 44 ／ upload 26 ／ **verdict 14**
    closes を宣言              26件
    moves を宣言 82件 …… うち **0以外は 17件**

**240回のうち223回が「この回で到達日は動かない」と自分で言いながら通っていました。**

そして `eta.py` は毎回こう印字しています ——
**「作る・出す・直すは、軌跡の入力に入りません。軌跡の腕が動くのは、
`config/hypotheses.yaml` の前提を1件閉じたときだけ」。**

**機械は「何が目標を動かすか」を既に知っている。門がそれを読んでいなかった。**
`stop_check.sh` は「1件出せば通す」で、`fix` はその回のうちに必ず完結するので
**いちばん安い。** 実験は16本作って2週間待たないと1件も閉じません。
**同じ「1件」なら `fix` を選ぶのが合理的で、実際そうなっていました。**
サボりではなく、**合格の定義が目標とつながっていなかった**だけです。

## この道具がやること

**比を印字するだけです。** 判断はしません ——
**印字されていない数字は、無い数字と同じ**だからです（このリポジトリは
`retention.py` で同じ穴を踏んでいる。10日間ずっと正しく印字していたのに、
その道具を走らせた回にしか届かなかった）。

`--gate` を付けると、**厳しい1条件のときだけ** exit 2 を返します:

    期限の来た前提がある、**かつ** 直近 STALE_ROUNDS 回に verdict が1件も無い

**`fix` を禁じてはいけません。** 壊れた計器で実験しても答えは出ないので、
直すこと自体は正しい。**上の条件は「直すのはいいが、期限の来た問いを
置き去りにしたまま直し続けるのはだめ」**という形にしてあります。

**覆る条件**: 実験の律速が動機ではなく**供給**（1つのA/Bに16本要るのに
日に4本しか作れない）だと分かったら、この門は効きません。そのときは
ここではなく `topic_forge` 側 —— **「節を書く」を実験に紐づいた成果に
格上げすること。** 2026-08-28 の `day_cap` 判定が、その切り分けになります。
"""
from __future__ import annotations

import argparse
import functools
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import levers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs.jsonl"
HYPS = ROOT / "config" / "hypotheses.yaml"
#: 役ごとの周の印（`scripts/next_round.py` が書く）。**θ の応答時間を出すのに使います。**
ROUNDS = ROOT / "data" / "rounds.jsonl"

JST = timezone(timedelta(hours=9))


def today_jst() -> str:
    """**基準日は JST（2026-08-26 に直した）。**

    `config/hypotheses.yaml` の `deadline` も、予約の日付も、全部 JST です。
    ここは `datetime.now().date()` ＝ **コンテナの TZ（UTC）**を読んでいました。
    9時間ずれるので、**JST の 00:00〜09:00 は「昨日」として判定します** ——
    つまり**その日に期限が来た前提が、来ていないことにされる**時間帯が毎日9時間。
    定期実行は2時間ごとなので、**1日のうち4〜5周がそこに落ちます。**

    実測（2026-08-26 02:0x JST）: 期限 08-26 の前提が1件 来ているのに、
    この門は「**期限の来た前提: なし**」と印字しました。
    **門が期限を見落とす時間帯があるなら、期限を前へ倒しても効きません。**

    同じ穴は `scripts/eta.py` と `scripts/status.py` が**それぞれ自分の中で
    註つきで直しています**（「この器は UTC なので `date.today()` を使うと…」）。
    **知っていて、門にだけ当てていなかった**形です。
    """
    return datetime.now(JST).date().isoformat()


WINDOW_DAYS = 7
STALE_ROUNDS = 20
KINDS = ("upload", "means", "verdict", "fix")

# **この先 SUPPLY_HORIZON 日に期日が来る、開いている前提の数**を在庫と呼びます。
# 期限切れ（期日が過ぎて未判定）も**いま閉じられる**ので在庫に数えます。
SUPPLY_HORIZON = 7


def _kind_of(what: str) -> str:
    """ship の1行から種別を読む。**先頭の語だけを見ます。**

    `--ship "fix: ..."` の形が慣習で、`run_marker.py` は種別を別欄に
    持っていません。**欄を足すのが本筋ですが、既存の240件を読めなくなる**ので、
    ここは既にある書き方から読みます。
    """
    head = (what or "").strip().lower()
    for k in KINDS:
        if head.startswith(k):
            return k
    return "その他"


def _kind_of_rec(rec: dict) -> str:
    """ship の1行の種別。**書く側が残した欄が先。無ければ頭の語。**

    ## なぜ欄を先にするか（2026-08-26・最適化の回）

    すぐ上の `_kind_of()` は `what` の**先頭の語だけ**を見ます。その docstring は
    「**欄を足すのが本筋ですが、既存の240件を読めなくなる**ので」と書いて、
    頭の語のほうを選んでいました。**その理由は当たっていません** ——
    欄を足しても、欄の無い古い行は頭の語で読めばよいだけです（この関数がそれです）。

    **選ばなかった代償**（2026-08-26 18:5x の実測）: **ship 381件 のうち 155件（41%）が
    「その他」**。中身は「その他」ではありません ——
    「長尺1本を 09/07 20:00 JST に予約（VG6EYTKXl1M）」（＝ `upload`）、
    「M9（配信の上限は…）を実データで判定」（＝ `verdict`）が同じ袋に入っています。

    **そしてこの数は門に乗っています** ——
    `drifting = bool(od_now) and verdicts_tail == 0`。
    **4割こぼす目盛りの上で、漂流かどうかを決めていました。**

    `scripts/run_marker.py` が `ship_kind` を書くようにしたので、
    **これ以降の行は正しく数えます。** 古い行は頭の語のままです
    （＝過去の「その他 41%」は、この関数では減りません。**それが正しい**）。

    ## 覆る条件

    `data/runs.jsonl` の「その他」が 5% を下回ったら、欄は要りません。
    そのときは `_kind_of()` だけに戻すこと。
    """
    k = rec.get("ship_kind")
    if isinstance(k, str) and (k in KINDS or k == "その他"):
        return k
    return _kind_of(rec.get("what", ""))


def load_runs(since: str | None = None) -> list[dict]:
    if not RUNS.exists():
        return []
    out = []
    for ln in RUNS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("kind") != "ship":
            continue
        if since and str(r.get("at", "")) < since:
            continue
        out.append(r)
    return out


def overdue(today: str) -> list[dict]:
    """期限が来ていて、まだ閉じていない前提。"""
    try:
        import yaml
    except ImportError:
        return []
    if not HYPS.exists():
        return []
    try:
        d = yaml.safe_load(HYPS.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = d if isinstance(d, list) else (d.get("hypotheses") or next(iter(d.values()), []))
    out = []
    for h in rows or []:
        if not isinstance(h, dict):
            continue
        # **鍵があるかどうかで見ます。値の真偽で見ないこと。**
        # `verdict: false` は「前提が外れた」＝**閉じている**という意味で、
        # Python の偽値と衝突します。2026-08-24、検査がここを捕まえました
        # （`test_閉じた前提は期限切れに数えない`）。**外れた前提こそ、
        # いちばん価値のある判定**なので、これを未判定に数えると
        # 「ちゃんと判定した回」を外れ扱いにして止めることになります。
        if any(k in h for k in ("verdict", "closed_on", "outcome")):
            continue
        dl = str(h.get("deadline") or h.get("settle_by") or "")
        if dl and dl <= today:
            out.append(h)
    return out


# --- **期限が来た ≠ 判定できる**（2026-08-26 夕・最適化の回に足した）---
#
# `overdue()` は `deadline <= today` だけを見ます。**判定に要るデータが
# 揃っているかは、一度も見ていませんでした。** そのせいで、この日
# **2つの道具が同じ前提について正反対のことを言っていました**:
#
#     scripts/deadline_check.py  「[..] まだ数えはじめたところです。
#                                  **この回は何もしないのが正解**です
#                                  （畳まないこと・条件を緩めないこと）」
#     scripts/drift.py --gate    exit 2 → `stop_check.sh` が
#                                「**この回は verdict を出すこと。**
#                                  実データで判定して `verdict:` を書く」
#                                 （3回まで止める）
#
# 対象は「深い題のショート」1件。台帳自身の `falsified_if` はこう書いています ——
# **「どちらも 8本 に満たなければ判定できません。期限を延ばすこと。
# 『まだ分からない』で閉じないこと。」** 実測は **要 8／いま 7**、
# 使える日 **要 3／いま 0**。**判定できる本は1本もありません。**
#
# **門が、台帳が禁じている行為を要求していた**ということです。
# 主実行に残る道は3つしかなく、どれも損です:
#
#     (1) 嘘の verdict を書く  → 台帳が明示的に禁じている。しかも
#         `arm_speed.arm()` は `effect` の倍率を**その腕の伸び幅としてそのまま使う**ので、
#         軌跡が嘘の日付を出します（同じ事故は `config/hypotheses.yaml` の
#         「測っていない腕に、測った倍率が書き込まれます」で既に1回 起きています）
#     (2) 3回ぶんの stop を焼いて JOURNAL に言い訳を書く → 毎周 その税を払う
#     (3) `[!]` を無視する → **これがいちばん高い。**
#         前の回が 666 commits かけて「印字は読まれない、赤い門にしろ」と
#         直したばかりで、**その門が嘘をつくと、門ごと信用を失います。**
#
# **`[!]` が間違っているコストは、`[!]` が無いコストより高い。**
# 印字なら読み手が判断で逃げられますが、**門は判断を要求しない形にしてある**ので
# 逃げ道が無く、逃げ道を作ると門そのものが効かなくなります。
# **判断を門に落としたなら、門の真偽はこちらが持つこと。**
#
# **覆る条件**: `deadline_check` の `ready` が外れる（実際には判定できたのに
# `warming` を返す）なら、止めるべき回を止めなくなります。そのときは
# ここではなく `src/judgeable.py` の床を直すこと ——
# **この門を `overdue()` だけに戻さないこと。** 戻すと上の (1)〜(3) に帰ります。

#: 判定できるか分からないときに、門を鳴らす側へ倒すか（**倒します**）。
#: 計器が読めないことを理由に門が黙ると、外れに気づけません。
_LOUD_WHEN_UNKNOWN = True


def _judge_state_by_claim() -> dict[str, tuple] | None:
    """`_judge_state_cached` の入口。**台帳が差し替わったら読み直します。**

    `HYPS` は検査が `monkeypatch` で差し替えます。素の `lru_cache` だと
    **最初の1件で固まって、以後どの検査も同じ答えを見ます。**
    鍵に台帳の道と更新時刻を入れて、そこだけで畳みます。
    """
    try:
        key = (str(HYPS), HYPS.stat().st_mtime_ns if HYPS.exists() else 0)
    except Exception:                               # noqa: BLE001
        key = (str(HYPS), 0)
    return _judge_state_cached(key)


@functools.lru_cache(maxsize=8)
def _judge_state_cached(_key: tuple) -> dict[str, tuple] | None:
    """claim → (`ready` / `warming` / `unreachable` / `unchecked`, 判定できる日 or None)。

    読めなければ `None`。**呼び手はそのとき門を鳴らす側へ倒します**
    （`_LOUD_WHEN_UNKNOWN`）—— 計器が1つ読めないことは、
    「外れていない」ことの証拠ではありません。

    **`deadline_check` は毎回 予約と Analytics を当たり直すので 約3秒**、
    しかもこの道具の中で**2か所が呼びます**（門と在庫）。
    同じ回で答えは変わらないので `lru_cache` で1回に畳みます
    （`scripts/eta.py` の `_ready_by_claim` が同じ理由で同じことをしています）。
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "drift_deadline_check", ROOT / "scripts" / "deadline_check.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["drift_deadline_check"] = mod   # dataclass が __module__ を引きます
        spec.loader.exec_module(mod)                # type: ignore[union-attr]
        # **`mod.load()` ではなく、この道具が実際に読んでいる台帳を渡すこと。**
        # `load()` は `config/hypotheses.yaml` を直に読むので、検査が `HYPS` を
        # 差し替えても**本物のほうを見ます** —— 門の検査が、本物の台帳の
        # 都合で緑にも赤にもなります（＝何も主張しない検査になる）。
        rows = _hypotheses()
        if not rows:
            return None                             # 台帳が読めない → 鳴らす側へ
        vs = mod.check(rows)
        out: dict[str, object] = {}
        for v in vs:
            if v.ready is not None:
                # **`slips` と `slack` も持って上がること**（2026-08-27・最適化の回）。
                # ここが `(kind, ready)` だけを返していたので、`split_overdue()` は
                # 「`ready` が今日より後」というだけで**期限を延ばせ**と言っていました。
                # `deadline_check.py` は同じ前提について
                # 「**期限 08-27 は判定日 08-28 の帯（±1日）の中。書き換えないこと**」
                # と印字しています —— **drift がその deadline_check を根拠に挙げながら、
                # 逆のことを指示していた**（実測 2026-08-27）。
                # `Answer.slack` の註が名指ししている churn そのものです:
                # 「3回とも『期限がずれています』と言われ、3回とも期限だけを書き換えた。
                #   到達日は1日も動いていない」。
                out[v.claim] = ("ready", v.ready,
                                bool(getattr(v, "slips", True)),
                                int(getattr(v, "slack", 0) or 0))
            elif getattr(v, "unreachable", False):
                out[v.claim] = ("unreachable", None)
            elif getattr(v, "unchecked", False):
                out[v.claim] = ("unchecked", None)
            else:
                # **`todo` も持って上がること**（2026-08-27・最適化の回。`slips` と同じ穴）。
                # `warming` を一律に「待てば日が出ます」と印字していましたが、
                # **待ち方は2つ**あります —— 時計待ち（本当に待つだけ）と、
                # **データを取っていない**（＝待っても永久に出ない）。
                # 後者に「待つこと」と言うと、その前提は期限を過ぎたまま止まります。
                todo = next((a.todo for a in (getattr(v, "answers", None) or [])
                             if getattr(a, "todo", "")), "")
                # **`why` も持って上がること**（2026-08-27 14:5x。`todo` と同じ穴の3件目）。
                # `todo` の無い `warming` を一律に
                # 「まだ数えはじめたところ（伸び率が出ないので日が出せない）」と
                # 印字していましたが、**待ちには時刻の分かっているものがあります。**
                # 実測: `day_cap` の対照日は `deadline_check.py` が
                # 「**08/27 22:00 JST に出ます**（いま 14:35 JST）」と時刻つきで
                # 言っているのに、`drift.py`（＝ `status.py` に載る側）は
                # 「伸び率が出ない」とだけ言っていました。**別のことを言っています** ——
                # 読んだ回は「いつ来るか分からない待ち」と読み、その日のうちに
                # 拾える前提を翌日以降へ流します。
                why = next((a.why for a in (getattr(v, "answers", None) or [])
                            if getattr(a, "ready", None) is None
                            and getattr(a, "why", "")), "")
                # **時刻の分かっている待ちか**（`needs[].at_time_jst`）。
                # `deadline_check.py` の印字はここで2つに分かれています ——
                # 「**今日の HH:MM JST に出ます**」と「まだ数えはじめたところ」。
                when = next((str(x.get("at_time_jst")) for x in (getattr(v, "needs", None) or [])
                             if isinstance(x, dict) and x.get("at_time_jst")), "")
                out[v.claim] = ("warming", None, None, 0, todo, why, when)
        return out
    except Exception:                               # noqa: BLE001
        return None


def split_overdue(od: list[dict], today: str) -> tuple[list[dict], list[tuple[dict, str, str]]]:
    """期限の来た前提を「**いま判定できる**」と「**まだできない**」に割る。

    返り: `(判定できるもの, [(前提, 理由, その回にやること), ...])`。

    **門が読むのは前だけ**です。後ろは印字しますが止めません ——
    止めても、その回にできることが無いからです（上の長い註）。
    """
    ready_map = _judge_state_by_claim()
    if ready_map is None:
        # 計器が読めない。**全部を門に載せます**（黙るより鳴らす）。
        return (list(od), [])
    now: list[dict] = []
    blocked: list[tuple[dict, str, str]] = []
    for h in od:
        claim = str(h.get("claim") or h.get("q") or "")
        got = ready_map.get(claim)
        if got is None:
            # 台帳には在るのに `deadline_check` が返さない ＝ 突き合わせ不能。鳴らす側へ。
            now.append(h) if _LOUD_WHEN_UNKNOWN else blocked.append(
                (h, "突き合わせ不能", "—"))
            continue
        # **3つ目以降は後から足しました。** 検査が2つ組を差し込むので、
        # 長さで受けます。**無いときは「分からない」＝ 従来どおり延ばせと言う側**へ。
        kind, ready = got[0], got[1]
        slips = got[2] if len(got) > 2 else None
        slack = got[3] if len(got) > 3 else 0
        if kind == "ready":
            if str(ready) <= today:
                now.append(h)
            elif slips is False:
                # **帯の中。`deadline_check.py` は「書き換えないこと」と言っています。**
                # ここが「延ばせ」と言うと、根拠に挙げた道具と逆を指示することになり、
                # **書き換えても次の回にまた同じ行が出ます**（到達日は1日も動かない）。
                blocked.append((
                    h, f"判定できるのは {ready}（期限との差は帯 ±{slack}日 の中）",
                    "**この回は何もしないのが正解です** —— "
                    "`python scripts/deadline_check.py` が「**書き換えないこと**」と"
                    "言っています（帯の中で動かしても、届く日は1日も動きません）。待てば判定できます"))
            else:
                blocked.append((
                    h, f"判定できるのは {ready}（期限のほうが手前）",
                    "**期限を延ばすこと**（`falsified_if` は1文字も触らない）。"
                    "`python scripts/deadline_check.py` がその日を出します"))
        elif kind == "warming":
            todo = got[4] if len(got) > 4 else ""
            why = got[5] if len(got) > 5 else ""
            when = got[6] if len(got) > 6 else ""
            if todo:
                # **待っても出ない側。** 手が在るので、そのまま渡します。
                blocked.append((h, "時計は来たが、要るデータが在りません", str(todo)))
            else:
                # **時刻の分かっている待ちを、「伸び率が出ない」で塗り潰さないこと。**
                # 塗り潰すと、**その日のうちに拾える前提が翌日以降へ流れます**（上の註）。
                #
                # **同じ周に2つの回が、別々にここを直しました**（2026-08-27 14:5x）——
                # 片方は持ち上げた状態（`got[6]`）から、もう片方は台帳の `needs` から。
                # **同じことを2か所で数えるのは、この repo がいちばん多く踏んでいる形**
                # なので、1か所に畳んで**持ち上げた側を先**にしました
                # （あちらは `deadline_check` の `why` も連れてきます）。
                # 台帳の側は、状態が短い組で返ったときの控えです。
                at = when or next(
                    (str(n.get("at_time_jst")) for n in (h.get("needs") or [])
                     if isinstance(n, dict) and n.get("at_time_jst")), "")
                if at:
                    blocked.append((
                        h, str(why) or f"時計待ち（**今日の {at} JST** に出ます）",
                        f"**今日の {at} JST に出ます**（伸び率の話ではありません）。"
                        "**その時刻を過ぎた回が拾うこと** —— 畳まない・条件を緩めない"))
                else:
                    blocked.append((
                        h, "まだ数えはじめたところ（伸び率が出ないので日が出せない）",
                        "**この回は何もしないのが正解です**（畳まない・条件を緩めない）。"
                        "待てば日が出ます"))
        elif kind == "unreachable":
            now.append(h)          # 止める。ただし「verdict を出せ」ではない（下で分ける）
        else:                      # unchecked
            now.append(h)
    return now, blocked


def report(today: str, window_days: int = WINDOW_DAYS) -> tuple[str, bool]:
    """印字する本文と、「外れている」かどうかを返す。"""
    since = (date.fromisoformat(today) - timedelta(days=window_days)).isoformat()
    runs = load_runs(since)
    n = len(runs)
    kinds = Counter(_kind_of_rec(r) for r in runs)
    closes = sum(1 for r in runs if r.get("closes"))
    declared = sum(1 for r in runs if r.get("moves") is not None)
    nonzero = sum(1 for r in runs if r.get("moves"))

    # 直近 STALE_ROUNDS 回に verdict があるか（窓ではなく件数で見る）
    all_runs = load_runs()
    tail = all_runs[-STALE_ROUNDS:]
    verdicts_tail = sum(1 for r in tail if _kind_of_rec(r) == "verdict")

    od = overdue(today)
    # **期限が来た ≠ 判定できる**（上の註）。門に載せるのは前だけ。
    od_now, od_blocked = split_overdue(od, today)
    drifting = bool(od_now) and verdicts_tail == 0

    lines = [
        "=== この輪は目標に向かっているか（直近 %d日 / ship %d件）===" % (window_days, n),
    ]
    if n:
        parts = " ／ ".join(f"{k} {kinds.get(k, 0)}" for k in KINDS)
        lines.append(f"  種別: {parts} ／ その他 {kinds.get('その他', 0)}")
        lines.append(
            f"  到達日を動かすと宣言した回: **{nonzero}/{n}**"
            f"（moves を書いた回 {declared}／前提を閉じた宣言 {closes}）"
        )
    else:
        lines.append("  この窓に ship がありません。")

    lines.append(f"  直近{STALE_ROUNDS}回の verdict: **{verdicts_tail}件**")
    if od_now:
        lines.append(f"  **期限が来ていて、いま判定できる前提: {len(od_now)}件**")
        for h in od_now[:5]:
            claim = str(h.get("claim") or h.get("q") or "")[:64]
            lines.append(f"    {h.get('deadline', '?')}  {claim}")
    else:
        lines.append("  期限が来ていて、いま判定できる前提: なし")

    if od_blocked:
        # **止めません。印字だけします。**（`split_overdue` の註）
        #
        # **ただし「できることが無い」は、もう全部には掛かりません**
        # （2026-08-27・最適化の回）。`warming` のうち **時計は来たがデータが
        # 無い**側は、**取り直せばその回のうちに判定できます** ——
        # そこへ「できることが無い」と書くと、読んだ回はそのまま帰ります。
        acts = sum(1 for _, why, _ in od_blocked if "要るデータが在りません" in why)
        tail = ("（**門には載せません** —— その回にできることが無いので）"
                if not acts else
                f"（**門には載せません**。ただし **{acts}件 は、この回に手が在ります** ——"
                "『→』の行がその手です）")
        lines.append(
            f"  期限は来たが、まだ判定できない前提: {len(od_blocked)}件{tail}")
        for h, why, todo in od_blocked[:5]:
            claim = str(h.get("claim") or h.get("q") or "")[:56]
            lines.append(f"    {h.get('deadline', '?')}  {claim}")
            lines.append(f"        {why}")
            lines.append(f"        → {todo}")

    lines.append("")
    if drifting:
        lines.append(
            "  [!] **外れています。** いま判定できる前提の期限が来ているのに、"
            f"直近{STALE_ROUNDS}回で1件も判定していません。"
        )
        lines.append(
            "      `eta.py` は「作る・出す・直すは軌跡の入力に入らない。"
            "動くのは前提を1件閉じたときだけ」と印字しています。"
        )
        lines.append("      **この回は verdict を出すこと。** 出せないなら理由を JOURNAL に。")
    else:
        lines.append("  外れの条件（**いま判定できる**期限切れの前提 かつ 判定ゼロ）には当たっていません。")

    return "\n".join(lines), drifting


def rounds_per_day(today: str, days: int = WINDOW_DAYS) -> float:
    """**この輪が1日に何周しているか。** 周＝ `run_marker.py` の印を打ったセッション。

    今日は途中なので数えません（半端な日を混ぜると周速が下振れします）。
    """
    if not RUNS.exists():
        return 0.0
    t = date.fromisoformat(today)
    window = {(t - timedelta(days=i)).isoformat() for i in range(1, days + 1)}
    seen: dict[str, set] = {}
    for ln in RUNS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        d = str(r.get("at", ""))[:10]
        if d in window:
            seen.setdefault(d, set()).add(r.get("session"))
    return sum(len(v) for v in seen.values()) / float(days)


def closed_per_day(today: str, days: int = WINDOW_DAYS) -> int:
    """直近 days 日に**実際に閉じた**前提の件数（`closed_on` を数える）。"""
    rows = _hypotheses()
    t = date.fromisoformat(today)
    lo = (t - timedelta(days=days)).isoformat()
    return sum(1 for h in rows
               if str(h.get("closed_on") or "") and lo < str(h["closed_on"]) <= today)


def _hypotheses() -> list[dict]:
    try:
        import yaml
    except ImportError:
        return []
    if not HYPS.exists():
        return []
    try:
        d = yaml.safe_load(HYPS.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = d if isinstance(d, list) else (d.get("hypotheses") or next(iter(d.values()), []))
    return [h for h in (rows or []) if isinstance(h, dict)]


def closable_within(today: str, horizon: int = SUPPLY_HORIZON) -> list[dict]:
    """**この先 horizon 日のあいだに閉じられる、開いた前提。**

    期日が過ぎているものも数えます —— **いますぐ閉じられる**ので在庫です。
    """
    end = (date.fromisoformat(today) + timedelta(days=horizon)).isoformat()
    ready = _ready_by_claim()
    out = []
    for h in _hypotheses():
        if any(k in h for k in ("verdict", "closed_on", "outcome")):
            continue
        # **`deadline` は置いた回の勘です**（2026-08-25 22:5x）。
        # 実際に判定できる日は `scripts/deadline_check.py` が予約・台帳・
        # Analytics の遅れから出します。2つは実測で **10件・合計46日** ずれていて、
        # ここが `deadline` を読んでいるあいだ、**在庫が実際より薄く見えていました**
        # （＝この門が「在庫0」で止める側にも、素通しする側にも外れます）。
        r = ready.get(str(h.get("claim") or ""))
        dl = str(r) if r else str(h.get("deadline") or h.get("settle_by") or "")
        if dl and dl <= end:
            # **その日が「勘」なのか「計器の答え」なのかを、持って出ること**
            # （2026-08-27・最適化の回）。`deadline` へ落ちた行は、
            # `deadline_check` が「まだ判定できない」と言っている前提です ——
            # 在庫としては数えてよい（窓の中で判定できるようになりうる）が、
            # **「いま閉じられる」とは言えません。** ここが区別を持たずに
            # 出していたので、`theta_response()` は判定できない前提について
            # 「期日は1日 過ぎています ＝ **この回に閉じられます**」と
            # 印字していました（実測 08/27）。
            out.append({**h, "_closable_on": dl, "_closable_est": r is None})
    return out


def _ready_by_claim() -> dict:
    """**前提ごとの「判定できる最早の日」**（`scripts/deadline_check.py`）。

    壊れても在庫の数えそのものは止めないこと —— 落ちたら `deadline` に戻ります。

    **2026-08-26 に `_judge_state_by_claim()` からの導出に変えました。**
    それまで、この道具は同じ回のうちに `deadline_check` を**2度 読み込んで**
    いました（門の側と、この在庫の側）。1回 約3秒 で、`stop_check.sh` の
    `timeout 30` に対して素直に2倍 払っていたことになります。
    **数字は1文字も変わりません** —— 同じ `check()` の `ready` です。
    """
    st = _judge_state_by_claim()
    if not st:
        return {}
    return {k: v[1] for k, v in st.items() if v[0] == "ready" and v[1] is not None}


def role_gap_hours(role: str, limit: int = 40) -> float | None:
    """**その役の、周と周のあいだは実測で何時間か。**（`data/rounds.jsonl` の中央値）

    書いているのは `scripts/next_round.py` だけです。**時刻を当てません** ——
    直近 `limit` 周の実測の中央値を返します（周が2つ未満なら `None`）。
    """
    if not ROUNDS.exists():
        return None
    seen: list[str] = []
    for ln in ROUNDS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("role") != role:
            continue
        at = str(r.get("round") or r.get("at") or "")
        if at and at not in seen:
            seen.append(at)
    seen = sorted(seen)[-limit:]
    ts = []
    for s in seen:
        try:
            ts.append(datetime.fromisoformat(s))
        except ValueError:
            continue
    if len(ts) < 2:
        return None
    gaps = sorted((ts[i + 1] - ts[i]).total_seconds() / 3600.0 for i in range(len(ts) - 1))
    mid = len(gaps) // 2
    return gaps[mid] if len(gaps) % 2 else (gaps[mid - 1] + gaps[mid]) / 2.0


def theta_response(today: str, closed: int, soonest: str | None,
                   days: int = WINDOW_DAYS) -> list[str]:
    """**この θ は、1周ごとの答え合わせに使えるか。**（応答時間を同じ画面に出す）

    ## なぜ要るのか（2026-08-27・最適化の回。**5周 続けて誤報していた**）

    `docs/spawn_prompt.md` は最適化の役に、毎周こう自己採点させていました:

        答えが毎回変わるのに θ（前提を閉じる速さ）が改善しない
          → **問いではなく、答え方が外れています**

    **この採点は、ほぼ確実に「外れています」と出ます。** 理由は2つとも
    このファイルの中にあります:

    - `rounds_per_day()` は**今日を数えません**（半端な日を混ぜないため）。
      つまり θ の**分子は、同じ日のあいだ1度も動きません。**
    - 分母 `closed_per_day()` が動くのは、実際に前提が閉じた日だけ ——
      実測 **0.86件/日**（直近7日で6件）。

    一方この役の周は実測 **1.14時間ごと**（`data/rounds.jsonl`・35周）＝ 1日 21周。
    **1周のあいだに θ が動く見込みは 4%。96% の回は、何をしても
    「改善していません」と読みます。** 実際、8/26〜8/27 の最適化の回は
    **5周 続けて同じ 22周/26周 を読み**、そのたびに「答え方が外れている」と
    判定して**前の回の答えを捨て、新しい答えを立てていました。**
    答えが毎回変わっていたのは、**採点器が毎回 誤報していたから**です。

    ## 応答時間を測ると、そもそも桁が合っていません

    直近7日に閉じた6件を、`config/hypotheses.yaml` へ**立てた日**（git 履歴）と
    突き合わせた実測 —— 立ててから閉じるまで **0 / 7 / 10 / 10 / 11 / 14日**
    （中央値 **10日**）。この役の周に直すと **中央値 210周**。
    **210周 かかって届く数を、1周ごとに読んでいた**わけです。

    ## だから、この行を θ の隣に置きます

    消すのではありません —— θ は 7日の窓では正しい数です。
    **1周ごとの合否に使うな**と、読む場所に書いてあれば足ります。
    **1周で応えるのは予定表の θ**（`src/arm_speed.forward()`。
    `scripts/queue_lag.py` が毎回 印字しています）—— 入れ替え・期限・
    群への割り当てを触ると、**その回のうちに動きます。**

    **覆る条件**: 周の間隔が伸びて、`p_move`（下で印字する数）が
    **50% を超える** —— そこまで来たら θ は1周ごとに読める数になるので、
    この節ごと外すこと。
    """
    gap = role_gap_hours("optimizer")
    per_day = (closed / float(days)) if days else 0.0
    out = ["", "  --- **この θ を、1周ごとの答え合わせに使わないこと**（応答が遅すぎる） ---"]
    out.append(
        "  分子（周）は `rounds_per_day()` が**今日を数えません** →"
        " **同じ日のあいだ1度も動きません**（このファイルの事実）"
    )
    out.append(
        f"  分母が動くのは、実際に前提が閉じた日だけ ＝ 実測 **{per_day:.2f}件/日**"
        f"（直近{days}日で {closed}件）"
    )
    if gap:
        rounds_day = 24.0 / gap
        p = min(1.0, per_day / rounds_day) if rounds_day else 0.0
        out.append(
            f"  この役の周は実測 **{gap:.2f}時間**ごと（`data/rounds.jsonl`）＝ 1日 **{rounds_day:.0f}周**"
        )
        out.append(
            f"  → **他の誰かが閉じるのを待つなら、1周で動く見込みは {p * 100:.0f}%**"
            f"（残り {(1 - p) * 100:.0f}% の回は「改善していません」と読めます）"
        )
        # **この数を「何をしても動かない」と読まないこと**（2026-08-27・最適化の回に直した）。
        #
        # 前の版は「**1周のあいだに θ が動く見込みは 4%。96% の回は、何をしても
        # 『改善していません』と読みます**」でした。**「何をしても」が誤り**です ——
        # `closed_per_day()` は **`lo < closed_on <= today`**、つまり**今日を数えます。**
        # **この回が1件 閉じれば、その場で動きます**（実測 08/27: 6件 → 7件 で
        # **22周に1回 → 19周に1回**）。上の `p` は「**自分では閉じず**、他の回が
        # 閉じるのを待った場合」の確率で、**自分の手を勘定に入れていません。**
        #
        # 差は決定的です。前の読み方だと「この採点器は壊れている」に行き着き、
        # 実際そう判定して**採点器そのものを取り替えました**（`_forward_theta_line`）。
        # 正しく読むと「**この採点器は、自分が閉じたときだけ動く**」——
        # つまり**望みどおりの向き**です。
        out.append(
            "    **ただし「何をしても動かない」ではありません** ——"
            " `closed_per_day()` は**今日を数えます**。"
            f"**この回が1件 閉じれば、その場で {closed}件 → {closed + 1}件** です"
        )
        if soonest:
            try:
                d = (date.fromisoformat(soonest) - date.fromisoformat(today)).days
                if d <= 0:
                    # **期日は過ぎています。** 負の日数を「-21周 後」と印字しないこと
                    # （2026-08-27 に出しました）。過ぎた期日は**いま閉じられる**ので、
                    # この回に θ を動かす道が実際に在るという意味です。
                    out.append(
                        f"  次に1件 閉じられるのは **{soonest}**（期日は{-d}日 過ぎています"
                        " ＝ **この回に閉じられます**）"
                    )
                else:
                    out.append(
                        f"  次に1件 閉じられるのは **{soonest}**（+{d}日 ＝ この役の"
                        f" **{d * rounds_day:.0f}周** 後）"
                    )
            except ValueError:
                pass
    else:
        out.append("  この役の周の間隔が測れません（`data/rounds.jsonl` に印が足りません）")
    out.append(
        "  **1周で応えるのは予定表の θ**（`src/arm_speed.forward()`）——"
        " 入れ替え・期限・群への割り当ては**その回のうちに動きます**"
    )
    out += _forward_theta_line()
    return out


def _forward_theta_line() -> list[str]:
    """**代わりに読む数を、同じ画面に出す。**（`src/arm_speed.forward()` の14日窓）

    **これを出さないと、上の行は「読むな」しか言っていません。**
    `queue_lag.py` も同じ数を出しますが、あちらは長い出力の真ん中で、
    しかも**入れ替えを解いてから**なので数十秒かかります。ここは台帳だけ
    （API 0単位・予約も読みません）。

    **窓は14日だけ**にします —— `forward()` の註が
    「短い窓ほど信用できる」「長い窓の `ratio` は台帳の件数で決まる」と
    言っているので、**1周ごとに読む数として意味があるのは短い窓だけ**です。

    落ちても drift 全体は止めません（**採点器のために門を壊さないこと**）。
    """
    try:
        sys.path.insert(0, str(ROOT))
        from src import arm_speed  # noqa: PLC0415
        fw = arm_speed.forward(_ready_by_claim())
    except Exception as exc:  # pragma: no cover - 台帳が読めない回
        return [f"    （予定表の θ が出せません: {exc}）"]
    if fw.get("missing"):
        return [f"    （予定表の θ が出せません: {fw['missing']}）"]
    for h in fw.get("horizons") or []:
        if h.get("days") == 14:
            n, per = int(h["n"]), float(h["per_day"])
            return [
                f"    いまの予定表の θ（14日窓）: **{per:.2f}/日**"
                f"（判定日の付いた前提 {n}件）"
                " ← **この数を JOURNAL に残すこと。次の回はここと比べます**",
            ] + _forward_sign_lines(n, per)
    return []


def _forward_sign_lines(n: int, per: float, days: int = 14) -> list[str]:
    """**この数は、どちらへ動けば「良い」のか。**（2026-08-27・最適化の回）

    ## 実測（本物の台帳で、閉じる側と足す側の両方を当てた）

        いまのまま                          **0.786/日**（11件）
        前提を**1件 閉じた**あと            **0.714/日**（10件）  ← **−9.2%**
        中身の無い複製を**1件 足した**あと  **0.857/日**（12件）  ← **+9.1%**

    **符号が逆です。** `forward()` の分子は「**いま開いている**前提のうち、
    窓の内側に判定日があるもの」なので、**閉じた前提は分子から出ていきます。**
    `eta.py` は毎回「軌跡の腕が動くのは**前提を1件閉じたときだけ**」と
    印字しています —— その唯一の手を撃つと、この採点器は**下がります。**
    そして**中身を問わず1件 足すだけ**で、同じ幅だけ上がります。

    ## これは机上の心配ではありません（**1日で3回 起きました**）

    この数は 2026-08-27 に `docs/spawn_prompt.md` の**1周ごとの合否**になり、
    その日のうちに **0.64（9件）→ 0.71（10件）→ 0.79（11件）**と上がりました。
    **同じ日に閉じた前提は 0件**です（`closed_on` の最後は **08-26**）。
    上がったぶんは**全部、台帳が増えたぶん**でした。前の回の日誌は
    その +11% を「**予定表の θ は、その回のうちに動きました**」と、
    採点器が直った証拠として書いています。

    `forward()` の註も `spawn_prompt` も「**期限を手前へ倒すだけで上がる**」
    までは書いていました。**書いていないほうが危険**です ——
    **正しい手を撃つと下がる。**

    ## 消さずに、隣に出す

    `forward()` は**予測としては正しい**（開いた前提が 11件 あれば、
    14日で 11件 閉じうる）。壊れているのは**読み方**なので、
    その場の数で「どちらへ動くと上がるのか」を並べます。

    ## **`queue_lag.py` の使い方は、これに当たりません**（消しに行かないこと）

    あちらは**同じ台帳の前後**で `forward()` を2回 呼び、
    「入れ替えで判定日を手前に倒すと、窓に何件 入るか」を見ています ——
    **前提の数は変わりません。** 符号が逆になるのは、
    **回をまたいで「この回は良かったか」を採点するとき**だけです。
    **中身が動く A/B と、時をまたぐ成績表を、同じ数で兼ねないこと。**

    **覆る条件**: `forward()` の分子が「開いた前提」から
    「**この窓の中に決着が付く（付いた）前提**」に変わって、
    閉じても分子から出ていかなくなったら、この3行は要りません。
    """
    if not n:
        return []
    return [
        f"      ↓ 前提を**1件 閉じる**と **{(n - 1) / days:.2f}/日** へ**下がります**"
        f"（閉じたものは分子から出ます）",
        f"      ↑ 中身を問わず**1件 足す**と **{(n + 1) / days:.2f}/日** へ**上がります**",
        "      → **これは在庫の数であって、閉じた速さではありません。**"
        " 上がったことを、そのまま成果と読まないこと"
        "（実測 08/27: 0.64→0.71→0.79 は**全部 足したぶん**。同じ日に閉じたのは **0件**）",
    ]


def supply_report(today: str, horizon: int = SUPPLY_HORIZON) -> tuple[str, bool]:
    """**到達日は「何周に1回」動きうるか。** 本文と「在庫が尽きている」かを返す。

    ## なぜ要るのか（2026-08-24・最適化の回）

    `eta.py` は毎回こう印字しています ——
    **「軌跡の腕が動くのは、前提を1件閉じたときだけ。作る・出す・直すは
    軌跡の入力に入りません」。** つまり**到達日が動きうる回数の上限は、
    その期間に閉じられる前提の数**であって、周の数ではありません。

    ところが上の `report()` は **「到達日を動かすと宣言した回 17/341」**と
    印字していました。**分母は周、分子は宣言で、上限はどこにも出てきません。**
    実測すると、直近7日は **141周に対して閉じた前提は6件** ——
    **上限は 6 で、宣言は 17。** 宣言のほうが上限の 2.8倍 あり、
    **「動かす」と言った回の大半は、裏づけになる前提を持っていませんでした。**

    2か所が別々のことを言っていて、片方しか読まれていない箇所がこれです:
    **`eta.py` は上限を知っていて、門はそれを一度も計算していなかった。**

    ## 止める条件（1つだけ）

    **在庫 0** —— この先 horizon 日に期日の来る開いた前提が1件も無い。
    そのときは**どの回が何をしても、その期間に到達日は動きません**。
    これは働き方の良し悪しではなく、**確実にそうなる**という意味で外れです。
    直し方は安く、その場でできます: 期日の近い前提を1件立てる（または
    期日を手前に倒す）。**それがその回の成果です。**

    **薄い（0ではないが少ない）だけでは止めません。** 実験は待ち時間が本体で、
    在庫3件で1週間回すのは正しい場面があります。**印字はします。**
    """
    rate = rounds_per_day(today)
    ahead = rate * horizon
    stock = closable_within(today, horizon)
    closed = closed_per_day(today)
    rounds_7d = rate * WINDOW_DAYS

    lines = ["", "=== 到達日は「何周に1回」動きうるか ==="]
    lines.append(
        "  `eta.py`: **軌跡の腕が動くのは、前提を1件閉じたときだけ**"
        "（作る・出す・直すは軌跡の入力に入りません）"
    )
    if rounds_7d and closed:
        lines.append(
            f"  実績（直近{WINDOW_DAYS}日）: 周 **{rounds_7d:.0f}** ／ 閉じた前提 **{closed}件**"
            f" → **{rounds_7d / closed:.0f}周に1回**"
        )
    elif rounds_7d:
        lines.append(
            f"  実績（直近{WINDOW_DAYS}日）: 周 **{rounds_7d:.0f}** ／ 閉じた前提 **0件**"
            " → **1回も動いていません**"
        )
    else:
        lines.append(f"  実績（直近{WINDOW_DAYS}日）: 周が数えられません（印がありません）")

    if stock:
        dls = sorted(str(h.get("_closable_on")
                         or h.get("deadline") or h.get("settle_by") or "") for h in stock)
        ratio = (f"**{ahead / len(stock):.0f}周に1回**" if ahead else "（周速が測れません）")
        lines.append(
            f"  見込み（今後{horizon}日）: 見込み周 **{ahead:.0f}** ／ 期日の来る前提"
            f" **{len(stock)}件** → {ratio}"
        )
        lines.append(f"    期日: {' / '.join(dls[:6])}")
        # **「次に1件 閉じられるのは」には、計器が日を出した前提だけを渡すこと。**
        # `deadline` へ落ちた行（`_closable_est`）は `deadline_check` が
        # 「まだ判定できない」と言っている前提です —— そこを渡すと
        # 「期日は1日 過ぎています ＝ **この回に閉じられます**」と出て、
        # **撃ちに行った回が空振りします**（実測 08/27）。
        real = sorted(str(h.get("_closable_on")) for h in stock
                      if not h.get("_closable_est"))
        lines += theta_response(today, closed, real[0] if real else None)
        if not real:
            lines.append(
                "    **次に閉じられる日は出せません** ——"
                " 在庫の期日は全部`deadline`（置いた回の勘）で、"
                "`deadline_check` は「まだ判定できない」と言っています")
    else:
        lines.append(
            f"  見込み（今後{horizon}日）: 期日の来る前提 **0件** →"
            f" **この{horizon}日は、何をしても到達日は動きません**"
        )

    dry = not stock
    lines.append("")
    if dry:
        lines.append(
            f"  [!] **在庫が尽きています。** 開いた前提の期日が、今後{horizon}日に1件もありません。"
        )
        lines.append(
            "      **これは働き方の問題ではありません** —— この期間は、"
            "どの回が何をしても到達日が動かないことが**確定しています**。"
        )
        lines.append(
            "      **この回の成果は「期日の近い前提を1件立てる」こと**"
            "（`config/hypotheses.yaml` に claim / deadline / falsified_if / next_if_false）。"
        )
        lines.append("      期日を手前に倒せる開いた前提があるなら、それでも構いません。")
    else:
        lines.append("      （在庫あり。**薄いだけでは止めません** —— 実験は待ち時間が本体です）")
    return "\n".join(lines), dry


# ---------------------------------------------------------------------------
# **引き代のない腕を、何回選んだか**（2026-08-24）
#
# `eta.py` の軌跡は、天井 ×1.00 の腕を **解く前に外します** ——
# その腕をどれだけ引いても到達日は1日も動きません。
# 8/24 の実測で `density` がそれ（1日に再生が付く上限 10本 ÷
# いま続けられる 12.1本/日 ＝ **すでに 1.2倍 超えて出している**）。
#
# ところがこの数は `eta.py` の stdout にしか無く、**選ぶ側に届いていません**。
# だから同じ日の ship が、名指し（`lever_hint`＝`rpm`）ではなく
# `density` を繰り返し選んでいました。ここはその比を毎周1行で出します。
#
# **門にはしません。** 天井そのものが未判定の前提に乗っているためです
# （`density` の ×1.00 は day_cap=10本 に乗り、それは 13:30 の窓と
# **まだ切り分けられていません** —— 08/28 の判定で窓のほうなら天井は上がる）。
# **覆る条件**: 08/28 の判定が「窓」に出たら、この節の `density` の行は消えます。
# ---------------------------------------------------------------------------

def dead_arm_report(today: str, window_days: int = WINDOW_DAYS) -> str:
    """直近の ship が、**引き代のない腕**をどれだけ選んだか。"""
    state = levers.latest_arm_state(ROOT / "data" / "eta.jsonl")
    caps, hint = state.get("caps") or {}, state.get("hint")
    since = (date.fromisoformat(today) - timedelta(days=window_days)).isoformat()
    runs = [r for r in load_runs(since) if r.get("lever")]
    out = ["", "=== 到達日を動かせない腕を、何回選んだか ==="]
    if not caps:
        out.append("  （`data/eta.jsonl` に `arm_caps` がまだありません。"
                   "`python scripts/eta.py` を1回走らせると出ます）")
        return "\n".join(out)
    if not runs:
        out.append("  （この窓に `--lever` つきの ship がありません）")
        return "\n".join(out)
    tally = Counter(r["lever"] for r in runs)
    # **「引き代がない」は2種類あります**（2026-08-25）。
    #     ここは天井 ×1.00 だけを数えていて、**天井は大きいのに到達日に
    #     触らない腕**（`sub_rate` 天井 ×2,923.79）を**生きた腕として数えて
    #     いました。** 判定は `levers.arm_state()` が持ちます（1か所に寄せる）。
    why = state.get("dead_why") or {}
    #: **死んだ腕から外した理由**（面が割れている腕。いまは `density` だけ）。
    open_why = state.get("open_why") or {}
    # --- **「引き代なし」と「十分でないだけ」を、同じ数に足さない**（2026-08-26）---
    #
    # ここは長らく、`dead_why` に載った腕を**理由を問わず** `n_dead` へ足し、
    # 「この回では到達日が動きえない回 **175/249（70%）**」の分子にしていました。
    # **`dead_why` には2種類 入っています**（`src/levers.arm_state`）:
    #
    #     「天井」                  天井 ×1.00 ＝ 引いても動かない
    #     「天井まで引いても届かない」 **その腕だけ**を天井まで引いても届かない
    #
    # 後者は**十分でない**ことしか言っていません。**必要かどうかは別の問い**で、
    # 同じ日の `eta.py --alloc` は「**次の1件は `sub_rate` に置くのが最短**
    # （3日 早い）」と出していました。**同じプログラムが正反対を言っていた**
    # ので、`drift` の側はそれを「無駄に選んだ回」として数えていたわけです。
    #
    # 判別は測ればつきます —— **その腕を凍らせて軌跡を解き直す**
    # （`eta.frozen_days`。回転はよその腕へ配り直したうえで）。
    # 遠のくなら必要、動かないなら要らない。**その数を読んで割ります。**
    #
    # **覆る条件**: `arm_frozen_days` が行に無い回は、判別できません。
    # そのときは**鳴らす側ではなく、数えない側へ倒します** ——
    # 「引き代が無かった」は主実行の作業を否定する数なので、
    # **読めないまま否定しないこと**（`_LOUD_WHEN_UNKNOWN` の逆向きです。
    # あちらは門、ここは自己評価の比で、外れる向きの損が反対です）。
    frozen = state.get("frozen") or {}
    dead = sorted(k for k in tally if k in why)
    NOT_ENOUGH = "天井まで引いても届かない"
    # **天井 ×1.00 の側は、そのまま確定の「引き代なし」**（判別は要りません）。
    hard = [k for k in dead if why.get(k) != NOT_ENOUGH]
    # **「その腕だけでは届かない」側だけを、凍らせた線で割ります。**
    needed, unknown = [], []
    for k in (x for x in dead if why.get(x) == NOT_ENOUGH):
        fz = frozen.get(k)
        if not isinstance(fz, (int, float)):
            unknown.append(k)          # 判別できていない → 分子に入れない（下で印字）
        elif fz > 0.5:
            needed.append(k)           # 凍らせると遠のく ＝ **必要**
        else:
            hard.append(k)             # 回転をよそへ回しても同じ ＝ 引き代なし
    hard, needed, unknown = sorted(hard), sorted(needed), sorted(unknown)
    n_needed = sum(tally[k] for k in needed)
    n_dead = sum(tally[k] for k in hard)
    # **`none` は、定義そのものが「この回は予測日を動かさない」です**
    #     （`src/levers.LEVERS`。`MOVING` はここだけを外して作られています）。
    #     ここは長らく `none` を**分母にだけ**入れていました ——
    #     つまり「動かない回」を「生きた腕を引いた回」と同じ側で数えていた。
    #     **外れる向きが悪いほうでした**: 実測 2026-08-26 で
    #     **43/175（25%）** と印字していたものが、`none` 71回 を入れると
    #     **114/175（65%）** です。25% は「まあ許容」に読め、65% は読めません。
    #     この節に渡される本文が言っている「べた書きが判断をひっくり返す」の、
    #     計算版です。**`fix` を禁じるためではありません**（この道具の冒頭を読むこと）——
    #     禁じるのではなく、**2つを別々に印字して、合計も出します。**
    n_none = tally.get("none", 0)
    for k, n in tally.most_common():
        cap = caps.get(k)
        mark = ""
        if k == "none":
            mark = "  ← **宣言どおり、この回は到達日を動かしません**（道具・手順・記録の整備）"
        elif open_why.get(k):
            # **面が割れていて生きている腕**（2026-08-27・最適化の回）。
            #     ここが無いと、`density` の行は「（天井 ×1.00）」だけになります ——
            #     **分子から外したのに、読む側には「死んでいる」と同じ字で出る。**
            #     外した理由（＝長尺の面が開いている・何をすれば引けるか）を
            #     同じ行に置かないと、次の回はまた `none` を選びます。
            mark = f"  ← **{open_why[k]}**"
        elif (why.get(k) or "").startswith("天井") and why.get(k) != "天井まで引いても届かない":
            # **前方一致で見ること**（2026-08-26）。`arm_state` は理由に但し書きを
            #     足すことがあり（「天井（**ショートの面の数**）」）、完全一致だと
            #     **分子に数えている腕の行から理由が消えます** —— 実際に消えていました。
            mark = f"  ← **{why[k]} ×{cap:.2f}（いまの実測では引き代なし）**"
        elif why.get(k) == "天井まで引いても届かない":
            cap_s = f"天井 ×{cap:,.2f}。" if cap is not None else ""
            fz = frozen.get(k)
            if isinstance(fz, (int, float)) and fz > 0.5:
                mark = (f"  ← {cap_s}**この腕だけでは届きませんが、"
                        f"凍らせると軌跡は {fz:+,.0f}日 ＝ 必要な腕です**"
                        "（無駄に選んだ回には数えません）")
            elif isinstance(fz, (int, float)):
                mark = (f"  ← **{cap_s}凍らせても {fz:+,.0f}日 ＝ "
                        "回転をよそへ回しても同じ。引き代なし**")
            else:
                mark = (f"  ← {cap_s}**この腕だけを天井まで引いても届きません**"
                        "（＝十分でない。**要らないという意味ではありません** ——"
                        " 凍らせた線がこの行にまだ無いので、"
                        "**動きえない回には数えていません**）")
        elif cap is not None:
            th = (state.get("thresholds") or {}).get(k)
            th_s = f"／出はじめ ×{th:,.2f}" if isinstance(th, (int, float)) else ""
            mark = f"  （天井 ×{cap:.2f}{th_s}）"
        out.append(f"    {k:<10} {n:>3}回{mark}")
    out.append(f"  → 動かす腕を選んだのに**引き代が無かった回: {n_dead}/{len(runs)}**"
               f"（{n_dead / len(runs) * 100:.0f}%）")
    # **判別できていない腕を、黙って分子から外さないこと**（2026-08-26）。
    #     外すだけだと、`--no-frozen` を1回 付ける／`eta.py` が古いまま という
    #     **計器を止めるだけでこの比が良くなる**道ができます。前の回が
    #     「**計器を壊すだけで門が緑になる作りにしないこと**」と書いたのと同じ形なので、
    #     **読めなかったことと、数えたらいくつかを、必ず両方 印字します。**
    if unknown:
        n_unknown = sum(tally[k] for k in unknown)
        out.append(f"  [!] **凍らせた線がこの行にありません: "
                   f"{'／'.join(f'`{k}`' for k in unknown)}** ——"
                   " その腕が「十分でないだけ」か「要らない」かを**判別できていません**。"
                   f" 数えた場合は **{n_dead + n_unknown}/{len(runs)}**"
                   f"（{(n_dead + n_unknown) / len(runs) * 100:.0f}%）。"
                   " **判別するには `python scripts/eta.py` を1回**"
                   "（`--no-frozen` を付けないこと。腕1本 15〜20秒・API 0単位）")
    if n_needed:
        out.append(f"  → **十分ではないが必要な腕を選んだ回: {n_needed}/{len(runs)}**"
                   f"（{n_needed / len(runs) * 100:.0f}%）"
                   f" —— {'／'.join(f'`{k}`（凍らせると {frozen[k]:+,.0f}日）' for k in needed)}。"
                   " **これは漂流ではありません。上の分子には入れていません**")
    out.append(f"  → **`none`（動かさないと宣言した回）: {n_none}/{len(runs)}**"
               f"（{n_none / len(runs) * 100:.0f}%）")
    out.append(f"  → 合わせて、**この回では到達日が動きえない回: "
               f"{n_dead + n_none}/{len(runs)}**"
               f"（{(n_dead + n_none) / len(runs) * 100:.0f}%）"
               f" —— 動きうるのは残りの **{len(runs) - n_dead - n_none}回**")
    if not state.get("reaches"):
        out.append("      （`arm_reaches` がまだ行に入っていません。"
                   "**「天井まで引いても届かない」側は数えられていません** ——"
                   " `python scripts/eta.py` を1回走らせると入ります）")
    if hint:
        # **名指しを外した回と、`eta.py` 自身が「外せ」と言った回は別ものです**
        #     （2026-08-26・最適化の回）。
        #
        #     `eta.py` は、名指しした腕の測定がもう予約済みのとき、こう印字します:
        #
        #     > **その `per_video` の測定は、予約済みの本が 2026-08-31 に答えます**
        #     > → **この回は別の腕を引くこと。** `--lever` が `per_video` でなくても、
        #     >   この回は「名指しを外した」ではありません
        #
        #     `run_marker.py` はそれを `lever_hint_covered` として**その回の行に
        #     残しています**。ところがここは `lever == hint` だけを数えていて、
        #     **その欄を1度も読んでいませんでした。**
        #
        #     外れる向きが悪いほうです —— 読まないと「名指しに従った回 21%」と出て、
        #     読んだ回が「instrument を8割 無視している」と受け取ります。
        #     **そして直し方は「per_video の回を増やす」になります** ——
        #     `eta.py` が「その腕はもう測定中だから別を引け」と言っている、
        #     まさにその腕を。**この repo が何度も踏んでいる「同じことを2か所が
        #     別々に言っていて、片方しか読まれていない」の、また1件**です。
        covered = [r for r in runs if r.get("lever_hint_covered")]
        judged = [r for r in runs if not r.get("lever_hint_covered")]
        follow = sum(1 for r in runs if r["lever"] == hint)
        out.append(f"  → 名指し **`{hint}`** に従った回: **{follow}/{len(runs)}**"
                   f"（{follow / len(runs) * 100:.0f}%）")
        if covered:
            when = sorted({str(r.get("lever_hint_covered")) for r in covered})
            f2 = sum(1 for r in judged if r["lever"] == hint)
            out.append(
                f"      うち **{len(covered)}回** は、`eta.py` 自身が"
                f"**「この回は別の腕を引くこと」**と言っていた回です"
                f"（名指しの測定が {'／'.join(when)} に予約済み）。"
                f"**外した回には数えないこと。**")
            if judged:
                out.append(f"      それを除くと: **{f2}/{len(judged)}**"
                           f"（{f2 / len(judged) * 100:.0f}%）"
                           f" ← **こちらが「名指しに従ったか」の数**です")
            else:
                out.append("      **除くと1回も残りません** ——"
                           "この窓は、名指しの腕がずっと測定中でした。"
                           "**従いようがない窓を、従わなかった窓と読まないこと。**")
    if n_dead:
        out.append("      **止めてはいません。** 天井は未判定の前提に乗ることがあり、"
                   "そのときは引き代のほうが後から出ます。")
        out.append("      引くなら、**天井が乗っている前提を1件、実データで判定する**こと。")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", action="store_true",
                    help="外れているとき exit 2（stop フックから読む用）")
    ap.add_argument("--today", default=None, help="基準日（検査用）")
    ap.add_argument("--window", type=int, default=WINDOW_DAYS)
    ap.add_argument("--horizon", type=int, default=SUPPLY_HORIZON,
                    help="在庫を数える先の日数（既定 %d日）" % SUPPLY_HORIZON)
    a = ap.parse_args(argv)
    today = a.today or today_jst()
    text, drifting = report(today, a.window)
    print(text)
    stext, dry = supply_report(today, a.horizon)
    print(stext)
    print(dead_arm_report(today, a.window))
    return 2 if (a.gate and (drifting or dry)) else 0


if __name__ == "__main__":
    sys.exit(main())
