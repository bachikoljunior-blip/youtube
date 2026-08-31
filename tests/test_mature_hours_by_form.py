"""**「標本に入れてよい年齢」は、形ごとに違うこと。**（2026-08-31）

## なぜ要るか（この回に撃って出た数）

`src/settle.py` は `MATURE_HOURS = 48` に「**48時間で伸びが終わります**」と書き、
その覆る条件に**最初から**こう書いてありました ——

    **長尺には当てていません。** 長尺は1本 4.0回 で標本にならないので、
    ここの数はショートの形です。長尺で判定する前提を置くときは測り直すこと

**測り直していませんでした。** 形で割った実測（`settle.views_curve(form=...)`・
`data/video_forms.json`・API 0単位）::

    48h で「伸びきった本」の割合   ショート **96.2%**（n=79）／ 長尺 **25.0%**（n=8）
    96h で                        ショート 100.0%        ／ 長尺 **62.5%**
    48h の中央値                  ショート 100.1%        ／ 長尺 **73.2%**

**48時間の長尺は、一生ぶんではなく4〜7割ぶん**を持って標本に入ります。
`scripts/eta.drop_unripe()` の docstring が「(2) …一生ぶんではなく数時間ぶんを
持って平均に入ります」と禁じている形の、**長尺ぶん**です。

## なぜ効くか（**ここが要点**）

下振れした長尺の1本あたり再生は `analyse()` の `per_video_by_band` を通り、
`長尺 お金 高` の帯を実際より遠くに出します。**その帯は、ショートの天井
（`config/hypotheses.yaml` の `ceiling.value: 1891`）から出る唯一の逃げ道**です
（同じ `ceiling:` の `escape_note`：「外す道は形を替えること（＝腕 rpm）しかない」）。
**逃げ道を、合わない物差しで測っていました。**

## この検査が落ちる条件（＝**直し方**）

- 長尺の年齢がショートと同じに戻ったら → 1つの数に畳み直されています。
  **形で割り直すこと**（消すのではなく）
- 形の分からない本が長尺の年齢で判定されるようになったら →
  `data/video_forms.json` は**公開済みだけ**を持つので、
  **新しく出した本はしばらく形が分かりません。** そこを 96時間 に倒すと、
  ショートが2日ぶん余計に落ちます
- 実測のほうが動いたら（長尺の標本が増えた・`full_at` を延ばした）→
  `MATURE_HOURS_BY_FORM` を上げ直すこと。**どちらも上げる向きにしか動きません**
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import settle  # noqa: E402

_NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def eta():
    spec = importlib.util.spec_from_file_location("etamod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_長尺の年齢はショートより長い():
    s = settle.MATURE_HOURS_BY_FORM["ショート"]
    l = settle.MATURE_HOURS_BY_FORM["長尺"]
    assert l > s, (
        f"長尺 {l}時間 がショート {s}時間 を超えていません —— "
        "実測（48h で伸びきった本: ショート 96.2% ／ 長尺 25.0%）と逆です"
    )


def test_形が分からない本はショートの年齢へ落ちる():
    """**新しく出した本は、しばらく形が分かりません**（`video_forms.json` は公開済みだけ）。"""
    assert settle.mature_hours(None) == settle.MATURE_HOURS
    assert settle.mature_hours("なぞ") == settle.MATURE_HOURS
    assert settle.MATURE_HOURS == settle.MATURE_HOURS_BY_FORM["ショート"]


def test_drop_unripe_は形ごとの年齢を当てている(eta):
    """**同じ齢の2本が、形だけで分かれること。**"""
    s_h = settle.MATURE_HOURS_BY_FORM["ショート"]
    l_h = settle.MATURE_HOURS_BY_FORM["長尺"]
    age = (s_h + l_h) / 2          # ショートには熟し、長尺にはまだ若い齢
    born = _NOW - timedelta(hours=age)
    rows = [["s", 900, 20, 40.0], ["l", 900, 20, 40.0]]
    pub = {"s": born, "l": born}
    kept, dropped = eta.drop_unripe(rows, pub, _NOW,
                                    video_forms={"s": "ショート", "l": "長尺"})
    ids = [r[0] for r in kept]
    assert ids == ["s"], f"残ったのは {ids} —— 形で分かれていません"
    assert dropped.get("未熟") == ["l"]


def test_長尺も熟せば標本に入る(eta):
    born = _NOW - timedelta(hours=settle.MATURE_HOURS_BY_FORM["長尺"] + 1)
    kept, _ = eta.drop_unripe([["l", 900, 20, 40.0]], {"l": born}, _NOW,
                              video_forms={"l": "長尺"})
    assert [r[0] for r in kept] == ["l"]


def test_落とした理由の印字が形ごとの数を出している(eta):
    """**1つの数で刷ると、長尺のぶんが嘘になります。**"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    # **`dropped` の初期化にも同じ鍵があります**（`"未熟": []`）。
    #     見たいのは「人が読む理由」のほうなので、`公開から` を含む側を採ります。
    i, pos = -1, 0
    while True:
        k = src.find('"未熟":', pos)
        if k < 0:
            break
        if "公開から" in src[k:k + 400]:
            i = k
            break
        pos = k + 1
    assert i >= 0, "「未熟」の理由の印字が見つかりません"
    j = src.index('"窓の外":', i)
    body = src[i:j]
    assert "MATURE_HOURS_BY_FORM" in body, (
        "「未熟」の理由が、形ごとの数を読んでいません（1つの数で刷ると嘘になります）"
    )


def test_実測が形で割れる(eta):
    """**根拠のほうも撃てること。** 撃てない数は、次の回が確かめられません。"""
    short = settle.views_curve((48,), min_views=30.0, form="ショート")
    long_ = settle.views_curve((48,), min_views=1.0, form="長尺")
    if not short or not long_:
        pytest.skip("data/views.jsonl / data/video_forms.json に標本がありません")
    assert short[48]["share_settled"] > long_[48]["share_settled"], (
        f"48h で伸びきった本の割合が、ショート {short[48]['share_settled']:.1%} "
        f"／ 長尺 {long_[48]['share_settled']:.1%} —— 逆転しています。"
        "逆転が続くなら `MATURE_HOURS_BY_FORM` を測り直すこと"
    )
