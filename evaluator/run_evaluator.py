import argparse
import asyncio

from evaluator.client import PerformanceEvaluator
# from evaluator.cca_client import CCAPerformanceEvaluator
# from evaluator.opt_cca_client import OptCCAPerformanceEvaluator

def getEvaluatorClass(evaluator_name):
    return PerformanceEvaluator 

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='client1')
    parser.add_argument('--client', default='default')
    args = parser.parse_args()

    evaluator = getEvaluatorClass(args.evaluator)(args.name)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(evaluator.run())