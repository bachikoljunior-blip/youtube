"""**起こしを「置いた」か「置かなかった」かを、台帳に残す**（`next_round.wake_is_fresh`）。

**なぜ要るか**（2026-09-10 04:5x JST・optimizer・Opus が実測して足した。§5・METHOD §7 (d)）:

`wake_latency_minutes()` は 04:0x に「同じ届きを指す起こしを畳む」を入れ、その覆る条件 (3) に
**「重なりが半分を越えたら、親が起こしを2本 置くこと自体を見ること」**と書きました。
**その前提が、この回の実測で外れました** —— 親は 2本 置いていません。

    起こしを置いた行 **53** → 指した狙い先 **34**・うち **18** を 2行 以上 が指す
    **その 18 のどれ 1つ も、2回 届いていない**（狙い先 ±3分 に来た行は 0 か 1）
    重なった側 **19行 のうち 16行（84%）が :58〜:02** ＝ **毎時の心拍**

親は**起こしと心拍の両方で起きる**ので、間隔が明けていない回は必ず 2度 起きます。
2度目は `WAKE_SAME_SEC`（120秒）の門が正しく撃たせていません。
**＝ 重なりは「置きすぎ」ではなく「起こされすぎ」。**

**分けられなかった理由は道具の側に在りました**: 判定は `main()` にべた書きで、
`log_wake()` は**その手前**で行を書くので、**台帳は「親が起きた」しか残していません。**
だから「2本 置いた」と「2度 起こされた」が、あとから読むと**同じ形**に見えます
（§8 が 2度 書いた「呼ぶ側で1つずつ塞ぐ形は漏れる」の、**読む側での形**）。

この検査が見ているのは **`wake_placed` が台帳に残ること**と、**門がその答えのとおりに撃つこと**。
"""
import datetime as dt
import json

from scripts import next_round


def _at(minutes: float, base: dt.datetime) -> dt.datetime:
    return base + dt.timedelta(minutes=minutes)


def _use_wake(tmp_path, monkeypatch):
    p = tmp_path / "parent_wake.json"
    monkeypatch.setattr(next_round, "WAKE", p)
    return p


def test_置いてある起こしが無ければ_置く(tmp_path, monkeypatch):
    _use_wake(tmp_path, monkeypatch)
    now = dt.datetime(2026, 9, 10, 4, 0, tzinfo=dt.timezone.utc)
    fresh, pending = next_round.wake_is_fresh(_at(40, now), now=now)
    assert fresh is True and pending is None


def test_同じ届きを指す起こしが在れば_撃たない_これが本題(tmp_path, monkeypatch):
    """**実測の 18回 は全部これ** —— 心拍で 2度目に起きた回。"""
    _use_wake(tmp_path, monkeypatch)
    now = dt.datetime(2026, 9, 10, 4, 0, tzinfo=dt.timezone.utc)
    want = _at(40, now)
    next_round.wake_write(want, now=now)
    # 1分 あと（＝ 毎時の心拍）に、ほぼ同じ狙い先で起こされた
    later = _at(1, now)
    fresh, pending = next_round.wake_is_fresh(_at(39, later), now=later)
    assert fresh is False
    assert pending == want


def test_門より遠い起こしは別の届き_置く(tmp_path, monkeypatch):
    """`WAKE_SAME_SEC` より離れていれば、それは**別の届き**。畳んではいけない。"""
    _use_wake(tmp_path, monkeypatch)
    now = dt.datetime(2026, 9, 10, 4, 0, tzinfo=dt.timezone.utc)
    next_round.wake_write(_at(40, now), now=now)
    far = _at(40, now) + dt.timedelta(seconds=next_round.WAKE_SAME_SEC + 30)
    fresh, _ = next_round.wake_is_fresh(far, now=now)
    assert fresh is True


def test_過ぎた起こしは置いてある扱いにしない(tmp_path, monkeypatch):
    """既に届いた起こしを「置いてある」と読むと、**次の周をまるごと落とします**。"""
    _use_wake(tmp_path, monkeypatch)
    now = dt.datetime(2026, 9, 10, 4, 0, tzinfo=dt.timezone.utc)
    next_round.wake_write(_at(-5, now), now=_at(-45, now))
    fresh, pending = next_round.wake_is_fresh(_at(40, now), now=now)
    assert fresh is True and pending is None


def test_台帳に_wake_placed_が残る(tmp_path, monkeypatch):
    """`log_wake` は `decide()` の列を全部 写すので、**足すのは書き写しだけ**。"""
    p = tmp_path / "parent_wakes.jsonl"
    monkeypatch.setattr(next_round, "WAKES", p)
    next_round.log_wake({"go": False, "live": 0, "live_source": "--live",
                         "wait_min": 21.0, "roles": [], "why": "間隔の途中",
                         "wake_placed": False})
    (row,) = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert row["wake_placed"] is False


def test_本物の台帳では_重なりが二重の届きになっていない_これが前提の当のもの():
    """**04:0x の覆る条件 (3) の前提**（親が 2本 置いた）**が外れていること**を、実物で見る。

    同じ狙い先を 2行 以上 が指した回に、**その刻へ 2回 届いていたら** (3) は生きています。
    実測ではそれが **0回** なので、(3) は取り消してあります。
    この検査が落ちる回 ＝ 親が本当に 2本 置き始めた回 ＝ **(3) を書き直す回**。
    """
    rows = [r for r in next_round.wake_rows() if r.get("who") == "owner"]
    if len(rows) < 40:                      # 台帳が薄い環境では何も主張しない
        return
    got = sorted((t, r) for r in rows if (t := next_round._wake_at(r)) is not None)
    ats = [t for t, _ in got]
    aims: dict[dt.datetime, list[dt.datetime]] = {}
    for t, r in got:
        if r.get("go") or r.get("live"):
            continue
        wait = r.get("wait_min")
        if not wait:
            continue
        key = (t + dt.timedelta(minutes=float(wait))).replace(second=0, microsecond=0)
        aims.setdefault(key, []).append(t)
    twice = 0
    for key, srcs in aims.items():
        if len(srcs) < 2:
            continue
        # 狙い先の ±3分 に**届いた**行（置いた行そのものは数えない）
        landed = [a for a in ats
                  if abs((a - key).total_seconds()) <= 180 and a not in srcs]
        if len(landed) >= 2:
            twice += 1
    assert twice == 0, (
        f"同じ狙い先へ 2回 届いた回が {twice} 件 出ました ＝ 親が本当に起こしを"
        " 2本 置いています。`wake_latency_minutes` の覆る条件 (3) を書き直すこと")


# --- 2026-09-10 05:3x（optimizer・Opus）: **(2) の分母の門** ---------------------
#
# 04:5x が置いた新しい覆る条件 (2)「`wake_placed` が **False の行が 0 になったら**
# 畳みは要らない」には、**n が書かれていませんでした。**
# 書いた回には行が 0本、その1周あとには **2本・どちらも True** ＝ 文字どおりには
# **もう満たされています**。しかし置く側の癖は変わっていません（実測 32.3% が False の側）。
# ＝ **黙って通る門**（`rounding_evidence` の註が名指しした「通っても何も言えない門」の裏返し）。
# 下の 4件 は、その門が「数えられる本数」を持つことと、数が台帳へ出ることを見ます。


def test_列を持たない古い行は分母に入れない_これが本題():
    """列を足す前の行を False に数えると、**台帳のほとんどが「置かなかった」に化けます**。"""
    rows = [{"who": "owner", "wake_placed": True},
            {"who": "owner", "wake_placed": False},
            {"who": "owner"},                      # 列を足す前の行
            {"who": "sub", "wake_placed": True}]   # 親以外
    assert next_round.wake_placed_counts(rows) == (1, 1)


def test_門の本数は_率が変わらなくても通ってしまう確率が_5パーセントを切る所に在る():
    """実測の率 32.3% で `0.677 ** n < 0.05` を満たす最小の n が `WAKE_PLACED_MIN_N`。

    **陽性対照**: 門を 1つ 下げると 5% を越える（＝ この数は「切りのいい 10」ではない）。
    """
    n = next_round.WAKE_PLACED_MIN_N
    assert 0.677 ** n < 0.05
    assert 0.677 ** (n - 1) >= 0.05


def test_門に届かないうちは_False_が_0_でも引かれたと読まないこと():
    """いまの台帳（True 2本・False 0本）で (2) を読むと「引かれた」に化ける形。"""
    rows = [{"who": "owner", "wake_placed": True} for _ in range(2)]
    yes, no = next_round.wake_placed_counts(rows)
    assert no == 0                                   # 文字どおりには満たされる
    assert yes < next_round.WAKE_PLACED_MIN_N        # **が、まだ読んではいけない**


def test_decide_が数を台帳へ書き写す_手で数えないため(tmp_path, monkeypatch):
    """`gap_ratio_n` を書き忘れた 09:5x と同じ穴を、こちらで開けないこと。"""
    monkeypatch.setattr(next_round, "WAKES", tmp_path / "parent_wakes.jsonl")
    d = next_round.decide(live=1)
    assert "wake_placed_true" in d and "wake_placed_false" in d
