"""**題の打ち直しを `catchup` に入れた**（2026-09-17 12:5x・optimizer・Opus・**API 0単位**）。

**踏んだ当のもの**: `watermark`（50単位）は 09/16 15:3x に名指しされてから **5周** 撃てずに
終わりました —— 詰まっていたのは判断ではなく順番で、それを潰すために `catchup` が在ります。
`docs/GOAL.md` (4-r) 4 は 09/17 01:4x に「題を `named_topic` の升へ変える」と**決め済み**で、
残っていたのは文字列 1つ だけでした。**同じ詰まり方を 2度 しないために、決めを手へ落とします。**

**いちばん怖いのは 2度 撃つこと**（YouTube は題の変更を 14日 に 3回 まで ＝ 外したら 14日 戻せない）。
だから `rename_pending` は台帳と `config` の **2つ** を見て、**どちらかが「済んだ」と言えば撃ちません**。

**陽性対照 3つ**（＝ 門が本当に効いているかを、逆向きにも当てる）:
 (1) 台帳に `channel_renamed` が在れば False（1度 撃ったら 2度目は無い）
 (2) `config` が既に目当ての題なら False（台帳に書く前に落ちた回を拾う）
 (3) どちらでもなければ True（いまの repo の状態）
"""
import studio.cli as cli


def test_目当ての題は名前と制度名の升に入る():
    from studio import peers
    assert peers.PERSONA_RE.match(cli.RENAME_TARGET)
    assert peers.TOPIC_NARROW_RE.search(cli.RENAME_TARGET)
    # **肩書き（人間の経歴）は 1文字 も主張しない** —— `config/channel.yaml` 08/30 が閉じた腕
    assert not peers.CRED_RE.search(cli.RENAME_TARGET)


def test_台帳に印が在れば撃たない():
    assert cli.rename_pending([{"event": "channel_renamed", "at": "2026-09-17T16:01:00+09:00"}]) is False


def test_configが既に目当ての題なら撃たない(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "channel.yaml").write_text(f'channel:\n  name: "{cli.RENAME_TARGET}"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cli.rename_pending([]) is False


def test_どちらでもなければ撃つ(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "channel.yaml").write_text('channel:\n  name: "お金と仕事の教科書"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cli.rename_pending([]) is True


def test_詰まった手の行に題が出る(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "channel.yaml").write_text('channel:\n  name: "お金と仕事の教科書"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    line = cli.catchup_line([{"event": "watermark_set", "at": "2026-09-17T16:01:00+09:00"}])
    assert "題 未" in line and cli.RENAME_TARGET in line
    # **値段も 52単位 ぶん動く**（`channels.list` 1 ＋ `update` 50 ＋ 読み返し 1）
    assert "53単位" in line   # 1（口を試す）＋ 52


def test_全部済んでいれば0件(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "channel.yaml").write_text(f'channel:\n  name: "{cli.RENAME_TARGET}"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cli.catchup_line([{"event": "watermark_set", "at": "2026-09-17T16:01:00+09:00"}]) \
        .endswith("0件")
