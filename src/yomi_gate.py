"""読みの門 —— **語を1つずつ直す形をやめるための層**（2026-09-02）。

## なぜ要るか（オーナー原文・`CLAUDE.md` 固定その3）

> **「ナレーションの漢字の読み方全部正しくして」**

2026-08-16、オーナーが耳で「額」が「ひたい」と読まれているのを見つけた。
そのとき直したのは**裸の「額」1語だけ**（`src/yomi.FIXES`）。

**この回に数えた: 公開ずみ 694本・読み上げ 6,206行・漢字のかたまり 異なり 3,514語。
そのうち `src/verify._check_yomi` が見ていた語は 1語（0.03%）。**
残り 3,513語 は**誰も見ていない**。「全部正しくして」に対して 0.03% は最適化ではない。

## この層が変えること —— 既定を反転する

古い形: **既知の壊れる語を並べて、それが残っていたら落とす**（`BROKEN_SHAPES`）。
        → 並べていない語は**無検査で通る**。語を足すまで直らない。

この層: **読み上げに出る漢字を全部 形態素解析にかけ、危ない形を機械が名指しする**。
        → 語の一覧は要らない。**危ない条件のほうを書く。**

## 危ない条件（語の一覧ではなく、形で決めている）

    R0 落ちる   漢字なのに発音が空 or 「、」 ＝ **その字は音から消える**（無条件で落とす）
    R1 割れる   同じ表層が文脈で別の発音になる ＝ **エンジン間でも割れうる**
    R2 刻まれる 漢字の連なりが1文字トークンに刻まれている ＝ 辞書に無い並び
    R3 台帳     耳が誤読と判定し**正しい読みまで記録した**語が、漢字のまま残っている
                （＝ `src/yomi.to_speech()` の自動置換が効いていない、という警報）

R1 の「割れる」は**この repo の読み上げ 6,206行を実際に通して測った**もので
（`scripts/yomi_audit.py` → `data/yomi_risk.json`）、推測ではない。

## 何が確かめられて、何が確かめられないか（**ここを混ぜないこと**）

open-jtalk は**本番のエンジンではない**。本番は Google Cloud TTS。
この回に撃って確かめた: **open-jtalk は「実際の額は…」を ガク と読む** ——
つまり**オーナーが実際に踏んだ誤読を、open-jtalk は再現できない。**
`scripts/check_yomi.py` が「合格」と言っていたのは、`to_speech()` が先に仮名へ
置換していたからで、**門が誤りを見つけたのではない。**

だから**判定するのは耳のほう**（`scripts/probe_yomi.py`）。この層は
**耳に何を聞かせるかを決める**（＝候補を全語から漏れなく作る）役で、
最終判定は `data/yomi_ledger.json` に入る。

**覆る条件**: R1/R2 で名指しした語のうち、耳で測って `safe` の割合が
9割を超えたら、その条件は候補として粗すぎる（絞り込みを足すこと）。
逆に耳が `misread` と言った語が R0〜R2 のどれにも掛からなかったら、
**条件が足りていない**（その形を足すこと）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICT = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE = "/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice"

RISK_PATH = ROOT / "data" / "yomi_risk.json"
LEDGER_PATH = ROOT / "data" / "yomi_ledger.json"

#: 漢字の範囲。**基本多言語面だけでは足りない** —— 2026-09-02 に実測で踏んだ:
#: 「𠮟」（U+20B9F・拡張B面）は open-jtalk が記号にして**音から落とす**のに、
#: `一-鿿` では1文字も掛からず、R0 が素通りしていた。互換漢字面も入れてある。
KANJI = "\u4e00-\u9fff\u3005\u3007\uf900-\ufaff\U00020000-\U0002a6df"
_KANJI_RE = re.compile(f"[{KANJI}]")
_KANJI_RUN = re.compile(f"[{KANJI}]+")

#: 発音の欄がこれなら「音にならなかった」。open-jtalk は読めない字を記号にして落とす。
_SILENT = {"", "、", "*", "。"}


def available() -> bool:
    return bool(shutil.which("open_jtalk")) and Path(DICT).exists() and Path(VOICE).exists()


#: **1回の解析で返ってくるトークンの上限**（2026-09-02 に実測）。
#: これを超える入力は、**エラーも警告も無しに切り落とされます** ——
#: 40文字 を 12回 つないだ 491文字 で 326 に張り付き、983文字 でも 326 のまま。
#: **「解析した」と「全部 解析した」は別**なので、`analyze()` は
#: 自分で切って回します（下）。**ここを撤去すると、長い段は黙って無検査になります。**
MAX_TOKENS = 326
#: 切る幅。上限の 326トークン に対し、日本語は 1文字 ≒ 0.9トークン なので余裕を見る。
CHUNK_CHARS = 240


def _analyze_one(one: str) -> list[dict]:
    """**切らずに1回だけ**解析する。呼ぶのは `analyze()` から。"""
    if not one:
        return []
    with tempfile.TemporaryDirectory() as td:
        trace = Path(td) / "trace.txt"
        proc = subprocess.run(
            # `-r 5.0` は**話速**。ここで要るのは形態素の表だけで、
            # 書かせた wav は捨てます —— 速く喋らせるほど合成が短く済み、
            # **表は1トークンも変わりません**（2026-09-02 実測: 既定 1.77秒 →
            # 0.63秒（**2.8倍**）、どちらもトークン 215件 で一致。
            # `-r 20` `-r 100` にしても 0.63秒 で頭打ち）。
            # `-s`（サンプリング周波数）は効きません（1.78秒）。
            # **覆る条件**: ここが書いた wav を使う日が来たら、この旗を外すこと。
            ["open_jtalk", "-x", DICT, "-m", VOICE, "-r", "5.0",
             "-ot", str(trace), "-ow", str(Path(td) / "o.wav")],
            input=one.encode("utf-8"), capture_output=True,
        )
        if proc.returncode != 0 or not trace.exists():
            raise RuntimeError(
                f"open_jtalk 失敗: {proc.stderr.decode('utf-8', 'ignore')[:200]}")
        out: list[dict] = []
        # **`read_text()` で丸ごと読まないこと**（2026-09-02 に踏んだ）。
        # トレースは 40文字 の入力でも **339KB**、327文字 で **2.7MB** あり、
        # 頭の「形態素の表」より下は音響パラメータで、**UTF-8 でない並びが
        # 混ざります** —— 丸ごと decode すると
        # `'utf-8' codec can't decode byte ...` を投げ、`analyze()` は
        # `RuntimeError` ではなく `UnicodeDecodeError` で落ちます。
        # 実測: 300文字 を超える入力は**全部これで落ちていました**
        # （＝ 複数行をまとめて解析する道が塞がっていた）。
        # 要るのは最初の空行までなので、**そこで読むのをやめる。**
        with trace.open("rb") as fh:
            for raw in fh:
                line = raw.decode("utf-8", "ignore")
                if not line.strip():
                    break                  # 空行から先は音響パラメータ
                f = line.rstrip("\r\n").split(",")
                if len(f) < 10:
                    continue               # "[Text analysis result]" の見出し
                out.append({"surface": f[0], "pos": f[1], "pos2": f[2],
                            "base": f[7], "yomi": f[8], "pron": f[9].replace("’", "")})
        return out


def analyze(text: str) -> list[dict]:
    """テキストを形態素解析して、トークンごとの (表層, 品詞, 読み, 発音) を返す。

    **open-jtalk は入力の1行目しか解析しない**ので改行を潰し、
    **1回に 326トークン までしか返さない**ので `CHUNK_CHARS` ごとに切って回す。
    どちらも 2026-09-02 の実測で、**黙って落ちる**種類の欠け方です。
    """
    one = " ".join(text.splitlines()).strip()
    if not one:
        return []
    if len(one) <= CHUNK_CHARS:
        return _analyze_one(one)
    out: list[dict] = []
    for start in range(0, len(one), CHUNK_CHARS):
        out += _analyze_one(one[start:start + CHUNK_CHARS])
    return out


def analyze_many(lines: list[str], chunk_chars: int = CHUNK_CHARS) -> list[dict]:
    """**複数行をまとめて**解析する。台本1本や公開ずみ全文を通すのはこちら。

    **速くはなりません。** 2026-09-02 に測りました —— 48行 を
    まとめて 14.5秒 対 行ごと 14.9秒（**3%**）。
    重さは呼び出しの回数ではなく**文字数**に乗っています（open_jtalk は
    表を出すついでに音声も合成するため）。**速くしたいなら `-r`**
    （`_analyze_one` の註。実測 2.8倍）。
    ここが返すのは、行の切れ目を気にせず全部のトークンを並べたものです。
    """
    out: list[dict] = []
    buf: list[str] = []
    size = 0
    for line in lines:
        one = " ".join(str(line).splitlines()).strip()
        if not one:
            continue
        if size + len(one) > chunk_chars and buf:
            out += _analyze_one("　".join(buf))
            buf, size = [], 0
        buf.append(one)
        size += len(one) + 1
    if buf:
        out += _analyze_one("　".join(buf))
    return out


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_risk() -> dict:
    """`scripts/yomi_audit.py` が公開ずみ全文から作った「割れる語」の表。"""
    return _load(RISK_PATH).get("split", {})


def load_ledger() -> dict:
    """耳（`scripts/probe_yomi.py`）が出した語ごとの判定。"""
    return _load(LEDGER_PATH).get("words", {})



def _kanji_only(surface: str) -> bool:
    return bool(surface) and not re.sub(f"[{KANJI}]", "", surface)


def _numeral(tok: dict) -> bool:
    """1文字の数詞。**読みが文脈で変わるのが正しい振る舞い**なので R1 から外す。

    実測（2026-09-02）: 十五 は ジュー、十歳 は ジュッ —— **どちらも正しい。**
    後ろの助数詞で決まる連濁・促音を「割れている」と数えると、
    1本ぶんの名指しが **168件** になり、その **9割が数詞** で埋まって
    本当に危ない語が読めなくなる（実測で踏んだ）。
    **数詞そのものの読み違いは R1 ではなく耳（`scripts/yomi_ear.py`）が見る。**

    **覆る条件**: 耳が数詞の誤読を実際に捕まえたら、その形をここへ戻すこと。
    """
    return tok.get("pos2") == "数" and len(tok.get("surface", "")) == 1


def _glue(tok: dict) -> bool:
    """接頭辞・接尾辞・数詞。**1文字なのが正常**なので R2 の合図にしない。

    「医療＋費」「百万＋円」は辞書どおりの切れ方で、辞書に無い並びではない。
    """
    return tok.get("pos") in ("接頭詞",) or tok.get("pos2") in ("接尾", "数")


def inspect(text: str, risk: dict | None = None, ledger: dict | None = None) -> list[dict]:
    """1行ぶんの危ない形を返す。**語の一覧ではなく、形で決めている。**

    返すのは `{"code","surface","pron","why"}` の並び。空なら危ない形は無い。
    """
    risk = load_risk() if risk is None else risk
    ledger = load_ledger() if ledger is None else ledger
    toks = analyze(text)
    found: list[dict] = []
    named: set[str] = set()
    for t in toks:
        s = t["surface"]
        if not _KANJI_RE.search(s):
            continue
        pron = t["pron"]
        if pron in _SILENT:
            found.append({"code": "R0", "surface": s, "pron": pron,
                          "why": f"「{s}」が音にならない（発音の欄が空）"})
            named.add(s)
            continue
        entry = ledger.get(s) or {}
        if entry.get("verdict") == "misread" and entry.get("correct"):
            found.append({"code": "R3", "surface": s, "pron": pron,
                          "why": f"「{s}」は耳の実測で誤読。"
                                 f"「{entry['correct']}」に置換されるはずが漢字のまま残っている "
                                 f"（src/yomi.to_speech が台帳を読めていない）"})
            named.add(s)
            continue
        if entry.get("verdict") == "safe":
            continue                        # 耳が通した語はここで終わり
        prons = risk.get(s)
        if _numeral(t):
            continue                        # 下の註を見ること
        if prons and len(prons) > 1:
            found.append({"code": "R1", "surface": s, "pron": pron,
                          "why": f"「{s}」は文脈で読みが割れる（実測 {'/'.join(sorted(prons))}）。"
                                 f"耳で判定するまで通せない"})
            named.add(s)
    # R2: 漢字の連なりが1文字トークンに刻まれている（辞書に無い並び）。
    # **隣り合うトークンの並びで見ること** —— 行のどこかに在る1文字を
    # 文字列として当てにいくと、別の場所の字が別の熟語の中に「見つかって」しまう
    # （2026-09-02 に実測: 「賃金日額」が、行の別の場所の「額」で名指しされていた）。
    group: list[dict] = []
    for t in list(toks) + [{"surface": "", "pos": "", "pos2": "", "pron": ""}]:
        if t["surface"] and _kanji_only(t["surface"]):
            group.append(t)
            continue
        if len(group) >= 2:
            run = "".join(g["surface"] for g in group)
            inside = [g["surface"] for g in group
                      if len(g["surface"]) == 1 and not _glue(g)]
            if len(run) >= 3 and run not in named and inside:
                found.append({"code": "R2", "surface": run, "pron": "",
                              "why": f"「{run}」が1文字に刻まれている（{'・'.join(inside)}）。"
                                     f"辞書に無い並びで、エンジンごとに読みが変わる"})
                named.add(run)
        group = []
    return found


def problems(script: dict, spoken_of=None) -> list[dict]:
    """台本1本ぶん。**読み上げに渡る文字列**（`to_speech()` 済み）を見る。

    返すのは `inspect()` の当たりに `seg`（何番目のセグメントか）を足したもの。
    **文字列ではなく形のまま返す** —— 呼ぶ側が「落とす／積む」を分けるとき、
    `code` と `surface` が要るからです（文字列から切り出すと、
    表現を変えた瞬間に静かに壊れます）。
    """
    if not available():
        return []
    from .yomi import to_speech
    spoken_of = spoken_of or to_speech
    risk, ledger = load_risk(), load_ledger()
    out: list[dict] = []
    for i, seg in enumerate(script.get("segments", []) or []):
        text = str(seg.get("narration") or "")
        if not text.strip():
            continue
        try:
            hits = inspect(spoken_of(text), risk, ledger)
        except RuntimeError:
            return []                       # 解析器が動かない環境では黙って通す
        for h in hits:
            out.append(dict(h, seg=i + 1))
    return out


def say(hit: dict) -> str:
    """当たり1件を1行にする。**表示の形はここ1か所。**"""
    return f"セグメント{hit.get('seg', 0)} {hit['code']}: {hit['why']}"

QUEUE_PATH = ROOT / "data" / "yomi_queue.json"


def queue(hits: list[dict]) -> None:
    """落とさない名指し（R1/R2）を積む。**耳に回す入口はここ1つ。**

    落とさない代わりに、**必ず残す**。残さなければ「全語を見た」は口だけになる。
    `scripts/yomi_ear.py` がここを読んで、上から判定していく。
    """
    blob = _load(QUEUE_PATH)
    seen = dict(blob.get("open", {}))
    for hit in hits:
        key = f"{hit['code']}\t{hit['surface']}"
        row = seen.get(key) or {}
        seen[key] = {"code": hit["code"], "surface": hit["surface"],
                     "why": hit["why"], "n": int(row.get("n", 0)) + 1}
    # **判定ずみの語を待ち行列に残さないこと。** 耳が safe と言った語は
    # `inspect()` がもう名指ししないので、ここに残っていると
    # `status.py` が**いつまでも古い名前を出し続けます**（積むだけで減らない表は、
    # 読まれなくなって、積んでいないのと同じになります）。
    done = {w for w, e in load_ledger().items() if e.get("verdict") == "safe"}
    seen = {k: v for k, v in seen.items() if v.get("surface") not in done}
    body = json.dumps({"at": _now(), "open": seen}, ensure_ascii=False, indent=1)
    # **`batch_build` は並列に走る。** そのまま write_text すると、
    # 別の工程が途中まで書かれた JSON を読む（`_load` が握り潰して空扱いにする ＝
    # 名指しが黙って消える）。一時ファイルに書いて rename すれば、
    # 読み手が見るのは常に「前の版」か「次の版」のどちらかになる。
    tmp = QUEUE_PATH.with_suffix(f".{os.getpid()}.tmp")
    try:
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(QUEUE_PATH)
    finally:
        if tmp.exists():
            tmp.unlink()


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def corrections() -> dict:
    """耳が「誤読」と判定し、**正しい読みまで記録できた**語だけを返す。

    **1文字の語はここから外してあります**（2026-09-02 に踏んだ）。1文字の漢字は
    活用語幹でもあるので、前後が漢字でない出現だけに絞っても足りません ——
    「重」→ ジュー は「重課」を避けられても**「重い」を「ジューい」にします。**
    1文字の誤読は `src/yomi.FIXES` に**文脈つきの正規表現**で入れること
    （「額」がそうなっています。`scripts/check_yomi.py` が巻き込みを毎回 検算します）。

    距離が離れているだけでは、**どちらのエンジンが正しいかは分からない**
    （2026-09-02 の実測: 「額」は open-jtalk が正しく Google が誤り、
    「年」は逆に open-jtalk が トシ と読み Google のほうが正しい）。
    **だから距離だけで自動置換しないこと。** ここが返すのは、
    `correct` の欄まで埋まった語 ＝ **向きまで確かめた語**だけ。
    """
    return {w: e["correct"] for w, e in load_ledger().items()
            if e.get("verdict") == "misread" and e.get("correct") and len(w) >= 2}


def apply_corrections(text: str, table: dict | None = None) -> str:
    """台帳の置換を当てる。**熟語の中の1字を巻き込まないこと。**

    素の `str.replace()` で当ててはいけません（2026-09-02 に気づいて塞いだ）——
    たとえば「重」を ジュー に置き換えると、**「重い」が「ジューい」**になります。
    `src/yomi.FIXES` の「額」が最初から
    `(?<![漢字])額(?![漢字])` と書いてあるのは同じ理由です。

    だからここは**前後が漢字でない出現だけ**を置き換えます。
    熟語の中の誤読は、仮名1字の差し替えでは直りません
    （直すなら熟語ごと。そちらは `data/yomi_queue.json` に残して、
    次の回が語ではなく**熟語**として台帳に入れること）。
    """
    table = corrections() if table is None else table
    for word, kana in table.items():
        text = re.sub(f"(?<![{KANJI}]){re.escape(word)}(?![{KANJI}])", kana, text)
    return text
