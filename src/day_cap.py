"""**1日に何本まで「再生される」か。**（API は 0 単位。読むのは `data/views.jsonl` だけ）

## なぜ要るか（2026-08-21 16:2x に測って足した）

`src/supply.py` は **「25本/日 を作れるか」**を測っています。ここが測るのは別の所で、
**「作って出したとして、その25本に再生が付くか」**です。**付きませんでした。**

実測（`data/views.jsonl`・公開から6時間以上たった読み・長尺は最初から0なので除く）:

    2026-08-20 は 25本 公開した。**11本目から先は 25本中 15本が 0〜3再生**
      #9=352  #10=1111  |  #11=0  #12=0  #13=1  #14=0 … #25=2

**これは「時刻が遅いから」ではありません。** 切り分けが1組あります:

    08/16 の 14時 = その日の **#4** → **1361再生**
    08/20 の 14時 = その日の **#12** → **0再生**
    08/20 の 13時台に3本: #9=352 / #10=1111 / **#11=0**（同じ日・同じ時刻帯・同じ齢）

**同じ時刻でも、その日の何本目かで 1361 と 0 に割れます。**
だから軸は時刻ではなく **その日の通し番号** です。

## **何本目か、ではなく何本か**（2026-08-24 に測り直した。17本 → 10本）

上の切り分けは正しいのですが、**数え方が「生きたいちばん後ろの番号」でした。**
公開の順番と、YouTube が配信する順番は**同じではありません。** 実測（08/21・32本）:

    00:00 280  00:15   1  00:30 184  00:45   5  01:00 996  01:15  1  01:30 1066
    02:00 367  02:15   0  02:30 314  02:45   0  03:00 1045  03:15 13  03:30 1097
    03:45   3  04:00 1075  04:30 190  |  05:00 以降の15本は全部 0〜5

**生きたのは :00 と :30 の 10本ちょうど**で、そのあいだに挟まれた :15/:45 の7本は
死んでいます。**番号で数えると「#17 まで生きた」＝ 上限17本**になりますが、
**実際に再生が付いた本数は 10本**です。08/20・08/22 も 25本 出して **ちょうど 10本**。

    08/20  25本 → 生きた 10本      08/21  32本 → 生きた 10本      08/22  25本 → 生きた 10本
    08/19   8本 → 生きた  8本（上限より少ない日。上限の証拠にはならない）

**3日とも 10本で一致**しているので、上限は**その日の本数**であって順番ではありません。
17本 のままだと、段1 が **1.7倍 楽観**になります（`scripts/eta.py`）。

**覆る条件**: 上限より多く出した日に、**生きた本数が 10本を超えたら**上へ動きます
（`floor` が自動で追います。定数ではありません）。

## 何を壊していたか

`scripts/eta.py` の段1 は

    days_subs_at[n] = 残りの登録者 / (n × 1本あたり再生 × 登録率)

で、**n を増やせば増やすだけ再生が増える**と読んでいました。実測は
**n が上限を超えたぶんは 0 再生**なので、25本/日 の段1 は **2.5倍 楽観**です。

## 覆る条件（**上限は測り直せます**）

上限を上へ動かせるのは、**「上限より多く出した日」に、上限より後ろの本が
再生を取ったとき**だけです（`floor` が下から、`collapse` が上から挟みます）。
1日 10本しか出していない日は、**上限が10であることの証拠になりません** ——
崩れ方を観測していないので、この道具はそういう日から上限を読みません。

**上限が YouTube 側の1日あたりの押し出し量なら、登録者が増えると上がるはず**です。
そのときは崩れる番号が後ろへ動き、ここが自動で追います（定数ではありません）。
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"
FORMS = ROOT / "data" / "video_forms.json"
UPLOADED = ROOT / "data" / "uploaded.jsonl"

#: **長尺と呼ぶ尺の下限（秒）。** `scripts/eta.LONG_FORM_SECONDS` と同じ数です。
#: ショートの上限は60秒、この作りの長尺は4分以上（`src/verify.py`）なので、
#: あいだの180秒に置いています。**実測でこの帯に本は1つもありません**
#: （`_long_by_duration()` の「二山」の節）。
LONG_MIN_SECONDS = 180.0

JST = dt.timezone(dt.timedelta(hours=9))

MIN_AGE_H = 6.0        # これより若い読みは「まだ伸びていない」と見分けが付かない

# **長尺だけは 6時間 では数えられません**（2026-08-26 に測って足した）。
# このファイルはずっとそう書いていました ——「長尺は数日かけて付くので、
# これは崩れの証拠になりません。**測るなら 7日 以上の齢で数え直すこと**」——
# **ですが `long_form()` は 6時間 の読みを返したままでした。**
#
# 実測（同じ生データを、読みの齢だけ変えて数え直した）:
#
#     2026-08-21（**長尺を5本 出した唯一の日**）
#       齢  6時間 → 再生が付いたのは **1/5本**  [0, 0, 0, 2, 0]
#       齢 24時間 → **5/5本**                   [3, 13, 1, 5, 1]
#       齢 48時間 → **5/5本**                   [5, 1, 3, 15, 1]
#
# **「1/5本」は崩れではなく、読みが早すぎただけです。**
# 6時間 で数えているかぎり、長尺は何本 出しても「ほぼ全部 死んだ」に見えます。
# **ショート側は齢を変えても動きません**（6/12/24/48/72時間 のどれで数えても
# `cap=10 floor=10 collapse=11`）。**ずれるのは長尺だけ**です。
LONG_MIN_AGE_H = 48.0  # 長尺を数えるときの齢。24時間で足りるが、余裕を取る
DEAD_SHARE = 0.05      # その日の上位3本の中央値の 5% 未満なら「再生が付いていない」
MIN_PER_DAY = 3        # 崩れを見るのに要る最低の本数
MIN_TOP_VIEWS = 50     # その日の上位3本の中央値がこれ未満なら、面に載っていない日
FALLBACK = 10          # 読みが足りないときの既定（**この日の実測そのもの**）

LONG_FORM = "長尺"     # `data/video_forms.json` の値（`youtubeAnalytics: creatorContentType`）


# ---------------------------------------------------------------------------
# **この上限は「ショートの面」のものです**（2026-08-26 に、実物を数えて足した）
#
# 冒頭の実測は「**長尺は最初から0なので除く**」と書いていました。
# **除いていませんでした。** `_readings` は `data/views.jsonl` を丸ごと読み、
# `measure` は 0再生 の本を **`n_dead`（＝上限の証拠）**として数えます。
# つまり長尺は、除かれるどころか **ショートの上限を押し下げる側**に入っていました。
#
# 実測（`data/video_forms.json` と突き合わせた）:
#
#     2026-08-21  32本 → 生きた10 / 死んだ22 の**うち5本が長尺**
#                 （-NbX_FMzAg0 0再生 ／ Qb-m7s1T5gk 0 ／ WuTf0Z-tRJc 0 ／
#                   _Mz5rg6jQ_A 0 ／ UHo79-HCOWo 2）
#     2026-08-04   7本 → 死んだ5 の**うち1本が長尺**（qm-w6nVwMhY 1再生）
#
# **いまは `cap` の値を変えません**（10本のまま）。長尺は全部「死んだ」側なので
# `n_alive` が動かず、`collapse` も 11 のまま。**ですが無害なのは偶然です** ——
# ショートが全部生きた日に長尺が1本混ざれば、その日が「崩れた日」に化けて
# 上限を1本ぶん下げます。**そうなってから気づく形にしないこと。**
#
# **もっと効くのは、この上限が何の上限かのほうです。** `scripts/eta.py` の
# `physical_caps` は、ここを **`density` の腕の天井**として使っています。
# ところが長尺はショートの面を1枠も食いません（`SHORTS_FEED` の外）。
# **4,000時間の門に入るのは長尺だけ**なので、「密度は天井 ×1.00 ＝ 引き代なし」は
# **唯一開いている門について、何も言っていません。** `long_form()` を別に出すのは
# そのためです。**混ぜて1つの数にしないこと。**
# ---------------------------------------------------------------------------


def forms(path: pathlib.Path | None = None) -> dict[str, str]:
    """id → 形（`長尺` / `ショート`）。**読めなければ空**（回は止めない）。"""
    p = path or FORMS
    if not p.exists():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    got = doc.get("forms")
    return {str(k): str(v) for k, v in got.items()} if isinstance(got, dict) else {}


def _long_by_duration(path: pathlib.Path | None = None) -> set[str]:
    """**控えの尺で見た長尺**（`data/uploaded.jsonl` の `duration_s`）。

    ## なぜ要るか（2026-08-30・最適化の回。**実測で見つけた**）

    `forms()` が読む `data/video_forms.json` は Analytics の
    `creatorContentType` です。**あれは公開して再生の付いた本にしか付きません。**
    だから**予約ぶんの長尺は、1本も入っていません** —— 実測（この回に撃った）:

        `forms()` が「長尺」と言う本            **18本**
        控えの `duration_s` が 180秒 以上の本   **98本**
        **重なり                                  1本**

    **予約の側こそ、この関数の相手**です。`live_ids()` は控えの予約行も
    受け取るので（`ab_split.published()`）、そこを見分けられないと
    **長尺がショートの帯の枠を取ったことに気づけません。**
    実測（同じ回・控えと公開済み 629本）:

        `forms()` 由来の 18本 で見る    帯の枠を取っている長尺 **0本** ／ 落ちたショート **0本**
        控えの尺で見る                  帯の枠を取っている長尺 **16本** ／ 落ちたショート **7本**

    **`tests/test_live_ids_long_form.py` が「落ちたら直す回」と書いていた
    その条件は、すでに満たされていました。** 検査が気づけなかったのは、
    **検査も `_long_ids()` を使っていた**からです ——
    見張りと見張られる側が、同じ目で見ていました。

    ## 尺で割ってよい理由（この回に測った）

    控えの `duration_s`（178本）に、**55秒 と 260秒 のあいだの本は 1本もありません。**
    分布が二山なので、180秒 の境目はどちらの山も切りません。
    `forms()` と重なる 1本 でも、両者の答えは一致しています（食い違い 0件）。

    **この repo は既にこの読み方に寄せてあります** ——
    `src/judgeable._short_topics()`／`src/ab_split._shorts_only()`／
    `src/watches._durations()` は、どれも控えの `duration_s` で形を割ります
    （2026-08-27 の結論「`judgeable` のほうが正しい」）。
    **`day_cap` だけが、そこに合流していませんでした。**

    **後の行が勝ちます**（`published()` と同じ規則。撃ち直しで尺が変わる本のため）。

    **覆る条件**: ショートの上限が 3分 まで伸びたら（YouTube 側の仕様変更）、
    `LONG_MIN_SECONDS` を測り直すこと。**境目を跨ぐ本が出たら、上の「二山」も
    測り直すこと** —— そのときは尺だけでは割れません。
    """
    p = path or UPLOADED
    if not p.exists():
        return set()
    out: set[str] = set()
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    for line in lines:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid, sec = r.get("video_id"), r.get("duration_s")
        if not vid or sec is None:
            continue
        try:
            long_form = float(sec) >= LONG_MIN_SECONDS
        except (TypeError, ValueError):
            continue
        if long_form:
            out.add(str(vid))
        else:
            out.discard(str(vid))       # **後の行が勝ち**（撃ち直しで尺が変わる本）
    return out


def _long_ids(forms_path: pathlib.Path | None = None,
              uploaded_path: pathlib.Path | None = None) -> set[str]:
    """**形が分かっている長尺だけ**。不明は落としません（落とすと母集団が消えます）。

    出どころは2つ、**足し合わせます**（どちらも「分かっている」側）:

      1. `forms()`   —— Analytics の `creatorContentType`。**公開して再生の付いた本だけ**
      2. `_long_by_duration()` —— 控えの `duration_s`。**予約ぶんも入る**

    **1 だけでは予約が見えません**（重なりは実測 1本／18本 対 98本）。
    理由と実測は `_long_by_duration()` の docstring。
    """
    known = {v for v, f in forms(forms_path).items() if f == LONG_FORM}
    return known | _long_by_duration(uploaded_path)


#: `_readings()` の控え。鍵は（path・mtime・大きさ・齢の下限）。
#: **ファイルが変われば鍵が変わる**ので、古い数を返しません。
_READINGS_MEMO: dict[tuple, dict[str, tuple[dt.datetime, float, int]]] = {}
_READINGS_MEMO_MAX = 8


def _readings(path: pathlib.Path | None = None,
              min_age_h: float | None = None) -> dict[str, tuple[dt.datetime, float, int]]:
    """id → (公開時刻JST, 齢, 再生)。**齢は `min_age_h` にいちばん近いものを採ります。**

    既定は `MIN_AGE_H`（6時間）で、**これはショートの面の話**です。
    長尺は数日かけて付くので、**長尺を数えるときは `LONG_MIN_AGE_H` を渡すこと**
    （`long_form()` がそうしています。理由はそちらの docstring）。
    """
    min_age = MIN_AGE_H if min_age_h is None else min_age_h
    p = path or VIEWS
    if not p.exists():
        return {}
    # --- **同じファイルを、1回の走りで何十回も読み直さないこと**（2026-08-30 に測って足した）---
    #     実測（`python -m cProfile scripts/eta.py --reflect`・2026-08-30 06:2x）:
    #
    #         eta.py --reflect        65.8秒
    #           day_cap._readings     **201回・累計 40.8秒**（走り全体の 62%）
    #           day_cap.long_form     160回・累計 33.7秒（中身はほぼ上）
    #           json.loads          **5,286,452回**（＝ `data/views.jsonl` を 201回 読み直している）
    #
    #     **これは 2026-08-28 に `day_cap.cap()` で直したのと同じ形**です
    #     （`scripts/eta.py` の `_view_cap_per_day`。あのとき 4分 → 24秒 になった）。
    #     **あちらは memo を `eta.py` 側に置いた**ので、`_readings` を直に呼ぶ
    #     `long_form()` / `by_day()` / `day_total()` / `deep_short` には効いていません。
    #     **1か所で直すこと** —— 呼ぶ側ごとに memo を置くと、次に足された
    #     呼び口だけがまた 200回 読みます（それがこの 40秒 の由来です）。
    #
    #     **鍵にファイルの状態（mtime と大きさ）を入れます。** 走っている最中に
    #     `scripts/snapshot.py` が追記しても、次の呼びで読み直します ——
    #     **古い数を返すくらいなら、読み直すほうがいい。**
    #     **覆る条件**: 同じ mtime のまま中身が変わる積み方をしたら（例: 書き換え）
    #     ここは古い数を返します。`data/views.jsonl` は追記だけなので、いまは起きません。
    try:
        st = p.stat()
        key = (str(p), st.st_mtime_ns, st.st_size, float(min_age))
    except OSError:
        key = None
    if key is not None and key in _READINGS_MEMO:
        # **控えそのものを渡さないこと。** 呼ぶ側が触ると、次の呼びに漏れます
        #     （いまの呼び口は全部 `.items()` を回すだけですが、**次に足される
        #     呼び口はそうとは限りません**）。値は tuple なので浅い写しで足ります。
        return dict(_READINGS_MEMO[key])
    first: dict[str, dt.datetime] = {}
    best: dict[str, tuple[float, int]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        at = dt.datetime.fromisoformat(r["at"].replace("Z", "+00:00"))
        pub = at - dt.timedelta(hours=r["hours"])
        if r["id"] not in first or pub < first[r["id"]]:
            first[r["id"]] = pub
        if r["hours"] < min_age:
            continue
        cur = best.get(r["id"])
        # **いちばん若い読みを採ります**（伸びきる前で揃えたい。齢が散ると
        # 「後ろの本は若いだけ」という別の説明が残ります）
        if cur is None or r["hours"] < cur[0]:
            best[r["id"]] = (r["hours"], r["views"])
    out = {v: (first[v].astimezone(JST), h, n)
           for v, (h, n) in best.items() if v in first}
    if key is not None:
        # **際限なく積まないこと。** 鍵はファイルの状態 × 齢の下限なので、
        #     1回の走りで増えるのは高々数件（実測: 6h／24h／48h の3つ）ですが、
        #     追記のたびに古い鍵が残ります。**新しい順に少しだけ持つこと。**
        if len(_READINGS_MEMO) >= _READINGS_MEMO_MAX:
            _READINGS_MEMO.pop(next(iter(_READINGS_MEMO)))
        _READINGS_MEMO[key] = out
    return dict(out)


def by_day(path: pathlib.Path | None = None,
           forms_path: pathlib.Path | None = None,
           include_long: bool = False) -> dict[dt.date, list[tuple[str, int, float]]]:
    """公開日（JST）→ [(id, 再生, 齢)]。**公開の早い順**。

    **既定で長尺を外します**（この節の上の註）。ここが測っているのは
    **ショートの面の上限**で、長尺はその枠を1つも使いません。
    `include_long=True` は、外す前後を比べるとき用です。
    """
    skip = set() if include_long else _long_ids(forms_path)
    out: dict[dt.date, list] = collections.defaultdict(list)
    for vid, (pub, h, n) in _readings(path).items():
        if vid in skip:
            continue
        out[pub.date()].append((pub, vid, n, h))
    return {d: [(v, n, h) for _, v, n, h in sorted(rows)] for d, rows in out.items()}


def long_form(path: pathlib.Path | None = None,
              forms_path: pathlib.Path | None = None,
              min_age_h: float = LONG_MIN_AGE_H) -> dict:
    """**長尺の面は、1日に何本まで出せるのか。**

    `measure()` の 10本 は**ショートの上限**で、長尺には掛かりません。

    **2026-08-26 に、齢をそろえて数え直しました**（上の `LONG_MIN_AGE_H` の註）。
    それまでここは **6時間 の読み**を返していて、
    **長尺を5本 出した日を「1/5本しか付かなかった」と報告していました。**
    同じ日を 24時間 で数えると **5/5本** です。
    **崩れは1日も観測されていません。**

    そのせいで `docs/JOURNAL.md`（2026-08-26）にはこう書かれていました ——
    「**`--long` を既定にしてよいかは、まだ決まっていません。**
    長尺の面の上限は `measured: False` のままで、**1日に何本まで生きるか
    誰も測っていません**」。**面の側は、少なくとも 5本/日 までは空いています。**

    **ただし「だから長尺を増やせ」にはなりません。** 面が空いていることと、
    出す価値があることは別です —— 同じ齢（48時間）でそろえた1本あたり再生は
    **長尺 2.8回 対 ショート 666.8回 ＝ 1/238**（n=12/71）。
    `config/hypotheses.yaml` の閉じた前提にも同じ向きの実測があります
    （`rpm` ×256「同じ日の同じ本数で ショート256回 対 長尺1回」）。
    **面の広さではなく、1本あたりのほうが縛っています。**

    返り:
      per_day    長尺を出した日 → 本数
      most       1日に出した最大の本数（**これを超えた日がまだ無い**）
      alive      その最大の日に、再生が付いた本数
      age_h      数えた読みの齢（時間）
      collapsed  **その最大の日に、崩れ（出したのに付かない）があったか**
      measured   崩れを観測しているか（＝ `collapsed`）。**観測できて初めて上限が言える**
    """
    longs = _long_ids(forms_path)
    days: dict[dt.date, list[tuple[str, int]]] = collections.defaultdict(list)
    for vid, (pub, _h, n) in _readings(path, min_age_h).items():
        if vid in longs:
            days[pub.date()].append((vid, n))
    per_day = {d: len(rows) for d, rows in days.items()}
    most = max(per_day.values(), default=0)
    alive = 0
    for d, rows in days.items():
        if len(rows) == most:
            alive = max(alive, sum(1 for _, n in rows if n > 0))
    # **崩れと呼べるのは、いちばん多く出した日に「出したのに付かない」本が
    # 出たときだけ**です。1本ずつの日で 0再生 が出るのは、面の上限ではなく
    # **その本が外れた**だけ（`measure()` の `floor` と同じ考え方）。
    collapsed = most > 0 and alive < most
    return {"per_day": per_day, "most": most, "alive": alive,
            "age_h": min_age_h, "collapsed": collapsed, "measured": collapsed}


def long_form_lines(path: pathlib.Path | None = None,
                    forms_path: pathlib.Path | None = None) -> list[str]:
    """**長尺の面は、どこまで空いているか。**齢をそろえた数で毎回出す。"""
    m = long_form(path, forms_path)
    if not m["per_day"]:
        return ["  **長尺の面**: 読める長尺がまだありません（上限は未測定）"]
    # **見出しは `collapsed` で分けること**（2026-08-27 に直した）。
    #
    # ここは長らく「**{most}本/日 までは崩れていません**」を**無条件**で印字して
    # いました。`collapsed` が立った日に、この行は
    # 「**7本/日 までは崩れていません**（最大の日 **5/7本** が生存）」と出ます ——
    # **同じ行の中で、自分の言っていることを自分で否定しています。**
    # そのあいだ `batch_build._long_ring()` のほうは正しく `most - 1` へ落として
    # いました。**機構は正しく、読まれる側だけが偽**という形です
    # （`scripts/batch_build.live_ring()` の節と同じ形。今日3件目）。
    if m["collapsed"]:
        out = [
            f"  **長尺の面: {m['most']}本/日 で崩れました → 上限は"
            f" {max(1, m['most'] - 1)}本/日**"
            f"（齢 {m['age_h']:.0f}時間 でそろえた実測。"
            f"最大の日 {m['alive']}/{m['most']}本 しか生存していません）",
        ]
    else:
        out = [
            f"  **長尺の面: {m['most']}本/日 までは崩れていません**"
            f"（齢 {m['age_h']:.0f}時間 でそろえた実測。"
            f"最大の日 {m['alive']}/{m['most']}本 が生存）",
        ]
    out.append(
        "    **上の上限はショートの面のもので、長尺には掛かりません**"
        "（長尺は `SHORTS_FEED` の枠を1つも使わない）。")
    if not m["collapsed"]:
        out.append(
            f"    **上限そのものはまだ出ていません**（{m['most']}本/日 を超えた日が無い）。"
            "**`measured: False` は「面が狭い」ではなく「まだ広いほうの端を見ていない」**です。")
    out.append(
        "    **6時間の読みで数えないこと**（2026-08-26 に踏んだ）——"
        "同じ 08/21 の5本が、齢 6時間 では **1/5本**、24時間 では **5/5本** です。"
        "早く読むと、長尺は何本 出しても『ほぼ全部 死んだ』に見えます。")
    out.append(
        "    **ただし面が空いていることは、出す価値があることではありません** ——"
        "同じ齢でそろえた1本あたり再生は **長尺 対 ショート ＝ 1/238**"
        "（閉じた前提 `rpm` ×256 と同じ向き）。**縛っているのは1本あたりのほう**です。")
    return out


def measure(path: pathlib.Path | None = None,
            forms_path: pathlib.Path | None = None,
            include_long: bool = False) -> dict:
    """**上限を、崩れた日から読む。**

    返り:
      cap        1日に何本まで再生が付くか
      floor      「ここまでは付いた」と観測できている番号（下から）
      collapse   その `floor` より後ろで崩れた、いちばん小さい番号（無ければ None）
      days       証拠に使った日
      measured   `floor` より後ろの崩れを観測しているか（False なら `cap` は既定値）

    **1本ごとの不発と、上限とを分けています。** ある日の #3 から先が 0 でも、
    別の日に #10 が 1,111再生 を取っているなら、それは上限ではなく**その3本が
    外れた**だけです。上限だと言えるのは、**これまでに効いたいちばん後ろの番号
    （`floor`）より、さらに後ろで崩れたとき**だけ。
    """
    days = by_day(path, forms_path, include_long=include_long)
    qual: list[tuple[dt.date, list, float, int, int]] = []
    floor = 0
    for d, rows in sorted(days.items()):
        if len(rows) < MIN_PER_DAY:
            continue
        top = statistics.median(sorted((n for _, n, _ in rows), reverse=True)[:3])
        if top < MIN_TOP_VIEWS:
            continue                      # その日は面に載っていない。上限の話ではない
        line = top * DEAD_SHARE
        # **数えるのは「生きた本数」で、生きたいちばん後ろの番号ではありません**
        # （2026-08-24 に測り直した。理由はこのファイルの冒頭「何本目か、何本か」）。
        n_alive = sum(1 for _, n, _ in rows if n >= line)
        floor = max(floor, n_alive)
        qual.append((d, rows, line, n_alive, len(rows) - n_alive))

    probes: list[tuple[int, str]] = []
    for d, rows, line, n_alive, n_dead in qual:
        # **上限の証拠になるのは、「生きた本数が最良の日と同じで、なお死んだ本が
        # ある日」だけです。** 生きた本数が最良より少ない日は、上限ではなく
        # **その日の題材が外れた**日です（08/04 の7本で cap=2 と出た形）。
        if n_dead and n_alive >= floor:
            probes.append((n_alive + 1,
                           f"{d} {len(rows)}本→再生が付いたのは {n_alive}本"
                           f"（{n_dead}本が0）"))

    if probes:
        collapse = min(r for r, _ in probes)
        return {"cap": max(min(floor, collapse - 1), 1), "floor": floor,
                "collapse": collapse, "days": [t for _, t in probes[-3:]], "measured": True}
    return {"cap": max(FALLBACK, floor), "floor": floor, "collapse": None,
            "days": [], "measured": False}



# --- **「1日N本」と「時刻の壁」は、まだ切り分けられていません** ------------------
#
# 2026-08-24 に、上の 17→10 の測り直しと同じ生データを**公開時刻の側**から並べたら、
# 別の説明が同じ数字を出すことが分かりました。
#
#     08/20  生きた 09:00〜13:30（10本） ／ 13:59 以降は 12本とも 0〜3
#     08/21  生きた 08:59〜13:30（10本） ／ 14:00 以降は 15本とも 0〜5
#     08/22  生きた 09:00〜13:30（10本） ／ 14:00 以降は 15本とも 0〜5
#
# **「1日10本の予算」と「13:30 JST で閉じる窓」は、まったく同じ数字を出します。**
# このチャンネルは**一度も 08:59 より前に公開していない**（`batch_build --hour` の
# 既定が 9 だから）ので、**どちらなのかを区別する日が1日もありません。**
#
# **視聴者の時計では説明できません** —— 死んでいる 14:00〜21:00 JST は日本の視聴の
# ピーク帯です。20:00 に出した本が 1再生 なのに、13:30 の本が 203再生 を取っています。
#
# なぜ効くか: 窓のほうなら、**09:00 より前に置いたぶんは丸ごと上積み**になります
# （05:00 から 30分きざみなら 13:30 まで 18枠 ＝ いまの 1.8倍）。**作る本数は
# 1本も増えません。** 予算のほうなら、早く置いても後ろが死ぬだけで差し引き 0 です。
#
# **切り分ける実験**: 09:00 より前から公開する日を1日作り、その日の**生きた本数**を
# 数える。10本 を超えたら「窓」、10本 のままなら「予算」。
# 2026-08-27 に 05/06/07/08時 の4本を置いてあります（09:00〜13:30 の10本はそのまま）。


def _qual_days(path: pathlib.Path | None = None):
    """上限の証拠に使える日だけを (日, [(公開時刻JST, id, 再生)], 死線) で返す。"""
    out: dict[dt.date, list] = collections.defaultdict(list)
    for vid, (pub, _h, n) in _readings(path).items():
        out[pub.date()].append((pub, vid, n))
    for d in sorted(out):
        rows = sorted(out[d])
        if len(rows) < MIN_PER_DAY:
            continue
        top = statistics.median(sorted((n for _, _, n in rows), reverse=True)[:3])
        if top < MIN_TOP_VIEWS:
            continue
        yield d, rows, top * DEAD_SHARE


MIN_GAP_MIN = 30.0     # これより詰めて出した本は死ぬ（08/21 の :15/:45 が7本とも0）


def _spaced(times: list[dt.datetime], gap_min: float = MIN_GAP_MIN) -> list[dt.datetime]:
    """**間隔で落ちるぶんを先に落とす。** 前に残した本から `gap_min` 未満のものは捨てる。

    2026-08-21 の実測: 08:59〜13:30 に 17本 出して、生きたのは :00/:30 の **10本**。
    あいだの :15/:45 の7本は 0〜2再生。**間隔の効きは、上限の話とは別の軸**なので、
    2つのモデルを比べる前にここで揃えます（揃えないと、間隔で死んだ本が
    「窓のせいで死んだ」に見えます）。
    """
    kept: list[dt.datetime] = []
    for t in sorted(times):
        if not kept or (t - kept[-1]).total_seconds() / 60.0 >= gap_min - 1.0:
            kept.append(t)
    return kept


TIE_GAP_MIN = 1.0      # これ未満は「どちらが死んだか」を**測っていない**


def ties(times: list[dt.datetime], gap_min: float = TIE_GAP_MIN) -> list[list[dt.datetime]]:
    """**同じ分に入っている組**を返す（2本以上の塊だけ）。

    `_spaced()` は「詰めて出した2本のうち、**後ろが死んで前が生きる**」と読みます。
    それは 2026-08-21 の実測で確かめてあります —— :00/:30 の10本が生きて、
    あいだの :15/:45 の7本が 0〜2再生。**確かめてあるのは 15分 の間隔まで**です。

    **間隔0（同じ分）は、一度も測っていません。** 起こりうる読みが3つあり、
    どれも `_spaced()` の1つの答えには畳めません:

        前が生きて後ろが死ぬ   `_spaced()` の読み。**同分では未測定**
        両方とも死ぬ           同時押しがまとめて弾かれる
        両方とも生きる         YouTube が同分を区別していない

    **どれかに決められないあいだ、その日の死は上限のせいだと言えません。**
    """
    groups: list[list[dt.datetime]] = []
    cur: list[dt.datetime] = []
    for t in sorted(times):
        if cur and (t - cur[-1]).total_seconds() / 60.0 < gap_min:
            cur.append(t)
        else:
            if len(cur) > 1:
                groups.append(cur)
            cur = [t]
    if len(cur) > 1:
        groups.append(cur)
    return groups


DECIDE_GAP_MIN = 3     # 2つのモデルの予測がこれだけ離れていない日からは決めない


def split_power(times: list[dt.datetime], c: int, t_min: int,
                gap_min: float = MIN_GAP_MIN) -> dict:
    """**その日の形が (A)/(B) をどれだけ切り分けるか**（2026-08-27 に足した）。

    `window()` は日を決めるときに2つの門を通しています ——
    **予測の差が `DECIDE_GAP_MIN` 以上**（`abs(pc - pw)`）と、
    **同じ分の組が無いこと**（`ties()`）。どちらも**予約の形だけで先に分かります。**

    ところが `booked_split_day()` は長らく「**`first_pub` より前に出す本が
    1本でもある日**」で切り分けの日を選んでいました。**それは必要でも十分でも
    ありません**（2026-08-27 に実測で分かった）:

        2026-08-28  早い本 0本 だが 差 0 —— 早い本が無くても切り分かる日はある…
        2026-09-07  早い本 0本・差 **5**  ←（13:30 より後ろが多い日は、
                    **窓のほうが少なく**予測するので、それだけで切り分きます）
        2026-09-02  早い本 2本・差 **3**（ぎりぎり。1本 動けば消える）
        2026-08-27  早い本 8本・差 **8**（05:00〜13:30 の18本 ＋ 16:00 の1本）

    **差の大きい日を選ぶこと。** 「早い本があるか」は、差を作る**片方の道**に
    すぎません（もう片方は「13:30 より後ろに出す本があるか」）。

    返り: `kept`（間隔で残る本数）／`count`（(A) の予測）／`window`（(B) の予測）
    ／`gap`（その差）／`ties`（同じ分の組の数）／`decisive`（門を2つとも通るか）
    """
    kept = _spaced(times, gap_min)
    pc = min(len(kept), c)
    pw = sum(1 for x in kept if x.hour * 60 + x.minute <= t_min)
    tied = ties(times)
    return {"kept": len(kept), "count": pc, "window": pw, "gap": abs(pc - pw),
            "ties": len(tied),
            "decisive": abs(pc - pw) >= DECIDE_GAP_MIN and not tied}


def left_edge(path: pathlib.Path | None = None) -> dict | None:
    """**窓の左端**（これより早く出した本は、その日 0再生で終わる）。

    ## なぜ要るか（2026-08-27 16:xx・実測して足した）

    `window()` の2つのモデルは、**どちらも左端を持っていません**:

        (A) 本数   生きるのは**先頭から** C 本   → 早い本ほど生きる
        (B) 窓     生きるのは **T まで**の本 全部 → 早い本は全部生きる

    **両方とも「早く出すほど有利」と言っています。** `cap_if_window()` は
    そこから **05:00 から出せば 18枠（×1.80）** を出し、`scripts/eta.py` は
    それを `density` の腕の上振れとして印字していました。

    **2026-08-27 に実際に置いて、測りました。** 05:00〜08:30 JST に 8本
    （30分きざみ）。結果は **8本とも 0再生**（07:30 の1本だけ 4再生）で、
    生きたのは 08:59 以降の 10本です。**8本とも `public` / `processed`** を
    `videos.list` で確かめてあるので、**投稿の失敗ではありません。**

        05:00 0    05:30 0    06:00 0    06:30 0    07:00 0
        07:30 4    08:00 0    08:30 0   ← ここまで死
        08:59 313  09:30 106  10:00 84  10:30 367 …… 13:30 71  ← ここから生

    **つまり早く出すほど有利ではありません。** 窓には左端があり、
    **05:00 に倒すと本が死にます。** `density` の ×1.80 は**実在しません** ——
    09:00〜13:30 は30分きざみで**ちょうど10枠**で、`cap()` の 10 と同じです。

    **覆る条件**: 左端は日によって動くかもしれません（配信の面が育てば早い時刻にも
    人がいる）。ここは**毎日その日の実物から測り直します**（定数で持ちません）。
    右端のほうはまだ 13:30 で、**それより後ろは未測**です。

    返り: `{"after", "by", "dead", "days"}` ＝ 左端は `after` より後・`by` まで。
    早い時刻で死んだ本が1本も無ければ `None`（＝ まだ測っていない）。
    """
    found: list[tuple[int, dt.time, dt.time, str]] = []
    n_dead = 0
    days: list[str] = []
    for d, rows, line in _qual_days(path):
        alive = [p for p, _v, n in rows if n >= line]
        if not alive:
            continue
        first_alive = min(alive)
        # **その日いちばん早く生きた本より前に出て、死んだ本**だけを見ます。
        # 「上限を超えて死んだ本」は後ろに出るので、ここには入りません。
        early_dead = [p for p, _v, n in rows if n < line and p < first_alive]
        if not early_dead:
            continue
        n_dead += len(early_dead)
        days.append(f"{d}（{min(early_dead):%H:%M}〜{max(early_dead):%H:%M} の "
                    f"{len(early_dead)}本が0再生 ／ 最初に生きたのは {first_alive:%H:%M}）")
        found.append((len(early_dead), max(early_dead).time(),
                      first_alive.time(), str(d)))
    if not found:
        return None
    # **日をまたいで max/min を取らないこと**（2026-08-27 16:xx に踏んだ）。
    # 死んだ時刻の最大と、生きた時刻の最小を**別々の日から**拾うと、
    # 08-26（09:00 が死・09:30 から生）と 08-27（08:30 まで死・08:59 から生）で
    # **`after=09:00` / `by=08:59` ＝ 左端が右端より後ろ**という、
    # 成り立たない括弧を返します。**括弧は1日の中でしか閉じません。**
    # 採るのは**早い時刻の死を いちばん多く見た日**（＝ わざと置いた実験日）。
    n, after, by, day = max(found, key=lambda x: x[0])
    return {"after": after.strftime("%H:%M"), "by": by.strftime("%H:%M"),
            "dead": n_dead, "from": day, "from_dead": n, "days": days}


def window(path: pathlib.Path | None = None) -> dict:
    """**上限が「1日N本」なのか「時刻の窓」なのかを、切り分けられているか。**

    2つのモデルを実測から当てはめて、**同じ数を出しているあいだは「切り分けて
    いない」と言います。** 当て推量（始まりの時刻がどれだけばらけているか）では、
    切り分けの実験が返ってきた回に自分で下りません。

        (A) 本数   生きるのは、間隔で残った本のうち **先頭から C 本**
        (B) 窓     生きるのは、間隔で残った本のうち **T までに出した本 全部**

    C は証拠の日の生きた本数、T は証拠の日で生きた本の**いちばん遅い公開時刻**。
    どちらも 08/20〜08/22 では 10 を出します（09:00 から30分きざみだと
    13:30 がちょうど10本目だから）。**05:00 から出す日を1日置けば、
    (A) は 10・(B) は 18 を出すので、その日の実測が決めます。**

    返り:
      C / T           当てはめた2つのモデルの値
      confounded      True ＝ **どの日でも2つが同じ数**（区別できていない）
      decided_by      切り分けた日（無ければ None）
      verdict         "count" / "window" / None
      blocked         [(日, 組の数, 巻き込まれた本数)] ＝ **同じ分の組があって使えなかった日**

    **同じ分の組がある日からは決めません**（2026-08-25 に足した）。理由は `ties()`。
    実物で確かめた落ち方 —— 08/27 は 19本のうち **5組10本が同じ分**にいました。
    そこで「窓が真・組は両方死ぬ」を当てると生きた本が 9本 になり、
    **本数モデルの予測（10本）に着地**します。守りが無いと、この道具は

        decided_by=2026-08-27（出した 19本・生きた 9本 ／ 本数なら 10・窓なら 14）
        verdict='count'  confounded=False

    と**確信つきで逆を印字**しました。`density` の天井が 10本 に固定され、
    **1.8倍 を取り落とします。**

    **覆る条件**: 同じ分の2本がどう死ぬかを1日測れば、`_spaced()` に畳めます。
    そうしたらこの守りは要りません（`ties()` の3つの読みのどれかに決まる）。
    """
    per_day: list[tuple[dt.date, list, float, int, int]] = []
    blocked: list[tuple[dt.date, int, int]] = []
    tied_days: set[dt.date] = set()
    floor = 0
    for d, rows, line in _qual_days(path):
        n_alive = sum(1 for _p, _v, n in rows if n >= line)
        tied = ties([p for p, _v, _n in rows])
        if tied:
            # **同じ分の組がある日は、ここで1度だけ外します。**
            # `floor` にも入れません —— 入れると、割り当てられない日が
            # 「ここまでは付いた」の線を持ち上げ、**まともな日が全部
            # `a >= floor` から落ちて証拠が空になります**（2026-08-25 に踏んだ）。
            tied_days.add(d)
            blocked.append((d, len(tied), sum(len(g) for g in tied)))
        else:
            floor = max(floor, n_alive)
        per_day.append((d, rows, line, n_alive, len(rows) - n_alive))
    # **証拠になるのは `measure()` と同じ日だけ**（生きた本数が最良で、なお死んだ本がある日）。
    # 生きた本数が最良より少ない日は、上限ではなく**その日の題材が外れた**日です。
    #
    # **同じ分の組がある日は、ここでも外します**（2026-08-25）。決めるときだけ
    # 外して当てはめに残すと、**C と T が汚れた日から決まります** —— 08/27 を
    # 「窓が真・組の後ろだけ死ぬ」で当てると生きた 14本 が C に入り、
    # C=14 のまま 08/20 を見て `window` と印字しました。**答えは合っていても、
    # 根拠が測っていない日**です。割り当てられない日は、当てはめにも使いません。
    evidence = [(d, rows, line, a) for d, rows, line, a, dead in per_day
                if dead and a >= floor and d not in tied_days]
    if not evidence:
        # **`blocked` は必ず返します。** 空にすると、同分で潰れた測定日が
        # 「まだ測っていない日」と見分けが付かなくなります。
        return {"days": 0, "C": None, "T": None, "confounded": bool(blocked),
                "decided_by": None, "verdict": None, "first_pub": None,
                "last_alive": None, "blocked": blocked}

    def _fit(exclude: dt.date | None):
        """**その日を除いて**、2つのモデルの値を当てはめる。

        `exclude` を外すのが要点です（2026-08-25）。C を「証拠の日の生きた本数の
        最大」で置くと、**試している日そのものが C を決めます** —— 窓が真なら
        08/27 の生きた 14本 がそのまま C=14 になり、`本数なら 14・窓なら 14` で
        **予測が一致して、その日は「どちらにも読める」で捨てられます。**

        つまり**本数モデルは、それを覆すために作った日では絶対に覆りません。**
        実測（衝突を散らした 08/27・窓が真）で `verdict=None` を確かめました。
        当てはめは**前の日から**やり、試す日は当てるだけにします。
        """
        ev = [e for e in evidence if e[0] != exclude]
        if not ev:
            return None
        c = max(a for _d, _r, _l, a in ev)
        times = [p for _d, rows, line, _a in ev for p, _v, n in rows if n >= line]
        t = max(times, key=lambda x: x.hour * 60 + x.minute)
        fp = min((rows[0][0] for _d, rows, _l, _a in ev),
                 key=lambda x: x.hour * 60 + x.minute)
        return c, t, t.hour * 60 + t.minute, fp

    C, T, T_min, first_pub = _fit(None)

    def predict(rows, c: int, t_min: int):
        """**どの本が生きるか**を、2つのモデルそれぞれの「集合」で返す。

        **本数で返さないこと**（2026-08-27 16:xx に踏んだ）。ここは長らく
        `min(len(kept), c)` と `sum(x <= t_min)` の**2つの整数**を返し、
        下の `decided_by` はそれを生きた**本数** `a` と比べていました。
        ところが 08/27 の実物は:

            本数モデル  生きるのは先頭10本 ＝ 05:00〜09:30
            実測        生きたのは 08:59〜13:30 の10本

        で、**数は 10 と 10 でぴったり一致し、中身は 19本中 16本が
        入れ替わっています**（本数モデルが「生きる」と名指しした 8本は
        全部 0再生、「死ぬ」と名指しした 8本は全部 生きた）。
        それでも整数しか返さないので `near` は `count` を**距離0**で選び、
        この道具は `verdict='count'` を**確信つきで**印字しました ——
        **その日の実物が、選ばれたモデルを丸ごと否定しているのに**です。

        数だけを見ると「当たり」に見えるのは、生きている窓 09:00〜13:30 が
        30分きざみで**ちょうど10枠**だからです。**それがこの `confounded` の
        正体そのもの**なので、**数で切り分けようとするかぎり、
        どんな日を足しても永久に切り分かりません。**
        """
        kept = _spaced([p for p, _v, _n in rows])
        return (set(kept[:c]),
                {x for x in kept if x.hour * 60 + x.minute <= t_min},
                kept)

    decided_by = verdict = None
    misfit: list[str] = []
    for d, rows, line, a, _dead in per_day:
        held = _fit(d)                    # **その日を除いて当てはめる**
        if held is None:
            continue                      # 前の日が無い ＝ 比べる相手がいない
        c_d, _t_d, t_min_d, _fp_d = held
        pred_c, pred_w, kept = predict(rows, c_d, t_min_d)
        pc, pw = len(pred_c), len(pred_w)
        if abs(pc - pw) < DECIDE_GAP_MIN:
            continue                      # 2つの予測が近い日は、どちらにも読める
        if d in tied_days:
            # **同じ分の組がある日からは決めません。** そこで死んだ本が
            # 「衝突で死んだ」のか「上限で死んだ」のか、**割り当てられません**。
            # 黙って通すと答えが反転します（2026-08-25 に 08/27 の実物で確かめた）——
            # 窓が真で、組が両方死ぬ場合、生きた本数が**本数モデルの予測に着地**し、
            # `count` を確信つきで印字します。**それは 1.8倍 を取り落とす向き**です。
            continue
        # **生きた「本」の集合**で比べます。`_spaced()` で落ちた本は
        # どちらのモデルの守備範囲でもない（衝突で死ぬ）ので、外します。
        in_kept = set(kept)
        act = {p for p, _v, n in rows if n >= line and p in in_kept}
        # **上限が効いていない日から決めないこと**（2026-08-27 16:xx に足した）。
        # 2026-08-04（登録者9人・18:29 から7本）は生きたのが 1本 だけです。
        # 本数モデルは「先頭4本」、窓モデルは 13:30 までが1本も無いので
        # **「1本も生きない」**を予測します。**何も生きないと言うモデルは、
        # ほとんど何も生きなかった日で必ず勝ちます** —— 取り違え 窓1本 対
        # 本数3本 で、この道具は `verdict='window'` を印字しました。
        # 2026-08-24 に「コインの裏表で断定」として直した所が、
        # 本の取り違えで測り直したとたんに**別の入口から戻っています。**
        #
        # 上限の話をしているのは、**その日が上限の近くまで埋まった日**だけです。
        # 当てはめた C の半分に届かない日は、縛っているのが上限ではありません
        # （面が細い・題材が外れた）。**覆る条件**: C 自体が下がって
        # まともな日まで落ちるようなら、床は割合ではなく `floor` で持つこと。
        if len(act) * 2 < c_d:
            continue
        miss_c, miss_w = len(pred_c ^ act), len(pred_w ^ act)
        near, far = sorted(((miss_c, "count"), (miss_w, "window")))
        # **どちらにも合っていない日で決めないこと。** 2026-08-04（登録者が9人・
        # 18:29 から7本）は 生きた2本 に対し 本数なら4・窓なら0 で、**両方から等距離**
        # です。ここを通していたので、この道具は「窓のほうが上限」と**コインの裏表で
        # 断定**していました（2026-08-24 に踏んで直した）。
        #
        # **本の取り違えで測るようになったので、ここは 08/27 でも効きます** ——
        # 取り違え 本数16本・窓8本 に対し 門は 19本の 25% ＝ 4.75本 なので、
        # **どちらも通りません**（＝ この日からは決めない）。**それが正解**です:
        # 実測の「生きた10本」は 08:59 から始まっており、**窓の左端が
        # 05:00 ではない**ことを言っています。2つのモデルはどちらも
        # 左端を持っていないので、**この日はどちらのモデルでも説明できません。**
        if near[0] > max(1.0, 0.25 * len(kept)):
            misfit.append(
                f"{d}（出した {len(rows)}本・生きた {len(act)}本 ／ "
                f"本を取り違えた数 本数 {miss_c}本・窓 {miss_w}本 "
                f"＝ **どちらのモデルも合っていません**）")
            continue                      # 実測がどちらのモデルにも乗っていない日
        if far[0] - near[0] < 2:
            continue                      # 差が付いていない
        verdict = near[1]
        decided_by = (f"{d}（出した {len(rows)}本・生きた {len(act)}本 ／ "
                      f"本を取り違えた数 本数 {miss_c}本・窓 {miss_w}本）")
        break

    return {"days": len(evidence), "C": C, "T": T.strftime("%H:%M"),
            "confounded": decided_by is None, "decided_by": decided_by,
            "verdict": verdict, "first_pub": first_pub.strftime("%H:%M"),
            "last_alive": T.strftime("%H:%M"), "blocked": blocked,
            "misfit": misfit, "left_edge": left_edge(path)}


def cap(path: pathlib.Path | None = None) -> int:
    return measure(path)["cap"]


def effective(per_day: float, path: pathlib.Path | None = None) -> float:
    """**その本数のうち、再生が付くぶん。** 上限を超えたぶんは 0 として数えます。"""
    return min(float(per_day), float(cap(path)))


# ---------------------------------------------------------------------------
# **本数を増やすと、その日の再生は増えるのか**（2026-08-28 18:xx に測って足した）
#
# この上の `measure()` が答えているのは「**その日の何本に再生が付くか**」で、
# **「その日いくつ再生が付くか」ではありません。** 2つは別の問いです ——
# 上限 10本 は「11本目から 0」と言うだけで、**その 10本の合計が
# 本数によって動くかどうかについては、何も言っていません。**
#
# 実測（`data/views.jsonl`・齢24時間でそろえた・公開日ごとの合計）:
#
#     08/19   8本 → 8,147     08/23  13本 → 9,798
#     08/20  25本 → 6,329     08/24  10本 → 7,897
#     08/21  21本 → 6,605     08/25  10本 → 2,385
#     08/22  25本 → 5,845     08/26  14本 → 1,495     08/27  19本 → 3,484
#
# **8本の日と25本の日で、合計はほとんど変わりません。**
# 08/19〜08/24 の6日だけを見ると、本数と合計の順位相関は **負**です
# （本数を3倍にした日のほうが、合計は少ない）。
#
# **これが効くのは `density` の腕です。** `scripts/eta.py` は
# 「1日 n本 × 1本あたり再生」で段1を解いており、`measure()` の上限で
# n を 10本 に頭打ちにしています。**ですが上の実測は、10本の中でも
# 合計が動いていないと言っています** —— つまり縛っているのは本数ではなく
# **その日にチャンネルへ配られる総量**のほうです。
#
# **ここは「密度は無駄だ」と決めつける道具ではありません。** 日数が9日しか
# 無く、08/25 に別の段差（下の `SPLIT` の註）が入っています。
# **出すのは相関と、その日数と、段差の位置だけ**です。判断はそれを読む側がします。
#
# **覆る条件**: 本数を上限より大きく振った日が増えて、相関が正へ寄ったら
# この註は要りません（`day_total()` が毎回 数え直します。定数はありません）。
# ---------------------------------------------------------------------------

DAY_TOTAL_MIN_AGE_H = 24.0   # 合計を数えるときの齢。**6時間では半分しか付いていません**
DAY_TOTAL_MIN_DAYS = 4       # 相関を出すのに要る最低の日数


def _rank(xs: list[float]) -> list[float]:
    """同順位は平均順位。**scipy を入れないため**（依存を増やさない）。"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """順位相関。**動かない列があれば None**（0 と区別が付かないため）。"""
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    rx, ry = _rank(xs), _rank(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx <= 0 or dy <= 0:
        return None
    return num / (dx * dy) ** 0.5


def day_total(path: pathlib.Path | None = None,
              forms_path: pathlib.Path | None = None,
              min_age_h: float = DAY_TOTAL_MIN_AGE_H,
              include_long: bool = False,
              since: dt.date | None = None) -> dict:
    """**その日に何本 出したかで、その日の再生の合計は動くのか。**

    `measure()` は「何本に付くか」、ここは「**いくつ付くか**」です。
    上の註のとおり、**2つは別々に動きます。**

    返り:
      days       [{"date": …, "n": 本数, "total": 合計, "med": 中央値}]（古い順）
      rho        本数 と 合計 の順位相関（**全部の日**。日数が足りなければ None）
      rho_scale  **上限まで出した日だけ**（n >= cap）の同じ相関
      n_scale    その日数
      n_days     数えた日数
      age_h      そろえた齢
      drop       合計がいちばん大きく落ちた境目 `{"at": 日, "before": …, "after": …}`
                 （前後3日ずつの中央値で見る。見つからなければ None）

    **`rho` と `rho_scale` は逆の符号になることがあります**（実測 08/28:
    全24日 **+0.75** ／ 上限まで出した8日 **-0.01** ／ 08/19〜08/24 の6日 **-0.76**）。
    **`rho` のほうは立ち上がりを含んでいるから**です —— 08/15〜08/18 は
    1〜4本/日 で合計も数百回。**「本数が少ないから再生も少ない」ではなく、
    その頃はチャンネルがまだ面に載っていなかった**だけ。
    **`rho` 単独を density の根拠にしないこと。**
    """
    skip = set() if include_long else _long_ids(forms_path)
    per: dict[dt.date, list[int]] = collections.defaultdict(list)
    for vid, (pub, _h, n) in _readings(path, min_age_h).items():
        if vid in skip:
            continue
        d = pub.date()
        if since is not None and d < since:
            continue
        per[d].append(n)
    days = [{"date": d, "n": len(v), "total": sum(v), "med": statistics.median(v)}
            for d, v in sorted(per.items())]
    rho = None
    if len(days) >= DAY_TOTAL_MIN_DAYS:
        rho = _spearman([float(r["n"]) for r in days],
                        [float(r["total"]) for r in days])
    # **上限まで出した日だけで数え直す。** 立ち上がり（1〜4本/日）を混ぜると
    # 「本数が多い日は合計も多い」が出ますが、それは面に載る前の日を
    # 本数の効きとして数えているだけです（上の docstring の実測）。
    c = measure(path, forms_path, include_long)["cap"]
    at_cap = [r for r in days if r["n"] >= c]
    rho_scale = None
    if len(at_cap) >= DAY_TOTAL_MIN_DAYS:
        rho_scale = _spearman([float(r["n"]) for r in at_cap],
                              [float(r["total"]) for r in at_cap])
    # **段差は「前後3日ずつの中央値の比」がいちばん大きい所**。
    # 平均ではなく中央値なのは、1日の跳ねで境目が動くのを避けるため。
    drop = None
    if len(days) >= 6:
        best = 0.0
        for i in range(3, len(days) - 2):
            before = statistics.median([r["total"] for r in days[max(0, i - 3):i]])
            after = statistics.median([r["total"] for r in days[i:i + 3]])
            if after <= 0:
                continue
            ratio = before / after
            if ratio > best:
                best = ratio
                drop = {"at": days[i]["date"], "before": before,
                        "after": after, "ratio": ratio}
        if drop is not None and drop["ratio"] < 1.5:
            drop = None
    return {"days": days, "rho": rho, "rho_scale": rho_scale,
            "n_scale": len(at_cap), "n_days": len(days),
            "age_h": min_age_h, "drop": drop}


def day_total_lines(path: pathlib.Path | None = None,
                    forms_path: pathlib.Path | None = None) -> list[str]:
    """**本数と、その日の合計。**上限とは別の問いなので、別の行で出す。"""
    m = day_total(path, forms_path)
    if m["n_days"] < DAY_TOTAL_MIN_DAYS:
        return [f"  **本数 → その日の合計**: 読める日が {m['n_days']}日 しかありません"
                f"（要る日数 {DAY_TOTAL_MIN_DAYS}）"]
    out = []
    rho, rho_s = m["rho"], m["rho_scale"]
    # **読むのは `rho_scale` のほうです**（`rho` は立ち上がりを含む。docstring の実測）
    show = rho_s if rho_s is not None else rho
    if show is None:
        out.append("  **本数 → その日の合計**: 順位相関が出せません（列が動いていない）")
    else:
        verdict = ("**本数を増やしても合計は増えていません**" if show < 0.3
                   else "本数と合計は同じ向きに動いています")
        if rho_s is not None:
            out.append(f"  **本数 → その日の合計の順位相関: {rho_s:+.2f}**"
                       f"（**上限 {m['n_scale']}日ぶんだけ**・齢 {m['age_h']:.0f}時間）"
                       f"—— {verdict}")
            if rho is not None:
                out.append(f"    **全 {m['n_days']}日 で数えると {rho:+.2f} です。"
                           "そちらを使わないこと** —— 立ち上がり（1〜4本/日・合計 数百回）を"
                           "混ぜており、**面に載る前の日を「本数が少ないから」と数えます**")
        else:
            out.append(f"  **本数 → その日の合計の順位相関: {rho:+.2f}**（{m['n_days']}日・"
                       f"齢 {m['age_h']:.0f}時間）—— {verdict}"
                       "（**上限まで出した日が足りません**。立ち上がりが混ざっています）")
        out.append("    **上の『上限 n本』とは別の問いです。** 上限は"
                   "「その日の**何本に**付くか」、ここは「その日**いくつ**付くか」。"
                   "**`density` の腕が効くのは、ここが正のときだけ**です")
    for r in m["days"][-8:]:
        out.append(f"      {r['date']}  {r['n']:2d}本 → 合計 {r['total']:6d}"
                   f"（中央値 {r['med']:.0f}）")
    if m["drop"] is not None:
        d = m["drop"]
        out.append(f"    [!] **合計が {d['at']} を境に {d['ratio']:.1f}倍 落ちています**"
                   f"（前3日の中央値 {d['before']:.0f} → 後3日 {d['after']:.0f}）。"
                   "**本数は境目で変わっていません** —— 落ちたのは1本あたりのほうです")
        out.append("    **段差があるあいだ、上の相関は2つの群を混ぜています。**"
                   "本数の効きだけを見るなら、境目の**片側だけ**で数え直すこと")
    return out


def lines(path: pathlib.Path | None = None) -> list[str]:
    m = measure(path)
    out = [f"  **1日に再生が付く本数の上限: {m['cap']}本**（**ショートの面**）"
           + ("（実測）" if m["measured"] else "（**崩れをまだ観測していません**・既定値）")]
    if m["measured"]:
        out.append(f"    再生が付いた本数の最大: {m['floor']}本 ／ "
                   f"それ以上出しても付かなかった: {m['collapse']}本目から")
        for d in m["days"][-3:]:
            out.append(f"      {d}")
        out.append("    **上限を超えて出したぶんは 0再生です。**本数を増やしても、"
                   "ここを超えたぶんは登録者に効きません")
        out.extend(window_lines(path))
    else:
        out.append(f"    **上限より多く出した日がまだありません**（見えている最大 {m['floor']}本）。"
                   "崩れを観測するまで、この数は既定値です")
    out.extend(day_total_lines(path))
    out.extend(long_form_lines(path))
    return out



def past_split_days(path: pathlib.Path | None = None,
                    c: int | None = None, t_min: int | None = None,
                    after_min: int | None = None) -> list[dict]:
    """**公開ずみの日のうち、3つのモデルを切り分けた日**（API 0単位・2026-09-01 に足した）。

    ## なぜ要るか（**手で1回やった跡です**）

    `booked_split_day()` は **`if day < today: continue`** で過ぎた日を飛ばします。
    註は「過ぎた日は、もう読みのほうで数えています」——
    **それは上限（`measure()`）の話で、「どのモデルが当たったか」ではありません。**

    そして **規則1（1日1本）の下では、切り分けの日は二度と予約できません** ——
    3つのモデルが別々の集合を予測するには、**1日に十数本**要ります。
    `scripts/deadline_check.py` の末尾は、期日までに満ちない前提について
    「**(2) すでに公開ずみの日で判定できるなら、いま閉じる**」と言いますが、
    **その日を探す手がどこにもありませんでした**（2026-09-01 の回は、
    使い捨ての script を書いて手で探しています。**次の回が同じことをやり直します**）。

    ## 3つのモデル（`window()` の2つ ＋ `left_edge()` の帯）

        本数  間隔で残った本の**先頭 C 本**            → 早い本ほど生きる
        窓    間隔で残った本のうち **T まで**の本 全部 → 早い本は全部生きる
        帯    そのうち **左端より後ろ**だけ            → 早すぎる本は死ぬ

    **比べるのは本数ではなく集合です**（`window()` が 2026-08-27 に直した所）。
    生きた本数が合っていても、**生きた本が入れ替わっている**ことがあります。

    ## 返り

    日ごとに `{"day", "n", "ties", "kept", "alive", "pred", "diff", "separates"}`。
    `diff` は**対称差**（取り違えた本の数）で、`falsified_if` の門と同じ単位です。
    `separates` は **3つの予測集合が互いに別**（＝ その日で決められる）。

    **`ties` が 0 でない日と、生きた本が 3本 未満の日は、そのまま返しますが
    `separates` を立てません** —— `config/hypotheses.yaml` の「判定しない条件」
    (1)(2) と同じ門です。**呼ぶ側で数え直さないこと。**

    ## **割り引いて読むこと**

    **左端は、いちばん早い死をいちばん多く見た日から測っています**
    （`left_edge().from`）。**その日で当てはめて、その日で当てると、
    帯の対称差 0 は「良く当たった」ではなく「当てはめた」に近い。**
    独立に見たいのは「**早い本ほど生きる**」（本数・窓が両方 言うこと）が
    **別の日でも外れているか**のほうで、それは `left_edge().days` が並べます。
    """
    w = window(path)
    if c is None:
        c = int(w["C"]) if w.get("C") else None
    if t_min is None and w.get("T"):
        t_min = int(str(w["T"])[:2]) * 60 + int(str(w["T"])[3:])
    if c is None or t_min is None:
        return []
    if after_min is None:
        le = left_edge(path)
        if le:
            after_min = int(le["after"][:2]) * 60 + int(le["after"][3:])

    def _m(t: dt.datetime) -> int:
        return t.hour * 60 + t.minute

    out: list[dict] = []
    for d, rows, line in _qual_days(path):
        times = [p for p, _v, _n in rows]
        kept = _spaced(times)
        keptset = set(kept)
        tied = ties(times)
        pred_count = set(kept[:c])
        pred_win = {t for t in kept if _m(t) <= t_min}
        pred_band = ({t for t in pred_win if _m(t) > after_min}
                     if after_min is not None else set(pred_win))
        alive = {p for p, _v, n in rows if n >= line and p in keptset}
        preds = {"band": pred_band, "window": pred_win, "count": pred_count}
        distinct = (pred_band != pred_win and pred_win != pred_count
                    and pred_band != pred_count)
        out.append({
            "day": str(d),
            "n": len(rows),
            "ties": len(tied),
            "kept": len(kept),
            "alive": len(alive),
            "pred": {k: len(v) for k, v in preds.items()},
            "diff": {k: len(v ^ alive) for k, v in preds.items()},
            "separates": bool(distinct and not tied and len(alive) >= 3),
        })
    return out


def past_split_lines(path: pathlib.Path | None = None) -> list[str]:
    """`past_split_days()` の印字。**切り分けた日が無ければ、そう言います。**"""
    days = past_split_days(path)
    sep = [d for d in days if d["separates"]]
    if not days:
        return []
    out = [f"  **公開ずみの日で、3つのモデル（帯／窓／本数）を切り分けた日: "
           f"{len(sep)}日**（数えた {len(days)}日・API 0単位）"]
    if not sep:
        out.append("    **1日もありません。** 規則1（1日1本）の下では"
                   "**新しくは作れません** —— 切り分けには1日に十数本 要ります。"
                   "**期日を待つ前提は、待っても閉じません。**")
        return out
    for d in sep:
        best = min(d["diff"], key=lambda k: d["diff"][k])
        out.append(f"    {d['day']}  出した {d['n']}本 ／ 生きた {d['alive']}本  "
                   f"取り違え 帯{d['diff']['band']} / 窓{d['diff']['window']} / "
                   f"本数{d['diff']['count']}  → **{best}** がいちばん当たっています")
    out.append("    **左端は、この中の1日から当てはめた値です**（`left_edge().from`）。"
               "**同じ日で当てて 0本 なのは「当てはめた」に近い。** "
               "独立に見るのは `left_edge().days`（別の日でも早い本が死んでいるか）。")
    return out


def booked_split_day(first_pub: str, today: dt.date | None = None,
                     uploaded: pathlib.Path | None = None,
                     c: int | None = None, t_min: int | None = None) -> dict | None:
    """**その切り分けの日は、もう予約されていないか**（2026-08-25 に足した）。

    `window_lines()` は「**`first_pub` より前から公開する日を1日作れ**」と
    言うだけで、**その日がもう帳面にあるかを見ていませんでした。**
    実測（2026-08-25）—— **08/27 は 19本**が予約済みで、うち4本が
    **05:00 / 06:00 / 07:00 / 08:00 JST**です。

    **2026-08-25 22:5x に、この日の形を直しました。** それまで
    **19本すべてが 13:30 以前**で、その形だと **(B) 窓モデルは「19本とも生きる」
    ＝ 1本も死なない**を予測します。**死ぬ本が無ければ証拠が立たず、
    `verdict=None`** ——**(A) 本数モデルの側にしか答えられない日**でした
    （`config/hypotheses.yaml` の note (3) が名指ししていた形）。
    同じ分に2本ある組が5組あったので、**その重複5本を 13:30 の後ろへ**動かしました
    （14:00 / 14:30 / 15:00 / 15:30 / 16:00）。**09:00〜13:30 の10本は1本も
    動かしていません。**

    いまの形と、読み方:

        13:30 まで **14本** ／ 13:30 より後 **5本**
        → **10本しか生きなければ (A)、14本 生きれば (B)**

    （**「19本とも生きれば (B)」ではありません。** それは直す前の形の読み方で、
    その形では (B) が反証不能でした。）

    それを言わないと、次の回は「1日作れ」を**もう1度作ります** ——
    そして日が増えるほど交絡が増えます（同じ分の組・穴埋め）。
    `scripts/eta.py` の `blocking` にあったのと**同じ形の欠陥**です
    （そちらは「もう測っている値」を「まだ測っていない」と言っていた）。

    返すのは `{"day", "before", "total", "answer", ...}`、無ければ `None`。

        day     いちばん早い切り分けの日（JST）
        before  そのうち `first_pub` より前に置かれている本数
        total   その日の予約の合計
        answer  生きた本数を**読めるようになる日**（その日の最後の本が `MIN_AGE_H`
                に達する日。**Analytics の3日遅れは掛かりません** —— 下の註）
        count / window / gap / ties / decisive   `split_power()` の中身
        running True ＝ **その日は今日**（もう動いている ＝ 置き直せないが、答えは返る）

    ## **2026-08-27 に、この関数が2つの理由で答えを6日 遅らせていました**

    **(1) 今日を飛ばしていました。** `<= today` で切っていたので、
    **その日が今日になった瞬間、対照日が視界から消えます。** 実測 ——
    08/27 の予約は **19本・05:00 から30分きざみ・同じ分の組は0**で、
    (A) 本数なら **10本 生き**、(B) 窓なら **18本 生き**ます（**差 8**）。
    **これ以上の切り分けの日は帳面のどこにもありません。**
    それでもこの関数は 08/27 を飛ばし、**差 3 しかない 09/02** を名指しして、
    `window_lines()` は「読めるのは **2026-09-07**」「**答えが返るまで
    他の日の本数を増やさないこと**」と毎回 印字していました。
    **11日 ぶん、`density` の 1.8倍 が宙に浮きます。**

    「置き直せない日は名指ししない」は**作る側の理屈**です。この関数の
    読み手（`window_lines` / `measure_window.split_day_window` / `cap_if_window`）が
    要るのは「**どの日が答えるのか・いつ読めるのか**」で、
    **走っている日はまさにそれです**（守るほうも、まだ間に合います ——
    08/27 は 16:00 の1本がこの時点でまだ公開前でした）。

    **(2) 「Analytics 3日遅れ」を足していました。** `window()` が読むのは
    `data/views.jsonl` で、あれは **Data API（`videos.list` の `statistics`）**を
    `scripts/snapshot.py` が積んだものです —— **Analytics は1行も通りません。**
    `_readings()` の齢の下限は `MIN_AGE_H`（6時間）なので、
    **その日の最後の本が6時間 たてば読めます**（08/27 なら 16:00 + 6h ＝ 22:00 JST）。
    足していた5日は、**どこからも来ていない数**でした。

    **覆る条件**: `_readings()` の齢の下限がショート側でも 24時間 に上がったら、
    `answer` はその齢で計算し直すこと（この関数は `MIN_AGE_H` を読んでいます）。
    """
    today = today or dt.datetime.now(JST).date()
    try:
        cut = dt.datetime.strptime(first_pub, "%H:%M").time() if first_pub else None
    except ValueError:
        cut = None

    # **帳面の読み手を増やさないこと**（`docs/JOURNAL.md` 2026-08-25）。
    # 「後の行を採る・JST で割る」の2規則は `src.motion_groups` が持っています。
    from src import motion_groups

    at = motion_groups.scheduled_at(uploaded) if uploaded else motion_groups.scheduled_at()
    per_day: dict[str, list[dt.datetime]] = collections.defaultdict(list)
    for when in at.values():
        day = motion_groups.jst_day(when)
        if not day:
            continue
        t = dt.datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(JST)
        per_day[day].append(t)

    if c is None or t_min is None:
        w = window()
        if not w.get("C") or not w.get("T"):
            return None
        c = int(w["C"])
        t_min = int(str(w["T"])[:2]) * 60 + int(str(w["T"])[3:])

    for day in sorted(per_day):
        if dt.date.fromisoformat(day) < today:
            continue                       # **過ぎた日は、もう読みのほうで数えています**
        times = sorted(per_day[day])
        power = split_power(times, c, t_min)
        if not power["decisive"]:
            continue                       # 予測が離れない日・同じ分の組がある日
        early = [t for t in times if cut and t.time() < cut]
        last = max(times) + dt.timedelta(hours=MIN_AGE_H)
        return {"day": day, "before": len(early), "total": len(times),
                "answer": last.date().isoformat(),
                "answer_at": last.strftime("%H:%M"),
                "answer_ts": last.isoformat(),
                "running": dt.date.fromisoformat(day) == today,
                **{k: power[k] for k in ("count", "window", "gap", "ties", "kept")}}
    return None


def readable_at(b: dict, now: dt.datetime | None = None) -> dict:
    """**その「読める時刻」に、本当に読めるのか**（2026-08-27 に足した）。

    ## 何が起きていたか（**申し送りが3周 連続で外していた**）

    `booked_split_day()` の `answer` / `answer_at` は **齢だけ**で出ています ——
    「その日の最後の本が `MIN_AGE_H`（6時間）になる時刻」。**読む口のことは
    1文字も見ていません。**

    ところが `data/views.jsonl` を積むのは `scripts/snapshot.py` ＝
    **Data API の `videos.list`** で、**日枠が尽きている窓では 403 しか返りません。**
    `snapshot.py` 自身が「1本も読めませんでした（日枠は JST 16:00 に戻ります）」と
    印字して終了コード1で降ります。

    実測 2026-08-27 20:5x JST —— この窓の 403 は **88回** 観測ずみで、
    枠が戻るのは **08/28 16:00 JST**。それでも `_booked_lines()` は
    「読めるのは **2026-08-27 22:00** 以降」と印字し、
    `docs/JOURNAL.md` の申し送りは **3周 続けて**
    「**22:00 JST を過ぎていたら、まず `python scripts/snapshot.py` を撃つこと**」を
    運んでいました。**22:00 に撃っても 403 です。**

    **これは `docs/JOURNAL.md` が (N-1) の回で名指しした形そのもの**です ——
    「**主実行が『撃て』と言われている手が、その時刻に本当に撃てるか**」。
    そこでは「口は開いているか」を問い、**この関数は「いつ開くか」を答えます。**

    ## 何を返すか

        at          実際に読める、いちばん早い時刻（JST・aware）
        binding     "age" ＝ 齢が縛っている ／ "quota" ＝ 日枠が縛っている
        quota_at    日枠が戻る時刻（JST。読めたときだけ。読めなければ None）

    **`answer` のほうは変えません** —— あちらは「齢としては足りる時刻」で、
    それ自体は正しい事実です。**遅いほうを採るのが、実際に読める時刻**です。

    ## 覆る条件

    - `data/views.jsonl` を Data API 以外（Analytics や手元の控え）から積めるように
      なったら、日枠は縛らなくなります。そのときこの関数は `binding="age"` を
      返し続けるので、**消してよい**（`upload_cap.day_quota().open` が常に True）
    - `upload_cap.day_quota()` が読めない回は、**縛っていない側へ倒します**
      （読めないことを「閉じている」と読むと、押せる回まで押さなくなる ——
      `day_quota()` 自身と同じ考え方）
    """
    now = now or dt.datetime.now(JST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    try:
        age_at = dt.datetime.fromisoformat(str(b.get("answer_ts") or ""))
    except ValueError:
        return {"at": None, "binding": "age", "quota_at": None}
    if age_at.tzinfo is None:
        age_at = age_at.replace(tzinfo=JST)

    try:
        from src import upload_cap
        dq = upload_cap.day_quota()
    except Exception:                      # noqa: BLE001 — 読めない回は縛らない側へ
        return {"at": age_at, "binding": "age", "quota_at": None}

    if dq.open:
        # いま開いている ＝ 齢が来れば読める（窓は毎日 戻るので、
        # 齢のほうが先なら、その時点で開いているかは別の回が見ます）
        return {"at": age_at, "binding": "age", "quota_at": None}

    quota_at = dq.resets_at.astimezone(JST)
    if quota_at <= age_at:
        return {"at": age_at, "binding": "age", "quota_at": quota_at}
    return {"at": quota_at, "binding": "quota", "quota_at": quota_at}


def cap_if_window(path: pathlib.Path | None = None,
                  uploaded: pathlib.Path | None = None,
                  today: dt.date | None = None) -> dict | None:
    """**(B)「時刻の窓」だったときの上限**（枠の数。**測った天井ではありません**）。

    ## なぜ要るか（2026-08-26・最適化の回）

    `window()` は「(A) 1日 C本 と (B) T までに出した本は全部生きる の
    **どちらか分かっていない**」と、`confounded=True` で毎回言っています。
    ところが **`cap()` は (A) の数だけを返し**、`scripts/eta.py` の
    `physical_caps` はそれだけを読んで

        density 天井 ×1.00 …… **すでに上限を 1.8倍 超えて出しています ＝ 引き代なし**

    と印字していました。**分かっていないほうの枝を、断定して印字しています。**
    `CLAUDE.md` が (イ) で禁じている形そのものです ——
    「**裸の「届きません」を出さないこと。何を固定したせいでそう出たのかを
    同じ行に並べる**」。

    **`cap()` は変えません。** 軌跡は保守的な (A) の側を歩くべきで、
    測っていない (B) で歩かせると「実在しない世界」を歩きます
    （`physical_caps` の docstring が禁じている形）。**変えるのは印字だけ**で、
    ここが返すのは**その断定に添える、もう一方の枝の数**です。

    ## 数の出どころ（**全部その場の実物。書き写していません**）

        T         `window()["T"]`（実測で死線が立っている時刻）
        きざみ    `MIN_GAP_MIN`（**このファイルが既に持っている実測**。
                  08/21 に :15/:45 で詰めた7本が0再生 ＝ これより詰めると死ぬ）
        いちばん早い時刻
                  **切り分けの日にもう予約してある本**のいちばん早い時刻
                  （`booked_split_day` が名指しする日。実測 08/27 の 05:00）

    ## **これは「1日 N本 出せる」ではありません**

    このチャンネルは **08:59 より早く公開したことが一度もありません**
    （`batch_build --hour` の既定が 9）。だから **05:00 が生きるかどうかも
    測っていません。** 08/27 の切り分けの日は、**モデルの別と、早い時刻が
    生きるかを同時に**答えます。それまでは `measured: False` のままです。

    返すのは `{"cap", "earliest", "T", "step_min", "measured", "answer_on"}`、
    切り分けが済んでいる（`confounded=False`）か材料が無ければ `None`。
    """
    w = window(path)
    if not w.get("confounded") or not w.get("T"):
        return None
    try:
        end = dt.datetime.strptime(str(w["T"]), "%H:%M").time()
    except ValueError:
        return None

    booked = booked_split_day(str(w.get("first_pub") or ""), today=today,
                              uploaded=uploaded)
    if not booked:
        return None

    # **帳面の読み手を増やさないこと**（`docs/JOURNAL.md` 2026-08-25）——
    # 「後の行を採る・JST で割る」の2規則は `src.motion_groups` が持っています。
    from src import motion_groups

    at = motion_groups.scheduled_at(uploaded) if uploaded else motion_groups.scheduled_at()
    earliest: dt.time | None = None
    for when in at.values():
        if motion_groups.jst_day(when) != booked["day"]:
            continue
        t = dt.datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(JST).time()
        if earliest is None or t < earliest:
            earliest = t
    if earliest is None or earliest >= end:
        return None

    # **左端が測れていたら、そこより前から数えないこと**（2026-08-27 16:xx）。
    # ここは「切り分けの日に**予約してある**いちばん早い時刻」から数えていました。
    # 08/27 はそれが 05:00 なので **05:00〜13:30 ＝ 18枠（×1.80）** を返し、
    # `scripts/eta.py` が `density` の上振れとして印字していました。
    #
    # **その 05:00 は、同じ日に実際に置いて、死ぬのを測った時刻です**
    # （`left_edge()`。05:00〜08:30 の 8本が 0再生・全部 `public`/`processed`）。
    # **予約してあることは、再生が付くことを1つも意味しません。**
    # 左端まで詰めると 08:59〜13:30 ＝ **10枠** ＝ `cap()` と同じで、
    # **(B) の側にも上振れはありません。**
    edge = left_edge(path)
    clamped = False
    if edge:
        by = dt.datetime.strptime(edge["by"], "%H:%M").time()
        if earliest < by:
            earliest, clamped = by, True
        if earliest >= end:
            return None

    step = int(MIN_GAP_MIN)
    span = ((end.hour * 60 + end.minute) - (earliest.hour * 60 + earliest.minute))
    return {"cap": int(span // step) + 1,
            "earliest": earliest.strftime("%H:%M"),
            "T": str(w["T"]),
            "step_min": step,
            "measured": False,
            "left_edge": edge,
            "clamped": clamped,
            "answer_on": booked["answer"]}


def window_lines(path: pathlib.Path | None = None) -> list[str]:
    """**その上限が「本数」なのか「時刻の窓」なのかを、黙って断定しない。**"""
    w = window(path)
    if not w["days"]:
        return []
    blocked = [
        f"    [!] **同じ分の組があるので、{d} からは決めていません**"
        f"（{g}組・{n}本）。そこで死んだ本は「衝突で死んだ」のか"
        f"「上限で死んだ」のか割り当てられません"
        for d, g, n in w.get("blocked", [])
    ]
    if blocked:
        blocked.append("        散らしてから測ること: `python -m src.collisions` の"
                       "割り当てを `scripts/reschedule.py --move` で撃つ"
                       "（`videos.update` は JST 16:00 以降）")
    if not w["confounded"]:
        which = ("**本数のほうが上限**です（早く出しても、後ろが死ぬだけ）"
                 if w["verdict"] == "count"
                 else f"**時刻の窓のほうが上限**です（**{w['T']} JST までに出した本は全部生きる**）")
        return [f"    切り分け済み: {which}",
                f"      決めた日: {w['decided_by']}"] + blocked
    edge = w.get("left_edge")
    misfit = w.get("misfit") or []
    head = [
        "    [!] **この本数は「時刻の窓」と切り分けられていません。**",
        f"        当てはまる説明が2つあり、**どの日でも同じ数**を出します ——"
        f" (A) 1日 {w['C']}本 まで ／ (B) **{w['T']} JST** までに出した本は全部生きる。",
    ]
    if edge:
        # **左端は測れています**（2026-08-27 16:xx）。ここが埋まっている回は、
        # 「早い時刻に置けば上積み」を**もう書かないこと** —— 測って、死にました。
        head += [
            f"        **窓の左端は測れています: {edge['after']} より後・{edge['by']} まで**"
            f"（{edge['from']} に {edge['from_dead']}本 置いて、**全部 0再生**）。",
            f"        → **早い時刻に置いても上積みになりません。** {edge['by']}〜{w['T']} は"
            f"30分きざみで **ちょうど {w['C']}枠** ＝ (A) の {w['C']}本 と同じで、"
            "**(B) の側にも引き代はありません**（`cap_if_window()` はここで頭打ちにしています）。",
            "        **残っているのは右端だけ**です —— "
            f"**{w['T']} より後ろ**に置いた本が生きるかは、まだ測っていません。",
        ]
        head += [f"          {d}" for d in edge.get("days", [])]
    else:
        head += [
            f"        測れている {w['days']}日 は全部 **{w['first_pub']} JST** から始めており、"
            f"30分きざみだと {w['T']} がちょうど {w['C']}本目です。",
            "        窓のほうなら、**その時刻より前に置いたぶんは丸ごと上積み**になります"
            "（作る本数は1本も増えません）。",
            f"        **道は2つあります。** (i) **{w['first_pub']} より前**に置く"
            f"（窓のほうが**多く**予測する）／ (ii) **{w['T']} より後ろ**に置く"
            "（窓のほうが**少なく**予測する）。**同じ分に2本 置かないこと**"
            "（`ties()`。そこで死んだ本を割り当てられません）。",
        ]
    if misfit:
        head += [
            "        [!] **どちらのモデルでも説明できない日があります**"
            "（生きた**本数**は合うのに、**生きた本が入れ替わっている**）:",
        ] + [f"          {m}" for m in misfit] + [
            "          → **本数だけを見て決めないこと。** この形は "
            "`window()` が長らく `count` と**断定**していた所です"
            "（2026-08-27 に、本の取り違えで測るよう直した）。",
        ]
    return blocked + head + _booked_lines(w["first_pub"], w)


def _booked_lines(first_pub: str, w: dict | None = None) -> list[str]:
    """**その日がもう予約されているなら、そう言うこと**（2026-08-25 に足した）。

    このファイルの冒頭の註には「2026-08-27 に 05/06/07/08時 の4本を置いてあります」と
    **既に書いてありました。** それでも `window_lines()` の出力は
    「**1日作り**」で終わっており、**道具は知っているのに黙っていました。**
    註は読まれません。**出力に出ていないものは、無いのと同じです。**
    """
    # **当てはめ済みの C / T を渡すこと**（2026-08-27）。渡さないと
    # `booked_split_day()` が `window()` を呼び直し、`data/views.jsonl`
    # （2万行）を**同じ回のうちに2度**読みます。
    t = str((w or {}).get("T") or "")
    try:
        b = booked_split_day(
            first_pub,
            c=(w or {}).get("C"),
            t_min=(int(t[:2]) * 60 + int(t[3:])) if len(t) == 5 else None,
        )
    except Exception:                      # 帳面が読めない回でも出力を止めない
        return []
    if not b:
        return ["        [!] **切り分けられる日が、予約のどこにもありません。**"
                f"（門は2つ ——(A)/(B) の予測差が **{DECIDE_GAP_MIN}本 以上**・"
                "**同じ分の組が無い**。`src.day_cap.split_power()`）"
                "この回に1日 置けば、そのぶん早く切り分きます"]
    where = "**その日は、いま走っています**" if b.get("running") else "**その日はもう予約されています**"
    return [
        f"        {where}: **{b['day']}**"
        f"（{b['total']}本・うち {b['before']}本 が {first_pub} より前）"
        f" → **(A) 本数なら {b['count']}本 生き ／ (B) 窓なら {b['window']}本 生き**"
        f"（差 {b['gap']}本・同じ分の組 {b['ties']}）。",
        f"        → 生きた本数を読めるのは **{b['answer']} {b.get('answer_at', '')}** 以降"
        f"（その日の最後の本が 齢 {MIN_AGE_H:.0f}時間 になる時刻）。"
        "**もう1日作らないこと**（日を増やすほど交絡が増えます）。",
        "        **読むには、その時刻より後に `python scripts/status.py` が1回 走ること** ——"
        "`data/views.jsonl` は **Data API**（`videos.list`）で積んでいます。"
        "**Analytics の3日遅れは掛かりません**（2026-08-27 に直した。"
        "ここは長らく +5日 を足していて、答えを6日 遅らせていました）。",
    ] + _readable_lines(b) + [
        "        [!] **答えが返るまで、他の日の本数を増やさないこと** ——"
        "その日が対照です。",
    ]


def _readable_lines(b: dict) -> list[str]:
    """**齢が足りても、口が閉じていれば読めません**（2026-08-27 に足した）。

    上の行は「齢としては足りる時刻」を出します。**そこで撃てるとは言っていません。**
    `data/views.jsonl` を積むのは `scripts/snapshot.py` ＝ `videos.list`（Data API）で、
    **日枠の尽きている窓では 403** です。理由と実測は `readable_at()` の docstring。
    """
    r = readable_at(b)
    if not r.get("at") or r.get("binding") != "quota":
        return []
    return [
        f"        [!] **その時刻には読めません。** `videos.list`（Data API）の"
        f"**日枠がこの窓では尽きています** —— `scripts/snapshot.py` も"
        f"`scripts/status.py` も、いま撃つと 403 で1本も積めません"
        f"（`snapshot.py` は『1本も読めませんでした』で降ります）。",
        f"        → **実際に読めるのは {r['at']:%Y-%m-%d %H:%M} JST 以降**"
        f"（日枠が戻る時刻。齢のほうは {b['answer']} {b.get('answer_at', '')} に足ります）。"
        f"**その前に撃たないこと** —— 撃った回は 403 を1つ足すだけで、答えは1分も早まりません。",
    ]


if __name__ == "__main__":  # pragma: no cover
    for line in lines():
        print(line)


# --- 再生が付く本／付かない本を、**1か所で**決める -------------------------
#
# ## なぜここに置くか（2026-08-26。**12件目の「2か所が別々に言っている」**）
#
# このファイルは「1日に再生が付くのは 10本」「30分より詰めた本は死ぬ」を
# **実測から**持っています。ところが `src/judgeable.py` は A/B の群を
# **公開日だけ**で数えていて、**死ぬと分かっている本も1本と数えていました。**
#
# 実測（2026-08-26・`data/views.jsonl` の6時間以上たった読み）:
#
#     この帯に入る本   n=74   再生の中央値 **718**
#     入らない本       n=81   再生の中央値 **2**（>10再生 は 81本中 17本）
#
# **中央値が 359倍 違います。** 帯の外の本は、A/B の標本としては 0 です。
# それを「1本」と数えると、`falsified_if` は「上回らなければ外れ（同点も外れ）」
# なので、**足りない標本はそのまま「外れ」に化けます**
# （`src/judgeable.py` の `ANALYTICS_LAG_DAYS` の節が、同じ壊れ方を1日ぶんで書いています）。
#
# ## **結果（再生数）で落とさないこと**
#
# 落とす条件は **その日の何本目か** だけです。**中身とは無関係**に、
# 予約を置いた側が決めている量なので、処置とは独立です。
# **「再生が0だったから落とす」は結果で条件付けること**になり、
# 処置そのものが再生を落としている場合に、その効果を隠します。
# ここは順番だけを見ます。

def live_ids(rows: list[dict], path: pathlib.Path | None = None,
             *, include_long: bool = False,
             forms_path: pathlib.Path | None = None,
             uploaded_path: pathlib.Path | None = None) -> set[str]:
    """**再生が付く側の `video_id`** を返す（API 0単位。公開済みも予約も同じ規則）。

    `rows` は `ab_split.published()` の行（`at` が JST の datetime、`video_id`）。
    2段で絞ります。**`measure()` が上限を出すときと同じ2段**です:

      1. 間隔 —— 前に残した本から `MIN_GAP_MIN` 未満のものは落とす（`_spaced`）
      2. 本数 —— 残ったうちの**先頭 `cap()` 本**

    **覆る条件**: `cap()` は実測から動きます（定数ではありません）。
    上限が上がれば、ここが返す集合も自動で広がります。

    ## **ここは長尺を外します**（2026-08-30・最適化の回に既定を変えた）

    `by_day()` はもとから外していました（`include_long=False`）——
    測っているのが**ショートの面**で、長尺は `SHORTS_FEED` の枠を
    1つも使わないからです。**ここだけが外していませんでした。**

    ### 前の回（2026-08-29）が「差は 0本」と測ったのは、なぜ 0本 だったか

    あの回はこう書いていました（控えと公開済み 578本）:

        live_ids(全部)             **452本**
        live_ids(長尺を先に除く)    **452本**
        長尺が帯の枠を取っている数   **0本** ／ そのせいで落ちたショート **0本**

    **数え方が正しく、長尺の一覧のほうが空でした。** `_long_ids()` は
    `data/video_forms.json`（Analytics の `creatorContentType`）だけを読んでおり、
    あれは**公開して再生の付いた本にしか付きません** ——
    **予約ぶんの長尺が、1本も入っていませんでした**（実測 18本 対 98本・重なり 1本）。

    **「差は 0本」は、長尺を 18本 しか見なかったときの 0本 です。**
    控えの `duration_s` で数え直すと、同じ日のうちに:

        live_ids(全部)             **446本**
        live_ids(長尺を先に除く)    **437本**
        長尺が帯の枠を取っている数  **16本** ／ そのせいで落ちたショート **7本**

    **前の回が「落ちたら直す回」と書いた検査は、すでに落ちる条件を満たしていました。**
    気づけなかったのは、**検査も同じ `_long_ids()` を使っていた**からです ——
    見張りと見張られる側が同じ目で見ていた形（`_long_by_duration()` の節）。

    ### 既定を変えると何が動くか（**呼び手を全部 見た**）

    標本は**広がる向き**です（長尺が枠を明け渡し、ショートが `alive` に戻る）。

      `judgeable` / `deep_short` / `motion_groups` / `watch_eta`
          A/B の群はもともと長尺を入れません（`ab_split._shorts_only`）。
          **増えるのはショートだけ** ＝ 床に早く届く ＝ **判定が早まる向き**
      `live_slots` / `ab_slots` / `queue_lag`
          `_swap_candidates` も `band_stray` も `vid in live` を要求するので、
          **長尺は入れ替えの対象から外れます**（ショートの帯へ引きずり込まない）。
          `Board._alive_on()` が下がるぶん、その日に置けるショートが増えます
      `scripts/eta.py`
          あちらは 08/29 から**手前で `_long_ids` を引いてから渡して**いました。
          その手当てはそのまま効き、`_long_ids()` が広がったぶん正しくなります

    **`include_long=True` は、外す前後を比べるとき用**です（`by_day()` と同じ）。

    **覆る条件と検査**: `tests/test_live_ids_long_form.py`。
    長尺がショートの面（`SHORTS_FEED`）の枠を実際に食うと分かったら、
    既定を戻すこと —— そのときは `by_day()` の既定も同時に戻すこと。
    **片方だけ戻すと、また今日と同じ形になります。**
    """
    if not include_long:
        skip = _long_ids(forms_path, uploaded_path)
        if skip:
            rows = [r for r in rows if str(r.get("video_id") or "") not in skip]
    per_day: dict[dt.date, list[tuple[dt.datetime, str]]] = collections.defaultdict(list)
    for row in rows:
        when, vid = row.get("at"), str(row.get("video_id") or "")
        if isinstance(when, dt.datetime) and vid:
            per_day[when.date()].append((when, vid))
    keep: set[str] = set()
    limit = cap(path)
    for day in per_day:
        seen = sorted(per_day[day])
        spaced = _spaced([w for w, _ in seen])
        alive = {w: v for w, v in reversed(seen) if w in set(spaced)}
        for when in spaced[:limit]:
            if when in alive:
                keep.add(alive[when])
    return keep


def live_lines(rows: list[dict], path: pathlib.Path | None = None) -> list[str]:
    """予約と公開済みのうち、**何本が再生の付かない側に居るか**。"""
    keep = live_ids(rows, path)
    total = sum(1 for r in rows if r.get("video_id") and isinstance(r.get("at"), dt.datetime))
    dead = total - len(keep)
    out = [f"  予約と公開済み **{total}本** のうち、"
           f"再生が付く帯に居るのは **{len(keep)}本**／**{dead}本 は 0再生の側**"
           f"（1日 {cap(path)}本・間隔 {MIN_GAP_MIN:.0f}分）"]
    if dead:
        out.append("    **A/B の本がここに落ちていると、その群は標本が足りません。**"
                   "`python scripts/live_slots.py` が、どの前提が何本 落としているかを出します")
    return out
