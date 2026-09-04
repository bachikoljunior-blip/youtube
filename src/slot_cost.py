"""**枠の機会費用 —— この1枠を別のことに使ったら、何回 だったか。**（2026-09-05・最適化の回）**API 0単位。**

## この道具が答える1つの問い

オーナーが固定した規則は **「動画は1日一本」**（`src/house_rule.py` 規則1・2）。
＝ **出せる本は1日1枠しかありません。** だから枠を1つ使うたびに、
その枠で出せた**別の本**を必ず1つ捨てています。**その捨てた分が枠の機会費用です。**

**この回（2026-09-05 00:xx）に自分で撃った数**（`src/daily_pick.compare()`・
齢48時間・`data/views.jsonl`）:

        規則の密度（≤2本/日）の日だけ      全部の日（密度を混ぜた数）
        ショート  n=15  中央値 **1,049回**   n=216  中央値 **164回**
        長尺      n= 7  中央値 **    1回**   n= 36  中央値 **  1回**
        長尺の**規則の密度での最大は 4回**（p90 3回）

**混ぜた数（164回）は、規則がもう禁じている 8本以上/日 の日の本 201本 に
引っ張られています**（その帯だけなら中央値 131回）。**規則の下で1枠が実際に
何回 だったかは 1,049回 です。** ＝ **枠の機会費用は 164回 ではなく 1,049回。**

## なぜこの道具が要ったか（**過去の回を数えて出た欠陥**）

`daily_pick.lines()` は `compare()` が両方の形について持っている `rule`（規則の密度）を
**ショートにだけ印字し、長尺には生涯を印字していました。** ＝ **2つの形が、同じ物差しで
並んだことが1度もありませんでした。**（`c["rule"]["長尺"]` は計算ずみで、
どこにも出ていない。この回に `compare()` を撃って確かめた。）

その結果、`config/hypotheses.yaml` の前提「外の作り方を写した長尺」は
**当たりの門を「48時間で 100回 超え」**に置いて 09/04・09/05 の枠を取りました。

    枠の機会費用（ショート・規則の密度・中央値） **1,049回**
    その試しの**当たり**の門                       **  100回**   ← 機会費用の **1/10**
    その形の規則の密度での**最大**                 **    4回**   ← 門の 1/25

**＝ 全部うまくいっても、捨てた枠より小さい試し**でした。これは題材の良し悪しでも
サボりでもありません。**枠を食う試しに、機会費用の門が無かった**ということです。

## この道具が置く門（1つだけ）

> **枠を1つ食う試しは、当たったときの見込みが、その枠の機会費用**（＝ 実測でいちばん
> 高い形の中央値）**以上でなければ、枠を使う価値がありません。**

`verdict()` 自体は数と1行を返すだけです。**ただし 2026-09-05 から、これは門です** ——
`daily_pick.record()` が `kind=decide`・本番の控え（`path is None`）・`anyway` 空 のとき
`verdict()` を呼び、`ok is False` なら **通しません**（`--anyway <数字を含む1行>` で越えられ、
越えた行は控えに残ります）。**印字だけだった間、決めは 11回 連続で長尺のままでした。**

**覆る条件**: 長尺（またはどの形でも）が
規則の密度で中央値を上げれば `slot_value()` の勝者はその形に自分で入れ替わり、
この門は自分でその形を通します。**形の禁止ではなく、測った数で倒れる門です。**
"""
from __future__ import annotations
import math

#: 判定に使う齢。前提 `外の作り方を写した長尺` の判定窓と同じ 48時間。
HOURS = 48

#: これより薄い標本は「薄い」と名指しします。**落としはしません** ——
#: 落とすと「標本が無いから比べない」で、いままでどおり枠が黙って消えます。
MIN_N = 10

#: **標本の最後の1本が、これより古ければ「化石」と名指しします。**（2026-09-05 02:5x に足した）
#:
#: なぜ要ったか —— **この道具は 1,049回 を「いま何回 か」として出していましたが、
#: その 15本 は 2026-08-05〜08-18 の本だけで、いちばん新しい1本が 18日前**でした
#: （この回に `daily_pick.aged_views()` を撃って数えた。日付は
#: 08-05/06/07/08/09/10/11/12(2本)/13/14/15(2本)/17/18）。
#: **`scripts/eta.py` は同じ化石を `per_video` について毎周 名指ししています** ——
#: 「`per_video` の標本は 2026-08-18 で止まっています（18日前・帯 ≤2本/日 の 12日）」。
#: **同じ 12日 の同じ帯を、こちらは何も言わずに『いま』として印字していました。**
#:
#: 何が実際に壊れるか: `win_band()` の `paid` の境目が `cost` ＝ 1,049回 です。
#: 化石が高いままなら、**どの試しも `paid` に届かず、形の判断は永久に動きません** ——
#: 倒れない門は、測って倒す門ではありません（この道具自身の「覆る条件」がそう書いています）。
#:
#: **それでも `cost` は下げません。** 直近14日の中央値（ショート 129回・n=135）は
#: **規則が禁じている 8本以上/日 の日の本に引かれていて**、こちらも「いまの1枠」ではない。
#: **きれいで新しい数は、いまこの repo に1つも在りません。** 両方を並べて、
#: どちらも『いま』ではないと名指しするところまでが、この回に測れたことです。
STALE_DAYS = 7


def sample_window(rows, form: str, *, max_per_day: int | None = None) -> dict:
    """**その形の標本が、いつの本で出来ているか。**（API 0単位）

    `daily_pick.compare()` の `rows`（`aged_views()` の行）から、`form` の
    `max_per_day` 以下の日の本だけを拾い、`first` / `last`（公開日）と `n` を返します。
    **中央値そのものは何も変えません** —— 数の**齢**を、数と同じ画面に出すためだけの手です。
    """
    first = last = None
    n = 0
    for r in rows or ():
        if r.get("form") != form:
            continue
        if max_per_day is not None and r.get("day_count", 0) > max_per_day:
            continue
        pub = r.get("pub")
        if pub is None:
            continue
        n += 1
        if first is None or pub < first:
            first = pub
        if last is None or pub > last:
            last = pub
    return {"first": first, "last": last, "n": n}


def slot_value(cmp: dict | None = None, *, now=None) -> dict:
    """**1枠は、いま何回 か。** 形ごとに「規則の密度の日だけ」の実測を返す。API 0単位。

    返す dict:
        ``forms``  形 → {n, median, p90, max, mixed_median, mixed_n}
        ``best``   実測でいちばん中央値が高い形（＝ 枠をそこに使ったときの値）
        ``cost``   その中央値（＝ **枠の機会費用**）
        ``thin``   標本が薄い形の名（n < ``MIN_N``）。数は返すが、薄さを隠さない。
        ``stale``  標本の最後の1本が ``STALE_DAYS`` より古い形の名（**化石**）。
                   形ごとに ``last_pub`` / ``first_pub`` / ``sample_age_days`` と、
                   同じ形の直近14日（`compare()` の ``recent``）を ``recent_*`` で持ちます。
    """
    from datetime import date as _date, datetime as _dt, timezone as _tz
    from . import daily_pick as dp
    c = cmp if cmp is not None else dp.compare(now=now)
    rows = c.get("rows") or []
    t = (now or _dt.now(_tz.utc)).astimezone(dp.JST)
    today: _date = t.date()
    forms: dict[str, dict] = {}
    for f in dp.FORMS:
        ru = dict(c.get("rule", {}).get(f) or {})
        al = dict(c.get("all", {}).get(f) or {})
        re = dict(c.get("recent", {}).get(f) or {})
        ru["mixed_median"] = al.get("median")
        ru["mixed_n"] = al.get("n", 0)
        ru["recent_median"] = re.get("median")
        ru["recent_n"] = re.get("n", 0)
        w = sample_window(rows, f, max_per_day=dp.RULE_BAND_MULT)
        ru["first_pub"], ru["last_pub"] = w["first"], w["last"]
        ru["sample_age_days"] = ((today - w["last"]).days
                                 if isinstance(w["last"], _date) else None)
        forms[f] = ru
    live = {f: v for f, v in forms.items()
            if v.get("median") is not None and v.get("n", 0) > 0}
    best = max(live, key=lambda f: live[f]["median"]) if live else None
    stale = sorted(f for f, v in forms.items()
                   if isinstance(v.get("sample_age_days"), int)
                   and v["sample_age_days"] > STALE_DAYS)
    return {
        "forms": forms,
        "best": best,
        "cost": (live[best]["median"] if best else None),
        "cost_age_days": ((forms.get(best) or {}).get("sample_age_days") if best else None),
        "thin": sorted(f for f, v in forms.items() if 0 < v.get("n", 0) < MIN_N),
        "stale": stale,
        "stale_days": STALE_DAYS,
        "recent_days": c.get("recent_days"),
        "hours": HOURS,
    }


def stale_lines(sv: dict | None = None, *, cmp: dict | None = None, now=None) -> list[str]:
    """**`cost` が化石なら、その齢と、同じ形の直近の数を並べる行。**（API 0単位）

    **数は1つも書き換えません。** 出すのは「この 1,049回 は何日前の本で出来ているか」と
    「同じ形の直近14日は何回か」の2つだけで、**どちらも『いまの1枠』ではない**と
    言い切るところまでです（片方は古く、片方は規則の外の密度に引かれている）。

    **覆る条件**: 規則の密度の日に ショート が1本 出れば、その本が標本の最後になり、
    `sample_age_days` は 0〜2日 に落ちて、この行は自分で消えます。
    ＝ **09/06 の枠（`DtpnSVFDtAE`・ショート）が出た時点で、この註は要らなくなります。**
    """
    s = sv if sv is not None else slot_value(cmp=cmp, now=now)
    best, cost = s.get("best"), s.get("cost")
    age = s.get("cost_age_days")
    if best is None or cost is None or not isinstance(age, int) or age <= s.get("stale_days", STALE_DAYS):
        return []
    v = s["forms"].get(best) or {}
    first, last = v.get("first_pub"), v.get("last_pub")
    rn, rm = v.get("recent_n", 0), v.get("recent_median")
    out = [f"       [数] **その {cost:,.0f}回 は「いま」ではありません** —— "
           f"{best} の規則の密度の標本 n={v.get('n', 0)} は "
           f"{first}〜{last} の本だけで、**いちばん新しい1本が {age}日前**です"
           f"（`slot_cost.sample_window`・API 0単位）。"
           f"`scripts/eta.py` が `per_video` について毎周 名指ししている化石"
           f"（「標本は 2026-08-18 で止まっています」）と**同じ帯・同じ日付**です。"]
    if rm is not None and rn:
        out.append(f"       [数] 同じ形の**直近{s.get('recent_days', 14)}日**は n={rn} 中央値 "
                   f"**{rm:,.0f}回**（{cost / rm:,.1f} 分の1）。"
                   f"**ただしこちらも『いまの1枠』ではありません** —— "
                   f"規則が禁じている 8本以上/日 の日の本に引かれています。"
                   f"**きれいで新しい数は、いま1つも在りません。**")
    out.append(f"       [数] **だから `win_band()` の `paid` の境目 {cost:,.0f}回 は、"
               f"{age}日前の帯の高さです。** 倒れない門は測って倒す門ではないので、"
               f"**この帯で `unpaid` が出ても「形は動かせない」と読み切らないこと** ——"
               f"読めるのは「{age}日前の帯には届かなかった」までです。"
               f"規則の密度の日に {best} を1本 出せば、この註は自分で消えます。")
    return out


def verdict(win: float | None, *, form: str | None = None, cmp: dict | None = None,
            sv: dict | None = None, now=None) -> dict:
    """**その試しは、食う枠のぶんを払えるか。**（`win` ＝ 当たったときの見込み・齢48h）

    返す dict: ``ok``（払える／None ＝ 数が足りない）・``cost``・``ratio``（win÷cost）・
    ``best``・``own_max``（`form` の規則の密度での最大）・``why``（1行）。
    **禁止はしません。** 数と1行を返すだけです。
    """
    s = sv if sv is not None else slot_value(cmp=cmp, now=now)
    cost = s.get("cost")
    if win is None or cost in (None, 0):
        return {"ok": None, "cost": cost, "ratio": None, "best": s.get("best"),
                "own_max": None, "why": "枠の機会費用が測れません（標本 0本）。"}
    ratio = float(win) / float(cost)
    own = (s["forms"].get(form) or {}) if form else {}
    own_max = own.get("max")
    ok = ratio >= 1.0
    if ok:
        why = (f"当たり {win:,.0f}回 ≥ 枠の機会費用 {cost:,.0f}回"
               f"（{s.get('best')}・規則の密度の中央値）＝ **この試しは枠のぶんを払えます。**")
    else:
        why = (f"当たり {win:,.0f}回 は 枠の機会費用 {cost:,.0f}回"
               f"（{s.get('best')}・規則の密度の中央値）の **1/{1 / ratio:,.0f}**"
               f" ＝ **全部うまくいっても、捨てた枠より小さい試しです。**")
    if own_max is not None and win > own_max:
        why += (f" なお {form} の規則の密度での最大は {own_max:,.0f}回 で、"
                f"門はその **×{win / own_max:,.0f}**。")
    return {"ok": ok, "cost": cost, "ratio": ratio, "best": s.get("best"),
            "own_max": own_max, "why": why}


def lines(cmp: dict | None = None, *, now=None, win: float | None = None,
          form: str | None = None) -> list[str]:
    """`daily_pick.lines()` が毎周 印字する塊。API 0単位。"""
    from . import daily_pick as dp
    s = slot_value(cmp=cmp, now=now)
    out = [f"     **枠の機会費用**（規則1「1日1本」＝ 1枠使うたび、別の1本を必ず捨てています。"
           f"齢{s['hours']}時間・規則の密度 ≤{dp.RULE_BAND_MULT}本/日 の日だけ・`src/slot_cost.py`）:"]
    for f in dp.FORMS:
        v = s["forms"].get(f) or {}
        n = v.get("n", 0)
        mark = "  ← 標本が薄い" if 0 < n < MIN_N else ""
        out.append(
            f"       {f:　<4} n={n:<3} 中央値 {dp._fmt(v.get('median')):>8}"
            f"  p90 {dp._fmt(v.get('p90')):>8}  最大 {dp._fmt(v.get('max')):>8}"
            f"  ／ 密度を混ぜた数 n={v.get('mixed_n', 0)} 中央値 "
            f"{dp._fmt(v.get('mixed_median'))}{mark}")
    if s.get("cost") is not None:
        out.append(f"       ＝ **この1枠は {s['cost']:,.0f}回**（{s['best']}）。"
                   f"**枠を食う試しは、当たりの門がこの数以上でなければ、"
                   f"当たっても枠のぶんを払えません。**")
        out.append("       （混ぜた数は、規則がもう禁じている 8本以上/日 の日の本に引かれています。"
                   "**比べるのは規則の密度のほうです。**）")
        out += stale_lines(sv=s)
    if win is not None:
        v = verdict(win, form=form, sv=s)
        out.append(f"       試しの当たりの門 {win:,.0f}回 → {v['why']}")
    return out


#: **実際に枠を取った2つの言い分**（`data/daily_pick.jsonl`・09/04 22:24／22:54／23:24 の
#: `why` から、この回に読んだ原文）。**どちらも門を通ったのではなく、門が無かったので通りました。**
#: ここに残すのは、次の回が同じ言い分でまた枠を取れないようにするためです。
OVERRIDES = (
    ("既に使った枠が捨てになる",
     "09/04 の枠はもう使い終わっています。**使い終わった枠は、次の枠の値を1回も上げません。**"
     "決めるのは「09/05 の1枠を、いま何回 の見込みに使うか」だけ ——"
     "**{cost:,.0f}回（規則の密度の中央値）か、当たっても {win:,.0f}回 か。**"),
    ("比べる相手の分母が処置0本だから比べられない",
     "枠の機会費用に処置は要りません。**{cost:,.0f}回 は、何も足していない普通のショートが"
     "規則の密度の日に実際に出した数**（n={n}）です。"
     "**その枠を捨てて買うものが {win:,.0f}回 なら、処置の有無に関係なく足りません。**"),
)


def override_notes(win: float | None, *, sv: dict | None = None,
                   cmp: dict | None = None, now=None) -> list[str]:
    """**枠を取るときに実際に使われた言い分に、数で答える行。** API 0単位。"""
    s = sv if sv is not None else slot_value(cmp=cmp, now=now)
    cost, best = s.get("cost"), s.get("best")
    if win is None or cost in (None, 0):
        return []
    n = (s["forms"].get(best) or {}).get("n", 0)
    return [f"       ・「{name}」→ " + body.format(cost=cost, win=win, n=n)
            for name, body in OVERRIDES]


def open_slot_experiments(path=None) -> list[dict]:
    """`config/hypotheses.yaml` の**枠を食う前提**を返す。API 0単位。

    「枠を食う」＝ `claim` に「1本 出す」と書いてある前提。返す行:
    ``claim`` / ``win``（claim から読んだ当たりの門・回）/ ``form``。
    **読めなかった門は `win=None`** で返します（黙って落とさない ——
    落とすと門の無い前提だけが検査を素通りします）。
    """
    import re
    from pathlib import Path
    p = (Path(path) if path
         else Path(__file__).resolve().parent.parent / "config" / "hypotheses.yaml")
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return []
    out = []
    for m in re.finditer(r'^\s*-\s*claim:\s*"(.*?)"\s*$', text, re.M):
        claim = m.group(1)
        if "1本 出す" not in claim and "1本出す" not in claim:
            continue
        form = ("長尺" if "長尺を1本" in claim
                else ("ショート" if "ショートを1本" in claim else None))
        win = None
        g = re.search(r"×[\d,]+（([\d,]+)回?）を超える", claim)
        if g:
            try:
                win = float(g.group(1).replace(",", ""))
            except ValueError:
                win = None
        out.append({"claim": claim, "win": win, "form": form})
    return out


#: 帯の名前（`win_band()` が返す `band`）。**3つだけ。**
BANDS = ("miss", "unpaid", "paid")


def win_band(v: float | None, *, gate: float, give_up: str = "ショート",
             sv: dict | None = None, cmp: dict | None = None, now=None) -> dict:
    """**48時間に実際に出た数が、どの帯に落ちたか。**（API 0単位）

    ## なぜ要るか（2026-09-05 01:5x・毎時の回が撃った数）

    `verdict()` は**撃つ前**の門です（「当たっても枠のぶんを払えるか」）。
    ところが**撃った後**を読む所には、門が **1つしかありませんでした** ——
    `daily_pick.OUTSIDE_48H_GATE` ＝ **100回**。その 100回 の出どころは
    前提の `claim` にそのまま書いてあります:

        「48時間の再生は **いまの長尺の中央値 1回 の ×100**（100回）を超える」

    **＝ 自分の記録だけで作った数（鏡）です。** この repo は同じ誤りを
    2026-09-03 に1度 閉じています —— 前提「`per_video` の天井 4,229回 は
    帯の天井ではなく、いまの作り方の天井である（＝ `ceiling_at_rule()` が
    **自分の記録だけで作った鏡**）」`outcome: survived`。
    **鏡だと分かって天井を捨てたのに、その後継の前提の「当たりの門」は、
    同じ作り方（自分の中央値 ×N）のまま残っていました。**

    ## 何が実際に壊れるか（散文ではなく、書いてある帰結）

    `config/hypotheses.yaml` の姉妹の前提（外の作りの**ショート**）の註に、
    こう書いてあります —— 「**覆る条件**: `外の作り方を写した長尺` が当たった
    （48h で **100回** 超え）なら、**形を長尺へ寄せる判断が先**」。

    ＝ 09/07 の判定が **101回** で返ってきたら、その1本は「当たり」と読まれ、
    **これから先の枠が長尺へ寄ります。** ところが同じ枠をショートに使えば、
    実測の中央値は **1,049回**（規則の密度・`slot_value()`・2026-09-05）です。
    **101回 は「作りは効いた」の証拠にはなりますが、「枠をこの形に寄せてよい」
    の証拠には一度もなっていません。** 2つの問いに、門が1つしかありませんでした。

    ## だから帯を3つに割ります（**どちらの門も緩めません**）

        v <  gate            → ``miss``    前提は外れ。`next_if_false` へ。
        gate ≤ v < cost      → ``unpaid``  **作りは効いた／枠の代金は払えていない。**
                                           前提は当たり（`falsified_if` は満たした）が、
                                           **形を長尺へ寄せる根拠にはならない** ——
                                           同じ枠のショートの実測に負けている。
        v ≥ cost             → ``paid``    当たり、かつ枠のぶんを払えた。
                                           **このときだけ形の判断を動かしてよい。**

    返す dict: ``band`` / ``gate`` / ``cost`` / ``give_up`` / ``may_move_form``
    （＝ `band == "paid"`）/ ``line``（印字する1行）。

    **数が足りない回は `band=None`・`line=""` を返します**（推測で埋めない）。
    `cost` が読めないときは `gate` だけで `miss`／`unpaid` を分け、
    **`paid` は名乗りません**（払えたことを、測らずに言わないため）。

    **覆る条件**: 長尺が規則の密度で中央値を上げれば `slot_value()` の勝者が
    入れ替わり、`cost` はその形の数になります。＝ **形の禁止ではなく、
    測った数で自分が倒れる帯です。** また `gate` が `cost` 以上に置き直された日、
    `unpaid` の幅は 0 になり、この関数は 2帯 に自分で縮みます。
    """
    if v is None or gate is None:
        return {"band": None, "gate": gate, "cost": None, "give_up": give_up,
                "may_move_form": False, "line": ""}
    try:
        v = float(v)
        gate = float(gate)
    except (TypeError, ValueError):
        return {"band": None, "gate": None, "cost": None, "give_up": give_up,
                "may_move_form": False, "line": ""}
    if not (math.isfinite(v) and math.isfinite(gate)):
        return {"band": None, "gate": None, "cost": None, "give_up": give_up,
                "may_move_form": False, "line": ""}
    s = sv if sv is not None else slot_value(cmp=cmp, now=now)
    give = s.get("forms", {}).get(give_up) or {}
    cost = give.get("median")
    if not isinstance(cost, (int, float)) or isinstance(cost, bool) \
            or not math.isfinite(cost) or cost <= 0:
        cost = None
    #: **`cost` の齢**（2026-09-05 02:5x に足した）。`paid` の境目がどれだけ古い帯の
    #: 高さかを、帯と同じ行に出します。**境目そのものは動かしていません。**
    cost_age = give.get("sample_age_days")
    cost_stale = isinstance(cost_age, int) and cost_age > s.get("stale_days", STALE_DAYS)
    if v < gate:
        band = "miss"
        line = (f"**{v:,.0f}回 ＜ 前提の門 {gate:,.0f}回 → 外れ**"
                f"（`next_if_false` へ）")
    elif cost is None:
        band = "unpaid"
        line = (f"**{v:,.0f}回 ≥ 前提の門 {gate:,.0f}回 → 前提は当たり。"
                f"ただし枠の機会費用が測れません（{give_up} の規則の密度の標本 0本）"
                f"→ 形を寄せる判断はまだ取れません**")
    elif v < cost:
        band = "unpaid"
        line = (f"**{v:,.0f}回 ≥ 前提の門 {gate:,.0f}回 → 前提は当たり"
                f"（`falsified_if` は満たしています）。"
                f"ただし同じ枠の {give_up} の実測 {cost:,.0f}回"
                f"（規則の密度の中央値・`slot_value`）に負けています ＝ "
                f"**作りは効いた／枠の代金は払えていない**。"
                f"→ **この数で形を長尺へ寄せないこと。**"
                f"寄せてよいのは {cost:,.0f}回 を越えた回だけです")
    else:
        band = "paid"
        line = (f"**{v:,.0f}回 ≥ 前提の門 {gate:,.0f}回 かつ "
                f"≥ 同じ枠の {give_up} の実測 {cost:,.0f}回 → 当たり、"
                f"かつ枠のぶんを払えました ＝ 形の判断を動かしてよい**")
    if cost is not None and cost_stale and band in ("unpaid", "paid"):
        line += (f"　[!] **その {cost:,.0f}回 は {cost_age}日前の帯の高さです**"
                 f"（{give_up} の規則の密度の標本は {give.get('first_pub')}〜"
                 f"{give.get('last_pub')} の {give.get('n', 0)}本 で止まっています・"
                 f"`slot_cost.stale_lines`）。**この境目で読み切らないこと。**")
    return {"band": band, "gate": gate, "cost": cost, "give_up": give_up,
            "cost_age_days": cost_age, "cost_stale": cost_stale,
            "may_move_form": band == "paid", "line": line}
