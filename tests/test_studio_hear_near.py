"""1モーラの誤読が `hear` の門を素通りすること、そしてそれが印字に出ること（2026-09-11 13:2x JST・hourly・Opus）。

出どころ: オーナー 2026-09-11 12:4x「**まだ読みがおかしいのがあるよ。ひらがなも漢字もあった。**
説明の解釈が誤解されないようにするようにして」（受け取り帳 `3f4ef885`）。
撃って分かった機構: `diff_spans(min_len=2)` が **1字だけの差を捨てている** ので、
09/10 の本の コマ9「**つま**（妻）」→ 3つの聞き取りが全部「すま」でも `diffs` は 0件 ＝ `OK` と出ていた。
規則と覆る条件は `studio/hear.near_spans` / `near_repeats` の註。

**陽性対照**（この回に撃って落としてある）:
  - `near_spans` の `< 2` を `< 1` にすると `test_1字の誤読は門を通る` の後半 2件 が落ちる
  - `near_repeats` の `len(ii) >= 2` を `>= 1` にすると `test_散った1字差は名指ししない` が落ちる
  - `_LOOSE` から `("へ", "え")` を外すと `test_助詞のへは畳む` が落ちる
"""
from studio.hear import diff_spans, isms_pairs, loose, near_repeats, near_spans


def test_1字の誤読は門を通る():
    """`diffs` は空・`near` が拾う。**この 2つが同時に成り立つのが、この回に見つけた穴**。"""
    exp, got = loose("つまのきそねんきん"), loose("すまのきそねんきん")
    assert diff_spans(exp, got) == []          # 門は通る（hear は OK と言う）
    assert near_spans(exp, got) == [("つ", "す")]

    exp2, got2 = loose("べつのきまりです"), loose("れつのきまりです")
    assert diff_spans(exp2, got2) == []
    assert near_spans(exp2, got2) == [("べ", "れ")]


def test_2字以上の差はnearに出ない():
    """門が拾う差は `near` に二重に出さない（印字が二重になる）。"""
    exp, got = loose("ぜいりつは"), loose("ぜいきんは")
    assert diff_spans(exp, got) == [("りつ", "きん")]   # 門が拾う
    assert near_spans(exp, got) == []


def test_同じならどちらも空():
    exp = loose("きまりでは、20年をこえると")
    assert diff_spans(exp, exp) == [] and near_spans(exp, exp) == []


def test_重なった1字差だけを名指しする():
    """同じ本で 2コマ以上に出た 1字差 ＝ TTS 側を先に疑う所（実測 09/10 の コマ7・9 の「妻」）。"""
    rows = [{"i": 7, "near": [("つ", "す")]},
            {"i": 9, "near": [("つ", "す")]},
            {"i": 10, "near": [("え", "べ")]}]
    assert near_repeats(rows) == [(("つ", "す"), [7, 9])]


def test_散った1字差は名指ししない():
    """whisper の癖はコマをまたいで散る ＝ 1コマ だけのものは名指ししない。"""
    rows = [{"i": 1, "near": [("ね", "め")]}, {"i": 4, "near": [("ね", "れ")]}, {"i": 6, "near": []}]
    assert near_repeats(rows) == []


def test_nearが無い行でも落ちない():
    assert near_repeats([{"i": 1}, {"i": 2, "near": []}]) == []


def test_既知のwhisperの癖は名指ししない():
    """`_WHISPER_ISMS` に載っている 1字の取り違えは、重なっても名指ししない。

    出どころ: この道具の 1回目の実行（09/12 の本）が `('ね','め')` 4か所・`('ね','れ')` 2か所 を
    名指しし、**2つとも めんきん／れんきん → ねんきん として既に記録ずみ**だった。
    **同じ語が何度も出れば、whisper の癖も重なります。**
    """
    assert frozenset(("ね", "め")) in isms_pairs()
    assert frozenset(("ね", "れ")) in isms_pairs()
    assert frozenset(("つ", "す")) not in isms_pairs()   # 09/10 の「妻」は載っていない ＝ 名指しは残る
    rows = [{"i": 2, "near": [("ね", "れ")]}, {"i": 4, "near": [("ね", "れ")]},
            {"i": 7, "near": [("つ", "す")]}, {"i": 9, "near": [("つ", "す")]}]
    assert near_repeats(rows) == [(("つ", "す"), [7, 9])]


def test_助詞のへは畳む():
    """「人へ」は え と読む ＝ **予定の側の誤り**。両側に当たる `loose` で畳む（実測 09/10・09/12 の コマ1）。"""
    assert loose("ひとへ") == loose("ひとえ")
    assert near_spans(loose("もらうひとへ"), loose("もらうひとえ")) == []
