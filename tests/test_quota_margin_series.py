"""余裕（`ceiling_rate()` ÷ 要る速さ）の列は、**手で送らず台帳から読む**。

2026-09-11 07:5x・optimizer・Opus。

**なぜ足したか**: §7「いまの数」が「3.07 → 3.07 → 3.07 → 3.08 → 3.08 → 3.09」を
**周ごとに手で送って**いました。**`pace(過去の刻)` で数え直しても、その列は出ません** ——
`per_lap` も遅れも**いまの台帳**から引き直されるので、過去の点まで「いまの基準」で塗り替わります
（実測 09/10 17:45〜21:58 の 8周 を数え直すと **3.094〜3.098**・手の列は 3.07〜3.09）。
＝ **その周が見た数は、その周に書くしかありません**（`quota.record_model_choice`）。

**陽性対照**（壊したら落ちるまで撃つ・METHOD §5 の教訓の形3つ目）:
畳みを外すと同じ周が 2回 出る／門の定数を別々に持たせると片方だけ動く／
`reach_ceiling_margin` を書かない行だけの台帳で「まだ 1点も無い」と言えること。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quota  # noqa: E402


def _write(tmp_path, rows):
    f = tmp_path / "model_choice.jsonl"
    f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return f


def _row(at, margin=None, role="hourly"):
    r = {"at": at, "work_kind": f"{role}:leverage", "model": "fable"}
    if margin is not None:
        r["reach_ceiling_margin"] = margin
    return r


def test_同じ周の_2行_は_1つ_に畳むこと(tmp_path, monkeypatch):
    """親は 1周に 2行（`hourly` と `optimizer`）積みます。畳まないと周の数が倍に出ます。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T06:58:40+09:00", 3.09, "hourly"),
        _row("2026-09-11T06:58:40+09:00", 3.09, "optimizer"),
        _row("2026-09-11T07:34:00+09:00", 3.05, "hourly"),
        _row("2026-09-11T07:34:00+09:00", 3.05, "optimizer"),
    ]))
    assert quota.margin_series() == [("2026-09-11T06:58:40+09:00", 3.09),
                                     ("2026-09-11T07:34:00+09:00", 3.05)]


def test_古い順に返し_窓の外は落とすこと(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row(f"2026-09-11T0{i}:00:00+09:00", 3.0 + i / 100) for i in range(1, 8)
    ]))
    xs = quota.margin_series(3)
    assert [v for _, v in xs] == [pytest.approx(3.05), pytest.approx(3.06), pytest.approx(3.07)]


def test_書いていない行しか無ければ_黙って_0_を返さず言うこと(tmp_path, monkeypatch):
    """**この列が在る前の行を「0点」と読ませないこと**（覆る条件 (1)）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T06:00:00+09:00"), _row("2026-09-11T06:36:00+09:00")]))
    assert quota.margin_series() == []
    assert "まだ 1点も積まれていません" in quota.margin_line()


def test_門を切った周は名指しすること(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T07:00:00+09:00", 3.05),
        _row("2026-09-11T07:36:00+09:00", 2.98)]))
    line = quota.margin_line()
    assert "**切った周: 09-11T07:36 2.98**" in line and "掃き直すこと" in line
    assert "門の上" not in line


def test_門の上なら切った周を名指ししないこと(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T07:00:00+09:00", 3.05),
        _row("2026-09-11T07:36:00+09:00", 3.01)]))
    line = quota.margin_line()
    assert "＝ **門の上**" in line and "切った周" not in line


def test_門の出どころは_1か所(tmp_path, monkeypatch):
    """**片方だけ動かせる形にしないこと** —— `pace_report` と `margin_line` が
    3.0 を別々に持っていました（2026-09-11 07:5x に定数へ寄せた）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", _write(tmp_path, [
        _row("2026-09-11T07:00:00+09:00", 3.05)]))
    monkeypatch.setattr(quota, "CEILING_MARGIN_GATE", 4.0)
    assert "**切った周: 09-11T07:00 3.05**" in quota.margin_line()
    src = (Path(__file__).resolve().parents[1] / "scripts" / "quota.py").read_text(encoding="utf-8")
    assert src.count('"（門 3.0倍）"') == 0        # 生の 3.0 を印字に残さないこと


def test_親が周ごとに余裕を積むこと(tmp_path, monkeypatch):
    """**この列は親が書きます** —— `record_model_choice` が実際に欄を足すこと
    （`pace()` が落ちても行は書く ＝ そのときは `None`・覆る条件 (1)）。"""
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", tmp_path / "model_choice.jsonl")
    monkeypatch.setattr(quota, "pace", lambda now=None: {"used_now": 78.1, "reach_ceiling_margin": 3.0462})
    row = quota.record_model_choice("optimizer", "opus", "検査")
    assert row["reach_ceiling_margin"] == 3.046          # 3桁 に丸めて積む
    assert [v for _, v in quota.margin_series()] == [3.046]

    def boom(now=None):
        raise RuntimeError("目盛りが無い")

    monkeypatch.setattr(quota, "pace", boom)
    row = quota.record_model_choice("hourly", "fable", "検査")
    assert row["reach_ceiling_margin"] is None
    assert [v for _, v in quota.margin_series()] == [3.046]   # 空の周は列に入れない


def test_壊れた行は落として続けること(tmp_path, monkeypatch):
    f = tmp_path / "model_choice.jsonl"
    f.write_text('{"at": "2026-09-11T07:00:00+09:00", "reach_ceiling_margin": 3.05}\n'
                 "{ここは JSON ではない\n"
                 '{"at": "2026-09-11T07:36:00+09:00", "reach_ceiling_margin": 3.02}\n',
                 encoding="utf-8")
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", f)
    assert [v for _, v in quota.margin_series()] == [3.05, 3.02]
