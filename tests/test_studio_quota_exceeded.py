"""日枠を使い切った周と、口が壊れた周を**別のものとして読む**（2026-09-16 04:2x）。

**踏んだ形**: `channel` を書くのは `status` だけで、`status` は日枠が尽きた周には撃てない。
だから `stall.mouth_gap` が立ち、その潰し手が **`YT_REFRESH_TOKEN` の取り直し ＝ オーナーの手**を
名指していた。**口は壊れていないのに。** オーナーへの訊きは数が限られているので、偽の 1件 の値段が高い。

**陽性対照 3つ**:
 (1) `quota_exceeded` の行を外すと、潰し手がオーナーの手へ戻る。
 (2) その行が **前の日枠の窓**（16:00 より前）なら、いまの周には効かない。
 (3) その行が `channel` より**古い**なら効かない（＝ そのあと口は開いている）。
 (4) `owner` は `True` のまま ＝ **3分 の再実行に入れない**（日枠は 3分 では戻らない・16:00 JST まで 12時間）。
"""
import datetime as dt

from studio import budget, cli, stall
from studio.common import JST


def _t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=JST)


class _HttpErrorish(Exception):
    def __init__(self, msg, details=None):
        super().__init__(msg)
        self.error_details = details or []


def test_quotaExceeded_を_reason_で引く():
    e = _HttpErrorish("<HttpError 403 ...>", [{"reason": "quotaExceeded", "domain": "youtube.quota"}])
    assert cli.quota_exceeded(e)


def test_quotaExceeded_を_文言でも引く():
    assert cli.quota_exceeded(Exception(
        'The request cannot be completed because you have exceeded your quota'))


def test_口が拒まれた例外は日枠ではない():
    assert not cli.quota_exceeded(Exception("invalid_grant: Bad Request"))
    assert cli.token_rejected(Exception("invalid_grant: Bad Request"))


def test_別の403は日枠ではない():
    e = _HttpErrorish("<HttpError 403 ...>", [{"reason": "forbidden"}])
    assert not cli.quota_exceeded(e)


def _rows(qx_at=None, ch_at="2026-09-16T01:47:00+09:00"):
    rows = [{"at": ch_at, "event": "channel", "id": "UCx"}]
    # 日枠を 8,979 ぶん使った形（予約 5本）
    rows += [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"} for _ in range(5)]
    if qx_at:
        rows.append({"at": qx_at, "event": "quota_exceeded", "id": "-"})
    return rows


def _mouth(rows, now):
    got = [s for s in stall.signs(rows, rounds=[], now=now) if s["code"] == "mouth_gap"]
    return got[0] if got else None


def test_日枠を使い切った周はオーナーの手を名指さない():
    m = _mouth(_rows(qx_at="2026-09-16T03:34:00+09:00"), _t("2026-09-16T04:00:00"))
    assert m is not None                     # 印そのものは消さない（口は実際に閉じている）
    # `owner` は `True` のまま ＝ **3分 の再実行に入れない**（日枠は 3分 では戻らない）。
    # **「オーナーに訊きを置くか」を持つのは `dry` のほう**（`stall.signs` の註）。
    assert m["owner"] is True
    assert m["dry"] is True
    assert "口は壊れていません" in m["crush"]
    assert "オーナーの手は要りません" in m["crush"]
    assert "16:00 JST" in m["crush"]
    assert "owner_ask" not in m["crush"]


def test_日枠の行が無ければオーナーの手へ戻る():
    """**陽性対照 1**: これが落ちたら、日枠の枝が常に真になっている。"""
    m = _mouth(_rows(), _t("2026-09-16T04:00:00"))
    assert m is not None
    assert m["dry"] is False
    assert "owner_ask" in m["crush"]


def test_前の日枠の窓の行は効かない():
    """**陽性対照 2**: 16:00 JST より前の行 ＝ もう戻った枠のもの。"""
    m = _mouth(_rows(qx_at="2026-09-15T15:00:00+09:00"), _t("2026-09-16T04:00:00"))
    assert m is not None and m["dry"] is False and "owner_ask" in m["crush"]


def test_channelより古い行は効かない():
    """**陽性対照 3**: そのあと `status` が通って `channel` を書けている ＝ 口も枠も生きていた。"""
    m = _mouth(_rows(qx_at="2026-09-15T23:00:00+09:00", ch_at="2026-09-16T01:47:00+09:00"),
               _t("2026-09-16T04:00:00"))
    assert m is not None and m["dry"] is False and "owner_ask" in m["crush"]


def test_日枠の残りでは読まない():
    """`budget.spent` は**過小** —— 1,021単位 余っていると言った周に `status` は 403 だった。

    ＝ **残りが取り分を上回っていても**、落ちた行が在れば `dry` になること。
    """
    rows = _rows(qx_at="2026-09-16T03:34:00+09:00")
    assert budget.spent(rows, _t("2026-09-16T04:00:00"))["left"] > budget.RESERVE
    assert _mouth(rows, _t("2026-09-16T04:00:00"))["dry"] is True


def test_間隔の行も訊きを置くと言わない():
    """`crush` が「オーナーの手は要りません」と言う隣で、`why` が「訊きを置く」と言わないこと。

    **陽性対照 4**: `dry` の行を外すと、`why` は「訊きを置く」へ戻る。
    """
    st = stall.state(_rows(qx_at="2026-09-16T03:34:00+09:00"), rounds=[], now=_t("2026-09-16T04:00:00"))
    assert "訊きは置かない" in st["why"] and "16:00 JST" in st["why"]
    st2 = stall.state(_rows(), rounds=[], now=_t("2026-09-16T04:00:00"))
    assert "訊きを置く" in st2["why"]
