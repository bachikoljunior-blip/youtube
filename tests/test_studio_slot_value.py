"""枠 1つ の値打ちを、扉の通貨で（2026-09-19 02:3x・optimizer・Opus・1周1体）。

**何を挟むか**: 枠の配り（`cli.LONG_SLOTS` / `SHORT_SLOTS`）は 09/17 19:xx から
`form_yield` の **1本あたり再生の中央**で決まっていました。その比べ方は 2か所 で
問いとずれています —— **(1) 中央で比べている**（円も扉(b) の時間も n本 の**合計**なので、
掛けてよいのは平均）・**(2) 再生で比べている**（再生はどちらの扉の通貨でもない）。

**この検査が押さえるのは 3つ**:
  1. `form_yield` が **平均も返す**こと（中央だけに戻したら落ちる）
  2. `yen_now` が **平均を掛ける**こと（中央に戻したら落ちる ＝ 実測で 15.6倍 ずれた側）
  3. `slot_value` で **ショートの扉(b) の時間が 0**であること（GOAL (4-g) 1）

**陽性対照を先に置くこと**（この repo の決め）—— 「差がありませんでした」は、
計器が死んでいても同じ字で出ます。下の `test_陽性対照_中央と平均は実際に割れる` は、
**中央が同じで平均だけが違う台帳**をその場で作り、2つ が実際に割れることを測ります。

決めと覆る条件は `studio/trend.slot_value` の註と `docs/METHOD.md` §5。
"""
import json

from studio import trend


def _rows(items):
    """`items` は (台本id, video_id, views, age_h) の並び。齢は帯（24〜96h）の中に置く。"""
    rows = []
    for i, (sid, vid, _views, _age) in enumerate(items):
        rows.append({"event": "scheduled", "id": sid, "video_id": vid,
                     "publish_at": f"2026-09-{10 + (i % 9):02d}T10:00+09:00"})
    for sid, vid, views, age in items:
        if views is None:
            continue
        rows.append({"event": "measured", "id": vid, "views": views, "age_h": age,
                     "at": "2026-09-19T02:00:00+09:00"})
    return rows


def _scripts(tmp_path, items, forms):
    for (sid, _vid, _views, _age), form in zip(items, forms):
        (tmp_path / f"{sid}.json").write_text(
            json.dumps({"id": sid, "date": "2026-09-15", "title": "t",
                        "takeaway": "t", "form": form}), encoding="utf-8")
    return tmp_path


# ---- 陽性対照（先に置くこと） ---------------------------------------------------

def test_陽性対照_中央と平均は実際に割れる(tmp_path):
    """**同じ中央・違う平均**の台帳で、2つ が割れることを測る。

    割れなければ、下の検査が「平均を使っている」と言っても意味がありません
    （中央と平均が同じ台帳では、どちらを掛けても同じ字が出る）。
    """
    items = [(f"s{i}", f"v{i}", views, 48.0)
             for i, views in enumerate([0, 0, 2, 2, 1000])]
    d = trend.form_yield(_rows(items), _scripts(tmp_path, items, ["long"] * 5))
    lg = d["long"]
    assert lg["median"] == 2.0, lg
    assert abs(lg["mean"] - 200.8) < 0.1, lg
    # **100倍 割れている** ＝ この台帳の上では、どちらを掛けたかが字に出ます。
    assert lg["mean"] / lg["median"] > 50


def test_form_yield_は平均を返す(tmp_path):
    items = [("s0", "v0", 10, 48.0), ("s1", "v1", 20, 48.0), ("s2", "v2", 300, 48.0)]
    d = trend.form_yield(_rows(items), _scripts(tmp_path, items, ["short"] * 3))
    s = d["short"]
    assert s["median"] == 20.0
    assert abs(s["mean"] - 110.0) < 1e-6
    assert s["sum"] == 330
    assert s["max"] == 300


def test_yen_now_は中央ではなく平均を掛ける(tmp_path):
    """**円/日 ＝ 本/日 × 平均 × RPM ÷ 1000。** 中央に戻したら、この検査が落ちます。

    実測（2026-09-19・同じ台帳）: long は 中央 2回 対 平均 31.1回 ＝ **15.6倍**。
    その 1語 が、形どうしの倍率を 19倍 ずらし、枠の配りを決めていました。
    """
    items = [(f"s{i}", f"v{i}", views, 48.0)
             for i, views in enumerate([0, 0, 2, 2, 1000])]
    rows = _rows(items)
    d = trend.yen_now(rows, _scripts(tmp_path, items, ["long"] * 5))
    lg = d["forms"]["long"]
    assert lg["median"] == 2.0 and abs(lg["mean"] - 200.8) < 0.1
    rpm = lg["rpm"]["中"]
    # 平均を掛けている（中央を掛けていたら 2.0 * rpm / 1000 になる）
    assert abs(lg["yen_per_video"]["中"] - 200.8 * rpm / 1000.0) < 1e-6
    assert lg["yen_per_video"]["中"] > 2.0 * rpm / 1000.0 * 50


def test_ショートの扉bの時間は0(tmp_path):
    """**ショートの視聴は 4,000時間 に 1秒も入りません**（GOAL (4-g) 1）。

    ＝ 扉(b) しか開いていないあいだ、ショートの枠の値打ちは
    **再生が何回でも 時間の欄は 0** です。ここが 0 でなくなったら、
    扉の読み方が変わったということなので、`slot_value` の註の覆る条件 (2) を読むこと。
    """
    assert trend.SHORT_GATE_MIN_PER_VIEW == 0.0
    items = [(f"s{i}", f"v{i}", 1000, 48.0) for i in range(4)]
    d = trend.slot_value(_rows(items), _scripts(tmp_path, items, ["short"] * 4))
    assert d["short"]["hours"] == 0.0, d["short"]
    assert d["short"]["mean"] == 1000.0


def test_slot_value_line_は数を出して決めを出さない(tmp_path):
    """**この口は枠をどう配るかを言いません**（判断はサブ・オーナー 2026-09-06 14:0x）。"""
    items = [(f"s{i}", f"v{i}", 100 * (i + 1), 48.0) for i in range(4)]
    s = trend.slot_value_line(_rows(items), _scripts(tmp_path, items, ["short"] * 4))
    assert "枠 1つ の値打ち" in s
    assert "扉(b) に 1秒も入りません" in s
    for word in ("にしろ", "座らせないこと", "やめること"):
        assert word not in s, s
