"""**冷読が英語で返る draw**（`critic.lang_of` / `critic.cold_read` の引き直し / `cli read` の印字）。

2026-09-11 23:4x（optimizer・Opus）に足した —— §15 の申し送り（`critic.py`・hourly が 23:1x に数えた）。
実測の出どころは台帳 `data/studio/ledger.jsonl` の `cold_read` **79件 のうち 6件（7.6%）**が
`takeaway` を丸ごと英語で返した所（09/06 19:45・09/08 00:58・09/09 00:51・09/09 18:17・
**09/11 23:12 は同じ周に 2件**）。**英語の draw は `unclear` の件数が別物になります**
（0件 と 3件 対 日本語 5件 ＝ §4 (1) が周をまたいで比べる当のもの）。

陽性対照は 3つ:
  `test_日本語の返しは引き直さない`（引き直しの門を外すと 2回 引いて落ちる）
  `test_英語のままでも返した側は捨てた側に入れない`（返した draw を `dropped` にも入れると落ちる）
  `test_促しに日本語の指定が在る`（促しから 1行 外すと落ちる ＝ 値段 0 の手のほう）
"""
from studio import critic, script


class _Draws:
    """`critic.ask` の代わり。決めた JSON を順に返すだけ（`claude -p` を回さない）。"""

    def __init__(self, *results: str):
        self.results = list(results)
        self.prompts: list[str] = []

    def __call__(self, prompt, model="sonnet", timeout=300):
        self.prompts.append(prompt)
        return self.results[min(len(self.prompts), len(self.results)) - 1]


JA = '{"takeaway": "退職金の非課税枠は勤続年数で決まります。", "unclear": ["累進"]}'
EN = '{"takeaway": "Severance pay has a tax-free threshold.", "unclear": ["progressive taxation"]}'


def _script():
    return script.Script(
        id="t-cold", date="2026-09-12", title="t", takeaway="t", description="t", tags=["t"],
        segments=[script.Segment(say="これはためしの文です。", show="ためし")],
    )


# ---------- 言語の述語 ----------

def test_仮名か漢字が1字でも在れば日本語():
    assert critic.lang_of("退職金の話です。") == "ja"
    assert critic.lang_of("iDeCo は 60歳まで") == "ja"
    assert critic.lang_of("カタカナ") == "ja"


def test_仮名も漢字も無ければ英語():
    assert critic.lang_of("Severance pay has a tax-free threshold.") == "en"
    assert critic.lang_of("") == "en"
    assert critic.lang_of(None) == "en"


def test_台帳の6件はどれも英語と読める():
    """**実物の形を列挙してから門を置く**（§5 の教訓 4つ目）。台帳に在った 6件 の写し。"""
    for t in ["Delaying pension from age 65 to 70 increases monthly payments by 42%.",
              "People receiving pension from age 65 get extra monthly money.",
              "When a spouse receiving an occupational pension dies, the surviving spouse receives 3/4.",
              "When a husband receiving occupational pension dies, the widow's total annual pension decreases.",
              "Japan has a special tax system for lump-sum retirement bonuses.",
              "Severance pay receives favorable tax treatment with a tax-free threshold."]:
        assert critic.lang_of(t) == "en"


# ---------- 引き直し ----------

def test_日本語の返しは引き直さない(monkeypatch):
    """**陽性対照**: `lang_of(...) == "ja"` の break を外すと、ここが 2回 引いて落ちる。"""
    ask = _Draws(JA, EN)
    monkeypatch.setattr(critic, "ask", ask)
    r = critic.cold_read(_script())
    assert len(ask.prompts) == 1
    assert r["lang"] == "ja"
    assert r["dropped"] == []


def test_英語で返ったら1回だけ引き直す(monkeypatch):
    ask = _Draws(EN, JA)
    monkeypatch.setattr(critic, "ask", ask)
    r = critic.cold_read(_script())
    assert len(ask.prompts) == 2
    assert r["lang"] == "ja"
    assert r["takeaway"].startswith("退職金")
    assert r["dropped"] == ["Severance pay has a tax-free threshold."]


def test_英語のままでも返した側は捨てた側に入れない(monkeypatch):
    """**陽性対照**: 返した draw まで `dropped` に入れると、同じ 1 draw を 2回 数えることになる
    （次の回が「引き直しの回数」で覆る条件 (1) を数えるので、そこが二重になる）。"""
    ask = _Draws(EN, EN)
    monkeypatch.setattr(critic, "ask", ask)
    r = critic.cold_read(_script())
    assert len(ask.prompts) == 2
    assert r["lang"] == "en"
    assert len(r["dropped"]) == 1        # 捨てたのは 1回目 だけ。2回目 は返り値の側


def test_引き直しの回数はtriesで決まる(monkeypatch):
    ask = _Draws(EN, EN, EN)
    monkeypatch.setattr(critic, "ask", ask)
    r = critic.cold_read(_script(), tries=3)
    assert len(ask.prompts) == 3
    assert len(r["dropped"]) == 2
    ask2 = _Draws(EN)
    monkeypatch.setattr(critic, "ask", ask2)
    assert critic.cold_read(_script(), tries=1)["dropped"] == []


# ---------- 値段 0 の手（促し） ----------

def test_促しに日本語の指定が在る(monkeypatch):
    """**陽性対照**: 促しから この 1行 を外すと落ちる。引き直しは 7.6% の回にだけ 1 draw 掛かるが、
    促しは **0 draw** なので、こちらが先に効くこと（`cold_read` の覆る条件 (1)）。"""
    ask = _Draws(JA)
    monkeypatch.setattr(critic, "ask", ask)
    critic.cold_read(_script())
    assert "かならず日本語で書いてください" in ask.prompts[0]
