# Raft on Weekends
Delight 2024の夏合宿用。
このレポジトリはRaftを作成するためのひな形を提供します。
具体的にはノード間が実装されています。
この上にRaftの機能（RequestVote, AppendEntries）を実装します。

## 必要な環境
- Docker
- Docker Compose
- Python 3.x (with pyyaml)

## 日程と内容 
日程と各種内容です。
進捗状況によって、行う内容は変更します。
各Docsは最低限の説明のみ記載しています。
わかないことがあれば適宜メンターに相談するか、自分で調べて実装を進めることにする。

### 1日目
実装に必要な知識の習得
- [イントロダクション(0-intro.md)](docs/0-intro.md)
- [並列/並行処理入門(1-parallel-pcoessing.md)](docs/1-parallel-pcoessing.md)
- [一貫性モデル入門(2-consistency.md)](docs/2-consistency.md)
- [Raftの説明(3-raft.md)](docs/3-raft.md)

### 2日目以降
Pythonを用いた実装
- [このレポジトリのファイル構成について(4-repo.md)](docs/4-repo.md)
- [ハンズオンの説明(5-handson.md)](docs/5-handson.md)

## 問い合わせ
moz [at] sfc.wide.ad.jp
