"""**コマの頭の切り落とし**を、TTS の誤読と分ける手（`hear.head_gap` / `head_probe` / `head_voice` /
`energy_start`）と、鳴ったコマに文の字数を並べる所（`script.sentence_lens`）。

2026-09-11 22:4x（optimizer・Opus）に足した —— §15 の申し送り (1)(2)。
実測の出どころは 09/11 10:3x（`hourly`・Opus）の 09/12 の本 コマ6（43字・8.32秒）:
`予定「けさんするとさんじゅねんのち」 聞こえた「」` ＝ **頭の 13字 が丸ごと無い**。
そのとき `tail_gap`/`tail_probe`/`tail_rate`/`tail_voice` は **4つ とも末尾を見る**ので 1行も印字されず、
手で撃った頭の窓（先頭 4秒）だけが `けいさんすると30…` と書いた。

陽性対照は 3つ:
  `test_末尾の欠けを頭の口が拾わない`（位置を見ていない門は落ちる）
  `test_丸ごと空は頭の口に入らない`（`e != exp` を外すと落ちる ＝ 同じ行を 2つ の口が数える）
  `test_誤読は頭を聞き直しても通さない`（`tail_probe` の陽性対照の鏡）
"""
from pathlib import Path

from studio import hear, script


class _FakeHearer:
    """切り出しに対して、決めた仮名を返すだけ（whisper を回さない）。"""

    def __init__(self, heard: str, words: list | None = None):
        self.heard = heard
        self.words = words or []
        self.calls: list[Path] = []

    def transcribe(self, wav, prompt=None):
        self.calls.append(wav)
        return self.heard

    def transcribe_words(self, wav, prompt=None):
        return self.words


def _probe(monkeypatch, tmp_path, missing: str, head_heard: str) -> dict:
    wav = tmp_path / "seg.wav"
    wav.write_bytes(b"")
    monkeypatch.setattr(hear, "run", lambda cmd: (tmp_path / "seg-head.wav").write_bytes(b""))
    return hear.head_probe(_FakeHearer(head_heard), wav, missing, {})


# ---------- どの差が「頭の切り落とし」か ----------

def test_頭が丸ごと無い差だけを拾う():
    exp = "けさんするとさんじゅねんのちごじゅまんえんになります"
    assert hear.head_gap(exp, [("けさんするとさんじゅねんのち", "")]) == "けさんするとさんじゅねんのち"


def test_末尾の欠けを頭の口が拾わない():
    """**陽性対照**: 位置を見ていない門は、ここで落ちる。"""
    exp = "つまのぶんがすくないときのかたちでおおければけさんがかわります"
    assert hear.head_gap(exp, [("おおければけさんがかわります", "")]) is None


def test_丸ごと空は頭の口に入らない():
    """**陽性対照**: `e != exp` を外すと、同じ行を `tail_gap` と 2つ で数えることになる。"""
    exp = "けさんするとさんじゅねんのち"
    assert hear.head_gap(exp, [(exp, "")]) is None
    assert hear.tail_gap(exp, [(exp, "")]) == exp   # そちらは前からこの行を持っている


def test_短い欠けと聞こえた欠けは拾わない():
    exp = "けさんするとさんじゅねんのちごじゅまんえん"
    assert hear.head_gap(exp, [("けさん", "")]) is None                      # 4字 未満
    assert hear.head_gap(exp, [("けさんするとさん", "けいさん")]) is None    # 聞こえている
    assert hear.head_gap(exp, []) is None


# ---------- 頭 4秒 を聞き直す ----------

def test_頭を聞き直して在れば切り落とし(monkeypatch, tmp_path):
    r = _probe(monkeypatch, tmp_path, "けさんするとさんじゅねんのち",
               "けさんするとさんじゅねんのちごじゅまんえんに")   # 窓の末に次の語が入り込む
    assert r["ok"] and r["diffs"] == []


def test_誤読は頭を聞き直しても通さない(monkeypatch, tmp_path):
    """**陽性対照**（`tail_probe` の鏡）: 別の語で読まれていれば、頭の窓でも差が残る。"""
    r = _probe(monkeypatch, tmp_path, "ねんろくじゅろくまんえん", "としろくじゅろくまんえんふえます")
    assert not r["ok"] and r["diffs"]


def test_頭の窓も切られたら差が残る(monkeypatch, tmp_path):
    """`tail_probe` が 06:5x に踏んだ穴の、頭の側（窓の中の頭も落ちることが在る）。"""
    r = _probe(monkeypatch, tmp_path, "けさんするとさんじゅねんのち", "ごじゅまんえんになります")
    assert not r["ok"]


# ---------- 音の側（聞き取りを通らない片側） ----------

def test_音の始まりは最初に閾を越えた窓(monkeypatch, tmp_path):
    monkeypatch.setattr(hear, "_loud_windows", lambda w, t, n: [4, 5, 6, 20])
    assert hear.energy_start(tmp_path / "a.wav", 0.05, 0.05) == 0.2
    assert hear.energy_end(tmp_path / "a.wav", 0.05, 0.05) == 1.05
    monkeypatch.setattr(hear, "_loud_windows", lambda w, t, n: [])
    assert hear.energy_start(tmp_path / "a.wav", 0.05, 0.05) == 0.0


def test_頭に音が在れば音は在ると言う(monkeypatch, tmp_path):
    monkeypatch.setattr(hear, "energy_start", lambda w: 0.10)
    h = _FakeHearer("", [("ごじゅ", 2.50, 2.9)])
    assert hear.head_voice(h, tmp_path / "a.wav")["verdict"] == "音は在る"


def test_頭に音が無ければ音が無いと言う(monkeypatch, tmp_path):
    monkeypatch.setattr(hear, "energy_start", lambda w: 0.10)
    h = _FakeHearer("", [("けい", 0.20, 0.6)])
    assert hear.head_voice(h, tmp_path / "a.wav")["verdict"] == "音が無い"


def test_あいだは分けられないと言う(monkeypatch, tmp_path):
    monkeypatch.setattr(hear, "energy_start", lambda w: 0.10)
    h = _FakeHearer("", [("けい", 0.40, 0.8)])
    assert hear.head_voice(h, tmp_path / "a.wav")["verdict"] == "分けられない"


def test_語が1つも返らない回は分けられない(monkeypatch, tmp_path):
    monkeypatch.setattr(hear, "energy_start", lambda w: 0.10)
    r = hear.head_voice(_FakeHearer("", []), tmp_path / "a.wav")
    assert r["verdict"] == "分けられない" and r["gap"] is None


def test_閾は頭と末尾で同じ():
    assert hear.voice_verdict(hear.VOICE_GAP_PRESENT) == "音は在る"
    assert hear.voice_verdict(hear.VOICE_GAP_ABSENT - 0.01) == "音が無い"


# ---------- 秒数の側は位置を見ない ----------

def test_秒数は頭でも同じ口が当たる(monkeypatch):
    rows = [
        {"i": 1, "exp": "あ" * 40, "diffs": [], "_gap": None, "_head": None, "_wav": "1.wav"},
        {"i": 2, "exp": "あ" * 50, "diffs": [], "_gap": None, "_head": None, "_wav": "2.wav"},
        {"i": 3, "exp": "あ" * 43, "diffs": [("あ" * 13, "")], "_gap": None, "_head": "あ" * 13,
         "_wav": "3.wav"},
    ]
    durs = {"1.wav": 8.0, "2.wav": 10.0, "3.wav": 8.32}
    monkeypatch.setattr(hear, "probe_duration", lambda w: durs[w])
    hear._add_rates(rows)
    assert rows[2]["rate"]["where"] == "頭"
    assert rows[2]["rate"]["present"]            # 43/8.32=5.17 は帯の中・30/8.32=3.61 は帯の外
    assert "rate" not in rows[0]


# ---------- 文の字数（申し送り (1)） ----------

def test_文の字数を頭から順に返す():
    # 句点は文の側に付く（`_SENT_END` は後読みで切る ＝ `long_sentences` と同じ数え方）
    assert script.sentence_lens("けいさんします。30年のうち、はじめの20年はこうです。") == [8, 20]
    assert script.sentence_lens("") == []


def test_長い文の門と同じ切り方():
    """**`long_sentences` と同じ数**であること（食い違うと `lint` の `[?]` と `hear` の印字がずれる）。"""
    say = "あ" * 40 + "。" + "い" * 10 + "。"
    assert script.sentence_lens(say) == [41, 11]
    assert len(script.long_sentences(say)) == 1   # MAX_SENTENCE 40 を越えるのは 1文
    assert max(script.sentence_lens("あ" * 39 + "。")) == 40
    assert script.long_sentences("あ" * 39 + "。") == []
