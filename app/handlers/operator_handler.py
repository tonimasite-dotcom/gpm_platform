import datetime 
import traceback
from io import BytesIO
from typing import Union, List, Coroutine
from logs.log_info import logger
import json

from aiogram import types, Bot
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.utils.exceptions import BotBlocked

from app import dependencies
from app.db import models
from app.db.models import User, ChatMessages
from app.dependencies import dp, global_config, MODERATOR_ID,API_TOKEN, CHAT_IDS, REQUESTS_ID, TICKETS_ID, RAISING_ID
from app.services import bot_texts as bt
from app.services.city_location import search_address, ForbiddenError
from app.services.keyboard import requests_cd
from app.services.states import OperatorState
from app.services.ya_disk import delete_file, upload_file
from app.services.sending_manager import SenderCounter, sending_manager
from app.services.priority_groups import get_priority_group

@dp.message_handler(commands=['register_operator'], state='*')
async def register_operator(message: types.Message, state: FSMContext):
    user = await models.User.get_user(message.from_user.id)
    if user is None:
        user = await models.User.add_user(message.from_user)

    operator = await models.Operator.get_operator(user)
    if operator is not None:
        await message.answer(text=bt.ALREADY_OPERATOR_MSG)
        return

    request = await models.OperatorInvite.add_request(user)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.CONFIRM_BTN, callback_data=f'confirm_operator_request:{request.id}'))
    mk.row(types.InlineKeyboardButton(text=bt.DECLINE_BTN, callback_data=f'decline_operator_request:{request.id}'))
    msg_text = bt.NEW_OPERATOR_REQUEST_MSG.format(
        telegram_id=user.telegram_id,
        username=user.username
    )
    await message.bot.send_message(chat_id=dependencies.MODERATOR_ID, text=msg_text, reply_markup=mk)
    await message.answer(text=bt.OPERATOR_REQUEST_SEND_MSG, reply_markup=types.ReplyKeyboardRemove())


@dp.callback_query_handler(text='add_request', state='*')
async def add_request(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    bots = await models.Bot.all().values('id', 'city')
    mk = types.InlineKeyboardMarkup()
    user = await models.User.get_user(call.from_user.id)
    operator = await models.Operator.get_operator(user)
    if await check_for_seal(operator):
        return
    for bot in bots:
        mk.row(types.InlineKeyboardButton(text=bot['city'], callback_data=f'operator_city:{bot["id"]}'))

    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    if call.message.text != bt.OPERATOR_SELECT_CITY_MSG or call.message.reply_markup != mk:
        try:
            await call.message.edit_text(text=bt.OPERATOR_SELECT_CITY_MSG, reply_markup=mk)
            await OperatorState.first()
        except:
            pass


@dp.callback_query_handler(Text(startswith='operator_city:'), state='*')
async def operator_city(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    bot_id = int(call.data.split(':')[1])
    bot = await models.Bot.get_by_id_prefetched_towns(bot_id)
    if len(bot.towns) == 0:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
        await state.update_data(bot_id=bot_id)
        await call.message.edit_text(text=bt.OPERATOR_SEND_ORDER_ID_MSG, reply_markup=mk)
        await OperatorState.order_id.set()
        return

    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bot.city, callback_data=f'operator_region:{bot.id}'))
    for town in bot.towns:
        mk.row(types.InlineKeyboardButton(text=town.name, callback_data=f'operator_region:t{town.id}'))

    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await call.message.edit_text(text=bt.OPERATOR_SELECT_REGION_MSG, reply_markup=mk)
    await OperatorState.next()


@dp.callback_query_handler(Text(startswith='operator_region:'), state='*')
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

    await OperatorState.date.set()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await call.message.edit_text(text=bt.OPERATOR_SEND_ORDER_ID_MSG, reply_markup=mk)
    await OperatorState.order_id.set()


@dp.message_handler(state=OperatorState.order_id)
async def operator_order_id(message: types.Message, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await state.update_data(order_id=message.text)
    await message.answer(text=bt.OPERATOR_SEND_DATE_MSG, reply_markup=mk)
    await OperatorState.next()


@dp.callback_query_handler(text='operator_date', state='*')
@dp.message_handler(state=OperatorState.date)
async def operator_date(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    if isinstance(message, types.Message):
        date = message.text
        await state.update_data(date=date)
    else:
        await message.message.edit_reply_markup()
        message = message.message

    data = await state.get_data()
    region_id = data.get('region_id')
    if region_id is None:
        bot_id = data.get('bot_id')
        bot = await models.Bot.get_by_id(bot_id)
        mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    else:
        region = await models.Town.get_by_id(region_id)
        mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))

    await message.answer(text=bt.OPERATOR_SEND_PEOPLE_MSG, reply_markup=mk)
    await OperatorState.next()


@dp.callback_query_handler(text='operator_people_amount', state='*')
@dp.message_handler(state=OperatorState.people_amount)
async def operator_people_amount(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    if isinstance(message, types.Message):
        people_amount = message.text
        if not people_amount.isdigit() or int(people_amount) > 150:
            mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='operator_date'))
            await message.answer(text=bt.OPERATOR_WRONG_PEOPLE_AMOUNT_FORMAT_MSG,
                                 reply_markup=mk)
            return
        await state.update_data(people_amount=people_amount)
    else:
        await message.message.edit_reply_markup()
        message = message.message

    mk.row(types.InlineKeyboardButton(text=bt.RUSSIAN_BTN, callback_data='operator_national:yes'))
    #mk.row(types.InlineKeyboardButton(text=bt.NOT_RUSSIAN_BTN, callback_data='operator_national:no'))
    mk.row(types.InlineKeyboardButton(text=bt.EVERY_ONE_BTN, callback_data='operator_national:every'))
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text=bt.OPERATOR_CHOICE_NATIONALITY_MSG, reply_markup=mk)
    await OperatorState.next()


@dp.callback_query_handler(Text(startswith='operator_national:'), state='*')
async def operator_national(call: types.CallbackQuery, state: FSMContext):
    national = call.data.split(':')[1]
    await state.update_data(national=national)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.SKIP_BTN, callback_data='skip_metro'))
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await call.message.edit_reply_markup()
    await call.message.answer(text=bt.OPERATOR_SEND_METRO_MSG, reply_markup=mk)
    await OperatorState.next()


@dp.callback_query_handler(text='skip_metro', state='*')
async def skip_metro(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(metro=None)
    data = await state.get_data()
    min_time = data.get('min_time')
    if min_time:
        await operator_min_time(call, state)
    else:
        await operator_metro(call, state)


@dp.callback_query_handler(text='operator_metro', state='*')
@dp.message_handler(state=OperatorState.metro)
async def operator_metro(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    if isinstance(message, types.Message):
        metro = message.text
        await state.update_data(metro=metro)
    else:
        await message.message.edit_reply_markup()
        message = message.message

    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text=bt.OPERATOR_SEND_ADDRESS_MSG, reply_markup=mk)
    await OperatorState.address.set()


@dp.message_handler(state=OperatorState.address)
async def operator_address(message: types.Message, state: FSMContext):
    data = await state.get_data()
    region_id = data.get('region_id')
    if region_id is None:
        bot_id = data.get('bot_id')
        bot = await models.Bot.get_by_id(bot_id)
        city = bot.city
        city_state = bot.state
    else:
        region = await models.Town.get_by_id(region_id)
        city = region.name
        city_state = region.bot.state

    mk = types.InlineKeyboardMarkup()

    try:
        if global_config.bypass_geocoder:
            raise ForbiddenError('geocoder is disabled')
        address_data = await search_address(message.text, city, city_state)
    except ForbiddenError as e:
        if 'geocoder is disabled' not in str(e):
            global_config.bypass_geocoder = True
            await message.bot.send_message(
                MODERATOR_ID,
                text='Api ключ геокодера недействителен. \n'
                     'Геокодер отключен.\n'
                     'Адреса будут вводиться вручную, без координат'
            )
            logger.error(traceback.format_exc())

        msg_text = bt.FIND_ADDRESS_MSG.format(
            address=message.text
        )
        await state.update_data(address_full=message.text)
        mk.row(types.InlineKeyboardButton(bt.CONFIRM_BTN, callback_data='manual_confirm_address'))
    else:
        if address_data is None:
            address_list = []
            for i, address_dict in enumerate(message.text, start=1):
                address_list.append(f'{i}. {address_dict["street"]} д. {address_dict["housenumber"]}')
                mk.row(types.InlineKeyboardButton(f'Адрес {i}', callback_data=f'confirm_address:{i}'))

            msg_text = bt.FIND_MORE_ADDRESS_MSG.format(
                address_list='\n'.join(address_list)
            )
        else:
            lon = address_data[0]['lon']
            lat = address_data[0]['lat']
            address = f'{address_data[0]["street"]} {address_data[0]["housenumber"]}'
            await state.update_data(address_data=address_data)
            if len(address_data) == 1:
                msg_text = bt.FIND_ADDRESS_MSG.format(
                    address=f'<a href="https://yandex.ru/maps/?ll={lon},{lat}&z=12&text={lat},{lon}">{address}</a>'
                )
                mk.row(types.InlineKeyboardButton(bt.CONFIRM_BTN, callback_data='confirm_address:1'))
            else:
                address_list = []
                for i, address_dict in enumerate(address_data, start=1):
                    address_list.append(f'{i}. {address_dict["street"]} д. {address_dict["housenumber"]}')
                    mk.row(types.InlineKeyboardButton(f'Адрес {i}', callback_data=f'confirm_address:{i}'))

                msg_text = bt.FIND_MORE_ADDRESS_MSG.format(
                    address_list='\n'.join(address_list)
                )

    mk.row(types.InlineKeyboardButton(text=bt.ENTER_AGAIN_BTN, callback_data='operator_metro'))
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text=msg_text, reply_markup=mk, parse_mode='HTML', disable_web_page_preview=True)
    await OperatorState.next()


@dp.callback_query_handler(text='manual_confirm_address', state=OperatorState.choice_address)
async def confirm_address(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    address_full = data.get('address_full')
    await state.update_data(
        address_street=address_full,
        address_number='0',
        address_lat=0,
        address_lon=0
    )
    await call.message.edit_reply_markup()
    message = call.message
    await message.answer(
        text=bt.OPERATOR_CHOICE_ADDRESS_MSG.format(address=address_full),
        disable_web_page_preview=True)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text=bt.OPERATOR_SEND_COMMENT_MSG, reply_markup=mk)
    await OperatorState.next()


@dp.callback_query_handler(Text(startswith='confirm_address:'), state=OperatorState.choice_address)
async def confirm_address(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index_address = int(call.data.split(':')[1]) - 1
    address_data = data.get('address_data')

    address_dict = address_data[index_address]
    address = f'{address_dict["street"]} д. {address_dict["housenumber"]}'
    await state.update_data(address_street=address_dict["street"],
                            address_number=address_dict["housenumber"],
                            address_lat=address_dict['lat'],
                            address_lon=address_dict['lon'])
    lat, lon = address_dict['lat'], address_dict['lon']
    await call.message.edit_reply_markup()
    message = call.message
    await message.answer(text=bt.OPERATOR_CHOICE_ADDRESS_MSG.format(
        address=
        f'<a href = "https://yandex.ru/maps/?ll={lon},{lat}&z=12&text={lat},{lon}" > {address} </a>'),
        disable_web_page_preview=True)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text=bt.OPERATOR_SEND_COMMENT_MSG, reply_markup=mk)
    await OperatorState.next()


@dp.callback_query_handler(text='operator_description', state='*')
@dp.message_handler(state=OperatorState.description)
async def operator_description(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    if isinstance(message, types.Message):
        description = message.text
        await state.update_data(description=description)
    else:
        await message.message.edit_reply_markup()
        message = message.message

    mk.row(types.InlineKeyboardButton(text="Смена", callback_data="select_mode:shift"))
    mk.row(types.InlineKeyboardButton(text="Ставка", callback_data="select_mode:rate"))
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text="Выберите режим работы:", reply_markup=mk)
    await OperatorState.next()

@dp.callback_query_handler(Text(startswith='select_mode:'), state=OperatorState.mode_selection)
async def select_mode(call: types.CallbackQuery, state: FSMContext):
    mode = call.data.split(':')[1]
    await state.update_data(mode=mode)
    
    if mode == 'shift':
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
        await call.message.edit_text(text="Введите описание смены (например: 'Ночная смена 22:00-06:00, 5000 руб за смену')", reply_markup=mk)
        await OperatorState.shift_description.set()
    else:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
        await call.message.edit_text(text=bt.OPERATOR_SEND_PRICE_REGULAR_MSG, reply_markup=mk)
        await OperatorState.price_regular.set()

@dp.message_handler(state=OperatorState.shift_description)
async def operator_shift_description(message: types.Message, state: FSMContext):
    shift_description = message.text
    await state.update_data(
        shift_description=shift_description,
        price_regular="0",
        price_state="0",
        price_per_hour="0",
        min_time="0"
    )
    await operator_check_data(message, state)

@dp.callback_query_handler(text='operator_price_regular', state='*')
@dp.message_handler(state=OperatorState.price_regular)
async def operator_price_regular(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    if isinstance(message, types.Message):
        price_per_hour = message.text
        await state.update_data(price_regular=price_per_hour)
    else:
        await message.message.edit_reply_markup()
        message = message.message

    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text=bt.OPERATOR_SEND_PRICE_STATE_MSG, reply_markup=mk)
    await OperatorState.next()

@dp.callback_query_handler(text='operator_price_state', state='*')
@dp.message_handler(state=OperatorState.price_state)
async def operator_price_regular(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    if isinstance(message, types.Message):
        price_per_hour = message.text
        await state.update_data(price_state=price_per_hour)
    else:
        await message.message.edit_reply_markup()
        message = message.message

    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text=bt.OPERATOR_SEND_PRICE_HOUR_MSG, reply_markup=mk)
    await OperatorState.next()


@dp.callback_query_handler(text='operator_price_hour', state='*')
@dp.message_handler(state=OperatorState.price_per_hour)
async def operator_price_hour(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    if isinstance(message, types.Message):
        price_per_hour = message.text
        await state.update_data(price_per_hour=price_per_hour)
    else:
        await message.message.edit_reply_markup()
        message = message.message

    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await message.answer(text=bt.OPERATOR_SEND_MIN_TIME_MSG, reply_markup=mk)
    await OperatorState.next()


async def prepare_request_text(data: dict):
    region_id = data.get('region_id')
    if region_id is None:
        city_id = data.get('bot_id')
        city = (await models.Bot.get_by_id(city_id)).city
    else:
        city = (await models.Town.get_by_id(region_id)).name

    date = data.get('date')
    order_id = data.get('order_id')
    people_amount = data.get('people_amount')
    national = data.get('national')
    if national == 'yes':
        national = 'Да'
    elif national == 'no':
        national = 'Нет'
    else:
        national = 'Не важно'

    metro = data.get('metro')
    address_street = data.get('address_street')
    address_number = data.get('address_number')
    address_lat = data.get('address_lat')
    address_lon = data.get('address_lon')
    if address_number == '0' and address_lat == 0 and address_lon == 0:
        address = address_street
        manual_address: bool = True
    else:
        address = f'{address_street} д. {address_number}'
        manual_address: bool = False

    description = data.get('description')
    price_regular = data.get('price_regular')
    price_state = data.get('price_state')
    price_per_hour = data.get('price_per_hour')
    min_time = data.get('min_time')
    text = bt.REQUEST_CITY_MSG.format(city=city) + '\n'
    text += bt.REQUEST_ORDER_ID_MSG.format(order_id=order_id) + '\n'
    text += bt.REQUEST_DATE_MSG.format(date=date) + '\n'
    text += bt.REQUEST_PEOPLE_MSG.format(people=people_amount) + '\n'
    text += bt.REQUEST_NATIONAL_MSG.format(national=national) + '\n'
    if metro is not None:
        text += bt.REQUEST_METRO_MSG.format(metro=metro) + '\n'

    if manual_address:
        text += bt.REQUEST_MANUAL_ADDRESS_MSG.format(address=address) + '\n'
    else:
        text += bt.REQUEST_ADDRESS_MSG.format(address=address, lat=address_lat, lon=address_lon) + '\n'

    text += bt.REQUEST_COMMENT_MSG.format(comment=description) + '\n'

    if data.get('mode') == 'shift':
        text += f"Режим работы: Смена\n"
        text += f"Описание смены: {data.get('shift_description', 'Не указано')}\n"
    else:
        text += bt.REQUEST_PRICE_REGULAR_MSG.format(price_regular=price_regular) + '\n'
        text += bt.REQUEST_PRICE_STATE_MSG.format(price_state=price_state) + '\n'
        text += bt.REQUEST_PRICE_HOUR_MSG.format(price_hour=price_per_hour) + '\n'
        text += bt.REQUEST_MIN_TIME_MSG.format(min_time=min_time) + '\n'
    text += bt.REQUEST_STATUS_MSG.format(status='Открыт ✅') + '\n'
    return text


@dp.callback_query_handler(text='operator_check_data', state='*')
async def operator_check_data(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    data = await state.get_data()
    text = await prepare_request_text(data)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.CONFIRM_BTN, callback_data='operator_confirm'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_DATA_BTN, callback_data='operator_change_data'))
    await OperatorState.next()
    if isinstance(message, types.CallbackQuery):
        await message.message.edit_reply_markup()
        message = message.message

    await message.answer(text=text, reply_markup=mk, disable_web_page_preview=True)


@dp.message_handler(state=OperatorState.min_time)
async def operator_min_time(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    if isinstance(message, types.Message):
        min_time = message.text
        await state.update_data(min_time=min_time)

    await operator_check_data(message, state)


@dp.callback_query_handler(text='operator_change_data', state='*')
async def operator_change_data(call: types.CallbackQuery, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_ORDER_ID_BTN, callback_data='change_operator:order_id'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_DATE_BTN, callback_data='change_operator:date'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_PEOPLE_BTN, callback_data='change_operator:people'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_NATIONAL_BTN, callback_data='change_operator:national'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_METRO_BTN, callback_data='change_operator:metro'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_ADDRESS_BTN, callback_data='change_operator:address'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_COMMENT_BTN, callback_data='change_operator:comment'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_PRICE_REGULAR_BTN, callback_data='change_operator:price_regular'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_PRICE_STATE_BTN, callback_data='change_operator:price_state'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_PRICE_HOUR_BTN, callback_data='change_operator:price_hour'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_MIN_TIME_BTN, callback_data='change_operator:min_time'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='operator_check_data'))
    if call.message.text != bt.OPERATOR_SELECT_CITY_MSG or call.message.reply_markup != mk:
        try:
            await call.message.edit_reply_markup(mk)
        except Exception as e:
            logger.error(f'Ошибка {e}')
    await OperatorState.change_data.set()


@dp.callback_query_handler(Text(startswith='change_operator:'), state=OperatorState.change_data)
async def change_operator_data(call: types.CallbackQuery, state: FSMContext):
    param = call.data.split(':')[1]
    mk = types.InlineKeyboardMarkup()
    if param == 'date':
        msg_text = bt.OPERATOR_SEND_DATE_MSG
    elif param == 'order_id':
        msg_text = bt.OPERATOR_SEND_ORDER_ID_MSG
    elif param == 'people':
        msg_text = bt.OPERATOR_SEND_PEOPLE_MSG
    elif param == 'metro':
        msg_text = bt.OPERATOR_SEND_METRO_MSG
        mk.row(types.InlineKeyboardButton(text=bt.SKIP_BTN, callback_data='skip_metro'))
    elif param == 'address':
        msg_text = bt.OPERATOR_SEND_ADDRESS_MSG
    elif param == 'comment':
        msg_text = bt.OPERATOR_SEND_COMMENT_MSG
    elif param == 'price_regular':
        msg_text = bt.OPERATOR_SEND_PRICE_REGULAR_MSG
    elif param == 'price_state':
        msg_text = bt.OPERATOR_SEND_PRICE_STATE_MSG
    elif param == 'price_hour':
        msg_text = bt.OPERATOR_SEND_PRICE_HOUR_MSG
    elif param == 'min_time':
        msg_text = bt.OPERATOR_SEND_MIN_TIME_MSG
    elif param == 'national':
        msg_text = bt.OPERATOR_CHOICE_NATIONALITY_MSG
        mk.row(types.InlineKeyboardButton(text=bt.RUSSIAN_BTN, callback_data='change_operator_national:yes'))
       #mk.row(types.InlineKeyboardButton(text=bt.NOT_RUSSIAN_BTN, callback_data='change_operator_national:no'))
        mk.row(types.InlineKeyboardButton(text=bt.EVERY_ONE_BTN, callback_data='change_operator_national:every'))

    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='operator_check_data'))
    await state.update_data(param=param)
    await call.message.edit_text(text=msg_text, reply_markup=mk)
    await OperatorState.in_process_change_data.set()


@dp.callback_query_handler(Text(startswith='change_operator_national:'), state=OperatorState.in_process_change_data)
async def change_operator_national(call: types.CallbackQuery, state: FSMContext):
    national = call.data.split(':')[1]
    await state.update_data(national=national)
    await call.message.answer(text=bt.CHANGE_DATA_SUCCESS_MSG)
    await operator_check_data(call, state)


@dp.message_handler(state=OperatorState.in_process_change_data)
async def operator_change_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    param = data.get('param')
    if param == 'date':
        await state.update_data(date=message.text)
    elif param == 'order_id':
        await state.update_data(order_id=message.text)
    elif param == 'people':
        await state.update_data(people_amount=message.text)
    elif param == 'metro':
        await state.update_data(metro=message.text)
    elif param == 'address':
        if ',' in message.text:
            address_street, address_number = message.text.split(",")[0], message.text.split(",")[1]
        else:
            address_street, address_number = message.text.split(" ")[0], message.text.split(" ")[-1]
        msg_text = bt.FIND_ADDRESS_MSG.format(
            address=f'{address_street} {address_number}'
        )
        await message.answer(text=msg_text)
        await state.update_data(address_street=address_street, address_number=address_number,
                                address_lon=1, address_lat=1)
    elif param == 'comment':
        await state.update_data(description=message.text)
    elif param == 'price_regular':
        await state.update_data(price_regular=message.text)
    elif param == 'price_state':
        await state.update_data(price_state=message.text)
    elif param == 'price_hour':
        await state.update_data(price_per_hour=message.text)
    elif param == 'min_time':
        await state.update_data(min_time=message.text)
    else:
        return

    await message.answer(text=bt.CHANGE_DATA_SUCCESS_MSG)
    await operator_check_data(message, state)


@dp.callback_query_handler(text='operator_confirm', state='*')
@dp.async_task
async def operator_confirm(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await call.message.edit_reply_markup()
    load_msg = await call.message.answer(text=bt.SENDING_MSG)
    msg_text = await prepare_request_text(data)
    region_id = data.get('region_id')
    user = await models.User.get_user(call.from_user.id)
    operator = await models.Operator.get_operator(user=user)
    
    if region_id:
        town = await models.Town.get_by_id(region_id)
        bot_token = town.bot.token
        city = await models.Bot.get_by_id(town.bot.id)
        implementers = list(town.implementers) + list(city.implementers)
    else:
        city_id = data.get('bot_id')
        city = await models.Bot.get_by_id(city_id)
        bot_token = city.token
        implementers = city.implementers

    request_data = {
        "town_id": town.id if region_id else None,
        "city_id": city.id if not region_id else None,
        "date": data.get('date'),
        "order_id": data.get('order_id'),
        "people": data.get('people_amount'),
        "national": data.get('national'),
        "metro": data.get('metro'),
        "address_number": data.get('address_number'),
        "address_street": data.get('address_street'),
        "address_lat": data.get('address_lat'),
        "address_lon": data.get('address_lon'),
        "comment": data.get('description'),
        "operator": operator
    }

    if data.get('mode') == 'shift':
        request_data.update({
            "price_regular": "0",
            "price_state": "0",
            "price_hour": "0",
            "min_time": "0",
            "shift_description": data.get('shift_description')
        })
    else:
        request_data.update({
            "price_regular": data.get('price_regular'),
            "price_state": data.get('price_state'),
            "price_hour": data.get('price_per_hour'),
            "min_time": data.get('min_time'),
            "shift_description": None
        })

    request = await models.Request.add_request(**request_data)

    if request is None:
        await call.message.answer(text='Слишком большой текст, невозможно отправить')
        return

    logger.info(f"Запрос {request.order_id} успешно создан.")

    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.MAIN_MENU_BTN, callback_data='start'))
    await load_msg.edit_text(
        text=bt.OPEN_REQUEST_START_MESSAGING.format(order_id=request.order_id),
        reply_markup=mk
    )

    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.TAKE_REQUEST_BTN, callback_data=f'take_request:{request.id}'))
    temp_bot = Bot(token=bot_token, parse_mode='HTML')
    filtered_implementers = []
    if request.national is None:
          for implementer in implementers:
            if not implementer.user.is_blocked: 
                filtered_implementers.append(implementer)
    elif request.national == 'yes':
        for implementer in implementers:
            if not implementer.user.is_blocked: 
                if implementer.nationality:
                    filtered_implementers.append(implementer)
    elif request.national == 'no':
        for implementer in implementers:
            if not implementer.user.is_blocked: 
                if not implementer.nationality:
                    filtered_implementers.append(implementer)
    try:
        sorted_implementers = sorted(filtered_implementers, key=lambda x: (x.priority_group == 0, x.priority_group))
        logger.debug(f'Отсортированный список {sorted_implementers} заказа номер {request.id}')
    except Exception as e:
        logger.error(f'Ошибка при сортировке {str(e)}')
    
    blocked_list = []
    counter = SenderCounter()
    coros: list[list[Coroutine]] = [[]]
    logger.info(f"Начало отправки сообщений исполнителям: {len(sorted_implementers)} исполнителей.")
    for i, implementer in enumerate(sorted_implementers):
        async def send(user_id: str):
            try:
                await temp_bot.send_message(
                    chat_id=user_id,
                    text=msg_text,
                    reply_markup=mk,
                    disable_web_page_preview=True
                )
                # logger.debug(f"Отправлено сообщение исполнителю {user_id}. Сообщение {counter.count}.")
                #print(f'sending num{counter.count}')
                counter.count += 1
                
            except Exception as e:
                if str(e) == "Forbidden: bot was blocked by the user":
                    blocked_list.append(user_id) 
                    # try:
                    #     UserToBan = await models.User.get_user(int(user_id))
                    #     logger.info(f"Получен пользователь для блокировки {UserToBan}")
                    #     UserToBan.is_blocked = True
                    #     UserToBan.block_reason = "BotBlocked"
                    #     await UserToBan.save()
                    #     logger.info(f"Пользователь заблокирован {user_id}: {str(e)}")
                    # except Exception as f:
                    #     logger.info(f'Что то не так {str(f)}')
                        
                else: 
                    pass
                    #logger.error(f"Ошибка при отправке сообщения исполнителю {user_id}: {str(e)}")
                

        coros[-1].append(send(implementer.user.telegram_id))
        if len(coros[-1]) == 30:
           coros.append([])
           continue

    if not coros[-1]:
        coros.pop(-1)

    await sending_manager.send_main(bot_token, coros)
    # temp_bot_session = await temp_bot.get_session()
    # await temp_bot_session.close()
    logger.info(f"Все сообщения успешно отправлены. Всего сообщений: {counter.count} для заказа {request.order_id} .")
    async def block_by_id(user_id: int):
        try:
            user = await models.User.get_user(user_id)
            user.is_blocked = True
            user.block_reason = 'BotBlocked'
            await user.save()
            logger.info(f"Пользователь заблокирован {user_id}")
        except Exception as f:
            logger.error(f'Ошибка при блокировке пользователя {str(f)}')

    for i in blocked_list:
        await block_by_id(int(i))  
    msg_text += '\n' + f'Логист заказа: @{request.operator.user.username}'
    temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')
    
    await temp_bot.send_message(chat_id=REQUESTS_ID,
                text=msg_text,
                disable_web_page_preview=True)
    
    msg_text += '\n' + 'Присылайте сразу фото паспорта и номер телефона в личные сообщения'
    try:
        if city.city in CHAT_IDS:
            response = await temp_bot.send_message(chat_id=CHAT_IDS.get(city.city),
                text=msg_text,
                disable_web_page_preview=True)
            try:
                chat_messages = await ChatMessages.create(request=request.id)
                await add_message(chat_messages, response.chat.id, response.message_id)
            except Exception as e:
                logger.error(f'Ошибка ChatMessages {e}')
            if city == 'Москва':
                response = await temp_bot.send_message(chat_id=CHAT_IDS.get("Москва_2"),
                text=msg_text,
                disable_web_page_preview=True)
                await add_message(chat_messages, response.chat.id, response.message_id)
            if city == 'Санкт-Петербург': 
                response = await temp_bot.send_message(chat_id=CHAT_IDS.get("Санкт-Петербург_2"),
                text=msg_text,
                disable_web_page_preview=True)
                await add_message(chat_messages, response.chat.id, response.message_id)
    except Exception as e:
        logger.error(f'Ошибка при отправке в чаты {e}')

    await call.message.answer(text=bt.OPEN_REQUESTS_MSG.format(
        count=counter.count, order_id=request.order_id
    ))


@dp.callback_query_handler(Text(startswith='operator_select_request:'), state='*')
async def admin_select_request_handler(call: types.CallbackQuery, state: FSMContext):
    implementer_request_id = int(call.data.split(':')[1])
    implementer_request = await models.ImplementerRequests.get_by_id(implementer_request_id)
    if implementer_request is None:
        await call.message.edit_text(text='Заявка не найдена')
        return

    request = await models.Request.get_by_id(implementer_request.request_id)
    if request is None:
        await call.message.edit_text(text='Заявка не найдена')
        return

    # if len(implementer_request.implementers_ids) > request.people - len(request.implementers):
    #     await call.message.answer(text='Количество пользователей в заявке превышает необходимое количество')
    #     return

    for implementer_id in implementer_request.implementers_ids:
        implementer = await models.Implementer.get_by_id(implementer_id)
        await request.implementers.add(implementer)
        request.operator.priority_stats[implementer.priority_group+9] += 1 
        logger.info(f'Добавлены принятые отклики приоритетной группы {implementer.priority_group}')
        await request.operator.save()

    #await implementer_request.delete()
    implementer_request.accepted = True
    await implementer_request.save()
    await call.message.edit_text(text=call.message.html_text + '\n\n' + '✅ Добавлены в заказ')


@dp.callback_query_handler(Text(startswith='operator_reject_request:'), state='*')
async def admin_reject_request_handler(call: types.CallbackQuery, state: FSMContext):
    implementer_request_id = int(call.data.split(':')[1])
    implementer_request = await models.ImplementerRequests.get_by_id(implementer_request_id)
    if implementer_request is None:
        await call.message.edit_text(text='Заявка не найдена')
        return

    await implementer_request.delete()
    await call.message.edit_text(text=call.message.html_text + '\n\n' + '❌ Отклонено')


@dp.callback_query_handler(text='my_requests', state='*')
async def operator_requests(call: types.CallbackQuery,state: FSMContext):
    #call_data = int(call.data.split(':')[1])
    #logger.info(call_data)
    await state.finish()
    user = await models.User.get_user(call.from_user.id)
    operator = await models.Operator.get_operator(user)
    requests = await models.Request.get_by_operator(operator)
    if len(requests) == 0:
        await call.answer(text='У вас нет заявок', show_alert=True)
        return
    msg_text, mk = await requests_info(requests, 1, 'all')
    await call.message.delete()
    await call.message.answer(text=msg_text, reply_markup=mk, disable_web_page_preview=True)

async def requests_info(requests: List[models.Request], page: int, request_type: str):
    request = requests[page - 1]
    mk = types.InlineKeyboardMarkup()
    if request.national is None:
        national = 'Не важно'
    elif request.national == 'yes':
        national = 'Да'
    else:
        national = 'Нет'

    msg_text = f'Заказ №{request.order_id}\n\n'
    if request.town_id:
        town = await models.Town.get_by_id(request.town_id)
        try:
            msg_text += bt.REQUEST_CITY_MSG.format(city=town.name) + '\n'
        except: 
            msg_text += bt.REQUEST_CITY_MSG.format(city=bt.REQUEST_DELETED_CITY) + '\n'
    else:
        try:
            city = await models.Bot.get_by_id(request.city_id)
            msg_text += bt.REQUEST_CITY_MSG.format(city=city.city) + '\n'
        except: 
            msg_text += bt.REQUEST_CITY_MSG.format(city=bt.REQUEST_DELETED_CITY) + '\n'

    msg_text += bt.REQUEST_DATE_MSG.format(date=request.date) + '\n'
    msg_text += bt.REQUEST_PEOPLE_MSG.format(people=request.people) + '\n'
    msg_text += bt.REQUEST_NATIONAL_MSG.format(national=national) + '\n'
    if request.metro:
        msg_text += bt.REQUEST_METRO_MSG.format(metro=request.metro) + '\n'

    if request.address_number == '0' and request.address_lat == 0 and request.address_lon == 0:
        address = request.address_street
        msg_text += bt.REQUEST_MANUAL_ADDRESS_MSG.format(address=address) + '\n'
    else:
        address = f'{request.address_street} д. {request.address_number}'
        msg_text += bt.REQUEST_ADDRESS_MSG.format(address=address, lat=request.address_lat,
                                                  lon=request.address_lon) + '\n'

    msg_text += bt.REQUEST_COMMENT_MSG.format(comment=request.comment) + '\n'
    msg_text += bt.REQUEST_PRICE_REGULAR_MSG.format(price_regular=request.price_regular) + '\n'
    msg_text += bt.REQUEST_PRICE_STATE_MSG.format(price_state=request.price_state) + '\n'
    msg_text += bt.REQUEST_PRICE_HOUR_MSG.format(price_hour=request.price_hour) + '\n'
    msg_text += bt.REQUEST_MIN_TIME_MSG.format(min_time=request.min_time) + '\n'
    mk.row(types.InlineKeyboardButton(text=bt.IMPLEMENTERS_BTN, callback_data=f'request_implementers:{request.id}'))
    if request.is_completed is True and request.is_canceled is False:
        status = 'Завершен ✅'
    elif request.is_active is True and request.is_completed is False:
        status = 'Открыт ✅'
        mk.row(types.InlineKeyboardButton(text=bt.CLOSE_BTN, callback_data=requests_cd.new(page=page,
                                                                                           direction='switch',
                                                                                           type=request_type)))
        # if not request.is_completed and request.is_canceled is False:
        #     mk.row(types.InlineKeyboardButton(text='Выполнен', callback_data=f'complete_request:{request.id}'))
    elif request.is_active is False and request.is_completed is False:
        status = 'Закрыт 🔒'
        mk.row(types.InlineKeyboardButton(text='Перевыложить', callback_data=requests_cd.new(page=page,
                                                                                          direction='switch',
                                                                                          type=request_type)))
        mk.row(types.InlineKeyboardButton(text='Завершен', callback_data=f'complete_request:{request.id}'))                                                                
    else:
        status = 'Отменен ❌'

    mk.row(types.InlineKeyboardButton(text=bt.FILTER_BTN, callback_data='filter_requests'))
    msg_text += bt.REQUEST_STATUS_MSG.format(status=status)
    if len(requests) > 1:
        mk.row(
            types.InlineKeyboardButton(text=bt.PREV_BTN, callback_data=requests_cd.new(page=page, direction='prev',
                                                                                       type=request_type))
        )
    mk.insert(
        types.InlineKeyboardButton(text=f'{page}/{len(requests)}', callback_data='empty')

    )

    mk.insert(
        types.InlineKeyboardButton(text=bt.NEXT_BTN, callback_data=requests_cd.new(page=page, direction='next',
                                                                                   type=request_type))
    )
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='start'))
    mk.row(types.InlineKeyboardButton(text=bt.COMPLETE_WITHOUT_IMP, callback_data='complete_all'))
    return msg_text, mk


@dp.callback_query_handler(text='filter_requests', state='*')
async def filter_requests(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.SEARCH_BY_NUMBER_BTN, callback_data='search_by_number'))
    mk.row(types.InlineKeyboardButton(text=bt.ACTIVE_REQUESTS_BTN, callback_data='active_requests'))
    mk.row(types.InlineKeyboardButton(text=bt.CLOSE_REQUESTS_BTN, callback_data='close_requests'))
    mk.row(types.InlineKeyboardButton(text=bt.COMPLETED_REQUESTS_BTN, callback_data='completed_requests'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
    await call.message.edit_text(text=bt.FILTER_REQUESTS_MSG, reply_markup=mk)
    await state.set_state('filter_requests')


@dp.callback_query_handler(text='active_requests', state='filter_requests')
async def active_requests(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    user = await models.User.get_user(call.from_user.id)
    operator = await models.Operator.get_operator(user)
    requests = await models.Request.get_by_operator(operator, True, False)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='filter_requests'))
    if len(requests) == 0:
        await call.message.edit_text(text='У вас нет активных заявок')
        return

    msg_text, mk = await requests_info(requests, 1, 'active')
    await call.message.edit_text(text=msg_text, reply_markup=mk, disable_web_page_preview=True)


@dp.callback_query_handler(text='close_requests', state='filter_requests')
async def close_requests(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    user = await models.User.get_user(call.from_user.id)
    operator = await models.Operator.get_operator(user)
    requests = await models.Request.get_by_operator(operator, False, False)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='filter_requests'))
    if len(requests) == 0:
        await call.message.edit_text(text='У вас нет закрытых заявок')
        return

    msg_text, mk = await requests_info(requests, 1, 'close')
    await call.message.edit_text(text=msg_text, reply_markup=mk, disable_web_page_preview=True)


@dp.callback_query_handler(text='completed_requests', state='filter_requests')
async def completed_requests(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    user = await models.User.get_user(call.from_user.id)
    operator = await models.Operator.get_operator(user)
    requests = await models.Request.get_by_operator(operator, True, True)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='filter_requests'))
    if len(requests) == 0:
        await call.message.edit_text(text='У вас нет завершенных заявок')
        return

    msg_text, mk = await requests_info(requests, 1, 'completed')
    await call.message.edit_text(text=msg_text, reply_markup=mk, disable_web_page_preview=True)

@dp.callback_query_handler(text='complete_all', state='*')
async def complete_all(call: types.CallbackQuery, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.YES_BTN, callback_data='complete_all_finish'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='start'))
    await call.message.answer(text=bt.CONFIRM_COMPLETE, reply_markup=mk)

@dp.callback_query_handler(text='complete_all_finish', state='*')
async def complete_all_finish(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    await call.message.edit_text(text=bt.COMPLETION_MSG)
    user = await models.User.get_user(call.from_user.id)
    operator = await models.Operator.get_operator(user)
    requests = await models.Request.get_by_operator(operator, False, False)
    count = 0

    for request in requests:
        if not request.implementers:
            count+=1
            if not request.is_active:
                operator.seal_count -= 1
            request.is_completed = True
            request.is_active = False
            await request.save()
    await operator.save()
    await call.message.edit_text(text=f'Завершено {count} заказов без исполнителей')
    


@dp.callback_query_handler(text='search_by_number', state='*')
async def search_by_number(call: types.CallbackQuery, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
    await call.message.edit_text(text=bt.SEARCH_BY_NUMBER_MSG, reply_markup=mk)
    await state.set_state('enter_request_number')


@dp.message_handler(state='enter_request_number')
async def enter_request_number(message: types.Message, state: FSMContext):
    order_id = message.text
    requests = await models.Request.get_by_order_id(order_id)
    if len(requests) == 0:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
        await message.answer(text='Заявка с данным номером не найдена', reply_markup=mk)
        return

    await state.finish()
    await state.update_data(current_requests=[requests[0]])
    msg_text, mk = await requests_info([requests[0]], 1, 'current')
    await message.answer(text=msg_text, reply_markup=mk, disable_web_page_preview=True)


@dp.callback_query_handler(text='empty')
async def empty(call: types.CallbackQuery, state: FSMContext):
    await call.answer(cache_time=60)


async def send_request_to_implementers(request: models.Request):
    region_id = request.town_id
    if region_id is None:
        city_id = request.city_id
        city = await models.Bot.get_by_id(city_id)
        bot_token = city.token
        implementers = city.implementers
        city = city.city
    else:
        town = await models.Town.get_by_id(region_id)
        bot_token = town.bot.token
        city = await models.Bot.get_by_id(town.bot.id)
        implementers = list(town.implementers) + list(city.implementers)
        city = town.name
        
    logger.info(f"Запрос {request.order_id} успешно изменен.")
    filtered_implementers = []
    if request.national is None:
        for implementer in implementers:
            if not implementer.user.is_blocked: 
                filtered_implementers.append(implementer)
    elif request.national == 'yes':
        for implementer in implementers:
            if not implementer.user.is_blocked: 
                if implementer.nationality:
                    filtered_implementers.append(implementer)
    elif request.national == 'no':
        for implementer in implementers:
            if not implementer.user.is_blocked: 
                if not implementer.nationality:
                    filtered_implementers.append(implementer)

    date = request.date
    people_amount = request.people
    metro = request.metro
    description = request.comment
    order_id = request.order_id
    price_regular = request.price_regular
    price_state = request.price_state
    price_per_hour = request.price_hour
    min_time = request.min_time
    text = bt.REQUEST_CITY_MSG.format(city=city) + '\n'
    text += bt.REQUEST_ORDER_ID_MSG.format(order_id=order_id) + '\n'
    text += bt.REQUEST_DATE_MSG.format(date=date) + '\n'
    text += bt.REQUEST_PEOPLE_MSG.format(people=people_amount) + '\n'
    if metro is not None:
        text += bt.REQUEST_METRO_MSG.format(metro=metro) + '\n'

    if request.address_number == '0' and request.address_lat == 0 and request.address_lon == 0:
        address = request.address_street
        text += bt.REQUEST_MANUAL_ADDRESS_MSG.format(address=address) + '\n'
    else:
        address = f'{request.address_street} д. {request.address_number}'
        text += bt.REQUEST_ADDRESS_MSG.format(address=address, lat=request.address_lat,
                                              lon=request.address_lon) + '\n'

    text += bt.REQUEST_COMMENT_MSG.format(comment=description) + '\n'
    text += bt.REQUEST_PRICE_REGULAR_MSG.format(price_regular=price_regular) + '\n'
    text += bt.REQUEST_PRICE_STATE_MSG.format(price_state=price_state) + '\n'
    text += bt.REQUEST_PRICE_HOUR_MSG.format(price_hour=price_per_hour) + '\n'
    text += bt.REQUEST_MIN_TIME_MSG.format(min_time=min_time) + '\n'

    if request.is_completed is True and request.is_canceled is False:
        status = 'Завершен ✅'
    elif request.is_active is True and request.is_completed is False:
        status = 'Открыт снова ✅'
    elif request.is_active is False and request.is_completed is False:
        status = 'Закрыт 🔒'
    else:
        status = 'Отменен ❌'

    text += bt.REQUEST_STATUS_MSG.format(status=status)
    mk = types.InlineKeyboardMarkup()
    if request.is_active:
        mk.row(types.InlineKeyboardButton(text=bt.TAKE_REQUEST_BTN, callback_data=f'take_request:{request.id}'))
    temp_bot = Bot(token=bot_token, parse_mode='HTML')
    
    sorted_implementers = sorted(filtered_implementers, key=lambda x: (x.priority_group == 0, x.priority_group))
    #logger.debug(f'Отсортированный список {sorted_implementers} измененного заказа номер {request.id}')


    blocked_list = []
    counter = SenderCounter()
    coros: list[list[Coroutine]] = [[]]
    logger.info(f"Начало отправки сообщений исполнителям: {len(sorted_implementers)} исполнителей.")
    for i, implementer in enumerate(sorted_implementers):
        async def send(user_id: str):
            try:
                await temp_bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=mk,
                    disable_web_page_preview=True
                )
                # logger.debug(f"Отправлено сообщение исполнителю {user_id}. Сообщение {counter.count}.")
                #print(f'sending num{counter.count}')
                counter.count += 1
                
            except Exception as e:
                if str(e) == "Forbidden: bot was blocked by the user":
                    blocked_list.append(user_id) 
                else: 
                    pass
                    #logger.error(f"Ошибка при отправке сообщения исполнителю {user_id}: {str(e)}")
                

        coros[-1].append(send(implementer.user.telegram_id))
        if len(coros[-1]) == 30:
           coros.append([])
           continue

    if not coros[-1]:
        coros.pop(-1)

    await sending_manager.send_main(bot_token, coros)
    # temp_bot_session = await temp_bot.get_session()
    # await temp_bot_session.close()
    logger.info(f"Все сообщения успешно отправлены. Всего сообщений: {counter.count} для измененного заказа {request.order_id} .")
    return counter.count


@dp.callback_query_handler(requests_cd.filter())
async def operator_requests_handler(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    page = int(callback_data['page'])
    direction = callback_data['direction']
    request_type = callback_data['type']
    user = await models.User.get_user(call.from_user.id)
    operator = await models.Operator.get_operator(user)
    if request_type == 'all':
        requests = await models.Request.get_by_operator(operator)
        await state.update_data(current_requests=requests)
    elif request_type == 'current':
        data = await state.get_data()
        requests = data.get('current_requests')
    elif request_type == 'completed':
         requests = await models.Request.get_by_operator(operator, False, True)
         await state.update_data(current_requests=requests)
    elif request_type == 'active':
        requests = await models.Request.get_by_operator(operator, True, False)
        await state.update_data(current_requests=requests)
    elif request_type == 'close':
        requests = await models.Request.get_by_operator(operator, False, False)
        await state.update_data(current_requests=requests)
    request_type = 'current'
    if direction == 'prev':
        page -= 1
    elif direction == 'next':
        page += 1
    elif direction == 'switch':
        request = requests[page - 1]
        await request.refresh_from_db()
        if request.is_active:
            request.is_active = False
            operator.seal_count += 1
            logger.info (f'Оператор закрыл заказ его счет {operator.seal_count}')
            #await check_for_seal(operator)
            await operator.save()
            load_msg_text = bt.CLOSE_REQUESTS_MSG
        elif request.is_completed:
            await call.message.answer(f'Заявка {request.order_id} уже завершена')
            return
        else:
            request.is_active = True
            load_msg_text = bt.OPEN_AGAIN_REQUESTS_MSG
            operator.seal_count += -1
            await operator.save()
            #await check_for_seal(operator)

        await request.save()
        # await request.refresh_from_db(fields=['is_active'])
        msg_text, mk = await requests_info(requests, page, request_type)
        await call.message.edit_text(text=msg_text, reply_markup=mk, disable_web_page_preview=True)

        load_msg = await call.message.answer(text=bt.SENDING_MSG_2)
        implementers_count = await send_request_to_implementers(request)
        await load_msg.edit_text(text=load_msg_text.format(count=implementers_count, order_id=request.order_id))

        chat_messages = await ChatMessages.get_or_none(request=request.id)
        temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')
        if chat_messages and chat_messages.message_ids:
            if request.is_active:
                msg_text += f'\nЛогист заказа: @{request.operator.user.username}'
                msg_text += '\n' + 'Присылайте сразу фото паспорта и номер телефона в личные сообщения'
            else:
                msg_text += '\nЗаказ закрыт, всем спасибо 🤝'
            for msg in chat_messages.message_ids:
                chat_id = msg["chat_id"]
                message_id = msg["message_id"]

                await temp_bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=msg_text
                )
        else:
            logger.error('Сообщения не найдены')
              

    if page < 1:
        page = len(requests)
    elif page > len(requests):
        page = 1

    msg_text, mk = await requests_info(requests, page, request_type)
    await call.message.edit_text(text=msg_text, reply_markup=mk, disable_web_page_preview=True)


mk = types.InlineKeyboardMarkup()


@dp.callback_query_handler(Text(startswith='request_implementers:'))
async def request_implementers(call: types.CallbackQuery, state: FSMContext):
    request_id = int(call.data.split(':')[1])
    request = await models.Request.get_by_id(request_id)
    implementers = request.implementers
    msg_text = f'Заказ №{request.order_id}\n\n'
    for implementer in implementers:
        msg_text += f'Исполнитель: {implementer.full_name}\n'
        msg_text += f'Дата рождения: {implementer.date_birth.strftime("%d.%m.%Y")}\n'
        msg_text += f'Телефон: {implementer.phone_number}\n'
        msg_text += f'Гражданство РФ: {implementer.national}\n'
        msg_text += f'Telegram: @{implementer.user.username}\n'
        msg_text += 'Статус самозанятости: {inn}'.format(inn='Нет' if not implementer.inn else 'Да') + '\n'
        msg_text += 'Статус подтвержденного паспорта: {passport}'.format(
            passport='нет' if not implementer.passport else implementer.passport
        ) + '\n'
        msg_text += f'Пометка: {implementer.mark}\n'
        msg_text += f'Рейтинг: {implementer.rating}\n'
        msg_text += f'Успешных заказов: <code>{implementer.success_requests}</code>\n'
        msg_text += f'Сорванных заказов: <code>{implementer.fail_requests}</code>\n\n'

    mk = types.InlineKeyboardMarkup()
    if not request.is_completed:
        #mk.row(types.InlineKeyboardButton(text='Выполнен', callback_data=f'complete_request:{request.id}'))
        mk.row(types.InlineKeyboardButton(text='Удалить исполнителя', callback_data=f'delete_imp:{request_id}'))
        mk.row(types.InlineKeyboardButton(text='Добавить исполнителя', callback_data=f'add_imp:{request_id}'))
 
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
    await call.message.edit_text(text=msg_text, reply_markup=mk)

@dp.callback_query_handler(Text(startswith='add_imp:'), state='*')
async def add_imp(call: types.CallbackQuery, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
    await call.message.answer(f'Введите Username исполнителя', reply_markup=mk)
    await state.set_state('add_imp')
    await state.update_data(request=call.data.split(':')[1])


@dp.message_handler(state='add_imp')
async def add_imp_get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()

    username = message.text.replace('@', '')
    user = await models.User.get_by_username(username)
    implementer = await models.Implementer.get_implementer(user)

    if implementer is None:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
        await message.answer('Пользователь не найден', reply_markup=mk)
        return

    order_id = int(data['request'])
    order = await models.Request.get_by_id(order_id)

    if order is None:
        return

    await order.implementers.add(implementer)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data=f'start'))
    implementer.priority_group = await get_priority_group(implementer.id)
    await implementer.save()
    order.operator.priority_stats[implementer.priority_group] += 1 
    order.operator.priority_stats[implementer.priority_group+9] += 1 
    await order.operator.save()
    await message.answer('Исполнитель добавлен в заказ', reply_markup=mk)  # Удалить
    await state.finish()


@dp.callback_query_handler(Text(startswith='delete_imp:'), state='*')
async def delete_imp(call: types.CallbackQuery, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
    await call.message.answer(f'Введите Username исполнителя', reply_markup=mk)
    await state.set_state('delete_imp')
    await state.update_data(request=call.data.split(':')[1])


@dp.message_handler(state='delete_imp')
async def delete_imp_get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()

    username = message.text.replace('@', '')
    user = await models.User.get_by_username(username)
    implementer = await models.Implementer.get_implementer(user)

    if implementer is None:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
        await message.answer('Пользователь не найден', reply_markup=mk)
        return

    order_id = int(data['request'])
    order = await models.Request.get_by_id(order_id)
    await order.implementers.remove(implementer)

    if order is None:
        return

    await order.implementers.remove(implementer)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data=f'start'))
    await message.answer('Исполнитель удалён с заказа', reply_markup=mk)  # Удалить
    await state.finish()


@dp.callback_query_handler(Text(startswith='complete_request:'), state='*')
async def complete_request(call: types.CallbackQuery, state: FSMContext):
    print('workk')
    request_id = int(call.data.split(':')[1])
    request = await models.Request.get_by_id(request_id)
    implementers = request.implementers
    logger.info(f'Начало закрытия заказа оператором {request.operator.user.username}')
    if request.is_completed:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text='Ок', callback_data='done'))
        call.message.answer(text='Заказ уже завершен',reply_markup=mk)
        return
    if len(implementers) == 0:
        mk = types.InlineKeyboardMarkup()
        request.is_completed = True
        request.is_active = False
        #logger.info('заказ завершен')
        request.operator.seal_count += -1
        #operator = await models.Operator.get_by_id(request.operator.id)
        await request.save()
        await request.operator.save()
        #await check_for_seal(operator)
        mk.row(types.InlineKeyboardButton(text='Ок', callback_data='done'))
        await call.message.answer(text=f'Заказ №{request.order_id} завершен',
                                     reply_markup=mk)
        logger.info(f'Заказ завершен без исполнителей оператором {request.operator.user.username}')
        return

    implementer = implementers[0]
    msg_text = f'Исполнитель: {implementer.full_name}\n'
    msg_text += f'Дата рождения: {implementer.date_birth.strftime("%d.%m.%Y")}\n'
    msg_text += f'Телефон: {implementer.phone_number}\n'
    msg_text += f'Пометка: {implementer.mark}\n'
    msg_text += f'Рейтинг: {implementer.rating}\n'
    msg_text += f'Telegram: @{implementer.user.username}\n\n'
    msg_text += 'Оцените работу исполнителя'
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Справился', callback_data=f'complete_implementer:{request_id}:0:success'))
    mk.insert(
        types.InlineKeyboardButton(text='Не справился', callback_data=f'complete_implementer:{request_id}:0:fail'))
    mk.row(types.InlineKeyboardButton(text='Нейтрально', callback_data=f'complete_implementer:{request_id}:0:neutral'))
    mk.row(types.InlineKeyboardButton(text='Справился с нареканиями', callback_data=f'complete_implementer:{request_id}:0:good'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
    await call.message.answer(msg_text, reply_markup=mk)
    await state.finish()


@dp.callback_query_handler(Text(startswith='complete_implementer:'))
@dp.async_task
async def complete_implementer(call: types.CallbackQuery, state: FSMContext):
    request_id = int(call.data.split(':')[1])
    implementer_index = int(call.data.split(':')[2])
    result = call.data.split(':')[3]
    request = await models.Request.get_by_id(request_id)
    implementers = request.implementers
    implementer = implementers[implementer_index]
    if result == 'success':
        try:
            implementer.success_requests += 1
            implementer.rating += 2
            await implementer.save()
            await check_rating(implementer)
        except Exception as e:
            logger.error(f'Ошибка при установке рейтинга {e}')
    elif result == 'fail':
        implementer.fail_requests += 1
        implementer.rating += -2
        await check_rating(implementer)
        await implementer.save()
    elif result == 'good':
        implementer.rating += 1 
        await implementer.save()
    elif result == 'neutral':
        await implementer.save()
    if implementer_index == len(implementers) - 1:
        request.is_completed = True
        request.is_active = False
        request.operator.seal_count += -1
        #operator = await models.Operator.get_by_id(request.operator.id)
        #await check_for_seal(operator)
        await request.save()
        await request.operator.save()

        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text='Ок', callback_data='done'))
        await call.message.edit_text(text=f'Спасибо за оценку! Заказ №{request.order_id} завершен',
                                     reply_markup=mk)
        logger.info(f'Заказ завершен оператором {request.operator.user.username}')

        # await send_request_to_implementers(request)
    else:
        implementer = implementers[implementer_index + 1]
        msg_text = f'Исполнитель: {implementer.full_name}\n'
        msg_text += f'Дата рождения: {implementer.date_birth.strftime("%d.%m.%Y")}\n'
        msg_text += f'Телефон: {implementer.phone_number}\n'
        msg_text += f'Пометка: {implementer.mark}\n'
        msg_text += f'Рейтинг: {implementer.rating}\n'
        msg_text += f'Telegram: @{implementer.user.username}\n\n'
        msg_text += 'Оцените работу исполнителя'
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text='Справился',
                                          callback_data=f'complete_implementer:{request_id}:{implementer_index + 1}:success'))
        mk.insert(types.InlineKeyboardButton(text='Не справился',
                                             callback_data=f'complete_implementer:{request_id}:{implementer_index + 1}:fail'))
        mk.row(types.InlineKeyboardButton(text='Нейтрально',
                                          callback_data=f'complete_implementer:{request_id}:{implementer_index + 1}:neutral')
                                          )
        mk.row(types.InlineKeyboardButton(text='Справился с нареканиями',
                                          callback_data=f'complete_implementer:{request_id}:{implementer_index + 1}:good'))
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='my_requests'))
        await call.message.edit_text(text=msg_text, reply_markup=mk)


@dp.message_handler(state='block_user')
async def block_user_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    edit_msg: bool = data['edit_msg']

    user = await models.User.get_user(data['user_id'])
    user.is_blocked = True
    user.block_reason = message.text
    await user.save()

    block_msg: str = f'Пользователь {user.username} заблокирован\nПричина блокировки:\n{message.text}'

    if edit_msg:
        photo: bool = data['photo']
        message_text: str = data['message_text'].replace('Причина блокировки?', block_msg)

        message_id: int = data['message_id']
        if photo:
            await message.bot.edit_message_caption(
                chat_id=message.chat.id, message_id=message_id,
                caption=message_text
            )
        else:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=message_id,
                text=message_text
            )
    else:
        await message.answer(block_msg)
    operator = await models.User.get_user(message.from_user.id)
    block_msg += f'\n оператором @{operator.username}'
    await message.bot.send_message(dependencies.SUPPORT_ID, block_msg)
    await message.bot.send_message(dependencies.MODERATOR_ID, block_msg)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Подтвердить блокировку', callback_data=f'accept_block:{user.telegram_id}'))
    mk.row(types.InlineKeyboardButton(text='Отклонить блокировку', callback_data=f'decline_block:{user.telegram_id}'))
    await message.bot.send_message(text=block_msg, chat_id=dependencies.TICKETS_ID, reply_markup=mk)
    await state.reset_state()


@dp.callback_query_handler(Text(startswith='block_user:'), state='*')
async def block_user(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split(':')[1])
    user = await models.User.get_user(user_id)
    await state.set_state('block_user')
    if call.message.photo:
        photo = True
        msg_text = (
            await call.message.edit_caption(caption=call.message.html_text + f'\n\nПричина блокировки?')).caption
    else:
        photo = False
        msg_text = (await call.message.edit_text(text=call.message.html_text + f'\n\nПричина блокировки?')).text

    await state.update_data({'user_id': user_id, 'edit_msg': True, 'message_text': msg_text, 'photo': photo,
                             'message_id': call.message.message_id})
    await call.answer()

@dp.callback_query_handler(Text(startswith='decline_block:'), state='*')
async def decline_block_user(call: types.CallbackQuery, state: FSMContext):
    try:
        user_id = int(call.data.split(':')[1])
        user = await models.User.get_user(user_id)
        user.is_blocked=False
        await user.save()
        await call.message.edit_text(f'Пользователь @{user.username} разблокирован')
        block_msg = (f'Пользователь @{user.username} разблокирован')
        await call.bot.send_message(dependencies.MODERATOR_ID, block_msg)
    except Exception as e:
        logger.info(f'ошибка при блокировке {e}')

@dp.callback_query_handler(Text(startswith='accept_block:'), state='*')
async def accept_block_user(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split(':')[1])
    user = await models.User.get_user(user_id)
    user.is_blocked=True
    await user.save()
    await call.message.edit_text(f'Пользователь @{user.username} заблокирован')
    block_msg = f'Пользователь @{user.username} заблокирован'
    await call.bot.send_message(dependencies.MODERATOR_ID, block_msg)


@dp.message_handler(commands=['block', 'unblock'], state='*')
async def block_user_(message: types.Message, state: FSMContext):
    user = await models.User.get_user(message.from_user.id)
    operator = await models.Operator.get_operator(user)
    if operator is None:
        return

    command_args = message.text.split(' ')
    if len(command_args) == 1:
        await message.answer(text='Для блокировки пользователя введите /block @username')
        return
    elif len(command_args) > 2:
        await message.answer(text='Неверный формат команды')
        return
    else:
        current_user = await models.User.get_by_username(username=command_args[1].replace('@', ''))
        if current_user is None:
            await message.answer(text='Пользователь не найден.')
            return
        else:
            if command_args[0] == '/block':
                await state.set_state('block_user')
                await state.update_data({'user_id': current_user.telegram_id, 'edit_msg': False})
                await message.answer('Причина блокировки?')
                return
            else:
                current_user.is_blocked = False
                current_user.block_reason = None
                msg_text = f'Пользователь @{current_user.username} разблокирован' 

            await current_user.save()
            await message.answer(text=msg_text)


@dp.message_handler(commands=['data'], state='*')
async def get_user_data(message: types.Message, state: FSMContext):
    user = await models.User.get_user(message.from_user.id)
    operator = await models.Operator.get_operator(user)
    if operator is None and message.chat.id != RAISING_ID:
        return
    else:
        # mk = types.InlineKeyboardMarkup()
        # mk.row(types.InlineKeyboardButton(text='Главное меню', callback_data='start'))
        # msg_text = bt.ENTER_USER_USERNAME_MSG
        # await message.answer(msg_text, reply_markup=mk)
        command_args = message.text.split(' ')
        if len(command_args) == 1:
            await message.answer(text='Для вывода данных исполнителя введите /data @username')
            return
        elif len(command_args) > 2:
            await message.answer(text='Неверный формат команды')
            return
        else:
            current_user = await models.User.get_by_username(username=command_args[1].replace('@', ''))
            if current_user is None:
                await message.answer(text='Пользователь не найден.')
                return
            else:

                implementer = await models.Implementer.get_implementer(current_user)
                if implementer is None:
                    await message.answer(text='Вы не являетесь исполнителем')
                    return

                msg_text = 'Телефон: {phone}'.format(phone=implementer.phone_number) + '\n'
                msg_text += 'ФИО: {name}'.format(name=implementer.full_name) + '\n'
                msg_text += 'Дата рождения: {date_birth}'.format(date_birth=implementer.date_birth.strftime('%d.%m.%Y')) + '\n'
                msg_text += 'Гражданство РФ: {nationality}'.format(nationality=implementer.national) + '\n'
                msg_text += 'Статус самозанятости: {inn}'.format(inn='Нет' if not implementer.inn else 'Да') + '\n'
                msg_text += 'Подтвержденный паспорт: {passport}'.format(
                    passport='нет' if not implementer.passport else implementer.passport
                ) + '\n'

                msg_text += 'Пометка: {mark}'.format(mark=implementer.mark) + '\n'
                await implementer.fetch_related('towns')
                towns = implementer.towns
                bots = implementer.bots
                bot_info = []
                for bot in bots:
                    bot_info.append(bot.city)

                for town in towns:
                    bot_info.append(town.name)

                bot_name = ', '.join(info for info in bot_info)
                msg_text += 'Город(-а): {location}'.format(location=bot_name) + '\n'
                mk = types.InlineKeyboardMarkup()
                mk.row(types.InlineKeyboardButton(text='Изменить данные', callback_data='implementer_change_data'))
                msg_text+= f'Рейтинг {implementer.rating}' + '\n'
                msg_text += 'Штатный: {Employed}'.format(
                Employed='<b>Да</b>' if implementer.employment_type == 'state' else '<b>Нет</b>') + '\n'
                if current_user.is_blocked:
                    msg_text += f'\n\n<b>Заблокирован</b>\nПричина блокировки: {current_user.block_reason}'
                elif current_user.block_reason:
                    msg_text += f'\n\n<b>Был в блокировке</b>\nПричина блокировки: {current_user.block_reason}\n'

                if isinstance(message, types.Message):
                    await message.answer(msg_text, reply_markup=mk)
                else:
                    await message.message.answer(msg_text, reply_markup=mk)

                await state.update_data(user_id=current_user.telegram_id)


# @dp.message_handler(state='enter_username')
# @dp.callback_query_handler(Text(startswith='user_data:'))
# async def enter_username(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
#     await state.finish()
#     if isinstance(message, types.Message):
#         username = message.text
#         if username.startswith('@'):
#             username = username[1:]
#         user = await models.User.get_by_username(username)
#         if user is None:
#             await message.answer(text='Пользователь не найден')
#             return
#     else:
#         user_id = int(message.data.split(':')[1])
#         user = await models.User.get_user(user_id)

#     implementer = await models.Implementer.get_implementer(user)
#     if implementer is None:
#         await message.answer(text='Вы не являетесь исполнителем')
#         return

#     msg_text = 'Телефон: {phone}'.format(phone=implementer.phone_number) + '\n'
#     msg_text += 'ФИО: {name}'.format(name=implementer.full_name) + '\n'
#     msg_text += 'Дата рождения: {date_birth}'.format(date_birth=implementer.date_birth.strftime('%d.%m.%Y')) + '\n'
#     msg_text += 'Гражданство РФ: {nationality}'.format(nationality=implementer.national) + '\n'
#     msg_text += 'Статус самозанятости: {inn}'.format(inn='Нет' if not implementer.inn else 'Да') + '\n'
#     msg_text += 'Подтвержденный паспорт: {passport}'.format(
#         passport='нет' if not implementer.passport else implementer.passport
#     ) + '\n'

#     msg_text += 'Пометка: {mark}'.format(mark=implementer.mark) + '\n'
#     await implementer.fetch_related('towns')
#     towns = implementer.towns
#     bots = implementer.bots
#     bot_info = []
#     for bot in bots:
#         bot_info.append(bot.city)

#     for town in towns:
#         bot_info.append(town.name)

#     bot_name = ', '.join(info for info in bot_info)
#     msg_text += 'Город(-а): {location}'.format(location=bot_name) + '\n'
#     mk = types.InlineKeyboardMarkup()
#     mk.row(types.InlineKeyboardButton(text='Изменить данные', callback_data='implementer_change_data'))
#     msg_text+= f'Рейтинг {implementer.rating}' + '\n'
#     if user.is_blocked:
#         msg_text += f'\n\n<b>Заблокирован</b>\nПричина блокировки: {user.block_reason}'
#     elif user.block_reason:
#         msg_text += f'\n\n<b>Был в блокировке</b>\nПричина блокировки: {user.block_reason}\n'
#     if isinstance(message, types.Message):
#         await message.answer(msg_text, reply_markup=mk)
#     else:
#         await message.message.answer(msg_text, reply_markup=mk)

#     await state.update_data(user_id=user.telegram_id)


@dp.callback_query_handler(lambda call: call.data in ['implementer_data', 'implementer_change_data'], state='*')
async def implementer_change_data(call: types.CallbackQuery):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Изменить имя',
                                      callback_data='implementer_change_data:name'))
    mk.row(types.InlineKeyboardButton(text='Изменить фамилию',
                                      callback_data='implementer_change_data:surname'))
    mk.row(types.InlineKeyboardButton(text='Изменить отчество',
                                      callback_data='implementer_change_data:middlename'))
    mk.row(types.InlineKeyboardButton(text='Изменить дату рождения',
                                      callback_data='implementer_change_data:date_birth'))
    mk.row(types.InlineKeyboardButton(text='Изменить гражданство',
                                      callback_data='implementer_change_data:nationality'))
    mk.row(types.InlineKeyboardButton(text='Изменить фото паспорта',
                                      callback_data='implementer_change_data:passport'))
    mk.row(types.InlineKeyboardButton(text='Изменить пометку',
                                      callback_data='implementer_change_data:mark'))
    mk.row(types.InlineKeyboardButton(text='Изменить инн/статус самозанятости',
                                      callback_data='implementer_change_data:inn'))
    mk.row(types.InlineKeyboardButton(text='Изменить город',
                                     callback_data='implementer_change_data:city'))
    mk.row(types.InlineKeyboardButton(text='Паспортные данные',
                                    callback_data='implementer_change_data:passport_data'))
    mk.row(types.InlineKeyboardButton(text="Изменить рейтинг",
                                      callback_data='implementer_change_data:rating'))
    mk.row(types.InlineKeyboardButton(text="Изменить статус штатного",
                                      callback_data='implementer_change_data:employment'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='back_btn'))
    if call.message.text != bt.OPERATOR_SELECT_CITY_MSG or call.message.reply_markup != mk:
        try:
            await call.message.edit_reply_markup(mk)
        except Exception as e:
            logger.error (f'Ошибка {e}')

@dp.callback_query_handler(text='back_btn', state='*')
async def back(call: types.CallbackQuery, state: FSMContext):
    await call.message.delete()
    await state.finish()

@dp.callback_query_handler(text='implementer_change_data:rating', state='*')
async def implementer_change_rating(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Отправьте новое значение рейтинга', reply_markup=mk)
    await state.set_state('implementer_change_rating')


@dp.message_handler(state='implementer_change_rating')
async def implementer_change_rating_finish(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await message.answer(text='Вы не являетесь исполнителем')
        return
    implementer.rating = int(message.text)
    await implementer.save(update_fields=['rating'])
    await message.answer(text='Данные успешно изменены')
    await check_rating(implementer)
    await state.finish()
    
@dp.callback_query_handler(text='implementer_change_data:passport_data', state='*')
async def implementer_change_mark(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Отправьте паспортные данные / отправьте 0 чтобы установить подтвержденных данных: НЕТ ', reply_markup=mk)
    await state.set_state('implementer_change_passport_data')


@dp.message_handler(state='implementer_change_passport_data')
async def implementer_change_inn_finish(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await message.answer(text='Вы не являетесь исполнителем')
        return
    if message.text == '0':
        implementer.passport = None
    else:
        implementer.passport = message.text
    await implementer.save(update_fields=['passport'])
    await message.answer(text='Данные успешно изменены')
    await state.finish()


@dp.callback_query_handler(text='implementer_change_data:inn', state='*')
async def implementer_change_inn(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Отправьте новый инн / отправьте 0 чтобы установить статус самозанятости: НЕТ ', reply_markup=mk)
    await state.set_state('implementer_change_inn')


@dp.message_handler(state='implementer_change_inn')
async def implementer_change_inn_finish(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await message.answer(text='Вы не являетесь исполнителем')
        return
    if message.text == '0':
        implementer.inn = None
    else:
        implementer.inn = message.text
    await implementer.save(update_fields=['inn'])
    await message.answer(text='Данные успешно изменены')
    await state.finish()

@dp.callback_query_handler(text='implementer_change_data:city', state='*')
async def implementer_change_mark(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    bot_list = []
    botss = await models.Bot.get_all_bots()
    
    for i in botss:
        bot_list.append(i)

    await call.message.answer(bt.SELECT_LOCATION_MSG, reply_markup=select_city_markup(bot_list, [], []))
    await state.update_data(bot_list=bot_list)
    await state.set_state('implementer_change_city')


@dp.callback_query_handler(state='implementer_change_city')
async def implementer_change_city_finish(call: types.CallbackQuery, state: FSMContext):
    data = call.data.split(':')
    state_data = await state.get_data()
    if data[0] != 'select_bot':
        await state.finish()
        return

    bot_list = state_data.get('bot_list', [])
    city_list = state_data.get('city_list', [])
    town_list = state_data.get('town_list', [])

    if data[1] == 'city':
        if int(data[2]) not in city_list:
            city_list.append(int(data[2]))
        else:
            city_list.remove(int(data[2]))

        await state.update_data(city_list=city_list)
        await call.message.edit_reply_markup(select_city_markup(bot_list, city_list, town_list))

    elif data[1] == 'town':
        if int(data[2]) not in town_list:
            town_list.append(int(data[2]))
        else:
            town_list.remove(int(data[2]))

        await state.update_data(town_list=town_list)
        await call.message.edit_reply_markup(select_city_markup(bot_list, city_list, town_list))

    elif data[1] == 'confirm':
        if len(city_list) == 0 and len(town_list) == 0:
            await call.answer(show_alert=True, text=bt.LOCATION_NOT_SELECTED_MSG)
            return

        city_name_list = []
        town_name_list = []
        for bot in bot_list:
            if bot.id in city_list:
                city_name_list.append('- ' + bot.city)
            for town in bot.towns:
                if town.id in town_list:
                    town_name_list.append('- ' + town.name)

        general_list = city_name_list + town_name_list
        selected_names = '\n'.join(general_list)

        await call.message.edit_text(text=bt.SELECTED_LOCATION_MSG + selected_names)
        

        user_id = state_data.get('user_id')
        user = await models.User.get_user(user_id)
        implementer = await models.Implementer.get_implementer(user)
        await implementer.bots.clear()
        await implementer.save()
        bot_list = []
        for city_id in city_list:
            bot = await models.Bot.get_by_id(city_id)
            await bot.implementers.add(implementer)
            bot_list.append(bot)
        for town_id in town_list:
            town = await models.Town.get_by_id(town_id)
            await town.implementers.add(implementer)
            if town.bot not in bot_list:
                bot_list.append(town.bot)

        bot_info = []
        for bot in bot_list:
            bot_info.append([bot.title, bot.username])

        bot_name = ', '.join(info[0] for info in bot_info)
        mk1 = types.InlineKeyboardMarkup()
        for info in bot_info:
            link = f'https://t.me/{info[1]}'
            mk1.row(types.InlineKeyboardButton(text=info[0], url=link))
        try:
            temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')
            await temp_bot.send_message(chat_id=user_id,
                text=bt.SUCCESS_REGISTER_MSG.format(bot_title=bot_name), reply_markup=mk1,
                disable_web_page_preview=True)
    
        except Exception as e:
            logger.error(f'Ошибка при отправке новых городов пользователю {e}')
        await state.finish()         


@dp.callback_query_handler(text='implementer_change_data:mark', state='*')
async def implementer_change_mark(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Отправьте пометку об операторе', reply_markup=mk)
    await state.set_state('implementer_change_mark')


@dp.message_handler(state='implementer_change_mark')
async def implementer_change_mark_finish(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await message.answer(text='Вы не являетесь исполнителем')
        return

    implementer.mark += f'{message.text}\n'
    await implementer.save(update_fields=['mark'])
    await message.answer(text='Данные успешно изменены')
    await state.finish()

@dp.callback_query_handler(text='implementer_change_data:name', state='*')
async def implementer_change_name(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Отправьте ваше имя', reply_markup=mk)
    await state.set_state('implementer_change_name')


@dp.message_handler(state='implementer_change_name')
async def implementer_change_name_finish(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await message.answer(text='Вы не являетесь исполнителем')
        return

    full_name_list = implementer.full_name.split(' ')
    full_name = f'{full_name_list[0]} {message.text} {full_name_list[2]}'
    implementer.full_name = full_name
    await implementer.save(update_fields=['full_name'])
    await message.answer(text='Данные успешно изменены')
    await state.finish()


@dp.callback_query_handler(text='implementer_change_data:surname', state='*')
async def implementer_change_surname(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Отправьте вашу фамилию', reply_markup=mk)
    await state.set_state('implementer_change_surname')


@dp.message_handler(state='implementer_change_surname')
async def implementer_change_surname_finish(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await message.answer(text='Вы не являетесь исполнителем')
        return

    full_name_list = implementer.full_name.split(' ')
    full_name = f'{message.text} {full_name_list[1]} {full_name_list[2]}'
    implementer.full_name = full_name
    await implementer.save(update_fields=['full_name'])
    await message.answer(text='Данные успешно изменены')
    await state.finish()


@dp.callback_query_handler(text='implementer_change_data:middlename', state='*')
async def implementer_change_middlename(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Изменить отчество', reply_markup=mk)
    await state.set_state('implementer_change_middlename')


@dp.message_handler(state='implementer_change_middlename')
async def implementer_change_middlename_finish(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await message.answer(text='Вы не являетесь исполнителем')
        return

    full_name_list = implementer.full_name.split(' ')

    full_name = f'{full_name_list[0]} {full_name_list[1]} {message.text}'
    implementer.full_name = full_name
    await implementer.save(update_fields=[])
    await message.answer(text='Данные успешно изменены')
    await state.finish()


@dp.callback_query_handler(text='implementer_change_data:date_birth', state='*')
async def implementer_change_date_birth(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('''
Введи дату рождения в формате <b>ДД.ММ.ГГГГ</b>

Например: <b>01.01.1994</b>
''', reply_markup=mk)
    await state.set_state('implementer_change_date_birth')


@dp.message_handler(state='implementer_change_date_birth')
async def implementer_change_date_birth_finish(message: types.Message, state: FSMContext):
    try:
        user_date = datetime.datetime.strptime(message.text, '%d.%m.%Y') + datetime.timedelta(days=1)
    except ValueError:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
        await message.answer(text='Неверный формат даты рождения', reply_markup=mk)
        return

    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await message.answer(text='Вы не являетесь исполнителем')
        return

    implementer.date_birth = user_date
    await implementer.save(update_fields=['date_birth'])
    await message.answer('Данные успешно изменены')
    await state.finish()


@dp.callback_query_handler(text='implementer_change_data:nationality', state='*')
async def implementer_change_nationality(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Подтвердить', callback_data='confirm_change_implementer_nationality'))
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Вы уверены, что хотите изменить гражданство?', reply_markup=mk)


@dp.callback_query_handler(text='confirm_change_implementer_nationality', state='*')
async def implementer_change_nationality_finish(call: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return

    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
        await call.message.edit_text('Вы не являетесь исполнителем', reply_markup=mk)
        return

    if implementer.nationality:
        new_national = 'Нет'
    else:
        new_national = 'Да'

    implementer.nationality = not implementer.nationality
    await implementer.save(update_fields=['nationality'])
    await call.message.edit_reply_markup()
    await state.finish()

@dp.callback_query_handler(text='implementer_change_data:employment', state='*')
async def implementer_change_employment(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Штатный', callback_data='change_employment:state'))
    mk.row(types.InlineKeyboardButton(text='Подрядчик', callback_data='change_employment:contract'))
    await call.message.answer('Установите статус', reply_markup=mk)


@dp.callback_query_handler(Text(startswith='change_employment:'))
async def implementer_change_employment_confirm(call: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return
    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        return
    
    employment_type = call.data.split(':')[1]
    implementer.employment_type=employment_type
    await implementer.save()
    await call.message.answer('Данные успешно изменены')
    await state.finish()

@dp.callback_query_handler(text='implementer_change_data:passport', state='*')
async def implementer_change_passport_photo(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Назад', callback_data='implementer_data'))
    await call.message.answer('Отправьте фото паспорта', reply_markup=mk)
    await state.set_state('implementer_change_passport_photo')
    


@dp.message_handler(state='implementer_change_passport_photo', content_types=types.ContentType.PHOTO)
async def implementer_change_passport_photo_finish(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = user_data.get('user_id')
    user = await models.User.get_user(user_id)
    if user is None:
        return
    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        return
    
    await message.answer(text='Загрузка фото...')
    bytes_io = BytesIO()
    await message.bot.download_file_by_id(message.photo[-1].file_id, bytes_io)
    bytes_io.seek(0)
    today = datetime.datetime.now().date().strftime('%d_%m_%Y')
    await delete_file(f'{implementer.full_name}_{implementer.bots[0].city}_{today}'.replace(' ', '_'))
    await upload_file(bytes_io, dependencies.YANDEX_DIR +
                      f"/{implementer.full_name}_{implementer.bots[0].city}_{today}.jpg".replace(' ', '_'))

    bytes_io = BytesIO()
    await message.bot.download_file_by_id(message.photo[-1].file_id, bytes_io)
    bytes_io.seek(0)
    # implementer.pass_photo = bytes_io.read()
    # await implementer.save(update_fields=['pass_photo'])
    await state.finish()
    await message.answer('Данные успешно изменены')

@dp.message_handler(commands=['commands'], state='*')
async def cmd_list(message: types.Message, state: FSMContext):
    try:
        user = await models.User.get_user(message.from_user.id)
        if user is None:
            await message.answer("Пользователь не найден.")
            return

        operator = await models.Operator.get_operator(user)
        if operator is None and message.chat.id != RAISING_ID:
            await message.answer("Оператор не найден.")
            return

        
        if not bt.CMD_LIST:
            await message.answer("Список команд пуст.")
            return

        text = '\n'.join(bt.CMD_LIST)
        await message.answer(text)

    except Exception as e:
        
        logger.error(f"Ошибка при выполнении команды /commands: {str(e)}")
        await message.answer("Произошла ошибка при обработке команды.")

@dp.message_handler(commands=['stats'], state='*')
async def cmd_list(message: types.Message, state: FSMContext):
    user = await models.User.get_user(message.from_user.id)
    operator = await models.Operator.get_operator(user)
    if operator is None:
        return
    else:
        command_args = message.text.split(' ')
        if len(command_args) == 1:
            await message.answer(text='Для вывода статистики оператора введите /stats @username')
            return
        elif len(command_args) > 2:
            await message.answer(text='Неверный формат команды')
            return
        else:
            current_user = await models.User.get_by_username(username=command_args[1].replace('@', ''))
            if current_user is None:
                await message.answer(text='Пользователь не найден.')
                return
            else:
                await state.finish()
                mk = types.InlineKeyboardMarkup()
                await state.update_data(user_id=current_user.telegram_id)    
                operator = await models.Operator.get_operator(current_user)
                if operator is None:
                    await message.answer(text='Пользователь не оператор')
                    return
                if  operator.priority_stats is None:
                    operator.priority_stats = [0] * 18
                    await operator.save()
                    logger.info (f'у оператора {operator.user.telegram_id} не было статистики, устанавливаю')
                if len(operator.priority_stats) == 16:
                    operator.priority_stats.insert(1,0)
                    operator.priority_stats.insert(10,0)
                    await operator.save()
                msg_text = f'Группа: Штатный / всего: {operator.priority_stats[1]} принятые: {operator.priority_stats[10]}'+ '\n'
                msg_text += f'Группа: рф, подтвержденные данные, самозанятый / всего: {operator.priority_stats[2]} принятые: {operator.priority_stats[11]}'+ '\n'
                msg_text += f'Группа: рф, самозанятый / всего: {operator.priority_stats[3]} принятые: {operator.priority_stats[12]}' + '\n'
                msg_text += f'Группа: самозанятый, подтвержденные данные / всего: {operator.priority_stats[4]} принятые: {operator.priority_stats[13]}' + '\n'
                msg_text += f'Группа: самозанятый / всего: {operator.priority_stats[5]} принятые: {operator.priority_stats[14]}' + '\n'
                msg_text += f'Группа: рф, подтвержденные данные / всего: {operator.priority_stats[6]} принятые: {operator.priority_stats[15]}' + '\n'
                msg_text += f'Группа: подтвержденные данные / всего: {operator.priority_stats[7]} принятые: {operator.priority_stats[16]} ' + '\n'
                msg_text += f'Группа: рф / всего: {operator.priority_stats[8]} принятые: {operator.priority_stats[17]}' + '\n'
                msg_text += f'Группа: остальные / всего: {operator.priority_stats[0]} принятые: {operator.priority_stats[9]} ' + '\n'
                mk.row(types.InlineKeyboardButton(text='Отклики самозанятых по датам', callback_data='operator_self_employed_stats'))
                await message.answer(text=msg_text,reply_markup=mk)



@dp.callback_query_handler(Text(startswith='operator_self_employed_stats'))
async def get_operator_self_employed_stats(call: types.CallbackQuery, state: FSMContext):
    
    await call.message.answer('''Введите дату в формате <b>ДД.ММ.ГГГГ</b>  
Например: <b>01.01.1994</b>''')
    await call.message.edit_reply_markup()
    await state.set_state('operator_self_employed_stats_math')

@dp.message_handler(state='operator_self_employed_stats_math')
async def get_operator_self_employed_stats_finish(message: types.Message, state: FSMContext):
    try:
        stat_date = datetime.datetime.strptime(message.text, '%d.%m.%Y').date() #+ datetime.timedelta(days=1)
    except ValueError:
        await message.answer(text='Неверный формат даты')
        return
    try:
        state_data= await state.get_data()

        user_id = state_data.get('user_id')

        user = await models.User.get_user(user_id)
        operator = await models.Operator.get_operator(user)
        requests = await models.Request.filter(
            operator_id=operator.id,
        ).all()
        filtered_requests = []
        for request in requests:
            try:
                request_date = datetime.datetime.strptime(request.date[:10], '%d.%m.%Y').date()
                logger.debug (f'request_date {request_date} == {stat_date}')   
                if request_date == stat_date:
                    filtered_requests.append(request)
            except ValueError:
                continue
                


        total_implementers_with_inn = 0
        accepted_implementers_with_inn = 0

        # Множества для уникальных исполнителей с INN
        unique_implementers_with_inn = set()
        accepted_implementers_with_inn_set = set()

        for request in filtered_requests:
            implementer_requests = await models.ImplementerRequests.filter(request_id=request.id).all()
            # Извлекаем всех исполнителей, связанных с request через поле 'implementers'
            implementers_for_request = await request.implementers.all()
            #logger.info(f'исполнители заказа {request.id} {implementers_for_request}')
            implementer_ids = []
            for req in implementer_requests:
                implementer_ids.extend(req.implementers_ids)  # Извлекаем implementers_ids из JSON
            implementers_with_inn = await models.Implementer.filter(
                id__in=implementer_ids,
                inn__isnull=False
            ).values_list('id', flat=True)


            # Учитываем всех исполнителей с INN
            unique_implementers_with_inn.update(implementers_with_inn)

           # Проверяем, кто из этих исполнителей был принят
            accepted_implementers = [
                implementer.id for implementer in implementers_for_request
                if implementer.inn
    ]
            accepted_implementers_with_inn_set.update(accepted_implementers)

        # Подсчёт общего количества исполнителей с INN
        total_implementers_with_inn = len(unique_implementers_with_inn)

        # Подсчёт принятых исполнителей с INN
        accepted_implementers_with_inn = len(accepted_implementers_with_inn_set)

        # Вывод результатов
        await message.answer(
            f'По дате {stat_date.strftime("%d.%m.%Y")}: '
            f'Общее количество самозанятых исполнителей : {total_implementers_with_inn}\n'
            f'Принятые самозанятые исполнители: {accepted_implementers_with_inn}'
        )
    except Exception as e:
        logger.info (f'Ошибка при обработке {e}')
    await state.finish()

@dp.message_handler(commands=['get_priority'], state='*')
async def get_priority(message: types.Message, state: FSMContext):
    user = await models.User.get_user(message.from_user.id)
    operator = await models.Operator.get_operator(user)
    if operator is None:
        return
    else:
        command_args = message.text.split(' ')
        if len(command_args) == 1:
            await message.answer(text='Для получения приоритетной группы исполнителя введите /get_priority @username')
            return
        elif len(command_args) > 2:
            await message.answer(text='Неверный формат команды')
            return
        else:
            current_user = await models.User.get_by_username(username=command_args[1].replace('@', ''))
            if current_user is None:
                await message.answer(text='Пользователь не найден.')
                return
            else:
                try:
                    implementer = await models.Implementer.get_implementer(user)    
                    if implementer is None: 
                        await message.answer('Пользователь не исполнитель')
                        return
                    else:
                        implementer.priority_group = await get_priority_group(implementer.id)
                        msg_text= f'РФ: {implementer.national}\n'
                        msg_text+= 'Статус самозанятости: {inn}'.format(inn='нет' if not implementer.inn else 'Да') + '\n'
                        msg_text+='Статус подтвержденного паспорта: {passport}'.format(
                        passport='Нет' if not implementer.passport else 'Да'
                    ) + '\n'
                        msg_text += 'Штатный: {Employed}'.format(
                            Employed='<b>Да</b>' if implementer.employment_type == 'state' else '<b>Нет</b>') + '\n'
                        await message.answer(msg_text + f'Приоритетная группа {implementer.priority_group}')
                            
                except (ValueError, IndexError):
                    await message.reply("Укажите корректный ID пользователя после команды.")



# @dp.message_handler(state='get_priority')
# @dp.callback_query_handler(Text(startswith='priority_group:'))
# async def priority_group_check(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
#     await state.finish()
#     if isinstance(message, types.Message):
#         username = message.text
#         if username.startswith('@'):
#             username = username[1:]
#         user = await models.User.get_by_username(username)
#         if user is None:
#             await message.answer(text='Пользователь не найден')
#             return
#     else:
#         user_id = int(message.data.split(':')[1])
#         user = await models.User.get_user(user_id)
 
#     try:
#         async def get_priority_group(implementer_id):
#             implementer_pg = await models.Implementer.get_or_none(id=implementer_id)
#             if implementer_pg.nationality and implementer_pg.passport and implementer_pg.inn:
#                 return 1  
#             elif implementer_pg.nationality and implementer_pg.inn:
#                 return 2 
#             elif implementer_pg.inn and implementer_pg.passport:
#                 return 3  
#             elif implementer_pg.inn:
#                 return 4  
#             elif implementer_pg.nationality and implementer_pg.passport:
#                 return 5  
#             elif implementer_pg.passport:
#                 return 6  
#             elif implementer_pg.nationality:
#                 return 7  
#             else:
#                 return 0  
        
#         implementer = await models.Implementer.get_implementer(user)    
#         if implementer is None: 
#             await message.answer('Пользователь не исполнитель')
#             return
#         else:
#             implementer.priority_group = await get_priority_group(implementer.id)
#             msg_text= f'РФ: {implementer.national}\n'
#             msg_text+= 'Статус самозанятости: {inn}'.format(inn='нет' if not implementer.inn else 'Да') + '\n'
#             msg_text+='Статус подтвержденного паспорта: {passport}'.format(
#             passport='Нет' if not implementer.passport else 'Да'
#         ) + '\n'
#             await message.answer(msg_text + f'Приоритетная группа {implementer.priority_group}')
                
#     except (ValueError, IndexError):
#         await message.reply("Укажите корректный ID пользователя после команды.")

def select_city_markup(bot_list: list, selected_city: list, selected_town: list):
        mk = types.InlineKeyboardMarkup()
        for bot in bot_list:
            if bot.id in selected_city:
                btn_text = f'{bt.CHECKED_BTN} {bot.city}'
            else:
                btn_text = bot.city

            mk.row(types.InlineKeyboardButton(text=btn_text, callback_data=f'select_bot:city:{bot.id}'))
            for town in bot.towns:
                if town.id in selected_town:
                    btn_text = f'{bt.CHECKED_BTN} {town.name}'
                else:
                    btn_text = town.name

                mk.row(types.InlineKeyboardButton(text=btn_text, callback_data=f'select_bot:town:{town.id}'))

        mk.row(types.InlineKeyboardButton(text=bt.CONFIRM_BTN, callback_data='select_bot:confirm:0'))
        return mk

async def check_for_seal(operator: models.Operator):
    seal_list = [20,40,60,80,90,95]
    try:
        if operator.seal_manual:
                return 0
        if operator.seal_count in seal_list:
                text = f'Внимание, у оператора @{operator.user.username} скопилось {operator.seal_count} не завершенных заказов\nПри достижении 100 незаверешнных заказов он не сможет выкладывать заявки'
                temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')
                await temp_bot.send_message(chat_id=MODERATOR_ID,
                            text=text,
                            disable_web_page_preview=True)
                return 0
        if operator.seal_count >= 100:
            operator.seal = True
            operator.save()
            text = f'Внимание, у оператора @{operator.user.username} скопилось {operator.seal_count} незавершенных заказов.\nОн больше не можете выкладывать новые заявки, пожалуйста завершите заказы в меню Мои заказы'
            temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')
            await temp_bot.send_message(chat_id=MODERATOR_ID,
                                text=text,
                                disable_web_page_preview=True)
            return 1
        else:
            if operator.seal:
                operator.seal = False
                operator.save()
                try:
                    text = f'Вы снова можете выкладывать новые заказы, но у вас все еще {operator.seal_count} незавершенных заказов '
                    temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')
                    await temp_bot.send_message(chat_id=operator.user.telegram_id,
                                    text=text,
                                    disable_web_page_preview=True)
                    return 0
                except Exception as e:
                    logger.error(f'Ошибка при попытке отправить уведомление о количестве незавершенных заказов {e}')
            else:
                return 0
    except Exception as e:
        logger.error (f'Ошибка чек сил {e}')

async def check_rating(implementer: models.Implementer):
    if implementer.rating <= -10:
        temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')
        mk = types.InlineKeyboardMarkup()
        text = f'Исполнитель @{implementer.user.username} достиг рейтинга {implementer.rating}'
        mk.row(types.InlineKeyboardButton(text=bt.BLOCK_BTN, callback_data=f'accept_block:{implementer.user.telegram_id}'))
        mk.row(types.InlineKeyboardButton(text='Отклонить блокировку', callback_data=f'decline_block:{implementer.user.telegram_id}'))
        await temp_bot.send_message(chat_id=MODERATOR_ID,
                                text=text,
                                disable_web_page_preview=True,
                                reply_markup=mk
                                )
        return 1
    else:
        return 0
@dp.callback_query_handler(Text(startswith='done'))
async def done(call: types.CallbackQuery):
    await call.message.delete()

async def add_message(chat_messages, chat_id, message_id):
    chat_messages.message_ids = chat_messages.message_ids + [{"chat_id": chat_id, "message_id": message_id}]
    await chat_messages.save()

