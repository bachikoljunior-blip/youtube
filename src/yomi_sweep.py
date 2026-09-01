"""**台本の全部の漢字**に読みの検算を当てる（オーナー固定その3・1つ目）。

    「ナレーションの漢字の読み方全部正しくして」（2026-09-02・原文）

## この道具が要る理由 —— 語を1つずつ直す形をやめる

2026-08-16、オーナーが動画を**耳で**聞いて「額」が「ひたい」と読まれているのを
見つけました。そのとき直したのは**裸の「額」1語だけ**（`src/yomi.FIXES`）。
**1語ずつ直す形では、次の語は次にオーナーが聞くまで見つかりません。**

だからここは**語を指定しません。** 台本（または公開済みの台本 694本）に出る
**漢字を含む語を全部**取り、そのうち**読みが割れうる語だけ**を本番のエンジンに
当てます。

## 何が測れて、何が測れないか（**ここを間違えると、直っていない語が直った顔をします**）

    open-jtalk（`scripts/check_yomi.py`）  無料・毎回撃てる。**本番のエンジンではない**
    Google TTS（`scripts/probe_yomi.py`）  本番と同じ声。**候補を2つ以上 渡さないと測れない**

**2026-09-02 に、この2つが逆向きに外れる例を両方 踏みました:**

    額  open-jtalk は全文脈で ガク。**Google が ひたい**（＝ open-jtalk では見つからない）
    行  open-jtalk は「この行」を **クダリ**。**Google は ぎょう**（＝ open-jtalk の
        言うことをそのまま直すと、合っている語を壊す）

**＝ open-jtalk の読みは「正解」ではなく「候補の出どころ」です。**
この道具は open-jtalk を**候補を作るためだけ**に使い、**判定は必ず Google TTS**で
やります（`probe_yomi.probe()` の相対比較。**絶対値のしきい値は効きません** ——
実測で合っている側 0.239〜0.350、外れている側 0.335〜0.731 と**重なります**）。

## 候補をどこから作るか（**手で並べないこと。それが「1語ずつ」そのものです**）

**自分の台本の中で、同じ語が別々に読まれている所**を候補にします。
公開済み 694本・6,206行 を open-jtalk に通すと、
**数詞を除いて 10語**が2通り以上に読まれていました（2026-09-02 実測）:

    年 ネン/トシ   日 ニチ/ヒ/ビ   人 ヒト/ニン   分 ブン/フン/プン
    行 クダリ/ギョー   上 ウエ/ジョー   方 カタ/ホー   下 シタ/カ
    高 タカ/コー   後 ゴ/アト

**候補が1つしか出ない語は、この道具では判定できません**（＝「額」がここで
見つからなかった理由）。**それは「合っている」ではなく「測っていない」です。**
`sweep()` は数を分けて返すので、**その差を隠さないこと。**

## 覆る条件

**単語ごとに複数の読みを持つ辞書が手元に入ったら**（いまの `naist-jdic` は
コンパイル済みで読み出せません）、候補は自分の台本ではなく辞書から作ること ——
そうすれば「額」の類（自分の台本では割れない語）も測れるようになります。
そこまでは、**測れた語と測れていない語の件数を毎回 並べて出すこと。**
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KANJI = re.compile(r"[一-鿿々]")
#: 数詞は**割れて当たり前**です（十 ジュッ/ジュー・百 ヒャク/ビャク/ピャク ＝ 連濁・促音便）。
#: ここを候補に入れると、正しい音便が「読みが割れている」として毎回 出ます。
NUMERAL = re.compile(r"^[一二三四五六七八九十百千万億兆〇零]+$")
#: 判定の結果を積む所。**次の回はこれを読んで、同じ語を測り直しません。**
LEDGER = ROOT / "data" / "yomi_engine.jsonl"


def _kata_to_hira(kana: str) -> str:
    """候補の文に差し込むのは平仮名。**片仮名のままでも音は同じ**だが、
    `probe_yomi` の既存の記録（がく／ひたい）と字を揃えておく。"""
    out = []
    for ch in kana.replace("’", ""):
        code = ord(ch)
        out.append(chr(code - 0x60) if 0x30A1 <= code <= 0x30F6 else ch)
    return "".join(out)


def corpus_lines(paths: list[Path] | None = None) -> list[str]:
    """公開済みの台本の地の文。`data/critique_queue/*.json` の `narration`。"""
    lines: list[str] = []
    for path in sorted((paths if paths is not None else
                        (ROOT / "data" / "critique_queue").glob("*.json"))):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for line in data.get("narration") or []:
            if isinstance(line, str) and line.strip():
                lines.append(line.strip())
    return lines


def script_lines(path: Path) -> list[str]:
    """台本1本ぶんの地の文（`segments[].narration`）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [str(s.get("narration") or "").strip()
            for s in data.get("segments", []) if str(s.get("narration") or "").strip()]


def readings_of(lines: list[str], batch: int = 40):
    """(語 → 読み → 件数) と、読みごとの例文を返す。**open-jtalk・API 0単位。**"""
    from scripts.check_yomi import readings

    occ: dict[str, Counter] = defaultdict(Counter)
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    for i in range(0, len(lines), batch):
        chunk = lines[i:i + batch]
        try:
            tokens = readings("\n".join(chunk))
        except Exception:
            continue
        # 行の境目は、表層形を先頭から食べて追う（open-jtalk は改行を落とす）。
        li, pos = 0, 0
        for surface, kana in tokens:
            while li < len(chunk) and pos >= len(chunk[li]):
                li, pos = li + 1, 0
            cur = chunk[li] if li < len(chunk) else ""
            if cur[pos:pos + len(surface)] == surface:
                pos += len(surface)
            else:
                found = cur.find(surface, pos)
                pos = found + len(surface) if found >= 0 else pos
            if KANJI.search(surface):
                key = kana.replace("’", "")
                occ[surface][key] += 1
                if cur and len(examples[(surface, key)]) < 2:
                    examples[(surface, key)].append(cur)
    return occ, examples


def split_words(occ: dict[str, Counter]) -> tuple[dict[str, Counter], list[str]]:
    """**測れる語**（読みが2通り以上・数詞でない）と、**測れない語**に分ける。

    「測れない」は「合っている」ではありません —— 候補が1つしか無いので
    相対比較ができない、という意味です（`額` がここに落ちます）。
    """
    testable = {s: c for s, c in occ.items() if len(c) > 1 and not NUMERAL.match(s)}
    untestable = [s for s in occ if s not in testable and not NUMERAL.match(s)]
    return testable, untestable


def sweep(lines: list[str], limit_per_word: int = 2, verbose: bool = True) -> dict:
    """**本番のエンジンに当てる。** 戻りは判定の一覧。

    語ごとに、読みが割れている**それぞれの読みの例文**を取り、
    その文の中でその語がどの候補で読まれているかを Google TTS で測ります
    （`probe_yomi.probe()`）。**open-jtalk の言うほうが負けたら、
    open-jtalk のほうが外れています**（`行` がその例）——
    だから「負けた」だけでは誤読と呼びません。**誤読と呼ぶのは、
    その文脈で意味の通らない読みが勝ったときだけ**で、その判断は
    `data/yomi_engine.jsonl` に人が読める形で残します。
    """
    from scripts.probe_yomi import probe

    occ, examples = readings_of(lines)
    testable, untestable = split_words(occ)
    results = []
    for surface, counter in sorted(testable.items(), key=lambda kv: -sum(kv[1].values())):
        cands = [_kata_to_hira(k) for k in counter]
        for kana, _n in counter.most_common():
            for sentence in examples[(surface, kana)][:limit_per_word]:
                index = sentence.find(surface)
                if index < 0:
                    continue
                # **通信は落ちます**（2026-09-02 実測: 40件 めで
                # `Response ended prematurely`）。落ちるたびに総当たりが
                # 丸ごと消えると、**測り終わる回が永久に来ません。**
                # 合成の結果は `build/yomi_cache/` に残るので、
                # 撃ち直しても課金は増えません。
                scored = None
                for attempt in range(3):
                    try:
                        scored = probe(sentence, surface, cands, at=index)
                        break
                    except Exception as exc:
                        last = str(exc)
                        if verbose:
                            print(f"    [再試行 {attempt + 1}/3] {surface}: {last[:60]}")
                if scored is None:
                    results.append({"surface": surface, "open_jtalk": _kata_to_hira(kana),
                                    "engine": None, "gap": None, "agree": None,
                                    "sentence": sentence[:80], "error": last})
                    continue
                best, second = scored[0], scored[1]
                row = {
                    "surface": surface,
                    "open_jtalk": _kata_to_hira(kana),
                    "engine": best[1],
                    "gap": round(second[0] - best[0], 4),
                    "agree": best[1] == _kata_to_hira(kana),
                    "sentence": sentence[:80],
                }
                results.append(row)
                if verbose:
                    mark = "一致" if row["agree"] else "**割れた**"
                    print(f"{mark}  {surface}  open-jtalk={row['open_jtalk']} "
                          f"／ 本番={row['engine']}（差 {row['gap']:.3f}）  {sentence[:40]}")
    return {"testable": len(testable), "untestable": len(untestable), "results": results}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--scan-only" in argv
    argv = [a for a in argv if a != "--scan-only"]
    lines = script_lines(Path(argv[0])) if argv else corpus_lines()
    print(f"=== 読みの総当たり（地の文 {len(lines)}行）===")
    occ, examples = readings_of(lines)
    testable, untestable = split_words(occ)
    print(f"  漢字を含む語 {len(occ)}種  → **読みが割れている語 {len(testable)}種**"
          f"／割れていない語 {len(untestable)}種（**測れない ＝ 合っているではない**）")
    for surface, counter in sorted(testable.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"    {surface}  {dict(counter)}")
    if dry:
        return 0
    out = sweep(lines)
    if out.get("error"):
        print(f"[sweep] 本番のエンジンに当てられませんでした: {out['error']}")
        return 2
    split = [r for r in out["results"] if not r["agree"]]
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        for row in out["results"]:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"  測った {len(out['results'])}件 のうち、**2つのエンジンが割れた {len(split)}件**")
    print(f"  → {LEDGER}（次の回はここを読むこと。同じ語を測り直さない）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
