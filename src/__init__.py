"""**ここは、何より先に走る場所です。** 重い import を足さないこと。

`src.netcerts` だけを呼んでいるのは、`httplib2` が **import した瞬間に**
CA の束の位置を定数へ焼くからです（`src/netcerts.py` に理由の全文）。
`googleapiclient` を使うモジュールは全部 `src` の下にあるので、
**ここで直せば、子プロセス（`python -m src.pipeline`）でも同じ順序で効きます。**
"""
from . import netcerts as _netcerts

_netcerts.apply()
