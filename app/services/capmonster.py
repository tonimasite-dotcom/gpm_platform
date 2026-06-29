from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import ImageToTextRequest

from app.dependencies import CAPMONSTER_API_KEY


client_options = ClientOptions(api_key=CAPMONSTER_API_KEY)
cap_monster_client = CapMonsterClient(options=client_options)


async def solve_captcha(image: bytes) -> str:
    captcha = ImageToTextRequest(
        image_bytes=image, threshold=95, case=True, numeric=False, math=False
    )
    result: dict = await cap_monster_client.solve_captcha(captcha)
    return result['text']

















