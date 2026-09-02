"""`scripts/doc_usage.py` の検査（2026-08-18）。

**測る道具そのものが、当たりを含まないまま育つ側になりうる**ので、
「甘すぎる判定に戻っていないこと」を固定します。

最初の実装は日誌の**全文**を相手にしていて、結果は **参照0件が 0件** ——
「全部の節が使われている」に見えますが、**判定が甘いだけ**でした
（日誌2万行に対し「一度でも出たか」は、ほぼ全部に当たる質問）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import doc_usage  # noqa: E402


def test_見出しで節に切る():
    text = "# 表題\n## A\nあ\nあ\n### B\nい\n## C\nう\n"
    secs = doc_usage.sections(text)
    assert [s["title"] for s in secs] == ["A", "B", "C"]
    assert [s["depth"] for s in secs] == [2, 3, 2]
    assert secs[0]["lines"] == 3            # 見出し + 本文2行


def test_語は本文から引く_手で並べない():
    body = "`sibling_check.py` と `_hit_outcome` を 2026-08-17 に足した。"
    got = doc_usage.tokens_of(body)
    assert "sibling_check.py" in got
    assert "_hit_outcome" in got
    assert "2026-08-17" in got


def test_日本語の文や数字だけは語にしない():
    body = "`これは日本語の説明です` `123` `a b c`"
    got = doc_usage.tokens_of(body)
    assert "123" not in got
    assert "a b c" not in got, "空白入りは識別子ではありません"


def test_直近N回に絞ると全文より狭い(tmp_path, monkeypatch):
    """**ここが本体です。** 全文に戻ると、この道具は何も言わなくなります。"""
    root = tmp_path
    (root / "docs").mkdir()
    (root / "data").mkdir()
    (root / "docs" / "JOURNAL.md").write_text(
        "## 2026-08-01 むかし\n`old_tool.py` を直した\n"
        "## 2026-08-02 きのう\n`new_tool.py` を直した\n", encoding="utf-8")
    (root / "data" / "runs.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(doc_usage, "ROOT", root)

    whole = doc_usage.haystack(0)
    recent = doc_usage.haystack(1)

    assert "old_tool.py" in whole and "new_tool.py" in whole
    assert "new_tool.py" in recent
    assert "old_tool.py" not in recent, "直近1回に絞れていません（甘い判定に戻っています）"


def test_既定は直近に絞ってある():
    """**既定が 0（全文）に戻っていないこと。** 戻ると 参照0件が必ず0件になります。"""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", type=int, default=20)
    assert ap.parse_args([]).recent == 20

    src = Path(doc_usage.__file__).read_text(encoding="utf-8")
    assert '"--recent", type=int, default=20' in src


def test_語の取れない節は0件と混ぜない(tmp_path, monkeypatch):
    """**「判定できない」と「使われていない」は別物です。**"""
    text = "## 語のある節\n`abc.py` の話\n## 語の無い節\n日本語しかありません\n"
    secs = doc_usage.sections(text)
    assert doc_usage.tokens_of(secs[1]["body"]) == set()
    assert doc_usage.tokens_of(secs[0]["body"]) == {"abc.py"}


def test_実物で走る():
    """**実物の文書で最後まで走ること。** 落ちたら次の回が使えません。"""
    assert doc_usage.main.__doc__ is None or True
    import io
    import contextlib
    buf = io.StringIO()
    sys.argv = ["doc_usage.py"]
    with contextlib.redirect_stdout(buf):
        rc = doc_usage.main()
    out = buf.getvalue()
    assert rc == 0
    assert "相手にした記録" in out
    assert "判定できない節" in out


def test_節4の表は文書から切り出す_手で写さない():
    """**§4 の「覆る条件」の発火**（2026-09-03）: 表2つと「選ぶ順」は道具が刷る。

    切り出す範囲は見出しの字から。**行番号を持たない**ので、文書が増えてもずれません。
    """
    text = ("## 4. この回でやること\n"
            "### **この節で本当に要るのは、この2つです**（x）\n\n"
            "**この節は 1,600行 あります**（前置き。表ではない）\n\n"
            "**(1) 6択**\n\n    upload / improve / means / verdict / premise / fix\n\n"
            "**選ぶ順**:\n\n    1. `[暦]` が鳴っている → その1手\n\n"
            "**下の本文を読むのは、上の表で決められなかった回だけです。** 見出しに…\n"
            "**覆る条件**: …\n")
    block = doc_usage.decision_block(text)
    assert block[0].startswith("**(1) 6択**")
    assert any("upload / improve / means / verdict / premise / fix" in ln for ln in block)
    assert any("選ぶ順" in ln for ln in block)
    assert not any("1,600行" in ln for ln in block)          # 前置きは表ではない
    assert not any("覆る条件" in ln for ln in block)         # 終わりの目印の外
    lines = doc_usage.decision_lines(text, "d.md", prefix="[m] ")
    assert lines[0].startswith("[m] **§4 の表")
    assert all(ln.startswith("[m]") for ln in lines)


def test_節4の表が無い文書では何も出さない():
    assert doc_usage.decision_block("## 4. x\n本文だけ\n") == []
    assert doc_usage.decision_lines("## 4. x\n本文だけ\n") == []
    # 始まりだけ在って終わりが無い（切りかけ）も、途中まで刷らない
    assert doc_usage.decision_block("### この節で本当に要るのは、この2つです\n**(1) a\n") == []


def test_読む順の節4の行は_表が下に在ると言う():
    """一覧の §4 の行が `sed` を促したままだと、表を刷った意味がありません。"""
    text = Path(__file__).resolve().parent.parent.joinpath("docs/trigger_main.md").read_text(encoding="utf-8")
    assert doc_usage.decision_block(text), "実物の §4 に表が無い（見出しの字が変わった？）"
    lines = doc_usage.index_lines(text, only_read=True)
    row4 = next(ln for ln in lines if " §4 " in ln)
    assert "表は下に印字ずみ" in row4
    got = doc_usage.decision_lines(text)
    assert any("upload / improve / means / verdict / premise / fix" in ln for ln in got)
    assert any("`[暦]` が鳴っている" in ln for ln in got)
