"""`src/build_perf.py` の検査。

**先に置いたのは「既知の当たり」1件**（`docs/trigger_main.md` §4）——
`test_key_resolves_for_most_measured_videos` です。

2026-08-19 15:1x の回は「鍵（`video_id` → テーマID）を `data/uploaded.jsonl` から
作る道は**使えません**。直近28日に再生のあった28本のうち ledger に居たのは6本だけ」と
申し送りました。**この道具は、その申し送りが正しければ成り立ちません。**
だから最初に、実物で数え直す検査を置いています。**落ちたら、どちらかが嘘です。**
"""

from __future__ import annotations

import json

from src import build_perf


def test_key_resolves_for_most_measured_videos():
    """**再生のある本の大半は、控えからテーマIDが引けます。**

    15:1x の申し送り（6/28 しか引けない）はここで落ちます。
    実測 2026-08-19: 再生のある20本のうち **19本**。
    """
    stats = build_perf.per_video()
    led = build_perf.ledger()
    have = [v for v, s in stats.items() if s.get("views", 0) > 0]
    hit = [v for v in have if v in led]
    assert len(have) >= 10, "実績のある本が少なすぎます（scan が古い？）"
    assert len(hit) / len(have) >= 0.8, (
        f"控えから鍵が引けたのは {len(hit)}/{len(have)} 本。"
        "8割を切ったら、`data/uploaded.jsonl` の書き込みが落ちています"
    )


def test_features_are_all_known_before_publishing():
    """**特徴は全部、公開前に決まっているものだけ。**

    再生や engaged を特徴に混ぜると「よく回った本はよく回る」という
    同義反復が向きとして出ます。
    """
    f = build_perf.features("nonexistent-topic", "年金の繰下げは1234円得します #Shorts", {})
    assert set(f) == {
        "尺（秒）", "図の枚数", "1枚目の棒", "棒の本数", "題の幅",
        "数字までの幅", "題の数字の桁", "題の数字の個数", "題が問いか",
        "冒頭の声の幅", "冒頭に数字", "冒頭の絵の変化",
        # **1枚目の見出し**（2026-08-19 に足した）。engaged が決まるのは
        # 最初の1〜2秒で、そこで画面を占めているのが1枚目の見出しですが、
        # ここは長らく**棒の本数（`1枚目の棒`）しか見ていません**でした。
        "1枚目の幅", "1枚目に数字",
    }
    assert f["題の数字の桁"] == 4.0
    assert f["題の数字の個数"] == 1.0
    assert f["図の枚数"] == 0.0
    # 「年金の繰下げは」＝ 全角7字 → 幅14 で最初の数字に当たる
    assert f["数字までの幅"] == 14.0
    assert f["題が問いか"] == 0.0


def test_missing_features_are_none_not_zero():
    """**測れない特徴は `None`。0 で埋めない。**

    0 で埋めると「冒頭に数字が無い本」と「冒頭が分からない本」が同じ値になり、
    向きが静かに薄まります（`usage` の 4つ組を `0,0,0,0` と書かない話と同じ形）。
    """
    f = build_perf.features("t", "年金 #Shorts", {})
    assert f["尺（秒）"] is None
    assert f["冒頭の声の幅"] is None
    assert f["冒頭の絵の変化"] is None
    g = build_perf.features("t", "年金 #Shorts", {}, seconds=52, head={"冒頭に数字": 0.0})
    assert g["尺（秒）"] == 52.0
    assert g["冒頭に数字"] == 0.0        # **0 は「無い」ではなく「数字が入っていない」**
    assert g["冒頭の声の幅"] is None


def test_question_titles_are_detected():
    """`題が問いか` が末尾の「か」だけを見ていないこと。"""
    ask = build_perf.features("t", "医療費控除でいくら戻る #Shorts", {})["題が問いか"]
    assert ask == 1.0
    assert build_perf.features("t", "戻る額は何円か #Shorts", {})["題が問いか"] == 1.0
    assert build_perf.features("t", "医療費控除で2万209円戻る", {})["題が問いか"] == 0.0


def test_known_hit_length_vs_views_is_negative():
    """**既知の当たり**（`docs/trigger_main.md` §4「道具を足す回は当たりを先に固定する」）。

    `scripts/status.py` が別の道（Analytics の一覧）で出している
    **尺 × 再生 = -0.33**（n=20・再生30未満は除外）を、この道具でも持ちます。
    **配線が落ちると、特徴の件数は減らないまま向きだけ消えるので、
    ここが唯一の物差しです。**
    """
    rows, _ = build_perf.collect()
    d = next(c for c in build_perf.correlations(rows) if c["name"] == "尺（秒）")
    assert d["why"] == "", f"尺が測れていません: {d}"
    assert d["n"] >= 15, f"測れた本が {d['n']}本 しかありません"
    assert d["views"] is not None and d["views"] < -0.15, (
        f"尺 × 再生 = {d['views']}。status.py の -0.33 と符号が合いません。"
        "**特徴 → 順位相関 の配線を疑うこと**"
    )


def test_no_data_and_no_variation_are_told_apart():
    """**「本数が足りない」と「一度も試していない」を混ぜないこと。**

    前の版はどちらも `None` を返し、口が両方「本数が足りない」と印字していました。
    ＝ **待っても出ないもの**（全部の本が同じ値）が、待てば出るものに見えていました。
    """
    rows = [
        {"features": {"ずっと同じ": 1.0, "足りない": 5.0}, "engaged": 0.1 * i, "views": 10.0 * i}
        for i in range(1, build_perf.MIN_N + 1)
    ]
    for r in rows[3:]:
        r["features"]["足りない"] = None
    out = {d["name"]: d for d in build_perf.correlations(rows)}
    assert out["ずっと同じ"]["why"] == "変化なし"
    assert out["ずっと同じ"]["n"] == build_perf.MIN_N
    assert out["足りない"]["why"] == "本数不足"
    assert out["足りない"]["n"] == 3


def test_width_counts_fullwidth_as_two():
    assert build_perf._width("年金") == 4
    assert build_perf._width("ab") == 2
    # **#Shorts は幅に入れません**（全部の題に付くので、差を作りません）
    a = build_perf.features("t", "年金 #Shorts", {})["題の幅"]
    b = build_perf.features("t", "年金", {})["題の幅"]
    assert a == b == 4


def test_min_views_floor_is_reported_not_hidden():
    """**落とした本は数えて出すこと。**（15:0x の「床」の件と同じ形）"""
    rows, dropped = build_perf.collect()
    assert rows, "測れる本が1本もありません"
    assert all(r["views"] >= build_perf.MIN_VIEWS for r in rows)
    # 落ちた側は理由つきで残っている
    assert all(isinstance(w, str) and w for _, w in dropped)


def test_correlations_cover_every_feature():
    """**測れなかった特徴を、黙って表から落とさないこと。**

    落とすと「無関係だった」と「そもそも測っていない」が区別できなくなります。
    """
    rows, _ = build_perf.collect()
    names = set(rows[0]["features"])
    assert {d["name"] for d in build_perf.correlations(rows)} == names


def test_first_seconds_is_absent_for_videos_stashed_before_0817():
    """**冒頭の材料は、いま少数の本にしかありません**（2026-08-19 に数え直した）。

    16:0x の申し送りは「`narration` は 352本ぶんある」と書きましたが、
    **`engaged` と突き合わせられる 19本のうち、控えのあるのは数本**です
    （控えを取り始めたのが 08/17・再生の付いている本は 08/04〜08/15 の公開）。
    **この検査は「少ないこと」を固定するためのものではありません** ——
    `MIN_N` に届いたら、口が向きを出し始めます。ここは
    **「0 で埋めていないこと」**だけを見ています。
    """
    rows, _ = build_perf.collect()
    have = [r for r in rows if r["features"]["冒頭の声の幅"] is not None]
    missing = [r for r in rows if r["features"]["冒頭の声の幅"] is None]
    assert missing, "全部の本に控えがあるなら、この節は役目を終えています"
    for r in missing:
        assert r["features"]["冒頭に数字"] is None, "控えの無い本を 0 で埋めています"
    for r in have:
        assert r["features"]["冒頭の声の幅"] > 0


def test_bars_file_is_readable():
    """図の枚数の出どころ。**壊れたら特徴が全部0になって、静かに無関係が出ます。**"""
    data = json.loads(build_perf.BARS.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and data
    assert any("charts" in v for v in data.values())


def test_日枠の切れた点だけで測らない():
    """**最新の1点に `尺` が無くても、向きが消えないこと**（2026-08-19 17:2x に踏んだ）。

    `videos.list`（日枠）が 403 の13時間は、その回の点に `尺` も `題` も入りません
    （`views` は Analytics ＝ 別枠なので入る）。実測は3点続けて **動画キー253・尺0**。
    最新の1点だけを読む版は `尺` が **n=0** になり、
    **この道具の唯一の物差し（既知の当たり 尺 × 再生）が落ちました。**

    **特徴が消えても件数は減らない**ので、口は「本数不足」と印字します ——
    「まだ待て」と読めますが、**枠が戻るまで永久に0**です。
    """
    stats = build_perf.per_video()
    with_len = [v for v in stats.values() if "尺" in v]
    assert with_len, "**古い点から `尺` を拾えていません**"

    # 最新の1点だけを渡したら、**その1点しか読まないこと**（検査が形を固定できる）
    latest = build_perf._scans()[-1]
    only_latest = build_perf.per_video(latest)
    assert set(only_latest) <= set(stats)
    for vid, m in only_latest.items():
        assert set(m) <= set(stats[vid])


def test_古い点から拾った件数を言う():
    """**黙って古い値を使わないこと。** 使ったなら、いくつ使ったかを出す。"""
    n = build_perf.stale_keys()
    assert isinstance(n, int) and n >= 0
    assert build_perf.stale_keys(build_perf._scans()[-1]) == 0   # 1点だけなら拾いようがない


# --- 1枚目の見出し（2026-08-19 に足した）--------------------------------------


def test_1枚目の見出しは控えが無ければNone():
    """**0 で埋めないこと。** 「見出しに数字が無い」と区別がつかなくなります。"""
    assert build_perf.first_slide("no-such-video-id") is None
    f = build_perf.features("t", "題 #Shorts", {})
    assert f["1枚目の幅"] is None
    assert f["1枚目に数字"] is None


def test_1枚目の見出しを控えから読む(tmp_path, monkeypatch):
    """`<id>.plan.json` の先頭のコマの見出しを、幅と「数字があるか」で測る。"""
    monkeypatch.setattr(build_perf, "QUEUE", tmp_path)
    (tmp_path / "vid1.plan.json").write_text(
        '[{"headline": "児童手当 3人目は1万5000円"}, {"headline": "次"}]',
        encoding="utf-8")
    got = build_perf.first_slide("vid1")
    assert got["1枚目に数字"] == 1.0
    assert got["1枚目の幅"] == build_perf._width("児童手当 3人目は1万5000円")

    (tmp_path / "vid2.plan.json").write_text(
        '[{"headline": "ふるさと納税の上限"}]', encoding="utf-8")
    assert build_perf.first_slide("vid2")["1枚目に数字"] == 0.0


def test_narrationが無くても1枚目は落ちない(tmp_path, monkeypatch):
    """**受け口を2つに分けた理由そのもの。**

    `<id>.json`（narration）と `<id>.plan.json` は別々に欠けます。
    1つの辞書で受けると、片方が無い本で**もう片方まで消えます**。
    """
    monkeypatch.setattr(build_perf, "QUEUE", tmp_path)
    (tmp_path / "v.plan.json").write_text(
        '[{"headline": "上限は1234円"}]', encoding="utf-8")
    assert build_perf.first_seconds("v") is None          # narration は無い
    f = build_perf.features("t", "題 #Shorts", {},
                            head=build_perf.first_seconds("v"),
                            slide=build_perf.first_slide("v"))
    assert f["冒頭に数字"] is None                          # 片方は None のまま
    assert f["1枚目に数字"] == 1.0                          # **もう片方は生きている**


def test_こわれた控えでも例外を出さない(tmp_path, monkeypatch):
    monkeypatch.setattr(build_perf, "QUEUE", tmp_path)
    (tmp_path / "a.plan.json").write_text("{", encoding="utf-8")
    (tmp_path / "b.plan.json").write_text("[]", encoding="utf-8")
    (tmp_path / "c.plan.json").write_text('[{"headline": ""}]', encoding="utf-8")
    for vid in ("a", "b", "c"):
        assert build_perf.first_slide(vid) is None
