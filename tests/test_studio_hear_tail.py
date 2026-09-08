"""**長いコマの末尾の切り落とし**を、TTS の誤読と分ける手（`hear.tail_gap` / `hear.tail_probe`）。

2026-09-09 05:5x（optimizer・Opus）に足した。実測の出どころは 09/10 の本 `2026-09-10-izoku-kosei-4bunno3` コマ8
（59字・11.1秒）——small も medium も末尾の「多ければ計算が変わります」を1字も書かず、
`escalate`（段を上げる）は「差が減らない」と見て small のまま置いていた。
**末尾 5秒 だけを同じ medium に渡すと、0差 で聞こえる。**
＝ 段を上げる手と、末尾だけを聞き直す手は、**同じ音に別の答えを返す**（§5 の「教訓の形」）。

陽性対照は `test_誤読は末尾を聞き直しても通さない`（同じコマの末尾を「年66万円ふえます」＝
Neural2-D が「とし」と読む語に差し替えた実測の再現）。**これが落ちない検査は、切り落としと誤読を分けていない。**
"""
from pathlib import Path

from studio import hear


class _FakeHearer:
    """末尾の切り出しに対して、決めた仮名を返すだけ（whisper を回さない）。"""

    def __init__(self, heard: str):
        self.heard = heard
        self.calls: list[Path] = []

    def transcribe(self, wav, prompt=None):
        self.calls.append(wav)
        return self.heard


def _probe(monkeypatch, tmp_path, missing: str, tail_heard: str) -> dict:
    wav = tmp_path / "seg.wav"
    wav.write_bytes(b"")
    monkeypatch.setattr(hear, "probe_duration", lambda p: 11.1)
    monkeypatch.setattr(hear, "run", lambda cmd: (tmp_path / "seg-tail.wav").write_bytes(b""))
    return hear.tail_probe(_FakeHearer(tail_heard), wav, missing, {})


# ---------- どの差が「末尾の切り落とし」か ----------

def test_末尾が丸ごと無い差だけを拾う():
    exp = "つまのぶんがおとのはんぶんよりすくないときのかたちでおおければけさんがかわります"
    assert hear.tail_gap(exp, [("おおければけさんがかわります", "")]) == "おおければけさんがかわります"


def test_途中の差や置き換えは拾わない():
    exp = "ねんきんはまいとしきゅじゅまんえんです"
    # 置き換え（誤読）は末尾でも拾わない —— 音は在って、別に聞こえている
    assert hear.tail_gap(exp, [("ねんきん", "めんきん")]) is None
    # 末尾ではない欠け
    assert hear.tail_gap(exp, [("まいとし", ""), ("です", "でした")]) is None
    # 短すぎる欠け（1〜3字）は whisper の語尾の揺れと分けられないので拾わない
    assert hear.tail_gap(exp, [("です", "")]) is None
    assert hear.tail_gap(exp, []) is None


# ---------- 末尾だけを聞き直す ----------

def test_切り落としは末尾を聞き直すと0差(monkeypatch, tmp_path):
    # 実測（09/10 の本 コマ8・末尾 5秒 medium）: 頭に前の語が入り込むが、末尾は予定どおり
    r = _probe(monkeypatch, tmp_path, "おおければけさんがかわります",
               "はんぶんよりすくないときのかたちでおおければけさんがかわります")
    assert r["ok"] and r["diffs"] == []


def test_誤読は末尾を聞き直しても通さない(monkeypatch, tmp_path):
    """**陽性対照**（この検査が落ちないなら、切り落としと誤読を分けていない）。

    実測: 同じコマの末尾を「年66万円ふえます」に差し替えて焼くと、全部の聞き取りは**同じ形**で切れ
    （予定「ねんろくじゅろくまんえんふえます」 聞こえた「」）、末尾 5秒 だけが「とし…」と聞こえた。"""
    r = _probe(monkeypatch, tmp_path, "ねんろくじゅろくまんえんふえます",
               "いちによりすくないときのかたちでとしろくじゅろくまんへんふえます")
    assert not r["ok"] and r["diffs"]


def test_音が無ければ通さない(monkeypatch, tmp_path):
    """TTS が末尾を読んでいない（本当に音が無い）ときは、末尾 5秒 は前の語だけになる。"""
    r = _probe(monkeypatch, tmp_path, "おおければけさんがかわります",
               "つまのぶんがおとのはんぶんよりすくないときのかたちで")
    assert not r["ok"]


def test_頭の入り込みは差にしない(monkeypatch, tmp_path):
    """切り出した頭に前の語が残るのは音の在り方の話で、コマの差ではない（exp 側が空の差は落とす）。"""
    r = _probe(monkeypatch, tmp_path, "けさんがかわります",
               "ときのかたちでおおければけさんがかわります")
    assert r["ok"]
