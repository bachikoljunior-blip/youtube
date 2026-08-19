"""`src/build_perf.py` の検査。

**先に置いたのは「既知の当たり」1件**（`docs/trigger_main.md` §4）——
`test_key_resolves_for_most_measured_videos` です。

2026-08-19 15:1x の回は「鍵（`video_id` → テーマID）を `data/uploaded.jsonl` から
作る道は**使えません**。直近28日に再生のあった28本のうち ledger に居たのは6本だけ」と
申し送りました。**この道具は、その申し送りが正しければ成り立ちません。**
だから最初に、実物で数え直す検査を置いています。**落ちたら、どちらかが嘘です。**
"""

from __future__ import annotations

import json

from src import build_perf


def test_key_resolves_for_most_measured_videos():
    """**再生のある本の大半は、控えからテーマIDが引けます。**

    15:1x の申し送り（6/28 しか引けない）はここで落ちます。
    実測 2026-08-19: 再生のある20本のうち **19本**。
    """
    stats = build_perf.per_video()
    led = build_perf.ledger()
    have = [v for v, s in stats.items() if s.get("views", 0) > 0]
    hit = [v for v in have if v in led]
    assert len(have) >= 10, "実績のある本が少なすぎます（scan が古い？）"
    assert len(hit) / len(have) >= 0.8, (
        f"控えから鍵が引けたのは {len(hit)}/{len(have)} 本。"
        "8割を切ったら、`data/uploaded.jsonl` の書き込みが落ちています"
    )


def test_features_are_all_known_before_publishing():
    """**特徴は全部、公開前に決まっているものだけ。**

    再生や engaged を特徴に混ぜると「よく回った本はよく回る」という
    同義反復が向きとして出ます。
    """
    f = build_perf.features("nonexistent-topic", "年金の繰下げは1234円得します #Shorts", {})
    assert set(f) == {"図の枚数", "棒の本数", "題の幅", "題の数字の桁", "題の数字の個数"}
    assert f["題の数字の桁"] == 4.0
    assert f["題の数字の個数"] == 1.0
    assert f["図の枚数"] == 0.0


def test_width_counts_fullwidth_as_two():
    assert build_perf._width("年金") == 4
    assert build_perf._width("ab") == 2
    # **#Shorts は幅に入れません**（全部の題に付くので、差を作りません）
    a = build_perf.features("t", "年金 #Shorts", {})["題の幅"]
    b = build_perf.features("t", "年金", {})["題の幅"]
    assert a == b == 4


def test_min_views_floor_is_reported_not_hidden():
    """**落とした本は数えて出すこと。**（15:0x の「床」の件と同じ形）"""
    rows, dropped = build_perf.collect()
    assert rows, "測れる本が1本もありません"
    assert all(r["views"] >= build_perf.MIN_VIEWS for r in rows)
    # 落ちた側は理由つきで残っている
    assert all(isinstance(w, str) and w for _, w in dropped)


def test_correlations_cover_every_feature():
    rows, _ = build_perf.collect()
    names = set(rows[0]["features"])
    assert {n for n, _, _ in build_perf.correlations(rows)} == names


def test_bars_file_is_readable():
    """図の枚数の出どころ。**壊れたら特徴が全部0になって、静かに無関係が出ます。**"""
    data = json.loads(build_perf.BARS.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and data
    assert any("charts" in v for v in data.values())
