"""**形ごとの「伸びきる年齢」は、地平を延ばしても同じか。**（2026-08-31・最適化の回）

## なぜこの検査が要るか（実測で見つけました。**API 0単位**）

`src/settle.py` の `MATURE_HOURS_BY_FORM["長尺"] = 96` は、
`views_curve(..., full_at=168.0)` から出た数です。**その 168 は「置いた」数**で、
同じ関数の覆る条件が自分でこう書いていました ——

> **168時間 を「伸びきった」と置いているのも、長尺には短い**見込みです。
> **ここが伸びるほど、上の割合はさらに下がります**

**延ばして当てました。下がるどころか、答えが消えます**
（`settle.settles_at()`・`share_settled` が 95% を超える最小の年齢）::

    地平    形        24h   48h   72h   96h  120h  168h  240h  336h    n
    168h  ショート    61%   81%   89%   91%   92%  100%  100%  100%   99
    480h  ショート    57%  100%  100%  100%  100%  100%  100%  100%    9
    168h  長尺        12%   25%   38%   62%   62%  100%  100%  100%    8
    240h  長尺         0%   12%   25%   50%   50%   50%  100%  100%    8
    336h  長尺         0%    0%    0%    0%    0%    0%    0%  100%    5
    480h  長尺         0%    0%    0%    0%    0%    0%    0%    0%    5

**ショートは、どの地平でも 48〜72時間 で 100%。地平を延ばしても動きません。**
**長尺は、地平を延ばすと「伸びきる年齢」が1つも出ません。**

## これが縛っている所

`scripts/eta.py` の `drop_unripe` は、齢 96時間 の長尺を**「一生ぶん」として
標本に入れます**。そこから出るのが `long_per_video`（16.0回/本）と
長尺の記録（156回/本）で、その2つが `src/form_record` の **×21.4** ——
**この機械が持っている「形をまたがない」いちばん小さい隔たり**を作ります。

**分母が伸びきっていないなら、×21.4 は隔たりの上限であって、実測ではありません。**
そして「どの帯でも届きません」の長尺側は、その分母の上に立っています。

## この検査が守るもの

**数そのものではありません**（標本が増えれば動きます）。守るのは
**「伸びきっていない形の記録を、伸びきったものとして出さないこと」** ——
`form_record.per_video_best()` の `settled` が、実測と食い違ったら落とします。

## 覆る条件

- **長尺が伸びきる年齢が1つでも出たとき。** そのとき `settled` が真になり、
  下の `test_長尺は伸びきっていない` が落ちます。**落ちたら消してよい検査です**
  （そのときは `MATURE_HOURS_BY_FORM["長尺"]` を実測の年齢へ書き換えること）
- `data/views.jsonl` が古い長尺を観測しなくなったとき。**地平が足りなくなり、
  この検査は「伸びきらない」側へ黙って倒れます** —— 齢 649時間 の長尺が
  積まれ続けていることが前提です
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import form_record, settle  # noqa: E402


def test_ショートは地平を延ばしても伸びきる():
    """**ショートは 48時間 で伸びきる。** 地平 480時間 でも同じ。"""
    s = settle.settles_at("ショート")
    if not s["by_horizon"]:
        pytest.skip("`data/views.jsonl` にショートの標本がありません")
    assert s["supported"], (
        "ショートが、いちばん長い地平で伸びきらなくなりました。"
        f" 地平ごと: {s['by_horizon']}。"
        " `MATURE_HOURS_BY_FORM['ショート']` を測り直すこと"
    )
    assert s["hours"] is not None and s["hours"] <= settle.mature_hours("ショート"), (
        f"ショートが伸びきる年齢 {s['hours']}時間 が、"
        f" `MATURE_HOURS_BY_FORM['ショート'] = {settle.mature_hours('ショート')}` を"
        " 超えました。**標本に入れる年齢のほうを上げること**"
    )


def test_長尺は伸びきっていない():
    """**この検査は「落ちたら直す」ではなく「落ちたら消してよい」側です。**

    落ちる ＝ 長尺が伸びきる年齢が出た ＝ `×21.4` の分母が実測になった、
    という**良い知らせ**です。そのときは `MATURE_HOURS_BY_FORM["長尺"]` を
    その年齢へ書き換えて、この検査を消すこと。
    """
    s = settle.settles_at("長尺")
    if not s["by_horizon"]:
        pytest.skip("`data/views.jsonl` に長尺の標本がありません")
    assert not s["supported"], (
        f"**長尺が伸びきる年齢が出ました（{s['hours']}時間）。良い知らせです。**"
        f" 地平ごと: {s['by_horizon']}。"
        f" `src/settle.py` の `MATURE_HOURS_BY_FORM['長尺']`"
        f"（いま {settle.mature_hours('長尺')}）をその年齢へ書き換え、"
        " この検査を消すこと"
    )


def test_記録は伸びきりの実測と食い違わない():
    """`form_record` の `settled` が、`settle` の実測とずれたら落とす。

    **写しが黙って古くなる形を塞ぎます** —— ずれたらどちらかが古い。
    """
    recs = form_record.per_video_best()
    if not recs:
        pytest.skip("`data/views.jsonl` / `data/video_forms.json` がありません")
    for form, rec in recs.items():
        want = settle.mature_hours_supported(form)
        assert rec.get("settled") == want, (
            f"`form_record` は {form} を settled={rec.get('settled')} と持っていますが、"
            f" `settle.mature_hours_supported({form!r})` は {want} です。"
            " **どちらかが古い。** `form_record._settled()` を見ること"
        )


def test_伸びきっていない形の記録は下限として扱われる():
    """**`gaps()` の行が `settled` を運んでいること。**

    運ばないと、`scripts/eta.py` は `×21.4` を「実測の隔たり」として印字します。
    **分母が下限なら、比は上限**です。そこを言わない印字は、
    `CLAUDE.md`「(イ) 裸の『届きません』を出さないこと」に反します。
    """
    recs = form_record.per_video_best()
    if not recs:
        pytest.skip("記録がありません")
    rows = form_record.gaps({"ショート 高": 60, "長尺 お金 高": 2_000},
                            {"ショート 高": 111_111.0, "長尺 お金 高": 3_333.0},
                            per_day=1.0, target_yen=200_000)
    assert rows, "`gaps()` が1行も返しません"
    for r in rows:
        assert "settled" in r, (
            f"`gaps()` の行に `settled` がありません: {r['band']}。"
            " **伸びきっていない分母の比を、実測の比として出すことになります**"
        )
        assert r["settled"] == recs[r["form"]]["settled"]
