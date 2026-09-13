"""`trend.loop_open` / `loop_open_line`
—— **まだ予約していない台本の、輪（§4 (1)）の答えが いまの本文のものか**を毎周 印字する口。

2026-09-14 03:0x JST・`optimizer`・Opus。

**なぜ足したか**: `cli.loop_stale` は `lint` と `build` からしか撃たれません。
**予約する回は build を撃たないことがあります**（`schedule` の `build_sig` の門が通るため）ので、
**焼きが合っていて輪だけが古い本は、どの印字にも出ませんでした**。
この回に実際に踏んだ形は JOURNAL 2026-09-14 03:0x（09/14 02:0x の回が コマ13 の `say` を直し、
read も critique も build も撃たずに終い、METHOD §18 に「輪は閉じた」と書いた）。

**陽性対照つき**（§5 の教訓の形 3つ目 ＝ **落ちるまで撃つ**）。
"""
import datetime as dt
import json

from studio import script as sscript
from studio import trend

TODAY = dt.datetime(2026, 9, 14, 3, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))


def _script(vid: str, say: str = "たとえば、65歳の人。") -> dict:
    return {
        "id": vid,
        "date": vid[:10],
        "title": "検査の本",
        "takeaway": "検査のための本です。",
        "description": "検査",
        "tags": ["検査"],
        "segments": [{"say": say, "show": "けんさ", "sub": "けんさ", "tag": "前提"}],
        "notes": "検査",
    }


def _put(tmp_path, monkeypatch, *books: dict):
    monkeypatch.setattr(sscript, "SCRIPTS", tmp_path)
    for b in books:
        (tmp_path / f"{b['id']}.json").write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")


def _sig(vid: str) -> str:
    return sscript.load(vid).loop_sig()


def test_同じ指紋なら_fresh(tmp_path, monkeypatch):
    vid = "2026-09-15-a"
    _put(tmp_path, monkeypatch, _script(vid))
    rows = [{"event": "critique", "id": vid, "sig": _sig(vid), "at": "2026-09-14T01:00:00+09:00"}]
    q = trend.loop_open(rows, now=TODAY)
    assert [b["state"] for b in q["books"]] == ["fresh"]
    assert q["stale"] == [] and q["unknown"] == []


def test_本文が動いたら_stale_で_行に_名指しが出る(tmp_path, monkeypatch):
    """**この回に実際に踏んだ形**（輪を閉じたあとに `say` を直した）。"""
    vid = "2026-09-15-a"
    _put(tmp_path, monkeypatch, _script(vid, say="たとえば、65歳の人。"))
    old = _sig(vid)
    _put(tmp_path, monkeypatch, _script(vid, say="たとえば、所得195万円以下で、65歳の人。"))
    assert _sig(vid) != old
    rows = [{"event": "critique", "id": vid, "sig": old, "at": "2026-09-14T01:00:00+09:00"}]
    q = trend.loop_open(rows, now=TODAY)
    assert q["stale"] == [vid]
    line = trend.loop_open_line(rows, now=TODAY)
    assert "!!" in line and vid in line and "read → critique" in line


def test_予約ずみの本は数えない(tmp_path, monkeypatch):
    """**陽性対照**: 同じ台本でも `scheduled` の行が在れば、この口は黙る。"""
    vid = "2026-09-15-a"
    _put(tmp_path, monkeypatch, _script(vid))
    rows = [{"event": "critique", "id": vid, "sig": "2:ちがう", "at": "2026-09-14T01:00:00+09:00"}]
    assert trend.loop_open(rows, now=TODAY)["stale"] == [vid]
    rows.append({"event": "scheduled", "id": vid, "video_id": "xxx", "at": "2026-09-14T02:00:00+09:00"})
    assert trend.loop_open(rows, now=TODAY)["books"] == []


def test_過ぎた日の台本は数えない(tmp_path, monkeypatch):
    vid = "2026-09-13-a"
    _put(tmp_path, monkeypatch, _script(vid))
    rows = [{"event": "critique", "id": vid, "sig": "2:ちがう", "at": "2026-09-13T01:00:00+09:00"}]
    assert trend.loop_open(rows, now=TODAY)["books"] == []


def test_輪をまだ撃っていない本は_unknown_で_古いとは言わない(tmp_path, monkeypatch):
    vid = "2026-09-15-a"
    _put(tmp_path, monkeypatch, _script(vid))
    q = trend.loop_open([], now=TODAY)
    assert q["unknown"] == [vid] and q["stale"] == []
    assert "!!" not in trend.loop_open_line([], now=TODAY)


def test_指紋の版が違う行は_unknown(tmp_path, monkeypatch):
    """**版が違う行とは本文を比べられません**（`script.LOOP_SIG_VERSION`・`cli.loop_stale` と同じ）。"""
    vid = "2026-09-15-a"
    _put(tmp_path, monkeypatch, _script(vid))
    rows = [{"event": "critique", "id": vid, "sig": "1:" + _sig(vid).split(":")[1],
             "at": "2026-09-14T01:00:00+09:00"}]
    q = trend.loop_open(rows, now=TODAY)
    assert q["unknown"] == [vid] and q["stale"] == []


def test_指紋の無い古い行は_unknown(tmp_path, monkeypatch):
    """指紋を書く前の回の行 —— **古いかどうかを言えないので黙る**（嘘より安い）。"""
    vid = "2026-09-15-a"
    _put(tmp_path, monkeypatch, _script(vid))
    rows = [{"event": "critique", "id": vid, "at": "2026-09-14T01:00:00+09:00"}]
    assert trend.loop_open(rows, now=TODAY)["unknown"] == [vid]


def test_予約前の台本が_0件_のときも_1行_出る(tmp_path, monkeypatch):
    monkeypatch.setattr(sscript, "SCRIPTS", tmp_path)
    assert "予約前の台本 0件" in trend.loop_open_line([], now=TODAY)


def test_毎周の印字に入っている():
    """**印字して捨てない**（`cli.py` の註 ＝ 毎周 読む所に在ること）。"""
    src = (trend.__file__)
    with open(src, encoding="utf-8") as f:
        body = f.read()
    assert "out.append(loop_open_line(rows, now=now))" in body
