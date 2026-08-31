"""**待つ日数が、実測から離れていないか。**（2026-08-26 に作った）

なぜ要るか。`SETTLE_DAYS = 7` は**一度も測っていない勘**で、4か月ぶん残りました。
その間に `scripts/eta.py` は同じ量を `MATURE_HOURS = 48` として**実測つきで**持ち、
`config/hypotheses.yaml` は 2026-08-21 に測って1件だけ 24時間 に直しています。
**3つが別々の数を持ち、判定の門はいちばん遅い数だけを読んでいました。**

この検査は「7 に戻っていないか」を見るのではありません。
**その時点の実データが、いま使っている数を支えているか**を見ます。
支えなくなったら（後から拾われる本が出たら）、ここが落ちて次の回に知らせます。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from src import settle

ROOT = Path(__file__).resolve().parent.parent


def test_待つ日数は実データに支えられている():
    """`SETTLE_DAYS` の時点で、**いちばん遅い本**が伸びきっているか。"""
    curve = settle.views_curve((float(settle.SETTLE_DAYS * 24),))
    row = curve.get(float(settle.SETTLE_DAYS * 24))
    if not row or row["n"] < 10:
        pytest.skip(f"標本が薄い（n={row['n'] if row else 0}）—— 判定しない")
    assert row["median"] >= 0.99, (
        f"{settle.SETTLE_DAYS*24}時間 で中央値 {row['median']:.3f} —— "
        "**待つ日数が短すぎます。** `src/settle.py` の「覆る条件」を読んで上げ直すこと"
    )
    # **`min` を門にしないこと**（2026-08-29 に直した。`src/settle.py` の
    #   `SETTLED_SHARE_FLOOR` の註に実測）。`min` は標本が増えれば単調に下がるので、
    #   **何も悪くなっていない回でも、いつか必ず落ちます** ——
    #   実測 96h: 中央値 1.0000・p10 0.9967 なのに **min 0.5105**（外れは 1本/60本、
    #   その1本は 96h で 48再生 の本）。その1本のために `SETTLE_DAYS` を 4 → 7 に
    #   上げると、開いている前提 27件 の判定日が全部 +3日 動きます。
    assert row["p10"] >= 0.95, (
        f"{settle.SETTLE_DAYS*24}時間 で下位10% が {row['p10']:.3f} —— "
        "**後から拾われる本が出ています。** `SETTLE_DAYS` を上げ直すこと"
        f"（いちばん遅い本は {row['min']:.3f}）"
    )
    assert row["share_settled"] >= 0.95, (
        f"{settle.SETTLE_DAYS*24}時間 で伸びきっている本が "
        f"{row['share_settled']:.1%}（外れ {row['n_unsettled']}本 / {row['n']}本）—— "
        "**外れが 5% を超えました。これは本物です。**`SETTLE_DAYS` を上げ直すこと"
    )


def test_極値だけでは門にしない():
    """**`min` が下がっただけの回で `SETTLE_DAYS` を上げないこと。**

    `min` は標本が増えれば単調に下がります。**増えること自体が門を厳しくする**ので、
    そのまま門にすると「何も悪くなっていないのに必ずいつか落ちる検査」になります
    （2026-08-29 に実際にそうなっていた。同じ日に `scripts/trajectory.py` の
    後ろカタログの門でも同じ形を直した）。
    """
    curve = settle.views_curve((float(settle.SETTLE_DAYS * 24),))
    row = curve.get(float(settle.SETTLE_DAYS * 24))
    if not row:
        pytest.skip("標本なし")
    assert "share_settled" in row and "n_unsettled" in row, (
        "**何本 外れているか**を数えていません。数えないと、"
        "1本の外れと 20本 の外れが同じ顔で出ます"
    )
    assert "min" in row, "**`min` を消さないこと。** 門から外すのと、隠すのは別です"


def test_engaged_比率もその時点で確定している():
    """判定がじっさいに使うのは engaged 比率のほう。**確定値との差が 2pt 未満か。**

    **2026-08-31 に、形で割りました。** それまで形を混ぜて測っており、
    混ぜた最大 17.08pt で落ちていました。落ちたときの文面は
    「**`SETTLE_DAYS` を上げ直すこと**」でしたが、**上げてはいけませんでした** ——
    形で割ると、そのずれは全部 長尺のものです（齢 96h ／ 確定 120h・門 2pt）::

        形        n    最大ずれ   中央    門超え
        ショート  49    1.01pt   0.00pt   **0本**
        長尺       2   17.08pt   9.19pt     1本

    外れは `13TynquQzQU`（長尺）で、**96h → 120h に再生が 30 → 82**（窓の中で 2.7倍）。
    `settles_at("長尺")` が「どの地平でも伸びきらない」と出す本そのものです。

    **`SETTLE_DAYS` は θ（腕の動く速さ）の分母**です
    （`src/judgeable.py` の「判定できる日」に足され、`scripts/eta.py` は毎回
    「軌跡の腕が動くのは前提を1件 閉じたときだけ」と印字します）。
    **長尺2本のために上げると、ショートの A/B 49本ぶんが道連れで遅くなります。**

    だからこの検査は `SETTLE_DAYS` を測った形＝**ショートで**当てます。
    """
    age = float(settle.settle_days("ショート") * 24)
    eng = settle.engaged_curve((age,), form="ショート")
    row = eng.get(age)
    if not row or row["n"] < 10:
        pytest.skip("scan のショートの標本が薄い —— 判定しない")
    assert row["max"] < 0.02, (
        f"**ショートの** engaged 比率が確定値から最大 {row['max']*100:.2f}pt "
        f"ずれています（n={row['n']}）—— **この年齢では判定が入れ替わります。**"
        " `SETTLE_DAYS_BY_FORM['ショート']` を上げ直すこと"
        "（**混ざった数で上げないこと。形で割ってから**）"
    )


def test_長尺は判定の窓の中でまだ動く():
    """**長尺は、`SETTLE_DAYS` の年齢で確定していません。**（2026-08-31 に測って足した）

    この検査は「落ちたら直す」ではなく **「落ちたら消してよい」**側です ——
    落ちる ＝ 長尺も窓の中で動かなくなった ＝ `SETTLE_DAYS_BY_FORM` に
    長尺を載せてよくなった、という**良い知らせ**です。

    **数そのものは守りません**（標本が増えれば動きます）。守るのは
    **「長尺の不確定さを、ショートの門に混ぜないこと」**。
    """
    age = float(settle.SETTLE_DAYS * 24)
    eng = settle.engaged_curve((age,), form="長尺")
    row = eng.get(age)
    if not row:
        pytest.skip("scan に長尺の標本がありません")
    s_row = settle.engaged_curve((age,), form="ショート").get(age)
    if not s_row:
        pytest.skip("比べるショートの標本がありません")
    assert row["max"] > s_row["max"], (
        f"**長尺のずれ {row['max']*100:.2f}pt が、ショート {s_row['max']*100:.2f}pt "
        f"を下回りました。良い知らせです。**"
        f" `SETTLE_DAYS_BY_FORM` に長尺を載せられるか見直し、この検査を消すこと"
    )


def test_長尺を混ぜた門で_ショートの待ちを延ばさない():
    """**混ぜた数を門にすると、ショートの A/B が長尺の道連れで遅くなる。**

    混ぜた `engaged_curve()` の最大は、形で割ったショートの最大より
    **必ず大きいか等しい**（長尺が外れているあいだ）。
    その混ざった数で `SETTLE_DAYS` を決めると、**θ の分母が長尺2本で決まります。**
    """
    age = float(settle.SETTLE_DAYS * 24)
    mixed = settle.engaged_curve((age,)).get(age)
    short = settle.engaged_curve((age,), form="ショート").get(age)
    if not mixed or not short:
        pytest.skip("標本が薄い")
    assert short["max"] <= mixed["max"], (
        "形で割ったショートのずれが、混ぜたものより大きくなりました。"
        " `engaged_curve(form=...)` の絞り込みを見ること"
    )
    assert short["n"] <= mixed["n"]


def test_同じ数を他所で定義していない():
    """**このファイルの外に数を書かないこと。** 8件みつかった壊れ方の再発を止める。"""
    for rel in ("src/ab_split.py", "scripts/eta.py", "scripts/deadline_check.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        body = "\n".join(l for l in text.splitlines()
                         if not l.lstrip().startswith("#") and not l.lstrip().startswith("#:"))
        assert not re.search(r"^\s*SETTLE_DAYS\s*=\s*\d", body, re.M), \
            f"{rel} が `SETTLE_DAYS` を自分で定義しています（`src/settle.py` から読むこと）"
        assert not re.search(r'settle_days"\s*,\s*\d', body), \
            f"{rel} が `settle_days` の既定を直に書いています（`src/settle.py` から読むこと）"


def test_yaml_の_settle_days_も同じ数を使っている():
    """前提ごとに別の待ち日数が残っていないか。**0 は「待たない」で意図的**。"""
    data = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    for h in data["hypotheses"]:
        for need in h.get("needs") or []:
            if "settle_days" not in need:
                continue
            got = int(need["settle_days"])
            assert got in (0, settle.SETTLE_DAYS), (
                f"「{str(h.get('claim'))[:30]}」の settle_days が {got} —— "
                f"いまの実測は {settle.SETTLE_DAYS}日 です。**長く待つ理由があるなら、"
                "その理由を `src/settle.py` に書いてからこの検査を直すこと**"
            )


# ---- 遅れの帯（2026-08-26）----------------------------------------------

def test_遅れの帯は実測から出る():
    """**遅れは点ではありません。1日の中で動きます。**

    Analytics は日の途中で新しい日を出すので、**同じ日でも早い時刻に走った回は
    4日、遅い時刻の回は 3日**を見ます。実測 438観測で 3日が 381・4日が 57、
    **1日のうちに両方を観測した日が 6日**（08/18〜08/22・08/26）。

    この幅を `scripts/deadline_check.py` が帯として使い、
    **「期限が1日 ずれています」という churn を止めます。**
    """
    b = settle.analytics_lag_band()
    assert set(b) >= {"lag", "lo", "hi", "band", "n"}
    assert b["lo"] <= b["lag"] <= b["hi"] or b["n"] < 2
    assert b["band"] == b["hi"] - b["lo"] >= 0


def test_観測が足りない回は帯を主張しない(tmp_path):
    """**黙って広げないこと。** 帯が広いほど「ずれ」を見逃すので、根拠が要ります。"""
    空 = tmp_path / "からっぽ.jsonl"
    空.write_text("", encoding="utf-8")
    assert settle.analytics_lag_band(path=空)["band"] == 0


def test_窓の外の観測は帯に入れない(tmp_path):
    """古い遅れを混ぜると、**もう起きない幅**で今日の判定を黙らせます。"""
    import json
    p = tmp_path / "lag.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"at": "2020-01-01T00:00:00+09:00", "last_day": "2019-12-01"},   # 31日 遅れ・窓の外
        {"at": "2026-08-26T02:00:00+09:00", "last_day": "2026-08-22"},   # 4日
        {"at": "2026-08-26T06:00:00+09:00", "last_day": "2026-08-23"},   # 3日
    ]), encoding="utf-8")
    b = settle.analytics_lag_band(window_days=10**6, path=p)
    assert b["hi"] == 31 and b["band"] == 28, "窓を広げれば入る（この検査じしんの前提の確認）"

    b = settle.analytics_lag_band(window_days=14, path=p)
    assert b["hi"] == 4 and b["lo"] == 3, "窓の中に残るのは 08/26 の2件だけ"
    assert b["band"] == 1, ("古い 31日 を混ぜて帯を 28日 にしないこと —— "
                            "**もう起きない幅で今日の判定を黙らせる**ことになります")


def test_過去の日の遅れは0にならない():
    """**過去の `as_of` に、その日にはまだ無かった観測を混ぜないこと。**

    実測 2026-08-29: `analytics_lag_days(date(2026,8,26))` は **0日** を返していた
    （`max(last_day)` を台帳ぜんたいから採っていたため）。
    `ANALYTICS_LAG_FALLBACK` の註が「**0 にしないこと** —— いちばん危ない側へ
    倒れます」と禁じている、その値そのもの。

    何が壊れるか: `readable_by(as_of, s)` は `as_of - (settle + lag)` なので、
    **lag が 0 に落ちると判定の締切が 3日 うしろへ伸び、まだ読めていない
    データで判定する側へ倒れます**（`falsified_if` は「上回らなければ外れ」）。
    """
    from datetime import date as _date

    for d in (_date(2026, 8, 20), _date(2026, 8, 26), _date(2026, 8, 29)):
        got = settle.analytics_lag_days(d)
        assert got > 0, (
            f"{d} の遅れが {got}日 —— **「遅れは無い」と言い切っています。** "
            "台帳ぜんたいの `max(last_day)` を採っていませんか"
            "（その日以降に積まれた行が混ざります）"
        )

    # 台帳より前の日を訊かれたら、控えへ落ちること（0 にしない）
    assert settle.analytics_lag_days(_date(2026, 1, 1)) == settle.ANALYTICS_LAG_FALLBACK


def test_遅れは今日でも0にならない():
    """いまの日でも 0 にならないこと（Analytics は日次で遅れる）。"""
    assert settle.analytics_lag_days() > 0
