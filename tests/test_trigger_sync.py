"""**トリガーの正本（`docs/trigger_spec.json`）が実物とズレたら落ちる検査。**

## この検査が守っているもの（2026-08-20）

`docs/TRIGGER.md` は「自動実行の正本」と名乗っていましたが、**正本ではありません。**
実物は Routine 側にあり、**この repo を1文字書き換えても発火は1秒も変わりません。**
2026-08-12 には、この文書が `9 */6`、実物が `9 */12`、親の見立てが `9 */8` で
**3か所とも違って**いました。「変えたら同時に直すこと」と書いてありましたが、
**書いても直っていません。**

だから、次の3つが崩れたら赤くします:

1. **親が byte 比較する写し（`docs/trigger_body.rendered.md`）が古くなったら**
   —— 型か識別子だけ直して写しを忘れると、親は古い本文を当て続けます
2. **差し込み口が埋まらないまま出ようとしたら** —— `<<key>>` が本文に残ります
3. **「子が本文を直せる」形に戻ったら** —— 2026-08-20 に子が実際に撃って
   弾かれています。戻すと、撃って弾かれたことに気づかないまま
   「直した」と日誌に書く回が出ます
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("trigger_sync",
                                               ROOT / "scripts" / "trigger_sync.py")
ts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ts)


def test_rendered_copy_is_current() -> None:
    """**親が取るのは写しです。** 古いと、親は古い本文を当て直します。"""
    want = ts.render_body(ts.load_spec()) + "\n"
    got = ts.RENDERED.read_text(encoding="utf-8")
    assert got == want, ("`docs/trigger_body.rendered.md` が古いです。"
                         "`python scripts/trigger_sync.py --write-rendered` を打つこと")


def test_no_placeholder_survives() -> None:
    body = ts.render_body(ts.load_spec())
    assert "<<" not in body, f"埋まらない差し込み口が本文に残っています: {body[:120]}"


def test_missing_placeholder_is_loud(tmp_path: Path) -> None:
    """**黙って `<<key>>` のまま出さないこと。** 親がそれをそのまま当てます。"""
    spec = ts.load_spec()
    spec["body_file"] = "body.md"
    (tmp_path / "body.md").write_text("親へ <<存在しない口>> です", encoding="utf-8")
    with pytest.raises(SystemExit):
        ts.render_body(spec, root=tmp_path)


def test_child_cannot_write_the_body() -> None:
    """**本文は子から撃てません**（2026-08-20 実測）。

    `CHILD_WRITABLE` に `body` を足したら落とします —— 足すと、次の子が
    `update_trigger(prompt=…)` を撃ち、`editing the prompt of a routine whose
    fires deliver into a session that is not your own` で弾かれます。
    **弾かれたことに気づかない回が出るのが本当の損失です。**
    """
    assert "body" not in ts.CHILD_WRITABLE
    assert "body" in ts.PARENT_ONLY


def test_plan_never_mixes_the_body_into_the_child_call() -> None:
    """**混ぜると呼び全体が弾かれ、cron だけ直せた回まで失敗になります。**"""
    spec = ts.load_spec()
    seen = {"id": spec["trigger_id"], "name": "ちがう名前",
            "cron_expression": "0 */6 * * *", "enabled": True,
            "persistent_session_id": spec["persistent_session_id"],
            "environment_id": spec["environment_id"], "body": "ふるい本文",
            "ingested_at": "2099-01-01T00:00:00+00:00"}
    out = ts.plan(spec, seen)
    child_call = out.split("## 本文")[0]
    assert "cron_expression" in child_call
    assert "prompt" not in child_call, "子の呼びに本文が混ざっています"
    # 2026-08-24 まで `親だけ` を見ていました。**親も撃ってはいけません** ——
    # 12:10:35Z、親が撃って `Waiting on permission: …update_trigger` で止まり、
    # 次の発火が届かなくなりました。見るのは「子は撃てません」のほうだけにします。
    assert "子は撃てません" in out


def test_drift_is_detected_field_by_field() -> None:
    spec = ts.load_spec()
    ok = {"id": spec["trigger_id"], "name": spec["name"],
          "cron_expression": spec["cron_expression"], "enabled": spec["enabled"],
          "persistent_session_id": spec["persistent_session_id"],
          "environment_id": spec["environment_id"],
          "body": ts.render_body(spec), "ingested_at": "2099-01-01T00:00:00+00:00"}
    assert ts.diff(spec, ok) == []
    assert ts.diff(spec, {**ok, "cron_expression": "9 */12 * * *"}) != []
    assert ts.diff(spec, None) != []


def test_never_seen_is_not_the_same_as_matching() -> None:
    """**「見ていない」を「合っている」と読まないこと。** 8/12 の入口です。"""
    text, drifted = ts.render(ts.load_spec(), None)
    assert drifted is True
    assert "一度も見ていません" in text


def test_stale_observation_still_rings() -> None:
    """古い観測は、合っていても鳴らします（**証拠の古さ自体が欠陥**）。"""
    spec = ts.load_spec()
    old = {"id": spec["trigger_id"], "name": spec["name"],
           "cron_expression": spec["cron_expression"], "enabled": spec["enabled"],
           "persistent_session_id": spec["persistent_session_id"],
           "environment_id": spec["environment_id"],
           "body": ts.render_body(spec), "ingested_at": "2000-01-01T00:00:00+00:00"}
    assert ts.diff(spec, old) == []
    _text, drifted = ts.render(spec, old)
    assert drifted is True


def test_observed_reads_both_shapes_of_the_return() -> None:
    """`list_triggers` と `update_trigger` は**返りの形が違います。**

    片方しか受けないと、「積んだつもりで積めていない」回が出ます。
    """
    spec = ts.load_spec()
    row = {"id": spec["trigger_id"], "name": "n", "cron_expression": "9 * * * *",
           "enabled": True, "persistent_session_id": "session_x",
           "job_config": {"ccr": {"environment_id": "env_x", "events": [
               {"data": {"message": {"content": "ほんぶん"}}}]}}}
    for dump in ({"data": [row]}, {"trigger": row}, [row], row):
        got = ts.observed(dump, spec["trigger_id"])
        assert got is not None and got["body"] == "ほんぶん", dump
    assert ts.observed({"data": [row]}, "trig_ちがう") is None


def test_spec_matches_the_documented_identifiers() -> None:
    """正本の欄が欠けたまま push されないこと。"""
    spec = json.loads((ROOT / "docs" / "trigger_spec.json").read_text(encoding="utf-8"))
    for key in ("trigger_id", "cron_expression", "persistent_session_id",
                "environment_id", "repo_url", "branch", "body_file"):
        assert spec.get(key), f"`docs/trigger_spec.json` に {key} がありません"


def test_正本が観測より後に変わったら_それを先に言う(tmp_path, monkeypatch):
    """**ズレの正体が「実物が違う」ではなく「観測が古い」場合を見分ける。**

    2026-08-21 に実測: 前の回が `update_trigger` で 1日21回→19回 を当てたのに
    `list_triggers` を積み直さなかったので、次の回の `status.py` が
    「実物は21回のまま」と読み、**直っているものを直しにいく**ところでした。
    時刻では見分けられません（clone のたびに mtime が起動時刻になる）。
    """
    import json as _json
    from scripts import trigger_sync as ts

    spec = ts.load_spec()
    seen = {
        "id": spec["trigger_id"],
        "name": spec["name"],
        "cron_expression": spec["cron_expression"],
        "enabled": spec["enabled"],
        "persistent_session_id": spec.get("persistent_session_id"),
        "environment_id": spec.get("environment_id"),
        "body": ts.render_body(spec),
        "ingested_at": ts.datetime.now(ts.timezone.utc).isoformat(timespec="seconds"),
        "spec_fingerprint": ts.spec_fingerprint(spec),
    }
    text, drifted = ts.render(spec, seen)
    assert not drifted, text
    assert "正本がこの観測より後に" not in text

    # 正本だけを動かす（＝直した直後に積み直していない回）
    moved = _json.loads(_json.dumps(spec))
    moved["cron_expression"] = "9 */3 * * *"
    text, drifted = ts.render(moved, seen)
    assert drifted
    assert "正本がこの観測より後に変わっています" in text
    assert "まず `list_triggers` を保存して `--ingest` を打つこと" in text


def test_指紋の無い古い観測では余計なことを言わない():
    """`spec_fingerprint` を入れる前に積んだ観測が残っていても、鳴らさない。"""
    from scripts import trigger_sync as ts

    spec = ts.load_spec()
    seen = {
        "id": spec["trigger_id"],
        "cron_expression": "9 */12 * * *",     # わざとズラす
        "enabled": spec["enabled"],
        "body": "",
        "ingested_at": ts.datetime.now(ts.timezone.utc).isoformat(timespec="seconds"),
    }
    text, drifted = ts.render(spec, seen)
    assert drifted
    assert "正本がこの観測より後に" not in text

def test_本文のズレは_鳴らすが_命じない() -> None:
    """**毎周の1行が、誰にもできないことを命じていた**（2026-09-01 08:2x に直した）。

    `diff()` の body の行は長らく「`--emit-body` を当てること」でした。
    **`--emit-body` は当てません。当てるべき姿を印字するだけ**です。
    実際に当てるには `update_trigger` が要り、**この repo はその道を意図して
    閉じてあります**:

        親が撃つ  2026-08-24 12:10Z → `SESSION_STATUS_REQUIRES_ACTION`
                  ＝ 承認待ちで親が止まり、**次の発火も届かない**
        子が撃つ  2026-08-20 / 08-24 の2回、道具ごと弾かれている

    `docs/trigger_parent.md`「トリガー本文の正本」は、まさにこれを理由に
    **節ごと空にしてあります**。**同じ repo の2か所が逆を言っていました。**

    **鳴らすのはよい**（識別子のズレはここでしか見えない）。**命じるのが誤り**でした。

    **覆る条件**: `update_trigger` が承認待ちにならずに通るようになったら、
    `docs/trigger_parent.md` の同じ節と**両方**を戻すこと（片方だけ戻すと、
    また逆のことを言う2か所になります）。
    """
    spec = ts.load_spec()
    seen = {k: spec[k] for k in ts.FIELDS if k in spec}
    seen["body"] = "みじかい"
    line = next((g for g in ts.diff(spec, seen) if g.startswith("body:")), None)
    assert line is not None, "本文のズレが鳴っていません（識別子のズレも同じ節で見ます）"
    assert "当てること" not in line, (
        "本文のズレの行が、まだ「当てること」と命じています。"
        "**親は承認待ちで鎖ごと止まり、子は道具ごと弾かれます** —— "
        "`docs/trigger_parent.md`「トリガー本文の正本」と逆のことを言う2か所目に戻っています"
    )
    assert "当て直さないこと" in line
    assert "trigger_parent.md" in line, (
        "なぜ当てないかの出どころが行に無いと、次の回が理由を探して自分で考え始めます"
        "（同じ形が 2026-08-24 12:0x にあります）"
    )
