"""**GPT Image 2.0 の絵が、注文されて・受け取られて・動画の中に入ること。**

## なぜ要るか（2026-09-03 21:2x）

オーナー原文（2026-09-03 20:0x JST）:
**「動画内で使う画像はチャットgptのimages2.0を活用して」**

受け渡しの約束（`docs/IMAGE_ORDERS.md`）と置き場（`assets/images/`・
`data/image_orders/`）は 19:3x に切られていました。**ところが実測すると**
注文 0件・絵 0件・**`image_orders` を書くコード 0か所**・
**`assets/images` を読むコード 0か所**でした ——
**約束が文書だけで、機械の側が1行も無い**状態です
（この repo でいちばん多い壊れ方: **言っている所と、している所が別**）。

**この検査が見ているのは「絵が良いか」ではなく、道が繋がっているか**です:

    注文が置ける（**冪等**）      → 外のセッションが拾える
    届いた絵を見つけられる        → `image_for()`
    絵が画面に入る                → `build_html(..., bg_image=…)`
    **来なくても止まらない**      → `None` / 空文字で、今までどおり焼ける

**いちばん大事なのは最後の1つです。** `docs/IMAGE_ORDERS.md` が
「来ていなければ、**待たずに**自前の図解で焼くこと（**止めない**）」と言っています。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src import image_orders, visuals

VISUAL = {
    "kind": "stat",
    "headline": "年金の受け取り方を65歳と70歳で比べる",
    "stat": "月12万4500円",
    "note": "2026年4月改正の条件で計算",
}


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """**実物の `data/` と `assets/` を汚さない。**"""
    orders = tmp_path / "orders"
    images = tmp_path / "images"
    orders.mkdir()
    images.mkdir()
    monkeypatch.setattr(image_orders, "ORDERS", orders)
    monkeypatch.setattr(image_orders, "IMAGES", images)
    return orders, images


def test_注文の_id_は同じ本なら何度でも同じ():
    """**焼き直しで id が変わると、同じ絵を毎回 注文し直します**（外の1時間が溶ける）。"""
    a = image_orders.order_id("zaishoku-2026-62man", day="2026-09-04")
    b = image_orders.order_id("zaishoku-2026-62man", day="2026-09-04")
    assert a == b
    assert image_orders.ID_RE.match(a), a


def test_注文は冪等_二度目は書かない(sandbox):
    orders, _ = sandbox
    first = image_orders.place("topic-a", "背景", day="2026-09-04")
    assert first["already"] is False
    p = orders / f"{first['id']}.json"
    p.write_text(p.read_text(encoding="utf-8").replace('"pending"', '"done"'),
                 encoding="utf-8")
    second = image_orders.place("topic-a", "べつの文", day="2026-09-04")
    assert second["already"] is True
    # **上書きしていないこと**（外のセッションが書いた status を潰さない）。
    assert second.get("status") == "done"


def test_注文票に字を入れるなと必ず書いてある(sandbox):
    """生成画像の中の日本語は崩れます（`docs/IMAGE_ORDERS.md`）。
    **呼ぶ側に書かせない** —— 忘れると崩れた字が焼き付きます。"""
    row = image_orders.place("topic-b", "背景", day="2026-09-04")
    assert "文字" in row["avoid"]
    # 図表も入れさせない。こちらの計算した図と食い違って見えるため。
    assert "図表" in row["avoid"] or "グラフ" in row["avoid"]


def test_締切が近いと_late_が立つ_ただし止めない(sandbox):
    due = image_orders._now() + timedelta(minutes=30)
    row = image_orders.place("topic-c", "背景", day="2026-09-04", due=due)
    assert row["late"] is True
    far = image_orders._now() + timedelta(hours=9)
    row2 = image_orders.place("topic-d", "背景", day="2026-09-04", due=far)
    assert row2["late"] is False


def test_絵が来ていなければ_None_例外にしない(sandbox):
    """**`None` は異常ではなく、正常な合図です**（自前の図解で焼く）。"""
    assert image_orders.image_for("まだ無い本", day="2026-09-04") is None
    assert visuals.bg_image_for("まだ無い本") == ""


def test_実物のファイルが正本_受領の行ではない(sandbox):
    """`data/image_orders.jsonl` に done と書いてあってもファイルが無いことは在ります
    （push が途中で落ちた場合）。**実物を見ること。**"""
    _, images = sandbox
    oid = image_orders.order_id("topic-e", day="2026-09-04")
    assert image_orders.delivered(oid) is None
    (images / f"{oid}.jpg").write_bytes(b"\xff\xd8\xff\xdb" + b"0" * 64)
    assert image_orders.delivered(oid) is not None
    # **中身が空のファイルは「来ていない」扱い**（0バイトで push されることが在る）。
    (images / f"{oid}.jpg").write_bytes(b"")
    assert image_orders.delivered(oid) is None


def test_絵が無い画面は前と1文字も変わらない():
    off = visuals.build_html(VISUAL, None, False, 0, 1.0, False, "")
    # CSS の規則は常に在る（配色を差し込んで作る）。**要素のほうを見ること。**
    assert '<div class="bg-photo"' not in off
    assert '<div class="bg-veil"' not in off
    assert visuals.build_html(VISUAL, None, False, 0, 1.0, False) == off


def test_絵を渡すと画面に入る():
    html = visuals.build_html(VISUAL, None, False, 0, 1.0, False,
                              "data:image/jpeg;base64,AAAA")
    assert 'class="bg-photo"' in html
    assert "data:image/jpeg;base64,AAAA" in html
    # **暗幕が必ず一緒に入ること**（文字が読めなくなる）。
    assert 'class="bg-veil"' in html


def test_pending_は齢を出す_外のセッションが止まったのに気づく口(sandbox):
    image_orders.place("topic-f", "背景", day="2026-09-04")
    assert len(image_orders.pending()) == 1
    assert image_orders.pending(timedelta(hours=2)) == []


@pytest.mark.parametrize("portrait", [False, True])
def test_絵は数字の下に敷かれる_ブラウザに重ね順を数えさせる(portrait):
    """**主役は計算した数字です**（CLAUDE.md「自分で計算した結果を発表する」）。
    絵が上に来たら、この作りの根幹が崩れます。"""
    pw = pytest.importorskip("playwright.sync_api")

    # 1x1 の赤い PNG。
    png = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
           "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    probe = """() => {
      const z = el => getComputedStyle(el).zIndex;
      return {photo: z(document.querySelector('.bg-photo')),
              veil: z(document.querySelector('.bg-veil')),
              head: z(document.querySelector('.headline')),
              body: z(document.querySelector('.body'))};
    }"""
    size = visuals.VIEWPORT_PORTRAIT if portrait else visuals.VIEWPORT
    with pw.sync_playwright() as p:
        br = p.chromium.launch(executable_path=visuals._chromium_path(),
                               args=["--font-render-hinting=none"])
        pg = br.new_page(viewport={"width": size[0], "height": size[1]},
                         device_scale_factor=visuals.SCALE)
        pg.set_content(visuals.build_html(VISUAL, None, portrait, 0, 1.0, False, png),
                       wait_until="load")
        got = pg.evaluate(probe)
        bad_on = pg.evaluate(visuals._LINE_PROBE_JS)
        pg.set_content(visuals.build_html(VISUAL, None, portrait, 0, 1.0, False, ""),
                       wait_until="load")
        bad_off = pg.evaluate(visuals._LINE_PROBE_JS)
        br.close()

    assert int(got["photo"]) == 0 and int(got["veil"]) == 0, got
    assert int(got["head"]) == 1 and int(got["body"]) == 1, got
    # **絵を敷いても、折り返しは1つも動かないこと。**
    assert bad_on == bad_off, (bad_on, bad_off)
