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
        
    def load_node_portlist(self):
        with open('node_portlist.json', 'r') as file:
            self.node_host_port = json.load(file)    

    async def connect(self):
        loop = asyncio.get_event_loop()
        self.protocol = ClientUDPProtocol(self.commit_events, self.handle_response, self)
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
        request_id = response.get('request_id')
        if not response.get('success'):
            # リーダーでない場合、新しいリーダーに接続
            if response.get('error') == 'not_leader':
                new_leader = response.get('leader_hint')
                if new_leader:
                    logger.info(f"リーダーを{new_leader}に変更します")
                    self.current_leader = new_leader
        else:
            # 読み込みリクエストの場合は、結果を保存して、read_eventを発火
            if request_id in self.read_events:
                self.read_results[request_id] = response.get('value')
                self.read_events[request_id].set()

    def handle_write_response(self, response):
        request_id = response.get('request_id')
        if not response.get('success'):
            # リーダーでない場合、新しいリーダーに接続
            if response.get('error') == 'not_leader':
                new_leader = response.get('leader_hint')
                if new_leader:
                    logger.info(f"リーダーを{new_leader}に変更します")
                    self.current_leader = new_leader
                    # 保留中のリクエストを再送信
                    if request_id in self.commit_events:
                        self.commit_events[request_id].set()
        else:
            # logger.info(f"✅ コミット成功: request_id={request_id}")
            if request_id in self.commit_events:
                self.commit_events[request_id].set()
                

    async def send_request(self, request):
        leader_node = self.current_leader
        leader_ip = self.node_host_port[leader_node]['host']
        leader_port = self.node_host_port[leader_node]['internal_port']
        data = MessagePackSerializer.pack(request)
        self.transport.sendto(data, (leader_ip, leader_port))

    async def read(self, key):
        request_id = str(uuid.uuid4())
        self.read_events[request_id] = asyncio.Event()

        request = {
            'type': 'ClientRead',
            'key': key,
            'request_id': request_id,
        }
        await self.send_request({"data": request})

        # リーダーからのレスポンスを待つ
        try:
            await asyncio.wait_for(self.read_events[request_id].wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error(f"リーダーからのReadレスポンスがタイムアウトしました: {request_id}")
            return None
        finally:
            del self.read_events[request_id]
            result = self.read_results[request_id]
            del self.read_results[request_id]

        return result

    async def write(self, key, value):
        start_time = asyncio.get_event_loop().time()  # リクエスト開始時間
        
        request_id = str(uuid.uuid4())
        self.commit_events[request_id] = asyncio.Event()
        
        request = {
            'type': 'ClientWrite',
            'key': key,
            'value': value,
            'request_id': request_id,
        }
        
        await self.send_request({"data": request})
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
                try:
                    value = 892
                    await self.write('random_number', value)
                except Exception as e:
                    logger.error(f"エラーが発生しました: {e}")
        finally:
            self.stats_timer.stop()  # 統計タイマーを停止
            self.transport.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='client1')
    args = parser.parse_args()

    client = PerformanceEvaluator(args.name)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client.run())