"""台帳の行の "at" は「いつやったか」であって、本文の値に上書きされない。

実測 2026-09-07 12:3x JST（optimizer・Opus）: `cmd_schedule` が
`ledger("scheduled", ..., at=公開の時刻)` と書いており、`common.ledger()` が
`{"at": now, ...} | **detail` の順で組んでいたので **detail が now を潰していた。
結果、`data/studio/ledger.jsonl` の scheduled 3行は全部 公開の時刻を "at" に持つ:
  - 09/07 の行は 09/06 02:2x に書かれたのに "2026-09-07T10:00+09:00"（未来の日付）
  - 09/06 の2行（元の s3hb9Tl1jLw と差し替えの EkNqtkK49Bw）は どちらも
    "2026-09-06T10:00+09:00" ＝ **どちらが先か台帳から読めない**。
    残る手がかりは行の並びだけで、その並びは merge が崩す（実測 524行 中 9箇所 が降順）。
`unscheduled` は同じ物を `was_at` に置いて "at" を残していたので、直す側はそちらに揃えた。

**覆る条件**: 台帳の "at" を「その行の主題の時刻」に読み替えると決めたとき
（そのときは measured の age_h・rounds.jsonl との突き合わせも同時に直すこと）。
"""
import json
import re

from studio import common


def test_detail_は_at_を上書きしない(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA", tmp_path)
    monkeypatch.setattr(common, "LEDGER", tmp_path / "ledger.jsonl")
    common.ledger("scheduled", "2026-09-09-x", video_id="v1", at="2026-09-09T10:00+09:00")
    row = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip())
    assert row["at"] != "2026-09-09T10:00+09:00"
    assert row["at"] == common.now_jst().isoformat(timespec="seconds")[:16] or row["at"].startswith("20")
    assert row["id"] == "2026-09-09-x" and row["event"] == "scheduled"


def test_id_も上書きされない(tmp_path, monkeypatch):
    # event= は仮引数と名前がぶつかって TypeError になるので、そもそも書けない。
    # id= は仮引数が vid なので通ってしまう ＝ ここで止める。
    monkeypatch.setattr(common, "DATA", tmp_path)
    monkeypatch.setattr(common, "LEDGER", tmp_path / "ledger.jsonl")
    common.ledger("built", "real-id", id="uso")
    row = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip())
    assert row["id"] == "real-id" and row["event"] == "built"


def test_予約は公開の時刻を_publish_at_に置く():
    src = (common.ROOT / "studio" / "cli.py").read_text(encoding="utf-8")
    i = src.index('ledger("scheduled"')
    call = src[i:i + 240]
    assert "publish_at=" in call, "公開の時刻は publish_at（was_at と同じ向き）"
    assert not re.search(r"[(,]\s*at=", call), '"at" は「いつやったか」なので渡さない'
