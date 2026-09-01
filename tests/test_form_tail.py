"""`src/form_tail.py` —— **形ごとの「上の裾」の形**（API 0単位）。

**既知の当たりを1件、先に固定します**（`docs/trigger_main.md`
「`src/` に道具を新しく足す回は、『既知の当たり』を1件、検査に先に固定すること」）。

    2026-09-02 01:2x の実物（`data/views.jsonl` 22,667点・`data/video_forms.json`）
        ショート  n=171  max=1,891回  max/10位 **1.33**
        長尺      n= 24  max=  156回  max/10位 **39.00**
        ショートを n=24 へ 2,000回 間引いた中央値 **4.2 前後**
        長尺の実測 39.00 は、その 2,000回 のどれよりも大きい（**p < 0.0005**）

**この数が動いたら、`config/hypotheses.yaml` の
「1,891 は面の上限であって中身の天井ではない」が判定できます。**
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import form_tail

ROOT = Path(__file__).resolve().parent.parent


def _write(tmp_path, points, forms):
    v = tmp_path / "views.jsonl"
    v.write_text("".join(json.dumps({"id": i, "views": n}) + "\n" for i, n in points))
    f = tmp_path / "forms.json"
    f.write_text(json.dumps({"forms": forms}))
    return v, f


def test_上位が団子なら比は小さく_散らばれば大きい():
    assert form_tail.top_ratio([100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90], k=10) \
        == pytest.approx(100 / 91, rel=1e-6)
    assert form_tail.top_ratio([1000, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1], k=10) \
        == pytest.approx(1000.0, rel=1e-6)


def test_k位が無い群は_None_で_推測しない():
    assert form_tail.top_ratio([5, 4, 3], k=10) is None
    assert form_tail.hill([5, 4, 3], k=10) is None


def test_裾が重いほど_Hill_は小さい():
    flat = [100 - i for i in range(30)]                 # ほぼ一様 ＝ 軽い裾
    heavy = [10 ** 4] + [10 ** (3 - i * 0.1) for i in range(29)]
    assert form_tail.hill(flat, k=10) > form_tail.hill(heavy, k=10)


def test_本数を揃えて比べる_p_は間引きの分母で出る(tmp_path):
    """**片方が少ないだけで散らばって見えるのを、間引きで潰します。**"""
    pts = [(f"s{i}", 1000 - i) for i in range(60)]      # ショート: 上が団子
    pts += [(f"l{i}", 1000 // (i + 1)) for i in range(15)]   # 長尺: 上が散らばる
    forms = {f"s{i}": "ショート" for i in range(60)}
    forms.update({f"l{i}": "長尺" for i in range(15)})
    v, f = _write(tmp_path, pts, forms)
    s = form_tail.shape(views_path=v, forms_path=f, draws=200)
    assert s["ショート"]["n"] == 60 and s["長尺"]["n"] == 15
    m = s["matched"]
    assert m["big"] == "ショート" and m["small"] == "長尺" and m["n"] == 15
    assert m["draws"] == 200
    assert m["observed"] > m["median"], m


def test_帳面が読めない回は空を返す_落ちない(tmp_path):
    s = form_tail.shape(views_path=tmp_path / "no.jsonl",
                        forms_path=tmp_path / "no.json", draws=5)
    assert s.get("matched") is None


@pytest.mark.skipif(not (ROOT / "data" / "views.jsonl").is_file(),
                    reason="実物の帳面が無い")
def test_実物_ショートの上だけが詰まっている_2026_09_02の実測():
    """**既知の当たり。** ここが崩れたら前提が判定できるようになっています。

    **数を狭く固定しません** —— `data/views.jsonl` は毎周 伸びるので、
    固定すると次の回に「実物が動いた」ではなく「検査が古い」で赤くなります。
    固定するのは**向き**です。
    """
    s = form_tail.shape(draws=200)
    if not s.get("長尺") or not s.get("ショート") or not s.get("matched"):
        pytest.skip("形の札が片方しか無い窓")
    assert s["ショート"]["top_ratio"] < s["長尺"]["top_ratio"], s
    m = s["matched"]
    # 本数を揃えても、少ないほうが散らばっている（＝ n では説明できない）
    assert m["observed"] > m["median"], m
