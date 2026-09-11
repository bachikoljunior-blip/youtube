"""道で呼ばれた `id` が、id に戻ること（2026-09-12 02:1x・hourly・Opus）。

**実物を踏んだ回の検査**: `build data/studio/scripts/<id>.json` が
**絵が在るのに単色で焼き**、台帳の `id` に道を書いた（§16・JOURNAL 02:1x）。
陽性対照つき —— `norm_id` を素通しに戻すと、下の 3件 が落ちます。
"""
from studio import cli, script


def test_道は_id_に戻る():
    assert script.norm_id("data/studio/scripts/2026-09-13-fuka-nenkin-400en.json") \
        == "2026-09-13-fuka-nenkin-400en"
    assert script.norm_id("2026-09-13-fuka-nenkin-400en.json") == "2026-09-13-fuka-nenkin-400en"


def test_素の_id_は動かない():
    assert script.norm_id("2026-09-13-fuka-nenkin-400en") == "2026-09-13-fuka-nenkin-400en"


def test_戻した_id_から_path_for_が同じ所を指す():
    p = "data/studio/scripts/2026-09-13-fuka-nenkin-400en.json"
    assert script.path_for(script.norm_id(p)).resolve() == script.path_for(p).resolve()


def test_道で呼んでも背景の絵が見つかる(tmp_path, monkeypatch):
    """**この検査が、実物の欠陥そのもの**（`image_for(a.id)` が道を受け取っていた）。"""
    monkeypatch.setattr(cli, "IMAGES", tmp_path)
    (tmp_path / "xx-bg.jpg").write_bytes(b"\xff\xd8\xff")
    assert cli.image_for("xx") is not None
    assert cli.image_for("data/studio/scripts/xx.json") is None      # 素で渡すと見つからない
    assert cli.image_for(script.norm_id("data/studio/scripts/xx.json")) is not None


def test_main_が_id_を正規化してから渡す(monkeypatch):
    seen = {}
    monkeypatch.setitem(cli.__dict__, "cmd_lint", lambda a: seen.setdefault("id", a.id) and 0 or 0)
    cli.main(["lint", "data/studio/scripts/2026-09-13-fuka-nenkin-400en.json"])
    assert seen["id"] == "2026-09-13-fuka-nenkin-400en"
