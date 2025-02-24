import asyncio
import json
from .network import NodeUDPProtocol, ClientUDPProtocol
from .logger import logger

from raft.state import State
from raft.o_state import OState
from raft.cca_state import CCAState
from raft.opt_cca_state import OptCCAState

def getStateClass(name):
    """ 指定された名前に基づいて適切なステートクラスを返す """
    if name == 'o':
        return OState
    elif name == 'cca':
        return CCAState
    elif name == 'opt_cca':
        return OptCCAState
    elif name == 'default':
        return State
    else:
        raise ValueError(f"Invalid state name: {name}")

async def register_as_server_node(names, loop, state_name):
    for name in names:
        if name not in Node.cluster:
            node = Node(name, loop, is_myself=True, state_name=state_name)
            logger.info("Starting {} as a node server".format(name))
            await node.start()

async def register_as_client_node(names, loop, state_name):
    for name in names:
        if name not in Node.cluster:
            node = Node(name, loop, is_myself=False, state_name=state_name)
            logger.info("Starting {} as a node client".format(name))
            await node.start()


async def register_as_raft_client(names, loop):
    for name in names:
        if name not in Client.clients:
            client = Client(name, loop)
            logger.info("Starting {} as a raft client".format(name))
            await client.start()


def stop():
    for node in Node.cluster:
        node.stop()
    for client in Client.clients:
        client.stop()

def setup():
    BaseNode.load_node_portlist()


class BaseNode:

    ip_to_name_dicts = {}

    cluster = []
    clients = []

    def __init__(self, name, loop, is_myself=False):
        self.name = name  # ノード名
        self.loop = loop or asyncio.get_event_loop()
        self.is_myself = is_myself  # クライアントかどうか
        self.request_queue = asyncio.Queue()

    @staticmethod
    def load_node_portlist():
        with open('node_portlist.json', 'r') as file:
            BaseNode.ip_to_name_dicts = json.load(file)

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


    def __init__(self, name, loop, state_name, is_myself=False,):
        super().__init__(name, loop, is_myself)
        self.state = getStateClass(state_name)(self) if is_myself else None
        self.__class__.cluster.append(self)


    async def start(self):
        protocol = NodeUDPProtocol(queue=self.request_queue, request_handler=self.request_handler, loop=self.loop, base_node=self)
        host = self.ip_to_name_dicts[self.name]['host']
        port = self.ip_to_name_dicts[self.name]['internal_port']
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

    def __init__(self, name, loop):
        super().__init__(name, loop, is_myself=False)
        self.requests = {}
        self.responses = {}
        self.__class__.clients.append(self)

    async def start(self):
        protocol = ClientUDPProtocol(queue=self.request_queue, request_handler=None, loop=self.loop, base_node=self)
        host = self.ip_to_name_dicts[self.name]['host']
        port = self.ip_to_name_dicts[self.name]['internal_port']
        address = (host, port)
        self.transport, _ = await asyncio.Task(
                self.loop.create_datagram_endpoint(protocol, remote_addr=address),
                loop=self.loop)
        logger.info("Connecting on {}:{}".format(address[0], address[1]))

    
    @staticmethod
    async def register_as_raft_client(names, loop):
        for name in names:
            if name not in Client.clients:
                client = Client(name, loop)
                logger.info("Starting {} as a client".format(name))
                await client.start()
