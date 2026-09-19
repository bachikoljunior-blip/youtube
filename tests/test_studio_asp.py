"""`studio/asp.py`（成果報酬のリンクを説明欄に入れる一点）の検査。

2026-09-18 20:3x・optimizer。**何を守っているか**:
 (1) **冪等** —— 2度 通しても塊は 1つ（`verify_meta` は同じ本に何度も `update_meta` を撃つ）
 (2) **表示の決まり**（ステマ規制）—— `【PR】` と「アフィリエイト」の 2語 が必ず出る
 (3) **口の側に入っていること** —— `yt.upload` と `yt.update_meta` が `asp.compose` を通す
     （通さない口が 1つ でも在れば、その本だけ分子が 0 になります）
 (4) **比べる側も同じ字を見ていること** —— `cli.drift_fields` が生の台本と比べると、
     上がっている本が毎周「食い違い」に見えて 50単位 が空撃ちされます
 (5) 案件が 0本 のときは素通し（`asp_links.json` が無い環境でも道具は止まらない）
"""
from __future__ import annotations

import inspect

from studio import asp, cli, yt


def test_塊には広告の表示が在る():
    b = asp.block()
    assert b, "案件が 0本（data/studio/asp_links.json）"
    assert "【PR】" in b
    assert "アフィリエイト" in b
    assert "af.moshimo.com" in b


def test_冪等():
    once = asp.compose("本文")
    assert asp.compose(once) == once
    assert once.count("【PR】") == 1


def test_上に入る():
    out = asp.compose("本文です")
    assert out.startswith("【PR】")
    assert out.endswith("本文です")


def test_下にも置ける():
    out = asp.compose("本文です", top=False)
    assert out.startswith("本文です")
    assert "【PR】" in out


def test_案件が0本なら素通し(monkeypatch):
    monkeypatch.setattr(asp, "OFFERS", [])
    assert asp.compose("本文") == "本文"
    assert asp.block() == ""


def test_youtube_okがfalseの案件は出さない(monkeypatch):
    bad = {k: {**v, "youtube_ok": False} for k, v in asp.links().items()}
    monkeypatch.setattr(asp, "links", lambda: bad)
    assert asp.offers() == []


def test_口の両方がcomposeを通している():
    for fn in (yt.upload, yt.update_meta):
        src = inspect.getsource(fn)
        assert "asp.compose(description)" in src, f"{fn.__name__} が塊を通していません"


def test_比べる側もcomposeを通している():
    for fn in (cli.drift_fields, cli.desc_appended):
        assert "asp.compose(" in inspect.getsource(fn), f"{fn.__name__} が生の台本と比べています"


def test_食い違いは塊を入れた字で判定される():
    class S:
        title = "題"
        description = "本文"
        tags = ["a"]

    live = {"title": "題", "description": asp.compose("本文"), "tags": ["a"]}
    assert cli.drift_fields(live, S()) == []
    assert cli.drift_fields({**live, "description": "本文"}, S()) == ["説明欄"]


def test_後ろに足された橋は食い違いにならない():
    class S:
        title = "題"
        description = "本文"
        tags = ["a"]

    live = {"description": asp.compose("本文") + "\n\n【くわしい計算（長尺）】\nhttps://youtu.be/x"}
    assert cli.desc_appended(live, S()).startswith("【くわしい計算")


def test_上限を越えたら台本の側を落とす():
    """**塊は落とさない**（落とすと、その本だけ分子が 0 になる）。"""
    long = "あ" * 6000
    out = asp.compose(long)
    assert len(out) <= asp.LIMIT
    assert out.startswith("【PR】")
    assert "af.moshimo.com" in out
    assert out.endswith("…")


def test_上限の中なら1字も落とさない():
    d = "本文\n" * 100
    out = asp.compose(d)
    assert d.strip() in out


def test_入れ直しの蓋は実測で取る():
    """推計（`budget.spent`）は台帳に `units` を書かない口を数えず、**必ず小さく出ます**。

    2026-09-18 の実測: 推計 8,756 対 実測 9,126（差 370単位 ＝ 7本ぶん）。
    推計だけで蓋を取ると「12本 撃てる」と出て、日枠を使い切ります
    （`budget` の覆る条件 (1)「この行を信じて枠を使い切らないこと」）。
    """
    src = inspect.getsource(cli.cmd_asp)
    assert "meter.spent(" in src
    assert "max(est, real)" in src


def test_入れ直しは台帳に印を残す():
    """説明欄を**前に足す**形は前方一致では引けない（`cli.desc_appended` の覆る条件 (1)）。"""
    assert '"redescribed"' in inspect.getsource(cli.cmd_asp)


# ---------------------------------------------------------------------------
# **コメント欄の側**（2026-09-18 22:xx・optimizer・Opus 5・ultracode）
#
# 何を守っているか:
#  (6) **表示の決まりはコメントでも同じ** —— `【PR】` と「アフィリエイト」が塊の頭に出る
#      （景表法・ステマ規制は面を問いません）
#  (7) **2度 置かない** —— 台帳 `cta_comment` に在る本は `cmd_cta` の相手から外れる
#      （置き直すと視聴者には同じ広告が 2つ 並び、YouTube には連投に見えます）
#  (8) **背景から呼ぶ口を作らない**（§8 で止めた旧 `post_pending_comments.py` と別物である条件）
#  (9) **値段が台帳に載っている** —— `budget.UNITS_BY_EVENT` に `cta_comment` が在る
#      （無いと `status` の推計が 50単位/本 ぶん小さく出て、枠を使い切ります）
# ---------------------------------------------------------------------------


def test_コメントの塊にも広告の表示が在る():
    b = asp.comment_block()
    assert b, "案件が 0本（data/studio/asp_links.json）"
    assert b.startswith("【PR】"), "1行目 に無いと、畳まれた状態で表示が見えません"
    assert "アフィリエイト" in b
    assert "af.moshimo.com" in b


def test_コメントの塊の道順はリンク欄が無くても当たる():
    # リンク欄はオーナーの手（窓【2】）。機械が置ける面（説明欄）はスマホでは「…もっと見る」の中に出るので、
    # コメントの道順は「もっと見る」で言う（`asp.COMMENT_NOTE` の註）。説明欄の `PROFILE_NOTE` は drift の門があるので別の字。
    b = asp.comment_block()
    assert "もっと見る" in b
    assert asp.COMMENT_NOTE in b
    assert asp.PROFILE_NOTE not in b


def test_コメントの塊は上限の内側():
    assert len(asp.comment_block()) <= asp.COMMENT_LIMIT


def test_コメントの塊は説明欄の塊より短い():
    # コメントは 4行 ほどで畳まれるので、説明欄と同じ長さにしない。
    assert len(asp.comment_block()) <= len(asp.block()) + 40


def test_案件が0本ならコメントの塊も空(monkeypatch):
    monkeypatch.setattr(asp, "OFFERS", [])
    assert asp.comment_block() == ""


def test_ctaは台帳に在る本を2度置かない():
    src = inspect.getsource(cli.cmd_cta)
    assert '"cta_comment"' in src, "台帳の印で外していません"
    assert "placed" in src


def test_ctaの値段が台帳の表に在る():
    from studio import budget
    assert budget.UNITS_BY_EVENT.get("cta_comment") == 50


def test_ctaを背景から呼ぶ口が無い():
    # §8 で止めた旧 `post_pending_comments.py` と別物である条件（`reply` と同じ）。
    import pathlib
    root = pathlib.Path(cli.__file__).resolve().parents[1]
    hits = []
    for p in list((root / "studio").rglob("*.py")) + list((root / "scripts").rglob("*.py")):
        if p.name == "cli.py":
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = line.strip()
            if ln.startswith(("def ", "#", "*", '"')):
                continue          # 定義そのものと註は「呼ぶ口」ではない
            if "post_comment(" in ln or "cmd_cta(" in ln:
                hits.append(f"{p}: {ln[:60]}")
    assert not hits, f"背景から呼べる口が在る: {hits}"


def test_post_commentは公開ずみの本の口():
    src = inspect.getsource(yt.post_comment)
    assert "commentThreads()" in src
    assert "videoId" in src


# (10) **思い出させる行**（`cli.cta_gap_line`）—— `CLAUDE.md` 09/02 15:3x「選ばれない手は撃たれません」。
#      `cli cta` は その回が思い出したときだけ撃つ手なので、`status` に置き忘れの行が要ります。


def _fake_pub(vid, iso, views=100, title="題"):
    return {"id": vid, "publish_at": iso, "views": views, "title": title, "privacy": "public"}


def test_置き忘れの行が若い本を先に出す():
    import datetime as dt
    now = dt.datetime(2026, 9, 18, 22, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    pubs = [_fake_pub("fresh1", "2026-09-18T20:00:00+09:00"),
            _fake_pub("old1", "2026-09-01T10:00:00+09:00")]
    line = cli.cta_gap_line([], pubs, now)
    assert "2本" in line
    assert "**1本**" in line, "齢 48h 以内 の数が出ていません"
    assert "fresh1" in line and "old1" not in line


def test_置いた本は行から消える():
    import datetime as dt
    now = dt.datetime(2026, 9, 18, 22, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    pubs = [_fake_pub("v1", "2026-09-18T20:00:00+09:00")]
    rows = [{"event": "cta_comment", "video_id": "v1"}]
    assert cli.cta_gap_line(rows, pubs, now) == ""
