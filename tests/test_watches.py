"""`src/watches.py` と `config/watches.yaml` の検査。

**この検査の本体は最後の1件（`test_待ちを印字するファイルは台帳にあるか`）です。**
残りは台帳そのものが壊れていないことを見ています。

2026-08-20 に踏んだ壊れ方はこうでした ——
`scripts/retention.py` が「30秒設計の3本が出れば測れるようになります」と印字し、
**その3本は出たのに、10日間だれも気づかなかった。**
待ちを書いた回と、条件が満ちる回は別の回なので、**印字では繋がりません。**
だから「まだ判定できません」と印字するファイルは、
**台帳に載るか、載せない理由を書くか**のどちらかを強制します。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import watches  # noqa: E402


#: 「いまは測れない」と読める印字。**待ちがあるという合図。**
GATE_PHRASES = ("判定できません", "まだ判定しない", "測れるようになります",
                "検定は今回効きません")


def _registry():
    return watches.load()


def test_台帳が読めてidが重複していない():
    ws = _registry()
    assert ws, "待ちが1件もありません"
    ids = [w.id for w in ws]
    assert len(ids) == len(set(ids)), f"idが重複しています: {ids}"


@pytest.mark.parametrize("field", ["what", "cond", "then", "source"])
def test_どの待ちも空欄がない(field):
    for w in _registry():
        assert getattr(w, field).strip(), f"{w.id} の {field} が空です"


def test_どの待ちも実装のある種類を指している():
    for w in _registry():
        assert w.kind in watches.KINDS, f"{w.id} の kind `{w.kind}` に実装がありません"


def test_どの待ちも実際に評価できる():
    """**計器が落ちても回は止めない。ただし黙らない。**

    手元の材料が欠けている回は `err` に理由が入ります（例外は投げません）。
    ここで見るのは「例外で落ちないこと」と「数が入っていること」です。
    """
    for w in _registry():
        g = w.gauge()
        assert isinstance(g, watches.Gauge)
        assert g.need > 0, f"{w.id} の need が 0 です（満ちる条件になりません）"


def test_満ちて答えの無い待ちは大きく鳴る():
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    out = watches.render([w])
    assert "満ちました" in out and "何かする" in out
    assert "answered" in out, "答えの書き方が画面に出ていません"


def test_満ちて答えのある待ちは1行に畳む():
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0},
                      answered="2026-08-20 判定済み")
    out = watches.render([w])
    assert "満ちました" not in out
    assert "済 試験: 2026-08-20 判定済み" in out


def test_まだの待ちは残りを数で出す():
    w = watches.Watch(id="試験", what="試し", cond="巨大", then="何かする",
                      source="tests", kind="length_spread", params={"need": 99.0})
    out = watches.render([w])
    assert "あと" in out and "99" in out


def test_読めない待ちも節を落とさない():
    w = watches.Watch(id="試験", what="試し", cond="?", then="?", source="tests",
                      kind="存在しない種類", params={})
    out = watches.render([w])
    assert "読めません" in out and "試験" in out


def _flagged() -> dict[str, list[str]]:
    """「いまは測れない」と**印字している**ファイルを拾う（註釈は除く）。"""
    out: dict[str, list[str]] = {}
    for path in sorted(list((ROOT / "scripts").glob("*.py"))
                       + list((ROOT / "src").rglob("*.py"))):
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("#") or not re.search(r"[\"']", line):
                continue
            if any(p in line for p in GATE_PHRASES):
                out.setdefault(str(path.relative_to(ROOT)), []).append(s[:70])
    return out


def test_待ちを印字するファイルは台帳にあるか免除に理由がある():
    """**この検査が、同じ壊れ方を二度させないための本体です。**

    新しく「まだ判定できません」と印字する道具を書くと、ここが落ちます。
    直し方は2つだけ:

        1. `config/watches.yaml` の `watches:` に、満ちる条件を**数で**足す
        2. 待ちではないなら `exempt:` に**理由**を書く（黙って外せません）
    """
    sources = {w.source for w in _registry()}
    allowed = watches.exempt()
    missing = {f: ls for f, ls in _flagged().items()
               if f not in sources and f not in allowed}
    assert not missing, (
        "「いまは測れない」と印字しているのに、待ちの台帳にありません:\n"
        + "\n".join(f"  {f}: {ls[0]}" for f, ls in missing.items())
        + "\n  → config/watches.yaml の watches: に数で足すか、exempt: に理由を書くこと"
    )


def test_免除には理由が書いてある():
    for path, why in watches.exempt().items():
        assert len(why.strip()) >= 20, f"{path} の免除に理由がありません"
        assert (ROOT / path).exists(), f"{path} はもうありません（免除も消すこと）"


# --------------------------------------------------- 仮説の側から見張る（穴C）
#
# **印字を見張るだけでは足りません**（2026-08-20 に足した）。
# 待ちが次に書かれる場所は、道具の print ではなく
# `config/hypotheses.yaml` の `falsified_if` です。そこには
# 「3,000再生に達した時点で」「6本たまった時点で」のような**数の門**が入ります。
# **門を書いたのに台帳に載せないと、満ちたことは誰にも届きません。**

#: `falsified_if` に「いつ測れるようになるか」が書いてある印。
GATE_IN_YAML = re.compile(
    r"(達した時点|たまった時点|溜まった時点|貯まった時点|満たなければ|"
    r"届いていなければ|届かなければ)")


def _open_hypotheses():
    import yaml

    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    return [h for h in doc.get("hypotheses", []) if not h.get("verdict")]


def test_数の門を持つ未判定の仮説は台帳を指している():
    """**門を書いたら、見張る先も書く。** 直し方は `watch:` を1行足すだけ。"""
    ids = {w.id for w in _registry()}
    bad = []
    for h in _open_hypotheses():
        if not GATE_IN_YAML.search(str(h.get("falsified_if", ""))):
            continue
        w = h.get("watch")
        if not w:
            bad.append(f"{h.get('deadline')} {str(h.get('claim'))[:34]} → watch: が無い")
        elif w not in ids:
            bad.append(f"{h.get('deadline')} {str(h.get('claim'))[:34]} → watch: {w} は台帳に無い")
    assert not bad, (
        "数の門を書いた未判定の仮説が、待ちの台帳を指していません:\n  "
        + "\n  ".join(bad)
        + "\n  → config/watches.yaml に待ちを足し、仮説に watch: <id> を書くこと")


def test_台帳が指されている仮説は判定済みでも壊れない():
    """判定が書かれた項の `watch:` は、あってもなくてもよい（消し忘れで落とさない）。"""
    ids = {w.id for w in _registry()}
    for h in _open_hypotheses():
        w = h.get("watch")
        assert w is None or w in ids


# --------------------------------------------------- 鳴り続けを数える（穴B）

def test_鳴った回を積んで回数を出す(tmp_path):
    ledger = tmp_path / "rings.jsonl"
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    old = watches.RINGS
    try:
        watches.RINGS = ledger
        watches.note_rings([w], at="2026-08-20T10:00:00+09:00")
        watches.note_rings([w], at="2026-08-20T11:00:00+09:00")
        hist = watches.ring_history(ledger)
        assert hist["試験"][0] == 2
        assert hist["試験"][1].startswith("2026-08-20T10")
        out = watches.render([w])
        assert "2回鳴っています" in out, "放置の長さが画面に出ていません"
    finally:
        watches.RINGS = old


def test_答えを書いた待ちは鳴らない():
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0},
                      answered="2026-08-20 判定済み")
    assert watches.unanswered([w]) == []


def test_満ちて答えの無い待ちはunansweredに出る():
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    assert [x.id for x in watches.unanswered([w])] == ["試験"]


def test_記録しないのが既定():
    """検査や下見で `render` を呼んでも、帳面を汚さないこと。"""
    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    before = watches.RINGS.read_text(encoding="utf-8") if watches.RINGS.exists() else ""
    watches.render([w])
    after = watches.RINGS.read_text(encoding="utf-8") if watches.RINGS.exists() else ""
    assert before == after


# --- 尺は後ろの一枚から補う（2026-08-21 03:0x）------------------------------------

def test_尺の空いた一枚が積まれても_後ろから補う(tmp_path, monkeypatch):
    """Data API の日枠が切れた回の走査は、**尺の欄が丸ごと空**で積まれます。

    最後の一枚をそのまま採ると、尺を読む待ちが全部「読めません」に落ちます。
    実測: 8/20 23:52 の一枚は 29本ぶんの尺つき、01:3x の一枚は 0本 ——
    **在るのに読んでいないだけ**で、しかも Data API の枠が戻る JST 16:00 まで
    毎日その時間帯に必ず起きます。
    """
    import json as _json

    scan = tmp_path / "scan.jsonl"
    good = {"at": "2026-08-20T23:52:01+09:00",
            "values": {"動画.aaa.尺": 29, "動画.aaa.views": 100,
                       "動画.bbb.尺": 31, "動画.bbb.views": 200}}
    # Data API が 403 の回: Analytics の指標だけ・尺は1本も無い
    degraded = {"at": "2026-08-21T01:36:16+09:00",
                "values": {"動画.aaa.views": 111, "動画.bbb.views": 222}}
    scan.write_text(_json.dumps(good) + "\n" + _json.dumps(degraded) + "\n",
                    encoding="utf-8")
    monkeypatch.setattr(watches, "SCAN", scan)

    rows = watches._last_scan()
    # **動く数は新しい一枚のまま**（古いほうを混ぜない）
    assert rows["aaa"]["views"] == 111 and rows["bbb"]["views"] == 222
    # **尺だけ補う**
    assert rows["aaa"]["尺"] == 29 and rows["bbb"]["尺"] == 31

    w = watches.Watch(id="試験", what="試し", cond="0以上", then="何かする",
                      source="tests", kind="length_spread", params={"need": 0.0})
    assert "満ちました" in watches.render([w])


def test_新しい一枚に居ない本は_呼び戻さない(tmp_path, monkeypatch):
    """補うのは尺だけで、**消えた本まで戻さない**こと。"""
    import json as _json

    scan = tmp_path / "scan.jsonl"
    good = {"at": "1", "values": {"動画.aaa.尺": 29, "動画.zzz.尺": 40,
                                  "動画.aaa.views": 1, "動画.zzz.views": 2}}
    degraded = {"at": "2", "values": {"動画.aaa.views": 9}}
    scan.write_text(_json.dumps(good) + "\n" + _json.dumps(degraded) + "\n",
                    encoding="utf-8")
    monkeypatch.setattr(watches, "SCAN", scan)
    rows = watches._last_scan()
    assert set(rows) == {"aaa"}
    assert rows["aaa"]["尺"] == 29


# --- 2026-08-26 夜（最適化の回）に足した「満ちた ≠ 判定できる」の検査 ---
#
# `config/watches.yaml` の「深い題のショート-16本」には、こう書いてあった:
#
#     **数え方は仮説の `needs.count_expr` と同じ**にしてあります。
#     片方だけ直すと、鳴る日と判定できる日がずれます。
#
# **その日のうちに、片方だけが直った。** きょうだいの回が `needs` を
# 「作った16本」→「公開して分類が付いた8本 ＋ 使える日3日」に直し、
# `_k_deep_shorts`（作った本を数える）はそのままだった。結果:
#
#     deadline_check.py   「[..] まだ数えはじめたところ。**何もしないのが正解**」
#     drift.py --gate     exit 2 →「**この回は verdict を出すこと**」
#     watches --pending   「**満ちました。この回で判定すること**」（3回まで止める）
#
# **数え方を写し直すのは、同じ事故をもう一度 予約すること。**
# だから「判定できるか」の答えは `deadline_check` の1か所に訊く。
# 下の検査は、その配線が両向きに効いていることを縛る。


def _w(wid="試験"):
    return watches.Watch(id=wid, what="試し", cond="0以上", then="何かする",
                         source="config/hypotheses.yaml", kind="length_spread",
                         params={"need": 0.0})


def test_仮説がまだ判定できない待ちは鳴らさない(monkeypatch):
    """`deadline_check` が `warming` と言う待ちは、目盛りが満ちても鳴らさない。

    **その回にできることが1つも無いので、止めても損しかしない。**
    """
    monkeypatch.setattr(watches, "_hypothesis_judge_state",
                        lambda: {"試験": ("warming", None)})
    assert watches.unanswered([_w()]) == []


def test_鳴らさなかった待ちは_理由つきで必ず印字する(monkeypatch):
    """**黙って消さないこと。** 消すと、次の回には存在しなかったことになる。"""
    monkeypatch.setattr(watches, "_hypothesis_judge_state",
                        lambda: {"試験": ("warming", None)})
    out = watches.render([_w()])
    assert "まだ判定できません" in out
    assert "何もしないのが正解" in out
    assert "満ちました" not in out


def test_判定できる日が未来の待ちも鳴らさない(monkeypatch):
    from datetime import date as _d, timedelta as _td
    later = _d.today() + _td(days=30)
    monkeypatch.setattr(watches, "_hypothesis_judge_state",
                        lambda: {"試験": ("ready", later)})
    assert watches.unanswered([_w()]) == []
    assert str(later) in watches.render([_w()])


def test_いま判定できる待ちは_これまでどおり鳴る(monkeypatch):
    """**片側だけ緩めないための検査。**"""
    from datetime import date as _d, timedelta as _td
    monkeypatch.setattr(watches, "_hypothesis_judge_state",
                        lambda: {"試験": ("ready", _d.today() - _td(days=1))})
    assert [x.id for x in watches.unanswered([_w()])] == ["試験"]
    assert "満ちました" in watches.render([_w()])


def test_計器が読めないときは鳴らす側へ倒す(monkeypatch):
    """`deadline_check` が読めないことは、「判定できない」ことの証拠ではない。

    ここを逆に倒すと、**計器を壊すだけで待ちが全部 黙る。**
    """
    monkeypatch.setattr(watches, "_hypothesis_judge_state", lambda: None)
    assert [x.id for x in watches.unanswered([_w()])] == ["試験"]


def test_仮説と結ばれていない待ちは_これまでどおり(monkeypatch):
    """`config/hypotheses.yaml` の `watch:` に無い待ちは、自分の目盛りだけで鳴る。"""
    monkeypatch.setattr(watches, "_hypothesis_judge_state",
                        lambda: {"別の待ち": ("warming", None)})
    assert [x.id for x in watches.unanswered([_w()])] == ["試験"]


def test_判定できる日が出せない待ちは抑えない(monkeypatch):
    """`unreachable` / `unchecked` は抑えない。

    前者は**前提の立て方ごと**変える必要があり、後者は分からないだけ。
    **どちらも人が読む価値がある** —— 抑えると、直す機会ごと消える。
    """
    for kind in ("unreachable", "unchecked"):
        monkeypatch.setattr(watches, "_hypothesis_judge_state",
                            lambda k=kind: {"試験": (k, None)})
        assert [x.id for x in watches.unanswered([_w()])] == ["試験"], kind


def test_待ちの門と_deadline_check_が逆を言っていないこと():
    """**本物の台帳で、2つの道具が食い違っていないこと。**

    合成では捕まらない。2026-08-26 に実際に起きたのは実物の側。

    落ちたときの直し方: `src/watches.py` の `_split_rung` が
    `deadline_check` の答えを読めていない。**`_k_*` の数え方を
    仮説に合わせて写し直すのは直し方ではありません** ——
    「同じにしてある」と註に書いてあって、それでもずれたのが由来です。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "twdc", Path(__file__).resolve().parent.parent / "scripts" / "deadline_check.py")
    dc = importlib.util.module_from_spec(spec)
    sys.modules["twdc"] = dc
    spec.loader.exec_module(dc)

    rows = dc.load()
    warming_claims = {v.claim for v in dc.check(rows) if v.warming}
    warming_watch_ids = {str(h.get("watch") or "").strip()
                         for h in rows if isinstance(h, dict)
                         and str(h.get("claim") or "") in warming_claims}
    warming_watch_ids.discard("")

    rung = {w.id for w in watches.unanswered()}
    clash = sorted(rung & warming_watch_ids)
    assert not clash, (
        "`src/watches.py` が「この回で判定すること」と言っている待ちを、"
        "`scripts/deadline_check.py` は「まだ数えはじめたところ・"
        f"何もしないのが正解」と言っています: {clash}"
    )
