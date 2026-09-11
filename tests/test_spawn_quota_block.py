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
import sys
from datetime import timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quota as _quota  # noqa: E402  （門も判定も、この 1か所 から引く）


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
        # **前の行を見ないこと**（この検査を書いた回に踏んだ）—— 直前の行が別の用で
        # 「METHOD §5 の表のとおり」と言っており、**古い字のままでも緑になりました**。
        # **2026-09-11 17:0x に「後ろ 300字」から「同じ行」へ当て直しました**（optimizer・Opus）:
        # 【枠】の段が運ぶ `quota.short_words()` の行は **§5 を文の頭に置く**ので、
        # 後ろだけを見る形では**指し先が在るのに落ちます**（実測・この回）。
        # 行は文より狭い単位なので、上の「別の行が指していた」型は**入りません**。
        beg = text.rfind("\n", 0, i) + 1
        end = text.find("\n", i)
        seg = text[beg:] if end < 0 else text[beg:end]
        assert "§5" in seg, f"「短く終わる」が §5 の決めを指していません: {seg[:160]}"
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
    # **判定の行は差し替えない**（2026-09-11 17:0x）—— 門と側と `blind` は
    # `quota.short_words` の 1か所 に在り、この段はそれを運ぶだけ。
    # ここで偽の判定を返すと、**検査だけが通る門**を作ることになります。
    mod.short_words = _quota.short_words
    mod.SHORT_LANDING_GATE = _quota.SHORT_LANDING_GATE
    for name in ("scripts.quota", "quota"):
        monkeypatch.setitem(sys.modules, name, mod)


def test_門ちょうどの字を出さない(monkeypatch):
    """97.5% は「98%」ではなく **97.5%** と出ること（門 98% と見分けが付く）。"""
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    got = sp._quota_block()
    assert "いまの間隔のまま **97.5%**" in got, got
    assert "いまの間隔のまま **98%**" not in got


def test_門の数を段の中で名指しすること(monkeypatch):
    """読む側が METHOD を開かずに比べられるよう、門を同じ段に置くこと。

    **2026-09-11 17:0x に当て直しました**（optimizer・Opus）—— 前は
    `"門は **98%**" in ...` と**門の数そのもの**を当てており、段の側も literal で
    98 を持っていました（`SHORT_LANDING_GATE` と 2か所 ＝ `short_verdict` の覆る条件 (3)）。
    いま段が運ぶのは `quota.short_words()` の1行なので、当てるのは
    **定数から作った字が在るか**だけです。
    """
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    assert f"（門 {_quota.SHORT_LANDING_GATE:.0f}%）" in sp._quota_block()


def test_判定そのものを印字すること(monkeypatch):
    """**手で引き比べさせないこと**（13:1x の決め・§5 教訓の形 7つ目）。

    段は 2つ の数と門を並べるだけでなく、**引かれたか**を言うこと。
    ここは門を跨ぐ 2通りを撃って、**向きが両方 出る**ことまで見ます
    （**きょうの状態を不変条件にしない**・§5 教訓の形 6つ目）。
    """
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    assert "**引かれました ＝ 持ち場に何も無ければ短く終わってよい**" in sp._quota_block()
    _stub_landing(monkeypatch, reach_carry=90.0, land_all=90.0)
    assert "**引かれません ＝ 余る側 ＝ 短く終わらないこと**" in sp._quota_block()


def test_2つの側が答えを違える回は段がそう言うこと(monkeypatch):
    """§5 13:1x の覆る条件 (2')（`agree` False）は、**段の側でも見えること**。"""
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    assert "**もう一方の側は逆の答え**" in sp._quota_block()


def test_positive_control_口が無い回は空欄にしない(monkeypatch):
    """**陽性対照**: `short_words` を外すと、段は黙らず「読めません」と言うこと。

    （`from` で縛っていた頃は、この差し替えで**段が丸ごと空**になりました ＝
    空欄が「余裕がある」に読まれる形・`_short_lines` の註）
    """
    import sys
    _stub_landing(monkeypatch, reach_carry=97.5, land_all=99.7)
    for name in ("scripts.quota", "quota"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "short_words"):
            monkeypatch.delattr(mod, "short_words", raising=False)
    got = sp._quota_block()
    assert "**短く終わってよいかが読めません**" in got, got
    assert "床に従えば **すべて 99.7%**" in got, got


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


# ---- 尽きた枠に、これから尽きる話を渡さないこと（2026-09-11 16:3x・optimizer・Opus）
# **踏んだ形**: 目盛りは 09/11 12:38 JST で「Fable のみ」100%・`sub_model` は 2役 とも opus を
# 返しているのに、この段は「床に従うと **リセットの 14時間 前に 100%** → そこから `hourly` も opus」と
# **未来形**で渡していた（しかも見込みは実際の到達より 4時間 遅い）。METHOD §5 は 10:3x に
# 「短く終わるか」を**その周に実際に立った模型**で読めと決めており、**その模型がこの段に無い**。
# derivation と覆る条件は `spawn_prompt._quota_block` の註（16:3x）。

def _stub_fable(monkeypatch, est: float, spent: float | None,
                models: dict | None = None, cap: float = 100.0,
                rolled: bool = False, ration_est: float = 0.0):
    """**`rolled` は「枠が戻った回」**（2026-09-11 20:5x・optimizer・Opus が足した）。

    戻った枠では `fable_estimate()["est"]` は**前の枠の目盛りのまま**（100%）で、
    いまの枠の使用量は `fable_ration()["est"]`（0% から数え直し）です
    —— `quota.fable_rolled` / `quota.fable_estimate` の註。
    `rolled=False` の呼びは前と同じ物を返します（**古い検査を動かさない**）。
    """
    import datetime as _dt
    import sys
    import types
    mod = types.ModuleType("quota_stub")
    jst = timezone(timedelta(hours=9))
    reset = _dt.datetime(2026, 9, 12, 7, 0, tzinfo=jst)
    mod.pace = lambda *a, **k: {"per_lap": 0.567, "floor_min": 37.0, "used_now": 86.0,
                                "left_hours": 15.0, "window_reset": reset,
                                "carry_rate": 0.88, "reach_carry": 99.4,
                                "reach_lag_min": 1.7}
    mod.fable_estimate = lambda *a, **k: {
        "est": est, "gauge": {"at": _dt.datetime(2026, 9, 11, 12, 38, tzinfo=jst)}}
    mod.fable_rate = lambda *a, **k: {"rate": 1.0}
    mod.landing = lambda *a, **k: {"all": 99.4, "fable": est,
                                   "fable_spent_h_before_reset": spent, "laps": 23}
    mod.JST = jst
    mod.FABLE_CAP_PCT = cap
    mod.fable_rolled = lambda fe: rolled
    mod.fable_ration = lambda *a, **k: {
        "line": 0.1, "est": ration_est, "over": ration_est > 0.1, "rolled": rolled,
        "start": reset, "resets": reset + timedelta(hours=168),
        "elapsed_h": 1.0, "left_h": 167.0, "per_sub": 0.93, "subs_since": 0,
        "gauge": {"pct": 100.0}}
    mod.fable_ration_words = lambda r: "配りの線 0.1% 対 いま推定 0.0% ＝ 線の下 → Fable" if r else ""
    if models is not None:
        mod.sub_roles = lambda: tuple(models)
        mod.sub_model = lambda now=None, role=None: (models[role], "理由")
    for name in ("scripts.quota", "quota"):
        monkeypatch.setitem(sys.modules, name, mod)
    return mod


def test_尽きた枠では未来形で言わないこと(monkeypatch):
    _stub_fable(monkeypatch, est=100.0, spent=14.0,
                models={"hourly": "opus", "optimizer": "opus"})
    got = sp._quota_block()
    assert "前に 100%" not in got, got
    assert "もう 100%" in got and "目盛り 09/11 12:38 JST" in got, got


def test_立った模型を役ごとに名前で出すこと(monkeypatch):
    """§5 10:3x —— 読む側は「役」ではなく**その周に実際に立った模型**で決める。"""
    _stub_fable(monkeypatch, est=100.0, spent=14.0,
                models={"hourly": "opus", "optimizer": "opus"})
    got = sp._quota_block()
    assert "この周は hourly opus・optimizer opus" in got, got
    assert "§5 10:3x" in got, got


def test_並びが割れた回は役ごとの形がそのまま出ること(monkeypatch):
    """**覆る条件 (2)**: 並びが割れたら、§5 15:1x の役ごとの形がそのまま効く。

    **この検査は「枠が戻った回」ではありません**（2026-09-11 20:5x に名を直した）——
    目盛りは 100% のまま ＝ **尽きた枠**で並びだけが割れた形です。
    前の名（`test_Fableが戻った枠では…`）は**戻った枠を見ていると読めて**、
    そのせいで「**もう 100%**」と「この周は hourly **fable**」を同じ段が並べる形が
    **緑のまま 1周 通りました**（§5 教訓の形 4つ目 ——「検査は緑で、実物の形だけが抜けていた」）。
    戻った枠は下の `test_戻った枠では前の枠の目盛りを運ばないこと` が見ます。
    """
    _stub_fable(monkeypatch, est=100.0, spent=14.0,
                models={"hourly": "fable", "optimizer": "opus"})
    assert "この周は hourly fable・optimizer opus" in sp._quota_block()


# ---- 戻った枠に、尽きた枠の話を渡さないこと（2026-09-11 20:5x・optimizer・Opus）
# **踏んだ形**: リセット（09/12 07:00 JST）の後、`fable_estimate()` は
# `est = 前の枠の目盛り`（= 100%）を返し続けます（`rate_source: "reset"`・関数の註）。
# `sub_model` はその枝で **0%** を渡し直すので模型は正しく `fable` に戻るのに、
# この段は `fe["est"]` を素で運んでいたため
# 「Fable のみ **もう 100%** … ＝ **この周は hourly fable**」を**同じ行に並べて**渡していました。
# 16:3x（尽きた枠に未来形）の**鏡**で、しかも §5 の模型の段の**覆る条件 (4)**
# （リセットで Fable が戻ったら役ごとの形がそのまま効く）を読む印字が **1つも無かった**側です。
# 門は `quota.fable_rolled`（1か所）。derivation は JOURNAL 2026-09-11 20:5x。

def test_戻った枠では前の枠の目盛りを運ばないこと(monkeypatch):
    _stub_fable(monkeypatch, est=100.0, spent=14.0,
                models={"hourly": "fable", "optimizer": "opus"},
                rolled=True, ration_est=0.0)
    got = sp._quota_block()
    assert "もう 100%" not in got, got
    assert "枠は戻りました" in got, got
    assert "Fable のみ **0%**" in got, got
    assert "この周は hourly fable・optimizer opus" in got, got
    assert "覆る条件 (4)" in got, got
    assert "前に 100%" not in got, got


def test_positive_control_戻っていない枠では前の字がそのまま出ること(monkeypatch):
    """**陽性対照**: 上の門は、戻っていない回の字まで消してはいけない。"""
    _stub_fable(monkeypatch, est=100.0, spent=14.0,
                models={"hourly": "opus", "optimizer": "opus"}, rolled=False)
    got = sp._quota_block()
    assert "もう 100%" in got, got
    assert "枠は戻りました" not in got, got


def test_positive_control_古い_quota_には_戻りの門が無くても落ちないこと(monkeypatch):
    """`fable_rolled` を持たない `quota` でも、段は前と同じ字で出ること。"""
    mod = _stub_fable(monkeypatch, est=100.0, spent=14.0,
                      models={"hourly": "opus", "optimizer": "opus"})
    del mod.fable_rolled
    del mod.fable_ration
    got = sp._quota_block()
    assert "もう 100%" in got and "枠は戻りました" not in got, got


def test_positive_control_尽きていない回は未来形が出ること(monkeypatch):
    """**陽性対照**: 上の門は、尽きていない回まで消してはいけない。"""
    _stub_fable(monkeypatch, est=80.0, spent=14.0,
                models={"hourly": "fable", "optimizer": "opus"})
    got = sp._quota_block()
    assert "床に従うと **リセットの 14時間 前に 100%**" in got, got
    assert "もう 100%" not in got and "この周は hourly" not in got, got


def test_模型が読めない回でも段を落とさないこと(monkeypatch):
    """`sub_model` が引けない回は、**言えないことを言わない**（段は残す）。"""
    _stub_fable(monkeypatch, est=100.0, spent=14.0, models=None)
    got = sp._quota_block()
    assert "もう 100%" in got and "`quota.sub_model` が決めます" in got, got
    assert "この周は hourly" not in got
