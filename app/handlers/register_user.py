import datetime
import io
from typing import Union

from aiogram import types, Bot
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

from app import dependencies
from app.db import models
from app.dependencies import dp, TICKETS_ID, bot
from app.services.city_location import reverse_geocode
from app.services.states import RegisterState
from app.services import bot_texts as bt
from app.services.ya_disk import upload_file
from logs.log_info import logger

@dp.message_handler(content_types=types.ContentType.CONTACT, state=RegisterState.phone_number)
async def get_phone_number(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    await state.update_data(phone_number=phone_number)
    
    bot_list = []
    botss = await models.Bot.get_all_bots()
    for i in botss:
        bot_list.append(i)
    
    await message.answer(bt.SELECT_LOCATION_MSG, reply_markup=select_city_markup(bot_list, [], []))
    await state.update_data(bot_list=bot_list)
    await RegisterState.choice_region.set()


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


@dp.message_handler(content_types=types.ContentType.LOCATION, state=RegisterState.city)
async def get_city(message: types.Message, state: FSMContext):
    city = message.location
    city, city_state = await reverse_geocode(city.latitude, city.longitude)
    if city is None and state is None:
        await message.answer(bt.WRONG_LOCATION_MSG)
        return

    bot_list = []
    if city:
        bot = await models.Bot.get_by_city(city)
        if bot:
            bot_list.append(bot)

    if city_state:
        bots = await models.Bot.get_by_state(city_state)
        for bot in bots:
            if bot not in bot_list:
                bot_list.append(bot)

    if len(bot_list) == 0:
        bot_list = []
        botss = await models.Bot.get_all_bots()
        print(botss)
        for i in botss:
            bot_list.append(i)
        await message.answer(bt.SELECT_LOCATION_MSG, reply_markup=select_city_markup(bot_list, [], []))
        await state.update_data(bot_list=bot_list)
        await RegisterState.next()
        return

    if len(bot_list) == 1 and len(bot_list[0].towns) == 0:
        text = bt.FIND_LOCATION_MSG.format(city=bot_list[0].city)
        selected_city = bot_list[0].id
        await state.update_data(city_list=[selected_city])

        bot_list = []
        botss = await models.Bot.get_all_bots()
        print(botss)
        for i in botss:
            bot_list.append(i)

        await message.answer(text, reply_markup=select_city_markup(bot_list, [selected_city], []))
        await state.update_data(bot_list=bot_list)
        await RegisterState.next()
        return

    await message.answer(bt.SELECT_LOCATION_MSG, reply_markup=select_city_markup(bot_list, [], []))
    await state.update_data(bot_list=bot_list)
    await RegisterState.next()


@dp.callback_query_handler(state=RegisterState.choice_region)
async def get_region(call: types.CallbackQuery, state: FSMContext):
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
        await call.message.answer(text=bt.BEFORE_SEND_NAME_MSG, reply_markup=types.ReplyKeyboardRemove())
        await call.message.answer(text=bt.SEND_FIRST_NAME_MSG)
        await RegisterState.name.set()


@dp.message_handler(state=RegisterState.name)
async def get_name(message: types.Message, state: FSMContext):
    try:
        name = message.text
        if len(name.split()) > 1:
            await message.answer(text=bt.SEND_FIRST_NAME_MSG)
            return
        await state.update_data(name=name)
        await message.answer(bt.SEND_SURNAME_MSG)
        await RegisterState.next()
    except Exception as e:
        logger.error(f'Ошибка регистрации {e}')
    


@dp.message_handler(state=RegisterState.surname)
async def get_surname(message: types.Message, state: FSMContext):
    surname = message.text
    if len(surname.split()) > 1:
        await message.answer(text=bt.SEND_SURNAME_MSG)
        return
    await state.update_data(surname=surname)
    await message.answer(bt.SEND_MIDDLE_NAME_MSG)
    await RegisterState.next()


@dp.message_handler(state=RegisterState.middle_name)
async def get_middle_name(message: types.Message, state: FSMContext):
    middle_name = message.text
    if len(middle_name.split()) > 1:
        await message.answer(text=bt.SEND_MIDDLE_NAME_MSG)
        return
    await state.update_data(middle_name=middle_name)
    await message.answer(bt.SEND_DATE_BIRTH_MSG)
    await RegisterState.next()


@dp.message_handler(state=RegisterState.date_birth)
async def get_date_birth(message: types.Message, state: FSMContext):
    date_birth = message.text
    try:
        date_birth_dt = datetime.datetime.strptime(date_birth, '%d.%m.%Y')
    except ValueError:
        await message.answer(bt.WRONG_DATE_BIRTH_MSG)
        return

    today = datetime.datetime.now()
    age = today.year - date_birth_dt.year - ((today.month, today.day) < (date_birth_dt.month, date_birth_dt.day))

    if age < 18:
        await message.answer(text=bt.YOUNGER_MSG)
        return

    await state.update_data(date_birth=date_birth_dt)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.YES_BTN, callback_data='nationality:yes'))
    mk.row(types.InlineKeyboardButton(text=bt.NO_BTN, callback_data='nationality:no'))
    await message.answer(bt.SEND_NATIONALITY_MSG, reply_markup=mk)
    await RegisterState.next()


# @dp.message_handler(content_types=types.ContentType.PHOTO, state=RegisterState.pass_photo)
# async def get_pass_photo(message: types.Message, state: FSMContext):
#     photo = message.photo[-1].file_id
#     await state.update_data(pass_photo=photo)
#     mk = types.InlineKeyboardMarkup()
#     mk.row(types.InlineKeyboardButton(text=bt.YES_BTN, callback_data='nationality:yes'))
#     mk.row(types.InlineKeyboardButton(text=bt.NO_BTN, callback_data='nationality:no'))
#     await message.answer(bt.SEND_NATIONALITY_MSG, reply_markup=mk)
#     await RegisterState.next()


async def confirm_data(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    data = await state.get_data()
    city_list = data.get('city_list', [])
    town_list = data.get('town_list', [])
    location_name_list = []
    for city in city_list:
        bot = await models.Bot.get_by_id(city)
        location_name_list.append(bot.city)

    for town_id in town_list:
        town = await models.Town.get_by_id(town_id)
        location_name_list.append(town.name)

    location_text = ', '.join(location_name_list)

    full_name = f'{data["surname"]} {data["name"]} {data["middle_name"]}'
    msg_text = bt.REQUEST_PHONE_MSG.format(phone=data['phone_number']) + '\n'
    msg_text += bt.REQUEST_NAME_MSG.format(name=full_name) + '\n'
    msg_text += bt.REQUEST_DATE_BIRTH_MSG.format(date_birth=data['date_birth'].strftime('%d.%m.%Y')) + '\n'
    msg_text += bt.REQUEST_NATIONALITY_MSG.format(nationality="Да" if data['nationality'] else "Нет") + '\n'
    msg_text += bt.REQUEST_LOCATION_MSG.format(location=location_text)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.CONFIRM_BTN, callback_data='confirm_register'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_DATA_BTN, callback_data='change_data'))
    if isinstance(message, types.CallbackQuery):
        message = message.message
        await message.edit_reply_markup()
    await message.answer(text=msg_text, reply_markup=mk)
    await RegisterState.confirm_data.set()


@dp.callback_query_handler(Text(startswith='nationality:'), state=RegisterState.nationality)
async def get_nationality(call: types.CallbackQuery, state: FSMContext):
    param = call.data.split(':')[1]
    if param == 'yes':
        nationality = True
    else:
        nationality = False
   
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.YES_BTN, callback_data='straps:yes'))
    mk.row(types.InlineKeyboardButton(text=bt.NO_BTN, callback_data='straps:no'))
    await call.message.answer(bt.SEND_STRAPS_MSG, reply_markup=mk)
    await RegisterState.next()
    await state.update_data(nationality=nationality)
    
    # await confirm_data(call, state)

@dp.callback_query_handler(Text(startswith='straps:'), state=RegisterState.tools)
async def get_straps(call: types.CallbackQuery, state: FSMContext):
    param = call.data.split(':')[1]
    if param == 'yes':
        straps = True
    else:
        straps = False

    await state.update_data(straps=straps)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.YES_BTN, callback_data='tools:yes'))
    mk.row(types.InlineKeyboardButton(text=bt.NO_BTN, callback_data='tools:no'))
    await call.message.answer(bt.SEND_TOOLS_MSG, reply_markup=mk)

@dp.callback_query_handler(Text(startswith='tools:'), state=RegisterState.tools)
async def get_nationality(call: types.CallbackQuery, state: FSMContext):
    param = call.data.split(':')[1]
    if param == 'yes':
        tools = True
    else:
        tools = False

    await state.update_data(tools=tools)
    await confirm_data(call, state)


@dp.callback_query_handler(text='confirm_register', state=RegisterState.change_data)
@dp.callback_query_handler(text='confirm_register', state=RegisterState.confirm_data)
async def confirm_register(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()

        city_list = data.get('city_list', [])
        town_list = data.get('town_list', [])
        full_name = f'{data["surname"]} {data["name"]} {data["middle_name"]}'
        user = await models.User.get_user(
            telegram_id=message.from_user.id
        )
        implementer = await models.Implementer.add_implementer(
            user=user,
            full_name=full_name,
            phone_number=data['phone_number'],
            date_birth=data['date_birth'],
            nationality=data['nationality'],
            straps=data['straps'],
            tools=data['tools']
        )
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
        mk = types.InlineKeyboardMarkup()
        for info in bot_info:
            link = f'https://t.me/{info[1]}'
            mk.row(types.InlineKeyboardButton(text=info[0], url=link))

        if isinstance(message, types.CallbackQuery):
            await message.message.edit_reply_markup()
            message = message.message
        await message.answer(bt.SUCCESS_REGISTER_MSG.format(bot_title=bot_name), reply_markup=mk)
        await state.finish()
    except Exception as e:
        if 'duplicate key value violates unique constraint "implementers_phone_number_key"' in str(e):
                if isinstance(message, types.CallbackQuery):
                    await message.message.edit_reply_markup()
                    message = message.message
                mk =  types.InlineKeyboardMarkup()
                mk.row(types.InlineKeyboardButton(text='Отправить', callback_data=f'send_ticket:{user.telegram_id}'))
                mk.row(types.InlineKeyboardButton(text='Не отправлять', callback_data='cancel_ticket'))
                await message.reply(text='⚠️ Этот номер телефона уже зарегистрирован в системе.\n\n'
                'Отправить запрос на удаление старого профиля?',reply_markup=mk)
        logger.error(f'ошибка регистрации {e}')

@dp.callback_query_handler(Text(startswith='send_ticket:'), state=RegisterState.change_data)
@dp.callback_query_handler(Text(startswith='send_ticket:'), state=RegisterState.confirm_data)
async def send_ticket(call:types.CallbackQuery, state: FSMContext):
    try:
        user_id = int(call.data.split(':')[1])
        data = await state.get_data()
        old_implementer = await models.Implementer.get(phone_number=data['phone_number'])
        old_implementer = await models.Implementer.get_by_id(old_implementer.id)
        new_user = await models.User.get_user(user_id)

        text = 'Пользователь запросил удаление старого профиля\n'
        text += f'Старый профиль пользователя @{old_implementer.user.username}\n'
        text += f'Рейтинг старого пользователя: {old_implementer.rating}\n'
        if old_implementer.user.block_reason:
            text+= f'Был заблокирован, причина: {old_implementer.user.block_reason}\n'
        text += f'Новый профиль пользователя @{new_user.username}\n'
        text += f'Причина: занят номер телефона {old_implementer.phone_number}\n'

        mk =  types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text='Одобрить', callback_data=f'approve_del:{old_implementer.id}:{call.from_user.id}'))
        mk.row(types.InlineKeyboardButton(text='Не одобрять', callback_data=f'cancel_del:{call.from_user.id}'))

        await bot.send_message(chat_id=TICKETS_ID,text=text,reply_markup=mk)

        await call.message.edit_reply_markup()
        await call.message.edit_text("✅ Запрос отправлен администратору. Ожидайте решения.")
    except Exception as e:
        logger.error(f"Ticket error: {e}")
        await call.answer("⚠ Ошибка при отправке запроса")
    finally:
        await state.finish()
@dp.callback_query_handler(text='cancel_ticket', state=RegisterState.change_data)
@dp.callback_query_handler(text='cancel_ticket', state=RegisterState.confirm_data)
async def cancel_ticket(call:types.CallbackQuery, state: FSMContext):
    await call.message.edit_text('Действие отменено')
    await state.finish()

@dp.callback_query_handler(text='change_data', state=RegisterState.in_process_change_data)
@dp.callback_query_handler(text='change_data', state=RegisterState.confirm_data)
async def change_data(call: types.CallbackQuery):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_NAME_BTN, callback_data='change_data:name'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_SURNAME_BTN, callback_data='change_data:surname'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_MIDDLE_NAME_BTN, callback_data='change_data:middlename'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_NATIONALITY_BTN, callback_data='change_nationality'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_DATE_BIRTH_BTN, callback_data='change_data:date_birth'))
    mk.row(types.InlineKeyboardButton(text=bt.CHANGE_PASSPORT_PHOTO_BTN, callback_data='change_data:pass_photo'))
    mk.row(types.InlineKeyboardButton(text=bt.CONFIRM_BTN, callback_data='confirm_register'))
    await call.message.edit_reply_markup(mk)
    await RegisterState.change_data.set()


@dp.callback_query_handler(text='change_nationality', state=RegisterState.change_data)
async def change_nationality(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    nationality = data.get('nationality')
    if nationality:
        await state.update_data(nationality=False)
    else:
        await state.update_data(nationality=True)

    await call.message.answer(text=bt.CHANGE_DATA_SUCCESS_MSG)
    await confirm_data(call, state)


@dp.callback_query_handler(Text(startswith='change_data:'), state=RegisterState.change_data)
async def change_data_param(call: types.CallbackQuery, state: FSMContext):
    param = call.data.split(':')[1]
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='change_data'))
    await state.update_data(param=param)
    if param == 'name':
        msg_text = bt.SEND_FIRST_NAME_MSG
    elif param == 'surname':
        msg_text = bt.SEND_SURNAME_MSG
    elif param == 'middlename':
        msg_text = bt.SEND_MIDDLE_NAME_MSG
    elif param == 'date_birth':
        msg_text = bt.SEND_DATE_BIRTH_MSG
    elif param == 'pass_photo':
        msg_text = bt.SEND_PASSPORT_PHOTO_MSG

    await call.message.edit_reply_markup()
    await call.message.answer(msg_text, reply_markup=mk)
    await RegisterState.in_process_change_data.set()


@dp.message_handler(state=RegisterState.in_process_change_data,
                    content_types=types.ContentTypes.TEXT | types.ContentTypes.PHOTO)
async def finish_change_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    param = data['param']
    back_mk = types.InlineKeyboardMarkup()
    back_mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='change_data'))
    if message.content_type == types.ContentTypes.PHOTO and param != 'pass_photo':
        return

    if param == 'name':
        await state.update_data(name=message.text)
    elif param == 'surname':
        await state.update_data(surname=message.text)
    elif param == 'middlename':
        await state.update_data(middle_name=message.text)
    elif param == 'date_birth':
        date_birth = datetime.datetime.strptime(message.text, '%d.%m.%Y')
        today = datetime.datetime.now()
        age = today.year - date_birth.year - ((today.month, today.day) < (date_birth.month, date_birth.day))

        if age < 18:
            await message.answer(text=bt.YOUNGER_MSG)
            return
        try:
            await state.update_data(date_birth=date_birth)
        except ValueError:
            await message.answer(bt.WRONG_DATE_BIRTH_MSG, reply_markup=back_mk)
            return
    elif param == 'pass_photo':
        if message.photo:
            photo_file_id = message.photo[-1].file_id
            await state.update_data(pass_photo=photo_file_id)
        else:
            await message.answer(bt.SEND_PASSPORT_PHOTO_MSG, reply_markup=back_mk)
            return

    await message.answer(bt.CHANGE_DATA_SUCCESS_MSG)
    await confirm_data(message, state)
