"""`status` は、上がっている本の 題・説明欄・tags が台本と食い違っていたら名指しで言うこと（2026-09-09 01:5x・hourly・Fable）。

「処理 済」だけでは、説明欄を予約の後に直した回の分が古いまま 10:00 に出る。同じ 1単位 の `snippet` で見える。
tags は YouTube が並べ替えて返す（実測 09/09 01:4x `gv1u7n_pCAQ`）ので集合で比べる。
"""
import json

from studio import asp, cli, script, yt

# **2026-09-18 20:3x（optimizer）: live の説明欄は `asp.compose()` を通った字です**
# （`studio/asp.py`・成果報酬の塊を `yt.upload` / `yt.update_meta` の口で足す）。
# **比べる側（`cli.drift_fields` / `cli.desc_appended`）も同じ字と比べます** ——
# 通さないと、上がっている本が毎周「食い違い」に見えて 50単位 の直しが空撃ちされます。
# だから、この検査の「live」側も塊を通します（**陽性対照は通したまま でも拾えること**で守ります）。


class _Svc:
    def __init__(self, items):
        self._items = items

    def videos(self):
        return self

    def list(self, **kw):
        assert "snippet" in kw["part"] and "processingDetails" in kw["part"]
        return self

    def execute(self):
        return {"items": self._items}


def _script(tmp_path, monkeypatch, desc="説明欄A"):
    d = {"id": "2026-09-09-x", "date": "2026-09-09", "title": "題A #Shorts", "takeaway": "t", "description": desc,
         "tags": ["年金", "加給年金"], "segments": [{"say": "あ", "show": "あ", "sub": "あ"}], "notes": "n"}
    (tmp_path / "2026-09-09-x.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(script, "SCRIPTS", tmp_path)
    return d


ROWS = [{"event": "scheduled", "id": "2026-09-09-x", "video_id": "VID"}]


def _rd(title="題A #Shorts", desc="説明欄A", tags=("加給年金", "年金")):
    return {"ok": True, "title": title, "description": asp.compose(desc), "tags": list(tags)}


def test_readinessは_snippetも返す(monkeypatch):
    monkeypatch.setattr(yt, "svc", lambda: _Svc([{"id": "A", "snippet": {"title": "T", "description": "D", "tags": ["a"]},
                                                  "status": {"uploadStatus": "processed"},
                                                  "processingDetails": {"processingStatus": "succeeded"}}]))
    r = yt.readiness("A")
    assert r["ok"] and r["title"] == "T" and r["description"] == "D" and r["tags"] == ["a"]


def test_一致なら空_tagsは並びを見ない(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)
    assert cli.meta_drift("VID", _rd(), ROWS) == []
    assert "一致" in cli.meta_mark([])


def test_説明欄が違えば名指し(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch, desc="説明欄B（予約の後に直した）")
    d = cli.meta_drift("VID", _rd(), ROWS)
    assert d == ["説明欄"]
    m = cli.meta_mark(d)
    assert "!!" in m and "説明欄" in m and "update_meta" in m


def test_題とtagsも見る(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)
    assert cli.meta_drift("VID", _rd(title="題B", tags=("年金",)), ROWS) == ["題", "tags"]


def test_台帳に無い本は比べない(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)
    assert cli.meta_drift("OLD", _rd(), ROWS) is None
    assert cli.meta_mark(None) == ""


# --- `retitled` の本は、行の向きが逆（2026-09-16 01:4x・optimizer・Fable・ultracode） ---
#
# 21:0x の題の A/B は live が新・台本が旧。そこへ `update_meta(<videoId>, s.title, ...)` を撃つと
# **台本の旧の題が live を上書きして A/B が 1本 消えます**（同じ消え方を `schedule --replace` の側で
# 16:1x が実物で踏んだ）。`status` の行だけが、まだその手を指していました。

RETITLED = ROWS + [{"event": "retitled", "id": "VID",
                    "old_title": "題A #Shorts", "new_title": "【対象】新しい題"}]


def test_retitledの本は_台本を直せと言う_update_metaを指さない(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)                      # 台本の題は 題A #Shorts（旧）
    d = cli.meta_drift("VID", _rd(title="【対象】新しい題"), RETITLED)
    assert d == ["題"]
    m = cli.meta_mark(d, "VID", RETITLED, script_title="題A #Shorts")
    # 撃てる形（コピーできる呼び出し）で出さないこと ＝ これを撃つと A/B が戻る
    assert "update_meta(<videoId>" not in m
    assert "戻ります" in m                              # 名前は出すが、警告としてだけ
    assert "台本" in m and "【対象】新しい題" in m


def test_台本を直したあとは_この行そのものが出ない(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)
    # 台本の題を新しい題に書き換えた後は live と一致 ＝ drift が空
    assert cli.meta_drift("VID", _rd(title="題A #Shorts"), RETITLED) == []


def test_陽性対照_retitledを見ないと逆の手を指す(tmp_path, monkeypatch):
    """`vid` を渡さない（＝ 台帳を見ない）と、昔の行がそのまま出る ＝ 門が効いている印。"""
    _script(tmp_path, monkeypatch)
    assert "update_meta" in cli.meta_mark(["題"])


def test_陽性対照_説明欄だけの食い違いは_retitledの本でも従来どおり(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch, desc="説明欄B")
    d = cli.meta_drift("VID", _rd(), RETITLED)
    assert d == ["説明欄"]
    assert "update_meta" in cli.meta_mark(d, "VID", RETITLED, script_title="題A #Shorts")


def test_script_title_of_は台帳から台本の題を引く(tmp_path, monkeypatch):
    _script(tmp_path, monkeypatch)
    assert cli.script_title_of("VID", ROWS) == "題A #Shorts"
    assert cli.script_title_of("OLD", ROWS) is None
