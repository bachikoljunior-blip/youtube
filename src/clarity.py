"""**「人間にわかるか」を、人の側の数で確かめる所**（2026-09-02）。

    python -m src.clarity          # API 0単位・数秒。控えと `data/retention.json` だけ読みます

## 出どころ（オーナー原文・2026-09-02。`CLAUDE.md` 冒頭「固定その3」）

> **「動画内の説明は人間にわかるようにして」**

`CLAUDE.md` はこう書いています ——
**「いまの検査は『合っているか』しか見ていません ＝ 人に分かるかを誰も見ていない」**、
そして**「覆る条件: 『分かる』を測る形が、実際には分かりやすさと無関係だと
実測で出たとき。そのときは測り方を変えること」**。

**この module は、その『覆る条件』を撃てる形にしたものです。**

## いま在る3つの物差しは、どれも一度も人に当てられていませんでした

    src/verify._check_ear_load   一息で耳が持たされる数の個数（上限 5個）  ← **生成の輪に配線ずみ**
    scripts/deixis_count         画面を見ないと指す先が分からない語        ← (c) 寝かせ
    src/pipeline.slide_pace      1コマの秒数（2.5 対 4.5 の A/B・判定 09-24）

**3つとも「多いほど分かりにくいはずだ」で置いた閾値**で、
**「本当に分かりにくいのか」を人の側の数と突き合わせた回は1度もありません**
（`_check_ear_load` の docstring の実測は、全部 台本の側の分布です）。
この repo がいちばん多く踏む形（**言っている所と、している所が別**）の、
いちばん奥にあるものです。

## 人の側の数として何を使うか —— `data/retention.json`

`scripts/retention.py` が貯めている **1本 100点の維持率カーブ**
（`audienceWatchRatio` と `relativeRetentionPerformance`）。
**「分かる」そのものではありません** —— 見続けた理由は分かること以外にもあります。
それでも、**いま repo に在る「人がどうしたか」の数はこれだけ**で、
分からなければ離脱する向きには効くはずのものです。

**因果を決めつけないこと**（`analytics.fetch_retention` の註 ——
「維持率が低いから伸びないのか、伸びたから維持率が下がったのか」は決まりません）。
ここが答えるのは**もっと弱い問い**だけです ——
**その物差しは、人の側の数と、そもそも関係があるか。**

## **陽性対照が要ります**（この module のいちばん大事な部分）

**「関係がありませんでした」は、計器が死んでいても同じ字で出ます。**
だから毎回、**分かりきったことを1つ測って**から本題に入ります ——
**落ちは動画の前のほうに寄る**（`retention.py` が100点を引いた理由そのもの）。

    実測 2026-09-02: 位置 と 落ち方（1秒あたり）の順位相関 **rho = -0.468**（410コマ）
                     本の中だけで見た平均も **-0.473**（69本）

**これが出ないうちは、下の数を読まないこと。** `control()` が門です。

## 2026-09-02 の実測（69本・控えと維持率カーブが両方ある本）

    n=69 → 有意（両側5%）になるのは |rho| ≧ 0.238

    物差し                     50%地点の維持   25%地点   相対(平均)   向き
    数の個数 平均               **+0.125**     +0.068    +0.072      ✗ 逆
    数の個数 最大               **+0.170**     +0.130    +0.115      ✗ 逆
    言った桁 合計/コマ           +0.159        +0.106    +0.089      ✗ 逆
    言った桁 一息の最大           +0.133        +0.083    +0.061      ✗ 逆
    1つの数の桁 最大             +0.161        +0.125    +0.075      ✗ 逆
    指示語（広い）合計           -0.109        -0.096    +0.054      ○ ただし小さい
    文字/コマ                  -0.130        -0.073    -0.066      ○ ただし小さい

**読み方は2つあり、混ぜないこと。**

1. **有意なものは1つもありません**（|rho| が 0.238 に届いた物差しはゼロ）。
   **＝「効かない」と証明されたのではなく、n=69 では何も言えない。**
2. **ただし、いま唯一 生成の輪に配線されている物差し（数の個数）だけは、
   3つの出口の全部で向きが逆**です —— 数を多く積んだ本ほど、維持率が**高い**。
   偶然でも起きる大きさですが、**「多いほど分かりにくい」の側の証拠は1つもありません。**

**それでも `EAR_LOAD_MAX` を、この回に緩めていません。** n が足りず、
`_check_ear_load` の docstring の覆る条件は「1本あたり再生が動かないなら弱めること」で、
**動いたかどうかを言える数がまだ無い**からです（`config/hypotheses.yaml` の
`clarity_ear_load_sign` に、判定できる本数と期日を置きました）。

## 何本 貯まれば言えるか

    |rho| = 0.20 を 5% で拾うのに要る本  **n ≒ 194**
    |rho| = 0.30                        **n ≒  85**

`data/retention.json` は **88本**、うち控えのある本が **71本**、
コマが4つ以上ある本が **69本**。**`python scripts/retention.py` を撃つたびに増えます**
（貯めに無いIDだけ引くので、`--refresh` は要りません）。
**＝ この判定を早める手は「新しい物差しを考える」ではなく「カーブを貯める」ほうです。**

## 覆る条件

- **陽性対照（`control()`）が -0.20 より弱くなったら**、下の数を読まないこと。
  台本の側の時間割（文字数 ÷ 話速）が実物とずれた、というほうを先に疑うこと
- **本数が 194本 を超えても、どの物差しも |rho| < 0.20 のままなら**、
  維持率カーブは「分かるか」の代わりになりません。**そのときは人の側の数を
  替えること**（コメントの文面・`engaged`・アンケート）—— **指示そのものは固定です**
- **配線ずみの物差し（数の個数）が、有意に「逆」で出たら**、
  `verify.EAR_LOAD_MAX` を緩めるのではなく**外す**こと。
  逆に効いている門は、緩めても向きが変わりません
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from src import config, narrated

#: 読み上げの速さ（字/秒）。`src/pipeline.CHARS_PER_SECOND` と同じ値。
#: **ここで import しないのは、`pipeline` が重い（ffmpeg・描画）から**です。
#: 食い違ったら `tests/test_clarity.py::test_話速が_pipeline_と同じ` が赤くします。
CHARS_PER_SECOND = 5.2

#: 陽性対照の門。**位置と落ち方の順位相関が、これより弱かったら計器が死んでいます。**
#: 実測 2026-09-02 は -0.468。**-0.20 は「半分になっても通る」ゆるさ**で置いています
#: —— きつくすると、控えが増えただけで赤くなります。
CONTROL_MAX_RHO = -0.20

#: コマがこれより少ない本は数えません（1本の中の並びが見られないので）。
MIN_SEGMENTS = 4

#: **画面を見ないと指す先が分からない語**（`scripts/deixis_count.WIDE` の写し）。
#: **正本はあちらです** —— ここに写しを置いているのは、`scripts/` を
#: `src/` から import すると `retro._CALL_RE` が「配線ずみ」と読み替えてしまい、
#: あの道具の (c) の札が黙って剥がれるからです（2026-09-02 に踏んだ形）。
#: 食い違ったら `tests/test_clarity.py::test_指示語の語彙が_正本と同じ` が赤くします。
DEIXIS_WIDE = (
    r"左端|右端|左側|右側|左から|右から|上の(?:ほう|方)|下の(?:ほう|方)"
    r"|真ん中|中央の|上から\d+|下から\d+|一番上|一番下|いちばん上|いちばん下"
    r"|(?:この|その|あの|こちらの)(?:線|棒|帯|矢印|枠|列|行|欄|軸|点|グラフ|図|表|色|部分|ところ)"
    r"|2つの線|2本の棒"
    r"|画面の|(?:図|表|グラフ)の(?:ように|とおり)|ご覧のとおり|見てのとおり"
    r"|(?:青|赤|緑|黄色|オレンジ|灰色|グレー)(?:い)?(?:の|い)?(?:線|棒|帯|部分|ところ|ほう|方)"
    r"|帯|棒グラフ|棒|グラフ|この表|その表|縦軸|横軸|凡例|矢印|色分け|ハイライト|太字|囲み"
)

_DEIXIS = re.compile(DEIXIS_WIDE)

QUEUE = config.ROOT / "data" / "critique_queue"
CURVES = config.ROOT / "data" / "retention.json"


def spearman(xs: list[float], ys: list[float]) -> float:
    """順位相関。**同順位は平均順位**で潰します（指示語は 0 だらけなので必須）。"""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return 0.0

    def rank(v: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: v[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def significant_at(n: int) -> float:
    """その本数で、両側5%になる |rho|。**n を書かずに rho だけ引用しないこと。**"""
    return 1.96 / math.sqrt(n - 1) if n > 2 else float("inf")


def needed_for(rho: float) -> int:
    """その大きさの関係を 5% で拾うのに要る本数（`significant_at` の逆）。"""
    if not rho:
        return 0
    return int(math.ceil((1.96 / abs(rho)) ** 2 + 1))


def curve_at(curve: list[tuple[float, float, float]], x: float) -> float:
    """維持率カーブを位置 `x`（0〜1）で線形に読む。"""
    if not curve:
        return 0.0
    prev: tuple[float, float] | None = None
    for row in curve:
        r, a = float(row[0]), float(row[1])
        if r >= x:
            if prev is None or r == prev[0]:
                return a
            r0, a0 = prev
            return a0 + (x - r0) / (r - r0) * (a - a0)
        prev = (r, a)
    return float(curve[-1][1])


def segment_rows(narration: list[str]) -> list[dict]:
    """読み上げの1文ごとに、**時間割**と**物差しの原料**を並べる。

    時間割は**文字数 ÷ 話速**です（`pipeline._check_short_script` と同じ考え方）。
    実物の音声は測っていないので**近似**ですが、`control()` の陽性対照が
    そのずれごと引っかけます（ずれが大きければ位置の相関が消えます）。
    """
    texts = [t for t in narration if isinstance(t, str) and t.strip()]
    if not texts:
        return []
    durs = [max(len(t) / CHARS_PER_SECOND, 0.1) for t in texts]
    total = sum(durs)
    rows: list[dict] = []
    cum = 0.0
    for i, (t, du) in enumerate(zip(texts, durs)):
        start, end = cum / total, (cum + du) / total
        cum += du
        nums = narrated.numbers(t)
        rows.append({
            "i": i,
            "text": t,
            "start": start,
            "end": end,
            "pos": (start + end) / 2,
            "sec": du,
            "数の個数": len(nums),
            "言った桁": sum(d for _tok, _v, d in nums),
            "桁の最大": max([d for _tok, _v, d in nums], default=0),
            "指示語": len(_DEIXIS.findall(t)),
            "文字数": len(t),
        })
    return rows


def books() -> list[tuple[str, list[tuple[float, float, float]], list[dict]]]:
    """控えと維持率カーブが**両方ある**本だけ。`(動画ID, カーブ, コマの列)`。"""
    if not CURVES.exists() or not QUEUE.is_dir():
        return []
    try:
        curves = json.loads(CURVES.read_text())
    except Exception:
        return []
    out = []
    for vid, curve in sorted(curves.items()):
        p = QUEUE / f"{vid}.json"
        if not p.exists() or not curve:
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        rows = segment_rows(d.get("narration") or [])
        if len(rows) < MIN_SEGMENTS:
            continue
        clean = sorted((float(c[0]), float(c[1]), float(c[2]) if len(c) > 2 else 0.0)
                       for c in curve)
        out.append((vid, clean, rows))
    return out


def control(bs: list | None = None) -> tuple[float, int]:
    """**陽性対照**: 位置 と 1秒あたりの落ち方。`(rho, コマ数)`。

    落ちが前に寄るのは、`scripts/retention.py` が100点を引いた理由そのものです。
    **これが `CONTROL_MAX_RHO` より弱かったら、下の数は読めません。**
    """
    bs = books() if bs is None else bs
    pos: list[float] = []
    drop: list[float] = []
    for _vid, curve, rows in bs:
        for r in rows:
            pos.append(r["pos"])
            drop.append((curve_at(curve, r["start"]) - curve_at(curve, r["end"])) / r["sec"])
    return spearman(pos, drop), len(pos)


#: 物差し ＝ `(コマの列 → 本ごとの1つの数, 分かりにくいほど維持率がどちらへ動くはずか)`。
#: **向きを一緒に置くのが、この表の本体です** —— 向きが書いていない物差しは、
#: どんな数が出ても「そういうものだ」と読めてしまいます。
MEASURES: dict[str, tuple] = {
    "数の個数 平均": (lambda rs: sum(r["数の個数"] for r in rs) / len(rs), -1),
    "数の個数 最大": (lambda rs: max(r["数の個数"] for r in rs), -1),
    "言った桁 合計/コマ": (lambda rs: sum(r["言った桁"] for r in rs) / len(rs), -1),
    "言った桁 一息の最大": (lambda rs: max(r["言った桁"] for r in rs), -1),
    "1つの数の桁 最大": (lambda rs: max(r["桁の最大"] for r in rs), -1),
    "指示語（広い）合計": (lambda rs: sum(r["指示語"] for r in rs), -1),
    "文字/コマ": (lambda rs: sum(r["文字数"] for r in rs) / len(rs), -1),
}

#: 人の側の出口。**1つに絞らないこと** —— 1つだけだと、その出口の癖を
#: 物差しの性質と読み違えます（`request_form` が同じ所を踏んでいます）。
OUTCOMES: dict[str, tuple] = {
    "50%地点の維持": (lambda c: curve_at(c, 0.5), "audienceWatchRatio"),
    "25%地点の維持": (lambda c: curve_at(c, 0.25), "audienceWatchRatio"),
    "相対（平均）": (lambda c: sum(r[2] for r in c) / len(c), "relativeRetentionPerformance"),
}

#: **生成の輪に実際に配線されている物差し**（`src/verify._check_ear_load`）。
#: 名前で持っているのは、報告が「配線ずみのものだけ」を名指しできるようにするため。
WIRED = "数の個数 最大"


def table(bs: list | None = None) -> dict:
    """物差し × 出口 の順位相関。`report_lines()` の材料。"""
    bs = books() if bs is None else bs
    n = len(bs)
    out: dict = {"n": n, "門": significant_at(n) if n > 2 else float("inf"), "行": {}}
    if n < 3:
        return out
    for mname, (fn, sign) in MEASURES.items():
        xs = [fn(rows) for _v, _c, rows in bs]
        row = {"向き": sign, "rho": {}}
        for oname, (ofn, _src) in OUTCOMES.items():
            ys = [ofn(curve) for _v, curve, _r in bs]
            row["rho"][oname] = spearman(xs, ys)
        vals = list(row["rho"].values())
        row["逆が全部"] = all(v * sign < 0 for v in vals)
        row["最大"] = max(vals, key=abs)
        out["行"][mname] = row
    return out


def report_lines() -> list[str]:
    bs = books()
    if len(bs) < 3:
        return ["  控えと維持率カーブが両方ある本が足りません"
                f"（{len(bs)}本）。`python scripts/retention.py` で貯まります"]
    rho_c, ncoma = control(bs)
    out = [f"控えと維持率カーブが両方ある本 **{len(bs)}本** / {ncoma}コマ"]
    ok = rho_c <= CONTROL_MAX_RHO
    out.append(f"  陽性対照（位置 vs 1秒あたりの落ち方）: **rho = {rho_c:+.3f}**"
               f"（門 {CONTROL_MAX_RHO:+.2f}）→ " + ("計器は生きています" if ok else
               "**[!] 計器が死んでいます。下の数を読まないこと**"))
    if not ok:
        out.append("      先に疑うのは台本の側の時間割（文字数 ÷ 話速）"
                   "が実物とずれているほうです（`segment_rows`）")
        return out
    t = table(bs)
    gate = t["門"]
    out.append(f"  n={t['n']} → 有意（両側5%）になるのは **|rho| ≧ {gate:.3f}**")
    names = list(OUTCOMES)
    out.append("  " + " " * 20 + "".join(f"{o:>14s}" for o in names) + "   向き")
    for mname, row in t["行"].items():
        cells = "".join(f"{row['rho'][o]:>+14.3f}" for o in names)
        # `向き` は「分かりにくいほど維持率がどちらへ動くはずか」（-1 ＝ 下がるはず）。
        # **同じ符号なら見込みどおり**です（rho が負・向きが -1 → 積は正）。
        mark = "✗ 逆" if row["逆が全部"] else ("○" if row["最大"] * row["向き"] > 0 else "—")
        star = " ★" if abs(row["最大"]) >= gate else ""
        tag = "*" if mname == WIRED else " "
        out.append(f"  {tag}{mname:19s}{cells}   {mark}{star}")
    hit = [m for m, r in t["行"].items() if abs(r["最大"]) >= gate]
    out.append(f"  有意な物差し: **{len(hit)}件**"
               + (f"（{'・'.join(hit)}）" if hit else " —— **n がまだ足りません**"))
    w = t["行"].get(WIRED)
    if w:
        need = needed_for(w["最大"])
        out.append(f"  * ＝ 生成の輪に配線ずみ（`verify._check_ear_load`）。"
                   f"いまの大きさ {w['最大']:+.3f} を 5% で拾うには **{need}本** 要ります"
                   f"（あと {max(0, need - t['n'])}本）")
        if w["逆が全部"]:
            out.append("  [!] **配線ずみの物差しだけ、3つの出口の全部で向きが逆です。**"
                       "「多いほど分かりにくい」の側の証拠は1つもありません"
                       "（`config/hypotheses.yaml` の `clarity_ear_load_sign`）")
    out.append("  **カーブを貯めると判定が早まります**: `python scripts/retention.py`"
               "（貯めに無いIDだけ引くので `--refresh` は要りません）")
    return out


def main() -> int:
    for line in report_lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
