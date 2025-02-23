import argparse
import raft
import asyncio


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--node')
    parser.add_argument('--cluster')
    parser.add_argument('--name')
    args = parser.parse_args()

    hostname = args.node
    node_address = ("0.0.0.0", 8080) # 8080で固定
    name = args.name
    cluster_addresses = [(address, 8080) for address in args.cluster.split(',')]


    loop = asyncio.get_event_loop()
    loop.create_task(raft.register_as_server_node(names=[name], addresses=[node_address], loop=loop))
    loop.create_task(raft.register_as_client_node(names=args.cluster.split(','), addresses=cluster_addresses, loop=loop))
    loop.run_forever()
    # loop.run_until_complete(run(hostname))