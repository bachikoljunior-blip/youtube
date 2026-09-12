"""`docs/METHOD.md` の「毎回 読む」側が、6周の窓でどれだけ伸びたかを印字する（API 0単位・git だけ）。

    python scripts/method_growth.py            # いちばん新しい窓
    python scripts/method_growth.py --after "2026-09-10 10:17"   # 窓の頭を JST の刻より後に固定
    python scripts/method_growth.py --laps 6 --points 3          # 窓の長さと、並べる点の数

**なぜ道具にしたか**（2026-09-10 12:1x JST・optimizer・Opus）:
冒頭「この文書の読み方」は **2つの門**を置いています —— 行 **1周 +20行**・
本文の字 **1周 +300字**（11:0x）。**どちらにも印字する口がありませんでした。**
数え方は JOURNAL 05:5x の「そのままの手」に散文で在るだけで、
**6周ごとに、次の回がその一節を探し出して手で回す**形です。

これは METHOD 自身が repo でいちばん多い壊れ方と呼んでいるもの
（**言っている所と、している所が別**）で、`trend.py` の「毎周 印字する数」・
`§6` の「**覚えないこと**」と同じ扱いにします。**門は、読む人ではなく道具が見ます。**

**数え方**（05:5x が決め、11:0x が本文の側へ絞ったもの。**変えるときは点を1点目から取り直すこと**）:

    「毎回 読む」側  §0 の見出しから §7 の手前まで ＋ §8 の見出しから §9 の手前まで
    本文            `>` で始まらない**非空**行（＝ 引用ブロックを除いた側）
    引用            `>` で始まる行
    窓の端          **`data/rounds.jsonl` の周の刻**。**commit ではない**
                    —— 05:5x の実測: 窓の頭を近くの commit で取ると **+1,348字 ずれる**
                    （その commit が既に +1,937字 を含んでいた）。
                    **窓の取り方が 1点ごとに違うと、点は比べられません**
    1周に 2行       `rounds.jsonl` は `hourly` と `optimizer` を同じ刻で記録するので、
                    **`round` で畳んでから数える**（畳まないと素の差の半分が 0.0分 になる・§5）

**門**（冒頭「この文書の読み方」の (2) と 11:0x の字の門）:

    行   1周 **+20行** を越えた窓が続いたら、log を `docs/METHOD_LOG.md` へ移す
    本文字 1周 **+300字** を越えた窓が **2つ 続いたら**、その窓を吸った節を名指しして
         §5／§6 の形（決めは本文・derivation は外）を当てる

**行の門は、単独では効きません**（11:0x の実測）—— 点3 は **+0.5行/周** で
門 20行 の **1/40** しか使わずに **+616字/周** 積みました。
**表と長い行に対して、行の門は構造として盲**なので、2つとも印字します。

**覆る条件**: (1) §6 の表を別ファイルへ出す判断が出たら、「毎回 読む」側の定義が変わる ＝
この物差しは作り直し・点は 1点目から取り直すこと（`SECTIONS` を変えたらそれが起きています）。
(2) 削りの回（derivation を JOURNAL へ移すなど）を窓に含めると、**伸びではなく削りを測ります**
—— `--after` で窓の頭をその後ろへ固定すること（11:0x が点4 についてそう書いた）。
(3) 節の見出しの字（`## 0.` など）が変われば `_section_bounds` が `KeyError` で止まります。
**黙って 0 を返さないこと** —— 止まるほうが、外れた数を配るより安いので、そのままにしてあります。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
METHOD = "docs/METHOD.md"
ROUNDS = ROOT / "data" / "rounds.jsonl"

# 「毎回 読む」側 ＝ この2区間（見出しの頭で挟む）。**変えたら点は 1点目から取り直し。**
SECTIONS = (("## 0.", "## 7."), ("## 8.", "## 9."))

LINE_GATE = 20    # 1周ぶんの行（冒頭「この文書の読み方」(2)）
CHAR_GATE = 300   # 1周ぶんの本文の字（11:0x の字の門）


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def _section_bounds(lines: list[str], head: str) -> int:
    for i, l in enumerate(lines):
        if l.startswith(head):
            return i
    raise KeyError(f"{METHOD} に見出しが在りません: {head!r} —— 節の名が変わったなら、この物差しは作り直し（註の覆る条件 (3)）")


def _count(seg: list[str]) -> dict:
    body = [l for l in seg if not l.startswith(">") and l.strip()]
    quote = [l for l in seg if l.startswith(">")]
    return {
        "body_lines": len(body),
        "body_chars": sum(len(l) for l in body),
        "quote_chars": sum(len(l) for l in quote),
    }


def measure(text: str) -> dict:
    """「毎回 読む」側の 本文の行・本文の字・引用の字 を数える。"""
    lines = text.split("\n")
    seg: list[str] = []
    for head, tail in SECTIONS:
        seg += lines[_section_bounds(lines, head):_section_bounds(lines, tail)]
    return _count(seg)


def section7_spans(lines: list[str]) -> list[tuple[int, int]]:
    """**毎周 読むのに、上の物差しが 1字も見ていない 3つの塊**の行の範囲（**4つ に割って返す**）。

    冒頭「この文書の読み方」が読ませているのは **§0〜§6・§8 だけではありません** ——
    §7 も「いまの数」と「末尾の覆る条件の一覧」の 2つ は毎周 読みます
    （**日付つきの節は飛ばす**）。**12:1x の物差しは、そこを 1字も見ていませんでした。**

    ＝ **伸びる先が測られない側へ移る**（§7 (i) が `status` の写しで名指しした形）が、
    物差しそのものに在りました。2026-09-10 23:5x・optimizer・Opus に足しています。

    **どこで挟むか**（見出しが無い塊なので、字の形で挟みます）:

        読み方      ファイルの頭から `## 0.` の手前まで（冒頭「この文書の読み方」——
                    `SECTIONS` は `## 0.` から始まるので、**ここも measure の外**でした）
        いまの数    `### いまの数` から、その後ろの最初の `**【2026-` の手前まで
                    （＝ 日付つきの節が始まる所。この塊は**毎周 上書き**される側）。
                    **この塊はさらに 2つ に割ります** —— 「数の表」と「次に見る所」
                    （`_now_cut` の註・2026-09-11 12:0x。伸びているのは下側だけ）
        末尾の一覧  **最後の** `- **【2026-` の後ろで、最初に来る `- **`（日付つきでない）
                    から `## 8.` の手前まで

    **覆る条件**: (1) §7 の日付つきの節が `- **【2026-` 以外の書き出しになったら、
    下の 2つ の挟みは黙って外れます —— **`ValueError` で止めます**（黙って 0 を返さないこと）。
    (2) 「いまの数」が `###` の見出しを失ったら、同じく止まります。
    (3) §7 を別ファイルへ割る判断が出たら、この物差しは作り直し（点は 1点目から）。
    """
    head = _section_bounds(lines, "## 0.")
    a0 = _section_bounds(lines, "### いまの数")
    a1 = next((i for i in range(a0 + 1, len(lines)) if lines[i].startswith("**【2026-")), None)
    if a1 is None:
        raise ValueError("§7 に日付つきの節が 1つも在りません —— 挟みが外れています（註の覆る条件 (1)）")
    a1_now = _now_cut(lines, a0, a1)
    end = _section_bounds(lines, "## 8.")
    dated = [i for i in range(a0, end) if lines[i].startswith("- **【2026-")]
    if not dated:
        raise ValueError("§7 に `- **【2026-` の節が 1つも在りません —— 挟みが外れています（註の覆る条件 (1)）")
    b0 = next((i for i in range(dated[-1] + 1, end)
               if lines[i].startswith("- **") and not lines[i].startswith("- **【")), None)
    if b0 is None:
        raise ValueError("§7 の末尾に覆る条件の一覧が在りません —— 挟みが外れています（註の覆る条件 (1)）")
    return [(0, head), (a0, a1_now), (a1_now, a1), (b0, end)]


#: 「いまの数」の中の 2つ目の塊の書き出し（字下げ ＋ この語）。**見出しではありません。**
NEXT_LOOK = "次に見る所"


def _now_cut(lines: list[str], a0: int, a1: int) -> int:
    """「いまの数」を **数の表** と **次に見る所** に割る行（2026-09-11 12:0x・optimizer・Opus）。

    **なぜ割るか**（この回に手で数えた）: 塊の門（`split_drawn`）が「いまの数」を名指ししても、
    **その塊は 2つ の別の物でできています** —— 上は「数と口の名だけ」の表、下は `(a)〜(m)` の
    「次に見る所」。**実測 09/11 08:12 → 11:58（6周）**: 塊は 14,919 → 18,830字（**1周 +652**）で、
    内訳は **数の表 4,485 → 4,617（1周 +22）／次に見る所 10,434 → 14,213（1周 +630）**
    ＝ **伸びは 96% が下側**。上の表は 07:3x に当てた形（数と口の名だけ）が**効いています**。

    ＝ 門が名指しした塊へ「§5／§6 の形を当てる」と読むと、**既に形の効いている側を畳みに行きます**。
    **名指しは、実際に伸びている側まで降りること。**（この回は手で割って見つけた ＝ §7 (i) の
    「手で数えないこと」に対して、物差しの側が 1段 浅かった）

    **覆る条件**: (1) 「次に見る所」の書き出しの語が変わったら、この割りは黙って外れます ——
    **`a1`（塊の終わり）を返して 2つ目を空にします**（合計は変わらない ＝ 上の塊の門は
    割る前と同じに鳴る）。**0 を配らないための形**で、`section7_spans` の覆る条件 (1)(2) の
    「止める」とは別（あちらは塊そのものが外れる ＝ 数が嘘になる側）。
    (2) 「次に見る所」が `###` の見出しを持ったら、この字の挟みは捨てて見出しで挟むこと。
    """
    return next((i for i in range(a0 + 1, a1) if lines[i].strip().startswith(NEXT_LOOK)), a1)


#: `section7_spans` が返す 4塊 の名（並びは同じ）。**「いまの数」は 2つ に割れています**（`_now_cut`）。
SPAN7_NAMES = ("読み方", "いまの数", "次に見る所", "末尾の一覧")


def measure7(text: str) -> dict:
    """**毎周 読むのに measure が見ていない側**だけを数える（日付つきの節は入れない）。"""
    lines = text.split("\n")
    seg: list[str] = []
    for a, b in section7_spans(lines):
        seg += lines[a:b]
    return _count(seg)


def measure7_split(text: str) -> dict:
    """同じ塊を**塊ごと**に数える（門が引かれた回に、吸った塊を名指しするため）。

    **4つ 返します** —— 「いまの数」は `_now_cut` で 2つ に割れています（その註）。
    **合計は `measure7` と同じ**（割りは足し算を変えません・検査で押さえてあります）。
    """
    lines = text.split("\n")
    return {n: _count(lines[a:b]) for n, (a, b) in zip(SPAN7_NAMES, section7_spans(lines))}


#: §9 以降の「1本の節」の見出し（`## <番号>. <N>本目（<日付>・`<id>`）…`）。
#: **id で挟みます** —— 節の番号は本が増えるたびに動くので、窓の両端で同じ節を指せません。
BOOK_HEAD = re.compile(r"^## (\d+)\. .*?`(\d{4}-\d{2}-\d{2}-[^`]+)`")

#: **毎周 読むのは「直近の1本」だけ**（冒頭「この文書の読み方」）。どちらの節かは枠の状態で変わる
#: （きょうの枠が公開前なら `hourly` は 1つ 手前を読む）ので、**いちばん新しい 2つ**を見ます。
BOOK_READ = 2


def book_sections(lines: list[str]) -> list[dict]:
    """**§9 以降の「1本の節」**の 番号・id・行の範囲（古い順）。

    **なぜ足したか**（2026-09-11 06:5x JST・optimizer・Opus。**この回に数えて踏んだ**）:
    冒頭「この文書の読み方」が毎周 読ませているのは 4つ で、**4つ目が「§9 以降のうち 直近の1本」**です。
    12:1x（§0〜§6・§8）と 23:5x（§7 の 3塊）の物差しは、**その 4つ目を 1字も見ていませんでした。**

    **見ていない側がいちばん大きくなっていました**（この回の実測・本文の字）:

        §14（09/11 の本・`hourly` が読む側）  **24,125字**   ← 引用 0行
        §4                                   12,969字
        §5 本文                              11,958字
        §13（5本目）                          6,002字   §15（7本目）  3,791字

    ＝ **§14 だけが 兄弟の 4倍 で、毎周 読む物のどれよりも大きい。**
    節の頭は「**この節は『いまの状態』を上書きする 1塊**（§13 と同じ形）」と書いており、
    §13・§15 はそのとおりに小さいまま ＝ **形が悪いのではなく、§14 でだけ守られていません。**

    **なぜ守られなかったか**: §14 が自分に置いた門は **行の門**でした
    （「この節の伸びを 1周 +5行 以内に」）。行は守られています —— 直近の周は
    10:2x の塊へ **1周 1行**ずつ畳み込んでおり、その 1行 が
    **116〜1,288字**（18本・中央 **578字**）です。
    ＝ 冒頭「この文書の読み方」が 11:0x に名指しした形そのもの
    （**「表と長い行に対して、行の門は構造として盲です」**）が、
    **行の門しか置いていない唯一の節**に残っていました。

    **この道具は数えるだけです** —— §14 は**きょうの枠の本 ＝ `hourly` の持ち場**（§5）なので、
    畳むかどうかは hourly が決めること（§7 (i) が §4 についてそう書いたのと同じ形）。

    **覆る条件**: (1) 本の節の見出しから id（バッククォートの中の `YYYY-MM-DD-…`）が消えたら、
    挟みは黙って外れます —— **`ValueError` で止めます**（黙って 0 を返さないこと）。
    (2) 「直近の1本」が 2つ で足りなくなったら（1周に 3本 の節を読む形に変わったら）`BOOK_READ` を上げること。
    (3) 本の節を別ファイルへ割る判断が出たら、この物差しは作り直し（点は 1点目から取り直す）。
    """
    heads = [(int(m.group(1)), m.group(2), i)
             for i, l in enumerate(lines) if (m := BOOK_HEAD.match(l)) and int(m.group(1)) >= 9]
    if not heads:
        raise ValueError("§9 以降に本の節が 1つも在りません —— 挟みが外れています（註の覆る条件 (1)）")
    out = []
    for k, (num, sid, i) in enumerate(heads):
        end = (heads[k + 1][2] if k + 1 < len(heads)
               else next((j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")), len(lines)))
        out.append({"num": num, "id": sid, "a": i, "b": end})
    return out


def books_all(text: str) -> dict[str, dict]:
    """**§9 以降の本の節を全部**、id ごとに数える（窓の頭で同じ id を引くため）。"""
    lines = text.split("\n")
    return {b["id"]: _count(lines[b["a"]:b["b"]]) for b in book_sections(lines)}


def measure_books(text: str) -> dict[str, dict]:
    """**毎周 読む「直近の1本」の候補**（いちばん新しい `BOOK_READ` 個）を id ごとに数える。"""
    lines = text.split("\n")
    return {b["id"]: _count(lines[b["a"]:b["b"]]) for b in book_sections(lines)[-BOOK_READ:]}


def rounds() -> list[datetime]:
    """周の刻（`round` で畳む ＝ 1周に 2行 入るので）。古い順。"""
    seen: set[str] = set()
    out: list[datetime] = []
    for line in ROUNDS.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line).get("round")
        if r and r not in seen:
            seen.add(r)
            out.append(datetime.fromisoformat(r))
    return sorted(out)


def worktree_text() -> str:
    """**いま作業ツリーに在る** METHOD（commit していない直しも入る）。

    **なぜ blob ではないか**（2026-09-11 05:1x JST・optimizer・Opus。**この回に踏んだ**）:
    `report()` の「いま 本文 N字」は `points()` の最後の窓の `now`（＝ **周の刻より前の
    最後の commit の blob**）から取っていました。窓の端は commit ではなく周の刻で挟むのが
    正しい（上の註）—— **ですが「いま」はその窓の端ではなく、この回が読んでいる字**です。
    実測: この回が §7 末尾の一覧を **-4,166字** 縮めた直後に撃つと、
    「いま 28,669字」（＝ 縮める前の数）と印字しました。
    **その数を §7 の「いまの数」へ書き写すと、削った回ほど大きい嘘が載ります**
    （METHOD が repo でいちばん多いと呼ぶ壊れ方 ＝「言っている所と、している所が別」）。
    **窓の差（伸び）は blob のまま**です —— 動かしたのは「いま」の1行だけ。

    **覆る条件**: (1) この道具を、作業ツリーが無い所（CI・別の checkout）から撃つ回が出たら、
    読めないときに blob へ落ちる枝が要る（いまは無い ＝ 読めなければそのまま止まる。
    黙って古い数を配るより安い・上の (3) と同じ扱い）。
    (2) 「いま」に commit していない直しが入るのが邪魔になる回が出たら（例: 2体が同じ
    作業ツリーを見る形に変わったとき）、印字を「いま」と「周の刻の blob」の2行に分けること。
    """
    return (ROOT / METHOD).read_text(encoding="utf-8")


def blob_at(when: datetime) -> str | None:
    """その刻**より前**の最後の commit の METHOD（commit の刻で挟まない・05:5x の決め）。"""
    sha = _git("log", "-1", f"--before={when.isoformat()}", "--format=%H", "--", METHOD).strip()
    return _git("show", f"{sha}:{METHOD}") if sha else None


def points(laps: int = 6, n: int = 3, after: datetime | None = None) -> list[dict]:
    """窓を `n` 個ぶん、古い順に並べる。各窓は `laps` 周ぶん。"""
    rs = [r for r in rounds() if after is None or r >= after]
    out = []
    # いちばん新しい窓が末尾に来るように、後ろから `laps` きざみで切る。
    edges = rs[len(rs) - 1 - laps * n:: laps] if len(rs) > laps * n else rs[::laps]
    for head, tail in zip(edges, edges[1:]):
        a, b = blob_at(head), blob_at(tail)
        if a is None or b is None:
            continue
        ma, mb = measure(a), measure(b)
        # §7 の毎周 読む側は**別に**数えます（同じ数に足さない ＝ 12:1x の 3点 を壊さないため）。
        try:
            s7a, s7b = measure7(a), measure7(b)
        except (KeyError, ValueError):
            s7a = s7b = None
        # **塊ごと**も同じ窓で数えます（合計の門は、塊どうしの打ち消しに対して盲・`split_drawn` の註）。
        try:
            sp_a, sp_b = measure7_split(a), measure7_split(b)
            s7_split = {nm: (sp_b[nm]["body_chars"] - sp_a[nm]["body_chars"]) / laps for nm in SPAN7_NAMES}
        except (KeyError, ValueError):
            s7_split = None
        # **本の節**（毎周 読む 4つ目・2026-09-11 06:5x）。**id で挟む** —— 節の番号は本が増えると動く。
        try:
            bk_a, bk_b = books_all(a), measure_books(b)
            books = {sid: {"now": cb["body_chars"],
                           "d": None if sid not in bk_a else cb["body_chars"] - bk_a[sid]["body_chars"],
                           "per_lap": None if sid not in bk_a else (cb["body_chars"] - bk_a[sid]["body_chars"]) / laps}
                     for sid, cb in bk_b.items()}
        except (KeyError, ValueError):
            books = None
        out.append({
            "books": books,
            "from": head, "to": tail, "laps": laps,
            "d_lines": mb["body_lines"] - ma["body_lines"],
            "d_body": mb["body_chars"] - ma["body_chars"],
            "d_quote": mb["quote_chars"] - ma["quote_chars"],
            "lines_per_lap": (mb["body_lines"] - ma["body_lines"]) / laps,
            "chars_per_lap": (mb["body_chars"] - ma["body_chars"]) / laps,
            "now": mb,
            "s7_body": None if s7b is None else s7b["body_chars"] - s7a["body_chars"],
            "s7_per_lap": None if s7b is None else (s7b["body_chars"] - s7a["body_chars"]) / laps,
            "s7_split": s7_split,
            "s7_now": s7b,
        })
    return out


def too_few_windows(n: int, vals: list[float] | None = None, unit: str = "字/周") -> str:
    """**窓が 2つ 無い回に「引かれません」と言わないこと**（2026-09-13 07:2x・optimizer・Opus）。

    **この回に踏みました。** 04:3x の申し送りは「手の効きは `--after '<手の刻>' --laps 1` で読め」
    と書いており、そのとおり `--after "2026-09-13 02:42" --laps 5 --points 2` を撃つと、
    周が 5つ しか無いので窓は **1つ** しか作れません。そこで出た行は

        字の門 1周 +300字: 引かれません（直近 2窓 で越えたのは 1 つ）

    で、**「2窓 在って続かなかった」と読めます。** 実際は **まだ測れていない**（窓が 1つ）。
    `trend` が「まだ測れていません」と「引かれません」を分けているのと同じ穴で、
    ここは**分けていませんでした**。**向きが悪い**: 窓が足りない回ほど「引かれません」と言うので、
    手の直後（周が積まっていない回）にだけ、静かなほうへ倒れます。

    **覆る条件**: 窓の数を印字しても、次の回が「1つ」を見落として同じ読み違いをしたら、
    数ではなく**撃ち方**（`--laps` を周の数で割った値に丸める）を道具の側で直すこと。
    """
    now = f"（いまの窓 {vals[-1]:+.0f}{unit}）" if vals else ""
    return (f"**まだ測れません** —— 窓が {n}つ しか在りません（門は 2窓 要る）{now}。"
            "**「引かれません」ではありません**（`--laps` を小さくするか、周が積まるのを待つこと）")


def level_caveat(vals: list[float]) -> str:
    """**門は「続いたか」を見ており、水準を見ていません**（2026-09-13 07:2x・optimizer・Opus）。

    **窓の幅を変えると、同じ +300字 が別の厳しさになります。**
    `--laps 6` は 6周 を均すので、水準が門の上なら隣り合う 2窓 はほぼ必ず越えます。
    `--laps 1` は均さないので、**同じ水準でも 1周 凹めば門は鳴りません。**

    **実測（この回・`--after "2026-09-13 02:42"`・4塊）**: 02:5x の手の後の 5周 は
    **+713 / -28 / +134 / +45 / +1,019字** ＝ 並べた 5窓 の平均 **+377字/周（門の上）**。
    それでも `--laps 1` の門は「引かれません」で、同じ台帳を `--laps 5` で読むと 1周 **+377字**。
    ＝ **04:3x の申し送り（「`--laps 1` で 2周 続けて越えるか」）は、
    門を引いた側（`--laps 6`）より構造として厳しく、水準が上でも鳴りません。**
    そのまま次の回が読めば「02:5x の手が効いた」と結論します —— 水準は落ちていないのに。

    ＝ 続いていなくても、**並べた窓の平均が門の上なら、そう言います**（門の答えは変えません）。

    **覆る条件**: (1) この行が出たのに、そのあと 2窓 続けて越える回が 1度も来ないまま
    水準が門の下へ落ちたら、この行は「凹み 1つ」を騒いでいただけ ＝ 畳んでよい。
    (2) 逆に この行の次の回で門が本当に引かれたら、**申し送りには `--laps` を必ず書くこと**
    —— 幅を書かない申し送りは、門を引いた物とは別の門を指しています（§5 教訓の形 13つ目の裏）。
    """
    if not vals:
        return ""
    mean = sum(vals) / len(vals)
    if mean <= CHAR_GATE:
        return ""
    return (f"。**ただし並べた {len(vals)}窓 の平均は {mean:+.0f}字/周 で門の上です** ——"
            "門が見ているのは「続いたか」で、**水準ではありません**。"
            "**窓の幅を変えると同じ門が別の厳しさになります**（`--laps 1` は均さない）"
            "＝ 申し送りには `--laps` を必ず書くこと（`level_caveat` の註）")


def verdict(ps: list[dict]) -> list[str]:
    """門を引くのは道具。**次の回は覚えていなくてよい。**"""
    if not ps:
        return ["点が 1つも取れません（`data/rounds.jsonl` が窓ぶん無い ＝ まだ測れていない）"]
    out = []
    over_line = [p for p in ps if p["lines_per_lap"] > LINE_GATE]
    out.append(f"行の門 1周 +{LINE_GATE}行: " + (
        f"**越えた窓 {len(over_line)}/{len(ps)}**" if over_line else f"引かれません（最大 {max(p['lines_per_lap'] for p in ps):+.1f}行/周）"))
    vals = [p["chars_per_lap"] for p in ps]
    tail2 = ps[-2:]
    over2 = [p for p in tail2 if p["chars_per_lap"] > CHAR_GATE]
    if len(tail2) < 2:
        out.append(f"字の門 1周 +{CHAR_GATE}字: " + too_few_windows(len(tail2), vals))
    elif len(over2) == 2:
        out.append(f"字の門 1周 +{CHAR_GATE}字: **引かれました** —— 直近 2窓 とも越えています"
                   f"（{tail2[0]['chars_per_lap']:+.0f} / {tail2[1]['chars_per_lap']:+.0f}）。"
                   "**吸った節を名指しして、§5／§6 の形（決めは本文・derivation は外）を当てること**")
    else:
        out.append(f"字の門 1周 +{CHAR_GATE}字: 引かれません"
                   f"（直近 2窓 で越えたのは {len(over2)} つ ＝ 2つ 続いていない）" + level_caveat(vals))
    return out


def split_report(laps: int = 6, n: int = 3, after: datetime | None = None) -> str:
    """**どの塊がその窓を吸ったか**（`--split`）。門が引かれた回に撃つこと。"""
    rs = [r for r in rounds() if after is None or r >= after]
    edges = rs[len(rs) - 1 - laps * n:: laps] if len(rs) > laps * n else rs[::laps]
    out = ["塊ごとの伸び（本文の字・日付つきの節は入れない）"]
    for head, tail in zip(edges, edges[1:]):
        a, b = blob_at(head), blob_at(tail)
        if a is None or b is None:
            continue
        try:
            ba, bb = measure7_split(a), measure7_split(b)
        except (KeyError, ValueError) as e:
            out.append(f"  {head.astimezone(JST):%m/%d %H:%M} → 挟みが外れています: {e}")
            continue
        out.append(f"  {head.astimezone(JST):%m/%d %H:%M} → {tail.astimezone(JST):%m/%d %H:%M} JST")
        for name in SPAN7_NAMES:
            d = bb[name]["body_chars"] - ba[name]["body_chars"]
            out.append(f"    {name:6s} {ba[name]['body_chars']:6,d} → {bb[name]['body_chars']:6,d}"
                       f"  ＝ {d:+6,d}字（1周 **{d / laps:+.0f}**）")
    return "\n".join(out)


def split_drawn(ps: list[dict]) -> list[str]:
    """**塊ごとの門**（1周 +300字・直近 2窓 とも越えたら）。名前は `SPAN7_NAMES` の順。

    **なぜ合計とは別に要るか**（2026-09-11 07:3x・optimizer・Opus が足した）:
    3塊 の門は**合計だけ**を見ていました。合計は**塊どうしの打ち消しに対して盲**です ——
    1つ が伸び、別の 1つ が畳まれた窓では、合計は下を向きます。
    **実測（この回・`--split --points 8`）**:

        09/11 03:22 → 06:58   いまの数 **+416字/周** / 末尾の一覧 **-1,401字/周**
                              → 合計は **-882字/周** ＝ 門は鳴らない

    ＝ **畳んだのは 末尾の一覧（04:4x の -8,404字）で、伸びたのは「いまの数」**。
    合計の側から見ると、この 2つ は同じ 1つ の数に潰れます。
    **4つ目（本の節）の門は最初から節ごと**なので（`book_report`）、
    **塊の側だけが合計で読まれていました** —— そろえます。

    **この門が名指しする側の水準**（同じ回に数えた）: 「いまの数」は
    **09/09 23:1x の 3,957字 → 09/11 06:5x の 16,339字（48周 で +313%）**。
    §7 自身が「**毎周 上書き**する1塊」と書いている側が、3塊 の **58%** を占めています。

    **覆る条件**: (1) この門が引かれた回に `--split` を撃って、名指しされた塊が
    実際には**日付つきの節の出入り**で動いていた（挟みが滑った）なら、
    直すのは門ではなく `section7_spans`（その註の覆る条件 (1)(2)）。
    (2) 合計の門と塊の門が **3窓 続けて同じ答え**しか返さなければ、塊の側は畳んでよい
    （＝ 打ち消しは起きていない ＝ この註の前提が外れた）。
    """
    ok = [p for p in ps if p.get("s7_split")]
    tail2 = ok[-2:]
    if len(tail2) < 2:
        return []
    drawn = []
    for nm in SPAN7_NAMES:
        vals = [p["s7_split"][nm] for p in tail2]
        if all(v > CHAR_GATE for v in vals):
            drawn.append(f"{nm}（{vals[0]:+.0f} / {vals[1]:+.0f}）")
    return drawn


def window_caveat(laps: int) -> str:
    """**幅のある窓は、手を打った回の効きを答えられない**（2026-09-13 04:3x・optimizer・Opus）。

    窓が `laps` 周ぶん在るあいだ、手の刻をまたぐ窓は **手の前の周を最大 `laps`-1 周ぶん運びます**。
    そこで読んだ数は「手の効き」ではなく「手の前がどうだったか」で、**手の直後ほど前の側が重い**。
    実測（JOURNAL 09/13 04:3x）: 02:5x の手のあと、6周窓は 1窓目 +671／2窓目 +678字/周（門 300 の上）。
    同じ台帳を `--after '2026-09-13 02:42' --laps 1` で読むと **+713 → -28字/周** ＝ **手の後の周は門の下**。
    ＝ **2窓 待っても答えは変わりません**（窓が丸ごと手の後になるのは `laps` 周 後）。
    **覆る条件**: 窓の幅を 1周 にした回が出たら、この註の「最大 `laps`-1 周」は 0 になる ＝ この行ごと畳むこと。
    """
    return (f"  **この窓では、手を打った回の効きを読まないこと** —— 窓は {laps}周 幅なので、"
            f"手の刻が窓の中に在るあいだ、この数は手の**前**の周を最大 {laps - 1}周 ぶん運びます"
            f"（窓が丸ごと手の後になるのは {laps}周 後）。"
            f"手の効きは `--after '<手の刻 JST>'`（できれば `--laps 1`）で読むこと。")


def report(laps: int = 6, n: int = 3, after: datetime | None = None) -> str:
    ps = points(laps, n, after)
    out = [f"METHOD の「毎回 読む」側（§0〜§6・§8）の伸び —— 窓は {laps}周・**周の刻で挟む**（commit ではない）"]
    if laps > 1 and after is None:
        out.append(window_caveat(laps))
    for p in ps:
        out.append(
            f"  {p['from'].astimezone(JST):%m/%d %H:%M} → {p['to'].astimezone(JST):%m/%d %H:%M} JST"
            f"   本文 {p['d_lines']:+d}行 / {p['d_body']:+d}字"
            f"  ＝ 1周 **{p['lines_per_lap']:+.1f}行・{p['chars_per_lap']:+.0f}字**"
            f"   （引用 {p['d_quote']:+d}字）")
    if ps:
        m = measure(worktree_text())   # **窓の端の blob ではなく、いま作業ツリーに在る字**（註）
        out.append(f"  いま 本文 {m['body_lines']}行・{m['body_chars']:,}字 ／ 引用 {m['quote_chars']:,}字"
                   f"（引用は**飛ばしてよい側** ＝ 守れるのはここだけ・§5。"
                   f"**この行だけは作業ツリー** ＝ 押していない直しも入る・`worktree_text` の註）")
    out += ["  " + v for v in verdict(ps)]
    s7 = [p for p in ps if p["s7_per_lap"] is not None]
    if s7:
        out.append("**毎周 読むのに、上の物差しが見ていない 4塊**（冒頭「この文書の読み方」＋"
                   "§7 の「**数の表**」＋「**次に見る所**」＋§7 末尾の覆る条件の一覧。"
                   "日付つきの節は入れない・2026-09-10 23:5x に足し、**12:0x に「いまの数」を 2つ に割った**）")
        for p in s7:
            out.append(f"  {p['from'].astimezone(JST):%m/%d %H:%M} → {p['to'].astimezone(JST):%m/%d %H:%M} JST"
                       f"   本文 {p['s7_body']:+d}字  ＝ 1周 **{p['s7_per_lap']:+.0f}字**")
        m7 = measure7(worktree_text())   # 同じ（註）
        out.append(f"  いま 本文 {m7['body_lines']}行・{m7['body_chars']:,}字"
                   f"（**上の §0〜§6・§8 とは別の数** ＝ 足さないこと。**この行も作業ツリー**）")
        s7vals = [p["s7_per_lap"] for p in s7]
        over = [p for p in s7[-2:] if p["s7_per_lap"] > CHAR_GATE]
        if len(s7[-2:]) < 2:
            s7line = too_few_windows(len(s7[-2:]), s7vals)
        elif len(over) == 2:
            s7line = ("**引かれました** —— 直近 2窓 とも越えています。"
                      "**`--split` で どの塊が吸ったかを名指ししてから、§5／§6 の形を当てること**")
        else:
            s7line = f"引かれません（直近 2窓 で越えたのは {len(over)} つ）" + level_caveat(s7vals)
        out.append(f"  字の門 1周 +{CHAR_GATE}字: " + s7line)
        # **塊ごとの門**（合計は打ち消しに対して盲・`split_drawn` の註・2026-09-11 07:3x）。
        sd = split_drawn(ps)
        if sd:
            sdline = ("**引かれました** —— " + "・".join(sd) +
                      "。**合計が下を向いていても、この塊は伸びています**（打ち消し）。"
                      "§5／§6 の形を当てること（決めは本文・derivation は外）")
        elif len(s7[-2:]) < 2:
            sdline = too_few_windows(len(s7[-2:]))
        else:
            sdline = "引かれません（直近 2窓 とも越えた塊は 0 つ）"
        out.append(f"  塊ごとの門 1周 +{CHAR_GATE}字: " + sdline)
    out += book_report(ps)
    return "\n".join(out)


def book_report(ps: list[dict], now: dict | None = None) -> list[str]:
    """**毎周 読む 4つ目（§9 以降のうち 直近の1本）**の水準と伸び（2026-09-11 06:5x に足した）。

    上の 2つ の物差しは「伸び」を見ますが、**ここは水準も印字します** ——
    この節は 1本 出るたびに作り直される（＝ 新しい節は 0 から始まる）ので、
    伸びだけでは「兄弟の 4倍 の節が居る」ことが 1度も鳴りません。
    """
    bs = [p for p in ps if p.get("books")]
    if not bs:
        return []
    out = ["**毎周 読むのに、上の 2つ が見ていない 4つ目**（§9 以降のうち **直近の1本**"
           "・冒頭「この文書の読み方」の 4つ目・2026-09-11 06:5x に足した）"]
    # **「いま」は窓の端の blob ではなく作業ツリー**（2026-09-11 05:1x の `worktree_text` の註と同じ）。
    # **この回に踏みました** —— 相手の押しを merge した直後に撃つと、`bs[-1]["books"]`（＝ blob）は
    # **167字 古い数**（24,292）を印字し、実物は 24,125 でした。書いた回に撃つ数は、その回の字であること。
    if now is None:
        try:
            now = measure_books(worktree_text())
        except (KeyError, ValueError):
            now = None
    for sid, c in (now or {}).items():
        out.append(f"  {sid}  いま 本文 **{c['body_chars']:,}字**"
                   "（**作業ツリー** ＝ 押していない直しも入る）")
    last = bs[-1]["books"]
    for p in bs:
        for sid, c in p["books"].items():
            if c["per_lap"] is None:
                out.append(f"  {p['from'].astimezone(JST):%m/%d %H:%M} → {p['to'].astimezone(JST):%m/%d %H:%M} JST"
                           f"   {sid}  **この窓の頭には無い節**（＝ 伸びではなく、書き下ろし {c['now']:,}字）")
            else:
                out.append(f"  {p['from'].astimezone(JST):%m/%d %H:%M} → {p['to'].astimezone(JST):%m/%d %H:%M} JST"
                           f"   {sid}  本文 {c['d']:+,d}字  ＝ 1周 **{c['per_lap']:+.0f}字**")
    # 門は上の 2つ と同じ（1周 +300字・2窓 続いたら）。**節ごとに引きます。**
    drawn = []
    for sid in last:
        tail2 = [p["books"].get(sid) for p in bs[-2:]]
        vals = [c["per_lap"] for c in tail2 if c and c["per_lap"] is not None]
        if len(vals) == 2 and all(v > CHAR_GATE for v in vals):
            drawn.append(f"{sid}（{vals[0]:+.0f} / {vals[1]:+.0f}）")
    if drawn:
        bline = ("**引かれました** —— " + "・".join(drawn) +
                 "。**この節は `hourly` の持ち場**（きょうの枠の本・§5）なので、"
                 "畳むかは hourly が決めること —— optimizer は数を並べるまで")
    elif len(bs[-2:]) < 2:
        bline = too_few_windows(len(bs[-2:]))
    else:
        bline = "引かれません（直近 2窓 とも越えた節は 0 つ）"
    out.append(f"  字の門 1周 +{CHAR_GATE}字: " + bline)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--laps", type=int, default=6, help="1つの窓の周の数（既定 6）")
    ap.add_argument("--points", type=int, default=3, help="並べる窓の数（既定 3）")
    ap.add_argument("--after", default=None, help='窓の頭をこの JST の刻より後に固定（例 "2026-09-10 10:17"）。削りの回を窓に入れないため')
    ap.add_argument("--split", action="store_true", help="門が引かれた回に、どの塊が吸ったかを名指しする")
    a = ap.parse_args()
    after = datetime.strptime(a.after, "%Y-%m-%d %H:%M").replace(tzinfo=JST) if a.after else None
    print(report(a.laps, a.points, after))
    if a.split:
        print(split_report(a.laps, a.points, after))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
