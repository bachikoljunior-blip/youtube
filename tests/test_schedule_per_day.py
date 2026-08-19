"""`status.py` の「予約の先」が、**日ごとの本数**を出すこと。

## なぜ要るか（2026-08-19 に踏んだ）

この節は長らく **「控えの最後 09/27（あと 39.3日 / 246本）」の1行だけ**でした。
そこから読めるのは平均 **6.4本/日** です。ところが実物はこうでした:

    08/19=1 08/20=1 08/21=1 08/22=1 08/23=1 08/24=22 08/25=23 08/26=25 08/27=22 08/28=1

**今日から5日が1本/日**で、平均はその形を完全に消しています。
見つけたのはこの回が**手で数え直したから**で、手順のどこにも
「日ごとに数えろ」とは書いてありません。**次の回は同じ穴を踏みます。**

## その日ごとの表が、**0本の日を1日も見ていませんでした**（2026-08-19 17:xx）

直した版は `Counter` の**鍵**を並べていました。鍵は予約のある日しか持たないので、
**0本の日は一覧に存在せず、`thin` に入る道がありません。**
薄い日を名指しするための仕掛けが、**いちばん薄い日だけを構造的に見落とす**形です。

実測（控え345本）: **08/28〜09/03 が 0本 ＝ 7日連続で投稿が途切れる**のに、
名指しされていたのは **09/04 の1日だけ**でした（09/20〜09/26 の1本/日も、
「直近12日」が暦ではなく**予約のある12日**だったため窓の外）。

だから、この検査は**暦を歩いていること**を見ます。
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import status as st  # noqa: E402

JST = timezone(timedelta(hours=9))

# 検査の「今日」。**実時計を使わないこと** —— 使うと日付が変わった朝に落ちます。
TODAY = date(2026, 8, 19)


def _ahead(spec: dict[str, int]) -> list[datetime]:
    """`{"2026-08-20": 3}` → その日に3本ある形の並び（JST の 9時から30分ずつ）。

    **1時間ずつにしないこと** —— 25本置くと 9+24 で `hour must be in 0..23` になります。
    実物の詰め方（30分きざみ・9〜21時 ＝ 1日25枠）と同じにしてあります。
    """
    out = []
    for day, n in spec.items():
        y, m, d = (int(x) for x in day.split("-"))
        for i in range(n):
            out.append((datetime(y, m, d, 9, 0, tzinfo=JST)
                        + timedelta(minutes=30 * i)).astimezone(timezone.utc))
    return sorted(out)


def test_日ごとの本数が出る(capsys):
    st._print_per_day(_ahead({"2026-08-20": 1, "2026-08-21": 3}), today=TODAY)
    out = capsys.readouterr().out
    assert "08/20=1" in out and "08/21=3" in out


def test_薄い日を名指しする(capsys):
    """**平均では見えない形**を、名前で出すこと。"""
    st._print_per_day(_ahead({"2026-08-20": 1, "2026-08-21": 1, "2026-08-22": 25}),
                      today=TODAY)
    out = capsys.readouterr().out
    assert "1日2本以下の日が 2日" in out
    assert "08/20" in out and "08/21" in out
    assert "08/22" not in out.split("1日2本以下")[1]


def test_薄い日が無ければ黙る(capsys):
    st._print_per_day(_ahead({"2026-08-20": 25, "2026-08-21": 25}), today=TODAY)
    out = capsys.readouterr().out
    assert "08/20=25" in out
    assert "1日2本以下" not in out


def test_横に長くしない(capsys):
    """**読まれない行を作らないこと。** 出すのは明日から `PER_DAY_SPAN` 日ぶんだけ。"""
    many = {f"2026-08-{d:02d}": 1 for d in range(20, 32)}
    st._print_per_day(_ahead(many), today=TODAY)
    line = [x for x in capsys.readouterr().out.splitlines() if "日ごと" in x][0]
    assert line.count("=") == st.PER_DAY_SPAN


def test_空でも落ちない(capsys):
    st._print_per_day([], today=TODAY)
    assert capsys.readouterr().out == ""


def test_窓を見ろと言う(capsys):
    """薄い日は「空けてある」ことがあります（M14 の測定の窓）。

    **詰めろとだけ言うと、測定を壊しにいかせます。**
    """
    st._print_per_day(_ahead({"2026-08-20": 1, "2026-08-21": 25}), today=TODAY)
    out = capsys.readouterr().out
    assert "measure_window" in out and "reschedule" in out


# --- ここから下が 2026-08-19 17:xx に足したぶん（**0本の日**）---


def test_予約が1本も無い日を名指しする(capsys):
    """**これが落ちていた1件です。**

    08/20 と 08/24 に本があり、あいだの **08/21〜08/23 は0本**。
    `Counter` の鍵を並べる版では、この3日はそもそも一覧に現れません。
    """
    st._print_per_day(_ahead({"2026-08-20": 25, "2026-08-24": 25}), today=TODAY)
    out = capsys.readouterr().out
    assert "予約が1本も無い日が 3日" in out
    for d in ("08/21", "08/22", "08/23"):
        assert d in out
    assert "08/21=0" in out and "08/23=0" in out


def test_0本の日は薄い日とは別に出す(capsys):
    """**損失の大きさが違います。** 0本は投稿が途切れる日で、1〜2本は薄いだけ。"""
    st._print_per_day(_ahead({"2026-08-20": 1, "2026-08-22": 25}), today=TODAY)
    out = capsys.readouterr().out
    assert "予約が1本も無い日が 1日" in out and "08/21" in out
    assert "1日2本以下の日が 1日" in out
    # 0本の日を「薄い日」の側に混ぜないこと（詰め方が違う）
    assert "08/21" not in out.split("1日2本以下")[1]


def test_0本の日は印字の窓の外まで見る(capsys):
    """**窓を出た所で途切れていても、途切れていることに変わりはありません。**

    実測の穴（08/28〜09/03）は、**明日から数えて9日目**に始まります。
    印字は12日ぶんでも、名指しは**予約の最後まで**歩くこと。
    """
    st._print_per_day(_ahead({"2026-08-20": 25, "2026-09-20": 25}), today=TODAY)
    out = capsys.readouterr().out
    assert "予約が1本も無い日が 30日" in out
    assert "09/03" in out       # 印字の12日（08/20〜08/31）より先の日を名指ししている
    assert "ほか16日" in out    # 名前は14日ぶんで打ち切る（行が読めなくなるので）


def test_薄い日も印字の窓の外まで見る(capsys):
    """実測では 09/20〜09/26 の7日が 1本/日 で、**1日も名指しされていませんでした。**"""
    spec = {"2026-08-20": 25}
    spec.update({f"2026-09-{d:02d}": 1 for d in range(20, 27)})
    st._print_per_day(_ahead(spec), today=TODAY)
    out = capsys.readouterr().out
    assert "1日2本以下の日が 7日" in out
    assert "09/20" in out and "09/26" in out


def test_今日は数えない(capsys):
    """**今日の枠は半分が過ぎています。**

    17時に数えると、9〜13時に公開済みの本は `ahead` に居ません。
    今日を入れると「今日が0本＝断絶」と**毎回鳴ります**（誤検知）。
    """
    st._print_per_day(_ahead({"2026-08-20": 25}), today=TODAY)
    out = capsys.readouterr().out
    assert "08/19" not in out
    assert "予約が1本も無い日" not in out


def test_最後の予約より先は穴と呼ばない(capsys):
    """在庫が尽きた先は「途切れた日」ではなく、**まだ埋めていない日**です。

    ここを穴と数えると、件数が毎回「暦の残り」になって読めなくなります。
    """
    st._print_per_day(_ahead({"2026-08-20": 25, "2026-08-21": 25}), today=TODAY)
    out = capsys.readouterr().out
    assert "予約が1本も無い日" not in out
    assert "08/31=0" in out  # 印字には出る（＝在庫の切れ目が目で見える）


def test_鍵ではなく暦を歩いている(capsys):
    """**この検査が本体です。**

    `per_day_counts()` の鍵は「予約のある日」しか持ちません。
    印字の行の日数が `PER_DAY_SPAN` と一致し、かつ `=0` の欄が出るなら、
    歩いているのは鍵ではなく暦です。
    """
    ahead = _ahead({"2026-08-20": 1, "2026-08-30": 1})
    assert len(st.per_day_counts(ahead)) == 2      # 鍵は2つしかない
    st._print_per_day(ahead, today=TODAY)
    line = [x for x in capsys.readouterr().out.splitlines() if "日ごと" in x][0]
    assert line.count("=") == st.PER_DAY_SPAN      # なのに12日ぶん出る
