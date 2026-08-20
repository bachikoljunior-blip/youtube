"""`src/rpm_mix.py` —— 腕 `rpm` の天井を、推測から実測に入れ替えた側の検査。

**この検査が守っているのは「数字が出ること」ではありません。**
守っているのは次の3つです。

1. **重みが再生数であること。** 最初に書いた版は視聴分で重みを付けていて、
   天井が ×41.5 と出ました。帯（¥20 / ¥400 …）は「1,000**再生**あたり」の数なので、
   割合も再生で取らないと単位が合いません。**視聴分で取ると長尺を実際より重く数えます。**
   再生で取り直した天井は ×15.5。**ここが視聴分に戻ったら落とします。**
2. **測れていないときに、黙って据え置きの ×100 へ戻らないこと。**
   戻ってよいのですが、`why` に「まだ測っていません」と出ること。
3. **帯の写しが黙って古くならないこと**（`BANDS` と `eta.RPM_SCENARIOS`）。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from src import rpm_mix

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


# --- 3. 写しが古くならないこと -------------------------------------------------
def test_帯は_eta_と同じ():
    assert rpm_mix.BANDS == eta.RPM_SCENARIOS


# --- 1. 重みは再生数 -----------------------------------------------------------
def test_実効rpmは再生で重みを付ける():
    """長尺は1再生あたりの視聴分が長いので、視聴分で重みを付けると重く出ます。

    再生 99 対 1、視聴分 50 対 50 という（実際にありうる）形を当てます。
    """
    views = {"ショート": 99.0, "長尺": 1.0}
    got = rpm_mix.effective_rpm(views, "低")
    assert abs(got - (0.99 * 20 + 0.01 * 400)) < 1e-9
    # 視聴分で取っていたら ¥210 になる。**そこには絶対に行かないこと。**
    assert got < 30


def test_知らない形は0円で数える():
    """`liveStream` などが混ざったとき、黙ってショート扱いにしない。"""
    got = rpm_mix.effective_rpm({"ショート": 50.0, "liveStream": 50.0}, "低")
    assert abs(got - 10.0) < 1e-9


def test_再生が0なら0を返す():
    assert rpm_mix.effective_rpm({}, "低") == 0.0
    assert rpm_mix.effective_rpm({"ショート": 0.0}, "低") == 0.0


def test_形べつの集計は呼び名でまとめる():
    by_form = {"shorts": {"views": 10, "minutes": 3},
               "videoOnDemand": {"views": 2, "minutes": 4}}
    assert rpm_mix.views_by_form(by_form) == {"ショート": 10.0, "長尺": 2.0}
    assert rpm_mix.minutes_by_form(by_form) == {"ショート": 3.0, "長尺": 4.0}


def test_国の割合():
    assert rpm_mix.jp_share({"JP": {"minutes": 90}, "US": {"minutes": 10}}) == 0.9
    # 行が無ければ 1.0（割り引きを勝手に掛けない）
    assert rpm_mix.jp_share({}) == 1.0


# --- 天井 ---------------------------------------------------------------------
def _mix(short_views: float, long_views: float, days: float = 90) -> dict:
    return {"days": days, "start": "2026-05-22", "end": "2026-08-20",
            "by_form": {"shorts": {"views": short_views, "minutes": short_views * 0.13},
                        "videoOnDemand": {"views": long_views, "minutes": long_views * 0.64}}}


def _reach(imp: float, days: float = 34) -> dict:
    return {"長尺": {"impressions": imp}, "ショート": {"impressions": 0.0}, "days": days}


def test_天井は面で止まる():
    """長尺の面 ＝ 1日あたりの再生の上限（CTR 100%）。混ざり方はそこで頭打ち。"""
    mix = _mix(short_views=9000, long_views=11, days=90)   # ショート 100再生/日
    got = rpm_mix.surface_ceiling(mix, _reach(imp=3400, days=34))  # 長尺 100回/日
    assert abs(got["long_share_max"] - 0.5) < 1e-6
    assert abs(got["rpm_max"] - (0.5 * 2000 + 0.5 * 60)) < 1e-6


def test_面が測れていなければ天井を出さない():
    """**測れないときに据え置きへ黙って戻らないため**、`factor` は None。"""
    got = rpm_mix.surface_ceiling(_mix(9000, 11), _reach(imp=0))
    assert got["factor"] is None
    assert got["rpm_max"] is None


def test_面が増えると天井は上がる():
    """「長尺を出すと `rpm` の天井が上がる」が、そのまま数字に出ること。"""
    mix = _mix(short_views=9000, long_views=11)
    small = rpm_mix.surface_ceiling(mix, _reach(imp=340))
    big = rpm_mix.surface_ceiling(mix, _reach(imp=3400))
    assert big["factor"] > small["factor"]


def test_視聴分は診断にしか使わない():
    """視聴分の割合は残すが、`rpm_now` の重みには入っていないこと。"""
    mix = _mix(short_views=9000, long_views=11)
    got = rpm_mix.surface_ceiling(mix, _reach(imp=3400))
    assert got["long_minutes_share_now"] > got["long_share_now"]     # 視聴分のほうが重い
    assert abs(got["rpm_now"] - rpm_mix.effective_rpm(
        rpm_mix.views_by_form(mix["by_form"]), "低")) < 1e-9


# --- 積む・読む ---------------------------------------------------------------
def test_積んだ点には重みの名前が入る(tmp_path):
    """欄が無いと、次に読む側が「視聴分の版か再生の版か」を区別できません。"""
    mix = _mix(9000, 11)
    ceiling = rpm_mix.surface_ceiling(mix, _reach(imp=3400))
    log = tmp_path / "rpm_mix.jsonl"
    rec = rpm_mix.record(mix, ceiling, path=log)
    assert rec["weight"] == "views"
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["weight"] == "views"
    assert rpm_mix.last(path=log)["rpm_max"] == rec["rpm_max"]


def test_点が無ければ_None(tmp_path):
    assert rpm_mix.last(path=tmp_path / "no.jsonl") is None


# --- 2. `eta.physical_caps` の側 ----------------------------------------------
def test_etaの天井は実測を使う(monkeypatch):
    monkeypatch.setattr(eta.rpm_mix, "last",
                        lambda *a, **k: {"factor": 15.51, "rpm_now": 20.2, "rpm_max": 313.0,
                                         "why": "長尺の面 …"})
    caps = eta.physical_caps({"sub_rate": 0.0004}, density=1.0)
    assert caps["rpm"]["measured"] is True
    assert abs(caps["rpm"]["factor"] - 15.51) < 1e-9


def test_測っていなければ据え置きに戻るが黙らない(monkeypatch):
    monkeypatch.setattr(eta.rpm_mix, "last", lambda *a, **k: None)
    caps = eta.physical_caps({"sub_rate": 0.0004}, density=1.0)
    assert caps["rpm"]["measured"] is False
    assert "まだ測っていません" in caps["rpm"]["why"]
