from io import BytesIO

import yadisk_async
from app.dependencies import CLIENT_ID, CLIENT_SECRET, YANDEX_TOKEN


async def upload_file(file_path: BytesIO, ya_disk_path: str) -> bool:
    y = yadisk_async.YaDisk(CLIENT_ID, CLIENT_SECRET, YANDEX_TOKEN)
    if not await y.check_token():
        return False

    await y.upload(file_path, ya_disk_path)
    await y.close()
    return True


async def delete_file(file_name: str) -> bool:
    y = yadisk_async.YaDisk(CLIENT_ID, CLIENT_SECRET, YANDEX_TOKEN)
    if not await y.check_token():
        return False

    try:
        await y.remove(f"disk:/Подрядчики Телеграмм Бот паспорта/{file_name}.jpg")
    except yadisk_async.exceptions.PathNotFoundError:
        return False
    finally:
        await y.close()

    return True


async def test():
    file_path = "disk:/Подрядчики Телеграмм Бот паспорта/Тест_Евгений_Тест_Пермь_05_07_2023.jpg"
    print(await delete_file(file_path))


if __name__ == '__main__':
    import asyncio
    asyncio.run(test())
