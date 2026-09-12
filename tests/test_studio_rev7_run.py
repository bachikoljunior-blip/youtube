"""`trend.rev7_draws` / `rev7_run` / `rev7_line`
—— **§7 の収益の節の 覆る条件 (4)（直近7日の平均が続けて上がったら、分子はチャンネルの回復の側）を数える口**。

2026-09-12 21:2x JST・optimizer・Opus。

**族の 6例目**（`late_run` 04:3x／`blind_run` 16:0x／`reporting_empty_run` 18:4x／
`outside_runs` 20:0x／`views_streak` 20:3x）—— 「N 続いたら」と書きながら、**N を数える物が無い**。

**同じ回に、単位のほうも外れていました**: (4) は「3**周**」と書いてありますが、
この平均が動くのは `cli analytics` を撃った回だけ（20時間 の門 ＝ 1日1回）で、
周は 1時間 弱。**周で数えると、引いた次の周に必ず「上がらなかった」が入り、連は永久に 1 で切れます**
＝ **引けない条件**でした（20:3x の「時刻 10:00」の 2例目・**あちらは分母が割れない側**）。

**陽性対照つき**（§5 の教訓の形 3つ目 ＝ **落ちるまで撃つ**）。数は JOURNAL 21:2x。
"""
import datetime as dt

from studio import trend


def _draw(at: str, days: dict[str, int]) -> list[dict]:
    """1回の引き（同じ `at` の `analytics_day` の塊）。`days` は "09-07" → 再生。"""
    return [{"event": "analytics_day", "id": f"2026-{d}", "views": v,
             "at": f"2026-09-{at}+09:00", "minutes": 0}
            for d, v in days.items()]


def _rising() -> list[dict]:
    """**実物と同じ形**（09/10 に 3回 引き直し → 09/11 → 09/12・7日の平均は上がる）。"""
    first = {f"09-0{i}": v for i, v in zip(range(1, 8), [140, 202, 66, 458, 1821, 783, 318])}
    rows = _draw("10T16:07:33", first)
    rows += _draw("10T16:17:54", first)          # 同じ日までの引き直し（落ちる側）
    rows += _draw("11T12:18:52", {"09-08": 977})
    rows += _draw("12T08:25:23", {"09-09": 471})
    return rows


def test_引き直した回は数えない():
    d = trend.rev7_draws(_rising())
    # 引きは 4回 あるが、**`last_day` が進んだのは 3回**（09/10 の 2回目は同じ 09-07 まで）。
    assert [x["last_day"] for x in d] == ["2026-09-07", "2026-09-08", "2026-09-09"]
    assert [round(x["avg"], 1) for x in d] == [541.1, 660.7, 699.1]


def test_連は引きで数える_門はまだ():
    r = trend.rev7_run(_rising())
    assert (r["run"], r["gate"], r["drawn"]) == (2, 3, False)
    # **周で数えていれば 0**（引きと引きのあいだの周は「上がらなかった」）＝ 単位の差はここに出る。
    assert r["since"] is not None


def test_上がりが止まれば連は切れる():
    rows = _rising() + _draw("13T08:00:00", {"09-10": 0})
    r = trend.rev7_run(rows)
    assert (r["run"], r["drawn"]) == (0, False)


def test_三回目で門が引かれる():
    rows = _rising() + _draw("13T08:00:00", {"09-10": 5000})
    r = trend.rev7_run(rows)
    assert (r["run"], r["drawn"]) == (3, True)
    assert "引かれました" in trend.rev7_line(rows)
    assert "量は毒" in trend.rev7_line(rows)


def test_古い日が書き直されても_過去の点はそのとき読めた数のまま():
    """**そのとき台帳に在った値**で組み直す（いまの値で過去を作ると、読めなかった数が並ぶ）。"""
    rows = _rising() + _draw("13T08:00:00", {"09-01": 99999, "09-10": 5000})
    d = trend.rev7_draws(rows)
    assert round(d[0]["avg"], 1) == 541.1      # 09/10 の点は 09-01 の古い値のまま
    # 最後の引きは 09-01 が窓の外（09-04〜09-10）なので、書き直しは平均に入らない。
    assert d[-1]["last_day"] == "2026-09-10"


def test_七日と十二日で向きが逆の引きは名指しする():
    r = trend.rev7_run(_rising())
    assert r["split"] is True                  # 実物: 7日 は上がり・12日 は下がり
    assert "窓から落ちた日" in trend.rev7_line(_rising())


def test_引きが無い_一回だけ():
    assert "1度も引いていません" in trend.rev7_line([])
    one = _draw("10T16:07:33", {"09-06": 783, "09-07": 318})
    assert "引きが 2回 そろってから" in trend.rev7_line(one)


def test_距離は撃つたびに出る():
    line = trend.rev7_line(_rising())
    # §7 の収益の節に写した「101〜205倍」は動く数 ＝ **印字の側が持つ**。
    assert "倍**）" in line and "90日" in line
