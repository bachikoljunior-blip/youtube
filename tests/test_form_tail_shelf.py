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


# ---------------------------------------------------------------------------
# **外挿が上端まで届いているか**（`tail_elasticity`）
#
# `rule_per_video.ceiling_at_rule()` は「観測された最大」に `n ** (-b)` を掛けて
# 1本/日 へ外挿します。その `b` は **平均**に当てた回帰の傾きです。
# **平均の傾きを極値に当ててよいか**を、ここで数えます。
# ---------------------------------------------------------------------------

def _rows(spec):
    """`{日: [再生, ...]}` → `_settled()` と同じ形 `(日, 本ID, 再生)`。"""
    out = []
    for day, vals in spec.items():
        for i, v in enumerate(vals):
            out.append((day, f"{day}-{i}", v))
    return out


def test_上端も平均と同じだけ動くなら外挿は届いている():
    """**全部が同じ倍率で動く**（＝ 分布ごと平行移動）なら、外挿は上端にも効きます。"""
    # **日の中の形を n から独立にします** —— 倍率を 1.0 / 0.5 で交互に置くと、
    # 偶数本の日はどれも「最大 ×1.0・平均 ×0.75」。**動くのは `n ** -0.7` だけ**なので、
    # 上端と平均は同じ傾きで下がります（＝ 分布ごとの平行移動）。
    spec = {}
    for i, n in enumerate([2, 2, 4, 4, 6, 6, 8, 8, 12, 12, 20, 20]):
        scale = 10000 * (n ** -0.7)
        spec[f"2026-08-{i + 1:02d}"] = [int(scale * (1.0 if j % 2 == 0 else 0.5))
                                        for j in range(n)]
    te = form_tail.tail_elasticity(_rows(spec))
    assert te is not None
    assert te["reaches_tail"] is True, te


def test_上端が棚なら外挿は届いていない():
    """**上端だけが動かない**（棚）なら、平均の傾きを極値に当ててはいけません。"""
    spec = {}
    for i, n in enumerate([1, 1, 2, 2, 3, 3, 8, 8, 12, 12, 20, 20]):
        # 最大は 1,000 に張り付き、下だけが本数で薄まる
        vals = [1000] + [int(900 * (n ** -0.9) * (1 - 0.02 * j))
                         for j in range(n - 1)]
        spec[f"2026-08-{i + 1:02d}"] = vals
    te = form_tail.tail_elasticity(_rows(spec))
    assert te is not None
    assert te["reaches_tail"] is False, te
    assert te["inflation"] > 1.0, te


def test_いまの実測では外挿が上端まで届いていない():
    """**この検査が、前提「天井 4,101回 は外挿ぶんだけ上振れ」の judge です**。

    覆る条件: 上端の 95% 区間が平均の `b` を**含むようになったら**、
    この前提は falsified —— そのとき `ceiling_at_rule()` の外挿はそのままでよい。
    """
    te = form_tail.tail_elasticity()
    if te is None:                                # 控えが無い環境
        return
    assert te["max"]["lo"] <= te["max"]["b"] <= te["max"]["hi"]
    assert te["reaches_tail"] is False, te
    # 上端の傾きは 0 と区別が付かない（＝ 密度を下げても棚は上がらない）
    assert abs(te["max"]["t"]) < 2.0, te
    # 平均の傾きは 0 と区別が付く（＝ 平均のほうは本当に動く）
    assert abs(te["mean"]["t"]) > 2.0, te


def test_画面に外挿の行が出る():
    out = "\n".join(form_tail.lines())
    if "ショート" not in out:
        return
    assert "弾力性" in out, out
