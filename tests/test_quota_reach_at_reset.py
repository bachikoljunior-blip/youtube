"""**枠が戻る瞬間に何%まで行くか**（2026-09-09 21:5x・optimizer・Opus）。

オーナー 21:13「全てのモデル100％いきそう？」/ 21:1x「どうすんの？」。
親は `--pace` の画面を読んで「いきません」と答えました（**結論は正しい**）。
ところが親が読んだ行はこう出ていました:

    このままならリセットまで届きます（100% 到達は 09/13 03:09 JST）

—— **「届きます」と書いてあり、その時刻は枠が戻った 09/12 07:00 の後**です。
＝ **決して来ない時刻**を、肯定の語で印字していた。

この行が答えていたのは `exhaust_at`（**`carry_rate` のまま**走ったらいつ 100% か）で、
オーナーの問い（**リセットまでに使い切るか**）とは別の問いです。しかも `carry_rate` は
**間隔を変える前**の速さで、床は同じ 21:13 の目盛りで **52.9分 → 41.6分** に動いていました。

だから `reach_at_reset()` を足しました。床は毎周 `per_lap / ((100-used)/left)` で
引き直されるので**閉じた輪**で、1周 遅れれば次の床がそのぶん縮みます。実測の答え:

    床に従えば          **99.8%**（遅れ +2.9分/周 を乗せても）
    いまの間隔のまま    **87.1%**
    ＝ 差の 13 ポイントは**間隔だけ**で決まる。**「いく／いかない」ではなく「床に乗るか」。**

**覆る条件**: `per_lap` が枠の途中で変われば見込みは外れます（「Fable のみ」100% は
09/11 11:37 JST 見込みで、その後は 2体 とも opus ＝ **この枠の中で起きる**）。
実測でずれたら `per_lap` を段ごとに分けること。
"""
from __future__ import annotations

import pytest

from scripts import quota


def test_床に従えば枠を使い切る():
    """閉じた輪 —— 床を毎周 引き直すなら、リセット時はほぼ 100%。"""
    got = quota.reach_at_reset(used_now=50.6, left_hours=57.1, per_lap=0.600)
    assert got is not None
    assert got >= 99.0, got


@pytest.mark.parametrize("lag", [0.0, 1.0, 2.9, 5.0])
def test_起こしの遅れを乗せても閉じた輪は閉じる(lag):
    """遅れは片側にしか出ない（実測 中央値 2.9分・負は 1本も無い）。

    それでも床が縮んで吸うので、**+5分/周 まではほぼ 100% のまま**。
    """
    got = quota.reach_at_reset(50.6, 57.1, 0.600, lag_min=lag)
    assert got >= 99.0, (lag, got)


def test_遅れが大きくなるほど到達は下がる():
    """**単調**であること。ここが崩れたら、輪の向きを疑う。"""
    seq = [quota.reach_at_reset(50.6, 57.1, 0.600, lag_min=g)
           for g in (0.0, 5.0, 10.0, 20.0, 40.0)]
    assert all(a >= b - 1e-9 for a, b in zip(seq, seq[1:])), seq
    assert seq[-1] < seq[0], seq


def test_間隔を固定すると枠が余る():
    """**陽性対照** —— 床に乗らない（56分 のまま）と、13 ポイント 残ります。

    これが「いく／いかない」ではなく「床に乗るか」だ、と言える根拠。
    床に従う側との差が 5 ポイント 以上 開くことを固定する。
    """
    floor_side = quota.reach_at_reset(50.6, 57.1, 0.600, lag_min=2.9)
    flat = 50.6 + (57.1 * 60.0 / 56.0) * 0.600          # 56分 のまま回した場合
    assert floor_side - flat > 5.0, (floor_side, flat)


@pytest.mark.parametrize("bad", [
    {"used_now": 50.0, "left_hours": 0.0, "per_lap": 0.6},     # 枠が閉じている
    {"used_now": 50.0, "left_hours": 10.0, "per_lap": 0.0},    # 1周の重さが測れていない
    {"used_now": 50.0, "left_hours": 10.0, "per_lap": None},
    {"used_now": 50.0, "left_hours": -1.0, "per_lap": 0.6},    # またいだ後
])
def test_測れないときは数を出さない(bad):
    """**測れないことを「余裕がある」と読ませない。** None を返す。"""
    assert quota.reach_at_reset(**bad) is None


def test_すでに使い切っていれば100のまま():
    assert quota.reach_at_reset(100.0, 57.1, 0.600) == 100.0


def test_pace_が到達を持って返す():
    p = quota.pace()
    if p is None:                       # 目盛りが無い環境（検査だけの clone）
        pytest.skip("目盛りが無い")
    assert "reach_floor" in p and "reach_carry" in p
    if p.get("per_lap") and p.get("left_hours", 0) > 0:
        assert p["reach_floor"] is not None
        assert 0.0 <= p["reach_floor"] <= 100.0


def test_遅れの当て先は2つ試すこと():
    """**`python scripts/quota.py` で撃つと `sys.path[0]` が `scripts/` になる。**

    `scripts.next_round` だけを試す形だと import が落ち、画面には
    **「遅れ 0.0分/周」**と出て、測った 2.9分 が黙って消えます（この回に踏んだ）。
    ＝ 09/09 09:5x の「当て先が 2つ あった」（`run_marker`）と同じ族。
    """
    text = open(quota.__file__, encoding="utf-8").read()
    assert '"scripts.next_round", "next_round"' in text, \
        "遅れの当て先が 1つ に戻っている（裸の import を試していない）"


def test_画面は来ない時刻を肯定の語で書かないこと():
    """**陽性対照つきの見張り** —— 親が読んだ当の行。

    旧: `このままならリセットまで届きます（100% 到達は 09/13 03:09 JST）`
    ＝ 枠が戻った後の時刻を「届きます」と書いていた。
    """
    import re
    text = open(quota.__file__, encoding="utf-8").read()
    # 註が旧文を引用しているので、**印字している所**だけを見る。
    printed = re.findall(r'print\(\s*f?"[^"]*"', text)
    assert not any("リセットまで届きます" in q for q in printed), \
        "「届きます」が印字に戻っている（100% 到達がリセットより後でも肯定で書く形）"
    assert any("リセットまでに届きません" in q for q in printed)


def test_このままの註は両方の枝に出ること():
    """`carry_rate` のままの話だ、という註は**どちらの枝でも**要る。

    旧は「鎖が止まる」側の枝にしか無く、**実際に親を誤らせたのは註の無い側**でした。
    """
    text = open(quota.__file__, encoding="utf-8").read()
    assert text.count("**「このまま」＝ 直近の速さ") == 1, \
        "註が枝ごとに分かれている（1か所にまとめて両枝から出すこと）"
    i_note = text.index("**「このまま」＝ 直近の速さ")
    i_dead = text.index('if p["dead_hours"] > 0:')
    assert i_note > i_dead, "註が dead_hours の枝の中に戻っている"
