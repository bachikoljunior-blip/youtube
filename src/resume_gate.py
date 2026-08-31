"""**収益化の審査に受かる確率**を、この機械が読める形にする。

## なぜ要るか（2026-08-30・最適化の回が実測して足した）

`scripts/eta.py` は、止まっている間ずっと次を印字していました（自分の言葉で）。

    **固定してこの日付が出ています**: **収益化の審査に受かる確率を 1.0** に置いたまま
    …… **その項はまだこの機械に入っていません。**

**入っていないのは註ではなく、掛け算の項です。** 収益 ＝ 再生 ÷ 1000 × RPM は、
**審査に受かった世界でだけ**成り立ちます。受からなければ再生がいくつでも収入は 0 円
（`CLAUDE.md`「収益化されなければ、RPM がいくつでも収入はゼロです」）。
つまり `p_pass` は到達日に**掛かる**項で、腕（`per_video` / `rpm` / `density` /
`sub_rate`）はその内側にあります。**外側が 0 なら、内側を何倍にしても 0 です。**

### 実測（この回に自分で数えた・`data/runs.jsonl` 501行）

    08/26 → 08/30 の 4.1日で ship **359件**
    そのあいだ到達日は 2026-12-28 → 2027-01-10 ＝ **+13日 遠のいた**
    直近200件の種別: fix 145 ／ upload 34 ／ means 16 ／ **verdict 5**

`eta.py` 自身が「**軌跡の腕が動くのは前提を1件 閉じたときだけ**」と印字しているので、
**200件中 195件（97.5%）は、この機械の模型では到達日を動かせない種類**でした。
そして 08/30 の停止後は、**腕そのものが1つも引けません**（`src/pause_guard`）。
語彙に「引ける腕」しか無いので、停止中の回は `--lever none`（40件中 20件）へ落ちます。

**律速は腕ではなく、この門です。**

    腕を ∞ 倍にしても                到達日は動かない（生成が塞がっている）
    θ（前提が閉じる速さ）を ∞ にして  **-47日**（`eta.py` の実測）
    **`p_pass` を 0 → 1 にすると**    **「出ません」→ 有限**（＝ 上限なし）

## この模型が置いていること（**推測を数字で埋めないこと**）

**`p_pass` の値は、この機械からは測れません。** YouTube の審査に n 回 出して
何回 通ったかの実績が無いからです（0回）。だから**確率を捏造しません。**
代わりに、確率が 1.0 で**ない**ことだけを構造で言います。

    門が 6件 とも閉じている  → `p_pass` は「この機械の外」（審査の実物次第）
    1件でも開いている        → **`p_pass = 1.0` と置く根拠はどこにも無い**

**そして到達日は、門が閉じるまで始まりません** —— 停止中は本が1本も出ないので、
軌跡の 48日 は門が閉じた**後**から数え直しになります。これが床(d)です。

    (d) 門が閉じる日 ＋ 軌跡の日数

門が閉じる速さは、**閉じた実績からしか出しません**（`data/resume_gate.jsonl`）。
0件 閉じているうちは速さが測れないので、**0 とも ∞ とも書かず「測れていません」**と返します
（`docs/JOURNAL.md` 2026-08-30 の「覆る条件」4番:
 **測れないことを誤りゼロとして印字するのが、この仕掛けの最悪の壊れ方**）。

## 覆る条件

1. **`AUTOMATION_PAUSED.md` が消えたら、この module は黙ります**（`is_paused()` が偽）。
   停止が明けたのに門が縛り続ける形にしないこと
2. 門を 6件 閉じても審査に落ちたら、**この6件が十分条件でなかった**ということ。
   そのときは `AUTOMATION_PAUSED.md` の側を書き換える（ここは写しているだけ）
3. 条件の本文は**オーナーが push したファイルが正本**です。ここに書き写さないこと ——
   写した瞬間に、向こうを直しても効かなくなります
4. 閉じる速さが 3件 以上の実績で測れたら、`days_to_close()` の推定が立ちます。
   それまでは `None`（「測れていません」）を返し続けます
5. **速さは「件数 ÷ 経過」では作りません**（2026-08-30 に実測して直した）。
   同じ日にまとめて閉じた分は速さを1つも言わないのに、その割り算は数を返し、
   **「残り全部が明日 閉じる」→ その後は1日 経つごとに2日 遠のく**、という
   2段の壊れ方をしました（`days_per_close()` の docstring に実測の表）。
   いまは**間隔**で数えます。種別ごとの実績が貯まったら、種別で分けること
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import pause_guard

ROOT = Path(__file__).resolve().parent.parent

#: **判定は持ちません。写しもしません。**（2026-08-31）
#:
#: ここには `PAUSE_FILE = ROOT / "AUTOMATION_PAUSED.md"` と
#: `def is_paused(): return PAUSE_FILE.is_file()` が**独立に**書いてありました。
#: `src/pause_guard` にも同じ2行があり、**同じ問いに2つの答えがある状態**でした。
#: 片方だけ直した回が「**動いているのに停止中と印字する**」形を作れます ——
#: この repo でいちばん多い壊れ方（「言っている所と、している所が別」）そのものです。
#:
#: いまは `src/pause_guard` が1か所で持ちます。ここは**文書を読むだけ**です。
PAUSE_FILE = pause_guard.PAUSE_FILE
LEDGER = ROOT / "data" / "resume_gate.jsonl"

#: 閉じた実績が何件たまれば「閉じる速さ」を口にしてよいか。
#: **1件で割ると、たまたま早かった1件が全部の予定になります。**
MIN_CLOSED_FOR_RATE = 3

#: **分母のほうの下限**（2026-08-30・解除条件5の回に足した。**実際に踏む1日前に見つけた**）。
#:
#: 件数の門（上）だけでは足りません。**3件が同じ日にまとめて閉じる**からです ——
#: 実測: 門1・2・5 は**3件とも 2026-08-30 に閉じました**（`data/resume_gate.jsonl`）。
#: 停止の開始も 08/30 なので、翌日には
#:
#:     span = 1日 ／ 閉じた 3件 → **3.0件/日** → 残り3件は **1.0日で閉じる**
#:
#: と印字されます。**同じ瞬間に起きた3件は、間隔について何も言っていません。**
#: しかもこの数は日が経つほど下がる（3.0 → 1.5 → 0.5）ので、
#: **測っているのは閉じる速さではなく、停止が始まってからの経過**です。
#:
#: この module は「**測れないことを 0 と印字しない**」ために作られています
#: （`p_pass()` が値を返さないのと同じ理由）。**小さすぎる分母で割った数を
#: 『測った』と印字するのは、同じ壊れ方の裏返し**です。
#:
#: **覆る条件**: 窓を広げれば当然 鈍くなります。閉じた実績が
#: 十分たまって（例えば 6件・14日）から、`(k-1) / (最後の close - 最初の close)`
#: のような、間隔そのものを見る推定へ替えてよい。**そのときここは消すこと。**
MIN_SPAN_DAYS = 3

_JST = timezone(timedelta(hours=9))


def is_paused() -> bool:
    """**`src/pause_guard` へ委譲します。ここで独立に判定しないこと**（上の註）。"""
    return pause_guard.is_paused()


def _pause_text() -> str:
    try:
        return PAUSE_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""


def paused_since(text: str | None = None) -> date | None:
    """`# AUTOMATION PAUSED — 2026-08-30` の日付。**見出しから読むこと。**

    ファイルの mtime は merge や clone で動くので使いません
    （この repo は worktree を毎回 作り直します）。
    """
    body = _pause_text() if text is None else text
    m = re.search(r"^#\s*AUTOMATION PAUSED\s*[—\-–]\s*(\d{4})-(\d{2})-(\d{2})", body, re.M)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def conditions(text: str | None = None) -> list[tuple[int, str]]:
    """`## Resume gate` の番号つき箇条書きを、そのまま返す。

    **本文をこの module に写さないこと**（覆る条件3）。オーナーが
    `AUTOMATION_PAUSED.md` を直したら、こちらは翌回から自動で追随します。
    """
    body = _pause_text() if text is None else text
    m = re.search(r"^##\s*Resume gate\s*$", body, re.M)
    if not m:
        return []
    tail = body[m.end():]
    nxt = re.search(r"^##\s", tail, re.M)
    block = tail[: nxt.start()] if nxt else tail
    out: list[tuple[int, str]] = []
    for ln in block.splitlines():
        # **字下げした行は条件ではありません**（2026-08-30 夜に踏んだ）。
        #     ここは長らく `^\s*(\d+)\.` で、**字下げの深さを見ていませんでした。**
        #     `## Resume gate` の節に「解除したらやること」を
        #     4字 下げたコードブロックで `1. 2. 3.` と書いた回があり、
        #     **門が 6件 から 9件 に増えました**（`--gate` が「9/9」と印字）。
        #     `state()` は番号で台帳と突き合わせるので、**足された 1〜3 は
        #     本物の 1〜3 の判定をそのまま貰い、閉じたことになります** ——
        #     つまり**黙って増え、黙って閉じます。**
        #
        #     条件は本文の第1階層に書かれる（`1.` が行頭から始まる）ので、
        #     **字下げ 4字 以上は落とします**（Markdown のコードブロックの下限）。
        #     箇条書きの中の入れ子（2字）は残します。
        #
        #     **覆る条件**: 条件そのものを字下げして書く形に正本が変わったら、
        #     ここを直すこと。検査は `tests/test_gate_all_closed.py`。
        mm = re.match(r"^(\s{0,3})(\d+)\.\s+(.*\S)\s*$", ln)
        if mm:
            out.append((int(mm.group(2)), mm.group(3)))
    return out


#: **正本の側に付く「閉じた」の印。**（2026-08-30 に踏んで足した）
#:
#: 同じ日に2つの回が別々にここへ着きました。片方は `data/resume_gate.jsonl` に
#: 積み、もう片方は `AUTOMATION_PAUSED.md` の箇条書きに
#: **「← 2026-08-30 に閉じた」と直接 書き足しました。**
#: 合流した直後の実測 —— `eta.py` が
#:
#:     開いている 5件: **1** sensitive-topic AI persona を使わない
#:     **← 2026-08-30 に閉じた（下の「進捗」）** ／ …
#:
#: と印字しました。**同じ1行の中で「開いている」と「閉じた」を両方 言っています。**
#: 正本はオーナーが push したファイルなので、**そちらの印を勝たせます。**
#:
#: **印は行末まで捨てること。** `←` から `閉じた` までだけを消すと
#: 「（下の「進捗」）**」が本文に残り、そのまま親の型へ印字されます
#: （実測 2026-08-30: 「1 sensitive-topic AI persona を使わない  **」）。
#: **2つに分けること**（2026-08-30 に2回 踏んだ）。
#:
#:     `_NOTE` …… `←` 以降の**書き込み全部**。条件の本文ではないので、必ず落とす
#:     `_CLOSED` … その書き込みが「**閉じた**」と言っているか
#:
#: 1回目は「閉じた」までしか落とさず、「（下の「進捗」）**」が本文に残りました。
#: 2回目は、きょうだいが 4番 に **「← 2026-08-30 に当てた」**（＝ 閉じてはいない）
#: と書き、**落とす条件と閉じる条件を同じ正規表現で見ていたせいで、
#: 開いている条件の本文に書き込みがそのまま印字されました。**
#: **見た目の話ではありません** —— この本文は親の型にも入り、次の子が読みます。
_NOTE = re.compile(r"\s*\*{0,2}←[^\n]*$", re.M)
_CLOSED = re.compile(r"閉じた|\bclosed\b", re.I)


def _ledger_rows(path: Path | None = None) -> list[dict]:
    p = LEDGER if path is None else path
    if not p.is_file():
        return []
    rows = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows


def state(text: str | None = None, path: Path | None = None) -> list[dict]:
    """6件それぞれの、いまの姿。

    返すのは `{"n", "text", "closed", "closed_on", "evidence"}`。
    **台帳の最後の行が勝ちます**（追記だけで直せる形にするため）。
    **開き直しも書けます**（`state="open"` を後から積む ＝ `reopen()`）。

    ## **その「開き直し」は、2026-08-30 夜まで効いていませんでした**

    ここには 08/30 の朝から「開き直しも書けます」と書いてあり、**そう書いてあるのに
    `closed = by_ledger or by_file` でした** —— 正本の `AUTOMATION_PAUSED.md` に
    `← 2026-08-30 に閉じた` の註が在る門は、台帳へ `state="open"` を積んでも
    **閉じたまま**になります。実測（この直しの前）:

        1・2・5・6  註が条件と**同じ行**にある → `by_file=True` → 開き直せない
        3・4        註が**次の行**にあり `conditions()` が拾わない → 開き直せる

    **同じ台帳の同じ書き方が、門の番号によって効いたり効かなかったりしていました。**
    しかも効かない側は**黙って**閉じたままになります（`--gate` は 6/6 と出る）。

    `docs/spawn_prompt.md` は毎回のサブに「閉じた根拠を実測で当て直し、
    **外れていたらその件を開き直せ**」と渡しています。**その手が無かった**、
    という形です（この repo の一番よくある壊れ方 ——「言っている所と、している所が別」）。

    **いまは台帳の明示の `open` が正本の註に勝ちます。** 註は写しで、
    台帳のほうが正本だからです（`AUTOMATION_PAUSED.md` 自身が
    「この一覧は写しです。正本は `data/resume_gate.jsonl`」と書いています）。

    **覆る条件**: 正本を台帳ではなくファイルの側に戻すなら、この向きも戻すこと。
    そのときは `_NOTE` が条件の**次の行**も拾うようにしないと、番号で挙動が割れます。
    """
    conds = conditions(text)
    last: dict[int, dict] = {}
    for r in _ledger_rows(path):
        try:
            n = int(r.get("n"))
        except (TypeError, ValueError):
            continue
        last[n] = r
    out = []
    for n, body in conds:
        r = last.get(n) or {}
        by_ledger = (r.get("state") == "closed")
        # **台帳が明示で開き直したか**（`reopen()`）。上の docstring の理由で、
        #     これは正本の註に**勝ちます**。「書いていない」とは別物なので、
        #     `not by_ledger` で代用しないこと（まだ1度も触っていない門と混ざります）。
        reopened = (r.get("state") == "open")
        # **正本の印を勝たせる**（`_NOTE` / `_CLOSED` の註）。
        #     書き込みは**閉じていなくても落とす**（本文ではないので）。
        note = _NOTE.search(body)
        by_file = bool(note and _CLOSED.search(note.group(0)))
        clean = _NOTE.sub("", body).strip(" 　*")
        closed = by_ledger or (by_file and not reopened)
        out.append({
            "n": n,
            "text": clean or body,
            "closed": closed,
            # **どちらが閉じたと言っているか。** 食い違いはここから読めます。
            "by_ledger": by_ledger,
            "by_file": by_file,
            "reopened": reopened,
            # **正本が閉じたと言っているのに、根拠の1行が台帳に無い状態。**
            #     `AUTOMATION_PAUSED.md` は「次の全条件が**記録される**まで
            #     解除しない」と書いているので、これは未完了です。
            #     **開き直した門はここに入りません**（未完了ではなく、開いています）。
            "unrecorded": by_file and not by_ledger and not reopened,
            "closed_on": (r.get("at") or "")[:10] if by_ledger else None,
            "evidence": r.get("evidence") if by_ledger else None,
        })
    return out


def closed_count(text: str | None = None, path: Path | None = None) -> int:
    return sum(1 for r in state(text, path) if r["closed"])


def open_items(text: str | None = None, path: Path | None = None) -> list[dict]:
    return [r for r in state(text, path) if not r["closed"]]


def p_pass(text: str | None = None, path: Path | None = None) -> float | None:
    """**審査に受かる確率。値は返しません（`None`）。**

    返せる回は1つだけです —— 門が 6件 とも閉じていて、かつ実際に審査へ出して
    通った実績があるとき。**この機械にその実績は 0件** なので、いまは常に `None`。

    **`1.0` を返さないことが、この関数の仕事の全部です。**
    `eta.py` は長らく「受かる確率 1.0」を暗黙に置いて日付を出していました。
    """
    return None


def _closed_dates(text: str | None = None, path: Path | None = None) -> list[date]:
    """**日付の付いた閉じ方**だけを、古い順に。（正本の印には日付がありません）"""
    out: list[date] = []
    for r in state(text, path):
        if not (r["closed"] and r["closed_on"]):
            continue
        try:
            y, m, d = (int(x) for x in str(r["closed_on"]).split("-"))
        except (TypeError, ValueError):
            continue
        out.append(date(y, m, d))
    return sorted(out)


def days_per_close(text: str | None = None, path: Path | None = None,
                   today: date | None = None) -> float | None:
    """**1件 閉じるのに何日かかっているか。** 測れなければ `None`。

    ## なぜ「件数 ÷ 停止からの日数」をやめたか（2026-08-30・最適化の回が実測して直した）

    直す前は `閉じた件数 ÷ 停止からの経過日数` でした。**分母は経過で、分子は件数**
    なので、**分子が全部おなじ日に入っていても、そのまま割ります。**
    実測 —— 門1・2 は `2026-08-30`、つまり**停止したその日**に閉じています。
    ここへ3件目を同じ日に足して、その後1件も閉じなかった線を引くと:

        today       rate/日   残り日数   門が閉じる日
        2026-08-30   ——        ——        （span=0 なので黙る）
        2026-08-31     3.00       1.0   2026-09-01   ← **「残り3件は明日 閉じる」**
        2026-09-01     1.50       2.0   2026-09-03
        2026-09-02     1.00       3.0   2026-09-05
        …
        2026-09-14     0.20      15.0   2026-09-29

    **壊れ方が2つ、続けて出ます。**

    1. **3件目が閉じた翌日、残り全部が「あと1日」になります。** 停止中に動く床は
       この床だけなので、主実行はそこを読んで「門は ほぼ ただ」と判断し、
       **塞がっている腕のほうへ戻ります。** その回は到達日を1日も動かしません。
    2. その後は **1日 経つごとに、閉じる日が2日 遠のきます**（`T → 2T`）。
       **追いつかないので、この日付は永久に来ません。**

    どちらも根は同じで、**同じ日にまとめて閉じた分は「速さ」を1つも言っていない**
    のに、割り算が数を返してしまうことです。**測れているのは間隔のほう**です。

    ## いまの数え方

        完了した間隔  閉じた日どうしの差の平均（同じ日に固まっていれば 0日）
        打ち切りの間隔 最後に閉じてから今日までの日数（**次の1件は「最低でも」これ**）
        1件あたり     その2つの**大きいほう**

    打ち切りのほうを下限に採るのは、**すでに待った日数より速く閉じると言わせない**
    ためです（10日 止まっているのに「次は0.3日」とは言えません）。
    どちらも 0 なら **`None`**（＝「測れていません」。0 でも ∞ でもない）。

    ## この数え方が置いていること（**覆る条件**）

    **6件が同じ難しさだと置いています。** 実際には閉じた1・2 は
    `config/channel.yaml` の1行と検査1つで閉じ、残る 3〜6 は**チャンネルの形そのもの**
    を決める話です。**安いほうから閉じた実績で、高いほうの日数を見積もっています。**
    種別ごとの実績が貯まったら、ここは種別で分けること。
    """
    ds = _closed_dates(text, path)
    if len(ds) < MIN_CLOSED_FOR_RATE:
        return None
    day = today or datetime.now(_JST).date()
    # **窓の門は残します**（`MIN_SPAN_DAYS`。同じ日に別の回が足したもの）。
    #     間隔で数えても、停止した直後の窓は薄いままです ——
    #     `2026-08-30` に3件が固まって閉じた翌日、こちらは
    #     「1件あたり 1日」（打ち切りの間隔）から始めます。**それは
    #     『1日 待った』としか言っていません。** 窓が開くまでは黙るほうが素直です。
    start = paused_since(text)
    if start is not None and (day - start).days < MIN_SPAN_DAYS:
        return None
    gaps = [(b - a).days for a, b in zip(ds, ds[1:])]
    done = (sum(gaps) / len(gaps)) if gaps else 0.0
    trailing = max((day - ds[-1]).days, 0)
    per = max(done, float(trailing))
    return per if per > 0 else None


def rate_per_day(text: str | None = None, path: Path | None = None,
                 today: date | None = None) -> float | None:
    """門が閉じる速さ（件/日）。**実績が薄い間は `None`。**

    中身は `1 ÷ days_per_close()` です（**割り算の向きだけの違い**）。
    印字が「件/日」で来た側のために残してあります。

    薄いかどうかは**3つ**見ます —— 件数（`MIN_CLOSED_FOR_RATE`）、
    **割る窓**（`MIN_SPAN_DAYS`）、そして**間隔そのもの**
    （`days_per_close()`。同じ日に固まっていれば 0日 ＝ 測れていない）。
    """
    per = days_per_close(text, path, today)
    if not per:
        return None
    return 1.0 / per


def days_to_close(text: str | None = None, path: Path | None = None,
                  today: date | None = None) -> float | None:
    """門が全部 閉じるまでの日数。**測れなければ `None`**（0 ではありません）。"""
    # **残りが 0件 なら、速さが測れていなくても 0日** です（閉じるものがない）。
    #     速さを先に見ると、同じ日に6件とも閉じた回が `None` を返します。
    if len(open_items(text, path)) <= 0:
        return 0.0
    per = days_per_close(text, path, today)
    if not per:
        return None
    return len(open_items(text, path)) * per


def cap(text: str | None = None, path: Path | None = None) -> float | None:
    """この腕の「天井までの倍率」。**`levers.LEVERS` に載せる条件**です。

    `src/levers.py` は「腕を増やすときは `eta.py` の側に **その腕を何倍にすれば
    いいか** が出ていること」と決めています。門の倍率は件数の比です。

        閉じた 0件 → 倍率は**定義できません**（0倍 では 6件 になりません）→ `None`
        閉じた k件 → **×(6/k)**
    """
    total = len(conditions(text))
    if not total:
        return None
    k = closed_count(text, path)
    if k <= 0:
        return None
    return total / k


def summary(text: str | None = None, path: Path | None = None,
            today: date | None = None) -> dict:
    """`eta.py` が印字に使う一式。**印字の文言はここに置かないこと。**"""
    conds = conditions(text)
    st = state(text, path)
    op = [r for r in st if not r["closed"]]
    return {
        "paused": is_paused(),
        "total": len(conds),
        "closed": len(st) - len(op),
        "open": len(op),
        "open_items": op,
        "since": paused_since(text),
        "p_pass": p_pass(text, path),
        "rate_per_day": rate_per_day(text, path, today),
        "days_per_close": days_per_close(text, path, today),
        "days_to_close": days_to_close(text, path, today),
        # **最後に閉じてから何日 経ったか**（打ち切りの間隔）。
        #     印字がここを出さないと、「残り N日」がどこから来たのか読めません。
        "since_last_close": (
            max(((today or datetime.now(_JST).date()) - _closed_dates(text, path)[-1]).days, 0)
            if _closed_dates(text, path) else None),
        "cap": cap(text, path),
        "min_closed_for_rate": MIN_CLOSED_FOR_RATE,
        # **正本が閉じたと言っているのに、根拠が台帳に無い件**（`state()` の註）。
        "unrecorded": [r for r in st if r.get("unrecorded")],
    }


def queue(path: Path | None = None, now: datetime | None = None) -> dict:
    """**停止しても、まだ公開され続ける本**を数える（API 0単位・実測 0.1秒）。

    ## なぜ門の隣に置くか（2026-08-30）

    `AUTOMATION_PAUSED.md` が止めたのは「**新しく作って足すこと**」で、
    **すでに YouTube 側へ入っている予約の列ではありません。**
    実測（`data/uploaded.jsonl` を `video_id` で重複排除・後の行が勝つ）:

        控えにある本            691本（`video_id` と `at` の両方を持つ行だけ。
                                 台帳の重複排除後は 735本 で、44本 は `at` を持たない
                                 —— **数えられないものを数えたことにしない**）
        **これから公開される     482本**（2026-08-30 11:00 〜 2026-10-09 23:00 JST）
        ペース                  **12.1本/日**

    **機械が1回も起きなくても公開されます。** その全部が、停止の理由になった
    旧 `persona` で作られています。つまり **`p_pass` は、こちらが何もしなくても
    毎日 下がりうる** —— 門は「開いている」だけでなく、**時計が回っています。**

    そして引っ込める道具（`reschedule.py`）は `src/pause_guard` の対象なので、
    **この機械からは止められません。** ここが出すのは数だけです。

    **覆る条件**: 予約が尽きる（`upcoming` が 0）か、停止が明けたら、この行は消えます。
    """
    p = (ROOT / "data" / "uploaded.jsonl") if path is None else path
    if not p.is_file():
        return {"held": 0, "upcoming": 0, "first": None, "last": None, "per_day": None}
    seen: dict[str, str] = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        vid, at = r.get("video_id"), r.get("at")
        if vid and at:
            seen[vid] = at  # **後の行が勝つ**（`retimed_at` で予定が動くため）
    ref = now or datetime.now(timezone.utc)
    future = []
    for at in seen.values():
        try:
            t = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if t > ref:
            future.append(t)
    future.sort()
    if not future:
        return {"held": len(seen), "upcoming": 0, "first": None, "last": None, "per_day": None}
    span = max((future[-1] - future[0]).days, 1)
    return {
        "held": len(seen),
        "upcoming": len(future),
        "first": future[0].astimezone(_JST),
        "last": future[-1].astimezone(_JST),
        "per_day": len(future) / span,
    }


def close(n: int, evidence: str, *, path: Path | None = None,
          at: datetime | None = None) -> dict:
    """門を1件 閉じる。**根拠の文が要ります**（空なら受け付けない）。

    閉じるのは「決めた」ではなく「**記録した**」ときです ——
    `AUTOMATION_PAUSED.md` が「次の全条件が**記録される**まで解除しない」と
    書いているので、根拠の所在（ファイル名・commit・実測）を必ず添えること。
    """
    if not evidence or not evidence.strip():
        raise ValueError("根拠の文が要ります（どこに何を記録したか）")
    valid = {num for num, _ in conditions()}
    if valid and n not in valid:
        raise ValueError(f"{n} は Resume gate の番号ではありません（{sorted(valid)}）")
    return _append({"at": (at or datetime.now(_JST)).isoformat(timespec="seconds"),
                    "n": int(n), "state": "closed", "evidence": evidence.strip()}, path)


def reopen(n: int, evidence: str, *, path: Path | None = None,
           at: datetime | None = None) -> dict:
    """門を1件 **開き直す**。`close()` の逆で、**同じく根拠の文が要ります**。

    ## いつ撃つか

    **閉じた根拠を実測で当て直して、外れたとき**です
    （`docs/spawn_prompt.md` が毎回のサブにそう渡しています ——
    「閉じた根拠は上限であって、出来上がりの実測ではありません」）。

    **閉じるより開くほうが安い、と読まないこと。** 開き直すのは
    「もう一度やる」ではなく「**いま出しても審査に通らないと分かった**」の記録です。
    根拠には**何を測って、どこと食い違ったか**を書くこと。

    ## なぜ関数が要るか（2026-08-30 夜に足した）

    `state()` の docstring は 08/30 の朝から「開き直しも書けます」と言っていましたが、
    **書く口が無く、手で積んでも 1・2・5・6 では効きませんでした**
    （`state()` の「その開き直しは効いていませんでした」の節）。
    **手順に書いてある逃げ道が、実装に無い**のがこの repo の一番よくある壊れ方です。
    """
    if not evidence or not evidence.strip():
        raise ValueError("根拠の文が要ります（何を測って、どこと食い違ったか）")
    valid = {num for num, _ in conditions()}
    if valid and n not in valid:
        raise ValueError(f"{n} は Resume gate の番号ではありません（{sorted(valid)}）")
    return _append({"at": (at or datetime.now(_JST)).isoformat(timespec="seconds"),
                    "n": int(n), "state": "open", "evidence": evidence.strip()}, path)


def _append(rec: dict, path: Path | None = None) -> dict:
    p = LEDGER if path is None else path
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
