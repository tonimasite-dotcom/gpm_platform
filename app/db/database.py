from tortoise import Tortoise
from app import dependencies


async def init_db():
    await Tortoise.init(dependencies.DB_CONFIG)
    await Tortoise.generate_schemas()


async def close_db():
    await Tortoise.close_connections()
