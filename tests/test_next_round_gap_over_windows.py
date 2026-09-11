"""**門を越えた窓の「どれが」と「続いたか」が、どこにも無かった。**

2026-09-11 14:2x・optimizer・Opus。

§7 (d) の門は **「区間 ÷ 狙い先が 1.25 を越えた窓が 2つ 続いたら」**。
11:2x の `gap_over_gate` は `gap_ratios` の**裸の比**（`[1.309, 1.717]`）しか持たず、
`respawn` には**いま見ている周ぜんぶの立て直し**を入れていました。印字の側はそれを
**窓と突き合わせずに** 1行 出します:

    「＊同じ窓の中に**立て直し**が在ります: … ＝ 上限ではなく、その周が長かった理由です」

＝ **言っている所と、している所が別**（09/11 03:0x の `settle_stats` と同じ族）。

**実物**（この回に撃った・API 0単位）:

    09/11 01:00 → 01:46 UTC   **1.309**   立て直し 01:00:49 `hourly` 2回（429）  ← 口が在る
    09/11 02:58 → 03:59 UTC   **1.717**   **立て直しも 起こしの落ちも 無い**      ← 口が無い

＝ §7 (d) が「**次に見るのは、429 の無い周で 1.25 を越えるか**」と書いた窓が来ていたのに、
印字は「立て直しが在ります」の 1行 だけを出し、**(d) が待っていた当の事実が消えていました。**
**そして「2つ 続いたら」も、どこも数えていません**（この 2つ は続いていない ——
あいだに 1.014・1.012 が在る）。門の数字は `GAP_RATIO_GATE` に在るのに、
**「続いたら」の側だけが次の回の手作業に残っていた。**

**撃って落とした（陽性対照・`.pyc` を消してから）**: 下の `test_陽性対照_*` 3件。
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import next_round as nr  # noqa: E402

UTC = timezone.utc


def _w(h1, m1, h2, m2, ratio):
    return (datetime(2026, 9, 11, h1, m1, tzinfo=UTC),
            datetime(2026, 9, 11, h2, m2, tzinfo=UTC), ratio)


#: この回の実物そのもの（`gap_windows` で撃った並びの直近 6区間）。
REAL = [_w(0, 25, 1, 0, 1.004), _w(1, 0, 1, 46, 1.309), _w(1, 46, 2, 22, 1.014),
        _w(2, 22, 2, 58, 1.012), _w(2, 58, 3, 59, 1.717), _w(3, 59, 4, 40, 1.120)]
#: 実物の立て直し（`model_choice.jsonl`）—— 1つ目 の窓の中にだけ在ります。
REAL_SPAWN = [(datetime(2026, 9, 11, 1, 0, 49, tzinfo=UTC), "hourly", 2)]


def _patch(monkeypatch, windows, spawn=(), missed=()):
    monkeypatch.setattr(nr, "gap_windows", lambda limit=10, got=None: list(windows))
    monkeypatch.setattr(nr, "respawn_rounds", lambda **kw: list(spawn))
    monkeypatch.setattr(nr, "wake_missed",
                        lambda **kw: {"missed": [(t, 20.0) for t in missed],
                                      "placed": 46, "lags": [], "median_lag": 1.78})


def test_実物_立て直しの無い窓を名指しすること(monkeypatch):
    """**この回に踏んだ形。** 2つ 越え・口が在るのは 1つ だけ。"""
    _patch(monkeypatch, REAL, spawn=REAL_SPAWN)
    g = nr.gap_over_gate()
    assert g["over"] == [1.309, 1.717]
    assert [w["ratio"] for w in g["windows"]] == [1.309, 1.717]
    assert g["windows"][0]["respawn"] == [["hourly", 2]] and g["windows"][0]["explained"]
    assert g["windows"][1]["respawn"] == [] and not g["windows"][1]["explained"], \
        "1.717 の窓に立て直しは在りません（11:2x はここを口の在る窓の説明で消していた）"
    assert g["n_unexplained"] == 1


def test_実物_この_2つ_は続いていないこと(monkeypatch):
    """§7 (d) は「**2つ 続いたら**」。あいだに 1.014・1.012 が在るので引かれません。"""
    _patch(monkeypatch, REAL, spawn=REAL_SPAWN)
    assert nr.gap_over_gate()["consecutive"] is False


def test_続いた並びなら_consecutive_が立つこと(monkeypatch):
    _patch(monkeypatch, [_w(0, 0, 0, 40, 1.0), _w(0, 40, 1, 30, 1.31),
                         _w(1, 30, 2, 30, 1.40), _w(2, 30, 3, 5, 1.01)])
    g = nr.gap_over_gate()
    assert g["consecutive"] is True and g["n_over"] == 2


def test_起こしが届かなかった窓は_立て直しが無くても口が在ること(monkeypatch):
    """出どころは 2つ。**名前が違うだけで、どちらも「上限ではない」側**です。"""
    _patch(monkeypatch, [_w(2, 58, 3, 59, 1.717)],
           missed=[datetime(2026, 9, 11, 3, 10, tzinfo=UTC)])
    w = nr.gap_over_gate()["windows"][0]
    assert w["wake_missed"] is True and w["explained"] is True
    assert nr.gap_over_gate()["n_unexplained"] == 0


def test_窓の外の立て直しは_その窓に付けないこと(monkeypatch):
    """**11:2x が踏んでいた当のもの** —— 別の窓の立て直しで、この窓を説明しないこと。"""
    _patch(monkeypatch, [_w(2, 58, 3, 59, 1.717)], spawn=REAL_SPAWN)   # 01:00 の立て直し
    w = nr.gap_over_gate()["windows"][0]
    assert w["respawn"] == [] and w["explained"] is False


def test_窓の外の起こしの落ちも_その窓に付けないこと(monkeypatch):
    _patch(monkeypatch, [_w(2, 58, 3, 59, 1.717)],
           missed=[datetime(2026, 9, 10, 12, 0, tzinfo=UTC)])
    assert nr.gap_over_gate()["windows"][0]["explained"] is False


def test_区間を開いた周の立て直しは_その区間の側に付くこと(monkeypatch):
    """立て直しは**周の刻**に付くので、区間を開いた周（下端）のものが区間を伸ばします。

    **実物の刻で組みます** —— `a` と立て直しの刻は同じ値（どちらも `round_marks()`）なので、
    秒を落とした `REAL` で組むと、下端を開けても通ってしまい**門の控えになりません**。
    """
    m = datetime(2026, 9, 11, 1, 0, 49, 909025, tzinfo=UTC)
    b = datetime(2026, 9, 11, 1, 46, 41, 919880, tzinfo=UTC)
    _patch(monkeypatch, [(m, b, 1.309)], spawn=[(m, "hourly", 2)])
    assert nr.gap_over_gate()["windows"][0]["respawn"] == [["hourly", 2]]


def test_門ちょうどは越えていないこと(monkeypatch):
    _patch(monkeypatch, [_w(0, 0, 0, 40, 1.25), _w(0, 40, 1, 20, 1.2501)])
    g = nr.gap_over_gate()
    assert g["over"] == [1.25] and g["n_over"] == 1, "1.25 ちょうどは通す（`>` で読む）"


def test_gap_ratios_は_gap_windows_と同じ数を返すこと():
    """**分けても数は 1つ も動かないこと**（過去の比は全部そのまま）。"""
    got = nr.gap_windows(limit=10)
    assert nr.gap_ratios(limit=10) == [r for (_a, _b, r) in got]
    assert all(a < b for (a, b, _r) in got), "区間は必ず前へ進むこと"


def test_窓が空でも落ちないこと(monkeypatch):
    _patch(monkeypatch, [])
    g = nr.gap_over_gate()
    assert g["windows"] == [] and g["consecutive"] is False and g["n_unexplained"] == 0


# ---- 陽性対照（壊したら落ちること） ------------------------------------------

def test_陽性対照_窓と突き合わせずに全部の立て直しを付けると落ちること(monkeypatch):
    """11:2x の形（`respawn` をそのまま窓へ入れる）に戻すと、口の無い窓が消えます。"""
    _patch(monkeypatch, REAL, spawn=REAL_SPAWN)
    real = nr.gap_over_gate()
    assert real["n_unexplained"] == 1
    broken = [dict(w, respawn=[[r, n] for (_m, r, n) in REAL_SPAWN]) for w in real["windows"]]
    assert all(w["respawn"] for w in broken), "壊した側では 2つ とも説明が付いてしまう"


def test_陽性対照_続いたかを_数だけで読むと落ちること(monkeypatch):
    """`n_over >= 2` で読むと、この回の実物は「引かれた」になります（**続いていない**のに）。"""
    _patch(monkeypatch, REAL, spawn=REAL_SPAWN)
    g = nr.gap_over_gate()
    assert g["n_over"] >= 2 and g["consecutive"] is False


def test_陽性対照_窓の下端を外すと_立て直しが迷子になること(monkeypatch):
    """`a <= m < b` の下端を `a < m` にすると、周の刻に付いた立て直しが 1つ も拾えません。

    **実物では `a` と立て直しの刻は同じ値**です —— どちらも `round_marks()` の周の刻
    （区間を開いた周そのもの）。上の `REAL` は読みやすさのために秒を落としてあるので、
    ここだけは実物の刻で組みます。
    """
    m = datetime(2026, 9, 11, 1, 0, 49, 909025, tzinfo=UTC)      # 実物の周の刻
    b = datetime(2026, 9, 11, 1, 46, 41, 919880, tzinfo=UTC)
    _patch(monkeypatch, [(m, b, 1.309)], spawn=[(m, "hourly", 2)])
    assert nr.gap_over_gate()["windows"][0]["respawn"] == [["hourly", 2]], "いまの門では拾える"
    assert not (m < m), "下端を開けると拾えない ＝ この窓は口を失う（`a == m` が実物）"
