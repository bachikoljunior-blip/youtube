"""**新しい本 1本 に配られる面（trial impressions）** を毎周 印字すること。

**足した理由**（2026-09-18 11:2x・optimizer・Opus）:
盤には「チャンネル合計の面（日ごと）」（`channel_reach`）と「1本あたり再生」
（`trend.long_per_video`）が在りましたが、**そのあいだの数 ——
「1本 に何回 配られたか」—— を持つ口が 1つ も在りませんでした。**

実測（窓 08/18〜・246本）: **面の中央 12回／押されたの中央 0**（合計 面 14,772 → 押された 266）。
＝ `long_per_video` の「長尺 **1回/本**」は、**面 13回 × CTR 2% ＝ 1回** で説明が付きます。
**謎ではなく、面のほうが縛っている。**

この検査が守るのは 2つ:
  (1) 面の日付は**太平洋時間の日**（`pt_day`）で、JST の日と突き合わせると公開日の面が落ちる。
  (2) 報告が止まっても `reach_line`／`trial_reach_line` は古い台帳を元気に印字する
      ＝ **黙って凍る盤**。`reach_stale_days` が印字に出ること（実測 403 SERVICE_DISABLED で 8日）。
"""
import datetime as dt
import json

from studio import reporting as R
from studio.common import JST


def row(date, vid, imp, ctr=0.02, created="2026-09-13T00:00:00Z", **kw):
    return {"date": date, "video_id": vid, "video_thumbnail_impressions": str(imp),
            "video_thumbnail_impressions_ctr": str(ctr), "_created": created, **kw}


def _pub(tmp_path, monkeypatch, mapping):
    """`publish_days` の出どころ 2つ を tmp へ差し替える（本物の台帳を読ませない）。"""
    up = tmp_path / "uploaded.jsonl"
    up.write_text("".join(json.dumps({"video_id": v, "at": a}) + "\n"
                          for v, a in mapping.items()), encoding="utf-8")
    monkeypatch.setattr(R, "_UPLOADED", up)
    monkeypatch.setattr(R, "_LEDGER_FOR_PUB", tmp_path / "nope.jsonl")


def test_公開日は太平洋時間の日で突き合わせる(tmp_path, monkeypatch):
    """**10:00 JST の公開は前日の報告の行に入ります**（`pt_day` の註）。

    JST の日で突き合わせると、公開当日の面が丸ごと窓の外に落ちます ＝ 面が小さく出る向き。
    """
    _pub(tmp_path, monkeypatch, {"v": "2026-09-01T10:00:00+09:00"})
    assert R.publish_days()["v"] == "20260831"


def test_窓のあいだの面だけを足す(tmp_path, monkeypatch):
    _pub(tmp_path, monkeypatch, {"v": "2026-08-20T19:00:00+09:00"})   # → pt_day 20260820
    rows = [row("20260819", "v", 999),      # 公開より前 ＝ 入れない
            row("20260820", "v", 10),
            row("20260825", "v", 5),
            row("20260901", "v", 777)]      # 窓（7日）の外 ＝ 入れない
    d = R.trial_reach(rows, window_days=7)
    assert d["n"] == 1 and d["imp_sum"] == 15


def test_次元で割れた行は足す(tmp_path, monkeypatch):
    """1本1日 が複数行になる（`latest_rows` の註）。足さないと面が小さく出ます。"""
    _pub(tmp_path, monkeypatch, {"v": "2026-08-20T19:00:00+09:00"})
    rows = [row("20260820", "v", 100, 0.02, country_code="JP"),
            row("20260820", "v", 50, 0.04, country_code="US")]
    d = R.trial_reach(rows)
    assert d["imp_sum"] == 150 and round(d["clicks_sum"], 3) == 4.0


def test_刻の分からない本は分母から落ちる(tmp_path, monkeypatch):
    """**覆る条件 (3)** ＝ `n` は台帳の本数と一致しません。数える側がそれを知っていること。"""
    _pub(tmp_path, monkeypatch, {"v": "2026-08-20T19:00:00+09:00"})
    d = R.trial_reach([row("20260820", "v", 10), row("20260820", "unknown", 999)])
    assert d["n"] == 1


def test_止まった報告は印字に出る():
    """**黙って凍らないこと。** 報告が止まった日数が 3日 以上なら、行にその旨が出る。"""
    old = [row("20260911", "v", 10)]
    days = R.reach_stale_days(old, now=dt.datetime(2026, 9, 18, 11, 0, tzinfo=JST))
    assert days == 5.8          # 期間の終わり 09/12 16:00 JST から数える（下の検査）
    line = R.trial_reach_line(old)
    assert "止まっています" in line


def test_止まりは報告の日の終わりから数える():
    """**日の始まりから数えると 1.5日 大きく出ます** ＝ 門（3日）を偽で鳴らす向き。

    `date` は太平洋時間の日で、期間は **その日の 07:00Z 〜 翌 07:00Z**
    （＝ 20260820 の行は **08/21 16:00 JST** まで埋まっている）。
    """
    rows = [row("20260820", "v", 10)]
    now = dt.datetime(2026, 8, 21, 20, 0, tzinfo=JST)    # 期間の終わりの 4時間後
    assert R.reach_stale_days(rows, now=now) == 0.2
    assert "止まっています" not in R.trial_reach_line(rows, now=now)


def test_数えられる本が無ければ黙って0を返さない():
    """**「0回」と「数えられなかった」を同じ字にしないこと**（この repo で何度も踏んだ族）。"""
    assert R.trial_reach([]) == {"n": 0}
    assert "1本も在りません" in R.trial_reach_line([])
    assert R.trial_reach_short([]) == ""


def test_statusと_trendの両方に行が在る():
    """**固定2 は `status` で最初に答える問い** ＝ `trend` にしか無い行は間に合いません。"""
    src = (R.Path("studio/cli.py")).read_text(encoding="utf-8")
    assert "trial_reach_short()" in src      # status の側
    assert "trial_reach_line()" in src       # trend の側
