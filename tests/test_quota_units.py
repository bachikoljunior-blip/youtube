"""**日枠を「回数」ではなく「単位」で数えること。**

2026-08-27 の実測（窓 08/27 07:00Z〜）:

    videos.update  269回 × 50 = 13,450単位
    thumbnails.set  10回 × 50 =    500単位
    ------------------------------------------
                               13,950単位 で 403

`videos.insert` は**この枠に入っていません** —— 最初の 403 は 07:47Z なのに、
10:33Z と 10:37Z の投稿は通っています（`data/uploaded.jsonl` の 8本）。
**「投稿を止めれば単位が空く」は効きません。**

この検査が守るのは2つだけです。**値段で数えること**と、
**投稿を `videos.update` と同じ枠に数え直さないこと**。
"""
from __future__ import annotations

import json

import pytest

from src import upload_cap


def _ledger(tmp_path, rows):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / "day_quota.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return tmp_path


def test_unit_cost_prices_the_calls_we_actually_make():
    assert upload_cap.unit_cost("videos.update abc") == 50
    assert upload_cap.unit_cost("thumbnails.set abc") == 50
    assert upload_cap.unit_cost("videos.list snapshot") == 1
    assert upload_cap.unit_cost("channels.list mine") == 1
    # **知らない呼び出しを0にしないこと** —— 0円にすると使った量を必ず低く見る。
    assert upload_cap.unit_cost("something.we.have.not.seen") == 1
    assert upload_cap.unit_cost(None) == 1


def test_insert_is_not_on_the_same_budget_as_update():
    """**この2つを同じ枠に足さないこと。**

    足すと「投稿を止めれば単位が空く」と読めます。実測はその逆で、
    枠が尽きた後も投稿だけは通っていました。値段表は別々に持ちます。
    """
    assert upload_cap.UNIT_COST["videos.insert"] == 1600
    assert upload_cap.UNIT_COST["videos.update"] == 50
    # `spend_in_window` が数えるのは day_quota 帳の行だけで、
    # そこに `videos.insert` の成功は載りません（載せたら、この検査が教える）。
    assert "videos.insert" not in upload_cap.DAY_QUOTA_HITS


def test_spend_in_window_reports_units_not_just_calls(tmp_path, monkeypatch):
    rows = [{"at": "2026-08-27T08:00:00+00:00", "ok": True,
             "detail": f"videos.update v{i}"} for i in range(4)]
    rows.append({"at": "2026-08-27T08:01:00+00:00", "ok": True,
                 "detail": "videos.list snapshot"})
    monkeypatch.setattr(upload_cap, "_root", lambda: _ledger(tmp_path, rows))
    from datetime import datetime, timezone
    now = datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc)
    s = upload_cap.spend_in_window(now)
    assert s["ok"] == 5
    assert s["units"] == 4 * 50 + 1, "**回数ではなく値段で足すこと**"


def test_measured_budget_reads_the_floor_off_a_past_window(tmp_path, monkeypatch):
    """枠の下限は、**過去の窓で 403 の前に通った単位**から出す（推測しない）。"""
    rows = [
        # 前の窓: 403 の前に 100回 × 50 = 5,000単位 通った
        *[{"at": f"2026-08-26T07:{i:02d}:00+00:00", "ok": True,
           "detail": f"videos.update a{i}"} for i in range(10)],
        {"at": "2026-08-26T09:00:00+00:00", "detail": "videos.update a9"},
        # この窓: まだ 200単位 しか使っていない
        *[{"at": f"2026-08-27T07:{i:02d}:00+00:00", "ok": True,
           "detail": f"videos.update b{i}"} for i in range(4)],
    ]
    monkeypatch.setattr(upload_cap, "_root", lambda: _ledger(tmp_path, rows))
    from datetime import datetime, timezone
    now = datetime(2026, 8, 27, 8, 0, tzinfo=timezone.utc)
    b = upload_cap.measured_budget(now)
    assert b["floor"] == 10 * 50, "前の窓が 403 の前に通した単位が、枠の下限"
    assert b["spent"] == 4 * 50
    assert b["left"] == 10 * 50 - 4 * 50
    # **いまの窓を下限の材料にしないこと**（自分で自分の天井を決めてしまう）
    assert b["from"] == "08/26"


def test_measured_budget_never_reports_negative_headroom(tmp_path, monkeypatch):
    rows = [
        {"at": "2026-08-26T07:00:00+00:00", "ok": True, "detail": "videos.update a"},
        {"at": "2026-08-26T09:00:00+00:00", "detail": "videos.update a"},
        *[{"at": f"2026-08-27T07:{i:02d}:00+00:00", "ok": True,
           "detail": f"videos.update b{i}"} for i in range(9)],
    ]
    monkeypatch.setattr(upload_cap, "_root", lambda: _ledger(tmp_path, rows))
    from datetime import datetime, timezone
    now = datetime(2026, 8, 27, 8, 0, tzinfo=timezone.utc)
    b = upload_cap.measured_budget(now)
    assert b["spent"] > b["floor"]
    assert b["left"] == 0, "**前例を超えたら 0。負の残量を印字しないこと**"


def test_day_quota_line_names_update_not_insert(tmp_path, monkeypatch):
    """**止める先を名指しできること。**

    この行が「`videos.insert` 1本 1,600単位なので7本で尽きます」と言っていた
    あいだ、実際に枠を焼いていたのは `videos.update` でした。
    """
    rows = [
        {"at": "2026-08-26T07:00:00+00:00", "ok": True, "detail": "videos.update a"},
        {"at": "2026-08-26T09:00:00+00:00", "detail": "videos.update a"},
    ]
    monkeypatch.setattr(upload_cap, "_root", lambda: _ledger(tmp_path, rows))
    from datetime import datetime, timezone
    now = datetime(2026, 8, 27, 8, 0, tzinfo=timezone.utc)
    line = upload_cap.day_quota(now).line
    assert "videos.update" in line
    assert "7本" not in line, "**投稿の本数で枠を語らないこと**（別枠なので効かない）"


@pytest.mark.parametrize("detail", ["videos.update x", "thumbnails.set x"])
def test_the_fifty_unit_calls_are_the_ones_that_burn_the_day(detail):
    assert upload_cap.unit_cost(detail) == 50
