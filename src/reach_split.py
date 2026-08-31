#!/usr/bin/env python3
"""**インプレッションを「長尺」と「ショート」で割る。**（2026-08-20 21:3x に作った）

`scripts/reach.py` が積む `data/reach.jsonl`（YouTube Reporting API の
`channel_reach_basic_a1`）を読んで、**面に載っている本数**を形べつに出す。
**API は1単位も叩きません**（積んである CSV を読むだけ）。

## なぜ要るか（この道具が出た日の実測）

`reach.py` は 2026-08-15 に作られ、**8/20 21:2x に初めて叩かれました**（5日ぶん放置）。
そして出た数字には、**欠陥が2つ**ありました。

1. **報告を新しい3本しか落としていませんでした**（`reports[-3:]`）。ジョブは
   **作った時点から30日ぶん遡って**日ごとの CSV を置きます。全部落としたら
   **3日 → 34日**（165行 → 540行）。**在るのに読んでいなかっただけ**です
2. **CTR の列を百分率として読んでいました**（`/ 100`）。実物は**割合**です
   （`_clicks()` に裏取り）。**クリック数が100分の1に見えていました**

直したうえで、形で割るとこうです（2026-07-15〜2026-08-17・34日）:

    ショート  インプレッション 1,339  クリック 18   CTR **1.34%**
    長尺 6本  インプレッション 1,278  クリック  3   CTR **0.23%**

**この「6本」が、2026-08-24 まで欠陥でした**（`long_ids` の docstring）。
長尺は同じ34日で **12本**あり、面は **1,278 → 1,456**（+13.9%）。
表の形は変わりません —— **見せて、押されていない**のはそのままです。

**長尺は「見せられていない」のではありませんでした。**
1,278回 見せて、押されたのが3回です。そして**見せる量そのものが落ちています** ——
08/09 の **346/日** から 08/15〜17 は **5/日**。**試されて、外された**形です。

**段取り（`scripts/eta.py` の段2・段4）は、長尺で月50万再生を立てています。**
直近の面は 1日5回。**CTR を100%にしても月150回**で、要る数の3,300分の1。
`status.py` の実測では再生の **99.9% が SHORTS_FEED**、WATCH は28日で13再生 ——
**この34日で、サムネの面が生んだ再生は合計21回**です。数字が合います。

## 読み方（**インプレッションと CTR は、直す場所が正反対**）

    インプレッションが少ない  → 見せられていない（**題材・本数・面そのもの**）
    CTR が低い                → 見せたのに押されない（**サムネと題**）

**ショートのフィードは、この報告のインプレッションに入りません**（スワイプは
サムネのクリックではない）。だから**ショートの再生数と、ここの数字は別物**です。
ここに出るのは「**サムネを見せた面**」＝ ブラウズ・検索・関連動画の合計です。
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

from . import house_rule

ROOT = Path(__file__).resolve().parent.parent

#: 「いま続いている量」を測る窓（日）。**平均でも最大でもない、段取りが乗る数。**
RECENT_DAYS = 7

#: **窓の中の1日が、この割合以上を占めていたら「平均」は使えません**（2026-08-26 に足した）。
#:
#: 実測（`data/reach.jsonl`・長尺・08/15〜08/21 の7日）:
#:
#:     4 / 8 / 5 / 7 / 8 / 17 / **1,285**   → 平均 190.6 ・ 中央値 **8**
#:
#: 08/21 の 1,285回 のうち **1,276回（99.3%）が、その日に公開した5本**に付いています。
#: 同じ日、それ以前の長尺6本に付いたのは **1〜3回ずつ**でした。
#: つまり長尺の面は「立っている面」ではなく、**公開日の立ち上がりだけ**です。
#: `tail()` の docstring は最初から「**平均は burst をならしてしまいます**」と
#: 書いていましたが、**`per_day_recent` は平均のままでした** ——
#: そして `scripts/eta.py` の段2 がその 190.6 を読んで
#: 「合格点 191回/日 と**ちょうど同じ（×1.00）**」と印字していました。
#: 続いている量は 8回/日 なので、実際は **24倍 足りません。**
#: **同じ帳面の読み手2つが逆を向いていた形の5件目**（4件目は `summary()` の docstring）。
BURST_SHARE = 0.5
STORE = ROOT / "data" / "reach.jsonl"
LEDGER = ROOT / "data" / "uploaded.jsonl"
PAIRS = ROOT / "config" / "pairs.yaml"
#: **YouTube 自身が「長尺」と数えた動画IDの控え**（`src/rpm_mix.py --record` が書く）。
#: この道具は API を叩かないので、**測った側が置いていったものを読みます。**
FORMS = ROOT / "data" / "video_forms.json"

#: **この機械が「長尺として作った」と書き残した帳面**（`scripts/batch_build.py --long`）。
#: `data/video_forms.json` は **YouTube が分類し終えた本**しか持ちません ——
#: つまり「まだ公開していない本」と「公開したが再生0の本」が丸ごと落ちます。
BATCH_RUNS = ROOT / "data" / "batch_runs.jsonl"

#: 段4（月20万）が長尺に置いている月あたり再生数。`scripts/eta.py` の
#: `TARGET_YEN 200,000` ÷ `RPM_SCENARIOS["長尺 お金 低"] 400` × 1000。
#: **写しではなく計算で出すこと**（片方だけ動くと、この道具が古い数字で断じます）。
def plan_views_month(target_yen: int = 200_000, rpm: int = 400) -> float:
    return target_yen * 1000 / rpm


def load_rows(path: Path | None = None) -> list[dict]:
    """`data/reach.jsonl` を読む。**無ければ空**（この道具は API を叩かない）。"""
    p = path or STORE
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def dedupe(rows: list[dict]) -> list[dict]:
    """同じ `(date, video_id)` は**最後に積んだ行**を残す。

    報告は日ごとに作り直されることがあり、`reach.py` は追記しかしません。
    **積み直した日が二重に数えられる**ので、読む側で潰します。
    """
    keep: dict[tuple[str, str], dict] = {}
    for r in rows:
        keep[(str(r.get("date", "")), str(r.get("video_id", "")))] = r
    return list(keep.values())


def measured_long_ids(forms_path: Path | None = None) -> set[str]:
    """**YouTube 自身が長尺と数えた動画ID**（`data/video_forms.json`）。

    書くのは `src/rpm_mix.py --record`（Analytics の `creatorContentType` を
    `video` べつに1回引くだけ）。**ここでは API を叩きません** ——
    この道具の約束は「積んであるものを読むだけ」だからです。

    **無ければ空**を返します。呼ぶ側（`long_ids`）が `pairs.yaml` と足すので、
    控えがまだ無い機械でも、いままでと同じ答えになります。
    """
    p = forms_path or FORMS
    if not p.exists():
        return set()
    try:
        raw = json.loads(p.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        return set()
    forms = raw.get("forms") or {}
    return {vid for vid, form in forms.items() if form == "長尺"}


def built_long_ids(path: Path | None = None) -> set[str]:
    """**この機械が「長尺として作った」と書き残した動画ID**（`data/batch_runs.jsonl`）。

    ## なぜ要るか（2026-08-26 に足した。**同じ帳面の7件目の同じ穴**）

    `long_ids()` は「**YouTube が長尺と数えた本**」を正本にしています。
    正しいのですが、**その名簿に載るのは、公開されて再生の付いた本だけ**です。
    だから **これから公開する本は、1本も入りません。**

    そのせいで `publishes_per_day()` が数えているのは
    「その日に公開した長尺のうち、**もう分類が終わったもの**」で、
    **公開日の本数そのものではありません**。実測（2026-08-26）:

        08/21 の長尺の公開   `long_ids()` だけ **5本** ／ 作った帳面と足すと **7本**
        公開1本あたりの面    **396.8回** → **248.0回**（**60% 上振れていた**）

    **上振れの向きが悪い。** `per_publish` は「公開を止めていた日を分母から外す」
    ために置いた数で、**段2 の面が足りているかの判断に直に入ります。**
    分母（公開本数）が小さいほど「1本あたりよく回っている」と出るので、
    **測り漏らすほど、面は足りているように見えます。**

    ## 混ざらないことは実測で確かめました

    `long: true` で作った 43本 のうち、YouTube が**ショートと数えた本は 0本**
    （`data/video_forms.json` と突き合わせ・2026-08-26）。逆に、
    測った長尺 12本 のうち 7本 はこの帳面より古く、載っていません。
    **どちらの穴も、足せば塞がります**（`long_ids()` の docstring と同じ形）。

    **覆る条件**: `long: true` で作った本が、YouTube にショートと数えられた
    （`data/video_forms.json` に「ショート」で載る）ことが1本でもあったら、
    ここは足し算ではなく突き合わせに変えること。
    """
    p = path or BATCH_RUNS
    out: set[str] = set()
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not row.get("long"):
            continue
        for res in row.get("results") or []:
            vid = res.get("video_id")
            if vid:
                out.add(str(vid))
    return out


def long_ids(pairs_path: Path | None = None,
             forms_path: Path | None = None,
             batch_path: Path | None = None) -> set[str]:
    """長尺の動画ID ＝ **測った控え ∪ `config/pairs.yaml`**。

    ## なぜ足すのか（2026-08-24 に直した。**天井の分母が半分だった**）

    ここは長らく `config/pairs.yaml` **だけ**を読んでいました。ところが
    あの表は「**ショート → 同じ題材の長尺**」の対応表で、
    ファイルの頭にこう書いてあります —— 「**同じ題材の公開済み長尺が
    あるものだけ**」。つまり**対になっていない長尺は、初めから入りません。**

    実測（2026-08-24・Analytics の `creatorContentType`）:

        `pairs.yaml` が名指しする長尺   **6本**
        YouTube が長尺と数えた本        **12本**（直近90日に再生のあったもの）

    そして `src/rpm_mix.surface_ceiling()` は、この集合で
    **長尺のインプレッション（面）**を数え、それが `scripts/eta.py` の
    段2 の合格点を決めています ——

        [!] いまの面（長尺のインプレッション 37.6回/日）は、CTR 100% でも 38回/日。
            合格点の 187回/日 に **5.0倍 足りません**

    **その 37.6 が、半分の本で数えた数でした。**（足すと 42.8回/日 ＝ +13.9%）

    **もっと悪いのは向きのほうです。** `rpm_mix` は自分でこう印字します ——
    「**長尺を出せば面が増え、次の回の測り直しでこの天井は上がります**」。
    `pairs.yaml` は**手で書く表**なので、新しく出した長尺は入りません。
    **出しても天井が動かない** ＝ 腕 `rpm` を引いた回が、
    自分の効きを測れない形になっていました。

    **控えのほうを正本にしないのは**、再生が0本の長尺を Analytics が
    返さないからです（実測 `SSI1MVb12Ng`）。**足すと、どちらの穴も塞がります。**
    """
    out = measured_long_ids(forms_path)
    p = pairs_path or PAIRS
    if p.exists():
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out |= set(dict(raw.get("pairs", {})).values())
    # **作った帳面も足す**（2026-08-26。`built_long_ids()` に実測）。
    #     測った控えは「公開されて再生の付いた本」しか持たないので、
    #     **これから公開する本が1本も入りません** —— `publishes_per_day()` が
    #     公開日の本数を 5/7本 に取り違えていました。
    #     **足したぶん、長尺の面は 3,435 → 3,683回 に増えます**（ショートから移る）。
    #     保存済みの点との段差はここです。**向きは「より正しい側」**で、
    #     08/22 以降の最大の1日は 337 → 492回（`config/hypotheses.yaml` の
    #     09/05 の前提が見ている 643回 の線は、どちらでも越えません）。
    out |= built_long_ids(batch_path)
    return out


def _ledger_by_id(ledger_path: Path | None = None) -> dict[str, dict]:
    """`video_id` → 控えの行。**同じIDが複数行にあるときは後の行が勝ちます。**

    `data/uploaded.jsonl` は追記だけの帳面で、`scripts/reschedule.py` が
    予約を動かすと**同じ本が別の `at` でもう1行**入ります。だから
    「いま何日に何本 置いてあるか」を数える側は、**行ではなく id で**数えます
    （規則の出どころは `src/day_cap._long_by_duration()`「後の行が勝ちます」）。

    **数え直しの実測は `publishes_per_day()` の節**にあります。
    """
    out: dict[str, dict] = {}
    p = ledger_path or LEDGER
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid = row.get("video_id")
        if vid:
            out[str(vid)] = row
    return out


def publishes_per_day(longs: set[str] | None = None,
                      ledger_path: Path | None = None) -> dict[str, int]:
    """**その日に公開した長尺の本数**（`YYYYMMDD` → 本数）。

    ## なぜ要るか（2026-08-26 に足した。**この帳面の6件目の同じ穴**）

    `BURST_SHARE` の註が、この帳面でいちばん大事なことを既に書いています ——

    > 08/21 の 1,285回 のうち **1,276回（99.3%）が、その日に公開した5本**に
    > 付いています。…長尺の面は「立っている面」ではなく、**公開日の立ち上がりだけ**です。

    **そこまで分かったうえで、次の行が「続いている量」を1日あたりで測っています。**
    直近7日の中央値 **8.0回/日** で、`scripts/eta.py` はそれを読んで
    「**22.4倍 足りません。足りないのはインプレッションで、サムネと題（CTR）では
    動きません**」と印字します。

    **その7日のうち、長尺を1本でも公開した日は1日だけです**（08/21）。
    残り6日は**公開が0本**で、面が立ち上がる元がありません。
    **中央値は、その6日のほうを拾います。**

    これは `summary()` の docstring が書いている穴と**同じ形の、1段 下**です ——
    あちらは「最初の20日は面そのものが存在しない日（長尺の公開前）で、
    平均はそれを分母に数えていた」。**こちらは、公開の止まっていた日を
    『続いている量』の分母に数えています。**

    面が公開で立つなら、続く量を決めるのは**カレンダーではなく公開の本数**です。
    だから、この関数が返す本数で割った `per_publish` を一緒に出します。

    **控えの `at`（予約時刻）から数えます。** `at` の無い本（2026-08-16 より前に
    公開したぶん）は数えられないので、**古い窓では本数が下振れします** ——
    直近の窓（`RECENT_DAYS`）でだけ使うこと。

    ## **1行 ＝ 1本ではありません**（2026-08-30・最適化の回。**実測で見つけた**）

    ここは長らく `out[day] += 1` を**行ごと**に撃っていました。
    `data/uploaded.jsonl` は**追記だけの帳面**なので、同じ `video_id` が
    何度も出ます —— 実測（この回に数えた・全 798行）:

        distinct `video_id`   **683**（＝ 余分な行 **115**）
        同じ行がそのまま2回以上   **81行**
        `at` の違う行を持つ id     **34件**（`reschedule.py` で動かした本）

    後者が効きます。**予約を動かした本は、古い日と新しい日の両方で数えられます。**
    実測（この回・`publishes_per_day()` の返りをそのまま比べた）:

        これから7日     行で数える **8.43本/日**  ／  id で数える **4.29本/日**（**1.97倍**）
        全部の日        行で数える   191本      ／  id で数える   122本（**1.57倍**）
        いちばん外れた日 20260906  行 **14** ／ 実際 **3**（**4.7倍**）

    **この関数の返りは2か所へ入ります。**`surface_forecast()` が
    「これから先の面 ＝ 公開1本あたり × 本数/日」で**掛け**、
    `summary()` 側の `per_publish` は「面 ÷ 本数」で**割り**ます。
    だから `scripts/eta.py` の段2 に出ていた
    「公開1本あたり 274.8回 × 長尺 **7.86本/日** ＝ 面 2,159回/日」は、
    **分子が約2倍、1本あたりが約1.6分の1**でした。

    **同じ帳面の他の読み手は、もうこの規則で読んでいます** ——
    `src/day_cap._long_by_duration()`「**後の行が勝ちます**」／
    `src/build_perf.ledger()`／`src/judgeable._publish_by_topic`／
    `scripts/deadline_check.py`。**ここだけ合流していませんでした**
    （`day_cap` が 2026-08-30 に合流したのと同じ形の、1つ隣）。

    **覆る条件**: 控えが「1行 ＝ 1本」になったら（追記をやめて上書きにしたら、
    または `video_id` の無い行を数える必要が出たら）、この節ごと畳むこと。
    検査は `tests/test_publishes_per_day_dedup.py`。
    """
    longs = long_ids() if longs is None else longs
    out: dict[str, int] = {}
    for vid, row in _ledger_by_id(ledger_path).items():
        at = row.get("at")
        if not at or vid not in longs:
            continue
        # ---- **作り置きは供給ではありません**（規則2・2026-08-31 のオーナー原文
        #      「使わなければ良いだけ前提にも再利用もしない」の2つ目）。
        #      ここは `surface_forecast()` が「これから先の面」を掛ける分母 ＝
        #      **この行を落とさないと、外して非公開にする本で面が立ちます。**
        #      落とすのは **未来の予約 かつ 規則より前に作った本**だけで、
        #      公開済み（実績）と、規則の下で作る本は残ります。
        #      判定は `src.house_rule.is_stockpile()` の1か所です（写さないこと）。
        if house_rule.is_stockpile(row):
            continue
        day = str(at)[:10].replace("-", "")
        out[day] = out.get(day, 0) + 1
    return out


def surface_forecast(sm: dict, pubs: dict[str, int] | None = None,
                     days: int = RECENT_DAYS,
                     today: str | None = None,
                     make_per_day: float | None = None,
                     slots_per_day: int | None = None,
                     stock: int | None = None) -> dict | None:
    """**これから先の面（インプレッション/日）を、予約の長尺の本数から出す。**

    ## なぜ要るか（2026-08-26。**この帳面の8件目の同じ穴**）

    `per_day_sustained`（直近7日の中央値）は「**続いている量**」の名で、
    実際に測っているのは**カレンダーの1日あたり**です。ところが
    `publishes_per_day()` の docstring が既にこう書いています ——

    > 面が公開で立つなら、続く量を決めるのは**カレンダーではなく公開の本数**です。

    そこまで書いたうえで、`scripts/eta.py` の段2 は中央値の **17.0回/日** を読み、
    「**10.5倍 足りません。足りないのはインプレッションで、サムネと題では
    動きません**」と印字していました。**その7日のうち5日は長尺の公開が0本**です。
    公開が0本の日の面を「続いている量」と呼ぶと、**測っているのは
    「公開を止めたら面はいくつか」**であって、段2 の問い
    （「門2a を 450日 かけて開けられるか」）の答えではありません。

    ## 何を返すか

    **予約は控えに入っています**（`data/uploaded.jsonl` の `at`）。
    だから「これから N日 で長尺を何本 公開する予定か」は、API を1単位も
    使わずに数えられます。面はそこから出します:

        面（回/日） ＝ 公開1本あたり `per_publish` × これからの公開 本/日

    実測（2026-08-26）: `per_publish` **248.0回** × これから7日の **2.43本/日**
    ＝ **603回/日**（段2 の合格点 178回/日 の **3.4倍**）。
    **同じ帳面の中央値は 17.0回/日** —— どちらも正しく、**問いが別**です。

    ## いちばん大事なのは `dry_days` のほう

    予約を日ごとに数えると、**09/08〜09/20 の 13日 が長尺 0本**でした
    （2026-08-26 の実測）。面が公開で立つ以上、**そこで面は 08/15〜08/20 と
    同じ 4〜17回/日 へ落ちます。** 「面が足りない」のではなく
    **「予定表に穴がある」**で、直す先はサムネでも題でもありません。

    **返り**（測れなければ `None`。回を止めない・推測で埋めない）:

        per_publish       公開1本あたりの面（回）
        per_day_planned   これから `days` 日の見込み（回/日）
        pubs_per_day      これから `days` 日の長尺の公開（本/日）
        planned           その内訳（`YYYYMMDD` → 本）
        dry_days          これから60日で長尺の公開が0本の日（連なりの先頭から）
        dry_span          いちばん長い連なり `(始まり, 終わり, 日数)`
        dry_fill          **その穴は、作る速さで自然に埋まるか**（下）

    ## `dry_span` を「直せ」と読ませないこと（2026-08-26 夜に足した）

    上の註は「直す先はサムネでも題でもなく、**その 13日 に長尺を置くこと**」と
    書いていました。**それは、たいていの回で間違った手を指します。**

    予約の時刻を決めているのは `uploader.next_publish_at()` だけで、
    **その時刻で最初に空いている日**へ置きます ＝ **手前から順に埋まります。**
    だから未来の空き日は「穴」ではなく「**まだ順番が来ていない日**」で、
    作りつづけていれば、その日が来る前に頭が通過して埋まります。

    実測 2026-08-26（`data/uploaded.jsonl` の長尺 28本・全部 08/24 以降のアップ）::

        公開 08/29 [3.2 3.3 3.4 3.7日前]  …… 頭は 5本/日 で前へ進む
        公開 09/06 [10.9 11.7日前]
        公開 09/20〜10/10 [25〜45日前]     …… 1日1本だった頃の置き方の残り
        → 空いているのは **09/07〜09/19**（頭と、古い置き方の残りのあいだ）

    埋まるかどうかを決めるのは、**穴までの日数と、作る速さ**です::

        穴の手前にある空き枠  ＝ Σ max(0, 1日の枠 − その日の予約)
        埋まるまでの日数      ＝ 空き枠 ÷ 作る速さ（本/日）
        穴の日までの日数 より短ければ、**放っておいて埋まります**

    **足りないときに要るのは「その日に置くこと」ではなく、作る速さのほうです。**
    既にある本を後ろへ動かして穴を埋めると、判定が遅れるぶん**必ず損**します
    （`scripts/queue_lag.py` が数えているのと同じ日数）。

    `make_per_day` / `slots_per_day` を渡さなければ `dry_fill` は `None`
    （**測っていないことを、埋まる/埋まらないのどちらにも倒さない**）。
    """
    from datetime import date, timedelta

    long = (sm or {}).get("長尺") or {}
    per_pub = long.get("per_publish")
    if not per_pub or per_pub <= 0:
        return None
    pubs = publishes_per_day() if pubs is None else pubs
    start = date.fromisoformat(today) if today else date.today()
    horizon = [(start + timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]
    planned = {d: int(pubs.get(d, 0)) for d in horizon}
    n = sum(planned.values())
    # **穴を探すのは、予定表が続いているあいだだけ**（2026-08-26 に踏んだ）。
    #     控えの最後より先は「長尺が0本」ではなく「**まだ何も置いていない**」で、
    #     混ぜると必ずいちばん長い連なりがそこになります（実測 10/06〜10/24 の19日）。
    #     予約が切れていること自体は `status.py`「予約の先」が別に鳴らします。
    last = last_scheduled_day()
    far: list[str] = []
    for i in range(365):
        d = (start + timedelta(days=i)).strftime("%Y%m%d")
        if last and d > last:
            break
        far.append(d)
    dry: list[str] = [d for d in far if not pubs.get(d)]
    best: tuple[str, str, int] | None = None
    run: list[str] = []
    for d in far:
        if pubs.get(d):
            run = []
            continue
        run.append(d)
        if best is None or len(run) > best[2]:
            best = (run[0], run[-1], len(run))
    return {"per_publish": float(per_pub),
            "per_day_planned": float(per_pub) * n / len(horizon),
            "pubs_per_day": n / len(horizon),
            "planned": planned,
            "last_scheduled": last,
            "dry_days": dry,
            "dry_span": best,
            "dry_fill": dry_fill(best, pubs, make_per_day, slots_per_day,
                                 today=start, stock=stock)}


def dry_fill(span: tuple[str, str, int] | None,
             pubs: dict[str, int] | None,
             make_per_day: float | None,
             slots_per_day: int | None,
             today=None,
             stock: int | None = None) -> dict | None:
    """**その穴は、作る速さで自然に埋まるか。**（`surface_forecast` の説明を読むこと）

    返り（測れなければ `None` —— **どちらにも倒さない**）::

        open_slots   穴の手前にある空き枠（本）
        reach_days   その枠が埋まるまでの日数（＝ open_slots ÷ 作る速さ）
        gap_days     いまから穴の初日までの日数
        ok           reach_days <= gap_days（＝ 放っておいて埋まる）
        short_per_day 足りないとき、作る速さをいくつ上げれば間に合うか（本/日）
        bound        何が縛っているか（`"render"` ＝ 作る速さ ／ `"topics"` ＝ 題材）
        stock        いま在る長尺向けのテーマ（本）。渡されなければ `None`
        topics_needed        穴の手前を埋めるのに、あと何本の**新しい題材**が要るか
        topics_per_day_needed その本数を `gap_days` で割った、要る題材の速さ（本/日）

    ## `make_per_day` だけで見ると、必ず「埋まります」に倒れます（2026-08-29）

    **`make_per_day` は描画の速さで、題材の有無を1つも見ていません**
    （`eta.long_supply_per_day()` は `data/batch_runs.jsonl` の
    「作れた本」を数えます ＝ **題材が在った日の記録**）。
    実測 2026-08-29: 描画 **9.14本/日**・空き枠 17本 → `reach_days` **1.9日**、
    穴まで 15日 なので **`ok=True`**。同じ時刻に

        `src/supply.py`        長尺向けの在庫 **0本**
        `scripts/topic_forge.py --list`  7日ぶんで取れるのは最大 **0本**

    **描画は速いが、描くものが1本も無い状態**です。それでも
    `scripts/eta.py` は「**放っておいて埋まります／その日に置きにいかないこと**」
    と印字していました —— **4,000時間の門に入るのは長尺だけ**なので、
    これは門に直結した面について「手を出すな」と言っていたことになります。

    `eta._long_make_per_day()` の docstring は、この壊れ方を名指ししています ——
    「**願望で割ると『埋まります』と出て、実際には空のまま公開日が来ます**」。
    あちらが防いでいたのは `measured: False`（計画値へ落ちる枝）だけで、
    **実測なのに測っている段が違う**、この枝は素通りでした。

    ## だから、題材の側でも割ります

    `stock` を渡すと、**いま在る題材で埋められる本数**が上限になります::

        埋められる ＝ min(空き枠, 在庫)          ← 新しい題材を作らない場合
        要る新題材 ＝ max(0, 空き枠 − 在庫)

    **`stock` を渡さなければ、これまでと1文字も変わりません**
    （`bound` は `None`。測っていないことを、埋まる/埋まらないのどちらにも倒さない）。

    **`ok` は両方を通ったときだけ真**です。`stock` が足りなければ
    `bound="topics"` を返し、**直す先は描画ではなく `src/calc/` の節**になります
    （`scripts/topic_forge.py --list` の「(2) 既にある表に節を足して」）。

    覆る条件: 長尺が `s-` 以外の題以外からも作れるようになったら、
    `stock` の数え方（`src/supply.py` の `surfaces()["long"]["stock"]`）が
    先に外れます。`tests/test_reach_dry_fill.py` がそこを押さえています。
    """
    from datetime import date, timedelta

    if not span or not make_per_day or make_per_day <= 0 or not slots_per_day:
        return None
    start = today or date.today()
    try:
        first = date(int(span[0][:4]), int(span[0][4:6]), int(span[0][6:]))
    except ValueError:
        return None
    gap = (first - start).days
    if gap <= 0:
        return None
    pubs = pubs or {}
    open_slots = 0
    for i in range(gap):
        d = (start + timedelta(days=i)).strftime("%Y%m%d")
        open_slots += max(0, int(slots_per_day) - int(pubs.get(d, 0)))
    reach = open_slots / float(make_per_day)
    need = (open_slots / gap) if gap else None
    render_ok = reach <= gap
    out = {"open_slots": open_slots, "reach_days": reach, "gap_days": gap,
           "ok": render_ok, "make_per_day": float(make_per_day),
           "slots_per_day": int(slots_per_day),
           # **埋まる回でも、どこで割れるかを返すこと。** 「埋まります」だけだと
           #     次の回は作る速さを落としてよいと読みます（余裕は実測 1.9日 しかない）。
           "need_per_day": need,
           "short_per_day": (None if render_ok
                             else max(0.0, need - float(make_per_day))),
           "bound": None, "stock": None,
           "topics_needed": None, "topics_per_day_needed": None}
    if stock is None:
        # **測っていない側へ倒さない。** ここを `0` で埋めると、在庫を
        #     読めなかった回が全部「題材が無い」になります（docstring 参照）。
        if not render_ok:
            out["bound"] = "render"
        return out
    stock = max(0, int(stock))
    short_topics = max(0, open_slots - stock)
    out["stock"] = stock
    out["topics_needed"] = short_topics
    out["topics_per_day_needed"] = (short_topics / gap) if gap else None
    # **両方 通ったときだけ「埋まります」**。描画が速くても、描くものが無ければ
    #     公開日は空のまま来ます（2026-08-29 の実測: 描画 9.14本/日・在庫 0本）。
    out["ok"] = render_ok and short_topics == 0
    if not out["ok"]:
        # **縛っている側を名指しすること。** 「埋まりません」だけだと、
        #     次の回は既定の助言（＝作る速さを上げろ）へ行きます。
        out["bound"] = "topics" if short_topics > 0 else "render"
    return out


def last_scheduled_day(ledger_path: Path | None = None) -> str | None:
    """**控えに入っている最後の予約日**（`YYYYMMDD`）。無ければ `None`。

    形は問いません（長尺でもショートでも）。ここが要るのは
    「**予定表がどこまで続いているか**」だけで、その先の空白は
    「長尺を置いていない日」ではなく「まだ何も置いていない日」だからです。

    **`max` を取るので、動かした本の古い予約が末尾に化けます**
    （2026-08-30 に直した）。`reschedule.py` が本を前へ動かすと、控えには
    古い `at` の行が残ります。行ごとに `max` を取ると、**もう誰も居ない日**が
    「予約の先」になります —— 実測（この回）: 行で取ると **20261012**、
    id で取ると **20261009**（**3日 長く見えていた**）。
    予約が切れる日を早めに鳴らす側の数字なので、**長く見える向きが危ないほう**です。

    **覆る条件**: `publishes_per_day()` と同じ（控えが追記でなくなったら畳む）。
    """
    best: str | None = None
    for row in _ledger_by_id(ledger_path).values():
        at = row.get("at")
        if not at:
            continue
        day = str(at)[:10].replace("-", "")
        if len(day) == 8 and (best is None or day > best):
            best = day
    return best


def _imp(row: dict) -> float:
    try:
        return float(row.get("video_thumbnail_impressions") or 0)
    except (TypeError, ValueError):
        return 0.0


def _clicks(row: dict) -> float:
    """クリック数 ＝ インプレッション × CTR。**CTR の列は「割合」です。**

    2026-08-20 21:4x に実物で確かめました。`scripts/reach.py` は長らく
    **`/ 100` して**いましたが、この列は百分率ではありません:

        impressions 148 / ctr 0.0067567567567567571  ＝ **1/148**（クリック1）
        impressions 112 / ctr 0.0089285714285714281  ＝ **1/112**（クリック1）
        impressions   1 / ctr 1                      ＝ **1/1**（クリック1）

    **逆数がぴったり出ます。** 百分率なら 0.0067% ＝ 1万回に1回で、
    1本の動画に 148回しか見せていない日には出ようがない数です。
    裏取りがもう1つあります —— 2026-08-15 にオーナーが Studio の画面で読んだ
    **CTR 1.3%** は、この直し方でショートの実測（1.34%）と一致します
    （`/100` のままだと 0.013% で、100倍ずれます）。
    """
    try:
        return _imp(row) * float(row.get("video_thumbnail_impressions_ctr") or 0)
    except (TypeError, ValueError):
        return 0.0


def tail(rows: list[dict], days: int) -> list[dict]:
    """**直近 N 日ぶんだけ**返す（日付の実物で切る。今日から数えない）。

    平均は burst をならしてしまいます —— 長尺は 08/09 に 346回 見せられ、
    08/17 には 5回です。**段取りが乗るのは、いま見せられている量のほう。**
    """
    dates = sorted({str(r.get("date", "")) for r in rows if r.get("date")})[-days:]
    keep = set(dates)
    return [r for r in rows if str(r.get("date", "")) in keep]


def _median(vals: list[float]) -> float:
    """**並べて真ん中**。空なら 0.0（呼ぶ側で「測れていない」に落とすため）。"""
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def summary(rows: list[dict], longs: set[str],
            publishes: dict[str, int] | None = None) -> dict:
    """形べつに集計する。

    `publishes` は `{"YYYYMMDD": その日に公開した長尺の本数}`。
    省略すると控え（`data/uploaded.jsonl`）から数えます
    （`publishes_per_day()`。**なぜ本数で割るのかは、そちらの註**）。

    返り: `{"長尺": {...}, "ショート": {...}, "days": n, "dates": [...],
    "last_day": "20260821"}`。**`last_day` は「積んである最後の日」**で、
    今日ではありません（2026-08-24 に足した —— この帳面が4日ぶん止まったまま
    天井を作っていて、誰にも見えていませんでした）。
    **「ショート」は「長尺でないもの」**です（控えに無い本もこちらへ入れる ——
    分母を大きく見せる側に倒すため。長尺の側を大きく見せない）。

    ## `per_day` と `per_day_max` は、使い先が違います（2026-08-24 に分けた）

        per_day        全期間の平均。**いま出ている量**を言う（表示むき）
        per_day_max    いちばん大きかった1日。**天井**を言う（`surface_ceiling` むき）
        per_day_live   中身のある日だけの平均（立ち上がる前の 0日 を分母から外す）
        per_day_recent 直近 RECENT_DAYS 日の平均。**段取りが乗る量**（段2 むき）

    **この4つを取り違えると、答えが逆になります。** 2026-08-25 の実測:

        全期間の平均    73.0回/日   → 段2 の合格点 191回/日 に **2.6倍 足りない**
        直近7日の平均  190.6回/日   → 合格点と **ほぼ同じ（×1.0）**
        最大の1日    1,285.0回/日   → 合格点の **6.7倍**

    そして `scripts/eta.py` の段2 は、**最大の1日**を当てて
    「**面は足りています（6.7倍）** —— ここから先で効くのは CTR のほう」と
    印字していました。同じ回の `status.py` は同じ帳面から
    「**87倍 足りません。足りないのはインプレッションです**」と印字しています。
    **同じ帳面の読み手2つが、逆を向いていた**（この形は4件目）。
    段2 が問うているのは「450日 続けられるか」で、**38日でいちばん良かった1日は
    その答えになりません。** 天井（`rpm` が届きうるか）だけが最大の1日を使います。

    **平均を天井に使うと、天井が実測より下に出ます。** 実物（08/24）:
    38日の平均 **73.0回/日** に対し、最大の1日は **1,285回**（08/21・全期間の46%）。
    最初の20日は**面そのものが存在しない日**（長尺の公開前）で、平均はそれを分母に
    数えていました。**存在しなかった日を数えて上限を作っていた**ということです。
    この 73.0 が `rpm` の天井（¥287）→ 段4 の合格点（695,675回/月）→
    **「月20万には届きません」**まで、まっすぐ効いていました。
    """
    rows = dedupe(rows)
    dates = sorted({str(r.get("date", "")) for r in rows if r.get("date")})
    out: dict[str, dict] = {}
    per_day_of: dict[str, dict[str, float]] = {}
    for key in ("長尺", "ショート"):
        out[key] = {"impressions": 0.0, "clicks": 0.0, "videos": set()}
        per_day_of[key] = {d: 0.0 for d in dates}
    for r in rows:
        key = "長尺" if str(r.get("video_id")) in longs else "ショート"
        out[key]["impressions"] += _imp(r)
        out[key]["clicks"] += _clicks(r)
        out[key]["videos"].add(str(r.get("video_id")))
        d = str(r.get("date", ""))
        if d in per_day_of[key]:
            per_day_of[key][d] += _imp(r)
    days = len(dates)
    for key, v in out.items():
        v["videos"] = len(v["videos"])
        v["per_day"] = v["impressions"] / days if days else 0.0
        v["ctr"] = (v["clicks"] / v["impressions"] * 100) if v["impressions"] else 0.0
        # **いちばん大きかった1日**（2026-08-24 に足した）。`per_day` は平均で、
        # **天井の分母には使えません** —— 下の docstring 「天井は最大の1日で読む」。
        series = per_day_of[key]
        best = max(series.items(), key=lambda kv: kv[1], default=("", 0.0))
        v["per_day_max"] = best[1]
        v["per_day_max_on"] = best[0] or None
        v["per_day_series"] = series
        # 中身のある日だけの平均（面が立ち上がる前の 0日 を分母から外した数）
        live = [x for x in series.values() if x > 0]
        v["per_day_live"] = (sum(live) / len(live)) if live else 0.0
        v["live_days"] = len(live)
        # **いま続いている量**（直近 RECENT_DAYS 日の平均。2026-08-25 に足した）。
        #     上の `tail()` の docstring が「**段取りが乗るのは、いま見せられている
        #     量のほう**」と書いているのに、その数は `render()` の中で
        #     `summary(tail(rows, 7))` を組み直したときにしか出ませんでした。
        #     **`summary()` の返りだけを持って歩く呼び側（`rpm_mix.surface_ceiling`
        #     → `scripts/eta.py`）からは、平均か最大の2つしか見えていません。**
        #     どちらも段取りの分母には使えない数です（片方は存在しなかった日を
        #     数え、片方は38日でいちばん良かった1日）。ここで一緒に返します。
        recent = dates[-RECENT_DAYS:]
        v["per_day_recent"] = (
            (sum(series[d] for d in recent) / len(recent)) if recent else 0.0)
        v["recent_days"] = len(recent)
        # **その平均を、1日が丸ごと作っていないか**（2026-08-26 に足した。
        #     `BURST_SHARE` の docstring に実測）。**上の平均は残します** ——
        #     保存済みの点と比べられなくなるため。判断に使うのは下の
        #     `per_day_sustained` のほうです。
        vals = sorted(series[d] for d in recent)
        total_recent = sum(vals)
        top = vals[-1] if vals else 0.0
        v["per_day_recent_top"] = top
        v["per_day_recent_top_share"] = (top / total_recent) if total_recent else 0.0
        v["per_day_recent_median"] = _median(vals)
        if v["per_day_recent_top_share"] >= BURST_SHARE and len(vals) >= 3:
            v["per_day_sustained"] = v["per_day_recent_median"]
            v["per_day_sustained_basis"] = (
                f"直近{len(vals)}日の中央値"
                f"（平均 {v['per_day_recent']:,.1f} は"
                f" 1日で {v['per_day_recent_top_share'] * 100:.0f}% ＝ 立ち上がりの burst）")
        else:
            v["per_day_sustained"] = v["per_day_recent"]
            v["per_day_sustained_basis"] = f"直近{len(vals)}日の平均"
        # **公開1本あたりの面**（2026-08-26 に足した。`publishes_per_day` の註）。
        # 上の `per_day_*` は全部カレンダーの1日あたりで、**公開が0本の日を
        # 分母に数えます。** 面が公開の立ち上がりで立つなら、そちらは
        # 「続いている量」ではなく「**公開を止めていた量**」です。
        # **上の数は1つも変えていません**（保存済みの点と比べられなくなるため）。
        # ここで足すのは読みのほうだけで、判断は呼び側がします。
        if key == "長尺":
            pubs = publishes_per_day(longs) if publishes is None else publishes
            n_pub = sum(pubs.get(d, 0) for d in recent)
            v["recent_publishes"] = n_pub
            v["recent_publish_days"] = sum(1 for d in recent if pubs.get(d, 0))
            v["recent_zero_publish_days"] = len(recent) - v["recent_publish_days"]
            v["per_publish"] = (
                (sum(series[d] for d in recent) / n_pub) if n_pub else None)
            if v["recent_zero_publish_days"]:
                v["per_day_sustained_basis"] += (
                    f"。**この{len(recent)}日のうち"
                    f"{v['recent_zero_publish_days']}日は長尺を1本も公開していません**"
                    + (f"（公開1本あたりでは {v['per_publish']:,.1f}回"
                       f" ／ 公開 {n_pub}本）" if n_pub else "（公開 0本）"))
    return {"長尺": out["長尺"], "ショート": out["ショート"], "days": days,
            "dates": dates, "last_day": dates[-1] if dates else None}


def gap(sm: dict, need_views_month: float | None = None) -> dict:
    """**長尺の面が、段4の要求に対して何倍足りないか。**

    上限は「**CTR 100%**」で置きます（サムネと題を極限まで直した先）。
    ここでも足りないなら、**直す先はサムネではなく面そのもの**です。
    """
    need = plan_views_month() if need_views_month is None else need_views_month
    per_day = sm["長尺"]["per_day"]
    ceiling_month = per_day * 30            # CTR 100% の上限
    now_month = ceiling_month * sm["長尺"]["ctr"] / 100
    return {
        "need_views_month": need,
        "impressions_per_day": per_day,
        "ceiling_views_month": ceiling_month,
        "now_views_month": now_month,
        "short_by": (need / ceiling_month) if ceiling_month else float("inf"),
    }


def render(rows: list[dict], longs: set[str] | None = None) -> str:
    """毎回の状態に出す短い節（**6行**）。**判断に使うのは直近のほう。**"""
    longs = long_ids() if longs is None else longs
    rows = dedupe(rows)
    sm = summary(rows, longs)
    if not sm["days"]:
        return ("=== サムネを見せた面（Reporting API）===\n"
                "  **まだ1行もありません。** `python scripts/reach.py` を叩くこと"
                "（ジョブが無ければ `--setup`）。")
    rc = summary(tail(rows, RECENT_DAYS), longs)
    g = gap(rc)
    lines = [
        "=== サムネを見せた面（Reporting API・**ショートのフィードは入りません**）===",
        f"  実測 {sm['days']}日ぶん（{sm['dates'][0]}〜{sm['dates'][-1]}）"
        f"／ 直近 {rc['days']}日で見ます",
        f"  ショート  全期間 {sm['ショート']['impressions']:>7,.0f}回"
        f"  CTR {sm['ショート']['ctr']:.2f}%"
        f"  ／ 直近 **1日 {rc['ショート']['per_day']:.1f}回**"
        f"  CTR {rc['ショート']['ctr']:.2f}%",
        f"  長尺      全期間 {sm['長尺']['impressions']:>7,.0f}回"
        f"  CTR {sm['長尺']['ctr']:.2f}%"
        f"  ／ 直近 **1日 {rc['長尺']['per_day']:.1f}回**"
        f"  CTR {rc['長尺']['ctr']:.2f}%",
    ]
    if g["short_by"] == float("inf") or g["short_by"] > 1:
        lines += [
            f"  [!] 段4は長尺で **月 {g['need_views_month']:,.0f}再生** を立てています。"
            f"いまの面は **CTR 100% でも月 {g['ceiling_views_month']:,.0f}回**"
            f" ＝ **{g['short_by']:,.0f}倍 足りません**",
            "      **段4 に対しては、足りないのはインプレッションです。**"
            "サムネと題（CTR）をいくら直しても、この面は動きません",
            # **どの合格点に対して言っているかを、同じ行に書くこと**（2026-08-27）。
            #     ここは長らく「**足りないのはインプレッションです**」と
            #     **無条件の断言**で終わっていました。同じ回の `scripts/eta.py` は
            #     段2（門2a・450日）の合格点に対して
            #     「**面は足りています（1.8倍）** —— 効くのは CTR のほう」と印字しており、
            #     **2つの道具が、同じ帳面から次に引く腕を正反対に名指し**していました
            #     （2026-08-27 の回が 25分 使って突き合わせた。「同じ帳面の読み手2つが
            #      逆を向く」の5件目）。**どちらも自分の問いには正しい** ——
            #     段4 は 月20万円（500,000回/月）、段2 は 門2a（4,000時間）で、
            #     **合格点が桁で違います。**
            #     **印字が問いを名乗らないと、読む側は片方だけを持って帰ります。**
            "      （**段2（門2a・4,000時間）の合格点は桁が下で、そちらでは"
            "『面は足りている・効くのは CTR』と出ます** —— "
            "`scripts/eta.py` の段2 の行。**どちらも正しく、比べている合格点が別です**）",
        ]
    else:
        lines.append("  段4 に対しては、面は足りています。"
                     "**足りないなら CTR のほう**（サムネと題）")
    return "\n".join(lines)
