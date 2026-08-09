"""**維持率カーブを、100点ぜんぶ見る。**

## なぜ要るか

`src/analytics.py` の `fetch_retention` は 2026-08-09 から
**1本につき100点**返していた。`status.py` はそのうち **3点（5%・25%・50%）**
しか出していない。**97%を捨てていた。**

この回（8/10）で3回続けて同じ形の穴が出ている。

    次元を8個ぶん引いていない            → 走査で塞いだ
    動画べつを引いたのに読んでいない      → 横並びで塞いだ
    **カーブを100点引いて3点しか出していない**  ← ここ

**引く量ではなく、出す量が足りていない。**

## 何が分かるか

**落ちる位置が「秒」でそろうのか「割合」でそろうのか。** ここが分かれ目。

- **秒でそろう** → 尺を縮めても落ちる時刻は同じ。**縮めても効かない**
- **割合でそろう** → 落ちるのは尺に比例。**縮めれば落ちる前に終われる**

8/19 の仮説（30秒に縮めると engaged が上がる）は後者を仮定している。
**この100点は、公開を待たずにその仮定を測れる。**

## 使い方

    python scripts/retention.py              # 全本のカーブと、そろい方の検定
    python scripts/retention.py --html 出力先 # 重ねたグラフを HTML で書き出す
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src.analytics import fetch_retention

CACHE = config.ROOT / "data" / "retention.json"
SNAP = config.ROOT / "data" / "scan.jsonl"


def videos() -> list[dict]:
    """走査の最後の一枚から、再生のあった本を尺つきで拾う。"""
    rows: dict[str, dict] = {}
    lines = [l for l in SNAP.read_text(encoding="utf-8").splitlines() if l.strip()]
    vals = json.loads(lines[-1])["values"]
    for k, v in vals.items():
        if k.startswith("動画.") and k.count(".") >= 2:
            _, vid, m = k.split(".", 2)
            rows.setdefault(vid, {"id": vid})[m] = v
    out = [r for r in rows.values() if r.get("views", 0) > 0 and r.get("尺")]
    return sorted(out, key=lambda r: -r["views"])


def curves(vs: list[dict], refresh: bool = False) -> dict[str, list]:
    """カーブを取ってきて貯める。**API を毎回叩かない**（100点×本数は重い）。"""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    for v in vs:
        if refresh or v["id"] not in cache:
            got = fetch_retention(v["id"])
            if got:
                cache[v["id"]] = got
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


BLOCKS = " ▁▂▃▄▅▆▇█"


def spark(ys: list[float], lo: float, hi: float) -> str:
    span = (hi - lo) or 1.0
    return "".join(BLOCKS[max(0, min(8, int((y - lo) / span * 8)))] for y in ys)


def biggest_drop(curve: list, length: int) -> tuple[float, float, float]:
    """**いちばん落ちた1区間**を返す。`(秒, 割合, 落ちた量)`。

    先頭の1点目（0→1%）は「再生が始まった」ぶんなので除く。
    """
    best = (0.0, 0.0, 0.0)
    for i in range(1, len(curve)):
        d = curve[i - 1][1] - curve[i][1]
        if d > best[2]:
            best = (curve[i][0] * length, curve[i][0], d)
    return best


def half_point(curve: list, length: int) -> tuple[float, float] | None:
    """**半分が居なくなる位置。** 落差より、こちらのほうが尺の話に効く。"""
    start = curve[0][1] if curve else 0
    if not start:
        return None
    for pos, watch, _ in curve:
        if watch <= start / 2:
            return pos * length, pos
    return None


def _spread(xs: list[float]) -> float:
    """ばらつき（変動係数）。**単位が違うものを比べるので、平均で割る。**"""
    if len(xs) < 2:
        return float("inf")
    m = sum(xs) / len(xs)
    if not m:
        return float("inf")
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5 / m


def report(vs: list[dict], cache: dict) -> None:
    print("\n=== 維持率カーブ（100点ぜんぶ / 縦は audienceWatchRatio）===")
    print("  1.0 を超えるのは巻き戻し。**0.5 を切った先は半分が居ない**\n")

    secs, ratios = [], []
    for v in vs:
        c = cache.get(v["id"])
        if not c:
            continue
        ys = [row[1] for row in c]
        length = v["尺"]
        drop_s, drop_r, amount = biggest_drop(c, length)
        half = half_point(c, length)
        secs.append(drop_s)
        ratios.append(drop_r)
        title = str(v.get("題", v["id"]))[:22]
        print(f"  {title:24} {v['views']:>5}再生 {length:>3}s")
        print(f"    {spark(ys, 0, max(ys))}")
        print(f"    最大の落差 **{drop_s:.1f}秒**（{drop_r * 100:.0f}%地点 / "
              f"{amount:.2f} 落ちる）" +
              (f" │ 半減 **{half[0]:.1f}秒**（{half[1] * 100:.0f}%地点）"
               if half else " │ 半減しない"))

    # **ここが本題。落ちる位置は秒でそろうのか、割合でそろうのか。**
    #
    # ただし**尺がそろっていると、この検定は原理的に効かない。**
    # 秒 = 割合 × 尺 なので、尺が一定なら2つの軸は定数倍でしかなく、
    # ばらつきも同じ値になる。**「どちらとも言えない」と出たとき、
    # データが黙っているのか、検定が効いていないのかは別物。**
    # 8/10 に一度、47〜56秒の6本で「どちらとも言えません」と出した。
    # あれはデータの結論ではなく、**尺を振っていないだけ**だった。
    lengths = [v["尺"] for v in vs if cache.get(v["id"])]
    if len(secs) >= 4 and _spread(lengths) < 0.15:
        print(f"\n  [!] **この検定は今回効きません。**尺が "
              f"{min(lengths)}〜{max(lengths)}秒に固まっていて"
              f"（ばらつき {_spread(lengths):.2f}）、"
              "**秒の軸と割合の軸がほぼ同じもの**になっています。")
        print("      分けるには尺の違う本が要ります。"
              "**30秒設計の3本（8/16〜18）が出れば、ここで測れるようになります。**")
    elif len(secs) >= 4:
        sv, rv = _spread(secs), _spread(ratios)
        print(f"\n  最大の落差の位置: 秒で見ると {min(secs):.1f}〜{max(secs):.1f}秒"
              f"（ばらつき {sv:.2f}） / 割合で見ると "
              f"{min(ratios) * 100:.0f}〜{max(ratios) * 100:.0f}%"
              f"（ばらつき {rv:.2f}）")
        if sv < rv * 0.8:
            print("  → **秒のほうがそろっています。落ちる時刻は尺に依存しない。**")
            print("     **尺を縮めても、落ちる時刻は動きません**"
                  "（8/19 の仮説はこの向きに不利）")
        elif rv < sv * 0.8:
            print("  → **割合のほうがそろっています。落ちる位置は尺に比例する。**")
            print("     **縮めれば落ちる前に終われます**（8/19 の仮説に有利）")
        else:
            print("  → **どちらとも言えません**（ばらつきが近い）。"
                  "本数が増えるまで、尺の議論はこの数字で決めないこと")
        print(f"  n={len(secs)}。**1本入れ替わると向きが変わりうる段階です**")

    # **尺を振らなくても言えること。** 落差の位置そのもの。
    if secs:
        print(f"\n  **最大の落差は全本 {min(secs):.1f}〜{max(secs):.1f}秒に集まっています。**")
        print("  旧設計の1枚目は 7.9〜13.8秒あったので、"
              "**落ちている時点でまだ画面が変わっていません。**")
        print("  つまり視聴者は「次の画面」を見る前に抜けている"
              "（8/26 の仮説の根拠はここ。相関ではなく時刻を見た結論）")
    if len(secs) >= 4:
        halves = [half_point(cache[v["id"]], v["尺"])[0] for v in vs
                  if cache.get(v["id"]) and half_point(cache[v["id"]], v["尺"])]
        if len(halves) >= 4:
            print(f"  一方**半減の位置は {min(halves):.1f}〜{max(halves):.1f}秒"
                  f"とばらばら**（落差の位置の3倍以上の幅）。")
            print("  **冒頭は全本同じように落ち、その後の残り方だけが本ごとに違う。**")


HTML = """<title>維持率カーブ</title>
<style>
:root{--bg:#fff;--fg:#111;--grid:#e3e3e3;--muted:#666}
:root:not([data-theme=light]){@media (prefers-color-scheme:dark){
  --bg:#111;--fg:#eee;--grid:#333;--muted:#999}}
:root[data-theme=dark]{--bg:#111;--fg:#eee;--grid:#333;--muted:#999}
body{background:var(--bg);color:var(--fg);font:15px/1.7 system-ui,sans-serif;
  margin:0 auto;padding:24px;max-width:900px}
h1{font-size:20px} h2{font-size:16px;margin-top:32px}
.wrap{overflow-x:auto} svg{max-width:100%%;height:auto;display:block}
table{border-collapse:collapse;font-size:13px;width:100%%}
td,th{padding:4px 8px;border-bottom:1px solid var(--grid);text-align:right}
th:first-child,td:first-child{text-align:left}
p{color:var(--muted);font-size:13px}
</style>
<h1>維持率カーブ（%(n)d本 / 各100点）</h1>
<p>縦軸 audienceWatchRatio。1.0 を超えるのは巻き戻し。
点線は 0.5（半分が居なくなる高さ）。</p>
<h2>横軸＝秒（落ちる<b>時刻</b>がそろうか）</h2>
<div class="wrap">%(by_sec)s</div>
<h2>横軸＝再生位置の割合（落ちる<b>割合</b>がそろうか）</h2>
<div class="wrap">%(by_ratio)s</div>
<h2>本</h2>
<table><tr><th>題</th><th>再生</th><th>尺</th><th>engaged</th>
<th>最大の落差</th><th>半減</th></tr>%(rows)s</table>
"""

PALETTE = ["#4269d0", "#efb118", "#ff725c", "#6cc5b0", "#3ca951",
           "#ff8ab7", "#a463f2", "#97bbf5"]


def svg(series: list[tuple[str, list[tuple[float, float]]]], xmax: float,
        xlabel: str) -> str:
    W, H, L, B = 860, 300, 44, 34
    top, right = 12, 12
    px = lambda x: L + (x / xmax) * (W - L - right)
    ymax = max((y for _, pts in series for _, y in pts), default=1.2)
    py = lambda y: top + (1 - y / ymax) * (H - top - B)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img">']
    for f in (0, 0.25, 0.5, 0.75, 1.0):
        y = ymax * f
        out.append(f'<line x1="{L}" y1="{py(y):.1f}" x2="{W - right}" '
                   f'y2="{py(y):.1f}" stroke="var(--grid)"/>')
        out.append(f'<text x="{L - 6}" y="{py(y) + 4:.1f}" text-anchor="end" '
                   f'font-size="11" fill="var(--muted)">{y:.1f}</text>')
    out.append(f'<line x1="{L}" y1="{py(0.5):.1f}" x2="{W - right}" '
               f'y2="{py(0.5):.1f}" stroke="var(--muted)" '
               f'stroke-dasharray="4 4"/>')
    for i in range(5):
        x = xmax * i / 4
        out.append(f'<text x="{px(x):.1f}" y="{H - 12}" text-anchor="middle" '
                   f'font-size="11" fill="var(--muted)">{x:.0f}</text>')
    out.append(f'<text x="{W - right}" y="{H - 12}" text-anchor="end" '
               f'font-size="11" fill="var(--muted)">{xlabel}</text>')
    for i, (name, pts) in enumerate(series):
        d = " ".join(f"{'M' if j == 0 else 'L'}{px(x):.1f},{py(y):.1f}"
                     for j, (x, y) in enumerate(pts))
        out.append(f'<path d="{d}" fill="none" stroke="{PALETTE[i % 8]}" '
                   f'stroke-width="2"/>')
    # 凡例
    for i, (name, _) in enumerate(series):
        cy = top + 14 + i * 16
        out.append(f'<rect x="{W - right - 210}" y="{cy - 8}" width="10" '
                   f'height="10" fill="{PALETTE[i % 8]}"/>')
        out.append(f'<text x="{W - right - 194}" y="{cy + 1}" font-size="11" '
                   f'fill="var(--fg)">{name}</text>')
    out.append("</svg>")
    return "".join(out)


def write_html(vs: list[dict], cache: dict, path: Path) -> None:
    import html as _h

    by_sec, by_ratio, rows = [], [], []
    for v in vs:
        c = cache.get(v["id"])
        if not c:
            continue
        name = _h.escape(str(v.get("題", v["id"]))[:18])
        by_sec.append((name, [(p * v["尺"], w) for p, w, _ in c]))
        by_ratio.append((name, [(p * 100, w) for p, w, _ in c]))
        ds, dr, amt = biggest_drop(c, v["尺"])
        hp = half_point(c, v["尺"])
        eng = v.get("engagedViews")
        rows.append(
            f"<tr><td>{name}</td><td>{v['views']}</td><td>{v['尺']}s</td>"
            f"<td>{eng / v['views'] * 100:.1f}%</td>" if eng else
            f"<tr><td>{name}</td><td>{v['views']}</td><td>{v['尺']}s</td><td>-</td>")
        rows[-1] += (f"<td>{ds:.1f}s</td>"
                     f"<td>{hp[0]:.1f}s</td></tr>" if hp
                     else f"<td>{ds:.1f}s</td><td>—</td></tr>")
    xs = max((x for _, pts in by_sec for x, _ in pts), default=60)
    path.write_text(HTML % {
        "n": len(by_sec),
        "by_sec": svg(by_sec, xs, "秒"),
        "by_ratio": svg(by_ratio, 100, "%"),
        "rows": "".join(rows),
    }, encoding="utf-8")


def main(argv: list[str]) -> int:
    vs = videos()
    cache = curves(vs, refresh="--refresh" in argv)
    report(vs, cache)
    if "--html" in argv:
        out = Path(argv[argv.index("--html") + 1])
        write_html(vs, cache, out)
        print(f"\n  書き出しました: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
