"""`trend.hold` —— 「齢 Nh までに、いまの再生の何%が付いていたか」（2026-09-09 23:2x・optimizer・Opus）。

§7 の「90秒の上限」の行は 09/05 から **`measured` の 6時間再生／48時間再生の比**を見ろと書いているのに、
その比を出す道具が 4日 のあいだ無く、1度も数えられていなかった。この検査はその比を機械に留める。
"""
import datetime as dt

import studio.trend as tr


def _rows(points, vid="AAA", start="2026-09-08T10:00:00+09:00", scheduled=True):
    """(齢h, 生の再生) の並びから measured 行を作る。"""
    pub = dt.datetime.fromisoformat(start)
    out = []
    if scheduled:
        out.append({"event": "scheduled", "video_id": vid, "at": start})
    for age, views in points:
        out.append({
            "event": "measured", "id": vid, "age_h": age, "views": views,
            "at": (pub + dt.timedelta(hours=age)).isoformat(),
        })
    return out


def test_pct_is_share_of_now():
    rows = _rows([(1.0, 10), (6.0, 40), (30.0, 100)])
    six = tr.hold(rows)[0]["at"][6.0]
    assert six["views"] == 40 and round(six["pct"]) == 40


def test_both_ends_are_read_from_the_envelope_not_the_raw_point():
    """**分子も分母も、遅れている複製に落ちてはいけない**（`envelope` の註 ＝ 最大 28% 下に外す）。

    分子: 6h の直前に高い点が在れば、6h の生の点が低くてもその高い側を採る。
    分母: 最後の点が遅れた複製でも、いまの再生はそれまでの最大。
    """
    rows = _rows([(1.0, 10), (5.0, 80), (6.0, 20), (30.0, 100), (31.0, 72)])
    got = tr.hold(rows)[0]
    assert got["views"] == 100                    # 分母 —— 生の 72 で終わらない
    assert got["at"][6.0]["views"] == 80          # 分子 —— 生の 20 に落ちない
    assert round(got["at"][6.0]["pct"]) == 80


def test_no_point_yet_is_none_not_zero():
    """齢が届いていない所は **None**（0% ではない）。13h の本を「24h で 100%」と読ませない。"""
    rows = _rows([(1.0, 10), (6.0, 40), (13.0, 90)])
    got = tr.hold(rows)[0]
    assert got["at"][12.0] is not None
    assert got["at"][24.0] is None
    assert "24h   -" in "\n".join(tr.hold_lines(rows))


def test_growing_book_is_marked_because_its_share_is_an_upper_bound():
    """**確定は「平らの長さ」で決める**（2026-09-11 05:4x に、直近2点から `flats` の境目へ移した）。

    前の形は `env[-1] > env[-2]` ——**直近2点がたまたま同じ値**なら、
    0.5時間 前に伸びた本でも「確定」と印字していた（`hold` の 05:4x の註）。
    """
    growing = tr.hold(_rows([(1.0, 10), (6.0, 40), (30.0, 100)]))[0]
    assert growing["growing"] is True
    # **門（`flats` の境目・この並びでは床の 24時間）を越えて平らな本だけが確定**
    settled_rows = _rows([(1.0, 10), (6.0, 40), (30.0, 100), (95.0, 100)])
    settled = tr.hold(settled_rows)[0]
    assert settled["growing"] is False
    assert settled["since_rise_h"] == 65.0 and settled["flat_thresh_h"] == 24.0
    assert "確定" in "\n".join(tr.hold_lines(settled_rows))


def test_band_count_is_derived_from_the_numbers_not_a_copy():
    """**印字の数は数から作る**（§7 が 7周 踏んだ「写しを持たない」）。

    2026-09-10 05:0x に `n/m` から「帯の中 n本・帯の外 m本・分けられない k本」へ変えた
    （`trend.hold_verdict` の註）。**どちらの形でも、写しを持たないことは同じ。**
    """
    inside = _rows([(1.0, 10), (6.0, 80), (30.0, 100), (95.0, 100)], vid="IN")
    assert "帯の中 1本・帯の外 0本・分けられない 0本" in "\n".join(tr.hold_lines(inside))
    outside = _rows([(1.0, 10), (6.0, 40), (30.0, 100), (95.0, 100)], vid="OUT")
    assert "帯の中 0本・帯の外 1本・分けられない 0本" in "\n".join(tr.hold_lines(outside))
    assert "帯の中 1本・帯の外 1本・分けられない 0本" in "\n".join(tr.hold_lines(inside + outside))


# ---------------------------------------------------------------------------
# 挟み（2026-09-10 05:0x・optimizer・Opus）
#   `hold` は「h 以前の最後の点」を採るので、6h ちょうどの点が無い本では
#   **1.7時間 手前の点を「6h の値」として数えて**いた。`trend.hold_verdict` の註。
# ---------------------------------------------------------------------------

def test_上は_h_を越えた最初の点で作る():
    """真の 6h の値は「6h 以前の最後の点」以上・「6h を越えた最初の点」以下。"""
    six = tr.hold(_rows([(1.0, 10), (4.3, 61), (7.0, 90), (60.0, 100), (61.0, 100)]))[0]["at"][6.0]
    assert six["age_h"] == 4.3 and round(six["pct"]) == 61
    assert six["hi_age_h"] == 7.0 and round(six["hi_pct"]) == 90


def test_h_ちょうどの点が在れば挟みは潰れる():
    """6h の点が在るなら、挟む物は無い（下 ＝ 上 ＝ その点）。"""
    six = tr.hold(_rows([(1.0, 10), (6.0, 39), (7.1, 45), (60.0, 100), (61.0, 100)]))[0]["at"][6.0]
    assert six["age_h"] == 6.0
    assert six["hi_age_h"] == 6.0 and six["hi_pct"] == six["pct"]
    assert tr.hold_verdict(six, growing=False) == "out"


def test_帯を跨いだ本は分けられないで_帯の外に数えない():
    """**陽性対照つきの本体** —— 実物 `EkNqtkK49Bw` の形（挟み 61% 〜 90%）。

    直す前は「6h の点 ＝ 61%」の 1点 で見て **帯の外** に数えており、
    その 0/4 が §1 と §7 に写っていた。挟みは帯 70〜90% を跨ぐので **分けられない**。
    """
    rows = _rows([(1.0, 10), (4.3, 61), (7.0, 90), (60.0, 100), (61.0, 100)])
    six = tr.hold(rows)[0]["at"][6.0]
    assert tr.hold_verdict(six, growing=False) == "unknown"
    line = "\n".join(tr.hold_lines(rows))
    assert "分けられない 1本" in line and "帯の外 0本" in line
    # **陽性対照**: 上を見ずに下の 1点 だけで判定すると（＝ 直す前の形）「帯の外」になる。
    assert tr.hold_verdict({"pct": six["pct"], "hi_pct": six["pct"]}, growing=False) == "out"


def test_伸びている本に_帯の中_は返さない():
    """分母（いまの再生）が増える ＝ `pct` も `hi_pct` も**上限** ＝ 下限が下限でない。"""
    growing = tr.hold(_rows([(1.0, 10), (4.0, 75), (7.0, 88), (30.0, 100)]))[0]
    assert growing["growing"] is True
    assert tr.hold_verdict(growing["at"][6.0], growing=True) == "unknown"
    # **陽性対照**: 同じ挟みでも、確定した本なら「帯の中」と言い切れる。
    assert tr.hold_verdict(growing["at"][6.0], growing=False) == "in"


def test_上限が帯の下より低ければ_伸びていても外と言い切れる():
    """上限が 70% を割っていれば、分母がこれから増えても帯には入らない。"""
    six = tr.hold(_rows([(1.0, 10), (5.3, 49), (6.3, 59), (30.0, 100)]))[0]["at"][6.0]
    assert round(six["hi_pct"]) == 59
    assert tr.hold_verdict(six, growing=True) == "out"


def test_実物の台帳で_分けられない本が_1本_出る():
    """実物（`EkNqtkK49Bw` は 齢4.3h と 齢7.0h に挟まれ、帯 70〜90% を跨ぐ）。

    **この検査は数を固定しません**（本が増えれば動く）—— 見るのは
    「**挟みが帯を跨いだ本を、帯の外に数えていないこと**」だけ。
    """
    rows = tr.ledger_rows()
    got = tr.hold(rows)
    seen = {r["id"]: tr.hold_verdict(r["at"][6.0], bool(r["growing"])) for r in got if r["at"][6.0]}
    for r in got:
        six = r["at"][6.0]
        if not six:
            continue
        lo, hi = six["pct"], six["hi_pct"]
        if lo < tr.HOLD_BAND[0] <= hi:            # 挟みが帯の下端を跨いでいる
            assert seen[r["id"]] != "out", r["id"]


def test_only_our_books():
    """旧作りの本（`scheduled` の無い id）は出さない —— §1 の帯はこちらの作りの話。"""
    old = _rows([(1.0, 10), (6.0, 40), (60.0, 100)], vid="OLD", scheduled=False)
    assert tr.hold(old) == []


def test_ledger_now_answers_the_question_section7_asked():
    """実物の台帳で 6h の割合が出ること（4日 間 出ていなかった数）。"""
    got = tr.hold(tr.ledger_rows())
    six = [r for r in got if r["at"][6.0]]
    assert len(six) >= 4
    assert all(0 < r["at"][6.0]["pct"] <= 100 for r in six)


# ---------------------------------------------------------------------------
# 「確定」は平らの長さで決める（2026-09-11 05:4x・optimizer・Opus）
#   この回に踏んだ形: 3本目 `lQHX9LJ80Sg` が **0.5時間 前に +2回 伸びた**まま
#   「確定」へ落ちた（直近2点が同じ値だった ＝ それだけ）。`hold` の 05:4x の註。
# ---------------------------------------------------------------------------

def test_直近2点が平らなだけの本を確定と読まない():
    """**踏んだ実物の形**（齢 67h・0.5時間 前に伸び・最後の2点が同じ値）。"""
    rows = _rows([(1.0, 10), (6.0, 200), (66.0, 690), (66.7, 692), (67.2, 692)])
    got = tr.hold(rows)[0]
    assert got["since_rise_h"] == 0.5
    assert got["growing"] is True
    line = "\n".join(tr.hold_lines(rows))
    assert "まだ伸びている" in line and "最後の伸びから 0.5h" in line
    # **陽性対照**: 直す前の形（直近2点だけ）は、この本を「確定」と読む。
    env = tr.envelope(tr.series(rows)[list(tr.series(rows))[0]])
    assert (env[-1] > env[-2]) is False


def test_門は_flats_の境目で_定数を足していない():
    """門は `flats` が実測から引き直す（`FLAT_STOP_H` はその床）。**新しい定数は無い。**"""
    # 「20時間 平らだったあとに伸びた」本が同じ台帳に居ると、門はその長さより上へ動く。
    resumed = _rows([(1.0, 10), (10.0, 50), (40.0, 50), (41.0, 90), (120.0, 90)], vid="BACK")
    thresh = tr.flats(resumed)["thresh_h"]
    assert thresh == tr.hold(resumed)[0]["flat_thresh_h"]
    assert thresh >= tr.FLAT_STOP_H


def test_一度も伸びていない本は_並びの全長で見る():
    """伸びた点が 1つも無い本を、`0時間 前に伸びた`（＝ 門を素通り）と読まないこと。"""
    rows = _rows([(1.0, 7), (30.0, 7), (95.0, 7)])
    got = tr.hold(rows)[0]
    assert got["since_rise_h"] == 94.0 and got["growing"] is False
    # **陽性対照**: 同じ形でも、まだ 24時間 に届いていなければ確定にしない。
    young = tr.hold(_rows([(1.0, 7), (30.0, 7), (50.0, 7)], vid="YOUNG"))[0]
    assert young["since_rise_h"] == 49.0 and young["growing"] is False
    fresh = tr.hold(_rows([(1.0, 7), (20.0, 7)], vid="FRESH"))[0]
    assert fresh["growing"] is True          # 齢 48h 前 ＝ 分母はこれから増える


def test_実物の台帳で_確定の本は最後の伸びから門を越えている():
    """**この検査は数を固定しません**（本が増えれば動く）—— 見るのは規則だけ。"""
    got = tr.hold(tr.ledger_rows())
    assert got
    for r in got:
        if not r["growing"]:
            assert r["age_h"] >= 48.0
            assert r["since_rise_h"] >= r["flat_thresh_h"], r["id"]


def test_帯の判定は_この直しで動いていない():
    """**向きは変わらないこと**（05:4x の註）——伸びている本に「帯の中」は返さない側は同じ。"""
    got = tr.hold(tr.ledger_rows())
    tally = {"in": 0, "out": 0, "unknown": 0}
    for r in got:
        v = tr.hold_verdict(r["at"][6.0], bool(r["growing"]))
        if v:
            tally[v] += 1
    assert tally["in"] == 0                  # 帯の中と言い切れる本は 0本 のまま
