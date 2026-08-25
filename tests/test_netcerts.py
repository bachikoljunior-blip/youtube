"""CA の束の差し替えが効いているか。

**2026-08-15 21:4x に生成が 0/8 本で落ちた原因**を、二度目は機械が先に言うため。
症状は `SSLCertVerificationError` ですが、**ネットワークは生きていて `curl` は通る**
ので、読み違えやすい形で出ます（実際その回は「作る側の不具合」と読みかけた）。

**外に出る検査はここには置きません。** 代理サーバの状態でむらが出て、
`pytest` が落ちる回と通る回に分かれます。**外へ出る確認は `python -m src.netcerts`**。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import netcerts  # noqa: E402


def test_import_src_sets_every_env_var():
    """`import src` を通った時点で、束を見る環境変数が全部立っていること。"""
    if netcerts.build() is None:
        pytest.skip("この環境には CA の束が1つもありません")
    for name in netcerts.ENV_VARS:
        assert os.environ.get(name) == str(netcerts.MERGED), (
            f"{name} が差し替わっていません。**httplib2 は import 時に焼くので、"
            f"あとから立てても効きません**"
        )


def test_merged_bundle_has_every_certificate():
    """つないだ束は、**材料のどれよりも枚数が多い**こと。

    8/15 の事故は「環境が立てていた束（24枚）に、実際に使われている CA が
    入っていなかった」ことでした。**多いほうへ寄せる**のがこの直しの中身です。
    """
    if netcerts.build() is None:
        pytest.skip("この環境には CA の束が1つもありません")
    merged = netcerts.count()
    assert merged > 0
    for path in netcerts.CANDIDATES:
        if not path.exists():
            continue
        n = path.read_text(errors="replace").count("BEGIN CERTIFICATE")
        assert merged >= n, f"{path} の {n}枚 より少ない {merged}枚 になっています"


def test_bundle_is_outside_the_repository():
    """束をリポジトリの中に置かないこと（git に入ると毎回差分が出る）。"""
    repo = Path(__file__).resolve().parent.parent
    assert repo not in netcerts.MERGED.resolve().parents


def test_verification_is_never_switched_off():
    """**検証を切る道を作らないこと。**

    落ちているのは「信頼の材料が足りない」ことで、検証そのものは正しい。
    切ると代理サーバの向こうで何が起きても分からなくなります。

    **注釈と文字列は外してから見ること。** 最初に書いたときは素の文字列一致で、
    **この直しの説明文そのものに当たって落ちました**（禁じている語を、
    禁じていると書くために引用しているため）。見たいのは実行される側です。
    """
    src = Path(__file__).resolve().parent.parent / "src"
    banned = ("disable_ssl_certificate_validation=True", "verify=False",
              "_create_unverified_context", "CERT_NONE")
    for py in src.rglob("*.py"):
        code = _code_only(py)
        for word in banned:
            assert word not in code, f"{py.name} に {word} があります"


def _code_only(path: Path) -> str:
    """注釈と文字列リテラルを落として、実行される字だけ返す。"""
    import io
    import tokenize

    text = path.read_text(encoding="utf-8", errors="replace")
    out: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return text  # 読めないなら素のまま見る（見逃すより落ちるほうがよい）
    return " ".join(out)
