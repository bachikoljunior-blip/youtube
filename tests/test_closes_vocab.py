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
    """`carry_over` / `missing_thumbnail` は持ち越しの語ではなく**一覧の鍵**です。"""
    from src import alerts
    keys = [r.key for r in alerts.table()]
    assert keys, "鍵が1つも無い（`data/alerts.jsonl` が空。ここが空なら検査になりません）"
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
