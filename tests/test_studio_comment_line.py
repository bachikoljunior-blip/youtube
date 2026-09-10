"""`status` の視聴者コメントの行は、**黙って字を落とさない**こと（`studio.cli.comment_line_text`）。

2026-09-10 12:0x JST（optimizer・Opus）。**この回に実物で踏んだ穴**を見張る:
`status` は `c["text"][:60]` を素で印字しており、09/09 23:49 の礼（**88字**）が
**文の途中**で切れ、落ちた側に「ハッキリした回答が得られなかったので大変助かりました」
＝ §7 が名指ししている当の節が入っていた。**切れた印も無い。**
さらに文中の改行で **1件が 2行に割れ**、2行目には刻も ID も `[未返信]` も付かない。

**陽性対照は 3つ とも撃って落としてある**（§5 の教訓の形3つ目「落ちるまで撃つ」）:
`comment_line_text` を `text[:60]` へ戻すと 4件 落ちる。
"""
import pytest

from studio import cli

# 実物（`data/studio/ledger.jsonl`・09/09 23:49・@gsf8778）。**この文字列を縮めないこと** ——
# 縮めると、この検査が見張っている「文の途中で切れる」形そのものが消える。
本物 = (
    "​@お金と仕事の教科書丁寧に回答していただきありがとうございます。\n"
    "年金事務所の方に聞きに行ってもたぶん有効みたいな感じでハッキリした回答が"
    "得られなかったので大変助かりました。"
)


def test_1件は必ず1行に収まる():
    """改行で割らない ＝ 刻も ID も付かない行を作らない。"""
    out = cli.comment_line_text(本物)
    assert "\n" not in out
    assert " ⏎ " in out  # 改行が在ったことは残す（消さない）


def test_落とした字は数で言う():
    """**印が無ければ、読む側は切れたことを知りません。**"""
    out = cli.comment_line_text(本物)
    畳んだ = " ⏎ ".join(本物.split("\n"))
    assert out.startswith(畳んだ[: cli.STATUS_COMMENT_CHARS])
    assert f"＋{len(畳んだ) - cli.STATUS_COMMENT_CHARS}字" in out
    assert "comments" in out  # 全文の引き方を同じ行に置く


def test_この実物は実際に切れる():
    """**陰性対照つきの前提**: 88字 は門（60）を越える ＝ この検査は空振りしない。"""
    assert len(本物) > cli.STATUS_COMMENT_CHARS
    assert "ハッキリした回答が得られなかった" not in 本物[: cli.STATUS_COMMENT_CHARS]


def test_門に収まる行は1字も変えない():
    """**陰性対照**: 短い行に印を付けない（付けたら毎行が汚れる）。"""
    短い = "カッチャン、有難う😊"
    assert cli.comment_line_text(短い) == 短い
    assert "…〔" not in cli.comment_line_text(短い)


def test_境目ちょうどは鳴らない():
    """**陰性対照**: `limit` ちょうどの行は完全なので、印を付けない。"""
    ちょうど = "あ" * cli.STATUS_COMMENT_CHARS
    assert cli.comment_line_text(ちょうど) == ちょうど


def test_comments_の側は改行を残す():
    """`comments` は 1件を複数行で出す所なので、畳まない。**印だけ同じ。**"""
    out = cli.comment_line_text(本物, 400, one_line=False)
    assert out == 本物  # 400字 に収まる ＝ 1字も落ちない
    assert "\n" in out


def test_comments_の側でも落としたら数で言う():
    """`status` が「全文は `comments`」と指す先が黙って切れていたら、指しが嘘になる。"""
    長い = "あ" * 500
    out = cli.comment_line_text(長い, 400, one_line=False)
    assert "＋100字" in out


@pytest.mark.parametrize("text", [本物, "短い"])
def test_落とした字と出た字を足すと元に戻る(text):
    """**印の数が本当か**を、印そのものから検算する（写しではなく足し算で見る）。"""
    out = cli.comment_line_text(text)
    畳んだ = " ⏎ ".join(text.split("\n"))
    if "…〔＋" in out:
        n = int(out.split("…〔＋")[1].split("字")[0])
        assert len(out.split("…〔＋")[0]) + n == len(畳んだ)
    else:
        assert out == 畳んだ
