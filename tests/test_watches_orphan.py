"""**前提の `watch:` を書き替えたら、古い待ちが孤児になって鳴り続けます。**

## なぜ要るか（2026-09-01 10:3x に実測で踏んだ。**46回 鳴っていました**）

`tests/test_watches.py::test_数の門を持つ未判定の仮説は台帳を指している` は
**前提 → 待ち**の向きだけを見ています。**逆向きが空いていました。**

実測 —— `config/watches.yaml` の `長尺1本あたり-30本`:

    2026-08-29  前提「長尺の1本あたり再生 8.0回 は長尺の天井ではない」に
                `watch: 長尺1本あたり-30本` を書き、待ちを置いた
    2026-09-01  同じ前提の `falsified_if` を書き直した回が、床を 30本 → 13本、
                齢を 24〜72時間 → 96時間 に直し、**`watch:` を
                `長尺1本あたり-13本` へ書き替えた**（30 > 直近28日 なので
                規則1 の下では永久に満ちなかった。`house_rule.window_unreachable()`）
    2026-09-01  同じ日に、その前提は `outcome: falsified` で閉じた
                （n=22・中央値 4回・門 80回・p=0.0001）

**書き替えたときに、古い `長尺1本あたり-30本` が残りました。**
どの前提からも指されていないので、`src/watches.py` は「閉じた前提の待ち」だと
気づけません。`status.py` は 2026-09-01T02:23 から **46回** これを鳴らし、
毎回「**満ちました** → いまから判定せよ」と、**同じ日に閉じた前提の
`verdict:` に答えが書いてある問いを出していました。**

**孤児は「鳴っているのに誰も潰さない待ち」になります。** この repo の
`src/alerts.py` が名指ししている「**一覧が当たりを含まないまま育つ**」の形で、
`retro.py` の持ち越しと同じく **偽陽性は本物より高くつきます** ——
毎周、読む側が「これは何だったか」を調べ直すからです。

## 何を見るか

`kind: hypothesis_needs` の待ちは、**その定義からして前提にぶら下がっています**
（床の数を持たず、`needs` を前提に訊きに行く）。だから

    開いた前提のどれかが `watch: <この id>` と書いている   → 生きている
    どの開いた前提も指していない                          → **前提が閉じたか、
                                                            id が書き替わったか**

後者は `answered:` を入れて畳むこと。**消さないこと** ——
畳んだ跡は「なぜ鳴らなくなったか」の記録になります（`config/watches.yaml` 冒頭）。

**覆る条件**: `kind: hypothesis_needs` 以外の待ちが前提にぶら下がるように
なったら、ここの絞り込みを広げること。逆に、待ちの側が
「自分がどの前提のものか」を欄で持つようになったら（`hypothesis:` のような）、
**この検査は id の一致を見るだけで済みます。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import watches  # noqa: E402


def _hypotheses() -> list[dict]:
    import yaml

    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    return list(doc.get("hypotheses", []) or [])


def _watched_by_open() -> set[str]:
    """**開いた前提が指している待ちの id。**（`verdict:` の入った項は閉じた側）"""
    return {str(h.get("watch")) for h in _hypotheses()
            if not h.get("verdict") and h.get("watch")}


def test_前提にぶら下がる待ちは_開いた前提から指されている():
    """**孤児は、答えの出ている問いを毎回 鳴らします。**"""
    live = _watched_by_open()
    orphans = []
    for w in watches.load():
        if w.kind != "hypothesis_needs":
            continue
        if getattr(w, "answered", None):
            continue                      # 畳みずみ。跡として残してよい
        if w.id not in live:
            orphans.append(w.id)
    assert not orphans, (
        "`kind: hypothesis_needs` の待ちが、どの**開いた**前提からも"
        " `watch:` で指されていません:\n  " + "\n  ".join(orphans)
        + "\n  → 前提が閉じたか、前提の `watch:` の id が書き替わったかです。"
          "\n     **鳴らす相手がいない待ちは、毎回「満ちました」と言い続けます**"
          "（2026-09-01 の実測: `長尺1本あたり-30本` が 46回）。"
          "\n  → 直し方: その待ちに `answered:` を入れて畳むこと（消さないこと）。"
          "\n     まだ生きているなら、前提の側の `watch:` をこの id に戻すこと。")


def test_畳んだ待ちは_この検査を素通りする():
    """**`answered:` の入った待ちは、指されていなくてよい。**

    畳んだ跡を消させないための逃げ道です（`config/watches.yaml` 冒頭 ——
    「満ちた待ちは `answered:` に1行（日付と答え）を入れるまで毎回鳴ります」）。
    ここで畳んだものまで赤くすると、**跡を消すのが直し方になってしまいます。**
    """
    answered = [w for w in watches.load()
                if w.kind == "hypothesis_needs" and getattr(w, "answered", None)]
    assert answered, (
        "`kind: hypothesis_needs` で `answered:` の入った待ちが1件もありません。"
        "**この逃げ道が効いているかを、実物で確かめられません** ——"
        "1件も無くなったら、この検査は消してよい（`answered:` を書く先が"
        "無いということなので）")
    live = _watched_by_open()
    assert any(w.id not in live for w in answered), (
        "畳んだ待ちが全部まだ前提から指されています。**それ自体は正常です** ——"
        "ただし、この逃げ道が実際に使われた例が無いので、"
        "上の検査が畳んだ跡を赤くしないことを実物では確かめられていません")


def test_長尺1本あたり30本は畳まれている():
    """**実測で踏んだ1件を、名指しで守る**（`src/alerts.py` の「一覧が育つ」の逆）。

    この id が `answered:` 抜きで戻ってきたら、また 46回 鳴りはじめます。
    """
    w = next((w for w in watches.load() if w.id == "長尺1本あたり-30本"), None)
    if w is None:
        return                            # 台帳から消えたなら、それでよい
    assert getattr(w, "answered", None), (
        "`長尺1本あたり-30本` の `answered:` が消えています。"
        "**元の前提は 2026-09-01 に `falsified` で閉じており**"
        "（中央値 4回 対 門 80回）、生きているのは `長尺1本あたり-13本` のほうです")
