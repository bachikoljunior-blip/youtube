"""親が起きて決めたことを、GO でも WAIT でも1行 残す（`scripts/next_round.log_wake`）。

**なぜ要るか**（2026-09-08 17:0x JST・optimizer・Opus が実測して足した）:
`data/rounds.jsonl` に載るのは **GO で立てた周だけ**なので、**周が立たなかった時間は
あとから読むと 3つ が同じ顔をする** —— (1) 間隔の途中で待った（設計どおり）／
(2) サブが走っているので待った（サブが詰まっている）／(3) そもそも起きなかった（心拍の壊れ）。

実測 2026-09-08: **08:41 → 14:59 JST に 378分 の穴**（前後は 119〜124分 の等間隔）。
`list_triggers` の `last_fired_at` は 16:59 JST ＝ cron は毎時 撃てており、
親は穴の中で生きていた（12:41 JST に commit を押している）。**それでも (1) と (2) を分けられなかった。**
分けるのに要るのは新しい判断ではなく、**決めたことを残すこと**だけ。
"""
import json

from scripts import next_round


def _read(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _use(tmp_path, monkeypatch):
    p = tmp_path / "parent_wakes.jsonl"
    monkeypatch.setattr(next_round, "WAKES", p)
    return p


def test_GOを残す(tmp_path, monkeypatch):
    p = _use(tmp_path, monkeypatch)
    next_round.log_wake({"go": True, "live": 0, "live_source": "--live",
                         "wait_min": 0, "roles": ["hourly", "optimizer"], "why": "間隔が明けた"})
    (row,) = _read(p)
    assert row["go"] is True and row["roles"] == ["hourly", "optimizer"]


def test_WAITも残す_これが本題(tmp_path, monkeypatch):
    """**GO だけ残すと、立たなかった時間が読めない** —— それが 378分 の穴で起きたこと。"""
    p = _use(tmp_path, monkeypatch)
    next_round.log_wake({"go": False, "live": 0, "live_source": "--live",
                         "wait_min": 77.0, "roles": [], "why": "間隔の途中"})
    (row,) = _read(p)
    assert row["go"] is False and row["wait_min"] == 77.0


def test_サブが走っている待ちと間隔の待ちを見分けられる(tmp_path, monkeypatch):
    """(1) と (2) を分けるのが、この台帳の全部の仕事。`live` がその1つの列。"""
    p = _use(tmp_path, monkeypatch)
    next_round.log_wake({"go": False, "live": 2, "live_source": "list_sessions",
                         "wait_min": 30.0, "roles": [], "why": "二重に立てないため"})
    next_round.log_wake({"go": False, "live": 0, "live_source": "--live",
                         "wait_min": 30.0, "roles": [], "why": "間隔の途中"})
    busy, idle = _read(p)
    assert busy["live"] == 2 and idle["live"] == 0


def test_足していく_前の行を消さない(tmp_path, monkeypatch):
    """穴は「行が無い」ことで読むので、上書きすると穴と区別がつかなくなる。"""
    p = _use(tmp_path, monkeypatch)
    for _ in range(3):
        next_round.log_wake({"go": False, "live": 0, "wait_min": 1, "roles": [], "why": "x"})
    assert len(_read(p)) == 3


def test_書けなくても周を止めない(tmp_path, monkeypatch):
    """**止める仕掛けを足さないこと**（`CLAUDE.md`）。記録は周より軽い。"""
    monkeypatch.setattr(next_round, "WAKES", tmp_path / "no" / "such" / "dir" / "x.jsonl")
    monkeypatch.setattr(next_round.Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("読み取り専用")))
    assert next_round.log_wake({"go": True, "live": 0, "wait_min": 0, "roles": [], "why": "x"})


def test_決めたところで撃たれている():
    """`decide()` の答えを印字する所と同じ流れで呼ぶこと ——
    **親が「記録して」と言われて覚えている形にはしない**（覚えていないと残らない形は 08-24 に踏んだ）。"""
    src = (next_round.ROOT / "scripts" / "next_round.py").read_text(encoding="utf-8")
    body = src[src.index("走っているサブ: **"):]
    # **註やコメントの中の文字列に当てないこと** —— 最初に書いたとき `log_wake(d)` を
    # 素で探しており、`#log_wake(d)` に潰しても検査が通った（陽性対照で捕まえた）。
    called = [l for l in body[:400].splitlines() if l.strip().startswith("log_wake(d)")]
    assert called, "decide() の答えの直後で呼ばれていない（コメントアウトも含めて見ている）"


def test_検査からは本物の控えへ書かない():
    """**足した回自身が踏んだ穴**（2026-09-08 17:2x）——
    `python -m pytest tests/` を撃っただけで、`main()` を呼ぶ既存の検査から
    本物の `data/parent_wakes.jsonl` に 2行 入った。§8 の
    「検査を撃つことに副作用が付いていた」（`niche_ceiling.kick()`）と同じ形で、
    **穴を読むための台帳に、親が起きていない行が混ざる** ＝ 台帳の意味が壊れる。
    差し替えた検査（`WAKES` を tmp に向けた回）は書いてよい —— 上の5件がそれ。
    """
    real = next_round.WAKES
    before = real.read_text(encoding="utf-8") if real.exists() else ""
    next_round.log_wake({"go": True, "live": 0, "wait_min": 0, "roles": ["hourly"], "why": "x"})
    after = real.read_text(encoding="utf-8") if real.exists() else ""
    assert after == before, "検査から本物の控えへ書いている"


def test_誰が撃ったかを残す(tmp_path, monkeypatch):
    """**親か、手で撃ったか。** 親は必ず `next_round_owner.py` を通す（`docs/trigger_parent.md` 第1節）。
    これが無いと、道具を確かめただけの回が「親が起きて待った」に化ける ——
    **足した回自身が、押す直前の動作確認で本物の控えに 1行 入れて気づいた**（2026-09-08 17:3x）。
    穴を読むときは `who == "owner"` の行だけ数えること。
    """
    import sys
    p = _use(tmp_path, monkeypatch)
    monkeypatch.delitem(sys.modules, "scripts.next_round_owner", raising=False)
    monkeypatch.setattr(sys, "argv", ["scripts/next_round.py", "--live", "0"])
    next_round.log_wake({"go": False, "live": 0, "wait_min": 5, "roles": [], "why": "x"})
    monkeypatch.setitem(sys.modules, "scripts.next_round_owner", object())
    next_round.log_wake({"go": True, "live": 0, "wait_min": 0, "roles": ["hourly"], "why": "y"})
    hand, parent = _read(p)
    assert hand["who"] == "direct", hand
    assert parent["who"] == "owner", parent


def test_親は直に走らせるのでargvも見る(tmp_path, monkeypatch):
    """**`sys.modules` だけでは足りない**（同じ回に撃って分かった）——
    親は `python scripts/next_round_owner.py` と直に走らせるので、あれは `__main__` に入り、
    `scripts.next_round_owner` という名前では載らない。実測: 本物の呼びが `direct` と出た。"""
    import sys
    p = _use(tmp_path, monkeypatch)
    monkeypatch.delitem(sys.modules, "scripts.next_round_owner", raising=False)
    monkeypatch.setattr(sys, "argv", ["scripts/next_round_owner.py", "--live", "2"])
    next_round.log_wake({"go": False, "live": 2, "wait_min": 9, "roles": [], "why": "z"})
    (row,) = _read(p)
    assert row["who"] == "owner", row
