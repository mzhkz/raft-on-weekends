import asyncio

from raft.serializers import MessagePackSerializer


class ClientUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, commit_events, response_handler, base_node):
        self.serializer = MessagePackSerializer
        self.commit_events = commit_events
        self.response_handler = response_handler
        self.base_node = base_node

        self.address_to_node = {}
        self._convert_addrs_to_node()

    def _convert_addrs_to_node(self):
        for key, value in self.base_node.node_host_port.items():
            self.address_to_node[value['host']] = key
            
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        response = self.serializer.unpack(data)
        data = response['data']
        node_name = self.address_to_node[addr[0]]
        self.response_handler(data)