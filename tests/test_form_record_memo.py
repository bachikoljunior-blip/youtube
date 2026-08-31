"""**予測の道具が、答えを返せる時間で終わること**（2026-08-31・最適化の回）。

## この検査が持っている主題

`CLAUDE.md` は毎回こう言います —— **「毎回これを出してから作業を決める」**
（`scripts/eta.py` の1行目）。**この回、その道具は終わりませんでした。**

    python scripts/eta.py --offline --no-record   →  **300秒 走って未完**

faulthandler で背骨を取ると、100% ここで止まっていました::

    trajectory() の1日ずつの探索ループ
      → analyse() → _gate_legs()
      → form_record.per_video_best() → censor_factor() → json.loads

**実測（2026-08-31・この回に撃った・API 0単位）**::

    150秒 のうち **139.4秒（93%）** が per_video_best() の中
    その間の呼び出し **623回**（それでもまだ終わっていない時点の数）
    1回 620ms ＝ data/views.jsonl（2MB・22,667行）を **3回** 読む
      （自分で1回 ＋ censor_factor が形ごとに1回ずつ ＝ 2回）

`_CENSOR_MEMO` は、この形を**塞いだつもりで塞げていませんでした**。
憶える条件が `views_path is None and forms is None` なのに、
**唯一の呼び手 `per_video_best()` は常に両方を渡す** ので、一度も当たりません。
その註が書いていた「1回の走りで 6〜8回」も外れです（実測 623回 以上）。

**「憶えている」と書いてあることは、憶えている証拠になりません。**
一度も当たったことのない憶えは、無いのと同じです。だから数えます。

## この検査が見ている3点

1. **同じファイルなら読み直さないこと**（回数を数える。速さは測りません ——
   速さの検査は機械の混み具合で揺れます）
2. **ファイルが動いたら憶えを捨てること**（憶えが古くなる道を塞ぐ。
   ここが緩むと、`data/views.jsonl` が伸びても記録が動かなくなります ——
   **速くなる代わりに、間違った数で日付を出す**という、いちばん高い壊れ方）
3. **返すのは写しであること**（`scripts/eta.py` は返りの dict を触ります。
   憶えの本体を渡すと、1回目の呼び手の書き込みが2回目に漏れます）

**緩めないこと。** 2 を落とすと 1 が「速い嘘」になります。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src import form_record


def _views_reads(fn) -> int:
    """`fn()` のあいだに `data/views.jsonl` を何回 読んだか。"""
    n = [0]
    orig = Path.read_text

    def counting(self, *a, **k):
        if self.name == "views.jsonl":
            n[0] += 1
        return orig(self, *a, **k)

    Path.read_text = counting                                  # type: ignore[assignment]
    try:
        fn()
    finally:
        Path.read_text = orig                                  # type: ignore[assignment]
    return n[0]


def test_同じファイルなら_記録は読み直さない():
    """**1 の検査。** 5回 呼んでも、読むのは最初の1回ぶんだけ。

    落ちたときの直し方: `form_record._BEST_MEMO` / `_CENSOR_MEMO` の鍵を見ること。
    鍵が「既定の引数で呼んだか」に戻っていたら、**唯一の呼び手が引数を渡すので
    一度も当たりません**（それが 2026-08-31 まで の姿です）。
    """
    if not form_record.VIEWS.exists():
        pytest.skip("`data/views.jsonl` がありません")
    form_record.censor_memo_clear()

    # **冷たい1回ぶんは数えません。** そこは `censor_factor` と `settle.settles_at`
    #     （地平ぶん読む）の合計で、形の数と地平の数で決まります ——
    #     **憶えの検査ではありません。** 見るのは「**2回目からは 0 か**」だけ。
    #     実測 2026-08-31: 冷たい1回 = 11回 読み（1 ＋ 形2 ＋ `_settled` の地平ぶん）。
    cold = _views_reads(form_record.per_video_best)
    assert cold > 0, "1回目が 0回 読み ＝ この検査は素通りしています（前の回が憶えを残した）"

    def four_more():
        for _ in range(4):
            form_record.per_video_best()

    again = _views_reads(four_more)
    assert again == 0, (
        f"1回目に {cold}回 読んだ後、さらに 4回 呼んだら {again}回 読み直しました。"
        " **憶えが当たっていません。** 鍵が「既定の引数で呼んだか」に戻っていると、"
        "唯一の呼び手 `per_video_best()` が常に引数を渡すので一度も当たりません。"
        " 実測 2026-08-31: この形で `scripts/eta.py --offline` は 300秒 走って終わりませんでした"
        f"（4回ぶんなら {cold - 3}〜{4 * 3}回 前後 読み直します）"
    )


def test_ファイルが動いたら憶えは捨てられる(tmp_path: Path):
    """**2 の検査（いちばん大事）。** 速い嘘を作らないこと。

    憶えが古くなると、`data/views.jsonl` が伸びても記録が動かなくなります。
    そのとき機械は**速く・間違った**日付を出します。
    """
    views = tmp_path / "views.jsonl"
    forms = {"aaaaaaaaaaa": "長尺", "bbbbbbbbbbb": "長尺"}
    rows = [
        {"at": "2026-08-01T00:00:00Z", "id": "aaaaaaaaaaa", "hours": 100.0, "views": 10},
        {"at": "2026-08-01T00:00:00Z", "id": "bbbbbbbbbbb", "hours": 100.0, "views": 20},
    ]
    views.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    form_record.censor_memo_clear()
    before = form_record.per_video_best(views_path=views, forms=forms)
    assert before["長尺"]["best"] == 20

    with views.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": "2026-08-02T00:00:00Z", "id": "aaaaaaaaaaa",
                             "hours": 124.0, "views": 999}) + "\n")
    # mtime の刻みが粗い環境で、追記が同じ刻みに落ちないようにする
    import os
    st = views.stat()
    os.utime(views, ns=(st.st_atime_ns + 10 ** 9, st.st_mtime_ns + 10 ** 9))

    after = form_record.per_video_best(views_path=views, forms=forms)
    assert after["長尺"]["best"] == 999, (
        "`data/views.jsonl` が伸びたのに記録が動きませんでした。"
        " **憶えが古くなっています** —— 鍵にファイルの mtime／大きさが入っているか"
        " (`form_record._file_key`) を見ること。**速い嘘は、遅い正しさより高くつきます**"
    )


def test_憶えが返すのは写しである():
    """**3 の検査。** 呼び手が触っても、次の呼び手に漏れないこと。

    `scripts/eta.py` は `per_video_best()` の返りを組み替えて使います。
    憶えの本体を渡すと、**1回目の書き込みが2回目の答えになります。**
    """
    if not form_record.VIEWS.exists():
        pytest.skip("`data/views.jsonl` がありません")
    form_record.censor_memo_clear()
    first = form_record.per_video_best()
    if not first:
        pytest.skip("記録がありません")
    form = next(iter(first))
    keep = first[form]["best"]
    first[form]["best"] = -12345
    second = form_record.per_video_best()
    assert second[form]["best"] == keep, (
        "憶えの本体をそのまま返しています。呼び手が触ると次の答えが変わります"
    )


def test_記録を何度も引く輪が_現実的な時間で終わる():
    """**1 の別の測り方。** 回数ではなく、**桁**で見ます。

    `eta.trajectory()` は `analyse()` を探索の日数ぶん回し、`analyse()` は
    `_gate_legs()` 経由でここを呼びます。実測 623回 でも終わりませんでした。
    ここでは 200回 を 1つの読み込みぶんの時間で終わらせられることだけ見ます
    （**絶対の秒では見ません** —— 混んだ機械で揺れるので、
      「冷たい1回」との比で見ます）。
    """
    if not form_record.VIEWS.exists():
        pytest.skip("`data/views.jsonl` がありません")
    form_record.censor_memo_clear()
    t = time.perf_counter()
    form_record.per_video_best()
    cold = time.perf_counter() - t

    t = time.perf_counter()
    for _ in range(200):
        form_record.per_video_best()
    warm200 = time.perf_counter() - t

    assert warm200 < cold * 5, (
        f"暖まった 200回（{warm200:.2f}秒）が、冷たい 1回（{cold:.2f}秒）の 5倍 を超えました。"
        " **憶えが効いていません。** 200回 が 200倍 かかる形のまま `eta.trajectory()` を"
        " 回すと、道具は終わりません（実測 2026-08-31: 300秒 で未完）"
    )
