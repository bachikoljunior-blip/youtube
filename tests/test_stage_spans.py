"""**焼きの 55〜90分 の内訳を、log から出せること。**

`ahead_sweep._run_out` の docstring は 2026-09-03 から
「**どの段が遅いか** …… いま誰も測れていません」と書いていました。
流すようにしても**行に時刻が無ければ段の長さは出ません** ——
25回 焼いて `data/rebake.jsonl` に残っているのは総和の `seconds` だけで、
55分 の内訳を言えた回は 0回 でした（2026-09-04 17:1x に数えた）。

いまは1行ごとに `[+MM:SS]` が付き、`stage_spans()` がその差から段を出します。
**新しい帳面も道具も足していません**（log だけで足ります）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import ahead_sweep as _as  # noqa: E402


def test_時刻の無い行からは何も出さない():
    """09-04 17:1x より前の log は時刻を持ちません。**推測で埋めないこと。**"""
    old = ["[sweep]   [clarity] 2周目: 挙がった 40件/40件",
           "[sweep]   [render] クリップ 5/83"]
    assert _as.stage_spans(old) == []


def test_段ごとの分が出る():
    log = [
        "[sweep] $ python -m src.pipeline …",
        "[sweep]   [+00:00] [pipeline] 台本を読み込みました",
        "[sweep]   [+00:30] [clarity] 1周目: 挙がった 40件/40件",
        "[sweep]   [+20:30] [tts:google] 1/83 3.20s こんにちは…",
        "[sweep]   [+25:30] [render] クリップ 1/83",
        "[sweep]   [+37:00] [render] 字幕焼き込み + 音声合成",
        "[sweep]   [+39:00] [verify] 検査に通りました",
    ]
    got = dict(_as.stage_spans(log))
    assert got["分かりやすさの輪"] == 20.0, got
    assert got["音声合成"] == 5.0, got
    assert got["クリップ"] == 11.5, got
    assert got["台本・下ごしらえ"] == 0.5, got
    # いちばん長い段が先頭に来ること（次に何を速くするかを、ここで選びます）
    assert _as.stage_spans(log)[0][0] == "分かりやすさの輪"


def test_輪が行き来しても合計で拾う():
    """分かりやすさの輪は「直してから初めから評価し直す」ので、何周もします。"""
    log = [
        "[sweep]   [+00:00] [clarity] 1周目",
        "[sweep]   [+10:00] [pipeline] 書き直しました",
        "[sweep]   [+11:00] [clarity] 2周目",
        "[sweep]   [+21:00] [tts:google] 1/83",
        "[sweep]   [+26:00] [verify] おわり",
    ]
    got = dict(_as.stage_spans(log))
    assert got["分かりやすさの輪"] == 20.0, got
    assert got["台本・下ごしらえ"] == 1.0, got


def test_知らない行はその他に落ちる():
    log = ["[sweep]   [+00:00] なにか知らない行",
           "[sweep]   [+02:00] [verify] おわり"]
    assert dict(_as.stage_spans(log))["その他"] == 2.0


def test_段の名前は重なりの無い順で当てる():
    """`[render] クリップ` は `[render]` より先に当たること
    （順が逆だと、クリップが「字幕・合成」に化けて 11分 が消えます）。"""
    marks = [m for m, _ in _as.STAGE_MARKS]
    assert marks.index("[render] クリップ") < marks.index("[render]")


def test_実物のlogの1行で当たる():
    """**行の字が変わったら、この検査が先に落ちること。**"""
    real = [
        "[sweep]   [+01:00] [clarity] 2周目: 挙がった 40件/40件 → 根拠あり 38件/39件",
        "[sweep]   [+02:00] [tts:google] 12/83  3.41s  ねんきんの…",
        "[sweep]   [+03:00] [render] クリップ 5/83",
        "[sweep]   [+04:00] [pipeline] タイトル: …",
        "[sweep]   [+05:00] おわり",
    ]
    got = dict(_as.stage_spans(real))
    for want in ("分かりやすさの輪", "音声合成", "クリップ", "台本・下ごしらえ"):
        assert want in got, f"{want} が拾えていません: {got}"
    assert "その他" not in got or got.get("その他", 0) == 0


def test_行に時刻が付くようになっている():
    """`_run_out` が `[+MM:SS]` を付けていること（付けないと上は全部 死にます）。"""
    import inspect
    src = inspect.getsource(_as._run_out)
    assert "[+{" in src or "+{int(el" in src, "行に経過時間を付けていません"


# ---------------------------------------------------- 画面に出ること（配線）

def test_画面の口が在る(tmp_path):
    """**出さない道具は、次の回から見えません**（この repo の
    「どこからも撃たれていない道具」の形）。`--write` が読む
    `next_slot.machine_rebake_lines()` の中から呼ばれること。"""
    import inspect
    from src import next_slot
    src = inspect.getsource(next_slot.machine_rebake_lines)
    assert "_bake_stage_span_lines" in src, "段の内訳が画面に出ていません"


def test_logが無くても黙らない(tmp_path):
    """`data/rebake.log` は `.gitignore` 済みで、作業場に無い回があります。
    **黙ると、配線が死んでいるのかまだ焼いていないのかを区別できません。**"""
    from src import next_slot
    got = next_slot._bake_stage_span_lines(root=tmp_path)
    assert got and "まだ出せません" in got[0], got


def test_時刻つきのlogから画面の行が出る(tmp_path):
    from src import next_slot
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "rebake.log").write_text(
        "[sweep]   [+00:00] [clarity] 1周目\n"
        "[sweep]   [+20:00] [tts:google] 1/83\n"
        "[sweep]   [+25:00] [render] クリップ 1/83\n"
        "[sweep]   [+36:30] [verify] おわり\n", encoding="utf-8")
    got = next_slot._bake_stage_span_lines(root=tmp_path)
    assert any("分かりやすさの輪" in ln and "20.0分" in ln for ln in got), got
    assert any("いちばん長いのは" in ln for ln in got), got
