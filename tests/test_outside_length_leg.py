"""**外の型の長尺が、帯の切れ目（25分）を割ったまま焼かれないこと。**

## なぜ要るか（2026-09-05 03:5x に足した）

`OUTSIDE_RULE_LEGS` の「ナレーションの合計を 8,800〜9,800文字にすること」は、
2026-09-05 02:1x まで **`数えない:`** の側に置かれていました。理由もそこに
書いてあります ——「字数の上限を落とす口はまだ在りません（下限だけ `verify` の
`min_minutes`）。足りない字数で焼くと尺が帯の遅い側へ落ちるので、**数えるなら
`long_script_problems` に足すこと** —— この回は入れていない」。

**数えていなかったあいだに何が通ったか。** 09/05 09:00 の枠の `GFvAcxvDmYM` は
**台本 7,699字 ＝ 22.7分**で、外の帯の切れ目 25分 を **2.3分 下回っています**。
それでも `daily_pick.pick_legs()` は 4脚とも ○ を返すので、毎周の画面は
**「焼き直して得られる脚は 0本」**と刷り続け、帯でいちばん大きく効いている軸が
どの回からも見えませんでした（`data/niche_corpus.jsonl` の長尺 335本・1日あたりの
中央値: 20〜25分 792回/日 対 25〜30分 2,094回/日 ＝ **×2.6**）。

この検査が見るのは3つです。

1. 床が**狙い（26分）ではなく帯の切れ目（25分）**から引かれていること。
   狙いに置くと 8,430〜8,800字 の台本が書き直しの回数（3回）を食います。
2. 床が**べた書きの数ではない**こと（`OUTSIDE_LONG_KNEE_SEC` を動かせば追随する）。
3. `style: outside_long` の道（`long_script_problems`）から**実際に呼ばれている**こと。
   —— 09-03 から5回 続けて、脚は「本文に書いたが数える口に繋がなかった」形で漏れています。

**上を数えないこと**も、ここで留めます。帯は 30〜35分 で 969回/日 まで落ち、
35〜60分 で 2,519回/日 へ戻る ＝ **上側に罰は測れていません。**
測っていない理由で書き直しの回数を食わないこと。

## 覆る条件

前提「外の作り方を写した長尺」が外れたら（48h で 100回 未満）、`OUTSIDE_LONG_RULE`
ごと落とすので、この file も一緒に消すこと。帯を数え直して切れ目が 25分 でなく
なったときは `daily_pick.OUTSIDE_LONG_KNEE_SEC` を動かせば足り、ここは触りません。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import daily_pick as dp  # noqa: E402
from src import script_writer as sw  # noqa: E402


def _script(chars: int):
    """ナレーション合計が `chars` 字ちょうどの台本を1つ作る。"""
    d = {
        "title": "【60歳以上の方へ】75歳までなら総額2052万円差 損が最小は69歳7か月",
        "description_body": "本文",
        "tags": ["年金"],
        "thumbnail_kicker": "年金",
        "thumbnail_line1": "年180万・75歳まで",
        "thumbnail_line2": "最小は69歳7か月",
        "segments": [{"narration": "あ" * chars, "visual": {"kind": "stat", "value": "1"}}],
    }
    try:
        return sw.VideoScript.model_validate(d)
    except Exception:  # noqa: BLE001
        # スキーマが変わっていたら、この検査が見たいのは字数だけなので、
        # 実物の控えを土台にして narration だけ差し替える。
        import json
        base = json.loads((ROOT / "data" / "critique_queue"
                           / "GFvAcxvDmYM.script.json").read_text(encoding="utf-8"))
        base["segments"] = [dict(base["segments"][0], narration="あ" * chars)]
        return sw.VideoScript.model_validate(base)


def test_floor_is_the_measured_knee_not_the_aim():
    """**床は帯の切れ目（25分）** —— 狙いの 26分 に置かないこと。"""
    floor = sw.outside_length_chars_floor()
    knee = int(dp.OUTSIDE_LONG_KNEE_SEC * dp.LONG_CHARS_PER_SECOND)
    assert floor == knee, f"床が切れ目から引かれていません（{floor} 対 {knee}）"
    aim_lo = int(26 * 60 * dp.LONG_CHARS_PER_SECOND)
    assert floor < aim_lo, (
        "床を狙い（26分）に置くと、切れ目を越えている台本まで書き直しの回数を食います")


def test_floor_follows_the_knee_constant(monkeypatch):
    """**べた書きの数ではないこと** —— 帯を数え直した回が定数1つで動かせること。"""
    monkeypatch.setattr(dp, "OUTSIDE_LONG_KNEE_SEC", 1800)
    assert sw.outside_length_chars_floor() == int(1800 * dp.LONG_CHARS_PER_SECOND)


def test_short_script_is_caught_and_names_the_gap():
    """切れ目を割った台本は落ち、**足りない字数**を言うこと。"""
    floor = sw.outside_length_chars_floor()
    probs = sw.outside_length_problems(_script(floor - 731))
    assert probs, "切れ目を割った台本が通っています"
    assert "731" in probs[0], f"足りない字数を言っていません: {probs[0]}"


def test_script_over_the_knee_passes():
    """切れ目を越えていれば、狙い（8,800字）に届いていなくても落とさないこと。"""
    assert sw.outside_length_problems(_script(sw.outside_length_chars_floor())) == []


def test_long_script_is_not_caught_from_above():
    """**上では落とさないこと** —— 帯に上側の罰は測れていない。"""
    assert sw.outside_length_problems(_script(20_000)) == []


def test_the_leg_is_wired_into_the_outside_long_path():
    """`style: outside_long` の道から**実際に呼ばれている**こと（脚の数え落としを留める）。"""
    src = (ROOT / "src" / "script_writer.py").read_text(encoding="utf-8")
    head = src.split("def long_script_problems", 1)[1].split("\ndef ", 1)[0]
    assert "outside_length_problems(script)" in head, (
        "`long_script_problems` から呼ばれていません（本文に書いて口に繋がない形の6回目）")
    assert ("ナレーションの合計を 8,800〜9,800文字にすること", "outside_length_problems") \
        in sw.OUTSIDE_RULE_LEGS, "`OUTSIDE_RULE_LEGS` が数える口を指していません"
    # **番号を書かないこと** —— 規則の (1)〜(5) は 冒頭／章／締め／題・サムネ／間合い で、
    # 尺はその外の箇条書き。(3) と書くと「締め」を指します。
    assert not any(k == "ナレーションの合計を 8,800〜9,800文字にすること" and "(" in v
                   for k, v in sw.OUTSIDE_RULE_LEGS), "尺の脚に、他の節の番号が付いています"


def test_the_book_in_todays_slot_is_below_the_knee():
    """**この検査を足した理由そのもの** —— 09/05 の枠の本が切れ目を割っていること。

    この本が差し替わる（か、控えが消える）と落ちます。そのときは、
    **落ちたことが「差し替わった」の合図**なので、この検査ごと消してよい。
    """
    import json
    p = ROOT / "data" / "critique_queue" / "GFvAcxvDmYM.script.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    chars = sum(len(str(x.get("narration") or "")) for x in (d.get("segments") or []))
    assert chars < sw.outside_length_chars_floor(), (
        f"09/05 の枠の本が切れ目を越えました（{chars:,}字）。この検査は役目を終えています")
