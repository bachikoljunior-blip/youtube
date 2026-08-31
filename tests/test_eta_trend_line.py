"""**到達日の向きは、1歩ぶんの差では出ない。** 累計を、読まれる3行に出すこと。

## なぜ要るか（2026-08-29 の実測。最適化の回）

`headline()` は 08-20 以来「**前の回の予測 → ±N日**」だけを出していました。
**1歩ぶん**です。実測 2026-08-28 の回は **+3日** —— 読んだ回は誤差として通します。

**同じ台帳（`data/eta.jsonl`）を 7日 ぶん足すと、こうでした**::

    08/21 の中央値   2026-12-10（残り 111日）
    08/28 の点       2027-01-12（残り 136日）
    → **+33日 遠のいた**（残りの距離は **+25日**）

そのあいだに **147周・342 ship**（`scripts/drift.py` の同じ窓）。
日ごとの差は **−9 〜 +15日** で振れるので、**1歩ずつ見ても向きは1度も出ません。**

## そして「遠のいた」を裸で出さない

`CLAUDE.md`「**裸の『届きません』を出さないこと**」。同じ行に理由を並べます。
この台帳で実際に効いていたのは**天井の分母**でした::

    月の再生 `views_28d`              28,339 → 69,386  **+145%**
    分母 `videos_with_views_28d`          30 → 126     **+320%**
                                                     （**上限を超えて出したぶんが 0再生 のまま入る**。
                                                       齢ではありません —— 2026-08-29 に測り直した）
    比  `per_video_now`                  944 → 550     **−42%**

**再生は2.4倍 になったのに、比は 42% 落ちています。** 分母が齢で揃っておらず、
昨日 公開した本も 28日 回った本と同じ「1本」として入るからです。
`ceiling_views_month` ＝ その比 × `view_cap_per_day`(10) × 30 なので、
**出すほど天井が下がり、`lever_hint` は `per_video` を指し続けます** ——
主実行が毎周やっていること（出す）が、その回の採点を下げる形です
（`src/arm_speed.forward()` の符号が逆だったのと同じ形）。

## 覆る条件

- `per_video_now` が**齢を揃えた**推定になったら、`_trend_why` の分母の行は
  意味を失います。**そのときこの検査の「分母を名指しする」を、新しい入力の
  名前へ書き換えること**（消すのではなく、書き換える）
- `ceiling_views_month` が `per_video_now` を掛けなくなったら、
  `_trend_why` が名指ししている経路そのものが消えます
"""
import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("eta_trend_mod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NOW = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)


def _pt(days_ago: float, traj: str, **extra):
    row = {"at": (NOW - timedelta(days=days_ago)).isoformat(), "traj_date": traj}
    row.update(extra)
    return row


def _plan(lever="per_video"):
    return {
        "target_date": None,
        "days_to_target": 136.0,
        "binding": "再生数が天井に当たっている",
        "lever_hint": lever,
        "lever_from": "軌跡",
        "lever_hint_binding": lever,
        "lever_days": [],
    }


def _traj(when=date(2027, 1, 12)):
    return {
        "base": {"date": when, "days": 136.0, "t_work": 50, "plan_days": 86.0,
                 "blocking": []},
        "choice": [{"lever": "per_video", "reachable": True, "days": 136.0,
                    "date": when, "t_work": 50}],
        "arms": {"per_video": {"lever": "per_video", "throughput": 0.9,
                               "p": 0.2, "n": 3, "hits": 1, "source": "自前"}},
    }


# --------------------------------------------------------------- traj_trend

def test_点が足りなければ名乗らない():
    eta = _load()
    assert eta.traj_trend([], date(2027, 1, 12), now=NOW) is None
    assert eta.traj_trend([_pt(3, "2026-12-10")], date(2027, 1, 12), now=NOW) is None


def test_窓が1日に満たないなら名乗らない():
    """**1日 未満の窓から「7日の累計」と名乗らないこと。**

    `_project_nth` は 08/27 に、まさに同じ穴で偽の伸び率を出しています
    （窓 0日 から「1日 5本 作れる」）。**同じ穴を、同じファイルの別の関数で
    もう一度 開けないため**の検査です。
    """
    eta = _load()
    pts = [_pt(0.4, "2026-12-10"), _pt(0.1, "2027-01-12")]
    assert eta.traj_trend(pts, date(2027, 1, 12), now=NOW) is None


def test_起点は最古の1点ではなくその日の中央値():
    """**同じ日の中の振れを、そのまま起点にしないこと**（実測 08/21 は幅 18日）。

    08/21 の点は 2026-12-02〜2026-12-28 に散っており、**端を掴むと累計が
    18日 ずれます**。中央値なら、掴む点が1つ ずれても累計は動きません。
    """
    eta = _load()
    pts = [
        _pt(6.9, "2026-12-28"),   # ← その日のいちばん古い点（端）
        _pt(6.8, "2026-12-10"),   # ← 中央値
        _pt(6.7, "2026-12-02"),
        _pt(0.0, "2027-01-12"),
    ]
    tre = eta.traj_trend(pts, date(2027, 1, 12), now=NOW)
    assert tre is not None
    assert tre["from_date"] == date(2026, 12, 10), (
        "起点にその日の中央値を使っていません。"
        "1点だと、同じ日の 18日 の振れがそのまま累計に乗ります"
    )
    assert tre["delta"] == 33
    assert tre["base_spread"] == 26, "同じ日の幅を出していません（読む側が精度を測れません）"


def test_窓の外の点を起点にしない():
    eta = _load()
    pts = [_pt(30, "2026-06-01"), _pt(6.0, "2026-12-10"), _pt(0.0, "2027-01-12")]
    tre = eta.traj_trend(pts, date(2027, 1, 12), now=NOW)
    assert tre is not None and tre["from_date"] == date(2026, 12, 10), (
        "7日 の窓の外の点を起点にしています（`days` が効いていません）"
    )


# --------------------------------------------------------------- _trend_why

def _why_pts(views_a, n_a, views_b, n_b):
    return [
        _pt(6.5, "2026-12-10", views_28d=views_a, videos_with_views_28d=n_a,
            per_video_now=views_a / n_a, view_cap_per_day=10),
        _pt(0.0, "2027-01-12", views_28d=views_b, videos_with_views_28d=n_b,
            per_video_now=views_b / n_b, view_cap_per_day=10),
    ]


def test_分子が増えて比が落ちた回は分母を名指しする():
    """**「遠のきました」を裸で出さない**（`CLAUDE.md`）。"""
    eta = _load()
    tre = eta.traj_trend(_why_pts(28339, 30, 69386, 126), date(2027, 1, 12), now=NOW)
    why = eta._trend_why(tre)
    assert why, "内訳が出ていません（向きだけを出すのは裸の『届きません』と同じ形）"
    assert "videos_with_views_28d" in why, (
        "落ちたのが**分母**であることを名指ししていません。"
        "名指ししないと、読んだ回は『1本あたり再生が落ちた＝中身が悪い』と読み、"
        "`per_video` を追いに行きます"
    )
    # **2026-08-29 に書き換えた**（この検査の書き換えは、`_trend_why` の
    # 「覆る条件」が名指しで許しています ——「`per_video_now` が別の入力に
    # なったら、この検査を新しい入力の名前へ書き換えること」）。
    # 前は「齢で揃っていません」を要求していましたが、**実測でそれは原因では
    # ありませんでした**（ショートは齢24h で伸びきる: 1,018回 → 1,015回）。
    assert "超えて出したぶん" in why, (
        "分母が膨らむ本当の理由（**上限を超えて出したぶんが 0再生 のまま分母に入る**）を"
        "言っていません。齢のせいにすると、読んだ回は「もっと待てば戻る」と読みます"
    )
    assert "live_band_views" in why, (
        "**天井の分母からは外してある**ことを言っていません。"
        "言わないと、読んだ回は「天井もこの比で出来ている」と読み、"
        "**もう直っているものを二度 直します**"
    )


def test_分子も比も落ちた回は名指ししない():
    """**本当に世界が悪くなった回まで「分母のせい」と言わないこと。**"""
    eta = _load()
    tre = eta.traj_trend(_why_pts(69386, 126, 30000, 126), date(2027, 1, 12), now=NOW)
    assert eta._trend_why(tre) == "", (
        "再生そのものが減った回にまで分母を名指ししています。"
        "これは『どんな回でも道具のせいにする』言い訳になります"
    )


# ---------------------------------------------------------------- headline

def test_累計の行が読まれる3行に出る():
    eta = _load()
    pts = _why_pts(28339, 30, 69386, 126)
    prev = pts[-1]
    # **`now=` を渡すこと。** 渡さないと `headline()` の中の `traj_trend()` が
    # 実時刻を読み、点は `NOW`（08/28）基準なので、**壁時計が1日 進んだだけで
    # この検査は黙って赤くなります**（2026-08-29 に実際に踏んだ）。
    lines = eta.headline(_plan(), prev, _traj(), pts, now=NOW)
    hit = [ln for ln in lines if "の累計" in ln]
    assert hit, (
        "累計の行が頭（＝尾）に出ていません。**`CLAUDE.md` は「読むのは3行だけ」**"
        "と言っており、ここに出さないと誰も 7日 ぶんを足しません"
    )
    assert "1周ごとの ±N日 では、この向きは見えません" in hit[0]


def test_headlineは時刻を渡せる():
    """**`now` を通せること。** 通せないと、この検査群は壁時計で赤くなります。

    実測 2026-08-29: `headline()` が `traj_trend()` に `now` を渡していなかった
    ため、08/28 に書かれた上の検査が翌日に落ち、**恒久的に赤い検査**の山に
    積まれていました（中身は1つも壊れていない）。
    """
    eta = _load()
    pts = _why_pts(28339, 30, 69386, 126)
    # 窓（7日）の外へ時計を進めたら、累計の行は**出ない**こと ＝ 実際に効いている
    far = NOW + timedelta(days=30)
    assert not [ln for ln in eta.headline(_plan(), pts[-1], _traj(), pts, now=far)
                if "の累計" in ln], "`now` が `traj_trend` まで届いていません"


def test_前の回と比べておきながら比べる点が無いと言わない():
    """**同じ枠の2行が食い違っていないか**（`docs/JOURNAL.md` 2026-08-28）。

    実測 2026-08-28 の回は、頭と尾の両方でこう出していました::

        ### 前の回の予測 2027-01-09 → **+3日** **遠のきました**（軌跡どうし）
        ### （比べられる前の点がまだありません）

    原因は `if/elif/else` の取り違えです —— 上の `if` が訊いているのは
    「**密度の入力が入れ替わった回か**」で、**前の点の有無とは別の問い**でした。
    """
    eta = _load()
    pts = _why_pts(28339, 30, 69386, 126)
    lines = eta.headline(_plan(), pts[-1], _traj(), pts, now=NOW)   # 壁時計に依存させない
    compared = [ln for ln in lines if "前の回の予測" in ln]
    none_yet = [ln for ln in lines if "比べられる前の点がまだありません" in ln]
    assert compared, "前の回との差が出ていません"
    assert not none_yet, (
        "「前の回の予測 → ±N日」と「比べられる前の点がまだありません」が"
        "同じ枠に並んでいます。**読んだ回は、下の行を信じて上の差を捨てます**"
    )


def test_前の点が本当に無い回はそう言う():
    eta = _load()
    lines = eta.headline(_plan(), None, _traj(), [])
    assert any("比べられる前の点がまだありません" in ln for ln in lines), (
        "前の点が本当に無い回に、何も言わなくなっています"
    )
