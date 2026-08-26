"""**`--long` は、選ぶ側にも効くこと**を固定する（2026-08-26 に踏んだ）。

`scripts/batch_build.py --long` は長らく `build_one(topic, long_form)` にしか
`--long` を渡しておらず、**題は在庫の上から取っていました。**
在庫はショート向け（`s-` で始まる id）が圧倒的多数なので、
**`--long` を付けても、ほぼ確実にショート向けの題で長尺を作ります。**

実測（2026-08-26 01:5x）: 長尺向けの題を7件足した直後の `--count 1 --long` が
`s-zangyo-nenkan-kyujitsu-tanka` を取り、5.4分の長尺として投稿しました。
**落ちも警告も出ません** —— ショート向けの細い表が尺に引き伸ばされるだけで、
外からは成功に見えます。だから**検査でしか気づけません。**

ここで固定するのは3つ:

1. `--long` のときは `s-` の題を取らない
2. **長尺向けが在庫に無い回は、止めずにショート向けを取る**
   （投稿が途切れるのが最大の損失。`CLAUDE.md`）
3. 既定（ショート）のときは、今までどおり両方から取る
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from scripts import batch_build  # noqa: E402


def _topics(*ids: str) -> dict:
    return {"topics": [{"id": i, "calc": i.split("-")[-1], "score": 1.0,
                        "calc_sections": [f"節 {i}"]} for i in ids]}


def _stub(monkeypatch, *ids: str) -> None:
    from src import config

    monkeypatch.setattr(config, "load_topics", lambda: _topics(*ids))
    monkeypatch.setattr(batch_build, "_posted_including_ledger", lambda: set())
    monkeypatch.setattr(batch_build, "_drop_doomed", lambda u, p: u)
    monkeypatch.setattr(batch_build, "_drop_queue_tail_calcs", lambda u, p: u)


def test_長尺はショート向けの題を取らない(monkeypatch):
    _stub(monkeypatch, "s-alpha", "s-bravo", "charlie", "s-delta")
    got = [t["id"] for t in batch_build.pick(3, [], long_form=True)]
    assert got == ["charlie"], got


def test_長尺向けが無い回は止めずにショート向けを取る(monkeypatch):
    _stub(monkeypatch, "s-alpha", "s-bravo")
    got = [t["id"] for t in batch_build.pick(2, [], long_form=True)]
    assert len(got) == 2, got
    assert all(i.startswith("s-") for i in got), got


def test_既定は両方から取る(monkeypatch):
    _stub(monkeypatch, "s-alpha", "charlie")
    got = [t["id"] for t in batch_build.pick(2, [])]
    assert sorted(got) == ["charlie", "s-alpha"], got


# ---- ショートの回が、長尺の在庫を食うときの値札（2026-08-26 09:5x に踏んだ）----
#
# `--long` を付けない `pick` は `s-` で始まらない題も候補に残します
# （そうでないと「深い題をショートで出す」前提が永久に溜まりません）。
# ですが `s-` で始まらない題は、**そのまま長尺の在庫**でもあります。
# 族の最後の1件をショートで使うと、**7日ぶんの長尺の上限が2本 落ちます。**
#
# 実測: `topic_forge --count 2 --long` で `jutaku` の族を作って
# 上限を 22本 → 24本 にした直後、同じ回の `batch_build --count 2`（`--long` なし）が
# `jutaku-hanbun-jougen` を取りました。**どこにも印字されません。**
#
# **止めません。** どちらの使い道にも理由があるので、**値札を出すだけ**にします。


def _stub_ledger(monkeypatch, used: set[str]) -> None:
    from src import dupes

    monkeypatch.setattr(dupes, "ledger_rows",
                        lambda: [{"topic": t} for t in used])


def test_ショート向けの題があるなら_族の最後の1件は残す(monkeypatch):
    """**2026-08-26 12:0x に向きを変えた検査です。消していません。**

    ここは長らく「`charlie`（族の最後の深い題）を取って、**値札を出す**」を
    固定していました。09:5x の回が値札を足したときの検査です。

    ですが値札は**選んだ後**に出ます。同じ在庫に `s-delta` が居るのだから、
    **そちらを取れば族は死にません** —— 値札を読む人は要らなかった。
    実測（12:0x の `pick(8)`）: **同じ深い題3件**を取りながら、
    落ちる上限が **2本 → 0本** になりました。

    だから固定するものを裏返しました。**値札そのものは消していません** ——
    逃げ場が無い回には、下の `test_逃げ場が無い回は_値札を出して取る` で出ます。
    """
    _stub(monkeypatch, "charlie", "s-delta")
    _stub_ledger(monkeypatch, set())
    got = [t["id"] for t in batch_build.pick(1, [])]
    assert got == ["s-delta"], got


def test_逃げ場が無い回は_値札を出して取る(monkeypatch, capsys):
    """**在庫が尽きているときは止めません**（投稿が途切れるのが最大の損失）。

    守りは1周目だけで、埋まらなければ2周目が同じ手を取ります。
    そのときは 09:5x の値札が、今までどおり出ること。
    """
    _stub(monkeypatch, "charlie")
    _stub_ledger(monkeypatch, set())
    got = [t["id"] for t in batch_build.pick(1, [])]
    assert got == ["charlie"], got
    out = capsys.readouterr().out
    assert "7日ぶんの長尺の上限が 2本 落ちます" in out
    # **止めないこと**（深い題ショートは 09/03 の前提に積む）
    assert "止めません" in out
    assert "topic_forge.py --count N --long" in out


def test_族に長尺の題がまだ残るなら_上限は動かないと言う(monkeypatch, capsys):
    # 同じ族（calc は id の最後の語）に2件ある ＝ 1件使っても族は残る
    _stub(monkeypatch, "alpha-charlie", "bravo-charlie", "s-delta")
    _stub_ledger(monkeypatch, set())
    batch_build.pick(1, [])
    out = capsys.readouterr().out
    assert "7日ぶんの長尺の上限は動きません" in out


def test_ショート向けの題だけの回は_何も言わない(monkeypatch, capsys):
    _stub(monkeypatch, "s-alpha", "s-bravo")
    _stub_ledger(monkeypatch, set())
    batch_build.pick(2, [])
    out = capsys.readouterr().out
    assert "長尺の在庫" not in out


def test_長尺の回では値札を出さない(monkeypatch, capsys):
    """`--long` の回は、そもそも長尺として使っているので値札は要りません。"""
    _stub(monkeypatch, "charlie", "s-delta")
    _stub_ledger(monkeypatch, set())
    batch_build.pick(1, [], long_form=True)
    out = capsys.readouterr().out
    assert "長尺の在庫" not in out
