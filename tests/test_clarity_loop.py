"""**説明が分かりやすいかの修正ループ**の検査（2026-09-03）。

オーナー原文（`CLAUDE.md` 冒頭・**一字も変えないこと**）:
「説明が分かりやすいかの修正ループ回してから、その全文照合修正ループ回すようにして」
「説明が分かりやすいかの修正ループは評価する時に分かりにくい部分を批判的に全て上げ、
1番可能性が高いものがほとんど言いがかりになったらループおわり。」
「修正してからまた初めから評価する」

ここが固定するのは4つ:

    1. **順番** —— 分かりやすさの輪が、音を作るより前・全文照合より前に居ること
    2. **「ほとんど言いがかり」の物差し** —— 門A（根拠が本文に在るか）と
       門B（独立にもう1回で再現するか）。**先頭が再現しなければ輪は終わる**
    3. **白紙から評価し直す** —— 前の周の列挙を1件も引き継がないこと
    4. **止め方** —— 同じ指摘が2周 先頭／書き直しで検査が増える／上限

**模型は1度も叩きません**（`reader` / `rewriter` を差し替えて回します）。
"""
from __future__ import annotations

import json

import pytest

from src import clarity_loop as C


# ---------------------------------------------------------------- 形が生きているか

def test_pipeline_は分かりやすさの輪を音より前に回す():
    """**逆にすると、照合した音が全部 捨てになります**（読み上げが変わるので）。"""
    src = (C.config.ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    assert "clarify_and_fix(script" in src, "pipeline から分かりやすさの輪が消えている"
    body = src.split("def main(")[1]
    at_clarity = body.index("clarify_and_fix(script")
    at_audio = body.index("# 2. 音声")
    at_hear = body.index("hear_and_fix(script")
    assert at_clarity < at_audio, "分かりやすさの輪が、音を作ったあとに落ちている"
    assert at_clarity < at_hear, (
        "オーナーの順（分かりやすさ → 全文照合）が逆になっている")


def test_分かりやすさの輪の後ろで読み上げを変えないこと():
    """**オーナー原文（2026-09-03 11:0x・`CLAUDE.md` 冒頭）**:

    > 「全ての改善が終わった後に、分かりやすさループを回して、
    >   それが終わったら読み照合ループにして」

    ＝ **分かりやすさの輪は、読み上げ本文を書き換える最後の手**です。
    ここより後ろに `narration` を書き換える行を足した瞬間、その順が破れます
    （輪が評価したのと違う本文が音になり、控えの指紋も合わなくなる）。
    """
    src = (C.config.ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    after = src.split("if clarify_and_fix(script")[1]
    # 輪そのものの書き戻し（`script.segments[i].narration = ...` は
    # `clarify_and_fix` の中だけ）より後ろに、代入が1つも無いこと
    bad = [ln.strip() for ln in after.splitlines()
           if ".narration =" in ln or '["narration"] =' in ln]
    assert not bad, (
        "分かりやすさの輪より後ろで読み上げを書き換えています: "
        f"{bad[:2]}。**オーナーの順（全ての改善 → 分かりやすさ → 読み照合）が破れます**")


def test_verify_の門になっていて_全文照合より前に並ぶ():
    src = (C.config.ROOT / "src" / "verify.py").read_text(encoding="utf-8")
    assert "_check_clarity_loop(work, script)" in src
    body = src.split("def check(")[1]
    assert body.index("_check_clarity_loop(") < body.index("_check_yomi_heard("), (
        "門の並びが、オーナーの順（分かりやすさ → 全文照合）と逆")
    # 絵を描く前に撃たれる側（本文しか無い）へ入れていないこと ——
    # あちらは輪より前に走るので、控えがまだ在りません
    only = src.split("def script_only_problems(")[1].split("\ndef ")[0]
    assert "_check_clarity_loop" not in only


def test_輪が落ちた回も控えを残す():
    """**輪の側の故障で、その日の投稿を落とさないこと。**

    `verify._check_clarity_loop` は控えが無ければ落とします。だから
    `clarify_and_fix` は、輪が例外で抜けた回にも控えを1つ置かなければいけません。
    """
    src = (C.config.ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    body = src.split("def clarify_and_fix(")[1].split("\ndef ")[0]
    assert "clarity_loop.REPORT_NAME" in body, (
        "輪が落ちた回に控えが残らない（`verify` がその本を落とします）")


def test_書き直したら台本を置き直して機械の検査を当て直す():
    src = (C.config.ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    body = src.split("if clarify_and_fix(script")[1][:900]
    assert 'work / "script.json"' in body, "書き換えた台本を置き直していない"
    assert "script_only_problems" in body, (
        "書き直しのあとに機械の検査を当て直していない"
        "（絵を全部 描いたあとで落ちます）")


def test_渡された台本にも書き戻す():
    """**`rebake_plan` の sha が毎回 食い違うのを防ぐ。**

    あちらは「控え（焼いて上げた本文）」と「`data/scripts/` の台本」の sha を
    比べて焼き直しを決めます。書き戻さないと、焼き直すたびに輪が本文を書き換え、
    **同じ本の焼き直しで `REBAKE_MAX_PER_DAY` を毎日 使い切ります。**
    """
    src = (C.config.ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    body = src.split("if clarify_and_fix(script")[1][:2000]
    assert "Path(args.script).write_text" in body, (
        "分かりやすさの書き直しを、渡された台本へ書き戻していない")


# ---------------------------------------------------------------- 門A（根拠）

LINES = [
    "六十五歳から受け取ると、基準の額がそのまま受け取れます。",
    "七十歳まで待つと、この二つの差はひと月あたりで広がっていきます。",
    "先ほどの線は、そちらの帯の左端と同じ位置にあります。",
]


def f(seg, quote, why="耳で取れない", fix="言い換える"):
    return C.Finding(seg=seg, quote=quote, why=why, fix=fix)


def test_本文に無い引用は落とす():
    """**本文に無い所を指しているものは、本文の評価ではありません。**"""
    good = f(2, "この二つの差はひと月あたり")
    bad = f(2, "この三つの差は一年あたりで縮みます")
    assert C.grounded([bad, good], LINES) == [good]


def test_短すぎる引用は根拠にならない():
    assert C.grounded([f(1, "額")], LINES) == []
    assert C.grounded([f(1, "基準の額")], LINES) != []


def test_コマ番号が範囲の外なら落とす():
    assert C.grounded([f(9, "六十五歳から受け取ると")], LINES) == []
    assert C.grounded([f(0, "六十五歳から受け取ると")], LINES) == []


def test_空白のゆれは畳むが文字は落とさない():
    assert C.span(f(1, "基準の 額が　そのまま"), LINES) is not None
    assert C.span(f(1, "基準の値がそのまま"), LINES) is None


# ---------------------------------------------------------------- 門B（再現）

def test_同じコマの重なる範囲に出れば再現():
    a = f(3, "先ほどの線は、そちらの帯の左端")
    b = f(3, "そちらの帯の左端と同じ位置")
    assert C.reproduced(a, [b], LINES) is not None


def test_別のコマなら再現ではない():
    a = f(3, "先ほどの線は、そちらの帯の左端")
    b = f(2, "この二つの差はひと月あたり")
    assert C.reproduced(a, [b], LINES) is None


def test_同じコマでも重ならなければ再現ではない():
    a = f(2, "七十歳まで待つと")
    b = f(2, "ひと月あたりで広がって")
    assert C.reproduced(a, [b], LINES) is None


# ---------------------------------------------------------------- 輪

def script_of(lines):
    return {"segments": [{"narration": x, "visual": {}} for x in lines]}


@pytest.fixture(autouse=True)
def _no_ledger(tmp_path, monkeypatch):
    """**帳面を本物に書かないこと**（検査は data/ を汚さない）。"""
    monkeypatch.setattr(C, "LEDGER", tmp_path / "clarity_loop.jsonl")
    monkeypatch.setattr(C, "mech_problems", lambda script, topic, portrait: [])


def test_先頭が再現しなければ輪は終わる_これがオーナーの止め方():
    """**「1番可能性が高いものがほとんど言いがかりになったらループおわり。」**"""
    script = script_of(LINES)
    calls = {"read": 0, "fix": 0}

    def reader(ls):
        calls["read"] += 1
        # 1回目と2回目で、先頭が別のコマ ＝ 再現しない
        return ([f(1, "六十五歳から受け取ると")] if calls["read"] % 2
                else [f(3, "先ほどの線は、そちらの帯")])

    def rewriter(ls, hits, extra=""):
        calls["fix"] += 1
        return {}

    rep = C.loop(script, "t", None, reader=reader, rewriter=rewriter, log=lambda *a: None)
    assert calls["fix"] == 0, "言いがかりで書き直しに行っている"
    assert len(rep["rounds"]) == 1
    assert rep["rounds"][0]["top_confirmed"] is False
    assert "言いがかり" in rep["reason"]
    assert rep["changed"] is False


def test_根拠のある指摘が0件でも終わる():
    script = script_of(LINES)
    rep = C.loop(script, "t", None,
                 reader=lambda ls: [f(1, "本文に無い言葉をここに書く")],
                 rewriter=lambda ls, h, e="": {}, log=lambda *a: None)
    assert rep["rounds"][0]["grounded"] == [0, 0]
    assert "根拠" in rep["reason"]


def test_再現したら直して_白紙から評価し直す():
    """**「修正してからまた初めから評価する」** —— 前の列挙を引き継がないこと。"""
    script = script_of(LINES)
    seen: list[list[str]] = []

    def reader(ls):
        seen.append(list(ls))
        if "先ほどの線" in ls[2]:
            return [f(3, "先ほどの線は、そちらの帯の左端")]
        return []                       # 直ったら、もう挙がらない

    def rewriter(ls, hits, extra=""):
        assert [h.seg for h in hits] == [3]
        return {2: "六十五歳の帯の左端と、七十歳の帯の左端は同じ位置にあります。"}

    rep = C.loop(script, "t", None, reader=reader, rewriter=rewriter, log=lambda *a: None)
    assert rep["fixed"] == 1
    assert rep["changed"] is True
    assert script["segments"][2]["narration"].startswith("六十五歳の帯")
    # 2周目の評価は、**書き換わった本文**を見ている（白紙から）
    assert "先ほどの線" in seen[0][2] and "先ほどの線" not in seen[-1][2]
    assert len(rep["rounds"]) == 2 and rep["rounds"][-1]["grounded"] == [0, 0]


def test_同じ指摘が2周_先頭に来たら止める():
    """書き直しがその文に触らなかった ＝ **この組では直らない**。"""
    script = script_of(LINES)
    rep = C.loop(script, "t", None,
                 reader=lambda ls: [f(3, "先ほどの線は、そちらの帯の左端")],
                 # 別のコマだけ書き換えて、指摘された文は触らない
                 rewriter=lambda ls, h, e="": {0: "六十五歳から受け取ると、基準の額が出ます。"},
                 log=lambda *a: None)
    assert "直らない" in rep["reason"]
    assert len(rep["rounds"]) == 2


def test_書き直しで機械の検査が増えたらその周を捨てる(monkeypatch):
    """**分かりやすくして検査に落ちるのは、退化です。**"""
    script = script_of(LINES)
    before = list(LINES)
    monkeypatch.setattr(C, "mech_problems",
                        lambda s, t, p: ([] if s["segments"][2]["narration"] == LINES[2]
                                         else ["画面に無い数を言っている"]))
    rep = C.loop(script, "t", None,
                 reader=lambda ls: [f(3, "先ほどの線は、そちらの帯の左端")],
                 rewriter=lambda ls, h, e="": {2: "新しい数 12万3000円 を足した文。"},
                 log=lambda *a: None)
    assert "増えた" in rep["reason"]
    assert [s["narration"] for s in script["segments"]] == before, (
        "捨てるはずの周が、台本に入っている")
    assert rep["changed"] is False


def test_上限で止まる():
    script = script_of(LINES)
    n = {"i": 0}

    def rewriter(ls, hits, extra=""):
        n["i"] += 1
        return {2: f"言い換えた文 その{n['i']}。先ほどの線は、そちらの帯の左端です。"}

    rep = C.loop(script, "t", None, rounds=2,
                 reader=lambda ls: [f(3, "先ほどの線は、そちらの帯の左端")],
                 rewriter=rewriter, log=lambda *a: None)
    assert len(rep["rounds"]) == 2
    assert "上限" in rep["reason"] or "直らない" in rep["reason"]


def test_評価が落ちても輪は例外を投げない():
    """**模型が落ちたのは、本の欠陥ではない。**"""
    def boom(ls):
        raise RuntimeError("網が落ちた")

    rep = C.loop(script_of(LINES), "t", None, reader=boom,
                 rewriter=lambda ls, h, e="": {}, log=lambda *a: None)
    assert "評価に失敗" in rep["reason"]


def test_控えを仕事場に置く(tmp_path):
    rep = C.loop(script_of(LINES), "t", tmp_path,
                 reader=lambda ls: [], rewriter=lambda ls, h, e="": {}, log=lambda *a: None)
    blob = json.loads((tmp_path / C.REPORT_NAME).read_text(encoding="utf-8"))
    assert blob["end"] == C.fingerprint(LINES) == rep["end"]


# ---------------------------------------------------------------- 門（verify）

def test_控えが無ければ落とす(tmp_path):
    from src import verify
    if not __import__("shutil").which("claude"):
        pytest.skip("claude コマンドが無い環境では、この門は素通りする")
    out = verify._check_clarity_loop(tmp_path, script_of(LINES))
    assert out and "控え" in out[0]


def test_控えの指紋が違えば落とす(tmp_path):
    from src import verify
    if not __import__("shutil").which("claude"):
        pytest.skip("claude コマンドが無い環境では、この門は素通りする")
    (tmp_path / C.REPORT_NAME).write_text(
        json.dumps({"end": "0" * 16, "reason": "誤読 0件", "rounds": []}),
        encoding="utf-8")
    out = verify._check_clarity_loop(tmp_path, script_of(LINES))
    assert out and "この読み上げのもの" in out[0]


def test_指紋が合えば通す(tmp_path):
    from src import verify
    (tmp_path / C.REPORT_NAME).write_text(
        json.dumps({"end": C.fingerprint(LINES), "reason": "言いがかり", "rounds": [{}]}),
        encoding="utf-8")
    assert verify._check_clarity_loop(tmp_path, script_of(LINES)) == []


def test_模型が落ちた回は落とさない(tmp_path):
    """**誤報は不投稿。** 網が落ちたことは、本の欠陥ではありません。"""
    from src import verify
    (tmp_path / C.REPORT_NAME).write_text(
        json.dumps({"end": C.fingerprint(LINES),
                    "reason": "評価に失敗（RuntimeError: 網が落ちた）", "rounds": []}),
        encoding="utf-8")
    assert verify._check_clarity_loop(tmp_path, script_of(LINES)) == []


# ---------------------------------------------------------------- 秒を測る
#
# **1周が何分かかるかを、誰も測れていませんでした**（2026-09-03 16:1x）。
# この輪は毎本の焼き直しの中に在り、焼く側は子の出力をまるごと呑んでいたので
# （`ahead_sweep._run_out` の註）、「焼き直しが 25分」の内訳が1つも取れていない。
# **上限 4周 を減らすかどうかの判定に、この数が要ります。**

def test_帳面に秒と時刻が入る(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "clarity_loop.jsonl"
    monkeypatch.setattr(C, "LEDGER", ledger)
    C.record({"topic": "t", "model": "m", "rounds": [{"seconds": 1.5}, {"seconds": 2.5}],
              "fixed": 3, "reason": "r", "changed": True,
              "at": "2026-09-03T07:00:00+00:00", "seconds": 4.0})
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["at"] == "2026-09-03T07:00:00+00:00"
    assert row["seconds"] == 4.0
    assert row["round_seconds"] == [1.5, 2.5]


def test_秒の欄が無い控えでも落ちない(tmp_path, monkeypatch) -> None:
    """**古い控えを読む回で投げないこと**（帳面を書けずに、輪ごと落ちます）。"""
    ledger = tmp_path / "clarity_loop.jsonl"
    monkeypatch.setattr(C, "LEDGER", ledger)
    C.record({"topic": "t", "model": "m", "rounds": [{}], "fixed": 0,
              "reason": "", "changed": False})
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["at"] == "" and row["seconds"] == 0 and row["round_seconds"] == [0]


# ---------------------------------------------------------------- 捨てるのは、増やしたコマだけ（2026-09-05）

def test_検査を増やしたコマだけ落として_残りの直しは活かす(monkeypatch):
    """**8コマ ぶんを全部 捨てない。** 実測 22本 中 5本 が「0件 → 1件」で 1コマも直さず出ていた。"""
    script = script_of(LINES)
    # コマ3 の書き直しだけが検査を増やす（コマ1 の書き直しは無害）
    monkeypatch.setattr(C, "mech_problems",
                        lambda s, t, p: (["1枚目が 22文字 を越えた"]
                                         if "新しい数" in s["segments"][2]["narration"] else []))
    n = {"read": 0}

    def reader(ls):
        n["read"] += 1
        if n["read"] <= 2:
            return [f(3, "先ほどの線は、そちらの帯の左端"), f(1, "六十五歳から受け取ると")]
        return []                       # 直ったら、もう挙がらない

    rep = C.loop(script, "t", None, reader=reader,
                 rewriter=lambda ls, h, e="": {0: "六十五歳の年金を受け取ると、基準の額のままです。",
                                               2: "新しい数 12万3000円 を足した文。"},
                 log=lambda *a: None)
    row = rep["rounds"][0]
    assert row["salvaged"] == [1] and row["dropped"] == [3]
    assert script["segments"][0]["narration"].startswith("六十五歳の年金")
    assert script["segments"][2]["narration"] == LINES[2], "増やしたコマが台本に入っている"
    assert rep["fixed"] == 1 and rep["changed"] is True
    assert "増えた" not in rep["reason"], "1コマ 残ったのに、周ごと捨てている"


def test_1コマも残らなければ前と同じく周を捨てる(monkeypatch):
    script = script_of(LINES)
    monkeypatch.setattr(C, "mech_problems",
                        lambda s, t, p: ([] if s["segments"][2]["narration"] == LINES[2]
                                         else ["画面に無い数を言っている"]))
    rep = C.loop(script, "t", None,
                 reader=lambda ls: [f(3, "先ほどの線は、そちらの帯の左端")],
                 rewriter=lambda ls, h, e="": {2: "新しい数 12万3000円 を足した文。"},
                 log=lambda *a: None)
    assert "増えた" in rep["reason"] and rep["changed"] is False
    assert "salvaged" not in rep["rounds"][0]


def test_帳面に何が増えたかと残した数が入る(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "mech_problems",
                        lambda s, t, p: (["1枚目が 22文字 を越えた"]
                                         if "新しい数" in s["segments"][2]["narration"] else []))
    n = {"read": 0}

    def reader(ls):
        n["read"] += 1
        return ([f(3, "先ほどの線は、そちらの帯の左端"), f(1, "六十五歳から受け取ると")]
                if n["read"] <= 2 else [])

    C.loop(script_of(LINES), "t", None, reader=reader,
           rewriter=lambda ls, h, e="": {0: "六十五歳の年金を受け取ると、基準の額のままです。",
                                         2: "新しい数 12万3000円 を足した文。"},
           log=lambda *a: None)
    row = json.loads(C.LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["broke"] == ["1枚目が 22文字 を越えた"]
    assert row["salvaged"] == 1 and row["dropped"] == 1
    assert row["confirmed_last"] == 0


# ---------------------------------------------------------------- 主語を声で言わせる（2026-09-05）

def test_主語が最初の3コマの声に無ければ書き直しに添える(monkeypatch):
    """実物 `vmAll8GDkU8`: 27コマ の読み上げに「ふるさと納税」が1度も無い（画面には在る）。"""
    monkeypatch.setattr(C.config, "load_topics",
                        lambda: {"topics": [{"id": "s-x", "calc": "furusato"}]})
    silent = ["通知書の額は、寄付額より小さくても正常です。".replace("寄付", "きふ"),
              "内訳は基本分と特例分です。", "合計。これが通知書に載る額です。"]
    note = C.subject_note("s-x", silent)
    assert "ふるさと納税" in note and "22文字" in note
    assert C.subject_note("s-x", ["ふるさと納税をした人の通知書です。"] + silent[1:]) == ""
    assert C.subject_note("", silent) == ""
    assert C.subject_note("s-unknown", silent) == ""


def test_主語の段は書き直しの指示に乗る(monkeypatch):
    monkeypatch.setattr(C.config, "load_topics",
                        lambda: {"topics": [{"id": "s-x", "calc": "furusato"}]})
    got = {}

    def rewriter(ls, hits, extra=""):
        got["extra"] = extra
        return {}

    rep = C.loop(script_of(LINES), "s-x", None,
                 reader=lambda ls: [f(1, "六十五歳から受け取ると")],
                 rewriter=rewriter, log=lambda *a: None)
    assert "ふるさと納税" in got["extra"]
    assert rep["rounds"][0]["subject_asked"] is True
