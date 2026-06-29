import asyncio
from threading import Thread
from typing import Coroutine, List


class SenderCounter:
    def __init__(self):
        self.count = 0


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class SendingManager(metaclass=Singleton):
    def __init__(self):
        self.threads: dict[str, Thread] = {}

    async def _mail(self, coros: List[List[Coroutine]]) -> None:
        for coro_list in coros:
            await asyncio.wait([asyncio.create_task(coro) for coro in coro_list])
            await asyncio.sleep(1)

    def _main_thread_func(self, coros: List[List[Coroutine]]) -> None:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._mail(coros=coros))

    async def _send_main(self, bot_token: str, coros: List[List[Coroutine]]) -> None:
        thread: Thread = Thread(target=self._main_thread_func, args=(coros,))
        self.threads[bot_token] = thread
        thread.start()
        while thread.is_alive():
            print('wait')
            await asyncio.sleep(10)

    async def send_main(self, bot_token: str, coros: List[List[Coroutine]]) -> None:
        thread: Thread = self.threads.get(bot_token)
        while thread and thread.is_alive():
            await asyncio.sleep(10)
        await self._send_main(bot_token, coros)


sending_manager = SendingManager()
