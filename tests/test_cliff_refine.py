"""「崖」が、粗い目盛りのせいで滑らかな坂を崖と呼んでいないか。

`_classify` の崖は「隣り合う2点の段差が中央の5倍以上」です。
x が**数え上げ**（表の行）ならそれで正しい —— 行と行のあいだには何もありません。
**連続量では違います。** 格子が粗いと、**急な所から平らな所へ移るだけの
滑らかな曲線が、必ず崖に見えます。**

実物（2026-08-27）: `nenkin.assumption_flip（余裕_倍）` が
「`base_annual_man` が 90→123 で -0.3692 跳ぶ（ふだんの段差は 0.0043）」と出た。
格子は 33万きざみ。1万きざみで引き直すと 0.706 → 0.674 → 0.653 …… と
**1本の滑らかな坂**で、崖はありません。

**故障注入を両向きに掛けます**（`tests/test_premise.py` と同じ理由）——
当たりを見つけることと、**当たっていないものを鳴らさないこと**は別の性質で、
片方だけでは「全部鳴らす検査」と区別がつきません。
"""
from src import section_sweep as ss


def _refine(fn, x0, x1, key="返り値"):
    """`_refine_cliff` を、1引数の関数に対して呼ぶ。"""
    return ss._refine_cliff(fn, {}, "x", 1.0, key,
                            {"x の手前": x0, "x の先": x1})


# ---- 故障注入（鳴るべきでない側 ＝ 本物の崖） --------------------------------

def test_本物の段差は細かくしても崖のまま():
    """1点で跳ぶ階段。**8等分しても段は1つに集まります。**"""
    def step(x):
        return {"返り値": 0.0 if x < 100.0 else 1000.0}

    d = _refine(step, 90.0, 123.0)
    assert d["細かくすると崖ではない"] is False, d
    assert d["細かく刻んだ手前"] < 100.0 <= d["細かく刻んだ先"], d


def test_本物の崖は位置が細く出る():
    """崖と分かるだけでなく、**元の区間より狭い区間**を返すこと。"""
    def step(x):
        return {"返り値": 0.0 if x < 100.0 else 1000.0}

    d = _refine(step, 90.0, 123.0)
    width = d["細かく刻んだ先"] - d["細かく刻んだ手前"]
    assert width < (123.0 - 90.0) / 2, d


# ---- 故障注入（鳴るべき側 ＝ 目盛りが粗いだけの坂） --------------------------

def test_滑らかな坂は崖ではないと言う():
    """`assumption_flip（余裕_倍）` と同じ形（急→平ら の1本の曲線）。"""
    def slope(x):
        return {"返り値": 100.0 / x}

    d = _refine(slope, 90.0, 123.0)
    assert d["細かくすると崖ではない"] is True, d
    assert "細かく刻んだ手前" not in d, d


def test_実物の_assumption_flip_は坂と出る():
    """**この検査が守っているのは、この1件です**（2026-08-27 に踏んだ）。"""
    from src.calc import nenkin
    d = ss._refine_cliff(nenkin.assumption_flip, {}, "base_annual_man", 180.0,
                         "余裕_倍", {"x の手前": 90.0, "x の先": 123.0})
    assert d["細かくすると崖ではない"] is True, d


# ---- 呼べなかったときは、黙って通さないこと --------------------------------

def test_呼べなければ未判定と言う():
    """**崖でなかったことと、確かめられなかったことは別です。**"""
    def broken(x):
        raise ValueError("駄目")

    d = _refine(broken, 1.0, 2.0)
    assert "細かく刻めなかった" in d, d
    assert "細かくすると崖ではない" not in d, d


def test_欄が消えたら未判定と言う():
    def gone(x):
        return {"べつの欄": x}

    d = _refine(gone, 1.0, 2.0)
    assert "細かく刻めなかった" in d, d


def test_区間が取れなければ未判定と言う():
    def any_fn(x):
        return {"返り値": x}

    d = ss._refine_cliff(any_fn, {}, "x", 1.0, "返り値", {})
    assert "細かく刻めなかった" in d, d


# ---- 一覧の並び順（`逆転` の `[並 N点]` と同じ扱いになっているか） ----------

def test_坂は一覧の後ろへ回る():
    hit = {"形": "崖", "詳しく": {"細かくすると崖ではない": True}}
    assert ss.unnameable(hit) is True


def test_細かくしても崖なら沈めない():
    """**位置がより細く出た側**なので、むしろ書きやすくなっています。"""
    hit = {"形": "崖", "詳しく": {"細かくすると崖ではない": False,
                               "細かく刻んだ手前": 99.0, "細かく刻んだ先": 100.0}}
    assert ss.unnameable(hit) is False


def test_未判定は沈めない():
    """確かめられなかっただけの候補を、書けない側へ回さないこと。"""
    hit = {"形": "崖", "詳しく": {"細かく刻めなかった": "ValueError"}}
    assert ss.unnameable(hit) is False


# ---- 数え上げの軸には掛からないこと ----------------------------------------

def test_数え上げの崖には刻み直しが掛からない():
    """行と行のあいだには何もないので、**細かくする余地がありません。**

    `_refine_cliff` は連続量の掃引（`sweep_params`）からしか呼ばれません。
    表の行を歩く側（`enumerated=True`）から呼ばれていないことを、
    印字に `[坂]` も `[崖◎]` も出ないことで見ます。
    """
    from src.calc import nenkin
    lines = ss.report_lines(ss.sweep_calc("nenkin"))
    rows = [ln for ln in lines
            if "崖" in ln and "（表の行）" in ln]
    assert rows, "表の行を歩く崖が1件も出ていません（検査が空回りしています）"
    for ln in rows:
        assert "[坂]" not in ln and "[崖◎]" not in ln, ln
    assert nenkin is not None
