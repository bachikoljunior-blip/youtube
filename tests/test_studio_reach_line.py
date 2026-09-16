"""面（サムネのインプレッション）を `trend` が毎周 印字すること。

**足した理由**（2026-09-16 14:0x・optimizer・Fable 5.1・ultracode）:
`trend` は**再生しか見ていませんでした**。実測の窓（09/05〜09/11）で
**CTR は ×1.50・面は ×0.40**、掛け算した「押された数」は落ちています。
＝ **率が良くなっているのに、量が勝って絶対値が落ちている形**が、どの門にも鳴っていません。
"""
from studio import reporting as R


def row(date, vid, imp, ctr, created="2026-09-13T00:00:00Z", **kw):
    return {"date": date, "video_id": vid, "video_thumbnail_impressions": str(imp),
            "video_thumbnail_impressions_ctr": str(ctr), "_created": created, **kw}


def test_CTRは割合で入っている_百分率ではない():
    """実データの形（回帰）: `631 × 0.0158… = 10` ＝ **割合**。百分率として足すと 100倍 小さく出ます。"""
    out = R.channel_reach([row("20260828", "v", 631, 0.015847860538827259)])
    assert out == [("20260828", 631, 10, pytest_approx(1.5847860538827259))]


def pytest_approx(x, tol=1e-6):
    class _A:
        def __eq__(self, other):
            return abs(other - x) < tol

        def __repr__(self):
            return f"~{x}"
    return _A()


def test_次元で割れた行は足す():
    """1本1日 が 6行 になることが在る（`latest_rows` の註）。足さないと面が小さく出ます。"""
    rows = [row("20260901", "v", 100, 0.02, country_code="JP"),
            row("20260901", "v", 50, 0.04, country_code="US")]
    (_d, imp, clicks, _ctr), = R.channel_reach(rows)
    assert (imp, clicks) == (150, 4)


def test_本をまたいで足す():
    rows = [row("20260901", "a", 100, 0.02), row("20260901", "b", 100, 0.06)]
    (_d, imp, clicks, ctr), = R.channel_reach(rows)
    assert (imp, clicks) == (200, 8)
    assert abs(ctr - 4.0) < 1e-6, "CTR は面で重みを付けた平均（行ごとの % を平均しない）"


def test_訂正版があれば新しいほうを採る():
    rows = [row("20260901", "v", 100, 0.0, created="2026-09-02T00:00:00Z"),
            row("20260901", "v", 300, 0.0, created="2026-09-05T00:00:00Z")]
    (_d, imp, _c, _r), = R.channel_reach(rows)
    assert imp == 300


def test_窓の長さを守る():
    rows = [row(f"2026090{d}", "v", 10, 0.0) for d in range(1, 8)]
    assert len(R.channel_reach(rows, days=3)) == 3
    assert len(R.channel_reach(rows, days=0)) == 7


def test_行が無くても止まらない():
    assert "1行も在りません" in R.reach_line([])


def test_面の口はREACH_STOREから読む():
    """既定の `STORE` には面の欄を持たない報告が混ざっていて、`latest_rows` の鍵
    （日・本。**種類を見ない**）で面の行を押し出します ＝ 表が全部 0 になります。
    **0 は「面が無かった」と同じ字なので、赤は出ません**（2026-09-16 14:0x に踏んだ）。"""
    import inspect
    src = inspect.getsource(R.reach_line)
    assert "REACH_STORE" in src, "既定の store から読むと、面が 0 で出ます"


def test_trendがこの行を印字する():
    import inspect
    from studio import cli
    assert "reach_line" in inspect.getsource(cli.cmd_trend)
