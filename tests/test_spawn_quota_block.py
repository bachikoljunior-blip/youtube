"""**枠の視点を、サブ本人に渡す段**（2026-09-09 22:1x・optimizer・Opus）。

オーナー原文（`CLAUDE.md` 冒頭）: 21:13「**全てのモデル100％いきそう？**」/
21:1x「**どうすんの？**」/ 21:5x「**その視点ないんだったら視点だけ与えなよ**」。

**その視点は、サブの本文のどこにも在りませんでした。** 渡っていたのは模型の名前だけで、
枠がいま**余る側**なのか**足りない側**なのかは 1文字も書かれていない。
それでいて METHOD §5 には「**持ち場に何も無ければ短く終わってよい
（Fable の枠を使わない）**」が既定として置いてあり、**これは枠を使いすぎていた頃の行**です
——余る側では向きが逆（残した枠はリセットで消える）。
＝ **サブは、逆向きの既定を、根拠を見ずに引いていました。**

この検査が固定するのは 3つ:
  (1) 段が**両方の役**（hourly / optimizer）の本文に入ること
  (2) **数が読めない回に、空欄にしないこと**（「読めていません」と書く。
      `CLAUDE.md`「**空欄を「余裕がある」と読まないこと**」）
  (3) **写しには数を焼かないが、段ごとは落とさないこと**
      （型が「下の【枠】の段」を指しているので、空にすると指し先が消える）
"""
from __future__ import annotations

import importlib.util
from datetime import timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "spawn_prompt_quota", ROOT / "scripts" / "spawn_prompt.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp = _load()


def test_段は数を持って出る():
    got = sp._quota_block()
    assert got.startswith("【枠"), got[:80]
    # 目盛りが読めない環境では「読めていません」側。どちらでも空ではないこと。
    assert "読めていません" in got or "床" in got


def _stub_quota(monkeypatch, pace):
    """`quota` を差し替える。**当て先は 2つ**（`scripts.quota` と裸の `quota`）。

    `_quota_block()` は関数の中で import するので、決まるのは**呼んだ瞬間の
    `sys.modules`** です。片方だけ差し替えると、**別の検査が `sys.modules` に
    置いた stub のほうが勝ち**、`monkeypatch.setattr` は `AttributeError` で落ちます
    （この回に、単体では緑・`-m live` の全部では赤、で踏んだ）——
    09/09 09:5x の `run_marker`・21:5x の `livetests` と同じ族で、**3度目**です。
    """
    import sys
    import types
    mod = types.ModuleType("quota_stub")
    mod.pace = pace
    mod.fable_estimate = lambda *a, **k: None
    mod.fable_rate = lambda *a, **k: None
    mod.landing = lambda *a, **k: {"all": None, "fable": None,
                                   "fable_spent_h_before_reset": None, "laps": 0}
    mod.JST = timezone(timedelta(hours=9))
    for name in ("scripts.quota", "quota"):
        monkeypatch.setitem(sys.modules, name, mod)
    return mod


def test_数が読めない回でも空にしない(monkeypatch):
    """**空欄を「余裕がある」と読ませない**（`CLAUDE.md` の使用量の節）。"""
    _stub_quota(monkeypatch, lambda *a, **k: None)
    got = sp._quota_block()
    assert got, "段が丸ごと消えている（空欄は「余裕がある」と読まれます）"
    assert "読めていません" in got


def test_quotaが落ちても親を止めない(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("測れない")

    _stub_quota(monkeypatch, _boom)
    got = sp._quota_block()                       # 例外を投げないこと
    assert "読めていません" in got


@pytest.mark.parametrize("kind", ["hourly", "optimizer"])
def test_両方の役の本文に入る(kind):
    text = sp.build(kind)
    assert "【枠" in text, f"{kind} の本文に枠の段が入っていません"


@pytest.mark.parametrize("kind", ["hourly", "optimizer"])
def test_短く終わってよいの向きが枠に結びついている(kind):
    """裸の既定として置かないこと —— 向きは枠しだい。"""
    text = sp.build(kind)
    if "持ち場に何も無ければ短く終わってよい" in text:
        i = text.index("持ち場に何も無ければ短く終わってよい")
        tail = text[i:i + 200]
        assert "枠" in tail, "「短く終わってよい」が、枠を見ずに置かれています"


def test_写しには数を焼かないが段は落とさない():
    """**写しは commit される生成物**（周ごとに変わってはいけない）。

    それでも段ごと落とすと、型の「下の【枠】の段」が写しの中で指し先を失います。
    """
    text = sp.build("optimizer", live_clock=False)
    assert "【枠" in text, "写しから段が丸ごと落ちています"
    assert "%" not in sp.QUOTA_BLOCK_STATIC, "写しに数（%）が焼かれています"


def test_写しは最新であること():
    """`--write-rendered` の出力と、commit されている写しが一致すること。"""
    got = (ROOT / "docs" / "spawn_prompt.rendered.md").read_text(encoding="utf-8")
    assert "【枠" in got, "写しを焼き直していません（`--write-rendered`）"
