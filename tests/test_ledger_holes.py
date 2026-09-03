"""**「在るはずの列が空のまま」を、毎周 数える**（2026-09-04 に足した）。

`data/niche_ceiling.jsonl` の `top[].published` は **30本 中 30本 が空**で、
気づいてから **3周ぶん申し送りで運ばれ**ました。そのあいだずっと
`daily_pick` の「理論値の在りか」は **外の生涯の累計 ÷ 自分の 48時間** を出しています。

**誰も「何本 空か」を数えていませんでした。**
**空の列は、その列ぶんの損ではなく、それを読む画面ぜんぶの損です。**
"""
from __future__ import annotations

import json

from src import ledger_holes as lh


def _write(tmp_path, name: str, rows: list[dict]):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_入れ子の列を辿って数える(tmp_path) -> None:
    _write(tmp_path, "data/x.jsonl", [
        {"top": [{"published": ""}, {"published": "2026-01-01"}, {"published": ""}]}])
    got = lh.count("data/x.jsonl", ("top[].published",), root=tmp_path)
    assert got == [{"path": "top[].published", "n": 3, "empty": 2,
                    "pct": 200.0 / 3}]


def test_全部空なら書く道がないと言う(tmp_path) -> None:
    """**100% 空は「たまたま欠けた」ではありません** —— その列を書く道が無い、という意味。"""
    _write(tmp_path, "data/x.jsonl", [{"top": [{"published": ""}, {"published": ""}]}])
    out = "\n".join(lh.lines(root=tmp_path, watch={"data/x.jsonl": ("top[].published",)}))
    assert "2/2本 が空（**100%**）" in out
    assert "1件も入っていません" in out
    assert "それを読む画面ぜんぶの損" in out


def test_書き始めの1件では鳴らない(tmp_path) -> None:
    """**門は 20%。** 1件 空いただけで鳴らすと、まだ埋まっていない行で毎周 鳴ります。"""
    _write(tmp_path, "data/x.jsonl",
           [{"top": [{"published": "a"} for _ in range(9)] + [{"published": ""}]}])
    assert lh.lines(root=tmp_path, watch={"data/x.jsonl": ("top[].published",)}) == []


def test_埋まっていれば1行も出さない(tmp_path) -> None:
    """**出ない行は、読む側の手順を増やしません。**"""
    _write(tmp_path, "data/x.jsonl", [{"top": [{"published": "2026-01-01"}]}])
    assert lh.lines(root=tmp_path, watch={"data/x.jsonl": ("top[].published",)}) == []


def test_古い行は数えない(tmp_path) -> None:
    """書き方が変わる前の行で鳴っても、直す先がありません（既定は直近5行）。"""
    rows = [{"top": [{"published": ""}]} for _ in range(9)]
    rows.append({"top": [{"published": "2026-01-01"}]})
    _write(tmp_path, "data/x.jsonl", rows)
    got = lh.count("data/x.jsonl", ("top[].published",), root=tmp_path, rows_back=1)
    assert got[0]["empty"] == 0
    got = lh.count("data/x.jsonl", ("top[].published",), root=tmp_path, rows_back=10)
    assert got[0]["empty"] == 9


def test_帳面が無くても落ちない(tmp_path) -> None:
    assert lh.count("data/nope.jsonl", ("a",), root=tmp_path) == []
    assert lh.lines(root=tmp_path, watch={"data/nope.jsonl": ("a",)}) == []


def test_平たい列も数える(tmp_path) -> None:
    _write(tmp_path, "data/r.jsonl", [{"kind": "fix"}, {"kind": ""}, {}])
    got = lh.count("data/r.jsonl", ("kind",), root=tmp_path)
    assert got[0]["empty"] == 2 and got[0]["n"] == 3


def test_見張る列は在るはずの列だけ() -> None:
    """**在ってもなくてもよい欄を足さないこと**（毎周 鳴って読み飛ばされます）。

    この検査は「一覧が育ちすぎていないか」を見ます —— 帳面ごと 4列 まで。
    """
    for ledger, paths in lh.WATCH.items():
        assert ledger.startswith("data/") and ledger.endswith(".jsonl")
        assert 0 < len(paths) <= 4, ledger
