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
    return {
        "scale": scale,
        "need_month": need_month,
        "ceiling_month": ceiling_month,
        "ratio": r,
        "gap": (1.0 / r) if r else None,
        "reaches": r >= 1.0,
    }


def lines(res: dict | None, solo_need_over_cap: float | None = None,
          bar: str = "###") -> list[str]:
    """頭3行の下に足す行。**`res` が無ければ1行も出しません。**

    `solo_need_over_cap` は、画面が既に出している「天井を ×N 上げろ」の N。
    渡されたら**その N が何倍 大きい側か**まで書きます ——
    **書かないと、2つの数が同じ画面に並んで、読む側が選べません。**
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
    if (isinstance(solo_need_over_cap, (int, float)) and solo_need_over_cap
            and solo_need_over_cap > g * 1.05):
        out.append(
            f"{bar}     **すぐ上の ×{solo_need_over_cap:.2f} は「その1本だけを"
            f"動かしたとき」の数で、残りの距離ではありません**"
            f"（{solo_need_over_cap / g:.1f}倍 大きい側）。"
            " `rpm` は**分母**（要る再生/月）を下げ、`per_video` は**分子**を"
            "上げます —— **掛かる向きが別なので、1本ずつ測ると"
            "もう片方の効き目が毎回 捨てられます。**"
            f" **立てるべき前提の大きさは ×{g:.2f} のほう**です。")
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
