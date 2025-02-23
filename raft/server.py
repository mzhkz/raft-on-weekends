import asyncio
from .network import NodeUDPProtocol, ClientUDPProtocol
from .logger import logger
from .state import State


async def register_as_server_node(names, addresses, loop):
    for address, name in zip(addresses, names):
        if address not in Node.cluster:
            node = Node(name, *address, loop, is_myself=True)
            logger.info("Starting {} as a node server".format(name))
            await node.start()

async def register_as_client_node(names, addresses, loop):
    for address, name in zip(addresses, names):
        if address not in Node.cluster:
            node = Node(name, *address, loop, is_myself=False)
            logger.info("Starting {} as a node client".format(name))
            await node.start()


async def register_as_raft_client(names, addresses, loop):
    for address, name in zip(addresses, names):
        if address not in Client.clients:
            client = Client(name, *address, loop)
            logger.info("Starting {} as a raft client".format(name))
            await client.start()


def stop():
    for node in Node.cluster:
        node.stop()
    for client in Client.clients:
        client.stop()


class BaseNode:
    def __init__(self, name, host, port, loop, is_myself=False):
        self.name = name  # ノード名
        self.host = host  # ホスト名
        self.port = port  # ポート番号
        self.loop = loop or asyncio.get_event_loop()
        self.is_myself = is_myself  # クライアントかどうか
        self.request_queue = asyncio.Queue()

    async def start(self):
        raise NotImplementedError("Subclasses should implement this!")

    def stop(self):
        self.transport.close()

    def request_handler(self, data):
        loop = asyncio.get_event_loop()
        loop.create_task(self.state.receive(data))


    async def send(self, data):
        # サーバーの場合には送信する
        if not self.is_myself:
            await self.request_queue.put({"data": data})

    @staticmethod
    async def broadcast(data):
        for node in Node.cluster:
            # サーバーの場合には送信する
            if not node.is_myself:
                await node.send(data)  



class Node(BaseNode):
    cluster = []


    def __init__(self, name, host, port, loop, is_myself=False):
        super().__init__(name, host, port, loop, is_myself)
        self.state = State(self) if is_myself else None
        self.__class__.cluster.append(self)

    async def start(self):
        protocol = NodeUDPProtocol(queue=self.request_queue, request_handler=self.request_handler, loop=self.loop, base_node=self)
        host = f"10.0.0.{int(self.name.split('node')[1])+1}"
        port = self.port
        address = (host, port)
        if not self.is_myself:
            self.transport, _ = await asyncio.Task(
                self.loop.create_datagram_endpoint(protocol, remote_addr=address),
                loop=self.loop)
            logger.info("Connecting to {}:{}".format(address[0], address[1]))
        else:
            self.transport, _ = await asyncio.Task(
                self.loop.create_datagram_endpoint(protocol, local_addr=address),
                loop=self.loop)
            logger.info("Listeing on {}:{}".format(address[0], address[1]))

            # Start the state machine
            self.loop.create_task(self.state.start())


class Client(BaseNode):
    clients = []

    def __init__(self, name, host, port, loop):
        super().__init__(name, host, port, loop, is_myself=False)
        self.requests = {}
        self.responses = {}
        self.__class__.clients.append(self)

    async def start(self):
        protocol = ClientUDPProtocol(queue=self.request_queue, request_handler=None, loop=self.loop, base_node=self)
        # クライアントのIPアドレスを取得
        host = f"10.0.1.{int(self.name.split('client')[1])+1}"
        port = self.port
        address = (host, port)
        self.transport, _ = await asyncio.Task(
                self.loop.create_datagram_endpoint(protocol, remote_addr=address),
                loop=self.loop)
        logger.info("Connecting on {}:{}".format(address[0], address[1]))

    
    @staticmethod
    async def register_as_raft_client(names, addresses, loop):
        for address, name in zip(addresses, names):
            if address not in Client.clients:
                client = Client(name, *address, loop)
                logger.info("Starting {} as a client".format(name))
                await client.start()
