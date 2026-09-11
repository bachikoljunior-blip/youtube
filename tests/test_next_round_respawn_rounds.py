"""**門を越えた窓には、出どころが 2つ 在る。** 片方（立て直し）に口がありませんでした。

2026-09-11 11:2x・optimizer・Opus。

§7 (d)（区間 ÷ 狙い先・門 **1.25**・**2つ 続いたら**）が、この回に **1.309** で 1つ目 を出しました。
中身は上限でも丸めでもなく、**429（monthly spend limit）で `hourly` を立て直した 17分** です:

    10:00:39  GO（`hourly` は fable）→ 10:0x に 429 が 2体 → 10:17:17 に opus で立て直し
    10:46:35  次の周  ＝ 周から周 **45.9分**（床 35.0分 ＝ **1.309倍**）
              立て直しの刻から数えると **29.3分**（床の下）

門を越えた窓の出どころは、いま 2つ:

    起こしが届かず心拍が拾った   → `wake_missed()` が名指しする（09/10 12:18 の 1.481）
    **429 の立て直し**           → **どこも名指ししていなかった**（この回）

名指しが無いと、次の回は **在りもしない上限を探しに行きます**（§7 21:4x が書いた型）。
＝ `respawn_rounds()` / `gap_over_gate()` を足し、`decide()` が毎周 台帳へ書き、
`next_round.py` の印字が門の行の下に出します（**手で突き合わせないこと**・`wake_missed` と同じ形）。

**区間は 1つ も落としません** —— 落とすと「2つ 続いたら」の分子ごと消え、
本物の上限が来た回に鳴らなくなります（§5 教訓の形 4つ目）。

**撃って落とした**（陽性対照・`.pyc` を消してから）:
寄せる幅（`RESPAWN_NEAR_MIN`）を外すと **2件**／`n > 1` を `n >= 1` にすると **4件**／
`gap_over_gate` が門を `>=` で読むと **1件**。
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import next_round as nr  # noqa: E402
import quota  # noqa: E402

JST = timezone(timedelta(hours=9))


def _marks(*hhmm):
    return [datetime(2026, 9, 11, h, m, s, tzinfo=JST) for h, m, s in hhmm]


def _rows(*items):
    return [{"at": datetime(2026, 9, 11, h, m, s, tzinfo=JST).isoformat(),
             "work_kind": f"{role}:leverage", "model": model}
            for h, m, s, role, model in items]


def test_同じ周に同じ役を_2度_立てた周を名指しする():
    """**この回に実際に踏んだ形**（10:00 の周に `hourly` が fable → opus）。"""
    marks = _marks((10, 0, 49), (10, 46, 35))
    rows = _rows((10, 0, 39, "hourly", "fable"),
                 (10, 0, 40, "optimizer", "opus"),
                 (10, 17, 17, "hourly", "opus"),      # 429 で立て直した
                 (10, 46, 35, "hourly", "opus"),
                 (10, 46, 35, "optimizer", "opus"))
    got = nr.respawn_rounds(marks=marks, rows=rows)
    assert [(m.hour, m.minute, r, n) for m, r, n in got] == [(10, 0, "hourly", 2)]


def test_1周に_1度_ずつなら何も出さない():
    marks = _marks((10, 0, 49), (10, 46, 35))
    rows = _rows((10, 0, 39, "hourly", "fable"),
                 (10, 0, 40, "optimizer", "opus"),
                 (10, 46, 35, "hourly", "opus"),
                 (10, 46, 35, "optimizer", "opus"))
    assert nr.respawn_rounds(marks=marks, rows=rows) == []


def test_周から遠い行は_どの周にも付けないこと():
    """**寄せる幅が無いと、周の台帳が薄い日の行が端の周へ積まれます**（実物で踏んだ形）。

    ここでは 4時間 前の 2行 を置きます —— いちばん近い周は 10:00 ですが、
    `RESPAWN_NEAR_MIN`（30分）より遠いので、**立て直しには数えません**。
    """
    marks = _marks((10, 0, 49),)
    rows = _rows((6, 0, 0, "hourly", "fable"),
                 (6, 30, 0, "hourly", "fable"))
    assert nr.respawn_rounds(marks=marks, rows=rows) == []


def test_last_で見る窓のぶんだけに絞れること():
    marks = _marks((8, 0, 0), (9, 0, 0), (10, 0, 49))
    rows = _rows((8, 0, 0, "hourly", "fable"), (8, 5, 0, "hourly", "fable"),
                 (10, 0, 39, "hourly", "fable"), (10, 17, 17, "hourly", "opus"))
    assert len(nr.respawn_rounds(marks=marks, rows=rows)) == 2
    assert len(nr.respawn_rounds(marks=marks, rows=rows, last=2)) == 1, \
        "直近 2周 だけに絞れること（古い塊を毎回 出さない）"


def test_門は_1か所で_越えた窓だけを返すこと(monkeypatch):
    monkeypatch.setattr(nr, "gap_ratios", lambda limit=10: [1.0, 1.25, 1.26, 0.99])
    monkeypatch.setattr(nr, "respawn_rounds", lambda **kw: [])
    g = nr.gap_over_gate()
    assert g["gate"] == nr.GAP_RATIO_GATE == 1.25
    assert g["over"] == [1.26], "門ちょうど（1.25）は越えていません"
    assert g["n_over"] == 1


def test_decide_が毎周_台帳へ書くこと(tmp_path, monkeypatch):
    """**手で突き合わせないこと** —— 次の回は撃つだけで読めること。"""
    monkeypatch.setattr(nr, "gap_ratios", lambda limit=10: [1.0, 1.4])
    monkeypatch.setattr(nr, "respawn_rounds",
                        lambda **kw: [(datetime(2026, 9, 11, 10, 0, 49, tzinfo=JST), "hourly", 2)])
    d = nr.decide(live=1)
    assert d["gap_over_gate"] == [1.4] and d["gap_over_gate_n"] == 1
    assert d["respawn_rounds"][0][1:] == ["hourly", 2]


def test_台帳が無くても落ちないこと(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", tmp_path / "none.jsonl")
    monkeypatch.setattr(quota, "ROUNDS_LOG", tmp_path / "none-rounds.jsonl")
    assert nr.respawn_rounds() == []


def test_壊れた行は飛ばすこと(tmp_path, monkeypatch):
    f = tmp_path / "model_choice.jsonl"
    f.write_text("{壊れている\n"
                 + json.dumps({"at": "2026-09-11T10:00:39+09:00", "work_kind": "hourly:leverage"}) + "\n"
                 + json.dumps({"work_kind": "hourly:leverage"}) + "\n"        # at が無い
                 + json.dumps({"at": "だめな刻", "work_kind": "hourly:leverage"}) + "\n"
                 + json.dumps({"at": "2026-09-11T10:17:17+09:00", "work_kind": "hourly:leverage"}) + "\n",
                 encoding="utf-8")
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", f)
    got = nr.respawn_rounds(marks=_marks((10, 0, 49),))
    assert [(r, n) for _, r, n in got] == [("hourly", 2)]


@pytest.mark.parametrize("role", ["hourly", "optimizer"])
def test_役ごとに数えること(role):
    marks = _marks((10, 0, 49),)
    rows = _rows((10, 0, 39, role, "fable"), (10, 17, 17, role, "opus"),
                 (10, 0, 40, "other", "opus"))
    assert [(r, n) for _, r, n in nr.respawn_rounds(marks=marks, rows=rows)] == [(role, 2)]
