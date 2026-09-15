"""長尺の一手は **2か所**（前と出口）（2026-09-16 08:5x・optimizer・Fable 5.1・ultracode）。

**なぜこの検査が在るか**: 一手の門（`CTA_FROM` 2026-09-15）は、**まだ全部がショートだった日**に
引かれました。チャンネルは 09/14〜09/15 に長尺へ移り、**門は形と一緒に動きませんでした**。
実測（`data/retention.json`・`scripts/cta_reach.py` で数え直せる）:

    長尺 4本 の中央値   出口 **6.5%** ／ 5% の所 **75.8%** ／ 10% **38.5%** ／ 20% **18.7%**
    ショート 130本       出口 **21.4%**

＝ **出口だけに置くと、長尺では 1/3.3 の人にしか届いていませんでした。**
縛っているのは再生ではなく登録です（扉(b) が要る 1.62% 対 いま 0.041%）。
**門を消すには、この file を消すしかありません**（diff に出ます）。
"""
from __future__ import annotations

import json

from studio import script


def _seg(say: str = "たとえば、60歳の人。", sub: str = ""):
    return script.Segment(say=say, show="", sub=sub, tag="", board=[])


def _long(n: int, cta_at: int | None, date: str = "2026-09-20") -> script.Script:
    """n コマ の長尺。`cta_at` 番目（0 起点）に前の一手を置く。出口の一手は必ず置く。"""
    segs = [_seg() for _ in range(n - 1)]
    if cta_at is not None:
        segs[cta_at] = _seg(say="このあとも数字で出します。登録しておくと、とどきます。")
    segs.append(_seg(say="登録しておくと、あすの分がとどきます。"))
    return script.Script(id="t-early", date=date, title="て", takeaway="て",
                         form="long", yomi={}, segments=segs)


def _msg(s) -> list[str]:
    return [p for p in s.problems() if "長尺の前半に登録の一手" in p]


def test_前半に一手が無ければ止まる():
    assert _msg(_long(50, None))


def test_窓の中に在れば通る():
    """50コマ の 10% ＝ 5コマ目あたり。"""
    assert not _msg(_long(50, 4))


def test_窓より前は止まる():
    """**貰う前に頼まない** —— フックと最初の答えを先に渡す（下は 4%）。

    200コマ の本の 1コマ目 ＝ 0.5% の所。**50コマ だと 1コマ目 が既に 4% の中**なので、
    この検査は長い本で当てること（50コマ で書いて 1度 踏んだ）。
    """
    assert _msg(_long(200, 0))


def test_窓より後ろは止まる():
    """出口の 2.9倍 を切る所（20% より後ろ）は、置いたうちに入れない。"""
    assert _msg(_long(50, 30))


def test_ショートには当てない():
    """一手の置き場の判定は**長尺の retention から**引きました。ショートの数は別（陰性対照）。"""
    s = script.Script(id="t-early", date="2026-09-20", title="て #Shorts", takeaway="て",
                      form="short", yomi={},
                      segments=[_seg(), _seg(say="登録しておくと、とどきます。")])
    assert not _msg(s)


def test_出口の一手は別に要る():
    """前に置いたからといって、出口の門は開かない（2つ は別の門）。"""
    segs = [_seg() for _ in range(20)]
    segs[2] = _seg(say="登録しておくと、とどきます。")
    s = script.Script(id="t-early", date="2026-09-20", title="て", takeaway="て",
                      form="long", yomi={}, segments=segs)
    ps = s.problems()
    assert any("最後のコマに登録の一手が無い" in p for p in ps)
    assert not _msg(s)


def test_古い本は遡って赤くしない():
    ps = _long(50, None, date="2026-09-15").problems()
    assert not any("長尺の前半に登録の一手" in p for p in ps)
    assert script.EARLY_CTA_FROM == "2026-09-16"


def test_位置は累計字数で測る():
    """字/秒 は同じ本の中では 2.3% しか開かない ＝ 焼く前でも字で位置を言える。"""
    segs = [_seg(say="あ" * 10) for _ in range(10)]
    segs[0] = _seg(say="登録")           # 累計 2/(2+90) ≒ 2.2%
    assert script.early_cta_ratio(segs) < script.EARLY_CTA_LO
    assert script.early_cta_ratio([_seg(say="登録")]) == 1.0
    assert script.early_cta_ratio([_seg(say="あ")]) is None   # 一手が無い
    assert script.early_cta_ratio([]) is None                 # コマが無い
    # 画面の字だけでも拾う（出口の門と同じ ＝ `has_cta` と揃えてある）
    assert script.early_cta_ratio([_seg(say="あ", sub="登録すると")]) == 1.0


def test_型は声の上限に収まる():
    c = script.default_early_cta()
    assert len(c.say) <= script.MAX_SAY
    assert script.CTA_RE.search(c.say)
    assert "1本" not in c.say          # whisper が「いちぽん」と割る（出口の型と同じ註）
    assert c.say != script.default_cta().say   # 同じ文を 2度 鳴らさない


def test_窓は実測から引いてある():
    """窓を動かすなら、まず `scripts/cta_reach.py` を撃って数を見ること。"""
    assert (script.EARLY_CTA_LO, script.EARLY_CTA_HI) == (0.04, 0.20)
    assert (ROOT := __import__("pathlib").Path(script.__file__).parent.parent)
    assert (ROOT / "scripts" / "cta_reach.py").exists(), "数え直す口が消えたら、窓は根拠を失う"


def _scheduled_ids() -> set[str]:
    """**もう上げてある本**（`scheduled`）。動画の差し替えは再アップロードで、
    1本 1,650単位 かかり、予約の枠も取り直しになります ＝ **遡って赤くしない側**。"""
    out = set()
    led = __import__("pathlib").Path(script.__file__).parent.parent / "data" / "studio" / "ledger.jsonl"
    if not led.exists():
        return out
    for ln in led.read_text().splitlines():
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get("event") in ("scheduled", "uploaded") and d.get("id"):
            out.add(d["id"])
    return out


def test_これから焼く長尺は全部持っている():
    """**まだ上げていない**長尺の台本が、門を通っていること（**この回に入れた当のもの**）。

    日で切らないのは、予約が日と揃っていないからです —— 09/16〜09/19 の長尺 6本 は
    **09/15 のうちに もう上げてあり**、差し替えるには 1本 1,650単位（6本 で 9,900 ＝ ほぼ日枠 1日分）
    と予約の取り直しが要ります。**その判定は次の回へ**（`docs/JOURNAL.md` 2026-09-16 08:5x）。
    """
    done = _scheduled_ids()
    got = []
    for p in sorted(script.SCRIPTS.glob("*.json")):
        d = json.loads(p.read_text())
        if d["date"] < script.EARLY_CTA_FROM or d.get("form") != "long":
            continue
        if p.stem in done:
            continue
        s = script.load(p.stem)
        got.append((p.stem, not _msg(s)))
    assert got, "まだ上げていない長尺の台本が 1本も無い（この検査が空回りしている）"
    assert all(ok for _, ok in got), [n for n, ok in got if not ok]


# ---- A/B の側（置き場だけが違う 2群）--------------------------------------

def _ab_rows(tmp_path, early: bool, form: str = "long"):
    """長尺 1本。出口の一手は**両群とも**持たせる ＝ 測るのは置き場だけ。"""
    segs = [{"say": "あ" * 20} for _ in range(20)]
    if early:
        segs[1] = {"say": "登録しておくと、とどきます。"}   # 累計 ≒ 6%
    segs[-1] = {"say": "登録しておくと、あすの分がとどきます。"}
    (tmp_path / "a.json").write_text(json.dumps({
        "id": "a", "date": "2026-09-20", "title": "て", "takeaway": "て",
        "form": form, "segments": segs}, ensure_ascii=False))
    return [
        {"event": "scheduled", "id": "a", "video_id": "V1", "at": "2026-09-20T00:00:00+09:00"},
        {"event": "analytics_video", "id": "V1", "views": 1000, "subs_gained": 5,
         "at": "2026-09-22T00:00:00+09:00"},
    ]


def test_A_Bは前の一手の在る側と無い側を分ける(tmp_path):
    from studio import trend
    yes = trend.early_cta_cohorts(_ab_rows(tmp_path, True), scripts=tmp_path)
    assert yes["with"]["n"] == 1 and yes["without"]["n"] == 0
    no = trend.early_cta_cohorts(_ab_rows(tmp_path, False), scripts=tmp_path)
    assert no["with"]["n"] == 0 and no["without"]["n"] == 1


def test_A_Bはショートを数に入れない(tmp_path):
    """窓は長尺の retention から引いてある ＝ ショートを混ぜると別の数を測ります。"""
    from studio import trend
    c = trend.early_cta_cohorts(_ab_rows(tmp_path, True, form="short"), scripts=tmp_path)
    assert c["with"]["n"] == 0 and c["without"]["n"] == 0


def test_A_Bは3本たまるまで向きを読ませない(tmp_path):
    from studio import trend
    c = trend.early_cta_cohorts(_ab_rows(tmp_path, True), scripts=tmp_path)
    assert c["ready"] is False
    assert "たまるまで" in trend.early_cta_line(_ab_rows(tmp_path, True), scripts=tmp_path)


def test_行は毎周印字される側に在る():
    """`trend.lines` から外れたら、この A/B は誰も見ません（出口の A/B と同じ検査）。"""
    import inspect
    from studio import trend
    assert "early_cta_line(rows)" in inspect.getsource(trend.lines)
