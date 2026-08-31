"""**同じ入り方・同じ締め方が並ばないこと。**（2026-08-30・停止の解除条件3）

## なぜ要るか

`AUTOMATION_PAUSED.md` の解除条件は6件で、閉じたのは 1・2・5・6。
残る **3（final videos are materially varied and demonstrate a clear original
creative contribution）が本当の関門**だと、同じ日の回が `CLAUDE.md` と
`AUTOMATION_PAUSED.md` の両方に書きました。いま縛っているのは
(A) AI ペルソナではなく **(B) 汎用・反復** のほうです:

    AI-generated content made with generic or unoriginal templates
    giving the impression of mass production

**実物がありました。** `python -m src.frames` の実測（控え694本）:

    長尺 134本   1行目の頭4文字  「計算しま」 **84%**（113本）＝ 実効 **2.4本ぶん**
                 最終行の頭4文字 「明日やる」 **61%**（82本）＝ 実効 **3.8本ぶん**
    ショート 558本 最終行の頭4文字「あなたの」 **45%**（251本）
                 最終行の末尾6文字「てください。」**40%**（222本）

**中身は散っています**（題の族 526・出だしの形 689／694本。
`src.legacy_corpus.variety()`）。**揃っていたのは枠だけ**です。

そして**それは書き手の癖ではなく、指示文への直書きの写し**でした ——
`ROLE` に「『調べてみました』ではなく『計算しました』」「最後のセグメントは
『明日やること』」「例:『あなたの手当は全員同額ですか。…』」と書いてありました。

## ここで固定するもの（6つ）

1. 振り分けが**テーマIDだけで決まり、同じIDなら何度でも同じ**であること
2. 塩が既存の3つ（無塩 / `hook:` / `midreq:`）と**別**であること
   —— 同じにすると2つの振り分けが完全に重なり、**どちらが効いたか永久に分からない**
3. 割り当てが**実在のテーマIDで実際に散る**こと（**上限 ≤ 35%**）
4. ショートの締め方が **4通りとも「登録」を要求する**こと
   —— `src/endcard_verdict.is_request()` が最終行の「登録」だけで処置群を作っており、
   `config/hypotheses.yaml` 期限 2026-10-11 がそこにぶら下がっています。
   **落とすと処置群が黙って空になります**（向こうの docstring が名指しで警告）
5. `verify._check_frame_repeat()` が**揃った枠を落とす**こと
6. それが `script_only_problems()` に入っていること（＝ **クリップを焼く前**に当たる）

## 覆る条件

- **通り数を4から増やしたら、`verify.FRAME_MAX_SHARE` を下げること**
  （4通りで 0.5 は「期待の2倍」。8通りなら 0.3 が同じ厳しさ）
- 見る場所（頭4文字・末尾6文字）は `src/frames.py` の定数。**2か所に写さないこと**
- 実在する形が変わって偽陽性が出たら、**指示文へ決まり文句を戻すことでは直さないこと**
  —— それが元の穴です
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import frames  # noqa: E402
from src import script_writer as sw  # noqa: E402
from src import verify  # noqa: E402


# ---------------------------------------------------------------------------
# 1. 振り分けはテーマIDだけで決まる
# ---------------------------------------------------------------------------

def test_forms_are_deterministic_so_a_rebuild_keeps_the_same_frame():
    """撃ち直しで型が変われば、`frames` の測り直しが揺れます。"""
    for tid in ("iryohi-kojo-1", "s-nenkin-kuriage-3", "kyufu-3"):
        assert sw.opening_form(tid) == sw.opening_form(tid)
        assert sw.closing_form(tid, portrait=True) == sw.closing_form(tid, portrait=True)
        assert sw.closing_form(tid, portrait=False) == sw.closing_form(tid, portrait=False)


def test_forms_come_from_the_declared_sets():
    for tid in ("a", "b", "c", "d", "e", "f"):
        assert sw.opening_form(tid) in sw.OPENING_FORMS
        assert sw.closing_form(tid, portrait=False) in sw.CLOSING_FORMS_LONG
        assert sw.closing_form(tid, portrait=True) in sw.CLOSING_FORMS_SHORT


def test_every_form_has_a_rule_or_the_prompt_would_raise_KeyError():
    """`generate()` は `OPENING_RULES[opening]` を素で引きます。**欠けたら本番で落ちます。**"""
    for f in sw.OPENING_FORMS:
        assert f in sw.OPENING_RULES, f"入り方 {f} の指示文がありません"
    for f in sw.CLOSING_FORMS_LONG + sw.CLOSING_FORMS_SHORT:
        assert f in sw.CLOSING_RULES, f"締め方 {f} の指示文がありません"


# ---------------------------------------------------------------------------
# 2. 塩が既存の振り分けと別であること
# ---------------------------------------------------------------------------

def test_salts_differ_from_the_existing_three_assignments():
    """**同じ塩にすると、2つの振り分けが完全に重なります。**

    `title_form`（無塩）/ `hook_form`（`hook:`）/ `request_form`（`midreq:`）と
    独立であることを、実在しそうなIDを並べて見ます。**完全一致が無いこと**を見ます
    （相関の強さではなく、**写しになっていないこと**を見るのが目的）。
    """
    ids = [f"topic-{i}" for i in range(400)]
    opening = [sw.opening_form(i) for i in ids]
    closing = [sw.closing_form(i, portrait=True) for i in ids]

    # 2値の振り分けと4値の振り分けは、そもそも同じ列にならない。
    # 見るのは「入り方」と「締め方」が互いの写しになっていないこと。
    assert opening != closing, "入り方と締め方が完全に同じ列です（塩が同じ）"
    pairs = collections.Counter(zip(opening, closing))
    # 4×4＝16通りのうち、実際に出る組み合わせが十分に散っていること。
    assert len(pairs) >= 12, f"組み合わせが {len(pairs)}通りしか出ていません（塩が近い）"

    # 既存の2値の振り分けとも、片方に貼り付いていないこと。
    for other in (sw.title_form, sw.hook_form, lambda t: sw.request_form(t)):
        vals = [other(i) for i in ids]
        for form in sw.OPENING_FORMS:
            sub = [v for v, o in zip(vals, opening) if o == form]
            if len(sub) < 20:
                continue
            top = collections.Counter(sub).most_common(1)[0][1] / len(sub)
            assert top < 0.85, (
                f"入り方 {form} が、既存の振り分けの片側に {top:.0%} 寄っています。"
                "塩を変えること（重なると、どちらが効いたのか分かりません）")


# ---------------------------------------------------------------------------
# 3. 実在のテーマIDで、実際に散ること
# ---------------------------------------------------------------------------

def _ledger_topic_ids() -> list[str]:
    from src import legacy_corpus as lc
    return sorted({str(r.get("topic") or "") for r in lc._rows().values() if r.get("topic")})


@pytest.mark.parametrize("fn,label", [
    (sw.opening_form, "opening"),
    (lambda t: sw.closing_form(t, portrait=False), "closing_long"),
    (lambda t: sw.closing_form(t, portrait=True), "closing_short"),
])
def test_assignment_spreads_on_the_real_topic_ids(fn, label):
    """**上限 ≤ 35%。** いまの控えの最頻は 84% / 61% / 45% です。

    ここが本命の数字 —— **生成が止まっていても、割り当ては今日 数えられます。**
    """
    ids = _ledger_topic_ids()
    if len(ids) < 100:
        pytest.skip(f"台帳のテーマIDが {len(ids)}件 しかありません")
    c = collections.Counter(fn(i) for i in ids)
    top = c.most_common(1)[0][1] / len(ids)
    assert top <= 0.35, f"{label} の最頻が {top:.0%}（{c.most_common()}）"
    assert frames.effective(list(fn(i) for i in ids)) >= 3.5, (
        f"{label} の実効の型数が 3.5通りを下回りました")


# ---------------------------------------------------------------------------
# 4. ショートの締めは、4通りとも「登録」を残すこと
# ---------------------------------------------------------------------------

def test_short_closings_all_keep_the_subscribe_word():
    """**落とすと `endcard_verdict.is_request()` の処置群が黙って空になります。**

    `config/hypotheses.yaml` 期限 2026-10-11「ショートの最後で登録を直接1回頼むと、
    登録率が上がる」の処置群は「最終行に『登録』が入っている本」です。
    向こうの docstring が「**変えた回が足さないと、処置群が黙って空になります**」と
    警告しており、この振り分けは**依頼の有無ではなく位置と前置きだけ**を変えます。
    """
    from src import endcard_verdict

    for form in sw.CLOSING_FORMS_SHORT:
        rule = sw.CLOSING_RULES[form]
        assert "登録" in rule, f"ショートの締め方 {form} が「登録」を求めていません"
    # 判定側が見ている語そのものであること（規則と道具を離さない）。
    assert endcard_verdict.is_request(["この計算を毎日出しています。登録してください。"])
    assert not endcard_verdict.is_request(["コメントで教えてください。"])


def test_short_closings_do_not_reinstate_the_retired_opener():
    """「あなたの◯◯は」は 45% を占めていた型。**4通りとも禁じていること。**"""
    for form in sw.CLOSING_FORMS_SHORT:
        assert "「あなたの◯◯は」で始めないこと" in sw.CLOSING_RULES[form], (
            f"ショートの締め方 {form} が、退役した書き出しを禁じていません")


def test_retired_phrases_are_no_longer_prescribed_in_the_prompt():
    """**指示文に決まり文句を戻さないこと** —— 84% / 61% はその写しでした。"""
    role = sw.ROLE + sw.TASK
    assert "ではなく「計算しました」" not in role, (
        "`ROLE` に「計算しました」を既定の書き出しとして戻しています"
        "（長尺 134本の 84% がこの4文字で始まっていました）")
    assert "最後のセグメントは「明日やること」を手順として言う" not in role, (
        "`ROLE` が「明日やること」を長尺の既定に戻しています（61%）")
    assert "あなたの手当は全員同額ですか" not in role, (
        "`ROLE` にショートの締めの実例が戻っています（例文がそのまま型になりました）")


# ---------------------------------------------------------------------------
# 5-6. 出口の門
# ---------------------------------------------------------------------------

def _stash(tmp_path: Path, narrations: list[list[str]], orientation: str = "横") -> Path:
    import json
    st = tmp_path / "critique_queue"
    st.mkdir()
    for i, n in enumerate(narrations):
        (st / f"vid{i:03d}.json").write_text(json.dumps(
            {"video_id": f"vid{i:03d}", "topic": f"t-{i}", "narration": n,
             "orientation": orientation, "stashed_at": f"2026-08-{i % 28 + 1:02d}T00:00:00Z"},
            ensure_ascii=False), encoding="utf-8")
    return st


def _script(narration: list[str]) -> dict:
    return {"segments": [{"narration": x} for x in narration]}


def test_gate_falls_when_the_frame_matches_most_of_the_recent_window(tmp_path, monkeypatch):
    same = ["計算しました。年収500万円では12万円です。", "内訳です。", "明日やることです。まず源泉徴収票。"]
    st = _stash(tmp_path, [same] * 20)
    monkeypatch.setattr(frames, "STASH", st)
    problems = verify._check_frame_repeat(_script(same), portrait=False)
    assert problems, "揃った枠が落ちていません"
    assert any("計算しま" in p for p in problems)
    assert any("明日やる" in p for p in problems)


def test_gate_passes_when_the_frame_is_new(tmp_path, monkeypatch):
    old = ["計算しました。年収500万円では12万円です。", "内訳です。", "明日やることです。まず源泉徴収票。"]
    st = _stash(tmp_path, [old] * 20)
    monkeypatch.setattr(frames, "STASH", st)
    fresh = ["38万円が境目でした。1円こえると、この控除は消えます。", "内訳です。",
             "この計算が崩れるのは、賞与が入る場合です。"]
    assert verify._check_frame_repeat(_script(fresh), portrait=False) == []


def test_gate_says_nothing_when_the_history_is_too_shallow(tmp_path, monkeypatch):
    """**新しい実行環境では控えがゼロになります**（`src/bars.py` と同じ事故）。

    そこで「比較対象が無い＝合格」と黙るのではなく、**判定していない**と印字すること。
    """
    same = ["計算しました。12万円です。", "明日やることです。"]
    st = _stash(tmp_path, [same] * 3)
    monkeypatch.setattr(frames, "STASH", st)
    assert verify._check_frame_repeat(_script(same), portrait=False) == []


def test_gate_ignores_the_other_orientation(tmp_path, monkeypatch):
    """長尺の型でショートを落とさないこと（見ている群がちがいます）。"""
    same = ["計算しました。12万円です。", "明日やることです。まず源泉徴収票。"]
    st = _stash(tmp_path, [same] * 20, orientation="横")
    monkeypatch.setattr(frames, "STASH", st)
    assert verify._check_frame_repeat(_script(same), portrait=True) == []


def test_gate_excludes_my_own_earlier_attempt(tmp_path, monkeypatch):
    """撃ち直した自分の前の案を相手にしないこと（`used_bars` と同じ理由）。"""
    import json
    same = ["計算しました。12万円です。", "明日やることです。まず源泉徴収票。"]
    st = _stash(tmp_path, [same] * 20)
    for p in sorted(st.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["topic"] = "mine"
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(frames, "STASH", st)
    assert verify._check_frame_repeat(_script(same), portrait=False, topic_id="mine") == []


def test_gate_is_wired_into_the_pre_render_list():
    """**クリップを焼く前**に当たること（`tests/test_script_gate_before_render.py` と対）。"""
    assert "_check_frame_repeat" in verify.script_only_problems.__code__.co_names, (
        "`script_only_problems()` が枠の門を撃っていません。"
        "**レンダリング後に落とすと1本まるごと捨てです**")


def test_generate_appends_both_rules():
    """`generate()` が両方の指示文を足していること（片方だけだと型が半分しか散りません）。"""
    import inspect
    src = inspect.getsource(sw.generate)
    assert "OPENING_RULES[" in src and "CLOSING_RULES[" in src, (
        "`generate()` が入り方／締め方の指示文を足していません")


# ---------------------------------------------------------------------------
# 物差しそのもの
# ---------------------------------------------------------------------------

def test_effective_counts_distinct_frames_not_the_mode():
    assert frames.effective(["a"] * 10) == pytest.approx(1.0)
    assert frames.effective(list("abcdefghij")) == pytest.approx(10.0)
    # 8割が1つの型なら、残りが何通りあっても 2 前後にしかならない。
    skewed = ["a"] * 80 + [f"x{i}" for i in range(20)]
    assert 1.5 < frames.effective(skewed) < 3.5


def test_axes_drop_blank_lines_so_empty_stashes_are_not_counted_as_one_frame():
    assert frames.axes(["", "  ", "計算しました。"])["opening"] == "計算しま"
    assert frames.axes([]) == {}
    assert frames.axes(["", " "]) == {}


def test_axes_collapse_digits_so_the_same_frame_is_not_counted_as_different():
    a = frames.axes(["500万円が境目です。", "締めです。"])
    b = frames.axes(["380万円が境目です。", "締めです。"])
    assert a["opening"] == b["opening"], "数字だけ違う同じ型が、別の型に数えられています"
