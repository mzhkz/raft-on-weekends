import argparse
import asyncio
import uuid
import random
import json
from raft.serializers import MessagePackSerializer
from raft.logger import logger  # Raftのロガーをインポート

class RaftClient:
    def __init__(self, name):
        self.name = name
        self.commit_events = {}
        self.current_leader = 'node1'  # デフォルトのリーダー
        self.cluster_info = {}
        self.transport = None
        self.protocol = None
        self.node_host_port = {}

        self.load_node_portlist()
        
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
        request_id = response.get('request_id')
        if response.get('type') == 'ClientWriteResponse':
            if not response.get('success'):
                # リーダーでない場合、新しいリーダーに接続
                if response.get('error') == 'not_leader':
                    new_leader = response.get('leader_hint')
                    if new_leader:
                        logger.info(f"🔄 リーダーを{new_leader}に変更します")
                        self.current_leader = new_leader
                        # 保留中のリクエストを再送信
                        if request_id in self.commit_events:
                            self.commit_events[request_id].set()
            else:
                logger.info(f"✅ コミット成功: request_id={request_id}")
                if request_id in self.commit_events:
                    self.commit_events[request_id].set()

    async def send_request(self, request):
        leader_node = self.current_leader
        leader_ip = self.node_host_port[leader_node]['host']
        leader_port = self.node_host_port[leader_node]['internal_port']
        data = MessagePackSerializer.pack(request)
        logger.info(f"送信先: {leader_ip}, ポート: {leader_port}")
        self.transport.sendto(data, (leader_ip, leader_port))

    async def write(self, key, value):
        max_retries = 3  # 最大リトライ回数
        current_retry = 0
        
        while current_retry < max_retries:
            request_id = str(uuid.uuid4())
            self.commit_events[request_id] = asyncio.Event()
            
            request = {
                'type': 'ClientWrite',
                'key': key,
                'value': value,
                'request_id': request_id,
            }
            
            await self.send_request({"data": request})
            logger.info(f"📤 リクエスト送信: value={value}, request_id={request_id}")
            
            try:
                await asyncio.wait_for(self.commit_events[request_id].wait(), timeout=10.0)  # タイムアウト時間を10秒に延長
                del self.commit_events[request_id]
                return True
            except asyncio.TimeoutError:
                logger.warning(f"⏰ タイムアウト: request_id={request_id}, リトライ回数={current_retry + 1}")
                current_retry += 1
                await asyncio.sleep(1)  # リトライ前に少し待機
                
            finally:
                if request_id in self.commit_events:
                    del self.commit_events[request_id]
        
        logger.error("最大リトライ回数を超過しました")
        return False

    async def run(self):
        await asyncio.sleep(5)
        await self.connect()
        while True:
            try:
                value = random.randint(1, 100)
                success = await self.write('random_number', value)
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"エラーが発生しました: {e}")
                break

        self.transport.close()

class ClientUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, commit_events, response_handler, base_node):
        self.serializer = MessagePackSerializer
        self.commit_events = commit_events
        self.response_handler = response_handler
        self.base_node = base_node
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        response = self.serializer.unpack(data)
        data = response['data']
        for key, value in self.base_node.node_host_port.items():
            if value['host'] == addr[0]:
                data['sender'] = key
                break
        self.response_handler(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='client1')
    args = parser.parse_args()

    client = RaftClient(args.name)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client.run())