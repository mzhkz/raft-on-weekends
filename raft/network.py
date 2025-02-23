import asyncio
import json
from .serializers import MessagePackSerializer
from .logger import logger

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue, request_handler, loop):
        self.queue = queue
        self.request_handler = request_handler
        self.serializer = MessagePackSerializer
        self.loop = loop or asyncio.get_event_loop()

    def __call__(self):
        return self

    async def start(self):
        while not self.transport.is_closing():
            request = await self.queue.get()
            data = self.serializer.pack(request)
            self.transport.sendto(data, None)

    def connection_made(self, transport):
        self.transport = transport
        asyncio.ensure_future(self.start(), loop=self.loop)

    def datagram_received(self, data, addr):
        data = self.serializer.unpack(data)
        sender_ip = addr[0]
        # 10.0.0.0/16のIPアドレスはサーバーノード、それ以外はクライアント
        ip_parts = sender_ip.split('.')
        if ip_parts[0] == '10' and ip_parts[1] == '0':
            # サーバーノードの場合
            node_id = str(int(ip_parts[3])-1)
            data.update({
                "sender": f"node{node_id}",
                "connection": None  # サーバーノードの場合はconnection不要
            })
            logger.info(json.dumps(data))
        else:
            # クライアントの場合
            data.update({
                "sender": f"client_{sender_ip.replace('.', '_')}",
                "connection": self  # UDPProtocolインスタンス自体を保存
            })
            # クライアントのアドレスを保存
            self.client_addr = addr
        self.request_handler(data)

    def error_received(self, exc):
        logger.error('Error received:', exc)

    def connection_lost(self, exc):
        logger.warning('Connection lost:', exc)
        
    def _convert_ipv4_to_name(self, ip):
        node_id = str(int(ip.split('.')[3])-1)
        return f"node{node_id}"

    async def send(self, data):
        """クライアントへの応答用メソッド"""
        if not hasattr(self, 'client_addr'):
            logger.error('No client address available for sending response')
            return
        packed_data = self.serializer.pack(data)
        self.transport.sendto(packed_data, self.client_addr)