"""**記録は形ごとに数えること**（`src/form_record.py`・2026-08-31 の最適化の回）。

## この検査が持っている主題

`config/hypotheses.yaml` の `per_video` の天井 `ceiling.value: 1891` は
**形で絞らずに数えた最大**です（`tests/test_per_video_ceiling.py` の
`measured_max_24h()` に form の条件が1つもありません）。実物は
**ショートの本**（`NHKylqsNfTw`）で、`src/arm_speed.arm()` はそれを
**ショートの平均**で割って `per_video` の天井 ×3.34 を作ります。

ところが `scripts/eta.py` の段3・段4 は、その1本あたり再生を
**長尺の RPM（¥400・¥2,000）**と掛けます。**その組み合わせを作れる形は
1つもありません** —— ショートは ¥400 を稼がず、長尺は 566回 回っていません。

だから `src/form_record.py` は**形をまたがない最大**だけを出します。
ここが見るのは、その約束が守られているかの1点です。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src import form_record, rule_per_video

ROOT = Path(__file__).resolve().parent.parent


def _recorded_ceiling() -> int | None:
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    for h in doc.get("hypotheses") or []:
        c = h.get("ceiling") if isinstance(h, dict) else None
        if isinstance(c, dict) and c.get("lever") == "per_video" and c.get("value") is not None:
            return int(c["value"])
    return None


def test_ショートの記録が_hypotheses_の天井と一致する():
    """**2つの数え方が同じ数に着くこと。**

    片方は `config/hypotheses.yaml` に手で書かれた `1891`、もう片方は
    `data/views.jsonl` を形ごとに数え直した最大です。**ずれたら、どちらかが古い。**

    **落ちたときの直し方**: 記録が更新されたのなら `hypotheses.yaml` の
    `value` を実測へ書き換えること（`tests/test_per_video_ceiling.py` と同じ）。
    **この検査を緩めないこと** —— 緩めた瞬間、`per_video` の天井の
    出どころが誰にも辿れなくなります。

    ## **2026-09-01 に、比べる相手を1段 変えました**（緩めてはいません）

    2026-09-01 に `hypotheses.yaml` の `value` は **1891 → 3918** になりました。
    記録が更新されたからではありません —— **記録 1,891回（`NHKylqsNfTw`）は
    「3本/日 の日」の本**で、規則（1日1本・`src/house_rule.py`）の密度へ
    弾力性 -0.663 で直すと **3,918回**だからです（`src.rule_per_video.ceiling_at_rule`）。
    分子（`per_video` 942回）は既に規則の密度で測ってあるのに、
    分母（天井）だけ全密度の最大でした。

    **この検査はそれ以来ずっと赤でした**（`1891 == 3918` で落ちる）。
    **赤のまま置くと、この検査は何も見張りません** —— 記録が本当に
    更新された日も、同じ字で落ちるだけだからです。

    そこで比べる相手を「**記録そのもの**」から「**記録から同じ道で導いた数**」へ
    移しました。**見張る中身は1つも減っていません**:

        ・`ceiling_at_rule()` の `raw` が、いまも**ショートの記録**であること
        ・`hypotheses.yaml` の `value` が、その記録から導いた数と一致すること

    記録が動けば導いた数も動くので、**yaml が古びれば、いままでどおり落ちます。**

    **覆る条件**: `ceiling_at_rule()` が測れなくなったら（`data/views.jsonl` に
    密度が読める日が無い）、いままでどおり**記録そのもの**と比べます。
    """
    recs = form_record.per_video_best()
    if not recs.get("ショート"):
        pytest.skip("data/views.jsonl か data/video_forms.json がまだ無い")
    recorded = _recorded_ceiling()
    assert recorded is not None, "hypotheses.yaml に per_video の ceiling がありません"
    best = recs["ショート"]["best"]
    at_rule = rule_per_video.ceiling_at_rule()
    if not (at_rule and at_rule.get("value")):
        # 規則の密度へ直せない回は、いままでどおり記録そのものと比べます。
        assert best == recorded, (
            f"ショートの記録 {best} と hypotheses.yaml の天井 {recorded} が"
            "ずれています。どちらかが古い —— 記録が更新されたなら yaml を書き換えること"
        )
        return
    assert at_rule["raw"] == best, (
        f"規則の密度へ直す元の記録 {at_rule['raw']} が、"
        f"形ごとに数えたショートの記録 {best} と別の本です。"
        "**天井の出どころが2つに割れています**"
    )
    assert recorded == round(float(at_rule["value"])), (
        f"hypotheses.yaml の天井 {recorded} と、記録 {best} から規則の密度へ"
        f"直した数 {float(at_rule['value']):,.0f} がずれています。"
        "どちらかが古い —— 記録が更新されたなら yaml を書き換えること"
        "（`python -c \"from src import rule_per_video as r; print(r.ceiling_at_rule())\"`）"
    )


def test_長尺の記録が_ショートの記録と別に立っていること():
    """**長尺の最高が、ショートの最高で代用されていないこと。**

    2026-08-31 の実測は ショート 1,891回 ／ 長尺 156回 で、**12倍 ちがいます。**
    ここが同じ数になったら、形の絞りが効いていません。
    """
    recs = form_record.per_video_best()
    if not (recs.get("ショート") and recs.get("長尺")):
        pytest.skip("形の実測がまだ両方そろっていない")
    assert recs["長尺"]["best"] != recs["ショート"]["best"]
    assert recs["長尺"]["id"] != recs["ショート"]["id"]


def test_形の分からない本は_どの形にも入らない():
    """`data/video_forms.json` は**公開済みだけ**を持ちます。

    形の分からない本（2026-08-31 で 70本・最高 897回）を混ぜると、
    この道具の唯一の役目（形をまたがない）が消えます。
    """
    forms = {"a": "ショート", "b": "長尺"}
    recs = form_record.per_video_best(forms=forms)
    ids = {r["id"] for r in recs.values()}
    assert ids <= set(forms), "形の分からない本が記録に混ざっています"


def test_gaps_は帯の形と記録の形をそろえる():
    """**`長尺…` の帯には長尺の記録・それ以外にはショートの記録**が付くこと。

    ここが混ざると、`eta.py` が直そうとしている
    「ショートの1本あたり × 長尺の RPM」がそのまま再発します。
    """
    recs = {"ショート": {"best": 1891, "id": "s", "n": 156, "mean": 1.0, "median": 1.0},
            "長尺": {"best": 156, "id": "l", "n": 22, "mean": 1.0, "median": 1.0}}
    rpm = {"ショート 高": 60, "長尺 お金 高": 2000}
    need = {"ショート 高": 111_111.0, "長尺 お金 高": 3_333.0}
    rows = {r["band"]: r for r in form_record.gaps(
        rpm, need, per_day=1.0, target_yen=200_000, records=recs)}
    assert rows["ショート 高"]["record"] == 1891
    assert rows["長尺 お金 高"]["record"] == 156
    # 記録を毎日 出しても、どちらの形も目標には届きません（2026-08-31 の実測）
    assert rows["ショート 高"]["yen"] == pytest.approx(3_403.8)
    assert rows["長尺 お金 高"]["yen"] == pytest.approx(9_360.0)


def test_記録で割った倍率のほうが_平均で割ったものより小さい():
    """**記録は平均以上**なので、同じ帯なら倍率は必ず小さくなること。

    大小が逆になったら、分母のどちらかが形をまたいでいます。
    """
    recs = form_record.per_video_best()
    if not recs.get("長尺"):
        pytest.skip("長尺の実測がまだ無い")
    r = recs["長尺"]
    assert r["best"] >= r["mean"] >= 0
    assert r["best"] >= r["median"]


def test_規則の本数で解いていること():
    """`ceiling_yen` は `per_day` を掛けること（規則1本/日 が効く所）。"""
    assert form_record.ceiling_yen(1000, 400, 1.0) == pytest.approx(12_000.0)
    assert form_record.ceiling_yen(1000, 400, 2.0) == pytest.approx(24_000.0)
