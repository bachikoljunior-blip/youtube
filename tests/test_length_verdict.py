"""`src/length_verdict.py` の検査。

**先に「既知の当たり」を1件固定してあります**（`docs/trigger_main.md` §4）——
2026-08-20 12:3x に Analytics から実際に返った数字です。道具がこれを外したら、
中央値がいくら綺麗に出ても意味がありません。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src import length_verdict as lv


JST = timezone(timedelta(hours=9))


def _at(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=JST)


# --- 既知の当たり（2026-08-20 12:3x に Analytics が返した実測） --------------

#: 30秒設計6本の (video, views, engagedViews)。**この6本で中央値 24.7%。**
KNOWN_NEW = [
    {"video": "7b2-Z6Jw5DQ", "views": 1360, "engagedViews": 534},
    {"video": "CdX2oIb7BG8", "views": 1451, "engagedViews": 584},
    {"video": "NHKylqsNfTw", "views": 1864, "engagedViews": 521},
    {"video": "_4zhMy-VIyg", "views": 608, "engagedViews": 130},
    {"video": "crO3FUvL2NI", "views": 1041, "engagedViews": 216},
    {"video": "nPzWa_yhoQ0", "views": 315, "engagedViews": 46},
]

#: 旧設計のうち、**再生1〜4回で engaged 比率が 100% になった5本**。
#: この5本を入れると旧設計の中央値が 34.7% → 39.0% に持ち上がる。
KNOWN_OLD_NOISE = [
    {"video": "FcrqwSTZ7Kc", "views": 2, "engagedViews": 2},
    {"video": "G3VqIFpBwKo", "views": 3, "engagedViews": 3},
    {"video": "YHiigJ3Zpj4", "views": 1, "engagedViews": 1},
    {"video": "m_q1G_GNgY8", "views": 4, "engagedViews": 4},
    {"video": "qm-w6nVwMhY", "views": 1, "engagedViews": 1},
]


def test_既知の当たり_30秒設計6本の中央値は24点7パーセント():
    r = lv.ratios(KNOWN_NEW)
    assert len(r) == 6
    assert lv._median(list(r.values())) == pytest.approx(0.2469, abs=0.001)


def test_既知の当たり_再生1桁の本は落ちる():
    """**この5本は5本とも比率 100%。** 落とさないと比べる相手が偽物になる。"""
    assert lv.ratios(KNOWN_OLD_NOISE) == {}
    # 下限を 1 に緩めると、5本とも 100% で入ってくる（実測の再現）
    loose = lv.ratios(KNOWN_OLD_NOISE, min_views=1)
    assert len(loose) == 5
    assert all(v == 1.0 for v in loose.values())


# --- 群の切り方 -------------------------------------------------------------

def test_群は日付で切る_本数は写さない():
    pub = {
        "old1": _at("2026-08-04T09:00:00"),
        "old2": _at("2026-08-15T23:59:00"),
        "new1": _at("2026-08-16T00:00:00"),
        "new2": _at("2026-08-18T21:00:00"),
        "out1": _at("2026-08-03T23:00:00"),
        "out2": _at("2026-08-19T00:00:00"),
    }
    old, new = lv.groups(pub)
    assert old == ["old1", "old2"]
    assert new == ["new1", "new2"]


def test_境界はJSTで見る_UTCで見ると1日ずれる():
    """UTC 2026-08-15T16:00Z は **JST では 8/16 01:00** ＝ 30秒設計の側。"""
    pub = {"v": datetime(2026, 8, 15, 16, 0, tzinfo=timezone.utc)}
    old, new = lv.groups(pub)
    assert (old, new) == ([], ["v"])


# --- 判定そのもの -----------------------------------------------------------

def test_同点は外れ():
    assert lv.verdict([0.3, 0.3, 0.3], [0.3, 0.3, 0.3])["upheld"] is False


def test_上回れば当たり():
    assert lv.verdict([0.1, 0.2, 0.3], [0.4, 0.5, 0.6])["upheld"] is True


def test_届いていない本は上下に置いて挟む_挟んで同じなら判定できる():
    out = lv.verdict([0.9, 0.9, 0.9], [0.1, 0.1], missing=1)
    assert out["decided"] is True and out["upheld"] is False
    assert out["median_new_low"] <= out["median_new_high"]


def test_届いていない本で答えが変わるなら判定しない():
    """**期限は延ばさず、条件も変えない。**『判定できない』とだけ言う。"""
    out = lv.verdict([0.5], [0.4, 0.45], missing=2)
    assert out["decided"] is False
    assert out["upheld"] is None


def test_片方の群が空なら判定しない():
    assert lv.verdict([], [0.5, 0.6])["decided"] is False


# --- 線の産物でないか -------------------------------------------------------

def test_下限を振っても答えが変わらないことを見る():
    rows = KNOWN_NEW + KNOWN_OLD_NOISE + [
        {"video": "o1", "views": 800, "engagedViews": 320},   # 40.0%
        {"video": "o2", "views": 900, "engagedViews": 315},   # 35.0%
        {"video": "o3", "views": 700, "engagedViews": 245},   # 35.0%
    ]
    old = [r["video"] for r in KNOWN_OLD_NOISE] + ["o1", "o2", "o3"]
    new = [r["video"] for r in KNOWN_NEW]
    got = lv.sweep(rows, old, new, thresholds=(1, 30))
    assert [row["upheld"] for row in got] == [False, False]
    # 下限 1 のほうが旧設計の中央値は高く出る（100% の5本が入るので）
    assert got[0]["median_old"] > got[1]["median_old"]


def test_既知の当たり_外れても逆向きは立たない():
    """`falsified_if` が言えるのは「上回らなかった」まで。**逆は別の証拠が要る。**

    数字は 2026-08-20 12:3x の実測そのもの（再生30以上・旧15本 対 新6本）。
    中央値は 34.7% 対 24.7% で**外れ**だが、順位和の片側 p は **0.393**
    ＝ **「30秒が悪い」とは言えない。** ここを取り違えると、
    立っていない証拠で尺を戻す作業に賭けることになる。
    """
    old = [0.468, 0.191, 0.173, 0.365, 0.122, 0.457, 0.131, 0.347,
           0.398, 0.217, 0.390, 0.180, 0.288, 0.443, 0.390]
    new = [0.393, 0.402, 0.280, 0.214, 0.207, 0.146]
    assert lv._median(old) == pytest.approx(0.347, abs=0.001)
    assert lv._median(new) == pytest.approx(0.247, abs=0.001)
    assert lv.verdict(old, new)["upheld"] is False          # 外れ
    assert lv.reverse_p(old, new) == pytest.approx(0.393, abs=0.005)
    assert lv.reverse_p(old, new) > 0.20                    # だが逆向きは立たない


# --- API を叩かないこと -----------------------------------------------------

def test_群の切り分けと判定はAPIを叩かない(monkeypatch):
    def _boom(*a, **k):  # pragma: no cover - 呼ばれたら失敗
        raise AssertionError("API を叩きました")

    monkeypatch.setattr(lv, "fetch_engaged", _boom)
    lv.groups({"v": _at("2026-08-17T09:00:00")})
    lv.ratios(KNOWN_NEW)
    lv.verdict([0.3], [0.2])
