"""**完成音声を最初から最後まで聞き取り、予定の読みと照合する**門の検査（2026-09-03）。

オーナー原文（`CLAUDE.md` 冒頭・**一字も変えないこと**）:
「Google TTSで生成した完成音声の最初から最後までを機械で聞き取り、
予定していた読みと照合し、誤読があれば修正・再生成して、もう一度全文照合する」
「やるようにして。」

**「やるようにして」＝ 毎本、機械がそうする形にすること。** ここが見るのは、
その形が `pipeline` と `verify` の両方に生きていることと、
**照合がカナで行われている**こと（表記で比べると誤読が消える）。

**音声認識の模型も API キーも要りません** —— 聞き取りの結果を文字列で渡して、
照合の側だけを見ます。
"""
from __future__ import annotations

import json

import pytest

from src import verify, yomi_gate, yomi_hear


# ---------------------------------------------------------------- 形が生きているか

def test_pipeline_が音を作った直後に照合する():
    """**絵を描く前**に当てること（直すのがいちばん安い所）。"""
    src = (yomi_hear.ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    assert "hear_and_fix(" in src, "pipeline から照合が消えている"
    body = src.split("def main(")[1]
    at_hear = body.index("hear_and_fix(script")
    at_draw = body.index("# 3. 図解を自前で描いて撮る")
    assert at_hear < at_draw, "照合が、絵を描いたあとに落ちている"


def test_verify_の門になっている():
    """**通らない本は出さない。** `check()` から撃たれていること。"""
    src = (yomi_hear.ROOT / "src" / "verify.py").read_text(encoding="utf-8")
    assert "_check_yomi_heard(path, work, script)" in src
    # 絵を描く前に撃たれる側（音がまだ無い）へ入れていないこと
    only = src.split("def script_only_problems(")[1].split("\ndef ")[0]
    assert "_check_yomi_heard" not in only


def test_道具が_requirements_に入っている():
    req = (yomi_hear.ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "faster-whisper" in req


# ---------------------------------------------------------------- 照合の中身

def test_正書法のゆれは畳む():
    """門2。助詞の ハ／ワ は読みの誤りではない。"""
    assert yomi_hear.norm("ワ") == yomi_hear.norm("ハ")
    assert yomi_hear.norm("オ") == yomi_hear.norm("ヲ")
    assert yomi_hear.norm("ジ") == yomi_hear.norm("ヂ")
    # 句読点・記号・英数はカナ比較から落とす（**ここが空振りの 9割 だった**）
    assert yomi_hear.norm("ガ、ク。？ ’") == "ガク"


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_同音の書き違いは割れない():
    """聞き取りの誤りのうち**同音のもの**は、カナで比べれば消える。

    **ここが「表記で比べない」理由そのもの**です。音声認識は言語模型を持っていて、
    同じ音を別の漢字に当てます —— 表記で比べると、その全部が「誤読」に化けます。
    """
    assert yomi_hear.compare("意外な結果です。", "以外な結果です。") == []
    assert yomi_hear.compare("保険料が上がります。", "保健料が上がります。") == []


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_読みの誤りは名指しされる():
    """2026-08-16 にオーナーが耳で見つけた誤読そのもの（額 → ヒタイ）。"""
    hits = yomi_hear.compare("実際の額は賃金日額で決まります。",
                             "実際の飛体は賃金日額で決まります。")
    assert [h["surface"] for h in hits] == ["額"], hits
    assert hits[0]["pron"] == "ガク" and hits[0]["heard"] == "ヒタイ"


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_漢字の無い語は名指ししない():
    """門1。送った側が仮名なら、直す当てが無い ＝ 聞き取りの誤り以外ではありえない。

    実測: 「そのあとは」を認識器が「その後は」と書き、アト 対 ゴ で割れた。
    """
    hits = yomi_hear.compare("そのあとは賃金の動きで改定されます。",
                             "その後は賃金の動きで改定されます。")
    assert hits == [], hits


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_送り仮名の書き違いは名指ししない():
    """門1b。活用語の末尾1モーラは送り仮名で、漢字の読みではない。

    実測: 認識器が「受け取る」を「受け取り」と書き、ウケトル 対 ウケトリ で割れた。
    """
    hits = yomi_hear.compare("働きながら受け取る年金の話です。",
                             "働きながら受け取り年金の話です。")
    assert [h["surface"] for h in hits] == [], hits


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_同じ語が何回出ても取り合わない():
    """1文に同じ語が4回 出ても、**1つの出現を4回 使い回さない**。

    2026-09-03 に踏んだ形の裏返し —— 差分の整列に頼っていた頃は、
    「賞与」が4回 出る文で **在る語を「消えた」と16件** 名指ししていた。
    """
    line = "賞与のがくで動かします。賞与が年120万円なら止まります。賞与が無ければ変わりません。賞与の有無で違います。"
    assert yomi_hear.compare(line, line.replace("がく", "額")) == []
    # 1つだけ潰したら、**1件だけ**名指しされること（4件でも 0件でもない）
    broken = line.replace("賞与が年", "小指が年", 1).replace("がく", "額")
    assert len(yomi_hear.compare(line, broken)) == 1


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_割れた語には聞こえた音が付く():
    """`confirm()` は「1回目で予定の読みが聞こえたか」から始まるので、
    **聞こえた側の音**を必ず持って回ること。"""
    hits = yomi_hear.compare("実際の額は賃金日額で決まります。",
                             "実際の飛体は賃金日額で決まります。")
    assert hits and all(h.get("heard") and h.get("pron") and "char" in h for h in hits)


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_隣の語の同じ音では見逃さない():
    """窓を広げすぎると、**別の語の中の同じ音**で誤読が消える。

    2026-09-03 に踏んだ: 窓 12 のとき「額（ガク）」が
    「日額（ニチガク）」の中の ガク で「聞こえている」ことになり、
    **既知の誤読を1件 取りこぼした。**
    """
    hits = yomi_hear.compare("実際の額は賃金日額で決まります。",
                             "実際の飛体は賃金日額で決まります。")
    assert [h["surface"] for h in hits] == ["額"]


# ---------------------------------------------------------------- 門の効き方

def _script(lines):
    return {"segments": [{"narration": x} for x in lines]}


def _report(lines, hits, **extra):
    rep = {"lines": len(lines), "words": 10, "split": len(hits), "hits": hits,
           "passes": 1, "model": "medium",
           "fingerprint": yomi_hear.fingerprint(lines),
           "misread": sum(1 for h in hits if h.get("verdict") == "misread")}
    rep.update(extra)
    return rep


def _work(tmp_path, lines, report):
    (tmp_path / "audio").mkdir(parents=True, exist_ok=True)
    (tmp_path / yomi_hear.REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_誤読が残る本は落ちる(tmp_path, monkeypatch):
    monkeypatch.setattr(yomi_hear, "available", lambda: True)
    lines = ["控除額を計算します。"]
    hit = {"seg": 0, "surface": "控除額", "pron": "コージョガク", "heard": "コージョヒタイ",
           "verdict": "misread"}
    work = _work(tmp_path, lines, _report(lines, [hit]))
    problems = verify._check_yomi_heard(tmp_path / "final.mp4", work, _script(lines))
    assert problems and "控除額" in problems[0], problems


def test_1文字の誤読では止めない(tmp_path, monkeypatch):
    """**直せない誤読で落とすと、その本は二度と通りません**（＝ 投稿が永久に止まる）。

    `yomi_gate.corrections()` は1文字の語を返しません（活用語幹を巻き込むため）。
    しかも 2026-09-03 の実測では、1文字の「予定の読み」自体が
    **熟語を切り損ねた跡**でした（月 → ツキ・年 → ネン）。
    """
    monkeypatch.setattr(yomi_hear, "available", lambda: True)
    assert not yomi_hear.fixable("月") and yomi_hear.fixable("控除額")
    lines = ["年金が月20万円の人は、いま月9万5000円が止まります。"]
    hit = {"seg": 0, "surface": "月", "pron": "ツキ", "heard": "ズケ", "verdict": "misread"}
    work = _work(tmp_path, lines, _report(lines, [hit]))
    assert verify._check_yomi_heard(tmp_path / "final.mp4", work, _script(lines)) == []


def test_割れても確定していなければ落とさない(tmp_path, monkeypatch):
    """`unclear` は認識器が届かなかっただけ。**止めると投稿が止まる。**"""
    monkeypatch.setattr(yomi_hear, "available", lambda: True)
    lines = ["実際の額は賃金日額で決まります。"]
    hit = {"seg": 0, "surface": "額", "pron": "ガク", "heard": "ガグ", "verdict": "unclear"}
    work = _work(tmp_path, lines, _report(lines, [hit]))
    assert verify._check_yomi_heard(tmp_path / "final.mp4", work, _script(lines)) == []


def test_控えが別の台本のものなら落ちる(tmp_path, monkeypatch):
    """音を作ったあとで読み上げが変わっていたら、**全文照合になっていない。**"""
    monkeypatch.setattr(yomi_hear, "available", lambda: True)
    lines = ["実際の額は賃金日額で決まります。"]
    work = _work(tmp_path, lines, _report(["別の文です。"], []))
    problems = verify._check_yomi_heard(tmp_path / "final.mp4", work, _script(lines))
    assert problems and "この台本のもの" in problems[0], problems


def test_控えも音も無ければ落ちる(tmp_path, monkeypatch):
    """**控えが無いのに素通りしない。** 「やるようにして」がここで破れる。"""
    monkeypatch.setattr(yomi_hear, "available", lambda: True)
    (tmp_path / "audio").mkdir(parents=True)
    lines = ["実際の額は賃金日額で決まります。"]
    problems = verify._check_yomi_heard(tmp_path / "final.mp4", tmp_path, _script(lines))
    assert problems, "控えも音も無いのに通った"


def test_聞ける道具が無い所では止めない(tmp_path, monkeypatch):
    """投稿が途切れるのが最大の損失（`CLAUDE.md` 4）。"""
    monkeypatch.setattr(yomi_hear, "available", lambda: False)
    lines = ["実際の額は賃金日額で決まります。"]
    assert verify._check_yomi_heard(tmp_path / "final.mp4", tmp_path, _script(lines)) == []


def test_指紋は読み上げだけで決まる():
    a = yomi_hear.fingerprint(["あ", "い"])
    assert a == yomi_hear.fingerprint(["あ", "い"])
    assert a != yomi_hear.fingerprint(["あ", "う"])


def test_誤読は台帳に正しい読みまで入る(tmp_path, monkeypatch):
    """`yomi_gate.corrections()` は `correct` の埋まった語しか返さない ——
    埋めなければ、見つけても**次の合成で直りません。**"""
    ledger = tmp_path / "yomi_ledger.json"
    queue = tmp_path / "yomi_queue.json"
    ledger.write_text(json.dumps({"words": {}}), encoding="utf-8")
    queue.write_text(json.dumps({"open": {}}), encoding="utf-8")
    monkeypatch.setattr(yomi_gate, "LEDGER_PATH", ledger)
    monkeypatch.setattr(yomi_gate, "QUEUE_PATH", queue)
    report = {"hits": [{"seg": 0, "surface": "控除額", "pron": "コージョガク",
                        "heard": "コージョヒタイ", "verdict": "misread",
                        "sentence": "控除額を計算します。"}]}
    fixed = yomi_hear.record(report)
    assert fixed == {"控除額": "コージョガク"}
    saved = json.loads(ledger.read_text(encoding="utf-8"))["words"]["控除額"]
    assert saved["verdict"] == "misread" and saved["correct"] == "コージョガク"
    assert yomi_gate.corrections()["控除額"] == "コージョガク"
