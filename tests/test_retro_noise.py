"""持ち越しの一覧から「物の名前」を外す（2026-08-17 に足した）。

## 何を守っているか

`docs/trigger_main.md` §2.7 は **「持ち越しが出ていたら、そこから選ぶのが既定」**
と言っています。つまりこの一覧は**次の回の仕事を決めます。**

ところが並びは**素の出現数**で、申し送りは毎回「どの族に節を書いたか」
「何を出したか（upload / fix）」「どの動画を評価したか」を書きます。
実測（2026-08-17）: **17件のうち8件**が族名・種類・動画IDでした。
`status.py` が3回踏んだ「**一覧が当たりを含まないまま育つ**」の4件目です。

## 語彙を手で並べないこと

停止語の一覧を書くと、**calc を足した回が必ず書き忘れます**（この作りで通算8回）。
だから3つとも実物から引きます。この検査は**その「実物から引く」ほうを見ています** ——
新しい calc を足したら、何も書かなくても外れること。
"""
from __future__ import annotations

import json

from scripts import retro


def test_族名は_srcのcalcから引いている():
    noise = retro.noise_tokens()
    assert "nenkin" in noise["族名"]
    assert "shitsugyo" in noise["族名"]
    # `_template.py` / `_checks.py` は族ではない
    assert not any(t.startswith("_") for t in noise["族名"])


def test_新しいcalcを足したら_何も書かなくても外れる(tmp_path, monkeypatch):
    """**ここがこの直しの本体**です。手で並べた語彙なら、ここが落ちます。"""
    root = tmp_path
    (root / "src" / "calc").mkdir(parents=True)
    (root / "data" / "critique_queue").mkdir(parents=True)
    (root / "src" / "calc" / "atarashii.py").write_text("", encoding="utf-8")
    (root / "src" / "calc" / "_template.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(retro, "ROOT", root)
    noise = retro.noise_tokens()
    assert "atarashii" in noise["族名"]
    assert "_template" not in noise["族名"]


def test_動画IDは待ち行列と上げた記録の両方から引く(tmp_path, monkeypatch):
    """**待ち行列だけでは足りません**（上げた直後は `.plan.json` がまだ無い）。

    2026-08-17 の実物で `x2agstHS8m0` が1件だけ外れずに残り、そこで気づきました。
    """
    root = tmp_path
    (root / "src" / "calc").mkdir(parents=True)
    q = root / "data" / "critique_queue"
    q.mkdir(parents=True)
    (q / "AAAAAAAAAAA.plan.json").write_text("[]", encoding="utf-8")
    (root / "data" / "uploaded.jsonl").write_text(
        json.dumps({"video_id": "BBBBBBBBBBB"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(retro, "ROOT", root)
    vids = retro.noise_tokens()["動画ID"]
    assert vids == {"AAAAAAAAAAA", "BBBBBBBBBBB"}


def test_11字の道具名を動画IDと読み違えない():
    """`batch_build` も `topic_forge` も**ちょうど11字**です。

    最初はここを `[A-Za-z0-9_-]{11}` の形で書いて、2つとも巻き込みました。
    **形で判定しないこと**を、この検査で固定します。
    """
    vids = retro.noise_tokens()["動画ID"]
    assert "batch_build" not in vids
    assert "topic_forge" not in vids


def test_種類は手順の語だけ():
    """**正本と同じ集合であること。** ここに語を書き写さないこと。

    **2026-08-31 に、書き写していたせいで赤くなりました。** ここは
    `{"upload", "means", "verdict", "fix"}` を直に持っており、
    オーナーの規則3 で **`improve` が5語目に足された**とき、
    `scripts/retro.py` と `scripts/run_marker.py` は追随したのに
    **この検査だけが4語のまま**でした。

    **同じ数を2か所に置かない**（`retro.py` の `JST` の註が
    「この repo の『片方だけ』は通算10件です」と書いている、その11件目）。
    **正本は `run_marker.SHIP_KINDS`** です。
    """
    from scripts import run_marker as rm
    want = set(rm.SHIP_KINDS)
    assert retro.noise_tokens()["種類"] == want, (
        "`retro.SHIP_KINDS` が `run_marker.SHIP_KINDS` とずれています "
        f"（retro={retro.SHIP_KINDS} / run_marker={want}）")
    assert "improve" in want, (
        "`improve` が種類にありません。**オーナーの規則3**"
        "（次の枠で出る1本を良くする）を出した回が、`drift.py` から見えなくなります")


def test_問題の名前は外れない():
    """道具名・ファイル名は**問題の名前になりうる**ので外さないこと。

    `status.py` は実際に持ち越しでした（「名指しに従っていない」）。
    ここまで落とすと、一覧が空になって何も言わなくなります。
    """
    noise = retro.noise_tokens()
    for keep in ("status.py", "premise.py", "src/dupes.py", "score", "pick(8)"):
        assert not any(keep in words for words in noise.values()), keep
