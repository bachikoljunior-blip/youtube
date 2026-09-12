"""**音の側の答え（`hear.tail_voice` / `head_voice`）の `分けられない` の連を見張る**
（2026-09-13 01:5x JST・optimizer・Opus）。

註と derivation は `studio/trend.py` の `voice_runs`。要点だけ:
`tail_voice` の覆る条件は「**`分けられない` が 3本 続けて出るなら、閾（0.2／0.4秒）が
音の実物と合っていない**」だが、**その連を数える口が無かった**（族の 10例目）。
答えそのものは `cli.cmd_hear` が 09/09 から台帳へ積んでいる ＝ **読む物だけが無かった**側。

**単位は「本」** —— 同じ本を 1周 に 5回 聞き直す回が在るので、行で数えると連が甘くなる。
"""
import json
import pathlib

from studio import hear, trend

LEDGER = pathlib.Path(__file__).resolve().parents[1] / "data" / "studio" / "ledger.jsonl"


def _rows() -> list[dict]:
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]


def _heard(book: str, at: str, voice: dict | None = None,
           head_voice: dict | None = None) -> dict:
    return {"event": "heard", "id": book, "at": at,
            "voice": voice or {}, "head_voice": head_voice or {}}


def test_本物の台帳で連が数えられること() -> None:
    r = trend.voice_runs(_rows())
    assert r["spoke"], "音の側が答えた本が 0本 —— `cli.cmd_hear` が `voice` を積んでいない側を疑うこと"
    assert 0 <= r["run"] <= r["need"]
    assert r["drawn"] == (r["run"] >= r["need"])
    # **判定した実物を返り値に残す**（§5 教訓の形 4つ目）—— 次の回が列挙で確かめられる
    assert r["books"] and all(
        set(b) >= {"id", "n", "present", "absent", "unsure"} for b in r["books"])
    # 本の並びは `id` の日付（台帳の刻ではない —— 前の本を後から聞き直す周が在る）
    ids = [str(b["id"]) for b in r["books"]]
    assert ids == sorted(ids, reverse=True), ids
    # 内訳の合計が答えの数と合うこと（取りこぼした語が無いこと）
    for b in r["books"]:
        assert b["n"] == b["present"] + b["absent"] + b["unsure"], b


def test_単位は本_同じ本の聞き直しで連を数えないこと() -> None:
    """**行で数えると連が甘くなる**（`voice_runs` の註）。同じ本の 3行 は連 1 まで。"""
    rows = [_heard("2026-09-20-a", "2026-09-20T01:00:00+09:00", {"3": "分けられない"}),
            _heard("2026-09-20-a", "2026-09-20T02:00:00+09:00", {"3": "分けられない"}),
            _heard("2026-09-20-a", "2026-09-20T03:00:00+09:00", {"4": "分けられない"})]
    r = trend.voice_runs(rows)
    assert r["run"] == 1, r
    assert not r["drawn"]


def test_音の側が答えなかった本は連を伸ばしも切りもしないこと() -> None:
    """`tail_voice` は末尾に差の出たコマでしか撃たれない ＝ 答えの無い本は証拠ではない。"""
    rows = [_heard("2026-09-18-a", "2026-09-18T01:00:00+09:00", {"1": "分けられない"}),
            _heard("2026-09-19-b", "2026-09-19T01:00:00+09:00"),          # 1度も答えていない本
            _heard("2026-09-20-c", "2026-09-20T01:00:00+09:00", {"1": "分けられない"})]
    r = trend.voice_runs(rows)
    assert r["run"] == 2 and r["silent"] == 1 and r["spoke"] == 2, r


def test_陽性対照_3本続けば門に届き_1本混ざれば切れること() -> None:
    """**壊したら落ちるまで撃つ**（§5 教訓の形 3つ目）。"""
    def mk(third: str) -> list[dict]:
        return [_heard("2026-09-18-a", "2026-09-18T01:00:00+09:00", {"1": third}),
                _heard("2026-09-19-b", "2026-09-19T01:00:00+09:00", {"1": "分けられない"}),
                _heard("2026-09-20-c", "2026-09-20T01:00:00+09:00", {"1": "分けられない"})]
    got = trend.voice_runs(mk("分けられない"))
    assert got["run"] == 3 and got["drawn"], got
    cut = trend.voice_runs(mk("音は在る"))
    assert cut["run"] == 2 and not cut["drawn"], cut


def test_頭と末尾は同じ連に入ること() -> None:
    """閾は頭と末尾で同じ（`hear.voice_verdict`）＝ 連を 2つ に割らない。"""
    rows = [_heard("2026-09-20-a", "2026-09-20T01:00:00+09:00",
                   head_voice={"2": "分けられない"})]
    assert trend.voice_runs(rows)["run"] == 1
    # 閾そのものは `hear` の 1か所（`voice_runs` の覆る条件 (1)）
    assert hear.voice_verdict(hear.VOICE_GAP_PRESENT) == "音は在る"
    assert hear.voice_verdict(hear.VOICE_GAP_ABSENT - 0.01) == "音が無い"
    assert hear.voice_verdict((hear.VOICE_GAP_ABSENT + hear.VOICE_GAP_PRESENT) / 2) == "分けられない"


def test_門は註の数と同じ場所から来ること() -> None:
    """**門を 2か所 に置かない**（`voice_runs` の覆る条件 (1) と同じ向き）。"""
    r = trend.voice_runs(_rows())
    assert r["need"] == r["gate"] == trend.VOICE_UNSURE_NEED == 3


def test_印字は連と単位を言うこと() -> None:
    """**註ではなく印字が読まれる**（§5 教訓の形 7つ目）。"""
    line = trend.voice_line(_rows())
    assert "分けられない` の連" in line and "単位は「本」" in line
    assert "`trend.voice_runs`" in line
    r = trend.voice_runs(_rows())
    assert f"{r['run']}/{r['need']}本" in line
    assert ("門に届きました" in line) == bool(r["drawn"])


def test_答えた本が無ければ_0を音が無いと読ませないこと() -> None:
    line = trend.voice_line([_heard("2026-09-20-a", "2026-09-20T01:00:00+09:00")])
    assert "答えた本 0本" in line and "「音が無い」ではなく" in line
