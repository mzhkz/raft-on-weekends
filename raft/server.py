import asyncio
from .network import UDPProtocol
from .logger import logger
from .state import State


async def register_as_server(addresses, loop):
    for address in addresses:
        if address not in Node.cluster:
            node = Node(*address, loop, is_client=False)
            await node.start()

async def register_as_client(addresses, loop):
    for address in addresses:
        if address not in Node.cluster:
            node = Node(*address, loop, is_client=True)
            await node.start()


def stop():
    for node in Node.cluster:
        node.stop()


class Node:
    cluster = []

    def __init__(self, host, port, loop, is_client=False):
        self.host = host
        self.port = port
        self.loop = loop or asyncio.get_event_loop()
        self.is_client = is_client
        self.request = asyncio.Queue()
        self.__class__.cluster.append(self)
        self.state = State(self) if not is_client else None

    # https://python-doc-ja.github.io/py35/library/asyncio-protocol.html
    async def start(self):
        protocol = UDPProtocol(queue=self.request, request_handler=self.request_handler, loop=self.loop)
        address = (self.host, self.port)
        if self.is_client:
            self.transport, _ = await asyncio.Task(
            self.loop.create_datagram_endpoint(protocol, remote_addr=address),
            loop=self.loop)
            logger.info("Connecting to {}:{}".format(address[0], address[1]))
        else:
            self.transport, _ = await asyncio.Task(
            self.loop.create_datagram_endpoint(protocol, local_addr=address),
            loop=self.loop)
            
            # Start the state machine
            self.loop.create_task(self.state.start())
            logger.info("Starting node on {}:{}".format(address[0], address[1]))

    def stop(self):
        self.transport.close()

    def request_handler(self, data):
        self.state.request_handler(data)


    async def send(self, data):
        if not self.is_client:
            raise Exception("Only clients can send data")
        await self.request.put({"data": data})

    async def broadcast(self, data):
        for node in self.__class__.cluster:
            if node.is_client:
                await node.send(data)   