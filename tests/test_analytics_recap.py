"""`status._print_analytics_recap` の検査（2026-08-16）。

**なぜ検査するか。** この節の値打ちは「末尾にあること」と「落ちないこと」の2つだけです。
アナリティクスが1つでも欠けたときに**例外で落ちると、その回は末尾ごと消えます** ——
そうなると、この節を足す前（＝真ん中を読み飛ばす）と同じ状態に戻ります。

**故障注入つき。** 欠けた鍵・0再生・値そのものが無い回を通します。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import status  # noqa: E402


def _run(values: dict, capsys) -> str:
    import src.scan as scan
    orig = scan._previous
    scan._previous = lambda: {"values": values}
    try:
        status._print_analytics_recap()
    finally:
        scan._previous = orig
    return capsys.readouterr().out


FULL = {
    "合計.views": 13015,
    "合計.engagedViews": 4677,
    "合計.shares": 3,
    "合計.comments": 0,
    "合計.videosAddedToPlaylists": 3,
    "合計.redViews": 2975,
    "insightPlaybackLocationType.SHORTS_FEED": 12928,
    "insightPlaybackLocationType.WATCH": 12,
}


def test_実測の値がそのまま出る(capsys) -> None:
    out = _run(FULL, capsys)
    assert "engaged 35.9%" in out, out          # 4677 / 13015
    assert "視聴ページ 12再生（0.09%）" in out, out
    assert "共有 3 / コメント 0 / 保存 3" in out, out
    assert "Premium 再生 2975（23%）" in out, out


def test_鍵が欠けても落ちない(capsys) -> None:
    """**故障注入。** views 以外を全部落とす。

    落ちると末尾ごと消え、真ん中を読み飛ばす状態に戻ります。
    """
    out = _run({"合計.views": 100}, capsys)
    assert "[!]" not in out, out
    assert "engaged 0.0%" in out, out


def test_再生0や値なしでは黙る(capsys) -> None:
    """0除算で落とさない。**黙るのは正しい**（割る分母が無い）。"""
    assert _run({"合計.views": 0}, capsys).strip() == ""
    assert _run({}, capsys).strip() == ""


def test_Premiumが無い回はその行を出さない(capsys) -> None:
    v = dict(FULL)
    del v["合計.redViews"]
    out = _run(v, capsys)
    assert "Premium" not in out, out
    assert "engaged" in out, out


def test_節はmainの最後に呼ばれている() -> None:
    """**位置がこの節の本体です。** 呼び出しが `return 0` の直前にあること。"""
    src = Path(status.__file__).read_text(encoding="utf-8")
    tail = src.split("def _print_analytics_recap")[0]
    call = tail.rindex("_print_analytics_recap()")
    ret = tail.rindex("return 0")
    assert call < ret, "要点の節が main の最後に呼ばれていません"
    assert "\n    return 0" == tail[ret - 5:ret + 8], tail[ret - 20:ret + 10]
