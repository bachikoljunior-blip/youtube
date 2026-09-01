"""**待ちの条件を、機械が見張る。**

## なぜ要るか（2026-08-20 に、実物で踏んだ）

`scripts/retention.py` は 8/10 から、こう印字していました。

    [!] **この検定は今回効きません。**尺が 47〜56秒に固まっていて …
        **30秒設計の3本（8/16〜18）が出れば、ここで測れるようになります。**

**その3本は 8/16〜18 に出ています。** 条件は 8/18 に満ちていたのに、
**満ちたことに気づいた回が1つもありません**（気づいたのはオーナーで、10日後）。
道具は正しく「いつ測れるようになるか」を書いていました。**書いた先が、
誰も毎回は読まない場所（その道具を走らせた回の出力）だった**だけです。

**同じ壊れ方は「待ち」がある限り何度でも起きます。** 待ちを書いた回と、
条件が満ちる回は、別の回です。**あいだを繋ぐのは記憶ではなく機械です。**

## この道具がやること

`config/watches.yaml` に「何を待っているか」と「満ちる条件」を**数で**書き、
毎回の `scripts/status.py` がそれを**評価して**出します。

    [!] **満ちました** …  → 走らせるコマンド
    あと N …            → まだのものは、残りを数で

**外の口を1つも叩きません**（手元の `data/*.jsonl` だけ）。日枠が閉じている
回でも、待ちは必ず見えます。

## 満ちたものを黙らせる唯一の方法は、答えを書くこと

満ちた待ちは `answered:` に1行（日付と答え）を入れるまで鳴り続けます。
**「見た」では消えません。** 消すには判定するしかない、という形にしてあります。
"""
from __future__ import annotations

import collections
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

CONFIG = ROOT / "config" / "watches.yaml"
SCAN = ROOT / "data" / "scan.jsonl"
UPLOADED = ROOT / "data" / "uploaded.jsonl"
LAG = ROOT / "data" / "analytics_lag.jsonl"
CRITIQUE = ROOT / "data" / "critique.jsonl"
#: **鳴った回を積む帳面。** 満ちて答えの無い待ちが、何回ぶん放置されたか。
RINGS = ROOT / "data" / "watch_rings.jsonl"
BATCH_RUNS = ROOT / "data" / "batch_runs.jsonl"


@dataclass
class Gauge:
    """**いまの値と、要る値。** 単位はそのまま画面に出す。"""

    now: float
    need: float
    unit: str = ""
    note: str = ""
    err: str = ""

    @property
    def met(self) -> bool:
        return not self.err and self.now >= self.need

    @property
    def left(self) -> float:
        return max(0.0, self.need - self.now)


@dataclass
class Watch:
    id: str
    what: str
    cond: str
    then: str
    source: str
    kind: str
    params: dict = field(default_factory=dict)
    answered: str = ""

    def gauge(self) -> Gauge:
        fn = KINDS.get(self.kind)
        if fn is None:
            return Gauge(0, 1, err=f"kind `{self.kind}` は実装がありません")
        try:
            return fn(self.params)
        except Exception as exc:                               # noqa: BLE001
            # **計器が落ちても回は止めない。** ただし黙らない（err を出す）。
            return Gauge(0, 1, err=f"{type(exc).__name__}: {str(exc)[:90]}")


# ---------------------------------------------------------------- 手元の材料

#: **動かない指標**（後ろの一枚から補ってよいもの）。
#: 尺は Data API の `contentDetails.duration` から来ます。**動画の尺は変わりません**。
IMMUTABLE_METRICS = ("尺",)


def _row_metrics(line: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for k, v in json.loads(line)["values"].items():
        if k.startswith("動画.") and k.count(".") >= 2:
            _, vid, metric = k.split(".", 2)
            rows.setdefault(vid, {})[metric] = v
    return rows


def _last_scan() -> dict[str, dict]:
    """走査の最後の一枚から、動画べつの指標を組み立てる。

    **尺だけは、後ろの一枚から補います**（2026-08-21 03:0x に踏んだ）。

    走査は Analytics と Data API の**2本**から作られていて、**枠が別**です。
    Data API の1日枠（10,000単位）は太平洋時間の0時 ＝ **JST 16:00** に戻るので、
    その手前の数時間は `videos.list` が 403 を返し、走査は
    **Analytics の指標だけ・尺の欄が丸ごと空**の一枚を積みます。

    `_last_scan()` は最後の一枚を無条件で採っていたので、その一枚が積まれた瞬間に
    **尺を読む待ち（`length_spread`）が全部「読めません」に落ちました** ——
    実測: 8/20 23:52 の一枚は 29本ぶんの尺を持っていて、01:3x の一枚は 0本。
    **在るのに読んでいないだけ**で、しかも毎日その時間帯に必ず起きます。

    動く数（`views` など）を古い一枚から混ぜるのは間違いですが、
    **尺は動きません**。だから補ってよいのは `IMMUTABLE_METRICS` だけです。

    ## **補いは「後ろの一枚」で止めないこと**（2026-08-30 に測って直した）

    ここは長らく、**尺を持つ最初の一枚を見つけた時点で `missing.remove(mt)`**
    していました。**一枚が全部の本を持っている前提**です。持っていません ——
    走査の一枚は「この窓で再生のあった本」で作られ、Data API が
    途中で 403 になれば**その一枚は部分的に埋まります。**

    実測（2026-08-30 02:4x・`data/scan.jsonl` 240枚）::

        最後の一枚          156本 ／ 尺を持つ本 **0本**（Data API が日枠で 403）
        一枚だけ補う（前）   尺が付いた本 **50本** → 180秒以上 **6本** ＝ **19再生**
        全部の枚を補う（後） 尺が付いた本 **156本** → 180秒以上 **18本** ＝ **137再生**

    **7.2倍 の取りこぼしです。** そしてこれは印字だけの話ではありません ——
    待ち `長尺-1000再生`（`config/hypotheses.yaml` の「長尺の登録率は
    ショートより1桁以上高い」＝ 腕 `sub_rate` ／ 側 `dist`。`--alloc` が
    **いちばん早い腕**と名指ししているもの）が、この数で満ち具合を見ています。

        待ち（`_k_scan_sum`）      **19 / 1000**・伸び **-8.00/日** → **届きません**
        台帳（`deadline_check`）   **286 / 1000**・伸び 26.0/日 → **2026-09-27**

    同じ閾値を見ている2つが **15倍** ちがっていました。しかも「どの一枚が
    最初に尺を持つか」は回ごとに変わるので、**満ち具合が上下します** ——
    再生は減らないのに `伸び -8.00/日` と出ていたのはこれです（実測の増減ではなく、
    **補いに当たった一枚の当たり外れ**）。**負の伸びは、この関数の影でした。**

    **覆る条件**: `IMMUTABLE_METRICS` に「動くもの」が足されたら、この全走査は
    そのまま古い値を混ぜる道になります（`setdefault` なので新しい側が勝ちますが、
    **最後の一枚に欠けている本には古い値が入ります**）。足すときは、
    そのたびに「本当に動かないか」を確かめること。検査は
    `tests/test_watches_scan_backfill.py`。
    """
    lines = [l for l in SCAN.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = _row_metrics(lines[-1])
    missing = [mt for mt in IMMUTABLE_METRICS
               if any(mt not in v for v in rows.values())]
    for line in reversed(lines[:-1]):
        if not missing:
            break
        older = _row_metrics(line)
        for mt in list(missing):
            got = {vid: v[mt] for vid, v in older.items() if mt in v}
            if not got:
                continue
            for vid, val in got.items():
                # **その一枚に居る本にだけ**入れる（消えた本を呼び戻さない）
                if vid in rows:
                    rows[vid].setdefault(mt, val)
            # **まだ欠けている本が居るなら、もっと後ろの一枚も読むこと。**
            # 一枚で打ち切っていたのが 2026-08-30 の欠陥（上の docstring）。
            if all(mt in v for v in rows.values()):
                missing.remove(mt)
    return rows


def _uploaded() -> list[dict]:
    if not UPLOADED.exists():
        return []
    out = []
    for line in UPLOADED.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _uploaded_ats() -> dict[str, datetime]:
    """動画ID → **投稿した時刻**（`uploaded_at`）。

    **公開日ではありません。** 台本の作りを変えたとき、
    予約ずみの在庫は**古い作りのまま先の日付で公開される**ので、
    公開日で切ると新旧が混ざります（2026-08-24 に登録の依頼を入れたとき、
    在庫が 09/24 まで埋まっていて実際にそうなった）。
    **作りの変更を測る窓は、投稿時刻で切ること。**
    """
    out: dict[str, datetime] = {}
    for r in _uploaded():
        at, vid = r.get("uploaded_at"), r.get("video_id")
        if not at or not vid:
            continue
        try:
            out[vid] = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            continue
    return out


def _stockpile_ids(today: str | None = None) -> set[str]:
    """**控えのうち「作り置き」の動画ID**（規則2・`src/house_rule.is_stockpile`）。

    ## なぜ要るか（2026-09-01・最適化の回に、実測で踏んだ）

    `_publish_dates()` は **予約ぶんも入れます**（docstring がそう書いています）。
    そのまま `_k_published_count()` の `placed` に入るので、待ちの note は
    こう印字していました（実測 2026-09-01・`配信抑制-0824`）:

        いま 16 / 要る 30 … **予約表では 66本**（差 50本 は
        「出ていない」ではなく**「まだ実データが来ていない」**）

    **その 50本 は来ません。** 同じ日に数えた実測 ——
    **控えの未来の予約 293本 は、293本 とも作り置き**でした
    （`house_rule.is_stockpile` ・ 作り置きでない未来の予約は **0本**）。
    オーナーが 2026-08-31 に固定した規則2（作り置きをしない）の下では、
    **`pool_drain --apply` が外して非公開のまま置きます ＝ 1本も公開されません。**

    `src/house_rule.py` は、この壊れ方を名指しで警告しています ——
    **「これから出る本」として数えると、在りもしない供給で日付が早く出ます。**
    **「外した結果、到達日は後ろへ動きます。それが正しい姿です。隠さないこと。」**

    ## 何が変わるか

    「差 50本 は実データ待ち」を読んだ回は、**供給は足りている、待てばよい**と読みます。
    実際には この待ちは **規則の 1日1本 で作る新しい本でしか満ちません。**
    `scripts/eta.py` は毎回「**軌跡の腕が動くのは、前提を1件 閉じたときだけ**」と
    印字しているので、**満ちない待ちを「待てばよい」と読ませることは、
    到達日をそこで止めることと同じ**です。

    ## 覆る条件

    オーナーが規則2 を外したら（`house_rule.STOCKPILE_IS_SUPPLY` が `True`）、
    `is_stockpile()` が全部 `False` を返すのでこの集合は空になり、
    note の警告は自然に消えます。**ここを個別に直す必要はありません。**
    """
    try:
        from src import house_rule                              # noqa: PLC0415
    except Exception:                                           # noqa: BLE001
        return set()                                            # 読めない回は黙る
    out: set[str] = set()
    for r in _uploaded():
        vid = r.get("video_id")
        if not vid:
            continue
        try:
            if house_rule.is_stockpile(r, today):
                out.add(str(vid))
        except Exception:                                       # noqa: BLE001
            continue
    return out


def _publish_dates() -> dict[str, date]:
    """動画ID → 公開日（JST）。**予約ぶんも入ります**（`at` は予約時刻）。

    控えは 8/16 以降しかありません。それより前の本は入りません ——
    いま見張っている待ちは全部それより後の窓なので、足りています。
    **前を数える待ちを足すときは、`data/views.jsonl` からの復元
    （`scripts/per_day_views.published_at`）に替えること。**
    """
    out: dict[str, date] = {}
    for r in _uploaded():
        at = r.get("at") or r.get("uploaded_at")
        vid = r.get("video_id")
        if not at or not vid:
            continue
        try:
            out[vid] = datetime.fromisoformat(
                str(at).replace("Z", "+00:00")).astimezone(JST).date()
        except ValueError:
            continue
    return out


def analytics_last_day() -> date | None:
    """**実データがどこまで届いているか**（`status.py` が毎回積んでいる点）。

    公開しただけでは判定できません。**Analytics の日次は3日遅れる**ので、
    「本が出たか」ではなく「**その本の日に行が立ったか**」で数える待ちが要ります。
    """
    try:
        rows = [json.loads(x) for x in LAG.read_text(encoding="utf-8").splitlines()
                if x.strip()]
        return date.fromisoformat(max(r["last_day"] for r in rows))
    except Exception:                                          # noqa: BLE001
        return None


def _cv(xs: list[float]) -> float:
    """変動係数（ばらつき ÷ 平均）。単位の違うものを比べるので平均で割る。"""
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    if not m:
        return 0.0
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5 / m


def _day(s: str) -> date:
    return date.fromisoformat(str(s))


# ---------------------------------------------------------------- 条件の種類

def _k_length_spread(p: dict) -> Gauge:
    """尺のばらつき。**そろっていると、秒の軸と割合の軸が同じものになる。**"""
    scan = _last_scan()
    lens = [v["尺"] for v in scan.values()
            if v.get("尺") and v.get("views", 0) >= p.get("min_views", 1)]
    if len(lens) < 2:
        return Gauge(0, p["need"], "ばらつき", err="尺の読める本が2本ありません")
    return Gauge(_cv(lens), float(p["need"]), "ばらつき",
                 f"{len(lens)}本・{min(lens):.0f}〜{max(lens):.0f}秒")


def _durations() -> dict[str, float]:
    """動画ID → 尺（秒）。控え（`data/uploaded.jsonl`）の `duration_s` から。

    **`_last_scan()` の「尺」ではありません。** あちらは走査に載った本
    ＝ **もう実データの来た本**しか持たないので、`published_count` が
    数えたい「窓のなかに公開した本」には、まだ載っていないものが混じります。
    控えは投稿した瞬間に書かれるので、**予約ぶんも数えられます。**
    """
    out: dict[str, float] = {}
    for r in _uploaded():
        vid, sec = r.get("video_id"), r.get("duration_s")
        if not vid or sec is None:
            continue
        try:
            out[vid] = float(sec)
        except (TypeError, ValueError):
            continue
    return out


def _k_reveal_hold_arm(p: dict) -> Gauge:
    """**「完成形の保持」で比べられる本**（`src/reveal_hold`）。両群の少ないほう。

    ## なぜ `published_count` では足りないのか（2026-08-31 に測って足した）

    すぐ下の `_k_published_count()` は**公開日**で数えます。ところがこの前提の
    処置群を決めているのは**作った時刻**（`uploaded_at`）で、予約は 5〜6週 先まで
    入っているので、**08/27 以降に公開された本の大半は、それ以前に作った本**です。

    実測 2026-08-31 —— この待ちは「**満ちました（17 / 16）**」と出ていましたが、

        公開日で数えた（この待ちの前の数え方）        **17**
        作った時刻で割った処置群・本で畳んで          **11**
        うちショート（長尺は `reveal_variants` を通らない） **8**
        齢48時間 を超えた ＝ `falsified_if` が比べられる  **1**

    **満ちていません。** 満ちた待ちは `status.py` が `[!]` で出し、Stop フックが
    引き止めるので、**「判定しろ」と毎周 押し続けていました。**
    `config/hypotheses.yaml` の `count_expr` も同じ日に同じ理由で直しています。
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src import reveal_hold                                # noqa: PLC0415

    both = reveal_hold.comparable()
    now = min(len(both["処置"]), len(both["対照"]))
    ready = reveal_hold.next_ready(int(p.get("need") or 16))
    note = (f"処置 {len(both['処置'])} ／ 対照 {len(both['対照'])}"
            f"（**作った時刻で割る。公開日ではありません**）")
    if ready:
        note += f" ／ 予約表では {ready} にそろう"
    return Gauge(now, float(p["need"]), "本", note)


def _k_published_count(p: dict) -> Gauge:
    """窓のなかに公開した本数。`data_ready: true` なら**実データの来た本だけ**。

    **`min_duration_s` / `max_duration_s` で形を絞れます**（2026-08-27 に足した）。
    絞らないと、ショートが 9割 を占めるこのチャンネルでは
    **「長尺を14本 出したか」の門が、ショートだけで満ちます。**
    尺の分からない本（控えに `duration_s` が無い古い行）は、
    **絞りを指定した回では数えません** —— 満ちていないものを満ちたと
    言うより、遅れて満ちるほうが安全なので。

    ## **`data_ready` で削ったぶんを、同じ行に出します**（2026-08-30 に足した）

    **「いま 0」は「まだ数えられていない」であって「出ていない」ではありません。**
    ところが画面ではその2つが同じ字で出ます。実測（08/30 07:4x・`長尺シェア-14本`）:

        画面        あと **14本**（いま **0** / 要る 14）  2026-08-27〜2026-09-07
        控えの実物  窓の中に **49本**（08/28=8・08/31=5・09/03=5 …）＝ 要る本数の **3.5倍**

    0 なのは `data_ready: true` が「Analytics の最終日（08/27）より後の公開」を
    落とすからで、**08/27 の長尺がちょうど 0本**だったためです。
    **窓のあいだじゅう「あと14本」と鳴り続けるので、読んだ回は
    「供給が足りない」と読み、もう 3.5倍 入っている窓へ長尺を積み増す側に効きます。**

    だから `data_ready` が削ったときは、**削る前の数を note に出します**
    （「予約表では N本」）。**判定の数（`now`）は動かしません** ——
    実データの来ていない本で前提を閉じるほうが危険です。

    **覆る条件**: `data_ready` を使う待ちが「予約表の数 ＜ 要る数」の側で
    使われるようになったら、この行は毎回 同じことを言うだけになります
    （そのときは `need` に届いていない回だけ出すこと）。

    ## **その「予約表では N本」は、作り置きを供給に数えていました**（2026-09-01）

    上の註は「差 N本 は**まだ実データが来ていない**」と言い切っています。
    **来ない本が混ざっていました。** 実測 2026-09-01 ——
    **控えの未来の予約 293本 は、293本 とも作り置き**
    （`house_rule.is_stockpile`・作り置きでない未来の予約は **0本**）。
    規則2 の下では `pool_drain --apply` が外すので、**1本も公開されません。**

    だから差の内訳を出します（`_stockpile_ids()` に理由と実測）——
    **来る本だけで満ちるなら黙り、足りないぶんだけを「あと N本・最短 N日」**として
    出します。窓が閉じていて規則1 が許す本数に届かない待ちは、
    **「永久に満ちません」**と言い切ります（`house_rule.cap()`）。
    """
    dates = _publish_dates()
    since, until = _day(p["since"]), (_day(p["until"]) if p.get("until") else None)
    last = analytics_last_day()
    if p.get("data_ready") and last is None:
        return Gauge(0, float(p["need"]), "本", err="実データの最終日が読めません")
    lo, hi = p.get("min_duration_s"), p.get("max_duration_s")
    secs = _durations() if (lo is not None or hi is not None) else {}
    n = 0
    placed = 0
    stock = 0                       # placed のうち **作り置き**（規則2・公開されない）
    stock_ids = _stockpile_ids()
    for vid, d in dates.items():
        if d < since or (until and d > until):
            continue
        if lo is not None or hi is not None:
            sec = secs.get(vid)
            if sec is None:
                continue
            if lo is not None and sec < float(lo):
                continue
            if hi is not None and sec > float(hi):
                continue
        placed += 1
        if p.get("data_ready") and last and d > last:
            # **まだ数えていない本**。そのうち作り置きは「実データ待ち」ではなく
            # **来ない本**です（規則2・`_stockpile_ids()`）。
            if vid in stock_ids:
                stock += 1
            continue
        n += 1
    note = f"{since}〜{until or '以降'}"
    if lo is not None or hi is not None:
        note += f" / 尺 {lo or 0:.0f}〜{hi if hi is not None else '∞'}秒"
    if p.get("data_ready") and last:
        note += f" / 実データは {last} まで"
        if placed > n:
            note += (f" / **予約表では {placed}本**（差 {placed - n}本 は"
                     "「出ていない」ではなく「まだ実データが来ていない」）")
    # **作り置きは供給ではありません**（規則2・2026-09-01 に足した。
    # 理由と実測は `_stockpile_ids()` の docstring）。
    # **満ちている待ちには出しません** —— 満ちた後の「あと0本」は毎回 同じ字が
    # 増えるだけで、読む側の手を1つも変えません（`_k_published_count` の
    # 「覆る条件」と同じ姿勢）。
    # **足りない数を、来る本だけで数え直します。** 作り置きを引いてなお
    # 足りるなら、この待ちは実データで満ちます —— **そのときは黙ること。**
    # （満ちる待ちに毎回 同じ警告を出すと、読む側の手を1つも変えません）
    short = max(0, int(float(p["need"])) - n)
    waiting = placed - n
    real = waiting - stock                    # 本当に「実データ待ち」の本
    gap = short - real                        # 新しく作らないと埋まらない本数
    # **窓が閉じている待ちは、規則が許す本数のほうが先に効きます。**
    # 09/25〜09/26 の2日に 5本 を要る待ちは、1日1本 の下では**永久に満ちません**
    # （`src/house_rule.unreachable_needs()` が台帳の `needs` に対してやっていることを、
    #   待ちの側でもやります —— 待ちは `needs` を通らないので、あちらでは見えません）。
    if stock and gap > 0 and until:
        try:
            from src import house_rule as _hr                   # noqa: PLC0415
            span = (until - since).days + 1
            allowed = span * _hr.cap()
            if float(p["need"]) > allowed:
                note += (f"  [!] **この待ちは規則の下では永久に満ちません** —— "
                         f"窓は {span}日（{since}〜{until}）で、規則1 が許すのは "
                         f"**{allowed}本**。要る **{int(float(p['need']))}本** に届きません"
                         "（`src/house_rule.cap()`）。**待っても来ません。** "
                         "要件を 1日1本 で届く形に書き直すか、この前提を"
                         "**公開ずみの日で閉じること**（`docs/trigger_main.md` §4 の `verdict`）")
                return Gauge(n, float(p["need"]), "本", note)
        except Exception:                                       # noqa: BLE001
            pass                                                # 読めない回は下へ落とす
    if stock and gap > 0:
        note += (f"  [!] **その差 {waiting}本 のうち {stock}本 は作り置きです**"
                 "（規則2・`src/house_rule.is_stockpile`）—— "
                 "**`pool_drain --apply` が外すので、1本も公開されません。**"
                 f" 本当に実データ待ちなのは {real}本 だけなので、"
                 f"**あと {gap}本** は**規則の 1日1本 で これから作る本**でしか"
                 f"埋まりません（**最短 {gap}日**）。"
                 "**「予約に在るから待てばよい」ではありません。** "
                 "満ちる形に要件を書き直すか、公開ずみの日で閉じること"
                 "（`docs/trigger_main.md` §4 の `verdict`）")
    return Gauge(n, float(p["need"]), "本", note)


def _k_scan_sum(p: dict) -> Gauge:
    """走査の最後の一枚で、条件に合う本の指標を合計する（再生・登録など）。"""
    scan = _last_scan()
    dates = _publish_dates()
    metric = p.get("metric", "views")
    since = _day(p["published_since"]) if p.get("published_since") else None
    # **投稿時刻で切る窓**（台本の作りを変えたときは、こちらでないと在庫が混ざる）
    up_since = None
    if p.get("uploaded_since"):
        up_since = datetime.fromisoformat(
            str(p["uploaded_since"]).replace("Z", "+00:00"))
    ups = _uploaded_ats() if up_since else {}
    total, n = 0.0, 0
    for vid, v in scan.items():
        length = v.get("尺") or 0
        if p.get("min_length") and length < p["min_length"]:
            continue
        if p.get("max_length") and length > p["max_length"]:
            continue
        if since and (vid not in dates or dates[vid] < since):
            continue
        if up_since and (vid not in ups or ups[vid] < up_since):
            continue
        total += float(v.get(metric, 0) or 0)
        n += 1
    return Gauge(total, float(p["need"]), p.get("unit", metric), f"{n}本の合計")


def _k_days_with_min_videos(p: dict) -> Gauge:
    """**「その本数で置いた日」が何日たまったか。** 若い日は数えない。"""
    counts: dict[date, int] = {}
    for d in _publish_dates().values():
        counts[d] = counts.get(d, 0) + 1
    today = datetime.now(JST).date()
    age = int(p.get("min_age_days", 0))
    days = [d for d, c in counts.items()
            if c >= int(p["per_day"]) and (today - d).days >= age]
    note = f"{len(days)}日（{int(p['per_day'])}本以上・公開から{age}日以上）"
    if days:
        note += f" 直近 {max(days)}"
    return Gauge(len(days), float(p["need"]), "日", note)


def _k_scored_pairs(p: dict) -> Gauge:
    """**点を付けた本のうち、実績と突き合わせられるもの。**

    `scripts/critique_record.py --check` の突き合わせを、外の口を叩かずに
    数えます（あちらは Analytics、こちらは走査の最後の一枚）。
    """
    if not CRITIQUE.exists():
        return Gauge(0, float(p["need"]), "本", err="critique.jsonl がありません")
    scan = _last_scan()
    topic_to_video = {r["topic"]: r["video_id"] for r in _uploaded()
                      if r.get("topic") and r.get("video_id")}
    seen: set[str] = set()
    for line in CRITIQUE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            key = json.loads(line).get("video", "")
        except ValueError:
            continue
        vid = key if key in scan else topic_to_video.get(key, "")
        if vid and scan.get(vid, {}).get("views", 0) >= p.get("min_views", 30):
            seen.add(vid)
    return Gauge(len(seen), float(p["need"]), "本",
                 f"{p.get('min_views', 30)}再生以上で突き合わせ可能")


def _ab_group_from_sources(name: str) -> Gauge:
    """`src/judgeable` の群が、**落ち着いた本**で床に届いたか。

    `Floor.groups` は公開日の一覧なので、**落ち着いた本 ＝ 今日から
    `SETTLE_DAYS + ANALYTICS_LAG_DAYS` 引いた日までに公開した本**です。
    **遅れを引かないと、報告されていない本を数えます。**

    **`SOURCES` に無くても諦めないこと**（2026-08-26 22:5x に踏んだ）。
    `judgeable.ACCRUING` に入っている群（いまは `request_form`）は
    `SOURCES` から**わざと外れています** —— 外れているのは「期限の出し方」の
    話であって、**群の数え方と床は `MEMBER_SOURCES` に在ります。**
    ここで `SOURCES` だけを見ると、その群は「ありません」で落ちます。
    """
    from datetime import timedelta

    from src import ab_split, judgeable

    src = judgeable.SOURCES.get(name)
    if src is None:
        member_src = judgeable.MEMBER_SOURCES.get(name)
        if member_src is None:
            return Gauge(0, 1.0, "本",
                         err=f"{name}: `src/judgeable.MEMBER_SOURCES` にありません")
        _make_members, need = member_src
        src = ((lambda k=name: judgeable._days(judgeable.members(k))), need)
    make, need = src
    lag = ab_split.SETTLE_DAYS + judgeable.ANALYTICS_LAG_DAYS
    today = datetime.now(JST).date()
    cutoff = today - timedelta(days=lag)
    groups = {g: sorted(days) for g, days in make().items()}
    ready = {g: sum(1 for d in days if d <= cutoff) for g, days in groups.items()}
    if not ready:
        return Gauge(0, float(need), "本", err=f"{name}: 群が1つも立っていません")
    note = ("落ち着き " + " / ".join(f"{g} {n}本" for g, n in sorted(ready.items()))
            + _ab_bottleneck(groups, need, today, lag))
    return Gauge(min(ready.values()), float(need), "本", note)


def _ab_bottleneck(groups: dict[str, list], need: int, today, lag: int) -> str:
    """**足りないのは「本」か「齢」か。** 目盛りの数字だけでは区別が付きません。

    ## なぜ要るか（2026-08-27 に実測して足した）

    `Gauge.left` は `床 − 落ち着いた本` なので、画面には必ず

        あと **16本**  題の問い-両群16本（いま 0 / 要る 16）  問い 0本 / 断定 0本

    と出ます。**これは「16本 作れ」と読めます。**
    ところが同じ日の実測では、群には **問い 56本 / 断定 65本** が既に居ました
    （`judgeable.members("title_form")`）。**1本も作る必要がありません** ——
    足りないのは公開からの齢（`SETTLE_DAYS + ANALYTICS_LAG_DAYS`）だけで、
    床に届くのは **2026-09-05**（あと 9日）です。

    同じ日の 6件のうち **4件**（`title_form` 56/65本・`hook_form` 43/50本・
    `stat_split` 67/317本・`opening_motion` 28/8本）が この形でした。
    本当に本が足りないのは `slide_pace`（5/3本・床16）と
    `request_form`（20/22本・床72）の 2件だけです。

    **`eta.py` は同じ回に「本数を増やしても在庫を増やしても、日付は動きません」
    （腕 `density` の天井 ×1.00）と印字しています。** 目盛りを字面どおりに読んだ回は、
    1日も早まらない側へ丸ごと持っていかれます。

    ## **これは一度、1件だけ直されています**

    `config/hypotheses.yaml` の `opening_motion` には 2026-08-26 の註で
    「**本数は足りていて、縛っているのは日付でした**」と書いてあり、
    その前提の**期限だけ**が 09-13 → 10-16 へ延ばされています。
    **直したのは1件で、そう読ませている目盛りのほうは直っていませんでした。**
    （受け取り帳 `e6d3be89`・オーナー 2026-08-23「失敗したならそこだけ直すんじゃなくて
    応用しないの？」）

    **覆る条件**: 群に居る本が予約から消える（取り消し・生成失敗）なら、
    「本は足りている」は嘘になります。数えているのは控えの予約なので、
    予約が減れば次の回の同じ行が本数側へ倒れます。
    """
    from datetime import timedelta

    short = {g: need - len(ds) for g, ds in sorted(groups.items()) if len(ds) < need}
    have = " / ".join(f"{g} {len(ds)}本" for g, ds in sorted(groups.items()))
    if short:
        return (f" ／ **本が足りません** —— 群 {have}（床 {need}本）。"
                + "**あと " + " / ".join(f"{g} {n}本" for g, n in short.items()) + "**")
    settles = max(ds[need - 1] for ds in groups.values()) + timedelta(days=lag)
    left = (settles - today).days
    if left <= 0:
        return f" ／ 群 {have}（床 {need}本）"
    return (f" ／ **足りないのは本ではありません** —— 群 {have}（床 {need}本）。"
            f"**床に届くのは {settles}（あと {left}日）** ＝ 齢待ち。"
            "**ここに本を足しても1日も早まりません**")


def _k_ab_group(p: dict) -> Gauge:
    """A/B の**少ないほうの群**が、判定に要る本数に届いたか。

    数えているのは `src/judgeable.MEMBER_SOURCES` です（**同じ数を2箇所で持たない**）。
    ここは「その数を毎周ここにも出す」ためだけの入口。

    ## **`ab_split.MIN_PER_GROUP` を床に使わないこと**（2026-08-26 22:5x に踏んだ）

    ここは長らく「`name in ab_split.EXPERIMENTS` なら `MIN_PER_GROUP`（16）」で
    割っていました。**`request_form` の床は 72本 です**
    （`src/judgeable.MEMBER_SOURCES`・`config/hypotheses.yaml` の両方が
    「**16本 を写さないこと**」と明記しています —— 測っているのが
    engaged ではなく**登録**だから）。実測の症状:

        あと **13本**  途中の依頼-両群72本（いま 3 / **要る 16**）

    **見出しは 72本 と言い、目盛りは 16本 で割っています。**
    このまま 16本 で「満ちました」が鳴ると、`stop_check.sh` がその回を
    引き止め、**片群 6,700再生（期待 2.1人）で登録率を比べる**ことになります。
    `falsified_if` は「上回らなければ外れ（同点も外れ）」なので、
    **見分けられない標本で判定すると、そのまま「外れ」に化けます。**

    ## **数え方も `ab_split.split_counts` ではありません**（同じ回）

    `split_counts` は `exp.split(topic)` を**全部の本**に当てるので、
    **長尺も群に入ります。** 長尺は依頼そのものを書かない（`script_writer.ROLE`）ので
    どちらの群でもなく、`judgeable._members_by_request_form()` は
    控えの `duration_s` で落としています。実測の食い違い:

        この目盛り        終端のみ **6本** / 途中あり 3本
        judgeable 側      終端のみ **5本** / 途中あり 3本   ← 長尺が1本 混ざっていた

    **`MEMBER_SOURCES` に在る群は、床も数え方もそちらに訊くこと。**
    """
    from src import ab_split, judgeable

    name = p["experiment"]
    if name in judgeable.MEMBER_SOURCES:
        # **群の作り方も床も1か所**（`judgeable.MEMBER_SOURCES`）に置いてあるので、
        # ここは数えるのではなく訊くこと。`ACCRUING` で `SOURCES` から
        # 外れている群（`request_form`）も、あちらが拾います。
        return _ab_group_from_sources(name)
    if name not in ab_split.EXPERIMENTS:
        return _ab_group_from_sources(name)
    exp = ab_split.EXPERIMENTS[name]
    counts = ab_split.split_counts(exp)
    ready = counts.treated_ready
    # **ここでも `MIN_PER_GROUP` を写さないこと**（2026-08-27 に潰した。**6件目**）。
    #     この枝は `MEMBER_SOURCES` に無い実験だけが通るので、**いまは死に枝**です
    #     （3件とも上で拾われます）。ただし床の違う実験がこれから足されたら、
    #     **この2行が黙って 16本 で割ります** —— 上の註が防ごうとしている、
    #     まさにその形。`floor_of()` は `MEMBER_SOURCES` に無い名前を
    #     `MIN_PER_GROUP` に落とすので、**いまの値は1つも変わりません。**
    floor = float(ab_split.floor_of(name))
    if not ready:
        return Gauge(0, floor, "本",
                     err=f"{p['experiment']}: 群が1つも立っていません")
    low = min(ready.values())
    note = " / ".join(f"{g} {n}本" for g, n in sorted(ready.items()))
    return Gauge(low, floor, "本", note)


def _k_error_reasons(p: dict) -> Gauge:
    """**理由の入った生成失敗が、判定に要る本数たまったか**（2026-08-25 に足した）。

    見るのは `data/batch_runs.jsonl` の `results[].error_reason` です。
    **理由の無い行は数えません** —— 2026-08-24 より前は `build_one` が
    出力を捨てていたので理由が1文字も残っておらず、
    **分母に入れると必ず薄まります**（対応する仮説の `falsified_if` が
    「`error_reason` の無い行は数えないこと」と明記している、その分母です）。

    `long: true` を渡すと長尺の回だけを数えます。
    """
    if not BATCH_RUNS.exists():
        return Gauge(0, float(p["need"]), "本",
                     err="batch_runs.jsonl がありません")
    want_long = bool(p.get("long"))
    reasons: list[str] = []
    for line in BATCH_RUNS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if want_long and not row.get("long"):
            continue
        for item in row.get("results", []):
            why = (item or {}).get("error_reason")
            if why:
                reasons.append(str(why)[:24])
    top = collections.Counter(reasons).most_common(2)
    note = ("理由つきの失敗のみ"
            + ("（長尺）" if want_long else "")
            + ("　" + " / ".join(f"{k}×{n}" for k, n in top) if top else ""))
    return Gauge(len(reasons), float(p["need"]), "本", note)


def _k_deep_shorts(p: dict) -> Gauge:
    """**深い題（`s-` で始まらない）を、ショートの車線で何本 出したか**（2026-08-26 に足した）。

    見るのは `data/batch_runs.jsonl` です。`long` が偽の回 ＝ ショートの車線
    （`batch_build.build_one()` は `--long` が無ければ `--short` を付けるだけで、
    **題の id が `s-` かどうかは見ていません**）。そこに載った
    **`s-` で始まらない題**が、この待ちの数えるものです。

    **`video_id` の無い本は数えません** —— 生成に失敗した本は公開されないので、
    比べる群にも入りません。**分母に入れると、待ちだけが先に満ちます。**

    対応する仮説の `needs.count_expr` と**同じ数え方**にしてあります。
    片方だけ直すと、待ちが鳴る日と判定できる日がずれます。
    """
    if not BATCH_RUNS.exists():
        return Gauge(0, float(p["need"]), "本", err="batch_runs.jsonl がありません")
    since = str(p.get("since") or "")
    n = 0
    for line in BATCH_RUNS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("long"):
            continue                       # 長尺の車線は数えない
        if since and str(row.get("at", ""))[:10] < since:
            continue
        for item in row.get("results", []):
            item = item or {}
            if item.get("video_id") and not str(item.get("topic", "")).startswith("s-"):
                n += 1
    return Gauge(n, float(p["need"]), "本",
                 f"{since or '全期間'} 以降・ショートの車線に載った深い題")


def _k_hypothesis_needs(p: dict) -> Gauge:
    """**その前提自身の `needs` を、そのまま目盛りにする**（2026-08-29 に足した）。

    ## なぜ要るか

    `tests/test_watches.py::test_数の門を持つ未判定の仮説は台帳を指している` が
    2件で赤いままでした（09-19「族を外へ出しても1本あたり再生は変わらない」／
    10-22「登録は配信の広さで決まる」）。どちらも `falsified_if` に数の床が
    ありますが、**既存の kind では書けません** ——
    片方は「**題が `s-ribo-` で始まるショート 8本**」、
    もう片方は「**累計再生 342回 未満の本の再生合計が 20,000回**」。

    **写して新しい kind を増やすのは、同じ数を2箇所で持つことです。**
    このファイルは 2026-08-27 に、まさにそれで食い違っています
    （`_hypothesis_judge_state` の上の註 ——「数え方を写し直すのは、
    同じ事故をもう一度 予約すること」）。だから写さず、
    **`config/hypotheses.yaml` の `needs` に直接 訊きます。**

    いちばん足りていない `needs` を目盛りにします（`have / need` の最小）。
    `count_expr` を持たない `needs` しか無い前提は、床が数ではないので
    **読めません**と返します（黙らせません）。

    **覆る条件**: `deadline_check` が `count_expr` の評価をやめたら、ここも
    そこへ合わせること。**この関数の中で数え直さないこと。**
    """
    claim = str(p.get("claim") or "")
    if not claim:
        return Gauge(0, 1.0, "", err="`claim:` が書かれていません")
    try:
        import sys as _sys
        if str(ROOT / "scripts") not in _sys.path:
            _sys.path.insert(0, str(ROOT / "scripts"))
        import yaml

        import deadline_check as J
        doc = yaml.safe_load(
            (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    except Exception as exc:                                   # noqa: BLE001
        return Gauge(0, 1.0, "", err=f"台帳が読めません: {exc}")
    hit = next((h for h in doc.get("hypotheses", [])
                if str(h.get("claim", "")).startswith(claim[:24])), None)
    if hit is None:
        return Gauge(0, 1.0, "", err=f"台帳にこの claim がありません: {claim[:24]}")
    worst: tuple[float, int, float, str] | None = None
    for need in hit.get("needs") or []:
        if not isinstance(need, dict) or not need.get("count_expr"):
            continue
        want = float(need.get("need") or 0) or 1.0
        try:
            have = int(eval(str(need["count_expr"]), dict(J.EXPR_NS)))  # noqa: S307
        except Exception as exc:                               # noqa: BLE001
            return Gauge(0, want, "", err=f"`count_expr` が解けません: {exc}")
        ratio = have / want
        if worst is None or ratio < worst[0]:
            worst = (ratio, have, want, str(need["count_expr"])[:40])
    if worst is None:
        return Gauge(0, 1.0, "", err="数の床を持つ `needs` がありません（`count_expr` が無い）")
    _r, have, want, expr = worst
    return Gauge(have, want, "", f"`config/hypotheses.yaml` の needs: `{expr}`")


KINDS = {
    "ab_group": _k_ab_group,
    "deep_shorts": _k_deep_shorts,
    "hypothesis_needs": _k_hypothesis_needs,
    "length_spread": _k_length_spread,
    "published_count": _k_published_count,
    "reveal_hold_arm": _k_reveal_hold_arm,
    "scan_sum": _k_scan_sum,
    "days_with_min_videos": _k_days_with_min_videos,
    "scored_pairs": _k_scored_pairs,
    "error_reasons": _k_error_reasons,
}


# ---------------------------------------------------------------- 読み・出し

def load(path: Path = CONFIG) -> list[Watch]:
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for row in doc.get("watches") or []:
        row = dict(row)
        out.append(Watch(
            id=row.pop("id"), what=row.pop("what"), cond=row.pop("cond"),
            then=row.pop("then"), source=row.pop("source"),
            kind=row.pop("kind"), answered=row.pop("answered", "") or "",
            params=row,
        ))
    return out


def exempt(path: Path = CONFIG) -> dict[str, str]:
    """**見張らない**と決めたファイルと、その理由（検査が読みます）。"""
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(doc.get("exempt") or {})


# --- **満ちた ≠ 判定できる**（2026-08-26 夜・最適化の回に足した）---
#
# `config/watches.yaml` の「深い題のショート-16本」には、こう書いてありました:
#
#     **数え方は仮説の `needs.count_expr` と同じ**にしてあります。
#     片方だけ直すと、鳴る日と判定できる日がずれます。
#
# **その日のうちに、片方だけが直りました。** きょうだいの回が
# `config/hypotheses.yaml` の `needs` を
# 「**作った** 16本」→「**公開して分類が付いた** 8本 ＋ 使える日 3日」に直し、
# `src/watches.py::_k_deep_shorts`（**作った本を数える**）はそのままでした。
#
# 結果、同じ前提について3つの道具が別々のことを言っていました:
#
#     deadline_check.py   「[..] まだ数えはじめたところ。**何もしないのが正解**」
#     drift.py --gate     exit 2 →「**この回は verdict を出すこと**」
#     watches --pending   「**満ちました。この回で判定すること**」（3回まで止める）
#
# 実測は 要8／いま7、使える日 要3／**いま0**。**判定できる本は1本もありません。**
#
# **数え方を写し直すのは、同じ事故をもう一度 予約することです**（この註の上に
# 「同じにしてある」と書いてあって、それでもずれました）。だから写しません ——
# **判定できるかどうかの答えを持っている所を、1つに決めて、そこに訊きます。**
# それが `scripts/deadline_check.py`（＝ `src/judgeable.py` の床）です。
#
# **仮説と結ばれている待ちだけ**が対象です（`config/hypotheses.yaml` の
# `watch:` 欄。結ばれていない待ちは、これまでどおり自分の目盛りで鳴ります）。
#
# **覆る条件**: `deadline_check` が「判定できない」と言い続けるのに、
# 実際には判定できるようになっていたら、待ちが鳴らなくなります。
# そのときに直すのは `src/judgeable.py` の床のほうで、**ここを外すことではありません。**


def _hypothesis_judge_state() -> dict[str, tuple[str, object]] | None:
    """**待ちの id → その仮説を「いま判定できるか」**。

    返り: `{watch_id: ("ready"|"warming"|"unreachable"|"unchecked", 判定できる日 or None)}`。
    読めなければ `None` ——  **そのときは1件も抑えません**（黙るより鳴らす。
    計器が1本読めないことは、「判定できない」ことの証拠ではありません）。
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "watches_deadline_check", ROOT / "scripts" / "deadline_check.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["watches_deadline_check"] = mod   # dataclass が __module__ を引きます
        spec.loader.exec_module(mod)                  # type: ignore[union-attr]
        rows = mod.load()
        by_claim: dict[str, tuple[str, object]] = {}
        for v in mod.check(rows):
            if v.ready is not None:
                by_claim[v.claim] = ("ready", v.ready)
            elif getattr(v, "unreachable", False):
                by_claim[v.claim] = ("unreachable", None)
            elif getattr(v, "unchecked", False):
                by_claim[v.claim] = ("unchecked", None)
            else:
                by_claim[v.claim] = ("warming", None)
        out: dict[str, tuple[str, object]] = {}
        for h in rows or []:
            if not isinstance(h, dict):
                continue
            wid = str(h.get("watch") or "").strip()
            claim = str(h.get("claim") or "")
            if wid and claim in by_claim:
                out[wid] = by_claim[claim]
        return out
    except Exception:                                 # noqa: BLE001
        return None


def _too_early(w: Watch, state: dict[str, tuple[str, object]] | None) -> str:
    """**この待ちを、いま鳴らすと嘘になるか。** 嘘なら理由を返す（空なら鳴らしてよい）。

    **`unreachable` と `unchecked` は抑えません** —— 前者は前提の立て方ごと
    変える必要があり、後者は分からないだけです。**どちらも人が読む価値があります。**
    抑えるのは「**待てば判定できる**」と分かっている2つだけ。
    """
    if not state:
        return ""
    got = state.get(w.id)
    if not got:
        return ""
    kind, ready = got
    if kind == "warming":
        return ("`scripts/deadline_check.py`: **まだ数えはじめたところ**"
                "（判定に要るデータが揃っていません）")
    if kind == "ready" and ready is not None:
        # **JST で見ること。** この器は UTC なので `date.today()` を使うと
        # 00:00〜09:00 の9時間、「まだ判定できない」と言い続けます
        # （`scripts/drift.py::today_jst` が同じ穴を註つきで直しています）。
        today = datetime.now(timezone(timedelta(hours=9))).date()
        if ready > today:
            return f"`scripts/deadline_check.py`: **判定できるのは {ready}**"
    return ""


def unanswered(ws: list[Watch] | None = None) -> list[Watch]:
    """**満ちていて、しかも いま判定できる待ち。**

    `scripts/stop_check.sh` がこれを見て、回を引き止めます。
    **印字だけでは、読まなかった回に届きません**（それが 8/10〜8/20 の
    10日間に起きたことです）。

    **2026-08-26 に「いま判定できる」を足しました**（上の長い註）。
    目盛りが満ちても、判定に要るデータが揃っているとは限りません ——
    **その回にできないことを要求する門は、門ごと信用を失わせます。**
    """
    rung, _blocked = _split_rung(ws)
    return rung


def _split_rung(ws: list[Watch] | None = None) -> tuple[list[Watch], list[tuple[Watch, str]]]:
    """満ちた待ちを「**いま判定できる**」と「**まだ早い**」に割る。

    後ろは `render()` が理由つきで印字します。**黙って消さないこと** ——
    消すと、次の回には存在しなかったことになります。
    """
    state = _hypothesis_judge_state()
    rung: list[Watch] = []
    blocked: list[tuple[Watch, str]] = []
    for w in (ws if ws is not None else load()):
        if w.answered:
            continue
        if not w.gauge().met:
            continue
        why = _too_early(w, state)
        if why:
            blocked.append((w, why))
        else:
            rung.append(w)
    return rung, blocked


def note_rings(ws: list[Watch], at: str = "") -> None:
    """**鳴った回を1行積む。** 放置の長さを、人の記憶ではなく数で持つ。"""
    if not ws:
        return
    try:
        RINGS.parent.mkdir(parents=True, exist_ok=True)
        now = at or datetime.now(JST).isoformat(timespec="seconds")
        with RINGS.open("a", encoding="utf-8") as fh:
            for w in ws:
                fh.write(json.dumps({"at": now, "id": w.id},
                                    ensure_ascii=False) + "\n")
    except Exception:                                          # noqa: BLE001
        pass                                                   # 計器で回を止めない


def ring_history(path: Path | None = None) -> dict[str, tuple[int, str]]:
    """id → (鳴った回数, 最初に鳴った時刻)。"""
    src = path or RINGS
    out: dict[str, tuple[int, str]] = {}
    if not src.exists():
        return out
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        wid, at = r.get("id", ""), r.get("at", "")
        if not wid:
            continue
        n, first = out.get(wid, (0, at))
        out[wid] = (n + 1, min(first, at) if first and at else (first or at))
    return out


def _fmt(x: float) -> str:
    return f"{x:,.2f}".rstrip("0").rstrip(".") if x % 1 else f"{x:,.0f}"


def render(watches: list[Watch] | None = None, record: bool = False) -> str:
    """`status.py` が毎回出す節。**満ちたものを上に、大きく。**

    `record=True` のとき、**満ちて答えの無い待ちを1行ずつ積みます**
    （`data/watch_rings.jsonl`）。何回ぶん放置したかを、次の回が数で読めます。
    """
    try:
        ws = watches if watches is not None else load()
    except Exception as exc:                                   # noqa: BLE001
        return f"\n=== 待ちの条件 ===\n  読めませんでした（続行）: {str(exc)[:90]}"

    lines = ["\n=== 待ちの条件（**満ちたらここに出ます。コメントに書くだけにしない**）==="]
    # **満ちた ≠ 判定できる**（`_split_rung` の長い註）。
    # 「まだ早い」ものは、**鳴らさないが、理由つきで必ず印字する。**
    try:
        _early = {w.id: why for w, why in _split_rung(ws)[1]}
    except Exception:                                          # noqa: BLE001
        _early = {}
    rung, waiting, done, broken, early = [], [], [], [], []
    for w in ws:
        g = w.gauge()
        if g.err:
            broken.append((w, g))
        elif g.met and not w.answered and w.id in _early:
            early.append((w, g, _early[w.id]))
        elif g.met and not w.answered:
            rung.append((w, g))
        elif g.met:
            done.append((w, g))
        else:
            waiting.append((w, g))

    if record:
        note_rings([w for w, _ in rung])
    history = ring_history()
    for w, g in rung:
        n, first = history.get(w.id, (0, ""))
        rang = (f"  **{n}回鳴っています**（初回 {first[:16]}）" if n > 1 else "")
        lines.append(f"  [!] **満ちました** {w.id} —— {w.what}{rang}")
        lines.append(f"      {w.cond}: いま **{_fmt(g.now)}{g.unit}**"
                     f"（要る {_fmt(g.need)}{g.unit}）"
                     + (f" / {g.note}" if g.note else ""))
        lines.append(f"      → **{w.then}**")
        lines.append(f"      答えが出たら `config/watches.yaml` の "
                     f"`{w.id}` に `answered:` を1行。**それまで毎回鳴ります。**")
    for w, g, why in early:
        lines.append(f"  [..] **目盛りは満ちたが、まだ判定できません** {w.id} —— {w.what}")
        lines.append(f"       {why}")
        lines.append(f"       いま **{_fmt(g.now)}{g.unit}**（この待ちの目盛り）。"
                     "**この回は何もしないのが正解です**（畳まない・条件を緩めない）")
    for w, g in waiting:
        lines.append(f"  あと **{_fmt(g.left)}{g.unit}**  {w.id}"
                     f"（いま {_fmt(g.now)} / 要る {_fmt(g.need)}）"
                     + (f"  {g.note}" if g.note else ""))
    for w, g in broken:
        lines.append(f"  [!] 読めません {w.id}: {g.err}")
    for w, _g in done:
        lines.append(f"  済 {w.id}: {w.answered}")
    if not ws:
        lines.append("  （ありません）")
    if rung:
        lines.append("  **満ちた待ちは、この回で判定すること。**"
                     "待ちは、書いた回と満ちる回が別なので、記憶では繋がりません。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """`--pending` は `scripts/stop_check.sh` が読む形（1行1件）。"""
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--pending" in argv:
        for w in unanswered():
            print(f"{w.id}\t{w.then}")
        return 0
    print(render(record="--record" in argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
