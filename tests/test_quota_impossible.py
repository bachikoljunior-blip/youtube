"""**リセット時刻が観測時刻より前の点を積まないこと**（2026-08-18 に足した）。

枠は「まだ来ていないリセット」までの残りを言うので、`resets_at < seen_at` は
**時間の向きとして起こりえません。** 起きるのは写し違いだけです。

`sessions_compact.py` は `HH:MM:SS` だけの行を**その日**として読み、
日をまたいだ行にだけ `MM-DD/` を付けろと言っています。**付け忘れると
前日の25件が丸ごと今日として積まれます** —— 実測で 09:1x の回が24件、08-16 の回が14件。
**どちらも静かに通り**、`--pace`（1周いくら・持続できる間隔）の分母を汚しました。
**この計器が決めているのは、次の子を立てる間隔そのものです。**
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import quota  # noqa: E402


def test_リセットが観測より前なら捨てる():
    assert quota._is_impossible(
        {"seen_at": "2026-08-18T08:08:55+00:00", "resets_at": "2026-08-17T10:10:00+00:00"})


def test_普通の点は通す():
    assert not quota._is_impossible(
        {"seen_at": "2026-08-17T08:08:55+00:00", "resets_at": "2026-08-17T10:10:00+00:00"})


def test_欠けている欄では判定しない():
    """**空欄を「壊れている」と読まないこと。** `resets_at` は全部の行には入りません。"""
    assert not quota._is_impossible({"seen_at": "2026-08-17T08:08:55+00:00"})
    assert not quota._is_impossible({"resets_at": "2026-08-17T10:10:00+00:00"})
    assert not quota._is_impossible({})


def test_実際に踏んだ形をそのまま():
    """08-17 の行に `MM-DD/` を付け忘れると、こう出ます。"""
    bad = {"seen_at": "2026-08-18T14:09:37+00:00", "born_at": "2026-08-18T14:02:13+00:00",
           "window": "five_hour", "resets_at": "2026-08-17T15:10:00+00:00"}
    assert quota._is_impossible(bad)
