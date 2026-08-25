"""節ごとの実測（`status.py` の時間の内訳）。

**なぜこれを測るのか。** §6 (a2) の問い1「この回でいちばん時間を食ったのはどこか」
は、直近8回のうち4回で `status.py` を名指ししていました。**それでも直っていません** ——
どの答えも「`status.py` が」で止まっていて、**その中のどこか**を言っていないからです。
手で測るには1回まるごと（実測13分）走らせ直すことになるので、
**測るより推測するほうが安い**という形になっていました。

ここが守るのは3つです。**どれも黙って壊れる向き**なので、検査で留めます。

  1. **入れ子を引く**（容れ物と中身を足すと二重になる）
  2. **まだ終わっていない節を落とさない** —— 表を出すのは `_channel_main` の
     **中**なので、積んだぶんだけ出すと**いちばん大きい行が丸ごと消えます**
  3. **`_print_analytics_recap` より前に出す** —— あの節は「`tail` で拾っても
     落ちない」ことが存在理由なので、後ろには何も足せません
"""
import importlib.util
import inspect
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("status_mod", ROOT / "scripts" / "status.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_入れ子は引く():
    m = _load()
    m._TIMINGS.clear()
    m._TIME_STACK.clear()

    @m._clock("子")
    def child():
        time.sleep(0.05)

    @m._clock("親")
    def parent():
        time.sleep(0.05)
        child()

    parent()
    by = {r["label"]: r for r in m._TIMINGS}
    assert by["子"]["self"] >= 0.04
    # 親の「自分ぶん」から子が引かれている（引かなければ 0.1秒 近くになる）
    assert by["親"]["total"] >= 0.09
    assert by["親"]["self"] < by["親"]["total"] - 0.03


def test_落ちた節も積む():
    """外の口の待ちや再試行のあとで落ちる節こそ、時間を食っています。"""
    m = _load()
    m._TIMINGS.clear()
    m._TIME_STACK.clear()

    @m._clock("落ちる節")
    def boom():
        raise RuntimeError("落ちた")

    try:
        boom()
    except RuntimeError:
        pass
    assert [r["label"] for r in m._TIMINGS] == ["落ちる節"]
    assert not m._TIME_STACK          # 積みっぱなしにしない


def test_まだ途中の節も表に出る(capsys):
    """表を出すのは `_channel_main` の**中**。積んだぶんだけでは足りない。"""
    m = _load()
    m._TIMINGS.clear()
    m._TIME_STACK.clear()

    @m._clock("外の口（Data API）")
    def outer():
        time.sleep(0.05)
        m.print_timings()

    outer()
    out = capsys.readouterr().out
    assert "外の口（Data API）" in out
    assert "まだ途中" in out


def test_何も積んでいなければ何も出さない(capsys):
    m = _load()
    m._TIMINGS.clear()
    m._TIME_STACK.clear()
    m.print_timings()
    assert capsys.readouterr().out == ""


def test_要点の節より前に出す():
    """**後ろに足すと `tail` で拾えなくなります**（`_print_analytics_recap` の註）。"""
    m = _load()
    src = inspect.getsource(m._print_analytics_recap)
    assert "print_timings()" in src
    body = src.split('"""')[2]                 # docstring のあと
    first = [ln.strip() for ln in body.splitlines() if ln.strip()][0]
    assert first.startswith("print_timings()"), first


def test_節に時計が掛かっている():
    """包み忘れると、その節だけ表から消えます（**黙って**）。"""
    m = _load()
    for name in ("_channel_main", "print_topic_stock", "print_means",
                 "print_hypotheses", "print_budget"):
        fn = getattr(m, name)
        assert getattr(fn, "__wrapped__", None) is not None, f"{name} に時計が掛かっていません"
