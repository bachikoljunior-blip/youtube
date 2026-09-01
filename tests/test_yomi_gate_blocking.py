"""読みの門が **何で止まり、何で止まらないか**（2026-09-02）。

オーナー固定その3・1つ目「ナレーションの漢字の読み方全部正しくして」の門は
`src/yomi_gate.py` にあり、`src/verify._check_yomi()` から呼ばれます。

**この検査が守っているのは「止めすぎない」ほう**です。実測（2026-09-02）:
疑い（R1 読みが割れる／R2 1文字に刻まれる）まで止める側に置くと、
**公開ずみ 31本 が 31本とも止まりました**。そのうち **68%（2,301/3,397）は
数詞の音便**（十 ジュッ/ジュー・百 ヒャク/ビャク/ピャク）で、**全部 正しい読み**です。

**投稿が途切れるのが最大の損失**（`CLAUDE.md`「動き方の帰結」4）。
だから止めるのは **R0（音から消えた字）と R3（正しい読みが分かっている誤読）だけ**で、
疑いは `to_measure()` が耳の待ち行列へ回します。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import yomi_gate as G  # noqa: E402


def _script(*lines: str) -> dict:
    return {"segments": [{"narration": ln} for ln in lines]}


def test_止める符号は2つだけ():
    """R1/R2 をここへ足すと、その日から**全部の本が止まります。**"""
    assert G.BLOCKING == ("R0", "R3")


def test_数詞の音便はR1に数えない():
    """十 ジュッ/ジュー・百 ヒャク/ビャク/ピャク は連濁と促音便で、**正しい割れ方**。

    ここを数えると指摘の 68% が数詞になり、本当の誤読が埋もれます。
    """
    risk = {"十": ["ジュッ", "ジュー"], "行": ["クダリ", "ギョー"]}
    if not G.available():
        return
    found = G.inspect("十万円の控除を、表の行で見ます。", risk, {})
    r1 = {h["surface"] for h in found if h["code"] == "R1"}
    assert "十" not in r1, f"数詞が R1 に入っています: {found}"


def test_割れただけでは止めない_正しい読みが入って初めて止まる():
    """**「割れた」と「誤読」は別**（2026-09-02 に両方向の実例を測った）。

        額  open-jtalk ガク（正）／ Google ひたい（誤）→ 置換で**直る**
        行  open-jtalk クダリ（誤）／ Google ぎょう（正）→ 置換で**壊れる**

    耳が言えるのは「割れたか」までなので、`correct` が入るまで止めません。
    """
    if not G.available():
        return
    text = "表の行を見ます。"
    split_only = {"行": {"verdict": "split", "dist": 0.9}}
    resolved = {"行": {"verdict": "split", "dist": 0.9, "correct": "ぎょう"}}
    codes_split = {h["code"] for h in G.inspect(text, {}, split_only) if h["surface"] == "行"}
    codes_done = {h["code"] for h in G.inspect(text, {}, resolved) if h["surface"] == "行"}
    assert "R3" not in codes_split, "正しい読みが決まっていないのに止めています"
    assert "R3" in codes_done, "正しい読みが入っても止まっていません"


def test_台帳が行を安全と言っているあいだは止めない():
    """`data/yomi_ledger.json` の実測（本番の Google TTS は ぎょう）が生きていること。

    **これが消えると、次に耳を回した回が「行」を誤読と判定し、
    公開ずみ 680箇所 を『くだり』へ置換しかねません。**
    """
    ledger = G.load_ledger()
    entry = ledger.get("行") or {}
    assert entry.get("verdict") == "safe", f"行 の判定が変わっています: {entry}"
    assert "ぎょう" in str(entry.get("heard", "")), entry


def test_長い段でも黙って切り捨てない():
    """open_jtalk は 1回に **326トークン** までしか返しません（2026-09-02 実測）。

    切って回さないと、**長い段の後半が無検査で通ります。**
    """
    if not G.available():
        return
    base = "所得税の控除額は48万円で、住民税の控除額は43万円です。"
    toks = G.analyze("　".join([base] * 30))
    assert len(toks) > G.MAX_TOKENS, f"{len(toks)} 件で頭打ちしています"


def test_公開ずみの本が門で止まらない():
    """**止めすぎていないこと。** 3本だけ通す（全部通すと 90秒 かかる）。"""
    import json

    if not G.available():
        return
    files = sorted((ROOT / "data" / "critique_queue").glob("*.json"))
    done = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("narration"):
            continue
        script = _script(*[str(x) for x in data["narration"][:6]])
        assert G.problems(script) == [], f"{path.name} が止まりました"
        done += 1
        if done >= 3:
            break
    assert done, "公開ずみの台本が1本も読めていません"
