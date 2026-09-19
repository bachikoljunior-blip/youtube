# -*- coding: utf-8 -*-
"""**チャンネルの説明欄（概要）が、Shorts から押せる面として置かれるか**（2026-09-19 09:xx・optimizer・Fable 5.1・ultracode）。

**なぜ在るか**: Shorts の説明欄・コメント欄の URL は押せない（YouTube 2023-08-31）。押せるのはチャンネルページで、
その面は 2つ —— リンク欄（API に口が無い ＝ オーナーの手）と **説明欄**（`channels.update` 50単位 ＝ 機械の手）。
うちの説明欄は前のチャンネルの字のまま（「残業代と割増賃金、失業給付…」）で、年金の字もリンクも無かった。
この検査が守るのは 4つ:
  (1) 置く字が 景表法の 2語（`【PR】`・アフィリエイト）と案件の URL を持ち、上限 1,000字 の内であること
  (2) 公開ページから「説明欄に host が在るか」が、リンク欄と分けて読めること（陽性・陰性・読めない）
  (3) `catchup` が この手を数え、済んだら 2度 撃たないこと（台帳で見る・0単位）
  (4) `channel-desc --dry-run` が 0単位 で字を印字して 0 を返すこと
"""
import argparse
import json

from studio import asp, budget, cli, pubcheck


def test_置く字():
    t = asp.channel_description()
    assert asp.offers(), "案件が 0本（data/studio/asp_links.json）"
    assert len(t) <= asp.CHANNEL_DESC_LIMIT
    assert t.startswith(asp.CHANNEL_DESC_HEAD)
    assert "【PR】" in t and "アフィリエイト" in t, "景表法・ステマ規制の 2語"
    for url, _line in asp.offers():
        assert url in t
    assert asp.HOST in t
    assert "年金" in t.split("\n")[0], "1行目（もっと見る の上）で何のチャンネルか言う"
    assert "残業代" not in t and "失業給付" not in t, "前のチャンネルの字を引き継がない"


def test_案件が無ければリンク無しの字(monkeypatch):
    monkeypatch.setattr(asp, "offers", lambda: [])
    t = asp.channel_description()
    assert asp.HOST not in t and "【PR】" not in t
    assert t.startswith(asp.CHANNEL_DESC_HEAD) and asp.CHANNEL_DESC_TAIL in t


REAL_HEAD = (
    '{"metadataParts":[{"text":{"content":"39 subscribers"},'
    '"accessibilityLabel":"39 subscribers"}]},'
)
REAL_META = ('"channelMetadataRenderer":{"title":"\\u30ab\\u30ef\\u30a6\\u30bd",'
             '"description":"%s","vanityChannelUrl":"http://www.youtube.com/@x"}')


def test_公開ページ_説明欄にリンク在り():
    html = REAL_HEAD + REAL_META % "年金の手取り\\n【PR】https://af.moshimo.com/af/c/click?a_id=1"
    ch = pubcheck.channel_public("UCxxx", fetch=lambda url: html)
    assert ch["asp_link"] is True and ch["asp_link_desc"] is True
    assert ch["description"].startswith("年金の手取り\n")
    line = pubcheck.channel_public_line(ch)
    assert "**在**" in line and "説明欄" in line


def test_公開ページ_リンク欄だけ在り():
    html = REAL_HEAD + REAL_META % "前の字" + ',"link":{"content":"af.moshimo.com/af/c/click?a_id=1"}'
    ch = pubcheck.channel_public("UCxxx", fetch=lambda url: html)
    assert ch["asp_link"] is True and ch["asp_link_desc"] is False
    assert "リンク欄" in pubcheck.channel_public_line(ch)


def test_公開ページ_どちらも無い():
    html = REAL_HEAD + REAL_META % "前の字"
    ch = pubcheck.channel_public("UCxxx", fetch=lambda url: html)
    assert ch["asp_link"] is False and ch["asp_link_desc"] is False
    assert "channel-desc" in pubcheck.channel_public_line(ch), "機械の手が在ることを名指しする"


def test_公開ページ_説明欄が読めない():
    ch = pubcheck.channel_public("UCxxx", fetch=lambda url: REAL_HEAD + '"channelMetadataRenderer":{"title":"x"}')
    assert ch["asp_link_desc"] is None and ch["description"] is None


def test_済んだら撃たない():
    assert cli.channel_desc_pending([]) is True
    assert cli.channel_desc_pending([{"event": "channel_desc_set"}]) is False
    refused = [{"event": "channel_desc_refused"}] * cli.CHANNEL_DESC_REFUSE_CAP
    assert cli.channel_desc_pending(refused) is False
    assert cli.channel_desc_pending(refused[:-1]) is True


def test_単位の表():
    assert budget.UNITS_BY_EVENT["channel_desc_set"] == 51
    assert budget.UNITS_BY_EVENT["channel_desc_refused"] == 51


def test_dry_run_は0単位(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("dry-run で API を撃った")
    monkeypatch.setattr(cli.yt, "set_channel_description", boom)
    monkeypatch.setattr(cli, "ledger", boom)
    assert cli.cmd_channel_desc(argparse.Namespace(dry_run=True, anyway=False)) == 0
    out = capsys.readouterr().out
    assert "0単位" in out and asp.HOST in out


def test_読み返せなければ台帳に済を書かない(monkeypatch, capsys):
    wrote = []
    monkeypatch.setattr(cli, "ledger_rows", lambda: [])
    monkeypatch.setattr(cli, "ledger", lambda ev, vid, **d: wrote.append((ev, d)))
    monkeypatch.setattr(cli.yt, "set_channel_description",
                        lambda text: {"before": "前の字", "after": "前の字", "ok": False})
    assert cli.cmd_channel_desc(argparse.Namespace(dry_run=False, anyway=False)) == 1
    assert [e for e, _ in wrote] == ["channel_desc_refused"]
    wrote.clear()
    monkeypatch.setattr(cli.yt, "set_channel_description",
                        lambda text: {"before": "前の字", "after": text, "ok": True})
    assert cli.cmd_channel_desc(argparse.Namespace(dry_run=False, anyway=False)) == 0
    assert [e for e, _ in wrote] == ["channel_desc_set"] and wrote[0][1]["units"] == 51
