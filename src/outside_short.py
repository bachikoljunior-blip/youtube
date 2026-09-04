"""**外の帯の上位のショートの型**（`style: outside_short`）—— その本文と、実物で数える脚。

## なぜ在るか（2026-09-05 05:3x・サブの回）

前提「外の帯の上位の**ショート**の作り」（`config/hypotheses.yaml`・期限 09-08・腕 `per_video`）
には、**機械が1つもありませんでした** —— `style: outside_long` に当たる札も、
`script_writer.OUTSIDE_LONG_RULE` に当たる脚も、ショート側は **0件**。

**長尺の側は、そこで 2日 かけて穴を1つ踏んでいます** ——「**札だけの本が、処置として枠を食う**」
（`src/daily_pick.treated_probe` の註・`config/hypotheses.yaml` 611行 の【2026-09-04 22:3x 訂正】）。
`style: outside_long` を貼った本 `1huadpEk6HY` は、実物の台本で数えると 4脚中 **3脚 ✗** で、
**処置ではないのに前提の門を握っていました。**

**だから順番は 脚 → 札 → 本です。** このモジュールは**脚**だけを持ちます。
札（`config/topics.yaml` の `style: outside_short`）を先に置かないこと ——
置いた瞬間、`deadline_check._outside_supply()` の門が開き、
**中身が外の型でない本が、また枠を食います。**

## 数（この回に自分で撃った。`data/niche_corpus.jsonl`・API 0単位）

**尺** —— 外の帯のショート 162本を、齢で割った再生（回/日）で升に分けた::

      0〜 60秒   n=20  中央 **0.4回/日**
     60〜100秒   n=43  中央 **0.7回/日**
    100〜140秒   n=51  中央 **1.3回/日**
    140〜180秒   n=46  中央 **2.8回/日**   ← いちばん速い升
                                          （0〜60秒 の **×7.0**・4升 とも単調に増えている）

**自分のショートは 109本 が 109本とも 23.6〜32.6秒**（`data/uploaded.jsonl` の `duration_s`・
中央 **29.0秒**）＝ **外の帯でいちばん遅い升に、全部 入っています。**
出どころは `script_writer.SHORT_TOTAL_CHARS = 140`（÷ `EFFECTIVE_CHARS_PER_SECOND` 4.63
＝ **30.2秒**）で、**これは上限であって狙いではありません。**

**題** —— 『◯◯が来ました／公開します』型（実物を出して、その場で開ける）は
外の帯で **n=3**（中央 185.7回/日 対 それ以外 1.44回/日 ＝ ×129）。
**升が薄い（n<20）ので、単独の根拠にしないこと**（`niche_ceiling.TITLE_FEATURES` の註と同じ扱い）。
**尺の脚は n=46 対 n=20 で立っています。題の脚は立っていません** ——
だから `LEGS` は尺を `hard`、題と中身を `soft` にしてあります。

## 覆る条件

- 前提「外の帯の上位のショートの作り」が外れたら（齢48h で 1,864回 未満 ＝ 自分の最大にも届かない）、
  このモジュールごと落とすこと。`OUTSIDE_LONG_RULE` の docstring と同じ扱いです。
- 尺の升が n を増やして単調でなくなったら（`band_lines()` を毎周 数え直す）、`LENGTH_BAND` を
  そのとき速い升へ動かすこと。**べた書きの数を信じないこと** —— 上の表は 2026-09-05 の実測です。
"""
from __future__ import annotations

import json
import re
import statistics as _st
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 外の帯でいちばん速い升（秒）。**上の docstring の表が出どころ。**
LENGTH_BAND = (140, 180)

#: `script_writer.EFFECTIVE_CHARS_PER_SECOND` の写しではありません ——
#: **読むこと**（ずれると、命じる尺と落とす床が食い違う。長尺が 09/05 03:4x に踏んだ形）。
def _chars_per_second() -> float:
    from src import script_writer                       # noqa: PLC0415
    return float(script_writer.EFFECTIVE_CHARS_PER_SECOND)


def total_chars_band() -> tuple[int, int]:
    """`LENGTH_BAND` を、台本の合計文字数に直す。**API 0単位・純関数。**"""
    cps = _chars_per_second()
    return (int(LENGTH_BAND[0] * cps), int(LENGTH_BAND[1] * cps))


#: 題の型（『◯◯が来ました／公開します』＝ 実物を出して、その場で開ける）。
#: **n=3 の薄い升です。** 単独の根拠にしないこと。
TITLE_PAT = re.compile(r"来ました|公開します|届いた|届きました|開けて|見せます|やってみた")

#: 中身の型（制度の解説ではなく「届いた物を開けて、その場で数字を読む」）。
BODY_PAT = re.compile(r"通知書|定期便|明細|封筒|はがき|ハガキ|届い|開け|実物|画面のこれ")

OUTSIDE_SHORT_RULE = """
**外の帯の上位のショートの作りを写します**（`src/outside_short` の表が根拠。API 0単位）。

(1) **尺 140〜180秒**（合計 {lo}〜{hi}文字）。**ここがいちばん大きい脚です** ——
    外の帯 162本 を齢で割ると 140〜180秒 の升は 0〜60秒 の **×7.0**（n=46 対 n=20・4升 とも単調）。
    **いまの作りは 109本 が 109本とも 23.6〜32.6秒**（`SHORT_TOTAL_CHARS = 140` の 30.2秒）で、
    **外の帯でいちばん遅い升に全部 入っています。** 削るのではなく、**中身を1つ足すこと。**

(2) **題は「実物を出して、その場で開ける」**（『◯◯が来ました／公開します／届きました』）。
    制度の名前と数字を並べた題ではありません。**外の帯の1位は
    「年金通知書！遂に来ました！公開します！」（220,121回・147秒）。**
    [!] この升は **n=3** です。**単独では根拠になりません** —— (1) を満たしたうえで足す脚。

(3) **中身は解説ではなく「読み上げ」**。届いた物（通知書・定期便・明細）を画面に出し、
    **その場で数字を読む**。「制度はこうです」から始めないこと。
    [!] **台本がその話をしていない題を付けないこと** —— 実物が出てこないのに「公開します」と
    書いた本は『誤解を与える内容』で、**収益化されなければ再生が何回でも 0円**です
    （`CLAUDE.md`「YouTube のポリシーは制約ではなく事実」）。

(4) 一息 4個 まで・数字は画面にも出す（既存のショートの規則をそのまま引き継ぎます）。
"""


def rule_text() -> str:
    """`OUTSIDE_SHORT_RULE` に、いまの文字数の帯を埋めて返す。"""
    lo, hi = total_chars_band()
    return OUTSIDE_SHORT_RULE.format(lo=lo, hi=hi)


#: 脚の名前と重み。`hard` ＝ これを外したら処置ではない／`soft` ＝ 薄い升なので添えるだけ。
LEGS = (("(1) 尺", "hard"), ("(2) 題", "soft"), ("(3) 中身", "soft"))


def _narration(script: dict | object) -> str:
    segs = getattr(script, "segments", None)
    if segs is None and isinstance(script, dict):
        segs = script.get("segments") or []
    out = []
    for s in segs or []:
        n = getattr(s, "narration", None)
        if n is None and isinstance(s, dict):
            n = s.get("narration")
        out.append(str(n or ""))
    return "".join(out)


def _title(script: dict | object) -> str:
    t = getattr(script, "title", None)
    if t is None and isinstance(script, dict):
        t = script.get("title")
    return str(t or "")


def legs_of_script(script: dict | object) -> list[tuple[str, bool, str]]:
    """台本1本が、外のショートの型に届いているか。**API 0単位・純関数。**

    返すのは `(脚の名前, 通ったか, なぜ)` の並び。**`treated_probe` と同じ向き** ——
    読めないものを「通った」に数えません。
    """
    lo_s, hi_s = LENGTH_BAND
    lo_c, hi_c = total_chars_band()
    text = _narration(script)
    title = _title(script)
    secs = len(text) / _chars_per_second() if text else 0.0
    out: list[tuple[str, bool, str]] = []
    out.append(("(1) 尺", lo_c <= len(text) <= hi_c,
                f"{len(text)}字 ＝ {secs:.0f}秒（帯 {lo_s}〜{hi_s}秒 ＝ {lo_c}〜{hi_c}字）"))
    out.append(("(2) 題", bool(TITLE_PAT.search(title)),
                f"題『{title[:24]}』に『来ました／公開します』型が"
                + ("在る" if TITLE_PAT.search(title) else "無い")
                + "（**n=3 の薄い升**・単独の根拠にしないこと）"))
    out.append(("(3) 中身", bool(BODY_PAT.search(text)),
                "実物（通知書・定期便・明細）を出して読む語が"
                + ("在る" if BODY_PAT.search(text) else "無い")))
    return out


def probe(video_id: str | None, *, queue: Path | None = None) -> tuple[str, str]:
    """公開ずみの本1つが、外のショートの型かを**実物の台本の控え**で見る。

    返り: `("yes"|"no"|"unknown", なぜ)`。**`daily_pick.treated_probe` と同じ形**
    （`unknown` は「控えが読めない」で、**`no` とは別**。読めないものを
    「通った」にも「落ちた」にも数えません）。
    """
    if not video_id:
        return "unknown", "video_id がありません"
    q = queue or (ROOT / "data" / "critique_queue")
    p = q / f"{video_id}.script.json"
    try:
        script = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "unknown", f"台本の控えが読めません（`{p}`・{exc}）"
    legs = legs_of_script(script)
    hard = {name for name, w in LEGS if w == "hard"}
    bad = [f"{n}（{why}）" for n, ok, why in legs if not ok and n in hard]
    if bad:
        return "no", "・".join(bad)
    soft_bad = [n for n, ok, _ in legs if not ok and n not in hard]
    return "yes", ("全部の脚が通りました" if not soft_bad
                   else f"重い脚は通りました（薄い升で落ちたのは {'・'.join(soft_bad)}）")


def band_lines(path: Path | None = None) -> list[str]:
    """**外の帯のショートを、いま数え直して升で並べる**（`data/niche_corpus.jsonl`・API 0単位）。

    **べた書きの数を読ませないため**の口です。docstring の表は 2026-09-05 の実測で、
    帯は撃つたびに増えます。**毎周 ここを撃って、`LENGTH_BAND` が速い升のままかを見ること。**
    """
    p = path or (ROOT / "data" / "niche_corpus.jsonl")
    try:
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        return ["     外の帯のショートが読めません（`data/niche_corpus.jsonl`）"]
    now = datetime.now(timezone.utc)
    bins = ((0, 60), (60, 100), (100, 140), (140, 180))
    got: list[tuple[tuple[int, int], list[float], int]] = []
    for lo, hi in bins:
        vals = []
        for r in rows:
            if r.get("form") != "short" or not r.get("secs") or not r.get("views"):
                continue
            if not (lo <= r["secs"] < hi):
                continue
            try:
                pub = datetime.fromisoformat(str(r["published"]).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            vals.append(r["views"] / max(1.0, (now - pub).days))
        if vals:
            got.append(((lo, hi), vals, len(vals)))
    if not got:
        return ["     外の帯のショートに、齢の読める本が1本もありません"]
    parts = [f"{lo}〜{hi}秒 n={n} 中央 **{_st.median(v):.1f}回/日**"
             for (lo, hi), v, n in got]
    best = max(got, key=lambda g: _st.median(g[1]))
    slow = min(got, key=lambda g: _st.median(g[1]))
    ratio = _st.median(best[1]) / max(1e-9, _st.median(slow[1]))
    line = [f"     外の帯のショートを尺の升で（`src/outside_short.band_lines`・API 0単位）: "
            + " ／ ".join(parts)]
    line.append(f"       → いちばん速い升は **{best[0][0]}〜{best[0][1]}秒**"
                f"（いちばん遅い {slow[0][0]}〜{slow[0][1]}秒 の **×{ratio:.1f}**）。"
                f"`LENGTH_BAND` は {LENGTH_BAND[0]}〜{LENGTH_BAND[1]}秒 —— "
                + ("**合っています**" if best[0] == LENGTH_BAND
                   else "**食い違っています。速い升へ動かすこと**"))
    return line
