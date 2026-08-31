#!/usr/bin/env python3
"""1周の頭で、**前の回の申し送りを受け取る**。

**これは「設計の見直し」ではありません。** 見直し本体は
`docs/trigger_main.md` §6 (a2)（終わりぎわ）です。オーナーの2件目が
「**実行の最初ではなく**」と訂正しており、そちらに従っています。

これは **(a2) の渡し先を開ける道具**です。(a2) は自分でこう書いています ——
「ここで気づいた設計変更は、この回では実行できません。次の子に渡るところまでが1件」。
渡し先は日誌の「次の回へ」で、**それを読む手順がどこにもありませんでした。**

`docs/trigger_main.md` に `JOURNAL.md` は4回出てきますが、
**4回とも「書け」で、「読め」が1回もありません。**
`CLAUDE.md` には「末尾10件を読む」とありますが、**実際の手順書のほうに無い。**
**受け取る側が無ければ、(a2) は空に書き込むだけになります。**

その結果が、8/15 の題名です ——
「計器が3つ壊れていた」「独立評価が実績と永久に突き合わない」
「棒グラフの目盛りが2種類壊れていた」「画面に主語が出ていない」。
**毎回ちがう穴を見つけていますが、種類は全部同じ**（＝人が見れば一目で分かる欠陥を、
機械検査が素通りさせている）。**前の回を読んでいれば、次の穴を探しに行けたはずです。**

`grep -n "^### 次の回" docs/JOURNAL.md` は **20件**返ります。
**20回ぶんが、読まれないまま積まれていました。**

## 出すもの

1. 直近の `ship`（`data/runs.jsonl`）を種類別に。**偏っていたら、それが設計の癖**
2. 直近 N 回の「**次の回へ**」を全文
3. **2回以上の申し送りに出てくる語** ＝ 持ち越し。潰れていない証拠
   （**潰したと宣言された語は落とします。** 宣言の正本は
   `run_marker.py --ship --closes` が構造で残したほう ＝ `data/runs.jsonl`。
   散文からの読み取りも残してありますが、**あれは3回誤読しています**。
   詳しくは `recorded_closures()`）
4. **§6 (a2) の問い1を、縦に**（2026-08-15 に足した）
5. **前に「道筋」を見てから何回か。** 8回で1度、(a2) の問い4を出す

## 4 と 5 を足した理由（2026-08-15）

オーナーから「終わりに設計を見直す、は全部見てる？」と訊かれ、**答えは「いいえ」**でした
（(a2) の問い3つは主語が全部「この回」）。**そのとき一緒に見つかったのが 4 です。**

**(a2) の答えが、書かれたきり読み返されていませんでした。** ただし全部ではありません ——
実測すると、**問い3は6件中4件が「次の回へ」に昇格**しており（3件は「（上の見直し3）」と明記）、
**問い2は答えが「手順を直す」なのでその回のうちに `trigger_main.md` が書き換わります。**

**届いていなかったのは問い1だけ**でした。そして**問い1は、1回ぶんでは何も言いません。**
6件を縦に並べると「**作る段が4回・対象のせいが5回**」で、
**8/15 19:0x の並列化（CPU 2〜4%）は、この形に気づいた回**です。
**気づいたのは偶然で、並べる道具はありませんでした。** それが 4 です。

    python scripts/retro.py            # 直近8回
    python scripts/retro.py --n 12
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# **直に呼ばれると `sys.path` の頭は `scripts/` になります**（2026-08-16 に
# `batch_build` が6本まるごと ModuleNotFound で落ちた形）。根を先に通すこと。
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import alerts, upload_cap  # noqa: E402  （`sys.path` を通した後でないと読めません）

JOURNAL = ROOT / "docs" / "JOURNAL.md"
RUNS = ROOT / "data" / "runs.jsonl"

HANDOFF_RE = re.compile(r"^#{2,4}\s*次の回")
DATE_RE = re.compile(r"^##\s+(.*)$")
# §6 (a2) の節。見出しは 2026-08-15 に固定したが、**それ以前の3種類も拾う**
# （「この回の設計の見直し（§6 (a2)）」「この回の見直し（§6 a2）」「設計の見直し（§6 (a2)）」）。
# 過去のぶんが読めないと、縦に並べる意味がありません。
REVIEW_RE = re.compile(r"^#{2,4}\s*(?:この回の)?(?:設計の)?見直し（§6")
# **太字の始まる位置で落とさないこと**（2026-08-18。前の回の申し送り9）。
# 日誌の項目は `1. **いちばん…` と `**1. いちばん…` の2通りで書かれていて、
# ここは長らく後者を**項目として認識していませんでした** ——
# `retro.py` は前の回を「問い1に答えていない回」と数え、
# 節の切り出し（`_items`）でも**その項目を前の項目の続きとして飲み込みます。**
# 中身ではなく、`**` が番号の前に来たか後に来たかだけの違いです。
# §2.7 の「一覧が当たりを含まないまま育つ」と同じ形（**今度は取りこぼす向き**）。
ITEM_RE = re.compile(r"^\s*\*{0,2}([1-9])\.\s+(.*)$")
# 問い4に答えた回の印。次はここから数える（§6 (a2)「発火のさせ方」）。
ROUTE_MARK = "[道筋]"
ROUTE_EVERY = 8
# 申し送りの中で「同じものを指している」と機械で言える語だけを拾う。
# 散文の名詞を拾うと何もかも一致するので、**識別子と鉤括弧に限る。**
TOKEN_RE = re.compile(r"`([^`\n]{3,40})`|「([^」\n]{3,30})」")
# **日誌そのものの節の名前は、持ち越しの語ではありません**（2026-08-17 12:5x）。
# 「`「次の回へ」の5は**この回で閉じました。**`」と書くと、`closures()` が
# **「次の回へ」を閉じた語として読みます。** 節の名前なので、黙らせる相手が
# どこにもなく、そのぶん**本当の宣言が「最後の宣言」の座から押し出されます。**
# `noise_tokens()`（族名・種類・動画ID）と同じ形の、**5件目**です。
#
# **ここは手で並べています**（`noise_tokens()` の「手で並べるな」の例外）。
# 引ける実物は `src/` ではなく **この文書の見出し**で、それを持っているのは
# すぐ上の `HANDOFF_RE` / `REVIEW_RE` です。だから語彙ではなく、
# **`### <名前>` が本当にその正規表現に当たること**を検査で縛っています
# （`tests/test_retro_closed.py`）。見出しを変えた回は、そちらが落ちます。
SECTION_NAMES = {"次の回へ", "設計の見直し"}
# **潰した宣言**。日誌は「〜はこの回で閉じました」と、毎回この形で書いています
# （実測7件・2026-08-16）。**書く側はあったのに、読む側がありませんでした**（下）。
#
# **「閉じた」まで拾わないこと**（2026-08-16 09:5x に、入れた直後の実物で踏みました）。
# 「**一度閉じた後の再発**」という、**閉じていないことを言うための行**が
# 宣言として読まれ、`critique_queue` が丸ごと黙りました。**言葉の向きが逆です。**
# 丁寧形（「閉じました」）だけが宣言で、連体形は文中の言及に出ます。
CLOSED_RE = re.compile(r"閉じました")
# 宣言の形をしていても、**閉じていないことを言っている行**は数えない。
REOPEN_RE = re.compile(r"再発|閉じていない|閉じたつもり|閉じられていない")
# **引用符の中の「閉じました」は、宣言ではなく“その文字列の名前”です**
# （2026-08-16 10:xx。**同じ穴の3枚目**を実物で踏みました）。
#
# 09:5x の回が、自分の踏んだ穴をこう書き残しました ——
#
#     `closures()` を「`閉じました` か `閉じた`」で書いて回したら、`critique_queue` が
#
# **この行そのものが宣言として読まれ、`critique_queue` がまた丸ごと黙りました。**
# 09:5x が足した `REOPEN_RE` は効きません（この行に `再発` が無い）。
# **偽の宣言を説明する文が、次の偽の宣言になっています。**
#
# 直すのは語彙の足し算ではなく、**どこを読むか**のほう。バッククォートの中は
# 「その語を名指ししている」ので、**動詞として読まない。**
# 語（`TOKEN_RE`）は逆に中からしか拾わないので、両者は同じ行を別々に見ます。
#
# **同じ穴の4枚目（2026-08-16）。今度は鉤括弧のほうでした。**
# 前の回が push した日誌の故障注入の一覧に、この行があります ——
#
#     - **散文の「閉じました」では畳み続けること**（`closes` にしか反応しない）
#
# `TOKEN_RE` は **バッククォートと鉤括弧を同じ「引用」として**語を拾います
# （`` `x` `` も 「x」 も語）。ところが `prose_only` が落としていたのは
# **バッククォートだけ**でした。**片方だけ直した形**で、このリポジトリが
# 通算8回踏んでいるものです。結果、鉤括弧の中の `閉じました` が動詞として読まれ、
# **`閉じました` という語そのものが「閉じた語」として登録**されました
# （`tests/test_retro_closed.py` が実データで落ちて気づいた）。
#
# **引用の形が2つあるなら、2つとも落とすこと。** 語を拾う側と、
# 動詞を読む側は、**同じ範囲を裏返しに見ていなければ噛み合いません。**
#
# **同じ穴の5枚目（2026-08-17）。今度は「引用の入れ子」でした。**
# **リポジトリが赤い pytest で届いています**（前の回が押した日誌のこの行）——
#
#     上の追記で「`「次の回へ」の5は**この回で閉じました。**`」と書いたら、
#
# **前の回が、自分の踏んだ偽の宣言を説明した文が、また偽の宣言になっています**
# （09:5x とまったく同じ形の再来。あのときはバッククォート、今度は入れ子）。
#
# 理由は**優先順位**です。`QUOTE_RE` は左から順に当てるので、
# 外側の `「` の位置で鉤括弧の側が先に当たり、**内側の `」` で閉じてしまいます** ——
# `「\`「次の回へ」` までを落とし、**残った `の5は…閉じました。` が地の文になる。**
# 語のほうも同じ理由で ``「`「次の回へ」`` を拾い、**`` `「次の回へ `` という
# 存在しない語が「最後に閉じられた語」の座を奪います**（黙らせる相手がいないので、
# 本当の宣言が押し出される。`SECTION_NAMES` では防げません ——
# 語が `「` を含んでいて、節の名前と字が違うからです）。
#
# **直すのは語彙でも例外表でもなく、順序のほう。**
# **バッククォートを先に確定させてから、残りに鉤括弧を当てます**
# （markdown のコードスパンのほうが強い区切りなので、これが本来の読み）。
# `prose_only` と `tokens` が**同じ範囲**を使うのは前と同じで、
# 範囲を作るところを1か所（`quote_spans`）にまとめました ——
# **片方だけ直す形を、このリポジトリは通算8回踏んでいます。**
_BACKTICK_RE = re.compile(r"`([^`\n]*)`")
_BRACKET_RE = re.compile(r"「([^」\n]*)」")
QUOTE_RE = re.compile(r"`[^`\n]*`|「[^」\n]*」")
CODE_SPAN_RE = QUOTE_RE          # 旧名。呼んでいる側があるので残す


def quote_spans(line: str) -> list[tuple[int, int, str, str]]:
    """引用の範囲を `(始まり, 終わり, 中身, 種類)` で返す。**重なりは無し。**

    **バッククォートを先に取ります。** 入れ子（`「\\`x\\`」`）のとき、
    位置の早い順に当てると外側の `「` が内側の `」` で閉じ、
    **引用の残りが地の文に漏れます**（上の註）。
    """
    spans: list[tuple[int, int, str, str]] = []
    taken = bytearray(len(line))
    for m in _BACKTICK_RE.finditer(line):
        spans.append((m.start(), m.end(), m.group(1), "`"))
        taken[m.start():m.end()] = b"\x01" * (m.end() - m.start())
    for m in _BRACKET_RE.finditer(line):
        if any(taken[m.start():m.end()]):
            continue                      # コードスパンに食われている
        spans.append((m.start(), m.end(), m.group(1), "「"))
    return sorted(spans)


def ambiguous_quotes(line: str) -> bool:
    """**引用の対応が取れていない行**か（2026-08-17。**同じ穴の6枚目**）。

    5枚目を直した直後、**この回の日誌がまた赤くしました。** 書いたのはこの行です ——

        落ちるのは `「\\`「次の回へ」` までで、**残った `の5は…閉じました。` が…

    バックスラッシュで逃がしたバッククォートが**数を狂わせ**、対を組み替えます。
    結果 `の5は…閉じました。` が地の文へ漏れ、**`までで、**残った` という
    存在しない語**が「最後に閉じられた語」になりました。

    **5回とも、直し方は「その形をもう1つ知る」でした。** 6回目にして、
    形を数えるのをやめます —— **markdown の inline code は対でなければ成立しません。**
    奇数個なら、**どこが引用でどこが地の文かを、こちらは決められない。**
    決められない行から宣言を読むのが、この穴の再発そのものです。

    **黙って落とすのは宣言だけ**（`closures()`）。語のほうは落としません ——
    持ち越しは2回以上で初めて出るので、偽の語は自然に沈みます。
    宣言は**1回で効く**ので、曖昧な行を読ませないほうが安全です。
    """
    return line.count("`") % 2 == 1


def prose_only(line: str) -> str:
    """**引用（バッククォート・鉤括弧）を落とし、地の文だけ**を返す。

    落とす範囲は `tokens` が語を拾う範囲と**同じ**です。裏返しに見ています ——
    引用の中は「その語を名指ししている」ので**動詞として読まない**、
    引用の外は語ではないので**語として拾わない**。
    """
    out, at = [], 0
    for start, end, _, _ in quote_spans(line):
        out.append(line[at:start])
        out.append("　")
        at = end
    out.append(line[at:])
    return "".join(out)


# **語は「名前」です。式ではありません**（2026-08-19。**同じ穴の5枚目**）。
#
# 04:4x の回が、日誌にこう書きました ——
#
#     **そのうえで窓を閉じました**（`WINDOW = ("", "")`）。
#
# 地の文に「閉じました」があり、バッククォートの中に `WINDOW = ("", "")` があるので、
# **`closures()` はそれを「閉じられた語」として登録します。** そして
# `test_実物の日誌で最後の宣言が効く` が
# **「その語は宣言だけで、黙らせる相手がいません」**で赤くなりました
# （その語は、この世のどの申し送りにも出てきません）。
#
# **1〜4枚目と同じ形です** —— 偽の宣言を説明する文が、次の偽の宣言になる。
# ただし直す先が違います。1〜4枚目は「**どこを読むか**」（引用の外／中）でしたが、
# ここは**拾った中身の形**の話です。`=` と引用符は**名前には現れません。**
# 実物の日誌19語で測りました（2026-08-19）——
# 落ちるのは `WINDOW = ("", "")` の**1件だけ**で、`check_tables()` も
# `--closes` も `data/runs.jsonl` も `sibling_check --phase spawn` も残ります。
#
# **語彙の足し算にしないこと。** ここに「見なかったことにする語」を並べ始めたら、
# それは `src/alerts.py` が数えている「一覧が当たりを含まないまま育つ」の側です。
NOT_A_NAME_RE = re.compile(r"""[=＝"'\\]""")


def quoted_tokens(line: str) -> list[str]:
    """1行から**語**を拾う。`prose_only` と同じ範囲を、中身の側から見る。

    長さの下限・上限は種類ごとに違います（識別子のほうが長い）。
    **式は落とします**（`NOT_A_NAME_RE`。上のコメント）。
    """
    out = []
    for _, _, body, kind in quote_spans(line):
        body = body.strip()
        lo, hi = (3, 40) if kind == "`" else (3, 30)
        if lo <= len(body) <= hi and not NOT_A_NAME_RE.search(body):
            out.append(body)
    return out


def blocks_under(text: str,
                 head_re: re.Pattern[str]) -> list[tuple[str, list[str], int]]:
    """`head_re` に当たる見出しの中身を、直前の `## 日付` と**行番号**と一緒に返す。

    行番号を返すのは、**「潰したと宣言された後の言及か」を時系列で見るため**です
    （`carry_over()`）。日付だけだと、同じ回の中で「閉じました」と書いた行そのものが
    持ち越しの1回として数えられます。
    """
    lines = text.split("\n")
    blocks: list[tuple[str, list[str], int]] = []
    for i, line in enumerate(lines):
        if not head_re.match(line):
            continue
        date = ""
        for j in range(i, -1, -1):
            m = DATE_RE.match(lines[j])
            if m:
                date = m.group(1)
                break
        body: list[str] = []
        for k in range(i + 1, len(lines)):
            if re.match(r"^#{1,4}\s", lines[k]):
                break
            body.append(lines[k])
        while body and not body[-1].strip():
            body.pop()
        blocks.append((date, body, i))
    return blocks


def handoff_blocks(text: str) -> list[tuple[str, list[str], int]]:
    return blocks_under(text, HANDOFF_RE)


def closures(text: str) -> dict[str, int]:
    """**「この語はこの回で閉じました」を、日誌から拾う。**

    返すのは `語 → 宣言された行番号`（同じ語が何度も閉じられていたら**最後の1回**）。
    行番号で持つのは、**閉じた後にまた出てきたら、それは本当の再発**だからです
    （`critique_queue` は 04:2x に閉じて、そのあと別の理由で戻っています）。
    """
    found: dict[str, int] = {}
    for i, line in enumerate(text.split("\n")):
        # **引用の対応が取れない行からは、宣言を読まない**（`ambiguous_quotes`）。
        if ambiguous_quotes(line):
            continue
        # **宣言かどうかは地の文で見る。語は元の行から拾う**（`prose_only`）。
        bare = prose_only(line)
        if not CLOSED_RE.search(bare) or REOPEN_RE.search(bare):
            continue
        for tok in quoted_tokens(line):
            if tok not in SECTION_NAMES:
                found[tok] = i
    return found


def recorded_closures() -> dict[str, int]:
    """**`data/runs.jsonl` に構造で残された宣言。**（2026-08-16 に足した）

    返りの形は `closures()` と同じ `語 → 日誌の行番号`。
    こちらの行番号は `run_marker.py --ship --closes` が
    **宣言した時点の日誌の行数**を書いたものです（あちらの `journal_lines()`）。

    ## なぜ散文と別にするか

    上の `CLOSED_RE` / `REOPEN_RE` / `CODE_SPAN_RE` の3段は、**全部あとから足した
    継ぎ足し**です。**同じ穴を3回踏んでいます**（09:5x・10:3x と、`_template.py` の
    書き忘れ）。**踏み方が「書きすぎ」と「書き忘れ」で逆なのに、原因は1つ** ——
    **宣言が人の散文の中にしかなく、機械が文意を当てにいっていた**ことです。

    語彙を足す限り、日誌が新しい言い回しをすれば戻ります（3回戻りました）。
    **だから読む場所を増やしました。** 構造の側には解釈が要りません。

    **散文の側は消していません。** 過去の日誌はそれでしか読めず、
    消すと 8/16 以前の宣言が全部よみがえります。**これから先の正本は構造の側**で、
    同じ語が両方にあるときは**後に宣言されたほう**を採ります。
    """
    found: dict[str, int] = {}
    if not RUNS.exists():
        return found
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("kind") != "ship":
            continue
        at = rec.get("journal_lines")
        if not isinstance(at, int):
            continue
        for tok in rec.get("closes") or []:
            tok = str(tok).strip()
            if tok:
                found[tok] = max(found.get(tok, 0), at)
    return found


def all_closures(text: str) -> tuple[dict[str, int], set[str]]:
    """散文と記録を合わせた宣言と、**そのうち記録から来た語**。

    どちらから来たかを返すのは、**出す側で分けて見せるため**です
    （記録は裏が取れる／散文は取れない。混ぜて出すと同じ強さに見えます）。
    """
    merged = dict(closures(text))
    rec = recorded_closures()
    for tok, at in rec.items():
        merged[tok] = max(merged.get(tok, 0), at)
    return merged, set(rec)


def first_lines(body: list[str], want: str) -> str:
    """(a2) の節から、番号 `want` の項目の**1行目だけ**を返す。

    全文を出すと「次の回へ」と二重になって重くなります。**縦に並べたいのは
    「どこが重かったか」の一言だけ**なので、1行目で足ります。
    """
    for line in body:
        m = ITEM_RE.match(line)
        if m and m.group(1) == want:
            return m.group(2).strip()
    return ""


# **`improve` は 2026-08-31 に足しました**（オーナーの規則3。
# 正本は `run_marker.SHIP_KINDS`）。
SHIP_KINDS = {"upload", "improve", "means", "verdict", "fix"}


def noise_tokens() -> dict[str, set[str]]:
    """**問題の名前ではなく、物の名前**である語を、リポジトリ自身から集める。

    ## なぜ要るか（2026-08-17。**「一覧が当たりを含まないまま育つ」の4件目**）

    持ち越しは「2回以上の申し送りに出てくる語」を**素の出現数**で並べています。
    ところが申し送りは毎回「どの族に節を書いたか」「何を出したか（upload/fix）」
    「どの動画を評価したか」を書くので、**上位がその語で埋まります。** 実測（この回）:

        17件のうち 8件 が 族名（iryohi・nenkin・shitsugyo）・
        種類（upload・means・fix）・動画ID（Y3JUjFLrORY・x2agstHS8m0）

    そして `docs/trigger_main.md` §2.7 は **「持ち越しが出ていたら、そこから選ぶのが既定」**
    と言っています。**上位が物の名前で埋まった一覧は、次の回の選択を積極的に誤らせます。**
    `status.py` の同じ形（`src/alerts.py` の説明）と揃えて、ここでも塞ぎます。

    ## 手で並べた語彙にしないこと

    停止語を書き並べると、**calc を足した回が必ず書き忘れます**（この作りで通算8回）。
    だから3つとも**実物から引きます** —— 族名は `src/calc/*.py`、
    動画IDは `data/critique_queue/` の実ファイル名、種類は §4 の4語。
    **`[A-Za-z0-9_-]{11}` のような形での判定はしないこと**（この回に一度書いて、
    `batch_build` と `topic_forge` がちょうど11字で巻き込まれました）。
    """
    calcs = {p.stem for p in (ROOT / "src" / "calc").glob("*.py")
             if not p.stem.startswith("_")}
    vids = {p.name.split(".")[0]
            for p in (ROOT / "data" / "critique_queue").glob("*.plan.json")}
    # **待ち行列だけでは足りません**（2026-08-17 に実物で踏んだ）。
    # `x2agstHS8m0` は上げた直後で `.plan.json` がまだ無く、外れずに残りました。
    # **上げた本の正本は `data/uploaded.jsonl`** なので、そちらも読みます。
    up = ROOT / "data" / "uploaded.jsonl"
    if up.exists():
        for line in up.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                vid = json.loads(line).get("video_id")
            except json.JSONDecodeError:
                continue
            if vid:
                vids.add(str(vid))
    return {"族名": calcs, "種類": set(SHIP_KINDS), "動画ID": vids}


JST = timezone(timedelta(hours=9))
# **窓の頭はここに持ちません**（2026-08-17 22:4x に外した）。
# `QUOTA_BACK_HOUR = 16` と固定で持っていましたが、枠の頭は**太平洋時間の0時**なので
# **冬は JST 17:00** です。正本は `src.upload_cap`（`PT` を tz 名で持っている）。
# **同じ数を2か所に置かないこと** —— この repo の「片方だけ」は通算10件です。
# 申し送りの本文が「この項目は日枠が戻らないと動かせない」と言っている印。
# **手で語彙を並べていません** —— 日誌の実物から引いた4つの形だけです
# （`noise_tokens()` の教訓と同じ。ただしこちらは語ではなく**文の印**なので、
# `src/` から引ける実物がありません。増えたらここに足すこと）。
# **`16:00 JST 以降` の形も読むこと**（2026-08-27 に足した）。ここは長らく
# `JST 16:00` と `16:00 以降` の2つしか見ておらず、**申し送りが実際に使う
# 「【08/27 16:00 JST 以降の回へ】」に当たっていませんでした**（順が逆）。
# 実害が出ていなかったのは、その項目がたいてい「日枠」か「403」も
# 一緒に書いていたからで、**規則が効いていたのではありません。**
QUOTA_MARK_RE = re.compile(
    r"JST\s*16:00|16:00\s*JST|16:00\s*(?:以降|より前)|日枠|403")

#: 「【14:00 JST 以降の回へ】」の形。**時計で塞がっている申し送り**を拾う。
#: `QUOTA_MARK_RE` は日枠（16:00）しか見ていないので、
#: **それ以外の時刻で塞がっているものは、いままで上位に残っていました**
#: （2026-08-27 12:3x の回が踏んだ —— 持ち越しの上位4件が全部
#: 「【14:00 JST 以降の回へ】」で、12:3x に始まった回では1件も打てなかった）。
CLOCK_MARK_RE = re.compile(r"(\d{1,2}):(\d{2})\s*JST\s*以降")


def items_of(body: list[str]) -> list[list[str]]:
    """申し送りの本文を、番号つきの項目ごとに切る。

    **節ぜんぶを1つの文字列として見ないこと。** 申し送りは1回に5〜6件あり、
    そのうち1件だけが日枠がらみ、ということが普通に起きます。
    節で見ると、その1件の「JST 16:00」が**同じ回の他の5件を全部巻き込みます。**
    """
    items: list[list[str]] = []
    cur: list[str] = []
    for line in body:
        if ITEM_RE.match(line):
            if cur:
                items.append(cur)
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        items.append(cur)
    return items


def quota_blocked(blocks: list[tuple[str, list[str], int]], tok: str) -> bool:
    """その語を言っている項目が、**1つ残らず**日枠がらみか。

    ## なぜ要るか（2026-08-17。**「一覧が当たりを含まないまま育つ」の5件目**）

    `docs/trigger_main.md` §2.7 は **「持ち越しが出ていたら、そこから選ぶのが既定」**
    と言っています。ところが日枠は **JST 03:00〜16:00 の13時間ずっと切れていて**、
    そのあいだの回は `videos.update` も `thumbnails.set` も **403 で必ず落ちます。**
    この回（09:1x）の実測:

        4回  videos.update                  項目 4/4 が日枠がらみ
        4回  --closes missing_thumbnail     項目 4/4 が日枠がらみ
        3回  scripts/refresh_thumbnail.py   項目 3/3 が日枠がらみ
        3回  topic_forge                    項目 0/3
        3回  status.py                      項目 1/3

    **上位3件が全部、その回には物理的に潰せないものでした。** 1日13時間ぶんの回が、
    既定の選び先として**必ず不可能な3件**を読まされていたことになります。
    （だから `missing_thumbnail` の当たり率は 5回鳴って1回、`carry_over` は 10回で7回。
    **鳴っている一覧のほうが、時刻によって当たらなくなる**という形です。）

    ## 「全部」で見る理由（多数決にしないこと）

    上の実測は **4/4・4/4・3/3 対 0/3・1/3** で、真ん中がありません。
    **しきい値を置く必要がない分かれ方**なので、置いていません。
    比率で切ると、次に 2/3 の語が出たときに**その語の潰せる側の項目まで沈みます。**
    項目が1つしかない語（`tot == 1`）も沈めません —— 1件では癖と言えないからです。

    ## 消さないこと

    沈めるだけで、**一覧からは落としません**（件数も理由も印字します）。
    16:00 以降の回では逆に **「いまなら潰せます」** と印を付けて上に残します。
    落とすと、16:00 以降の回が「もう無い」と読んで永久に潰れなくなります。
    """
    total = 0
    marked = 0
    for _date, body, _start in blocks:
        for item in items_of(body):
            if tok not in tokens(item):
                continue
            total += 1
            text = "\n".join(item)
            if QUOTA_MARK_RE.search(text) or names_data_api_tool(text):
                marked += 1
    return total >= 2 and marked == total


def names_data_api_tool(text: str) -> bool:
    """その項目は、**日枠を使う道具を名指ししている**か（2026-08-27 に足した）。

    ## なぜ regex だけでは足りないか（**この回の実測**）

    `QUOTA_MARK_RE` が拾うのは**散文のほう**です —— 「日枠」「403」「16:00 JST」。
    ところが申し送りは、**塞がっていることに気づかないまま**書かれます。
    実測（この回の `retro.py` の持ち越し・20:44 JST）:

        2回  python scripts/snapshot.py     ← **沈んでいませんでした**
             08-27 14:2x「**22:00 JST を過ぎていたら、まず撃つこと**」
             08-27 16:0x「**【今日 22:00 JST 以降】** …… 1回 撃ってから」

    `snapshot.py` は `videos.list` ＝ **Data API** で、この窓の 403 は 88回、
    戻るのは **08/28 16:00 JST**。**22:00 に撃っても 403 です。**
    それでも 14:2x の項目は「日枠」とも「403」とも書いていないので
    `quota_blocked()` に拾われず、`clock_blocked()` は
    「22:00 JST **以降**」という言い回しでないと当たらないので
    **2件のうち1件しか当たらず、沈みませんでした**（`len(waits) == total` が門）。

    **散文の言い回しを追いかけると、次の書き方でまた抜けます。**
    この repo が何度も踏んでいる「註と実装のずれ」で、
    **註（＝申し送りの文）のほうを直しても、次の回が別の言い方をします。**

    ## 何を見るか —— **道具の名前。これは事実です**

    一覧は `src/upload_cap.DATA_API_TOOLS`（日枠という事実の持ち主）。
    **ここに写しを置かないこと。**

    ## 覆る条件

    - `videos.insert` のように**日枠が尽きても通る**道具を一覧に入れたら、
      打てる手まで沈みます（`DATA_API_TOOLS` の註に、入れてよい条件があります）
    - 沈めた語の当たり率（`--closes` の付き方）が、沈めなかった語より
      **低い**なら、見ているものが違います
    """
    try:
        from src import upload_cap
        tools = upload_cap.DATA_API_TOOLS
    except Exception:                                          # noqa: BLE001
        return False
    return any(t in text for t in tools)


def clock_blocked(blocks: list[tuple[str, list[str], int]], tok: str,
                  now: datetime | None = None) -> float | None:
    """その語を言っている項目が、**1つ残らず**「HH:MM JST 以降の回へ」で、
    **その時刻がまだ来ていない**か。来ていなければ、あと何時間かを返す。

    ## なぜ要るか（2026-08-27 12:3x に踏んだ。**`quota_blocked` の穴**）

    `quota_blocked()` は **日枠（16:00）だけ**を見ています。ところが
    申し送りは他の時刻でも塞がります —— この日の持ち越しの**上位4件**は
    全部これでした:

        4回  09:00 より前も生きるか / PROVEN_FROM_MIN / 生きた本数 / day_cap
             → どれも「**【08/27 14:00 JST 以降の回へ】** その時刻に判定できます」

    **12:3x に始まった回からは、1件も打てません。** それでも
    `quota_blocked()` は 16:00 しか知らないので、4件とも一覧の**いちばん上**に
    並びました。`docs/trigger_main.md` §2.7 は「持ち越しから選ぶのが既定」と
    言っているので、**既定に従うと、その回は何も選べない**ことになります。

    ## 同じ扱いにする理由

    塞いでいるのが単位か時計かは、**選ぶ側には関係ありません** ——
    「この回では打てない」という一点だけが効きます。だから
    `quota_blocked()` と同じく**沈めるだけで、消しません。**
    時刻が来た回では逆に上へ戻ります（`None` が返るので）。

    ## 「全部」で見るのと、1件では沈めないのは `quota_blocked()` と同じ
    """
    now = now or datetime.now(timezone.utc)
    jst = now.astimezone(JST)
    total, waits = 0, []
    for _date, body, _start in blocks:
        for item in items_of(body):
            if tok not in tokens(item):
                continue
            total += 1
            m = CLOCK_MARK_RE.search("\n".join(item))
            if not m:
                continue
            hh, mm = int(m.group(1)), int(m.group(2))
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                continue
            gate = jst.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if gate > jst:
                waits.append((gate - jst).total_seconds() / 3600)
    if total < 2 or len(waits) != total:
        return None
    return min(waits)


def quota_is_back(now: datetime | None = None) -> bool:
    """いま日枠（単位）で押せるか。

    **時計では決まりません**（2026-08-17 22:4x に実測して直した）。ここは長らく
    「JST 16時を回っていれば戻っている」でしたが、**単位枠は窓の中で、
    こちらの `videos.insert` が使い切ります**（1本 1,600単位・1周 7〜8本）。
    22:41 JST（窓が開いて 6.7時間後）の実測は、**時計が True・実物は 5本とも 403**。

    **窓が開いていること**と**単位が残っていること**は別の事実なので、両方見ます。
    観測した 403 は確実な事実で、`src.upload_cap` が窓ごとに持っています。
    """
    return upload_cap.day_quota(now or datetime.now(timezone.utc)).open


def hours_to_quota(now: datetime | None = None) -> float:
    """次に押せるようになるまで何時間か。**押せるなら 0.0**。

    窓の頭は**太平洋時間の0時**なので、`upload_cap` から引きます。
    **固定の時差（JST 16:00）で書かないこと** —— 冬は 17:00 です
    （`upload_cap.PT` がそう書いてあるのに、ここが書き直していました）。
    """
    now = now or datetime.now(timezone.utc)
    if quota_is_back(now):
        return 0.0
    return max(0.0, (upload_cap.window_end(now) - now).total_seconds() / 3600)


def tokens(body: list[str]) -> set[str]:
    # **1行ずつ見ること。** 引用は行をまたがない（`quote_spans` は `\n` を含めない）ので、
    # 繋いでから当てると、行末と次の行頭が1つの引用に見えることがあります。
    found = set()
    for line in body:
        found.update(quoted_tokens(line))
    return found


def ship_summary(n: int) -> tuple[Counter, list[str]]:
    kinds: Counter = Counter()
    recent: list[str] = []
    if not RUNS.exists():
        return kinds, recent
    rows = []
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    ships = [r for r in rows if r.get("kind") == "ship"]
    for r in ships[-n:]:
        what = r.get("what", "")
        head = what.split(":", 1)[0].strip() if ":" in what[:12] else "?"
        kinds[head] += 1
        recent.append(f"  {r.get('at', '')[5:16]}  {what[:96]}")
    return kinds, recent


def carry_over(n: int = 8) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """**いま持ち越しに出ている語**と、**物の名前として外した語**を返す。

    `main()` が画面に出しているものと**同じ計算**です（下の呼び出しに切り出しました）。
    切り出したのは、**`run_marker.py --ship --closes` に、その語が実在するかを
    確かめさせるため**です（2026-08-17。3回運ばれた申し送り）。

    **判定を呼ぶ側に写さないこと。** 写した瞬間に、
    `noise_tokens()` や「宣言より前だけ落とす」の直しが片方に入りません
    （`src/alerts.py` の「呼ぶ側に条件を置くと片方だけ書き忘れる」と同じ形です）。
    """
    journal = JOURNAL.read_text(encoding="utf-8")
    closed, _from_record = all_closures(journal)
    blocks = handoff_blocks(journal)[-n:]
    seen: defaultdict[str, list[str]] = defaultdict(list)
    for date, body, start in blocks:
        for tok in tokens(body):
            if tok in closed and start <= closed[tok]:
                continue
            seen[tok].append(date[:16])
    noise = noise_tokens()
    out: dict[str, list[str]] = {}
    dropped: dict[str, list[str]] = {}
    for tok, ds in seen.items():
        if len(ds) < 2:
            continue
        for label, words in noise.items():
            if tok in words:
                dropped.setdefault(label, []).append(tok)
                break
        else:
            out[tok] = ds
    return out, dropped


#: **「配線されている」と数える口**（`unwired_tools()`）。
#: 手順の本文は「毎周 撃つ」と同じ意味なので、ここに入れます。**日誌は入れません**
#: —— 日誌は「この道具の話をした」だけで、撃つ側にはなりません。
#: **`docs/JOURNAL.md` を足さないこと。** 足すと、一度でも申し送りに書かれた道具が
#: 全部「配線ずみ」に化けます（この一覧が5周 手で運ばれた原因そのものです）。
PROC_DOCS = ("docs/trigger_main.md", "docs/trigger_parent.md",
             "docs/spawn_prompt.md", "CLAUDE.md")

#: **(c)「わざと寝かせてある」の目印**。道具自身の docstring から拾います。
#: 語を増やすときは、**その道具の docstring に実際に在る字**にすること
#: （こちらで言い回しを想像して足すと、当たらないまま増えます）。
DORMANT_MARKS = ("だから検査は足していません", "わざと", "配線しないのが正しい",
                 "外の repo", "寝かせ")


def unwired_tools() -> list[dict]:
    """**`scripts/*.py` のうち、どこからも撃たれていない道具**を返す。

    ## なぜ要るか（2026-09-01 に測って足した）

    **この一覧は、5周 続けて申し送りに「`retro.py` の『どこからも呼ばれない』」
    として運ばれていました。ところが `retro.py` にそんな一覧はありませんでした。**
    `grep -n 呼ばれない scripts/retro.py` → **0件**。
    毎回、来た側が手で数え直していたということです。

    そして**手で運ぶうちに、中身がずれていました。** 申し送りの最後の値は
    「**残り 2本**」でしたが、この道具を書いて撃つと **4本**出ます ——
    2本は**一度も申し送りに出たことがありません。**
    **一覧を手で運ぶと、運ばれなかったものは存在しないことになります。**

    ## 何を「撃たれている」と数えるか —— **言及ではなく、呼び方の形**

        1. `scripts/<名前>.py` という**道**が、他の `.py` か手順本文にある
        2. `import <名前>` / `from <名前> import` / `src.<名前>` という**import**がある
        3. `tests/` がそのどちらかをしている（＝ **全体 `pytest` が毎周 撃つ**）

    **3 を入れているのは、`endcard_check` がその形で「配線した」と宣言されているから**です
    （`docs/JOURNAL.md` 2026-08-31 13:5x）。検査が撃つなら、それは撃たれています。

    ### **名前が出てくるだけ、を数えないこと**（2026-09-01 に**2回** 踏んだ）

    最初は `\b<名前>\b` の**素の言及**で数えていました。**2回とも同じ形で壊れました。**

        1回目  この docstring が、見つけた道具の名前を実例として書いた
               → その瞬間 `scripts/retro.py` の中に名前が現れ、**一覧が 4本 → 0本**
        2回目  検査（`tests/test_unwired_tools.py`）が同じ名前を散文で書いた
               → **また 0本**

    **一覧に載せる行為そのものが、載せたものを消していました。**
    「載せた／説明した」は撃つ側ではありません。**だから当てるのは呼び方の形だけ**です。
    こうすると除外の細工が1つも要らなくなります（`retro.py` も検査も、
    名前を散文で書くだけなので当たりません）。

    ## **(a) 配線する／(b) 消す の二択に、(c) を戻す**

    申し送りが5周 繰り返し頼んでいたのはここです ——
    「**(a)/(b) の二択で見ると、(c)『わざと寝かせてある』が落ちます。**
    `deixis_count` は自分の docstring に『だから検査は足していません』と書き、
    覆る条件まで置いてある」。

    だから **道具自身の docstring を読んで、その一行をそのまま添えます。**
    判定はしません —— **「この道具はこう言っています」と見せるだけ**です。
    寝かせるか起こすかは、読んだ回が決めること。

    ## 覆る条件

    - **`src/` は見ていません。** `src/calc/` の族表は動的に読まれるので、
      同じ数え方をすると 40本 前後の偽陽性で埋まります（実測 2026-09-01）。
      `src/` まで広げるなら、**先に「動的に読む口」を申告させること。**
    - **呼び方の形に当てています。** `subprocess` で組み立てた道や、
      `getattr` で引く呼び方は見えません。0本が続いたら、まずここを疑うこと。
    """
    tools = sorted(p for p in (ROOT / "scripts").glob("*.py") if p.name != "__init__.py")
    code: dict[Path, str] = {}
    for d in ("scripts", "src", "tests"):
        for p in (ROOT / d).rglob("*.py"):
            if "__pycache__" not in p.parts:
                code[p] = p.read_text(encoding="utf-8", errors="replace")
    proc = ""
    for rel in PROC_DOCS:
        f = ROOT / rel
        if f.exists():
            proc += f.read_text(encoding="utf-8", errors="replace")

    out: list[dict] = []
    for path in tools:
        n = re.escape(path.stem)
        call = re.compile(
            r"scripts/%s\.py"                       # 道で撃つ
            r"|(?:^|\n)\s*import\s+%s\b"            # import
            r"|(?:^|\n)\s*from\s+%s\s+import"       # from ... import
            r"|\bsrc\.%s\b"                         # src.<名前>
            r"|-m\s+scripts\.%s\b" % (n, n, n, n, n))
        if any(call.search(t) for p, t in code.items() if p != path):
            continue
        if call.search(proc):
            continue
        doc = (re.search(r'"""(.*?)"""', code[path], re.S) or (None, ""))[1]
        says = next((l.strip() for l in doc.splitlines()
                     if any(k in l for k in DORMANT_MARKS)), None)
        out.append({"name": path.stem,
                    "path": path.relative_to(ROOT).as_posix(),
                    "dormant_says": says})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8, help="さかのぼる回数。既定8")
    args = ap.parse_args()

    print("=" * 72)
    print(f"前の回を読む（直近 {args.n} 回）— **設計を見直してから、この回を決めること**")
    print("=" * 72)

    kinds, recent = ship_summary(args.n)
    print(f"\n## 出したもの（直近 {args.n} 件の ship）\n")
    if kinds:
        total = sum(kinds.values())
        for k, c in kinds.most_common():
            print(f"  {k:<8} {c:2d} 件  ({c * 100 // total}%)")
        print()
        for line in recent:
            print(line)
        if kinds.most_common(1)[0][1] * 2 > total:
            top = kinds.most_common(1)[0][0]
            print(f"\n  → **{top} に偏っています。** 同じ種類の手だけを打っていないか。")
    else:
        print("  記録がありません。")

    journal = JOURNAL.read_text(encoding="utf-8")
    closed, from_record = all_closures(journal)
    blocks = handoff_blocks(journal)[-args.n:]
    print(f"\n\n## 「次の回へ」（{len(blocks)} 件）\n")
    for date, body, _ in blocks:
        print(f"── {date}")
        for line in body:
            print(f"  {line}")
        print()

    muted: defaultdict[str, int] = defaultdict(int)
    for _date, body, start in blocks:
        for tok in tokens(body):
            if tok in closed and start <= closed[tok]:
                muted[tok] += 1      # **潰したと宣言された後より前の言及**
    # **一覧そのものは `carried()` が作ります**（`run_marker.py` も同じものを見ます）。
    # ここで作り直さないこと —— 2か所に置くと、次の直しが片方だけに入ります。
    carried, dropped = carry_over(args.n)
    print("\n## 持ち越し（2回以上の申し送りに出てくる語）\n")
    # **この一覧も、自分の当たり率で畳まれます**（`src/alerts.py`）。
    # 08:2x の「予約し忘れ」12件・13:0x の「強い重なり」22組と同じ形で、
    # ここも **当たりを含まないまま育っていました**（4件目）。
    r = alerts.ring("carry_over", len(carried))
    if carried and r.folded:
        print(f"  {r.line}")
        print("  （全文は `python scripts/retro.py --alerts-all`）")
    elif carried:
        # **いまの時刻で潰せないものを、下へ沈める**（2026-08-17。`quota_blocked()`）。
        # 消しません。§2.7 が「持ち越しから選ぶのが既定」と言っている以上、
        # **上位が必ず 403 で落ちる語で埋まっていると、選択そのものを誤らせます。**
        back = quota_is_back()
        blocked = {t for t in carried if quota_blocked(blocks, t)}
        # **時計で塞がっているものも同じ扱い**（2026-08-27 に足した。`clock_blocked()`）。
        # 塞いでいるのが単位か時計かは、選ぶ側には関係ありません。
        clocked = {t: h for t in carried
                   if (h := clock_blocked(blocks, t)) is not None}
        def _sinks(tok: str) -> bool:
            return ((tok in blocked) and not back) or (tok in clocked)
        order = sorted(carried.items(),
                       key=lambda kv: (_sinks(kv[0]), -len(kv[1])))
        for tok, dates in order:
            tail = "  ← **一度閉じた後の再発**" if tok in closed else ""
            if tok in blocked:
                tail += ("  ← **いまなら潰せます**（403 をまだ観測していません）" if back else
                         f"  ← **いまは潰せません**（単位枠。窓が変わるまであと {hours_to_quota():.1f} 時間）")
            # **印を二重に付けないこと。** 単位枠で沈めた語に時刻の印まで足すと、
            # 同じ1行に「いまは潰せません」が2回 出ます（2026-08-27 に実測）。
            if tok in clocked and not (tok in blocked and not back):
                tail += (f"  ← **いまは潰せません**（申し送りが時刻を指定。"
                         f"あと {clocked[tok]:.1f} 時間）")
            print(f"  {len(dates)}回  {tok}{tail}")
            print(f"        {' / '.join(dates)}")
        clock_only = [t for t in clocked if not (t in blocked and not back)]
        if clock_only:
            print(f"\n  **この {len(clock_only)}件 は、申し送り自身が「【HH:MM JST 以降の回へ】」"
                  f"と書いているものです。**")
            print("  **この回では打てません。**（日枠とは別の塞がり方です）"
                  "時刻が来た回では、逆に上へ戻ります。")
        if blocked and not back:
            print(f"\n  **下の {len(blocked)}件 は日枠（`videos.update` / `thumbnails.set`）待ちで、"
                  f"この回では 403 になります。**")
            print(f"  {upload_cap.day_quota().line}")
            print("  **この回で選ぶのは、その上にあるものから。**")
            print("  **消していません。**単位が戻った回では逆に上へ戻り、"
                  "「いまなら潰せます」と出ます。")
        elif blocked and back:
            print(f"\n  **上の {len(blocked)}件 は、いまなら潰せるかもしれません。**")
            # **「戻っている」と言い切らないこと**（2026-08-17 22:4x）。
            # 観測していないのは「残っている」ことの証拠ではありません ——
            # 単位はこちらの投稿が窓の中で使い切ります。
            print(f"  {upload_cap.day_quota().line}")
        print("\n  **これは「毎回言っているのに、まだ潰れていない」ものの候補です。**")
        print("  この回で1件は潰すこと。潰せないなら、なぜ潰さないかを JOURNAL に書く。")
        print("  潰したら **`run_marker.py --ship ... --closes carry_over`** と、"
              "潰した語そのものを両方書くこと（前者がこの一覧の当たり率になります）。")
    else:
        print("  ありません。（申し送りが毎回すべて片づいている、"
              "か、書き方が毎回違って機械では追えていない）")
    # **落としたものは必ず言うこと。** 黙って削ると「全部見た」に見えます。
    if dropped:
        total = sum(len(v) for v in dropped.values())
        print(f"\n  --- **物の名前なので外したもの（{total}件）** ---")
        for label, toks in sorted(dropped.items(), key=lambda kv: -len(kv[1])):
            print(f"  {label:>6s}  {' / '.join(sorted(toks))}")
        print("  **問題の名前ではなく物の名前**です（`noise_tokens()`）。"
              "族名は `src/calc/`、動画IDは `data/critique_queue/` の実物から引いています。")
    if muted:
        print("\n  --- **閉じたと宣言されているので、上から外したもの** ---")
        for tok, n in sorted(muted.items(), key=lambda kv: -kv[1]):
            # **出どころを分けて出す。** 記録は裏が取れ、散文は取れません。
            src = ("記録" if tok in from_record else "日誌の文")
            print(f"  {n}回ぶん  {tok}  ［{src}］")
        print("  ［記録］は `run_marker.py --ship --closes` が構造で残したもの"
              "（`data/runs.jsonl`）。**出したものと対になっているので裏が取れます。**")
        print("  ［日誌の文］は散文から読み取ったもの。**宣言のほうが間違っている"
              "ことがあります**（閉じたつもりで閉じていない）。"
              "\n  疑うなら日誌の宣言を読み、実物に当たること。**言及の回数は証拠になりません。**")

    unwired = unwired_tools()
    print(f"\n\n## どこからも撃たれていない道具（`scripts/*.py`・{len(unwired)}本）\n")
    if unwired:
        print("  **(a) 配線する ／ (b) 消す ／ (c) わざと寝かせてある** の三択で、1本ずつ倒すこと。")
        for row in unwired:
            print(f"  - `{row['path']}`")
            if row["dormant_says"]:
                print(f"      ← **(c) かもしれません。**その道具自身がこう書いています: "
                      f"{row['dormant_says'][:100]}")
        print("\n  **この一覧は、5周 申し送りで手で運ばれていたものです**"
              "（`unwired_tools()` の docstring）。**手で数え直さないこと。**")
    else:
        print("  ありません。")

    review_all = blocks_under(journal, REVIEW_RE)
    reviews = review_all[-args.n:]
    print(f"\n\n## 設計の見直し（§6 (a2)）を**縦に読む**（{len(reviews)} 件）\n")
    if reviews:
        print("  1回ぶんでは何も言いませんが、**並べると癖が出ます。**")
        print("  （問い1の1行目だけ。全文は日誌に）\n")
        for date, body, _ in reviews:
            q1 = first_lines(body, "1")
            print(f"  {date[:16]:<18} {q1[:88] if q1 else '（問い1に答えていない回）'}")
    else:
        print("  記録がありません。")

    # 問い4（いまの道筋）は判断で決めない。前の [道筋] から数えて機械が言う。
    since = None
    for i, (_, body, _s) in enumerate(reversed(review_all)):
        if any(ROUTE_MARK in line for line in body):
            since = i
            break
    print()
    if since is None:
        print(f"  **道筋の見直しは、まだ1度もありません**（(a2) は {len(review_all)} 件）。")
        due = len(review_all) >= ROUTE_EVERY
    else:
        print(f"  前に道筋を見てから **{since} 回**（{ROUTE_EVERY} 回で1度）。")
        due = since >= ROUTE_EVERY
    if due:
        print("  → **この回は、(a2) の問い4（いまの道筋）に答えること。**")
        print(f"     答えたら (a2) の節に `{ROUTE_MARK}` と書く（次がここから数えます）。")
    else:
        print("  → この回は問い1〜3だけでよい。")

    print("\n" + "=" * 72)
    print("**同じ種類の穴が続いていないか。** 直近の題名を並べて、種類で括ってみること。")
    print("違う穴を毎回1つずつ塞いでいるように見えて、**種類が同じなら、")
    print("塞ぐべきは穴ではなく、穴を作っている側**です。")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    # `--alerts-all` は、畳んだ一覧を全文で出す（`src/alerts.py`）。
    # **旗はここだけ**で、持ち越しの節は `alerts.ring()` の返り値しか見ません
    # （`status.py` と同じ形。call site に条件を書くと、次に一覧を足した回が
    # 片方だけ書き忘れます —— この作りで通算7回）。
    alerts.set_show_all("--alerts-all" in sys.argv[1:])
    sys.argv = [a for a in sys.argv if a != "--alerts-all"]
    raise SystemExit(main())
