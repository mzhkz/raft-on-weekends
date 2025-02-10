import asyncio
from .logger import logger
class State:
    """基本的にはここに必要なメソッドや変数を追加していく"""
    
    def __init__(self, node):
        self.node = node
        self.loop = self.node.loop or asyncio.get_event_loop()
        self.logs = ["x += 1"]
        self.statemachine = {"x": 1, "y": "2"}
        self.counter = 1


    # サンプルプログラム：ノードから受信したら、カウンターを増やす
    # data: {"sender": "node_name", "data": "data"}
    # sedner: 送信元のノード名
    # data: 送信元から受信したデータ
    async def receive(self, data):
        received_from = data["sender"] # 送信元のノード名を取得
        received_message = data["data"] # 送信元から受信したデータを取得
        logger.info("{}からメッセージをもらった！!: {}".format(received_from, received_message))
        self.logs.append(received_message) # 1番
        await asyncio.sleep(1)
        
        # リーダーにログを追加
        self.counter+=1
        if  self.counter >= 2:
            # ログの過半数以上をゲットしたら、コミットする
            # ログをコミットする
            # コミットしたログをステートマシンに適用する
            # コミットしたログを削除する
             self.counter = 1
        
        
        # リーダーだったら、ログ過半数以上ゲットするまでまつ
        # 
        

    # サンプルプログラム：ノード毎にカウンターを5秒ごとに送信する
    # 5秒ごとにノード毎のカウントを自分を除くすべてのノードに送信する
    async def start(self):
        from .server import Node
        if self.node.name == "node1": # 自分がリーダーだったら
            logentry = {"x": 100}
            await asyncio.sleep(5)
            self.logs.append(logentry) # 2番
            for node in Node.cluster: 
                if node.is_client: # 自分を除くすべてのノードに送信
                    await node.send(logentry) # ３番 データ送信


    def stop():
        pass