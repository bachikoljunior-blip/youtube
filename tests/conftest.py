"""**検査は、本物の台帳に書かないこと**（2026-08-17 に踏んで足した）。

`data/alerts.jsonl` の `status_lines` は 8回鳴って当たり0で畳まれ、
`status.py` の「警告の当たり率」にもそう出ていました。実物を数えると、
**8回とも鳴らしたのは `pytest`** です（`alerts._dedupe_token()` はセッションIDなので、
1周につき1行きっかり積まれる）。**`status.py` の出力が中央値の1.5倍を超えたことは
一度もありません。**

    当たり率という計器が、測っていたのは **検査の実行回数** でした。

そして8回目で畳まれた瞬間、**その畳みを見にいく検査そのものが赤くなります**
（`tests/test_status_lines.py::test_the_actual_break_would_have_rung`）。
放っておくと、次の子は毎回**赤い pytest で始まります** ——
8/17 14:1x の申し送り「届いた直後に pytest を叩く手順が要る」の、まさに逆側です。

**これは `src/alerts.py` の「一覧が当たりを含まないまま育つ」の7件目ですが、
原因の向きが新しい**（育て方でも時刻でもなく、**鳴らしている側が検査だった**）。

ここで環境変数を立てるのは、**呼ぶ側に何も書かせないため**です。
「検査では `ledger=` を渡す」を約束にすると、一覧を足した回が必ず片方だけ忘れます
（通算7回踏んだ形）。**`conftest.py` は全部の検査に自動で掛かります。**
"""
from __future__ import annotations
from pathlib import Path

import os
import re

import pytest


# ---- `-k` の網が広すぎる回に、その場で値札を出す（2026-08-28 に踏んで足した）----
#
# **申し送りは、撃つ瞬間には効きません。**
# 08/28 04:5x の回が申し送り⑥でこう名指ししていました ——
#
#   > **検査の `-k` を広げないこと。** `calc` を1語 入れると
#   > `test_calc_sections_still_hit.py` が 63本の calc を `runpy` で回して **8分22秒**。
#   > 実測: `-k "iryohi or furusato or calc or section"` **502秒** に対し
#   > `-k "test_section_depth"` **0.5秒**。
#
# **その申し送りを読んだ回（08/28 06:3x）が、そのまま踏みました。**
# `-k "shougai or shobyo or calc or section or assumption or topic"` を撃って、
# **30分 待っています。** 読んでいて、撃つ瞬間には効いていません。
#
# だから**呼ぶ側に何も約束させず**、`pytest` 自身に言わせます
# （このファイルの冒頭が、まさにその理由で書かれています）。
#
# **止めません。** CI と `fast_tests.py --all` は広い網で正しく、
# 「遅いと知ったうえで撃つ」も正しい判断です。**知らずに撃つのだけを潰します。**
#
# **覆る条件**: この行が出ても2回続けて広い `-k` が撃たれたら、原因は
# 「見えないこと」ではありません（＝ 値札を読んでも選べない）。
# そのときは既定で除外して、`--slow` で戻すこと。
_WIDE_K = {
    # 語: (何に当たるか, 実測)
    "calc": ("test_calc_sections_still_hit.py が 63本の calc を `runpy` で回します",
             "8分22秒"),
    "section": ("同上 ＋ test_section_sweep.py（118件）", "8分10秒"),
    "sweep": ("test_section_sweep.py / test_pair_sweep.py", "8分10秒"),
}


def _bake_is_live() -> str:
    """**いま動画を焼いている最中か。** 焼いていればその1行、いなければ `""`。純関数・API 0単位。

    正本は **`pgrep` と共通の台帳**です（`data/rebake.log` の `tail` は生死の判定に使えません ——
    焼く側の標準出力は 8KB ずつたまるので、生きていても 20分 動かないことがあります）。
    """
    import subprocess                                            # noqa: PLC0415
    for pat in ("src.pipeline --topic", "src.pipeline --script",
                "ahead_sweep.py --rebake-run"):
        try:
            out = subprocess.run(["pgrep", "-f", pat], capture_output=True,
                                 text=True, timeout=10)
        except Exception:                                        # noqa: BLE001
            continue
        pids = [x for x in (out.stdout or "").split() if x.strip()]
        # **`pgrep -f` は、その字を引数に持つ bash の殻にも当たります**（2026-09-05 11:4x に踏んだ）。
        # 実測: 4〜6時間 前に焼きを起こした `/bin/bash -c … src.pipeline --topic …` の殻 4つ
        # （CPU 0%・焼きはとうに終わっている）に当たり、焼いていない回の検査が `nice 19` で走った。
        # 焼いているのは **python の本体**だけなので、`/proc/<pid>/cmdline` の先頭が python の行に絞る。
        pids = [x for x in pids if _is_python(x)]
        if pids:
            return f"`{pat}`（pid {' '.join(pids[:4])}）"
    return ""


def _is_python(pid: str) -> bool:
    """その pid の argv[0] が python か（`/proc` が無い環境では、絞らずに通す）。"""
    try:
        argv0 = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0", 1)[0]
    except OSError:
        return True
    import os as _os                                             # noqa: PLC0415
    return _os.path.basename(argv0.decode("utf-8", "replace")).startswith("python")


def pytest_configure(config):
    """`-k` に網の広い語が入っていたら、**撃つ前に**値札を出す。

    ## **焼いている最中の全件は、自分で優先度を下げます**（2026-09-05 07:0x に足した）

    手順（`docs/spawn_prompt.md`）にはこう書いてあります ——
    **「並行に `python -m pytest -q tests/`（全件）を選ばないこと。この器は 4コア」**。
    実測 2026-09-04 22:0x: 全件を2本 走らせていた 20分 のあいだ、焼き側の CPU は
    **52%** まで落ち、分かりやすさの輪の3周目が **30分 進みませんでした**。

    **書いてあって、起きました。** 2026-09-05 07:00、09:00 公開の枠の焼き直しが
    読み照合の輪を回している最中に、**別の回が全件を2本** 走らせています
    （nice 0・CPU 85% と 79%）。手順は読まれていて、**守る所が無かった**だけです。
    この repo でいちばん多い壊れ方（言っている所と、している所が別）のこの回ぶんです。

    **止めません。** 検査を落とすと、その回が何も出せなくなります。
    **自分の優先度を下げるだけ**にします（`os.nice(19)`）—— 焼きが在るあいだ
    余った CPU は全部もらえるので、**空いている器では1秒も遅くなりません。**

    **覆る条件**: 器のコアが増えて、全件と焼きが同時に走っても焼きが遅れなく
    なったら、この段は要りません（`nproc` を見て畳むこと）。
    `os.nice` が使えない環境（Windows）では黙って飛ばします。
    """
    # ---- 焼きが在れば、自分を後ろへ下げる（**全件のときだけ**）
    if not (getattr(config.option, "keyword", "") or ""):
        live = _bake_is_live()
        if live:
            try:
                import os as _os                                 # noqa: PLC0415
                _os.nice(19)
                print(f"\n[conftest] **いま焼いている最中です** —— {live}。\n"
                      "  `-k` の無い全件なので、**この検査の優先度を下げました**"
                      "（`nice 19`）。\n"
                      "  止めてはいません。焼きが終われば元の速さで走ります。\n"
                      "  次からは `-k` で絞ること（`python scripts/fast_tests.py` が"
                      "その回の触った所から作ります）。\n")
            except Exception:                                    # noqa: BLE001
                print(f"\n[conftest] **いま焼いている最中です** —— {live}。"
                      " 全件は焼きを遅らせます（`-k` で絞ること）。\n")
    expr = getattr(config.option, "keyword", "") or ""
    if not expr:
        return
    words = {w for w in re.split(r"[^0-9A-Za-z_]+", expr) if w}
    hits = sorted(words & set(_WIDE_K))
    if not hits:
        return
    lines = ["",
             "[conftest] **`-k` に網の広い語が入っています。**"
             " 撃つ前に値札を読むこと:"]
    for w in hits:
        what, cost = _WIDE_K[w]
        lines.append(f"    `{w}`  → {what}（**{cost}**）")
    lines += [
        "  **`test_calc_sections_still_hit.py` は表ごとに割ってあります**"
        "（`@pytest.mark.parametrize`）。",
        "  `-k <族名>`（例 `-k shougai`）だけで、その表のぶんが選ばれます ——"
        " 網を広げる必要はありません。",
        "  この回が触った所から `-k` を作るなら: `python scripts/fast_tests.py`",
        "  **承知で撃つならそのまま進みます**（止めていません）。",
        "",
    ]
    print("\n".join(lines))


@pytest.fixture(autouse=True, scope="session")
def _alerts_ledger_to_tmp(tmp_path_factory):
    """`src/alerts.py` の台帳を、この検査だけの場所へ向ける。

    **`src` を import する前に環境変数を立てても間に合いません**
    （`alerts` は import 時に `LEDGER` を決めるので、import 済みなら効かない）。
    だから**モジュールの属性を直接差し替えます。**
    """
    d = tmp_path_factory.mktemp("alerts")
    os.environ["YT_ALERTS_LEDGER"] = str(d / "alerts.jsonl")
    os.environ["YT_ALERTS_RUNS"] = str(d / "runs.jsonl")

    from src import alerts

    keep = (alerts.LEDGER, alerts.RUNS)
    alerts.LEDGER = d / "alerts.jsonl"
    alerts.RUNS = d / "runs.jsonl"
    # **`ship()` の反映も、ここで止めます**（2026-08-20 に足した。理由は同じ）。
    # `tests/test_closes_vocab.py` は `run_marker.ship()` を直接呼ぶので、
    # 反映を既定にしたら**本物の `data/eta.jsonl` に 19行**入りました。
    # **`growth_per_day()` の回帰を汚す向き**なので、規律ではなく機械で外します。
    os.environ["YT_SKIP_REFLECT"] = "1"

    # **`scripts/run_marker.py` の `MARKS` も、ここで tmp へ向けます**
    # （2026-09-05 06:5x に踏んだ。**上の差し替えだけでは届いていませんでした**）。
    #
    # `alerts.RUNS` を tmp へ向けても、`run_marker` は**自分で持っている別の定数**
    # （`MARKS = <repo>/data/runs.jsonl`・67行目）で読み書きします。だから
    # `rm.ship()` / `rm.claim()` / `rm.mark()` を直接呼ぶ検査は、**本物の台帳へ
    # 書いていました。**
    #
    # 実測（この回・`data/runs.jsonl` の窓 504行）: 検査が書いた行は
    # `ship`「ふつうの回」6件・`fix_gate`「test」6件・`verdict_gate`「test」2件。
    # **`src/ledger_holes.py` が毎周 鳴らしている「`lever` が空」は、これが全部です** ——
    # ship 242件 中 空 6件 に対し、検査の行を外すと **236件 中 0件**。
    # あの警告に「書く道を先に直すこと」と書いてあるのが、まさにここ。
    #
    # **意図は最初から在りました** —— `run_marker.py` の 143行目が
    # 「**`MARKS` から辿らないこと。あちらは検査が tmp へ差し替えます**」と
    # 書いています。**書いてあるのに、差し替える側が無かった**だけです。
    #
    # `MARKS` は読みにも書きにも使われる（`recent_claims` / `ship_kind_share` ほか）ので、
    # 片側だけ向けると検査が自分の書いたものを読めなくなります。**両方ここで向きます。**
    #
    # **覆る条件**: `run_marker` が `alerts.RUNS` を見るようになったら、この段落は要りません。
    import scripts.run_marker as _rm

    keep_marks = _rm.MARKS
    _rm.MARKS = d / "runs.jsonl"

    yield
    alerts.LEDGER, alerts.RUNS = keep
    _rm.MARKS = keep_marks


@pytest.fixture()
def same_day_rule_on(monkeypatch):
    """**規則5（当日しか予約しない）が効いている側に固定する。**（2026-09-04 17:4x に足した）

    オーナーが「**目標以外全部外して良いよ**」と言い、
    `house_rule.OWNER_FLOORS_LIFTED = True` が入りました。＝ `same_day_only()` は
    **既定で False** です。**規則は床ではなく既定値になりました。**

    ところが、**掃き（`ahead_sweep.reasons_to_skip`）・池化の keep・暦の警告**は
    「規則5 が効いている間だけ在る手」で、その 13件 の検査は
    **regime を書かずに既定へぶら下がって**いました。床が外れた瞬間に、
    どれも1行目の「規則5 が外れています」で返って赤くなります ——
    **中身は1行も変わっていません。**

    だから、その検査は**自分がどちらの regime を見ているかを言う**こと。
    これを使う file は「**規則5 が効いている間のふるまい**」を見ています。

    **足りていないもの**（次に来た回へ）: 外れている側のふるまいは、
    いま `test_規則5_が外れたら掃かない` と `test_falls_back_when_the_rule_is_lifted`
    の 2件しかありません。**既定になったのは外れている側です。**
    先の日付に置くのが本当に速いかを測る回は、そちらの検査を足すこと。
    """
    from src import house_rule

    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", False)
    monkeypatch.setattr(house_rule, "SAME_DAY_SCHEDULING_ONLY", True)
    return house_rule


@pytest.fixture(autouse=True, scope="session")
def _content_caches_to_tmp(tmp_path_factory):
    """**音とクリップの控えを、この検査だけの場所へ向ける**（2026-09-04 17:2x に踏んで足した）。

    控え（`src/tts.TTS_CACHE_DIR` / `src/renderer.CLIP_CACHE_DIR`）は
    **中身で名前を付けた、器をまたいで残る置き場**です。向けておかないと
    **検査が本物の控えに書き**、次の検査がそれを引きます。

    実測（足した当日）: `tests/test_tts_no_fallback.py::test_default_still_falls_back` が
    赤くなりました。あの検査は `_google` を**わざと落として** open-jtalk へ倒れることを
    見ますが、**前の走りで偽の `_google` が書いた 4バイトの wav** が控えに残っており、
    2度目は控えから返って**落ちる所まで行きません**。
    ＝ **検査の結果が、前の走りの残りかすで変わる**形でした。

    `_alerts_ledger_to_tmp` と同じ理由で、**呼ぶ側に約束させず**モジュールの属性を
    差し替えます（「検査では `cache_dir=` を渡す」を約束にすると、
    控えを足した回が必ず片方だけ忘れます）。
    """
    d = tmp_path_factory.mktemp("content_cache")
    from src import renderer, tts

    keep = (tts.TTS_CACHE_DIR, renderer.CLIP_CACHE_DIR)
    tts.TTS_CACHE_DIR = d / "tts"
    renderer.CLIP_CACHE_DIR = d / "clips"
    yield
    tts.TTS_CACHE_DIR, renderer.CLIP_CACHE_DIR = keep


@pytest.fixture(autouse=True, scope="session")
def _measure_window_dynamic_off():
    """**`measure_window` の動的な窓を、検査のあいだ止める**（2026-08-27 に足した）。

    `WINDOWS` は手で書いた日付なので、`inside()` は純粋な関数でした。
    2026-08-27 に `day_cap` の**切り分けの対照日**を動的に守るようにしたので、
    **`inside()` は本物の予約（`data/uploaded.jsonl`）に依ります。**

    そうすると、**「適当な未来の日」を定数に使っている検査**が、
    たまたまその日が対照日になった回だけ落ちます ——
    実測 2026-08-27: `tests/test_live_slots.py` の5件が `2026-09-02` を
    使っていて、まとめて赤くなりました。**中身は1行も変わっていません。**

    **呼ぶ側に「その日は避けて書いてね」と約束させないこと** ——
    このファイルの冒頭が、まさにその理由で書かれています
    （「一覧を足した回が必ず片方だけ忘れる」通算7回）。

    動的な窓そのものは `tests/test_measure_window_split_day.py` が
    **旗を降ろして**見張ります（あちらは `day_cap` を差し替えて呼びます）。
    """
    from src import measure_window

    keep = measure_window.DISABLE_DYNAMIC
    measure_window.DISABLE_DYNAMIC = True
    yield
    measure_window.DISABLE_DYNAMIC = keep


def source_of(func, name: str | None = None) -> str:
    """`inspect.getsource()` を、**ファイルが読み込み後に動いた回に気づく形で**。

    ## なぜ要るか（2026-08-27 に踏んだ。**実測 2件 赤・2回とも同じ2件**）

    全体の検査は **20分半** かかります。そのあいだ**同じ木で `git merge` を撃つと、
    ファイルが下へずれます** —— 実測 08/27、兄弟の回が `scripts/status.py` に
    **60行**入れ（`e3a1144`）、その挿入点は `print_channel_signals`（1594行）と
    `_channel_main`（1773行）の**上**でした。

    `inspect.getsource()` は **import 時に決まった行番号**を
    **いまのファイル**に当てて切り出します。60行 ずれた回は
    **別の場所の中身**が返り、`assert "..." in src` が落ちます ——
    **コードは1文字も壊れていないのに、赤が2件 出ます。**

        tests/test_status_analytics_lag.py::test_遅れの日数はJSTで数える
        tests/test_status_blind_path.py::test_節の一覧は1か所にしかない

    **単体で撃つと両方 緑**なので、次に来た側は「気まぐれな赤」と読みます。
    そして `scripts/fast_tests.py` は「**押す前に1度は撃つこと** ——
    16分 かかるから誰も撃たない、が赤を何日も残した原因です」と言っています。
    **気まぐれに見える赤は、その1度を撃たない理由になります。**

    ## 何をしているか

    `linecache` を捨ててから切り出し、**先頭が本当にその関数か**を見ます。
    違えば「ファイルが動いた」と**名指しして**落とします ——
    `assert "..." in src` の赤より、そちらのほうが読めます。

    **覆る条件**: 検査の走りが1分を切る（＝ずれる窓が無くなる）なら、
    この包みは要りません。**素の `inspect.getsource` に戻すこと。**
    """
    import inspect
    import linecache

    name = name or getattr(func, "__name__", "?")
    try:
        linecache.checkcache(inspect.getsourcefile(func) or "")
    except Exception:
        pass
    src = inspect.getsource(func)
    # **先頭の行だけを見ること。** 「どこかに `def name` が在る」で見ると鳴りません ——
    #     `inspect.findsource()` は行番号が合わないとき**後ろへ探しに行かず**、
    #     ずれたぶんを**頭に付けたまま**返します。実測（60行 ずらした回）::
    #
    #         'x = 1\n' * 60 + "def target():\n    return ...\n"
    #
    #     `def target` は在るので「在るか」の検査は緑になり、**包みが黙ります**
    #     （2026-08-27、最初にそう書いて `DID NOT RAISE` で落ちました）。
    head = next((ln for ln in src.splitlines() if ln.strip()), "")
    h = head.strip()
    # 飾りが付いた関数は `@...` から始まります。**その回は、下に本体が在るかも見ること**
    #     （`@` だけで通すと、ずれた先がたまたま別の飾りでも黙ります）。
    defined = any(ln.strip().startswith((f"def {name}", f"async def {name}"))
                  for ln in src.splitlines())
    ok = defined and (h.startswith("@") or h.startswith(f"def {name}")
                      or h.startswith(f"async def {name}"))
    if not ok:
        raise AssertionError(
            f"**`{name}` の中身が取れていません。**"
            f" `inspect.getsource()` が返した先頭は {head!r} です。\n"
            "  **この検査は壊れていません** —— 読み込み後にファイルが動いています。"
            "（`git merge` を、走っている検査と同じ木で撃った回に起きます。"
            "実測 2026-08-27: 兄弟が `scripts/status.py` に 60行 入れ、"
            "その下の関数を見る検査が2件 赤くなりました）\n"
            "  **撃ち直すこと。** 木を動かさずに撃てば緑です。"
        )
    return src
