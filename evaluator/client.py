import argparse
import asyncio
import uuid
import random
import json
from raft.serializers import MessagePackSerializer
from raft.logger import logger  # Raftのロガーをインポート
from raft.timer import Timer

from client.network import ClientUDPProtocol

class PerformanceEvaluator:
    def __init__(self, name, duration, requests_per_second, write_ratio, key_range):
        # 評価の設定
        self.name = name
        self.duration = duration
        self.requests_per_second = requests_per_second
        self.write_ratio = write_ratio
        self.key_range = key_range

        # Raft処理用
        self.commit_events = {}
        self.read_events = {}
        self.current_leader = 'node1'  # デフォルトのリーダー
        self.cluster_info = {}
        self.transport = None
        self.protocol = None
        self.node_host_port = {}
        self.read_results = {}

        # パフォーマンス測定用の変数を追加
        self.total_requests = 0
        self.successful_requests = 0
        self.total_latency = 0
        self.write_requests = 0
        self.write_successful = 0
        self.write_latency = 0
        self.read_requests = 0
        self.read_successful = 0
        self.read_latency = 0
        
        # リクエスト開始時間を保存する辞書
        self.start_time = 0

        # リクエスト開始時間を保存する辞書
        self.start_times = {}

        # パフォーマンスデータを保存するリスト
        self.performance_data = []

        
        # ノードのポートリストを読み込む
        self.load_node_portlist()
        
        # 1秒間隔でパフォーマンス統計を報告するタイマー

        logger.info(f"PerformanceEvaluator {self.name} initialized")
        
    def load_node_portlist(self):
        """ ノードのポートリストを読み込む """

        with open('node_portlist.json', 'r') as file:
            self.node_host_port = json.load(file)   
        for key, value in self.node_host_port.items():
            if key.startswith('node'):
                self.cluster_info[key] = value 

    async def connect(self):
        """ クライアントを接続 """

        loop = asyncio.get_event_loop()
        self.protocol = ClientUDPProtocol(self.handle_response, self)
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self.protocol,
            local_addr=('0.0.0.0', 8888)
        )

    def handle_response(self, response):
        if response.get('type') == 'ClientWriteResponse':
            self.handle_write_response(response)
        elif response.get('type') == 'ClientReadResponse':
            self.handle_read_response(response)

    def handle_read_response(self, response):
        """ 読み込みリクエストのレスポンスを処理 """

        request_id = response.get('request_id')

        # リクエスト完了時間を計算
        if request_id in self.start_times:
            start_time = self.start_times[request_id]
            latency = asyncio.get_event_loop().time() - start_time
            self.total_latency += latency
            self.read_latency += latency
            del self.start_times[request_id]
        else:
            logger.warning(f"未知のリクエストID: {request_id}")

        if not response.get('success'):
            # リーダーでない場合、新しいリーダーに接続
            if response.get('error') == 'not_leader':
                new_leader = response.get('leader_hint')
                if new_leader:
                    logger.info(f"リーダーを{new_leader}に変更します")
                    self.current_leader = new_leader
            else:
                logger.error(f"読み込みリクエストが失敗しました: {request_id} {response.get('error')}")
        else:
            # 読み込みリクエストの場合は、結果を保存して、read_eventを発火
            if request_id in self.read_events:
                self.read_results[request_id] = response.get('value')
                self.read_events[request_id].set()
                self.successful_requests += 1
                self.read_successful += 1

    def handle_write_response(self, response):
        """ 書き込みリクエストのレスポンスを処理 """
        request_id = response.get('request_id')
        
        # リクエスト完了時間を計算
        if request_id in self.start_times:
            start_time = self.start_times[request_id]
            latency = asyncio.get_event_loop().time() - start_time
            self.total_latency += latency
            self.write_latency += latency
            del self.start_times[request_id]
        else:
            logger.warning(f"未知のリクエストID: {request_id}")

        if not response.get('success'):
            # リーダーでない場合、新しいリーダーに接続
            if response.get('error') == 'not_leader':
                new_leader = response.get('leader_hint')
                if new_leader:
                    logger.info(f"リーダーを{new_leader}に変更します")
                    self.current_leader = new_leader
            logger.error(f"書き込みリクエストが失敗しました: {request_id} {response.get('error')}")
        else:
            self.successful_requests += 1
            self.write_successful += 1
                

    async def send_request_to_leader(self, request):
        await self.send_request(request, self.current_leader)

    async def send_request(self, request, target_node):
        target_ip = self.node_host_port[target_node]['host']
        target_port = self.node_host_port[target_node]['internal_port']
        data = MessagePackSerializer.pack(request)
        self.transport.sendto(data, (target_ip, target_port))

    async def read(self, key):
        """ 読み込みリクエストを送信 """
         # リクエスト数をインクリメント 
        self.total_requests += 1
        self.read_requests += 1
        request_id = str(uuid.uuid4())
        self.read_events[request_id] = asyncio.Event()
        self.start_times[request_id] = asyncio.get_event_loop().time()
        await self.read_handler(key, request_id)

        # リーダーからのレスポンスを待つ
        try:
            await asyncio.wait_for(self.read_events[request_id].wait(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.error(f"リーダーから正常なレスポンスを受け取れませんでした: {request_id}")
            return None
        finally:
            del self.read_events[request_id]
            result = self.read_results[request_id]
            del self.read_results[request_id]

        return result

    async def write(self, key, value):
        """ 書き込みリクエストを送信 """
        # リクエスト数をインクリメント
        self.total_requests += 1
        self.write_requests += 1
        request_id = str(uuid.uuid4())
        self.start_times[request_id] = asyncio.get_event_loop().time()
        await self.write_handler(key, value, request_id)

    async def read_handler(self, key, request_id):
        """ 読み込みリクエストを送信 """

        request = {
            'type': 'ClientRead',
            'key': key,
            'request_id': request_id,
        }
        await self.send_request_to_leader({"data": request})


    async def write_handler(self, key, value, request_id):
        """ 書き込みリクエストを送信 """

        # リクエストを作成
        request = {
            'type': 'ClientWrite',
            'key': key,
            'value': value,
            'request_id': request_id,
        }
            
        # リクエストを送信
        await self.send_request_to_leader({"data": request})

    async def report_stats(self):
        """パフォーマンス統計を報告するコールバック関数"""
        elapsed_time = asyncio.get_event_loop().time() - self.start_time
        # 書き込み統計
        write_throughput = self.write_successful / elapsed_time
        write_avg_latency = self.write_latency / self.write_successful if self.write_successful > 0 else 0
        write_success_rate = (self.write_successful/(self.write_requests+0.0001)*100)
        
        # 読み込み統計
        read_throughput = self.read_successful / elapsed_time
        read_avg_latency = self.read_latency / self.read_successful if self.read_successful > 0 else 0
        read_success_rate = (self.read_successful/(self.read_requests+0.0001)*100)
        
        # 統計情報をリセットする前に、現在の値を保存
        current_stats = {
           "write": {
               "throughput": write_throughput,
               "avg_latency": write_avg_latency * 1000,  # ミリ秒に変換
               "success_rate": write_success_rate,
               "requests": self.write_requests,
               "successful": self.write_successful,
           },
           "read": {
               "throughput": read_throughput,
               "avg_latency": read_avg_latency * 1000,  # ミリ秒に変換
               "success_rate": read_success_rate,
               "requests": self.read_requests,
               "successful": self.read_successful,
           },
           "timestamp": elapsed_time
        }
        
        self.performance_data.append(current_stats)
        
        logger.info(f"""
                パフォーマンス統計:
                書き込み:
                  スループット: {write_throughput:.2f} req/sec
                  平均レイテンシ: {write_avg_latency * 1000:.3f} msec
                  成功率: {write_success_rate:.1f}%
                  リクエスト数: {self.write_requests}
                  成功数: {self.write_successful}
                読み込み:
                  スループット: {read_throughput:.2f} req/sec
                  平均レイテンシ: {read_avg_latency * 1000:.3f} msec
                  成功率: {read_success_rate:.1f}%
                  リクエスト数: {self.read_requests}
                  成功数: {self.read_successful}
                Evaluator: {self.__class__.__name__}
                """)
        
        # カウンターをリセット
        self.reset_counters()

    def reset_counters(self):
        """ カウンターをリセット """

        self.total_requests = 0
        self.successful_requests = 0
        self.total_latency = 0
        self.write_requests = 0 
        self.write_successful = 0
        self.write_latency = 0
        self.read_requests = 0
        self.read_successful = 0
        self.read_latency = 0
        self.start_time = asyncio.get_event_loop().time()

    def save_performance_data(self):
        """ パフォーマンスデータを保存 """

        write_ratio_name = str(self.write_ratio).replace('.', '_')
        with open(f'./dump/{self.__class__.__name__}-{self.name}-s{self.requests_per_second}-r{write_ratio_name}-k{self.key_range}-d{self.duration}.json', 'w') as f:
            json.dump(self.performance_data, f)


    async def run(self):
        """ 評価を実行 """

        logger.info(f"設定: リクエスト数/秒 = {self.requests_per_second}, 書き込み比率 = {self.write_ratio}, キーの範囲 = {self.key_range}, 実行時間 = {self.duration}秒")

        # 1.5秒待ってから評価開始 nodeが起動するまで待つ
        await asyncio.sleep(1.5)
        
        # 事前にキーを初期化
        logger.info(f"キーの初期化を開始します（範囲: 1-{self.key_range}）")
        await self.connect()
        # ランダムなキーを選択して書き込み, リーダーを選ぶ
        await self.write(f"key_{random.randint(1, self.key_range)}", 1)
        logger.info("キーの初期化が完了しました")
        # カウンターをリセット
        self.reset_counters()
        
        # 1秒待ってから評価開始
        await asyncio.sleep(0.5)
        self.start_time = asyncio.get_event_loop().time()

        # 1秒ごとにパフォーマンス統計を報告するタイマー
        stats_timer = Timer(1.0, self.report_stats)
        stats_timer.start()  # 統計タイマーを開始

        # リクエスト間隔を計算（秒）
        interval = 1.0 / self.requests_per_second

        # 終了時間を設定
        end_time = self.start_time + self.duration
        
        try:
            request_count = 0
            while asyncio.get_event_loop().time() < end_time:
                try:
                    request_start = asyncio.get_event_loop().time()
                    request_count += 1
                    
                    # ランダムなキーを選択
                    key = f"key_{random.randint(1, self.key_range)}"
                    
                    # 書き込みか読み込みかをランダムに決定
                    if random.random() < self.write_ratio:
                        # 書き込み操作
                        await self.write(key, 23)
                    else:
                        # 読み込み操作
                        await self.read(key)
                    
                    # 次のリクエストまでの時間を計算（固定間隔ではなく、処理時間を考慮）
                    elapsed = asyncio.get_event_loop().time() - request_start
                    sleep_time = max(0, interval - elapsed)
                    await asyncio.sleep(sleep_time)
                except Exception as e:
                    logger.error(f"エラーが発生しました: {e}")
            
            # 評価終了メッセージ
            logger.info(f"評価が完了しました。実行時間: {self.duration}秒、総リクエスト数: {request_count}")

            # パフォーマンスデータを保存
            self.save_performance_data()
        finally:
            stats_timer.stop()  # 統計タイマーを停止
            self.transport.close()
