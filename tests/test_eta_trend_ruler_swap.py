"""**7日の累計を説明する％の行が、物差しの入れ替えをまたいでいないか。**

## なぜ要るか（2026-08-29・最適化の回。**実測で踏んでいました**）

`traj_trend()` の覆る条件は、自分でこう書いています ——

    **物差しが変わった回は、この差に混ざります。**
    …だから `traj_date` どうしだけを比べ、入力の内訳は「％」で並べて、
    日付の差とは別の欄に出します

**日付の側は、そのとおり守られていました。％の側は守られていませんでした。**

`scripts/eta.py` の `_per_video()` は 2026-08-28 に落ち先を替えています
（`views_per_video` ＝帯の外まで入れた平均 → `views_per_video_live` ＝帯の中だけ）。
`data/eta.jsonl` の実測::

    08/22 05:33   per_video_now 856 ＝ views_per_video 856       （`_live` の欄なし）
    08/28 17:28   per_video_now 550 ＝ views_per_video 550       （同上）
    08/28 23:57   per_video_now 665 ＝ views_per_video_live 665  （views_per_video は 553）

7日 の窓は**この入れ替えの日をまたぎます。** そして `_trend_why` は
`per_video_now` どうしを割るので、実際に出ていたのは

    **1本あたり再生 −21%（856 → 673）**

で、**左が帯の外・右が帯の中**でした。同じ物差しで並べると 856 → 553 ＝ **−35%** です。

## なぜ「小さい表示の粗」で済まないか

この行は `CLAUDE.md` が「**読むのは3行だけ**」と言っている、その3行の中に出ます。
**輪が効いているかを主実行が読む、唯一の行**です。ここが物差しをまたぐと:

  ・入れ替えは `per_video_now` を **553 → 665 に上げる**向きなので、
    比の落ち方が**実際より軽く**出ます（−35% が −21% に見える）
  ・そして落ちた理由として**分母**を名指しするので、読んだ回は
    「分母はもう天井から外した ＝ 直っている」と読み、**次の手を打ちません**

## 覆る条件

- 窓の両端がどちらも `views_per_video_live` を持つようになったら
  （＝入れ替えから `TREND_DAYS` 日 たったら）、この枝は**自分で黙ります**。
  そのとき、この検査の1つ目は「入れ替えが無ければ黙る」ほうだけが残ります
- `_per_video()` の落ち先をまた替えたら、**欄の名前をここと `_trend_why` の
  両方で替えること**（片方だけ替えると、この検査は黙って通ります）
"""
import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)


def _load():
    spec = importlib.util.spec_from_file_location("eta_swap_mod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pt(days_ago: float, traj: str, **extra):
    row = {"at": (NOW - timedelta(days=days_ago)).isoformat(), "traj_date": traj}
    row.update(extra)
    return row


def _pts(*, live_on_new_end: bool):
    """実測の両端（08/22 と 08/28 23:57）をそのまま置く。"""
    old = _pt(6.5, "2026-12-10", views_28d=33405, videos_with_views_28d=39,
              views_per_video=856, per_video_now=856.0, view_cap_per_day=10)
    new = dict(views_28d=72203, videos_with_views_28d=127,
               views_per_video=553, view_cap_per_day=10)
    if live_on_new_end:
        new["views_per_video_live"] = 665
        new["per_video_now"] = 665.0
    else:
        new["per_video_now"] = 553.0
    return [old, _pt(0.0, "2027-01-12", **new)]


def test_物差しが入れ替わった窓では比を並べない():
    eta = _load()
    tre = eta.traj_trend(_pts(live_on_new_end=True), date(2027, 1, 12), now=NOW)
    why = eta._trend_why(tre)
    assert why, "入れ替えをまたいだ窓で、何も言わずに黙っています"
    assert "物差しが入れ替わりました" in why, (
        "**両端が別の数であること**を言っていません。言わないと、"
        "読んだ回は 856 → 665 を実績の変化として読みます"
    )
    assert "views_per_video_live" in why and "views_per_video" in why, (
        "どの欄からどの欄へ替わったのかを名指ししていません。"
        "名指ししないと、次の回は自分で `data/eta.jsonl` を掘り直します"
    )
    assert "553" in why and "-35%" in why.replace("−", "-"), (
        "**同じ物差しで並べた比**（`views_per_video` 856 → 553 ＝ −35%）を"
        "出していません。**裸で『比べられません』と言って終わらないこと** ——"
        "`CLAUDE.md`「何を固定したせいでそう出たのかを同じ行に並べる」"
    )
    assert "-21%" not in why.replace("−", "-"), (
        "またいだ側の比（856 → 665 ＝ −21%）を、まだ出しています"
    )
    assert "videos_with_views_28d" in why and "超えて出したぶん" in why, (
        "**入れ替えの窓のあいだ、分母の話が落ちています。**"
        "この枝は 7日 出つづけるので、そのあいだ「落ちたのは分母」が1度も"
        "読まれません —— 物差しの註を足す代わりに理由を消すのは、差し引きで悪化です"
    )


def test_入れ替えが無ければ今までどおり分母を名指しする():
    """**この枝が、元の説明を食い潰していないこと。**

    入れ替えの日を窓が追い越したあとは、`_trend_why` は今までどおり
    「分子は増えたのに比が落ちた ＝ 落ちたのは分母」を出さなければなりません。
    """
    eta = _load()
    tre = eta.traj_trend(_pts(live_on_new_end=False), date(2027, 1, 12), now=NOW)
    why = eta._trend_why(tre)
    assert "物差しが入れ替わりました" not in why, (
        "両端が同じ物差しなのに、入れ替えを名乗っています"
    )
    assert "videos_with_views_28d" in why, "分母の名指しが消えています"


def test_両端とも新しい物差しなら黙る():
    """**自分で消えること。** 消えないと、次は「毎回この行が出る」世話が仕事になります。"""
    eta = _load()
    pts = _pts(live_on_new_end=True)
    pts[0]["views_per_video_live"] = 856      # 起点の側も入れ替え後になった
    tre = eta.traj_trend(pts, date(2027, 1, 12), now=NOW)
    why = eta._trend_why(tre)
    assert "物差しが入れ替わりました" not in why, (
        "入れ替えから `TREND_DAYS` 日 たっても名乗り続けています。"
        "**この行は自分で消えなければなりません**"
    )
