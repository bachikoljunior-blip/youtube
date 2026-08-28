"""**1回で作った本が、全部おなじ配色になっていた。**（2026-08-28 の最適化の回）

## 実測（`data/critique_queue/` の実物の1コマ目・背景色で判定）

    08/27 21:56-21:57  **8本すべて** THEMES[2]
    08/28 08:40        4本すべて THEMES[1]
    08/28 00:59        4本すべて THEMES[0]
    08/27 10:34        4本すべて THEMES[0]
    08/27 08:07        4本すべて THEMES[1]
    08/27 20:58        3本すべて THEMES[4]

## なぜ起きたか（**片方だけが直っている**形）

`src/visuals.theme_for(topic_id, index)` は2つの枝を持ちます:

    index あり  → `THEMES[index % 5]`   **テーマIDを見ません**
    index なし  → テーマIDのハッシュ      （偶然重なりうる、と自分で断っている）

`CLAUDE.md` は「図解の配色は**テーマIDから変わる**ようにしてあり」と書いています ——
それは **index なし**の枝の話で、`src/pipeline.py` は index を渡します。
そして渡していた index は `len(history.posted_topic_ids())` で、
`scripts/batch_build.build_one()` は **`--dry-run`**（作っているあいだ1本も
投稿されない）＋**並列**なので、**この回のあいだ定数**でした。

`theme_for` の docstring は「index を渡すと**連続する回が必ず違う色になる**ので、
こちらを使うこと」と書いてあり、**渡し方のほうが、その保証を外していました。**

## なぜ目標の話なのか

`CLAUDE.md`（YouTube のポリシーの引用）:

> テンプレートを使用して作成されたと思われるコンテンツや、同じチャンネルの動画を
> 続けて数本視聴した後、繰り返しのように感じられる可能性のあるコンテンツ

**収益化されなければ RPM がいくつでも収入はゼロ**なので、これは体裁ではなく
到達可能性の条件です。

## 同じ直しが、日枠 27% も返します

子プロセスは1本ごとに `posted_topic_ids()`（≒**25単位**）を呼んでいました。
窓 08/27 16:00 JST の `data/day_quota.jsonl` で **108回**
（`by` が `history.py:_scan`・間隔の中央値 **2.0秒**）＝ **約2,700単位／日枠 1万**。
**答えが定数なのに、108回 買っていた**わけです。
起点を1回だけ読んで本ごとに +1 すれば、色は散り、読みは 1回に落ちます。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import visuals                                        # noqa: E402


def test_連続する本が同じ色にならない():
    """**これが「同じ絵を続けない」の中身です。**"""
    base = 137
    got = [visuals.theme_for(f"t{i}", base + i)["accent"]
           for i in range(len(visuals.THEMES))]
    assert len(set(got)) == len(visuals.THEMES), f"色が重なっています: {got}"
    for a, b in zip(got, got[1:]):
        assert a != b, f"連続する2本が同じ色です: {a}"


def test_同じ番号を渡すと全部おなじ色になること():
    """**壊れていた側の再現。** この検査が落ちるときは `theme_for` が変わっています
    （index でもテーマIDを混ぜるようになった）—— そのときは
    `batch_build.theme_base()` の「覆る条件」を読むこと。
    """
    got = [visuals.theme_for(f"t{i}", 137)["accent"] for i in range(8)]
    assert len(set(got)) == 1, (
        "`theme_for` が index だけで色を決めなくなりました。"
        "`scripts/batch_build.theme_base()` の覆る条件を読むこと")


def test_build_one_が配色の番号を子プロセスへ渡すこと(monkeypatch):
    """**渡していなければ、子プロセスはチャンネルを読み直します**（1本 25単位）。"""
    import batch_build

    seen: dict = {}

    def fake_run(cmd, timeout, label="", env=None):
        seen["env"] = env
        seen["cmd"] = cmd
        return 1, ""                       # 早く抜ける（生成はしない）

    monkeypatch.setattr(batch_build, "run", fake_run)
    batch_build.build_one({"id": "s-x-1", "calc": "x"}, False, None, 4242)
    assert seen["env"] and seen["env"].get(batch_build._THEME_ENV) == "4242", (
        f"`{batch_build._THEME_ENV}` が子プロセスへ渡っていません: {seen['env']}")


def test_腕と配色を同時に渡せること(monkeypatch):
    """**片方が片方を消さないこと。** `env` は1つの辞書で運ばれます。"""
    import batch_build

    seen: dict = {}

    def fake_run(cmd, timeout, label="", env=None):
        seen["env"] = env
        return 1, ""

    monkeypatch.setattr(batch_build, "run", fake_run)
    batch_build.build_one({"id": "s-x-1", "calc": "x"}, False, False, 7)
    assert seen["env"].get(batch_build._MOTION_ENV) == "0"
    assert seen["env"].get(batch_build._THEME_ENV) == "7"


def test_配色の番号が来た回は_チャンネルを読み直さないこと():
    """**日枠 27% はここに落ちていました。**（`src/pipeline.py`）

    字で見ます —— `main()` は引数と認証が要るので、丸ごとは走らせられません。
    見ているのは「`posted_topic_ids()` の呼び出しが、`THEME_INDEX` を見た
    `if` の**中**にあること」だけです。
    """
    body = (ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    assert 'config.env("THEME_INDEX"' in body, (
        "`src/pipeline.py` が `THEME_INDEX` を読んでいません。"
        "**渡しても効かないなら、子プロセスは毎回 25単位 を買い続けます**")
    head = body.split("history.posted_topic_ids()")[0]
    assert "THEME_INDEX" in head, (
        "`posted_topic_ids()` が `THEME_INDEX` の分岐より前に出ています ——"
        "**分岐の外なら、渡しても読み直します。**")


def test_起点が_APIを1単位も使わないこと(monkeypatch):
    """**並列の手前に、待つものを置かないこと。**

    最初の版は `history.posted_topic_ids()` を呼んでいました。108回 が 1回 には
    なりますが、その1回が並列の手前に立ち、
    `tests/test_batch_parallel.py::test_builds_actually_overlap` が
    **1.1秒 の増**で落ちました（枠切れの窓では 403 まで待つ）。
    起点に要るのは「**回をまたいで違う数**」だけなので、控えの行数で足ります。
    """
    import batch_build

    def boom(*a, **k):                     # noqa: ANN002, ANN003
        raise AssertionError("`theme_base()` が API を叩いています")

    monkeypatch.setattr(batch_build.history, "posted_topic_ids", boom)
    assert batch_build.theme_base() >= 0


def test_1回で作る本の番号がぶつからないこと():
    """`build_one` へ渡す番号が、本ごとに違うこと（字で見る）。"""
    body = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    assert "theme_base()" in body, "起点を1回だけ読む口がありません"
    assert body.count("_base + ") >= 2, (
        "**作りと撃ち直しの両方**で番号をずらすこと ——"
        "片方だけだと、撃ち直した本が1回目の本と同じ色になりえます")
