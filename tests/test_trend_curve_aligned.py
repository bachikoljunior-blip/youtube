"""維持率カーブを**同じ秒**で読む口（2026-09-11 11:4x・hourly・Opus）。

`analytics_curve` の刻は**割合**なので、尺の違う本を同じ刻で比べると**違う秒**を比べます
（旧作り 25〜32秒・新しい作り 90〜93秒 ＝ `10%` は 旧 3秒 対 新 9秒）。
ここで守るのは 3つ:

  1. 尺が台帳から出ること（`analytics_video` の `avg_seconds / avg_percent`）
  2. 同じ秒に直すと**向きが逆**になること（新が上）
  3. **印字が §3 の (1) を書き換えろと言わないこと** —— `lint` の「年に」「60秒」と同じ族で、
     **書き手は印字に従う**ので、印字が古ければ同じ本がまた出ます。

陽性対照つき（**壊したら落ちる**まで撃つ・METHOD §5 の教訓の形 3つ目）。
"""
import pytest

from studio import trend


def _curve(vid, studio, marks, views=200):
    return {"event": "analytics_curve", "id": vid, "at": "2026-09-10T16:17:55+09:00",
            "studio": studio, "views": views, "marks": marks}


def _vid(vid, studio, sec, pct, views=200):
    return {"event": "analytics_video", "id": vid, "at": "2026-09-10T16:18:09+09:00",
            "studio": studio, "views": views, "avg_seconds": sec, "avg_percent": pct}


OLD = {"p10": 1.06, "p25": 0.65, "p50": 0.45, "p75": 0.22, "p95": 0.14}
NEW = {"p10": 0.81, "p25": 0.53, "p50": 0.48, "p75": 0.36, "p95": 0.22}


def _rows():
    # 旧 30秒・新 90秒（実測の帯: 旧 25.1〜32.5秒／新 90.3〜92.7秒）
    return [_curve("old1", False, OLD), _vid("old1", False, 15, 50.0),
            _curve("new1", True, NEW), _vid("new1", True, 45, 50.0)]


def test_尺は台帳から出る():
    d = trend.curve_seconds(_rows())
    assert d == {"old1": 30.0, "new1": 90.0}


def test_平均視聴率が0の本は尺を出さない():
    rows = _rows() + [_curve("z", False, OLD), _vid("z", False, 0, 0.0)]
    assert "z" not in trend.curve_seconds(rows)


def test_同じ刻は同じ秒ではない():
    d = trend.curve_seconds(_rows())
    assert d["old1"] * 0.10 == pytest.approx(3.0)    # 旧の 10% は 3秒
    assert d["new1"] * 0.10 == pytest.approx(9.0)    # 新の 10% は 9秒


def test_挟めない秒はNone():
    assert trend.curve_at(OLD, 30.0, 1.0) is None    # いちばん手前の刻より前
    assert trend.curve_at(OLD, 30.0, 29.9) is None   # いちばん後ろの刻より後
    assert trend.curve_at(OLD, 0, 3.0) is None       # 尺が無い


def test_刻そのものの秒は刻の値を返す():
    assert trend.curve_at(OLD, 30.0, 3.0) == pytest.approx(1.06)
    assert trend.curve_at(NEW, 90.0, 22.5) == pytest.approx(0.53)


def test_読む秒は新の刻に寄せる():
    assert trend.curve_secs(_rows()) == (9.0, 22.5)


def test_同じ秒で読むと新が上():
    al = trend.curve_aligned(_rows())
    at9 = next(r for r in al if r["sec"] == 9.0)
    assert at9["new"] == [pytest.approx(0.81)]       # 新は実測の刻
    assert at9["old"][0] < 0.81                      # 旧は挟み ＝ 下
    at22 = next(r for r in al if r["sec"] == 22.5)
    assert min(at22["new"]) > max(at22["old"])       # 束が重ならない側


def test_印字は3秒のループと尺を名指しする():
    s = trend.curve_line(_rows())
    assert "ループ" in s and "同じ刻は同じ秒ではありません" in s
    assert "作りではありません" in s


def test_印字は出だしを書き換えろと言わない():
    """**陽性対照の逆**: 古い印字（「いちばん離れるのは 10% ＝ §3 の (1) の当のもの」）へ
    戻ったら、この検査が落ちること。"""
    s = trend.curve_line(_rows())
    assert "§3 の (1) を、この数で書き換えないこと" in s
    assert "いちばん離れるのは 10%" not in s
    assert "(1)（1文目で誰に向けた何の話かを言う）の当のもの" not in s


def test_尺が無ければ同じ秒では読めないと言う():
    rows = [_curve("old1", False, OLD), _curve("new1", True, NEW)]   # `analytics_video` 無し
    assert trend.curve_aligned(rows) == []
    assert "同じ秒では読めていません" in trend.curve_line(rows)


def test_陽性対照_尺を取り違えると向きが消える():
    """新を旧と同じ 30秒 だと読み違えたら（＝ 尺を混ぜたら）、9秒 で新が旧の下に来ること。
    これが落ちるなら、上の「向きが逆」は尺ではなく別の物を見ています。"""
    rows = [_curve("old1", False, OLD), _vid("old1", False, 15, 50.0),
            _curve("new1", True, NEW), _vid("new1", True, 15, 50.0)]   # 新も 30秒 に見せる
    at9 = next(r for r in trend.curve_aligned(rows, (9.0,)) if r["sec"] == 9.0)
    assert max(at9["new"]) < max(at9["old"])


def test_陽性対照_弦は上に外す():
    """`curve_at` の註（維持率カーブは下に凸 ＝ 弦はカーブの上）。
    刻を 3つ に増やした側と比べて、挟みのほうが**大きい**こと。"""
    coarse = {"p10": 0.90, "p50": 0.30, "p95": 0.10}
    fine = dict(coarse, p25=0.45)          # 実測の刻が 25% にも在る本
    assert trend.curve_at(coarse, 100.0, 25.0) > trend.curve_at(fine, 100.0, 25.0)
