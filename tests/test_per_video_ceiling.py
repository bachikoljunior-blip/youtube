"""`per_video` の天井は、**測った全部の最大**であること（1つの窓の最大ではない）。

2026-08-21 03:2x に測り直した。

`config/hypotheses.yaml` の天井は **1,447**（2026-08-15 に閉じた前提の、
**その窓のショート7本**の最大）でした。**天井を n=7 の最大で置くと、
標本が増えるたびに必ず外側が出ます** —— 実際 `data/views.jsonl` の
24時間ふきんの点がある39本で数え直すと **1,891回** で、1.31倍 外側でした。

これは小さな話ではありません。軌跡が「腕を全部振っても出ません」と言うとき、
**名指ししていた塞ぎ手が `per_video` の天井 ×1.57** です。
そこが n=7 の最大で決まっていたら、日付は標本の少なさで決まっていることになります。

**この検査は、記録が更新されたら落ちます。** 落ちたら、
`config/hypotheses.yaml` の `value` を実測の最大へ書き換えること（それが正しい直し方）。
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"

#: 「24時間の再生」として数える窓（時間）。公開直後の点と、伸びきった後の点を外す。
NEAR_24H = (12.0, 36.0)


def measured_max_24h(path: Path = VIEWS) -> tuple[int, str, int]:
    """`data/views.jsonl` から、24時間ふきんの再生の最大を出す。**API は叩かない。**

    返り: `(最大の再生, その動画ID, 数えた本数)`
    """
    by: dict[str, list[tuple[float, int]]] = collections.defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("hours") is None or r.get("views") is None:
            continue
        by[r["id"]].append((float(r["hours"]), int(r["views"])))
    best: dict[str, int] = {}
    for vid, pts in by.items():
        near = [v for h, v in pts if NEAR_24H[0] <= h <= NEAR_24H[1]]
        if near:
            best[vid] = max(near)
    if not best:
        return (0, "", 0)
    vid = max(best, key=lambda k: best[k])
    return (best[vid], vid, len(best))


def _recorded() -> int:
    import yaml

    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    for h in doc.get("hypotheses") or []:
        c = (h or {}).get("ceiling")
        if isinstance(c, dict) and c.get("lever") == "per_video":
            return int(c["value"])
    pytest.fail("`per_video` の天井が `config/hypotheses.yaml` にありません")


def test_記録した天井は実測の最大を下回らない():
    """**下回っていたら、標本が増えて記録が破られたということ。** 書き換えること。"""
    got, vid, n = measured_max_24h()
    if n < 2:
        pytest.skip(f"24時間ふきんの点がある本が {n} 本しかありません")
    rec = _recorded()
    assert rec >= got, (
        f"実測の最大 {got:,}回（{vid}・n={n}本）が、記録した天井 {rec:,} を超えています。"
        f" `config/hypotheses.yaml` の `per_video` の `value` を {got} へ書き換えること"
    )


def test_天井は1つの窓の最大ではない():
    """**n=7 の最大（1,447）に戻ったら落とす。**"""
    got, _, n = measured_max_24h()
    if n < 20:
        pytest.skip(f"標本が {n} 本（20本に満たないので、この検査は判定しない）")
    assert _recorded() >= got, "記録した天井が実測に追いついていません"
    assert _recorded() > 1447, (
        "天井が 1,447（2026-08-15 の窓のショート7本の最大）に戻っています。"
        "**標本が増えれば必ず外側が出ます** —— 全部の実測から数え直すこと"
    )


def test_天井は分子と同じ公開密度で測ってある():
    """**分子だけ規則の密度に揃えて、天井を全密度の最大のままにしないこと。**

    2026-09-01 に踏んだ欠陥そのものです。`scripts/eta.py` の腕 `per_video` の
    倍率 **×2.01** は「天井 ÷ 分子」ですが、

        分子   942回   規則の密度（1〜2本/日）の日**だけ**の平均（2026-08-31 に揃えた）
        天井 1,891回   **全密度の最大**（記録は 3本/日 の日の本）

    と、**母集団が別**でした。同じ機械が測った弾力性は
    `b = -0.663・t = -3.96・95% [-0.991, -0.335]`（密度が上がると1本あたりは薄まる）。
    1,500回以上を出した率も **低密度 3/21 対 高密度 2/139・フィッシャー p = 0.0166** です。

    **この検査は、天井を全密度の最大（1,891）へ戻す差分で落ちます。**
    戻したいときは、`src/rule_per_video.ceiling_at_rule()` の「覆る条件」
    （1本/日 の日が 15日 たまって 1,900回 を超えない）を**実測で満たしてから**、
    この検査ごと消すこと。
    """
    from src import rule_per_video

    c = rule_per_video.ceiling_at_rule()
    if not c:
        pytest.skip("弾力性が測れない（区間が 0 をまたぐ回は、天井を持ち上げません）")
    rec = _recorded()
    assert rec >= c["lo"], (
        f"記録した天井 {rec:,} が、規則の密度へ直した天井の**下端** "
        f"{c['lo']:,.0f}回 を下回っています（点推定 {c['value']:,.0f}回）。"
        f" {c['why']}。**分子は {c['max_per_day']}本/日 までの日で測っているので、"
        "天井も同じ密度で測ること**（`src/rule_per_video.ceiling_at_rule()`）"
    )


def test_この検査は全密度の最大へ戻したら落ちる(monkeypatch):
    """**故障を注入して、上の検査が本当に発火することを確かめる。**

    発火したことのない検査は検査ではない（`CLAUDE.md`）。
    ここでは「天井を 1,891（全密度の最大）へ戻した」世界を作って、
    `test_天井は分子と同じ公開密度で測ってある` が使う不等式が
    **偽になる**ことを見ます。
    """
    from src import rule_per_video

    c = rule_per_video.ceiling_at_rule()
    if not c:
        pytest.skip("弾力性が測れない")
    reverted = c["raw_max_all"]          # ＝ 全密度の最大（1,891）
    assert not (reverted >= c["lo"]), (
        f"全密度の最大 {reverted:,} が、規則の密度へ直した下端 {c['lo']:,.0f} を"
        "まだ上回っています —— **この検査は何も守っていません。**"
        "弾力性が 0 に近づいたか、素材の日が変わったので、"
        "`ceiling_at_rule()` の「覆る条件」を見直すこと"
    )
