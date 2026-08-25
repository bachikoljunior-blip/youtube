"""**長尺にも「落ちたら書き直させる輪」が掛かっていること**を固定する。

## なぜ要るか（2026-08-24 の実測）

`generate()` の作り直しの輪は、長らく `if max_minutes <= 1.5 and session:` の
中にありました。**ショート専用です。** 長尺には直す口が1つもありませんでした。

    ショート  08-24 は 10/10 通過   ← 落ちても3回まで書き直せる
    長尺      0/3・0/8              ← 書き直す口が無い

落ちた 3/3 は全部 `verify._check_not_repeat`（過去の図と棒が2本以上共通）で、
当たるのは `claude -p` に約250秒使ったあとの `src/pipeline.py` です。
そこには直す口が無いので、**その1本は丸ごと捨て**になっていました。

しかも落ちていた中身は、**書き直しで直る種類**でした ——
`120万円・240万円・360万円・480万円・600万円` は 120万円の1〜5倍の
「等差の梯子」で、何も計算していません。丸い数の空間は狭いので、
**梯子を出す動画は他の梯子の動画と必ずぶつかります。**

## ここで固定すること

1. **輪の条件が「ショートのときだけ」に戻らないこと** —— これが本体。
   `long_script_problems` を足しても、`generate()` から呼ばれていなければ
   **緑のまま何も起きません**（`test_calc_source_in_loop.py` と同じ穴）
2. **長尺の直し方の本文を、ショートのものに戻さないこと** ——
   ショートの本文は「140文字に削る」「セグメントを2つに割る」で、
   長尺には1行も当てはまりません。**長尺は4分を下回ると落ちる**ので、
   削れと言うと逆向きに壊れます
3. **梯子（過去と重なる棒）を、長尺の側で捕まえること**
4. **通る台本を落とさないこと** —— 偽陽性が怖い側です。
   落とすと投稿が止まり、それが最大の損失にあたります
5. **例外を投げないこと** —— 生成中に呼ばれるので、落ちると台本作りごと止まる
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import script_writer  # noqa: E402


# --- 台本の身代わり（`model_dump()` と属性の両方から読まれる） -----------------

class _V:
    def __init__(self, d):
        self._d = d
        self.headline = d.get("headline", "")
        self.kind = d.get("kind", "")

    def model_dump(self):
        return dict(self._d)


class _S:
    def __init__(self, seg):
        self.narration = seg["narration"]
        self.visual = _V(seg["visual"])

    def model_dump(self):
        return {"narration": self.narration, "visual": self.visual.model_dump()}


class _Script:
    def __init__(self, d):
        self.segments = [_S(s) for s in d["segments"]]
        self._d = d

    def model_dump(self):
        return dict(self._d)


def _chart(headline: str, displays: list[str]) -> dict:
    return {
        "kind": "chart", "headline": headline, "stat": "", "note": "",
        "stat_source": "", "formula": "", "items": [], "rows": [], "headers": [],
        "bars": [{"label": f"{i}", "value": float(i + 1), "display": d}
                 for i, d in enumerate(displays)],
    }


#: **ナレーションは、下限（4分＝1440文字）を超えさせておくこと。**
#: 足りないと `generate()` が先に「加筆してください」の follow_up を1回入れ、
#: **そちらが返した台本で輪が回ってしまいます**（この file の 1./2. が
#: 2026-08-24 に、その順番のせいで一度は緑・一度は赤になりました）。
#: ここで見たいのは**書き直しの輪のほう**なので、加筆の側は起こさない。
_PAD = "この節では、前提を1つずつ画面に出しながら計算の過程を追っていきます。" * 45


def _script(charts: list[list[str]]) -> _Script:
    segs = [
        {
            "narration": "この計算の前提は、年収600万円・扶養なしです。" + _PAD,
            "visual": {
                "kind": "stat", "headline": "この計算の前提", "stat": "35万9318円",
                "note": "年収600万・扶養なし", "stat_source": "359,318円",
                "formula": "35万9318円 ＝ 600万円 × 5.99%",
                "items": [], "rows": [], "headers": [], "bars": [],
            },
        }
    ]
    for i, c in enumerate(charts):
        segs.append({
            "narration": f"{i + 1}枚目の図では、計算した結果を並べています。",
            "visual": _chart(f"計算結果 その{i + 1}", c),
        })
    return _Script({"title": "計算した結果を発表します",
                    "thumbnail_line1": "", "thumbnail_line2": "",
                    "segments": segs})


# --- 1. 輪が長尺にも掛かっていること（**本体**） -------------------------------

def test_輪の条件がショート限定に戻っていないこと():
    """**`generate()` が、長尺でも `long_script_problems` を見て書き直させること。**

    `ask` と `follow_up` を差し替えて、長尺の設定で1本走らせる。
    輪がショート限定に戻っていれば `follow_up` は1度も呼ばれず、
    ここが赤くなる。
    """
    ladder = ["120万円", "240万円", "360万円"]
    bad = _script([ladder, ladder, ladder])
    good = _script([["120万円", "130万800円", "140万1600円"],
                    ["8万2400円", "9万1230円", "10万44円"],
                    ["21万3000円", "23万4500円", "25万6100円"]])

    calls: list[str] = []

    def fake_ask(model_cls, prompt, *, model, **kw):
        calls.append("ask")
        return bad, "session-1"

    def fake_follow_up(model_cls, session, prompt, *, model, **kw):
        calls.append(prompt)
        return good, session

    def fake_problems(script, topic_id=""):
        # 実際の検査は下の 3./4. で当てる。ここは輪の配線だけを見る。
        return ["図の棒が `s-nisa-growth-only-1200（公開済み）` と 3本 共通"] \
            if script is bad else []

    orig = (script_writer.ask, script_writer.follow_up,
            script_writer.long_script_problems)
    script_writer.ask = fake_ask
    script_writer.follow_up = fake_follow_up
    script_writer.long_script_problems = fake_problems
    try:
        out = script_writer.generate(_channel(long=True), _topic())
    finally:
        (script_writer.ask, script_writer.follow_up,
         script_writer.long_script_problems) = orig

    # **「follow_up が呼ばれた」では足りません。** 文字数が足りない台本では
    # 加筆の follow_up が別に入るので、それだけで緑になってしまいます。
    # 見るのは**輪が出す本文かどうか**（先頭の1行で見分ける）。
    loop_prompts = [c for c in calls
                    if c != "ask" and "投稿前の検査に落ちます" in c]
    assert loop_prompts, (
        "長尺で、書き直しの輪の follow_up が1度も呼ばれていません —— "
        f"輪がショート限定（`max_minutes <= 1.5`）に戻っています: {calls}"
    )
    assert out is good, "書き直した台本が返っていません"


# --- 2. 長尺の本文が、ショートのものに戻っていないこと -------------------------

def test_長尺の直し方がショートの本文ではないこと():
    long_txt = script_writer.LONG_FIX_GUIDANCE
    assert long_txt != script_writer.SHORT_FIX_GUIDANCE
    # ショート専用の指示が混ざっていないこと（長尺で削ると4分を割って落ちる）。
    assert "140文字" not in long_txt
    assert "セグメントを2つに割る" not in long_txt
    # 長尺が実際に落ちていた理由に、直し方が書いてあること。
    assert "梯子" in long_txt, "落ちていた 3/3 の原因に触れていません"


def test_長尺の本文が実際に渡ること():
    """**定数を足しても、輪に配線されていなければ意味がありません。**"""
    bad = _script([["120万円", "240万円", "360万円"]])
    good = _script([["120万円", "130万800円", "140万1600円"]])
    seen: list[str] = []

    def fake_ask(model_cls, prompt, *, model, **kw):
        return bad, "session-1"

    def fake_follow_up(model_cls, session, prompt, *, model, **kw):
        seen.append(prompt)
        return good, session

    orig = (script_writer.ask, script_writer.follow_up,
            script_writer.long_script_problems)
    script_writer.ask = fake_ask
    script_writer.follow_up = fake_follow_up
    script_writer.long_script_problems = (
        lambda script, topic_id="": ["図の棒が … と 3本 共通"] if script is bad else [])
    try:
        script_writer.generate(_channel(long=True), _topic())
    finally:
        (script_writer.ask, script_writer.follow_up,
         script_writer.long_script_problems) = orig

    loop_prompts = [t for t in seen if "投稿前の検査に落ちます" in t]
    assert loop_prompts, f"書き直しの輪の follow_up が呼ばれていません: {seen}"
    assert "梯子" in loop_prompts[0], \
        f"長尺の本文（LONG_FIX_GUIDANCE）が渡っていません: {loop_prompts[0][:200]}"


# --- 3./4. 検査そのもの ---------------------------------------------------------

def test_過去と重なる棒を長尺でも捕まえる(tmp_path, monkeypatch):
    """`long_script_problems` が `_check_not_repeat` を通していること。"""
    from src import config

    monkeypatch.setattr(config, "BUILD_DIR", tmp_path)
    other = tmp_path / "s-nisa-growth-only-1200"
    other.mkdir()
    (other / "script.json").write_text(
        __import__("json").dumps(
            _script([["120万円", "240万円", "360万円", "480万円"]]).model_dump(),
            ensure_ascii=False),
        encoding="utf-8")

    ladder = ["120万円", "240万円", "360万円"]
    problems = script_writer.long_script_problems(
        _script([ladder, ladder, ladder]), "s-tokurou-kurisage-nashi")
    assert any("共通" in p for p in problems), problems


def test_重なっていない台本は通る(tmp_path, monkeypatch):
    """**偽陽性が怖い側。** 落とすと投稿が止まります。"""
    from src import config

    monkeypatch.setattr(config, "BUILD_DIR", tmp_path)
    problems = script_writer.long_script_problems(
        _script([["120万円", "130万800円", "140万1600円"],
                 ["8万2400円", "9万1230円", "10万44円"],
                 ["21万3000円", "23万4500円", "25万6100円"]]),
        "")
    assert not any("共通" in p for p in problems), problems


def test_chartが足りなければ言う(tmp_path, monkeypatch):
    """長尺は chart 3枚が下限（`verify.MIN_CHARTS`）。輪の中で足させる。"""
    from src import config

    monkeypatch.setattr(config, "BUILD_DIR", tmp_path)
    problems = script_writer.long_script_problems(
        _script([["120万円", "130万800円"]]), "")
    assert any("chart" in p for p in problems), problems


def test_引けないテーマでも例外にしない():
    """**生成中に呼ばれるので、落ちると台本作りごと止まります。**"""
    assert script_writer.long_script_problems(
        _script([["1円", "2円", "3円"]]), "no-such-topic-id") is not None


# --- 足場 ----------------------------------------------------------------------

def _channel(long: bool) -> dict:
    return {
        "channel": {"name": "お金と仕事の教科書", "niche": "税と社会保険の計算",
                    "audience": "会社員", "persona": "計算した結果を発表する",
                    "avoid": ["断定的な助言"]},
        "video": {"target_minutes": 5.0 if long else 0.8,
                  "min_minutes": 4.0 if long else 0.3,
                  "max_minutes": 7.0 if long else 1.0},
        "generation": {"model": "test-model"},
    }


def _topic() -> dict:
    return {"id": "s-tokurou-kurisage-nashi", "title_seed": "題",
            "angle": "切り口"}
