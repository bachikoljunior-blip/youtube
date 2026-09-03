"""**予約の付いた本を、焼き直して枠ごと差し替える**（2026-09-04 06:5x）。

## なぜ要ったか（実測）

`rebake_plan()` は長らく **`if scheduled: return`** で、**一度 枠へ置いた本を
未来永劫 焼き直しませんでした。** 09/04 09:00 に出る `1huadpEk6HY` は 09/03 04:37 の
焼きのままで、そのあと入ったコード 6件（登録の依頼を説明欄／コメント／画面へ・
GPT Image 2.0 の絵）が **1つも入っていません**。
`rebake_plan_for(09/04)` は毎周 `do: False` を返し、
**規則3（次の枠の1本を良くし続ける）の当てどころが、毎周 選択肢から消えていました。**

断っていたのは `--replaces` の**重なりの検査**だけです（`scripts/upload_only.py`:
「private・予約なし ＝ 公開の並びに入っていない本」しか突き合わせから外さない）。
**予約を外せば通る** —— 問題は外す時刻でした:

    先に外す  焼く 30〜60分 のあいだ その日が 0本（焼く側が死んだら公開が飛ぶ。実測 3回連続で死んでいる）
    後で外す  外す→上げる→置く の 2〜5分 だけ 0本   ← いまの形（`takeover`）

## この検査が押さえている3つ

1. `scheduled=True` でも `do` が立ち、`takeover` の印が付くこと
2. 差し替えの窓（`_takeover_mark`）が在るあいだ、`place_today` が**置かない**こと
   —— 置くと旧 ID が枠へ戻り、直後の `--move 新` が規則1（1日1本）で弾かれる
3. その印が `TAKEOVER_STALE` より古ければ**無視される**こと
   —— 焼く側が器ごと消えた回に、印だけ残って**その日が永久に空**になるほうが高い
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scripts import ahead_sweep

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 4, 3, 15, tzinfo=JST)
SLOT = datetime(2026, 9, 4, 9, 0, tzinfo=JST)
CAND = {"video_id": "V1", "why": "[きょうの1本] 長尺 `t`"}


def _plan(**kw) -> dict:
    args = {
        "cur": {"video_id": "V1", "topic": "t"},
        "stash_text": '{"a": 1}',
        "draft_text": '{"a": 2}',
        "draft_newer": True,
        "attempted": False,
        "scheduled": False,
        "slot_at": SLOT,
        "now": NOW,
    }
    args.update(kw)
    return ahead_sweep.rebake_plan(**args)


def test_予約つきでも焼く_印は_takeover() -> None:
    p = _plan(scheduled=True)
    assert p["do"] is True
    assert p["takeover"] is True
    assert "予約つき" in p["why"]


def test_枠の線は予約つきでも効く() -> None:
    """**焼き上がる前に出てしまう本は、予約が付いていても焼かない。**

    `takeover` は「外す時刻を後ろへずらす」だけで、**焼く時間そのものは要ります。**
    """
    close = NOW + ahead_sweep.REBAKE_LEAD - timedelta(minutes=1)
    p = _plan(scheduled=True, slot_at=close)
    assert p["do"] is False and "焼き上がる前" in p["why"]


def test_差し替えの窓では置かない() -> None:
    plan = ahead_sweep.today_plan(
        NOW, count=0, cap=1, candidate=CAND, hour=9, quota_open=True,
        rule_on=True, paused="", insert_ok=True, takeover_pending=True)
    assert plan["do"] is False
    assert "差し替えの途中" in plan["why"]


def test_窓が無ければ普通に置く() -> None:
    plan = ahead_sweep.today_plan(
        NOW, count=0, cap=1, candidate=CAND, hour=9, quota_open=True,
        rule_on=True, paused="", insert_ok=True, takeover_pending=False)
    assert plan["do"] is True and plan["video_id"] == "V1"


def test_古い印は無視する(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    day = "2026-09-04"
    mark = ahead_sweep._takeover_mark(day)
    now = datetime(2026, 9, 4, 3, 15, tzinfo=timezone.utc)

    mark.write_text((now - timedelta(minutes=1)).isoformat() + "\n", encoding="utf-8")
    assert ahead_sweep.takeover_in_flight(day, now=now) is True

    mark.write_text((now - ahead_sweep.TAKEOVER_STALE - timedelta(minutes=1)).isoformat() + "\n",
                    encoding="utf-8")
    assert ahead_sweep.takeover_in_flight(day, now=now) is False

    mark.unlink()
    assert ahead_sweep.takeover_in_flight(day, now=now) is False


def test_印が壊れていても止めない(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**読めない印で、その日の公開を止めないこと。**"""
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    ahead_sweep._takeover_mark("2026-09-04").write_text("なんだこれ\n", encoding="utf-8")
    assert ahead_sweep.takeover_in_flight("2026-09-04") is False


def test_焼きが長引いたら引き継がない(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    """**焼き終えた「いま」で、もう一度 枠までを測ること。**

    枠の線（`REBAKE_LEAD`）を見たのは**焼く前**です。焼きが長引けば、引き継ぎに入る
    時点で枠が目の前（か、過ぎている）ことがあります。そこで予約を外すと
    **その日の公開が遅れるか、飛びます。** 間に合わない回は引き継がず、
    旧い本を予定どおり出し、**印を落として次の回に譲ります**（`done` を残すと
    `rebake_attempted()` が「焼いた」と読み、同じ台本は二度と焼かれません）。
    """
    calls: list[list[str]] = []
    notes: list[dict] = []
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    monkeypatch.setattr(ahead_sweep, "_rebake_note", lambda row, root=None: notes.append(row))
    monkeypatch.setattr(ahead_sweep, "_run", lambda cmd, *a, **k: (calls.append(cmd), 0)[1])
    monkeypatch.setattr(ahead_sweep, "_run_out",
                        lambda cmd, *a, **k: (calls.append(cmd), (0, "VIDEO_ID NEW1"))[1])
    # 枠は 5分 後（線 `TODAY_LEAD_MIN` = 20分 より近い）
    soon = datetime.now(timezone.utc).astimezone(JST) + timedelta(minutes=5)
    monkeypatch.setattr(ahead_sweep, "_slot_of", lambda v: soon.strftime("%Y-%m-%dT%H:%M"))

    rc = ahead_sweep.rebake_run("OLD1", "t", "sha1", takeover=True)

    out = capsys.readouterr().out
    assert "引き継ぎません" in out
    # **予約を外していないこと**（外すと、その日の公開が飛ぶ）
    assert not any("--unschedule" in " ".join(c) for c in calls)
    # **上げてもいないこと**（`--replaces` は予約つきを断るので、どのみち落ちる）
    assert not any("upload_only.py" in " ".join(c) for c in calls)
    # **`done` ではなく `late`** ＝ 次の回が、余裕のある枠でもう一度 焼ける
    kinds = [n.get("kind") for n in notes]
    assert "late" in kinds and "done" not in kinds
    assert rc == 0


def test_同じ題材の下書きを全部replacesに渡す(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """**3本目の焼き直しは、「1つ前」を外しても「2つ前」に `same-topic` で当たります。**

    実測 2026-09-04（焼き上がる前に気づいた）: 題材
    `nenkin-uketorikata-65-70-75-handan` の下書きは `dRZnZrRy2Lw`（09/02・予約なし）と
    `DfFyu8qZq3I`（09/03・予約なし）の 2本。走っていた焼きは
    `--replaces DfFyu8qZq3I` の1本だけを渡すので、**75分 かけて焼いたあと、
    引数1つで断られます** —— いちばん高い所を払ってから、いちばん安い所で落ちる形。

    `src/dupes.blocking()` の `exclude` は 2026-09-02 に複数を受けるよう直っており、
    `scripts/upload_only.py` も `--replaces a,b` を受けます。**渡す側だけが 1本のままでした。**
    """
    root = tmp_path
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "uploaded.jsonl").write_text(
        '{"video_id": "OLD1", "topic": "t"}\n'
        '{"video_id": "CUR", "topic": "t"}\n'
        '{"video_id": "OTHER", "topic": "other"}\n'
        '{"video_id": "BOOKED", "topic": "t"}\n',
        encoding="utf-8")
    # `BOOKED` だけ予約つき。**予約つきは混ぜないこと** ——
    # `drop_replaced()` は private・予約なし しか外さず、1本でも欠けたら全部 断るので、
    # 混ぜるとこの関数のせいで上げられなくなる。
    monkeypatch.setattr(ahead_sweep, "_slot_of",
                        lambda v: "2026-09-05T09:00" if v == "BOOKED" else "")
    got = ahead_sweep.same_topic_drafts("CUR", "t", root=root)
    assert got[0] == "CUR"                    # 先頭は必ず本人
    assert "OLD1" in got                      # 「2つ前」も外す
    assert "BOOKED" not in got                # 予約つきは混ぜない
    assert "OTHER" not in got                 # 別の題材は混ぜない
