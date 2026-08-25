"""**Python から Google に届く CA の束を、実際に効くものに直す。**

2026-08-15 21:4x に、生成が 0/8 本で落ちて見つけました。

    ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
    certificate verify failed: unable to get local issuer certificate

## 何が起きていたか

このコンテナの外向き通信は、**中身を見る代理サーバ（agent proxy）を必ず通ります。**
だから相手から返ってくる証明書は Google のものではなく、**代理サーバが
その場で発行したもの**です。検証を通すには、代理サーバの CA を信頼する要る。

環境は最初から次の2つを立てています。

    SSL_CERT_FILE      = /root/.ccr/ca-bundle.crt
    REQUESTS_CA_BUNDLE = /root/.ccr/ca-bundle.crt

**その束に、実際に使われている CA が入っていませんでした**（実測）。

    /root/.ccr/ca-bundle.crt          証明書 24枚  → Python は失敗する
    /etc/ssl/certs/ca-certificates.crt 証明書 90枚  → 通る

`curl` は `SSL_CERT_FILE` を見ないので**成功し**、Python だけが落ちます。
だから「ネットワークは生きているのに Python の API 呼び出しだけ死ぬ」という、
いちばん読み違えやすい形で出ました。実際 8/15 21:4x の回は、
**8本ぜんぶ落ちた原因を最初「作る側の不具合」と読んでいます。**

## 直し方（**検証は切らない**）

2つの束を**つないだ1本**を作り、そちらを見せます。片方にしか入っていない
CA があっても通り、**将来 `/root/.ccr/ca-bundle.crt` が直っても壊れません。**

**`disable_ssl_certificate_validation` や `verify=False` は使わないこと。**
検証を切ると、代理サーバの向こうで何が起きても分からなくなります。
落ちているのは「信頼の材料が足りない」ことで、**検証そのものは正しく動いています。**

## なぜ `src/__init__.py` から呼ぶのか

`httplib2` は **import した時点で** 束の位置を決めて定数に焼きます
（`httplib2/certs.py` の `where()` → `httplib2/__init__.py` の `CA_CERTS`）。
**あとから環境変数を変えても効きません。**

`src` の下のモジュールは、`googleapiclient` を import する前に必ず
`src/__init__.py` を通ります。`python -m src.pipeline` のような
**子プロセスでも同じ順序で通る**ので、ここが唯一の置き場所になります。
"""
from __future__ import annotations

import os
from pathlib import Path

# つなぐ相手。**両方あれば両方入れる。** 片方しか無くても動く。
CANDIDATES = (
    Path("/etc/ssl/certs/ca-certificates.crt"),   # OS の束（curl が見ているのはこちら）
    Path("/root/.ccr/ca-bundle.crt"),             # 代理サーバが置く束
)

# つないだ束の置き場。**リポジトリの外**に置く（git に入れない・毎回作り直す）。
MERGED = Path(os.environ.get("YT_CA_BUNDLE", "/tmp/youtube-ca-bundle.crt"))

# 束の位置を見ている環境変数。**名前がライブラリごとに違う**ので全部立てる。
ENV_VARS = (
    "SSL_CERT_FILE",        # OpenSSL / Python の ssl
    "REQUESTS_CA_BUNDLE",   # requests
    "HTTPLIB2_CA_CERTS",    # httplib2（googleapiclient が使う）
    "CURL_CA_BUNDLE",       # curl とその薄い包み
)


def _read(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if "BEGIN CERTIFICATE" in text else ""


def build(force: bool = False) -> Path | None:
    """つないだ束を作って、その場所を返す。**材料が1つも無ければ None。**"""
    parts = [t for t in (_read(p) for p in CANDIDATES) if t]
    if not parts:
        return None
    body = "\n".join(part.strip() for part in parts) + "\n"
    if force or not MERGED.exists() or MERGED.read_text(errors="replace") != body:
        try:
            MERGED.parent.mkdir(parents=True, exist_ok=True)
            MERGED.write_text(body, encoding="utf-8")
        except OSError:
            # **書けなくても止めない。** 既にある環境変数のままで進む
            # （投稿が途切れるほうが損。ここは通らないこともある）。
            return MERGED if MERGED.exists() else None
    return MERGED


def apply() -> Path | None:
    """束を作って、環境変数を差し替える。**import のいちばん早いところで呼ぶ。**"""
    merged = build()
    if merged is None:
        return None
    for name in ENV_VARS:
        os.environ[name] = str(merged)
    return merged


def count() -> int:
    """つないだ束に何枚入っているか（検査と日誌のため）。"""
    return _read(MERGED).count("BEGIN CERTIFICATE")


if __name__ == "__main__":
    merged = apply()
    if merged is None:
        raise SystemExit("CA の束が1つも読めませんでした")
    for path in CANDIDATES:
        n = _read(path).count("BEGIN CERTIFICATE")
        print(f"{str(path):40s} {n:3d}枚" + ("" if n else "  ← 読めない/空"))
    print(f"{str(merged):40s} {count():3d}枚  ← これを見せます")

    import httplib2  # noqa: E402  ここまで環境変数を立ててから import する

    for host in ("oauth2.googleapis.com", "www.googleapis.com",
                 "texttospeech.googleapis.com"):
        try:
            resp, _ = httplib2.Http(timeout=20).request(f"https://{host}/", "GET")
            print(f"  {host:32s} 通った（HTTP {resp.status}）")
        except Exception as exc:  # noqa: BLE001
            print(f"  {host:32s} **落ちた**: {type(exc).__name__}: {exc}")
