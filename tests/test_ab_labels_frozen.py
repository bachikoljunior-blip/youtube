"""**実験を閉じる手順が、その実験の証拠を消していた。**（2026-08-28 の最適化の回）

## 何が仕掛かっていたか

`slide_pace` と `request_form` の群は、**読むたびに計算し直されます**
（`pipeline.slide_pace(topic_id)` / `script_writer.request_form(topic_id)` ——
どちらも既定引数で `SLOW_PACE_SHARE` / `MID_REQUEST_SHARE` を見る）。

そして `config/hypotheses.yaml` は、**その2件の畳み方**をこう書いています:

    1281行  「刻みは畳む（**`SLOW_PACE_SHARE = 0` にする**）」
    1206行  「**`MID_REQUEST_SHARE = 0` にして畳む**」

**その1行を実行した瞬間、判定の根拠が全部 消えます。** 実測（561テーマ）:

    SLOW_PACE_SHARE   0.5 → 速い 296 ／ 遅い 265      0.0 → **速い 561 ／ 遅い 0**
    MID_REQUEST_SHARE 0.5 → 途中あり 286 ／ 終端のみ 275  0.0 → **終端のみ 561 ／ 途中あり 0**

判定に入る本で見ると、**`slide_pace` 遅い 7本 → 0本 ／ `request_form`
途中あり 23本 → 0本**。`deadline_check` も `queue_lag` も `status` も
`ab_slots` も同じ関数を読むので、**全部そろって、無かったことにします** ——
`src/motion_groups.py` が言う「**ラベルが静かに嘘になる**」形そのものです。

## 直し

`data/ab_labels.json` に名札を焼き、`ab_split.group_of()` が
**凍らせた名札を優先**します。share を動かしても**新しい本にだけ**効く ——
それが「振り分けを止める」の本来の意味です。

## 読み口が **3本ではなく4本** だったこと

`_members_by_split()` を通しただけでは `request_form` は守れません
（`judgeable._members_by_request_form()` という**別の関数**が群を作るため）。
**同じ問いを解く関数が2本あって、片方だけ直っている**形です。
実測: 片方だけ直した時点で `slide_pace` は守れて、`request_form` は 23 → 0 でした。
下の `test_群を読む口が全部_凍結を通っていること` が、その数え上げです。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import ab_split, judgeable                            # noqa: E402


def test_控えがあること():
    """**無ければ何も守っていません。**（`ab_split.freeze_labels()` で作る）"""
    frozen = ab_split.frozen_labels()
    assert frozen, f"{ab_split.LABELS} がありません。`freeze_labels()` を撃つこと"
    for name in ("slide_pace", "request_form"):
        assert frozen.get(name), f"{name} の名札が焼かれていません"


def test_share_を_0_にしても群が消えないこと(monkeypatch):
    """**`config/hypotheses.yaml` が指示している畳み方を、そのまま撃ってみる。**"""
    from src import pipeline, script_writer

    before_pace = {k: len(v) for k, v in judgeable.members("slide_pace").items()}
    before_req = {k: len(v) for k, v in judgeable.members("request_form").items()}
    assert before_pace.get("遅い", 0) > 0, "処置群が空です（この検査は何も見ていません）"
    assert before_req.get("途中あり", 0) > 0, "処置群が空です"

    # 既定引数は定義時に束縛されるので、そちらも差し替えて最悪の場合を作る
    monkeypatch.setattr(pipeline, "SLOW_PACE_SHARE", 0.0)
    monkeypatch.setattr(script_writer, "MID_REQUEST_SHARE", 0.0)
    monkeypatch.setattr(pipeline.slide_pace, "__defaults__", (0.0,))
    monkeypatch.setattr(script_writer.request_form, "__defaults__", (0.0,))

    after_pace = {k: len(v) for k, v in judgeable.members("slide_pace").items()}
    after_req = {k: len(v) for k, v in judgeable.members("request_form").items()}
    assert after_pace == before_pace, (
        f"`SLOW_PACE_SHARE = 0` で群が動きました: {before_pace} → {after_pace}。"
        "**閉じる手順が、閉じた根拠を消しています**（`ab_split.group_of` の註）")
    assert after_req == before_req, (
        f"`MID_REQUEST_SHARE = 0` で群が動きました: {before_req} → {after_req}")


def test_凍結が無ければ本当に消えること(monkeypatch):
    """**壊れていた側の再現。** これが落ちるなら、群はもう share を見ていません
    （＝ 凍結は不要になった）—— そのときは `ab_split.group_of` の覆る条件を読むこと。
    """
    from src import pipeline

    monkeypatch.setattr(ab_split, "_LABEL_CACHE", {})
    monkeypatch.setattr(pipeline, "SLOW_PACE_SHARE", 0.0)
    monkeypatch.setattr(pipeline.slide_pace, "__defaults__", (0.0,))
    after = {k: len(v) for k, v in judgeable.members("slide_pace").items()}
    assert after.get("遅い", 0) == 0, (
        "凍結を外しても群が残っています。`pipeline.slide_pace` が "
        "`SLOW_PACE_SHARE` を見なくなったなら、この検査ごと畳んでよい")


def test_群を読む口が全部_凍結を通っていること():
    """**手で並べないこと。** `exp.split(` を直に呼ぶ口が残っていたら、そこが穴です。

    実測: `_members_by_split()` だけ通した時点で `request_form` は素通りでした
    （`judgeable._members_by_request_form()` という**別の関数**が群を作る）。
    """
    import ast

    bad = []
    for base in ("src", "scripts"):
        for path in sorted((ROOT / base).glob("*.py")):
            if path.name == "ab_split.py":
                continue                   # 定義そのもの（`group_of` の中で呼ぶ）
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:                                # pragma: no cover
                continue
            # **字ではなく木で見ること**（2026-08-28）。字で見た版は
            # `src/watches.py` の**註の中の1行**を呼び出しとして拾いました。
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "split"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "exp"):
                    bad.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not bad, (
        "**群を `exp.split()` から直に読んでいます** ——"
        " `ab_split.group_of(exp, topic_id)` を通すこと"
        "（凍らせた名札が効きません）:\n  " + "\n  ".join(bad))


def test_作る側が名札を焼くこと():
    """**焼く場所が無ければ、名札は必ず古くなります。**

    実測 2026-08-28 —— 手で1回 焼いた **30分 後**に主実行が 2本 作り、
    上の `test_share_を_0_にしても群が消えないこと` が **遅い 9 → 7** で落ちました
    （新しい2本が名札を持たず、生の関数へ落ちた）。
    **腕はテーマIDの純関数なので、作る前に確定しています** ——
    だから作る側が、作る前に焼きます。
    """
    body = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    assert "freeze_labels(" in body, (
        "`scripts/batch_build.py` が `ab_split.freeze_labels()` を呼んでいません。"
        "**焼き直す口が無いと、新しい本は凍結の外に落ちます**")


def test_名札を上書きしないこと(tmp_path, monkeypatch):
    """**開いている実験の名札が動いたら、群を作り直したのと同じ**です。"""
    monkeypatch.setattr(ab_split, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(ab_split, "_LABEL_CACHE",
                        {"slide_pace": {"s-keep-1": "遅い"}})
    out = ab_split.freeze_labels(["s-keep-1"], names=["slide_pace"])
    assert out["slide_pace"]["s-keep-1"] == "遅い", (
        "既にある名札を上書きしました。**それは群の作り直しです**")
