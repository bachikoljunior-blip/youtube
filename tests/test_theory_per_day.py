"""**「理論値の在りか」は、外の生涯の累計 ÷ 自分の 48時間 でした**（2026-09-04 に測った）。

公開日を埋めて数えたら、外の上位に **48時間 以内の本は 1本もありません**
（長尺 齢 中央 203日／ショート 1,729日 ＝ 4.7年）。しかも撃つ窓が形ごとに違います
（`niche_ceiling.SP_FILTERS`: ショート＝全期間・長尺＝今年）。
＝ **別々の窓で測った2つを、横に並べて形を決めていました。**

1日あたりに直すと、ショートだけ向きが変わります（自分 524回/日 対 外 18回/日 ＝ ×0.04）。
長尺の ×21,145 は窓を揃えても残ります。

**累計を消していません** —— 累計は「その題でどこまで積めるか」、1日あたりは
「いま追い付けるか」。**片方だけだと、窓の差が結論を作ります。**
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src import daily_pick as dp

NOW = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)


def _ledger(tmp_path, *, short_age: int, long_age: int):
    """外の帳面を1件だけ書く（ショート・長尺とも上位 3本）。"""
    tmp_path.mkdir(parents=True, exist_ok=True)
    def top(form: str, views: list[int], age: int) -> list[dict]:
        return [{"id": f"{form}{i}", "form": form, "views": v, "secs": 60 if form == "short" else 1500,
                 "published": (NOW - timedelta(days=age)).isoformat().replace("+00:00", "Z")}
                for i, v in enumerate(views)]

    row = {"at": NOW.isoformat(), "queries": ["q"], "form": "any", "source": "free",
           "summary": {"short": {"n": 3, "max": 3000, "p90": 3000, "median": 2000, "channels": 3},
                       "long": {"n": 3, "max": 9000, "p90": 9000, "median": 6000, "channels": 3}},
           "top": top("short", [1000, 2000, 3000], short_age)
                  + top("long", [3000, 6000, 9000], long_age)}
    p = tmp_path / "niche_ceiling.jsonl"
    p.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


CMP = {"rule": {"ショート": {"median": 1000}, "長尺": {"median": 100}},
       "all": {"ショート": {"median": 1000}, "長尺": {"median": 100}}}


def test_齢で割った比も同じ画面に出す(tmp_path) -> None:
    led = _ledger(tmp_path, short_age=100, long_age=100)
    out = "\n".join(dp.theory_lines(CMP, ledger=led, now=NOW, need=None))
    assert "**理論値の在りか**" in out                     # 累計の側は消さない
    assert "同じものを1日あたりで" in out
    # ショート: 外の中央 2000/100日 = 20回/日 ÷ 自分 1000/48h = 500回/日 → ×0.04
    assert "ショート **×0.04**" in out
    # 長尺: 外の中央 6000/100日 = 60回/日 ÷ 自分 100/48h = 50回/日 → ×1.20
    assert "長尺 **×1.20**" in out
    assert "外の上位に 48時間 以内の本は 0本" in out


def test_1日あたりで近い形を名指しする(tmp_path) -> None:
    """**上の行と食い違うことがあります。** どちらか片方を根拠にしないこと。"""
    led = _ledger(tmp_path, short_age=100, long_age=100)
    out = "\n".join(dp.theory_lines(CMP, ledger=led, now=NOW, need=None))
    assert "いちばん近い形は **ショート**" in out
    assert "どちらか片方を根拠にしないこと" in out
    assert "SP_FILTERS" in out                            # 窓が形ごとに違うことも同じ行に


def test_齢が古いほど1日あたりは小さくなる(tmp_path) -> None:
    old = "\n".join(dp.theory_lines(CMP, ledger=_ledger(tmp_path / "a", short_age=2000,
                                                        long_age=100), now=NOW, need=None))
    assert "齢 中央 2,000日" in old
    assert "ショート **×0.00**" in old                     # 2000/2000日 = 1回/日 ÷ 500


def test_公開日が空なら1日あたりの行は出ない(tmp_path) -> None:
    """**中央値が1本で決まる帯から、形の結論を出さないこと**（標本 3本 未満は黙る）。"""
    led = _ledger(tmp_path, short_age=100, long_age=100)
    row = json.loads(led.read_text(encoding="utf-8"))
    for t in row["top"]:
        t["published"] = ""
    led.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    out = "\n".join(dp.theory_lines(CMP, ledger=led, now=NOW, need=None))
    assert "**理論値の在りか**" in out                     # 累計の側は前と同じに出る
    assert "同じものを1日あたりで" not in out
