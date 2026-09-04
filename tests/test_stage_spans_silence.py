"""**「1行も刷っていない空き」を、段の分と並べて言う**（`ahead_sweep.silent_gaps`）。

## なぜ要るか（2026-09-04 21:1x に、走っている焼きの log で実測した）

`[きょうの1本]` は毎周こう印字します ——
「**次に何を速くするかは、勘ではなくこの行で選ぶこと**（この 55〜90分 が、
規則3 の焼き直しが 25回 中 1回 しか本にならない直の理由）」。
その「この行」を作っているのが `stage_spans()` です。

`stage_spans()` は「ある行の時刻 → 次の行の時刻」を**前の行の段**に付けます。
**そこは正しい設計です** —— 黙って働く段が在るので（`test_stage_spans.py` の見本は
`[clarity] 1周目` の 20分後 に次の行が出る形で、それは分かりやすさの輪の本物の仕事）。
**問題は、黙っている別の段の時間も同じ所に乗ることです。**

**実測（09/04 20:02 の焼き・`data/rebake.log`・行間 n=184）**::

    行間の中央値       **1秒**        90%点 **2秒**
    600秒 超の行間     **2件・合計 51.9分**（log 全体 67.0分 ＝ **77%**）
      +12:12  `[tts:google] 82/82`                → `-- 加給（予定 カキュー / …）` 1,557秒
      +39:28  `[tts:google] **控えから 64/82コマ**` → 同じ行（**2周目**）           1,556秒
    本物の行間の最大    **252秒**（`[history]` → `[clarity]` ＝ 模型が考えている時間）

＝ **読み照合の聞き取り（whisper）が 2周・各 25.9分、その間 1行も刷りません。**
画面は それを **音声合成** の分として出していました
（**実物の音声合成は 2.0分** —— 82コマ・うち 64 は控えから）。
**この行を読んだ回は、もう速い段を速くしようとします。**

## 何をしたか（**付け替えていません**）

「長い空きは前の段に付けない」を1度 入れて、`test_stage_spans.py` を2件 赤にしました ——
**「長い空き ＝ 別の段」ではない**からです（上の clarity 20分 が反例）。
log には、どちらか書いてありません。**だから付け替えず、並べて言います。**

**覆る条件**: 黙っている段が自分で刻（`[yomi:hear] 12/82` のような行）を刷るように
なったら、空きは消え、この行も出なくなります。
**`SILENT_GAP_SEC` を上げるのではなく、その段に刻を刷らせること。**
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("_ahs", ROOT / "scripts" / "ahead_sweep.py")
ahs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ahs)


def _line(mm: int, ss: int, body: str) -> str:
    return f"[sweep]   [+{mm:02d}:{ss:02d}] {body}"


#: 実物の形（09/04 20:02 の焼き）。TTS が「終わった」と言った直後に 25.9分 の無音。
_LOG = [_line(0, 0, "[pipeline] 台本を読み込みました"),
        _line(7, 0, "[tts:google] 1/82  1.0s  あ"),
        _line(12, 12, "[tts:google] 82/82  6.14s  その二つを持って"),
        _line(38, 9, "-- 加給（予定 カキュー / 聞いた シタキュー） → noise"),
        _line(39, 28, "[tts:google] **控えから 64/82コマ**"),
        _line(65, 24, "-- 加給（予定 カキュー / 聞いた シタキュー） → noise"),
        _line(66, 11, "[visuals] 13/82 table")]


def test_無音の空きを見つける():
    got = ahs.silent_gaps(_LOG)
    assert len(got) == 2, got
    assert all(24.0 < mins < 27.0 for mins, _, _ in got), got
    # いちばん長いものが先頭（読む側はここだけ見れば足ります）
    assert got[0][0] >= got[1][0]
    assert "tts:google" in got[0][1], got[0]


def test_段の分は付け替えていない():
    """**`stage_spans()` の意味は変えていません。** 空きは今までどおり直前の段に乗ります
    （黙って働く段が在るので、それが正しい）。並べて言うのは `silent_gaps()` の仕事です。"""
    spans = dict(ahs.stage_spans(_LOG))
    assert spans.get("音声合成", 0) > 50, spans


def test_本物の行間は空きに数えない():
    """`[history]` → `[clarity]` の 252秒（模型が考えている時間）は空きではありません。"""
    log = [_line(0, 0, "[history] この窓のチャンネルの読みを再利用しました"),
           _line(4, 12, "[clarity] 1周目: 挙がった 40件/40件"),
           _line(4, 20, "[render] クリップ 1/82")]
    assert ahs.silent_gaps(log) == []


def test_時刻の順に並べ直してから引く():
    """log は**時刻の順とは限りません**（子が 8KB ためて吐く・`REBAKE_LOG` の註）。"""
    順 = [_line(0, 0, "[tts:google] 1/82"), _line(30, 0, "-- 加給"),
          _line(31, 0, "[render] クリップ 1/82")]
    逆 = [順[0], 順[2], 順[1]]
    assert [g[0] for g in ahs.silent_gaps(順)] == [g[0] for g in ahs.silent_gaps(逆)]


def test_門は本物の行間と疑わしい行間の間に在る():
    """**数を勝手に動かさないこと。** 上げるなら、その段に刻を刷らせるのが先です。"""
    assert 252 < ahs.SILENT_GAP_SEC < 1556


def test_画面がその空きを言う():
    """**表だけ出して空きを言わないと、読んだ回は もう速い段を速くします。**"""
    from src import next_slot
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "data").mkdir()
        (root / "data" / "rebake.log").write_text("\n".join(_LOG) + "\n", encoding="utf-8")
        got = next_slot._bake_stage_span_lines(root=root)
    assert any("1行も刷っていない空き" in ln for ln in got), got
    assert any("刻を刷らせる" in ln for ln in got), got
