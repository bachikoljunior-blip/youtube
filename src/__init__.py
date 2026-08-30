"""**ここは、何より先に走る場所です。** 重い import を足さないこと。

`src.netcerts` だけを呼んでいるのは、`httplib2` が **import した瞬間に**
CA の束の位置を定数へ焼くからです（`src/netcerts.py` に理由の全文）。
`googleapiclient` を使うモジュールは全部 `src` の下にあるので、
**ここで直せば、子プロセス（`python -m src.pipeline`）でも同じ順序で効きます。**

2026-08-30 以降は、現行の AI 金融ペルソナが YouTube の収益化ポリシーに
抵触するため、生成・投稿系 entry point を最初に止める。分析系は止めない。
"""
from . import netcerts as _netcerts
from .pause_guard import enforce_current_process as _enforce_current_process

_enforce_current_process()
_netcerts.apply()
