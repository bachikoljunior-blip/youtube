"""`trend.plan_branch` —— 場合分けの計画（GOAL (4-i)）の、いま生きている枝を機械が選ぶ。

2026-09-15 06:5x・optimizer・Fable。オーナー 06:26 `75061584`
「すぐ結果出ないんだったらその後のプランを場合分けしてプランすることを批判的にみてもそれがいいと思うんだったらそうして」。

**陽性対照**（撃って落とした）: 門 `LONG_GATE_48H_VIEWS` を 1000 にすると `test_A` が B に落ち、
`LONG_JUDGE_N` を 1 にすると `test_判定前` が枝を選んでしまう。
"""
import datetime as dt
import json

import pytest

from studio import trend

JST = trend.JST
T0 = dt.datetime(2026, 9, 15, 19, 0, tzinfo=JST)


def _script(dirp, sid: str, form: str = "long"):
    (dirp / f"{sid}.json").write_text(json.dumps({"id": sid, "form": form}), encoding="utf-8")


def _sched(sid: str, vid: str, at: dt.datetime, replaced=None) -> dict:
    return {"event": "scheduled", "id": sid, "video_id": vid, "publish_at": at.isoformat(),
            "replaced": replaced, "at": (at - dt.timedelta(hours=12)).isoformat()}


def _pts(vid: str, pub: dt.datetime, views_by_age: dict[float, int]) -> list[dict]:
    return [{"event": "measured", "id": vid, "age_h": h, "views": v,
             "at": (pub + dt.timedelta(hours=h)).isoformat()}
            for h, v in sorted(views_by_age.items())]


def _hours(vid: str, hours: float) -> dict:
    return {"event": "analytics_video", "id": vid, "minutes": hours * 60, "views": 10,
            "subs_gained": 0, "at": T0.isoformat()}


def _chan(at: dt.datetime, subs: int, views: int) -> dict:
    return {"event": "channel", "id": "c", "subs": subs, "views": views, "at": at.isoformat()}


@pytest.fixture
def 台(tmp_path, monkeypatch):
    monkeypatch.setattr(trend, "now_jst", lambda: T0 + dt.timedelta(days=4))
    for i, sid in enumerate(("s1", "s2", "s3")):
        _script(tmp_path, sid)
    _script(tmp_path, "short1", form="short")
    base = [_chan(T0 - dt.timedelta(days=3), 27, 80_000), _chan(T0, 28, 88_000),
            _sched("short1", "SHORT1", T0)]
    pubs = {"V1": T0, "V2": T0 + dt.timedelta(days=1), "V3": T0 + dt.timedelta(days=2)}
    scheds = [_sched("s1", "V1", pubs["V1"]), _sched("s2", "V2", pubs["V2"]),
              _sched("s3", "V3", pubs["V3"])]
    return tmp_path, base + scheds, pubs


def _run(rows, dirp, env=None):
    return trend.plan_branch(rows, scripts_dir=dirp, env=env or {})


def test_長尺は台本の_form_で引く_ショートは数えない(台):
    dirp, rows, pubs = 台
    b = _run(rows + _pts("SHORT1", T0, {1: 500, 50: 900}), dirp)
    assert b["n_long"] == 3 and {p["video_id"] for p in b["per"]} == {"V1", "V2", "V3"}


def test_差し替えは同じ台本idの後の行が勝つ(台):
    dirp, rows, pubs = 台
    rows = rows + [_sched("s3", "V3b", pubs["V3"], replaced="V3")]
    ids = {p["video_id"] for p in _run(rows, dirp)["per"]}
    assert "V3b" in ids and "V3" not in ids


def test_判定前は枝を選ばない(台):
    dirp, rows, pubs = 台
    rows = rows + _pts("V1", pubs["V1"], {1: 5, 50: 40}) + _pts("V2", pubs["V2"], {1: 3, 50: 30})
    b = _run(rows, dirp)
    assert b["branch"] == "pre" and b["n_reached"] == 2
    assert "判定前" in trend.plan_branch_line(rows, scripts_dir=dirp, env={})


def _three(pubs, v1, v2, v3):
    return (_pts("V1", pubs["V1"], {1: 1, 47: v1 - 1, 49: v1})
            + _pts("V2", pubs["V2"], {1: 1, 47: v2 - 1, 49: v2})
            + _pts("V3", pubs["V3"], {1: 1, 47: v3 - 1, 49: v3}))


def test_A_門を2つとも通る(台):
    dirp, rows, pubs = 台
    rows = rows + _three(pubs, 40, 60, 80) + [_hours("V2", 120)]
    b = _run(rows, dirp)
    assert b["branch"] == "A" and b["g1"] is True and b["g2"] is True and b["med48_hi"] == 60


def test_B_48hの中位が門以下なら配りの側(台):
    dirp, rows, pubs = 台
    rows = rows + _three(pubs, 10, 20, 200) + [_hours("V3", 150)]
    b = _run(rows, dirp)
    assert b["branch"] == "B" and b["med48_hi"] == 20
    assert "落ち" in trend.plan_branch_line(rows, scripts_dir=dirp, env={})


def test_C_再生は通るが視聴時間が届かない(台):
    dirp, rows, pubs = 台
    rows = rows + _three(pubs, 40, 60, 80) + [_hours("V1", 5), _hours("V2", 20)]
    assert _run(rows, dirp)["branch"] == "C"


def test_A疑問_視聴時間が未なら_A_として動く(台):
    dirp, rows, pubs = 台
    b = _run(rows + _three(pubs, 40, 60, 80), dirp)
    assert b["branch"] == "A?" and b["g2"] is None


def test_挟みが門をまたぐと_stable_が偽(台):
    dirp, rows, pubs = 台
    rows = (rows + _pts("V1", pubs["V1"], {1: 1, 40: 20, 55: 30})
            + _pts("V2", pubs["V2"], {1: 1, 40: 20, 55: 30})
            + _pts("V3", pubs["V3"], {1: 1, 40: 20, 55: 30}))
    b = _run(rows, dirp)
    assert b["branch"] == "A?" and b["stable"] is False
    assert "またいで" in trend.plan_branch_line(rows, scripts_dir=dirp, env={})


def test_2つ目の口は環境変数の名で見る(台):
    dirp, rows, pubs = 台
    assert _run(rows, dirp, env={})["second_channel"] is False
    assert _run(rows, dirp, env={trend.SECOND_CHANNEL_ENV: "x"})["second_channel"] is True


def test_門の数はGOALではなくここが持つ():
    """GOAL (4-g)(4-i) の「25回」「100時間」「3本」は写し ＝ 定数が正本。"""
    assert trend.LONG_GATE_48H_VIEWS == 25
    assert trend.LONG_GATE_HOURS_PER_VIDEO == 100.0
    assert trend.LONG_JUDGE_N == 3
