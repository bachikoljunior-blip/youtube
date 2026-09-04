"""**`expected_48h` は書かれるだけで、どこも読んでいなかった** —— 2026-09-04 19:2x に足した検査。

`src/daily_pick.record()` は最初からこの欄を書いています。`grep expected` の当たりは
引数・書く行・`replace_video()` が写す行の **3か所だけ**で、実物と並べる口が1つもなく、
実測 `data/daily_pick.jsonl` 22行 の `expected_48h` は **全部 null** でした。
＝ 欄の名前だけが「見込みを立てて後で答え合わせする」と言っている状態。

いまは `expected_lines()` が並べ、`--expected` で言えます。

**2026-09-04 22:5x（最適化の回）: 印字を門にしました。** 19:2x の「次に決める回は
`--expected` を付けること」という**印字**のあと、22:24 の決め（09-05 の長尺）も null でした
—— 実測 31行 中 `expected_48h` が入っているのは 4行。`record(kind="decide")` は
数が無ければ **通しません**。null が残る道は `kind="carry"`（焼き直しの写し）だけです。
"""
from __future__ import annotations

from datetime import date

from src import daily_pick as dp


def _pick(p, day, vid, exp=None, form="長尺", kind=dp.PICK_KIND_DECIDE):
    dp.record(form, "t", "数 1 で決めた", day=day, path=p, video_id=vid,
              expected=exp, kind=kind)


def test_決めは数が無ければ通らない(tmp_path):
    """**印字ではなく門**（2026-09-04 22:5x）。`--expected` 無しの `decide` は落ちる。

    文面は**相手の形の実測**を出すこと —— 選ぶ側が「負けている形を選ぶなら、
    その数を上回る見込みを置け」と読めるように。
    """
    p = tmp_path / "picks.jsonl"
    try:
        _pick(p, date(2026, 9, 5), "A")
    except ValueError as exc:
        assert "--expected" in str(exc)
        assert "齢48h 中央値" in str(exc)
    else:                                    # pragma: no cover
        raise AssertionError("`--expected` 無しの決めが通りました（門が効いていません）")
    assert not p.exists() or not p.read_text(encoding="utf-8").strip()


def test_写しは数が無くても通る(tmp_path):
    """焼き直しの写し（`carry`）は決めではないので、門は掛けません。"""
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 5), "A", kind=dp.PICK_KIND_CARRY)
    assert p.read_text(encoding="utf-8").strip()


def test_1件も言っていなければ名指しする(tmp_path):
    p = tmp_path / "picks.jsonl"
    # 門を入れる前に書かれた行（＝ 実物の 27行）と同じ形を、写しの道で作る
    _pick(p, date(2026, 9, 5), "A", kind=dp.PICK_KIND_CARRY)
    rows = [__import__("json").loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    rows[0]["kind"] = dp.PICK_KIND_DECIDE
    p.write_text("\n".join(__import__("json").dumps(r, ensure_ascii=False)
                            for r in rows) + "\n", encoding="utf-8")
    out = dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: [])
    assert len(out) == 1 and "1件も言っていません" in out[0]
    assert "--expected" in out[0]


def test_見込みと実物を並べる(tmp_path):
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 3), "A", exp=100.0)
    _pick(p, date(2026, 9, 4), "B", exp=10.0)
    aged = [{"video_id": "A", "views": 50}, {"video_id": "B", "views": 20}]
    out = dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged)
    body = "\n".join(out)
    assert "見込み 100回 → 実物 50回" in body and "×0.50" in body
    assert "見込み 10回 → 実物 20回" in body and "×2.00" in body
    assert "中央" in body


def test_齢48hに届いていない本は待ちに出る(tmp_path):
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 5), "A", exp=8.0)
    out = dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: [])
    body = "\n".join(out)
    assert "待ち" in body and "まだ 齢48h ではありません" in body


def test_同じ日の最後の決めだけを見る(tmp_path):
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 5), "A", exp=1000.0)
    _pick(p, date(2026, 9, 5), "A", exp=8.0)          # 決め直し
    aged = [{"video_id": "A", "views": 4}]
    body = "\n".join(dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged))
    assert "見込み 8回" in body and "1,000回" not in body


def test_焼き直したら新しいIDの実物と並べる(tmp_path):
    """見込みは「決め」の行から、実物は**その日の最後の行が名指ししている ID** から。

    焼き直しは決めを触らずに動画IDだけ写す（`kind="carry"`）ので、
    **決めの行の ID を引くと、焼き直したあとは古い ID を探して永久に「待ち」**になります。
    実際に出るのは新しいほうの本です。
    """
    p = tmp_path / "picks.jsonl"
    _pick(p, date(2026, 9, 5), "A", exp=8.0)
    dp.replace_video(["A"], "B", path=p)               # 焼き直しの写し
    aged = [{"video_id": "A", "views": 4}, {"video_id": "B", "views": 99}]
    body = "\n".join(dp.expected_lines(picks_path=p, aged_call=lambda *a, **k: aged))
    assert "見込み 8回 → 実物 99回" in body            # 出るのは B のほう
    assert "実物 4回" not in body
    # 見込みそのものは決めの行のまま（写しは決めではない）
    rows = [r for r in dp._jsonl(p)]
    assert dp.pick_kind(rows[-1]) == dp.PICK_KIND_CARRY
    assert rows[-1]["expected_48h"] == 8.0


def test_CLI_に見込みの口が在る():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "src.daily_pick", "--help"],
                       capture_output=True, text=True, timeout=120)
    assert "--expected" in r.stdout
