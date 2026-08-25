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


# ---------------------------------------------------------------------------
# **日付つきの判断点**（2026-08-26 に足した。**実物で4日ぶん過ぎていた**）
#
# M12 に「**8/22 時点で 20 以上** → 着手する／**10 未満** → 保留のまま」と
# 書いてあり、**8/22 は 4日 前に過ぎていて、誰も判定していませんでした。**
# この節は状態の一行しか見ておらず、`config/hypotheses.yaml` の期限を見る側は
# MEANS.md を読みません。**期日つきの判断が、2つの帳面の隙間に落ちます。**
# ---------------------------------------------------------------------------
_SAMPLE = "### M99. ためし\n- **状態**: **保留**\n- **7/01 時点で 20 以上** → 着手する\n"


def test_期日の来た判断点を拾う():
    got = status.means_due_dates(_SAMPLE)
    assert len(got) == 1
    code, when, over, line = got[0]
    assert code == "M99" and when.endswith("-07-01") and over > 0
    assert "20 以上" in line


def test_判定を書いた判断点は消える():
    """**閉じ方は1つだけ**: 同じ「M/D」と「判定」を同じ行に書くこと。"""
    closed = _SAMPLE + "\n#### 2026-07-05 — 7/01 の判断点を判定した\n"
    assert status.means_due_dates(closed) == []


def test_まだ来ていない期日は出さない():
    from datetime import datetime, timedelta

    soon = datetime.now(status.JST) + timedelta(days=3)
    body = f"### M98. x\n- **{soon.month}/{soon.day} 時点で 5 以上** → 着手\n"
    assert status.means_due_dates(body) == []


def test_実物のMEANSに未判定の期日が残っていない():
    """**残っていたら、その回が判定すること。** 落ちるのが正しい形です。

    当日ぶん（`grace_days=1`）は見逃します —— 期日の当日に落ちると、
    **その日に判定する回そのものが赤で始まります。**
    画面（`print_means`）のほうは当日から出ます。
    """
    got = status.means_due_dates(MEANS, grace_days=1)
    assert got == [], f"期日の来た判断点が未判定です: {got}"
