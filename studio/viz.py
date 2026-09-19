"""動く図 —— 分かりにくい仕組みと計算を、**動く表・棒・引き算**で画面に置く。

オーナー 2026-09-17 20:4x JST（受け取り帳 `d699098f`・**一字も変えないこと**）:

    「アニメーションとか画像でイメージしやすくって言ったのはさ、わかりにくい仕組みとか計算とかを
     動く表とかいろんなグラフとかあるいは何かを表したアニメーションとかにしないと意味ないでしょ。」

**この回（2026-09-17 21:0x・optimizer・Fable 5.1・ultracode）に数えた事実**:
  * 09/16 12:1x「説明のパートごとにアニメーションとか画像で」（`751f4947`）に当てたのは
    **部ごとの背景の絵**（`Segment.image`・GPT Image 2.0 の写真）でした。**動く物は 1つも無く**、
    画面で計算を見せているのは **板（`board`）の字だけ**です（実物: 16本・すべて 1コマ 1枚 の静止画）。
  * オーナーが言っているのは背景ではなく、**分かりにくい所そのもの**（仕組み・計算）を
    **動く表・グラフ・アニメーション**にすること。写真の背景は、それを 1つも持ちません。

**形**: `Segment.viz` に図の指定を書くと、そのコマは **1枚 の静止画ではなく、動く数枚** になります
（`render.build` が `slides.slide_frames` を呼び、ffmpeg の concat に短い刻で並べる）。
書かなければ **1コマ 1枚 のまま**（既に在る本は 1画素も動かない・指紋も動かない）。

    {"kind": "bars",      "title": "…", "items": [{"label": "…", "value": 75500}, …],
                          "total": {"label": "…", "value": 153300}}         # 棒が順に伸び、数が数え上がる
    {"kind": "waterfall", "title": "…", "start": {"label": "年金", "value": 1800000},
                          "steps": [{"label": "控除", "value": 1100000}, …],
                          "end": {"label": "所得", "value": 700000}}          # 1本 の棒から、引く分が赤く切れていく
    {"kind": "table",     "title": "…", "head": ["…", "…"], "rows": [["…", "…"], …]}   # 行が 1つずつ出る（最後の行が黄色）
                          ※ 同じ単位の数が縦に並ぶ列には、マスの中に**長さ**が引かれます（`table_bar_column`）
    {"kind": "gauge",     "title": "…", "marks": [{"label": "住民税がかかる線", "value": 450000}],
                          "value": {"label": "この方の所得", "value": 100000},
                          "verdict": {"text": "住民税 0円", "value": 0}}   # 数直線に線を引き、その人の位置を置く

    値は **円の整数**（`fmt_num` が 7万5500円 の形にする・`unit` で変えられる）。
    `text` を書けばその字をそのまま出す（率や「0円にならない」のような字）。

**置き場**: 板（`board`）と同じ所（縦は show の下 y 600〜1080・横は左の列）。
**同じコマに `board` と `viz` が両方 在れば `viz` が勝ちます**（板の字は critique には渡り続ける）。

**時間**: 動くのはコマの頭 `anim_seconds()`（0.6〜1.8秒・コマの 45%）で、残りは最後の絵で止まる
（声がその数を言い終わるより先に絵が出来ている・止まってから読める）。刻は `FPS`。

覆る条件:
 (1) 図を入れた本 3本 の維持率（`data/retention.json` の 25%・50%）が、板だけの本 3本 を下回ったら、
     図は気を散らす側 ＝ `anim_seconds` を 0 にして（動かない図）から疑うこと。**口は残す。**
 (2) 図が要る所（計算・しくみ）で、この 3つ の形（棒・引き算・表）に収まらない本が 2本 出たら、
     4つ目 の形（例: 齢 → 額 の折れ線・「何歳で元が取れるか」）を足すこと（`KINDS`）。
 (3) オーナーが画面の動きに言葉を出したら、その言葉が正本。
"""
from __future__ import annotations

import math
import re

from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_BLACK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"

KINDS = ("bars", "waterfall", "table", "lines", "gauge")
FPS = 12                 # 動く刻（1秒 12枚。ffmpeg は 30fps に伸ばす）
MAX_ITEMS = 6            # 棒・行の数の上限（縦 480px に 7行 は入らない）
MAX_LABEL = 14           # 札の字数（板の 1行 と同じ）
MAX_CELL = 12            # 表の 1マス
_TEN = re.compile(r"点|[0-9０-９]\.[0-9０-９]")

BLUE = (70, 130, 220)
RED = (220, 80, 70)
YELLOW = (255, 225, 120)
ORANGE = (220, 150, 40)
GREEN = (60, 160, 90)
WHITE = (245, 245, 245)
GRAY = (170, 170, 170)
COLORS = {"blue": BLUE, "red": RED, "yellow": YELLOW, "orange": ORANGE, "green": GREEN}


def fmt_num(v: float, unit: str = "円") -> str:
    """1800000 → 180万円・75500 → 7万5500円・153300 → 15万3300円・-12800 → −1万2800円。"""
    v = int(round(v))
    neg = v < 0
    v = abs(v)
    if v >= 10 ** 8:
        oku, rest = divmod(v, 10 ** 8)
        man, rest = divmod(rest, 10 ** 4)
        s = f"{oku}億" + (f"{man}万" if man else "") + (f"{rest}" if rest else "")
    elif v >= 10 ** 4:
        man, rest = divmod(v, 10 ** 4)
        s = f"{man}万" + (f"{rest}" if rest else "")
    else:
        s = f"{v}"
    return ("−" if neg else "") + s + unit


def _text(item: dict, unit: str, scale: float = 1.0) -> str:
    """項目の字。`text` が在ればそのまま・無ければ値を `fmt_num`。数え上がりの途中は 100 の刻で丸める。"""
    if item.get("text") and scale >= 1.0:
        return str(item["text"])
    v = float(item.get("value", 0)) * scale
    if scale < 1.0 and abs(v) >= 10000:
        v = round(v / 100) * 100
    return fmt_num(v, unit)


def check(spec: dict, where: str = "") -> list[str]:
    """形の検査（`Script.problems()` が呼ぶ・**止める**）。空なら通る。"""
    out = []
    pre = f"{where} viz" if where else "viz"
    if not isinstance(spec, dict):
        return [f"{pre} は dict で書く"]
    kind = spec.get("kind")
    if kind not in KINDS:
        return [f"{pre} kind「{kind}」は {'／'.join(KINDS)} のどれかに"]
    labels: list[str] = [str(spec.get("title") or "")]
    if kind == "bars":
        items = spec.get("items") or []
        if not items:
            out.append(f"{pre} items が空")
        if len(items) > MAX_ITEMS:
            out.append(f"{pre} items が {len(items)}（{MAX_ITEMS}まで）")
        for it in items + ([spec["total"]] if spec.get("total") else []):
            labels.append(str(it.get("label", "")))
            if "value" not in it and "text" not in it:
                out.append(f"{pre} 「{it.get('label')}」に value も text も無い")
    elif kind == "waterfall":
        for key in ("start", "end"):
            if not isinstance(spec.get(key), dict) or "value" not in spec[key]:
                out.append(f"{pre} {key} に value が無い")
            else:
                labels.append(str(spec[key].get("label", "")))
        steps = spec.get("steps") or []
        if not steps:
            out.append(f"{pre} steps が空")
        if len(steps) > MAX_ITEMS - 2:
            out.append(f"{pre} steps が {len(steps)}（{MAX_ITEMS - 2}まで）")
        for st in steps:
            labels.append(str(st.get("label", "")))
            if "value" not in st:
                out.append(f"{pre} step「{st.get('label')}」に value が無い")
        if not out:
            got = float(spec["start"]["value"]) - sum(abs(float(st["value"])) for st in steps)
            want = float(spec["end"]["value"])
            if abs(got - want) > 0.5:
                out.append(f"{pre} start − steps ＝ {fmt_num(got)} で end の {fmt_num(want)} と合わない")
    elif kind == "lines":
        xs = spec.get("x") or {}
        ser = spec.get("series") or []
        if len(ser) != 2:
            out.append(f"{pre} series は 2本（いま {len(ser)}）")
        for sr in ser:
            labels.append(str(sr.get("label", "")))
            for key in ("at", "per_month"):
                if key not in sr:
                    out.append(f"{pre} 「{sr.get('label')}」に {key} が無い")
        if "from" not in xs or "to" not in xs:
            out.append(f"{pre} x に from / to（横の齢の端）が無い")
        if not out:
            x0v, x1v = float(xs["from"]), float(xs["to"])
            xu = str(xs.get("unit", "歳"))
            if x1v <= x0v:
                out.append(f"{pre} x の from {x0v} が to {x1v} 以上")
            cx = _cross_x(ser[0], ser[1])
            if cx is None:
                out.append(f"{pre} 2本 の per_month が同じ ＝ 追い越しません")
            elif not (x0v < cx < x1v):
                out.append(f"{pre} 追い越すのは {_age_text(cx, xu)} で、x の {x0v}〜{x1v} の外")
            else:
                want = str((spec.get("cross") or {}).get("at", "") or "").strip()
                got = _age_text(cx, xu)
                if not want:
                    out.append(f"{pre} cross.at が無い（追い越す齢の字。計算では {got}）")
                elif want != got:
                    out.append(f"{pre} cross.at「{want}」は計算では {got}")
                else:
                    labels.append(want)
    elif kind == "gauge":
        marks = spec.get("marks") or []
        if not marks:
            out.append(f"{pre} marks が空（線が 1つ も無い ＝ この形ではありません）")
        if len(marks) > MAX_MARKS:
            out.append(f"{pre} marks が {len(marks)}（{MAX_MARKS}まで・覆る条件 (1)）")
        for m in marks:
            labels.append(str(m.get("label", "")))
            if "value" not in m:
                out.append(f"{pre} 印「{m.get('label')}」に value が無い")
        # `value`（その人の位置）は**無くてよい** —— 段を先に見せるコマ（まだ誰も乗っていない）が在ります
        # （実物 `2026-09-20-nenkin-tedori-hayamihyou` コマ67・68）。
        val = spec.get("value") or {}
        if val:
            if "value" not in val:
                out.append(f"{pre} value に value が無い（その人の位置）")
            else:
                labels.append(str(val.get("label", "")))
        if not out:
            lo, hi = _gauge_span(spec)
            for m in list(marks) + ([val] if val else []):
                v = float(m.get("value", 0) or 0)
                if not (lo <= v <= hi):
                    out.append(f"{pre} 「{m.get('label')}」{fmt_num(v, spec.get('unit', '円'))} が "
                               f"横の {fmt_num(lo, spec.get('unit', '円'))}〜{fmt_num(hi, spec.get('unit', '円'))} の外")
            if val and len(marks) == 1 and float(val.get("value", 0) or 0) == float(marks[0]["value"]):
                out.append(f"{pre} その人の位置が線とぴったり同じ ＝ 超えるか超えないかが絵で言えません")
        labels.append(str((spec.get("verdict") or {}).get("text", "")))
    elif kind == "table":
        rows = spec.get("rows") or []
        head = spec.get("head") or []
        if not rows:
            out.append(f"{pre} rows が空")
        if len(rows) > MAX_ITEMS:
            out.append(f"{pre} rows が {len(rows)}（{MAX_ITEMS}まで）")
        ncol = len(head) if head else (len(rows[0]) if rows else 0)
        if ncol < 2 or ncol > 4:
            out.append(f"{pre} 列は 2〜4（いま {ncol}）")
        for r in rows:
            if len(r) != ncol:
                out.append(f"{pre} 行「{'/'.join(map(str, r))}」の列数が {len(r)}（見出しは {ncol}）")
            for c in r:
                if len(str(c)) > MAX_CELL:
                    out.append(f"{pre} マス「{c}」が {len(str(c))}字（{MAX_CELL}まで）")
                labels.append(str(c))
        labels += [str(h) for h in head]
    for lb in labels:
        if len(lb) > MAX_LABEL and kind != "table":
            out.append(f"{pre} 札「{lb}」が {len(lb)}字（{MAX_LABEL}まで）")
        m = _TEN.search(lb)
        if m:
            out.append(f"{pre} に「{m.group()}」（点・小数）。整数で言い換える")
    return out


def describe(spec: dict) -> str:
    """critique と 指紋 に渡す 1行（**画面に出る数と字を全部 含む**・絵の寸法は含まない）。"""
    unit = spec.get("unit", "円")
    kind = spec.get("kind")
    t = f"{spec['title']}: " if spec.get("title") else ""
    if kind == "bars":
        parts = [f"{it.get('label', '')} {_text(it, unit)}" for it in spec.get("items", [])]
        if spec.get("total"):
            parts.append(f"＝ {spec['total'].get('label', '')} {_text(spec['total'], unit)}")
        return f"棒グラフ（順に伸びる）{t}" + " ／ ".join(parts)
    if kind == "waterfall":
        st, en = spec.get("start", {}), spec.get("end", {})
        parts = [f"{st.get('label', '')} {_text(st, unit)}"]
        parts += [f"− {s.get('label', '')} {fmt_num(abs(float(s.get('value', 0))), unit)}" for s in spec.get("steps", [])]
        parts.append(f"＝ {en.get('label', '')} {_text(en, unit)}")
        return f"引き算の棒（引く分が赤く切れる）{t}" + " ".join(parts)
    if kind == "lines":
        xs = spec.get("x") or {}
        xu = str(xs.get("unit", "歳"))
        parts = [f"{sr.get('label', '')}（{_age_text(float(sr.get('at', 0) or 0), xu)}から毎月"
                 f"{fmt_num(float(sr.get('per_month', 0) or 0), unit)}）" for sr in (spec.get("series") or [])]
        cr = str((spec.get("cross") or {}).get("at", "") or "")
        return (f"折れ線（合計が右へのびて交わる）{t}" + " ／ ".join(parts)
                + (f" → 合計が並ぶのは {cr}" if cr else ""))
    if kind == "gauge":
        ms = " ／ ".join(f"{m.get('label', '')} {_text(m, unit)}" for m in (spec.get("marks") or []))
        v = spec.get("value") or {}
        vd = (spec.get("verdict") or {}).get("text") or ""
        return (f"数直線（線に印・その人の位置）{t}{ms}"
                + (f" → {v.get('label', '')} {_text(v, unit)}" if "value" in v else "")
                + (f" ＝ {vd}" if vd else ""))
    if kind == "table":
        head = spec.get("head") or []
        rows = [" | ".join(map(str, r)) for r in spec.get("rows", [])]
        return f"表（行が 1つずつ出る）{t}" + (f"[{' | '.join(map(str, head))}] " if head else "") + " ／ ".join(rows)
    return f"図 {kind}"


def anim_seconds(seconds: float) -> float:
    """動く長さ。コマの 45%・0.6〜1.8秒。1秒 に満たないコマは動かない（最後の絵だけ）。"""
    if seconds < 1.0:
        return 0.0
    return max(0.6, min(1.8, seconds * 0.45))


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=0)


def _fit(d: ImageDraw.ImageDraw, text: str, path: str, size: int, width: int, floor: int = 22) -> ImageFont.FreeTypeFont:
    """幅に収まるまで字を下げる。"""
    while size > floor:
        f = _font(path, size)
        if d.textbbox((0, 0), text, font=f)[2] <= width:
            return f
        size -= 2
    return _font(path, floor)


def _title(d: ImageDraw.ImageDraw, spec: dict, W: int, pad: int) -> int:
    t = spec.get("title") or ""
    if not t:
        return pad
    f = _fit(d, t, FONT_BOLD, 40, W - 2 * pad)
    d.text((pad, pad), t, font=f, fill=WHITE, stroke_width=2, stroke_fill=(0, 0, 0))
    return pad + int(f.size * 1.35) + 6


def _slot(k: int, n: int, p: float) -> float:
    """k 番目（0〜）の項目の進み（0〜1）。全体の進み p を n 等分し、順に動かす。"""
    if n <= 0:
        return 1.0
    a, b = k / n, (k + 1) / n
    return 0.0 if p <= a else (1.0 if p >= b else (p - a) / (b - a))


def _ease(x: float) -> float:
    return 1 - (1 - x) ** 3


def _value_w(d, vf, values: list[float], unit: str, texts: list[str] = ()) -> int:
    """値の字のために右に空ける幅。**数え上がりの途中の字（96万2500円）は最後の字（110万円）より長い**ので、
    途中の値も測る（実物: 動く途中で右端が箱から出た・2026-09-17 21:xx）。"""
    cands = list(texts)
    for v in values:
        for f in (1.0, 0.93, 0.71, 0.37):
            vv = v * f
            if f < 1.0 and abs(vv) >= 10000:
                vv = round(vv / 100) * 100
            cands.append(fmt_num(vv, unit))
    return max((d.textbbox((0, 0), c, font=vf)[2] for c in cands if c), default=0) + 16


def _bar_rows(d, W, H, top, pad, rows: list[tuple[str, str, float, tuple, float]], maxv: float, unit: str = "円"):
    """rows: (札, 値の字, 値, 色, 進み)。札 → 棒 → 値 の 1行 を、行の数に合わせた字で描く。"""
    n = len(rows)
    row_h = min(100, (H - top - pad) // max(n, 1))
    fsz = max(24, min(40, int(row_h * 0.42)))
    lf = _font(FONT_BOLD, fsz)
    vf = _font(FONT_BLACK, fsz + 2)
    label_w = min(int(W * 0.34), max(d.textbbox((0, 0), lb, font=lf)[2] for lb, *_ in rows) + 16)
    value_w = _value_w(d, vf, [v for _, _, v, *_ in rows], unit, [vt for _, vt, *_ in rows])
    x0 = pad + label_w
    bar_w = max(60, W - pad - value_w - x0 - 16)
    bh = int(row_h * 0.52)
    y = top
    for lb, vt, v, color, prog in rows:
        cy = y + row_h // 2
        d.text((pad, cy - fsz // 2 - 4), lb, font=lf, fill=WHITE, stroke_width=2, stroke_fill=(0, 0, 0))
        if prog > 0:
            wv = int(bar_w * (abs(v) / maxv if maxv else 0) * _ease(prog))
            d.rounded_rectangle([x0, cy - bh // 2, x0 + max(wv, 6), cy + bh // 2], radius=8, fill=color)
            d.text((x0 + max(wv, 6) + 14, cy - fsz // 2 - 4), vt, font=vf, fill=color if color != BLUE else YELLOW,
                   stroke_width=2, stroke_fill=(0, 0, 0))
        y += row_h


def _draw_bars(d, spec, W, H, p, unit, pad):
    top = _title(d, spec, W, pad)
    items = list(spec.get("items") or [])
    total = spec.get("total")
    n = len(items) + (1 if total else 0)
    vals = [abs(float(it.get("value", 0))) for it in items] + ([abs(float(total.get("value", 0)))] if total else [])
    maxv = max(vals) if vals else 1.0
    rows = []
    for k, it in enumerate(items):
        pr = _slot(k, n, p)
        rows.append((str(it.get("label", "")), _text(it, unit, _ease(pr)) if pr > 0 else "",
                     float(it.get("value", 0)), COLORS.get(it.get("color", ""), BLUE), pr))
    if total:
        pr = _slot(n - 1, n, p)
        rows.append((str(total.get("label", "")), _text(total, unit, _ease(pr)) if pr > 0 else "",
                     float(total.get("value", 0)), COLORS.get(total.get("color", ""), YELLOW), pr))
    _bar_rows(d, W, H, top, pad, rows, maxv, unit)


def _draw_waterfall(d, spec, W, H, p, unit, pad):
    top = _title(d, spec, W, pad)
    st, en = spec["start"], spec["end"]
    steps = list(spec.get("steps") or [])
    n = 2 + len(steps)
    row_h = min(110, (H - top - pad) // n)
    fsz = max(24, min(40, int(row_h * 0.40)))
    lf = _font(FONT_BOLD, fsz)
    vf = _font(FONT_BLACK, fsz + 2)
    labels = [str(st.get("label", ""))] + [f"− {s.get('label', '')}" for s in steps] + [str(en.get("label", ""))]
    label_w = min(int(W * 0.34), max(d.textbbox((0, 0), lb, font=lf)[2] for lb in labels) + 16)
    total = abs(float(st.get("value", 0))) or 1.0
    value_w = _value_w(d, vf, [total] + [abs(float(s.get("value", 0))) for s in steps] + [float(en.get("value", 0))],
                       unit, [_text(st, unit), _text(en, unit)])
    x0 = pad + label_w
    bar_w = max(60, W - pad - value_w - x0 - 16)
    bh = int(row_h * 0.50)
    y = top
    # 1行目: もとの棒
    pr = _slot(0, n, p)
    cy = y + row_h // 2
    d.text((pad, cy - fsz // 2 - 4), labels[0], font=lf, fill=WHITE, stroke_width=2, stroke_fill=(0, 0, 0))
    if pr > 0:
        wv = int(bar_w * _ease(pr))
        d.rounded_rectangle([x0, cy - bh // 2, x0 + max(wv, 6), cy + bh // 2], radius=8, fill=BLUE)
        d.text((x0 + max(wv, 6) + 14, cy - fsz // 2 - 4), _text(st, unit, _ease(pr)), font=vf, fill=YELLOW,
               stroke_width=2, stroke_fill=(0, 0, 0))
    y += row_h
    # 引く分: 残りの棒（青）の右端が赤く切れていく
    remain = total
    for k, s in enumerate(steps, 1):
        pr = _slot(k, n, p)
        cy = y + row_h // 2
        d.text((pad, cy - fsz // 2 - 4), labels[k], font=lf, fill=WHITE, stroke_width=2, stroke_fill=(0, 0, 0))
        cut = abs(float(s.get("value", 0)))
        if pr > 0:
            w_rem = int(bar_w * remain / total)
            w_cut = int(bar_w * cut / total * _ease(pr))
            d.rounded_rectangle([x0, cy - bh // 2, x0 + max(w_rem, 6), cy + bh // 2], radius=8, fill=BLUE)
            if w_cut > 0:
                d.rounded_rectangle([x0 + w_rem - w_cut, cy - bh // 2, x0 + w_rem, cy + bh // 2], radius=8, fill=RED)
            d.text((x0 + max(w_rem, 6) + 14, cy - fsz // 2 - 4), fmt_num(cut * _ease(pr), unit) if pr < 1 else fmt_num(cut, unit),
                   font=vf, fill=RED, stroke_width=2, stroke_fill=(0, 0, 0))
        remain -= cut
        y += row_h
    # 最後: 残り（黄色）
    pr = _slot(n - 1, n, p)
    cy = y + row_h // 2
    d.text((pad, cy - fsz // 2 - 4), labels[-1], font=lf, fill=WHITE, stroke_width=2, stroke_fill=(0, 0, 0))
    if pr > 0:
        wv = int(bar_w * max(remain, 0) / total * _ease(pr))
        d.rounded_rectangle([x0, cy - bh // 2, x0 + max(wv, 6), cy + bh // 2], radius=8, fill=YELLOW)
        d.text((x0 + max(wv, 6) + 14, cy - fsz // 2 - 4), _text(en, unit, _ease(pr)), font=vf, fill=YELLOW,
               stroke_width=2, stroke_fill=(0, 0, 0))


_Z = str.maketrans("０１２３４５６７８９", "0123456789")
_NUM_TOK = re.compile(r"(?:\d+億)?(?:\d+万)?\d+|(?:\d+億)(?:\d+万)?|\d+万")
_CELL_UNITS = ("円", "歳", "か月", "ヶ月", "カ月", "年", "日", "%", "％", "倍", "人", "回", "分")
#: 棒を引くのに要る「いちばん小さい値 ÷ いちばん大きい値」の上限。
#: これより揃っていると棒は全部 同じ長さに見え、**字より分かりにくい飾り**になります
#: （実物: 「80歳10か月・81歳10か月…84歳10か月」＝ 0.95）。
TABLE_BAR_SPREAD = 0.85


def cell_value(c: str) -> tuple[float, str] | None:
    """表の 1マス の (値, 単位)。**数が 1つ でなければ None**（「30年2か月」「7割」は読まない）。

    「2万100円」→ (20100, "円")・「50日分」→ (50, "日")・「1年以上」→ (1, "年")。
    """
    t = str(c).translate(_Z)
    ms = _NUM_TOK.findall(t)
    if len(ms) != 1:
        return None
    m = _NUM_TOK.search(t)
    tok = m.group()
    v = 0.0
    g = re.match(r"(\d+)億", tok)
    if g:
        v += int(g.group(1)) * 10 ** 8
        tok = tok[g.end():]
    g = re.match(r"(\d+)万", tok)
    if g:
        v += int(g.group(1)) * 10 ** 4
        tok = tok[g.end():]
    if tok:
        if not tok.isdigit():
            return None
        v += int(tok)
    rest = t[m.end():]
    u = next((x for x in _CELL_UNITS if rest.startswith(x)), "")
    return (v, u)


def table_bar_column(head: list, rows: list) -> tuple[int, list[float]] | None:
    """表の中で**棒を引いてよい列**と、その値。引けなければ None。**API 0単位**。

    オーナー 2026-09-19 12:3x `9155fe09`「**画面がある意味が文字だけになってんのどうにかしろよ**」。
    この回（14:5x・optimizer・Opus 5・ultracode）に在庫 42本 の表 173 を数えたら:

        棒が引ける         **26**（15%）—— 同じ単位の数が縦に並んでいる表
        引けない          147     —— 「出さなくていい人／いる」のような**文の表**・
                                  単位が混ざる計算の並び（「684万円／毎月3万6000円／190か月」）

    **引けない 147 は、棒では直りません**（数が無い・比べる軸が無い）。
    そちらは「その図がこのコマに要るか」＝ 台本の側です。**ここで無理に引かないこと** ——
    下の 4つ の門は、どれも「引くと嘘になる」所を外しています:

      1. 行が 2行 未満／列が 2列 未満   … 比べる相手がいない
      2. その列に**読めないマス**が 1つ でも在る … 並びが欠ける
      3. 単位が 2つ 以上、または**単位が無い** … 「1 家族／2 自分／3 退職金」の
         **番号**に棒を引いた（実測・この回に踏んで外した）
      4. いちばん小さい ÷ いちばん大きい > `TABLE_BAR_SPREAD` … 全部 同じ長さの飾り

    列は**右から**探します（行の答えは右端 ＝ `step_keys` と同じ向き）。
    """
    rows = [[str(c) for c in r] for r in (rows or [])]
    ncol = len(head) if head else (len(rows[0]) if rows else 0)
    if len(rows) < 2 or ncol < 2:
        return None
    for j in range(ncol - 1, -1, -1):
        vals = [cell_value(r[j]) if j < len(r) else None for r in rows]
        if any(v is None for v in vals):
            continue
        us = {u for _, u in vals}
        if len(us) != 1 or not next(iter(us)):
            continue
        nums = [v for v, _ in vals]
        if max(nums) <= 0 or min(nums) / max(nums) > TABLE_BAR_SPREAD:
            continue
        return j, nums
    return None


def _draw_table(d, spec, W, H, p, unit, pad):
    # 箱が低い（縦で show が 4行 のコマ ＝ 約 300px）ときは題を描かない —— 題＋見出し＋4行 を 300px に入れると
    # 字が 24px まで落ちる（実物: 09/18 ショートのコマ8・sheet）。題は show が同じ字を持っている。
    top = _title(d, spec, W, pad) if H >= 360 else pad
    head = [str(h) for h in (spec.get("head") or [])]
    rows = [[str(c) for c in r] for r in (spec.get("rows") or [])]
    ncol = len(head) if head else len(rows[0])
    n = len(rows) + (1 if head else 0)
    row_h = min(96, (H - top - pad) // max(n, 1))
    fsz = max(24, min(40, int(row_h * 0.55)))     # 表は棒より行に余白が無いので、字は行の 55%（実物で 0.42 は小さすぎた）
    widths = spec.get("widths") or [1] * ncol
    tw = sum(widths)
    col_x = [pad]
    for wgt in widths:
        col_x.append(col_x[-1] + int((W - 2 * pad) * wgt / tw))
    # 字は、いちばん狭いマスに収まる大きさ
    for r in ([head] if head else []) + rows:
        for j, c in enumerate(r):
            f = _fit(d, c, FONT_BOLD, fsz, col_x[j + 1] - col_x[j] - 20)
            fsz = min(fsz, f.size)
    f = _font(FONT_BOLD, fsz)
    y = top
    shown = int(math.floor(p * len(rows) + 1e-9)) if p < 1 else len(rows)
    # **数が縦に並ぶ列には、そのマスの中に長さを引く**（オーナー 09/19 12:3x「画面が文字だけ」）。
    # 引ける表は 173 中 26 で、残りは数の無い文の表 ＝ **棒では直りません**（`table_bar_column` の註）。
    bar = table_bar_column(head, rows)
    if head:
        d.rectangle([pad, y, W - pad, y + row_h], fill=(255, 255, 255, 40))
        for j, c in enumerate(head):
            d.text((col_x[j] + 10, y + (row_h - fsz) // 2 - 4), c, font=f, fill=GRAY)
        y += row_h
    for k, r in enumerate(rows):
        if k >= shown:
            break
        last = k == shown - 1 and k == len(rows) - 1 or (k == shown - 1 and p < 1)
        if last:
            d.rectangle([pad, y, W - pad, y + row_h], fill=(255, 225, 120, 45))
        d.line([(pad, y + row_h), (W - pad, y + row_h)], fill=(255, 255, 255, 60), width=2)
        if bar:
            j, nums = bar
            mx = max(nums)
            wv = int((col_x[j + 1] - col_x[j] - 12) * (nums[k] / mx))
            bh2 = max(10, int(row_h * 0.60))
            # **字の下**に置く（字は上から重ねる ＝ 読めることは 1ミリも落とさない）。
            d.rounded_rectangle([col_x[j] + 4, y + (row_h - bh2) // 2,
                                 col_x[j] + 4 + max(wv, 8), y + (row_h + bh2) // 2],
                                radius=6, fill=(220, 150, 40, 140) if last else (70, 130, 220, 95))
        for j, c in enumerate(r):
            d.text((col_x[j] + 10, y + (row_h - fsz) // 2 - 4), c, font=f,
                   fill=YELLOW if last else WHITE, stroke_width=2, stroke_fill=(0, 0, 0))
        y += row_h


# ---------------------------------------------------------------- 折れ線（累計の追い越し・2026-09-19 13:3x）
# オーナー `9155fe09`「ナレーションとアニメーションの表現をリンクさせたりしないとわかりやすくなんない
# でしょ？**画面がある意味が文字だけになってんのどうにかしろよ**」——
# 前半（声に合わせる）は `frames_cued` が受けました。**ここは後半です。**
#
# 実測（2026-09-19 13:2x・在庫 42本 の台本を数えた）: 図 302 のうち **`table` が 173 ＝ 57%**。
# `table` は**字を並べた絵**なので、画面は字のままです。いちばん重いのが 繰り上げ受給 の本で、
# 山場（「いつ追いつかれるか」）が **4行 の字の表**、その次のコマが **4列×5行 の字の表**でした。
# ところが、その山場で声が言っているのは
#   「先の325万4400円を1万4400円で割ると、差がゼロになる226か月」
#   「65歳から18年10か月あとは83歳10か月。**ここで合計が同じになります**」
# ＝ **2本 の累計がのびて交わる**という、字では運べない形です。
#
# **これは冒頭の覆る条件 (2) が名指しで待っていた 4つ目 の形**です
# （「例: 齢 → 額 の折れ線・『何歳で元が取れるか』」）。覆る条件 (3)（オーナーが画面の動きに
# 言葉を出したら、その言葉が正本）が、それを引きました。
#
# 形は**累計の追い越しに絞ります**（一般の折れ線にしない）:
#   series は 2本・それぞれ「`at` の齢から毎月 `per_month` ずつ」。縦は合計、横は齢。
#   交わる齢は**この機械が解きます** —— 台本は答え（`cross.at`）だけ書き、`check` が計算と照らします
#   （`waterfall` の「start − steps ＝ end」と同じ、**本物の算数の門**）。
# **一般の折れ線（好きな点の列）は、まだ作りません。**
# 覆る条件 (4): 累計の追い越しに収まらない折れ線が要る本が 2本 出たら、`points` の形を足すこと。
# 覆る条件 (5): この形を入れた本 3本 の維持率が、字の表のままの本 3本 を下回ったら、字の表へ戻すこと。


def _age_text(x: float, unit: str = "歳") -> str:
    """83.8333… → 「83歳10か月」。月は四捨五入（1か月 ＝ 0.0833年）。"""
    y = int(math.floor(x + 1e-9))
    m = int(round((x - y) * 12))
    if m >= 12:
        y, m = y + 1, 0
    return f"{y}{unit}" + (f"{m}か月" if m else "")


def _cross_x(a: dict, b: dict) -> float | None:
    """2本 の累計（`at` から毎月 `per_month`）が同じ額になる齢。平行なら None。

    ra(x − aa) ＝ rb(x − ab)  →  x ＝ (ra·aa − rb·ab) / (ra − rb)   （「毎月」の 12 は消える）
    """
    ra, rb = float(a.get("per_month", 0) or 0), float(b.get("per_month", 0) or 0)
    aa, ab = float(a.get("at", 0) or 0), float(b.get("at", 0) or 0)
    if abs(ra - rb) < 1e-9:
        return None
    return (ra * aa - rb * ab) / (ra - rb)


def _draw_lines(d, spec, W, H, p, unit, pad):
    top = _title(d, spec, W, pad) if H >= 360 else pad
    xs = spec.get("x") or {}
    xu = str(xs.get("unit", "歳"))
    ser = list(spec.get("series") or [])
    n = len(ser) + 1
    x0v, x1v = float(xs.get("from", 0)), float(xs.get("to", 1))
    if x1v <= x0v:
        x1v = x0v + 1
    fsz = max(22, min(34, int((H - top) * 0.10)))
    lf = _font(FONT_BOLD, fsz)
    cols = [COLORS.get(s.get("color", ""), (ORANGE, BLUE)[k % 2]) for k, s in enumerate(ser)]

    # 凡例（色の棒 ＋ 札）を 1行。**線の札は線の横に置きません** —— 右の端では 2本 が近く、字が重なります。
    sw = fsz - 4
    x = pad
    for k, s in enumerate(ser):
        d.rounded_rectangle([x, top + fsz // 3, x + sw, top + fsz // 3 + sw // 3], radius=3, fill=cols[k])
        lb = str(s.get("label", ""))
        d.text((x + sw + 8, top), lb, font=lf, fill=cols[k], stroke_width=2, stroke_fill=(0, 0, 0))
        x += sw + 8 + d.textbbox((0, 0), lb, font=lf)[2] + 24

    plot_top = top + int(fsz * 1.55)
    base = H - pad - int(fsz * 1.35)
    if base - plot_top < 70:                      # 箱が低いコマでは凡例の下を詰める
        plot_top = top + int(fsz * 1.15)
    px0, px1 = pad + 6, W - pad - 6
    maxv = max([float(s.get("per_month", 0) or 0) * (x1v - float(s.get("at", 0) or 0)) for s in ser] + [1.0])

    def PX(v: float) -> float:
        return px0 + (v - x0v) / (x1v - x0v) * (px1 - px0)

    def PY(v: float) -> float:
        return base - (v / maxv) * (base - plot_top)

    d.line([(px0, base), (px1, base)], fill=(255, 255, 255, 110), width=3)

    prc = _slot(len(ser), n, p)
    cx = _cross_x(ser[0], ser[1]) if len(ser) == 2 else None
    inside = cx is not None and x0v <= cx <= x1v

    def _val(sr: dict, xv: float) -> float:
        a = float(sr.get("at", 0) or 0)
        return float(sr.get("per_month", 0) or 0) * max(0.0, xv - a)

    # **2本 のあいだを塗る（線より先に）。** 線だけだと 2本 はほとんど平行に見えます ——
    # 差は合計の 2〜7% で、7px の線の太さと同じくらいしかありません（実物で見た・2026-09-19 13:3x）。
    # 塗ると「**どちらが前に出ているか**」が面になり、**交わる所で面が 0 に潰れます**。
    # 潰れる瞬間が、声の「ここで合計が同じになります」と同じ刻に来ます ＝ 字では運べない形。
    if prc > 0 and inside:
        e = _ease(prc)
        mid = (x0v + cx) / 2                      # **前に出ている側は数えます**（series の並び順に頼らない）
        left = 0 if _val(ser[0], mid) >= _val(ser[1], mid) else 1
        for lo, hi, who in ((x0v, cx, left), (cx, x1v, 1 - left)):
            xs_pts = [lo + (hi - lo) * j / 24 for j in range(25)]
            poly = ([(PX(v), PY(_val(ser[who], v))) for v in xs_pts]
                    + [(PX(v), PY(_val(ser[1 - who], v))) for v in reversed(xs_pts)])
            d.polygon(poly, fill=cols[who] + (int(135 * e),))

    for k, s in enumerate(ser):
        pr = _ease(_slot(k, n, p))
        if pr <= 0:
            continue
        a = float(s.get("at", x0v) or 0)
        r = float(s.get("per_month", 0) or 0)
        xe = a + (x1v - a) * pr
        d.line([(PX(a), PY(0)), (PX(xe), PY(r * (xe - a)))], fill=cols[k], width=7)
        d.ellipse([PX(a) - 7, PY(0) - 7, PX(a) + 7, PY(0) + 7], fill=cols[k])

    if prc > 0 and inside:
        e = _ease(prc)
        a0 = float(ser[0].get("at", 0) or 0)
        r0 = float(ser[0].get("per_month", 0) or 0)
        cyy = PY(r0 * (cx - a0))
        alpha = int(220 * e)
        yy = base                                  # 軸から交わる所まで、点線で立てる
        while yy > cyy:
            d.line([(PX(cx), yy), (PX(cx), max(cyy, yy - 11))], fill=(255, 225, 120, alpha), width=3)
            yy -= 22
        rad = int(10 + 9 * (1 - e))                # 大きい輪が縮んで点に止まる
        d.ellipse([PX(cx) - rad, cyy - rad, PX(cx) + rad, cyy + rad],
                  outline=YELLOW, width=4, fill=(255, 225, 120, int(130 * e)))
        txt = str((spec.get("cross") or {}).get("at", "") or "")
        if txt:
            vf = _font(FONT_BLACK, fsz + 4)
            right = PX(cx) > (px0 + px1) / 2
            d.text((PX(cx) + (-14 if right else 14), base + 2), txt, font=vf, fill=YELLOW,
                   anchor="ra" if right else "la", stroke_width=3, stroke_fill=(0, 0, 0))


# ---------------------------------------------------------------- 線（数直線と、超えるか）2026-09-19 15:0x
# オーナー `9155fe09`「画面がある意味が文字だけになってんのどうにかしろよ」。
#
# **この局の題の芯は「線を超えるか」です**（この回に在庫 42本 の表 173 を数えた）——
# 「所得税の線 214万円」「住民税がかかる線 所得45万円」「125万円をこえると」「20年が境目」…。
# いまはそれが**全部 文の表**で出ていました（「214万円より少ない／引かれない」のような行）。
# **数の大小の話なのに、画面には大小が 1つも描かれていません。**
#
# この形は**数直線を 1本 引き、線に印を置き、その人の位置を置きます**。
# 声が「214万円」と言った瞬間に線が引かれ、「この方は160万円」と言った瞬間に印が乗る
# （刻みは `narration.cue_windows`・`step_keys` の順は marks → value → verdict）。
#
# 覆る条件:
#  (1) 印が 4つ 以上 要る本が 2本 出たら `MAX_MARKS` を上げること。
#      **3 にしてある理由**: この局の「段」は実物が 3段 です
#      （`2026-09-20-nenkin-tedori-hayamihyou` コマ68・128 の「43万円以下 7割／74万円以下 5割／
#        100万円以下 2割／それより上 なし」）。**帯は 4本**で、色は緑→赤の間を等分します。
#  (2) 「超えたら悪い」ではない線（超えると得をする線）が出たら、`good` で色の向きを渡すこと
#      —— **いまは「線より下が緑」で固定**です（税・保険料の線はどれもその向き）。
#  (3) 線が 1つ も無く、位置だけを見せたい本が出たら、それは `bars` の 1本 です。ここへ入れないこと。

MAX_MARKS = 3


def _gauge_span(spec: dict) -> tuple[float, float]:
    """横の端。`axis.from` / `axis.to` が在ればそれ、無ければ **0 から いちばん大きい数の 1.15倍**。"""
    ax = spec.get("axis") or {}
    vals = [float(m.get("value", 0) or 0) for m in (spec.get("marks") or [])]
    v = spec.get("value") or {}
    if "value" in v:
        vals.append(float(v["value"] or 0))
    lo = float(ax["from"]) if "from" in ax else min([0.0] + vals)
    hi = float(ax["to"]) if "to" in ax else (max(vals) * 1.15 if vals else 1.0)
    return (lo, hi if hi > lo else lo + 1.0)


def _draw_gauge(d, spec, W, H, p, unit, pad):
    top = _title(d, spec, W, pad)
    marks = list(spec.get("marks") or [])[:MAX_MARKS]
    val = spec.get("value") or {}
    verdict = spec.get("verdict") or {}
    n = steps(spec)
    lo, hi = _gauge_span(spec)
    x0, x1 = pad + 24, W - pad - 24
    avail = H - top - pad
    ay = top + int(avail * 0.52)
    bh = max(18, min(34, int(avail * 0.12)))
    fsz = max(22, min(34, int(avail * 0.13)))
    lf = _font(FONT_BOLD, fsz)
    vf = _font(FONT_BLACK, fsz + 2)

    def PX(v: float) -> float:
        return x0 + (max(lo, min(hi, float(v))) - lo) / (hi - lo) * (x1 - x0)

    # 帯（線より下が緑・上が赤。印が出るまでは灰色のまま ＝ 声が線を言う前に色で答えを出さない）
    d.rounded_rectangle([x0, ay - bh // 2, x1, ay + bh // 2], radius=bh // 2, fill=(255, 255, 255, 40))
    shown_marks = [m for k, m in enumerate(marks) if _slot(k, n, p) >= 1.0]
    edges = [x0] + [PX(m.get("value", 0)) for m in shown_marks] + [x1]
    nb = len(edges) - 1
    if shown_marks:
        # 色は **緑 → 赤 の間を帯の数で等分**（印が 1つ なら 緑・赤 の 2本）。
        # 段が 3つ の本（帯 4本）でも、色の並びを手で足さずに済みます。
        for i in range(nb):
            f = 0.0 if nb <= 1 else i / (nb - 1)
            c = tuple(int(GREEN[j] + (RED[j] - GREEN[j]) * f) for j in range(3))
            d.rounded_rectangle([edges[i], ay - bh // 2, edges[i + 1], ay + bh // 2],
                                radius=bh // 2, fill=(c[0], c[1], c[2], 150))
    # 印（線）—— 札は帯の上・数は帯のすぐ上
    xs_all = [PX(m.get("value", 0)) for m in marks]
    lsz = max(20, fsz - 10)
    for k, m in enumerate(marks):
        if _slot(k, n, p) <= 0:
            continue
        x = xs_all[k]
        d.line([(x, ay - bh // 2 - 10), (x, ay + bh // 2)], fill=WHITE, width=4)
        num = str(m.get("text") or fmt_num(float(m.get("value", 0) or 0), unit))
        lb = str(m.get("label", ""))
        # 隣の印とぶつからない幅（印が 2つ のとき、札どうしが横で重なった・実物 2026-09-19 15:1x）
        left = max([xx for xx in xs_all if xx < x] + [float(x0)])
        right = min([xx for xx in xs_all if xx > x] + [float(x1)])
        room = int(max(120, 2 * min(x - left, right - x)))
        lfk = _fit(d, lb, FONT_BOLD, lsz, room, floor=18) if lb else lf
        # 札は数の**さらに上**（重ねない —— 最初の版は 18px しか離さず、実物で重なった）
        # **CJK は字の高さが size の 1.35倍 あります**（PIL の y は上端）——
        # 札の下端が数の上端より上に来るまで離す（実測 2026-09-19 15:1x: 30px では 2px 重なった）
        for txt, dy, f, col in ((lb, -bh // 2 - 18 - (fsz + 2) - int(1.5 * lfk.size), lfk, GRAY),
                                (num, -bh // 2 - 16 - fsz, vf, WHITE)):
            if not txt:
                continue
            w = d.textbbox((0, 0), txt, font=f)[2]
            d.text((min(max(x - w / 2, pad), W - pad - w), ay + dy), txt, font=f, fill=col,
                   stroke_width=2, stroke_fill=(0, 0, 0))
    # その人の位置（帯の下に△と札）
    if "value" in val and _slot(len(marks), n, p) > 0:
        pr = _ease(_slot(len(marks), n, p))
        x = PX(float(val["value"]) * pr) if lo <= 0 else PX(val["value"])
        ty = ay + bh // 2 + 6
        d.polygon([(x, ty), (x - 16, ty + 22), (x + 16, ty + 22)], fill=YELLOW)
        txt = f"{val.get('label', '')} {_text(val, unit, pr)}".strip()
        w = d.textbbox((0, 0), txt, font=vf)[2]
        d.text((min(max(x - w / 2, pad), W - pad - w), ty + 26), txt, font=vf, fill=YELLOW,
               stroke_width=3, stroke_fill=(0, 0, 0))
    # 答え
    if verdict.get("text") and _slot(n - 1, n, p) >= 1.0:
        txt = str(verdict["text"])
        f = _fit(d, txt, FONT_BLACK, fsz + 6, W - 2 * pad)
        w = d.textbbox((0, 0), txt, font=f)[2]
        d.text(((W - w) // 2, H - pad - f.size - 6), txt, font=f, fill=YELLOW,
               stroke_width=4, stroke_fill=(0, 0, 0))


_DRAW = {"bars": _draw_bars, "waterfall": _draw_waterfall, "table": _draw_table,
         "lines": _draw_lines, "gauge": _draw_gauge}


def draw(spec: dict, size: tuple[int, int], progress: float = 1.0) -> Image.Image:
    """図の 1枚（RGBA・黒い半透明の箱つき）。`progress` 0〜1 が動きの進み。"""
    W, H = size
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=24, fill=(0, 0, 0, 150))
    _DRAW[spec["kind"]](d, spec, W, H, max(0.0, min(1.0, progress)), spec.get("unit", "円"), 28)
    return im


def frames(spec: dict, seconds: float, size: tuple[int, int]) -> list[tuple[Image.Image, float]]:
    """(絵, その絵を出す秒) の列。**合計はコマの秒数と同じ**（最後の絵が残りを持つ）。"""
    a = anim_seconds(seconds)
    if a <= 0:
        return [(draw(spec, size, 1.0), seconds)]
    n = max(1, int(round(a * FPS)))
    dt = a / n
    out = [(draw(spec, size, (k + 1) / n), dt) for k in range(n)]
    hold = seconds - a
    if hold > 1e-6:
        out.append((draw(spec, size, 1.0), hold))
    else:
        im, t = out[-1]
        out[-1] = (im, t + hold)
    return out


# ---------------------------------------------------------------- 声に合わせる（2026-09-19 12:4x）
# オーナー `9155fe09`「ナレーションとアニメーションの表現をリンクさせたりしないとわかりやすくなんない
# でしょ？画面がある意味が文字だけになってんのどうにかしろよ」——
# **冒頭の覆る条件 (3)「オーナーが画面の動きに言葉を出したら、その言葉が正本」を、この言葉が引きました。**
#
# 上の `anim_seconds`（コマの頭 0.6〜1.8秒）は **「声が言い終わるより先に絵が出来ている」** 形でした。
# ここから下は、**歩ごとに、その数を声が言う瞬間へ**合わせます（刻みは `studio/narration.py`）。
# `anim_seconds` と `frames` は**残します** —— 声が無い所（`say` が空・数が 1つも出ない図）の逃げ道で、
# `frames_cued` に窓を渡さなければ今までと同じ絵が出ます（陰性対照）。


_HAS_DIGIT = re.compile(r"[0-9０-９]")


def steps(spec: dict) -> int:
    """図の**歩の数**。`_slot` / `_draw_table` が進み 0〜1 を割っている数と**同じ式**（写しを持たない）。"""
    kind = spec.get("kind")
    if kind == "bars":
        return len(spec.get("items") or []) + (1 if spec.get("total") else 0)
    if kind == "waterfall":
        return 2 + len(spec.get("steps") or [])
    if kind == "table":
        return len(spec.get("rows") or [])
    if kind == "lines":
        return len(spec.get("series") or []) + 1      # 線 1本 ずつ → 最後に交わる所
    if kind == "gauge":
        # 印（線）1つ ずつ → その人の位置 → 答え
        return (len((spec.get("marks") or [])[:MAX_MARKS])
                + (1 if "value" in (spec.get("value") or {}) else 0)
                + (1 if (spec.get("verdict") or {}).get("text") else 0))
    return 1


def _keys_of(item: dict, unit: str) -> list[str]:
    """1歩 の**声の中の手がかり**（先に当たったものを採る）。値の字 → `text` → 札の順。"""
    out = []
    if "value" in item:
        out.append(fmt_num(float(item["value"]), unit))
    if item.get("text"):
        out.append(str(item["text"]))
    if item.get("label"):
        out.append(str(item["label"]))
    return [s for s in out if s]


def step_keys(spec: dict) -> list[list[str]]:
    """歩ごとの手がかりの列（`narration.cue_windows` に渡す）。長さは `steps(spec)` と同じ。

    **声は数を言います** —— 「枠は800万円です」。図の歩が持っているのも同じ数なので、
    **数そのものが、声と絵をつなぐ鍵**です（新しい注釈を台本に足さなくて済む ＝
    公開ずみ・在庫ずみの台本が 1字も要りません）。
    """
    unit = spec.get("unit", "円")
    kind = spec.get("kind")
    if kind == "bars":
        out = [_keys_of(it, unit) for it in (spec.get("items") or [])]
        if spec.get("total"):
            out.append(_keys_of(spec["total"], unit))
        return out
    if kind == "waterfall":
        return ([_keys_of(spec["start"], unit)]
                + [_keys_of(s, unit) for s in (spec.get("steps") or [])]
                + [_keys_of(spec["end"], unit)])
    if kind == "lines":
        # **齢（札）が先**。横の軸が齢なので、声の「65歳から」が線を、「83歳10か月」が交わる所を指します。
        out = []
        for sr in (spec.get("series") or []):
            k = [str(sr.get("label", "") or ""), str(sr.get("text", "") or "")]
            if "per_month" in sr:
                k.append(fmt_num(float(sr["per_month"] or 0), unit))
            out.append([x for x in k if x])
        cr = spec.get("cross") or {}
        out.append([x for x in (str(cr.get("at", "") or ""), str(cr.get("text", "") or "")) if x])
        return out
    if kind == "gauge":
        out = [_keys_of(m, unit) for m in (spec.get("marks") or [])[:MAX_MARKS]]
        if "value" in (spec.get("value") or {}):
            out.append(_keys_of(spec["value"], unit))
        vd = spec.get("verdict") or {}
        if vd.get("text"):
            # 答えにも `value` を書けます（「住民税 0円」に value 0 ＝ 声の「0円」で当たる）
            out.append(_keys_of(vd, unit))
        return out
    if kind == "table":
        out = []
        for r in (spec.get("rows") or []):
            cells = [str(c) for c in r if str(c).strip()]
            nums = [c for c in cells if _HAS_DIGIT.search(c)]
            out.append((nums[::-1] or cells[::-1]))   # 数のあるマスを右から（行の答えは右端）
        return out
    return [[]] * steps(spec)


def frames_cued(spec: dict, seconds: float, size: tuple[int, int],
                plan: list[tuple[float, float, int, int]]) -> list[tuple[Image.Image, float]]:
    """`narration.frame_plan` の刻みで描く。(絵, その絵を出す秒) —— **合計はコマの秒数**。

    同じ進みが続く刻は **同じ絵を使い回します**（描き直さない ＝ 焼きの時間が増えない）。
    """
    cache: dict[int, Image.Image] = {}
    out = []
    for dt, pr, _a, _b in plan:
        # **切り捨て**（丸めではない）。丸めると 2/3 が 0.667 になり、**まだ動いていない歩**が
        # `_slot` で 0.001 だけ進んで見えます —— 実測 2026-09-19 13:0x: 退職金の本のコマ7 で
        # 「手取り」の棒が、声がまだ税金の話をしている間に **5万5800円** と出ていました
        # （18,611,300 × 0.003）。**歩の境目は、越えないほうへ倒すこと。**
        k = int(max(0.0, min(1.0, pr)) * 10000)
        im = cache.get(k)
        if im is None:
            im = cache[k] = draw(spec, size, k / 10000.0)
        out.append((im, dt))
    return out
