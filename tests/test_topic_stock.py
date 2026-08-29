"""在庫は「尽きてから」ではなく「尽きる前に」出す、という検査（2026-08-16）。

## なぜ要るか

前の回の (a2) 問い3 がこう書き残しました ——

> 在庫が0になったのは**この回に分かった**ことで、`status.py` は
> 「手段の台帳 未着手0件」としか言っていませんでした。
> **在庫の底は、尽きてから気づくとその回の `upload` が選べなくなります。**

`status.py` は動画一覧・予約一覧・重なり66組・前提・門の掛け算を出しますが、
**「次に何本作れるか」だけがどこにも出ていませんでした。**

## ここで留めているのは3つ

1. **律速は `pick` の返り**（未投稿テーマ数ではない）。同じ節・同じ calc を
   並べない規則が上から掛かるので、**未投稿7件でも `pick` は6件**になります
2. **未使用の節が0のときは「表を足せ」と名指しする。**
   `topic_forge` は節を掘る道具で、**節を作りません。**
   ここを曖昧にすると、次の回が `topic_forge` を回して空振りします
3. **警告線は掛け算してから置く。** `pick < 8` で M14 の8の段が測れなくなる

**この検査は文言そのものを見ています。** 数字だけ合っていて言葉が変わると、
次の回が「何をすればいいか」を読み取れません（**読み手は毎回入れ替わります**）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import status  # noqa: E402


class _Fake:
    """`topic_forge.survey()` と `batch_build.pick()` を差し替える。"""

    def __init__(self, free: dict[str, list[str]], n_pick: int, total: int = 69):
        self.free = free
        self.n_pick = n_pick
        self.total = total

    def survey(self):
        used = self.total - sum(len(v) for v in self.free.values())
        allsec = dict(self.free)
        # 全体の件数だけ合わせる（見出しの中身はこの検査では見ない）
        allsec = {m: [f"=== {m}{i} ===" for i in range(len(v))]
                  for m, v in self.free.items()}
        allsec.setdefault("_used", [f"=== used{i} ===" for i in range(used)])
        return allsec, self.free, set()

    def pick(self, count, explicit):
        return [{"id": f"t{i}"} for i in range(self.n_pick)]


@pytest.fixture
def patched(monkeypatch):
    def apply(free, n_pick, total=69):
        fake = _Fake(free, n_pick, total)
        import batch_build
        import topic_forge
        monkeypatch.setattr(topic_forge, "survey", fake.survey)
        monkeypatch.setattr(batch_build, "pick", fake.pick)
        return fake
    return apply


def _run(capsys):
    status.print_topic_stock()
    return capsys.readouterr().out


def test_pick_の返りが本数として出る(patched, capsys):
    """**未投稿テーマ数ではなく `pick` の返り**が律速。そこを出していること。"""
    patched({"a": ["=== x ==="]}, n_pick=6)
    out = _run(capsys)
    assert "6本" in out
    assert "pick(8)" in out


def test_pickが0なら_uploadを選べないと言う(patched, capsys):
    """**この回に upload が選べない**ことは、いちばん強く出す。

    尽きた回が `upload` を選び、生成に入ってから空振りすると、
    その回の成果がゼロになります（1周41分のうち十数分）。
    """
    patched({}, n_pick=0)
    out = _run(capsys)
    assert "`upload` を選べません" in out


def test_pickが8を割ったらM14の段が作れないと言う(patched, capsys):
    """しきい値は掛け算してから置く。**8 は M14 の段**（1日8本）です。"""
    patched({"a": ["=== x ==="] * 6}, n_pick=7)
    out = _run(capsys)
    assert "8本の日" in out


def test_pickが8以上なら警告を出さない(patched, capsys):
    """**警告が毎回出ていたら、警告ではありません。**"""
    patched({"a": ["=== x ==="] * 6}, n_pick=8)
    out = _run(capsys)
    assert "[!]" not in out


def test_未使用の節が0なら_calcに表を足せと名指しする(patched, capsys):
    """**`topic_forge` は節を作りません。**

    ここを「テーマを増やせ」で終えると、次の回が `topic_forge` を回して
    0件を受け取ります（8/16 03:0x が実際にそうなった）。
    """
    patched({}, n_pick=6)
    out = _run(capsys)
    assert "src/calc/" in out
    assert "節そのものは作りません" in out
    # **`topic_forge` を打つ手として案内しないこと**（回しても増えない）
    assert "いま打つ手" not in out


def test_未使用の節が残り少ないと_尽きる前に警告する(patched, capsys):
    """**0 になってからでは遅い。** 5件を切ったら言う。"""
    patched({"a": ["=== x ===", "=== y ==="]}, n_pick=6)
    out = _run(capsys)
    assert "残り2件" in out
    assert "尽きます" in out


def test_余地があるときは_topic_forgeを打つ手として出す(patched, capsys):
    """節が余っていて `pick` が細いなら、**足すのではなく掘るのが先**。"""
    patched({"a": ["=== x ==="] * 9}, n_pick=6)
    out = _run(capsys)
    assert "topic_forge.py" in out
    assert "いま打つ手" in out


def test_余地が十分あるときは_どのcalcに余っているかを出す(patched, capsys):
    """**どこを掘るかが分からないと、掘りに行けません。**"""
    patched({"a": ["=== x ==="] * 3, "b": ["=== y ==="] * 7}, n_pick=8)
    out = _run(capsys)
    assert "b:7" in out
    assert "a:3" in out
    # 多い順（掘る先を先に見せる）
    assert out.index("b:7") < out.index("a:3")


def test_道具が落ちても_status全体を止めない(monkeypatch, capsys):
    """**在庫が読めないことは、状態表示をやめる理由になりません。**

    `topic_forge.survey()` は `src/calc/*` を1本ずつ子プロセスで走らせるので、
    **calc を1本壊すと、ここが落ちます。** そのとき登録者も予約も
    重なりも見えなくなるのは、明らかに割に合いません。
    """
    import topic_forge
    monkeypatch.setattr(topic_forge, "survey",
                        lambda: (_ for _ in ()).throw(SystemExit("calc が落ちました")))
    out = _run(capsys)
    assert "読めませんでした" in out
    assert "calc が落ちました" in out


def test_未使用の節が0でも_長尺の上限は族の数で別に出る(patched, capsys, monkeypatch):
    """**「未使用0件 ＝ 余地がありません」は、長尺については誤りです**（2026-08-26）。

    長尺の上限は節ではなく**族の数**で決まります ——
    `batch_build` の `--per-calc 2` と `_drop_queue_tail_calcs` が、
    どちらも**族の単位**で効くためです。だから
    **未使用の節が0件でも、族を1つ増やせば +2本 になります。**

    実測（この検査を書いた回）: 未使用0件・長尺向けのテーマ 30件 / 族 11
    → 7日ぶんで取れるのは 22本。`jutaku` に節を1つ足して `--long` で forge したら
    **族 12・上限 24本**。**同じ族に節を足していたら 0本 でした。**

    そして **その数字は `topic_forge --list` を撃った回にしか見えませんでした** ——
    1周の手順は `status.py` を毎回撃たせるのに、`--list` はどこにも書いていません。
    **毎回読むほうに出ていなければ、無いのと同じです。**
    """
    patched({}, n_pick=6)
    called = []
    import topic_forge
    monkeypatch.setattr(topic_forge, "print_long_stock",
                        lambda: called.append(True))
    out = _run(capsys)
    # **0件を「余地がありません」と言い切らないこと**（ショートの側の話だと断る）
    assert "テーマを増やす余地がありません" not in out
    assert "ショートの側の話" in out
    # **長尺の上限は、毎回ここから出すこと**（数え方は写さず、道具を呼ぶ）
    assert called == [True]


def test_長尺の在庫が読めなくても_在庫の節を止めない(patched, capsys, monkeypatch):
    """**長尺の数字が読めないことは、在庫表示をやめる理由になりません。**"""
    patched({"a": ["=== x ==="] * 9}, n_pick=6)
    import topic_forge
    monkeypatch.setattr(
        topic_forge, "print_long_stock",
        lambda: (_ for _ in ()).throw(RuntimeError("控えが壊れています")))
    out = _run(capsys)
    assert "長尺の在庫が読めませんでした" in out
    assert "控えが壊れています" in out
    assert "`pick(8)` が返す本数" in out
