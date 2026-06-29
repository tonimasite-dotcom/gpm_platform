import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import Union, Optional

import aiohttp
from loguru import logger


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class NPDResponse:
    def __init__(self, status: bool, internal_error: bool, incorrect_inn: bool):
        self.status = status
        self.internal_error = internal_error
        self.incorrect_inn = incorrect_inn


class NPDChecker(metaclass=Singleton):
    def __init__(self):
        self._queue: list[str] = []
        self._last_time_request: datetime = datetime.now() - timedelta(seconds=31)

    async def check_status(self, inn: Union[str, int], user_tg_id: str) -> Optional[NPDResponse]:
        if user_tg_id in self._queue:
            return None
        self._queue.append(user_tg_id)

        while self._queue[0] != user_tg_id or self._last_time_request + timedelta(seconds=31) > datetime.now():
            await asyncio.sleep(1)

        result: NPDResponse = await self._check_npd(inn)
        self._last_time_request = datetime.now()
        self._queue.remove(user_tg_id)
        return result

    @staticmethod
    async def _check_npd(inn: str) -> NPDResponse:
        today_str = datetime.now().strftime("%Y-%m-%d")

        url = 'https://statusnpd.nalog.ru/api/v1/tracker/taxpayer_status'

        data = {
            "inn": f"{inn}",
            "requestDate": today_str
        }

        headers = {'content-type': 'application/json'}

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(url, data=json.dumps(data)) as response:
                    resp: dict = await response.json()

            result = resp.get('status')

            if result is None:
                error = resp.get('message')
                if 'Указан некорректный ИНН' in error:
                    return NPDResponse(status=False, internal_error=False, incorrect_inn=True)
                else:
                    return NPDResponse(status=False, internal_error=True, incorrect_inn=False)

            return NPDResponse(status=result, internal_error=False, incorrect_inn=False)

        except Exception as e:
            logger.error(traceback.format_exc())
            return NPDResponse(status=False, internal_error=True, incorrect_inn=False)

