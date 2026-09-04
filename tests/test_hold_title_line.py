"""`[きょうの1本]` の (3)「作りが違う点を1つ入れる」に、**その場で当てられる数**を出す行。

言うだけで数を出していなかったので、題を触った回は毎回 その場で数え直し、
**同じ帯で3回 数えて3回とも食い違いました**（`niche_ceiling.TITLE_FEATURES` の註）。
"""
from __future__ import annotations

import pytest

from src import hold


class _NC:
    """`niche_ceiling` の代わり。**帯を撃たずに、行の作り方だけを見ます。**"""
    TITLE_FEATURES = {"断定・煽り": r"(必ず|大損)", "【】": r"【",
                      "疑問形": r"[？?]", "場面": r"20[0-9]{2}年"}

    def __init__(self, feats):
        self._f = feats

    def title_features(self, form):
        self.form_seen = form
        return self._f


def _feat(name, ratio, ny=50, nn=80, thin=False):
    return {"name": name, "n_yes": ny, "n_no": nn, "med_yes": 1.0,
            "med_no": 1.0 / ratio, "ratio": ratio, "thin": thin}


@pytest.fixture()
def nc(monkeypatch):
    obj = _NC([_feat("断定・煽り", 46.0), _feat("【】", 5.5),
               _feat("疑問形", 2.4), _feat("場面", 2.3, ny=5, nn=127, thin=True)])
    import sys
    monkeypatch.setitem(sys.modules, "niche_ceiling", obj)
    return obj


def test_form_comes_from_duration_not_from_the_caller(nc):
    """`next_slot.next_video()` の行に `form` は在りません（`duration_s` は在る）。
    **形を間違えると向きごと逆の手を打ちます**（疑問形は 長尺と ショート で符号が逆）。"""
    hold.title_feature_line({"title": "【x】y", "duration_s": 1361.0}, "ショート")
    assert nc.form_seen == "long"
    hold.title_feature_line({"title": "【x】y", "duration_s": 40.0}, "長尺")
    assert nc.form_seen == "short"
    # 尺が読めなければ、呼び手の持っている形へ倒す
    hold.title_feature_line({"title": "【x】y"}, "ショート")
    assert nc.form_seen == "short"


def test_forbidden_feature_is_shown_but_never_recommended(nc):
    """帯では ×46 で最大だが、**規則の本文が禁じている**。隠さず、勧めない。"""
    out = "\n".join(hold.title_feature_line({"title": "【x】いくら？", "duration_s": 40.0}))
    assert "断定・煽り" in out, "隠すと、09-07 に倒す回が数を見つけられません"
    assert "規則が禁じている" in out
    assert "いちばん厚い升で、まだ空いている特徴: 「断定・煽り」" not in out


def test_thin_cells_are_marked_and_not_recommended(monkeypatch):
    """**実物がこの形でした**（2026-09-05・`DtpnSVFDtAE`）—— 厚い2つは題に在り、
    残る3つ目は n=5対127 の薄い升。そのとき「打てる」は1行も出ないこと。"""
    import sys
    obj = _NC([_feat("【】", 5.5), _feat("疑問形", 2.4),
               _feat("場面", 2.3, ny=5, nn=127, thin=True)])
    monkeypatch.setitem(sys.modules, "niche_ceiling", obj)
    out = "\n".join(hold.title_feature_line({"title": "【x】いくら？", "duration_s": 40.0}))
    assert "薄い升" in out
    assert "← 打てる" in out          # 表には「無い」と出る
    assert "いちばん厚い升" not in out  # が、勧める行は出さない


def test_recommends_the_thickest_open_feature(nc):
    """題に【】が無ければ、いちばん厚い升の空いている特徴を名指しする。"""
    out = "\n".join(hold.title_feature_line({"title": "いくら？", "duration_s": 40.0}))
    assert "【】 ×5.50" in out and "← 打てる" in out
    assert "いちばん厚い升で、まだ空いている特徴: 「【】」" in out
    assert "retitle.py" in out and "--replace" in out


def test_always_says_do_not_copy_across_forms(nc):
    out = "\n".join(hold.title_feature_line({"title": "x", "duration_s": 40.0}))
    assert "形をまたいで写さないこと" in out


def test_no_row_no_lines(nc):
    assert hold.title_feature_line(None) == []
