"""却下した手段の「覆る条件」を、毎回の `status.py` に出す（2026-08-16 に足した）。

## なぜ要るか（**律速そのものが、台帳の中で見えなくなっていました**）

`status.py` の `print_means()` は長らく **未着手 と 保留 しか出していません**でした。
`docs/MEANS.md` の却下4件（M5・M7・M10・M11）は、全部に
「これが覆る条件」が数字で書いてあるのに、**一度も画面に出ていません。**

実害が出ています。**M11 は「ショートの登録率そのものを上げる」**で、
本文はその乗数を「**単独で M1 を不可能から1年台に動かしうる唯一の乗数**」と
書いています（登録率 0.038% は 1,000人の門に259万再生を要求している律速そのもの）。
それが見えないので、8/16 の回が**2回続けて**申し送りにこう書きました ——

    「`docs/MEANS.md` に、登録率を直接動かす手段を足すこと。
      未着手0件・保留2件で、**台帳が律速を1つも持っていません**」

**台帳は持っていました。この節が見せていなかっただけです。**
M11 自身が「この却下は**毎回もう一度提案されかけます**」と警告しており、
実際そのとおりになりかけています（次の回が M11 を書き直す ＝ 1周まるごと空振り）。

## 「後ろのものを採る」理由（**上から採ると、取り消された条件が出ます**）

M11 の条件1 は 8/15 に取り消し線つきで閉じられ、**同日 16:0x にその閉じ方ごと
取り消されています。** この台帳は追記式なので、**下にあるものが今の判断**です。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("status", ROOT / "scripts" / "status.py")
status = importlib.util.module_from_spec(spec)
sys.modules["status"] = status
spec.loader.exec_module(status)

MEANS = (ROOT / "docs" / "MEANS.md").read_text(encoding="utf-8")


def _entries() -> list[tuple[str, str, str]]:
    return re.findall(r"^### (M\d+)\. (.+?)$\n(.*?)(?=^### |\Z)", MEANS, re.M | re.S)


def _state(body: str) -> str:
    m = re.search(r"\*\*状態\*\*: (.+)", body)
    return m.group(1).strip() if m else ""


def test_覆る条件を1行で抜く():
    body = "- **これが覆る条件**: 流入が2桁/週になったとき\n- **次の項**: 関係ない\n"
    assert status.reversal_conditions(body) == ["流入が2桁/週になったとき"]


def test_取り消し線の中は落とす():
    """**死んだ条件を先に見せない。** M11 の条件1 がこの形でした。"""
    body = "- **覆る条件**: ~~もう来ない条件~~ 生きている条件\n"
    got = status.reversal_conditions(body)
    assert got and "もう来ない" not in got[0]
    assert "生きている条件" in got[0]


def test_二度書かれていたら後のほうを採る():
    """追記式の台帳なので、**下にあるものが今の判断**です。"""
    body = (
        "- **これが覆る条件**: 古い条件\n"
        "- **なにか別の話**: …\n"
        "- **これが覆る条件（書き直した）**: 新しい条件\n"
    )
    assert status.reversal_conditions(body) == ["新しい条件"]


def test_却下の項は全部が覆る条件を持っている():
    """**条件の無い却下は「二度と見ない」と同じ**なので、書き忘れをここで止める。"""
    missing = [
        code
        for code, _name, body in _entries()
        if ("却下" in _state(body) or "待ち" in _state(body))
        and not status.reversal_conditions(body)
    ]
    assert missing == [], f"覆る条件の無い却下: {missing}"


def test_M11_が却下の一覧に出る():
    """**この検査が本命です。** ここが落ちたら、律速がまた見えなくなっています。"""
    rejected = [
        code
        for code, _name, body in _entries()
        if "却下" in _state(body) or "待ち" in _state(body)
    ]
    assert "M11" in rejected


def test_M11_の覆る条件は8本の段のこと():
    """8/15 に取り消された「1本あたりが1桁上がる」を採っていたら落ちる（故障注入）。"""
    body = next(b for c, _n, b in _entries() if c == "M11")
    got = status.reversal_conditions(body)
    assert got, "M11 の覆る条件が抜けていません"
    assert "8本" in got[0], got[0]
    assert "取り消し" not in got[0], got[0]


def test_画面にM11が出る(capsys):
    status.print_means()
    out = capsys.readouterr().out
    assert "却下・待ち" in out
    assert "M11" in out
