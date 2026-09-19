"""**出た本に、成果報酬の塊がまだ置かれていない**を `catchup` が数えて撃つ口
（2026-09-19 07:xx・optimizer・Opus 5・ultracode）。

**なぜこの検査が在るか（この回に数えた数）**: `data/studio/ledger.jsonl` の `measured` 65本 で、
ショートは生涯の再生の **93〜100% を最初の 48h** に受け取ります
（`vum9GV8Sp6c` 1,191回@30h → 1,219回@63.6h ＝ **97.7%**）。古い 54本 の いまの伸びは
**合計 47回/日** —— **後から置き直しても戻りません**（54本 に置くと 2,700単位 ＝ 本 1.6本ぶん）。
＝ **公開の瞬間に塊が無い本は、生涯の 9割 を成果報酬 0 のまま配り終えます。**

**既に 2つ 在ったのに届いていませんでした**:
`cta_gap_line` は `yt.published()`（API）が要る ＝ **日枠が尽きた周では落ちる**（置き忘れるのはその周）。
`cli cta` は **その回が思い出したときだけ**撃つ手。
**だから台帳だけで数え（0単位）、`catchup` の 1コマンドに載せます。**

**この検査が守っているのは 4つ**:
 (1) **台帳だけで数える**（`yt` を 1度も呼ばない ＝ 日枠 0 の周でも数えられる）
 (2) **新しい順**（`cmd_cta` の既定「再生の多い順」＝ もう配り終えた側 とは逆）
 (3) **置いた本・消えた本・`CTA_FAIL_CAP` 回 落ちた本は、二度と数えない**
 (4) **順は 打ち直し → コメント欄 → 透かし → 題**（コメント欄が透かしより先）
"""
from __future__ import annotations

import argparse
import datetime as dt

import pytest

from studio import cli
from studio.common import JST


def _sched(vid: str, sid: str, at: dt.datetime, title: str = "題") -> dict:
    return {"event": "scheduled", "video_id": vid, "id": sid,
            "publish_at": at.isoformat(), "title": title}


NOW = dt.datetime(2026, 9, 19, 12, 0, tzinfo=JST)


def _rows():
    """3本 予約ずみ（刻は過ぎている）・古い順に A→B→C。"""
    return [_sched("A", "s-a", dt.datetime(2026, 9, 19, 7, 0, tzinfo=JST)),
            _sched("B", "s-b", dt.datetime(2026, 9, 19, 10, 0, tzinfo=JST)),
            _sched("C", "s-c", dt.datetime(2026, 9, 18, 18, 0, tzinfo=JST))]


# ---- (1) 台帳だけ ----------------------------------------------------------

def test_台帳だけで数える_口を1度も呼ばない(monkeypatch):
    monkeypatch.setattr(cli.yt, "published", lambda *a, **k: pytest.fail("API を撃った"))
    monkeypatch.setattr(cli.yt, "channel", lambda *a, **k: pytest.fail("API を撃った"))
    assert cli.cta_pending(_rows(), NOW) == ["B", "A", "C"]


def test_刻が来ていない本は数えない():
    rows = _rows() + [_sched("D", "s-d", dt.datetime(2026, 9, 19, 18, 0, tzinfo=JST))]
    assert "D" not in cli.cta_pending(rows, NOW)


# ---- (2) 新しい順 ----------------------------------------------------------

def test_新しい順で返す_再生の多い順ではない():
    # **48h の註**: これから配られる側（新しい本）が先。
    assert cli.cta_pending(_rows(), NOW) == ["B", "A", "C"]


# ---- (3) 二度と数えない 3つ -------------------------------------------------

def test_置いた本は数えない():
    rows = _rows() + [{"event": "cta_comment", "video_id": "B", "id": "B"}]
    assert cli.cta_pending(rows, NOW) == ["A", "C"]


def test_消えた本は置き直さない():
    # `studio/asp.py` の覆る条件 (2) ＝ YouTube 側がリンクを落としている。
    rows = _rows() + [{"event": "comment_gone", "video_id": "A", "id": "A"}]
    assert "A" not in cli.cta_pending(rows, NOW)


def test_落ちた本は上限まで_そこで数えるのをやめる():
    rows = _rows() + [{"event": "cta_comment_failed", "video_id": "C", "id": "C"}]
    assert "C" in cli.cta_pending(rows, NOW)       # 1回 なら まだ撃つ
    rows += [{"event": "cta_comment_failed", "video_id": "C", "id": "C"}]
    assert cli.CTA_FAIL_CAP == 2
    assert "C" not in cli.cta_pending(rows, NOW)   # 2回 落ちたら 50単位 を毎周 捨てない


def test_出ていない本には置かない():
    # コメント欄がまだ無い（`pubcheck.missing` が鳴っている本）。
    assert cli.cta_pending(_rows(), NOW, skip={"B"}) == ["A", "C"]


def test_上げ直された前の版は数えない():
    rows = _rows() + [{"event": "scheduled", "video_id": "B2", "id": "s-b",
                       "publish_at": dt.datetime(2026, 9, 19, 11, 0, tzinfo=JST).isoformat(),
                       "title": "題", "replaced": "B"}]
    got = cli.cta_pending(rows, NOW)
    assert "B" not in got and "B2" in got


# ---- 1行（`status` のいちばん上・API 0単位） --------------------------------

def test_行が_詰まった手として名指しする(monkeypatch):
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [])
    monkeypatch.setattr(cli, "rename_pending", lambda rows: False)
    s = cli.catchup_line(_rows() + [{"event": "watermark_set"}], NOW)
    assert "コメント欄の一手 未 3本" in s
    assert "約151単位" in s          # 1（口の試し）+ 3×50


def test_全部置いてあれば0件(monkeypatch):
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [])
    monkeypatch.setattr(cli, "rename_pending", lambda rows: False)
    rows = _rows() + [{"event": "watermark_set"}] \
        + [{"event": "cta_comment", "video_id": v, "id": v} for v in ("A", "B", "C")]
    assert cli.catchup_line(rows, NOW).endswith("0件")


def test_1回に置く本数には蓋が在る(monkeypatch):
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [])
    monkeypatch.setattr(cli, "rename_pending", lambda rows: False)
    many = [_sched(f"V{i}", f"s-{i}", dt.datetime(2026, 9, 18, 6, 0, tzinfo=JST)
                   + dt.timedelta(hours=i)) for i in range(12)]
    assert cli.CTA_CATCHUP_MAX == 5
    assert "コメント欄の一手 未 5本" in cli.catchup_line(many + [{"event": "watermark_set"}], NOW)


# ---- (4) 順 ----------------------------------------------------------------

def test_順は_打ち直し_コメント欄_透かし_題(monkeypatch):
    """**コメント欄が透かしより先**（どちらも 50単位・向きが違う）。

    透かしが増やすのは 登録（扉(a)）で **実測 0.67人/日 ＝ 1,000人 まで 約1,460日**（期限の外）。
    コメント欄の塊が触るのは**門の外の分子** ＝ 期限の中で 1 を切りうる ただ 1本 の腕。
    **そして相手は 48h で消えます**（透かしの相手は消えません）。
    """
    calls = []
    bad = {"video_id": "X", "script": "s-x", "publish_at": NOW, "title": "題",
           "code": 401, "late_h": 30.0, "hint": ""}
    monkeypatch.setattr(cli, "now_jst", lambda: NOW)
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [bad])
    monkeypatch.setattr(cli.pubcheck, "taken_slots", lambda *a, **k: [])
    monkeypatch.setattr(cli, "next_long_slots",
                        lambda taken, now, n=3: [dt.datetime(2026, 9, 19, 19, 0, tzinfo=JST)])
    monkeypatch.setattr(cli, "ledger_rows", _rows)
    monkeypatch.setattr(cli, "rename_pending", lambda rows: True)
    monkeypatch.setattr(cli.yt, "channel", lambda: {"subscriberCount": 39, "viewCount": 1})
    monkeypatch.setattr(cli.yt, "readiness",
                        lambda vid: {"no_publish_at": True, "publish_at": None, "privacy": "private"})
    monkeypatch.setattr(cli, "cmd_reschedule", lambda ns: calls.append(("reschedule", ns.id)) or 0)
    # **チャンネルの説明欄は 打ち直しの次・コメント欄より先**（2026-09-19 09:xx・`asp.py`「チャンネルの説明欄」の註）——
    # 全部の本からアイコン 1タップで着く面・押せる・消えない。コメント欄の塊は本 1本 の面で 48h で相手が消える。
    monkeypatch.setattr(cli, "channel_desc_pending", lambda rows: True)
    monkeypatch.setattr(cli, "cmd_channel_desc", lambda ns: calls.append(("channel_desc",)) or 0)
    monkeypatch.setattr(cli, "cmd_cta", lambda ns: calls.append(("cta", ns.ids)) or 0)
    monkeypatch.setattr(cli, "cmd_watermark", lambda ns: calls.append(("watermark",)) or 0)
    monkeypatch.setattr(cli, "cmd_rename_channel", lambda ns: calls.append(("rename", ns.title)) or 0)
    assert cli.cmd_catchup(argparse.Namespace(dry_run=False)) == 0
    assert calls == [("reschedule", "s-x"), ("channel_desc",), ("cta", "B,A,C"), ("watermark",),
                     ("rename", cli.RENAME_TARGET)]


def test_dry_run_は_コメント欄も撃たない(monkeypatch, capsys):
    monkeypatch.setattr(cli, "now_jst", lambda: NOW)
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [])
    monkeypatch.setattr(cli, "ledger_rows", lambda: _rows() + [{"event": "watermark_set"}])
    monkeypatch.setattr(cli, "rename_pending", lambda rows: False)
    monkeypatch.setattr(cli, "channel_desc_pending", lambda rows: False)
    monkeypatch.setattr(cli, "cmd_cta", lambda *a, **k: pytest.fail("dry-run で撃った"))
    monkeypatch.setattr(cli.yt, "channel", lambda: pytest.fail("dry-run で口を撃った"))
    assert cli.cmd_catchup(argparse.Namespace(dry_run=True)) == 0
    assert "約151単位" in capsys.readouterr().out
    # 説明欄が未なら 51 足す（2026-09-19 09:xx）。
    monkeypatch.setattr(cli, "channel_desc_pending", lambda rows: True)
    monkeypatch.setattr(cli, "cmd_channel_desc", lambda *a, **k: pytest.fail("dry-run で撃った"))
    assert cli.cmd_catchup(argparse.Namespace(dry_run=True)) == 0
    assert "約202単位" in capsys.readouterr().out


# ---- 陽性対照（この検査が死んでいないこと） --------------------------------

def test_陽性対照_置いていなければ必ず出る():
    assert cli.cta_pending(_rows(), NOW), "置いていない本が在るのに 0本 と言った"


def test_陽性対照_1本も予約が無ければ0本():
    assert cli.cta_pending([{"event": "watermark_set"}], NOW) == []
