import asyncio
import json
from .serializers import MessagePackSerializer
from .logger import logger

class BaseUDPProtocol(asyncio.DatagramProtocol):
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

    def error_received(self, exc):
        logger.error('Error received:', exc)

    def connection_lost(self, exc):
        logger.warning('Connection lost:', exc)

class NodeUDPProtocol(BaseUDPProtocol):
    def datagram_received(self, data, addr):
        data = self.serializer.unpack(data)
        sender_ip = addr[0]
        node_id = self._convert_ipv4_to_node_name(sender_ip)
        data.update({
                "sender": f"node{node_id}",
                "connection": None  # サーバーノードの場合はconnection不要
            })
        self.request_handler(data)

    @staticmethod
    def _convert_ipv4_to_node_name(ip):
        node_id = str(int(ip.split('.')[3])-1)
        return f"node{node_id}"

class ClientUDPProtocol(BaseUDPProtocol):
    def datagram_received(self, data, addr):
        data = self.serializer.unpack(data)
        sender_ip = addr[0]
        data.update({
                "sender": f"client_{sender_ip.replace('.', '_')}"
        })
        self.request_handler(data)