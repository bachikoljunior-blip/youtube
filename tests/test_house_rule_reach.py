"""**規則（1日1本）の下で、その前提はまだ満ちうるか。**（2026-08-31 に足した）

## なぜ要るか（**この回に実測した**）

`config/hypotheses.yaml` の `needs[].what` は、**未来の日に何本 公開しているか**を
前提にした要件をいくつも持っています。**どれも 2026-08-31 の規則より前に
書かれています**（実測: 開いた26件のうち **5件**）:

    「2026-09-02 の**12本すべて**の、公開から6時間 以上の読み」
    「09/10（16本 公開）の、公開から6時間たった読み」
    「`data/reach.jsonl` の 08/26〜09/07（長尺の予約 26本 ＝ 2.0本/日）」
    「`data/views.jsonl` の長尺 30本ぶん（08/29〜09/09 の長尺の予約は控えに 57本）」

規則1（公開は1日1本）と規則2（作り置きをしない ＝ 予約を池へ戻す）の下で、
**その日は来ません。** ところが `scripts/deadline_check.py` は
`[OK] …09/10 に出ます` と印字していました —— **永久に来ないデータを
「その日に出ます」と言っている**状態です。

**これは小さい話ではありません。** `scripts/eta.py` は
「**軌跡の腕が動くのは、前提を1件 閉じたときだけ**」と自分で印字しています。
満ちない要件を持った前提は閉じられないので、**到達日はそこで止まります。**

## この検査が固定するもの

    1. 判定は**規則の数から出る**こと（`PUBLISH_PER_DAY` を差し替えたら追随する）
    2. **過去の日は触らない**こと（もう起きたことなので、本数は事実）
    3. **読めないものは通す**こと（`is_stockpile` と同じ姿勢 ——
       測っていないことを、落とす側に倒さない）
    4. **止めないこと** —— 返すのは行だけで、何も落とさず、何も止めない

**覆る条件**: オーナーが規則を外したら、許す本数が増えてこの関数は自然に黙ります
（数をべた書きしていないので、この file も自動で追随します）。
"""
from __future__ import annotations

from src import house_rule


def test_未来の多本数の日は満ちないと言う():
    hit = house_rule.needs_beyond_rule(
        "09/10（16本 公開）の、公開から6時間たった読み（`data/views.jsonl`）",
        "2026-09-10", today="2026-08-31")
    assert hit is not None, "16本 公開 が 1日1本 の下で満ちる、と読んでいます"
    assert hit["named"] == 16
    assert hit["allowed"] == 10 * house_rule.PUBLISH_PER_DAY


def test_N本毎日という形は日数を掛けずに規則と比べる():
    """「2.0本/日」は**期日までの合計ではありません。** そのまま規則と比べること。"""
    hit = house_rule.needs_beyond_rule(
        "`data/reach.jsonl` の 08/26〜09/07（長尺の予約 26本 ＝ 2.0本/日）",
        "2026-09-07", today="2026-08-31")
    assert hit is not None
    assert hit["kind"] == "per_day"
    assert hit["named"] == 2.0
    assert hit["allowed"] == float(house_rule.PUBLISH_PER_DAY)


def test_規則の中に収まる要件は通す():
    assert house_rule.needs_beyond_rule(
        "09/03 の 1本の、公開から6時間たった読み", "2026-09-03",
        today="2026-08-31") is None


def test_過去の日は触らない():
    """**もう起きたことなので、本数は事実です。** 規則で否定しないこと。"""
    assert house_rule.needs_beyond_rule(
        "2026-08-20 の**25本すべて**の読み", "2026-08-20",
        today="2026-08-31") is None


def test_読めないものは通す():
    """測っていないことを、落とす側に倒さないこと（`is_stockpile` と同じ）。"""
    assert house_rule.needs_beyond_rule("", "2026-09-10", today="2026-08-31") is None
    assert house_rule.needs_beyond_rule("本数は書いていない", "", today="2026-08-31") is None
    assert house_rule.needs_beyond_rule("16本 公開", "だめな日付",
                                        today="2026-08-31") is None


def test_規則を動かすと判定も動く(monkeypatch):
    """**数をべた書きしないこと。** 出どころは `PUBLISH_PER_DAY` の1か所。"""
    what = "09/10（16本 公開）の読み"
    assert house_rule.needs_beyond_rule(what, "2026-09-10", today="2026-08-31")
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", 25)
    assert house_rule.needs_beyond_rule(what, "2026-09-10", today="2026-08-31") is None


def test_閉じた前提は数えない():
    rows = [{"claim": "閉じている", "closed_on": "2026-08-30",
             "needs": [{"on_date": "2026-09-10", "what": "09/10（16本 公開）の読み"}]}]
    assert house_rule.unreachable_needs(rows, today="2026-08-31") == []


def test_満ちない要件が無ければ1行も出さない():
    """**黙るときは完全に黙ること。** 見出しだけ出すと、次の回が誤読します。"""
    rows = [{"claim": "開いている", "deadline": "2026-09-10",
             "needs": [{"on_date": "2026-09-10", "what": "09/10 の 1本の読み"}]}]
    assert house_rule.unreachable_lines(rows, today="2026-08-31") == []


def test_行には何本と何本許されるかが並ぶ():
    """**裸の「満ちません」を出さないこと**（`CLAUDE.md` の (イ)）。"""
    rows = [{"claim": "1日に再生が付く本数の上限", "deadline": "2026-09-10",
             "needs": [{"on_date": "2026-09-10", "what": "09/10（16本 公開）の読み"}]}]
    lines = house_rule.unreachable_lines(rows, today="2026-08-31")
    body = "\n".join(lines)
    assert "16本" in body and "10本" in body, body
    assert "1日に再生が付く本数の上限" in body


def test_止める仕掛けにはなっていない():
    """**返すのは行だけ。** 何も落とさず、何も止めないこと（`CLAUDE.md` 2026-08-31）。"""
    rows = [{"claim": "x", "deadline": "2026-09-10",
             "needs": [{"on_date": "2026-09-10", "what": "09/10（16本 公開）の読み"}]}]
    before = list(rows)
    house_rule.unreachable_lines(rows, today="2026-08-31")
    assert rows == before, "入力を書き換えています"
    assert all(isinstance(l, str)
               for l in house_rule.unreachable_lines(rows, today="2026-08-31"))


def test_実物の台帳でも例外を出さない():
    """いまの `config/hypotheses.yaml` をそのまま通すこと。"""
    import yaml
    from pathlib import Path
    rows = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "config" / "hypotheses.yaml")
        .read_text(encoding="utf-8"))["hypotheses"]
    lines = house_rule.unreachable_lines(rows)
    assert isinstance(lines, list)
