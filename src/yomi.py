"""読み上げ専用の読み仮名層。**画面に出る文字は一切変えない。**

## なぜ要るか

2026-08-16、オーナーが動画を聞いて「額」が「ひたい」と読まれているのを見つけた。
6日間気づかなかったのは、**こちらの検査に音が1つも無かったから**。
映像・字幕・数字・引用は全部機械が見ているのに、音だけは誰も聞いていない。

本番のエンジンは Google Cloud TTS（`GOOGLE_TTS_API_KEY` が入っている）。
`scripts/probe_yomi.py` で実測したところ、**規則にならない**ことが分かった:

    実際の額は賃金日額で決まります。   → ひたい   （実際に公開済み）
    手元の額は住民税で前後します。     → ひたい   （実際に公開済み）
    税率が下がれば額も下がります。     → ひたい   （実際に公開済み）
    副業の所得は…経費を引いた額です。  → がく
    3000万円に1人600万円を足した額です。→ がく
    額は3万円です。                  → がく
    額が増えます。                    → ひたい
    額が減ります。                    → がく     ← 助詞でも決まらない

**同じ助詞でも割れるので、「この文脈だけ直す」は効かない。**
一方、漢字にはさまれた複合語（控除額・差額・総額・年額・月額・全額…）は
実測した範囲で全部「がく」だった。だから直すのは**裸の「額」だけ**にしてある。

## 直し方

TTS に渡す文字列の中でだけ仮名に置き換える。SSML の `<sub alias>` でも同じ音に
なることは確認済み（`probe_yomi.py` の測定で「がく」と一致）だが、採らなかった:

  - SSML にすると**全セグメントのリクエスト形式が変わる**。XML エスケープを1つ
    落とせば投稿が全部止まる。投稿が途切れるのが最大の損失なので、直し方の
    ほうを軽くする
  - 仮名置換なら **open-jtalk 側にもそのまま効く**（フォールバック経路も同時に直る）
  - 仮名置換の結果は **open-jtalk の形態素解析で機械的に検算できる**。
    API キーが無くても毎回走らせられる検査になる（`scripts/check_yomi.py`）

**覆る条件**: 置換後の読みで抑揚が不自然だと実測で分かったら、SSML `<sub>` に
移すこと（音は同じになることは確認済み）。

## 増やすとき —— **もう、ここに手で足す形ではありません**（2026-09-02）

オーナー原文（`CLAUDE.md` 固定その3・**一字も変えないこと**）:
「**ナレーションの漢字の読み方全部正しくして**」＝ **語を1つずつ直す形をやめろ。**

実測すると、この repo の読み上げは **694本・6,206行・漢字のかたまり 異なり 3,514語**。
`FIXES` は **1語**（0.03%）です。**残りは、この輪が自分で見つけます**:

    scripts/yomi_audit.py    公開ずみ全文 → 文脈で読みが割れる語（`data/yomi_risk.json`）
    src/yomi_gate.inspect()  台本の漢字を全部 名指し（`src/verify._check_yomi` が毎回 撃つ）
    scripts/yomi_ear.py      Google と open-jtalk の一致を測る（**候補は人が書かない**）
      〃      --direction    実測の読みを候補にして、**どちらが正しいか**まで決める
    data/yomi_ledger.json    その判定。`correct` が埋まった語は、下の `to_speech()` が
                             **自動で置換します** ＝ **`FIXES` に足す必要はありません**

**`FIXES` は種です。一覧ではありません。** ここに手で足すのは、
**上の輪が届かないと実測で分かった形**だけにすること（理由に、測った文を残すこと）。
"""
from __future__ import annotations

import re

_KANJI = r"一-鿿々"


class Fix:
    """1件の読み直し。

    `expect` と `cases` は飾りではなく検査の入力。`scripts/check_yomi.py` が
    `cases` を実際に形態素解析にかけ、`expect` が出ることを毎回確かめる。
    `untouched` は「直してはいけない形」で、複合語を巻き込んでいないかを見る。
    """

    def __init__(self, name: str, pattern: str, repl: str, reason: str,
                 expect: str, cases: list[str], untouched: list[str]):
        self.name = name
        self.regex = re.compile(pattern)
        self.repl = repl
        self.reason = reason
        self.expect = expect
        self.cases = cases
        self.untouched = untouched

    def apply(self, text: str) -> str:
        return self.regex.sub(self.repl, text)


FIXES: list[Fix] = [
    Fix(
        name="額",
        # 前後どちらも漢字でない「額」＝裸の額。控除額・額面・差額はここに入らない。
        pattern=rf"(?<![{_KANJI}])額(?![{_KANJI}])",
        repl="がく",
        reason=(
            "Google TTS が文脈次第で「ひたい」と読む。"
            "実測: 『実際の額は賃金日額で決まります。』『手元の額は住民税で前後します。』"
            "『税率が下がれば額も下がります。』がいずれも ひたい。"
            "複合語（控除額・差額・総額・年額・月額・全額・額面）は実測で全部 がく なので触らない。"
        ),
        expect="ガク",
        # 上の3つは実際に公開済みの動画から取った文。残りは実測で ひたい に落ちた文。
        cases=[
            "実際の額は賃金日額で決まります。前提は画面のとおりです。",
            "手元の額は住民税で前後します。",
            "税率が下がれば額も下がります。所得税は還付、住民税は翌年度。",
            "額が増えます。",
            "額に注目します。",
            "実際の額が増えます。",
            "手取り額に注目します。",
        ],
        untouched=["控除額", "差額", "総額", "年額", "月額", "全額", "額面", "支給額", "上限額"],
    ),
]

# 「直したはずの形」。to_speech を通したあとに残っていたら検査が落とす。
BROKEN_SHAPES: list[tuple[str, str]] = [
    (rf"(?<![{_KANJI}])額(?![{_KANJI}])", "裸の「額」（Google TTS が「ひたい」と読むことがある）"),
]


def to_speech(text: str) -> str:
    """TTS に渡す直前の文字列を作る。**字幕・画面・説明欄には絶対に使わない。**

    2つの層が順に当たる:

      1. `FIXES` …… 人が書いた置換。**ここに語を足していく形はもうやめる**
         （オーナー原文・`CLAUDE.md` 固定その3「漢字の読み方**全部**正しくして」）
      2. `data/yomi_ledger.json` …… **耳が実測で誤読と判定し、
         正しい読みまで確かめた語**。`scripts/yomi_ear.py` が積む。
         **語の一覧を人が書かずに増える**のはこちら側。

    **距離が離れているだけの語は、ここに入りません**（`yomi_gate.corrections()`）
    —— どちらのエンジンが正しいかは距離では決まらないので、
    `correct` の欄まで埋まった語だけが自動置換されます。
    """
    for fix in FIXES:
        text = fix.apply(text)
    try:
        from .yomi_gate import apply_corrections
        text = apply_corrections(text)      # **熟語の中の1字は巻き込みません**
    except Exception:                       # 台帳が読めなくても読み上げは止めない
        pass
    return text


def remaining_risks(text: str) -> list[str]:
    """to_speech を通してもなお誤読しうる形が残っていれば、その説明を返す。"""
    spoken = to_speech(text)
    return [why for pattern, why in BROKEN_SHAPES if re.search(pattern, spoken)]
