"""**出せる在庫の行**の検査（2026-09-18 18:xx・optimizer・Opus・ultracode）。

**なぜこの検査が在るか**（この回に踏んだ実測）: `work/` に焼けた本が **6本** 座っているのに、
`status` はその 1本 も映していませんでした。日枠が 16:00 に戻った窓で 5本 出そうとしたら
**5本 とも `schedule` が止め**（指紋が古い ＝ build のあとに台本が動いた）、
**焼き直しが要ると分かったのは上げようとした瞬間**でした。

日枠は 1日 5本 で、**使わなかった分は 16:00 に消えます**（貯まりません）。
09/07〜09/18 の 12日 で天井 60本 に対し上げたのは 39本（初めての本 35本）＝ **58%**。
**この行が守るのは「出す側の段取り」です。**

守るのは 3つ:
  (1) 上げずみの本を在庫に数えないこと（**同じ本を 2度 上げる ＝ 1,650単位/本 の損**）
  (2) 指紋が古い本を「出せる」と言わないこと（`schedule` が必ず止める側）
  (3) 在庫が 0 のときは 1字も出さないこと（`status` の毎周 読む側を太らせない）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio import cli, common, script


def _script(vid: str, tmp: Path) -> None:
    """最小の台本を書く（`script.load` が読める形）。"""
    s = {
        "id": vid, "date": "2026-09-30", "title": "て", "takeaway": "て",
        "description": "て", "tags": ["て"], "voice": "ja-JP-Neural2-D", "rate": 1.08,
        "yomi": {}, "kana_in_voice": [], "image_prompt": "", "form": "short", "thumb": [],
        "segments": [{"say": "てすとです。", "show": "て", "sub": "", "tag": "", "board": []}],
        "notes": "",
    }
    (tmp / f"{vid}.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


@pytest.fixture()
def bench(tmp_path, monkeypatch):
    """`work/` と `data/studio/scripts/` を tmp に振り替えた台（**本物の台帳は触らない**）。"""
    work, scripts = tmp_path / "work", tmp_path / "scripts"
    work.mkdir(), scripts.mkdir()
    monkeypatch.setattr(common, "WORK", work)
    monkeypatch.setattr(script, "SCRIPTS", scripts, raising=False)
    monkeypatch.setattr(cli, "image_for", lambda vid, part="": None)
    return work, scripts


def _bake(work: Path, scripts: Path, vid: str, *, fresh: bool) -> None:
    """mp4 と build.sig を置く。`fresh=False` なら指紋を古くする。"""
    d = work / vid
    d.mkdir()
    (d / f"{vid}.mp4").write_bytes(b"0")
    _script(vid, scripts)
    sig = script.load(vid).build_sig(None)
    (d / "build.sig").write_text(sig if fresh else "1:000000000000", encoding="utf-8")


def test_在庫が0なら1字も出さない(bench) -> None:
    """`status` の毎周 読む側を、空の行で太らせないこと。"""
    assert cli.shippable_line([]) == ""


def test_上げずみの本は在庫に数えない(bench) -> None:
    """**同じ本を 2度 上げると 1,650単位/本 の損**（`reupload_cost` の註 ＝ 09/15 に 4本 踏んだ）。"""
    work, scripts = bench
    _bake(work, scripts, "sumi", fresh=True)
    rows = [{"event": "scheduled", "id": "sumi", "video_id": "xxx"}]
    assert cli.shippable_line(rows) == ""


def test_焼きたては出せる側に出る(bench) -> None:
    work, scripts = bench
    _bake(work, scripts, "nama", fresh=True)
    line = cli.shippable_line([])
    assert "出せる **1本**" in line and "焼き直しが要る 0本" in line
    assert "nama" in line


def test_指紋が古い本は出せる側に出さない(bench) -> None:
    """`schedule` が必ず止める側を「出せる」と数えると、窓の中で初めて気づきます。"""
    work, scripts = bench
    _bake(work, scripts, "furui", fresh=False)
    line = cli.shippable_line([])
    assert "出せる **0本**" in line and "焼き直しが要る 1本" in line
    assert "焼き直す     furui" in line


def test_mp4が無い作業場は数えない(bench) -> None:
    """台本と絵だけ置いて焼いていない本は、**出せる在庫ではありません**。"""
    work, scripts = bench
    (work / "kara").mkdir()
    _script("kara", scripts)
    assert cli.shippable_line([]) == ""


def test_輪が開いたままの本は出せるの側に出さない(bench) -> None:
    """**2026-09-18 23:2x に足した**（`cli.shippable_line` の【23:2x】の段）。

    **実物**: この周が `2026-09-20-nenkin-tedori-hayamihyou` に `critique` を撃ち、
    台帳に `done: false`・`n_real: 2` が入りました（[real] の 1件 は
    「所得税の基礎控除 104万円」と「43万円との差は 5万円」が同時に立っている
    ＝ 差は 61万円 で、どちらかが誤り）。**それでも同じ周の `status` は
    「出せる」と印字していました** —— `build_sig` は「焼きがいまの本文か」しか見ず、
    `trend.loop_open` は「指紋が古いか」しか見ないため、**どちらも答えを見ていません。**

    **止めません**（`schedule` に門は足していない ＝ 投稿が途切れるのが最大の損失）——
    **選ぶ側の目に入れるだけ**です。

    **覆る条件**: `done: false` の本を次の回がわざと出した回が 2度 出たら、この印を畳むこと。
    """
    work, scripts = bench
    _bake(work, scripts, "2026-09-30-a", fresh=True)
    _bake(work, scripts, "2026-09-30-b", fresh=True)
    rows = [
        {"event": "critique", "id": "2026-09-30-a", "done": False, "n_real": 2},
        {"event": "critique", "id": "2026-09-30-b", "done": True, "n_real": 0},
    ]
    out = cli.shippable_line(rows)
    assert "輪が開いている" in out and "2026-09-30-a" in out
    # 閉じた本は今までどおり「出せる」の側
    for ln in out.splitlines():
        if "2026-09-30-b" in ln:
            assert "出せる" in ln and "輪が開いている" not in ln
    # 本数の見出しは 2本 のまま（印は数え直しではない）
    assert "出せる **2本**" in out


def test_doneを書かない台帳では黙る(bench) -> None:
    """**覆る条件 (5)** ＝ `critique` の行が `done` を持たない周は、印を出さないこと
    （`unknown` と同じ扱い ＝ **嘘より安い**）。"""
    work, scripts = bench
    _bake(work, scripts, "2026-09-30-a", fresh=True)
    out = cli.shippable_line([{"event": "critique", "id": "2026-09-30-a", "n_real": 2}])
    assert "輪が開いている" not in out
    assert "出せる       2026-09-30-a" in out
