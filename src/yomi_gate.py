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
    R3 台帳     `data/yomi_ledger.json` が `misread` と判定した語が漢字のまま残っている

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

KANJI = r"一-鿿々〇"
_KANJI_RE = re.compile(f"[{KANJI}]")
_KANJI_RUN = re.compile(f"[{KANJI}]+")

#: 発音の欄がこれなら「音にならなかった」。open-jtalk は読めない字を記号にして落とす。
_SILENT = {"", "、", "*", "。"}

#: **数詞は割れて当たり前**（十 ジュッ/ジュー・百 ヒャク/ビャク/ピャク ＝ 連濁と促音便）。
#: これを R1 に数えると、**正しい音便が指摘の 68% を占めます**
#: （2026-09-02 実測: 公開ずみ 31本 で R1/R2 合計 3,397件 のうち **2,301件 が数詞**。
#:  上位10語 は 十 499・百 326・二 303・五 268・千 162・一 152・六 141・八 138・
#:  四 124・七 109 で、**全部 数詞**）。本当の誤読がその中に埋もれます。
_NUMERAL_RE = re.compile(r"^[一二三四五六七八九十百千万億兆〇零]+$")

#: **この符号だけが投稿を止めます。**
#:   R0 その字が音から消えている（無条件に誤り）
#:   R3 耳（本番のエンジン）で誤読と実測ずみ
#: R1（読みが割れる）と R2（1文字に刻まれる）は**耳に何を聞かせるかを決める側**で、
#: **止める側ではありません。** 2026-09-02 に測ったら、R1/R2 を止める側に置くと
#: **公開ずみ 31本 が 31本とも止まりました**（数詞を除いても 1,096件 残り、
#: その大半は 所得税・住民税・医療費 のような、**実際には正しく読めている複合語**）。
#: **投稿が途切れるのが最大の損失**（`CLAUDE.md`「動き方の帰結」4）なので、
#: **証拠のある誤読だけを止め、疑いは耳の待ち行列へ回します。**
#: **覆る条件**: 耳が R1/R2 の語を判定し切って `data/yomi_ledger.json` が
#: 埋まったら、止まるのは R3 に移ります —— そのとき R1/R2 の指摘は自然に減ります。
BLOCKING = ("R0", "R3")


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
        verdict = entry.get("verdict")
        # **「割れた」と「誤読」は別**（2026-09-02 に、両方向の実例を測った）。
        #   額  open-jtalk ガク（正）／ Google ひたい（誤）→ 仮名に置換すると**直る**
        #   行  open-jtalk クダリ（誤）／ Google ぎょう（正）→ 仮名に置換すると**壊れる**
        #       （公開ずみに裸の「行」は **680箇所**。全部 表の行 ＝ ぎょう）
        # 耳が測れるのは「2つのエンジンが割れたか」までで、
        # **どちらが正しいかは言えません。** だから割れただけでは止めません ——
        # 止めるのは、**正しい読み（`correct`）が入って初めて**です。
        # **覆る条件**: 割れた語の 9割 で open-jtalk 側が正しいと実測できたら、
        # 既定を「open-jtalk の読みへ置換」に倒してよい（その根拠を data に残すこと）。
        if verdict in ("misread", "split") and entry.get("correct"):
            found.append({"code": "R3", "surface": s, "pron": pron,
                          "why": f"「{s}」は耳の実測で誤読。正しい読みは "
                                 f"{entry['correct']} —— 仮名に置き換えること"})
            named.add(s)
            continue
        if verdict in ("misread", "split"):
            found.append({"code": "R1", "surface": s, "pron": pron,
                          "why": f"「{s}」は2つのエンジンで読みが割れた"
                                 f"（距離 {entry.get('dist', '?')}）。**どちらが正しいかは"
                                 f"まだ決めていません** —— `correct` を入れるまで止めません"})
            named.add(s)
            continue
        if verdict == "safe":
            continue                        # 耳が通した語はここで終わり
        prons = risk.get(s)
        if prons and len(prons) > 1 and not _NUMERAL_RE.match(s):
            found.append({"code": "R1", "surface": s, "pron": pron,
                          "why": f"「{s}」は文脈で読みが割れる（実測 {'/'.join(sorted(prons))}）。"
                                 f"耳で判定するまで通せない"})
            named.add(s)
    # R2: 漢字の連なりが1文字トークンに刻まれている（辞書に無い並び）
    singles = {t["surface"] for t in toks
               if len(t["surface"]) == 1 and _KANJI_RE.search(t["surface"])}
    joined = "".join(t["surface"] for t in toks)
    for run in _KANJI_RUN.findall(joined):
        if len(run) < 3 or run in named:
            continue
        inside = sorted(c for c in singles if c in run)
        if inside:
            found.append({"code": "R2", "surface": run, "pron": "",
                          "why": f"「{run}」が1文字に刻まれている（{'・'.join(inside)}）。"
                                 f"辞書に無い並びで、エンジンごとに読みが変わる"})
            named.add(run)
    return found


def hits(script: dict, spoken_of=None) -> list[dict]:
    """台本1本ぶんの指摘を、**符号のまま**返す（止める側も、耳へ回す側も）。

    見るのは**読み上げに渡る文字列**（`to_speech()` 済み）です ——
    画面や説明欄の字ではありません。
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
            found = inspect(spoken_of(text), risk, ledger)
        except RuntimeError:
            return []                       # 解析器が動かない環境では黙って通す
        for h in found:
            out.append(dict(h, segment=i + 1))
    return out


def problems(script: dict, spoken_of=None) -> list[str]:
    """**投稿を止める指摘だけ**を返す（`BLOCKING` ＝ R0 と R3）。

    `src/verify.py` が呼ぶのはこちらです。**疑いでは止めません** ——
    2026-09-02 に測ったら、疑い（R1/R2）まで止める側に置くと
    **公開ずみ 31本 が 31本とも止まりました**。止まるのは
    「音から消えた字」と「耳で誤読と実測ずみの語」だけ。
    疑いのほうは `to_measure()` が耳の待ち行列へ渡します。
    """
    return [f"セグメント{h['segment']} {h['code']}: {h['why']}"
            for h in hits(script, spoken_of) if h["code"] in BLOCKING]


def to_measure(script: dict, spoken_of=None) -> list[dict]:
    """**耳に聞かせる候補**（R1/R2）。止めはしないが、放置もしない。

    `scripts/yomi_ear.py` がここを読んで、本番のエンジンに当てます。
    当たった結果は `data/yomi_ledger.json` に入り、`misread` なら
    次の回から R3 として**止まります**。
    """
    return [h for h in hits(script, spoken_of) if h["code"] not in BLOCKING]
