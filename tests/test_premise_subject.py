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


def test_leverがnoneなら主語の食い違いでも鳴らない(tmp_path):
    """**2026-09-01 に足した。配線した回の最初の `[!]` が、これで空振りだった。**

    実物は `config/hypotheses.yaml` の 2026-09-30
    「収益化の審査は、門1・門2a の数字が揃えば通る」——
    `claim` の「**収益**化」で主語が `rpm`、`needs` の「**登録者**1,000人」で
    数えているのが `sub_rate` になり、交わらないので `[!]` が付いていました。

    **あの行は量を主張していません**（`lever: none` ／ `side: infra` ＝
    腕を全部 掛ける側の係数）。**直しようのない `[!]` は、計器を読まれなくします。**
    """
    p = _yaml(tmp_path, """\
        - claim: "収益化の審査は、門1・門2a の数字が揃えば通る"
          deadline: "2026-09-30"
          lever: none
          side: infra
          falsified_if: "門1（登録者1,000人）が通っていないので、その日はまだ申請できません"
    """)
    row = ps.audit(p)[0]
    assert row["subject"] == {"rpm"}          # 語彙は拾えている（拾えないのとは別）
    assert row["measured"] == {"sub_rate"}    # 交わってもいない
    assert row["mismatch"] is False           # **それでも鳴らさない**
    assert row["lever_off"] is False


def test_leverがあれば主語の食い違いは今までどおり鳴る(tmp_path):
    """上の除外が、**腕のある行まで黙らせていないこと**（故障注入の逆向き）。"""
    p = _yaml(tmp_path, """\
        - claim: "収益化の審査は、門1・門2a の数字が揃えば通る"
          deadline: "2026-09-30"
          lever: rpm
          side: infra
          falsified_if: "門1（登録者1,000人）が通っていないので、その日はまだ申請できません"
    """)
    assert ps.audit(p)[0]["mismatch"] is True


# ---- `note:` の鎖（2026-09-01。**4周 持ち越された `[?]` は、これで消えます**）----

def test_noteに腕への鎖があれば札は鳴らない(tmp_path):
    """**当たっていたのは道具のほうでした。**

    実物2件（`config/hypotheses.yaml` の 09-11 と 09-19）は、どちらも
    `lever: rpm` への鎖を `note:` に書いてあります —— **2026-08-27〜08-29 に
    YAML のインラインの註から本文へ写されたもの**で
    （`tests/test_eta_headline_alloc_hand.py` が「註は `yaml.safe_load` に
    読まれない」で赤くなったため）、**この道具だけが写し先を読んでいませんでした。**
    """
    p = _yaml(tmp_path, """\
        - claim: "長尺の再生シェアは、長尺の公開本数を増やせば上がる"
          deadline: "2026-09-30"
          lever: rpm
          side: dist
          note: "実効RPM ＝ Σ_形（再生の割合 × その形の帯）。動かすのはシェア"
          falsified_if: "公開本数が 14本 に届かなければ判定しない"
    """)
    row = ps.audit(p)[0]
    assert row["measured"] == {"density"}    # 数えているのは今までどおり density
    assert row["lever_off"] is False         # **鎖が本文にあるので鳴らさない**
    assert row["note_backed"] is True        # **黙って消さない。`[n]` で出す**
    assert "実効RPM" in row["note_line"]


def test_noteに鎖がなければ今までどおり鳴る(tmp_path):
    """**故障注入の逆向き。** `note:` が在るだけでは外しません。"""
    p = _yaml(tmp_path, """\
        - claim: "長尺の再生シェアは、長尺の公開本数を増やせば上がる"
          deadline: "2026-09-30"
          lever: rpm
          side: dist
          note: "2026-08-27 に期限を 09-10 から 09-11 へ延ばした。条件は触っていない"
          falsified_if: "公開本数が 14本 に届かなければ判定しない"
    """)
    row = ps.audit(p)[0]
    assert row["lever_off"] is True
    assert row["note_backed"] is False
    assert row["note_line"] == ""


def test_noteはmismatchには足さない(tmp_path):
    """**`note:` は「なぜこの腕か」で、数えている値ではありません。**

    足すと印字の「数えている＝」の欄が実物と食い違います。
    """
    p = _yaml(tmp_path, """\
        - claim: "族を増やすと1本あたり再生が上がる"
          deadline: "2026-09-30"
          lever: per_video
          side: dist
          note: "1本あたり再生の話です（この語が mismatch を消してはいけない）"
          falsified_if: "登録が 2人 に届かないなら外れ"
    """)
    row = ps.audit(p)[0]
    assert row["mismatch"] is True           # **`note:` では救われない**
    assert row["measured"] == {"sub_rate"}   # 欄も動かない


def test_leverがnoneならnoteも読まない(tmp_path):
    p = _yaml(tmp_path, """\
        - claim: "収益化の審査は、門1・門2a の数字が揃えば通る"
          deadline: "2026-09-30"
          lever: none
          side: infra
          note: "収益の話です"
          falsified_if: "門1（登録者1,000人）が通っていないので、その日はまだ申請できません"
    """)
    row = ps.audit(p)[0]
    assert row["lever_off"] is False
    assert row["note_backed"] is False


def test_lever_chainは鎖のある行だけを返す():
    h = {"note": "1行目は関係のない話\n2行目に実効RPM の式がある\n3行目"}
    assert ps.lever_chain(h, "rpm") == "2行目に実効RPM の式がある"
    assert ps.lever_chain(h, "sub_rate") == ""      # 語が無ければ空
    assert ps.lever_chain({}, "rpm") == ""          # `note:` が無くても落ちない
    assert ps.lever_chain({"note": "x"}, "") == ""  # 腕が空でも落ちない


def test_実物の2件が鎖で外れている():
    """**この回に潰した持ち越しそのもの**（`retro.py` の `premise_subject` 4周）。

    **数は固定しません** —— 台帳は毎周 増えます。固定するのは
    「`[?]` に残っている行は、`note:` に鎖が書いていない行だけ」という**性質**です。
    """
    for r in ps.audit():
        if r["lever_off"]:
            assert not r["note_line"], (
                f"`note:` に鎖があるのに `[?]` に残っています: {r['claim'][:40]}")


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
