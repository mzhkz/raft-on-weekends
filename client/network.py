import asyncio

from raft.serializers import MessagePackSerializer


class ClientUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, response_handler, base_node):
        self.serializer = MessagePackSerializer
        self.response_handler = response_handler
        self.base_node = base_node

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        response = self.serializer.unpack(data)
        data = response['data']
       
        self.response_handler(data)