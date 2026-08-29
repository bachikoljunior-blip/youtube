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
        # **実物と同じ形にしてあります** —— 見出しは長く、`calc_sections` は
        # その一部を指す（部分一致）。短い見出しで書くと、公開済みの側の
        # 長い `calc_sections` がどの見出しにも当たらず、
        # `_section_numbers` が空になって**この検査が通らなくなります**
        # （2026-08-30 に踏んだ）。
        "nenkin": (
            ("いちばん損の小さい開始は**69歳7か月**（65歳でも70歳でもない）",
             "14500800 9691200 22050000"),
            ("別の節", "33333333 44444444"),
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


def test_同じ形で同じ節を同じ言葉で指すテーマは落ちる(sections, capsys):
    cand = _topic("nenkin-minimax", "nenkin", ["いちばん損の小さい開始は"])
    done = _topic("nenkin-saidai", "nenkin",
                  ["いちばん損の小さい開始は**69歳7か月**（65歳でも70歳でもない）"])
    kept = bb._drop_doomed([cand], [cand, done], posted={"nenkin-saidai"})
    assert kept == []
    out = capsys.readouterr().out
    assert "nenkin-saidai" in out, "**落とした理由に相手の名前が要ります**"


def test_相手がショートなら落とさない(sections):
    # **これが narrowing の理由**（2026-08-30 に測った）。
    #     形の条件が無いと、未投稿 22件 のうち **11件**（半分）が落ち、
    #     **そのうち 9件の相手は `s-` のショート**でした。
    #     ショートは節から2〜4本しか棒を取らないので、同じ節でも図は割れます。
    cand = _topic("furusato-hokenryoritsu-jougen", "nenkin",
                  ["いちばん損の小さい開始は"])
    done = _topic("s-furusato-6", "nenkin", ["いちばん損の小さい開始は"])
    kept = bb._drop_doomed([cand], [cand, done], posted={"s-furusato-6"})
    assert [t["id"] for t in kept] == ["furusato-hokenryoritsu-jougen"]


def test_別の言葉で同じ節に当たっても落とさない(sections):
    # `calc_sections` は部分一致なので、**別の言葉で同じ節に当たる**ことがあります。
    # そこまで同じでなければ「同じ本を二度 書いている」とは言えません。
    cand = _topic("nenkin-a", "nenkin", ["いちばん損の小さい"])
    done = _topic("nenkin-b", "nenkin", ["65歳でも70歳でもない"])   # 同じ節・別の言葉
    assert bb._same_section_words(cand, done) is False
    kept = bb._drop_doomed([cand], [cand, done], posted={"nenkin-b"})
    assert [t["id"] for t in kept] == ["nenkin-a"]


def test_calc_sectionsが空なら落とさない(sections):
    cand = _topic("nenkin-a", "nenkin", [])
    done = _topic("nenkin-b", "nenkin", ["いちばん損の小さい開始は"])
    kept = bb._drop_doomed([cand], [cand, done], posted={"nenkin-b"})
    assert [t["id"] for t in kept] == ["nenkin-a"]


def test_公開済みでも別の節なら落とさない(sections):
    cand = _topic("nenkin-minimax", "nenkin", ["いちばん損の小さい開始は"])
    done = _topic("nenkin-betsu", "nenkin", ["別の節"])
    kept = bb._drop_doomed([cand], [cand, done], posted={"nenkin-betsu"})
    assert [t["id"] for t in kept] == ["nenkin-minimax"]


def test_ショートどうしなら形はそろっている(sections):
    a = _topic("s-nenkin-a", "nenkin", ["いちばん損の小さい開始は"])
    b = _topic("s-nenkin-b", "nenkin", ["いちばん損の小さい開始は"])
    assert bb._same_form(a, b) is True
    kept = bb._drop_doomed([a], [a, b], posted={"s-nenkin-b"})
    assert kept == []


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
