"""`trend.views_absent` —— `viewCount` の欄が無い読みを、台帳から周をまたいで数える。

§7 (j)（`yt.views_of` の覆る条件 (1)）は「いま 0件・7本 過ぎて 1度も立たなければ外してよい」と
書きながら、**その 0件 も 7本 も、どこも数えていませんでした**（2026-09-10 21:0x に足した口）。

**陽性対照**（撃って落とした）:
`views_absent` の門（`r.get("views_absent")`）を外して全部の `measured` を数えると
`test_立っていない回は0件` が落ち、`VIEWS_ABSENT_SINCE` の刻の門を外すと
`test_口が在ってからの本だけを門の分母にする` が落ち、`ours` の絞りを外すと
`test_旧作りの本は門の分母に入れない` が落ちる。
"""
import datetime as dt

from studio import trend

JST = dt.timezone(dt.timedelta(hours=9))
SINCE = dt.datetime.fromisoformat(trend.VIEWS_ABSENT_SINCE)


def _m(vid: str, at: dt.datetime, views: int = 0, absent: bool = False,
       age_h: float = 1.0) -> dict:
    r = {"event": "measured", "id": vid, "age_h": age_h, "views": views,
         "at": at.isoformat()}
    if absent:
        r["views_absent"] = True
    return r


def _sched(vid: str) -> dict:
    return {"event": "scheduled", "video_id": vid, "at": SINCE.isoformat()}


def test_立っていない回は0件():
    rows = [_sched("a"), _m("a", SINCE + dt.timedelta(hours=1), views=12)]
    a = trend.views_absent(rows)
    assert a["n"] == 0 and a["books"] == []
    assert "欄が無い読み: 0件" in trend.views_absent_line(rows)


def test_立った本は名指しして0回を数から外させる():
    rows = [_sched("a"),
            _m("a", SINCE + dt.timedelta(hours=1), absent=True),
            _m("a", SINCE + dt.timedelta(hours=2), absent=True)]
    a = trend.views_absent(rows)
    assert a["n"] == 2 and a["books"] == ["a"], "行ではなく本で数える欄も持つこと"
    line = trend.views_absent_line(rows)
    assert "2件・1本" in line and "a" in line
    assert "数から外すこと" in line


def test_口が在ってからの本だけを門の分母にする():
    """陽性対照: 刻の門を外すと `since_books` が 2 になる。"""
    rows = [_sched("old"), _sched("new"),
            _m("old", SINCE - dt.timedelta(hours=3), views=5),
            _m("new", SINCE + dt.timedelta(hours=3), views=5)]
    assert trend.views_absent(rows)["since_books"] == 1


def test_旧作りの本は門の分母に入れない():
    """陽性対照: `ours` の絞りを外すと `since_books` が 2 になる。"""
    rows = [_sched("mine"),
            _m("mine", SINCE + dt.timedelta(hours=1), views=5),
            _m("legacy", SINCE + dt.timedelta(hours=1), views=5)]
    assert trend.views_absent(rows)["since_books"] == 1


def test_同じ本が毎周立っても本の数は1本():
    rows = [_sched("a")] + [_m("a", SINCE + dt.timedelta(hours=h), absent=True)
                            for h in (1, 2, 3, 4)]
    a = trend.views_absent(rows)
    assert (a["n"], len(a["books"])) == (4, 1)


# --- 門 7本 の分母（2026-09-13 20:3x・optimizer・Opus） ---------------------
# **踏んだ形**: `since_books` は 09/13 10:1x に 8本 ＝ 門 7本 を越えていましたが、
# その 8本 のうち 4本 は **この口が立った刻に既に 齢 28.5〜100.5h** で、
# `views_of` が挙げる 3つ の原因の 1つ「**処理の終わっていない本**」を
# **1度も見ていません**。＝ 8本 で「引かれた」と読むと、生きている口を空の数で外す。
#
# **陽性対照**（撃って落とした）: `since_books_early` の齢の門を外して
# `first` を全部 数えると `test_初測が遅い本は門の分母に入れない` が落ち、
# `drawn` を `since_books` の側で読むと `test_門は初測が若い本の側で読む` が落ちる。


def _early(vid: str, hours: int) -> list[dict]:
    """齢 1.0h で初めて測った本（門の分母に入る側）。"""
    return [_sched(vid), _m(vid, SINCE + dt.timedelta(hours=hours), views=5,
                            age_h=1.0)]


def test_初測が遅い本は門の分母に入れない():
    rows = [_sched("young"), _sched("old"),
            _m("young", SINCE + dt.timedelta(hours=1), views=5, age_h=2.0),
            _m("old", SINCE + dt.timedelta(hours=1), views=5, age_h=52.5)]
    a = trend.views_absent(rows)
    assert a["since_books"] == 2, "齢に依らない側の分母は 2本 のまま残すこと"
    assert a["since_books_early"] == 1 and a["early"] == ["young"]
    assert a["late"] == ["old"] and a["late_first_age_h"] == 52.5


def test_門は初測が若い本の側で読む():
    """陽性対照: `drawn` を `since_books` で読むと、この 8本 で引かれてしまう。"""
    rows = []
    for i in range(4):
        rows += _early(f"y{i}", i + 1)
    for i in range(4):
        rows += [_sched(f"o{i}"),
                 _m(f"o{i}", SINCE + dt.timedelta(hours=i + 1), views=5,
                    age_h=30.0)]
    a = trend.views_absent(rows)
    assert a["since_books"] == 8 and a["since_books_early"] == 4
    assert a["drawn"] is False, "8本 で外してはいけない（門は若い側の 4本）"
    line = trend.views_absent_line(rows)
    assert "まだ引けません" in line and "あと **4本**" in line
    assert "1度も見ていません" in line, "遅い初測の本は名指しして門から外すこと"


def test_若い本が門を越えたら引かれたと印字する():
    rows = []
    for i in range(trend.VIEWS_ABSENT_GATE + 1):
        rows += _early(f"y{i}", i + 1)
    a = trend.views_absent(rows)
    assert a["since_books_early"] == trend.VIEWS_ABSENT_GATE + 1
    assert a["drawn"] is True
    assert "引かれました" in trend.views_absent_line(rows)


def test_立った回は門を引かない():
    """`n` が 1件でも立ったら、本数に関わらず外してはいけない（覆る条件 (1)）。"""
    rows = []
    for i in range(trend.VIEWS_ABSENT_GATE + 1):
        rows += _early(f"y{i}", i + 1)
    rows.append(_m("y0", SINCE + dt.timedelta(hours=20), absent=True))
    a = trend.views_absent(rows)
    assert a["drawn"] is False and a["n"] == 1
    assert "数から外すこと" in trend.views_absent_line(rows)


def test_印字した門から引くと道具と同じ答えになる():
    """**印字した門 −  いまの分母 ＝ 印字した「あと N本」** であること。

    2026-09-13 21:5x JST（optimizer・Opus）に足した。**実物で払っていた値段**:
    `views_absent_line` は **「門 7本 … ＝ 4本 ＝ あと 4本」**と印字していました
    （`drawn` が `> GATE` ＝ 8本 で引くのに、印字は 7本）。読む側が引くと **3本** で、
    道具の答え（4本）と割れます。`trend.py` の他の門は全部 `>=` で、同じ言い回しのまま
    引き算が合う ＝ **この 1つ だけが同じ字で別の算**でした。

    **陽性対照**（撃って落とした）: 印字を `VIEWS_ABSENT_GATE` に戻すと、この検査が落ちる。
    """
    import re

    rows = []
    for i in range(4):
        rows += _early(f"y{i}", i + 1)
    line = trend.views_absent_line(rows)
    gate = int(re.search(r"門 (\d+)本", line).group(1))
    denom = int(re.search(r"＝ (\d+)本\*\* ＝", line).group(1))
    rest = int(re.search(r"あと \*\*(\d+)本\*\*", line).group(1))
    assert gate - denom == rest, f"印字した門 {gate} − 分母 {denom} ＝ {rest} にならない"
    assert gate == trend.VIEWS_ABSENT_NEED


def test_門の数と引かれる本の数は同じ物から出る():
    """`drawn` が立つ本の数 ＝ 印字した門。定数を 2か所 に置かないこと。"""
    rows = []
    for i in range(trend.VIEWS_ABSENT_NEED - 1):
        rows += _early(f"y{i}", i + 1)
    assert trend.views_absent(rows)["drawn"] is False
    rows += _early("last", trend.VIEWS_ABSENT_NEED)
    a = trend.views_absent(rows)
    assert a["since_books_early"] == trend.VIEWS_ABSENT_NEED
    assert a["drawn"] is True
