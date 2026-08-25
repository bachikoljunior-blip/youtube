"""**節を握ったまま死ぬテーマを、`topics.yaml` に書く前に外す**（2026-08-18）。

`scripts/batch_build._drop_doomed`（`tests/test_pick_doomed.py`）は、
**もう `topics.yaml` に入ってしまったもの**を作る前によけます。それで
「作った1本が捨てになる」ほうは止まりましたが、**よけられたテーマは
`calc_sections` を握ったまま残る**ので、`topic_forge.survey()` の
`claimed` に入り、**その節は二度と割り当てられません。**

実測（2026-08-18 21:4x。未投稿125件を実際に門へ通した）: **4件が該当。**
**4件とも節そのものは新しく、題の主役に選んだ数だけが既出**でした ——

    s-jidou-hitori-atari-6480000-todokanai   6,480,000円
      ← `児童手当 第3子は648万円 第1子の2.77倍`（09/14 予約）と同じ数

だから塞ぐのは節ではなく**数の選び方**で、手は2つあります:

    書かせる前  `dupes.used_amounts()` を貼って「この数は主役にするな」と言う
    書いた後    `topic_forge.drop_doomed()` が落とす（**節は未使用のまま残る**）

故障注入は両向き（落とす側と、落としてはいけない側）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "topic_forge", ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)

from src import dupes  # noqa: E402

TOPICS = [
    {"id": "s-jidou-posted", "calc": "jidou",
     "title_seed": "児童手当 第3子は648万円 第1子の2.77倍"},
    {"id": "s-other", "calc": "yukyu", "title_seed": "有給の出勤率8割の話"},
]

FORGED_DOOMED = {"id": "s-jidou-hitori-atari", "calc": "jidou",
                 "title_seed": "1人あたりの総額は6,480,000円に永久に届かない",
                 "angle": "ショート。", "calc_sections": ["1人あたり"]}
FORGED_CLEAN = {"id": "s-jidou-sa-48", "calc": "jidou",
                "title_seed": "長子が抜けると末っ子は月15,000円だけ残る",
                "angle": "ショート。", "calc_sections": ["1人あたり"]}


def _ledger(topics=None):
    """予約済みの1本だけを持つ控え（`calc` はテーマID経由で入る）。"""
    return [{"id": "vid00000001", "title": "児童手当 第3子は648万円 第1子の2.77倍",
             "topic": "s-jidou-posted", "calc": (topics or {}).get("s-jidou-posted", ""),
             "at": "2026-09-14T05:00:00Z", "scheduled": True}]


def test_既出の金額を主役にした種は書く前に落ちる(monkeypatch):
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    kept, dropped = forge.drop_doomed([FORGED_DOOMED, FORGED_CLEAN], TOPICS)
    assert [r["id"] for r in kept] == ["s-jidou-sa-48"]
    assert len(dropped) == 1
    assert "投稿の門が必ず止めます" in dropped[0]
    assert "6,480,000円" in dropped[0]


def test_落とした理由に節が残ることを書く(monkeypatch):
    """**落とすことが目的ではありません。**節を返すことが目的です。

    `topics.yaml` に1行も書かないので `survey()` の `claimed` に入らず、
    次の回が同じ節を**別の数字で**書き直せます。読む側にそれが伝わること。
    """
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    _, dropped = forge.drop_doomed([FORGED_DOOMED], TOPICS)
    assert "節は未使用のまま残す" in dropped[0]


def test_重ならない種は落とさない(monkeypatch):
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    kept, dropped = forge.drop_doomed([FORGED_CLEAN], TOPICS)
    assert [r["id"] for r in kept] == ["s-jidou-sa-48"]
    assert dropped == []


def test_同じcalcでなければ同じ数でも通す(monkeypatch):
    """**門は calc ごとに見ます。**別の族で同じ額が出るのは重なりではありません。"""
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    other = dict(FORGED_DOOMED, id="s-yukyu-6480000", calc="yukyu")
    kept, dropped = forge.drop_doomed([other], TOPICS)
    assert [r["id"] for r in kept] == ["s-yukyu-6480000"]
    assert dropped == []


def test_この回に作った行のcalcも渡っている(monkeypatch):
    """**渡し忘れると `same-yen` が1組も当たりません**（`test_pick_doomed` と同じ穴）。

    控えの行は「どの calc の本か」を**テーマID経由でしか知りません**。
    落とす対象そのものの calc が `calc_of` に入っていないと、
    門から見て族が空になり、素通りします。
    """
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    # `TOPICS` には s-jidou-hitori-atari が無い（まだ topics.yaml に無いので当然）。
    # それでも落ちるのは、`drop_doomed` が rows 側の calc を足しているから。
    kept, _ = forge.drop_doomed([FORGED_DOOMED], TOPICS)
    assert kept == []


def test_used_amounts_は既出の金額だけを族ごとに出す(monkeypatch):
    monkeypatch.setattr(dupes, "ledger_rows", lambda topics=None: [
        {"id": "v1", "title": "副業は20万円ルール 実際は359,318円",
         "topic": "s-a", "calc": "fukugyo", "at": None, "scheduled": False},
        {"id": "v2", "title": "有給は年10日から", "topic": "s-b",
         "calc": "yukyu", "at": None, "scheduled": False},
    ])
    got = dupes.used_amounts({"s-a": "fukugyo", "s-b": "yukyu"})
    assert got["fukugyo"] == [359318.0]      # 200,000 は丸いので入らない
    assert "yukyu" not in got                # 10日 は金額ではない


def test_貼る文に既出の金額が入る(monkeypatch):
    """書かせる前の手。**貼っていなければ、書き手は同じ数を選び続けます。**"""
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    prompt = forge.build_prompt(
        [("jidou", "=== 1人あたりの総額 ===")],
        {"jidou": {"=== 1人あたりの総額 ===": "6,480,000円 …"}},
        TOPICS)
    assert "6,480,000円" in prompt
    assert "主役に選ばないこと" in prompt


def test_既出が無い族には余計な行を貼らない(monkeypatch):
    monkeypatch.setattr(dupes, "ledger_rows", _ledger)
    prompt = forge.build_prompt(
        [("yukyu", "=== 出勤率 ===")],
        {"yukyu": {"=== 出勤率 ===": "8割 …"}},
        TOPICS)
    assert "既に題に出した金額" not in prompt
