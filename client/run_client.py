import argparse
import asyncio

from client.client import PerformanceEvaluator
from client.cca_client import CCAPerformanceEvaluator
from client.opt_cca_client import OptCCAPerformanceEvaluator

def getClientClass(client_name):
    if client_name == 'cca':
        return CCAPerformanceEvaluator
    elif client_name == 'opt_cca':
        return OptCCAPerformanceEvaluator
    elif client_name == 'default' or client_name == 'o':
        return PerformanceEvaluator
    else:
        raise ValueError(f"Invalid client name: {client_name}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='client1')
    parser.add_argument('--client', default='default')
    args = parser.parse_args()

    client = getClientClass(args.client)(args.name)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client.run())