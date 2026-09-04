"""`scripts/eta.py` —— **止まっている間、裸の到達日を先に出さないこと。**

## この検査が守っているもの（2026-08-30）

`CLAUDE.md` は、届かないときの印字について次の規則を置いています。

> **裸の「届きません」を出さないこと。**
> 何を固定したせいでそう出たのかを、同じ行に並べること。

**裸の到達日は、その規則の鏡像**です。符号が逆なだけで、同じ欠陥
——「特定の条件で言っているだけなのに、その条件が書いていない」。

実測 2026-08-30、`src/pause_guard` が生成と投稿を塞いでいる状態で、
`headline()` は次を印字していました。

    ### **月20万の到達予測（軌跡）: 2027-01-10**（133日後）
    ### 縛っているのは …… → **この回に引く腕は `per_video`**

**どちらもこの回には引けません。** 腕を引くには本を出す必要があり、
その入口が塞がっているからです。読み手が最初に見るのはこの3行なので
（`headline()` の docstring「最初に見た数字が、その回の入口になります」）、
**塞がっていることは、日付より先に出ないと意味がありません。**

固定するのは次の2つです。

1. **止まっている間、警告が到達日より前に出ること**（順番が逆なら落ちる）
2. **止まっていなければ、この段は自分で黙ること**（平時に雑音を足さない）
"""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_pause_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


# **最小の payload です。** `headline()` が読むのはこの3つだけ（2026-08-30 に確認）。
# 増えたらここが KeyError で落ちるので、**そのとき足すこと。**
_PL = {"target_date": None, "lever_hint": "per_video", "lever_days": {},
       "binding": "再生数が天井に当たっている"}

# **軌跡を必ず持たせます。** 持たせないと到達日の行が出ず、
# 「警告が日付より前か」の検査が**素通り（vacuous）**になります。
_TR = {"base": {"date": date(2027, 1, 10), "days": 133, "t_work": 47,
                "plan_days": 85, "blocking": []},
       "fast": {"date": date(2026, 12, 20)},
       "slow": {"date": date(2027, 3, 30)}}


def _lines(monkeypatch, *, paused: bool) -> list[str]:
    monkeypatch.setattr(eta.pause_guard, "is_paused", lambda: paused)
    return eta.headline(dict(_PL), None, dict(_TR), None)


#: **この段だけを名指しする印**（2026-09-04 に、赤くなってから置いた）。
#:
#: ここには長らく **素の「止まっています」**と書いてありました。**日本語のありふれた
#: 述語**なので、`headline()` の**別の段**が同じ語を使った日に、そのまま当たります。
#: 実測 2026-09-04、`per_video` の段が
#:
#:     **`per_video` の標本は 2026-08-18 で止まっています（17日前・帯 ≤2本/日 の 12日）。**
#:
#: を出すようになり、**平時に黙る検査**（`test_silent_when_not_paused`）が赤くなりました。
#: **鳴ったのは、この検査が守っているもの（停止の段）とは無関係の行です。**
#:
#: **もっと悪いのは、赤くならなかったほうです。** `_index()` は**最初に当たった行**を
#: 返すので、`test_paused_warning_comes_before_any_date` は
#: 「停止の段が到達日より前か」ではなく「**`止まっています` を含む最初の行**が
#: 到達日より前か」を測っていました。実測では停行が 2行目・`per_video` の段が 6行目 で
#: 順番がたまたま合っていただけで、**段の順が入れ替われば、黙って別の行を測ります。**
#:
#: だから印は**この段にしか出ない字**にします。実測（`headline()` を両方の状態で撃った）:
#:
#:     `**止まっています**`（太字）  止めた時 1行 ／ 平時 **0行**
#:     素の `止まっています`        止めた時 3行 ／ 平時 **1行**  ← 当たってしまう
#:
#: **覆る条件**: 停止の段の見出しの字が変われば、ここも変えること
#: （`scripts/eta.py` の `pause_guard.is_paused()` の枝）。**素の語へは戻さないこと。**
PAUSE_MARK = "**止まっています**"


def _index(lines: list[str], needle: str) -> int:
    """`needle` を含む行の位置。**2行以上に当たったら、その場で落とします。**

    **穴を塞ぐのではなく、穴を作っている側を塞ぐための門です**（2026-09-04）。

    この関数は「最初に当たった行」を返します。順番を測る検査
    （`test_paused_warning_comes_before_any_date`）がそれを使うと、
    **印がありふれた語のとき、黙って別の段を測ります** —— 赤くならないので、
    測る対象が入れ替わったことに誰も気づきません。実際 `PAUSE_MARK` を
    素の「止まっています」で置いていた間、`per_video` の段が同じ語を
    使い出しても、**順番がたまたま合っていたので緑のまま**でした。

    だから **1行に当たることを、印の側の条件にします。** 2行以上に当たったら
    「その印はこの段を名指ししていない」という意味なので、
    **印を細くすること**（段の側の字を薄めないこと）。

    実測（`headline()` を両方の状態で撃った・2026-09-04）:
    `**止まっています**` 1/0行 ／ `月20万の到達予測` 1/1行 ＝ どちらも 1行 以下。
    """
    hits = [i for i, ln in enumerate(lines) if needle in ln]
    assert len(hits) <= 1, (
        f"印 {needle!r} が {len(hits)}行 に当たっています（{hits}）——"
        " **印がこの段を名指ししていません。** 最初の1行だけを返すと、"
        "順番の検査が黙って別の段を測ります。印を細くすること（段の字を薄めないこと）")
    return hits[0] if hits else -1


def test_paused_warning_comes_before_any_date(monkeypatch):
    """**止まっている間は、警告が先。** 日付より後ろに落ちたら、読まれません。"""
    lines = _lines(monkeypatch, paused=True)
    warn = _index(lines, PAUSE_MARK)
    assert warn >= 0, "止まっているのに、そう書いていない"

    # 到達日の行（出ても出なくても）より前にあること
    date_line = _index(lines, "月20万の到達予測")
    assert date_line >= 0, (
        "到達日の行が出ていない —— この検査が素通りになっている（_TR を見直すこと）")
    assert warn < date_line, (
        "警告が到達日より後ろに出ている —— 最初に見た数字が、その回の入口になる")


def test_paused_names_what_was_frozen(monkeypatch):
    """**何を固定してその日付が出たのかを、同じ所に書くこと。**

    ここでの固定は「収益化の審査に受かる確率 1.0」です。止めた理由が
    まさにそこ（いまの構成が審査の除外側に当たる）なので、これを書かずに
    日付だけ出すと、**落ちる目が無い世界の日付**だと読み手に分かりません。
    """
    body = "\n".join(_lines(monkeypatch, paused=True))
    assert "1.0" in body, "受かる確率を固定していることが書かれていない"
    assert "pause_guard" in body, "どこが塞いでいるのかが名指しされていない"
    # **止めた理由は、いま何件 開いているかで言うこと**（2026-08-30 に直した）。
    #     ここには長らく `assert "なりすまし" in body` と書いてありました。
    #     **その語は、止めた日の理由の写しです** —— 同じ日のうちに
    #     `config/channel.yaml` から実務経歴が落ち、`verify` に出口の門が付き、
    #     Resume gate の 1・2 が閉じたので、**印字から消えるのが正しい姿**です。
    #     語を固定していたせいで、直した側が赤くなりました。
    #     **固定するのは語ではなく、「門の状態が同じ所に出ていること」のほう。**
    assert "審査の門" in body, "審査の門が名指しされていない"
    assert "/6" in body or "/6 件" in body, (
        "何件 開いているかが出ていない —— 件数が無いと、閉じても出力が変わりません")
    assert "--lever gate" in body, "この回に引ける腕の名前が出ていない"


def test_silent_when_not_paused(monkeypatch):
    """**平時は黙ること。** 常に出る警告は、読まれない警告になります。"""
    body = "\n".join(_lines(monkeypatch, paused=False))
    assert PAUSE_MARK not in body, (
        "平時なのに停止の段が出ている。**素の『止まっています』では数えないこと** —— "
        "`PAUSE_MARK` の註（別の段が同じ語を使って 2026-09-04 に赤くなった）")
