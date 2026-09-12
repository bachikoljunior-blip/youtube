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


def _deliveries(ats: list[dt.datetime]) -> list[dt.datetime]:
    """**「何回 届いたか」は、行の数ではなく `WAKE_SAME_SEC` で数える**
    （2026-09-12 09:4x・optimizer・Opus。**この検査が初めて落ちた回に直した**）。

    `WAKE_SAME_SEC`（120秒）は `next_round` 自身が置いている
    **「同じ届きと見なす幅」**です。下の検査はそれを使わず**行をそのまま数えて**いたので、
    **門が 2か所 に別々の幅で書かれて**いました（§5 ——「門は 1か所」）。

    **実物**（この回に落ちた 1件・狙い先 2026-09-12 00:04Z）: 届いたとされた 2行 は
    **00:05:46 の GO** と **その 25秒 後の 00:06:11 の WAIT**（`前の周の開始から 0分`）で、
    **25秒 ＝ 同じ届きの幅の中**です。これは 04:5x の註が既に名指ししている
    「**親は起こしと心拍の両方で起きるので、間隔が明けていない回は必ず 2度 起きる**」
    ＝ **起こされすぎ**の側で、**置きすぎ**（(3) が見ようとしている物）ではありません。
    ＝ **このままでは、覆る条件 (3) は「心拍が在ること」で引かれます。**

    **覆る条件**: 幅の外（120秒 より離れた）2回目の届きが出たら、この畳みでも落ちます
    ＝ **そのときが本当に (3) を書き直す回**（陽性対照は下の検査）。
    `WAKE_SAME_SEC` を動かす回は、こちらも一緒に動きます（同じ定数を読む）。
    """
    out: list[dt.datetime] = []
    for a in sorted(ats):
        if out and (a - out[-1]).total_seconds() <= next_round.WAKE_SAME_SEC:
            continue
        out.append(a)
    return out


def test_届きは行ではなく_WAKE_SAME_SEC_で数える_陽性対照つき():
    """**畳みが効くことと、幅の外なら落ちることの両方**を見る（§5 教訓の形 3つ目）。"""
    base = dt.datetime(2026, 9, 12, 0, 5, tzinfo=dt.timezone.utc)
    近い = [base, base + dt.timedelta(seconds=25)]
    assert len(_deliveries(近い)) == 1, "同じ届きの幅の中は 1回"
    遠い = [base, base + dt.timedelta(seconds=next_round.WAKE_SAME_SEC + 1)]
    assert len(_deliveries(遠い)) == 2, (
        "**陽性対照** —— 幅の外の 2回目は落ちないこと（落ちたら上の検査は何も見張らない）")
    assert _deliveries([]) == []


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
        if len(_deliveries(landed)) >= 2:
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

# ---- 2026-09-10 08:3x（optimizer・Opus）: 覆る条件 (3) を「読める形」にした ----
# `wake_is_fresh` の (3) は「`wake_placed` が **True の行だけ** を数えた中央値」と書いてあり、
# そのとおり **行ごと** 絞ると **届いた側の行まで落ちて 届き 0本**（門 5本）＝ **1度も読めない**。
# 絞るのは **頼んだ側の行だけ**（`placed_only`）。**陽性対照つき**。


def _wake_rows(base, spec):
    """`(基準からの分, 頼んだ分数 or None, wake_placed or None)` の並びを台帳の行にする。"""
    out = []
    for mins, asked, placed in spec:
        row = {"who": "owner", "at": _at(mins, base).isoformat()}
        if asked is not None:
            row["wake_min"] = asked
        if placed is not None:
            row["wake_placed"] = placed
        out.append(row)
    return out


#: 頼み 5本（True・遅れ 1.0〜1.4分）＋ 頼み 6本（False・遅れ 5.0〜7.5分）。
#: **届きの行は `wake_placed` の列を持ちません** —— 05:3x に列が足される前の
#: 台帳の行と同じ形で、実物の届きのほとんどがこの形です。
_TRUE_LAGS = (1.0, 1.1, 1.2, 1.3, 1.4)
_FALSE_LAGS = (5.0, 5.5, 6.0, 6.5, 7.0, 7.5)


def _rows_for_placed_only(base):
    spec = []
    for i, lag in enumerate([(x, True) for x in _TRUE_LAGS] + [(x, False) for x in _FALSE_LAGS]):
        lag_min, placed = lag
        spec.append((120.0 * i, 60, placed))
        spec.append((120.0 * i + 60.0 + lag_min, None, None))
    return _wake_rows(base, spec)


def test_placed_onlyは頼んだ側だけを絞る_届いた側は絞らない():
    """**陽性対照の当のもの**: 「True の行だけ」を行ごと絞ると、届いた側（列を持たない行）まで
    落ちて **届き 0本** になり、写しへ倒れる（＝ (3) を 1度も読めない）。"""
    base = dt.datetime(2026, 9, 10, 0, 0, tzinfo=dt.timezone.utc)
    got, why = next_round.wake_latency_minutes(_rows_for_placed_only(base), placed_only=True)
    assert "写し" not in why
    assert "届き 5回" in why
    assert abs(got - 1.2) < 0.01


def test_placed_onlyを渡さなければ_Falseの行も数える():
    """陰性対照: 既定（畳みの側）は `wake_placed` を見ない ＝ False の 6本 も分母に入る。"""
    base = dt.datetime(2026, 9, 10, 0, 0, tzinfo=dt.timezone.utc)
    got, why = next_round.wake_latency_minutes(_rows_for_placed_only(base))
    assert "届き 11回" in why
    assert abs(got - 5.0) < 0.01


def test_2つが割れたら道具がそう答える():
    """(3) の門そのものの陽性対照: 割れる台帳では 0.5分 以上 の差が出ること
    （＝ 門が「必ず通る」側に寝ていない）。"""
    base = dt.datetime(2026, 9, 10, 0, 0, tzinfo=dt.timezone.utc)
    rows = _rows_for_placed_only(base)
    folded, _ = next_round.wake_latency_minutes(rows)
    placed, _ = next_round.wake_latency_minutes(rows, placed_only=True)
    assert abs(folded - placed) >= 0.5
