"""**1周は2種類そろって1周である**ことを固定する検査（2026-08-25）。

オーナー指示（原文）:

> **「親が判断せずサブで2種類の実行走らせんだよわかってっか？」**

## この検査が守っているもの

**それまで `next_round.py` は2つの役を交互に立てていました。**
1周に1つ、2周で1組。**これは設計の劣化でした** —— 元の形は子セッション2枚
（`youtube-hourly` / `youtube-optimizer`）が**並行して走り続ける**もので、
片方だけが走る時間帯はありませんでした。交互にした時点で、
**最適化はどの瞬間も半分止まっています。**

実測でその穴を踏んでいます —— **2026-08-25 12:37Z の周は `hourly` だけが立ち、
`optimizer` は33分間どこにも走っていませんでした。**
文書が約束していた `--both` は**実装されていませんでした**（約束だけが残る形）。

## もう1つ、入れたその場で落ちた欠陥

周の幅を**固定30分**にしたところ、実データ（`hourly` 12:37Z /
`optimizer` 13:10Z ＝ **33.6分差**）が別の周に割れ、
**「`hourly` が欠けている」と出ました。** 主実行はそのとき走っています。
**従えば2枚目が立ち、2026-08-15 の「2人の子が同じ日の予約を取り合って
片方の生成が丸ごと無駄になった」形を踏みます。**

だから幅は**間隔の半分**（`round_span`）にしてあります。
**ここを固定値に戻さないこと。**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "next_round", ROOT / "scripts" / "next_round.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nr = _load()

HOURLY = {"at": "2026-08-25T12:37:05+00:00", "role": "hourly"}
OPTIMIZER = {"at": "2026-08-25T13:10:41+00:00", "role": "optimizer"}


def test_役は交互ではなく2種類そろえる():
    """**空の状態から立てるのは「全部」。** 1つだけなら交互に戻っています。"""
    d = nr.decide()
    assert "roles" in d, "`decide()` が `roles` を返していません（`role` のままです）"
    assert isinstance(d["roles"], list)
    assert len(nr.ROLES) == 2, "役が2つでなくなったら、この検査の前提を書き直すこと"


def test_記録が無ければ2種類とも立てる():
    got = nr.current_round([], span_min=45.0)
    assert got == []
    assert nr.missing_roles(got) == list(nr.ROLES), (
        "記録が無い回に立てるのは2種類とも。1つだけなら片肺で始まります"
    )


def test_片肺の周は欠けとして出る():
    """**8/25 12:37Z にこれが起きて、33分間 optimizer がいませんでした。**"""
    group = nr.current_round([HOURLY], span_min=nr.round_span(90))
    assert [r["role"] for r in group] == ["hourly"]
    assert nr.missing_roles(group) == ["optimizer"]


def test_欠けは間隔を待たずにGOになる(tmp_path, monkeypatch):
    """**待つと、その周は片肺のまま終わります。**"""
    rounds = tmp_path / "rounds.jsonl"
    rounds.write_text('{"at": "2026-08-25T12:37:05+00:00", "role": "hourly"}\n',
                      encoding="utf-8")
    monkeypatch.setattr(nr, "ROUNDS", rounds)
    monkeypatch.setattr(nr, "floor_minutes", lambda: (90.0, "検査"))
    from datetime import datetime, timezone
    d = nr.decide(now=datetime(2026, 8, 25, 12, 40, tzinfo=timezone.utc))
    assert d["go"] is True, "欠けているのに WAIT を返しています"
    assert d["roles"] == ["optimizer"]
    assert d.get("patch") is True


def test_そろっていれば間隔を待つ(tmp_path, monkeypatch):
    """**そろった周を穴埋め扱いしないこと。** 扱えば毎回2枚目が立ちます。"""
    rounds = tmp_path / "rounds.jsonl"
    rounds.write_text(
        '{"at": "2026-08-25T12:37:05+00:00", "role": "hourly"}\n'
        '{"at": "2026-08-25T13:10:41+00:00", "role": "optimizer"}\n',
        encoding="utf-8")
    monkeypatch.setattr(nr, "ROUNDS", rounds)
    monkeypatch.setattr(nr, "floor_minutes", lambda: (90.0, "検査"))
    from datetime import datetime, timezone
    d = nr.decide(now=datetime(2026, 8, 25, 13, 15, tzinfo=timezone.utc))
    assert d["go"] is False, (
        "**そろっている周で GO が出ています。** 従うと主実行の2枚目が立ち、"
        "2026-08-15 の「同じ日の予約を取り合う」を踏みます"
    )
    assert nr.missing_roles(
        nr.current_round([HOURLY, OPTIMIZER], span_min=45.0)) == []


def test_周の幅は固定値ではなく間隔の半分():
    """**固定30分は実データで落ちました**（33.6分差が別の周に割れた）。"""
    assert nr.round_span(90) == 45.0
    assert nr.round_span(60) == 30.0
    assert nr.round_span(200) == nr.ROUND_SPAN_MAX_MIN, "上限が効いていません"
    span = nr.round_span(90)
    group = nr.current_round([HOURLY, OPTIMIZER], span_min=span)
    assert [r["role"] for r in group] == ["hourly", "optimizer"], (
        f"実データ（33.6分差）が同じ周にまとまりません（幅 {span}分）。"
        "**割れると「主実行が欠けている」と出て、2枚目が立ちます**"
    )


def test_次の周は前の周を吸わない():
    """幅が広すぎると、次の周の記録を前に吸わせて「そろった」と誤読します。"""
    nxt = {"at": "2026-08-25T14:10:00+00:00", "role": "hourly"}
    group = nr.current_round([HOURLY, OPTIMIZER, nxt], span_min=nr.round_span(90))
    assert [r["role"] for r in group] == ["hourly"], (
        "次の周の1件目が、前の周に吸われています"
    )
    assert nr.missing_roles(group) == ["optimizer"]


def test_recordは複数の役を受ける(tmp_path, monkeypatch):
    rounds = tmp_path / "rounds.jsonl"
    monkeypatch.setattr(nr, "ROUNDS", rounds)
    for role in nr.ROLES:
        nr.record(role)
    got = [line for line in rounds.read_text(encoding="utf-8").splitlines() if line]
    assert len(got) == len(nr.ROLES)


@pytest.mark.parametrize("role", list(nr.ROLES))
def test_役の名前は渡す本文のkindと一致する(role):
    """名前がずれると、親は存在しない `kind:` を探して止まります。"""
    text = (ROOT / "docs" / "spawn_prompt.rendered.md").read_text(encoding="utf-8")
    assert f"## kind: {role}" in text
