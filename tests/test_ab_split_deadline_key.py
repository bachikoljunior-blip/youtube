"""`_deadline_from_yaml` が、**振り分けの在りかを実物から引く**こと。

## なぜ要るか（2026-08-28 に踏んだ）

`src/ab_split._deadline_from_yaml()` は、`config/hypotheses.yaml` の
`falsified_if` の中から**振り分けを名指ししている前提**を探して期限を引きます。
その鍵が **`script_writer.<name>` のべた書き**でした。

**`slide_pace` は `src/pipeline.py` に在ります**（`_pace_form.split_ref`）。
だから鍵が一度も当たらず、**この前提だけ静かに `fallback`（べた書きの日付）へ
落ちていました。** 08/28 13:57 の回が yaml の期限を **09-24 → 10-11** に直した
直後、`tests/test_ab_split.py::test_期限は_yaml_と同じ` が赤くなって見つかりました。

**同じ穴は 2026-08-27 に検査の側だけ塞がれています** ——
`tests/test_ab_split._split_ref` は「**在りかは実物から引くこと**」と書いて
`split_ref` を見るようになりましたが、**道具の側は写されませんでした。**
「同じことを2か所が別々に言っていて、片方しか読まれていない」の形です。

## この検査が守っているもの

`test_期限は_yaml_と同じ` は**結果**（引けた日付が yaml と同じか）を見ます。
ここが見るのは**鍵のほう**です —— yaml の期限がたまたま fallback と同じ日に
なった回には、あちらは通ってしまいます（**静かに落ちているのに緑**）。
"""
from __future__ import annotations

from datetime import date

from src import ab_split


def test_在りかは実物から引く():
    """包みが `split_ref` を持っていれば、それが鍵。無ければ関数自身の在りか。"""
    assert ab_split._split_ref_of(ab_split._pace_form, "slide_pace") == "pipeline.slide_pace"
    from src.script_writer import title_form
    assert ab_split._split_ref_of(title_form, "title_form") == "script_writer.title_form"
    # 渡されなかった回は、いままでどおり `script_writer.<name>`。
    assert ab_split._split_ref_of(None, "hook_form") == "script_writer.hook_form"


def test_pipeline_にある振り分けも_yaml_から引ける(tmp_path, monkeypatch):
    """**鍵そのもの**を見る。fallback と同じ日付でも落ちないように、別の日を置く。"""
    yml = tmp_path / "config"
    yml.mkdir()
    (yml / "hypotheses.yaml").write_text(
        "hypotheses:\n"
        "  - deadline: 2026-12-25\n"
        "    falsified_if: |\n"
        "      `pipeline.slide_pace` が振り分けた群で比べる\n",
        encoding="utf-8")
    monkeypatch.setattr(ab_split, "ROOT", tmp_path)
    got = ab_split._deadline_from_yaml("slide_pace", date(2026, 9, 24),
                                       split=ab_split._pace_form)
    assert got == date(2026, 12, 25), (
        "`pipeline.` に在る振り分けを、yaml から引けていません —— "
        "**鍵が `script_writer.<name>` のべた書きに戻っています**")


def test_見つからない回は静かに_fallback_へ落ちる(tmp_path, monkeypatch):
    """**ここで例外を上げないこと** —— `status.py` ごと止まって投稿が止まります。"""
    yml = tmp_path / "config"
    yml.mkdir()
    (yml / "hypotheses.yaml").write_text("hypotheses: []\n", encoding="utf-8")
    monkeypatch.setattr(ab_split, "ROOT", tmp_path)
    assert ab_split._deadline_from_yaml("slide_pace", date(2026, 9, 24),
                                        split=ab_split._pace_form) == date(2026, 9, 24)


def test_走っている実験は全部_fallback_ではなく_yaml_から引けている():
    """**実物で**、鍵が当たっていること（当たらないと fallback と同じ日になる）。

    `EXPERIMENTS` の期限が、`config/hypotheses.yaml` の値と一致すること自体は
    `test_ab_split.py::test_期限は_yaml_と同じ` が見ています。ここは
    **鍵が当たった件数**を見ます —— 1件でも当たらなければ、その実験は
    「yaml を読んでいるつもりで、べた書きを返している」状態です。
    """
    import yaml as _yaml
    doc = _yaml.safe_load(
        (ab_split.ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    for name, exp in ab_split.EXPERIMENTS.items():
        ref = ab_split._split_ref_of(exp.split, name)
        hit = [h for h in (doc.get("hypotheses") or [])
               if ref in str(h.get("falsified_if", "")) and not h.get("closed_on")]
        assert len(hit) == 1, (
            f"{name}: `{ref}` を名指ししている開いた前提が {len(hit)}件。"
            "**0件なら、期限はべた書きの fallback から出ています**")
