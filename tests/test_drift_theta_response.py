"""**θ の隣に、その θ の応答時間を出す。**（`scripts/drift.py`）

## この検査が守っているもの（2026-08-27・最適化の回）

`docs/spawn_prompt.md` は最適化の役に、毎周こう自己採点させていました ——
「答えが毎回変わるのに θ が改善しないなら、答え方が外れている」。

**その採点は、ほぼ必ず『外れている』と出ます。**

- `drift.rounds_per_day()` は**今日を数えません** → θ の分子は同じ日のあいだ不動
- 分母が動くのは前提が実際に閉じた日だけ ＝ 実測 **0.86件/日**
- 最適化の役の周は実測 **1.14時間**ごと ＝ 1日 21周

→ **1周のあいだに θ が動く見込みは 4%。96% の回は誤報。**
実際に **5周 続けて**同じ 22周/26周 を読み、そのたび前の回の答えを捨てていました。

**だから θ を消すのではなく、応答時間を同じ画面に置きます。**
消えたら（＝この検査が落ちたら）、次の役はまた 96% の誤報で自分を採点します。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import drift  # noqa: E402


def _rounds(tmp_path, monkeypatch, stamps, role="optimizer"):
    p = tmp_path / "rounds.jsonl"
    p.write_text(
        "\n".join(json.dumps({"at": s, "role": role}, ensure_ascii=False) for s in stamps) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(drift, "ROUNDS", p)
    return p


def test_周の間隔は実測の中央値で出す(tmp_path, monkeypatch):
    _rounds(tmp_path, monkeypatch, [
        "2026-08-27T00:00:00+00:00",
        "2026-08-27T01:00:00+00:00",
        "2026-08-27T03:00:00+00:00",
        "2026-08-27T04:00:00+00:00",
    ])
    # 差は 1h / 2h / 1h → 中央値 1h（平均 1.33h ではない）
    assert drift.role_gap_hours("optimizer") == 1.0


def test_別の役の周は混ぜない(tmp_path, monkeypatch):
    p = tmp_path / "rounds.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"at": "2026-08-27T00:00:00+00:00", "role": "optimizer"},
        {"at": "2026-08-27T00:30:00+00:00", "role": "hourly"},
        {"at": "2026-08-27T02:00:00+00:00", "role": "optimizer"},
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(drift, "ROUNDS", p)
    # hourly の 00:30 を混ぜると 0.5h になる。役で切れていれば 2h
    assert drift.role_gap_hours("optimizer") == 2.0


def test_周が1つ以下なら測らない(tmp_path, monkeypatch):
    _rounds(tmp_path, monkeypatch, ["2026-08-27T00:00:00+00:00"])
    assert drift.role_gap_hours("optimizer") is None


def test_印が無くても落ちない(tmp_path, monkeypatch):
    monkeypatch.setattr(drift, "ROUNDS", tmp_path / "no-such-file.jsonl")
    assert drift.role_gap_hours("optimizer") is None
    out = "\n".join(drift.theta_response("2026-08-27", 6, "2026-08-30"))
    assert "測れません" in out


def test_1周ごとに読むなと言い_見込みを数で出す(tmp_path, monkeypatch):
    _rounds(tmp_path, monkeypatch, [
        "2026-08-27T00:00:00+00:00",
        "2026-08-27T01:00:00+00:00",
        "2026-08-27T02:00:00+00:00",
    ])
    out = "\n".join(drift.theta_response("2026-08-27", 7, "2026-08-30"))
    # 1日 24周、閉じるのは 1.0件/日 → 4%
    assert "1周ごとの答え合わせに使わない" in out
    assert "4%" in out
    assert "96%" in out


def test_期日が過ぎていたら負の周数を出さない(tmp_path, monkeypatch):
    _rounds(tmp_path, monkeypatch, [
        "2026-08-27T00:00:00+00:00",
        "2026-08-27T01:00:00+00:00",
        "2026-08-27T02:00:00+00:00",
    ])
    out = "\n".join(drift.theta_response("2026-08-27", 6, "2026-08-26"))
    assert "この回に閉じられます" in out
    line = out.split("次に1件")[1].split("\n")[0]
    # **「-21周 後」を出していました**（2026-08-27 の実物）。周数そのものを出さない
    assert "周** 後" not in line
    assert "（+-" not in line


def test_1周で応える目盛りを名指しする(tmp_path, monkeypatch):
    _rounds(tmp_path, monkeypatch, [
        "2026-08-27T00:00:00+00:00",
        "2026-08-27T01:00:00+00:00",
    ])
    out = "\n".join(drift.theta_response("2026-08-27", 6, "2026-08-30"))
    # **代わりに読む所を言わないと、次の回は「読むな」しか受け取りません。**
    assert "arm_speed.forward()" in out


def test_閉じた前提が0件でも落ちない(tmp_path, monkeypatch):
    _rounds(tmp_path, monkeypatch, [
        "2026-08-27T00:00:00+00:00",
        "2026-08-27T01:00:00+00:00",
    ])
    out = "\n".join(drift.theta_response("2026-08-27", 0, None))
    assert "0.00件/日" in out
