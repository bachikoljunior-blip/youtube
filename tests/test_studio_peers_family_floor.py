"""**族の「床」（p25）**（`studio/peers.py`）—— 2026-09-16 14:4x・optimizer・Fable 5.1・ultracode。

固定 2（期限内にできるか → できる以外なら やり方を疑え）で疑った先:
**手は「どう作るか」に寄り、「どの族で作るか」は毎周 印字されるだけで、どこにも縛られていなかった。**
同じ corpus・同じ門（n≧10本）で、族の **床（下から1/4）は 生では 上と下で 5,087倍** 開きます。
**ただし その生の比は族の効きではありません**（15:0x に同じ回が撃って外した）——
**同じチャンネルの中で比べると 2.35倍**（2族 以上 を持つ口 29/218・上が大きい 23/29）で、
残りは口の大きさです（`title_shape` の「生の比を読むな」と同じ罠・`family_within_channel`）。
決めと数と覆る条件は `studio/peers.FAMILY_FLOOR_Q` の註・JOURNAL 2026-09-16 14:4x。

**陽性対照**（撃って落とした）:
 * `families()` の `floor` を `median` に替える → `test_床は中央値ではなく下から4分の1` が落ちる
 * `family_match()` の `all()` を `any()` に替える → `test_族は全部の語が当たった本だけ` が落ちる
 * `door_b_views()` の維持率を 1.0 に固定する → `test_扉bの回数は尺と維持率で動く` が落ちる
 * `family_within_channel()` の `pos[hi] == pos[lo]` の skip を外す（＝ 1族 の口が 1.00 を投げ込む）
   → `test_同じ口の中でだけ族を比べる` が落ちる（**撃って落とした**）
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


def test_同じ口の中でだけ族を比べる():
    """**1族 しか持たない口は数えない**（数えると自分で自分を割って 1.00 になる ＝ 退化）。"""
    rows = []
    # 口A: 2族 を持つ（上の族が 10倍）
    rows += [{"id": f"a{i}", "views": 1000, "form": "long", "q": "年金 手取り いくら",
              "channel": "A", "secs": 900} for i in range(12)]
    rows += [{"id": f"b{i}", "views": 100, "form": "long", "q": "医療費控除 いくら戻る",
              "channel": "A", "secs": 900} for i in range(12)]
    # 口B: 1族 しか持たない（**数に入ってはいけない**）
    rows += [{"id": f"c{i}", "views": 9, "form": "long", "q": "医療費控除 いくら戻る",
              "channel": "B", "secs": 900} for i in range(3)]
    w = peers.family_within_channel(rows)
    assert w["channels"] == 2 and w["n_channels"] == 1
    # **`total` が 1 であること**が、この検査の当のもの ——
    # skip を外すと 口B が 1.00 を投げ込んで `total` が 2 になり、比の中央が 5.5 へ薄まります
    assert w["total"] == 1 and w["up"] == 1
    assert w["ratio"] == 10.0


def test_床の行は生の比を族の効きと読ませない():
    rows = ([{"id": f"a{i}", "views": 200000, "form": "long", "q": "年金 手取り いくら",
              "channel": f"c{i}", "secs": 900} for i in range(12)]
            + [{"id": f"b{i}", "views": 5, "form": "long", "q": "医療費控除 いくら戻る",
                "channel": f"d{i}", "secs": 900} for i in range(12)])
    line = peers.family_floor_line(rows)
    # 生の比の隣に、必ず「同じチャンネルの中で」の断りが立つこと
    assert "生の比を「族の効き」と読まないこと" in line
    assert "同じチャンネルの中で比べると" in line
