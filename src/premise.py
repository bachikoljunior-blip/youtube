"""**節が「画面に出しようがない前提」に条件づけられていないか。**

## なぜ要るか（2026-08-17。**独立評価の指摘を測って入れた**）

`J0QK59pUg-4`（iDeCo・最後の1段は15.1%）に、3体のうち1体がこう書きました ——

> **半分しか信じられない。** 前提は画面に出てはいるが、
> **肝心の年収（課税所得）が一度も画面に出ていない。**
> 20.2%→15.1% の落ち方は所得税率の境目に乗るかどうかで決まるので、
> 年収が分からないと検証も自分への当てはめもできない。

実物を見ると、**台本の書き手が悪いのではありませんでした。**

    print("\\n=== 掛金の最後の1万2000円は、…安く効く年収がある ===")
    for row in last_step(4_600_000):          # ← 年収。**表の全部がこれで決まる**
        print(f"  累計{row['掛金の累計']:>8,}円  この1段 …")   # ← どの行にも出ない

`last_step()` が返す行は `掛金の累計 / 節税額 / この1段ぶん / この1段の効き` だけで、
**4,600,000 はどこにも出ません。** ASSUMPTIONS にも年収は入っていない。
つまり**書き手は、出そうにも持っていなかった。**

これは `CLAUDE.md` の根幹に直接あたります ——

> **前提と計算式を、画面と説明欄に全部出す。**
> 視聴者が自分で追試できることがテンプレート量産との違いになります。

答えを決めている値が画面に無い節は、**追試できません。**
「独自の計算を発表する」が「どこから来たか分からない数字」に落ちます。

## 見るもの（**節ごと**に見る。stdout 全体ではない）

`topic_forge` はテーマを**節の単位**で切ります。1節＝1本です。
だから「stdout のどこかには出ている」では足りません ——
別の節に出ていても、**その動画を書く側には関係がありません。**
実際 `ideco` の 4,600,000 は別の節（`grid()` の年収の列）には出ており、
**stdout 全体で見ると素通りします。** 節で見て初めて当たります。

拾うのは **`__main__` の中で、表を作る呼び出しに渡された数のリテラル**です。

- **変数を1つ挟んでも追います。** `base = Wage(base=250_000)` のように
  節の外で束ねてから使う書き方が実際にあり（`zangyo`）、
  直接の引数だけ見ると**取り逃がします**
- **1000未満は見ません。** 年・月数・人数・区分番号が大半で、当たりが薄い

## 実測（2026-08-17・calc 24本 / 節 91件）

    節で見る        **2件**   ideco 4,600,000 ／ zangyo 250,000
    stdout 全体で見る  1件   （ideco が消える。**上のとおり、消えるほうが誤り**）

**2件とも本物でした。** どちらも「表の全部を決めている値が、1行も出ていない」。
"""
from __future__ import annotations

import ast
from pathlib import Path

# **1000未満を見ない理由**: 年（2024）・月数・日数・人数・区分番号が大半で、
# それらは節の主題ではなく、出ていなくても追試の妨げになりません。
# 下げると誤報だけが増えます（実測で 1000 が境目）。
FLOOR = 1_000


def forms(n: int) -> list[str]:
    """同じ値の、印字されうる書き方。**桁区切り・万・億は実際に全部使われています。**

    **億を落とすと誤報が出ます**（2026-08-17 に実測）。`souzoku` の見出しは
    「課税価格1億5000万円」で、`150,000,000` をこの形でしか書いていません。
    """
    out = {str(n), f"{n:,}"}
    if n % 10_000 == 0:
        out.add(f"{n // 10_000}万")
    if n % 1_000 == 0:
        man, rest = divmod(n, 10_000)
        if man and rest:
            out.add(f"{man}万{rest:,}")
            out.add(f"{man}万{rest}")
    if n >= 100_000_000 and n % 10_000 == 0:
        oku, rest = divmod(n, 100_000_000)
        man = rest // 10_000
        out.add(f"{oku}億{man}万" if man else f"{oku}億")
        if man:
            out.add(f"{oku}億{man:,}万")
    return sorted(out)


def _main_block(tree: ast.Module) -> ast.If | None:
    for node in tree.body:
        if isinstance(node, ast.If) and ast.unparse(node.test).startswith("__name__"):
            return node
    return None


def _literals(node: ast.AST) -> set[int]:
    """この式の中で、**呼び出しの引数として**渡されている数のリテラル。"""
    out = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        if isinstance(sub.func, ast.Name) and sub.func.id == "print":
            continue
        for arg in list(sub.args) + [k.value for k in sub.keywords]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, int) \
                    and not isinstance(arg.value, bool) and arg.value >= FLOOR:
                out.add(arg.value)
    return out


def _names(node: ast.AST) -> set[str]:
    return {s.id for s in ast.walk(node) if isinstance(s, ast.Name)}


def sections(source: str) -> list[tuple[str, set[int]]]:
    """`__main__` を上から辿り、節ごとに「その節が条件づけられた値」を返す。

    **変数を1つ挟んだものも入ります**（`base = Wage(base=250_000)` を
    あとの節が使っている、という書き方が実物にあります）。
    """
    tree = ast.parse(source)
    main = _main_block(tree)
    if main is None:
        return []

    bound: dict[str, set[int]] = {}      # 変数名 → その変数が抱えている値
    out: list[tuple[str, set[int]]] = []
    cur: str | None = None
    lits: set[int] = set()
    used: set[str] = set()

    def close() -> None:
        nonlocal cur, lits, used
        if cur is None:
            return
        got = set(lits)
        for name in used:
            got |= bound.get(name, set())
        out.append((cur, got))
        cur, lits, used = None, set(), set()

    def visit(body: list[ast.stmt]) -> None:
        nonlocal cur, lits, used
        for stmt in body:
            # 節の切れ目 —— print("=== … ===")
            head = _header(stmt)
            if head is not None:
                close()
                cur = head
                continue
            # 変数に束ねている値を覚える（節をまたいで使われます）。
            # **束ねただけの行を、置かれている節の持ち物にしないこと**
            # （2026-08-17 に踏んだ誤報）。`zangyo` は `base = Wage(base=250_000)` を
            # 「平均所定労働時間」の節の**後ろ**に置いて、**次の節で**使っています。
            # ここで数えると、値を1度も使っていない節に濡れ衣を着せます。
            if isinstance(stmt, ast.Assign):
                got = _literals(stmt.value)
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        # **上書きであって、足し算ではありません**（2026-08-17 に踏んだ）。
                        # `|=` で積むと、`r` のような使い回しの名前が
                        # 前の節の値を**次の節へ持ち越します。** `zangyo` は
                        # `r = hours_error_shortfall(300_000, …)` の `r` を
                        # 次の節の `for r in allowance_grid()` でも使っており、
                        # **300,000 を無関係な節の濡れ衣にしていました。**
                        bound[tgt.id] = set(got)
                if got:
                    continue
            if cur is not None:
                lits |= _literals(stmt)
                used |= _names(stmt)
            if isinstance(stmt, (ast.For, ast.While, ast.If, ast.With)):
                # ループ変数は、その場で束ね直されます。**前の節の値を
                # 引き継がせないこと**（同じ `r` が節をまたいで使われます）。
                if isinstance(stmt, ast.For):
                    for name in _names(stmt.target):
                        bound.pop(name, None)
                visit(stmt.body)
                visit(getattr(stmt, "orelse", []))
    visit(main.body)
    close()
    return out


def _header(stmt: ast.stmt) -> str | None:
    """`print("\\n=== 見出し ===")` なら、その見出しを返す。"""
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return None
    call = stmt.value
    if not (isinstance(call.func, ast.Name) and call.func.id == "print"):
        return None
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                and "===" in arg.value:
            return arg.value.strip()
    return None


def printed_sections(stdout: str) -> dict[str, str]:
    """印字された節を「見出し → 本文（見出しを含む）」で返す。"""
    out: dict[str, str] = {}
    cur, buf = None, []
    for line in stdout.splitlines():
        if line.strip().startswith("===") and line.strip().endswith("==="):
            if cur is not None:
                out[cur] = cur + "\n" + "\n".join(buf)
            cur, buf = line.strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = cur + "\n" + "\n".join(buf)
    return out


def invisible(source: str, stdout: str) -> list[str]:
    """**その節を決めている値のうち、その節に1度も出ていないもの。**

    返るのは人が読む1行です。空なら問題なし。
    """
    printed = printed_sections(stdout)
    problems = []
    for head, lits in sections(source):
        body = printed.get(head.strip())
        if body is None:
            continue                      # 印字されなかった節は対象外
        missing = [n for n in sorted(lits)
                   if not any(f in body for f in forms(n))]
        if missing:
            nums = "・".join(f"{n:,}" for n in missing)
            problems.append(
                f"節「{head.strip(' =')}」は {nums} で計算しているのに、"
                "その値が節のどこにも出ていません。**画面に出しようがない前提です。**"
                " 行に列として足すか、見出しに書くこと"
            )
    return problems


def scan(path: Path, stdout: str) -> list[str]:
    return invisible(Path(path).read_text(encoding="utf-8"), stdout)
