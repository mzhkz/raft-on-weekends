import asyncio
from .logger import logger


class Timer:
    def __init__(self, interval, callback):
        """
        interval: タイマーの間隔（秒）
        callback: タイムアウト時に呼び出すコールバック関数
        """
        self.interval = interval
        self.callback = callback
        self.task = None
        self.is_running = False

    async def _run(self):
        """タイマーの実行ループ"""
        try:
            while self.is_running:
                await asyncio.sleep(self.interval)
                if self.is_running:  # sleep後も実行中か確認
                    await self.callback()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Timer error: {e}")

    def start(self):
        """タイマーを開始"""
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._run())

    def stop(self):
        """タイマーを停止"""
        self.is_running = False
        if self.task:
            self.task.cancel()
            self.task = None

    def reset(self):
        """タイマーをリセット"""
        self.stop()
        self.start()

    def is_active(self):
        """タイマーが実行中かどうかを返す"""
        return self.is_running