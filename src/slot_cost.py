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

`verdict()` はそれを返すだけです。**禁止はしません** —— 数を並べて、
`daily_pick.lines()` が毎周それを印字します。**覆る条件**: 長尺（またはどの形でも）が
規則の密度で中央値を上げれば `slot_value()` の勝者はその形に自分で入れ替わり、
この門は自分でその形を通します。**形の禁止ではなく、測った数で倒れる門です。**
"""
from __future__ import annotations

#: 判定に使う齢。前提 `外の作り方を写した長尺` の判定窓と同じ 48時間。
HOURS = 48

#: これより薄い標本は「薄い」と名指しします。**落としはしません** ——
#: 落とすと「標本が無いから比べない」で、いままでどおり枠が黙って消えます。
MIN_N = 10


def slot_value(cmp: dict | None = None, *, now=None) -> dict:
    """**1枠は、いま何回 か。** 形ごとに「規則の密度の日だけ」の実測を返す。API 0単位。

    返す dict:
        ``forms``  形 → {n, median, p90, max, mixed_median, mixed_n}
        ``best``   実測でいちばん中央値が高い形（＝ 枠をそこに使ったときの値）
        ``cost``   その中央値（＝ **枠の機会費用**）
        ``thin``   標本が薄い形の名（n < ``MIN_N``）。数は返すが、薄さを隠さない。
    """
    from . import daily_pick as dp
    c = cmp if cmp is not None else dp.compare(now=now)
    forms: dict[str, dict] = {}
    for f in dp.FORMS:
        ru = dict(c.get("rule", {}).get(f) or {})
        al = dict(c.get("all", {}).get(f) or {})
        ru["mixed_median"] = al.get("median")
        ru["mixed_n"] = al.get("n", 0)
        forms[f] = ru
    live = {f: v for f, v in forms.items()
            if v.get("median") is not None and v.get("n", 0) > 0}
    best = max(live, key=lambda f: live[f]["median"]) if live else None
    return {
        "forms": forms,
        "best": best,
        "cost": (live[best]["median"] if best else None),
        "thin": sorted(f for f, v in forms.items() if 0 < v.get("n", 0) < MIN_N),
        "hours": HOURS,
    }


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
