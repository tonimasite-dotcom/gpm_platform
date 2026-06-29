from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram import types
from aiogram.dispatcher import FSMContext
import pytz
import re
from datetime import datetime
import json
from tortoise import Tortoise
from aiogram.dispatcher.filters import Text
from .operator_handler import operator_check_data
from app import dependencies
from app.dependencies import bot, DB_CONFIG,dp,app, global_config, MODERATOR_ID, get_config

from app.services import bot_texts as bt
from app.db import models
from app.services.states import OperatorState
from logs.log_info import logger
from app.services.city_location import search_address,ForbiddenError

def get_date(order_data):
    if isinstance(order_data, str):
        order_data = json.loads(order_data)

    order_details = order_data.get("order_data", {})
    completion_data = order_details.get("completion_date", {})

    completion_date_str = completion_data.get("date")
    timezone_str = order_details.get("timezone", "UTC")

    if not completion_date_str:
        raise KeyError("Ключ 'completion_date.date' отсутствует в JSON!")

    completion_date_utc = datetime.fromisoformat(completion_date_str[:-1])
    completion_date_utc = pytz.utc.localize(completion_date_utc)

    try:
        timezone = pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        raise ValueError(f"Неизвестная временная зона: {timezone_str}")

    completion_date_local = completion_date_utc.astimezone(timezone)
    return completion_date_local.strftime("%d.%m.%Y %H:%M")


# def get_price_per_hour(order_data):

#     if isinstance(order_data, str):
#         order_data = json.loads(order_data)

#     order_details = order_data.get("order_data", {})
#     tariff_str = order_details.get("tariff", "")
#     try:
#         if tariff_str:
#             tariff_values = tariff_str.split("/")
#             if len(tariff_values) > 1:
#                 tariffs = [int(value) for value in tariff_values if int(value) > 0]
#                 if tariffs:
#                     return min(tariffs)
#     except:
#         return 350

#     return 350  # Значение по умолчанию


def prepare_message(data: dict) -> str:
    
    text = "Необходимо выбрать город" + "\n"
    text += bt.REQUEST_ORDER_ID_MSG.format(order_id=data["order_id"]) + "\n"
    text += bt.REQUEST_DATE_MSG.format(date=data["date"]) + "\n"
    text += bt.REQUEST_PEOPLE_MSG.format(people=data["people_amount"]) + "\n"
    
    national = data.get('national')
    if national == 'yes':
        national = 'Да'
    elif national == 'no':
        national = 'Нет'
    else:
        national = 'Не важно'
    text += bt.REQUEST_NATIONAL_MSG.format(national=national) + "\n"

    if data["metro"]:
        text += bt.REQUEST_METRO_MSG.format(metro=data["metro"]) + "\n"

    if data["address_number"] == "0" and data["address_lat"] == 0 and data["address_lon"] == 0:
        text += bt.REQUEST_MANUAL_ADDRESS_MSG.format(address=data["address_street"]) + "\n"
    else:
        text += bt.REQUEST_ADDRESS_MSG.format(
            address=f"{data['address_street']} д. {data['address_number']}",
            lat=data["address_lat"],
            lon=data["address_lon"],
        ) + "\n"
    
    
    text += bt.REQUEST_COMMENT_MSG.format(comment=data["description"]) + "\n"
    text += bt.REQUEST_PRICE_REGULAR_MSG.format(price_regular=data["price_regular"]) + "\n"
    text += bt.REQUEST_PRICE_STATE_MSG.format(price_state=data["price_state"]) + "\n"
    text += bt.REQUEST_PRICE_HOUR_MSG.format(price_hour=data["price_per_hour"]) + "\n"
    text += bt.REQUEST_MIN_TIME_MSG.format(min_time=data["min_time"]) + "\n"
    text += bt.REQUEST_STATUS_MSG.format(status="Открыт ✅") + "\n"

    return text

async def get_city():
    mk = types.InlineKeyboardMarkup()
    bots = await models.Bot.all().values('id', 'city')
    for bot in bots:
        mk.row(types.InlineKeyboardButton(text=bot['city'], callback_data=f'choose_city:{bot["id"]}'))

    return mk

@dp.callback_query_handler(Text(startswith='choose_city:'),state='*')
async def choose_city(call: types.CallbackQuery, state: FSMContext):
    try:
        user = await models.User.get_user(call.from_user.id)
       
        
        match = re.search(r"Номер заказа:\s*([\w/-]+)", call.message.text)
        bot_id = int(call.data.split(':')[1])
        order_number = match.group(1)
        data = await models.Order.get(order_id=order_number)
        
        
        operator = await models.Operator.get_operator(user)
        if not operator:
            call.message.edit_text('Вы не являетесь оператором')
            await data.delete()
            await data.save()
            return
        
        await OperatorState.min_time.set()
        await state.set_data(data.data)

        bot = await models.Bot.get_by_id_prefetched_towns(bot_id)
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
            
        if len(bot.towns) == 0 :

          
            await state.update_data(bot_id=bot_id)
            data = await state.get_data()
            try:
                if global_config.bypass_geocoder:
                    raise ForbiddenError('geocoder is disabled')
                address_data: list
                address_data = await search_address(data.get('address_street'), bot.city, bot.state)
                if address_data is None:
                    await call.message.answer('Адрес не найден геокодером')
                    await operator_check_data(call.message, state)
                else:
                    address_dict = address_data[0]
                    await state.update_data(address_street=address_dict["street"],
                                    address_number=address_dict["housenumber"],
                                    address_lat=address_dict['lat'],
                                    address_lon=address_dict['lon'])
                    await operator_check_data(call.message, state)
            except ForbiddenError as e:
                if 'geocoder is disabled' not in str(e):
                    global_config.bypass_geocoder = True
                await call.bot.send_message(
                    MODERATOR_ID,
                    text='Api ключ геокодера недействителен. \n'
                        'Геокодер отключен.\n'
                        'Адреса будут вводиться вручную, без координат'
                )
                await operator_check_data(call.message, state)
            await call.message.delete()
        else:    
            mk.row(types.InlineKeyboardButton(text=bot.city, callback_data=f'crmoperator_region:{bot.id}'))
            for town in bot.towns:
                mk.row(types.InlineKeyboardButton(text=town.name, callback_data=f'crmoperator_region:t{town.id}'))

            mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
            await call.message.edit_text(text=bt.OPERATOR_SELECT_REGION_MSG, reply_markup=mk)
        
    except Exception as e:
        logger.error(f'Ошибка црм интеграции {e}')
        pass

@dp.callback_query_handler(Text(startswith='crmoperator_region:'), state='*')
async def operator_region(call: types.CallbackQuery, state: FSMContext):
    region_id = call.data.split(':')[1]
    if region_id.startswith('t'):
        region_id = int(region_id[1:])
        await state.update_data(region_id=region_id)
        town = await models.Town.get_by_id(region_id)
        bot_id = town.bot.id
    else:
        region_id = int(region_id)
        await state.update_data(bot_id=region_id)
        city = await models.Bot.get_by_id(region_id)
        bot_id = city.id
    bot = await models.Bot.get_by_id(bot_id)
    data = await state.get_data()
    try:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
        
        if global_config.bypass_geocoder:
            raise ForbiddenError('geocoder is disabled')
        address_data: list
        address_data = await search_address(data.get('address_street'), bot.city, bot.state)
        if address_data is None:
            await call.message.answer('Адрес не найден геокодером')
            await operator_check_data(call.message, state)
        else:
            address_dict = address_data[0]
            await state.update_data(address_street=address_dict["street"],
                                    address_number=address_dict["housenumber"],
                                    address_lat=address_dict['lat'],
                                    address_lon=address_dict['lon'])
            await operator_check_data(call.message, state)
    except ForbiddenError as e:
        if 'geocoder is disabled' not in str(e):
            global_config.bypass_geocoder = True
        await call.bot.send_message(
            MODERATOR_ID,
            text='Api ключ геокодера недействителен. \n'
            'Геокодер отключен.\n'
            'Адреса будут вводиться вручную, без координат'
        )
        await operator_check_data(call.message, state)
    await call.message.delete()
   

@app.post("/api")
async def request_to_bot(data: Request):
    
    try:
        order_data = await data.json()

        if not order_data or not isinstance(order_data, dict):
            raise ValueError("Ошибка: JSON пуст или имеет некорректный формат!")

        
        order_details = order_data.get("order_data", {})

        if not isinstance(order_details, dict):
            raise KeyError("Ошибка: 'order_data' отсутствует или имеет неверный формат!")

        
        completion_data = order_details.get("completion_date", {})
    
        if not isinstance(completion_data, dict):
            raise KeyError("Ошибка: 'completion_date' отсутствует или имеет неверный формат!")

        
        loaders_data = order_details.get("loaders", {})
        

        if not isinstance(loaders_data, dict):
            raise KeyError("Ошибка: 'loaders' отсутствует или имеет неверный формат!")

        
        info_data = order_details.get("info", {})
        info_additional = info_data.get("additional", "")

        if isinstance(info_additional, (list, dict)):  
            info_additional = str(info_additional)
        info_additional = info_additional.replace("\\xa0", " ")
        if not isinstance(info_data, dict):
            raise KeyError("Ошибка: 'info' отсутствует или имеет неверный формат!")

        complete_data = {
            "region_id": None,
            "bot_id": None,
            "date": get_date(order_data),
            "order_id": order_details.get("order_number", "Неизвестный номер"),
            "people_amount": loaders_data.get("loader_count", 0),
            "national": "yes" if "Только РФ" in info_additional else "every",
            "metro": info_data.get("metro_station"),
            "address_street": info_data.get("address", "Адрес не указан"),
            "address_number": "0",
            "address_lat": 0,
            "address_lon": 0,
            "description": (order_details.get("note", "") or "")[:800],
            "price_per_hour": get_config('min_cost'),
            "price_regular": get_config('price_regular'),
            "price_state": get_config('price_state'),
            "min_time": order_details.get("min_time", 4),
        }
        mk = await get_city()
        user = await models.User.get_by_username(order_data.get("telegram_username"))  
        order = await models.Order.get_or_none(order_id=order_details.get("order_number"))
        if order:
            await order.delete()
            await order.save()
        await models.Order.create(order_id=order_details.get("order_number"),data=complete_data)
        await bot.send_message(text=prepare_message(complete_data), chat_id=user.telegram_id,reply_markup=mk)
        print("Received data:", data)
        return {"success": True}

    except Exception as e:
        print("Error:", e)  
        logger.info(f'Ошибка {e}')
        return {"status": "error", "message": str(e)}

