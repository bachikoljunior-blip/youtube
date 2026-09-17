"""**尽きた日枠を「うちが」食べたのかを分ける**（2026-09-17 11:0x・optimizer・Opus・**API 0単位**）。

**踏んだ当のもの**: 09/16 16:00 の窓で、うちが撃った分は上端でも 160単位 なのに 10,000 が
尽きていました。それまで `stall` の `dry` の枝は「**オーナーの手は要りません・16:00 に戻ります**」
としか言えず、**戻っても同じことが起きるのに、誰も画面を見ない**形でした。

**陽性対照 3つ**（＝ 門が本当に効いているかを、逆向きにも当てる）:
 (1) 予約 5本（8,250単位）の窓では `ours` が True に戻る ＝ 09/16 04:3x の読みは今も正しい
 (2) 読みの行を増やすと上端が上がる ＝ `READ_UNITS_CEILING` が効いている
 (3) `dry` でない窓では、この枝は 1文字も出ない
"""
import datetime as dt

from studio import budget, stall
from studio.common import JST


def _t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=JST)


NOW = _t("2026-09-17T10:30:00")
HEAD = "2026-09-16T16:00:00+09:00"


def _reads(n, at="2026-09-16T16:49:51+09:00"):
    return [{"at": at, "event": "channel"}] + [
        {"at": at, "event": "views_over"} for _ in range(n - 1)
    ]


def test_読みだけの窓は上端でも半分に届かない():
    rows = _reads(16)
    c = budget.spent_ceiling(rows, NOW)
    assert c["writes"] == 0
    assert c["reads"] == 16
    assert c["total"] == 16 * budget.READ_UNITS_CEILING
    assert c["total"] < budget.DAY_UNITS // 2
    assert budget.ours(rows, NOW) is False


def test_予約5本の窓はうちが食べた側():
    """**陽性対照 1**: 09/16 04:3x の窓（`scheduled` 5本 ＝ 8,250単位）は今も `ours`。"""
    rows = [{"at": "2026-09-16T20:26:37+09:00", "event": "scheduled",
              "publish_at": "2026-09-17T19:00:00+09:00"} for _ in range(5)]
    assert budget.spent_ceiling(rows, NOW)["total"] >= budget.DAY_UNITS // 2
    assert budget.ours(rows, NOW) is True


def test_読みの数で上端が動く():
    """**陽性対照 2**: 数えているのが本当に読みの行なら、行を増やせば上端が上がる。"""
    a = budget.spent_ceiling(_reads(4), NOW)["total"]
    b = budget.spent_ceiling(_reads(40), NOW)["total"]
    assert b - a == 36 * budget.READ_UNITS_CEILING


def test_窓の頭より前の読みは数えない():
    rows = _reads(20, at="2026-09-16T15:59:00+09:00")
    assert budget.spent_ceiling(rows, NOW)["total"] == 0


#: きょう（09/17）の枠を埋める 1行。**(D) `slot_missed` を立てないため** ——
#: この検査が見たいのは (A) `mouth_gap` の `dry` の枝だけで、(D) が混ざると
#: `crushable` が 1件 に化けて `why` が「3分 後に再実行」へ移ります（実際に踏んだ）。
SLOT = {"at": "2026-09-17T09:00:00+09:00", "event": "scheduled",
        "publish_at": "2026-09-17T19:00:00+09:00"}


def _stall_rows(reads, dry=True):
    rows = _reads(reads) + [dict(SLOT)]
    if dry:
        rows += [{"at": "2026-09-16T19:01:08+09:00", "event": "quota_exceeded", "cmd": "status"}]
    return rows


def _rounds():
    return [{"round": i, "at": f"2026-09-17T0{i}:00:00+09:00"} for i in range(1, 7)]


def _sg(rows):
    return stall.signs(rows, _rounds(), NOW)


def test_うちじゃない窓の潰し手はオーナーの画面():
    out = _sg(_stall_rows(16))
    mouth = [s for s in out if s["code"] == "mouth_gap"]
    assert mouth, "mouth_gap の印が立っていません"
    s = mouth[0]
    assert s["dry"]
    assert s["dry_ours"] is False
    assert "Quotas" in s["crush"] and "オーナーの手" in s["crush"]
    assert "オーナーの手は要りません" not in s["crush"]


def test_うちが食べた窓は今までどおり訊きを置かない():
    """**陽性対照 1 の続き**: 8,250単位 の窓では、元の文（訊きは置かない）に戻ること。"""
    rows = [{"at": "2026-09-16T20:26:37+09:00", "event": "scheduled",
              "publish_at": "2026-09-17T19:00:00+09:00"} for _ in range(5)]
    rows += [{"at": "2026-09-16T19:01:08+09:00", "event": "quota_exceeded", "cmd": "status"}]
    rows += _reads(2, at="2026-09-16T16:49:51+09:00") + [dict(SLOT)]
    mouth = [s for s in _sg(rows) if s["code"] == "mouth_gap"]
    assert mouth
    assert mouth[0]["dry_ours"] is True
    assert "オーナーの手は要りません" in mouth[0]["crush"]


def test_間隔の行も2つに割れている():
    a = stall.state(_stall_rows(16), _rounds(), NOW)
    assert "訊きを置く" in a["why"]
    assert a.get("retry_min") is None

    rows = [{"at": "2026-09-16T20:26:37+09:00", "event": "scheduled",
              "publish_at": "2026-09-17T19:00:00+09:00"} for _ in range(5)]
    rows += [{"at": "2026-09-16T19:01:08+09:00", "event": "quota_exceeded", "cmd": "status"}]
    rows += _reads(2, at="2026-09-16T16:49:51+09:00") + [dict(SLOT)]
    b = stall.state(rows, _rounds(), NOW)
    assert "訊きは置かない" in b["why"]


def test_dryでない窓ではこの枝が出ない():
    """**陽性対照 3**: 403 の行が無ければ `dry` は立たず、文も変わらない。"""
    mouth = [s for s in _sg(_stall_rows(16, dry=False)) if s["code"] == "mouth_gap"]
    if mouth:
        assert not mouth[0]["dry"]
        assert "Quotas" not in mouth[0]["crush"]
