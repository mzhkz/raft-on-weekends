import asyncio
import uuid
import random
import json
from raft.serializers import MessagePackSerializer
from raft.logger import logger
from raft.timer import Timer

from client.network import ClientUDPProtocol
from evaluator.client import PerformanceEvaluator

from crypto.VSS import split, combine
from crypto.parameters import TEST_PARAMS

class CCAPerformanceEvaluator(PerformanceEvaluator):
    def __init__(self, name, duration, requests_per_second, write_ratio, key_range, evaluator_name):
        super().__init__(name, duration, requests_per_second, write_ratio, key_range, evaluator_name)
        
       # cca client用の変数
        self.granted_share_events = {}
        self.share_granted = {}
        
        logger.info(f"CCAPerformanceEvaluator {self.name} initialized")

    def handle_response(self, response):
        request_id = response.get('request_id')
        response_type = response.get('type')
        if response_type == 'ClientWriteResponse':
            self.handle_write_response(response)
        elif response_type == 'ClientWriteShareResponse':
            self.handle_write_share_response(response)
        elif response_type == 'ClientGetShareResponse':
            self.handle_get_share_response(response)


    def handle_write_share_response(self, response):
        """シェアを受け取った時の処理"""
        request_id = response.get('request_id')
        if response.get('success'):
            if request_id in self.granted_share_events and request_id in self.share_granted:
                self.share_granted[request_id] += 1
                if self.share_granted[request_id] > len(self.cluster_info.keys()) // 2:
                    if request_id in self.granted_share_events:
                        self.granted_share_events[request_id].set()
                        del self.share_granted[request_id]
        else:
            logger.error(f"シェアを書き込めなかった: {request_id} {response.get('error')}")

    def handle_get_share_response(self, response):
        """シェアを受け取った時の処理"""
        request_id = response.get('request_id')
        if response.get('success'):
            # 読み込みリクエストの場合は、結果を保存して、read_eventを発火
            if request_id in self.read_events:
                if not request_id in self.read_results:
                    self.read_results[request_id] = []
                # シェアを保存
                self.read_results[request_id].append(response.get('shares'))
                # 2個のノードからシェアをもらったら、read_eventを発火
                if len(self.read_results[request_id]) >= 2:
                    total_shares = []
                    # シェアを一次元に結合
                    for result in self.read_results[request_id]:
                        total_shares.extend(result)
                    self.read_results[request_id] = total_shares
                    self.read_events[request_id].set()
                    # 読み込み成功数をインクリメント
                    self.successful_requests += 1
                    self.read_successful += 1
        else:
            logger.error(f"シェアを受け取れなかった: {request_id} {response.get('error')}")

    async def read_handler(self, key, request_id):
        """ 読み込みリクエストを送信 """
        self.read_events[request_id] = asyncio.Event()

        request = {
            'type': 'ClientGetShare',
            'key': key,
            'request_id': request_id,
        }

        # リーダーともう一つのノードにリクエストを送信
        await self.send_request_to_leader({"data": request})  # リーダーにリクエスト
        await self.send_request({"data": request}, list(self.cluster_info.keys())[1])  # もう一つのノードにリクエスト


        #  unique_shares = []
        #     for share in self.read_results[request_id]:
        #         if share not in unique_shares:
        #             unique_shares.append(share)

        #     result = combine(unique_shares, TEST_PARAMS['q']) # シェアを結合


    async def write_handler(self, key, value, request_id):
        """ 書き込みリクエストを送信 """

        node_count = len(self.cluster_info.keys())

        # シェアをレプリケーション  
        result = split(value, node_count, node_count, TEST_PARAMS['p'], TEST_PARAMS['q'], TEST_PARAMS['g'])
        shares = result["shares"]
        commitments = result["commitments"]

        self.granted_share_events[request_id] = asyncio.Event()
        self.share_granted[request_id] = 0

        for node_name in self.cluster_info.keys():
            node_index = list(self.cluster_info.keys()).index(node_name)
            shares_copy = shares.copy()
            shares_copy.pop(node_index)
            request = {
                'type': 'ClientWriteShare',
                'shares': shares, ## 擬似的なシェア分配
                'request_id': request_id,
            }
            await self.send_request({"data": request}, node_name)

        # シェアが揃ったら、コミットを実行
        try:
            await asyncio.wait_for(self.granted_share_events[request_id].wait(), timeout=5.0)
            del self.granted_share_events[request_id]
        except asyncio.TimeoutError:
            logger.error(f"シェアが揃わないままタイムアウトしました: {request_id}")
            del self.granted_share_events[request_id]
            return False
        
        request = {
            'type': 'ClientWrite',
            'key': key,
            'commitments': commitments,
            'request_id': request_id,
        }
        
        await self.send_request_to_leader({"data": request})
