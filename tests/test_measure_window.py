"""測定の窓（`src/measure_window.py`）が、**予約を書く道の全部**に効いていること。

## この検査が在る理由（2026-08-18）

窓そのものは 2026-08-15 からありましたが、門は `scripts/batch_build.py` の
中だけにあり、しかも `if args.date:` の中でした。実物を数えると、
**予約時刻を書ける道は4つあって、止まるのは1つ**でした:

    batch_build.py --date <窓の中>     止まる
    batch_build.py --hour 11           **素通り**
    upload_only.py <題> "" 11          **素通り**
    reschedule.py --move <id> <窓の中>  **素通り**

**素通りしても何も起きません**（成功して、静かに測定が壊れる）。
だから下の `test_全部の予約経路が窓の門を通る` は、**新しい道が増えたときに
落ちる形**にしてあります —— `publishAt` を書くファイルを実物から数えて、
そのファイルが `measure_window` を参照しているかを見ます。
**語彙を手で並べないこと**（このリポジトリでは、一覧を手で持つと
次に足した回が必ず書き忘れます。通算8件）。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import measure_window, uploader  # noqa: E402

JST = timezone(timedelta(hours=9))
WIN = ("2026-08-16", "2026-08-23")


# --- inside / check ------------------------------------------------------

@pytest.mark.parametrize("day", ["2026-08-16", "2026-08-20", "2026-08-23"])
def test_窓の中は_inside_が_True(day):
    assert measure_window.inside(day, WIN) is True


@pytest.mark.parametrize("day", ["2026-08-15", "2026-08-24", "2026-09-01"])
def test_窓の外は_inside_が_False(day):
    assert measure_window.inside(day, WIN) is False


def test_空の窓はどの日にも当たらない():
    """窓を終わらせる手は `WINDOW = ("", "")` の1行だけ。

    **呼ぶ側に `if WINDOW:` を書かせない。** 書かせると、次に呼ぶ側を
    足した回が書き忘れて、**空の窓が全部の日に当たります**（文字列比較で
    `"" <= 任意 <= ""` は False ですが、片側だけ空にされると崩れます）。
    """
    for day in ["2026-08-20", "2026-01-01", "2099-12-31"]:
        assert measure_window.inside(day, ("", "")) is False
    measure_window.check("2026-08-20", window=("", ""))   # 上がらない


def test_窓の中を名指しすると止まる():
    with pytest.raises(SystemExit) as e:
        measure_window.check("2026-08-20", tool="てすと", window=WIN)
    assert "M14" in str(e.value)
    assert "てすと" in str(e.value)


def test_force_なら通すが黙らない(capsys):
    measure_window.check("2026-08-20", force=True, tool="てすと", window=WIN)
    out = capsys.readouterr().out
    assert "M14" in out and "JOURNAL" in out


def test_実物の窓は文字列2つで両端を含む():
    lo, hi = measure_window.WINDOW
    for v in (lo, hi):
        assert v == "" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", v), v


# --- 構造: 予約を書く道が全部、門を通っているか --------------------------

def _publish_at_writers() -> list[Path]:
    """`publishAt` を**書いている**ファイルを実物から数える（検査自身は除く）。"""
    hits = []
    for path in sorted(ROOT.glob("**/*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r'publishAt"\]\s*=', text):
            hits.append(path)
    return hits


def test_publishAt_を書くファイルが実際に見つかる():
    """**0件で緑になる検査を作らないこと。**

    `docs/trigger_main.md` §4 の「足した検査は緑のまま0件で通る」の形です。
    """
    assert len(_publish_at_writers()) >= 2


def test_全部の予約経路が窓の門を通る():
    """`publishAt` を書くファイルは、`measure_window` を参照していること。

    **新しい予約経路を足した回が、ここで落ちます。** 一覧を手で持たず、
    実物（`publishAt` を書いている字）から数えているのがこの検査の要点です。
    """
    抜け = [p.relative_to(ROOT).as_posix() for p in _publish_at_writers()
            if "measure_window" not in p.read_text(encoding="utf-8")]
    assert not 抜け, (
        f"予約時刻を書くのに窓の門を通っていない: {抜け}\n"
        "  `from src import measure_window` を入れて、"
        "日を名指しするなら check()、自動で探すなら inside() で飛ばすこと。"
    )


# --- next_publish_at: 2つの道で止め方が違う ------------------------------

def _in_window_day() -> str:
    """窓の中で、いまより先の日を1つ。窓が過ぎていたら検査を飛ばす。"""
    lo, hi = measure_window.WINDOW
    if not lo:
        pytest.skip("窓は終わっています（WINDOW が空）")
    day = datetime.now(JST) + timedelta(days=1)
    while day.strftime("%Y-%m-%d") <= hi:
        if measure_window.inside(day.strftime("%Y-%m-%d")):
            return day.strftime("%Y-%m-%d")
        day += timedelta(days=1)
    pytest.skip("窓は過ぎています")


def test_日を釘づけして窓の中を指すと上がる():
    with pytest.raises(SystemExit):
        uploader.next_publish_at(9, 0, date_jst=_in_window_day())


def test_釘づけでも_force_window_なら通る():
    day = _in_window_day()
    got = uploader.next_publish_at(9, 0, date_jst=day, force_window=True)
    assert got.endswith("Z")


def test_自動で探す道は窓を飛ばす_止まらない(capsys):
    """**例外を上げないこと。** ここで止めると、窓のあいだ投稿が丸ごと止まります。

    `taken` を空にすると、既定では「明日の hour」が返ります。その明日が
    窓の中なら、返り値は**窓より後**でなければいけません。
    """
    day = _in_window_day()
    got = uploader.next_publish_at(11, 0, taken=set())
    got_jst = datetime.strptime(got, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc).astimezone(JST).strftime("%Y-%m-%d")
    assert not measure_window.inside(got_jst), got_jst
    assert got_jst > day
    assert "飛ばしました" in capsys.readouterr().out


def test_門を外せば今までどおり最初の枠が返る():
    """窓の門が、窓と関係ない所まで動かしていないこと（**副作用の検査**）。

    **「明日」と書かないこと。** `next_publish_at` が翌日へ送るのは
    「その時刻が 20分以内に来る」ときだけなので、**走らせる時刻で答えが
    変わります**（11:00 の検査を朝に回せば今日、昼に回せば明日）。
    最初に書いた版はそこで落ちました。
    """
    now = datetime.now(JST)
    want = now.replace(hour=11, minute=0, second=0, microsecond=0)
    if want <= now + timedelta(minutes=20):
        want += timedelta(days=1)
    got = uploader.next_publish_at(11, 0, taken=set(), force_window=True)
    got_jst = datetime.strptime(got, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc).astimezone(JST).strftime("%Y-%m-%d")
    assert got_jst == want.strftime("%Y-%m-%d")


# --- reschedule.py --move ------------------------------------------------

def test_reschedule_は_API_を呼ぶ前に止まる(monkeypatch):
    """**単位を捨てないこと。** 窓の門は認証も枠も要らないので、先に見ます。

    `_service()` が呼ばれたら落ちるようにしておいて、それでも
    `SystemExit`（窓の門）になることを見ています。
    """
    import reschedule

    def 呼ばれたら困る():
        raise AssertionError("API を呼ぶ前に止まっていない")

    monkeypatch.setattr(reschedule.uploader, "_service", 呼ばれたら困る)
    with pytest.raises(SystemExit) as e:
        reschedule.main(["--move", "abc123", f"{_in_window_day()}T09:00"])
    assert "M14" in str(e.value)


def test_過去の日は_窓ではなく過去として断られる():
    """**直し方が違うものに、同じ札を付けないこと**（2026-08-18 に踏んだ）。

    窓の門を `next_publish_at` の先頭に置いたら、`--date <昨日>` が
    「M14 の窓です」と答えました（昨日はたまたま窓の中）。呼ぶ側に要るのは
    「その日は過ぎている」で、窓の話ではありません。
    """
    昨日 = (datetime.now(JST) - timedelta(days=1)).strftime("%Y-%m-%d")
    with pytest.raises(ValueError):
        uploader.next_publish_at(10, 0, taken=set(), date_jst=昨日)


def test_形の誤りも_窓より先に断られる():
    """**例を差し替えた**（2026-08-19）。`"8/20"` はもう「形の誤り」ではありません。

    `batch_build.py --date 08/23` が**9本の生成（約20分）を全部やってから**
    予約の段で9本とも落ちたので、`MM/DD` を読めるようにしました
    （`uploader.normalize_date_jst`。**本体は入口で通すこと**のほう）。
    この検査が見ているのは**順番**（形の誤りは窓の門より先）なので、
    **消さずに、いまでも読めない形へ差し替えます。**
    """
    for bad in ("8月20日", "20/8/2026", "あした"):
        with pytest.raises(ValueError):
            uploader.next_publish_at(10, 0, taken=set(), date_jst=bad)


# --- 窓の一覧（2026-08-21 22:4x） ----------------------------------------
#
# **区間1本では足りませんでした。** 実物は離れた2日（08/22 と 09/10）で、
# 区間で持つと**あいだの18日まで窓**になります。そして `WINDOW` は
# 2026-08-19 に空にされ、**2つの測定日が機械の外**に出ていました ——
# 守っていたのは `reschedule.py --spread --since 2026-08-23` の
# `--since` を毎回手で打つ記憶だけです。

_TEST_WINDOWS = (
    {"from": "2026-08-22", "to": "2026-08-22", "until": "2026-09-05",
     "label": "M14", "why": "3日目"},
    {"from": "2026-09-10", "to": "2026-09-10", "until": "2026-09-16",
     "label": "M14", "why": "上から測り直す"},
)


@pytest.fixture()
def 二つの窓(monkeypatch):
    monkeypatch.setattr(measure_window, "WINDOWS", _TEST_WINDOWS)
    return _TEST_WINDOWS


def test_離れた2つの窓が両方とも当たる(二つの窓):
    assert measure_window.inside("2026-08-22", today="2026-08-21") is True
    assert measure_window.inside("2026-09-10", today="2026-08-21") is True


def test_窓と窓のあいだは窓ではない(二つの窓):
    """**ここが区間で持っていたときの落ち方です。** 18日ぶん止まります。"""
    for day in ["2026-08-23", "2026-09-01", "2026-09-09"]:
        assert measure_window.inside(day, today="2026-08-21") is False, day


def test_until_を過ぎた窓は自分で外れる(二つの窓):
    """**手で消す作業を残さない。** 消し忘れた窓は静かに予約を追い出します。"""
    assert measure_window.inside("2026-08-22", today="2026-09-05") is True
    assert measure_window.inside("2026-08-22", today="2026-09-06") is False
    assert measure_window.inside("2026-09-10", today="2026-09-06") is True
    assert measure_window.active(today="2026-09-17") == ()


def test_止めるときに理由が本文に出る(二つの窓):
    """**理由が文書にしかないと、止められた側は force を付けます。**"""
    with pytest.raises(SystemExit) as e:
        measure_window.check("2026-09-10", tool="てすと", today="2026-08-21")
    assert "上から測り直す" in str(e.value)
    assert "M14" in str(e.value)


def test_実物の窓は前提の期限を写している():
    """**`until` は、その窓が支えている前提の期限**（`config/hypotheses.yaml`）。

    短く書くと、前提が閉じる前に窓が開いて測定が壊れます。ここは
    「窓の `until` が、開いている前提のどれかの期限と一致する」ことだけを見ます。
    """
    import yaml

    def _walk(o):
        if isinstance(o, dict):
            if "claim" in o and "deadline" in o:
                yield o
            for v in o.values():
                yield from _walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from _walk(v)

    conf = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    期限 = {str(h["deadline"]) for h in _walk(conf) if not h.get("closed_on")}
    for w in measure_window.WINDOWS:
        assert w["until"] in 期限, (
            f'{w["from"]} の窓の until={w["until"]} が、開いている前提の期限に無い。'
            " 前提を閉じたなら窓も外すこと（`until` を過ぎれば自分で外れます）。"
        )


def test_窓には理由が必ず書いてある():
    """**「なぜか出ない日」を作らない。** 空欄は次の回に読めません。"""
    for w in measure_window.WINDOWS:
        for k in ("from", "to", "until", "label", "why"):
            assert w.get(k), (w, k)
        assert w["from"] <= w["to"] <= w["until"], w
        assert len(w["why"]) >= 40, w["why"]
