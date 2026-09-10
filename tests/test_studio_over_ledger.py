"""`status` の生の読みが台帳の最大を越えたときに、それを捨てないこと。

2026-09-10 12:4x JST（optimizer・Opus）。**この回に踏んだ形を、そのまま検査にした** ——
12:25 の `status` が 3本目 を 658回 と印字し、7分後の `measure` が 613回 を台帳へ書いた。
derivation は `studio/cli.over_ledger` の註と JOURNAL。

**陽性対照つき**（§5 の教訓の形3つ目「壊したら落ちるまで撃つ」）:
比べる先を「最大」から「最後の行」へ落とすと `test_数え直しで峰が落ちた本では最後の行で比べない` が落ち、
`>` を `>=` にすると `test_同じ値では鳴らない` が落ちる。
"""
from studio.cli import over_ledger


def _m(vid, views, at="2026-09-10T12:00:00+09:00"):
    return {"event": "measured", "id": vid, "views": views, "at": at}


def test_台帳より高い読みは差を返す():
    rows = [_m("a", 613)]
    assert over_ledger("a", 658, rows) == 45


def test_台帳より低い読みは鳴らない():
    """遅れている複製は既知で envelope が吸う（§6）。ここでは印字しない。"""
    rows = [_m("a", 658)]
    assert over_ledger("a", 613, rows) is None


def test_同じ値では鳴らない():
    rows = [_m("a", 613)]
    assert over_ledger("a", 613, rows) is None


def test_台帳にその本が無ければ鳴らない():
    """公開したばかりの本は台帳に行が無い ＝ 比べる先が無いので黙る。"""
    assert over_ledger("new", 0, [_m("a", 613)]) is None


def test_数え直しで峰が落ちた本では最後の行で比べない():
    """`recounts` は峰を落とすので、**最後の行より高い値が台帳に在る**（§6）。

    比べる先を最後の行にすると、既に台帳が持っている 216 を「まだ無い」と鳴らす。
    """
    rows = [_m("a", 216, "2026-09-09T10:00:00+09:00"),
            _m("a", 214, "2026-09-10T10:00:00+09:00")]
    assert over_ledger("a", 215, rows) is None
    assert over_ledger("a", 217, rows) == 1


def test_measured_以外の行は数えない():
    rows = [{"event": "built", "id": "a", "views": 9999},
            _m("a", 613)]
    assert over_ledger("a", 658, rows) == 45


def test_views_が数でない行は落とす():
    rows = [{"event": "measured", "id": "a", "views": None}, _m("a", 613)]
    assert over_ledger("a", 658, rows) == 45
