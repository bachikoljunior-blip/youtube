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

    実測 2026-09-02: 位置 と 落ち方（1秒あたり）の順位相関 **rho = -0.448**（689コマ・113本）
                     69本 だったときも -0.468 で、**本数が変わっても動きません**
                     （下の表の rho は 44本 で入れ替わりました。**対照だけが動かない**のが、
                      この対照を置いた意味です）

**これが出ないうちは、下の数を読まないこと。** `control()` が門です。

## **同じ回の中で、答えが入れ替わりました**（2026-09-02。**この節を最初に読むこと**）

**この module を書いた回は、まず 69本 で測って「配線ずみの物差し（数の個数）だけが
3つの出口の全部で向きが逆」と書きました。** そのうえで
`scripts/retention.py` を撃って **113本** にし、撃ち直したら:

    物差し              69本 のとき          113本 のとき
    数の個数 最大        +0.170 / +0.130 / +0.115   **+0.045 / -0.007 / -0.005**（消えた）
    文字/コマ           -0.130 / -0.073 / -0.066   **-0.200 / -0.180 / -0.137**（門を越えた）
    門（両側5%）        |rho| ≧ 0.238             |rho| ≧ 0.185

**44本 増えただけで、「逆に効いている」は消え、代わりに『一息の長さ』が
この repo で初めて門を越えました。** 教訓は2つ、どちらも同じ向きです:

1. **n=69 の rho は、符号すら憶えていられません。** 有意でない数から
   「向きが逆」を読むのは、この回がやりかけて外したことです。
   **`report_lines()` が門（`significant_at`）を必ず並べて出すのは、そのためです。**
2. **貯めるほうが、考えるより速い。** 撃ったのは1手（`python scripts/retention.py`・
   数分・Data API の日枠は使いません）で、それだけで**結論が入れ替わりました。**
   新しい物差しを考える前に、まずカーブを貯めること。

## 2026-09-02 の実測 その2（**113本**・こちらが新しい）

    n=113 → 有意（両側5%）になるのは |rho| ≧ 0.185

    物差し                     50%地点の維持   25%地点   相対(平均)   向き
    数の個数 平均               -0.006        -0.066    -0.067      ○ ほぼゼロ
    **数の個数 最大**           **+0.045**    -0.007    -0.005      — ← **配線ずみ**
    言った桁 合計/コマ           +0.112        +0.074    +0.060      ✗ 逆
    言った桁 一息の最大           +0.065        +0.013    +0.002      ✗ 逆
    1つの数の桁 最大             +0.103        +0.059    +0.049      ✗ 逆
    指示語（広い）合計           -0.039        -0.054    -0.017      ○ 小さい
    **文字/コマ**              **-0.200 ★**  -0.180    -0.137      ○ **門を越えた**

**＝ いま門に立っている物差し（一息にいくつ数が載っているか）は、人の側の数と
関係がありません**（いまの大きさ +0.045 を 5% で拾うには **1,864本** 要ります ——
チャンネルの本数を超えており、**実質 到達しません**）。
**関係があったのは『一息が何文字か』のほう**でした。

**それでも、この回に門を入れ替えていません。** ★ は3つの出口のうち1つで
やっと越えたところで、`src/alerts.py` の「**一覧が当たりを含まないまま育つ**」に
いちばん近い形だからです。**判定は台帳へ置きました**
（`config/hypotheses.yaml` の `clarity_ear_load_sign`・135本・期限 2026-09-25）。

## 2026-09-02 の実測 その1（69本。**上の節が言うとおり、これは残骸です**）

    n=69 → 有意（両側5%）になるのは |rho| ≧ 0.238

    物差し                     50%地点の維持   25%地点   相対(平均)   向き
    数の個数 平均               **+0.125**     +0.068    +0.072      ✗ 逆
    数の個数 最大               **+0.170**     +0.130    +0.115      ✗ 逆
    言った桁 合計/コマ           +0.159        +0.106    +0.089      ✗ 逆
    言った桁 一息の最大           +0.133        +0.083    +0.061      ✗ 逆
    1つの数の桁 最大             +0.161        +0.125    +0.075      ✗ 逆
    指示語（広い）合計           -0.109        -0.096    +0.054      ○ ただし小さい
    文字/コマ                  -0.130        -0.073    -0.066      ○ ただし小さい

**この表を残しているのは、上の節の証拠だからです。** 書いた回は
「有意なものは1つもない（門 0.238）」と正しく添えたうえで、
**「配線ずみの物差しだけ3つの出口の全部で向きが逆」を結論のように書きました。**
**44本 足しただけで、その向きは消えています。**
**有意でない rho から向きを読まないこと** ——
この節は、そのいちばん短い実例として置いてあります。

## 何本 貯まれば言えるか

    |rho| = 0.20 を 5% で拾うのに要る本  **n ≒ 194**
    |rho| = 0.30                        **n ≒  85**

`data/retention.json` は **132本**、うち控えがあってコマが4つ以上ある本が **113本**
（2026-09-02・この回に 88 → 132 まで貯めました）。
**貯めの井戸は、この回で尽きました** —— 2度目に撃って増えたのは **+1本**です
（`retention.videos()` が読む `data/scan.jsonl` の中の本を、ほぼ引ききった）。
**ここから先は、公開した本（1日1本）と走査の増えるぶんだけ**です。
**`python scripts/retention.py` を撃つたびに増えます**
（貯めに無いIDだけ引くので `--refresh` は要りません。
**Data API の日枠は使いません** —— Analytics は別の枠なので、403 の窓でも撃てます）。
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
- **`文字/コマ` が 2回 続けて門を越えたら**（別々の回・n が増えた状態で）、
  そちらを門にすること。**1回で入れないのは、113本 の ★ が
  3つの出口のうち1つでやっと越えたところだから**です
  （`src/alerts.py`「一覧が当たりを含まないまま育つ」）。
  入れ先は `script_writer.{long,short}_script_problems`
  （`_check_ear_load` の隣。**`verify.run` の門にしないこと** —— 誤報が不投稿になります）
"""
from __future__ import annotations

import json
import datetime as _dt
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

#: **読みの控え**。1周に1行 積みます。`streak()` の材料。
#: **なぜ要るか**: 昇格の条件（下）が「**n が増えた別々の回**で 2回 続けて」なので、
#: **その回の表だけでは判定できません。** 前の回の n を持っていないと、
#: **同じ 1回の観測を 2回 数えて昇格させます**（2026-09-02 11:4x に踏みかけた
#: —— `retention.py` が 500 で 0本 しか足さず、n が 113 のまま、
#: 表は前の回と1桁も違わないのに「2回目の ★」に見えました）。
LEDGER = config.ROOT / "data" / "clarity.jsonl"
VIEWS = config.ROOT / "data" / "views.jsonl"

#: **昇格の条件**（`docs/JOURNAL.md`「次の回へ」2. の原文を数にしたもの）——
#: 「`文字/コマ` が 2回 続けて門を越えたら（**別々の回・n が増えた状態で**）、
#: `script_writer.{long,short}_script_problems` に入れること。**1回では入れないこと**」
PROMOTE_STREAK = 2


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


def readings() -> list[dict]:
    """控えの行を古い順に。**n が同じ連続した行は、いちばん新しい1行へ畳みます。**

    畳むのは、**同じ観測を2回 数えないため**です。`record()` は n が動いた回だけ
    足しますが、merge で両方残った跡（この repo で何度も出ている形）が入っても、
    ここで1本になります。
    """
    if not LEDGER.exists():
        return []
    rows: list[dict] = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rows and rows[-1].get("n") == r.get("n"):
            rows[-1] = r          # 同じ n は畳む（新しいほうを残す）
        else:
            rows.append(r)
    return rows


def record(t: dict, rho_c: float) -> tuple[dict, bool]:
    """この回の読みを控えへ。`(その行, 足したか)`。

    **n が前の回から動いていない回は足しません。** 足すと `streak()` が
    「別々の回」を数えられなくなり、**1回の観測で昇格します**。
    """
    row = {
        "at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "n": t["n"],
        "門": t["門"],
        "対照": rho_c,
        "対照ok": rho_c <= CONTROL_MAX_RHO,
        "rho": {m: r["最大"] for m, r in t["行"].items()},
    }
    prev = readings()
    if prev and prev[-1].get("n") == row["n"]:
        return row, False
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row, True


def streak(measure: str, rows: list[dict] | None = None) -> int:
    """その物差しが、**n の増えた別々の回で** 何回 続けて門を越えているか。

    **昇格（`PROMOTE_STREAK`）はこの数だけで決めます。**
    表の ★ を目で2回 見ることでは決めません —— ★ は n が動かなくても同じ字で出ます。
    **対照が落ちている回は連を切ります**（計器が死んでいる回の ★ は読めない）。
    """
    rows = readings() if rows is None else rows
    out = 0
    for r in reversed(rows):
        if not r.get("対照ok", True):
            break
        v = (r.get("rho") or {}).get(measure)
        if v is None or abs(v) < r.get("門", float("inf")):
            break
        out += 1
    return out


def views_map() -> dict[str, int]:
    """`video_id` → 観測した最大の累計再生（`data/views.jsonl`）。**API 0単位。**

    `videos.list` の累計なので、Analytics の3日遅れは掛かりません。
    """
    out: dict[str, int] = {}
    if not VIEWS.exists():
        return out
    for line in VIEWS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid, v = r.get("id"), r.get("views")
        if vid and isinstance(v, (int, float)):
            out[str(vid)] = max(out.get(str(vid), 0), int(v))
    return out


def views_table(bs: list | None = None) -> dict:
    """物差し × **1本あたり再生**の順位相関。`(n, {物差し: rho})`。

    ## なぜ別に要るか（2026-09-02 11:5x）

    `OUTCOMES` は3つとも**維持率**です —— 「入ってきた人が最後まで見たか」。
    **`eta.py` が「引けるのは `per_video` だけ」と名指ししている腕は、そこではありません** ——
    あちらは「**何人が見に来たか**」（`rule_per_video.ceiling_at_rule()` ＝ 4,101回）で、
    **別の軸**です。維持率と再生数は逆相関することがあります
    （`analytics.fetch_retention` の註 —— 実測 537再生で相対0.50、1506再生で相対0.25）。

    **＝ 維持率で越えた物差しが、天井のほうにも効く保証はありません。**
    この表は、その1点だけを見ます。
    """
    bs = books() if bs is None else bs
    vm = views_map()
    pairs = [(rows, vm[vid]) for vid, _c, rows in bs if vid in vm]
    out: dict = {"n": len(pairs), "門": significant_at(len(pairs)) if len(pairs) > 2 else float("inf"),
                 "rho": {}}
    if len(pairs) < 3:
        return out
    ys = [v for _r, v in pairs]
    for mname, (fn, _sign) in MEASURES.items():
        out["rho"][mname] = spearman([fn(rows) for rows, _v in pairs], ys)
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
    # ---- 腕（`per_video`）のほうにも当ててみる ----
    vt = views_table(bs)
    if vt["n"] >= 3:
        vhit = [m for m, r in vt["rho"].items() if abs(r) >= vt["門"]]
        out.append(f"  **1本あたり再生（＝ 引ける腕 `per_video`）に当てると**（n={vt['n']}"
                   f"・門 {vt['門']:.3f}）: "
                   + (f"**{len(vhit)}件 が門を越えます**（"
                      + "・".join(f"{m} {vt['rho'][m]:+.3f}" for m in vhit) + "）"
                      if vhit else "**1件も越えません**"))
        out.append("      **維持率で越えた物差しが、天井のほうにも効くとはかぎりません**"
                   " —— 維持率は「入った人が残ったか」、こちらは「何人 来たか」で別の軸です"
                   "（`analytics.fetch_retention` の註: 実測で逆相関することがあります）")
    # ---- ここから下は「この ★ を、前の回の ★ と足してよいか」だけを言います ----
    # **表の ★ は n が動かなくても同じ字で出ます。** だから目で2回 見ても
    # 「2回 続けて越えた」の証拠になりません（2026-09-02 に踏みかけた形）。
    prev = readings()
    before = prev[-1] if prev else None
    row, added = record(t, rho_c)
    if before is None:
        out.append(f"  **この読みが控えの1点目です**（n={t['n']}・`data/clarity.jsonl`）。"
                   f"連は下の数で数えます")
    elif not added:
        out.append(f"  [!] **この読みは前の回と同じ n（{t['n']}本）です —— 新しい観測ではありません。**"
                   f"　控えへ足していません（前の読みは {before['at']}）")
        out.append(f"      **上の ★ を、前の回の ★ と足さないこと。**"
                   f"　n が増えていない回の ★ は、前の回の ★ と同じ1つの観測です")
        out.append(f"      n が増えないときは `scripts/retention.py` の出どころを見ること"
                   f"（**500 でも 0本 でも、あの道具は表を出して正常終了します**）")
    else:
        out.append(f"  **新しい観測です**: n {before['n']} → **{t['n']}本**"
                   f"（門 {before['門']:.3f} → {gate:.3f}）。控えへ足しました")
    # 昇格の条件を、prose ではなく数で出す
    rows = readings()
    for mname in t["行"]:
        k = streak(mname, rows)
        if k <= 0:
            continue
        if k >= PROMOTE_STREAK:
            out.append(f"  ★ **`{mname}` は n の増えた別々の回で {k}回 続けて門を越えました"
                       f"（条件 {PROMOTE_STREAK}回）→ 台本の側へ入れる番です**: "
                       f"`script_writer.{{long,short}}_script_problems`"
                       f"（`_check_ear_load` の隣。**`verify.run` の門にしないこと** ——"
                       f" 誤報が不投稿になります）")
        else:
            out.append(f"  `{mname}`: 連 **{k}／{PROMOTE_STREAK}回**"
                       f"（n の増えた回だけ数えています）。**まだ入れないこと**")
    out.append("  **カーブを貯めると判定が早まります**: `python scripts/retention.py`"
               "（貯めに無いIDだけ引くので `--refresh` は要りません）")
    return out


def main() -> int:
    for line in report_lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
