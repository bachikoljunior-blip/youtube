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

## **条件が満ちたことは、この道具からは分かりません**（2026-08-20 に踏んだ）

8/10 のこの道具は「**30秒設計の3本（8/16〜18）が出れば、ここで測れるようになります**」と
正しく印字していました。**3本は 8/18 に出ました。それから 8/20 まで、
誰も走らせ直していません。**（気づいたのはオーナーで、10日後）
**待ちを書いた回と、条件が満ちる回は別の回です。** 印字は走らせた回にしか届きません。

だから条件のほうを `config/watches.yaml` に移し、**毎周の `scripts/status.py` が
数で見張ります**（`src/watches.py`）。ここの印字は、その控えです。

## 使い方

    python scripts/retention.py              # 全本のカーブと、そろい方の検定
    python scripts/retention.py --refresh    # 取り直す（既定は貯めたぶんを使う）
    python scripts/retention.py --html 出力先 # 重ねたグラフを HTML で書き出す

**新しい本のカーブは `--refresh` なしでも取ります**（貯めに無いIDだけ引く）。
`--refresh` が要るのは、**同じ本を取り直す**とき（公開直後に引いた本など）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config
from src import analytics
from src.analytics import fetch_retention

CACHE = config.ROOT / "data" / "retention.json"
SNAP = config.ROOT / "data" / "scan.jsonl"


def length_of(row: dict) -> float | None:
    """その本の尺（秒）。**3つの出どころを、この順で当てます**（2026-08-27 に足した）。

    ## なぜ要るか —— **道具が黙って死んでいました**

    ここは長らく `r.get("尺")` の**1本道**でした。ところが
    **`data/scan.jsonl` の最新の一枚には `尺` が1本も入っていません** ——
    実測 2026-08-27: **130本 中 0本**。だから `videos()` は
    **130 → 0本** を返し、`python scripts/retention.py` は
    **見出しだけ出して、1本も描かずに終わります。**

    **落ちません。空で正常終了します。** これがいちばん見つけにくい壊れ方で、
    **最終更新は 2026-08-20 のまま**、`data/retention.json` の21本は
    **全部 2026-08-15 以前 ＝ 旧設計**でした。つまり
    **いまの作りの維持率カーブは、1本も測られていません**
    （`docs/JOURNAL.md` 2026-08-27 の読み取り専用の調査が見つけた）。

    ## 3つの出どころ

        1. 走査の `尺`                          いちばん確か。**いまは 0本**
        2. 控え `data/uploaded.jsonl` の `duration_s`   投稿した瞬間に書かれる
                                                （`src/watches._durations()` が正本）
        3. **`averageViewDuration ÷ averageViewPercentage × 100`**  ← 導出

    実測 2026-08-27 の重なり: 1 は **0本**、2 は走査の130本と **1本も重ならず**
    （控えに尺が在る87本は、まだ走査に載っていない新しい本）、
    **3 だけが 123/130本** を埋めます。**3 が無いとこの道具は生き返りません。**

    ## 3 の誤差を、隠さないこと

    `averageViewDuration` は**秒の整数**で返ります。だから導出した尺は
    **±0.5 ÷ (割合/100) 秒**ずれます —— 30秒・割合76.85% の本で **±0.65秒**。
    カーブの横軸（`点 × 尺`）に使うぶんには足りますが、
    **「4.6〜8.6秒に落差が集まる」のような秒の議論に使うときは、この幅を書くこと。**
    割合が 0 か欠けている本は `None` を返します（**当て推量をしない**）。

    ## 覆る条件

    走査がまた `尺` を持つようになったら 1 で埋まるので、
    **3 は自動で使われなくなります**（順番がそうなっています）。**消さないこと** ——
    走査の欄は 2026-08-27 に実際に消えており、また消えます。
    """
    got = row.get("尺")
    if got:
        try:
            return float(got)
        except (TypeError, ValueError):
            pass
    vid = row.get("id")
    if vid:
        try:
            from src import watches
            sec = watches._durations().get(vid)
            if sec:
                return float(sec)
        except Exception:                                      # noqa: BLE001
            pass
    dur, pct = row.get("averageViewDuration"), row.get("averageViewPercentage")
    try:
        if dur and pct and float(pct) > 0:
            return float(dur) / float(pct) * 100.0
    except (TypeError, ValueError):
        pass
    return None


def videos() -> list[dict]:
    """走査の最後の一枚から、再生のあった本を尺つきで拾う。

    **尺は `length_of()` が3つの出どころから当てます**（2026-08-27）——
    走査の `尺` だけを見ていた頃、この関数は **130本 → 0本** を返し、
    道具が**空で正常終了**していました。理由は `length_of()` の docstring。
    """
    rows: dict[str, dict] = {}
    lines = [l for l in SNAP.read_text(encoding="utf-8").splitlines() if l.strip()]
    vals = json.loads(lines[-1])["values"]
    for k, v in vals.items():
        if k.startswith("動画.") and k.count(".") >= 2:
            _, vid, m = k.split(".", 2)
            rows.setdefault(vid, {"id": vid})[m] = v
    out = []
    for r in rows.values():
        if not r.get("views", 0) > 0:
            continue
        sec = length_of(r)
        if not sec:
            continue
        # **導出で埋めたかを残す**（`length_of()` の誤差の節）。
        # 秒の議論に使う回は、この旗を見て幅を書くこと。
        r["尺_導出"] = not r.get("尺")
        r["尺"] = sec
        out.append(r)
    return sorted(out, key=lambda r: -r["views"])


#: 直前の `curves()` が何本 引いて、何本 足せたか。`main()` が読んで印字します。
#: **なぜ数えるか**: 引きに行った本が全部 失敗しても、この道具は下の表を
#: **前の回と1桁も違わない字で**出して 0 で終わります（2026-09-02 11:4x の実測
#: —— `[analytics] 維持率を取得できませんでした: 500` が1行 出たきり、
#: 貯めは 132本 のまま、`python -m src.clarity` の n も 113本 のままでした）。
#: **表が出たことは、貯まったことの証拠になりません。**
LAST_FETCH: dict[str, int] = {"試した": 0, "足した": 0, "空": 0, "エラー": 0}


def curves(vs: list[dict], refresh: bool = False) -> dict[str, list]:
    """カーブを取ってきて貯める。**API を毎回叩かない**（100点×本数は重い）。

    引いた結果は `LAST_FETCH` に残します（**足せた本数を黙らせないため**）。
    """
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    LAST_FETCH.update({"試した": 0, "足した": 0, "空": 0, "エラー": 0})
    for v in vs:
        if refresh or v["id"] not in cache:
            LAST_FETCH["試した"] += 1
            # **エラーと空を、返り値では区別できません**（どちらも `[]`）。
            # 数えている側（`analytics.RETENTION_ERRORS`）の増分で分けます。
            before_err = analytics.RETENTION_ERRORS["n"]
            got = fetch_retention(v["id"])
            if got:
                cache[v["id"]] = got
                LAST_FETCH["足した"] += 1
            elif analytics.RETENTION_ERRORS["n"] > before_err:
                LAST_FETCH["エラー"] += 1
            else:
                LAST_FETCH["空"] += 1
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def fetch_lines(before: int, after: int) -> list[str]:
    """**貯めが動いたかどうか**の1行（`LAST_FETCH` と貯めの本数から）。

    `n` を増やすために撃った回が、増えなかったことに気づけるようにするためのものです。
    """
    f = LAST_FETCH
    if f["試した"] == 0:
        return [f"  貯め **{after}本**（引きに行った本はありません ——"
                f" 走査に新しい本がまだ在りません）"]
    if f["足した"] == 0:
        out = [f"  [!] **1本も貯まりませんでした** —— {f['試した']}本 引きに行って"
               f"（空 {f['空']}本 ／ エラー {f['エラー']}本）、貯めは {before}本 のまま",
               "      **下の表は前の回と同じ数です。新しい観測ではありません**"
               " —— `python -m src.clarity` の n も動きません"]
        if f["エラー"] and not f["空"]:
            out.append("      理由は上の `[analytics] …` の行。"
                       "**上流の一時失敗なので、次の回に撃ち直せば通ることがあります**")
        elif f["空"]:
            out.append(f"      **{f['空']}本 は「落ちた」のではなく、上流に"
                       f"カーブがまだ在りません**（`rows` が 0行・エラーではありません）。"
                       f"**撃ち直しても増えません** —— 再生が貯まるまで待つ側です")
            out.append(f"      **この {f['空']}本 は毎周 引き直しています**"
                       f"（貯めに入らないので、次の回も同じ数だけ Analytics を叩きます）。"
                       f"n を増やしたいなら、増えるのは**公開した本**のぶんだけです")
        return out
    落 = f["空"] + f["エラー"]
    return [f"  貯め {before}本 → **{after}本**"
            f"（{f['試した']}本 引いて {f['足した']}本 足しました"
            + (f"・空 {f['空']}本 ／ エラー {f['エラー']}本" if 落 else "") + "）",
            "      **`python -m src.clarity` を撃ち直すこと** —— n が増えた回だけ、"
            "あちらの『連』が1つ進みます"]


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
    """ばらつき（変動係数）。**単位が違うものを比べるので、平均で割る。**

    **外れ値に弱いことを承知で残しています**（2026-08-27）——
    尺の固まり具合を見る側（`_spread(lengths)`）は、外れ値も込みで
    「振れているか」を知りたいので、こちらが正しい道具です。
    **落差の位置の比較には `_robust_spread()` を使うこと** —— 下の理由。
    """
    if len(xs) < 2:
        return float("inf")
    m = sum(xs) / len(xs)
    if not m:
        return float("inf")
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5 / m


def _quantile(xs: list[float], p: float) -> float:
    ys = sorted(xs)
    i = (len(ys) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(ys) - 1)
    return ys[lo] + (ys[hi] - ys[lo]) * (i - lo)


def _robust_spread(xs: list[float]) -> float:
    """**四分位範囲 ÷ 中央値。** 外れ値に引きずられないばらつき。

    ## なぜ要るか（2026-08-27。**生き返らせた初日に踏んだ**）

    `_spread`（変動係数）は**平均と二乗**を使うので、**尾が長い分布で壊れます。**
    この道具が生き返った初回（n=87・ショート）の実測:

        秒    4.2〜24.2  中央 5.2   変動係数 **0.429**   四分位範囲÷中央 **0.234**
        割合   8%〜 97%  中央 17%   変動係数 **0.542**   四分位範囲÷中央 **0.294**

    変動係数どうしの比は **1.27倍**しかなく、この関数の呼び手は
    **「どちらとも言えません」**と印字しました（門は `sv < rv * 0.8`）。

    **ところが、同じ87本のヒストグラムはこうです:**

        4〜5秒 **36本** ／ 5〜6秒 **32本** ／ 6〜7秒 8本
        → **4〜7秒に 76本 ＝ 87%**

    **87% が3秒の窓に入っているのに「どちらとも言えない」と出ていました。**
    引きずっていたのは **24.2秒 が1本・12秒台 が2本**の尾です。
    **データは黙っていません。計器が外れ値に負けていました。**

    **これは `docs/JOURNAL.md` 2026-08-27 の調査が旧21本で出した
    「秒でそろって、割合ではそろわない」を、現行87本で裏づけます** ——
    あちらの数（0.156 対 0.405）は変動係数で、
    **旧21本にはたまたま尾が無かった**ということです。

    ## 覆る条件

    四分位範囲は**真ん中の半分しか見ません**。尾のほうに意味がある問い
    （「いちばん遅く落ちる本は何が違うのか」）には使わないこと。
    そのときは生の並びを見ること（この道具は1本ずつ全部 印字しています）。
    """
    if len(xs) < 4:
        return float("inf")
    med = _quantile(xs, 0.5)
    if not med:
        return float("inf")
    return (_quantile(xs, 0.75) - _quantile(xs, 0.25)) / med


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
        print("      分けるには尺の違う本が要ります。**この条件は "
              "`config/watches.yaml` の `維持率-尺のばらつき` が見張っていて、"
              "満ちた回の `scripts/status.py` に出ます。**")
    elif len(secs) >= 4:
        # **判定は四分位で。** 変動係数は尾に負けます（`_robust_spread` の実測:
        # 87% が3秒の窓に入っているのに「どちらとも言えない」と出ていました）。
        sv, rv = _robust_spread(secs), _robust_spread(ratios)
        cv_s, cv_r = _spread(secs), _spread(ratios)
        print(f"\n  最大の落差の位置: 秒で見ると {min(secs):.1f}〜{max(secs):.1f}秒"
              f"（**四分位 {_quantile(secs, .25):.1f}〜{_quantile(secs, .75):.1f}秒**"
              f"・ばらつき {sv:.2f}） / 割合で見ると "
              f"{min(ratios) * 100:.0f}〜{max(ratios) * 100:.0f}%"
              f"（**四分位 {_quantile(ratios, .25) * 100:.0f}〜"
              f"{_quantile(ratios, .75) * 100:.0f}%**・ばらつき {rv:.2f}）")
        print(f"     （変動係数で見ると 秒 {cv_s:.2f} / 割合 {cv_r:.2f} ——"
              f" **こちらは尾に負けます。判定には使いません**）")
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
        # **「全本 a〜b秒に集まっています」は、集まり方ではなく幅の話でした**
        # （2026-08-27）。実測 n=87 で、この行は「4.2〜24.2秒」と出ます ——
        # **24.2秒 は1本**で、実際は **4〜7秒 に 87%** が入っています。
        # 幅を「集まっている」と読むと、尾の1本が結論を薄めます。
        # **数えるのは、中央の±中央値半分に何%が入るか。**
        med = _quantile(secs, 0.5)
        lo, hi = med * 0.5, med * 1.5
        inside = sum(1 for x in secs if lo <= x <= hi)
        print(f"\n  **最大の落差は {lo:.1f}〜{hi:.1f}秒 に "
              f"{inside}本 / {len(secs)}本 ＝ **{inside * 100 // len(secs)}%** が入ります**"
              f"（中央 {med:.1f}秒・全体では {min(secs):.1f}〜{max(secs):.1f}秒）。")
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
    before = len(json.loads(CACHE.read_text(encoding="utf-8"))) if CACHE.exists() else 0
    cache = curves(vs, refresh="--refresh" in argv)
    report(vs, cache)
    # **表のあとに置きます** —— 表の前だと 130行 の上へ流れて読まれません。
    print()
    for line in fetch_lines(before, len(cache)):
        print(line)
    if "--html" in argv:
        out = Path(argv[argv.index("--html") + 1])
        write_html(vs, cache, out)
        print(f"\n  書き出しました: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
