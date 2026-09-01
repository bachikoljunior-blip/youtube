"""**腕を「全部いっぺんに」天井まで引いたら、目標の何%に届くか。**（API 0単位）

    python -m src.joint_cap        # 手元の控えだけで解き直す

## なぜ要るか（2026-09-01・最適化の回に測って作った）

`scripts/eta.py` の `lever_ladder()` は、腕を **1本ずつ**しか動かしません ——

    a2 = analyse(m, points=points, scale={lever: f})     # ← 中身は1件だけ

そこから出た数が、毎周の頭3行に出ている

    **天井そのものを ×8.82 上げないと、この腕でも出ません**

です。**これは「per_video だけを動かしたとき」の数**であって、
**残りの距離ではありません。** 実測（2026-09-01・`_measure()` の本番の道）:

    腕を据え置き                      目標の **5.7%**（28,264 ／ 500,000 再生/月）
    per_video だけ天井（×2.01）       目標の **11.3%**
    rpm だけ天井（×28.05）            目標の **17.7%**
    **4本とも同時に天井**            目標の **35.5%**（56,730 ／ 159,710）

**残る隔たりは ×2.82 です。画面は ×8.82 と言っていました —— 3.1倍 大きい側。**

**上の数は、この docstring を書いた回のものです**（同じ 2026-09-01 の、もっと早い時刻）。
**同じ日のうちに 2件 直って動きました** —— `rpm` の天井が
**ショート再生/日 に連動する**ようになり（`src/rpm_mix.coupled()`）、さらに
**規則（1日1本）の天井が `plan()` の `min()` に届く**ようになったからです:

    残る隔たり   ×2.82 →（連動）×3.03 →（規則）**×7.06**
    4本とも天井  35.5% →      33.0% →       **14.2%**

**この表を引かないこと。撃って、その回の数を読むこと**（`python -m src.joint_cap`）。
数字が古びるのは、この道具が定数を持たないからではなく、**機械が動き続けるから**です。

差が出るのは、`rpm` が**分母（`need_month`）**を下げ、`per_video` が
**分子（`ceiling_day`）**を上げるからです。**掛かる向きが別なので、
片方ずつ測ると、もう片方の効き目が毎回 捨てられます。**

[!] **すぐ上の段落は、この道具を作った回の話です。同じ日の夕方に測ったら
偽になっていました。** 向きは確かに別ですが、**別の向きだからといって
掛かるとはかぎりません** —— `rpm` の腕が上げるのは帯（`band_rpm`）のほうで、
`plan()` は `rpm_plan = min(band_rpm, rpm_cap)` と切ります。`rpm_cap` は
`per_video` を引くほど下がるので（`rpm_mix.coupled()` の希釈）、
**`per_video` ×2.5 付近で `rpm` の効きは ×1.0000 になり、そこから先は
`×10^9` でも 0** です（`points` 付き ＝ 本番の道の実測。表は `solve()` の
docstring）。**この道具の「積」は、いつ積になっているかを毎回 確かめること** ——
`solve()` が1本ずつ抜いて `idle` を返し、`lines()` が名指しします。
**`idle` が空でないうちは、上の段落を引かないこと。**

## これが放っておけない理由

`×8.82` は「**測った物理の天井を、さらに 8.8倍 に**」という意味なので、
読んだ側は **手がない**と読みます（実際この repo は、その ×8.82 を
「立てるべき前提」として 2回 持ち越し、`長尺` の側を測って
**外れ**で閉じました —— `src/long_ceiling.py`）。
**×2.82 は、同じ字でも別の景色です。**

## **この道具は「届く」とは言いません**

4本とも天井でも **35.5%** ＝ **届きません。** 言えるのは
**残りがいくつか**だけです。そしてその残りは、どれか1本の天井を
壊すのではなく、**天井の積**を ×2.82 にすれば埋まります
（例: `per_video` の天井を ×2.82 —— `rpm` は既に天井まで引いた前提で）。

## 覆る条件

- **`lever_ladder()` が組み合わせを測るようになったら**、この道具は要りません
  （そのときは `arm_reaches` に joint の行が入るはずです）。
- **どれか1本の `reachable_at_cap` が真に戻ったら**、`headline()` の側の
  `lever_chosen_by == "need_over_cap"` が偽になり、この行は自分で消えます。
- `density` の天井は house rule（1日1本）で **×1.00 固定**です。
  オーナーが規則を外したら、この積はそこから動きます。

## 数え方（**定数を持ちません**）

    ratio(need_month, ceiling_month) = ceiling_month / need_month
    gap  = 1 / ratio                       ← 残りの倍率
"""
from __future__ import annotations

from collections.abc import Callable

#: 1か月の日数。`scripts/eta.py` の `ceiling_views_month` と同じ置き方。
DAYS_PER_MONTH = 30.0

#: **「抜いても変わらない」の線**（`solve()` の `idle`）。
#:
#: 1本 抜いた joint に対する比が、これを下回る腕は **joint に効いていない**
#: と読みます。0.5% は模型の丸めの幅より上、実測の差より下です ——
#: 2026-09-01 の実物は `rpm` / `sub_rate` が **ちょうど 1.0000**（`min()` で
#: ピン留めされて1点も動かない）、`per_video` が **1.585**。**間は空です。**
#:
#: **覆る条件**: 腕の効きが数%で並ぶようになったら、ここを 1.001 まで下げ、
#: `lines()` に「小さいが 0 ではない」の言い方を足すこと。
IDLE_FACTOR = 1.005


def joint_scale(rows: list[dict] | None) -> dict[str, float]:
    """`lever_ladder()` の行から、**天井まで引いた倍率の束**を作る。

    `cap` が `None` か `<= 1.0`（＝引き代なし）の腕は入れません ——
    入れても `analyse()` の答えが変わらないうえ、
    「動かした腕」として数えられてしまいます。
    """
    out: dict[str, float] = {}
    for r in rows or ():
        cap = r.get("cap")
        if isinstance(cap, (int, float)) and cap > 1.0:
            out[str(r.get("lever"))] = float(cap)
    return out


def ratio(need_month: float | None, ceiling_month: float | None) -> float | None:
    """**目標の何割に届くか。** 分母が無い／0 のときは `None`（＝言えない）。"""
    if not need_month or ceiling_month is None:
        return None
    try:
        return float(ceiling_month) / float(need_month)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def gap(need_month: float | None, ceiling_month: float | None) -> float | None:
    """**残りの倍率**（1.0 以下なら届いている）。"""
    r = ratio(need_month, ceiling_month)
    if not r:
        return None
    return 1.0 / r


def solve(rows: list[dict] | None,
          resolve: Callable[[dict[str, float]], tuple[float | None, float | None]],
          ) -> dict | None:
    """**全部の腕を天井まで引いて、解き直した1点。**

    `resolve(scale)` は `(need_month, ceiling_day)` を返すこと
    —— `scripts/eta.py` の `plan()` の欄をそのまま渡します。
    **`plan()` を直接は呼びません**（この模型の中身を知らないでいるため）。

    落ちたら `None`。**回を止めないこと。**

    ## **1本 抜いてみるところまでが、この関数です**（2026-09-01・最適化の回に足した）

    この関数は長らく「全部 引いた1点」しか返さず、`lines()` は
    その1点に **「`rpm` は分母を下げ、`per_video` は分子を上げます ——
    掛かる向きが別なので、1本ずつ測るともう片方の効き目が毎回 捨てられます」**
    という文を無条件で添えていました。**その文は、今日 測ると偽です。**

    実測（2026-09-01・`_measure()` の本番の道。数字は撃って読むこと）::

        据え置き                        目標の  5.73%
        `per_video` だけ天井（×4.16）   目標の 16.52%
        `rpm`       だけ天井（×36.72）  目標の 10.42%
        `sub_rate`  だけ天井（×6.64）   目標の  5.73%   ← 1点も動かしません
        **3本とも同時に天井**          目標の **16.52%**  ← `per_video` だけと同じ

    **積になっていません。** `rpm` の ×1.82 は `per_video` の ×2.88 の
    **内側**にあります。理由は `plan()` の1行::

        rpm_plan = min(band_rpm, rpm_cap)

    `rpm` の腕は `band_rpm`（帯 ¥400）のほうを上げますが、`rpm_cap` は
    実効RPMの物理の天井で、**`per_video` を引くほど下がります**
    （ショート再生が増えるほど長尺の割合が薄まる ＝ `rpm_mix.coupled()`）。
    倍率をふって挟むと、**乗り換え点は `per_video` ×2.5 付近**です。
    **下は `points` 付き ＝ 本番と同じ道**（`eta._points()` 448点）::

        per_video   rpm ×1     rpm ×10^9    `rpm` の効き
        ×1.00        5.65%      10.28%      **×1.8195**
        ×2.00       11.31%      13.09%        ×1.1583
        ×2.40       13.57%      13.84%        ×1.0204   ← まだ少し効く
        ×2.60       14.18%      14.18%      **×1.0000**  ← ここで死ぬ
        ×4.16       16.31%      16.31%      **×1.0000**

    **＝ `per_video` を ×2.5 あたりより上へ引いた瞬間、`rpm` の腕は
    永久に 0 になります。**

    **`points` 抜きで挟むと ×2.4 と出ます**（最初にそう書きました）。
    どちらでも結論は同じですが、**この repo の数は `points` 付きのほうを
    載せる決まり**なので、上の表は本番の道で取り直したものです
    （1回 **1.34秒**・`points` 抜きの 0.41秒 の 3.3倍）。
    `IDLE_FACTOR = 1.005` は、この表の ×1.0204 と ×1.0000 のあいだに
    落ちています —— **×2.40 では `rpm` はまだ `live` に数えられます。**
    そして `per_video` は、毎周の頭が「この回に引く腕」として名指ししている
    唯一の腕です。**通る道の上では、`rpm` の前提は燃料ではありません。**

    だから返りに `marginal`（1本 抜いたときの差）と `idle`（抜いても
    変わらない腕）を足します。**腕の数だけ `resolve()` を余分に呼びます**
    —— 実測 1回 **0.41秒**、腕3本で **+1.2秒**（`scripts/eta.py` 全体の 3% 弱）。

    **覆る条件**: `plan()` の `rpm_plan` が `min()` をやめる（＝帯が
    物理の天井を越えられるようになる）か、`rpm_mix.coupled()` が
    長尺の面もこの模型の密度で伸ばすようになったら、`idle` は空になり、
    上の文が自分で戻ります。**`idle` が空の回は、印字も元どおりです。**
    """
    scale = joint_scale(rows)
    if not scale:
        return None
    try:
        need_month, ceiling_day = resolve(scale)
    except Exception:                                          # noqa: BLE001
        return None
    if ceiling_day is None:
        return None
    ceiling_month = float(ceiling_day) * DAYS_PER_MONTH
    r = ratio(need_month, ceiling_month)
    if r is None:
        return None
    marginal: dict[str, dict] = {}
    idle: list[str] = []
    if len(scale) > 1:
        for k in scale:
            rest = {kk: vv for kk, vv in scale.items() if kk != k}
            try:
                n2, c2 = resolve(rest)
            except Exception:                                  # noqa: BLE001
                continue                                       # **回を止めないこと。**
            if c2 is None:
                continue
            r2 = ratio(n2, float(c2) * DAYS_PER_MONTH)
            if r2 is None or r2 <= 0:
                continue
            marginal[k] = {
                "ratio_without": r2,
                "delta": r - r2,
                "factor": (r / r2) if r2 else None,
            }
            if r / r2 < IDLE_FACTOR:
                idle.append(k)
    return {
        "scale": scale,
        "need_month": need_month,
        "ceiling_month": ceiling_month,
        "ratio": r,
        "gap": (1.0 / r) if r else None,
        "reaches": r >= 1.0,
        "marginal": marginal,
        # **抜いても joint が動かない腕。** 名前だけで判断しないこと ——
        #     その回の `resolve()` が出した数です。
        "idle": idle,
        # 実際に joint を動かしている腕（＝ `idle` の補集合）。
        "live": [k for k in scale if k not in idle],
    }


def lines(res: dict | None, solo_need_over_cap: float | None = None,
          bar: str = "###") -> list[str]:
    """頭3行の下に足す行。**`res` が無ければ1行も出しません。**

    `solo_need_over_cap` は、画面が既に出している「天井を ×N 上げろ」の N。
    渡されたら**その N が何倍 大きい側か**まで書きます ——
    **書かないと、2つの数が同じ画面に並んで、読む側が選べません。**

    ## **`idle` の行は、`solo_need_over_cap` に掛けないこと**（2026-09-01）

    最初の版は「積になっていません」を `solo_need_over_cap` が来た回だけ
    出していました。**あの値は来ない回があります** —— 実測 2026-09-01、
    `plan(..., points=None)` の道では `lever_need_over_cap` が `None` で、
    **`idle` が `['sub_rate','rpm']` と出ているのに1行も出ませんでした。**
    **警告のほうを、注釈の有無に括り付けないこと。**
    """
    if not res:
        return []
    g, r = res.get("gap"), res.get("ratio")
    if not g or r is None:
        return []
    names = "／".join(f"`{k}` ×{v:.2f}" for k, v in res["scale"].items())
    out = [
        f"{bar}   → **腕を1本ずつではなく、{len(res['scale'])}本とも同時に"
        f"天井まで引くと、目標の {r * 100:.1f}%** です"
        f"（{res['ceiling_month']:,.0f} ／ {res['need_month']:,.0f} 再生/月・"
        f"{names}）。**残りは ×{g:.2f}。**"
    ]
    idle = list(res.get("idle") or ())
    live = list(res.get("live") or ())
    mar = res.get("marginal") or {}
    solo = (solo_need_over_cap
            if (isinstance(solo_need_over_cap, (int, float)) and solo_need_over_cap
                and solo_need_over_cap > g * 1.05) else None)
    head = (f"{bar}     **すぐ上の ×{solo:.2f} は「その1本だけを"
            f"動かしたとき」の数で、残りの距離ではありません**"
            f"（{solo / g:.1f}倍 大きい側）。" if solo else f"{bar}     ")
    if idle:
        # **積になっていない回。** 下の「掛かる向きが別」は今日は偽なので
        #     出さないこと（`solve()` の docstring に実測と「覆る条件」）。
        movers = "／".join(f"`{k}`（抜くと ×{mar[k]['factor']:.2f}）"
                           for k in live if k in mar and mar[k].get("factor"))
        out.append(
            head
            + f"[!] **上の {len(res['scale'])}本は積になっていません** —— "
            + "／".join(f"`{k}`" for k in idle)
            + f" は**抜いても joint が1点も動きません**（×{IDLE_FACTOR:.3f} 未満）。"
            + (f" joint を動かしているのは {movers} だけです。" if movers else "")
            + f" **＝ 残りの ×{g:.2f} は、その腕**だけ**の天井を"
              "さらに、という意味です。**")
        out.append(
            f"{bar}     **抜いても動かない腕に前提を立てないこと。**"
            " 1本だけで測った天井は**買えません** ——"
            " `plan()` の `rpm_plan = min(band_rpm, rpm_cap)` が、"
            "`per_video` を引くほど下がる `rpm_cap` のほうでピン留めします"
            "（`rpm_mix.coupled()`／実測の乗り換え点は `per_video` ×2.5 付近。"
            "**そこを越えた瞬間、`rpm` の腕は永久に 0 になります**）。"
            " **通る道が `per_video` である限り、"
            + "／".join(f"`{k}`" for k in idle)
            + " の前提は燃料ではありません**"
            "（`deadline_check --fit` の『生きている腕』は"
            "**いまの `per_video` の値での**判定です。"
            "**あちらが `rpm` を生きていると言っても、この行が勝ちます**）。")
    elif solo:
        out.append(
            head
            + " `rpm` は**分母**（要る再生/月）を下げ、`per_video` は**分子**を"
            "上げます —— **掛かる向きが別なので、1本ずつ測ると"
            "もう片方の効き目が毎回 捨てられます。**"
            f" **立てるべき前提の大きさは ×{g:.2f} のほう**です"
            "（この回は腕が全部 joint に効いています ——"
            " 1本ずつ抜いて確かめた `idle` が空）。")
    return out


def main() -> int:                                             # pragma: no cover
    """手で撃つとき。**`scripts/eta.py` を読み込んで解き直します。**"""
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("_eta", root / "scripts" / "eta.py")
    if spec is None or spec.loader is None:
        print("scripts/eta.py が読めません")
        return 1
    eta = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eta)

    m = eta._measure()
    a = eta.analyse(m, None)
    sup = eta.supply_state()
    pl = eta.plan(m, a, supply=sup, sensitivity=True, points=None)
    rows = pl.get("lever_days") or []

    def _resolve(scale):
        a2 = eta.analyse(m, points=None, scale=scale)
        p2 = eta.plan(m, a2, supply=sup, sensitivity=False, points=None)
        return p2.get("need_month"), p2.get("ceiling_day")

    base_r = ratio(pl.get("need_month"), (pl.get("ceiling_day") or 0) * DAYS_PER_MONTH)
    print("=== 腕を全部いっぺんに天井まで引いたら（API 0単位）===")
    print(f"  腕を据え置き: 目標の {(base_r or 0) * 100:.1f}%")
    for r in rows:
        cap = r.get("cap")
        if not (isinstance(cap, (int, float)) and cap > 1.0):
            continue
        n, c = _resolve({r["lever"]: cap})
        rr = ratio(n, (c or 0) * DAYS_PER_MONTH)
        print(f"  {r['lever']:<10} だけ天井（×{cap:.2f}）: 目標の {(rr or 0) * 100:.1f}%")
    res = solve(rows, _resolve)
    for ln in lines(res, pl.get("lever_need_over_cap"), bar="  "):
        print(ln)
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
