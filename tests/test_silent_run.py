"""**repo に1行も残さずに終わった回**を、`list_sessions` の返りから見つける。

2026-08-17 04:1x の子は `sources` を渡されずに立ち、`/home/user/youtube` が
存在しないまま終わりました。その回は:

- `run_marker.py --write` を打てない（repo が無い）
- `inbox.py --open` も押せない（commit + push で残す道具なので）
- 日誌も書けない → **`retro.py` は構造上拾えません**

**残った経路は `set_session_title` だけ**でした。ところが §2 は
`sessions_compact.py` で題名を落とすと決めているので、**唯一生き残る経路を
こちらの手順が捨てていた**ことになります。

だから題名を写させるのではなく、**「題名を読みにいくべき回がある」**とだけ言います。
材料は既に手元にあります —— `list_sessions` の一覧と `data/runs.jsonl` の印。

**故障注入つき**（この検査が本当に効いているかを、両向きで見る）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker                                            # noqa: E402
import sibling_check                                          # noqa: E402


ME = "session_me"
NOW = "2026-08-17T05:10:53.000000Z"


def _sess(sid, born, *, status="SESSION_STATUS_ARCHIVED", tags=(sibling_check.TAG,)):
    return {"id": sid, "created_at": born, "session_status": status, "tags": list(tags)}


@pytest.fixture
def marks(tmp_path, monkeypatch):
    """`data/runs.jsonl` を差し替える。**実物を書き換えないこと。**"""
    path = tmp_path / "runs.jsonl"
    monkeypatch.setattr(run_marker, "MARKS", path)
    monkeypatch.setattr(run_marker, "PARENT_SESSIONS", {"session_parent"})

    def write(rows):
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8")
    return write


def test_印の無い回が見つかる(marks):
    marks([{"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"}])
    sessions = [
        _sess(ME, NOW, status="SESSION_STATUS_RUNNING"),
        _sess("session_ok", "2026-08-17T00:13:21.000000Z"),
        _sess("session_silent", "2026-08-17T04:11:50.000000Z"),
    ]
    found = sibling_check.silent_runs(sessions, ME)
    assert [s["id"] for s in found] == ["session_silent"]


def test_故障注入_印を足すと消える(marks):
    """**当たりの側でだけ鳴らない**形になっていないか（両向きで見る）。"""
    sessions = [
        _sess(ME, NOW, status="SESSION_STATUS_RUNNING"),
        _sess("session_silent", "2026-08-17T04:11:50.000000Z"),
    ]
    marks([{"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"}])
    assert sibling_check.silent_runs(sessions, ME), "印が無いのに鳴っていません"

    marks([
        {"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"},
        {"at": "2026-08-17T13:12:00+09:00", "session": "session_silent", "kind": "start"},
    ])
    assert not sibling_check.silent_runs(sessions, ME), "印があるのに鳴っています"


def test_親と自分とタグ違いは数えない(marks):
    marks([{"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"}])
    sessions = [
        _sess(ME, NOW, status="SESSION_STATUS_RUNNING"),        # 自分
        _sess("session_parent", "2026-08-17T04:00:00.000000Z"),  # 常駐の親
        _sess("session_other", "2026-08-17T04:00:00.000000Z", tags=("etaloop",)),
        _sess("session_ok", "2026-08-17T00:13:21.000000Z"),
    ]
    assert sibling_check.silent_runs(sessions, ME) == []


def test_生きている回はまだ打つかもしれない(marks):
    marks([{"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"}])
    sessions = [
        _sess(ME, NOW, status="SESSION_STATUS_RUNNING"),
        _sess("session_live", "2026-08-17T05:00:00.000000Z",
              status="SESSION_STATUS_RUNNING"),
    ]
    assert sibling_check.silent_runs(sessions, ME) == []


def test_印の記録より古い回は_覚えていないだけ(marks):
    """`data/runs.jsonl` は直近500行しか持ちません。

    それより前のセッションは「印が無い」ではなく **「もう覚えていない」**です。
    ここを区別しないと、一覧が古いセッションで埋まって
    **当たりを含まないまま育ちます**（`src/alerts.py` が4回踏んだ形）。
    """
    marks([{"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"}])
    sessions = [
        _sess(ME, NOW, status="SESSION_STATUS_RUNNING"),
        _sess("session_ancient", "2026-08-10T01:00:00.000000Z"),   # 印より前
    ]
    assert sibling_check.silent_runs(sessions, ME) == []


def test_印が1件も無いときは黙る(marks):
    """印そのものが読めない回で鳴らすと、**全員が容疑者**になります。"""
    marks([])
    sessions = [_sess("session_silent", "2026-08-17T04:11:50.000000Z")]
    assert sibling_check.silent_runs(sessions, ME) == []


def test_出力が題名を読めと言う(marks, capsys, monkeypatch, tmp_path):
    """件数だけでは何も伝わりません。**次の1手が書いてあること。**"""
    monkeypatch.setattr("src.alerts.LEDGER", tmp_path / "alerts.jsonl")
    marks([{"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"}])
    sessions = [
        _sess(ME, NOW, status="SESSION_STATUS_RUNNING"),
        _sess("session_silent", "2026-08-17T04:11:50.000000Z"),
    ]
    sibling_check.report_silent(sessions, ME)
    out = capsys.readouterr().out
    assert "session_silent" in out
    assert "title" in out, "**題名を読め**と言っていません（唯一の経路なのに）"
    assert "inbox.py --open" in out, "受け取り帳へ落とす手が書かれていません"


def test_実物の返りでも例外を投げない():
    """**実データ。** 形が変わっても落ちないこと（落ちると §2 が止まります）。"""
    assert sibling_check.silent_runs([], None) == []


def test_受け取り帳に入っている回は二度と名指ししない(marks, tmp_path, monkeypatch):
    """**入れた回に自分で踏みました。**

    名指しは `list_sessions` の窓（25件）が持っているあいだ**毎回鳴ります。**
    受け取り帳へ落としても消えないので、**次の子が同じ題名をもう一度 `--open`** し、
    同じ依頼が二重に開きます。印の代わりになるのは受け取り帳の本文で、
    §0 が「題名を `inbox.py --open` に落とせ」と言うので**IDが本文に入ります。**
    """
    marks([{"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"}])
    sessions = [
        _sess(ME, NOW, status="SESSION_STATUS_RUNNING"),
        _sess("session_silent", "2026-08-17T04:11:50.000000Z"),
    ]
    inbox = ROOT / "data" / "inbox.jsonl"
    assert sibling_check.silent_runs(sessions, ME), "落とす前から黙っています"

    monkeypatch.setattr(Path, "read_text", Path.read_text)   # 実物は触らない
    box = tmp_path / "inbox.jsonl"
    box.write_text('{"kind":"open","text":"前の回 session_silent の題名"}\n',
                   encoding="utf-8")
    real = Path.read_text

    def fake(self, *a, **kw):
        return box.read_text(encoding="utf-8") if self == inbox else real(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", fake)
    assert sibling_check.silent_runs(sessions, ME) == [], "落とした後も鳴っています"


# ---------------------------------------------------------------------------
# **同じ「印ゼロ」に、やることが正反対の落ち方が2つある**（2026-08-17 23:2x に足した）
#
# `session_01JBEBXm3FijEVuXTFeynLAU` は `sources` を渡されて立ったのに、
# **1ターン目で `API Error: 529 Overloaded` に当たって死にました**（出力2行・push なし）。
# 印はゼロなので `silent_runs` は正しく名指ししますが、**言う中身が間違っていました** ——
# 「`sources` が渡らなかった疑い ＝ 題名を読め」。
# その回の題名は **§6 (d) に届いていないので既定のまま**（中身ゼロ）です。
# ---------------------------------------------------------------------------

def _adv(*endings):
    found = [{"id": f"session_{i}", "created_at": NOW, "ending": e}
             for i, e in enumerate(endings)]
    return "\n".join(sibling_check.silent_advice(found))


def test_apifail_の回には題名を読みにいかせない():
    """**拾えないものを拾わせないのが、ここの仕事です。**

    読ませると、次の子は中身ゼロの既定題名を「申し送り」として受け取り帳に落とし、
    **さらに次の回がそれを閉じる仕事をします**（空の依頼が1件ふえるだけ）。
    """
    got = _adv("apifail")
    assert "拾い直すものがありません" in got
    assert "`inbox.py --open` に落とさないこと" in got
    assert "title` を読むこと" not in got, "題名を読みにいかせています"


def test_nosrc_の回には題名を読ませる():
    """**こちらは題名だけが記録です**（2026-08-17 04:1x）。両向きで見ること。"""
    got = _adv("nosrc")
    assert "`title` を読むこと" in got
    assert "inbox.py --open" in got
    assert "拾い直すものがありません" not in got


def test_落ち方が混ざったら両方言う():
    """1件が `apifail` でも、**もう1件の `nosrc` を黙らせないこと。**"""
    got = _adv("apifail", "nosrc")
    assert "`title` を読むこと" in got
    assert "拾い直すものがありません" in got


def test_落ち方が書かれていなければ_見る場所を言う():
    """**書かれていないことを「repo が無かった」と断定しないこと**（直す前はしていた）。"""
    got = _adv(None)
    assert "落ち方が書かれていません" in got
    assert "post_turn_summary" in got and "sources" in got


def test_名指しの行に落ち方が出る(marks):
    """一覧の行そのものにも出ること（`silent_advice` だけ直しても片効きになる）。"""
    marks([{"at": "2026-08-17T09:00:00+09:00", "session": "session_ok", "kind": "start"}])
    dead = _sess("session_dead", "2026-08-17T14:02:13.000000Z")
    dead["ending"] = "apifail"
    found = sibling_check.silent_runs(
        [_sess(ME, NOW, status="SESSION_STATUS_RUNNING"), dead], ME)
    assert found and found[0].get("ending") == "apifail"
    assert "API 一時失敗" in sibling_check.ENDING_LABEL["apifail"]
