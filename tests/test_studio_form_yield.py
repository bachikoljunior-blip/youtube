"""形ごとの 1本あたり再生（2026-09-17 19:xx・optimizer・Fable 5.1・ultracode）。

**何を挟むか**: `trend.long_per_video` は **長尺だけ**を分母にするので、
「その形に配りの口が在るか」を訊けません。`form_yield` は**同じ齢の門**で
形ごとに中央を出し、`form_yield_line` が毎周 1行 出します。

**陽性対照を先に置くこと**（この repo の決め）——「差がありませんでした」は、
計器が死んでいても同じ字で出ます。下の `test_陽性対照` は、
**片方の形だけに再生を入れた台帳**をその場で作り、**倍率が実際に出る**ことを測ります。

決めと覆る条件は `studio/trend.form_yield` の註と `docs/METHOD.md` §5「形の配り」。
"""
import json

from studio import trend


def _rows(items):
    """`items` は (台本id, video_id, form, views, age_h) の並び。

    `form` が None の台本は **`form` の鍵を書きません**（＝ 古い台本。既定 `short` に倒れる）。
    """
    rows = []
    for sid, vid, _form, _views, _age in items:
        rows.append({"event": "scheduled", "id": sid, "video_id": vid,
                     "publish_at": f"2026-09-1{len(rows) % 9}T10:00+09:00"})
    for sid, vid, _form, views, age in items:
        if views is None:
            continue
        rows.append({"event": "measured", "id": vid, "views": views, "age_h": age,
                     "at": "2026-09-17T19:00:00+09:00"})
    return rows


def _scripts(tmp_path, items):
    for sid, _vid, form, _views, _age in items:
        body = {"id": sid, "date": "2026-09-15", "title": "t", "takeaway": "t"}
        if form is not None:
            body["form"] = form
        (tmp_path / f"{sid}.json").write_text(json.dumps(body), encoding="utf-8")
    return tmp_path


# ---- 陽性対照（先に置くこと） ---------------------------------------------------

def test_陽性対照_片方の形だけに再生を入れると倍率が出る(tmp_path):
    items = [(f"s{i}", f"vs{i}", "short", 1000, 48.0) for i in range(4)]
    items += [(f"l{i}", f"vl{i}", "long", 1, 48.0) for i in range(4)]
    d = trend.form_yield(_rows(items), _scripts(tmp_path, items))
    assert d["short"]["median"] == 1000.0
    assert d["long"]["median"] == 1.0
    line = trend.form_yield_line(_rows(items), tmp_path)
    assert "1,000倍" in line, line


def test_陰性対照_同じ再生なら倍率は1倍(tmp_path):
    """計器が「常に大きい倍率」を出していないこと（陽性対照の裏）。"""
    items = [(f"s{i}", f"vs{i}", "short", 500, 48.0) for i in range(4)]
    items += [(f"l{i}", f"vl{i}", "long", 500, 48.0) for i in range(4)]
    line = trend.form_yield_line(_rows(items), _scripts(tmp_path, items))
    assert "1倍" in line and "500回/本" in line, line


# ---- 齢の門（`long_per_video` と同じ数を使うこと） --------------------------------

def test_齢が足りない本は分母に入らない(tmp_path):
    items = [("s0", "vs0", "short", 1000, 48.0),
             ("s1", "vs1", "short", 0, 1.0)]          # 出したその周の本
    d = trend.form_yield(_rows(items), _scripts(tmp_path, items))
    assert d["short"]["n"] == 2 and d["short"]["n_measured"] == 1
    assert d["short"]["median"] == 1000.0


def test_齢の門は長尺の側と同じ1か所から来る():
    """写しを持たないこと —— 門が 2か所 に増えたら、この検査が落ちます。"""
    src = (trend.__file__.replace(".pyc", ".py"))
    body = open(src, encoding="utf-8").read()
    assert body.count("LPV_MIN_AGE_H = ") == 1


# ---- 既定（`form` の無い古い台本は short） ---------------------------------------

def test_formの無い台本はshortに倒れる(tmp_path):
    items = [("old", "vold", None, 800, 48.0)]
    d = trend.form_yield(_rows(items), _scripts(tmp_path, items))
    assert set(d) == {"short"}
    assert d["short"]["median"] == 800.0


# ---- n が足りないときは倍率を読ませない（覆る条件 (2)） ----------------------------

def test_片側がFORM_MIN_N未満なら倍率を印字しない(tmp_path):
    items = [(f"s{i}", f"vs{i}", "short", 1000, 48.0) for i in range(4)]
    items += [("l0", "vl0", "long", 1, 48.0),
              ("l1", "vl1", "long", 1, 48.0)]          # n=2 < FORM_MIN_N
    line = trend.form_yield_line(_rows(items), _scripts(tmp_path, items))
    assert "倍率は読まないこと" in line, line
    assert "倍**" not in line, line


def test_台本が1本も無い台帳でも落ちない(tmp_path):
    line = trend.form_yield_line([], tmp_path)
    assert "1本 もありません" in line, line


# ---- 差し替え（同じ台本 id の後の `scheduled` が勝つ） ------------------------------

def test_差し替えた本は後の行が勝つ(tmp_path):
    items = [("s0", "old", "short", 5, 48.0)]
    rows = _rows(items)
    rows.append({"event": "scheduled", "id": "s0", "video_id": "new",
                 "publish_at": "2026-09-16T10:00+09:00"})
    rows.append({"event": "measured", "id": "new", "views": 900, "age_h": 48.0,
                 "at": "2026-09-17T19:00:00+09:00"})
    d = trend.form_yield(rows, _scripts(tmp_path, items))
    assert d["short"]["median"] == 900.0, d


# ---- 齢の**帯**（2026-09-19 01:5x・optimizer・Opus・1周1体） ----------------------
#
# **踏んだ defect**: 門が下端だけだと、1本 につき採るのは「齢 24h 以上の**最後の行**」で、
# **形ごとに測った刻が違っても同じ表に並びます**。この回に同じ台帳を `measure` の前後で
# 引いて、同じ 8本 が 719倍 → 約 350倍 に動きました（本も再生も変わっていない）。
# 決めと覆る条件は `studio/trend.form_yield` の註。


def test_陽性対照_帯の上端より古い測りは分母に入らない(tmp_path):
    """陽性対照を先に置くこと —— 帯が効いていなければ、この本が中央を動かします。"""
    items = [("s0", "vs0", "short", 1000, 48.0),
             ("s1", "vs1", "short", 999999, trend.FORM_AGE_MAX_H + 1.0)]
    d = trend.form_yield(_rows(items), _scripts(tmp_path, items))
    assert d["short"]["n"] == 2 and d["short"]["n_measured"] == 1
    assert d["short"]["median"] == 1000.0


def test_帯の中の測りは_あとから来た帯の外の測りに負けない(tmp_path):
    """**この検査が、直した defect そのものです。**

    同じ本を 2度 測り、2度目が帯の外（古すぎる齢）でも、帯の中の値が残ること。
    もとの実装は「最後の行」を採るので、2度目に倒れていました。
    """
    items = [("s0", "vs0", "short", 700, 48.0)]
    rows = _rows(items)
    rows.append({"event": "measured", "id": "vs0", "views": 5,
                 "age_h": trend.FORM_AGE_MAX_H + 50.0, "at": "2026-09-18T19:00:00+09:00"})
    d = trend.form_yield(rows, _scripts(tmp_path, items))
    assert d["short"]["median"] == 700.0, d


def test_形ごとに測った齢がずれていたら倍率を印字しない(tmp_path):
    """長尺だけ帯の中・ショートは全部 帯の外 ＝ **「差が無い」ではなく「そろっていない」**。"""
    items = [(f"s{i}", f"vs{i}", "short", 1000, trend.FORM_AGE_MAX_H + 10.0) for i in range(4)]
    items += [(f"l{i}", f"vl{i}", "long", 1, 48.0) for i in range(4)]
    line = trend.form_yield_line(_rows(items), _scripts(tmp_path, items))
    assert "倍率は読まないこと" in line, line
    assert "そろえた比べがまだ 1つ も無い" in line, line


def test_測った齢の中央を毎周_印字する(tmp_path):
    """読む側が「いつ測った数か」を見ずに倍率を引き写さないため（`form_yield` の註）。"""
    items = [(f"s{i}", f"vs{i}", "short", 1000, 48.0) for i in range(4)]
    items += [(f"l{i}", f"vl{i}", "long", 1, 48.0) for i in range(4)]
    d = trend.form_yield(_rows(items), _scripts(tmp_path, items))
    assert d["short"]["age_median"] == 48.0 and d["long"]["age_median"] == 48.0
    line = trend.form_yield_line(_rows(items), _scripts(tmp_path, items))
    assert "測った齢の中央 48h" in line, line


def test_帯の上端も1か所から来る():
    """写しを持たないこと（下端の検査と同じ形）。"""
    body = open(trend.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert body.count("FORM_AGE_MAX_H = ") == 1


def test_帯の中で齢がそろっていなければ倍率に上端の札を付ける(tmp_path):
    """帯 24〜96h は広く、片方だけ帯の上で測れば倍率は膨らみます（`FORM_AGE_SKEW_X`）。"""
    items = [(f"s{i}", f"vs{i}", "short", 1000, 90.0) for i in range(4)]
    items += [(f"l{i}", f"vl{i}", "long", 1, 30.0) for i in range(4)]
    line = trend.form_yield_line(_rows(items), _scripts(tmp_path, items))
    assert "1,000倍" in line, line
    assert "この倍率は上端" in line, line


def test_齢がそろっていれば上端の札は付かない(tmp_path):
    """陰性対照 —— 札が常時 出ているわけではないこと。"""
    items = [(f"s{i}", f"vs{i}", "short", 1000, 48.0) for i in range(4)]
    items += [(f"l{i}", f"vl{i}", "long", 1, 48.0) for i in range(4)]
    line = trend.form_yield_line(_rows(items), _scripts(tmp_path, items))
    assert "1,000倍" in line, line
    assert "この倍率は上端" not in line, line
