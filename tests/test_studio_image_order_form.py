"""**画像の注文の大きさは形から引く**（2026-09-14 17:3x・optimizer・Opus）。

14:2x に長尺の形（`form: "long"` ＝ 横 1920x1080）を `studio/` へ足したが、
`cli.cmd_order_image` は `"size": "1080x1920"` を**字で**持っていた ＝
**長尺の本は縦の絵を注文する**。`slides.background` は cover-fit なので、
届いた縦の絵は**真ん中の 32% だけ**に切り取られて横の画面へ貼られ、**赤は 1件も出ない**
（1080x1920 を 1920x1080 に合わせると 倍率 1.778・高さ 3413px のうち 1080px だけが残る）。

**この検査のいちばんの仕事は 2つ**:
  (1) 注文の `size` が `script.Form.size` から来ること（字で持たない ＝ 門は 1か所）
  (2) **陰性対照** —— `short` の注文が 1字も動かないこと（公開ずみ 9本 ＋ 予約前 1本 と同じ形）
"""
import json
from pathlib import Path

import pytest
from PIL import Image

import studio.trend as tr
from studio import cli, script, slides


class _A:
    def __init__(self, id):
        self.id = id


def _put(tmp_path, sid, form):
    d = tmp_path / "scripts"
    d.mkdir(exist_ok=True)
    (d / f"{sid}.json").write_text(json.dumps({"form": form}), encoding="utf-8")
    return d


def _script(sid, form):
    title = "t #Shorts" if form == "short" else "t"
    n = 6 if form == "short" else 30
    say = "あ" * 40 if form == "short" else "あ" * 60
    return script.Script(id=sid, date="2026-09-15", title=title, takeaway="t", form=form,
                         segments=[script.Segment(say=say, show="x") for _ in range(n)])


# ---- (1) 注文の大きさ ------------------------------------------------------------------

@pytest.mark.parametrize("form,size", [("short", "1080x1920"), ("long", "1920x1080")])
def test_注文の大きさは形から来る(tmp_path, monkeypatch, form, size):
    monkeypatch.setattr(cli, "ORDERS", tmp_path / "orders")
    monkeypatch.setattr(cli.script, "load", lambda vid: _script(vid, form))
    monkeypatch.setattr(cli, "ledger", lambda *a, **k: None)
    assert cli.cmd_order_image(_A("t-order")) == 0
    o = json.loads((tmp_path / "orders" / "t-order-bg.json").read_text(encoding="utf-8"))
    assert o["size"] == size
    assert f"形 {form}" in o["for"]


def test_注文の大きさは幾何と同じ数():
    """**陽性対照** —— `script.Form.size` と `slides.Geom` がずれたら、この検査が先に落ちる
    （注文だけ直して画面を直さない回・その逆の回を、どちらも止める）。"""
    for name, g in (("short", slides.SHORT), ("long", slides.LONG)):
        f = script.form_of(name)
        assert f.size == (g.w, g.h)


def test_縦の本の注文は1字も動かない():
    """**陰性対照** —— 公開ずみ 9本 ＋ 予約前 1本 は `short`。この注文の `size` は
    どれも `1080x1920` で、直しの前後で同じでなければならない。"""
    from studio.script import SCRIPTS
    root = Path(tr.ROOT) / "data" / "image_orders"
    seen = 0
    for p in sorted(root.glob("*.json")):
        o = json.loads(p.read_text(encoding="utf-8"))
        sid = o["id"][:-3]
        if not (SCRIPTS / f"{sid}.json").exists():
            continue                      # 旧 `src/` の注文（§8）
        assert o["size"] == "1080x1920", p.name
        seen += 1
    assert seen >= 9                       # 台本の在る本は 10本（予約前 1本 を含む）


def test_置いたあとに形が動いた注文は名指しするだけで上書きしない(tmp_path, monkeypatch, capsys):
    """注文は 1度しか置かない（`p.exists()` で戻る）ので、**撃ち直しでは直りません**。
    直し方は json の書き換え ＝ ここは `!!` を出すところまで。"""
    monkeypatch.setattr(cli, "ORDERS", tmp_path / "orders")
    monkeypatch.setattr(cli, "ledger", lambda *a, **k: None)
    monkeypatch.setattr(cli.script, "load", lambda vid: _script(vid, "short"))
    cli.cmd_order_image(_A("t-order"))
    monkeypatch.setattr(cli.script, "load", lambda vid: _script(vid, "long"))
    capsys.readouterr()
    cli.cmd_order_image(_A("t-order"))
    out = capsys.readouterr().out
    assert "!!" in out and "1080x1920" in out and "1920x1080" in out
    o = json.loads((tmp_path / "orders" / "t-order-bg.json").read_text(encoding="utf-8"))
    assert o["size"] == "1080x1920"       # 黙って書き換えない（届いた絵の履歴が切れる）


# ---- (2) `trend.image_orders` が漏れを数える -------------------------------------------

def _dirs(tmp_path):
    o, i = tmp_path / "orders", tmp_path / "images"
    o.mkdir()
    i.mkdir()
    return o, i


def _order(o, sid, size):
    (o / f"{sid}-bg.json").write_text(json.dumps({"id": f"{sid}-bg", "size": size}),
                                      encoding="utf-8")


def test_形と違う大きさの注文を名指しする(tmp_path):
    o, i = _dirs(tmp_path)
    _order(o, "a", "1080x1920")
    d = _put(tmp_path, "a", "long")
    (i / "a-bg.jpg").write_bytes(b"x")
    q = tr.image_orders([], orders=o, images=i, scripts=d)
    assert len(q["mis_form"]) == 1 and "1920x1080" in q["mis_form"][0]


def test_形と同じなら名指ししない(tmp_path):
    """陰性対照 —— いま在る注文と同じ形（`short` の注文に `short` の台本）。"""
    o, i = _dirs(tmp_path)
    _order(o, "a", "1080x1920")
    d = _put(tmp_path, "a", "short")
    (i / "a-bg.jpg").write_bytes(b"x")
    assert tr.image_orders([], orders=o, images=i, scripts=d)["mis_form"] == []


def test_台本の無い注文は数えない(tmp_path):
    """旧 `src/` の注文（`2026-09-03-…` ほか）は形を訊く先が無い ＝ 数えない（§8）。"""
    o, i = _dirs(tmp_path)
    _order(o, "old", "1920x1080")
    d = tmp_path / "scripts"
    d.mkdir()
    assert tr.image_orders([], orders=o, images=i, scripts=d)["mis_form"] == []


def test_届いた絵の画素が注文と違えば名指しする(tmp_path):
    o, i = _dirs(tmp_path)
    _order(o, "a", "1920x1080")
    d = _put(tmp_path, "a", "long")
    Image.new("RGB", (1080, 1920), (0, 0, 0)).save(i / "a-bg.jpg")
    q = tr.image_orders([], orders=o, images=i, scripts=d)
    assert len(q["mis_file"]) == 1 and "1080x1920" in q["mis_file"][0]
    assert q["mis_form"] == []            # 注文と形は合っている（外れたのは焼いた側）


def test_画素が合っていれば名指ししない(tmp_path):
    o, i = _dirs(tmp_path)
    _order(o, "a", "1920x1080")
    d = _put(tmp_path, "a", "long")
    Image.new("RGB", (1920, 1080), (0, 0, 0)).save(i / "a-bg.jpg")
    assert tr.image_orders([], orders=o, images=i, scripts=d)["mis_file"] == []


def test_絵が読めなくても落ちない(tmp_path):
    """`_png_size` は None を返すだけ（絵が読めないことは、この口の答えではない）。"""
    o, i = _dirs(tmp_path)
    _order(o, "a", "1920x1080")
    d = _put(tmp_path, "a", "long")
    (i / "a-bg.jpg").write_bytes(b"not an image")
    assert tr.image_orders([], orders=o, images=i, scripts=d)["mis_file"] == []


def test_いまの台帳では食い違い0件():
    """**この回の実物**（注文 18件・届いた絵 18枚 ＝ 画素まで注文どおり）。
    ここが落ちた回は、絵か注文のどちらかが動いている。"""
    from studio.common import ledger_rows
    q = tr.image_orders(ledger_rows())
    assert q["mis_form"] == [] and q["mis_file"] == []
    assert "大きさの食い違い 0件" in tr.image_line(ledger_rows())
