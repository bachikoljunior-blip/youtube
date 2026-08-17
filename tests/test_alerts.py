"""`src/alerts.py` —— 一覧に自分の当たり率を測らせる枠組みの検査。

**故障注入を含みます。** 「畳む」側だけを見ていると、
**当たりが入っているのに畳む**という逆向きの壊れ方を素通りします
（同じ向きの取りこぼしを、この repo は通算7回踏んでいます）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import alerts  # noqa: E402


@pytest.fixture(autouse=True)
def _no_show_all():
    alerts.set_show_all(False)
    yield
    alerts.set_show_all(False)


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")
    return path


def _ring_rows(key: str, n: int, *, start: int = 1) -> list[dict]:
    return [{"at": f"2026-08-16T{h:02d}:00:00+09:00", "key": key, "n": 3,
             "session": f"session_{h:02d}"}
            for h in range(start, start + n)]


def test_鳴っただけでは畳まない(tmp_path):
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", alerts.FOLD_AFTER - 1))
    runs = _write(tmp_path / "r.jsonl", [])
    st = alerts.state("k", ledger=led, runs=runs)
    assert st.rings_since == alerts.FOLD_AFTER - 1
    assert not st.folded


def test_当たり0がしきい値に届いたら畳む(tmp_path):
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", alerts.FOLD_AFTER))
    runs = _write(tmp_path / "r.jsonl", [])
    st = alerts.state("k", ledger=led, runs=runs, n=22)
    assert st.folded
    assert "22件" in st.line and "全文は `--alerts-all`" in st.line
    # **消していないこと。** 件数と、開き方と、当たりの残し方が1行に入る。
    assert "--closes k" in st.line


def test_当たりが1件でも入ったら数え直す(tmp_path):
    """**故障注入。** 当たりを入れた瞬間に畳むのをやめなければ、
    効いている一覧まで黙らせます（逆向きの壊れ方）。"""
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", alerts.FOLD_AFTER + 2))
    # 当たりは「鳴った途中」に入る。ここより後の鳴りだけが数え直しの対象。
    # 01:00〜10:00 の10回に対し、当たりが 08:30 なので残るのは 09:00・10:00 の2回。
    runs = _write(tmp_path / "r.jsonl", [
        {"at": "2026-08-16T08:30:00+09:00", "kind": "ship",
         "what": "fix: ...", "closes": ["k"]},
    ])
    st = alerts.state("k", ledger=led, runs=runs)
    assert st.acts_total == 1
    assert st.rings_total == alerts.FOLD_AFTER + 2
    assert st.rings_since == 2               # **当たりで数え直している**
    assert not st.folded


def test_一度当たった一覧が再び惰性に落ちたら畳む(tmp_path):
    """**当たり0件と書かないこと。** 通算では当たっているので、
    「最後に手が打たれてから」と書き分けます。"""
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", alerts.FOLD_AFTER + 2))
    runs = _write(tmp_path / "r.jsonl", [
        {"at": "2026-08-16T01:30:00+09:00", "kind": "ship", "closes": ["k"]},
    ])
    st = alerts.state("k", ledger=led, runs=runs, n=4)
    assert st.folded and st.acts_total == 1
    assert "最後に手が打たれてから" in st.line
    assert "当たり0件" not in st.line


def test_散文の宣言は当たりに数えない(tmp_path):
    """**日誌の文からは読みません**（`--closes` を足した回と同じ理由）。"""
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", alerts.FOLD_AFTER))
    runs = _write(tmp_path / "r.jsonl", [
        {"at": "2026-08-16T04:30:00+09:00", "kind": "ship",
         "what": "fix: k を閉じました（散文の宣言）"},
    ])
    assert alerts.state("k", ledger=led, runs=runs).folded


def test_ship以外の行は当たりに数えない(tmp_path):
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", alerts.FOLD_AFTER))
    runs = _write(tmp_path / "r.jsonl", [
        {"at": "2026-08-16T04:30:00+09:00", "kind": "start", "closes": ["k"]},
    ])
    assert alerts.state("k", ledger=led, runs=runs).folded


def test_件数0では鳴ったことにしない(tmp_path, monkeypatch):
    """「見にいったが空だった」を鳴った回数に混ぜると、当たり率が薄まります。"""
    led = tmp_path / "a.jsonl"
    runs = _write(tmp_path / "r.jsonl", [])
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID", "cse_zzz")
    alerts.ring("k", 0, ledger=led, runs=runs)
    assert not led.exists() or alerts.rings("k", path=led) == []


def test_同じ回に何度叩いても1回(tmp_path, monkeypatch):
    """鳴った回数は「回」で数える。1回の中で status.py を3回叩いても1回。"""
    led = tmp_path / "a.jsonl"
    runs = _write(tmp_path / "r.jsonl", [])
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID", "cse_abc")
    for _ in range(3):
        alerts.ring("k", 5, ledger=led, runs=runs)
    assert len(alerts.rings("k", path=led)) == 1


def test_別の回なら別に数える(tmp_path, monkeypatch):
    led = tmp_path / "a.jsonl"
    runs = _write(tmp_path / "r.jsonl", [])
    for sid in ("cse_a", "cse_b", "cse_c"):
        monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID", sid)
        alerts.ring("k", 5, ledger=led, runs=runs)
    assert len(alerts.rings("k", path=led)) == 3


def test_鍵ごとに独立(tmp_path):
    led = _write(tmp_path / "a.jsonl",
                 _ring_rows("k1", alerts.FOLD_AFTER)
                 + _ring_rows("k2", 2, start=20))
    runs = _write(tmp_path / "r.jsonl", [])
    assert alerts.state("k1", ledger=led, runs=runs).folded
    assert not alerts.state("k2", ledger=led, runs=runs).folded


def test_foldable_False_は畳まない(tmp_path):
    """期限の来た前提のように、**定義から必ず手を打つ一覧**は畳ませない。"""
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", alerts.FOLD_AFTER * 3))
    runs = _write(tmp_path / "r.jsonl", [])
    assert not alerts.state("k", ledger=led, runs=runs, foldable=False).folded


def test_show_all_で畳まない_ただし表には状態が残る(tmp_path):
    """`--alerts-all` を1回付けただけで状態まで消えると、
    「畳む条件に入っている」ことが見えなくなります。"""
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", alerts.FOLD_AFTER))
    runs = _write(tmp_path / "r.jsonl", [])
    alerts.set_show_all(True)
    st = alerts.state("k", ledger=led, runs=runs)
    assert not st.folded
    assert st.would_fold
    assert "**畳んだ**" in alerts.render_table([st])


def test_表は初出の順で全部の鍵を出す(tmp_path):
    led = _write(tmp_path / "a.jsonl",
                 _ring_rows("k1", 1) + _ring_rows("k2", 1, start=5)
                 + _ring_rows("k1", 1, start=9))
    runs = _write(tmp_path / "r.jsonl", [])
    rows = alerts.table(ledger=led, runs=runs)
    assert [r.key for r in rows] == ["k1", "k2"]
    assert rows[0].rings_total == 2


def test_当たり率(tmp_path):
    led = _write(tmp_path / "a.jsonl", _ring_rows("k", 4))
    runs = _write(tmp_path / "r.jsonl", [
        {"at": "2026-08-16T02:30:00+09:00", "kind": "ship", "closes": ["k"]},
    ])
    st = alerts.state("k", ledger=led, runs=runs)
    assert st.rings_total == 4 and st.acts_total == 1
    assert st.hit_rate == pytest.approx(0.25)


def test_壊れた行は落とさない(tmp_path):
    led = tmp_path / "a.jsonl"
    led.write_text('{"at":"2026-08-16T01:00:00+09:00","key":"k","n":1}\nこわれた行\n',
                   encoding="utf-8")
    runs = _write(tmp_path / "r.jsonl", [])
    assert alerts.state("k", ledger=led, runs=runs).rings_total == 1


def test_台帳が無くても落ちない(tmp_path):
    st = alerts.state("k", ledger=tmp_path / "none.jsonl", runs=tmp_path / "none2.jsonl")
    assert st.rings_total == 0 and not st.folded
    assert "まだ1件も鳴っていません" in alerts.render_table([])


# ---------------------------------------------------------------------------
# 実物の一覧を通した検査（**枠組みだけ通っても、繋がっていなければ0件で緑になる**）
# ---------------------------------------------------------------------------

def _dupes_videos():
    """`dupes.triage` が `actionable` に入れる組（予約 + 予約）を1組つくる。"""
    def _v(vid):
        return {"id": vid,
                "snippet": {"title": "手取りは35万9318円",
                            "description": "本文\n[t:a1]",
                            "publishedAt": "2026-08-25T00:00:00Z"},
                "status": {"privacyStatus": "private",
                           "publishAt": "2026-08-25T00:00:00Z"}}
    return [_v("v1"), _v("v2")], {"a1": "tedori"}


def test_dupesの一覧が実際に畳まれる(tmp_path, monkeypatch, capsys):
    """**繋がっていることを実物で見ます。**
    `src/alerts.py` の検査だけだと、`dupes.report` が `ring` を
    呼んでいなくても全部緑のままです（「足した検査は0件でも通る」）。"""
    from src import dupes

    videos, topics = _dupes_videos()
    monkeypatch.setattr(alerts, "LEDGER", tmp_path / "a.jsonl")
    monkeypatch.setattr(alerts, "RUNS", tmp_path / "r.jsonl")
    _write(tmp_path / "r.jsonl", [])

    # まだ鳴っていないので全文が出る
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID", "cse_first")
    dupes.report(videos, topics)
    assert "（片方を外すこと）" in capsys.readouterr().out

    # しきい値まで鳴らすと、機械のほうから畳む
    _write(tmp_path / "a.jsonl", _ring_rows("dupes_actionable", alerts.FOLD_AFTER))
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID", "cse_later")
    dupes.report(videos, topics)
    out = capsys.readouterr().out
    assert "（片方を外すこと）" not in out
    assert "畳んでいます" in out and "dupes_actionable" in out

    # **当たりを入れれば、次の回からまた全文で出る**（故障注入の逆向き）
    _write(tmp_path / "r.jsonl", [
        {"at": "2026-08-16T23:00:00+09:00", "kind": "ship",
         "closes": ["dupes_actionable"]},
    ])
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID", "cse_after_act")
    dupes.report(videos, topics)
    assert "（片方を外すこと）" in capsys.readouterr().out


# --- 検査が本物の台帳に書かないこと（2026-08-17 に踏んで足した）-----------------
#
# `status_lines` は 8回鳴って当たり0で畳まれ、`status.py` の表にもそう出ていました。
# 実物を `data/status_lines.jsonl` と突き合わせると、**本物の鳴りは1回だけ**
# （16:31。出力が 216→800行に伸びた回）で、**残り7回は `pytest`** です。
# `_dedupe_token()` はセッションIDなので、1周につき1行きっかり積まれていました。
#
#     当たり率という計器が、測っていたのは **検査の実行回数** でした。
#
# しかも8回目で畳まれた瞬間、**その畳みを見にいく検査が赤くなります。**
# 放っておくと、次の子は毎回**赤い pytest で始まります。**
#
# 塞ぎは `tests/conftest.py`（全部の検査に自動で掛かる）。
# **呼ぶ側に「検査では ledger= を渡す」を約束させないこと** ——
# 一覧を足した回が必ず片方だけ忘れます（通算7回踏んだ形）。


def test_検査の中では本物の台帳を触らない():
    """**これが本体。** `conftest.py` が効いていれば、書き先は repo の外。"""
    from src import alerts

    real = alerts.ROOT / "data" / "alerts.jsonl"
    assert alerts.LEDGER != real, "検査が data/alerts.jsonl に書いています"
    assert alerts.RUNS != alerts.ROOT / "data" / "runs.jsonl"


def test_鳴らしても本物の台帳の行数が増えない():
    """**属性を見るだけでは足りません**（差し替え漏れは実際に書いて分かる）。"""
    from src import alerts

    real = alerts.ROOT / "data" / "alerts.jsonl"
    before = real.read_text(encoding="utf-8") if real.exists() else ""
    alerts.ring("検査用のにせの鍵", 3)
    after = real.read_text(encoding="utf-8") if real.exists() else ""
    assert before == after, "検査が本物の台帳を書き換えました"


def test_故障注入_差し替えを外すと本物を指す():
    """**壊れていたときの姿**を検査が名指しで持っていること。

    環境変数も属性も無ければ、`alerts` は repo の `data/` を指します ——
    **それが7回ぶんの偽の点を積んだ経路**です。
    """
    import importlib
    import os

    from src import alerts as a

    keep = {k: os.environ.pop(k, None) for k in ("YT_ALERTS_LEDGER", "YT_ALERTS_RUNS")}
    try:
        fresh = importlib.reload(a)
        assert fresh.LEDGER == fresh.ROOT / "data" / "alerts.jsonl"
    finally:
        for k, v in keep.items():
            if v is not None:
                os.environ[k] = v
        importlib.reload(a)
        a.LEDGER = Path(os.environ["YT_ALERTS_LEDGER"])
        a.RUNS = Path(os.environ["YT_ALERTS_RUNS"])
