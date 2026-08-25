"""`src/reach_split.py` の検査（**API を1単位も叩かない**）。

ここで固定しているのは、2026-08-20 21:4x に**実物で踏んだ2つの欠陥**です。

1. **CTR の列は割合**（百分率ではない）。`/100` していたあいだ、
   クリックは100分の1に見えていました
2. **報告は全部読む**（`reach.py` が新しい3本しか落としていなかった）。
   こちらは `tests/test_reach_ingest.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import reach_split as R  # noqa: E402


def row(date: str, vid: str, imp, ctr) -> dict:
    return {"date": date, "video_id": vid,
            "video_thumbnail_impressions": imp,
            "video_thumbnail_impressions_ctr": ctr}


def test_CTRの列は割合であって百分率ではない():
    # 実物: impressions 148 / ctr 0.0067567... ＝ 1/148 ＝ クリック1
    r = row("20260810", "YHiigJ3Zpj4", "148", "0.0067567567567567571")
    assert abs(R._clicks(r) - 1.0) < 1e-6


def test_CTR1は全部押されたという意味():
    assert R._clicks(row("20260810", "x", "1", "1")) == 1.0


def test_壊れた値でも落ちない():
    assert R._clicks(row("20260810", "x", "", "")) == 0.0
    assert R._imp(row("20260810", "x", "abc", "0")) == 0.0


def test_同じ日と動画は最後の行だけ残る():
    rows = [row("20260810", "a", "10", "0"), row("20260810", "a", "12", "0"),
            row("20260811", "a", "5", "0")]
    out = R.dedupe(rows)
    assert len(out) == 2
    assert sum(R._imp(r) for r in out) == 17


def test_長尺とショートで割る():
    rows = [row("20260810", "L1", "100", "0.01"), row("20260810", "S1", "50", "0.02")]
    sm = R.summary(rows, {"L1"})
    assert sm["長尺"]["impressions"] == 100
    assert abs(sm["長尺"]["clicks"] - 1.0) < 1e-9
    assert abs(sm["長尺"]["ctr"] - 1.0) < 1e-9      # 1/100 ＝ 1%
    assert sm["ショート"]["impressions"] == 50
    assert sm["days"] == 1


def test_控えに無い動画はショート側へ入れる():
    """**長尺の側を大きく見せないこと。** 分からないものは分母の大きいほうへ。"""
    sm = R.summary([row("20260810", "unknown", "10", "0")], {"L1"})
    assert sm["ショート"]["impressions"] == 10
    assert sm["長尺"]["impressions"] == 0


def test_直近N日は日付の実物で切る():
    rows = [row(f"2026081{i}", "a", "10", "0") for i in range(1, 6)]
    assert len({str(r["date"]) for r in R.tail(rows, 2)}) == 2
    assert sorted({str(r["date"]) for r in R.tail(rows, 2)}) == ["20260814", "20260815"]


def test_足りない倍率はCTR100パーセントの上限で出す():
    """**サムネを極限まで直した先**と比べる。そこでも足りなければ、面の話。"""
    sm = R.summary([row("20260810", "L1", "10", "0")], {"L1"})
    g = R.gap(sm, need_views_month=3000)
    assert g["ceiling_views_month"] == 300      # 1日10回 × 30日
    assert g["short_by"] == 10


def test_面が1回も無ければ無限大にする():
    sm = R.summary([row("20260810", "S1", "10", "0")], {"L1"})
    assert R.gap(sm, need_views_month=1)["short_by"] == float("inf")


def test_段4の要求は写しでなく計算で出す():
    # 月20万 ÷ RPM ¥400 × 1000
    assert R.plan_views_month(200_000, 400) == 500_000
    assert R.plan_views_month(200_000, 2_000) == 100_000


def test_1行も無いときは何をすればいいかを出す():
    out = R.render([], {"L1"})
    assert "まだ1行もありません" in out
    assert "reach.py" in out


def test_出す節はインプレッションとCTRの両方を名指しする():
    rows = [row("20260810", "L1", "100", "0.01"), row("20260810", "S1", "50", "0.02")]
    out = R.render(rows, {"L1"})
    assert "長尺" in out and "ショート" in out
    assert "直近" in out


# ---------------------------------------------------------------------------
# **長尺の集合は `pairs.yaml` だけでは足りない**（2026-08-24 に踏んだ）
#
# `pairs.yaml` は「ショート → 同じ題材の長尺」の対応表で、
# **対になっていない長尺は初めから入りません**。ところがその集合が
# `rpm_mix.surface_ceiling()` の「面（インプレッション）」の分母で、
# `eta.py` の段2 の合格点（「CTR 100% でも 38回/日」）を決めていました。
#
# 実測: `pairs.yaml` 6本 対 YouTube が長尺と数えた 12本 ／ 面 37.6 → 42.8回/日。
# ---------------------------------------------------------------------------
import json  # noqa: E402


def _pairs(tmp_path, ids):
    p = tmp_path / "pairs.yaml"
    body = "pairs:\n" + "".join(f"  t{i}: {v}\n" for i, v in enumerate(ids))
    p.write_text(body, encoding="utf-8")
    return p


def _forms(tmp_path, mapping):
    p = tmp_path / "video_forms.json"
    p.write_text(json.dumps({"at": "2026-08-24", "forms": mapping},
                            ensure_ascii=False), encoding="utf-8")
    return p


def test_測った控えと対応表を足す(tmp_path):
    pairs = _pairs(tmp_path, ["A", "B"])
    forms = _forms(tmp_path, {"B": "長尺", "C": "長尺", "S": "ショート"})
    assert R.long_ids(pairs, forms) == {"A", "B", "C"}


def test_控えが無ければ対応表だけ_いままでと同じ答え(tmp_path):
    pairs = _pairs(tmp_path, ["A", "B"])
    assert R.long_ids(pairs, tmp_path / "no-such.json") == {"A", "B"}


def test_対応表に無い長尺を落とさない(tmp_path):
    """**これが 2026-08-24 の欠陥そのもの。** 6本しか数えていなかった。"""
    pairs = _pairs(tmp_path, ["A"])
    forms = _forms(tmp_path, {f"L{i}": "長尺" for i in range(12)})
    got = R.long_ids(pairs, forms)
    assert len(got) == 13 and "A" in got


def test_再生0の長尺は控えに出ないので対応表の側で残る(tmp_path):
    """Analytics は再生0の本を返しません（実測 `SSI1MVb12Ng`）。

    **だから控えを正本にしてはいけない** —— 足すことで、どちらの穴も塞がる。
    """
    pairs = _pairs(tmp_path, ["SSI1MVb12Ng"])
    forms = _forms(tmp_path, {"other": "長尺"})
    assert "SSI1MVb12Ng" in R.long_ids(pairs, forms)


def test_ショートは長尺に混ぜない(tmp_path):
    forms = _forms(tmp_path, {"S1": "ショート", "S2": "ショート"})
    assert R.measured_long_ids(forms) == set()


def test_控えが壊れていても落ちない(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{壊れた", encoding="utf-8")
    assert R.measured_long_ids(p) == set()


def test_面は長尺を足すと増える(tmp_path):
    """**向きの検査。** 長尺を1本足したら、面が増えなければ意味がない。"""
    rows = [row("20260810", "A", "100", "0.01"),
            row("20260810", "C", "50", "0.02"),
            row("20260810", "S", "10", "0.1")]
    few = R.summary(rows, {"A"})
    many = R.summary(rows, {"A", "C"})
    assert many["長尺"]["impressions"] > few["長尺"]["impressions"]


# ---------------------------------------------------------------------------
# **「いま続いている量」が、窓の中の1日で作られていないか**（2026-08-26 に足した）
#
# 実物（`data/reach.jsonl`・長尺・08/15〜08/21）: 4 / 8 / 5 / 7 / 8 / 17 / **1,285**
# 平均 190.6・中央値 8。そして 08/21 の 1,285回 のうち **1,276回（99.3%）**が
# その日に公開した5本に付いており、それ以前の長尺6本は **1〜3回ずつ**でした。
# つまり長尺の面は「立っている面」ではなく、**公開日の立ち上がり**です。
# `scripts/eta.py` の段2 はその 190.6 を読んで
# 「合格点 191回/日 と**ちょうど同じ（×1.00）＝ 余裕がありません**」と印字していました。
# 続いている量は 8回/日 なので、実際は **23.8倍 足りません。**
# ---------------------------------------------------------------------------
def _series(vals: list[float], vid: str = "L") -> list[dict]:
    return [row(f"202608{10 + i:02d}", vid, str(v), "0") for i, v in enumerate(vals)]


def test_1日が窓の半分以上を占めたら平均ではなく中央値へ落ちる():
    long = R.summary(_series([4, 8, 5, 7, 8, 17, 1285]), {"L"})["長尺"]
    assert abs(long["per_day_recent"] - 190.571428) < 1e-3   # 平均は残す
    assert long["per_day_recent_median"] == 8.0
    assert long["per_day_sustained"] == 8.0                  # 判断に使うのはこちら
    assert "中央値" in long["per_day_sustained_basis"]


def test_平らな窓では平均のまま():
    long = R.summary(_series([10, 12, 11, 9, 10, 13, 11]), {"L"})["長尺"]
    assert long["per_day_sustained"] == long["per_day_recent"]
    assert "平均" in long["per_day_sustained_basis"]


def test_平均は消さない_保存済みの点と比べられなくなるため():
    long = R.summary(_series([4, 8, 5, 7, 8, 17, 1285]), {"L"})["長尺"]
    assert long["per_day_recent"] > long["per_day_sustained"]
    assert long["per_day_recent_top_share"] > 0.9
