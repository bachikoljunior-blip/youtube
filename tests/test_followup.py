"""`src/followup.py` —— **外れた前提の「次の手」が消えないこと**を見る検査。

ここが落ちると、実験を閉じても**その代金（`next_if_false`）が回収されません。**
`eta.py` は「軌跡の腕が動くのは前提を1件閉じたときだけ」と印字していて、
閉じたときに手に入るのはその1行だけです。**消えたら、輪が空回りします。**

**いちばん大事なのは「消せない」ことのほう**なので、
「見た」「確認」のような**日付も採否も無い行で消せない**検査を先に置いています。
"""

from __future__ import annotations

from datetime import date

from src import followup

TODAY = date(2026, 8, 26)


def _doc(**over):
    h = {
        "claim": "テスト用の前提",
        "outcome": "falsified",
        "closed_on": date(2026, 8, 20),
        "lever": "per_video",
        "next_if_false": ["手A", "手B"],
    }
    h.update(over)
    return {"hypotheses": [h]}


def test_外れた前提の手は_記録するまで残る():
    rows = followup.pending(_doc(), TODAY)
    assert [r["step"] for r in rows] == ["手A", "手B"]
    assert all(r["age_days"] == 6 for r in rows)


def test_採用を書いた手だけが消える():
    rows = followup.pending(_doc(next_done=["2026-08-25 採用: やった"]), TODAY)
    assert [r["step"] for r in rows] == ["手B"], "並びで対応するので、消えるのは1件目だけ"


def test_却下も_正しい記録として消える():
    """**却下は正しい答えです。** 消えないと、正直に見送った回が罰されます。"""
    rows = followup.pending(_doc(next_done=["2026-08-25 却下: 桁が足りない",
                                            "2026-08-25 却下: 同上"]), TODAY)
    assert rows == []


def test_日付も採否も無い行では消せない():
    """**これがこの道具の本体です。**

    「見た」で消せる形にしたら、`status.py` が長らくやっていた
    「書かれているかだけ見る」に戻ります。
    """
    rows = followup.pending(_doc(next_done=["見た", "確認済み"]), TODAY)
    assert len(rows) == 2
    assert all(r["partial"] for r in rows), "書きかけとして、そう言うこと"


def test_日付だけ_採否だけでも消せない():
    rows = followup.pending(_doc(next_done=["2026-08-25 見た", "採用した"]), TODAY)
    assert len(rows) == 2


def test_生き残った前提の手は_出さない():
    """`survived` の `next_if_false` は**実行してはいけない手**です。"""
    assert followup.pending(_doc(outcome="survived"), TODAY) == []


def test_半々は出す():
    """`mixed` は半分外れているので、その手は生きています。"""
    assert len(followup.pending(_doc(outcome="mixed"), TODAY)) == 2


def test_文字列で書かれた次の手を_1字ずつ回さない():
    """**2026-08-17 の実物の穴。** `status.py` の出力 644行のうち 480行が1字になりました。"""
    rows = followup.pending(_doc(next_if_false="ひとつめの手\n\nふたつめの手"), TODAY)
    assert [r["step"] for r in rows] == ["ひとつめの手", "ふたつめの手"]


def test_猶予を超えた手があれば_止める側に倒れる():
    text, overdue = followup.report(_doc(), TODAY)
    assert overdue is True
    assert "外れた前提" in text

    fresh = _doc(closed_on=TODAY)
    _, overdue_fresh = followup.report(fresh, TODAY)
    assert overdue_fresh is False, "閉じたその日は止めない（判定は夜・実装は翌朝でよい）"


def test_同じ腕の開いた前提を_候補として並べる():
    doc = _doc()
    doc["hypotheses"].append({"claim": "まだ開いている前提", "lever": "per_video",
                              "deadline": date(2026, 9, 1)})
    assert followup.open_on_lever(doc, "per_video") == ["まだ開いている前提"]


def test_実物の台帳が読める():
    """**実物で落ちること自体は正常です**（未記録の手が残っている状態）。

    見ているのは「読めること」だけ —— 欄が増えても壊れないこと。
    """
    doc = followup.load()
    assert doc.get("hypotheses"), "config/hypotheses.yaml が読めていない"
    for r in followup.pending(doc):
        assert r["step"] and isinstance(r["step"], str)
        assert r["index"] < r["n_steps"]


# --- 束（`docs/MEANS.md` の M番号で束ねる） -----------------------------------
#
# **文字 n-gram で束ねた最初の実装は、文法を拾ったので捨てました**
# （「…と確定させ…」で、形式の話と説明欄の話が同じ束になった）。
# ここが守るのは「**話題ではなく参照で束ねている**」ことです。

def _rows(*steps):
    return [{"claim": f"前提{i}", "closed_on": date(2026, 8, 20 + i),
             "step": s, "lever": "per_video", "age_days": 6,
             "index": 0, "n_steps": 1, "partial": None}
            for i, s in enumerate(steps)]


def test_同じM番号を指す手は_束になる():
    cs = followup.clusters(_rows("形式そのものを疑う（M5 か M2 へ）",
                                 "M5（RPM の高いニッチ）へ移る"))
    assert [c["means"] for c in cs][:1] == ["M5"]
    assert len(cs[0]["keys"]) == 2


def test_言い回しが同じでも_参照が無ければ束にならない():
    """**これが n-gram 版を捨てた理由です。**"""
    cs = followup.clusters(_rows("タイトルだけでは載らないと確定させる",
                                 "説明欄は読まれていないと確定させる",
                                 "6 は揺らぎだったと確定させる"))
    assert cs == [], "文法で束ねないこと"


def test_同じ前提の中で同じMを2回書いても_1件と数える():
    assert followup.clusters(_rows("M5 へ。やはり M5 だ")) == []


def test_M番号の無い台帳では_黙る():
    """**薄いのは既知です。黙るほうが、間違った束を出すより良い。**"""
    assert followup.clusters(_rows("冒頭を短くする", "色を変える")) == []
