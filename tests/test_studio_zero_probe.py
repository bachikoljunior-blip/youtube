"""`cli.zero_probe_target` —— **公開ずみなのに 0回** の本を、1単位 で「出ていない側か」まで見る。

2026-09-10 15:0x・optimizer・Opus。5本目 `2YZ_4FXC-XI` が 齢 4.5h で 0回 だった回に足した。

**穴**: `yt.readiness()` は 09/08 02:5x から在るのに、`cmd_status` は
**`privacy != "public"` の本にしか当てていなかった** ＝ 公開したあとに処理が落ちた本・
拒否された本は、誰も見ない（見えるのは「0回」だけで、`trend` の側では
「配りが来ていない」と同じ形）。§4 (0-b) の族の 4つ目の型。

**この回に手で撃った実測**（`videos.list` 1単位・`2YZ_4FXC-XI` 齢 4.5h 0回）:
upload=processed・processing=succeeded・失敗なし・public・madeForKids false・PT1M30S
＝ **0回 は本物**。その1単位を道具へ入れた。

**陽性対照つき**（§5 の教訓の形 3つ目「陽性対照は落ちるまで撃つ」）。2026-09-10 15:0x に動かして確かめた:
  * 齢の門（`ZERO_PROBE_MIN_H`）を 0.0 にする → `test_齢が浅い本は引かない` が落ちる
  * studio の本の門を外す → `test_旧作りの本は引かない` が落ちる
  * 「いちばん若い1本だけ」を「全部」にする → `test_0回が2本_並んでも1本だけ` が落ちる
  * `views_absent` の門を外す → `test_欄が無い本は別の口なので引かない` が落ちる
  * `zero_probe_mark` の `ok` の枝を空文字にする → `test_okでも黙らない` が落ちる
"""
import datetime as dt

from studio import cli
from studio.common import JST


NOW = dt.datetime.now(JST)


def _v(vid, hours_ago, views=0, absent=False):
    at = NOW - dt.timedelta(hours=hours_ago)
    return {"id": vid, "title": "題", "privacy": "public", "publish_at": None,
            "published_at": at.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "views": views, "views_absent": absent, "likes": 0, "comments": 0}


def test_0回のまま門を越えた本を引く():
    assert cli.zero_probe_target([_v("a", 4.5)], {"a"}, NOW) == "a"


def test_齢が浅い本は引かない():
    """1回目が付くまでの齢は台帳で 5.0h まで（§7）。0.5h の 0回 はまだ何も言えない。"""
    assert cli.zero_probe_target([_v("a", 0.5)], {"a"}, NOW) is None


def test_齢が深い本は引かない():
    """48h を越えたら「配りが来ていない」ほうの話 ＝ 処理は関係ない。"""
    assert cli.zero_probe_target([_v("a", 120.0)], {"a"}, NOW) is None


def test_旧作りの本は引かない():
    """旧作りの 0回（09/05 の長尺 `fMlY_uzHOMw` の型）は診る先が無い ＝ §8。"""
    assert cli.zero_probe_target([_v("a", 4.5)], set(), NOW) is None


def test_再生が付いた本は引かない():
    assert cli.zero_probe_target([_v("a", 4.5, views=1)], {"a"}, NOW) is None


def test_欄が無い本は別の口なので引かない():
    """`viewCount` の欄が無い読みは `yt.views_of` の口（§7 (j)）。二重に引かない。"""
    assert cli.zero_probe_target([_v("a", 4.5, absent=True)], {"a"}, NOW) is None


def test_0回が2本_並んでも1本だけ():
    """1周 1単位 を越えないこと。選ぶのは**いちばん若い**本。"""
    assert cli.zero_probe_target([_v("old", 30.0), _v("young", 4.0)],
                                 {"old", "young"}, NOW) == "young"


def test_okでも黙らない():
    """`ok` のときこそ「0回 は本物」と言うのがこの行の仕事。"""
    m = cli.zero_probe_mark({"ok": True, "upload": "processed", "processing": "succeeded",
                             "failure": None, "rejection": None})
    assert "出ていない側ではありません" in m
    assert "processed" in m


def test_okでないときは覆る条件を名指しする():
    m = cli.zero_probe_mark({"ok": False, "upload": "rejected", "processing": "failed",
                             "failure": None, "rejection": "copyright"})
    assert "!!" in m and "copyright" in m and "覆る条件 (1)" in m


def test_5本目の実物の形で引ける():
    """この回に `videos.list` で見た形（齢 4.5h・viewCount 欄あり・値 0）。"""
    assert cli.zero_probe_target([_v("2YZ_4FXC-XI", 4.5)], {"2YZ_4FXC-XI"}, NOW) == "2YZ_4FXC-XI"
