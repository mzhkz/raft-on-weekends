import argparse
import asyncio

from raft.server import register_as_client_node, register_as_server_node, register_as_raft_client


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--node')
    parser.add_argument('--cluster')
    parser.add_argument('--clients')
    parser.add_argument('--name')
    args = parser.parse_args()

    # 自分のノードのアドレス
    hostname = args.node
    node_address = ("0.0.0.0", 8080) # 8080で固定
    name = args.name

    # クラスターのノードのアドレス
    cluster_addresses = [(address, 8080) for address in args.cluster.split(',')]
    client_addresses = [(address, 8888) for address in args.clients.split(',')]

    loop = asyncio.get_event_loop()
    loop.create_task(register_as_server_node(names=[name], addresses=[node_address], loop=loop))
    loop.create_task(register_as_client_node(names=args.cluster.split(','), addresses=cluster_addresses, loop=loop))
    loop.create_task(register_as_raft_client(names=args.clients.split(','), addresses=client_addresses, loop=loop))
    loop.run_forever()
    # loop.run_until_complete(run(hostname))