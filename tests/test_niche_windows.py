"""**形ごとに撃つ窓が違い、それが形の結論を作っていました**（2026-09-04 に測り直した）。

    `short`  再生数順 × 動画 × 4分未満（**日付の絞りなし ＝ 全期間**）  ← ショートの帯
    `year`   再生数順 × 動画 × 今年（**尺の絞りなし**）                   ← 長尺の帯

公開日を埋めて数えたら、ショートの上位の齢は **中央 1,729日（4.7年）**、長尺は **203日**。
`daily_pick.theory_lines` は、その2つを横に並べて「理論値の在る形」を出していました。

`SP_FILTERS` の註には「『今年 × 4分未満』の組み合わせは 5本 しか返らなかった」と
書いてありましたが、**撃ち直すと 79本 返りました**（3語・2026-09-04）。
写した数で決めないこと —— `--windows`（`window_counts`）で毎回 数えられます。
"""
from __future__ import annotations

from scripts import niche_ceiling as nc


def test_sp_は自分で組める() -> None:
    """**手で base64 を書き写さないこと。** 3つとも `sp_param()` の返りと一致すること。"""
    assert nc.sp_param(None, 1) == nc.SP_FILTERS["short"]        # 全期間 × 4分未満
    assert nc.sp_param(5, None) == nc.SP_FILTERS["year"]         # 今年 × 尺なし
    assert nc.sp_param(5, 1) == nc.SP_FILTERS["short_year"]      # 今年 × 4分未満（揃えた窓）


def test_窓の広さで別の値になる() -> None:
    got = {nc.sp_param(u, d) for u in (None, 3, 4, 5) for d in (None, 1)}
    assert len(got) == 8                                        # 取り違えたら潰れる


def test_窓ごとの数を数える(monkeypatch) -> None:
    """`window_counts` は **語ぶんを足して** 1行にすること（1語ずつ見ても窓は比べられない）。"""
    calls: list[str] = []

    class _Y:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False):
            calls.append(url)
            return {"entries": [{"view_count": 10}, {"view_count": 30}]}

    import sys
    import types
    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=_Y))
    rows = nc.window_counts(["a", "b"], cases=[("いま", None, 1), ("今年", 5, 1)])
    assert [r["n"] for r in rows] == [4, 4]                     # 2語 × 2本
    assert [r["median"] for r in rows] == [30, 30]
    assert len(calls) == 4
    assert nc.SP_FILTERS["short"] in calls[0]
    assert nc.SP_FILTERS["short_year"] in calls[2]


def test_yt_dlp_が無くても落ちない(monkeypatch) -> None:
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "yt_dlp":
            raise ImportError("no")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    assert nc.window_counts(["a"]) == []
