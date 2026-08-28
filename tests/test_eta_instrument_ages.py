"""**天井の隣に、その天井が乗っている控えの齢を置く**（2026-08-28・最適化の回）。

天井は **2つの実測の積**（混ざり方 × 面）です。そのどちらかが止まっても
**天井は黙って低く出ます** —— 実測 2026-08-24: `data/reach.jsonl` が 08/17 で
止まったまま出た天井が **¥184**、`scripts/reach.py` を撃ち直したら **¥287**。
**止まっていたことは、どこにも表示されていませんでした。**

`src.rpm_mix._reach_freshness_lines` は、この遅れを正しく測る書き方を
2026-08-24 に既に持っていました。**読まれる場所に無かっただけ**です
（あれが出るのは `rpm_mix` 自身の出力で、1周の中で誰も撃ちません）。
だから `eta.headline()` —— **毎回いちばん最初に読む3行** —— の側へ出します。

## この検査が留めている3つの向き

1. **しきい値を置かない。** 控えごとに追いつける最前線が違うので、
   時間で切ると追いついている日にも鳴ります（`_reach_freshness_lines` の註）。
   **事実（齢）だけを並べ、どれを取り直すかはその回が決めます。**
2. **日枠と別の枠を混ぜない。** `snapshot.py` だけが Data API の日枠。
   Analytics と Reporting は別の枠なので、日枠が尽きていても通ります
   （2026-08-28 に実際に通り、要件1件の判定日が 09-03 → 08-30）。
3. **齢は「中身の齢」であって「いつ撃ったか」ではない。**
   2026-08-28 に `python -m src.rpm_mix` を撃ち直しましたが、Analytics は
   3日遅れで新しい日が無く、**齢は 54時間 のまま動きませんでした**
   （控えも1行も増えていません）。**撃ち直しで齢が 0 に見える作りは、
   08/27 に取り下げた『偽の新しさ』と同じ形**です。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import eta  # noqa: E402
from src import upload_cap  # noqa: E402


def _dq(*, is_open: bool):
    return upload_cap.DayQuota(open=is_open, observed=not is_open, hits=364,
                               resets_at=datetime.now(timezone.utc) + timedelta(hours=1),
                               line="(検査)")


def test_控えの齢が1行にそろって出る():
    lines = eta.instrument_ages()
    assert len(lines) == 1, "**3行の側に置くので、1行に畳むこと**"
    line = lines[0]
    for label in ("面（インプレッション）", "混ざり方（RPM）", "1本あたり再生", "本べつの形"):
        assert label in line, f"天井が乗っている控え `{label}` が出ていません"


def test_日枠が尽きていればsnapshotだけを撃てない側に置く(monkeypatch):
    """**枠を混ぜないこと。** Analytics / Reporting は別の枠で、通ります。"""
    monkeypatch.setattr(upload_cap, "day_quota", lambda *a, **k: _dq(is_open=False),
                        raising=False)
    line = eta.instrument_ages()[0]
    head, _, tail = line.partition("1本あたり再生")
    assert "取り直せません" in tail.split("／")[0], \
        "**日枠を使う `snapshot.py` の側に、撃てない印が付いていません**"
    assert "取り直せません" not in head, \
        "**別の枠の控えまで『撃てない』側に落ちています**（08/28 の前の回が踏んだ読み違い）"
    assert "別の枠なので通ります" in line


def test_日枠が開いていれば誰も撃てない側に置かない(monkeypatch):
    monkeypatch.setattr(upload_cap, "day_quota", lambda *a, **k: _dq(is_open=True),
                        raising=False)
    assert "取り直せません" not in eta.instrument_ages()[0]


def test_しきい値で黙らない(monkeypatch):
    """**古い日だけ出す作りにしないこと。** 事実は毎回そろって出ます。

    鳴らす作りにすると、こんどは「何時間で鳴らすか」を次の回が世話します
    —— 控えごとに最前線が違うので、その数は決められません。
    """
    monkeypatch.setattr(upload_cap, "day_quota", lambda *a, **k: _dq(is_open=True),
                        raising=False)
    assert eta.instrument_ages(), "**追いついている日に黙ると、天井の齢が見えなくなります**"


def test_headlineが齢を連れてくる():
    """**入口はこちら。** 3行を組む側が `instrument_ages()` を呼んでいること。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    body = src.split("def headline(", 1)[1]
    assert "instrument_ages()" in body, \
        "**齢が、毎回読む3行の側に降りていません**（読まれない場所に置くと、08/24 に戻ります）"


def test_控えが壊れていてもetaを落とさない(monkeypatch, tmp_path):
    """**毎回いちばん最初に撃つ道具です。** 齢の行のために回を殺さないこと。

    `newest_point` は控えを解析するので、壊れた1件で例外が出ます。
    そこで落ちると、**その回は到達予測を1行も読めないまま終わります。**
    """
    import deadline_check

    def boom(_path):
        raise ValueError("壊れた控え")

    monkeypatch.setattr(deadline_check, "newest_point", boom, raising=False)
    lines = eta.instrument_ages()
    assert lines, "**例外を飲んだ結果、行ごと消えています**"
    assert "齢が読めません" in lines[0]


def test_控えが無くても落ちない(monkeypatch):
    monkeypatch.setattr(eta, "ROOT", Path("/nonexistent-xyz"), raising=False)
    lines = eta.instrument_ages()
    assert lines and "無し" in lines[0]
