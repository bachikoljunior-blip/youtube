# -*- coding: utf-8 -*-
"""**チャンネルの数を Data API 0単位 で読む口**（`pubcheck.channel_public`）の検査。

**陽性対照を先に置いてあります**（この repo が 7度 踏んだ形 ——
「読めなかった」と「0人だった」が同じ字で出る）:

    (1) 実物の写し（2026-09-19 04:xx に撃って取った字）から **39人** が出ること
    (2) その字を 1つ 崩すと **`None`** が返ること（＝ 0 ではない）
    (3) `channel_public_line` が (2) を「0人ではありません」と言うこと

**この 3件 が同時に通らないかぎり、この口の陰性は読めません。**
"""
from studio import cli, pubcheck

# 実物の写し（2026-09-19 04:xx・`https://www.youtube.com/channel/UChTXZzwkIJHqyL7L_fEtuqQ`）。
# **題は新しい `カワウソの年金計算室`・handle は古い `お金と仕事の教科書` のまま** ＝
# 改名が片側だけであることを、この写し自身が持っています。
REAL = (
    '{"metadataParts":[{"text":{"content":"39 subscribers"},'
    '"accessibilityLabel":"39 subscribers"}]},'
    '"channelMetadataRenderer":{"title":"\\u30ab\\u30ef\\u30a6\\u30bd\\u306e\\u5e74\\u91d1\\u8a08\\u7b97\\u5ba4",'
    '"vanityChannelUrl":"http://www.youtube.com/@%E3%81%8A%E9%87%91%E3%81%A8%E4%BB%95%E4%BA%8B%E3%81%AE%E6%95%99%E7%A7%91%E6%9B%B8"}'
)


def _fetch(html):
    return lambda url: html


def test_陽性対照_実物の写しから登録者が出る():
    ch = pubcheck.channel_public("UCxxx", fetch=_fetch(REAL))
    assert ch is not None
    assert ch["subscriberCount"] == 39
    assert ch["exact"] is True          # 1,000人 未満なので丸めではない
    assert ch["title"] == "カワウソの年金計算室"
    assert ch["handle"] == "お金と仕事の教科書"
    assert ch["src"] == "public_page"
    # **総再生と本数の欄は返さないこと**（`None` を 0 と読ませない ＝ `yt.views_of` の族）。
    assert "viewCount" not in ch and "videoCount" not in ch


def test_字が変わったら_0ではなくNoneで返る():
    broken = REAL.replace("subscribers", "followers")
    assert pubcheck.channel_public("UCxxx", fetch=_fetch(broken)) is None


def test_読めなかった行は_0人と同じ字にならない():
    line = pubcheck.channel_public_line(None)
    assert "0人" in line and "ではありません" in line
    assert "登録 **0**" not in line


def test_1000人を越えたら丸めだと言う():
    html = REAL.replace('"39 subscribers"', '"1.23K subscribers"')
    ch = pubcheck.channel_public("UCxxx", fetch=_fetch(html))
    assert ch["subscriberCount"] == 1230
    assert ch["exact"] is False
    assert "丸め" in pubcheck.channel_public_line(ch)


def test_日本語のページでも読める():
    html = REAL.replace('"content":"39 subscribers"', '"content":"チャンネル登録者数 39人"') \
               .replace('"accessibilityLabel":"39 subscribers"', '"accessibilityLabel":"チャンネル登録者数 39人"')
    ch = pubcheck.channel_public("UCxxx", fetch=_fetch(html))
    assert ch is not None and ch["subscriberCount"] == 39


def test_万の単位を桁で読む():
    html = REAL.replace('"content":"39 subscribers"', '"content":"チャンネル登録者数 5.78万人"') \
               .replace('"accessibilityLabel":"39 subscribers"', '"accessibilityLabel":"チャンネル登録者数 5.78万人"')
    ch = pubcheck.channel_public("UCxxx", fetch=_fetch(html))
    assert ch["subscriberCount"] == 57800 and ch["exact"] is False


def test_題とhandleがずれていたら行が名指しする():
    ch = pubcheck.channel_public("UCxxx", fetch=_fetch(REAL))
    line = pubcheck.channel_public_line(ch)
    assert "handle" in line and "お金と仕事の教科書" in line and "カワウソの年金計算室" in line


def test_揃っていたら余計なことを言わない():
    html = REAL.replace("%E3%81%8A%E9%87%91%E3%81%A8%E4%BB%95%E4%BA%8B%E3%81%AE%E6%95%99%E7%A7%91%E6%9B%B8",
                        "%E3%82%AB%E3%83%AF%E3%82%A6%E3%82%BD%E3%81%AE%E5%B9%B4%E9%87%91%E8%A8%88%E7%AE%97%E5%AE%A4")
    ch = pubcheck.channel_public("UCxxx", fetch=_fetch(html))
    assert ch["handle"] == ch["title"]
    assert "handle" not in pubcheck.channel_public_line(ch)


def test_取ってこられなくてもNoneで返る():
    def boom(url):
        raise OSError("proxy")
    assert pubcheck.channel_public("UCxxx", fetch=boom) is None


def test_台帳からチャンネルidを引ける():
    rows = [{"event": "measured", "id": "abc"},
            {"event": "channel", "id": "UCold", "subs": "27"},
            {"event": "quota_exceeded", "id": "-"},
            {"event": "channel", "id": "UCnew", "subs": "39"},
            {"event": "status", "id": "-"}]
    assert cli.last_channel_id(rows) == "UCnew"
    assert cli.last_channel_id([]) is None
    # `id` が `-` の行（`status` / `quota_exceeded`）を拾わないこと
    assert cli.last_channel_id([{"event": "channel", "id": "-"}]) is None
