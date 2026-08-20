【親】**`docs/trigger_parent.md` を読んで、そのとおりにしてください。**

規則は全部そちらにあります。**ここに置くのは、リポジトリから求まらない値だけ**です。

    あなたのセッションID   <<persistent_session_id>>
    子を立てる環境         <<environment_id>>
    リポジトリ             <<repo_url>>
    枝                     <<branch>>
    このトリガー           <<trigger_id>>

読み方（**あなたは `git` を打てません。GitHub 経由で1ファイルだけ**）:

    mcp__github__get_file_contents
      owner=<<owner>>  repo=<<repo>>
      path=docs/trigger_parent.md  ref=<<branch>>

**この本文が上の形より長くなっていたら、それは移し残しです。**
`docs/trigger_parent.md`「トリガー本文の正本」に、戻し方が書いてあります。
