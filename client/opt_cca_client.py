import argparse
import asyncio
import uuid
import random
import json
from raft.serializers import MessagePackSerializer
from raft.logger import logger  # Raftのロガーをインポート
from raft.timer import Timer

from crypto.VSS import split, combine
from crypto.parameters import TEST_PARAMS

from client.network import ClientUDPProtocol

class CCAPerformanceEvaluator:
    def __init__(self, name):
        self.name = name
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
        self.start_time = None
        
        self.load_node_portlist()
        
        self.stats_timer = Timer(2, self.report_stats)  # 10秒間隔でパフォーマンス統計を報告

        # cca client用の変数

        logger.info(f"CCAPerformanceEvaluator {self.name} initialized")
        
    def load_node_portlist(self):
        with open('node_portlist.json', 'r') as file:
            self.node_host_port = json.load(file)   
        for key, value in self.node_host_port.items():
            if key.startswith('node'):
                self.cluster_info[key] = value

    async def connect(self):
        loop = asyncio.get_event_loop()
        self.protocol = ClientUDPProtocol(self.commit_events, self.handle_response, self)
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self.protocol,
            local_addr=('0.0.0.0', 8888)
        )

    def handle_response(self, response):
        request_id = response.get('request_id')
        response_type = response.get('type')
        if response_type == 'ClientWriteResponse':
            self.handle_write_response(response)
        elif response_type == 'ClientWriteShareResponse':
            self.handle_write_share_response(response)
        elif response_type == 'ClientGetShareResponse':
            self.handle_get_share_response(response)
    
    def handle_write_response(self, response):
        """コミット完了時の処理"""
        request_id = response.get('request_id')
        if not response.get('success'):
            # リーダーでない場合、新しいリーダーに接続
            if response.get('error') == 'not_leader':
                new_leader = response.get('leader_hint')
                if new_leader:
                    logger.info(f"リーダーを{new_leader}に変更します")
                    self.current_leader = new_leader
        else:
            # logger.info(f"✅ コミット成功: request_id={request_id}")
            if request_id in self.commit_events:
                self.commit_events[request_id].set()

    def handle_write_share_response(self, response):
        """シェアを受け取った時の処理"""
        pass

    def handle_get_share_response(self, response):
        """シェアを受け取った時の処理"""
        request_id = response.get('request_id')
        if response.get('success'):
            # 読み込みリクエストの場合は、結果を保存して、read_eventを発火
            if request_id in self.read_events:
                if not request_id in self.read_results:
                    self.read_results[request_id] = []
                # シェアを保存
                self.read_results[request_id].append(response.get('shares'))
                # 2個のノードからシェアをもらったら、read_eventを発火
                if len(self.read_results[request_id]) >= 2:
                    total_shares = []
                    # シェアを一次元に結合
                    for result in self.read_results[request_id]:
                        total_shares.extend(result)
                    self.read_results[request_id] = total_shares
                    self.read_events[request_id].set()

    async def send_request(self, request, target_node):
        target_ip = self.node_host_port[target_node]['host']
        target_port = self.node_host_port[target_node]['internal_port']
        data = MessagePackSerializer.pack(request)
        self.transport.sendto(data, (target_ip, target_port))

    async def read(self, key):
        request_id = str(uuid.uuid4())
        self.read_events[request_id] = asyncio.Event()

        request = {
            'type': 'ClientGetShare',
            'key': key,
            'request_id': request_id,
        }

        # リーダーともう一つのノードにリクエストを送信
        await self.send_request({"data": request}, self.current_leader)  # リーダーにリクエスト
        await self.send_request({"data": request}, list(self.cluster_info.keys())[1])  # もう一つのノードにリクエスト

        # リーダーからのレスポンスを待つ
        try:
            await asyncio.wait_for(self.read_events[request_id].wait(), timeout=5.0)
            del self.read_events[request_id]

            unique_shares = []
            for share in self.read_results[request_id]:
                if share not in unique_shares:
                    unique_shares.append(share)

            result = combine(unique_shares, TEST_PARAMS['q']) # シェアを結合
            del self.read_results[request_id]
        except asyncio.TimeoutError:
            logger.error(f"リーダーからのReadレスポンスがタイムアウトしました: {request_id}")
            del self.read_events[request_id]
            return None

        return result

    async def write(self, key, value):
        start_time = asyncio.get_event_loop().time()  # リクエスト開始時間
        request_id = str(uuid.uuid4())

        node_count = len(self.cluster_info.keys())

        # シェアをレプリケーション  
        result = split(value, node_count, node_count, TEST_PARAMS['p'], TEST_PARAMS['q'], TEST_PARAMS['g'])
        shares = result["shares"]
        commitments = result["commitments"]

        self.granted_share_events[request_id] = asyncio.Event()
        self.share_granted[request_id] = 0

        for node_name in self.cluster_info.keys():
            if node_name != self.current_leader:
                node_index = list(self.cluster_info.keys()).index(node_name)
                shares_copy = shares.copy()
                shares_copy.pop(node_index)
                request = {
                    'type': 'ClientWriteShare',
                    'shares': shares, ## 擬似的なシェア分配
                    'request_id': request_id,
                }
                await self.send_request({"data": request}, node_name)

        # シェアが揃わなくてもコミットを実行
        self.commit_events[request_id] = asyncio.Event()
        
        request = {
            'type': 'ClientWrite',
            'key': key,
            'commitments': commitments,
            'shares': shares, ## 擬似的なシェア分配
            'request_id': request_id,
        }
        
        await self.send_request({"data": request}, self.current_leader)
        self.total_requests += 1
        
        try:
            await asyncio.wait_for(self.commit_events[request_id].wait(), timeout=5.0)

            # 書き込み結果を確認
            result =await self.read(key)
            if result != value:
                raise Exception(f"書き込み結果が一致しません: {result} != {value}")

            end_time = asyncio.get_event_loop().time()  # リクエスト完了時間
            latency = end_time - start_time
            self.total_latency += latency
            self.successful_requests += 1
            del self.commit_events[request_id]
            return True
        except asyncio.TimeoutError:
            del self.commit_events[request_id]
            return False

    async def report_stats(self):
        """パフォーマンス統計を報告するコールバック関数"""
        elapsed_time = asyncio.get_event_loop().time() - self.start_time
        throughput = self.successful_requests / elapsed_time
        avg_latency = self.total_latency / self.successful_requests if self.successful_requests > 0 else 0
        
        logger.info(f"""
                パフォーマンス統計:
                スループット: {throughput:.2f} req/sec
                平均レイテンシ: {avg_latency * 1000:.3f} msec
                成功率: {(self.successful_requests/(self.total_requests+0.0001)*100):.1f}%
                総リクエスト数: {self.total_requests}
                """)
        
        # カウンターをリセット
        self.total_requests = 0
        self.successful_requests = 0
        self.total_latency = 0
        self.start_time = asyncio.get_event_loop().time()

    async def run(self):
        await asyncio.sleep(5)
        await self.connect()
        self.start_time = asyncio.get_event_loop().time()
        self.stats_timer.start()  # 統計タイマーを開始
        
        try:
            while True:
                value = 23
                await self.write('token', value)
        finally:
            self.stats_timer.stop()  # 統計タイマーを停止
            self.transport.close()
