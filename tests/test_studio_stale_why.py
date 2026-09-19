"""**「焼き直しが要る」の理由を、指紋のどこが動いたかで言い分ける**（2026-09-20 00:xx・optimizer）。

守っているのは 2つ:

  1. **版だけ動いた本を「台本が動いた」と言わないこと。** 09/19 23:xx の周は、その 1文 を読んで
     「台本が build のあとに動いた 3本」と申し送り、**3本 とも台本は 1字 も動いていませんでした**
     （動いたのは `BUILD_SIG_VERSION` 2→3 ＝ オーナー `9155fe09` の直し）。
  2. **焼き直しの値段を形ごとに言うこと。** 「1本 92秒」はショートの数で、長尺は **実測 1,180秒**。
     同じ周が「1周（床 98分）で 3本」と決め、**1本も焼き上がりませんでした**。
"""
from studio.cli import (
    BUILD_SECONDS,
    detach_line,
    rebuild_cost,
    rebuild_seconds,
    stale_why,
)


def test_version_only_says_tool_moved_not_script():
    """版だけ動いたら「道具が直った」＝ **台本は動いていない**と言い切ること。"""
    msg = stale_why("2:0653fadbdbec", "3:0653fadbdbec")
    assert "道具が直った" in msg
    assert "2→3" in msg
    assert "台本は 1字 も動いていません" in msg
    # **ここが肝**: 旧い 1文 が混ざってはいけない（混ざると次の回が台本を読み直す）
    assert "台本が build のあとに動いた" not in msg


def test_body_only_says_script_moved():
    """中身だけ動いたら、これまでどおり「台本が動いた」。**前の字を消していません。**"""
    msg = stale_why("3:aaaaaaaaaaaa", "3:bbbbbbbbbbbb")
    assert "台本が build のあとに動いた" in msg
    assert "道具" not in msg


def test_both_moved_is_named_separately():
    """両方 動いた回は、そう言う（どちらが効いたか読めないと書く）。"""
    msg = stale_why("2:0ff130dd52b0", "3:0653fadbdbec")
    assert "道具も台本も動いた" in msg
    assert "2→3" in msg


def test_missing_sig_is_not_called_a_script_change():
    """刻印が無い本を「台本が動いた」と言わないこと（焼いていないのと見分けがつかなくなる）。"""
    msg = stale_why(None, "3:abc123abc123")
    assert "まだ焼いていない" in msg
    assert "台本が build のあとに動いた" not in msg


def test_long_is_not_priced_as_short():
    """長尺 1本 を 92秒 と言わないこと。**この 1行 が 09/19 23:xx の周を外させた当のもの。**"""
    assert BUILD_SECONDS["long"] > 10 * BUILD_SECONDS["short"]
    line = rebuild_cost(["a"], {"a": "long"})
    assert "92秒" not in line
    assert "long" in line


def test_long_is_flagged_for_detaching_even_inside_the_floor():
    """**長尺 1本 でも切り離せ**と言うこと。

    3本 でも 59分 ＝ **床（98分）の内側**です。それでも入らなかったのは、
    **サブが床より早く畳まれるから**（実測 28分）。**床で測ると、この札は一生 出ません。**
    """
    assert detach_line(["a"], {"a": "long"}) != ""
    three = detach_line(["a", "b", "c"], {"a": "long", "b": "long", "c": "long"})
    assert "longform_chain.sh" in three
    # 床の内側であることを、札そのものが認めていること（読む側が床で数え直さないように）
    assert "床 98分 の内側でも" in three
    assert "サブの寿命ではありません" in three


def test_short_alone_is_not_flagged():
    """ショート 1本 は切り離しの札を出さない（狼少年にしない）。"""
    assert detach_line(["d"], {"d": "short"}) == ""
    assert "92秒" in rebuild_cost(["d"], {"d": "short"})


def test_many_shorts_do_get_flagged():
    """ショートでも数が積まれれば切り離す ＝ 札は形ではなく**秒**で出ること。"""
    ids = [f"s{i}" for i in range(9)]           # 9 × 92秒 ＝ 828秒 > 600秒
    assert detach_line(ids, {i: "short" for i in ids}) != ""
    assert detach_line(ids[:3], {i: "short" for i in ids}) == ""   # 3 × 92 ＝ 276秒


def test_cost_line_no_longer_carries_the_hint():
    """値段の行に札を混ぜないこと（入れ子の括弧で見出しが読めなくなる）。"""
    line = rebuild_cost(["a", "b", "c"], {"a": "long", "b": "long", "c": "long"})
    assert "longform_chain.sh" not in line
    assert line.endswith(f"**約{3 * BUILD_SECONDS['long'] // 60}分**")


def test_rebuild_seconds_is_the_one_place_the_number_lives():
    assert rebuild_seconds(["a"], {"a": "long"}) == BUILD_SECONDS["long"]
    assert rebuild_seconds(["d"], {"d": "short"}) == BUILD_SECONDS["short"]
    assert rebuild_seconds([], {}) == 0


def test_mixed_forms_are_both_named():
    line = rebuild_cost(["a", "d"], {"a": "long", "d": "short"})
    assert "long 1本" in line and "short 1本" in line


def test_empty_is_quiet():
    assert rebuild_cost([], {}) == "`build` 0本"


def test_unknown_form_falls_back_to_short_not_crash():
    """形が台帳に無い本で落ちないこと（`shippable_line` は毎周 撃たれる）。"""
    line = rebuild_cost(["z"], {})
    assert "short 1本" in line
