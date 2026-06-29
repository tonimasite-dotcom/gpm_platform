import json
import traceback
import asyncio
from typing import Optional
import os
import sys
current_dir = os.path.dirname(os.path.realpath(__file__))

parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
main_dir = os.path.abspath(os.path.join(parent_dir, os.pardir))
sys.path.append(main_dir)

from tortoise import Tortoise
from app import dependencies
from app.db import models



from tortoise import Tortoise
from app import dependencies
from app.db import models

import json
import traceback
from typing import Optional

import aiohttp
import jwt
from loguru import logger

from app.db.models import Implementer
from app.dependencies import YOUDO_KID,YOUDO_CID, YOUDO_ISS, YOUDO_PRIVATE_KEY_PATH, YOUDO_PROJECT_ID


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class YouDoAPI(metaclass=Singleton):
    def __init__(self):
        self.kid: str = YOUDO_KID
        self.iss: str = YOUDO_ISS
        self.cid: str = YOUDO_CID
        self.__jwt: Optional[str] = None

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._jwt}", "Content-Type": "application/json"}

    @property
    def _jwt(self):
        if self.__jwt is None:
            self.__jwt = self._get_jwt()
        return self.__jwt

    def _get_jwt(self) -> str:
        with open('.private_key', 'r') as file:
            self.private_key = file.read()
        token = jwt.encode(
            payload={"iss": self.iss,"cid": self.cid},
            key=self.private_key,
            algorithm='RS256',
            headers={"alg": "RS256", "typ": "JWT", "kid": self.kid},
        )
        return token.decode()

    async def _create_user(self, implementer: Implementer, inn: str) -> dict:
        url = 'https://business-api.youdo.com/api/v1/Employee'
        full_name_split = implementer.full_name.split(' ')
        last_name = full_name_split[0]
        first_name = full_name_split[1]
        middle_name = ' '.join(full_name_split[2:])

        data = {
            "projectId": YOUDO_PROJECT_ID,
            "firstName": first_name,
            "lastName": last_name,
            "middleName": middle_name,
            "phone": implementer.phone_number,
            "inn": inn,
        }

        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.post(url, data=json.dumps(data)) as response:
                data = await response.json()

        return data

    async def create_user(self, implementer: Implementer, inn: str) -> Optional[int]:
        try:
            data = await self._create_user(implementer, inn)
            print (data)
            if data.get('error'):
                return 0
            return data['employeeId']

        except Exception as e:
            logger.exception(traceback.format_exc())
            return None

    async def _get_user(self, implementer: Implementer) -> dict:
        url = f'https://business-api.youdo.com/api/v1/Employee/{implementer.youdo_id}'

        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.get(url) as response:
                data = await response.json()
                print(data)

        return data

    async def check_user_ready_to_pay(self, implementer: Implementer) -> Optional[bool]:
        try:
            data = await self._get_user(implementer)
            if data['statusCode'] == "readyToPay":
                return True
            else:
                return False

        except Exception as e:
            logger.exception(traceback.format_exc())

async def check_data():
    user = await models.User.get_user(370901479)
    implementer = await models.Implementer.get_by_id(323)
    youdo_id = await YouDoAPI().check_user_ready_to_pay(implementer)

    print (youdo_id)

async def init_db():
    await Tortoise.init(dependencies.DB_CONFIG)
    await Tortoise.generate_schemas()

async def main():
   await init_db()
   await check_data()

if __name__ == "__main__":
    asyncio.run(main())