import asyncio
from .logger import logger
import random
from .timer import Timer
import uuid
class State:
    """基本的にはここに必要なメソッドや変数を追加していく"""
    
    def __init__(self, node):
        self.node = node
        self.loop = self.node.loop or asyncio.get_event_loop()
        
        # Raftの状態
        self.current_term = 0  # 現在のターム
        self.voted_for = None  # このタームで投票したノード
        self.state = 'follower'  # ノードの状態（follower, candidate, leader）
        self.leader_id = None
        
        # ログとステートマシン
        self.logs = []  # ログエントリのリスト
        self.statemachine = {}  # キーバリューストア
        self.commit_index = -1  # コミット済みの最新のログインデックス
        self.last_applied = -1  # ステートマシンに適用された最新のログインデックス
        
        # リーダー専用の状態
        self.next_index = {}  # 各フォロワーに送信する次のログインデックス
        self.match_index = {}  # 各フォロワーで複製されたログの最新インデックス
        
        # タイマー
        self.election_timer = None
        self.heartbeat_timer = None
        
        # クライアントのWrite要求を追跡するための辞書
        self.pending_requests = {}

        ## cca-Raft
        self.share_buckets = {}
        self.bucket_events = {}

        self.garbage_collection_timer = None



    def init_timers(self):
        # 選挙タイムアウトタイマーの設定（150-300msのランダムな時間）
        election_timeout = random.randint(150, 300) / 1000
        self.election_timer = Timer(
            interval=election_timeout,
            callback=self.start_election
        )
        
        # ハートビートタイマーの設定（固定値50ms）
        self.heartbeat_timer = Timer(
            interval=0.05,
            callback=self.send_heartbeat
        )


        # 古いバケットを削除するタイマー
        self.garbage_collection_timer = Timer(
            interval=10,
            callback=self.garbage_collection
        )

    async def start_election(self):
        """選挙を開始する"""
        self.state = 'candidate'
        self.current_term += 1
        self.voted_for = self.node.name
        self.received_votes = 1  # 自分への投票を含める
        
        logger.info(f"Node {self.node.name} starting election for term {self.current_term}")
        
        # 投票要求を送信
        request = {
            'type': 'RequestVote',
            'term': self.current_term,
            'candidate_id': self.node.name,
            'last_log_index': len(self.logs) - 1,
            'last_log_term': self.logs[-1]['term'] if self.logs else 0
        }
        
        # クラスタ内の全ノードに投票要求を送信
        await self.node.broadcast(request)

    # サンプルプログラム：ノードから受信したら、カウンターを増やす
    # data: {"sender": "node_name", "data": "data"}
    # sedner: 送信元のノード名
    # data: 送信元から受信したデータ
    async def receive(self, data):
        """メッセージを受信したときの処理
        - RequestVote: 投票要求
        - RequestVoteResponse: 投票応答
        - AppendEntries: ログ追加要求/ハートビート
        - AppendEntriesResponse: ログ追加応答
        - ClientWrite: クライアントからのWrite要求
        """
        message = data.get('data', {})
        message_type = message.get('type')
        term = message.get('term', 0)
        
        if term > self.current_term:
            self.current_term = term
            self.state = 'follower'
            self.voted_for = None
            self.leader_id = None
        
        if message_type == 'RequestVote':
            await self.handle_vote_request(message)
        elif message_type == 'RequestVoteResponse':
            await self.handle_vote_response(message)
        elif message_type == 'AppendEntries':
            await self.handle_append_entries(message)
        elif message_type == 'AppendEntriesResponse':
            message['sender'] = data.get('sender')
            await self.handle_append_entries_response(message)
        elif message_type == 'ClientWrite':  # クライアントからのWrite要求を処理
            message['sender'] = data.get('sender')
            await self.handle_client_write(message)
        elif message_type == 'ClientWriteShare':  # クライアントからのRead要求を処理
            await self.handle_client_write_share(message)
        elif message_type == 'ClientGetShare':
            await self.handle_client_get_share(message)

    async def start(self):
        """ノードの起動時の初期化処理"""
        logger.info(f"{self.node.name} starting as {self.state}")
        self.init_timers()
        self.garbage_collection_timer.start() # 古いバケットを削除するタイマーを開始
        
        if self.state == 'follower':
            # logger.info(f"{self.node.name} starting election timer")
            self.election_timer.start()  # フォロワーの場合のみ選挙タイマーを開始

    async def send_heartbeat(self):
        """ハートビートを送信する"""
        # logger.info(f"Node {self.node.name} sending heartbeat")
        if self.state != 'leader':
            return
        
        # AppendEntriesリクエストを作成（空のエントリで）
        for node in self.node.cluster:
            # クライアントの場合には送信する
            if not node.is_myself:
                prev_index = self.next_index[node.name] - 1
                request = {
                    'type': 'AppendEntries',
                    'term': self.current_term,
                    'leader_id': self.node.name,
                    'prev_log_index': prev_index,
                    'prev_log_term': self.logs[prev_index]['term'] if prev_index >= 0 else 0,
                    'entries': [],
                    'leader_commit': self.commit_index
                }
                await node.send(request)

    async def replicate_log(self, node_name):
        """特定のフォロワーにログをレプリケートする"""
        if self.state != 'leader':
            return
        
        next_idx = self.next_index[node_name]
        entries = self.logs[next_idx:]
        
        request = {
            'type': 'AppendEntries',
            'term': self.current_term,
            'leader_id': self.node.name,
            'prev_log_index': next_idx - 1,
            'prev_log_term': self.logs[next_idx - 1]['term'] if next_idx > 0 else 0,
            'entries': entries,
            'leader_commit': self.commit_index
        }
        
        node = next(n for n in self.node.cluster if n.name == node_name)
        await node.send(request)

    async def apply_logs(self):
        """コミット済みのログをステートマシンに適用する"""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.logs[self.last_applied]
            
            self.statemachine[entry['command']['key']] = {
                'value': entry['command']['value'],
                'bucket_id': entry['command']['bucket_id']
            }
        # logger.info(f"{self.node.name} applied log {self.last_applied}")

    async def become_leader(self):
        """リーダーになった時の初期化処理"""
        if self.state != 'candidate':
            return
        
        self.state = 'leader'
        self.leader_id = self.node.name
        logger.info(f"{self.node.name} became leader for term {self.current_term}")
        
        # リーダー状態の初期化
        for node in self.node.cluster:
            if not node.is_myself:
                self.next_index[node.name] = len(self.logs)
                self.match_index[node.name] = -1
        
        # 選挙タイマーを停止し、ハートビートタイマーを開始
        self.election_timer.stop()
        self.heartbeat_timer.start()
        
        # 最初のハートビートを即座に送信
        await self.send_heartbeat()

    async def handle_vote_response(self, message):
        """投票の応答を処理する"""
        if self.state != 'candidate' or message['term'] != self.current_term:
            return
        
        # 投票を集計
        if message.get('vote_granted'):
            self.received_votes += 1
        
        # 過半数の投票を得たらリーダーになる
        cluster_size = len(self.node.cluster)
        if self.received_votes > cluster_size // 2:
            await self.become_leader()

    async def handle_vote_request(self, message):
        """投票要求を処理する"""
        # 投票条件をチェック
        vote_granted = False
        
        # 1. 要求のタームが現在のターム以上
        # 2. まだ投票していないか、同じ候補者に投票している
        # 3. 候補者のログが自分のログと同じかより新しい
        candidate_log_ok = (
            message['last_log_term'] > (self.logs[-1]['term'] if self.logs else 0) or
            (message['last_log_term'] == (self.logs[-1]['term'] if self.logs else 0) and
             message['last_log_index'] >= len(self.logs) - 1)
        )
        
        if (message['term'] >= self.current_term and
            (self.voted_for is None or self.voted_for == message['candidate_id']) and
            candidate_log_ok):
            vote_granted = True
            self.voted_for = message['candidate_id']
            # 投票したらタイマーをリセット
            self.election_timer.reset()
        
        if vote_granted:
            logger.info(f"{self.node.name} voted for {message['candidate_id']} in term {self.current_term}")
        else:
            logger.info(f"{self.node.name} rejected vote for {message['candidate_id']} in term {self.current_term} ({message})")
        
        # 投票結果を返信
        response = {
            'type': 'RequestVoteResponse',
            'term': self.current_term,
            'vote_granted': vote_granted
        }
        sender = next(n for n in self.node.cluster if n.name == message['candidate_id'])
        await sender.send(response)

    async def handle_append_entries(self, message):
        """AppendEntriesリクエストを処理する"""
        success = False

        self.leader_id = message['leader_id']
        
        # 1. リーダーのタームが現在のターム以上であることを確認
        if message['term'] >= self.current_term:
            self.state = 'follower'  # リーダーを認識
            self.election_timer.reset()  # タイマーをリセット
            
            # 2. ログの整合性チェック
            log_ok = (
                message['prev_log_index'] == -1 or
                (message['prev_log_index'] < len(self.logs) and
                 self.logs[message['prev_log_index']]['term'] == message['prev_log_term'])
            )
            
            if log_ok:
                success = True
                # 新しいエントリがある場合は追加
                if message['entries']:
                    # logger.info(f"{self.node.name} received {len(message['entries'])} new log entries from leader (commit_index: {message['leader_commit']})")
                    # 競合するエントリを削除し、新しいエントリを追加
                    self.logs = self.logs[:message['prev_log_index'] + 1]
                    self.logs.extend(message['entries'])

                    # バケットが存在するか確かめる。なければ、バケットが作成されるまで待つ
                    for entry in message['entries']:
                        bucket_id = entry['command']['bucket_id']
                        # バケットが存在しない場合は、バケットが作成されるまで待つ
                        if bucket_id not in self.share_buckets:
                            self.bucket_events[bucket_id] = asyncio.Event()
                            try:
                                await asyncio.wait_for(self.bucket_events[bucket_id].wait(), timeout=5.0)
                            except asyncio.TimeoutError:
                                logger.error(f"Failed to get bucket: bucket_id={bucket_id}")
                            finally:
                                del self.bucket_events[bucket_id]
                
                # コミットインデックスの更新
                if message['leader_commit'] > self.commit_index:
                    self.commit_index = min(message['leader_commit'], len(self.logs) - 1)
                    await self.apply_logs()
        
        # 応答を返信
        response = {
            'type': 'AppendEntriesResponse',
            'term': self.current_term,
            'success': success
        }
        sender = next(n for n in self.node.cluster if n.name == message['leader_id'])
        await sender.send(response)

    async def handle_append_entries_response(self, message):
        """AppendEntriesの応答を処理する"""
        if self.state != 'leader':
            return
            
        sender = message['sender']
        success = message['success']

        
        if success:
            # 成功した場合、next_indexとmatch_indexを更新
            self.next_index[sender] = len(self.logs)
            self.match_index[sender] = len(self.logs) - 1
            
            # コミットインデックスの更新を試みる
            await self.update_commit_index()
        else:
            # 失敗した場合、next_indexをデクリメントして再試行
            if self.next_index[sender] > 0:
                self.next_index[sender] -= 1
                await self.replicate_log(sender)

    async def handle_client_write(self, message):
        """クライアントからのWrite要求を処理する"""
        client_id = message.get('sender')
        request_id = message.get('request_id', str(uuid.uuid4()))
        # logger.info(f"{self.node.name} received write request: {message}")
        if self.state != 'leader':
            # リーダーでない場合は、リーダーの情報をクライアントに返す
            response = {
                'type': 'ClientWriteResponse',
                'success': False,
                'error': 'not_leader',
                'leader_hint': self.leader_id,  # 既知のリーダー情報
                "request_id": request_id
            }
            client = next(c for c in self.node.clients if c.name == client_id)
            await client.send(response)
            return
        

        # writeShareと統合する
        shares = message.get('shares')
        bucket_id = request_id # バケットIDはリクエストIDと同じ
        bucket = {
            'shares': shares,
            'request_id': request_id,
            'bucket_id': bucket_id,
            'term': self.current_term,
        }

        self.share_buckets[bucket_id] = bucket

        # 新しいログエントリを作成
        entry = {
            'term': self.current_term,
            'command': {
                'type': 'set',
                'key': message['key'],
                'value': message['commitment'],
                'bucket_id': bucket['bucket_id']
            },
            "request_id": request_id
        }
        
        # リクエストを追跡するためにIDを保存
        if request_id:
            self.pending_requests[request_id] = client_id
        
        # ログに追加
        self.logs.append(entry)
        
        # 全フォロワーにログを複製
        for node in self.node.cluster:
            if not node.is_myself:
                await self.replicate_log(node.name)


    async def handle_client_write_share(self, message):
        """クライアントからのWrite要求を処理する"""
        client_id = message.get('sender')
        request_id = message.get('request_id', str(uuid.uuid4()))

        shares = message.get('shares')
        bucket_id = request_id # バケットIDはリクエストIDと同じ
        bucket = {
            'shares': shares,
            'request_id': request_id,
            'bucket_id': bucket_id,
            'term': self.current_term,
        }
        self.share_buckets[bucket_id] = bucket

        # バケット待ちがあれば、取得できたことを通知 (おもにFollowerだったときにAppendEntriesが先に来て、クライアントからのWriteShareが来るときに、バケットが作成されるまで待つ)
        if self.bucket_events.get(bucket_id):
            self.bucket_events[bucket_id].set()

        response = {
            'type': 'ClientWriteShareResponse',
            'success': True,
            'request_id': request_id
        }
        client = next(c for c in self.node.clients if c.name == client_id)
        await client.send(response)


    async def handle_client_get_share(self, message):
        """クライアントからのGetShare要求を処理する"""
        client_id = message.get('sender')
        request_id = message.get('request_id', str(uuid.uuid4()))

        # キーからバケットIDを取得
        key = message.get('key')
        bucket_id = self.statemachine.get(key, {}).get('bucket_id')
        bucket = self.share_buckets.get(bucket_id)

        # バケットが存在しない場合はエラー
        if not bucket:
            response = {
                'type': 'ClientGetShareResponse',
                'success': False,
                'error': 'bucket_not_found',
                'request_id': request_id
            }
            client = next(c for c in self.node.clients if c.name == client_id)
            await client.send(response)
            return
        
        # バケットが存在する場合は、シェアを返す
        response = {
            'type': 'ClientGetShareResponse',
            'success': True,
            'shares': bucket['shares'],
            'request_id': request_id
        }

        client = next(c for c in self.node.clients if c.name == client_id)
        await client.send(response)

    async def update_commit_index(self):
        """コミットインデックスの更新"""
        for n in range(self.commit_index + 1, len(self.logs)):
            if self.logs[n]['term'] != self.current_term:
                continue
                
            replicated = 1
            for match_idx in self.match_index.values():
                if match_idx >= n:
                    replicated += 1
                    
            if replicated > len(self.node.cluster) // 2:
                self.commit_index = n
                await self.apply_logs()
                
                # コミット完了後、関連するクライアントリクエストに応答
                entry = self.logs[n]
                for request_id, client_id in list(self.pending_requests.items()):
                    if entry['request_id'] == request_id:
                        response = {
                            'type': 'ClientWriteResponse',
                            'success': True,
                            'request_id': request_id
                        }
                    client = next(c for c in self.node.clients if c.name == client_id)
                    await client.send(response)
                    del self.pending_requests[request_id]
                
                # logger.info(f"{self.node.name} committed logs up to index {self.commit_index}")

    async def garbage_collection(self):
        """古いバケットを削除する"""
        for bucket_id, bucket in list(self.share_buckets.items()):
            for key, state in self.statemachine.items():
                if state['bucket_id'] == bucket_id:
                    break
            else:
                del self.share_buckets[bucket_id]
