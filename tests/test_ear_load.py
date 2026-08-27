"""**一息で、耳がいくつ数を持たされているか**（2026-08-27・オーナー指摘）。

オーナー原文（2026-08-27 21:0x）:

> 「一つの考えなんだけどさ、動画についてまず何言ってるか分かんないね。
> **音声だけで理解できない説明なのに画面はすぐ切り替わるし。**
> 説明を理解するにはかなり視聴者側の推論が必要だと思う。」

実測（`data/critique_queue/` の控え 539本・3,834コマ）:

    1コマあたりの数    中央値 2.0 ／ 平均 2.21 ／ **最大 16**
    5個以上            **514コマ（13.4%）／ 75本（14%）**

いちばん重い1コマは、**この日に予約した本**（`xaciR1LbaEs`）でした。

`src/narrated.py` と**向きが逆**です（あちらは「言った数が絵に在るか」）。
両方 要ります —— 絵に在っても、耳が16個は持てません。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import script_writer, verify  # noqa: E402


def _script(*narrations: str) -> dict:
    return {"segments": [{"narration": n, "visual": {"kind": "stat"}}
                         for n in narrations]}


def test_数が5個以上のコマを拾う():
    bad = ("下がり幅は2人で16万5千円、3人で22万円、4人で24万7500円、"
           "5人で26万4千円、10人で29万7千円です。")
    got = verify._check_ear_load(_script(bad))
    assert len(got) == 1
    # **見出しの数（「2人」「3人」）も数えます** —— 耳はそれも持たされるので。
    # 5個 ＝ おおむね「2組（見出し＋値）を超えたところ」です。
    assert "10個" in got[0]
    # **直し方まで言うこと** —— 落とすだけでは書き直しの輪が動きません
    assert "table" in got[0] or "chart" in got[0]
    assert "画面から数を減らさないこと" in got[0]


def test_4個までは通す():
    """**厳しくしないこと。** 書き直しの輪は3回しかありません
    （`long_script_problems` の冒頭）。"""
    ok = "2人で16万5千円、10人で29万7千円です。"      # 見出し2つ + 値2つ = 4個
    assert verify._check_ear_load(_script(ok)) == []


def test_形を言う直し方は通る():
    """**画面の数は1つも減らしていません。**耳の側だけを軽くした形。"""
    ok = ("2人めがいちばん重くて16万5千円。そこから先は伸びが鈍って、"
          "10人でも29万7千円どまりです。")
    assert verify._check_ear_load(_script(ok)) == []


def test_台本が無い回は黙る():
    assert verify._check_ear_load(None) == []
    assert verify._check_ear_load({}) == []


def test_門は_verify_run_ではなく書き直しの輪に置いてある():
    """**誤報は不投稿**なので、`verify.run` の門にはしません
    （`_check_narrated_shown` と同じ考え方 —— あちらの docstring
    「`verify` で落とすと1本 捨てになる」）。

    ここが落ちたら、**置き場所が変わっています。**
    """
    src = Path(script_writer.__file__).read_text(encoding="utf-8")
    assert src.count("verify._check_ear_load(data)") == 2, \
        "長尺とショートの両方の書き直しの輪に入っていること"
    run_src = Path(verify.__file__).read_text(encoding="utf-8")
    body = run_src.split("def run(", 1)[1] if "def run(" in run_src else ""
    assert "_check_ear_load" not in body, \
        "**`verify.run` の門にしないこと。**誤報が1本まるごとの不投稿になります"


def test_上限は定数で持っている():
    """**覆る条件が「数を動かす」なので、散らばっていると動かせません。**"""
    assert verify.EAR_LOAD_MAX == 5
    src = Path(verify.__file__).read_text(encoding="utf-8")
    assert src.count("EAR_LOAD_MAX") >= 3   # 定義 + 判定 + 文言


def test_書き手への指示にも入っている():
    """**輪で直させるより、初稿が良いほうが安い**（`claude -p` に約250秒）。"""
    src = Path(script_writer.__file__).read_text(encoding="utf-8")
    assert "一息（1セグメント）で、耳に載せる数は4個まで" in src
    assert "列挙は画面の仕事です" in src


def test_指摘は重い順に3件までにする():
    """**書き直しの輪は3回しかありません。** 控え539本の実測では、
    捕まる本の1本あたり **6.9件**。全部 並べると、他の検査の指摘が
    同じ画面の下へ押し出されます（この repo が何度も踏んでいる形）。
    **消してはいません** —— 残りは件数で言います。
    """
    heavy = [f"{i}人で{i}万{i}千円、{i+1}人で{i+1}万{i+1}千円、"
             f"{i+2}人で{i+2}万{i+2}千円です。" for i in range(1, 7)]
    got = verify._check_ear_load(_script(*heavy))
    assert len(got) == verify.EAR_LOAD_REPORT + 1      # 3件 + 「ほか N件」
    assert "ほか" in got[-1]
    # **重い順**（上から順に、載せている数が減っていく）
    nums = [int(g.split("**")[1].replace("個", "")) for g in got[:-1]]
    assert nums == sorted(nums, reverse=True)
