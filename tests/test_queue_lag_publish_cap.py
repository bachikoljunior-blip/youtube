"""**1日N本の与件が変わったら、床の間に合う／間に合わないが反転すること。**

## なぜ要るか（2026-08-31・最適化の回）

与件が足されました —— **公開は1日1本・作り置きはしない。**
処置は `batch_build.cap_by_density()`（＝**これから作る本**の置き方）に入りますが、
`scripts/queue_lag.py` の床の節は `batch_build.live_plan()`（帯 10枠/日）で
数えていたので、**上限が 10 から 1 に変わっても印字が1文字も動きませんでした。**

実測（足した回・`request_form` あと 96本・締切 2026-09-29）:

    上限 13本/日 → 最後の1本 2026-09-09  **間に合います**（余り 20日）
    上限  1本/日 → 最後の1本 2026-12-23  **85日 越えます**

**この検査が見ているのは、その反転が起きること**だけです。日付や日数は
毎日 動くので**写しません**（写すと、本が1本 増えるたびに赤くなります）。

**覆る条件**: `rate_lines()` が `publish_cap()` 以外から上限を取るようになったら、
差し替えが効かなくなるので、ここは赤くなります。**そのとき直すのは本体のほう**
—— 上限を2か所から読む形に戻っています。
"""
from __future__ import annotations

import re as _re

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.queue_lag as ql  # noqa: E402


def _lines(cap: int, monkeypatch) -> list[str]:
    monkeypatch.setattr(ql, "publish_cap", lambda: cap)
    rows = ql.scheduled()
    short = ql.answering(rows)[2]
    return ql.rate_lines(short, rows)


def test_上限を写していない(monkeypatch):
    """**`rate_lines()` は上限を `publish_cap()` からしか取らないこと。**"""
    out = "\n".join(_lines(7, monkeypatch))
    assert "**7本/日**" in out, out[:400]


def _last_dates(out: str) -> dict[str, str]:
    """群ごとの「最後の1本」の日を拾う。`` `群` あと **N本** → … **YYYY-MM-DD** ``。"""
    found = {}
    for m in _re.finditer(r"`([a-z_]+)`\s*あと\s*\*\*(\d+)本\*\*.*?最後の1本は\s*\*\*(\d{4}-\d\d-\d\d)\*\*", out):
        found[m.group(1)] = (int(m.group(2)), m.group(3))
    return found


def test_上限が1本になると床の日が後ろへ動く(monkeypatch):
    """**上限が印字だけでなく、計算にも効いていること。**

    ## **2026-09-02: ここは「越えます」を見ていて、赤くなりました**

    足した日（08-31）の実測は `request_form` **あと 96本**・締切 09-29 で、
    1本/日 なら **85日 越えます**でした。**いまは越えません** ——
    きょうだいの回が期限を実データで解き直し（title_form 09-07→09-27 ほか）、
    こちらの回が前提を1件 閉じたぶん、床が縮んだからです。
    **反転が起きないのは、模型が直った結果であって、欠陥ではありません。**

    docstring は「日付や日数は毎日 動くので写しません」と書いているのに、
    **「越えます」という*結果*のほうを写していました。** 同じ穴です。

    **だから見るのは結果ではなく差です** —— 上限を 13 から 1 へ落としたら、
    どの群の「最後の1本」も**後ろへ動く**こと（同じか、より後）。
    そして 2本以上 要る群が1つでもあれば、**少なくとも1群は厳密に後ろへ**。
    これは越える／越えないに関わらず、毎日 観測できます。

    **覆る条件**: `rate_lines()` が上限を `publish_cap()` 以外から取るように
    なったら、日が1日も動かなくなってここが赤くなります。
    **そのとき直すのは本体のほう** —— 上限を2か所から読む形に戻っています。
    """
    wide = _last_dates("\n".join(_lines(13, monkeypatch)))
    tight = _last_dates("\n".join(_lines(1, monkeypatch)))
    assert wide, "床の在る群が1つもありません（この検査が空回りしています）"
    assert set(wide) == set(tight), (wide, tight)
    for key, (_n, day) in wide.items():
        assert tight[key][1] >= day, (
            f"{key}: 上限を 13→1 に落としたのに、最後の1本が前へ動いています "
            f"({day} → {tight[key][1]})")
    movable = [k for k, (n, _d) in wide.items() if n >= 2]
    if movable:
        assert any(tight[k][1] > wide[k][1] for k in movable), (
            "2本以上 要る群があるのに、上限を 13→1 にしても日が1日も動きません "
            f"（`publish_cap()` が計算に効いていない）: {wide} → {tight}")


def test_上限が読めない回は答えを出さない(monkeypatch):
    """**既定へ落として印字しないこと** —— 10倍 楽観な日付が出ます。"""
    monkeypatch.setattr(ql, "publish_cap", lambda: 0)
    out = "\n".join(ql.rate_lines([], None))
    assert "答えを出しません" in out, out
    assert "越えます" not in out


def test_作り置きが上限を超えていれば鳴る(monkeypatch):
    """予約に在る本は `cap_by_density()` を通っていないので、別に数えること。"""
    out = "\n".join(_lines(1, monkeypatch))
    rows = ql.scheduled()
    if not rows:
        return
    assert "作り置きが、この上限を超えています" in out, out[:600]
