"""**「心拍」と呼んでいた 17.5分 は、心拍ではありませんでした。**

2026-09-11 15:0x・optimizer・Opus。

`heartbeat_minutes()` は `data/parent_wakes.jsonl` の **親の起きの間隔の中央値**を返し、
`decide()` も `wake_missed` の註も、それを**心拍**と呼んでいます（いま 17.5分）。
**台帳の実物は 3つ の別々の口でした**（`wake_sources`・API 0単位・219本）:

    置いた起こしが届いた   67本
    サブの終わりの届き    107本
    **心拍**              **45本**（毎時 :59 ＝ `docs/trigger_parent.md` の
                          `trig_01CTzKURfdS5LLHPGepXRwvt`・**毎時59分**）

＝ **17.5分 は「起こしの鎖が回っているときの刻み」で、鎖が落ちたときの刻みではありません。**
鎖が落ちた回の刻みは **心拍 1本ぶん ＝ 60分**。
`wake_missed` の註が「落ちても心拍が拾う（**頭打ち 40分 ＝ 心拍 2つ ぶん**）」と書いて
口を直さない判断をした、その **40分 が「起きの間隔の中央値 ×2」**でした。

**効き目**（§7 (d)）: 14:2x の回が「**口が在りません**」と名指しした窓
（09/11 02:58→03:59 UTC・区間 ÷ 狙い先 **1.717**）は、
**02:59:52 → 03:59:41 の 59.8分**（心拍から心拍まで、ほかの起きが **0本**）を丸ごと含みます。
＝ **口が無かったのではなく、こちらが 3つ目の口を持っていなかっただけ**でした。

**14:2x が書いた「置かれなかった起こし」は、口ではありません**（この回に数え直した）:
`wake_placed` の欄が無い WAIT は **15回 とも `live >= 1`** ＝ `decide()` は
**0体 の枝でしか起こしを置きません**（走っているサブの終わりが親を起こすから）。
そして **14回 は 区間 ÷ 床 が 0.98〜1.06** ＝ 周の間隔には出ていません。

**撃って落とした（陽性対照・`.pyc` を消してから）**: 下の `test_陽性対照_*` 3件。
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import next_round as nr  # noqa: E402

UTC = timezone.utc


def _row(h, m, s=0, wake_at=None, placed=None, day=11):
    row = {"who": "owner", "at": datetime(2026, 9, day, h, m, s, tzinfo=UTC).isoformat()}
    if wake_at is not None:
        row["wake_at"] = wake_at.isoformat()
    if placed is not None:
        row["wake_placed"] = placed
    return row


def _beats(n=24, minute=59):
    """心拍だけの台帳（分の位を数えられる本数まで）。"""
    return [_row((h % 24), minute, day=10 + h // 24) for h in range(n)]


def test_心拍の分の位は台帳から数えること():
    """**写しを持たない形**（`heartbeat_minutes` と同じ）。分の位を :17 にしても付いてくること。"""
    got, src = nr.beat_minute(_beats(minute=17))
    assert got == 17 and "実測" in src


def test_行が薄い回は写しへ落ちること():
    got, src = nr.beat_minute(_beats(n=3))
    assert got == nr.BEAT_MINUTE_FALLBACK and "写し" in src


def test_分の位は_60分_で回して読むこと():
    at = datetime(2026, 9, 11, 3, 0, 39, tzinfo=UTC)
    assert nr._near_minute(at, 59) is True, ":00:39 は :59 の心拍（跨いだ側）"
    assert nr._near_minute(at, 30) is False


def test_出どころを_3つ_に分けること():
    """置いた起こし（届いた）・心拍・サブの終わりの届き。"""
    want = datetime(2026, 9, 11, 2, 30, tzinfo=UTC)
    rows = _beats() + [_row(2, 20, wake_at=want, placed=True),
                       _row(2, 31, 45),                 # 置いた起こしが届いた
                       _row(2, 45),                     # サブの終わりの届き
                       _row(2, 59, 10)]                 # 心拍
    kinds = {s["at"][11:19]: s["kind"] for s in nr.wake_sources(rows)}
    assert kinds["02:31:45"] == "placed"
    assert kinds["02:45:00"] == "sub"
    assert kinds["02:59:10"] == "beat"


def test_撃っていない起こしは_届いたことにしないこと():
    """`wake_placed` が False の行は撃っていません（`wake_is_fresh` の門）。"""
    want = datetime(2026, 9, 11, 2, 30, tzinfo=UTC)
    rows = _beats() + [_row(2, 20, wake_at=want, placed=False), _row(2, 31)]
    kinds = {s["at"][11:19]: s["kind"] for s in nr.wake_sources(rows)}
    assert kinds["02:31:00"] == "sub"


def test_心拍は_1刻に_1本だけ数えること():
    """実測 09/10 19:59:53 と 20:00:36（43秒 差）—— 2本目 はサブの終わりの届きです。"""
    rows = _beats() + [_row(19, 59, 53), _row(20, 0, 36)]
    kinds = {s["at"][11:19]: s["kind"] for s in nr.wake_sources(rows)
             if s["at"].startswith("2026-09-11")}
    assert kinds["19:59:53"] == "beat" and kinds["20:00:36"] == "sub"
    assert [g for g in nr.beat_only_gaps(rows) if g["gap_min"] < 30.0] == [], \
        "43秒 の窓を「心拍だけの窓」に数えないこと"


def test_鎖が落ちた窓は_心拍_1本ぶんで立つこと():
    """実物の形（09/11 02:59:52 → 03:59:41・あいだに起きが 0本）。"""
    rows = _beats() + [_row(2, 59, 52), _row(3, 59, 41)]
    got = [g for g in nr.beat_only_gaps(rows) if g["from"].startswith("2026-09-11T02:59")]
    assert len(got) == 1 and 55.0 <= got[0]["gap_min"] <= 65.0


def test_心拍だけの窓は_あいだに何も無い時だけ立つこと():
    """同じ 2つ の心拍でも、あいだにサブの終わりが 1本 在れば鎖は落ちていません。"""
    rows = _beats() + [_row(2, 59, 52), _row(3, 20), _row(3, 59, 41)]
    got = [g for g in nr.beat_only_gaps(rows) if g["from"].startswith("2026-09-11T02:59")]
    assert got == [], "あいだに `sub` が在れば、鎖は落ちていません"


def test_実物の台帳では_3窓_だけで_どれも心拍_1本ぶんであること():
    """**この回の実測**（219本）。長さは 60.0・58.7・59.8分。

    件数は増えてよい（増えたら覆る条件 (1) が鳴る側）が、
    **「心拍 1本ぶんより長い窓」は別の話**（覆る条件 (2)）なので、そこだけ締めます。
    """
    got = nr.beat_only_gaps()
    assert got, "実物の台帳に 1窓 も無いなら、分け方が壊れています"
    assert all(40.0 <= g["gap_min"] <= 75.0 for g in got), [g["gap_min"] for g in got]


def test_届きの窓を振っても答えが動かないこと():
    """`WAKE_LAND_MIN` は測った穴の中（0.65〜7.9分 の外）に置いてあります。"""
    keep = nr.WAKE_LAND_MIN
    try:
        got = []
        for w in (2.0, 5.0, 8.0, 12.0, 15.0):
            nr.WAKE_LAND_MIN = w
            got.append([g["gap_min"] for g in nr.beat_only_gaps()])
    finally:
        nr.WAKE_LAND_MIN = keep
    assert all(g == got[0] for g in got), got


# ---- 陽性対照（壊したら落ちること） ------------------------------------------

def test_陽性対照_心拍を_1刻に_2本_数えると_43秒の窓が立つこと(monkeypatch):
    """「1刻に 1本」を外すと、心拍の直後のサブの終わりが 2本目 の心拍に化けます。"""
    rows = _beats() + [_row(19, 59, 53, day=10), _row(20, 0, 36, day=10)]
    real = nr._wake_kinds

    def broken(own, minute=None):
        kinds = real(own, minute)
        for i, r in enumerate(own):
            at = nr._at(r)
            if kinds[i] == "sub" and at is not None and minute is not None \
                    and nr._near_minute(at, minute):
                kinds[i] = "beat"           # 1刻に何本でも
        return kinds

    monkeypatch.setattr(nr, "_wake_kinds", broken)
    got = [g for g in nr.beat_only_gaps(rows) if g["gap_min"] < 5.0]
    assert got, "門を外したのに 43秒 の窓が立たないなら、この検査は何も守っていません"


def test_陽性対照_置いた起こしを数えないと_心拍だけの窓が増えること(monkeypatch):
    """`placed` を落とすと、置いた起こしの届きが `sub` へ流れます（＝ 窓は増えない側）。

    **逆向きの控え**: `sub` を全部 `beat` に読むと、窓が実測の 3つ より増えること。
    """
    real = nr._wake_kinds

    def broken(own, minute=None):
        kinds = real(own, minute)
        return [("beat" if k == "sub" and minute is not None else k) for k in kinds]

    monkeypatch.setattr(nr, "_wake_kinds", broken)
    assert len(nr.beat_only_gaps()) > 3


def test_陽性対照_窓の突き合わせを外すと_口の無い窓が消えること(monkeypatch):
    """`gap_over_gate` の側 —— 別の窓の「心拍だけの窓」で、この窓を説明しないこと。"""
    a = datetime(2026, 9, 11, 2, 58, tzinfo=UTC)
    b = datetime(2026, 9, 11, 3, 59, tzinfo=UTC)
    far = [{"from": datetime(2026, 9, 8, 8, 59, tzinfo=UTC).isoformat(),
            "at": datetime(2026, 9, 8, 9, 59, tzinfo=UTC).isoformat(), "gap_min": 60.0}]
    monkeypatch.setattr(nr, "gap_windows", lambda limit=10, got=None: [(a, b, 1.717)])
    monkeypatch.setattr(nr, "respawn_rounds", lambda **kw: [])
    monkeypatch.setattr(nr, "wake_missed",
                        lambda **kw: {"missed": [], "placed": 46, "lags": [],
                                      "median_lag": 1.78})
    monkeypatch.setattr(nr, "beat_only_gaps", lambda *a_, **kw: list(far))
    assert nr.gap_over_gate()["n_unexplained"] == 1, \
        "09/08 の窓で 09/11 の窓を説明しないこと（14:2x が踏んだ形と同じ族）"
