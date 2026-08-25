"""`src/ab_split.py` —— **指示が入った本だけで群を割る**ところを見る検査。

ここが落ちると、件数も見た目も正常なまま「どちらが効いたか」だけが壊れます
（2026-08-19 22:2x の実測: `hook_form` は判定日までに公開する本が
両群とも**指示入り0本**で、外れが確定する形になっていました）。
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from src import ab_split
from src.ab_split import (
    EXPERIMENTS,
    MIN_PER_GROUP,
    SETTLE_DAYS,
    Experiment,
    build_times,
    published,
    report,
    split_counts,
)

ROOT = Path(__file__).resolve().parent.parent


def _fake(tmp_path: Path, rows: list[tuple[str, str, str]]) -> tuple[Path, Path]:
    """(topic, 作った時刻, 公開日) から控え2つを組み立てる。"""
    batch, ledger = tmp_path / "batch.jsonl", tmp_path / "up.jsonl"
    batch.write_text(
        "\n".join(
            json.dumps({"at": built, "results": [{"topic": t, "video_id": "v" + t, "error": ""}]})
            for t, built, _ in rows
        ),
        encoding="utf-8",
    )
    ledger.write_text(
        "\n".join(
            json.dumps({"topic": t, "video_id": "v" + t, "at": pub + "T09:00:00Z"})
            for t, _, pub in rows
        ),
        encoding="utf-8",
    )
    return batch, ledger


def _exp(**kw) -> Experiment:
    base = dict(
        name="t",
        split=lambda tid: "問い" if tid.endswith("a") else "断定",
        treated="問い",
        control="断定",
        landed=datetime.fromisoformat("2026-08-19T16:50:00+09:00"),
        deadline=date(2026, 9, 12),
    )
    base.update(kw)
    return Experiment(**base)


def test_指示より前に作った本は群から外れる(tmp_path):
    """**これがこの道具の本体です。** IDが「問い」でも、指示より前なら数えない。"""
    b, l = _fake(
        tmp_path,
        [("old-a", "2026-08-19T10:00:00+09:00", "2026-08-25"),
         ("new-a", "2026-08-19T20:00:00+09:00", "2026-08-25")],
    )
    c = split_counts(_exp(), builds=build_times(b), ledger=published(l))
    assert c.treated_ready["問い"] == 1, "指示の後に作った1本だけが数えられること"
    assert c.stale["問い"] == 1, "指示より前の本は stale に出ること（黙って落とさない）"


def test_控えに作った記録が無い本は指示なし側に数える(tmp_path):
    """記録の無い本は**古い本**なので、安全側（stale）へ。"""
    b, l = _fake(tmp_path, [("x-a", "2026-08-19T20:00:00+09:00", "2026-08-25")])
    b.write_text("", encoding="utf-8")  # 作った記録だけ消す
    c = split_counts(_exp(), builds=build_times(b), ledger=published(l))
    assert c.treated_ready["問い"] == 0
    assert c.stale["問い"] == 1


def test_公開から7日たっていない本はまだ数えない(tmp_path):
    """`SETTLE_DAYS`。初速だけを見ないための床。"""
    when = date(2026, 9, 12)
    late = (when - timedelta(days=SETTLE_DAYS - 1)).isoformat()
    ok = (when - timedelta(days=SETTLE_DAYS)).isoformat()
    b, l = _fake(
        tmp_path,
        [("late-a", "2026-08-19T20:00:00+09:00", late),
         ("ok-a", "2026-08-19T20:00:00+09:00", ok)],
    )
    c = split_counts(_exp(), as_of=when, builds=build_times(b), ledger=published(l))
    assert c.treated_ready["問い"] == 1
    assert c.treated_all["問い"] == 2, "判定日までに公開する本は all のほうに出ること"


def test_判定日より後に公開する本は入らない(tmp_path):
    b, l = _fake(tmp_path, [("far-a", "2026-08-19T20:00:00+09:00", "2026-09-27")])
    c = split_counts(_exp(), as_of=date(2026, 9, 12), builds=build_times(b), ledger=published(l))
    assert c.treated_all["問い"] == 0 and c.stale["問い"] == 0


def test_公開日の無い行は数に入れず件数だけ出す(tmp_path):
    b, l = _fake(tmp_path, [("x-a", "2026-08-19T20:00:00+09:00", "2026-08-25")])
    l.write_text(json.dumps({"topic": "x-a", "video_id": "v", "at": None}), encoding="utf-8")
    c = split_counts(_exp(), builds=build_times(b), ledger=published(l))
    assert c.unknown_publish == 1
    assert c.treated_ready["問い"] == 0


def test_両群が床に届いて初めて判定できる(tmp_path):
    rows = [(f"a{i}-a", "2026-08-19T20:00:00+09:00", "2026-08-25") for i in range(MIN_PER_GROUP)]
    b, l = _fake(tmp_path, rows)
    c = split_counts(_exp(), builds=build_times(b), ledger=published(l))
    assert c.treated_ready["問い"] == MIN_PER_GROUP
    assert not c.judgeable, "片群だけ届いても判定できないこと"
    rows += [(f"b{i}-x", "2026-08-19T20:00:00+09:00", "2026-08-25") for i in range(MIN_PER_GROUP)]
    b, l = _fake(tmp_path, rows)
    assert split_counts(_exp(), builds=build_times(b), ledger=published(l)).judgeable


def test_撃ち直した本はいちばん早い作成時刻で見る(tmp_path):
    """指示より前に一度作られているなら、その本は指示より前の作り。"""
    batch = tmp_path / "b.jsonl"
    batch.write_text(
        "\n".join([
            json.dumps({"at": "2026-08-19T10:00:00+09:00",
                        "results": [{"topic": "r-a", "video_id": "v", "error": ""}]}),
            json.dumps({"at": "2026-08-19T20:00:00+09:00",
                        "results": [{"topic": "r-a", "video_id": "v", "error": ""}]}),
        ]),
        encoding="utf-8",
    )
    assert build_times(batch)["r-a"].hour == 10


def test_落ちた本は作った記録に数えない(tmp_path):
    batch = tmp_path / "b.jsonl"
    batch.write_text(
        json.dumps({"at": "2026-08-19T20:00:00+09:00",
                    "results": [{"topic": "e-a", "video_id": "", "error": "boom"}]}),
        encoding="utf-8",
    )
    assert build_times(batch) == {}


# --- 実物との突き合わせ（**ここが本番の配線**）-------------------------------

def test_走っている実験は全部_hypotheses_から引ける():
    """`EXPERIMENTS` に足したのに yaml に無い（またはその逆）を止める。"""
    text = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    for name in EXPERIMENTS:
        assert f"script_writer.{name}" in text, f"{name} が hypotheses.yaml に居ません"
    for name in re.findall(r"script_writer\.(\w+)` が", text):
        assert name in EXPERIMENTS, f"{name} が EXPERIMENTS に登録されていません"


def test_期限は_yaml_と同じ():
    """`deadline` を2か所で持っているので、ずれたら止める。"""
    data = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    for exp in EXPERIMENTS.values():
        hit = [h for h in data["hypotheses"]
               if f"script_writer.{exp.name}" in str(h.get("falsified_if", ""))]
        assert len(hit) == 1, f"{exp.name} の前提が {len(hit)}件"
        assert str(hit[0]["deadline"]) == exp.deadline.isoformat()


def test_床は_yaml_の文言と同じ数():
    """`MIN_PER_GROUP` / `SETTLE_DAYS` を勝手に緩めていないか。"""
    text = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    for exp in EXPERIMENTS.values():
        assert f"どちらの群も {MIN_PER_GROUP}本に満たなければ判定しない" in text
    assert f"公開から{SETTLE_DAYS}日以上たっていること" in text


def test_yaml_の条件に作った時刻の縛りが書いてある():
    """**母集団の直しが消えたら止める。** これが無いと元の壊れ方に戻ります。"""
    data = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    for exp in EXPERIMENTS.values():
        hit = [h for h in data["hypotheses"]
               if f"script_writer.{exp.name}" in str(h.get("falsified_if", ""))][0]
        cond = str(hit["falsified_if"])
        assert f"{exp.landed:%Y-%m-%d}" in cond or "より後に作った本だけ" in cond, exp.name
        assert "より後に作った本だけで数えること" in cond, exp.name


def test_実物で走って報告が出る():
    """控えが読めること（API を1単位も使わないこと込み）。"""
    out = report()
    for exp in EXPERIMENTS.values():
        assert exp.name in out
    assert "指示が入って落ち着いた本" in out


def test_hook_form_はいま判定できない():
    """**この検査が緑のうちは、hook_form を判定してはいけません。**

    指示が入ったのは 2026-08-19 21:00 で、それ以降に作った本はまだ公開されていません。
    緑でなくなったら（＝両群8本そろったら）、そのとき初めて判定します。
    """
    c = split_counts(EXPERIMENTS["hook_form"])
    if c.judgeable:
        pytest.skip("指示入りが両群そろいました。判定してよい段です")
    assert sum(c.stale.values()) > 0, "混ざっている本が居るなら、必ず数えて出すこと"


# ---------------------------------------------------------------------------
# `outlook` —— **足りない本を、残りの在庫で埋められるか**（2026-08-20 04:4x）
#
# `split_counts` は「あと8本」としか言いません。**その8本が作れるか**も、
# **いつまでに公開すれば数に入るか**も言いませんでした。
# ここは全部**手で作った行**です（実データが動いても意味が変わらないように）。
# ---------------------------------------------------------------------------


def _counts(**ready) -> ab_split.Counts:
    """群 → 落ち着いた本数 だけを持つ `Counts` を手で作る。"""
    return ab_split.Counts(experiment="t", treated_ready=dict(ready))


def test_公開の締切は判定日の7日前():
    """**これが outlook の本体**: 締切より後に公開する本は、1本も数に入らない。"""
    assert ab_split.settle_by(_exp(deadline=date(2026, 9, 16))) == date(2026, 9, 9)
    assert ab_split.settle_by(_exp(), as_of=date(2026, 9, 1)) == date(2026, 9, 1) - timedelta(
        days=SETTLE_DAYS
    )


def test_足りている群にはあと0本と出る():
    o = ab_split.outlook(_exp(), {"問い": 0, "断定": 0},
                         counts=_counts(問い=MIN_PER_GROUP, 断定=MIN_PER_GROUP + 3))
    assert o.need == {"問い": 0, "断定": 0}
    assert o.reachable
    assert "あと0本" in "\n".join(o.lines())


def test_在庫は通過率で割り引いてから床と比べる():
    """**在庫の本数をそのまま作れる本数と読まないこと。** 8本の在庫では 8本作れない。"""
    o = ab_split.outlook(_exp(), {"問い": MIN_PER_GROUP, "断定": 99}, counts=_counts(問い=0, 断定=99))
    assert o.buildable("問い") < MIN_PER_GROUP
    assert not o.reachable, "在庫ちょうどでは床に届かないこと（落ちる本がある）"
    o2 = ab_split.outlook(_exp(), {"問い": 20, "断定": 99}, counts=_counts(問い=0, 断定=99))
    assert o2.reachable


def test_床に届かないときは腕をそろえる手を名指しする():
    o = ab_split.outlook(_exp(), {"問い": 1, "断定": 99}, counts=_counts(問い=0, 断定=99))
    text = "\n".join(o.lines())
    assert "足りません" in text
    assert "ab_balance.py" in text, "**次に打つ手を言わない警告は、次の回に効きません**"


def test_足りない群があれば置く日付の締切を必ず言う():
    """在庫が足りていても言うこと —— **締切より後に置けば 0 になる**のは同じ。"""
    o = ab_split.outlook(_exp(deadline=date(2026, 9, 16)), {"問い": 30, "断定": 30},
                         counts=_counts(問い=0, 断定=0))
    text = "\n".join(o.lines())
    assert o.reachable
    assert "09/09" in text and "batch_build.py --date" in text


def test_在庫の総数を出す():
    """**28本しかない**ことが読めなければ、締切の重さが伝わりません。"""
    o = ab_split.outlook(_exp(), {"問い": 13, "断定": 15}, counts=_counts(問い=0, 断定=0))
    assert o.stock_total == 28
    assert "28本" in "\n".join(o.lines())


def test_報告に在庫を渡さなければ見通しは出ない():
    """**在庫を数えるのは重い**ので、既定では出さないこと。"""
    assert "この判定には入りません" not in report()


def test_実物_hook_form_の在庫の締切は09_09():
    """実データ側に固定してよいのは『まだ測れていない』ことのほう ——
    ここで固定するのは**期限の算術だけ**で、在庫の本数は固定しません。"""
    assert ab_split.settle_by(EXPERIMENTS["hook_form"]) == date(2026, 9, 9)
    assert ab_split.settle_by(EXPERIMENTS["title_form"]) == date(2026, 9, 5)


# --- 帳面は「1行1本」ではない（2026-08-25。群の分母が条件と食い違う形の4件目）---
#
# `data/uploaded.jsonl` は足すだけの帳面で、`scripts/reschedule.py` が公開時刻を
# 動かすたびに同じ `video_id` の行が増えます。実測 **505行 / 実物 491本**。
# 下の2件は、直す前の `published()` なら**どちらも落ちます。**


def test_動かした本は1本として数える(tmp_path):
    """同じ `video_id` が2行あっても1本。**片群だけ2回数えると床が早く開きます。**"""
    ledger = tmp_path / "up.jsonl"
    ledger.write_text(
        "\n".join([
            json.dumps({"topic": "x-a", "video_id": "vx", "at": "2026-08-20T09:00:00Z"}),
            json.dumps({"topic": "x-a", "video_id": "vx", "at": "2026-08-22T09:00:00Z"}),
        ]),
        encoding="utf-8",
    )
    rows = published(ledger)
    assert len(rows) == 1, "動かした本が2件に化けています"
    # **後の行**を採ること（最初の行は、すでに動かされた過去の予定）
    assert rows[0]["publish"] == date(2026, 8, 22)


def test_同じ題材でも別の本なら別に数える(tmp_path):
    """`topic` で畳むと、**実在する本が消えます**（実測 20件が別 `video_id`）。"""
    ledger = tmp_path / "up.jsonl"
    ledger.write_text(
        "\n".join([
            json.dumps({"topic": "x-a", "video_id": "v1", "at": "2026-08-20T09:00:00Z"}),
            json.dumps({"topic": "x-a", "video_id": "v2", "at": "2026-08-21T09:00:00Z"}),
        ]),
        encoding="utf-8",
    )
    assert len(published(ledger)) == 2, "別の本が1本に潰れています"


def test_公開日は_JST_で採る(tmp_path):
    """`at` は UTC。素直に `.date()` を採ると **JST の朝が前日に落ちます。**

    下の時刻は 08/27 の 05〜08時 JST に置いた「時刻の窓か本数か」の実験そのもので、
    UTC で割ると 4本とも 08/26 に落ちます（実測）。
    """
    ledger = tmp_path / "up.jsonl"
    ledger.write_text(
        json.dumps({"topic": "x-a", "video_id": "vx", "at": "2026-08-26T20:00:00Z"}),
        encoding="utf-8",
    )
    assert published(ledger)[0]["publish"] == date(2026, 8, 27), "UTC の日で割っています"


def test_実物の帳面は行数より少ない本数になる():
    """実データで、畳みが効いていること。"""
    ledger = ROOT / "data" / "uploaded.jsonl"
    if not ledger.exists():
        pytest.skip("控えがありません")
    lines = [x for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = published(ledger)
    seen = {json.loads(x)["video_id"] for x in lines}
    assert len(rows) == len(seen) < len(lines), (
        f"{len(lines)}行 → {len(rows)}本（実物 {len(seen)}本）"
    )


# --- landed_groups（2026-08-25 に足した）---------------------------------
# **振り分けの無い作りの変更**（冒頭の stat の割り方・冒頭の動きなど）は、
# 「入る前に作ったか・後に作ったか」が群そのものです。**公開日で割らないこと** ——
# 作ってから公開までの間隔が伸び続けているので、公開日は群を表しません
# （実測 2026-08-25: 8/16 公開の本は 0.9日・8/24 は 7.5日・予約全体は中央値 13.4日）。

from src.ab_split import landed_groups


def test_作った時刻で割る() -> None:
    JST_ = datetime(2026, 8, 23, 22, 3, 31).replace(tzinfo=ab_split.JST)
    builds = {
        "old-1": datetime(2026, 8, 20, 9, 0, tzinfo=ab_split.JST),
        "old-2": datetime(2026, 8, 23, 22, 3, 30, tzinfo=ab_split.JST),   # 1秒前
        "new-1": datetime(2026, 8, 23, 22, 3, 31, tzinfo=ab_split.JST),   # ちょうど
        "new-2": datetime(2026, 8, 24, 9, 0, tzinfo=ab_split.JST),
    }
    assert landed_groups(JST_, builds) == (["old-1", "old-2"], ["new-1", "new-2"])


def test_公開日で割ると処置群がほぼ空になる() -> None:
    """**この検査が、条件を書き直した理由そのものです。**

    実測（2026-08-25・`config/hypotheses.yaml` の 09/05「前提を先・数字を後」）:
    旧条件の『処置群』350本のうち、**実際に処置が入っていたのは 21本（6.0%）**。
    ここでは同じ形を小さく作って、**公開日で割ると処置群が薄まる**ことを固定します。
    """
    landed = datetime(2026, 8, 23, 22, 3, 31, tzinfo=ab_split.JST)
    # 3本とも「landed より後に公開」だが、作ったのは landed より前（在庫が先に積んである）
    builds = {f"t{i}": datetime(2026, 8, 18, 9, 0, tzinfo=ab_split.JST) for i in range(3)}
    builds["t-new"] = datetime(2026, 8, 24, 9, 0, tzinfo=ab_split.JST)
    before, after = landed_groups(landed, builds)
    assert len(after) == 1 and len(before) == 3, (
        "公開日ではなく作った時刻で割れていません"
    )


def test_実物で処置群は門に足りていない() -> None:
    """**まだ判定してはいけない**ことを、実データで固定する。

    足りているのに「足りない」と言い続けるほうが危ないので、
    **足りたらこの検査が落ちます。** 落ちたら判定に入ってよい合図です。
    """
    landed = datetime(2026, 8, 23, 22, 3, 31, tzinfo=ab_split.JST)
    before, after = landed_groups(landed)
    if not before and not after:
        pytest.skip("作った記録がありません")
    assert len(after) < MIN_PER_GROUP, (
        f"処置群が {len(after)}本 ＝ 門 {MIN_PER_GROUP} に達しました。"
        "**判定に入ってよい合図です** —— hypotheses.yaml の 09/05 を判定し、"
        "この検査を消すこと"
    )
