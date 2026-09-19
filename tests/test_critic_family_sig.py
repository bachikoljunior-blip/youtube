"""`script.family_sig` と、家族で数える `critic.repeat_reals`（2026-09-19 17:xx）。

なぜ: 連作は **1つ の型から 5本**（`series_kuriage` は 60〜64歳）で、本文は**数だけ**違います。
`repeat_reals` が `id` で数えていたあいだ、**同じ文に立った real が 1度も繰り返しに見えず**、
5本 は永久に「1周目」でした（実測: コマ8 の同じ文が 60歳 nitpick・61歳 real・62歳 real）。
"""
from studio import critic, script


def _seg(say: str):
    return script.Segment(say=say, show="", sub=say, tag="", board=[])


def _s(says):
    return script.Script(id="x", date="2026-09-21", title="t", takeaway="t",
                         description="d", tags=[], segments=[_seg(a) for a in says])


def test_数だけ違う本は同じ家族():
    a = _s(["年金を60歳から早くもらうと毎月11万4000円。", "250から60か月を引くと190か月。"])
    b = _s(["年金を61歳から早くもらうと毎月12万1200円。", "250から48か月を引くと202か月。"])
    assert a.family_sig() == b.family_sig()


def test_文が違えば別の家族():
    a = _s(["年金を60歳から早くもらうと毎月11万4000円。"])
    b = _s(["退職金2000万円の手取りは1830万5600円です。"])
    assert a.family_sig() != b.family_sig()


def test_版が頭に付く():
    assert _s(["あ"]).family_sig().startswith(f"{script.FAMILY_SIG_VERSION}:")


def _row(vid, koma, sig, family=None):
    r = {"event": "critique", "id": vid, "sig": sig,
         "wheres": [{"where": f"コマ{koma}", "sev": "real"}]}
    if family:
        r["family"] = family
    return r


def _c(where="コマ8", sev="real"):
    return {"items": [{"severity": sev, "where": where}]}


def test_家族を渡すと連作の繰り返しが見える():
    rows = [_row("k60", 8, "s1", "F"), _row("k61", 8, "s2", "F"), _row("k62", 8, "s3", "F")]
    # `id` だけでは 1本 ＝ 門（3）に届かない
    assert critic.not_converging("k63", _c(), rows)[0] is False
    ok, why = critic.not_converging("k63", _c(), rows, family="F")
    assert ok and "3つ" in why


def test_陰性対照_別の家族は数えない():
    rows = [_row("k60", 8, "s1", "F"), _row("t15", 8, "s2", "G"), _row("t20", 8, "s3", "G")]
    assert critic.not_converging("k61", _c(), rows, family="F")[0] is False


def test_家族が同じでも所が違えば数えない():
    rows = [_row("k60", 3, "s1", "F"), _row("k61", 4, "s2", "F"), _row("k62", 5, "s3", "F")]
    assert critic.not_converging("k63", _c("コマ8"), rows, family="F")[0] is False


def test_家族が無い古い行は家族として数えない():
    """**この周より前の台帳には `family` が在りません** —— 無い行を家族に数えないこと。"""
    rows = [_row("k60", 8, "s1"), _row("k61", 8, "s2"), _row("k62", 8, "s3")]
    assert critic.not_converging("k63", _c(), rows, family="F")[0] is False
