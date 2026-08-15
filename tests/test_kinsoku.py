"""行頭禁則・行末禁則。**画面の折り返し全部に効きます。**

`src/visuals.py` の `_wrap` は `subtitles._chunk` に委ねているので、
この1つの関数が**字幕・見出し・箇条書き・注記・ラベル**の全部を折っています。

## なぜ足したか（2026-08-15）

実物で `給与収入のみ` ／ `・扶養なし` と折れました（注記の前置き）。
**中黒が行頭に来ると、前の項目の続きではなく新しい項目に見えます。**
`_chunk` の行頭処理は `、。！？` の**4字しか見ていませんでした。**

これは 8/15 に4回続いた「**人が見れば一目で分かる欠陥を、機械検査が
素通りさせた**」と同じ種類です。だから直しと一緒に検査を置きます。

## この検査が見ているもの

1. **行頭に来てはいけない字で始まる行が無いこと**（2行目以降）
2. **行末にぶら下がった開き括弧が無いこと**（ただし次の行が溢れる場合は許す）
3. **字が1つも落ちていないこと**（折るだけで、削ってはいけない）

3 を入れてあるのは、禁則は「字を隣の行へ移す」処理なので、
**移す先を間違えると黙って消える**からです（`line[1:]` の取り違え1つで起きます）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.subtitles import NO_LINE_END, NO_LINE_START, _chunk  # noqa: E402

# (文, 1行の字数)。**縦は13字・横は22字**だが、
# 折れ方を出すために狭い幅も混ぜている（狭いほうが禁則を踏みやすい）。
CASES = [
    # ---- 実物で踏んだもの ----
    ("給与収入のみ・扶養なし", 6),
    ("給与収入のみ・扶養なし", 8),
    ("給与収入のみ・扶養なし", 13),
    # ---- 中黒が複数 ----
    ("東京都在住・40歳未満・賞与なし", 9),
    ("東京都在住・40歳未満・賞与なし", 13),
    # ---- 括弧（行頭に閉じ・行末に開きが来やすい） ----
    ("年収500万円（額面）の場合", 8),
    ("課税所得は195万円以下（税率5パーセント）", 10),
    ("勤続20年（退職所得控除は800万円）で計算します。", 13),
    ("「1年あたり」は5年ごとの差ではありません。", 11),
    # ---- 句読点（もともと見ていた4字。**壊していないこと**を確かめる） ----
    ("75歳開始なら1.84倍で、年331万2千円。", 13),
    ("総所得金額等が200万円未満なら足切りは5パーセントです。", 13),
    # ---- 長音・小書きのかな ----
    ("扶養控除はコース別ではありません", 7),
    ("ふるさと納税の上限はシミュレーションで変わります", 9),
    # ---- 記号 ----
    ("所得税率は23パーセント、住民税は10パーセントです。", 13),
]


def _problems(text: str, limit: int) -> list[str]:
    lines = _chunk(text, limit)
    out: list[str] = []

    for line in lines[1:]:
        if line and line[0] in NO_LINE_START:
            out.append(f"行頭に {line[0]!r} が来た: {lines!r}")

    for i, line in enumerate(lines[:-1]):
        # **1字だけの行は動かせません**（動かすと行が消える）。そこは許す。
        if len(line) > 1 and line[-1] in NO_LINE_END:
            # 次の行が溢れるなら、ぶら下げたままが正しい（溢れるほうが悪い）。
            if len(lines[i + 1]) + 1 <= limit:
                out.append(f"行末に {line[-1]!r} がぶら下がった: {lines!r}")

    if "".join(lines).replace(" ", "") != text.replace(" ", ""):
        out.append(f"字が変わった: {lines!r}（元: {text!r}）")

    return out


def test_no_forbidden_line_start():
    """2行目以降が、行頭禁則の字で始まっていないこと。"""
    failures = []
    for text, limit in CASES:
        lines = _chunk(text, limit)
        for line in lines[1:]:
            if line and line[0] in NO_LINE_START:
                failures.append(f"{text!r} (limit={limit}) 行頭 {line[0]!r}: {lines!r}")
    assert not failures, "\n".join(failures)


def test_no_forbidden_line_end():
    """開き括弧が行末にぶら下がっていないこと（次の行が溢れない範囲で）。"""
    failures = []
    for text, limit in CASES:
        lines = _chunk(text, limit)
        for i, line in enumerate(lines[:-1]):
            if len(line) > 1 and line[-1] in NO_LINE_END and len(lines[i + 1]) + 1 <= limit:
                failures.append(f"{text!r} (limit={limit}) 行末 {line[-1]!r}: {lines!r}")
    assert not failures, "\n".join(failures)


def test_nothing_is_dropped():
    """禁則は字を隣へ移すだけ。**1字も落ちてはいけない。**"""
    failures = []
    for text, limit in CASES:
        lines = _chunk(text, limit)
        joined = "".join(lines).replace(" ", "")
        if joined != text.replace(" ", ""):
            failures.append(f"{text!r} (limit={limit}) → {joined!r}: {lines!r}")
    assert not failures, "\n".join(failures)


def test_line_start_set_excludes_opening_brackets():
    """**開き括弧を行頭禁則に入れないこと。**

    入れると「（」が前の行の末尾へ吸われ、**行末禁則と真っ向からぶつかります**
    （片方が後ろへ送り、もう片方が前へ戻すので、直し合いになる）。
    実際に起きなくても、次に触る側がここで迷うので検査で釘を刺しておく。
    """
    overlap = set(NO_LINE_START) & set(NO_LINE_END)
    assert not overlap, f"行頭禁則と行末禁則が重なっています: {sorted(overlap)}"
    for ch in "（「『【〔":
        assert ch not in NO_LINE_START, f"{ch!r} は行末禁則であって行頭禁則ではありません"


def test_real_defect_is_fixed():
    """**8/15 に実物で出た1件を、そのまま固定する。**

    ここが緑でも `test_no_forbidden_line_start` が緑とは限らない（逆も同じ）。
    実物1件を名指しで残すのは、**一般の規則を緩めたときに気づくため**です。
    """
    assert _chunk("給与収入のみ・扶養なし", 8) == ["給与収入のみ・", "扶養なし"]


if __name__ == "__main__":
    bad = 0
    for text, limit in CASES:
        problems = _problems(text, limit)
        bad += len(problems)
        print(f"{'NG' if problems else 'ok'} {limit:>3} {_chunk(text, limit)}")
        for p in problems:
            print(f"      {p}")
    print(f"\n{len(CASES)}件中 {bad}件の問題")
    raise SystemExit(1 if bad else 0)
