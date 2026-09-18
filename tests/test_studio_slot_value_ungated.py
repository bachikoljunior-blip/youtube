"""枠の並びを、門の外の通貨で（2026-09-19 06:xx・optimizer・Opus 5・ultracode・1周1体）。

**何を挟むか**: `slot_value_line` は `yen`（＝ 平均再生 × RPM）で並べ替えて印字しており、
実測の台帳では **long を先に出していました**（long ¥31.1 対 short ¥20.4）。
`yen` は **RPM を掛けた数 ＝ 門（YPP）を通ったあとの円**で、その門は
`rev_deadline` の実測で **期限の 591日 後**に開きます。
＝ **期限の外で開く扉の通貨が、きょうの枠の順を決めていました。**

**同じ台帳で、門を通らない通貨（成果報酬 ＝ 再生 × 成約率 × 単価）で並べると向きが逆で、
short が 18.7倍 先です。**

**帯についての註**: 成果報酬の帯は 3つ とも未測で幅 200倍 です。
だから **絶対値は読めません**。**しかし比は読めます** —— 帯は short にも long にも
同じ数が掛かるので、**割ると消えます**。この検査の
`test_陽性対照_帯を動かしても比は動かない` が、帯を実際に動かして それを測ります
（「差がありませんでした」は計器が死んでいても同じ字で出るため）。

**この検査が押さえるのは 4つ**:
  1. `slot_value` が `perf_yen` を返すこと
  2. `slot_value_line` が **`perf_yen` で並べる**こと（`yen` に戻したら落ちる）
  3. 帯を動かしても **比が動かない**こと（陽性対照つき ＝ 絶対値は動く）
  4. `cmd_status` の 形の順 の行が、門の内側の 円/枠 だけで終わらないこと

決めと覆る条件は `studio/trend.slot_value` の註と `docs/METHOD.md` §5 2026-09-19 06:xx。
"""
import json

import pytest

from studio import trend


def _rows(items):
    rows = []
    for i, (sid, vid, _v, _a) in enumerate(items):
        rows.append({"event": "scheduled", "id": sid, "video_id": vid,
                     "publish_at": f"2026-09-{10 + (i % 9):02d}T10:00+09:00"})
    for sid, vid, views, age in items:
        if views is None:
            continue
        rows.append({"event": "measured", "id": vid, "views": views, "age_h": age,
                     "at": "2026-09-19T02:00:00+09:00"})
    return rows


def _scripts(tmp_path, items, forms):
    for (sid, _vid, _v, _a), form in zip(items, forms):
        (tmp_path / f"{sid}.json").write_text(
            json.dumps({"id": sid, "date": "2026-09-15", "title": "t",
                        "takeaway": "t", "form": form}), encoding="utf-8")
    return tmp_path


def _mixed(tmp_path):
    """実測に近い形: short 平均 583回 × 4本・long 平均 31回 × 4本。"""
    items = ([(f"s{i}", f"vs{i}", 583, 48.0) for i in range(4)]
             + [(f"l{i}", f"vl{i}", 31, 48.0) for i in range(4)])
    return _rows(items), _scripts(tmp_path, items, ["short"] * 4 + ["long"] * 4)


def test_slot_value_が門の外の円を返す(tmp_path):
    rows, sc = _mixed(tmp_path)
    d = trend.slot_value(rows, sc)
    for form in ("short", "long"):
        assert d[form]["perf_yen"] is not None, form
    # 平均 × 成約率の中段 × 単価の中段（写しを持たない ＝ 同じ定数から引く）
    want = 583.0 * trend.perf_rate_band()[1] * trend.PERF_YEN_PER_ACTION_BAND[1]
    assert d["short"]["perf_yen"] == pytest.approx(want)


def test_門の内と外で向きが逆になる実測の形(tmp_path):
    """**この台帳では 2つ の通貨が逆を向きます** —— それが挟みたかった当のものです。"""
    rows, sc = _mixed(tmp_path)
    d = trend.slot_value(rows, sc)
    assert d["long"]["yen"] > d["short"]["yen"], "門の内: long が先（RPM が 29倍）"
    assert d["short"]["perf_yen"] > d["long"]["perf_yen"], "門の外: short が先（再生が 18.7倍）"


def test_印字は門の外の円で並ぶ(tmp_path):
    """`yen` で並べ替えに戻したら落ちます（long が先に出るため）。"""
    rows, sc = _mixed(tmp_path)
    s = trend.slot_value_line(rows, sc)
    assert s.index("short") < s.index("long"), s
    assert "門の外" in s and "門の内" in s
    assert "向きが逆" in s
    # **決めは書かないこと**（判断はサブ・オーナー 2026-09-06 14:0x）
    for word in ("にしろ", "座らせないこと", "やめること", "禁止"):
        assert word not in s, s


def test_陽性対照_帯を動かしても比は動かない(tmp_path, monkeypatch):
    """**帯は比では約分されます。** 絶対値のほうは動くことも同じ検査で測ります

    —— 動かないなら、それは「帯が効いていない」＝ 計器が死んでいる側なので、
    下の 2つ目 の assert がそれを落とします。
    """
    rows, sc = _mixed(tmp_path)
    base = trend.slot_value(rows, sc)
    ratio0 = base["short"]["perf_yen"] / base["long"]["perf_yen"]
    abs0 = base["short"]["perf_yen"]

    # 帯を低の段へ（`PERF_CLICK_BAND` は (0.0005, 0.003, 0.010)）
    monkeypatch.setattr(trend, "PERF_CLICK_BAND", (0.0005, 0.0005, 0.0005))
    low = trend.slot_value(rows, sc)
    ratio1 = low["short"]["perf_yen"] / low["long"]["perf_yen"]

    assert ratio1 == pytest.approx(ratio0), "比は帯で動いてはいけません（約分される）"
    assert low["short"]["perf_yen"] != pytest.approx(abs0), \
        "陽性対照: 絶対値は帯で動くはず（動かないなら帯が効いていない）"


def test_陽性対照_再生が同じなら門の外の円も同じ(tmp_path):
    """**2つ の通貨が本当に割れる台帳**をその場で作って、割れる元を測ります。

    再生を揃えると門の外の円は同じになります ＝ この検査は
    「いつでも逆を向く」を主張していません（向きは台帳が決めます）。
    """
    items = ([(f"s{i}", f"vs{i}", 100, 48.0) for i in range(4)]
             + [(f"l{i}", f"vl{i}", 100, 48.0) for i in range(4)])
    rows = _rows(items)
    sc = _scripts(tmp_path, items, ["short"] * 4 + ["long"] * 4)
    d = trend.slot_value(rows, sc)
    assert d["short"]["perf_yen"] == pytest.approx(d["long"]["perf_yen"]), \
        "再生が同じなら門の外の円も同じ（帯は形で変えていない）"
    assert d["long"]["yen"] > d["short"]["yen"], "門の内は RPM だけで割れる"


def test_形の順の行が門の内側で終わらない():
    """`cmd_status` の 形の順 の行は、円/枠 を出したら

    **門の外の 円/枠 も同じ行に出すこと** —— 片方だけだと、次の周は
    門の内側（期限の外で開く扉）の通貨で きょうの枠を配ります。
    """
    import inspect

    from studio import cli
    src = inspect.getsource(cli)
    assert "perf_yen" in src, "cmd_status が門の外の通貨を 1度 も読んでいません"
    i = src.index("向きが再生と逆")
    assert "門の外" in src[i:i + 1200], "円/枠 を出す所の近くに門の外の円が在りません"
