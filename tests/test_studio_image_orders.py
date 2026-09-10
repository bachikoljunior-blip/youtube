"""`trend.image_orders` —— **届いた絵が、いちばん新しい build に載っているか**
（2026-09-11 02:0x・optimizer・Opus）。

`cmd_order_image` は注文を置くとき「届いたら build し直す」と印字するが、
**そのあと誰も見ていなかった**。実測（この検査を足した回）: 7本目
`2026-09-12-taishoku-koujo-70man` は 00:32・00:39 の 2回 とも `image=False` で焼かれ、
絵は 01:34 に届いた ＝ §15 の「12コマ とも目で見た」は**単色の sheet.png** を見ていた。
"""
import studio.trend as tr


def _dirs(tmp_path):
    o = tmp_path / "orders"
    i = tmp_path / "images"
    o.mkdir()
    i.mkdir()
    return o, i


def _order(o, vid):
    (o / f"{vid}-bg.json").write_text("{}", encoding="utf-8")


def _image(i, vid, ext="jpg"):
    (i / f"{vid}-bg.{ext}").write_bytes(b"x")


def _built(vid, image, at):
    return {"event": "built", "id": vid, "image": image, "at": at}


def test_届いた数を数える(tmp_path):
    o, i = _dirs(tmp_path)
    _order(o, "a"); _order(o, "b"); _order(o, "c")
    _image(i, "a"); _image(i, "b", ext="png")
    q = tr.image_orders([], orders=o, images=i)
    assert q["n"] == 3 and q["delivered"] == 2 and q["missing"] == ["c-bg"]


def test_絵は在るのに最後のbuildが単色なら名指しする(tmp_path):
    """**この回に実際に踏んだ形**（09/12 の本）。"""
    o, i = _dirs(tmp_path)
    _order(o, "a"); _image(i, "a")
    rows = [_built("a", False, "2026-09-11T00:32:00+09:00"),
            _built("a", False, "2026-09-11T00:39:00+09:00")]
    assert tr.image_orders(rows, orders=o, images=i)["restale"] == ["a"]


def test_あとで焼き直してあれば名指ししない(tmp_path):
    """陰性対照 —— 台帳の 5本 のうち 3本 はこの形（先に単色・あとで絵つき）。"""
    o, i = _dirs(tmp_path)
    _order(o, "a"); _image(i, "a")
    rows = [_built("a", False, "2026-09-11T00:32:00+09:00"),
            _built("a", True, "2026-09-11T02:00:00+09:00")]
    assert tr.image_orders(rows, orders=o, images=i)["restale"] == []


def test_順番を見ないと見落とす(tmp_path):
    """**陽性対照** —— 「1度でも絵つきで焼けたか」で見ると、この本を見落とす。

    絵つきの build が**先**に在り、そのあと単色で焼き直された本
    （絵の file が消えた・名が変わった回）。`any(image)` で数える実装なら
    `restale` は空になり、この検査が落ちる。
    """
    o, i = _dirs(tmp_path)
    _order(o, "a"); _image(i, "a")
    rows = [_built("a", True, "2026-09-11T00:10:00+09:00"),
            _built("a", False, "2026-09-11T00:39:00+09:00")]
    assert tr.image_orders(rows, orders=o, images=i)["restale"] == ["a"]


def test_絵が届いていない本は焼き直し待ちではない(tmp_path):
    """陰性対照 —— 単色で焼くしかなかった本を「焼き直せ」と言わないこと（**止めない**）。"""
    o, i = _dirs(tmp_path)
    _order(o, "a")                      # 絵は置かない
    rows = [_built("a", False, "2026-09-11T00:39:00+09:00")]
    q = tr.image_orders(rows, orders=o, images=i)
    assert q["restale"] == [] and q["missing"] == ["a-bg"]


def test_行は焼き直しが要るときだけ鳴る(monkeypatch):
    monkeypatch.setattr(tr, "image_orders",
                        lambda rows, **kw: {"n": 1, "delivered": 1, "missing": [],
                                            "restale": ["a"], "built_books": 1})
    assert "!!" in tr.image_line([])
    monkeypatch.setattr(tr, "image_orders",
                        lambda rows, **kw: {"n": 1, "delivered": 1, "missing": [],
                                            "restale": [], "built_books": 1})
    line = tr.image_line([])
    assert "!!" not in line and "0本" in line


def test_毎周の並びに出る():
    """印字だけにしない族 —— `trend` の報告に、この行が在ること。"""
    body = "\n".join(tr.report())
    assert "画像の注文" in body
