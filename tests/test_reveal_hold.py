"""**説明している図が、説明のあいだ画面に居るか。**（2026-08-27）

オーナー原文:

> 「動画についてまず何言ってるか分かんないね。音声だけで理解できない説明なのに
> 画面はすぐ切り替わるし。説明を理解するにはかなり視聴者側の推論が必要だと思う。」

`reveal_variants` は図を「要素を1つずつ足す」コマ列に割るので、
**完成形は最後の1コマにしかありません。** 2026-08-15 から 08-27 まで、
`pipeline` はその文の尺を**等分**していました:

    6.0秒 の文 → 3コマ × 2.0秒 → **完成形が居るのは最後の 2.0秒**

読み上げがその図を説明しているあいだ、画面には未完成の図しかありません。

この検査が守るのは2つ:
  1. `reveal_durations` が**等分に戻らない**こと
  2. `verify` の速さの検査が**上限だけ**に戻らないこと
"""
from __future__ import annotations

import json

from src import pipeline, verify


# --------------------------------------------------------------------------
# 1. 割り当ての側
# --------------------------------------------------------------------------

def test_complete_frame_gets_the_remainder_not_an_equal_share():
    """6秒の文を3コマに割ったら、完成形は 2.0秒 ではなく **4.2秒**。"""
    got = pipeline.reveal_durations(6.0, 3)
    assert len(got) == 3
    assert got[0] == got[1] == pipeline.REVEAL_STEP_SECONDS
    assert abs(got[-1] - (6.0 - 2 * 0.9)) < 1e-9
    assert got[-1] > 6.0 / 3, "**等分に戻っている**"


def test_total_is_preserved_so_the_audio_does_not_drift():
    for dur, n in [(6.0, 3), (4.0, 2), (9.0, 4), (2.0, 1), (7.3, 5)]:
        assert abs(sum(pipeline.reveal_durations(dur, n)) - dur) < 1e-6, (dur, n)


def test_complete_frame_never_falls_under_the_floor():
    """コマを減らしてでも、完成形に 2.5秒 を渡すこと。"""
    for dur in [3.0, 4.0, 5.0, 6.0, 8.0]:
        for n in range(1, 7):
            got = pipeline.reveal_durations(dur, n)
            assert abs(sum(got) - dur) < 1e-6
            if len(got) > 1:
                assert got[-1] + 1e-6 >= pipeline.SHORT_SLIDE_SECONDS, (dur, n, got)


def test_it_drops_frames_rather_than_shrinking_the_complete_one():
    """2.6秒 の文に4コマは入りません。**減らすのはコマのほう。**"""
    got = pipeline.reveal_durations(2.6, 4)
    assert len(got) < 4
    assert abs(sum(got) - 2.6) < 1e-6


def test_the_complete_frame_still_obeys_the_upper_bound():
    """長い文で完成形が 5.0秒 を超えたら、**途中のコマが引き取る**。"""
    got = pipeline.reveal_durations(12.0, 3)
    assert got[-1] <= verify.MAX_SECONDS_PER_PICTURE + 1e-9
    assert max(got) <= verify.MAX_SECONDS_PER_PICTURE + 1e-9
    assert abs(sum(got) - 12.0) < 1e-6
    assert got[0] > pipeline.REVEAL_STEP_SECONDS, "余りは途中のコマへ"


# --------------------------------------------------------------------------
# 2. 検査の側
# --------------------------------------------------------------------------

def _work(tmp_path, seconds, complete):
    (tmp_path / "slide_seconds.json").write_text(json.dumps(seconds), encoding="utf-8")
    (tmp_path / "slide_complete.json").write_text(json.dumps(complete), encoding="utf-8")
    return tmp_path


def test_verify_catches_a_flashed_complete_frame(tmp_path):
    # 6秒の文を等分した昔の形: [2.0, 2.0, 2.0]、完成形は index 2
    w = _work(tmp_path, [2.0, 2.0, 2.0], [2])
    out = verify._check_reveal_hold(w)
    assert out and "2.0秒" in out[0]


def test_verify_passes_the_new_allocation(tmp_path):
    secs = pipeline.reveal_durations(6.0, 3)
    w = _work(tmp_path, list(secs), [len(secs) - 1])
    assert verify._check_reveal_hold(w) == []


def test_verify_says_nothing_without_the_ledger(tmp_path):
    """長尺・古い build では黙ること（`_check_slide_hold` と同じ扱い）。"""
    assert verify._check_reveal_hold(tmp_path) == []
    (tmp_path / "slide_seconds.json").write_text("[1.0]", encoding="utf-8")
    assert verify._check_reveal_hold(tmp_path) == []


def test_the_pace_gates_are_no_longer_one_sided():
    """**上限だけに戻らないこと。**

    2026-08-27 まで、速さの検査は `MAX_*` の3つだけでした。落ちたときの文言は
    「セグメントを増やして画を動かすこと」で、**検査そのものが速いほうへ
    押していました。** 下限が1つも無い状態に戻ったら、ここで気づきます。
    """
    src = (verify.__file__)
    text = open(src, encoding="utf-8").read()
    assert "MIN_COMPLETE_SECONDS" in text
    assert "_check_reveal_hold(work)" in text, "**呼ばれていなければ、無いのと同じ**"
