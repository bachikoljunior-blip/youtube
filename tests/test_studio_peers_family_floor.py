"""**族の「床」（p25）**（`studio/peers.py`）—— 2026-09-16 15:0x・optimizer・Fable 5.1・ultracode。

固定 2（期限内にできるか → できる以外なら やり方を疑え）で疑った先:
**手は「どう作るか」に寄り、「どの族で作るか」は毎周 印字されるだけで、どこにも縛られていなかった。**
同じ corpus・同じ門（n≧10本）で、族の **床（下から1/4）は 上と下で 5,087倍** 開きます
（中央値の 3,187倍 より大きい）＝ **作りでは埋まらない差**。
決めと数と覆る条件は `studio/peers.FAMILY_FLOOR_Q` の註・JOURNAL 2026-09-16 15:0x。

**陽性対照**（撃って落とした）:
 * `families()` の `floor` を `median` に替える → `test_床は中央値ではなく下から4分の1` が落ちる
 * `family_match()` の `all()` を `any()` に替える → `test_族は全部の語が当たった本だけ` が落ちる
 * `door_b_views()` の維持率を 1.0 に固定する → `test_扉bの回数は尺と維持率で動く` が落ちる
"""
from studio import peers


def _long(vid, views, q):
    return {"id": vid, "views": views, "form": "long", "q": q, "channel": "c" + vid, "secs": 900}


def test_床は中央値ではなく下から4分の1():
    rows = [_long(f"v{i}", v, "族A") for i, v in enumerate([10, 20, 30, 40, 100])]
    f = peers.families(rows)[0]
    assert f["median"] == 30
    assert f["floor"] == 20          # 10,20,30,40,100 の p25
    assert f["floor"] < f["median"]


def test_分位は端でも落ちない():
    assert peers._quantile([], 0.25) == 0.0
    assert peers._quantile([7], 0.25) == 7


def test_族は全部の語が当たった本だけ():
    fams = ["年金 手取り いくら", "退職金 税金 いくら"]
    # 「年金」1語 では入らない（`any` にすると入ってしまう ＝ 陽性対照）
    assert peers.family_match("年金の話", fams) == []
    assert peers.family_match("年金の手取りはいくら", fams) == ["年金 手取り いくら"]


def test_扉bの回数は尺と維持率で動く():
    # 4,000時間 ÷（900秒 × 45.5%）＝ 35,164回
    assert peers.door_b_views(900, 0.455) == 35164
    # 尺が半分なら要る回数は倍 ＝ **この数は点ではない**
    assert peers.door_b_views(450, 0.455) == 70329


def test_床の行は判定しない_数と族を並べるだけ():
    rows = ([_long(f"a{i}", 200000, "年金 手取り いくら") for i in range(12)]
            + [_long(f"b{i}", 5, "医療費控除 いくら戻る") for i in range(12)])
    line = peers.family_floor_line(rows)
    assert "年金 手取り いくら" in line and "医療費控除" in line
    assert "判定は立ったサブとオーナー" in line
    for word in ("すべき", "やめろ", "必ず"):
        assert word not in line


def test_1本の族は床の高い順に返る():
    rows = ([_long(f"a{i}", 200000, "年金 手取り いくら") for i in range(12)]
            + [_long(f"b{i}", 5, "遺族年金 いくら 計算") for i in range(12)])
    hit = peers.family_of("年金の手取りと遺族年金はいくら", [], rows)
    assert [h["q"] for h in hit] == ["年金 手取り いくら", "遺族年金 いくら 計算"]
    # 入る族が無いときは空 ＝ **「天井が低い」ではなく「測っていない」**
    assert peers.family_of("不動産の話", [], rows) == []


def test_lintの註は長尺だけ_止めない():
    from studio import cli

    class S:
        form = "short"
        title = "年金の手取りはいくら"
        tags: list = []
    assert cli._family_floor_notes(S()) == []
    S.form = "long"
    notes = cli._family_floor_notes(S())
    assert len(notes) == 1 and "扉(b)" in notes[0]
