"""`src/m8_funnel.py` の検査。

**既知の当たりを先に置いています**（`docs/trigger_main.md` §4）。
この道具はまだ何も出していないので、出力の量や見た目では正しさが分かりません。
**手で確かめた1件だけが物差しです。**

置いた当たりは「実データの偶然」ではなく、**`falsified_if` の本文と
`config/pairs.yaml` が食い違っていないこと**です（02:1x の踏み方を避ける）。
実データが動いても意味が変わりません。
"""
from __future__ import annotations

from src import m8_funnel as m8


# --- 既知の当たり（手で確かめた・2026-08-20 08:3x）-------------------------
#
# `config/hypotheses.yaml` の反証条件は本文にこう書いてあります:
#
#     導線を入れたショート **8本** が計3,000再生に達した時点で、
#     対応する長尺 **6本** の再生のうち …
#
# この 8 と 6 は `config/pairs.yaml` の鍵の数と、値の重複を除いた数です。
# **表を足し引きすると、claim の本文だけが静かに古くなります。**
# 判定は「8本ぶんの再生」で門を開けるので、実際が7本なら門が下がり、
# 9本なら claim が測っていない本まで混ざります。


def test_既知の当たり_claimの8本と6本はpairs_yamlと一致する() -> None:
    pairs = m8.load_pairs()
    _, longs = m8.populations(pairs, m8.load_ledger())
    assert len(pairs) == m8.CLAIMED_SHORTS
    assert len(longs) == m8.CLAIMED_LONGS


def test_既知の当たり_pairsの鍵は全部が控えに実在する() -> None:
    """引けない鍵があると、**8本と言いながら7本で門を開けます。**

    落ちたら `config/pairs.yaml` か `data/uploaded.jsonl` のどちらかが
    先に進んでいます。**消さずに、どちらが正かを決めること。**
    """
    pairs = m8.load_pairs()
    shorts, _ = m8.populations(pairs, m8.load_ledger())
    missing = [topic for topic, ids in shorts.items() if not ids]
    assert missing == [], f"控えに無いテーマ: {missing}"


# --- 配線（手で作った行。実データが動いても意味が変わらない）---------------


def test_populations_は同じ長尺を2度返さない() -> None:
    pairs = {"a": "L1", "b": "L1", "c": "L2"}
    ledger = [
        {"topic": "a", "video_id": "S1"},
        {"topic": "b", "video_id": "S2"},
        {"topic": "c", "video_id": "S3"},
    ]
    shorts, longs = m8.populations(pairs, ledger)
    assert longs == ["L1", "L2"]
    assert shorts == {"a": ["S1"], "b": ["S2"], "c": ["S3"]}


def test_populations_は撮り直しを落とさず全部返す() -> None:
    """どれが導線入りかは控えからは決まらないので、**選ばずに渡します。**"""
    pairs = {"a": "L1"}
    ledger = [
        {"topic": "a", "video_id": "S1"},
        {"topic": "a", "video_id": "S2"},
    ]
    shorts, _ = m8.populations(pairs, ledger)
    assert shorts == {"a": ["S1", "S2"]}


def test_populations_は控えに無い鍵を空で返す() -> None:
    shorts, _ = m8.populations({"a": "L1"}, [])
    assert shorts == {"a": []}


def test_residual_は説明のつく4経路を引く() -> None:
    src = {
        "RELATED_VIDEO": 6,
        "YT_SEARCH": 1,
        "YT_CHANNEL": 1,
        "EXT_URL": 2,
        "NO_LINK_OTHER": 3,
        "SHORTS": 4,
    }
    assert m8.residual(src) == 7


def test_residual_は説明のつくものだけなら0() -> None:
    assert m8.residual({"RELATED_VIDEO": 6, "YT_SEARCH": 1}) == 0


def test_verdict_はショートが門に届くまで判定しない() -> None:
    out = m8.verdict(2999, 0)
    assert out["state"] == "not_yet"


def test_verdict_は届いて残りが足りなければ外れ() -> None:
    out = m8.verdict(3000, 4)
    assert out["state"] == "falsified"


def test_verdict_は届いて残りが足りれば保つ() -> None:
    out = m8.verdict(3000, 5)
    assert out["state"] == "held"


def test_verdict_の門は基準0からの上げ幅で見る() -> None:
    """基準は 3 ではなく 0（2026-08-15 に数えるものを直した）。"""
    assert m8.BASELINE == 0
    assert m8.NEED == 5
    assert m8.verdict(5000, 5)["state"] == "held"
    assert m8.verdict(5000, 4)["state"] == "falsified"
