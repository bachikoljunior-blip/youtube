"""読みの門が **止めすぎていないこと**（2026-09-02）。

オーナー固定その3・1つ目「ナレーションの漢字の読み方全部正しくして」の門は
`src/yomi_gate.py` にあり、`src/verify._check_yomi()` から毎回 撃たれます。

**この検査が守っているのは「止めすぎない」ほうです。** 実測（2026-09-02）:
疑い（R1 読みが割れる／R2 1文字に刻まれる）まで落とす側に置くと、
**公開ずみ 31本 が 31本とも止まりました**（R1/R2 合計 3,397件）。そのうち
**68%（2,301件）は数詞の音便**（十 ジュッ/ジュー・百 ヒャク/ビャク/ピャク）で、
**全部 正しい読み**です。**投稿が途切れるのが最大の損失**
（`CLAUDE.md`「動き方の帰結」4）なので、落とすのは
**R0（音から消えた字）と R3（正しい読みまで確かめた誤読）だけ**。

**`tests/test_yomi_gate_all_words.py` は「全語を見ていること」を見ます。
こちらは「見た結果で止めすぎないこと」を見ます。** 片方だけでは足りません。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import verify, yomi_gate as G  # noqa: E402


def _script(*lines: str) -> dict:
    return {"segments": [{"narration": ln} for ln in lines]}


def test_数詞の音便はR1に数えない():
    """十 ジュッ/ジュー・百 ヒャク/ビャク/ピャク は連濁と促音便で、**正しい割れ方**。"""
    if not G.available():
        return
    risk = {"十": ["ジュッ", "ジュー"], "百": ["ヒャク", "ビャク", "ピャク"]}
    found = G.inspect("十万円と、二百万円を並べます。", risk, {})
    named = {h["surface"] for h in found if h["code"] == "R1"}
    assert not (named & {"十", "百"}), f"数詞が R1 に入っています: {found}"


def test_台帳が行を安全と言っているあいだは止めない():
    """**「割れた」と「誤読」は別**（2026-09-02 に両方向の実例を測った）。

        額  open-jtalk ガク（正）／ Google ひたい（誤）→ 仮名置換で**直る**
        行  open-jtalk クダリ（誤）／ Google ぎょう（正）→ 仮名置換で**壊れる**

    公開ずみ 694本 に裸の「行」は **680箇所**、どれも表の行（＝ぎょう）。
    **この記録が消えると、次に耳を回した回が「行」を誤読と判定し、
    その 680箇所 を『くだり』へ置換しかねません。**
    """
    entry = G.load_ledger().get("行") or {}
    assert entry.get("verdict") == "safe", f"行 の判定が変わっています: {entry}"
    assert "ぎょう" in str(entry.get("heard", "")), entry


def test_向きの分からない語で自動置換しない():
    """`corrections()` が返すのは、**`correct` の欄まで埋まった語だけ**。

    距離が離れているだけでは、どちらのエンジンが正しいかは言えません。
    """
    for word, kana in G.corrections().items():
        assert kana, word
    ledger = G.load_ledger()
    unresolved = [w for w, e in ledger.items()
                  if e.get("verdict") == "misread" and not e.get("correct")]
    assert all(w not in G.corrections() for w in unresolved)


def test_長い段でも黙って切り捨てない():
    """open_jtalk は 1回に **326トークン** までしか返しません（2026-09-02 実測）。

    切って回さないと、**長い段の後半が無検査で通ります** ——
    しかもトレースを丸ごと decode すると、300文字 を超える入力は
    `UnicodeDecodeError` で落ちていました（音響パラメータが UTF-8 でない）。
    """
    if not G.available():
        return
    base = "所得税の控除額は48万円で、住民税の控除額は43万円です。"
    toks = G.analyze("　".join([base] * 30))
    assert len(toks) > G.MAX_TOKENS, f"{len(toks)} 件で頭打ちしています"


def test_公開ずみの本が門で止まらない():
    """**止めすぎていないこと。** 3本だけ通す（全部だと 90秒 かかる）。"""
    if not G.available():
        return
    files = sorted((ROOT / "data" / "critique_queue").glob("*.json"))
    done = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("narration"):
            continue
        script = _script(*[str(x) for x in data["narration"][:6]])
        assert verify._check_yomi(script) == [], f"{path.name} が止まりました"
        done += 1
        if done >= 3:
            break
    assert done, "公開ずみの台本が1本も読めていません"
