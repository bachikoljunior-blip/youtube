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

#: **超える本数を、規則から作ること**（2026-09-05 に書き替えた）。
#:
#: ここは「16本」「2.0本/日」をべた書きし、`PUBLISH_PER_DAY = 1` の下で
#: 「満ちない」を見ていました。2026-09-05 に規則が 10本/日 になると
#: **16本 も 2.0本/日 も規則の中に収まり**、この file の「満ちないと言う側」の
#: 検査が4件とも、満ちる場面を測る形へ化けます（実際に赤くなりました）。
#:
#: この file の冒頭は「**数をべた書きしていないので、この file も自動で追随します**」
#: と書いていました。**追随したのは算数だけで、場面は写しでした。**
#: **覆る条件**: `needs_beyond_rule` が「日数 × 上限」以外の式になったら作り直すこと。
_DAYS = 10                                          # 2026-08-31 → 2026-09-10
_ALLOWED = _DAYS * house_rule.PUBLISH_PER_DAY       # 規則の下で許される合計
_NAMED = _ALLOWED + 6                               # **わざと超える**本数
_PER_DAY_NAMED = float(house_rule.PUBLISH_PER_DAY) + 1.0    # 1日あたりで超える


def test_未来の多本数の日は満ちないと言う():
    hit = house_rule.needs_beyond_rule(
        f"09/10（{_NAMED}本 公開）の、公開から6時間たった読み（`data/views.jsonl`）",
        "2026-09-10", today="2026-08-31")
    assert hit is not None, \
        f"{_NAMED}本 公開 が {house_rule.PUBLISH_PER_DAY}本/日 の下で満ちる、と読んでいます"
    assert hit["named"] == _NAMED
    assert hit["allowed"] == _ALLOWED


def test_N本毎日という形は日数を掛けずに規則と比べる():
    """「N本/日」は**期日までの合計ではありません。** そのまま規則と比べること。"""
    hit = house_rule.needs_beyond_rule(
        f"`data/reach.jsonl` の 08/26〜09/07（長尺の予約 26本 ＝ {_PER_DAY_NAMED}本/日）",
        "2026-09-07", today="2026-08-31")
    assert hit is not None
    assert hit["kind"] == "per_day"
    assert hit["named"] == _PER_DAY_NAMED
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
    what = f"09/10（{_NAMED}本 公開）の読み"
    assert house_rule.needs_beyond_rule(what, "2026-09-10", today="2026-08-31")
    # **緩める先も、いまの規則から作ること**（25 のべた書きは、規則が 25 を
    # 超えた日に「緩めたのに黙らない」で赤くなります）。
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", _NAMED)
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
             "needs": [{"on_date": "2026-09-10",
                        "what": f"09/10（{_NAMED}本 公開）の読み"}]}]
    lines = house_rule.unreachable_lines(rows, today="2026-08-31")
    body = "\n".join(lines)
    assert f"{_NAMED}本" in body and f"{_ALLOWED}本" in body, body
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
