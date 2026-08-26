"""**登録の依頼を途中にも入れる A/B**（`src/script_writer.request_form`）。

`tests/test_hook_form.py` を写しています。**見ているのは3つ**:

1. 塩が `title_form` / `hook_form` と別か（同じだと、どちらが効いたか永久に分からない）
2. **長尺がどちらの群にも入らないか**（長尺は依頼そのものを書かない）
3. 処置の検出（`is_mid_request`）が、終端の判定（`is_request`）を壊していないか
"""
from __future__ import annotations

from src import endcard_verdict as ev
from src.script_writer import (
    HOOK_ASK_SHARE, MID_REQUEST_SHARE, TITLE_ASK_SHARE,
    hook_form, request_form, title_form,
)

IDS = [f"s-t{i:04d}" for i in range(2000)]


def test_ショートは二つの群に半々で割れる():
    got = [request_form(i) for i in IDS]
    assert set(got) == {"途中あり", "終端のみ"}
    share = got.count("途中あり") / len(got)
    assert 0.45 <= share <= 0.55, share


def test_振り分けはテーマIDだけを見る():
    """**接頭辞で長尺を落とさないこと**（2026-08-26 に書き直した）。

    控えの実測で `s-` なのに3分超が3件、`s-` でないのに3分以下（深い題ショート）が
    6件ありました。**接頭辞で落とすと、深い題ショートが群から丸ごと消えます。**
    落とすのは群を数える側（`src/judgeable._short_topics()` が `duration_s` で割る）。
    """
    for tid in ["iryohi-kougaku-100man", "nenkin-kuriage-5nen", "keihi-x"]:
        assert request_form(tid) in {"途中あり", "終端のみ"}


def test_長尺は群を数える側で落ちる():
    """`duration_s` が3分を超える本は、どちらの群にも入らないこと。"""
    from src import judgeable as J

    shorts = J._short_topics()
    long_topics = [
        str(r.get("topic") or "")
        for r in J._ledger_rows()
        if isinstance(r.get("duration_s"), (int, float)) and float(r["duration_s"]) > J.SHORT_MAX_S
    ]
    assert long_topics, "控えに長尺が1本もありません（この検査が空回りしています）"
    assert not (set(long_topics) & shorts), sorted(set(long_topics) & shorts)[:5]


def test_深い題ショートは群に入る():
    """`s-` で始まらないのに3分以下の本（深い題ショート）が落ちていないこと。"""
    from src import judgeable as J

    deep = [
        str(r.get("topic") or "")
        for r in J._ledger_rows()
        if isinstance(r.get("duration_s"), (int, float))
        and 0 < float(r["duration_s"]) <= J.SHORT_MAX_S
        and not str(r.get("topic") or "").startswith("s-")
    ]
    assert deep, "深い題ショートが控えに1本もありません（この検査が空回りしています）"
    assert set(deep) <= J._short_topics()


def test_塩が他の二つと別():
    """3つとも同じ割合(0.5)なので、**塩が同じなら群が完全に重なります。**"""
    assert TITLE_ASK_SHARE == HOOK_ASK_SHARE == MID_REQUEST_SHARE == 0.5
    a = [request_form(i) == "途中あり" for i in IDS]
    b = [title_form(i) == "問い" for i in IDS]
    c = [hook_form(i) == "問い" for i in IDS]
    for other, name in ((b, "title_form"), (c, "hook_form")):
        same = sum(1 for x, y in zip(a, other) if x == y) / len(a)
        assert 0.4 <= same <= 0.6, f"{name} と {same:.0%} 重なっています"


def test_割合を0にすると振り分けが止まる():
    assert all(request_form(i, share=0) == "終端のみ" for i in IDS[:50])
    assert all(request_form(i, share=1) == "途中あり" for i in IDS[:50])


def test_同じIDは何度でも同じ群():
    """作り直した本が別の群に移ると、比較が壊れます。"""
    assert [request_form(i) for i in IDS[:200]] == [request_form(i) for i in IDS[:200]]


def test_途中の依頼を終端の依頼と取り違えない():
    end_only = ["月30万円ならここが境目です。", "この計算を毎日出しています。登録してください。"]
    mid = ["月30万円ならここが境目です。", "医療費の続きは登録して受け取ってください。",
           "差は8万100円でした。", "この計算を毎日出しています。登録してください。"]
    assert ev.is_request(end_only) and not ev.is_mid_request(end_only)
    assert ev.is_request(mid) and ev.is_mid_request(mid)


def test_終端に依頼が無い本は処置群でもない():
    """**両群とも `endcard: request` のまま**が、この A/B の前提です
    （期限 2026-10-11 の母集団を1本も減らさないため）。"""
    no_end = ["登録して次の数字を受け取ってください。", "差は8万100円でした。"]
    assert not ev.is_request(no_end)
    assert ev.is_mid_request(no_end)          # 途中には在る
    # だから群わけは `is_request` で先に絞ること（`mid_request_compliance` がそうしている）
    got = ev.mid_request_compliance([])
    assert got["数えた"] == 0 and got["従った率"] is None


def test_一行だけの読み上げは途中ありにならない():
    assert not ev.is_mid_request(["登録してください。"])
    assert not ev.is_mid_request([])


def test_台帳と道具が同じ床を言っている():
    """床 72本 を片方だけ動かしたら止める。"""
    from pathlib import Path

    import yaml

    from src.judgeable import ACCRUING, MEMBER_SOURCES, SOURCES

    _, n = MEMBER_SOURCES["request_form"]
    assert n == 72
    # **群がそろうまでは `Floor` で見張れません**（`ACCRUING` の docstring）。
    assert "request_form" in ACCRUING and "request_form" not in SOURCES
    text = (Path(__file__).resolve().parent.parent
            / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    assert f"どちらの群も {n}本 に満たなければ判定しない" in text
    doc = yaml.safe_load(text)
    hit = [h for h in doc["hypotheses"]
           if "終端だけでなく途中にも" in str(h.get("claim", ""))]
    assert len(hit) == 1 and hit[0]["lever"] == "sub_rate"
    need = hit[0]["needs"][0]
    assert need["kind"] == "accrual" and need["need"] == n
    assert "ab_members" in need["count_expr"] and "min(" in need["count_expr"]


def test_群がそろったら見張りに戻せる形になっている():
    """`ACCRUING` から外すだけで `Floor` の見張りに戻ること。

    **戻し方が1手でないと、誰も戻しません。** `MEMBER_SOURCES` は残してあるので、
    `ACCRUING` から名前を消せば `SOURCES` に入り、`floors()` が拾います
    （そのとき yaml の `needs` を `kind: group_key` / `key: request_form` に戻す）。
    """
    from src.judgeable import MEMBER_SOURCES, _days, members

    make, n = MEMBER_SOURCES["request_form"]
    got = _days(members("request_form"))
    assert set(got) == {"途中あり", "終端のみ"}, got
    assert n == 72
