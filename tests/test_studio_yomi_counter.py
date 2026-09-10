"""1字の漢字の `yomi` が、予定の側で助数詞や複合語を割らないこと（2026-09-11 01:3x JST・optimizer・Opus）。

出どころ: 09/12 の本の 1回目の hear で コマ11 が外れ、**予定 いちひ ／ 音 いちにち**（TTS が正しい）。
`yomi` の `日 → ひ` が 助数詞「1日」にも当たっていた ＝ 測る側の欠陥。
規則と覆る条件は `studio/hear._apply_one_kanji_yomi` の註。

**陽性対照**（この回に撃って落としてある）: `after_num` を外すと 2件・
語で当てるのをやめて素の `replace` に戻すと 4件 落ちます。
**3つ目の枝（`名詞,接尾,助数詞` を別に見る）は書いてから消しました** ——
外しても 7件 とも通り、対照が落ちなかった（理由は `_apply_one_kanji_yomi` の註）。
"""
import json
import re
from pathlib import Path

from studio.hear import expected_kana

REPO = Path(__file__).resolve().parents[1]
ONE_KANJI = re.compile(r"[一-龥々]")


def test_助数詞は1字のyomiに割られない():
    # 助数詞の枝。外すと いちひ・さんひと・いちぶん になる
    assert expected_kana("1日でも", {"日": "ひ"}) == "いちにちでも"
    assert expected_kana("3人が", {"人": "ひと"}) == "さんにんが"
    assert expected_kana("1分で", {"分": "ぶん"}) == "いちふんで"


def test_数の直後の1字は当てない():
    # after_num の枝。外すと じゅうつきぶん になる（正しくは じゅうがつぶん）
    assert expected_kana("10月分の", {"月": "がつ"}) == "じゅうがつぶんの"
    assert expected_kana("10月分の", {"月": "つき"}) == "じゅうがつぶんの"


def test_1語の中に埋まった字は当てない():
    # 語で当てる枝。外すと はつひ・はんねん・ろくかがつ になる
    assert expected_kana("初日に", {"日": "ひ"}) == "しょにちに"
    assert expected_kana("半年で", {"年": "ねん"}) == "はんとしで"
    assert expected_kana("6か月で", {"月": "がつ"}) == "ろくかげつで"
    assert expected_kana("毎年12万円", {"年": "ねん"}) == "まいとしじゅうにまんえん"


def test_裸の1字には今までどおり当たる():
    """**この検査が、直しを「yomi を殺しただけ」から分けます。**"""
    assert expected_kana("その日から", {"日": "ひ"}) == "そのひから"
    assert expected_kana("税金の話です", {"話": "はなし"}) == "ぜいきんのはなしです"   # 実測: 09/12 の本のコマ1


def test_長い鍵が先に当たる():
    """複合語は長い鍵が取るので、1字の鍵は触れない（実測: 09/11 の本の `月収`）。"""
    y = {"月収": "げっしゅう", "月": "がつ"}
    assert expected_kana("月収30万円", y) == "げっしゅうさんじゅうまんえん"
    assert expected_kana("月収30万円", {"月": "がつ"}) == "げっしゅうさんじゅうまんえん"


def test_仮名の鍵はこれまでどおり素で当たる():
    """1字でも漢字でない鍵（ひらがな・カタカナ）は、語を見ずに当てる（形を変えていない）。"""
    assert expected_kana("ドルで", {"ドル": "どる"}) == "どるで"


def test_実物の台本の予定は1コマも動かない():
    """**実物から列挙して確かめる**（§5 の教訓の形4つ目）。

    台本の `yomi` を 2通りに当てて比べるのではなく、**いまの口が実物で何を返すか**を凍結する。
    ここが落ちたら、直しがどこかの本の予定を動かしたということ ＝ その本を名指しして見ること。
    """
    seen = ones = 0
    for p in sorted((REPO / "data" / "studio" / "scripts").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        y = s.get("yomi") or {}
        ones += sum(1 for k in y if len(k) == 1 and ONE_KANJI.fullmatch(k))
        for seg in s.get("segments") or []:
            k = expected_kana(seg.get("say") or "", y)
            assert k and re.fullmatch(r"[ぁ-ゖー]*", k), (p.name, seg.get("say"), k)
            seen += 1
    assert seen >= 60, f"台本のコマが減っています: {seen}"
    assert ones >= 20, f"1字漢字の yomi 鍵が減っています: {ones}（この検査が空を回している）"
