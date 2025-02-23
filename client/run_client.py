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
        self.protocol = ClientUDPProtocol(self.commit_events, self.handle_response)
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
        leader_port = 8080
        data = MessagePackSerializer.pack(request)
        logger.info(f"送信先: {leader_ip}, ポート: {leader_port}")
        self.transport.sendto(data, (leader_ip, leader_port))

    async def write(self, key, value):
        request_id = str(uuid.uuid4())
        self.commit_events[request_id] = asyncio.Event()

        request = {
            'type': 'ClientWrite',
            'key': key,
            'value': value,
            'request_id': request_id,
        }

        await self.send_request(request)
        logger.info(f"📤 リクエスト送信: value={value}, request_id={request_id}")

        try:
            await asyncio.wait_for(self.commit_events[request_id].wait(), timeout=5.0)
            del self.commit_events[request_id]
            return True
        except asyncio.TimeoutError:
            logger.warning(f"⏰ タイムアウト: request_id={request_id}")
            del self.commit_events[request_id]
            return False

    async def run(self):
        await self.connect()
        while True:
            try:
                value = random.randint(1, 100)
                success = await self.write('random_number', value)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"エラーが発生しました: {e}")
                break

        self.transport.close()

class ClientUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, commit_events, response_handler):
        self.serializer = MessagePackSerializer
        self.commit_events = commit_events
        self.response_handler = response_handler

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        response = self.serializer.unpack(data)
        self.response_handler(response)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='client1')
    args = parser.parse_args()

    client = RaftClient(args.name)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client.run())