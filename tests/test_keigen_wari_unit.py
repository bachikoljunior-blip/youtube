"""**`軽減の割合` はパーセントです。「割」で刷るなら10で割ること。**

2026-08-18 の1日で、同じ字が**2回**出ました。

    08/18 00:4x  `src/calc/kokuho.py`      `70割 → 50割`
    08/18 02:0x  `src/calc/ninikeizoku.py` `50割 → 20割`

**1回目の直しは、そのファイルの中で終わりました**（`f"{before // 10}割"` に
書き換えただけ）。**借りる側には何も伝わらないので、同じ日に再生産されました。**

そして**どちらも、値を見る検査は1件も落ちていません** —— 保険料も境目も
崖の高さも全部正しく、**違うのは字だけ**だからです。前の回の申し送りは
これを「**字を見る検査が無い**」と書いて終わっていました。ここがその検査です。

## 何を見ているか

`src/calc/*.py` と `scripts/*.py` の**ソースの字**を読み、次の形を落とします。

    その関数が「軽減の割合」（＝ パーセント）を読んでいる
    かつ その関数の中に `{式}割` という書き方がある
    かつ その式が 10 で割っていない

**関数の単位で見ています。** `kokuho` の実物は
`before = ...["軽減の割合"]` → `f"{before}割"` の形で、**変数名には
「軽減」の字が1つも入っていません。** 名前で探すやり方では捕まりません。

## この検査が捕まえないもの（**承知のうえです**）

- 関数をまたいで値を渡した場合（読む所と刷る所が別の関数）
- `割` ではなく「割合」「パーセント」と刷って単位を間違えた場合
- ソースにない経路（テンプレート、台本の書き手が作る文）

**それでも、実際に2回出た形はちょうどこれです。**
広げるのは3件目が別の形で出てからにすること
（`src/alerts.py` の「当たりを含まないまま育つ一覧」を増やさないため）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# その関数がパーセントの軽減を読んでいる印
READS_KEIGEN = ("軽減の割合", "keigen_rate(", "KEIGEN_STEPS")

# `{式}割` —— f-string の中で、閉じ括弧のすぐ後ろに「割」が来る書き方。
# 書式指定（`{x:,}割` など）も拾う。
WARI = re.compile(r"\{([^{}]+)\}割")

# 10 で割っている印。`// 10` `/ 10` `//10` `/10` と、割ってから渡した名前
DIVIDED = re.compile(r"//\s*10\b|/\s*10\b|_wari\b|割にした")


def source_files() -> list[Path]:
    files = sorted((ROOT / "src" / "calc").glob("*.py"))
    files += sorted((ROOT / "scripts").glob("*.py"))
    files += sorted((ROOT / "src").glob("*.py"))
    return [p for p in files if p.name != Path(__file__).name]


def offenders_in(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if "軽減" not in text:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover - ソースは常に読めるはず
        return []

    lines = text.splitlines()
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.Module)):
            continue
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", len(lines))
        if isinstance(node, ast.Module):
            # モジュール直下（`if __name__ == "__main__":` の中）も見る。
            # **`kokuho` の節はここに書かれています。**
            body = "\n".join(
                l for l in lines
                if not l.startswith(("def ", "async def ", "class ")))
        else:
            body = "\n".join(lines[start - 1:end])

        if not any(m in body for m in READS_KEIGEN):
            continue
        for line in body.splitlines():
            for expr in WARI.findall(line):
                if DIVIDED.search(expr):
                    continue
                # 制度の名前そのもの（「7割軽減」など）は式ではない
                if expr.strip().isdigit():
                    continue
                if not _is_percent_source(expr, body):
                    continue
                bad.append(f"{path.relative_to(ROOT)}: {line.strip()}")
    return sorted(set(bad))


# **式そのものがパーセントを指している**印。
# `軽減の割合` を直に読む形と、`pct` のように名前が単位を言っている形。
PERCENT_EXPR = re.compile(r"軽減の割合|keigen_rate\(|\bpct\b|\bpercent\b"
                          r"|パーセント|割合")


def _is_percent_source(expr: str, body: str) -> bool:
    """その式が「パーセントの値」か。**関数の中だけを見ます。**

    ここを入れないと、**producer 側で既に10で割った値**まで落とします
    （`ninikeizoku.jump_at_crossover` は `手前の軽減` を「割」で返すので、
    刷る側に `// 10` はありません。**それは正しい書き方です**）。
    """
    if PERCENT_EXPR.search(expr):
        return True
    # `before = ...["軽減の割合"]` のように、同じ関数の中で
    # パーセントから代入された裸の名前。**kokuho の実物がこの形でした。**
    name = expr.strip()
    if not name.isidentifier():
        return False
    assigned = re.compile(
        rf"\b{re.escape(name)}\s*=[^\n]*(軽減の割合|keigen_rate\()")
    return bool(assigned.search(body))


@pytest.mark.parametrize("path", source_files(), ids=lambda p: p.name)
def test_軽減の割合を割で刷るなら10で割っていること(path: Path):
    bad = offenders_in(path)
    assert not bad, (
        "**`軽減の割合` はパーセントです**（7割軽減 → 70）。"
        "「割」で刷るなら10で割ること。2026-08-18 に2回出ました:\n  "
        + "\n  ".join(bad))


def test_この検査が壊れた字を実際に捕まえる(tmp_path):
    """**発火したことのない検査は検査ではありません。** 故障を注入する。"""
    bad_src = (
        'def cliff():\n'
        '    before = premium()["軽減の割合"]\n'
        '    after = premium()["軽減の割合"]\n'
        '    return f"{before}割 → {after}割"\n'
    )
    p = tmp_path / "broken.py"
    p.write_text(bad_src, encoding="utf-8")
    # 相対パスの計算だけ ROOT に頼っているので、そこは直に呼ぶ
    text = p.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = "\n".join(lines[node.lineno - 1:node.end_lineno])
        if not any(m in body for m in READS_KEIGEN):
            continue
        for line in body.splitlines():
            found += [e for e in WARI.findall(line)
                      if not DIVIDED.search(e) and _is_percent_source(e, body)]
    assert found == ["before", "after"], found


def test_producer_側で割った値は落とさない():
    """**10で割るのは、刷る所とはかぎりません。**

    `ninikeizoku.jump_at_crossover` は「割」の欄と「パーセント」の欄を
    別に返すので、刷る側に `// 10` はありません。**それが正しい形**です。
    ここを落とすと、正しいコードで鳴る一覧になり、次の回が黙らせます。
    """
    body = ('j = jump_at_crossover(m)\n'
            'print(f"軽減が {j[\'手前の軽減\']}割 → {j[\'そこでの軽減\']}割")\n')
    exprs = [e for line in body.splitlines() for e in WARI.findall(line)]
    assert exprs, "そもそも {式}割 を拾えていない"
    assert not any(_is_percent_source(e, body) for e in exprs)


def test_正しく書いてあれば通る():
    """`kokuho` の直したあとの形（`{before // 10}割`）は落ちないこと。"""
    assert WARI.findall('f"{before // 10}割 → {after // 10}割"') == [
        "before // 10", "after // 10"]
    assert all(DIVIDED.search(e)
               for e in WARI.findall('f"{before // 10}割 → {after // 10}割"'))
