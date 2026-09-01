"""**上端が「棚」か「1本の飛び出し」かを分ける検査**（2026-09-02 に足した）。

`max/10位` は「上位が団子か」しか言いません。**団子は1日で作れます** ——
1本が跳ねて同じ日の隣を連れて上げれば、上位は簡単に固まります。
`shelf()` は「**別々の日の別々の題が、何度でも同じ高さで止まるか**」を見ます。

**これが赤くなるのは、`shelf()` が日付を見なくなったとき**です。
そのとき前提「per_video の天井は面の側にある」の証拠が、
`matched` の p 値 1本だけに戻ります（＝ 本数の差の否定だけ）。
"""
from __future__ import annotations

import json
from pathlib import Path

from src import form_tail


def _write(tmp_path: Path, rows, forms) -> tuple[Path, Path]:
    v = tmp_path / "views.jsonl"
    with v.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    f = tmp_path / "forms.json"
    f.write_text(json.dumps({"forms": forms}, ensure_ascii=False))
    return v, f


def test_同じ日に固まった上位は棚と呼ばない(tmp_path):
    """**1日で作れる団子を、配信の上限と読まないこと。**"""
    rows, forms = [], {}
    for i in range(12):
        vid = f"same{i}"
        rows.append({"id": vid, "views": 1000 - i, "at": "2026-08-16T02:00"})
        forms[vid] = "ショート"
    v, f = _write(tmp_path, rows, forms)
    s = form_tail.shelf(views_path=v, forms_path=f)
    assert s["shelf_n"] >= form_tail.SHELF_MIN_N     # 本数は足りている
    assert s["span_days"] == 0                        # 日が広がっていない
    assert s["is_shelf"] is False


def test_別々の日が同じ高さで止まっていれば棚(tmp_path):
    """**別の日の別の題が、何度でも同じ高さで止まる** ＝ 面の側の上限。"""
    rows, forms = [], {}
    for i in range(12):
        vid = f"day{i}"
        day = 6 + i                                   # 08/06 〜 08/17
        rows.append({"id": vid, "views": 1000 - i * 5,
                     "at": f"2026-08-{day:02d}T02:00"})
        forms[vid] = "ショート"
    v, f = _write(tmp_path, rows, forms)
    s = form_tail.shelf(views_path=v, forms_path=f)
    assert s["shelf_n"] >= form_tail.SHELF_MIN_N
    assert s["span_days"] >= form_tail.SHELF_MIN_SPAN_DAYS
    assert s["is_shelf"] is True


def test_1本だけ飛び出していれば棚ではない(tmp_path):
    """記録が1本だけ抜けている形（＝ 裾が伸びている）は棚ではありません。"""
    rows, forms = [], {}
    rows.append({"id": "spike", "views": 5000, "at": "2026-08-06T02:00"})
    forms["spike"] = "ショート"
    for i in range(12):
        vid = f"low{i}"
        rows.append({"id": vid, "views": 100 - i, "at": f"2026-08-{7 + i:02d}T02:00"})
        forms[vid] = "ショート"
    v, f = _write(tmp_path, rows, forms)
    s = form_tail.shelf(views_path=v, forms_path=f)
    assert s["shelf_n"] == 1
    assert s["is_shelf"] is False


def test_いまの実測は棚である():
    """**この検査が、前提「天井は面の側にある」の judge です**（API 0単位）。

    覆る条件: 棚に載る本が 5本 を切るか、初観測日の幅が 7日 を切ったら、
    この証拠は消えます（そのとき前提は `matched` の p 値だけで立ちます）。
    """
    s = form_tail.shelf()
    if not s["max"]:                                  # 控えが無い環境
        return
    assert s["shelf_n"] >= form_tail.SHELF_MIN_N, s
    assert s["span_days"] >= form_tail.SHELF_MIN_SPAN_DAYS, s
    assert s["is_shelf"] is True, s


def test_画面に棚の行が出る():
    """**測っても印字しなければ、次の回は見ません。**"""
    out = "\n".join(form_tail.lines())
    if "ショート" not in out:
        return
    assert "棚" in out, out
