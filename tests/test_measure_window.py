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

    `taken` を空にすると、**いちばん早く取れる枠**が返ります。
    その枠は**窓の中であってはいけません**（それが契約）。
    窓の手前に取れる回もあれば、窓を飛び越える回もあります ——
    **どちらも正しい動き**なので、飛び越えた回だけ「飛ばしました」を見ます。
    """
    day = _in_window_day()
    got = uploader.next_publish_at(11, 0, taken=set())
    got_jst = datetime.strptime(got, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc).astimezone(JST).strftime("%Y-%m-%d")
    # **これが契約です**: 自動で探した先が窓の中で終わらないこと。
    assert not measure_window.inside(got_jst), got_jst

    # **「窓より後」と「飛ばしました」は、飛び越えた回だけの話です。**
    #
    # 2026-08-24 に一度直しています（無条件で `got_jst > day` を見ていた）が、
    # そのときの直し方は **「明日が窓の中なら、窓より後へ行くはず」** でした。
    # **これも成り立ちません**（2026-08-26 に落ちた）。実測:
    #
    #     いま 08-26 01:5x JST ／ 窓は 08-27 ／ 返り **08-26 11:00**
    #     → `'2026-08-26' > '2026-08-27'` で落ちる
    #
    # **今日の枠がまだ残っていれば、窓の手前に取れます。** 飛び越える必要が
    # ないので、道具も「飛ばしました」とは言いません。**それが正しい動きです。**
    #
    # **契約は上の1行（窓の中で終わらないこと）だけ**で、ここは
    # 「**窓の日以降へ着いたのなら、飛び越えたと言っているか**」を見ます
    # （`taken` が空なので、いちばん早い枠に着きます ——
    # 窓より後に着いたということは、飛び越えたということです）。
    out = capsys.readouterr().out
    if got_jst >= day:
        assert got_jst > day
        assert "飛ばしました" in out


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
        day = _in_window_day()
        reschedule.main(["--move", "abc123", f"{day}T09:00"])
    # **札の名前ではなく、日付を見ること**（2026-08-24 に直した）。
    # ここは `"M14"` を直に見ていたので、**`label` が `day_cap` の窓を
    # 足した回に落ちました。** 門の約束は「API を呼ぶ前に、どの日で
    # 止まったかを言う」ことで、**札の綴りはその約束に入っていません。**
    assert day in str(e.value)


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


def _open_hypotheses():
    """`config/hypotheses.yaml` の、**閉じていない**前提を claim 引きで返す。"""
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
    return {str(h["claim"]): h for h in _walk(conf) if not h.get("closed_on")}


def test_窓は支えている前提を名指ししている():
    """**`until` の持ち主を書くこと。**（2026-08-28 に足した）

    ここが無いあいだ、検査は「`until` が**開いている前提のどれかの期限**と
    一致するか」しか見ていませんでした。**日付が合っていれば持ち主は誰でもよく**、
    `src/measure_window.py` の註は「たまたま通っていました」を**2回**、
    「動かされなかった」を**1回**記録しています。

    **`WINDOWS`（手で書いた窓）だけを見ます。** `day_cap_split` のように
    **計器が日付を出している窓には `claim` は要りません** ——
    あちらの `until` は `day_cap.booked_split_day()` の `answer` そのもので、
    **写しではないので古くなりようがない**からです。
    `claim` が要るのは「2か所に同じ日付が在る」窓だけ。
    **derived な窓に `claim` を足しにこないこと**（足すと、こんどはそちらが写しになります）。
    """
    for w in measure_window.WINDOWS:
        assert w.get("claim"), (
            f'{w["from"]} の窓に `claim` がありません。**その `until` は誰の期限ですか。**'
            " `config/hypotheses.yaml` の `claim` の全文を写すこと"
        )


def test_実物の窓は前提の期限を写している():
    """**`until` は、その窓が支えている前提の期限**（`config/hypotheses.yaml`）。

    短く書くと、前提が閉じる前に窓が開いて測定が壊れます。

    **2026-08-28 に「どれかの期限」から「`claim` の期限」へ締めました。**
    緩いままだと、次の3つが**全部 通ります**:

        1. 期限が動いたのに `until` が残っている
           —— **別の前提が偶然その日を持っていれば通る**（実測2回）
        2. 支えている前提が閉じたのに窓が残っている
           —— 同上
        3. `until` が**そもそも別の前提の日**を写している

    そして緩い版は `for` の中で assert するので**最初の1件で止まり**、
    2件目以降は隠れます —— 実測 2026-08-28: `day_cap`（08-27／前提 08-28）が
    先に落ちて、`density_engaged`（10-02／前提 10-03）が**見えませんでした。**
    ここは**全件を集めてから**まとめて出します。
    """
    opened = _open_hypotheses()
    bad: list[str] = []
    for w in measure_window.WINDOWS:
        claim = str(w.get("claim") or "")
        h = opened.get(claim)
        if h is None:
            bad.append(
                f'  {w["label"]}（{w["from"]}）: `claim` の前提が**開いている前提に居ません**。'
                " 閉じたなら窓も外すこと（`until` を過ぎれば自分で外れます）。"
                f" claim={claim[:40]}…")
            continue
        if str(h["deadline"]) != w["until"]:
            bad.append(
                f'  {w["label"]}（{w["from"]}）: until={w["until"]} ／'
                f' 前提の期限={h["deadline"]} —— **食い違っています。**'
                " 期限を動かしたら `until` も一緒に動かすこと")
    assert not bad, (
        "窓と前提の期限が合っていません（**全件**）:\n" + "\n".join(bad))


def test_窓には理由が必ず書いてある():
    """**「なぜか出ない日」を作らない。** 空欄は次の回に読めません。"""
    for w in measure_window.WINDOWS:
        for k in ("from", "to", "until", "label", "why"):
            assert w.get(k), (w, k)
        assert w["from"] <= w["to"] <= w["until"], w
        assert len(w["why"]) >= 40, w["why"]
