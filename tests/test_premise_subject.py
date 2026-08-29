"""`scripts/premise_subject.py` —— 主語と、反証条件が数えている値を並べる道具。

**故障注入を両向きに掛けます。** 当たりを見つけることと、
**当たっていないものを鳴らさないこと**は別の性質で、片方だけでは
「全部鳴らす検査」と区別がつきません（`docs/JOURNAL.md` 2026-08-16）。

**実物の台帳を「いま何件 食い違っているか」で固定しないこと。**
台帳は毎周 増えるので、数を書いた瞬間に赤くなります（`tests/test_doc_numbers.py`
が同じ壊れ方を何度も拾っています）。ここで固定するのは**道具の振る舞い**だけ。
"""
from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "premise_subject", ROOT / "scripts" / "premise_subject.py")
assert _spec and _spec.loader
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)


def _yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "hypotheses.yaml"
    p.write_text("hypotheses:\n" + textwrap.dedent(body), encoding="utf-8")
    return p


# ---- 語彙が量を拾えるか --------------------------------------------------

def test_量の語を拾う():
    assert ps.measures("1本あたり再生が上がる") == {"per_video"}
    assert ps.measures("登録率が上がる") == {"sub_rate"}
    assert ps.measures("1日の公開本数を増やす") == {"density"}
    assert ps.measures("実効RPM が上がる") == {"rpm"}


def test_量の語がなければ空集合():
    # **「拾えなかった」と「食い違っている」は別物**です。
    assert ps.measures("これは前提です") == set()
    assert ps.measures("") == set()


# ---- 故障注入（当たる側）------------------------------------------------

def test_主語と数えている値が交わらなければ鳴る(tmp_path):
    p = _yaml(tmp_path, """\
        - claim: "族を増やすと1本あたり再生が上がる"
          deadline: "2026-09-30"
          lever: per_video
          side: dist
          falsified_if: "登録が 2人 に届かないなら外れ"
    """)
    # 主語は per_video（「1本あたり再生」）と density（「族」）、
    # 数えているのは sub_rate（「登録」）—— 交わりません。
    rows = ps.audit(p)
    assert len(rows) == 1
    assert rows[0]["mismatch"] is True


def test_leverが数えている値と合っていなければ別の札で鳴る(tmp_path):
    p = _yaml(tmp_path, """\
        - claim: "1本あたり再生が上がる"
          deadline: "2026-09-30"
          lever: rpm
          side: dist
          falsified_if: "1本あたり再生が 100回 に届かないなら外れ"
    """)
    rows = ps.audit(p)
    assert rows[0]["mismatch"] is False      # 主語と値は交わっている
    assert rows[0]["lever_off"] is True      # ただし lever は数えていない量


# ---- 故障注入（当たらない側。**ここが無いと「全部鳴らす検査」と同じ**）----

def test_合っている前提は鳴らさない(tmp_path):
    p = _yaml(tmp_path, """\
        - claim: "題を問いの形にすると engaged が上がる"
          deadline: "2026-09-30"
          lever: per_video
          side: content
          falsified_if: "engaged 比率の差が 2ポイント 未満なら外れ"
    """)
    rows = ps.audit(p)
    assert rows[0]["mismatch"] is False
    assert rows[0]["lever_off"] is False


def test_片方が拾えないだけでは鳴らさない(tmp_path):
    # **主語が拾えない前提は 2026-08-30 の実物に 2件 あります**
    # （「長尺は1日4本 作れる」など）。ここで鳴らすと、その2件が
    # 毎周 `[!]` に居座り、本当の食い違いが埋まります。
    p = _yaml(tmp_path, """\
        - claim: "この輪は続けられる"
          deadline: "2026-09-30"
          lever: density
          side: dist
          falsified_if: "1日の公開本数が 10本 を割ったら外れ"
    """)
    assert ps.audit(p)[0]["mismatch"] is False


def test_leverがnoneなら札を付けない(tmp_path):
    # `none` は**正しい札**です（`config/hypotheses.yaml` 冒頭）。
    p = _yaml(tmp_path, """\
        - claim: "計算で独自性を出す構成なら、量産テンプレート判定を避けられる"
          deadline: "2027-12-18"
          lever: none
          side: infra
          falsified_if: "収益化が却下されたら外れ"
    """)
    assert ps.audit(p)[0]["lever_off"] is False


# ---- 閉じた前提は並べない ------------------------------------------------

def test_閉じた前提は出さない(tmp_path):
    p = _yaml(tmp_path, """\
        - claim: "族を増やすと登録が増える"
          deadline: "2026-09-30"
          lever: per_video
          side: dist
          effect: 1.0
          falsified_if: "登録が 2人 に届かないなら外れ"
    """)
    assert ps.audit(p) == []


# ---- 実物で走る（数は固定しない）----------------------------------------

def test_実物の台帳で走る():
    rows = ps.audit()
    assert rows, "開いている前提が1件も読めていません"
    assert all({"claim", "lever", "mismatch"} <= set(r) for r in rows)
