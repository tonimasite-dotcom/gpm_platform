from pprint import pprint
from typing import Optional, Tuple

import aiohttp

from app import dependencies

class ForbiddenError(Exception):
    pass


async def reverse_geocode(lat, lon) -> Optional[Tuple[str, str]]:
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

    if 'address' in data:
        address = data['address']
        city = address.get('city', None)
        if not city:
            city = address.get('town', None)
            if not city:
                city = address.get('village', None)

        state = address.get('state', None)

        return city, state


async def address_details(session: aiohttp.ClientSession, place_id: int) -> dict:
    url = f"https://nominatim.openstreetmap.org/details?place_id={place_id}&format=json"
    async with session.get(url) as response:
        data = await response.json()
        return data


async def search_city(city: str) -> Optional[str]:
    url = f"https://nominatim.openstreetmap.org/search?city={city}&format=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if len(data) == 0:
                return None
            place_id = data[0]['place_id']
            address = await address_details(session, place_id)
            city = address.get('localname', None)
            return city


async def search_address(address: str, city: str, state: str):
    address = address.replace(' ', '+')
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={dependencies.GEOCODER_API}&geocode={address}+{city}&format=json"
    return_data = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if data.get('statusCode') == 403:
                raise ForbiddenError(data['message'])
            data = data['response']['GeoObjectCollection']['featureMember']
            if len(data) == 0:
                return None

            for place in data:
                if place['GeoObject']['metaDataProperty']['GeocoderMetaData']['kind'] != 'house':
                    continue

                components = place['GeoObject']['metaDataProperty']['GeocoderMetaData']['Address']['Components']
                street = None
                house_number = None
                for component in components:
                    if component['kind'] == 'house':
                        house_number = component['name']
                    if component['kind'] == 'street':
                        street = component['name']

                if street is None:
                    for component in components:
                        if component['kind'] == 'district':
                            street = component['name']

                if street is None:
                    for component in components:
                        if component['kind'] == 'locality':
                            street = component['name']

                if street and house_number:
                    return_data.append(
                        {
                            'housenumber': house_number,
                            'street': street,
                            'lat': float(place['GeoObject']['Point']['pos'].split()[1]),
                            'lon': float(place['GeoObject']['Point']['pos'].split()[0])
                        }
                    )

            if len(return_data) > 0:
                return return_data
            else:
                return None


async def search_state(state: str) -> Optional[str]:
    url = f"https://nominatim.openstreetmap.org/search?state={state}&format=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if len(data) == 0:
                return None
            place_id = data[0]['place_id']
            address = await address_details(session, place_id)
            state = address.get('localname', None)
            return state


async def test(address: str, city: str, state: str = None):
    address = address.replace(' ', '+')
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={dependencies.GEOCODER_API}&geocode={address}+{city}&format=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            # pprint(data['response']['GeoObjectCollection']['featureMember'])
            pprint(data)


if __name__ == "__main__":
    import asyncio
    pprint(asyncio.run(search_address('ул Мира д.4', 'Пермь', None)))
