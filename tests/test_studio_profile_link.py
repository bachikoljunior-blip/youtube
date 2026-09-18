# -*- coding: utf-8 -*-
"""**ショートの出口が「押せる面」を指しているか**（2026-09-19 08:xx・optimizer・Fable 5.1・ultracode）。

**なぜ在るか**: YouTube は 2023-08-31 から Shorts の説明欄・コメント欄の URL を押せなくしています
（`support.google.com/youtube/answer/13748639`）。このチャンネルの配りの 93.9% は Shorts のフィード ＝
09/18 に置いた 2つ の面は、ほぼ全員に押せない字でした。押せる面は**チャンネルページのリンク**だけで、
API に口が無い（オーナーの手）。この検査が守るのは 3つ:
  (1) ショートの型（4つ の生成器）と在庫の 10本 が、**同じ 1か所**（`asp.CTA_SEG`）を指していること
  (2) 説明欄・コメント欄の塊が「押せない・押せる面はこちら」を **2行目** で言うこと（畳まれても見える）
  (3) 公開ページからリンクの有無が読めること（陽性対照 ＋ 陰性対照）
"""
import json
from pathlib import Path

from studio import asp, pubcheck, script, series, series_kuriage, series_taishoku, series_taishoku_years

ROOT = Path(__file__).resolve().parents[1]
SHORTS_10 = [f"2026-09-20-taishokukin-2000man-{n}nen-short" for n in (20, 25, 31, 35, 38)] + \
            [f"2026-09-21-kuriage-{a}sai-short" for a in (60, 61, 62, 63, 64)]


def test_出口の型は1か所():
    for m in (series, series_kuriage, series_taishoku, series_taishoku_years):
        assert m.CTA_SEG == asp.CTA_SEG, m.__name__


def test_出口は押せる面を指す():
    seg = script.Segment(**asp.CTA_SEG)
    assert script.has_cta(seg)
    assert "プロフ" in seg.say and "アイコン" in seg.say
    assert "説明欄" not in seg.say and "コメント" not in seg.say, "押せない面を指している"
    assert "広告" in seg.say, "ステマ規制: 声でも広告と言う"
    assert len(seg.say) <= 41, "在庫の字数の蓋（asp.CTA_SEG の註）"


def test_在庫の10本の出口が同じ():
    for i in SHORTS_10:
        d = json.loads((ROOT / f"data/studio/scripts/{i}.json").read_text(encoding="utf-8"))
        last = d["segments"][-1]
        assert last["say"] == asp.CTA_SEG["say"], i
        assert last["show"] == asp.CTA_SEG["show"], i
        assert last["board"] == asp.CTA_SEG["board"], i


def test_塊の2行目で押せる面を言う():
    for b in (asp.block(), asp.comment_block()):
        assert b, "案件が 0本（data/studio/asp_links.json）"
        lines = b.split("\n")
        assert lines[0].startswith("【PR】")
        assert lines[1] == asp.PROFILE_NOTE, lines[:2]
        assert "押せません" in asp.PROFILE_NOTE and "アイコン" in asp.PROFILE_NOTE


REAL = (
    '{"metadataParts":[{"text":{"content":"39 subscribers"},'
    '"accessibilityLabel":"39 subscribers"}]},'
    '"channelMetadataRenderer":{"title":"\\u30ab\\u30ef\\u30a6\\u30bd\\u306e\\u5e74\\u91d1\\u8a08\\u7b97\\u5ba4",'
    '"vanityChannelUrl":"http://www.youtube.com/@%E3%81%8A%E9%87%91"}'
)


def test_公開ページ_リンク無し():
    ch = pubcheck.channel_public("UCxxx", fetch=lambda url: REAL)
    assert ch["asp_link"] is False
    assert "プロフィールのリンク（成果報酬）は 未" in pubcheck.channel_public_line(ch)


def test_公開ページ_リンク在り():
    html = REAL + ',"link":{"content":"af.moshimo.com/af/c/click?a_id=5809177"}'
    ch = pubcheck.channel_public("UCxxx", fetch=lambda url: html)
    assert ch["asp_link"] is True
    assert "**在**" in pubcheck.channel_public_line(ch)


def test_読めなかったら言わない():
    assert "プロフィール" not in pubcheck.channel_public_line(None)
