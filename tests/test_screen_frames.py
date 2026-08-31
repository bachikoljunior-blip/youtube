"""**画面に出る文字の枠**が揃っていないか（2026-08-30 夜・解除条件3の続き）。

`tests/test_frame_forms.py` は**読み上げ**の側を見ています。こちらは**画面**です。

## なぜ別に要るか（実測）

解除条件3を閉じた回は、入口（`script_writer.OPENING_RULES` / `CLOSING_RULES`）も
出口（`verify._check_frame_repeat`）も**読み上げの文だけ**を相手にしていました。
控えの `*.plan.json`（655本・API 0単位）を同じ物差しで測ると、そこに同じ形が残っています:

    長尺 134本    読み上げの最終行の頭「明日やる」 61%
                  **最後のコマの見出し「明日やる」 83%**（実効 2.1本ぶん）
    ショート 521本 最後のコマの見出しが「あなたの」29% ＋「あなたは」25%

**読み上げより画面のほうが揃っていました。** 続けて数本 見た人が最初に気づくのは
目のほうなので、**片方だけ塞いでも「同じ動画に見える」は消えません。**
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import frames, legacy_corpus, script_writer, verify


#: 控えの読み上げを散らすための語。**数字を使わないこと** —— `frames.norm()` が
#: 数字を `N` に潰すので、「12万円が」「38万円が」は頭4文字が同じ `N万円が` になります
#: （この検査を書いた回が最初にそれで落ちました）。
_WORDS = ("勤続年数", "扶養の数", "住民税の帯", "賞与の月", "退職の月", "健康保険",
          "雇用保険", "所得の種類", "配偶者の欄", "医療費の合計")


def _plan(headline: str) -> list[dict]:
    return [{"kind": "stat", "headline": "入り口の数字", "stat": "12万円"},
            {"kind": "stat", "headline": headline, "stat": ""}]


def _script(headline: str, narration: list[str] | None = None) -> dict:
    lines = narration or ["38万円が境目でした。", "内訳です。", "崩れるのは賞与が入る場合です。"]
    segs: list[dict] = [{"narration": x} for x in lines]
    segs[-1]["visual"] = {"kind": "stat", "headline": headline}
    return {"segments": segs}


def _stash(tmp_path: Path, headlines: list[str], orientation: str = "横") -> Path:
    """`<id>.json`（読み上げ）と `<id>.plan.json`（画面）を**両方**書きます。

    **別々に欠けます。** 片方だけ在る回を作れることが、この道具の要点です。
    """
    st = tmp_path / "critique_queue"
    st.mkdir(exist_ok=True)
    for i, h in enumerate(headlines):
        vid = f"vid{i:03d}"
        (st / f"{vid}.json").write_text(json.dumps(
            {"video_id": vid, "topic": f"t-{i}",
             # **読み上げは全部ちがう**ものにします —— 落ちたら画面の門のせいだと分かる。
             # **数字で散らさないこと**（`norm()` が全部 `N` に潰すので、頭4文字が揃います）。
             "narration": [f"{_WORDS[i % len(_WORDS)]}は境目でした。", "内訳です。",
                           f"{_WORDS[(i + 3) % len(_WORDS)]}が変わると崩れます。"],
             "orientation": orientation, "stashed_at": f"2026-08-{i % 28 + 1:02d}T00:00:00Z"},
            ensure_ascii=False), encoding="utf-8")
        (st / f"{vid}.plan.json").write_text(
            json.dumps(_plan(h), ensure_ascii=False), encoding="utf-8")
    return st


# --- 物差しそのもの -------------------------------------------------------

def test_screen_axes_reads_the_last_headline():
    assert frames.screen_axes(_plan("明日やることです")) == {"screen_closing": "明日やる"}


def test_screen_axes_normalises_digits():
    """数字は `N` に潰すこと（`axes()` と同じ。**中身ではなく型**を見るため）。"""
    assert frames.screen_axes(_plan("2026年の限度額"))["screen_closing"] == "N年の限"


def test_screen_axes_survives_the_split_suffix():
    """割った後のコマは見出しに `2/2` や `＋…` が付きます。**頭4文字は動かない。**

    付く場所が頭に変わったら、この検査が先に落ちます（`_check_screen_frame_repeat`
    の「覆る条件」）。
    """
    assert (frames.screen_axes(_plan("明日やること　2/2"))["screen_closing"]
            == frames.screen_axes(_plan("明日やること"))["screen_closing"])


def test_screen_axes_is_empty_without_a_plan():
    assert frames.screen_axes([]) == {}
    assert frames.screen_axes(None) == {}
    assert frames.screen_axes([{"kind": "stat", "headline": "  "}]) == {}


def test_plan_of_returns_empty_when_the_file_is_missing(tmp_path):
    """`<id>.json` と `<id>.plan.json` は**別々に欠けます**（`build_perf` の註）。"""
    st = tmp_path / "critique_queue"
    st.mkdir()
    assert frames.plan_of("nope", st) == []


def test_screen_concentration_collapses_to_one(tmp_path):
    plans = [_plan("明日やること")] * 12
    c = frames.screen_concentration(plans)
    assert c["n"] == 12
    assert c["screen_closing"]["effective"] == pytest.approx(1.0)
    assert c["screen_closing"]["top_share"] == pytest.approx(1.0)


# --- 門 -------------------------------------------------------------------

def test_gate_falls_when_the_closing_headline_matches_the_window(tmp_path, monkeypatch):
    st = _stash(tmp_path, ["明日やること"] * 20)
    monkeypatch.setattr(frames, "STASH", st)
    problems = verify._check_frame_repeat(_script("明日やること"), portrait=False)
    assert any("最後のコマの見出し" in p for p in problems), (
        "**読み上げを散らしても、画面に同じ見出しが並べば同じ動画に見えます。**"
        f"落ちませんでした: {problems}")


def test_gate_passes_when_the_closing_headline_is_new(tmp_path, monkeypatch):
    st = _stash(tmp_path, ["明日やること"] * 20)
    monkeypatch.setattr(frames, "STASH", st)
    assert verify._check_frame_repeat(_script("賞与が入ると崩れる所"), portrait=False) == []


def test_gate_says_nothing_when_the_screen_history_is_too_shallow(tmp_path, monkeypatch):
    """**`*.plan.json` だけが薄い回**は「合格」ではなく「判定していない」。

    読み上げの控えは 20本 在るのに、画面は 3本しか読めない —— という形は実在します
    （実測: 台帳 694本 に対し `*.plan.json` は 655本）。
    """
    st = _stash(tmp_path, ["明日やること"] * 20)
    for p in sorted(st.glob("*.plan.json"))[3:]:
        p.unlink()
    monkeypatch.setattr(frames, "STASH", st)
    assert verify._check_frame_repeat(_script("明日やること"), portrait=False) == []


def test_gate_is_wired_into_the_narration_gate():
    """**同じ1回の呼び出しで両方 当たること。** 別の口にすると、片方だけ呼ぶ回が出ます。"""
    assert "_check_screen_frame_repeat" in verify._check_frame_repeat.__code__.co_names, (
        "画面の門が読み上げの門から呼ばれていません。"
        "**`script_only_problems()` に入っているのは読み上げの門のほうです**")


def test_the_entry_side_also_speaks_about_the_headline():
    """入口にも置くこと（**出口だけだと、書き直しの輪が毎回1周ぶん無駄になります**）。"""
    assert "CLOSING_HEADLINE_RULE" in script_writer.generate.__code__.co_names, (
        "締めの見出しの指示が指示文に足されていません")
    assert "明日やること" in script_writer.CLOSING_HEADLINE_RULE
    assert "あなたの" in script_writer.CLOSING_HEADLINE_RULE


# --- 実物に当てる ---------------------------------------------------------

def _real() -> list[dict]:
    if not frames.STASH.is_dir():
        pytest.skip("控えが無い実行環境")
    recs = [r for r in legacy_corpus.corpus() if r.get("plan")]
    if len(recs) < 100:
        pytest.skip(f"画面の読める控えが {len(recs)}本 しかない")
    return recs


def test_the_old_long_form_screen_would_be_caught():
    """**旧い長尺は、この門で落ちる側にあること。**

    落ちないなら、閾値か軸の取り方がまちがっています（旧い本の実測は 83%・
    `FRAME_MAX_SHARE` は 0.5）。**この数が 0.5 を下回ったら、
    「直った」のではなく「測る所がずれた」を先に疑うこと。**
    """
    recs = [r for r in _real() if r["orientation"] == "横"]
    if len(recs) < 50:
        pytest.skip("長尺の控えが薄い")
    c = frames.screen_concentration([r["plan"] for r in recs])
    assert c["screen_closing"]["top_share"] > verify.FRAME_MAX_SHARE, (
        f"旧い長尺の最頻が {c['screen_closing']['top_share']:.0%} まで落ちています。"
        "**軸の取り方がずれていないかを先に見ること**")


def test_the_screen_is_measured_by_the_persona_gate():
    """解除条件1・2 の物差しが、**画面の文字も分母に入れていること**。

    2026-08-30 夜まで `_as_script()` は読み上げしか渡しておらず、
    「画面は控えに無い」と註に書いてありました。**在りました。**
    """
    recs = _real()
    script = legacy_corpus._as_script(recs[0])
    assert any("visual" in s for s in script["segments"]), (
        "`_as_script()` が画面の文字を渡していません。"
        "**見ていないと書いてあるものは、本当に見ていないのかを確かめること**")


def test_no_persona_defect_on_the_screen_text():
    """**画面の側にも名乗りは1件も無いこと**（解除条件1・2の根拠を、当て直したもの）。

    ここが 0 でなくなったら、**解除条件1・2 を開き直すこと**
    （`AUTOMATION_PAUSED.md` の Resume gate。`data/resume_gate.jsonl` が正本）。
    """
    recs = _real()
    bad = []
    for r in recs:
        script = {"title": "", "segments": [{"visual": v} for v in r["plan"]]}
        if verify._check_no_human_expert_claim(script):
            bad.append(r["video_id"])
    assert not bad, f"画面に名乗りがある本: {bad[:5]}（{len(bad)}本）"
