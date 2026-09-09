"""親が置いた起こしの**届きの遅れ**を、`decide()` が引くこと（`scripts/next_round`）。

**なぜ要るか**（2026-09-09 18:2x JST・optimizer・Opus が実測して足した。`docs/METHOD.md` §5・§7）:

`decide()` の 0体 の枝は、起こしを「間隔が明ける瞬間 ＋ 1分」へ置いていました。
19:1x の註はそれを **「0体 の回は丸めません。`send_later` は分の粒度だから」** と説明しています。
**分の粒度で頼めることと、分の粒度で届くことは、別でした。**

実測（`data/parent_wakes.jsonl`・`who=owner` の `at + wake_min` と、その後の最初の `at`）:

    1.0 1.3 1.3 1.5 2.9 3.8 4.0 4.3 4.6 4.8 4.9 5.0 5.4 分（n=13・中央値 **3.96分**）

**負は 1本もありません** ＝ 片側にしか出ない損です。効き目は GO の側に そのまま出ていました:
床 53分 に対し GO は直近19回**すべて**超過（中央値 **+3.1分**・最小 +1.6）・周から周は **56〜58分**。
`pace()` は床そのものを決める側なので、**床の上に乗るこの遅れは `pace()` から見えません**
（床が下がるたび、同じ遅れがそのまま残る）。09/09 07:08 の目盛りで「すべてのモデル」は
線（09/07 08:04 の 25% から 0.62 %/時）より **13.2 ポイント 下**でした。

直しは 19:1x と同じ形です —— **どちらが `floor` に近いか**で決め、刻みは心拍ではなく この遅れ:

    いま出す        → 間隔は passed（`floor` に足りない ぶんだけ短い）
    次の届きまで待つ → 間隔は passed + 遅れ（`floor` を越えた ぶんだけ長い）
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import next_round

T0 = datetime(2026, 9, 8, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def rounds(tmp_path, monkeypatch):
    """前の周を1つだけ置いた台帳に差し替える。**本物には触らない。**"""
    p = tmp_path / "rounds.jsonl"
    rows = [{"at": T0.isoformat(), "role": r, "round": T0.isoformat()}
            for r in next_round.ROLES]
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    monkeypatch.setattr(next_round, "ROUNDS", p)
    monkeypatch.setattr(next_round, "WAKES", tmp_path / "parent_wakes.jsonl")
    return p


def _decide(monkeypatch, *, floor, passed, lat, live=0, beat=60.0):
    monkeypatch.setattr(next_round, "floor_minutes", lambda: (floor, "検査"))
    monkeypatch.setattr(next_round, "heartbeat_minutes", lambda *a, **k: (beat, "検査"))
    monkeypatch.setattr(next_round, "wake_latency_minutes", lambda *a, **k: (lat, "検査"))
    return next_round.decide(now=T0 + timedelta(minutes=passed), live=live)


# ---- 遅れを数える --------------------------------------------------------

def _wakes(tmp_path, monkeypatch, rows):
    p = tmp_path / "parent_wakes.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    monkeypatch.setattr(next_round, "WAKES", p)
    return p


def _row(minute, wake_min=None, who="owner"):
    r = {"at": (T0 + timedelta(minutes=minute)).isoformat(), "who": who}
    if wake_min is not None:
        r["wake_min"] = wake_min
    return r


def test_届いた起こしの遅れを中央値で取る(tmp_path, monkeypatch):
    """`at + wake_min` と、その後の最初の起きの差。"""
    rows = []
    for i, lag in enumerate((1.0, 2.0, 3.0, 4.0, 6.0)):
        base = i * 100.0
        rows.append(_row(base, wake_min=10))
        rows.append(_row(base + 10.0 + lag))
    _wakes(tmp_path, monkeypatch, rows)
    got, src = next_round.wake_latency_minutes()
    assert got == pytest.approx(3.0)
    assert "5回" in src


def test_本数が足りなければ写しを使う(tmp_path, monkeypatch):
    """**0 を返さないこと** —— 0 は「遅れは無い」という主張で、実測はそれを否定している。"""
    _wakes(tmp_path, monkeypatch, [_row(0.0, wake_min=10), _row(11.0)])
    got, src = next_round.wake_latency_minutes()
    assert got == next_round.WAKE_LATENCY_FALLBACK_MIN > 0.0
    assert "写し" in src


def test_心拍が拾った回は分母から外す(tmp_path, monkeypatch):
    """起こしが届かず、次の心拍まで空いた回を混ぜると、遅れが刻みの大きさに化ける。"""
    rows = []
    for i in range(6):
        base = i * 500.0
        rows.append(_row(base, wake_min=10))
        rows.append(_row(base + 10.0 + (2.0 if i < 5 else 120.0)))
    _wakes(tmp_path, monkeypatch, rows)
    got, src = next_round.wake_latency_minutes()
    assert got == pytest.approx(2.0)
    assert "5回" in src   # 6本 のうち 120分 の1本を外して 5回


def test_引きすぎない歯止め(tmp_path, monkeypatch):
    """台帳が壊れた回に、起こしを何十分も手前へ置かせない。"""
    rows = []
    for i in range(6):
        base = i * 100.0
        rows.append(_row(base, wake_min=10))
        rows.append(_row(base + 10.0 + next_round.WAKE_LATENCY_CAP_MIN + 1.0))
    _wakes(tmp_path, monkeypatch, rows)
    got, _ = next_round.wake_latency_minutes()
    assert got == next_round.WAKE_LATENCY_CAP_MIN


def test_サブや人が撃った行は数えない(tmp_path, monkeypatch):
    """`who != owner` の行は、親の起こしではない（`heartbeat_minutes` と同じ取り分）。"""
    rows = []
    for i in range(5):
        base = i * 100.0
        rows.append(_row(base, wake_min=10, who="sub"))
        rows.append(_row(base + 12.0, who="sub"))
    _wakes(tmp_path, monkeypatch, rows)
    got, src = next_round.wake_latency_minutes()
    assert got == next_round.WAKE_LATENCY_FALLBACK_MIN
    assert "写し" in src


# ---- 遅れを引く ----------------------------------------------------------

def test_遅れのぶん手前へ置く(rounds, monkeypatch):
    """届くのは「頼んだ時刻 ＋ 遅れ」なので、狙い先の手前に頼む。

    **狙い先は `floor`**（2026-09-09 20:5x に直した。18:2x は `target` を狙っていた）。
    """
    d = _decide(monkeypatch, floor=53.0, passed=0.0, lat=4.0)
    assert d["go"] is False
    # 狙い先 53.0 → 頼むのは 53 - 4 = 49分 後（届くのは 49 + 4 = 53分 ＝ 床ちょうど）
    assert d["wake_min"] == 49
    assert d["aim_min"] == pytest.approx(53.0)


def test_狙い先は境目ではなく床(rounds, monkeypatch):
    """**同じ遅れを 2度 引かないこと。**

    18:2x の形は `wait = target - passed` のまま `- lat` していたので、
    狙い先が `floor - lat/2` ＝ **毎周きっかり `lat/2` だけ床の下**でした
    （実測 2回 続けて -0.58/-0.98分。`next_round.wake_latency_minutes()` の註）。
    `floor - lat/2` は「もう届いた `passed` を出すか待つか」の境目であって、狙い先ではない。
    """
    for lat in (2.0, 4.0, 8.0):
        d = _decide(monkeypatch, floor=53.0, passed=10.0, lat=lat)
        assert d["go"] is False
        # 頼んだ分 ＋ 遅れ ＝ 届く時刻。床ちょうどに乗ること（切り上げのぶんだけ上）。
        arrives = 10.0 + d["wake_min"] + lat
        assert 53.0 <= arrives < 54.0, (lat, d["wake_min"], arrives)
        # 境目を狙っていたら、届く時刻は床の下（lat/2 ぶん）になる。
        assert arrives > 53.0 - lat / 2.0


def test_境目のほうは動かしていない(rounds, monkeypatch):
    """狙い先を床へ戻しても、**もう届いた回の「どちらが近いか」は 18:2x のまま**。"""
    assert _decide(monkeypatch, floor=53.0, passed=51.0, lat=4.0)["go"] is True
    assert _decide(monkeypatch, floor=53.0, passed=51.0, lat=4.0)["target_min"] == pytest.approx(51.0)


def test_台帳のwake_atは送った起こしと一致する(rounds, monkeypatch):
    """前の形は `floor + 1.0` を別に組み立てており、送った物と最大 1分 ずれていた。"""
    now = T0 + timedelta(minutes=10.0)
    d = _decide(monkeypatch, floor=53.0, passed=10.0, lat=4.0)
    assert d["wake_at"] == now + timedelta(minutes=d["wake_min"])


def test_遅れの半分だけ手前でGOを出す(rounds, monkeypatch):
    """**どちらが `floor` に近いか。** 待てば `floor + 遅れ`、いま出せば `floor - 遅れ/2`。"""
    assert _decide(monkeypatch, floor=53.0, passed=51.0, lat=4.0)["go"] is True
    assert _decide(monkeypatch, floor=53.0, passed=50.9, lat=4.0)["go"] is False


def test_遅れが消えれば補正も消える(rounds, monkeypatch):
    """**覆る条件そのもの。** 起こしが頼んだとおり届くようになったら、`floor` へ戻る
    （台帳から数え直す形なので、外しに来なくてよい）。"""
    assert _decide(monkeypatch, floor=53.0, passed=52.9, lat=0.0)["go"] is False
    assert _decide(monkeypatch, floor=53.0, passed=53.0, lat=0.0)["go"] is True


def test_頼む分は1分を切らない(rounds, monkeypatch):
    """`send_later` は 1分 が最小。0 や負を渡さないこと。"""
    d = _decide(monkeypatch, floor=53.0, passed=46.0, lat=8.0)
    assert d["go"] is False   # target = 49.0・passed 46.0
    assert d["wake_min"] >= 1


def test_サブが走っている回は心拍のまま(rounds, monkeypatch):
    """遅れは **0体 の枝（起こしを置く回）** の話。1体でも走っていれば刻みは心拍。"""
    d = _decide(monkeypatch, floor=77.0, passed=59.8, lat=4.0, live=1)
    assert d["go"] is True    # 心拍 60分 の「近いほうへ」がそのまま効く


def test_決めに使った遅れが台帳に残る(rounds, monkeypatch):
    """次の回が、引いたことと その大きさを数で見られること。"""
    d = _decide(monkeypatch, floor=53.0, passed=10.0, lat=4.0)
    assert d["wake_latency_min"] == pytest.approx(4.0)
    assert d["wake_latency_source"] == "検査"


def test_台帳から起こしの算数が読めること(rounds, monkeypatch):
    """`wait_min`（境目まで）と `wake_wait_min`（狙い先まで）は**分母が違う**。

    20:5x に狙い先を `floor` へ移したので、`wake_min` を `wait_min` から
    引き算し直すと合いません。**次の回が台帳の1行で確かめられること**
    （`rounding_evidence()` の註「うち target_min を持つ 0 ＝ 1行も答えられない」の族）。
    """
    d = _decide(monkeypatch, floor=53.0, passed=10.0, lat=4.0)
    assert d["wait_min"] == pytest.approx(51.0 - 10.0)        # 境目 51.0 まで
    assert d["wake_wait_min"] == pytest.approx(53.0 - 10.0)   # 狙い先 53.0 まで
    assert d["wake_min"] == pytest.approx(d["wake_wait_min"] - 4.0, abs=1.0)


# ---- 同じ届きを指す遅れを畳む（2026-09-10 04:0x・optimizer・Opus） ----------
#
# 親は**同じ届き先に起こしを2本 置くことがあります**（実測 09/09 17:58:39 と 17:59:27 が、
# どちらも 18:19 を狙って `send_later` を置いた）。行ごとに 1本 数えると、
# **同じ 1回の届きが 2〜3回 分母に入ります**（実測 27本 → 届きは 18回・17本 が重なり）。
# 効き目は中央値が **2.363 → 2.815分** に膨らむことで、
# 膨らんだぶん起こしを手前へ置きすぎ、**周が床の下へ落ちます**（実測 -0.42 / -1.13分）。


def _distinct(rows, lags=(5.0, 5.5, 6.0, 6.5, 7.0)):
    """重なりの無い届きを `lags` の数だけ足す（畳んだあとも n を `MIN_N` の上に保つ）。"""
    for i, lag in enumerate(lags):
        base = 100.0 * (i + 1)
        rows.append(_row(base, wake_min=10))
        rows.append(_row(base + 10.0 + lag))
    return rows


def test_陽性対照_同じ届きを指す起こしは1本に畳む(tmp_path, monkeypatch):
    """**畳む側を外すと落ちる。**

    同じ届き（30分）を 5本 の起こしが指す並び（遅れ 1.0/0.8/0.6/0.4/0.2）に、
    重なりの無い届き 5回（5.0〜7.0分）を混ぜる:

      畳まない  0.2 0.4 0.6 0.8 1.0 5.0 5.5 6.0 6.5 7.0 → 中央値 **3.0**
      畳む      1.0（いちばん早く置いた1本） 5.0 5.5 6.0 6.5 7.0 → 中央値 **5.75**
    """
    rows = [_row(m, wake_min=10) for m in (19.0, 19.2, 19.4, 19.6, 19.8)]
    rows.append(_row(30.0))
    _wakes(tmp_path, monkeypatch, _distinct(rows))
    got, src = next_round.wake_latency_minutes()
    assert got == pytest.approx(5.75), (
        f"{got:.2f} —— 同じ届きの 5本 を畳んでいない（畳まなければ中央値 3.0）")
    assert "6回" in src and "言い直し 4本 を畳んだ" in src, src


def test_畳んだ本数が台帳の言い分に出る(tmp_path, monkeypatch):
    rows = [_row(m, wake_min=10) for m in (19.0, 19.2)]
    rows.append(_row(30.0))
    _wakes(tmp_path, monkeypatch, _distinct(rows))
    _, src = next_round.wake_latency_minutes()
    assert "言い直し 1本 を畳んだ" in src, src


def test_重なりが無ければ言い分は変わらない(tmp_path, monkeypatch):
    """**畳みは、重なりが 0 の台帳では何もしない**（`wake_latency_minutes` の覆る条件 (2)）。"""
    rows = []
    for i, lag in enumerate((1.0, 2.0, 3.0, 4.0, 6.0)):
        base = i * 100.0
        rows.append(_row(base, wake_min=10))
        rows.append(_row(base + 10.0 + lag))
    _wakes(tmp_path, monkeypatch, rows)
    got, src = next_round.wake_latency_minutes()
    assert got == pytest.approx(3.0)
    assert "畳んだ" not in src, src


def test_本物の台帳で重なりが半分を越えている(tmp_path, monkeypatch):
    """**越えたら、直すのは畳みではなく「親が起こしを2本 置くこと」の側**（覆る条件 (3)）。

    いま 17/27 ＝ 63%。**0 になったら**この検査が落ちて、畳みが要らなくなったと教える。
    """
    _, src = next_round.wake_latency_minutes()
    assert "畳んだ" in src, (
        "本物の台帳から重なりが消えた ＝ 親が同じ届きに 2本 置くのをやめた印。"
        "`wake_latency_minutes` の覆る条件 (2) を読んで、畳みを外してよい")
