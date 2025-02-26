import argparse
import asyncio

from evaluator.client import PerformanceEvaluator
from evaluator.cca_client import CCAPerformanceEvaluator
from evaluator.opt_cca_client import OptCCAPerformanceEvaluator

def getEvaluatorClass(evaluator_name):
    if evaluator_name == 'default':
        return PerformanceEvaluator
    elif evaluator_name == 'cca':
        return CCAPerformanceEvaluator
    elif evaluator_name == 'opt_cca':
        return OptCCAPerformanceEvaluator

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='client1')
    parser.add_argument('--evaluator', default='default')
    parser.add_argument('--duration', default=4)
    parser.add_argument('--requests_per_second', default=1000)
    parser.add_argument('--write_ratio', default=1.0)
    parser.add_argument('--key_range', default=10)
    args = parser.parse_args()

    evaluator = getEvaluatorClass(args.evaluator)(args.name, int(args.duration), int(args.requests_per_second), float(args.write_ratio), int(args.key_range))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(evaluator.run())