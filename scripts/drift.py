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


def judgeable_split(od: list[dict], today: str) -> tuple[list[dict], list[dict]]:
    """期限切れの前提を「**いま判定できる**」と「**まだ判定できない**」に割る。

    ## なぜ要るか（2026-08-26 20:4x に踏んだ。**3つの道具が食い違っていた**）

    この回、同じ1件の前提について3つの道具がこう言いました:

        status.py（この道具） **[!] 外れています。この回は verdict を出すこと**
        eta.py                **期日の来た前提があります → verdict で日付が動かせます**
        deadline_check.py     **まだ数えはじめたところです。この回は何もしないのが正解**

    **正しいのは3つ目**でした。要 8本 に対し公開済み 7本、
    「両群がそろう公開日」は 3日 要るのに **0日**（Analytics が3日遅れ）。
    その前提の `falsified_if` 自身が「**どちらも 8本 に満たなければ
    判定できません。期限を延ばすこと。『まだ分からない』で閉じないこと**」
    と書いています。

    **ここが期限の日付しか見ていなかったのが原因です。**
    `deadline_check.Verdict` は 2026-08-26 から `warming`（待てば日が出る）と
    `unreachable`（こちらの手では起こせない）を持っていて、
    **判定できるかどうかは既に計算されていました。** 上がって来ていなかっただけです。

    **放っておくと、この赤は永久に消えません** —— 判定できない前提は
    判定されないので、`verdicts_tail == 0` のまま毎周この行が出ます。
    そして毎周が「verdict を出せと言われたが出せない」を一から考え直します
    （`retro.py` の (a2) 問い1 の直近5件が全部「何を出すか決めるところ」）。
    **いちばん悪い枝は、言われたとおりに判定できない前提を畳む回**です
    —— `docs/JOURNAL.md` 2026-08-26 が「判断を抜くと、入力の質が
    そのまま結果になる」と書いたのと同じ壊れ方になります。

    **覆る条件**: `deadline_check` を読めない・評価が落ちるときは、
    **全部を「判定できる」側に倒します**（第2返り値が空）。
    分からないときに赤を消すほうが危ないからです。
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import deadline_check as dc                          # noqa: PLC0415

        as_of = date.fromisoformat(today)
        # **`od` をそのまま渡すこと**（`dc.load()` を呼び直さない）。理由が2つ:
        #   1. `dc.load()` は既定の `config/hypotheses.yaml` を読むので、
        #      **`drift.HYPS` を差し替えた検査が、本物の台帳を評価しはじめます**
        #   2. `overdue()` は台帳の書き方3種（裸のリスト／`hypotheses:`／
        #      1つ目の値）を吸収しますが、`dc.load()` は `hypotheses:` だけです
        # そして期限切れの分だけ評価するので、**そのぶん速い**。
        by_claim = {str(v.claim): v for v in dc.check(od, as_of=as_of)}
    except Exception:                                        # noqa: BLE001
        return list(od), []

    now, later = [], []
    for h in od:
        v = by_claim.get(str(h.get("claim") or h.get("q") or ""))
        if v is None or v.unchecked:
            # **分からなければ赤の側。** `unchecked` ＝ `needs:` が書かれていない
            # ＝「判定できない」と分かったのではなく、**何が要るか誰も書いていない**。
            # ここを緑に倒すと、**書かなければ赤が消える**という抜け道になります。
            now.append(h)
            continue
        # **`ready` が今日までに来ているものだけが「いま判定できる」**。
        # `warming`（伸び率がまだ出ない）と `unreachable`（外の出来事待ち）は
        # `ready is None` なので、そのまま later に落ちます。
        if v.ready is not None and v.ready <= as_of:
            now.append(h)
        else:
            later.append(dict(h, _why=v.answers[0].why if v.answers else "",
                              _mark=v.mark))
    return now, later


def report(today: str, window_days: int = WINDOW_DAYS) -> tuple[str, bool]:
    """印字する本文と、「外れている」かどうかを返す。"""
    since = (date.fromisoformat(today) - timedelta(days=window_days)).isoformat()
    runs = load_runs(since)
    n = len(runs)
    kinds = Counter(_kind_of(r.get("what", "")) for r in runs)
    closes = sum(1 for r in runs if r.get("closes"))
    declared = sum(1 for r in runs if r.get("moves") is not None)
    nonzero = sum(1 for r in runs if r.get("moves"))

    # 直近 STALE_ROUNDS 回に verdict があるか（窓ではなく件数で見る）
    all_runs = load_runs()
    tail = all_runs[-STALE_ROUNDS:]
    verdicts_tail = sum(1 for r in tail if _kind_of(r.get("what", "")) == "verdict")

    od = overdue(today)
    # **期限が来たことと、判定できることは別です**（`judgeable_split` の註）。
    # 外れの条件に使うのは「**いま判定できる**」ほうだけ。
    od_now, od_later = judgeable_split(od, today)
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
    if od_later:
        # **この一覧は「サボっている証拠」ではありません。**
        # 判定に要るデータが、まだ手元に無いだけです（`judgeable_split`）。
        lines.append(
            f"  期限は来たが、**判定に要るデータがまだ無い前提: {len(od_later)}件**"
            "（`scripts/deadline_check.py` と同じ計算）"
        )
        for h in od_later[:5]:
            claim = str(h.get("claim") or h.get("q") or "")[:56]
            lines.append(f"    {h.get('_mark', '')} {h.get('deadline', '?')}  {claim}")
            if h.get("_why"):
                lines.append(f"         {str(h['_why'])[:96]}")
        lines.append(
            "      **これを verdict で畳まないこと。** `falsified_if` が"
            "「満たなければ判定できない。期限を延ばすこと。"
            "『まだ分からない』で閉じないこと」と書いている側です。"
        )

    lines.append("")
    if drifting:
        lines.append(
            "  [!] **外れています。** いま判定できる期限切れの前提があるのに、"
            f"直近{STALE_ROUNDS}回で1件も判定していません。"
        )
        lines.append(
            "      `eta.py` は「作る・出す・直すは軌跡の入力に入らない。"
            "動くのは前提を1件閉じたときだけ」と印字しています。"
        )
        lines.append("      **この回は verdict を出すこと。** 出せないなら理由を JOURNAL に。")
    elif od_later and verdicts_tail == 0:
        lines.append(
            "  外れではありません —— **期限は来ていますが、判定できる前提が1件もありません。**"
        )
        lines.append(
            "      この回に verdict を探さないこと（**待てば日が出ます**）。"
            "  縮められるのは期限のほうです: `python scripts/deadline_check.py`"
        )
    else:
        lines.append("  外れの条件（期限切れの前提 かつ 判定ゼロ）には当たっていません。")

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
            out.append({**h, "_closable_on": dl})
    return out


def _ready_by_claim() -> dict:
    """**前提ごとの「判定できる最早の日」**（`scripts/deadline_check.py`）。

    壊れても在庫の数えそのものは止めないこと —— 落ちたら `deadline` に戻ります。
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "drift_deadline_check", ROOT / "scripts" / "deadline_check.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["drift_deadline_check"] = mod   # dataclass が __module__ を引きます
        spec.loader.exec_module(mod)
        return mod.ready_by_claim()
    except Exception:
        return {}


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
    dead = sorted(k for k in tally if k in why)
    n_dead = sum(tally[k] for k in dead)
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
        elif why.get(k) == "天井":
            mark = f"  ← **天井 ×{cap:.2f}（いまの実測では引き代なし）**"
        elif why.get(k) == "天井まで引いても届かない":
            cap_s = f"天井 ×{cap:,.2f} だが、" if cap is not None else ""
            mark = f"  ← **{cap_s}天井まで引いても到達日に届きません**"
        elif cap is not None:
            th = (state.get("thresholds") or {}).get(k)
            th_s = f"／出はじめ ×{th:,.2f}" if isinstance(th, (int, float)) else ""
            mark = f"  （天井 ×{cap:.2f}{th_s}）"
        out.append(f"    {k:<10} {n:>3}回{mark}")
    out.append(f"  → 動かす腕を選んだのに**引き代が無かった回: {n_dead}/{len(runs)}**"
               f"（{n_dead / len(runs) * 100:.0f}%）")
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
