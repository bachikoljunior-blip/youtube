"""**周から周の間隔を、1周 2行 の台帳から正しく数えるか**
（2026-09-09 00:2x JST・optimizer・Opus）。

§7 21:4x の覆る条件 (1) は「**周から周の中央値が `floor` の 1.25倍 を越えていたら**、
上限は丸めではない」と書いている。ところがその数の出どころ `data/rounds.jsonl` は
**1周につき役の数だけ行**を書く（`hourly` と `optimizer` で 2行・同じ時刻）。
素朴に「行から行」を数えると 0分 が交互に挟まり、中央値が半分になる:

    素朴に行から行   39.6分   ← floor(76分) の 0.52倍 ＝ **条件は永久に引かれない**
    `round` で畳む   80.4分   ← 本当の周から周（floor の 1.06倍）

＝ 鳴らない見張り。ここで止めるのはその形。
"""
import json

import pytest

import scripts.next_round as nr


def _write(tmp_path, rows):
    p = tmp_path / "rounds.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return p


@pytest.fixture()
def rounds(tmp_path, monkeypatch):
    def _set(rows):
        monkeypatch.setattr(nr, "ROUNDS", _write(tmp_path, rows))
    return _set


def _round(at, rid=None):
    return [{"at": at, "role": r, "round": rid or at} for r in ("hourly", "optimizer")]


def test_同じ周の2行は畳まれる(rounds):
    rounds(_round("2026-09-08T12:40:00+00:00")
           + _round("2026-09-08T14:00:00+00:00")
           + _round("2026-09-08T15:20:00+00:00"))
    assert nr.round_gaps() == [80.0, 80.0]
    assert nr.gap_median() == 80.0


def test_素朴に行から行を数えると半分になる_これが踏んだ形(rounds):
    """**陽性対照**: 畳まないとどうなるかを、同じ台帳で見せる。"""
    got = (_round("2026-09-08T12:40:00+00:00")
           + _round("2026-09-08T14:00:00+00:00")
           + _round("2026-09-08T15:20:00+00:00"))
    rounds(got)
    naive = []
    ts = sorted(nr._at(r) for r in got)
    for a, b in zip(ts, ts[1:]):
        naive.append((b - a).total_seconds() / 60.0)
    assert naive == [0.0, 80.0, 0.0, 80.0, 0.0]     # 0 が交互に挟まる
    from statistics import median
    assert median(naive) == 0.0                     # 素朴な中央値は 0分
    assert nr.gap_median() == 80.0                  # 畳めば 80分


def test_roundが無い古い行は時刻で畳む(rounds):
    rounds([{"at": "2026-09-08T12:40:00+00:00", "role": "hourly"},
            {"at": "2026-09-08T12:40:00+00:00", "role": "optimizer"},
            {"at": "2026-09-08T14:00:00+00:00", "role": "hourly"}])
    assert nr.round_gaps() == [80.0]


def test_役が1つしか立たなかった周も1周として数える(rounds):
    """穴埋めの回（片方だけ立てた周）を、間隔から落とさない。"""
    rounds(_round("2026-09-08T12:40:00+00:00")
           + [{"at": "2026-09-08T14:00:00+00:00", "role": "hourly",
               "round": "2026-09-08T14:00:00+00:00"}])
    assert nr.round_gaps() == [80.0]


def test_周が1つなら間隔は空(rounds):
    rounds(_round("2026-09-08T12:40:00+00:00"))
    assert nr.round_gaps() == []
    assert nr.gap_median() is None


def test_decideの台帳に中央値と_floorとの比が載る(rounds, wakes, monkeypatch):
    """§7 の覆る条件が、手で数えずに読めること。

    **`wakes` を tmp に留めるのは、この検査が 1度 本物を読んだから**（2026-09-09 09:5x）——
    `gap_ratios` を足した日、この検査だけが落ちた。周の時刻（09/08 12:40・14:00・15:20 UTC）が
    **本物の親の周とぴったり同じ**なので、tmp の `rounds` に対して**本物の `parent_wakes.jsonl` の
    floor（75.4分）**が結びつき、1.0 のはずが 1.06 と出た。
    09/09 00:1x の「死んだ当て先を monkeypatch していた 4件」の逆向きで、
    **差し替え忘れた当て先が生きていた**形。台帳を読む関数を足したら、その台帳も留めること。
    """
    rounds(_round("2026-09-08T12:40:00+00:00")
           + _round("2026-09-08T14:00:00+00:00")
           + _round("2026-09-08T15:20:00+00:00"))
    wakes([])                                   # floor を持つ GO が無い ＝ 古い出し方へ落ちる
    monkeypatch.setattr(nr, "floor_minutes", lambda: (80.0, "検査"))
    got = nr.decide(live=0)
    assert got["gap_median_min"] == 80.0, got
    assert got["gap_over_floor"] == 1.0, got
    assert got["gap_ratio_n"] == 0, got          # 0 ＝「そのときの floor で割れていない」印


# ---------------------------------------------------------------------------
# **2026-09-09 02:5x（optimizer・Opus）に足したぶん** ——
# §5 の覆る条件 (2) の分母が、条件に答えられない行で埋まっていた件（`rounding_evidence`）。
# ---------------------------------------------------------------------------


@pytest.fixture()
def wakes(tmp_path, monkeypatch):
    """`data/parent_wakes.jsonl` を tmp に差し替える（本物へは書かない・`log_wake` の註）。"""
    p = tmp_path / "parent_wakes.jsonl"

    def _set(rows):
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                     encoding="utf-8")
        monkeypatch.setattr(nr, "WAKES", p)
        return p
    return _set


def _wake(live, go=False, floor=76.0, target=None, who="owner"):
    row = {"at": "2026-09-08T09:00:00+00:00", "who": who, "go": go, "live": live}
    if target is not None:
        row["floor_min"] = floor
        row["target_min"] = target
    return row


def test_数を持たない古い行は分母に入らない(wakes):
    """**この検査が本体** —— `live>0` でも `decide()` の数が無ければ、丸めを評価できない。

    実測（2026-09-09 02:5x）: `who=owner` 19行 のうち `live>0` は **3行**、
    そのうち `target_min` を持つ行は **0**（3行 とも、数を書き写すようにした 13:00 UTC より前）。
    ＝ 00:2x の「`live > 0` が 3回 溜まったら評価する」は、**開いても答えの無い門**だった。
    """
    wakes([_wake(1), _wake(1), _wake(1)])
    assert nr.rounding_evidence() == (0, 0)


def test_数を持つ行だけを数える(wakes):
    wakes([_wake(1),
           _wake(1, go=False, target=63.0),
           _wake(1, go=True, target=63.0),
           _wake(1, go=True, target=76.0)])
    assert nr.rounding_evidence() == (3, 1)


def test_0体の回とサブの回は数えない(wakes):
    """`decide()` は `live > 0` の回しか丸めない・`who != owner` は親ではない（`_who()` の註）。"""
    wakes([_wake(0, go=True, target=63.0),
           _wake(1, go=True, target=63.0, who="sub")])
    assert nr.rounding_evidence() == (0, 0)


def test_decideの台帳に丸めの分母が載る(rounds, wakes, monkeypatch):
    """次の回が手で数えずに読めること（00:2x が `round_gaps` でやった直しと同じ形）。"""
    rounds(_round("2026-09-08T12:40:00+00:00") + _round("2026-09-08T14:00:00+00:00"))
    wakes([_wake(1, go=True, target=63.0), _wake(1, go=False, target=70.0)])
    monkeypatch.setattr(nr, "floor_minutes", lambda: (80.0, "検査"))
    got = nr.decide(live=0)
    assert got["rounding_live"] == 2, got
    assert got["rounding_gos"] == 1, got


def test_log_wakeが丸めの分母を書き写す(tmp_path, monkeypatch):
    """`decide()` が返した数が、行に残ること（19:1x/21:4x が「数の側を捨てていた」と直した続き）。"""
    p = tmp_path / "parent_wakes.jsonl"
    monkeypatch.setattr(nr, "WAKES", p)
    nr.log_wake({"go": True, "live": 1, "roles": ["hourly"], "why": "検査",
                 "floor_min": 76.0, "target_min": 63.0,
                 "rounding_live": 2, "rounding_gos": 1})
    row = json.loads(p.read_text(encoding="utf-8").splitlines()[-1])
    assert row["rounding_live"] == 2 and row["rounding_gos"] == 1, row


# ---------------------------------------------------------------------------
# **2026-09-09 09:5x（optimizer・Opus）に足したぶん** ——
# `gap_over_floor` が「中央値 ÷ **いまの** floor」で、`pace()` が床を動かした直後に
# 追随している親へ向けて鳴っていた件（`gap_ratios` の註）。
# ---------------------------------------------------------------------------


def _go(at, floor):
    return {"at": at, "who": "owner", "go": True, "live": 0, "floor_min": floor}


def test_床が動いた直後でも比は追随した側を映す(rounds, wakes, monkeypatch):
    """**この検査が本体** —— 分子の区間と分母の floor は、同じ刻の物でなければならない。

    実測（2026-09-09 09:5x）: `pace()` が floor を 75.0 → 53.6分 に落とし、
    親は次の周から 55.6分 で回した（**そのときの floor の 1.04倍**）。
    ところが印字は `gap_median_min` 78.5 ÷ `floor` 53.3 ＝ **1.5**。
    §7 21:4x の覆る条件 (1)（1.25倍）は、**追随している親に対して鳴る**。
    """
    rounds(_round("2026-09-08T12:00:00+00:00")      # ↓ 80分（床 75）
           + _round("2026-09-08T13:20:00+00:00")    # ↓ 80分（床 75）
           + _round("2026-09-08T14:40:00+00:00")    # ↓ 56分（床 53・ここで床が落ちた）
           + _round("2026-09-08T15:36:00+00:00"))
    wakes([_go("2026-09-08T13:20:00+00:00", 75.0),
           _go("2026-09-08T14:40:00+00:00", 75.0),
           _go("2026-09-08T15:36:00+00:00", 53.0)])
    monkeypatch.setattr(nr, "floor_minutes", lambda: (53.0, "検査"))
    got = nr.decide(live=0)
    assert [round(x, 2) for x in nr.gap_ratios()] == [1.07, 1.07, 1.06]
    assert got["gap_over_floor"] == 1.07, got       # 追随している ＝ 1.25倍 で鳴らない
    assert got["gap_ratio_n"] == 3, got


def test_古い出し方だと同じ台帳で1_25倍を越える_これが踏んだ形(rounds, wakes, monkeypatch):
    """**陽性対照**: 「中央値 ÷ いまの floor」に戻すと、同じ台帳で門が鳴る。"""
    rounds(_round("2026-09-08T12:00:00+00:00")
           + _round("2026-09-08T13:20:00+00:00")
           + _round("2026-09-08T14:40:00+00:00")
           + _round("2026-09-08T15:36:00+00:00"))
    wakes([_go("2026-09-08T13:20:00+00:00", 75.0),
           _go("2026-09-08T14:40:00+00:00", 75.0),
           _go("2026-09-08T15:36:00+00:00", 53.0)])
    old = nr.gap_median() / 53.0                    # 80.0 ÷ 53.0
    assert old > 1.25                               # ← 21:4x の門が鳴る
    monkeypatch.setattr(nr, "floor_minutes", lambda: (53.0, "検査"))
    assert nr.decide(live=0)["gap_over_floor"] < 1.25   # ← 直したあとは鳴らない


def test_台帳より前の周は比に入れない(rounds, wakes, monkeypatch):
    """floor を持つ GO が結びつかない区間は、**捨てずに飛ばす**（数を作らない）。"""
    rounds(_round("2026-09-08T12:00:00+00:00")
           + _round("2026-09-08T13:20:00+00:00")
           + _round("2026-09-08T14:40:00+00:00"))
    wakes([_go("2026-09-08T14:40:00+00:00", 75.0)])  # 最後の周ぶんだけ
    assert len(nr.gap_ratios()) == 1
    monkeypatch.setattr(nr, "floor_minutes", lambda: (75.0, "検査"))
    assert nr.decide(live=0)["gap_ratio_n"] == 1


def test_周の時刻とGOの時刻が離れていたら結ばない(rounds, wakes):
    """GO は周を記録した直後に書かれる（実測 数秒）。離れた行を当てにいかない。"""
    rounds(_round("2026-09-08T12:00:00+00:00") + _round("2026-09-08T13:20:00+00:00"))
    wakes([_go("2026-09-08T13:40:00+00:00", 75.0)])   # 20分 ずれている
    assert nr.gap_ratios() == []
