"""**枠を実際に使う側（`ahead_sweep._today_candidate`）が、門を訊くこと。**

2026-09-05・最適化の回。門はぜんぶ **書き門**（`daily_pick.record()` の中）で、
**決めを書く瞬間**しか見ていなかった。ところが枠を使うのは `_today_candidate()` で、
そこは `daily_pick.current(day)` をそのまま返していた ＝ **1度 書けた決めは、
以後どの門も触れない。**

実測（2026-09-05・API 0単位）—— 09/05 09:00 の枠に立っていたのは
**長尺 `GFvAcxvDmYM`（見込み 1回）**。同じ時刻に

    and_path_form()            → ショート（道 ショート ×106・長尺 ×334）
    1本あたり登録              → ショート 0.261人 / 長尺 0.008人（**×33**）
    form_median_48h            → ショート 164回 / 長尺 1回
    path_form_hold("長尺")      → 止める
    anyway_pays_hold("長尺")    → 止める
    standing_form_stale_now()  → 止める

**止めは3つとも在って、3つとも正しく、3つとも鳴っていた。それでも枠は長尺だった。**

**この2件を消さないと、通し直しは戻せません。**
"""

from __future__ import annotations

import datetime as _dt

from src import daily_pick as dp

import scripts.ahead_sweep as sweep

DAY = _dt.date(2026, 9, 5)
NOW = _dt.datetime(2026, 9, 5, 5, 0, tzinfo=dp.JST)


def _pick(**kw):
    r = {"kind": dp.PICK_KIND_DECIDE, "for_day": DAY.isoformat(), "form": "長尺",
         "topic": "t", "video_id": "standing", "expected_48h": 1.0}
    r.update(kw)
    return r


def test_門で落ちる決めは枠に置かない(monkeypatch):
    """立っている決めが `standing_form_stale` で落ちたら、`source` は `pick` ではない。"""
    monkeypatch.setattr(dp, "current", lambda day, **k: _pick())
    monkeypatch.setattr(dp, "standing_form_stale",
                        lambda *a, **k: "門は ショート を指しています")
    # 池は空にして、下の枝まで落ちることだけを見る（`record` を撃たせない）。
    monkeypatch.setattr(dp, "compare", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("池は見ない")))
    got = sweep._today_candidate(NOW)
    assert got is None or got.get("source") != "pick", got


def test_門を通る決めはそのまま置く(monkeypatch):
    """落ちない日は、この手は**何もしない**（素通り）。"""
    monkeypatch.setattr(dp, "current", lambda day, **k: _pick(form="ショート"))
    monkeypatch.setattr(dp, "standing_form_stale", lambda *a, **k: "")
    got = sweep._today_candidate(NOW)
    assert got is not None
    assert got.get("source") == "pick"
    assert got.get("video_id") == "standing"


def test_門が例外なら止めない(monkeypatch):
    """**推測で止めないこと。** 通し直しが撃てない回は、決めをそのまま通す。"""
    monkeypatch.setattr(dp, "current", lambda day, **k: _pick())
    monkeypatch.setattr(dp, "standing_form_stale",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("読めない")))
    got = sweep._today_candidate(NOW)
    assert got is not None and got.get("source") == "pick"


def test_ほかの日の決めが名指す本は池から引く(tmp_path):
    """`claimed_elsewhere` —— 予約も公開も無い本でも、別の日が名指していれば取らない。"""
    p = tmp_path / "picks.jsonl"
    rows = [
        {"kind": dp.PICK_KIND_DECIDE, "for_day": "2026-09-05", "form": "ショート",
         "video_id": "own", "at": "2026-09-05T01:00:00+09:00"},
        {"kind": dp.PICK_KIND_DECIDE, "for_day": "2026-09-06", "form": "ショート",
         "video_id": "other", "at": "2026-09-05T00:38:00+09:00"},
    ]
    import json
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    got = dp.claimed_elsewhere(DAY, path=p)
    assert "other" in got          # 別の日が名指している
    assert "own" not in got        # **自分の日は入れない**（自分で自分を弾かない）


def test_その日の最後の決めだけを見る(tmp_path):
    """同じ日に決めが2つ在る回は、`current()` と同じく **`at` の新しいほう**。"""
    import json
    p = tmp_path / "picks.jsonl"
    rows = [
        {"kind": dp.PICK_KIND_DECIDE, "for_day": "2026-09-06", "form": "ショート",
         "video_id": "old", "at": "2026-09-05T00:10:00+09:00"},
        {"kind": dp.PICK_KIND_DECIDE, "for_day": "2026-09-06", "form": "ショート",
         "video_id": "new", "at": "2026-09-05T00:38:00+09:00"},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    got = dp.claimed_elsewhere(DAY, path=p)
    assert got == {"new"}, got


def test_窓の外の決めは無視する(tmp_path):
    """古い決めが池を永久に痩せさせないこと（既定 前後 14日）。"""
    import json
    p = tmp_path / "picks.jsonl"
    rows = [{"kind": dp.PICK_KIND_DECIDE, "for_day": "2026-01-01", "form": "ショート",
             "video_id": "ancient", "at": "2026-01-01T00:00:00+09:00"}]
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert dp.claimed_elsewhere(DAY, path=p) == set()
