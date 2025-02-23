import asyncio
import json
from .serializers import MessagePackSerializer
from .logger import logger

class BaseUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue, request_handler, loop, base_node=None):
        self.queue = queue
        self.request_handler = request_handler
        self.serializer = MessagePackSerializer
        self.loop = loop or asyncio.get_event_loop()
        self.base_node = base_node

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

    def error_received(self, exc):
        logger.error('Error received:', exc)

    def connection_lost(self, exc):
        logger.warning('Connection lost:', exc)

class NodeUDPProtocol(BaseUDPProtocol):
    def datagram_received(self, data, addr):
        data = self.serializer.unpack(data)
        sender_ip = addr[0]
        
        sender_name = self._convert_ipv4_to_node_name(sender_ip)
        data.update({
                "sender": f"{sender_name}"
            })
        self.request_handler(data)

    @staticmethod
    def _convert_ipv4_to_node_name(ip):
        octets = ip.split('.')
        if octets[2] == '0':
            # ノードのIPアドレスの場合
            node_id = str(int(octets[3]) - 1)
            return f"node{node_id}"
        elif octets[2] == '1':
            # クライアントのIPアドレスの場合
            client_id = str(int(octets[3]) - 1)
            return f"client{client_id}"
        else:
            return "unknown"

class ClientUDPProtocol(BaseUDPProtocol):
    def datagram_received(self, data, addr):
        pass