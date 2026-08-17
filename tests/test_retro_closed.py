"""持ち越しの数え方 —— **「潰した」と日誌が宣言した語を、数え続けないこと。**

## なぜ要るか（2026-08-16 に実測してから足しています）

`retro.py` の持ち越しは「2回以上の申し送りに出てくる語」で、**回数がそのまま
『まだ潰れていない証拠』として印刷されます。** ところが実物を測ると、上位が
**既に潰れたもので埋まっていました**（同日 09:3x の実測。直近8回の申し送り）:

    6回  usage                       → 07:2x に「9回運ばれた最後の1件を測って閉じた」
    5回  nenkin / ASSUMPTIONS        → 06:3x に「この回で閉じました」
    5回  sibling_check --phase spawn → 06:3x に「この回で閉じました」
    3回  status.py                   → 03:4x に「系（7回）はこの回で閉じました」

**日誌は毎回きちんと宣言していました**（実測7か所・書き方も揃っている）。
**読む側が無かっただけ**です —— `retro.py` そのものが「片方だけある」形で、
これは §2.7 が塞ぎに来た欠陥と**同じ種類**でした。

害は「多く出る」ことではありません。`retro.py` は最後に
**「この回で1件は潰すこと」**と言い、`trigger_main.md` §4 は
**「持ち越しが出ていたら、そこから選ぶのが既定」**と書いています。
**潰れたものを名指しすると、その回の選択そのものが空振りします。**

## 数え方（時系列で見ること。宣言の一括除外にしないこと）

`critique_queue` は 04:2x に閉じて、**そのあと別の理由で戻っています。**
だから落とすのは**宣言より前の言及だけ**で、後の言及は
**「一度閉じた後の再発」**として、むしろ強く出すこと。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("retro", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(spec)
sys.modules["retro"] = retro
spec.loader.exec_module(retro)


def test_宣言を拾う():
    doc = "**`nenkin`/`ASSUMPTIONS` の2語はこの回で閉じました**\n"
    found = retro.closures(doc)
    assert set(found) == {"nenkin", "ASSUMPTIONS"}


def test_宣言の無い行は拾わない():
    """**「閉じ」の字が無い行から拾うと、ただの言及で黙らせてしまいます。**"""
    assert retro.closures("`nenkin` の節を足した\n") == {}


def test_鉤括弧の宣言も拾う():
    doc = "「在庫が2週間を切ったら下限より生成を優先」はこの回で閉じました\n"
    assert "在庫が2週間を切ったら下限より生成を優先" in retro.closures(doc)


def test_同じ語が二度閉じられたら後のほうを採る():
    # 語は3字以上（`TOKEN_RE`）。1字だと拾われないので、そこで通る検査にしない
    doc = "`abc` を閉じました\n\n\n`abc` をまた閉じました\n"
    assert retro.closures(doc)["abc"] == 3


def test_宣言より前の言及は落ち_後の言及は残る():
    """**これが本体。** 行番号で見るので、同じ語でも前後で扱いが変わります。"""
    doc = "\n".join([
        "## 2026-08-16 01:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` の待ち",
        "",
        "## 2026-08-16 02:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` 系はこの回で閉じました",   # ← 宣言。ここまでが「前」
        "",
        "## 2026-08-16 03:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` がまた詰まった",           # ← 再発
        "",
        "## 2026-08-16 04:0x — 題",
        "### 次の回へ",
        "1. `critique_queue` がまだ詰まっている",
    ])
    closed = retro.closures(doc)
    blocks = retro.handoff_blocks(doc)
    kept = [d for d, body, start in blocks
            if "critique_queue" in retro.tokens(body)
            and not ("critique_queue" in closed and start <= closed["critique_queue"])]
    assert len(kept) == 2, kept
    assert all("03:0x" in d or "04:0x" in d for d in kept), kept


def test_実物の日誌で上位が入れ替わる():
    """**故障注入ではなく実データ。** 直近8回で、潰れた語が持ち越しから消えること。"""
    journal = (ROOT / "docs" / "JOURNAL.md").read_text(encoding="utf-8")
    closed = retro.closures(journal)
    blocks = retro.handoff_blocks(journal)[-8:]
    counted: dict[str, int] = {}
    for _date, body, start in blocks:
        for tok in retro.tokens(body):
            if tok in closed and start <= closed[tok]:
                continue
            counted[tok] = counted.get(tok, 0) + 1
    # 06:3x / 07:2x で閉じたと宣言された語は、もう持ち越しに立たない
    #
    # **`nenkin` をこの一覧から外しました**（2026-08-16 14:2x）。
    # 外した理由は「落ちたから」ではありません。**`nenkin` は本当に戻ってきた**
    # からです —— 11:0x が族べつ実績で名指しし、14:2x が実際に節を1つ足しました。
    # **宣言より後の言及が残るのは、この仕組みが意図してやっていること**です
    # （`critique_queue` と同じ「一度閉じた後の再発」）。
    #
    # ここで `nenkin` を残すと、**次の回から「日誌に `nenkin` と書けない」**
    # という縛りになります。検査を通すために日誌を曲げるのは本末転倒なので、
    # **戻ってこない語だけを残し、`nenkin` は下の「前の言及が黙るか」で見ます。**
    for tok in ("usage", "ASSUMPTIONS", "sibling_check --phase spawn"):
        assert counted.get(tok, 0) < 2, (tok, counted.get(tok))
    # 宣言そのものは日誌に在る（検査が「宣言が無いから通った」にならないように）
    for tok in ("usage", "nenkin", "ASSUMPTIONS", "sibling_check --phase spawn"):
        assert tok in closed, tok

    # **`nenkin` は、宣言より前の言及が黙っていることで見る。**
    # 前が9件あるので、ここが素通りしていたら必ず気づけます（空振りにならない）。
    before = [d for d, body, start in retro.handoff_blocks(journal)
              if "nenkin" in retro.tokens(body) and start <= closed["nenkin"]]
    assert len(before) >= 5, before
    # そのうち、直近8回に入っているものは1件も数えられていないこと
    silenced = [d for d, body, start in retro.handoff_blocks(journal)[-8:]
                if "nenkin" in retro.tokens(body) and start <= closed["nenkin"]]
    assert not silenced, silenced


def test_閉じていないことを言う行を宣言に数えない():
    """**入れた直後の実物で踏みました**（2026-08-16 09:5x）。

    「**一度閉じた後の再発**」は、**閉じていないことを言うための行**です。
    最初これを宣言として読み、`critique_queue` が丸ごと黙りました。
    **言葉の向きが逆なので、件数では絶対に気づけません**（黙るほうに出る）。
    """
    doc = "5. 持ち越し: `critique_queue` の待ち（**一度閉じた後の再発**・35本）\n"
    assert retro.closures(doc) == {}


def test_連体形は宣言に数えない():
    """「閉じた」は文中の言及に出ます。宣言は丁寧形だけ。"""
    assert retro.closures("`nenkin` を閉じた回の話をする\n") == {}
    assert "nenkin" in retro.closures("`nenkin` はこの回で閉じました\n")


def test_引用符の中の閉じましたは宣言に数えない():
    """**同じ穴の3枚目**（2026-08-16 10:xx。実物で踏みました）。

    09:5x の回が「偽の宣言を踏んだ」ことを日誌に書いた、**その説明文そのもの**が
    次の偽の宣言になりました。`REOPEN_RE` は効きません（`再発` が無い）。

        `closures()` を「`閉じました` か `閉じた`」で書いて回したら、`critique_queue` が

    バッククォートの中は **その語を名指ししている**ので、動詞として読まない。
    """
    doc = ("`closures()` を「`閉じました` か `閉じた`」で書いて回したら、"
           "**`critique_queue` が丸ごと黙りました。**\n")
    assert retro.closures(doc) == {}


def test_地の文の閉じましたは宣言のまま():
    """**片側だけ締めないこと。** 引用の外にある宣言は、今までどおり効く。"""
    got = retro.closures("**`_template.py`（7回）はこの回で閉じました**（実物で確認）。\n")
    assert "_template.py" in got


def test_引用の中に閉じましたがあっても地の文にあれば宣言():
    """1行に両方あるとき。**地の文が勝つ。**"""
    doc = "`closures()` の「`閉じました`」の判定を直し、`critique_queue` はこの回で閉じました\n"
    got = retro.closures(doc)
    assert "critique_queue" in got and "closures()" in got


def test_実物の日誌で最後の宣言が効く():
    """**実データ。** 日誌のいちばん新しい宣言が、それより前の言及を黙らせること。

    ## この検査は、何を測っていたか（2026-08-16 12:1x に**書き換えました**）

    ここは長く `test_実物の日誌で_critique_queue_は黙らない` で、
    **「`critique_queue` は 04:2x に閉じて、そのあと戻っているので再発として残る」**
    を実データで固定していました。**12:1x の回が `critique_queue` を実際に閉じた**
    ので、その言明はもう成り立ちません。

    **これは検査の敗北ではありません。** 「このバグはまだ開いている」を留める検査は、
    **閉じたら退役させるもの**です。回避（対象を別の語に差し替える、しきい値を緩める）は
    **検査そのものを嘘にします。**

    **落としたぶんの守りは残っています** ——
    「宣言より後の言及は残る」は `test_宣言より前の言及は落ち_後の言及は残る`
    （散文）と `tests/test_closes_record.py::test_宣言より後の言及は残る`（記録）が
    故障注入つきで持っています。**実データでしか言えないのは、
    「日誌にある宣言が、実際に読めているか」のほう**なので、そちらへ寄せました。

    ## **`assert not kept` を外しました**（2026-08-16 23:xx。**赤で始まって気づいた**）

    ここには最後に `assert not kept` があり、**「宣言より後に、その語を書いた
    申し送りが1件も無いこと」**を実データに要求していました。**設計の逆です。**

    `scripts/retro.py` は、宣言より後の言及を**わざと残します**
    （`main()` の `seen` 側。一覧では `← **一度閉じた後の再発**` と印が付く）。
    すぐ上の `test_宣言より前の言及は落ち_後の言及は残る` が、
    **同じ振る舞いを「残ること」として固定**しています。
    **同じリポジトリの2つの検査が、反対のことを言っていました。**

    そして壊れ方が悪い —— **コードを1行も触らなくても、日誌を書けば赤くなります。**
    実際 21:49 の回が `status.py` を `--closes` で閉じ、**同じ回が
    22:1x の申し送りで `status.py` に触れた**時点で赤くなり、
    その回は緑を見てから日誌を書いたので**気づかないまま push** されました
    （`origin/claude/youtube-auto-post-revenue-ggedij` は赤で届いています）。

    **毎回の回が赤い pytest から始まる**と、赤を読み飛ばす癖が付きます。
    残すのは、実データでしか言えないほう ——
    **「日誌にある宣言が実際に読めていて、それより前の言及を黙らせているか」**です。
    """
    journal = (ROOT / "docs" / "JOURNAL.md").read_text(encoding="utf-8")
    closed = retro.closures(journal)
    assert closed, "実物の日誌から宣言が1つも読めていません（読む側が壊れています）"
    # いちばん後ろで宣言された語を取り、**その宣言より前の言及が黙ること**を見る
    tok = max(closed, key=lambda t: closed[t])
    before = [d for d, body, start in retro.handoff_blocks(journal)
              if tok in retro.tokens(body) and start <= closed[tok]]
    assert before, f"{tok} は宣言だけで、黙らせる相手がいません"


def test_鉤括弧の中の閉じましたは宣言に数えない():
    """**同じ穴の4枚目**（2026-08-16。実データが赤で始まって気づきました）。

    3枚目（10:xx）はバッククォートだけを落としました。**鉤括弧は残っていました。**
    `TOKEN_RE` は**両方を同じ「引用」として**語を拾うのに、`prose_only` が
    落とすのは片方だけ —— **片方だけ直す形の8回目**です。

    前の回が push した故障注入の一覧に、この行があります ——

        - **散文の「閉じました」では畳み続けること**（`closes` にしか反応しない）

    これが宣言として読まれ、**`閉じました` という語そのものが「閉じた語」**として
    登録されていました。
    """
    doc = "- **散文の「閉じました」では畳み続けること**（`closes` にしか反応しない）\n"
    assert retro.closures(doc) == {}


def test_鉤括弧を落としても地の文の宣言は残る():
    """**片側だけ締めないこと。** 語が鉤括弧、動詞が地の文、という普通の形。"""
    got = retro.closures("「在庫が2週間を切ったら下限より生成を優先」はこの回で閉じました\n")
    assert "在庫が2週間を切ったら下限より生成を優先" in got


def test_実物の日誌に閉じましたという語の宣言が無い():
    """**実データ。** 動詞そのものが「閉じた語」として登録されていないこと。"""
    journal = (ROOT / "docs" / "JOURNAL.md").read_text(encoding="utf-8")
    closed = retro.closures(journal)
    assert "閉じました" not in closed
    assert "閉じた" not in closed
    assert closed, "宣言が1つも読めていません（締めすぎです）"


def test_節の名前は宣言として読まない():
    """**日誌そのものの節の名前は、持ち越しの語ではありません**（2026-08-17 12:5x）。

    「`「次の回へ」の5は**この回で閉じました。**`」という、ごく普通の書き方が
    `closures()` に「次の回へ を閉じた」と読ませていました。節の名前なので
    **黙らせる相手がどこにもなく**、そのぶん**本当の宣言が
    「最後の宣言」の座から押し出されます**（実際この検査が赤くなって見つかりました）。
    `noise_tokens()`（族名・種類・動画ID）と同じ形の5件目です。
    """
    text = ("「次の回へ」の5は**この回で閉じました。**\n"
            "`carry_over` は**この回で閉じました。**\n")
    got = retro.closures(text)
    assert "次の回へ" not in got
    assert "carry_over" in got


def test_SECTION_NAMES_は実物の見出しに当たる():
    """**語彙を手で並べたぶん、実物と繋いでおくこと。**

    引ける実物は `src/` ではなく**日誌の見出し**で、それを持っているのは
    `HANDOFF_RE` / `REVIEW_RE` です。見出しの言い方を変えた回は、ここが落ちます。
    """
    assert retro.HANDOFF_RE.match("### 次の回へ")
    assert retro.REVIEW_RE.match("### 設計の見直し（§6 (a2)）")
    assert retro.SECTION_NAMES == {"次の回へ", "設計の見直し"}
