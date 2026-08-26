"""**待ちの期限の正本は台帳。控えから見込みを出す。**（2026-08-26 に足した）

塞いだのは「同じことを2か所が別々に言っていて、片方しか読まれていない」の実例:

    config/watches.yaml    文面「期限 2026-09-14」   ← `deadline_of()` はこちらを読む
    config/hypotheses.yaml `deadline: 2026-10-11`   ← 8/25 に動かしたのはこちら

**27日 ずれていました。** `status.py` は台帳でまだ生きている前提を、毎回
「期限に間に合いません」と印字していました。

もう1つは `uploaded_since` の待ちの**誤報**です。あの窓は**投稿時刻**で切るので、
台本の作りを変えた瞬間から数え始めますが、**その作りの本が公開されるのは
予約の順番待ちのぶんだけ後**です。その間、走査の伸びは定義として 0.00/日 になり、
「**届きません**」と印字されていました —— **届かないのではなく、始まっていません。**
"""
from datetime import date, datetime

import pytest

from src import watch_eta
from src.watch_eta import deadline_of
from src.watches import Watch


def _w(what: str = "", cond: str = "") -> Watch:
    return Watch(id="x", what=what, cond=cond, then="", source="", kind="scan_sum")


def _wk(watch_id: str) -> Watch:
    w = _w(what="判定（期限 2026-09-14）")
    w.id = watch_id
    return w


def _ledger_file(tmp_path, body: str):
    doc = tmp_path / "h.yaml"
    doc.write_text(body, encoding="utf-8")
    return doc


# ---------------------------------------------------------------- 期限の正本

def test_台帳の期限が文面より優先される(tmp_path, monkeypatch) -> None:
    doc = _ledger_file(tmp_path, 'hypotheses:\n  - watch: w1\n    deadline: "2026-10-11"\n')
    monkeypatch.setattr(watch_eta, "HYPOTHESES", doc)
    assert deadline_of(_wk("w1")) == date(2026, 10, 11)


def test_台帳に無い待ちなら文面へ落ちる(tmp_path, monkeypatch) -> None:
    """**文面を消していません。** 台帳に無いときの控えとして残します。"""
    doc = _ledger_file(tmp_path, 'hypotheses:\n  - watch: other\n    deadline: "2026-10-11"\n')
    monkeypatch.setattr(watch_eta, "HYPOTHESES", doc)
    assert deadline_of(_wk("w1")) == date(2026, 9, 14)


def test_閉じた前提の期限は台帳から返さない(tmp_path, monkeypatch) -> None:
    doc = _ledger_file(
        tmp_path,
        'hypotheses:\n  - watch: w1\n    deadline: "2026-10-11"\n    closed_on: "2026-08-20"\n')
    monkeypatch.setattr(watch_eta, "HYPOTHESES", doc)
    assert deadline_of(_wk("w1")) == date(2026, 9, 14)


def test_名前が無ければ台帳を読まない() -> None:
    assert watch_eta.ledger_deadline("") is None


def test_壊れた台帳でも落ちない(tmp_path, monkeypatch) -> None:
    doc = _ledger_file(tmp_path, 'hypotheses:\n  - watch: w1\n    deadline: "とんでもない"\n')
    monkeypatch.setattr(watch_eta, "HYPOTHESES", doc)
    assert watch_eta.ledger_deadline("w1") is None


def test_実物の待ちが台帳の期限を指している() -> None:
    """**実物で線を引く。** 文面へ日付を書き戻したら、ここが落ちます。

    2026-08-26 の実測。3件とも文面のほうが古く、**そちらが読まれていました。**
    """
    from src import watches as W

    want = {
        "登録の依頼-30000再生": date(2026, 10, 11),   # 文面は 2026-09-14（27日 古い）
        "長尺-1000再生": date(2026, 11, 22),          # 文面は 2026-09-15（68日 古い）
        "族べつ登録率-15000再生": date(2026, 9, 17),   # 文面は 2026-09-20
    }
    by_id = {w.id: w for w in W.load()}
    for wid, deadline in want.items():
        assert wid in by_id, f"待ちが消えています: {wid}"
        w = by_id[wid]
        assert "期限" not in w.what, f"{wid}: 期限は台帳から引くこと（文面に書き戻さない）"
        assert deadline_of(w) == deadline, wid


# ---------------------------------------------------------------- 控えからの見込み

def _plan_watch() -> Watch:
    w = _w(what="判定")
    w.params.update({"uploaded_since": "2026-08-24T14:00:00+00:00",
                     "need": 30000, "max_length": 70})
    return w


@pytest.fixture()
def _ledger(monkeypatch):
    """処置3本（＋窓の外1本）。2本が期限までに公開、うち1本だけ生きた枠。"""
    ups = {
        "a": datetime.fromisoformat("2026-08-25T00:00:00+00:00"),
        "b": datetime.fromisoformat("2026-08-25T01:00:00+00:00"),
        "c": datetime.fromisoformat("2026-08-25T02:00:00+00:00"),
        "old": datetime.fromisoformat("2026-08-01T00:00:00+00:00"),
    }
    pubs = {"a": date(2026, 9, 1), "b": date(2026, 9, 2),
            "c": date(2026, 12, 1), "old": date(2026, 8, 1)}
    monkeypatch.setattr(watch_eta.W, "_uploaded_ats", lambda: ups)
    monkeypatch.setattr(watch_eta.W, "_publish_dates", lambda: pubs)
    monkeypatch.setattr(watch_eta, "_live_ids", lambda: {"a"})
    monkeypatch.setattr(watch_eta, "_per_video_views", lambda w: 600.0)


def test_控えから見込みを出す(_ledger) -> None:
    plan = watch_eta.queue_plan(_plan_watch(), date(2026, 10, 11),
                                today=date(2026, 8, 26))
    assert plan is not None
    assert plan.treated == 3           # `old` は窓の外
    assert plan.before_deadline == 2   # `c` は期限の後
    assert plan.live == 1              # 生きた枠は `a` だけ
    assert plan.est == 600.0
    assert round(plan.short_videos) == 49      # (30000 − 600) ÷ 600


def test_1本も公開されていなければ始まっていない(_ledger) -> None:
    """**「届かない」ではありません。** 予約の順番待ちで、まだ始まっていないだけ。"""
    plan = watch_eta.queue_plan(_plan_watch(), date(2026, 10, 11),
                                today=date(2026, 8, 26))
    assert plan is not None and plan.started is False


def test_公開が始まっていれば_started(_ledger) -> None:
    plan = watch_eta.queue_plan(_plan_watch(), date(2026, 10, 11),
                                today=date(2026, 9, 5))
    assert plan is not None and plan.started is True


def test_期限が無ければ全部を数える(_ledger) -> None:
    plan = watch_eta.queue_plan(_plan_watch(), None, today=date(2026, 8, 26))
    assert plan is not None and plan.before_deadline == 3


def test_処置が1本も無ければ計画を出さない(monkeypatch) -> None:
    monkeypatch.setattr(watch_eta.W, "_uploaded_ats", lambda: {})
    assert watch_eta.queue_plan(_plan_watch(), date(2026, 10, 11)) is None


def test_uploaded_since_の無い待ちは対象外() -> None:
    assert watch_eta.queue_plan(_w(what="判定"), date(2026, 10, 11)) is None


def test_足りていれば本数は0(_ledger, monkeypatch) -> None:
    monkeypatch.setattr(watch_eta, "_per_video_views", lambda w: 40000.0)
    plan = watch_eta.queue_plan(_plan_watch(), date(2026, 10, 11),
                                today=date(2026, 8, 26))
    assert plan is not None and plan.short_videos == 0.0


def test_1本あたりが0でも割らない(_ledger, monkeypatch) -> None:
    monkeypatch.setattr(watch_eta, "_per_video_views", lambda w: 0.0)
    plan = watch_eta.queue_plan(_plan_watch(), date(2026, 10, 11),
                                today=date(2026, 8, 26))
    assert plan is not None and plan.short_videos == 0.0


def test_実物で処置の本が控えに在る() -> None:
    """**実物で線を引く。** 依頼を入れた後の本が0件に戻ったら、ここが落ちます。"""
    from src import watches as W

    w = [x for x in W.load() if x.id == "登録の依頼-30000再生"][0]
    plan = watch_eta.queue_plan(w, deadline_of(w))
    assert plan is not None and plan.treated >= 1
