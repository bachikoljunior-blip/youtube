"""`_drop_doomed` は、**公開済みの本と図の棒がまるごと重なるテーマ**を落とすか。

`script_writer.used_bars()` は公開済みの棒を読み、重なると**台本の時点で**
`RuntimeError` を投げます。つまり `dupes` の門と同じ「作る前に分かる死」です。
それでも `_bars_clash` は長らく**この回に選んだ2本どうし**にしか当たっておらず、
`nenkin-minimax-69sai7kagetsu` が **4回 続けて**同じ理由で落ちて、
そのつど長尺の生成 13〜19分 を捨てていました（`docs/JOURNAL.md` 2026-08-30）。

**故障注入を両向きに掛けます。** 落とすことと、**落としてはいけないものを
落とさないこと**は別の性質です（`docs/JOURNAL.md` 2026-08-16）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "batch_build_for_test", ROOT / "scripts" / "batch_build.py")
assert _spec and _spec.loader
bb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bb)


@pytest.fixture()
def sections(monkeypatch):
    """`src.calc.*` を走らせずに、節の見出しと本文を作り物で差し替える。"""
    table = {
        "nenkin": (
            ("いちばん損の小さい開始は", "1450万800円 969万1200円 2205万円"),
            ("別の節", "3333万3333円 4444万4444円"),
        ),
        "kokuho": (
            ("保険料の上限", "1050000円 2020000円"),
        ),
    }

    def fake(calc: str):
        return table[calc]

    monkeypatch.setattr(bb, "_calc_sections_cached", fake)
    return table


def _topic(tid: str, calc: str, words: list[str]) -> dict:
    return {"id": tid, "calc": calc, "calc_sections": words, "title_seed": ""}


def test_公開済みと同じ節を指すテーマは落ちる(sections, capsys):
    cand = _topic("nenkin-minimax", "nenkin", ["いちばん損の小さい開始は"])
    done = _topic("nenkin-saidai", "nenkin", ["いちばん損の小さい開始は"])
    kept = bb._drop_doomed([cand], [cand, done], posted={"nenkin-saidai"})
    assert kept == []
    out = capsys.readouterr().out
    assert "nenkin-saidai" in out, "**落とした理由に相手の名前が要ります**"


def test_公開済みでも別の節なら落とさない(sections):
    cand = _topic("nenkin-minimax", "nenkin", ["いちばん損の小さい開始は"])
    done = _topic("nenkin-betsu", "nenkin", ["別の節"])
    kept = bb._drop_doomed([cand], [cand, done], posted={"nenkin-betsu"})
    assert [t["id"] for t in kept] == ["nenkin-minimax"]


def test_calcが違えば落とさない(sections):
    cand = _topic("nenkin-minimax", "nenkin", ["いちばん損の小さい開始は"])
    done = _topic("kokuho-jougen", "kokuho", ["保険料の上限"])
    kept = bb._drop_doomed([cand], [cand, done], posted={"kokuho-jougen"})
    assert [t["id"] for t in kept] == ["nenkin-minimax"]


def test_postedを渡さない回は今までどおり(sections):
    # **既定は `None`**。突き合わせる相手が無いだけで、門が緩むわけではありません。
    cand = _topic("nenkin-minimax", "nenkin", ["いちばん損の小さい開始は"])
    done = _topic("nenkin-saidai", "nenkin", ["いちばん損の小さい開始は"])
    kept = bb._drop_doomed([cand], [cand, done])
    assert [t["id"] for t in kept] == ["nenkin-minimax"]


def test_未投稿どうしは落とさない(sections):
    # ここが担当するのは**公開済みとの**突き合わせだけ。
    # 同じ回に選んだ2本どうしは `pick()` の `chosen` の輪が受けます。
    a = _topic("nenkin-a", "nenkin", ["いちばん損の小さい開始は"])
    b = _topic("nenkin-b", "nenkin", ["いちばん損の小さい開始は"])
    kept = bb._drop_doomed([a, b], [a, b], posted=set())
    assert [t["id"] for t in kept] == ["nenkin-a", "nenkin-b"]
