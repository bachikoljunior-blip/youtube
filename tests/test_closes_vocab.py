"""`--closes` に書いた語が、**本当に一覧に載っているか**を言うこと。

## なぜ要るか（2026-08-17。**3回運ばれて、3回とも未着手だった申し送り**）

申し送りの文はこうでした ——

> **`run_marker.py --ship --closes` が、`retro.py` の一覧に無い語を黙って受け取る。**
> 止めなくてよいので、**言うだけ**入れること。
> いまは書き間違いに気づく口がどこにもありません。

散文の宣言を構造へ移したのは、**「書きすぎ」と「書き忘れ」が3回起きた**からです
（`run_marker.ship()` の docstring）。ところが移した先の構造にも、
**同じ形の穴がそのまま残っていました** —— `--closes` はどんな語でも受け取り、
`data/runs.jsonl` に宣言だけが残って、**持ち越しは一覧に残り続けます。**

**止めないこと**も要件です。出したものの記録が語の綴りで落ちるのは、
**投稿が途切れるのと同じ形の損**（記録そのものが欠ける）なので、警告だけにしています。

## 語彙は実物から引くこと

見る先は2つで、**どちらも手で並べません**:

- `retro.carry_over()` ——`retro.py` が画面に出しているものと**同じ計算**
- `src/alerts.py` の鍵 —— 鳴った記録のあるもの（`data/alerts.jsonl`）

**片方に写して持たないこと。** `noise_tokens()` の直しが入ったときに、
片方だけ古くなります（このリポジトリが通算9回踏んでいる形）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- **`sys.modules` の名前を横取りしないこと**（2026-08-26 夜に直した）---
#
# ここは `importlib` でまっさらな module を作り、**`sys.modules["run_marker"]` を
# 上書き**していました。**これはこのファイルの中の話では済みません。**
#
# `tests/test_seen_mark.py` と `tests/test_silent_run.py` は
# `import run_marker` で**最初の**module を掴み、fixture がその `MARKS` を
# `monkeypatch` します。ところが `scripts/sibling_check.silent_runs()` は
# **呼ばれた時に** `import run_marker` します —— つまり
# **上書きされた後の module**、`MARKS` は実物のまま。
# 差し替えたはずの台帳は読まれず、検査は実物の `data/runs.jsonl` を見ます。
#
# pytest は**走らせる前に全部の test module を import する**ので、
# **並び順は関係ありません。** この2ファイルが同じ回に入っているだけで、
# 向こうの **9件** が落ちます（実測 2026-08-26: `test_seen_mark` 4件・
# `test_silent_run` 5件。**どちらも単体では緑**）。
#
# **緑と赤が「どのファイルを選んだか」で変わる検査は、何も主張していません。**
# しかも落ち方が「実装が壊れた」に見えるので、**本物の欠陥がその赤に紛れます**
# （同じ日、`tests/test_levers_density_surface.py` の本物の欠陥2件が
#  べた書きの1件の赤に紛れて 20時間 隠れていました）。
#
# **直し方は「1つの object にする」こと。** すでに読まれていればそれを使います。
# **覆る条件**: この検査が「まっさらな module」を要求するようになったら
# （import の副作用そのものを見たいなど）、**canonical でない名前**で読むこと ——
# `sys.modules["run_marker"]` を奪うのではなく `"closes_record_run_marker"` などに。

if "run_marker" in sys.modules:                 # **奪わない。すでに在るものを使う**
    run_marker = sys.modules["run_marker"]
else:
    spec = importlib.util.spec_from_file_location(
        "run_marker", ROOT / "scripts" / "run_marker.py")
    run_marker = importlib.util.module_from_spec(spec)
    sys.modules["run_marker"] = run_marker
    spec.loader.exec_module(run_marker)


def _say(closes, capsys):
    run_marker._warn_unknown(list(closes))
    return capsys.readouterr().out


def test_一覧に無い語は言う(capsys):
    out = _say(["zzz-not-a-real-carry-over"], capsys)
    assert "一覧に無い語" in out
    assert "zzz-not-a-real-carry-over" in out


def test_alerts_の鍵は通す(capsys):
    """`carry_over` / `missing_thumbnail` は持ち越しの語ではなく**一覧の鍵**です。

    ## **鍵は自分で鳴らすこと**（2026-08-19 に踏んだ）

    ここは長らく `alerts.table()` をそのまま読んでいました。ところが
    `tests/conftest.py` が**全部の検査で `alerts.LEDGER` を空の tmp へ向けます**
    （実物の帳面を汚さないため）。だから `table()` は**この検査の中では常に空**で、
    `assert keys` は「先に走った別の検査が、たまたま鳴らしてくれたか」だけを見ていました。

    **全体で走ると緑・単体で走ると赤**という形です。実際 04:4x の回が
    `tests/test_closes_vocab.py` だけを叩いて赤を踏み、**自分の直しのせいだと
    読みかけました**（`scripts/retro.py` を退避して同じ赤が出て、初めて分かった）。

    **順番に頼る検査は、頼っている相手が消えた回に嘘をつきます。**
    鳴らす相手はこの検査が自分で作ること。
    """
    from src import alerts

    for key in ("carry_over", "missing_thumbnail"):
        alerts.ring(key, 1)
    keys = [r.key for r in alerts.table()]
    assert keys, "鍵が1つも無い（自分で鳴らしたのに読めない ＝ 読む側が壊れています）"
    out = _say(keys, capsys)
    assert "一覧に無い語" not in out, f"鍵を知らない語と言っています: {out}"


def test_いま出ている持ち越しは通す(capsys):
    """**実データで確かめること。** 手で書いた語では、噛み合っているか分かりません。"""
    from retro import carry_over
    carried, _dropped = carry_over()
    if not carried:
        return          # 申し送りが全部片づいている回。**検査を落とす理由にはならない**
    out = _say(sorted(carried)[:3], capsys)
    assert "一覧に無い語" not in out, f"自分が出している語を知らないと言っています: {out}"


def test_物の名前として沈めた語も通す(capsys):
    """`noise_tokens()` で外した語は「一覧に無い」ではありません。

    外したのは**こちら側の都合**（族名・動画IDは問題の名前ではない）なので、
    それを潰したと宣言するのは正しい形です。**外したことを理由に叱らないこと。**
    """
    from retro import carry_over
    _carried, dropped = carry_over()
    toks = [t for v in dropped.values() for t in v]
    if not toks:
        return
    out = _say(toks[:3], capsys)
    assert "一覧に無い語" not in out, f"沈めた語を知らないと言っています: {out}"


def test_止めないこと(capsys):
    """**警告であって、失敗ではない。**（故障注入の向き: 止めるようにしたら落ちる）"""
    out = _say(["zzz-not-a-real-carry-over"], capsys)   # 例外が飛べばここで落ちます
    assert "一覧に無い語" in out


def test_一覧が読めない回は黙って通す(capsys, monkeypatch):
    """日誌が読めない・`retro` が壊れている回に、**記録の側を巻き込まないこと。**"""
    import retro
    monkeypatch.setattr(retro, "carry_over",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("読めません")))
    out = _say(["zzz-not-a-real-carry-over"], capsys)
    assert "一覧に無い語" not in out
    assert "読めませんでした" in out


def test_ship_が警告を通す(tmp_path, capsys, monkeypatch):
    """`--closes` の道から実際に呼ばれていること（**繋ぎ忘れは緑のまま通ります**）。"""
    monkeypatch.setattr(run_marker, "MARKS", tmp_path / "runs.jsonl")
    run_marker.ship("fix: 検査用", ["zzz-not-a-real-carry-over"])
    out = capsys.readouterr().out
    assert "潰した宣言を 1 件" in out
    assert "一覧に無い語" in out, "`ship()` から `_warn_unknown` が呼ばれていません"


def test_書き込む前の一覧で見ること(tmp_path, capsys, monkeypatch):
    """**入れた直後に自分で踏んだ形。**（2026-08-17）

    `carry_over()` は `recorded_closures()`（＝ `data/runs.jsonl`）を読みます。
    だから **先に記録してから見にいくと、たった今書いた宣言が自分の語を黙らせ**、
    一覧から消えます。結果、**正しい語を書いた回にかぎって「一覧に無い」と鳴る** ——
    **当たりのときだけ鳴らない**という、いちばん質の悪い向きの壊れ方でした。

    ここでは実データの持ち越しから1語を取り、`ship()` の道で宣言してみます。
    **書き込む前に語彙を読んでいれば、警告は出ません。**
    """
    import retro
    carried, _dropped = retro.carry_over()
    if not carried:
        return
    word = sorted(carried)[0]
    marks = tmp_path / "runs.jsonl"
    monkeypatch.setattr(run_marker, "MARKS", marks)
    # **`retro` にも同じファイルを見せること。** 別の口を見せると、
    # 「書いた記録が自分を黙らせる」という肝心の道が再現されません
    # （検査が緑のまま、直す前のコードも通ります）。
    monkeypatch.setattr(retro, "RUNS", marks)
    run_marker.ship("fix: 検査用", [word])
    out = capsys.readouterr().out
    assert "一覧に無い語" not in out, (
        f"いま出ている持ち越し `{word}` を宣言したのに「一覧に無い」と言っています。"
        "**記録を書いた後に一覧を読んでいます**（順番が逆）")


# ======================================================================
# **逆向き**: 一覧に載っている語を潰したのに、宣言しなかった回
#   （2026-08-17 15:3x。上の警告と対になります。**この回が実例に当たった**）
# ======================================================================


def _suggest(what, closes, carried, monkeypatch, tmp_path, capsys):
    """`data/alerts.jsonl` を汚さずに `_suggest_undeclared` を呼ぶ。"""
    from src import alerts
    monkeypatch.setattr(alerts, "LEDGER", tmp_path / "alerts.jsonl")
    monkeypatch.setattr(alerts, "RUNS", tmp_path / "runs.jsonl", raising=False)
    run_marker._suggest_undeclared(what, list(closes),
                                   (set(carried), {t: [] for t in carried}))
    return capsys.readouterr().out


def test_潰した語に触れているのに宣言が無ければ言う(monkeypatch, tmp_path, capsys):
    """**実例そのもの**（8/17 15:1x の ship を、そのまま入れています）。"""
    what = ("fix: CONSTRAINTS に「repo を触らずにできること」の節"
            "（3回持ち越し。効かない回には永久に着手されない構造ごと書いた）")
    out = _suggest(what, ["carry_over"],
                   ["repo を触らずにできること", "docs/CONSTRAINTS.md"],
                   monkeypatch, tmp_path, capsys)
    assert "持ち越しの語に" in out, f"逆向きの穴を見ていません: {out}"
    assert "repo を触らずにできること" in out
    # **パスの形の語は、見出しだけで書かれる。** ここが落ちると実例を取りこぼします
    assert "docs/CONSTRAINTS.md" in out, (
        "`docs/CONSTRAINTS.md` を「CONSTRAINTS に」から拾えていません")


def test_宣言済みの語は言わない(monkeypatch, tmp_path, capsys):
    what = "fix: CONSTRAINTS に「repo を触らずにできること」の節"
    out = _suggest(what, ["carry_over", "repo を触らずにできること",
                          "docs/CONSTRAINTS.md"],
                   ["repo を触らずにできること", "docs/CONSTRAINTS.md"],
                   monkeypatch, tmp_path, capsys)
    assert out.strip() == "", f"宣言済みの語をもう一度言っています: {out}"


def test_触れていない回は黙る(monkeypatch, tmp_path, capsys):
    """**鳴らないのが普通**です。ここが鳴ると、毎回の ship が一覧まみれになります。"""
    what = "means: calc/koureikoyou 節6・テーマ+6"
    out = _suggest(what, [], ["repo を触らずにできること", "docs/CONSTRAINTS.md"],
                   monkeypatch, tmp_path, capsys)
    assert out.strip() == "", f"触れていないのに鳴りました: {out}"


def test_パスでない語は語幹まで緩めない():
    """`status.py` を `status` まで緩めると `session_status` に当たります。

    **当たりを含まないまま育つ一覧**を、こちらから作らないための境目です。
    """
    assert run_marker._mentions("fix: status.py が10行で終わった", "status.py")
    assert not run_marker._mentions("post_turn_summary の session_status を読む",
                                    "status.py")
    # `/` を含む語（パス）だけ、見出しでも拾う
    assert run_marker._mentions("CONSTRAINTS に節を足した", "docs/CONSTRAINTS.md")
    assert not run_marker._mentions("節を足した", "docs/CONSTRAINTS.md")


def test_語彙が読めない回は黙って通す(capsys):
    """**読めないことを理由に、記録を止めないこと**（`_warn_unknown` と同じ）。"""
    run_marker._suggest_undeclared("fix: なんでも", [], None)
    assert capsys.readouterr().out == ""


def test_ship_の道でも鳴る(monkeypatch, tmp_path, capsys):
    """**呼び出しが繋がっていること。** 関数だけ緑で、誰も呼んでいない形を防ぐ。"""
    import retro
    from src import alerts
    carried, _dropped = retro.carry_over()
    if not carried:
        return
    word = sorted(carried, key=len, reverse=True)[0]
    marks = tmp_path / "runs.jsonl"
    monkeypatch.setattr(run_marker, "MARKS", marks)
    monkeypatch.setattr(retro, "RUNS", marks)
    monkeypatch.setattr(alerts, "LEDGER", tmp_path / "alerts.jsonl")
    run_marker.ship(f"fix: {word} を潰した", [])
    out = capsys.readouterr().out
    assert "持ち越しの語に" in out, (
        f"`ship()` から `_suggest_undeclared` が呼ばれていません（語 `{word}`）: {out}")
