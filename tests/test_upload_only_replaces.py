"""**焼き直し（規則3）が、自分が差し替える下書きに止められないこと。**

## なぜ要るか（2026-09-02 に実際に止められた）

オーナーが固定した規則3 は「次の枠で出る1本を、出る瞬間まで良くし続ける」。
その1手は焼き直し（`python -m src.pipeline` → `upload_only.py <題材> --draft`）で、
焼き直した本は**外そうとしている下書きと必ず同じ題材**です。
`src/dupes.find()` の `same-topic` は強い重なりなので、投稿が止まりました。

`--replaces <videoId>` は、その1本**だけ**を突き合わせから外します。
外してよいのは **private かつ 予約なし**（＝ 視聴者から見て存在しない）本だけ。
**予約済みを外せてはいけません** —— 2026-08-16 にすり抜けた `iTrogWVf4Eg` が
まさに予約済みで、あれは `same-topic` を止めるべき側でした。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import upload_only  # noqa: E402


def _v(vid: str, privacy: str = "private", publish_at: str | None = None) -> dict:
    st: dict = {"privacyStatus": privacy}
    if publish_at:
        st["publishAt"] = publish_at
    return {"id": vid, "snippet": {"title": vid}, "status": st}


def test_private予約なしは外れる():
    rows = [_v("old"), _v("other", "public")]
    kept, why = upload_only.drop_replaced(rows, "old")
    assert why == ""
    assert [r["id"] for r in kept] == ["other"]


def test_予約済みは外せない():
    """8/16 にすり抜けた形。ここが通ると、同じ枠に2本 並びます。"""
    rows = [_v("old", publish_at="2026-09-03T11:00:00Z")]
    kept, why = upload_only.drop_replaced(rows, "old")
    assert "予約" in why
    assert [r["id"] for r in kept] == ["old"], "断ったのに外れています"


def test_公開済みは外せない():
    rows = [_v("old", "public")]
    kept, why = upload_only.drop_replaced(rows, "old")
    assert "private" in why
    assert [r["id"] for r in kept] == ["old"]


def test_一覧にない本を名指ししたら断る():
    """打ち間違いを黙って通すと、門が降りたまま投稿されます。"""
    rows = [_v("old")]
    kept, why = upload_only.drop_replaced(rows, "typo")
    assert why
    assert [r["id"] for r in kept] == ["old"]


def test_札はmainへ渡る():
    """CLI の `--replaces <id>` が位置引数の数を壊さないこと。"""
    src = (ROOT / "scripts" / "upload_only.py").read_text(encoding="utf-8")
    assert '_replaces = _argv[_i + 1]' in src
    assert 'del _argv[_i:_i + 2]' in src
    assert "        _replaces,\n    ))" in src, "main への引き渡しがありません"


def test_控えから拾い直されないこと(monkeypatch):
    """**呼び手で抜くだけでは足りません**（2026-09-02 の実測）。

    `dupes.blocking()` は、`videos` に無い本を控え（`data/uploaded.jsonl`）から
    拾い直します。だから外すのは**混ぜたあと 1か所**でなければなりません。
    """
    from src import dupes

    ledger = [{"id": "old", "title": "介護の月額上限2万4600円で年間限度額の何割が埋まるか",
               "topic": "gassan-kaigo-alone-155", "calc": "gassan",
               "at": None, "scheduled": False}]
    monkeypatch.setattr(dupes, "ledger_rows", lambda topics=None: list(ledger))

    topics = {"gassan-kaigo-alone-155": "gassan"}
    title = "介護の月額上限2万4600円は年間限度額19万円の何割か"

    # `videos` から抜いただけ（＝ 直す前の姿）→ 控えから拾い直されて鳴る
    assert dupes.blocking(title, "gassan-kaigo-alone-155", [], topics)

    # `exclude` で外す → 通る
    assert not dupes.blocking(title, "gassan-kaigo-alone-155", [], topics,
                              exclude="old")
