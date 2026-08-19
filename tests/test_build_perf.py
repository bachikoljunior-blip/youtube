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
        # **1枚目の画面**（2026-08-19 に足し、2026-08-20 に測り直した）。
        # engaged が決まるのは最初の1〜2秒で、そこで画面を占めているのが1枚目です。
        # 19日の版は**見出し（画面上部の小さい札）だけ**を見ていました。
        # 実物の主役は `note`（`reveal_variants` が数字を伏せた 97% の本）なので、
        # **主役の幅**と**画面ぜんぶの数字**を測ります（`first_slide` の docstring）。
        "1枚目の幅", "1枚目の主役の幅", "1枚目に数字", "1枚目の数字の個数",
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


def test_既知の当たり_単調な特徴は向きが出る():
    """**既知の当たり**（`docs/trigger_main.md` §4「道具を足す回は当たりを先に固定する」）。

    **2026-08-20 に、実データの 尺 × 再生 = -0.33 から取り替えました**（下の検査）。
    あれは尺の効きではなく **08/15 の切替の前後** だったので、
    物差しとして使うと「時期と分けられない」を直した瞬間に落ちます。

    ここが見るのは **「特徴 → 順位相関」の配線だけ**です。
    手で作った行なので、実データが動いても意味が変わりません。
    **配線が落ちると、特徴の件数は減らないまま向きだけ消えます。**
    """
    # 時期はばらけさせる（**時期と分けられない側で落とさせない**）。
    # x は時期に対して行ったり来たりするが、views とは単調に増える。
    xs = [1.0, 12.0, 2.0, 11.0, 3.0, 10.0, 4.0, 9.0, 5.0, 8.0, 6.0, 7.0]
    rows = [
        {
            "video_id": f"v{i}",
            "topic": "t",
            "title": "",
            "views": float(x * 100),
            "engaged": x / 20.0,
            "subs": 0.0,
            "first_seen": f"2026-08-{i + 1:02d}T00:00:00Z",
            "features": {"手で作った特徴": x},
        }
        for i, x in enumerate(xs)
    ]
    d = next(c for c in build_perf.correlations(rows) if c["name"] == "手で作った特徴")
    assert d["why"] == "", f"向きが出ていません: {d}"
    assert d["views"] == 1.0 and d["eng"] == 1.0, (
        f"完全に単調なのに {d}。**特徴 → 順位相関 の配線を疑うこと**")


def test_既知の当たり_尺は時期と分けられない():
    """**実データ側の当たり**（2026-08-20 に実測して固定）。

    ショートの尺は 08/15 にパイプラインごと 47〜69秒 → 27〜30秒 へ切り替わっており、
    **最初に観測した順に並べると、境目で完全に割れます。**
    だから `尺 × 再生 = -0.32` は「短いほど回る」ではなく、
    **「切替の前後で再生が違った」**しか言っていません。

    **ここが緑でなくなったら、それは進歩です** —— 同じ時期の本で尺が割れた
    （＝ A/B で振り分けた）ということなので、そのときは向きを読んでよい。
    """
    rows, _ = build_perf.collect()
    d = next(c for c in build_perf.correlations(rows) if c["name"] == "尺（秒）")
    if d["why"] == "本数不足":
        return  # 日枠が切れて `尺` が引けない回（`videos.list` が 403）
    assert d["why"] == "時期と分けられない", (
        f"尺が時期と分けられるようになりました: {d}。"
        "**同じ時期の本で尺が割れたなら進歩です。**この検査を書き換えて、"
        "向きのほうを読むこと")
    assert d["eng"] is None and d["views"] is None, (
        "時期と分けられない特徴の向きを印字してはいけません")


def test_時期で完全に割れる特徴は向きを出さない():
    """**切替日で丸ごと入れ替わった作りは、再生との向きを出さないこと。**

    前の版は、こういう特徴も普通の順位相関として印字していました。
    そのまま読むと「短いほど回る」に見えますが、言えるのは
    **「切替の前後で再生が違った」**までです。
    """
    rows = []
    for i in range(12):
        late = i >= 6
        rows.append({
            "video_id": f"v{i}",
            "topic": "t",
            "title": "",
            "views": 1000.0 if late else 500.0,
            "engaged": 0.4 if late else 0.2,
            "subs": 0.0,
            "first_seen": f"2026-08-{i + 1:02d}T00:00:00Z",
            # 前半は 50〜55、後半は 27〜32。**重なりません**
            "features": {"尺（秒）": (27.0 + i) if late else (50.0 + i)},
        })
    d = next(c for c in build_perf.correlations(rows) if c["name"] == "尺（秒）")
    assert d["why"] == "時期と分けられない", d
    assert d["time"] == 1.0, f"完全に割れているのに {d['time']}"


def test_時期がばらけている特徴は_割れたと言わない():
    """**逆側**。同じ時期の中で値が割れている特徴は、そのまま向きを出すこと。

    `title_form` / `hook_form` はIDのハッシュで半々に割るので、
    **時期と直交します。**ここが誤って止まると、A/B の結果が読めなくなります。
    """
    rows = []
    for i in range(12):
        rows.append({
            "video_id": f"v{i}",
            "topic": "t",
            "title": "",
            "views": 1000.0 if i % 2 else 500.0,
            "engaged": 0.4 if i % 2 else 0.2,
            "subs": 0.0,
            "first_seen": f"2026-08-{i + 1:02d}T00:00:00Z",
            "features": {"問いか": float(i % 2)},
        })
    d = next(c for c in build_perf.correlations(rows) if c["name"] == "問いか")
    assert d["why"] == "", d
    assert d["views"] == 1.0


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
    for name in ("1枚目の幅", "1枚目の主役の幅", "1枚目に数字", "1枚目の数字の個数"):
        assert f[name] is None


def test_1枚目の画面を控えから読む(tmp_path, monkeypatch):
    """`<id>.plan.json` の先頭のコマを、**画面に出るぶん全部**で測る。"""
    monkeypatch.setattr(build_perf, "QUEUE", tmp_path)
    (tmp_path / "vid1.plan.json").write_text(
        '[{"headline": "児童手当 3人目は1万5000円"}, {"headline": "次"}]',
        encoding="utf-8")
    got = build_perf.first_slide("vid1")
    assert got["1枚目に数字"] == 1.0
    assert got["1枚目の幅"] == build_perf._width("児童手当 3人目は1万5000円")
    # `stat` も `note_lead` も無い本では、主役は見出しそのもの
    assert got["1枚目の主役の幅"] == got["1枚目の幅"]
    # 「3」「1」「5000」＝ 3つ
    assert got["1枚目の数字の個数"] == 3.0

    (tmp_path / "vid2.plan.json").write_text(
        '[{"headline": "ふるさと納税の上限"}]', encoding="utf-8")
    got2 = build_perf.first_slide("vid2")
    assert got2["1枚目に数字"] == 0.0
    assert got2["1枚目の数字の個数"] == 0.0


def test_数字を伏せた1枚目では補足が主役(tmp_path, monkeypatch):
    """**既知の当たりを検査に固定する**（`docs/trigger_main.md` §4）。

    `visuals.reveal_variants` は冒頭の `kind=stat` を2枚に割り、
    **1枚目の `stat` と `formula` を空にして `note_lead` を立てます**。
    実測 **332/341 = 97%** の本がこの形で、画面の主役は `note` です。

    2026-08-19 の版は見出しだけを見ていたので、この形の本を
    「1枚目に数字が無い」と数え、**51% という嘘の割合**を出していました
    （画面ぜんぶで数えると 96%）。**その読み違えをここで止めます。**
    """
    monkeypatch.setattr(build_perf, "QUEUE", tmp_path)
    (tmp_path / "v.plan.json").write_text(
        '[{"kind": "stat", "headline": "高額療養費 区分ウ", "stat": "",'
        ' "note": "医療費1000万円・窓口3割", "note_lead": true},'
        ' {"kind": "stat", "headline": "高額療養費 区分ウ", "stat": "177,430円"}]',
        encoding="utf-8")
    got = build_perf.first_slide("v")
    # 主役は補足のほう。**見出しではありません**
    assert got["1枚目の主役の幅"] == build_perf._width("医療費1000万円・窓口3割")
    assert got["1枚目の幅"] == build_perf._width("高額療養費 区分ウ")
    # 見出しには数字が無いが、**画面には出ている**
    assert build_perf._NUM.search("高額療養費 区分ウ") is None
    assert got["1枚目に数字"] == 1.0
    # 「1000」「3」＝ 2つ（`,` で切れる数は1つに数える）
    assert got["1枚目の数字の個数"] == 2.0


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
