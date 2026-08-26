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
    """**そろった周を穴埋め扱いしないこと。** 扱えば毎回2枚目が立ちます。

    実データ（`hourly` 12:37Z / `optimizer` 13:10Z ＝ 33.6分差）を使います。
    **同じ周かどうかは `round` が答えます** —— 時刻の幅では当てられません。
    """
    rounds = tmp_path / "rounds.jsonl"
    rid = "2026-08-25T12:37:05+00:00"
    rounds.write_text(
        '{"at": "2026-08-25T12:37:05+00:00", "role": "hourly", '
        f'"round": "{rid}"}}\n'
        '{"at": "2026-08-25T13:10:41+00:00", "role": "optimizer", '
        f'"round": "{rid}"}}\n',
        encoding="utf-8")
    monkeypatch.setattr(nr, "ROUNDS", rounds)
    monkeypatch.setattr(nr, "floor_minutes", lambda: (90.0, "検査"))
    from datetime import datetime, timezone
    d = nr.decide(now=datetime(2026, 8, 25, 13, 15, tzinfo=timezone.utc))
    assert d["go"] is False, (
        "**そろっている周で GO が出ています。** 従うと主実行の2枚目が立ち、"
        "2026-08-15 の「同じ日の予約を取り合う」を踏みます"
    )


def test_穴埋めは何分あいても同じ周を継ぐ(tmp_path, monkeypatch):
    """**時刻の幅を当てない**（2026-08-26。窓で2回外したあと）。

    33.6分 あけて片肺を埋めた実データが、幅10分では別の周に割れていました。
    `round` を継ぐので、**何分あいても割れません。**
    """
    from datetime import datetime, timedelta, timezone
    rounds = tmp_path / "rounds.jsonl"
    monkeypatch.setattr(nr, "ROUNDS", rounds)
    monkeypatch.setattr(nr, "floor_minutes", lambda: (90.0, "検査"))
    t0 = datetime(2026, 8, 25, 12, 37, 5, tzinfo=timezone.utc)

    first = nr.record("hourly", t0)
    assert nr.missing_roles(nr.current_round()) == ["optimizer"]

    patched = nr.record("optimizer", t0 + timedelta(minutes=33.6))
    assert patched["round"] == first["round"], (
        "穴埋めが別の周になっています。**幅を当てる作りに戻っています**"
    )
    assert nr.missing_roles(nr.current_round()) == []

    # 間隔を越えたら、埋まっていなくても新しい周
    nxt = nr.record("hourly", t0 + timedelta(minutes=95))
    assert nxt["round"] != first["round"]
    assert nr.missing_roles(nr.current_round()) == ["optimizer"]


def test_識別子の無い古い行は窓へ落ちる():
    """**過去の行を捨てないこと。** `round` が付く前の記録も読めること。"""
    group = nr.current_round([HOURLY], span_min=nr.round_span(90))
    assert [r["role"] for r in group] == ["hourly"]
    assert nr.missing_roles(group) == ["optimizer"]


def test_周の幅は間隔に比例させない():
    """**比例させて2回とも外しました**（2026-08-26）。

    1周の2件は `--record hourly,optimizer` の**1回の呼び**で書かれるので、
    実際の差は**マイクロ秒**です。隣の周までは `floor`（最低35分）離れます。
    **要る幅はその2つのあいだのどこか**で、`floor` に比例させる理由がありません。

        幅 = floor/2   間隔 36分 → 90分 で幅が45分になり、**40分おきの周が
                       数珠つなぎ**（「前の周から185分」・実際は21分前。
                       従えば二重に立つ）
        幅 = 45分固定  **片肺の周が前の周の1件を吸い**、欠けが消える

    **どちらも「幅が隣の周に届いた」ことが原因です。**
    """
    assert nr.round_span(90) == 10.0, "間隔が伸びても幅は伸びないこと"
    assert nr.round_span(36) == 9.0, "間隔が短いときは、そのぶん締めること"
    assert nr.round_span(1000) == 10.0, "上限が効いていません"

    # **隣の周に届かないこと。** 周の間隔は floor 以上なので、
    # 幅は floor より必ず小さい。
    for floor in (35.0, 36.0, 60.0, 90.0, 200.0):
        assert nr.round_span(floor) < floor, f"幅が間隔に届いています（{floor}分）"


def test_数珠つなぎにならない():
    """**40分おきに刻まれた周が、1つに繋がらないこと**（実データで踏んだ）。"""
    rows = []
    for hhmm in ("23:11:37", "23:51:55"):
        rows += [{"at": f"2026-08-25T{hhmm}+00:00", "role": r} for r in nr.ROLES]
    rows += [{"at": "2026-08-26T00:32:26+00:00", "role": r} for r in nr.ROLES]
    group = nr.current_round(rows, span_min=nr.round_span(90))
    assert len(group) == len(nr.ROLES), (
        f"周が数珠つなぎになっています（{len(group)}件）。"
        "**「前の周の開始から185分」と出て、21分前に立てた相手の上に重ねます**"
    )
    assert all(str(r["at"]).startswith("2026-08-26T00:32") for r in group)


def test_片肺の周が前の周の1件を吸わない():
    """**吸うと欠けが消え、片肺のまま完成扱いで見送ります。**"""
    rows = [{"at": "2026-08-25T23:51:55+00:00", "role": r} for r in nr.ROLES]
    rows += [{"at": "2026-08-26T00:32:26+00:00", "role": "hourly"}]
    group = nr.current_round(rows, span_min=nr.round_span(90))
    assert nr.missing_roles(group) == ["optimizer"], (
        "片肺の周が、前の周の `optimizer` を吸って「そろっている」に見えています"
    )


def test_同じ呼びで書いた2件は同じ周():
    """`--record hourly,optimizer` はマイクロ秒差で2行書きます。"""
    rows = [
        {"at": "2026-08-26T00:32:26.279234+00:00", "role": "hourly"},
        {"at": "2026-08-26T00:32:26.279375+00:00", "role": "optimizer"},
    ]
    group = nr.current_round(rows, span_min=nr.round_span(90))
    assert nr.missing_roles(group) == []


def test_次の周は前の周を吸わない():
    """幅が広すぎると、次の周の記録を前に吸わせて「そろった」と誤読します。"""
    nxt = {"at": "2026-08-25T14:10:00+00:00", "role": "hourly"}
    group = nr.current_round([HOURLY, OPTIMIZER, nxt], span_min=nr.round_span(90))
    assert [r["role"] for r in group] == ["hourly"], (
        "次の周の1件目が、前の周に吸われています"
    )
    assert nr.missing_roles(group) == ["optimizer"]
    # **件数でも止めます。** 幅だけだと、間隔が伸びたとき隣に届きます
    # （2026-08-26 に実測）。幅と件数の両方が要ります。


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
