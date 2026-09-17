"""**題材の段**（`studio/topics.py`・2026-09-17 17:4x・optimizer）。**陽性対照つき。**

この段が本物であることの測りは 2つ:
 (1) **重複を落とさないと、引き直した本ほど重くなる**（実物: 同じ 1本 が 3行 入っている）
 (2) **`dense`（面が在る）と `lottery`（当たりだけ）は、中央と最大の比で割れる** ——
     最大だけを見ると、中央 190 の段が 457,339 の段に見えます。
"""
import json

import pytest

from studio import topics


def _corpus(tmp_path, rows):
    p = tmp_path / "niche_corpus.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def _v(vid, views, q, form="long"):
    return {"id": vid, "views": views, "q": q, "form": form, "secs": 900,
            "channel": "UC_x", "title": f"{q} の本", "published": "2026-05-01T00:00:00Z"}


def test_同じ本の複数行を1本に畳む(tmp_path):
    """実物: `年金・給付金完全攻略` の 4,402,748 / 4,415,973 / 4,422,714 は**同じ 1本**。"""
    rows = [_v("hit", 4_402_748, "加給年金 いくら"), _v("hit", 4_415_973, "加給年金 いくら"),
            _v("hit", 4_422_714, "加給年金 いくら")] + [_v(f"s{i}", 100, "加給年金 いくら") for i in range(4)]
    got = topics.by_query(_corpus(tmp_path, rows))
    assert len(got) == 1
    assert got[0]["n"] == 5, f"重複を落としていない（n={got[0]['n']}・本当は 5本）"
    # あとの行（いちばん大きい）で上書きする。
    assert got[0]["max"] == 4_422_714


def test_陽性対照_畳まないと本数も中央も嘘になる(tmp_path):
    """**この検査が何か を測っている証拠**: 同じ行を素で数えると n も中央も変わる。"""
    rows = [_v("hit", 4_402_748, "加給年金 いくら"), _v("hit", 4_415_973, "加給年金 いくら"),
            _v("hit", 4_422_714, "加給年金 いくら")] + [_v(f"s{i}", 100, "加給年金 いくら") for i in range(4)]
    raw = [json.loads(line) for line in _corpus(tmp_path, rows).read_text(encoding="utf-8").splitlines()]
    assert len(raw) == 7 and len(topics.rows(_corpus(tmp_path, rows))) == 5


def test_面が在る段と当たりだけの段を分ける(tmp_path):
    """**最大では割れません** —— 下の 2つ は最大がほぼ同じで、中央が 3桁 違う。"""
    dense = [_v(f"d{i}", 500_000 + i, "年金 手取り いくら") for i in range(6)]
    dense[0] = _v("d0", 1_000_000, "年金 手取り いくら")
    lottery = [_v("L0", 1_000_000, "医療費控除 いくら戻る")] + \
              [_v(f"L{i}", 190, "医療費控除 いくら戻る") for i in range(1, 6)]
    got = {t["q"]: t for t in topics.by_query(_corpus(tmp_path, dense + lottery))}
    assert got["年金 手取り いくら"]["dense"] is True
    assert got["医療費控除 いくら戻る"]["dense"] is False, "当たり 1本 の段を『面が在る』と読んでいる"
    assert got["年金 手取り いくら"]["max"] == got["医療費控除 いくら戻る"]["max"], \
        "最大が違っては、この検査は『最大では割れない』を測っていない"


def test_本数の少ない語は段にしない(tmp_path):
    rows = [_v(f"a{i}", 999_999, "ふるさと納税 上限 計算") for i in range(topics.MIN_BOOKS - 1)]
    assert topics.by_query(_corpus(tmp_path, rows)) == []


def test_ショートは数えない(tmp_path):
    rows = [_v(f"s{i}", 800_000, "年金 手取り いくら", form="short") for i in range(6)]
    assert topics.rows(_corpus(tmp_path, rows)) == []


@pytest.mark.parametrize("text, want", [
    ("年金が毎月15万円の人の手取りは13万7000円", "年金 手取り いくら"),
    # **頭の語で錨を打たないと、ここが `年金 手取り いくら` に落ちる**（この回に踏んだ実物）。
    ("【退職金2000万円】30年勤めた人の手取りは1959万4300円", "退職金 税金 いくら"),
    ("医療費が1年で10万円をこえたら", None),
])
def test_題がどの段に居るか(tmp_path, text, want):
    rows = ([_v(f"n{i}", 600_000, "年金 手取り いくら") for i in range(6)]
            + [_v(f"t{i}", 300_000, "退職金 税金 いくら") for i in range(6)]
            + [_v(f"i{i}", 190, "医療費控除 いくら戻る") for i in range(6)])
    got = topics.tier_of(text, _corpus(tmp_path, rows))
    assert (got["q"] if got else None) == want


def test_毎周の1行は段の比を出す(tmp_path):
    rows = ([_v(f"n{i}", 600_000, "年金 手取り いくら") for i in range(6)]
            + [_v(f"i{i}", 190, "医療費控除 いくら戻る") for i in range(6)])
    s = topics.line(_corpus(tmp_path, rows))
    assert "年金 手取り いくら" in s and "3,157倍" in s, s


def test_corpusが無くても落ちない(tmp_path):
    assert "corpus が無い" in topics.line(tmp_path / "無い.jsonl")
