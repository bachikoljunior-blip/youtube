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
def test_短く終わるかは_METHOD_5_の決めを指すこと(kind):
    """**2026-09-10 20:4x に書き直した**（optimizer・Opus）。

    前の形は `if "持ち場に何も無ければ短く終わってよい" in text:` の**条件つき**で、
    その字を本文から外した回に**空振りの緑**になります（§6 の strict xfail と同じ族 ——
    「通った」しか見ないので「直った」と「見る物が消えた」を分けられない）。

    そして中身も古くなっていました: この段が書かれた 09/09 22:1x の時点では
    §5 の「持ち場に何も無ければ短く終わってよい」は**まだ決まっていません**でしたが、
    **2026-09-10 15:1x に `hourly` が役ごとの着地で決めました**（覆る条件 3つ つき）。
    それ以降もこの段は「**どちらかはあなたが決めること**」と毎周 言い続けており、
    **サブは毎回 決着ずみの問いを開け直すことになります**。
    ＝ 親の本文が、METHOD の決めと食い違っている側（**言っている所と、している所が別**）。

    **いま固定するのは 2つ**: 「短く終わる」に触れている所は**どれも §5 を指すこと**・
    **開いた問いとして置き直さないこと**。
    """
    text = sp.build(kind)
    hits = [i for i in range(len(text)) if text.startswith("短く終わ", i)]
    assert hits, "「短く終わる」の行が本文から消えました —— 決めの指し先ごと見直すこと"
    for i in hits:
        # **前を見ないこと**（この検査を書いた回に踏んだ）—— 直前の行が別の用で
        # 「METHOD §5 の表のとおり」と言っており、**古い字のままでも緑になりました**。
        # 指し先は**同じ文の中**に在ること ＝ 後ろだけを見る。
        seg = text[i:i + 300]
        assert "§5" in seg, f"「短く終わる」が §5 の決めを指していません: {seg[:120]}"
    assert "どちらかはあなたが決めること" not in text, (
        "09/09 22:1x の字が残っています —— §5 は 09/10 15:1x に役ごとの着地で決めました")


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


# ---- 着地の数を、門と同じ桁で丸めないこと（2026-09-11 11:4x・optimizer・Opus）
# **踏んだ形**: 「いまの間隔のまま」は METHOD 5 の 15:1x の覆る条件 (1)（門 **98%**）が読む数で、
# `:.0f` は **97.5 を「98%」**と印字していた ＝ 受け取った側は門ちょうどの字を見て
# 「越えた／越えていない」を判定することになる。`quota.py --pace` は同じ数を 1桁 で出すので、
# **2つの口が違うことを言う**形でもあった（`trend.channel_line_short` の覆る条件 (2) と同じ族）。

def _stub_landing(monkeypatch, reach_carry: float, land_all: float):
    import datetime as _dt
    import sys
    import types
    mod = types.ModuleType("quota_stub")
    reset = _dt.datetime(2026, 9, 12, 7, 0, tzinfo=timezone(timedelta(hours=9)))
    mod.pace = lambda *a, **k: {"per_lap": 0.552, "floor_min": 36.0, "used_now": 82.0,
                                "left_hours": 19.0, "window_reset": reset,
                                "carry_rate": 0.79, "reach_carry": reach_carry,
                                "reach_lag_min": 1.7}
    mod.fable_estimate = lambda *a, **k: {"est": 100.0}
    mod.fable_rate = lambda *a, **k: {"rate": 1.0}
    mod.landing = lambda *a, **k: {"all": land_all, "fable": None,
                                   "fable_spent_h_before_reset": None, "laps": 0}
    mod.JST = timezone(timedelta(hours=9))
    for name in ("scripts.quota", "quota"):
        monkeypatch.setitem(sys.modules, name, mod)


def test_門ちょうどの字を出さない(monkeypatch):
    """97.5% は「98%」ではなく **97.5%** と出ること（門 98% と見分けが付く）。"""
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    got = sp._quota_block()
    assert "いまの間隔のまま **97.5%**" in got, got
    assert "いまの間隔のまま **98%**" not in got


def test_門の数を段の中で名指しすること(monkeypatch):
    """読む側が METHOD を開かずに比べられるよう、門 **98%** を同じ行に置くこと。"""
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    assert "門は **98%**" in sp._quota_block()


def test_positive_control_丸めの差は実在する(monkeypatch):
    """**陽性対照**: 0桁 に戻すと門と同じ字になる並びで試していること。"""
    assert f"{97.5:.0f}" == "98" and f"{97.5:.1f}" == "97.5"
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    got = sp._quota_block()
    assert "97.5%" in got and "床に従えば **すべて 99.7%**" in got


def test_頭の行は模型の枠だと名乗ること(monkeypatch):
    """**「この回に使ってよい速さ」の隣に「API 0単位」を置かないこと**
    （2026-09-11 15:4x・optimizer・Opus。`_quota_block` の註）。

    あの字は**この段を作る値段**で、**この回に使ってよい API の量ではありません。**
    並べて置くと読み方は 1つ になり（「この回は API を 0単位 しか使えない」）、
    同じ本文の (a)（`measure`・`status`）と METHOD §7 (o-4)（`cli reporting`）と食い違います。
    """
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    head = sp._quota_block().splitlines()[0]
    assert "この回に使ってよい速さ" in head, head
    assert "API 0単位" not in head, head
    assert "模型の枠" in head, head
    # **Data API は別の枠**だと、同じ行で言うこと（読む側が枠を取り違えない）。
    assert "Data API" in head and "10,000単位/日" in head, head


def test_positive_control_頭の行の門は実在する(monkeypatch):
    """**陽性対照**: 古い字（`**API 0単位**` を頭に置く形）なら、上の検査は落ちること。"""
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    old_head = "【枠 —— この回に使ってよい速さ】**API 0単位**。オーナー 21:13"
    assert "API 0単位" in old_head and "模型の枠" not in old_head
