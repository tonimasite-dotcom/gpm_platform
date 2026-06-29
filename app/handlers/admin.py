import fileinput
import json
import os
import shutil
import traceback
import requests
from datetime import datetime
from typing import Union, Coroutine

from aiogram import types, Bot
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

from app import dependencies
from app.db import models
from app.db.models import User, Implementer
from app.dependencies import bot, dp, SUPPORT_ID, API_TOKEN, MODERATOR_ID, global_config
from app.dependencies import get_config, update_config
from app.dependencies import HEADERS, CRM_URL
from app.services import bot_texts as bt
from app.services.city_location import search_city, search_state
from app.services.sending_manager import SenderCounter, sending_manager
from logs.log_info import logger


@dp.callback_query_handler(Text(startswith='confirm_operator_request:'), state='*')
async def confirm_operator_request(call: types.CallbackQuery):
    request_id = int(call.data.split(':')[1])
    request = await models.OperatorInvite.get_by_id(request_id)
    if request is None:
        await call.message.edit_reply_markup()
        return

    await models.Operator.add_operator(request.user)
    request.is_accepted = True
    await request.save()
    await call.message.edit_text(text=call.message.html_text + '\n\n' + bt.ADMIN_CONFIRM_REQUEST_MSG)
    await call.bot.send_message(chat_id=request.user.telegram_id, text=bt.OPERATOR_REQUEST_CONFIRM_MSG)


@dp.callback_query_handler(Text(startswith='go_back'), state='send_response')
async def go_back(call: types.CallbackQuery, state: FSMContext):
    _, tg_user_id, city_dir = call.data.split(':')
    data: dict = await state.get_data()
    message = data['msg_text']
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Ответить', callback_data=f'ask_response:{tg_user_id}:{city_dir}'))

    await bot.send_message(SUPPORT_ID, message, reply_markup=mk)
    await state.finish()
    await call.message.delete()

@dp.callback_query_handler(Text(startswith='ask_response:'), state='*')
async def confirm_operator_request(call: types.CallbackQuery, state: FSMContext):
    _, tg_user_id, city_dir = call.data.split(':')
    await state.set_state('send_response')
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data=f'go_back:{tg_user_id}:{city_dir}'))
    msg = await call.message.answer(call.message.text + '\n\n <b>Введите ответ:</b>',reply_markup=mk)
    await state.update_data({
        'msg_text': call.message.text, 'msg_id': msg.message_id, 'tg_user_id': tg_user_id, 'city_dir': city_dir
    })

    await call.message.delete()


@dp.message_handler(state='send_response')
async def send_response(message: types.Message, state: FSMContext):
    data: dict = await state.get_data()
    msg_text = data['msg_text']
    msg_id = data['msg_id']
    tg_user_id = data['tg_user_id']
    city_dir = data['city_dir']

    msg_text: str = msg_text + f'\n\n<b>Ответ:</b>\n{message.text}'

    print(msg_text)
    user = await models.User.get_user(message.from_user.id)
    await message.bot.edit_message_text(
        text=msg_text + f'\n @{user.username}',
        message_id=int(msg_id),
        chat_id=SUPPORT_ID
    )
    await message.delete()

    new_msg_text = '<b>Получен ответ на ваш вопрос:</b>\n\n' + '\n\n'.join(msg_text.split('\n\n')[1:])

    with open(os.path.join('city_bots', city_dir, 'data.json'), 'r') as file:
        data = json.load(file)
        city_token = data['token']
        city_bot = Bot(token=city_token, parse_mode='HTML')
        await city_bot.send_message(
            chat_id=tg_user_id, text=new_msg_text
        )

    await state.reset_state(with_data=False)


@dp.callback_query_handler(Text(startswith='decline_operator_request:'), state='*')
async def decline_operator_request(call: types.CallbackQuery):
    request_id = int(call.data.split(':')[1])
    request = await models.OperatorInvite.get_by_id(request_id)
    if request is None:
        await call.message.edit_reply_markup()
        return

    await call.message.edit_text(text=call.message.html_text + '\n\n' + bt.ADMIN_DECLINE_REQUEST_MSG)
    await call.bot.send_message(chat_id=request.user.telegram_id, text=bt.OPERATOR_REQUEST_DECLINE_MSG)

@dp.callback_query_handler(text='disable_geocoder', state='*')
@dp.message_handler(commands=['disable_geocoder'], state='*')
async def disable_geocoder_handler(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return
    global_config.bypass_geocoder = True
    if isinstance(message, types.CallbackQuery):
        message = message.message
        await message.edit_reply_markup()
    await message.answer('Геокодер отключен до перезапуска бота.\nАдреса будут вводиться вручную, без координат')

@dp.callback_query_handler(text='enable_geocoder', state='*')
@dp.message_handler(commands=['enable_geocoder'], state='*')
async def enable_geocoder_handler(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return
    global_config.bypass_geocoder = False
    if isinstance(message, types.CallbackQuery):
        message = message.message
        await message.edit_reply_markup()
    await message.answer(
        'Геокодер включен.\nАдреса будут вводиться с проверкой геокодером.\n'
        'Геокодер автомотически отключится если яндекс сообщит о том что api ключ заблокирован'
    )

@dp.message_handler(commands=['ref_stats'], state='*')
async def show_ref_stats(message: types.Message, state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return

    try:
        referrals = await models.Referral.all().order_by('-counter')
    
        if not referrals:
            await message.answer("Нет данных о переходах по ссылкам.")
            return
            
        stats_text = [
            "📊 <b>Реферальная статистика</b>",
            "",
            "🔗 <i>Формат: Ссылка - Переходы - Регистрации</i>",
            ""
        ]
        
        for ref in referrals:
            registrations = await models.User.filter(referral_param=ref.param).count()
            stats_text.append(f"🔗 {ref.param}: {ref.counter} переходов → {registrations} регистраций")
        
        total_clicks = sum(ref.counter for ref in referrals)
        total_regs = await models.User.filter(referral_param__not_isnull=True).count()
        
        stats_text.extend([
            "",
            f"<b>Итого:</b>",
            f"Всего переходов: {total_clicks}",
            f"Всего регистраций: {total_regs}",
            f"Конверсия: {round((total_regs/total_clicks)*100 if total_clicks > 0 else 0, 1)}%"
        ])
        
        await message.answer("\n".join(stats_text), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка в ref_stats: {e}", exc_info=True)
        await message.answer("Произошла ошибка при получении статистики.")

@dp.message_handler(commands=['users'], state='*')
async def users_stats_handler(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return

    all_users: int = await models.User.all().count()
    all_implementers: int = await models.Implementer.all().count()
    implementers_self_employed: int = await models.Implementer.filter(inn__not_isnull=True).count()
    implementers_passport_confirmed: int = await models.Implementer.filter(passport__not_isnull=True).count()
    implementers_fully_confirmed: int = await models.Implementer.filter(passport__not_isnull=True, inn__not_isnull=True).count()

    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='По городам', callback_data='users_cities'))



    text = (
        f'Всего пользователей: {all_users}\n'
        f'Прошли первичную регистрацию: {all_implementers}\n'
        f'Подтвердили самозанятость: {implementers_self_employed}\n'
        f'Подтвердили ПД: {implementers_passport_confirmed}\n'
        f'Подтвердили самозанятость и ПД: {implementers_fully_confirmed}\n'
    )

    await message.answer(text=text, reply_markup=mk)

@dp.callback_query_handler(text='users_cities', state='*')
async def user_cities(call: types.CallbackQuery, state: FSMContext):
    try:
        bots = await models.Bot.filter(status=True).prefetch_related("implementers")
        implementers_count_by_city = {}

        for bot in bots:
            city_name = bot.city  
            if city_name not in implementers_count_by_city:
                implementers_count_by_city[city_name] = 0

        
            implementers_count_by_city[city_name] += len(bot.implementers)
        
        response = "Количество исполнителей по городам:\n"
        for city, count in implementers_count_by_city.items():
            response += f"\n{city}: {count} исполнителей"

        await call.message.answer(response)
    except Exception as e:
        logger.error(f'Ошибка пользователи по городам: {e}')

@dp.message_handler(commands=['mail'], state='*')
async def mail_handler(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return
    await state.set_state('mail')
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='start'))
    await message.answer('Введите ваше сообщение для рассылки',reply_markup=mk)


@dp.message_handler(state='mail')
async def mail_text_handler(message: types.Message, state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return
    await state.reset_state(with_data=False)

    counter = SenderCounter()
    coros: list[list[Coroutine]] = [[]]

    users: list[User] = await User.filter(is_blocked=False).all()

    await message.answer(f'Рассылка на {len(users)} пользователей.\nОжидайте сообщения об окончании рассылки. ')

    temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')

    for i, user in enumerate(users):
        async def send(user_id: str):
            try:
                await temp_bot.send_message(
                    chat_id=user_id,
                    text=message.text,
                    disable_web_page_preview=True
                )
                print(f'sending num{counter.count}')
                counter.count += 1
            except Exception as e:
                pass
        coros[-1].append(send(str(user.telegram_id)))
        if len(coros[-1]) == 30:
            coros.append([])
            continue


    if not coros[-1]:
        coros.pop(-1)

    await sending_manager.send_main(API_TOKEN, coros)

    temp_bot_session = await temp_bot.get_session()
    await temp_bot_session.close()

    await message.answer(text=f'Рассылка завершена. \nОтправлена {counter.count} пользователям.')

@dp.message_handler(commands=['planerka'], state='*')
async def planerka_handler(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return
    await state.set_state('planerka')
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='start'))
    await message.answer('Введите ваше сообщение для рассылки', reply_markup=mk)


@dp.message_handler(state='planerka')
async def planerka_text_handler(message: types.Message, state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return
    await state.reset_state(with_data=False)

    counter = SenderCounter()
    coros: list[list[Coroutine]] = [[]]

    users: list[User] = []
    # all_users = await User.filter(is_blocked=False).all()
    all_users = await User.filter().all()
    for user in all_users:
        implementer = await Implementer.get_implementer(user)
        if implementer and implementer.employment_type == 'state':
            users.append(user)

    await message.answer(f'Рассылка planerka на {len(users)} пользователей.\nОжидайте сообщения об окончании рассылки. ')

    temp_bot = Bot(token=API_TOKEN, parse_mode='HTML')

    for i, user in enumerate(users):
        async def send(user_id: str):
            try:
                await temp_bot.send_message(
                    chat_id=user_id,
                    text=message.text,
                    disable_web_page_preview=True
                )
                print(f'sending num{counter.count}')
                counter.count += 1
            except Exception as e:
                pass
        coros[-1].append(send(str(user.telegram_id)))
        if len(coros[-1]) == 30:
            coros.append([])
            continue

    if not coros[-1]:
        coros.pop(-1)

    await sending_manager.send_main(API_TOKEN, coros)

    temp_bot_session = await temp_bot.get_session()
    await temp_bot_session.close()

    await message.answer(text=f'Рассылка завершена. \nОтправлена {counter.count} пользователям.')


@dp.callback_query_handler(text='admin', state='*')
@dp.message_handler(commands=['admin'], state='*')
async def admin_handler(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return

    await state.finish()
    msg_text = 'Админ-панель'
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.OPERATORS_BTN, callback_data='admin_operators'))
    mk.row(types.InlineKeyboardButton(text=bt.BOTS_BTN, callback_data='admin_bots'))
    mk.row(types.InlineKeyboardButton(text='Включить геокодер', callback_data='enable_geocoder'))
    mk.row(types.InlineKeyboardButton(text='Отключить геокодер',callback_data='disable_geocoder'))
    mk.row(types.InlineKeyboardButton(text='Дать иммунитет оператору',callback_data='unseal_operator_state'))
    mk.row(types.InlineKeyboardButton(text='Отменить иммунитет оператору',callback_data='seal_operator_state'))
    mk.row(types.InlineKeyboardButton(text='Установить ставку на заказы',callback_data='set_tariff'))
    if isinstance(message, types.CallbackQuery):
        message = message.message
        await message.edit_reply_markup()
    await message.answer(text=msg_text, reply_markup=mk)

@dp.callback_query_handler(Text(startswith='set_tariff'))
async def set_tariff(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer('Введите ставку (Штатный постоянного графика)')
    await state.set_state('set_tariff_regular')

@dp.message_handler(state='set_tariff_regular')
async def set_tariff_regular(message: types.Message, state: FSMContext):
    update_config('price_regular',int(message.text))
    # await message.answer(f"Ставка {get_config('price_regular')} установлена")
    await message.answer('Введите ставку (Штатный свободного графика) ')
    await state.set_state('set_tariff_state')

@dp.message_handler(state='set_tariff_state')
async def set_tariff_state(message: types.Message, state: FSMContext):
    update_config('price_state',int(message.text))
    # await message.answer(f"Ставка {get_config('price_state')} установлена")
    await message.answer('Введите ставку (Наемник)')
    await state.set_state('set_tariff_finish')

@dp.message_handler(state='set_tariff_finish')
async def set_tariff_finish(message: types.Message, state: FSMContext):
    update_config('min_cost',int(message.text))
    await message.answer(f"Ставки установлены")



@dp.message_handler(commands=['reset_state'], state='*')
async def cmd_reset_state(message: types.Message, state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
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
                   
                   state_to_reset = dp.current_state(user=current_user.id, chat=current_user.id)
                   await state_to_reset.reset_state(with_data=False)
                   await message.reply(f"Состояние пользователя {current_user.id} было сброшено.")

# @dp.message_handler(state='reset_user_state')
# @dp.callback_query_handler(Text(startswith='reset_user_state:'))
# async def reset_user_state(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
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
#     state_to_reset = dp.current_state(user=user.id, chat=user.id)
#     await state_to_reset.reset_state(with_data=False)
#     await message.reply(f"Состояние пользователя {user.id} было сброшено.")

@dp.message_handler(commands=['seal'], state='*')
async def cmd_seal_op(message: types.Message, state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return
    else:
        command_args = message.text.split(' ')
        if len(command_args) == 1:
            await message.answer(text='Для снятия иммунитета оператора введите /seal @username')
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
                    operator = await models.Operator.get_operator(current_user)
                    operator.seal_manual = False
                    await operator.save()


    await message.reply(f"Иммунитет оператора по кол-ву незавершенных заказов @{operator.user.username} снят")

@dp.callback_query_handler(Text(startswith='seal_operator_state'))
async def get_operator_self_employed_stats(call: types.CallbackQuery, state: FSMContext):
    
    await call.message.answer('''Введите @username оператора''')
    await call.message.edit_reply_markup()
    await state.set_state('seal_operator_state')

@dp.message_handler(state='seal_operator_state')
async def cmd_seal_op_finish(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    await state.finish()
    if isinstance(message, types.Message):
        username = message.text
        if username.startswith('@'):
            username = username[1:]
        user = await models.User.get_by_username(username)
        if user is None:
            await message.answer(text='Пользователь не найден')
            return
        operator = await models.Operator.get_operator(user)
        if operator is None:
            await message.answer(text='Оператор не найден')
            return
    else:
        user_id = int(message.data.split(':')[1])
        user = await models.User.get_user(user_id)
        operator = await models.Operator.get_operator(user)
    operator.seal_manual = False
    await operator.save()


    await message.reply(f"Иммунитет оператора @{operator.user.username} снят")

@dp.callback_query_handler(Text(startswith='unseal_operator_state'))
async def get_operator_self_employed_stats(call: types.CallbackQuery, state: FSMContext):
    
    await call.message.answer('''Введите @username оператора''')
    await call.message.edit_reply_markup()
    await state.set_state('unseal_operator_state')


@dp.message_handler(commands=['unseal'], state='*')
async def cmd_unseal_op(message: types.Message, state: FSMContext):
    if message.from_user.id not in dependencies.ADMINS:
        return
    else:
        command_args = message.text.split(' ')
        if len(command_args) == 1:
            await message.answer(text='Для установки иммунитета оператора введите /unseal @username')
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
                    operator = await models.Operator.get_operator(current_user)
                    operator.seal_manual = True
                    await operator.save()
                    await message.reply(f"Оператор @{operator.user.username} получил имунитет по кол-ву незавершенных заказов")

@dp.message_handler(state='unseal_operator_state')
@dp.callback_query_handler(Text(startswith='unseal_operator_state:'))
async def cmd_unseal_op_finish(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    await state.finish()
    if isinstance(message, types.Message):
        username = message.text
        if username.startswith('@'):
            username = username[1:]
        user = await models.User.get_by_username(username)
        if user is None:
            await message.answer(text='Пользователь не найден')
            return
        operator = await models.Operator.get_operator(user)
        if operator is None:
            await message.answer(text='Оператор не найден')
            return
    else:
        user_id = int(message.data.split(':')[1])
        user = await models.User.get_user(user_id)
        operator = await models.Operator.get_operator(user)
        
    operator.seal_manual = True
    await operator.save()

    await message.reply(f"Оператор @{operator.user.username} получил имунитет по кол-ву незавершенных заказов")

@dp.callback_query_handler(text='admin_operators')
async def admin_operators_handler(call: types.CallbackQuery):
    operators = await models.Operator.get_all()
    msg_text = 'Операторы'
    mk = types.InlineKeyboardMarkup()
    for operator in operators:
        mk.row(types.InlineKeyboardButton(text=f'@{operator.user.username}',
                                          callback_data=f'admin_operator:{operator.id}'))

    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin'))
    await call.message.edit_text(text=msg_text, reply_markup=mk)


@dp.callback_query_handler(Text(startswith='admin_operator:'))
async def admin_operator_handler(call: types.CallbackQuery):
    operator_id = int(call.data.split(':')[1])
    operator = await models.Operator.get_by_id(operator_id)
    if operator is None:
        return

    msg_text = f'Оператор @{operator.user.username}\n' \
               f'ID: {operator.user.telegram_id}'

    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.DELETE_OPERATOR_BTN, callback_data=f'delete_operator:{operator.id}'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_operators'))
    await call.message.edit_text(text=msg_text, reply_markup=mk)


@dp.callback_query_handler(Text(startswith='delete_operator:'))
async def delete_operator_handler(call: types.CallbackQuery):
    operator_id = int(call.data.split(':')[1])
    operator = await models.Operator.get_by_id(operator_id)
    username = operator.user.username
    if operator is None:
        return

    await operator.delete()
    await call.message.edit_text(text=f'Оператор @{username} удален')
    await admin_operators_handler(call)


@dp.callback_query_handler(text='admin_bots', state='*')
async def admin_bots_handler(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    bots = await models.Bot.get_all()
    msg_text = 'Боты'
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.ADD_BOT_BTN, callback_data='admin_add_bot'))
    for bot in bots:
        mk.row(types.InlineKeyboardButton(text=f'@{bot.username}',
                                          callback_data=f'admin_bot:{bot.id}'))

    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin'))
    await call.message.edit_text(text=msg_text, reply_markup=mk)


@dp.callback_query_handler(text='admin_add_bot', state='*')
async def admin_add_bot_handler(call: types.CallbackQuery, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
    msg_text = 'Отправьте Token бота'
    await call.message.edit_text(text=msg_text, reply_markup=mk)
    await state.set_state('admin_add_bot')


@dp.message_handler(state='admin_add_bot')
async def admin_add_bot_handler(message: types.Message, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_add_bot'))
    token = message.text
    city = await models.Bot.get_by_token(token)
    if city is not None:
        await message.answer(text='Бот с таким токеном уже существует', reply_markup=mk)
        return
    try:
        temp_bot = Bot(token=token)
    except Exception as e:
        await message.answer(text='Неверный токен. Введите еще раз', reply_markup=mk)
        return

    me = await temp_bot.get_me()
    await state.update_data(token=token, username=me.username, title=me.full_name)
    await message.answer(text=f'Напишите название города', reply_markup=mk)
    await state.set_state('admin_add_bot_city')


@dp.message_handler(state='admin_add_bot_city')
async def admin_add_bot_city_handler(message: types.Message, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    city = await search_city(message.text)
    if city is None:
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
        await message.answer(text='Город не найден. Введите еще раз', reply_markup=mk)
        return

    await state.update_data(city=city)
    mk.row(types.InlineKeyboardButton(text=bt.SKIP_BTN, callback_data='admin_skip_state'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
    await message.answer(text=f'Найден город: <b>{city}</b>\nНапишите название области, либо пропустите',
                         reply_markup=mk)
    await state.set_state('admin_add_bot_state')


@dp.callback_query_handler(text='admin_skip_state', state='*')
async def admin_finish_add_bot_handler(message: Union[types.Message, types.CallbackQuery],
                                       state: FSMContext):
    data = await state.get_data()
    token = data.get('token')
    username = data.get('username')
    title = data.get('title')
    city = data.get('city')
    city_state = data.get('state')
    await state.finish()
    create_folder(f'/root/tgbot/city_bots/{username}')
    copy_files('/root/tgbot/city_bots/template', f'/root/tgbot/city_bots/{username}')
    os.rename(f'/root/tgbot/city_bots/{username}/bot.service', f'/root/tgbot/city_bots/{username}/{username}.service')
    replace_text(f'/root/tgbot/city_bots/{username}/{username}.service', '%(dir)s', username)
    replace_text(f'/root/tgbot/city_bots/{username}/data.json', '%(token)s', token)
    copy_file(f'/root/tgbot/city_bots/{username}/{username}.service', '/etc/systemd/system')
    os.system(f'systemctl daemon-reload')
    os.system(f'systemctl enable {username}')
    os.system(f'systemctl start {username}')

    bot = await models.Bot.add_bot(
        token=token,
        username=username,
        title=title,
        city=city,
        state=city_state,
    )
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.ADD_REGION_BTN,
                                      callback_data=f'admin_add_region:{bot.id}'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
    if isinstance(message, types.CallbackQuery):
        message = message.message
        await message.edit_reply_markup()

    await message.answer(text=f'Бот @{bot.username} добавлен', reply_markup=mk)


@dp.message_handler(state='admin_add_bot_state')
async def admin_add_bot_state_handler(message: types.Message, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    city_state = await search_state(message.text)
    if city_state is None:
        mk.row(types.InlineKeyboardButton(text=bt.SKIP_BTN, callback_data='admin_skip_state'))
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
        await message.answer(text='Область не найдена. Введите еще раз', reply_markup=mk)
        return

    await state.update_data(state=city_state)
    await message.answer(text=f'Найдена область: <b>{city_state}</b>')
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
    await admin_finish_add_bot_handler(message, state)


@dp.callback_query_handler(Text(startswith='admin_add_region:'))
async def admin_add_region_handler(call: types.CallbackQuery, state: FSMContext):
    bot_id = call.data.split(':')[1]
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
    await call.message.edit_text(text='Напишите название региона', reply_markup=mk)
    await state.update_data(bot_id=bot_id)
    await state.set_state('admin_add_region')


@dp.message_handler(state='admin_add_region')
async def admin_add_region_handler(message: types.Message, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    region = await search_city(message.text)
    if region is None:
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
        await message.answer(text='Регион не найден. Введите еще раз', reply_markup=mk)
        return

    data = await state.get_data()
    bot_id = int(data.get('bot_id'))
    bot = await models.Bot.get_by_id(bot_id)
    town = await models.Town.add_town(bot=bot, name=region)
    mk.row(types.InlineKeyboardButton(text='К боту', callback_data=f'admin_bot:{bot_id}'))
    await message.answer(text=f'Регион <b>{town.name}</b> добавлен', reply_markup=mk)
    await state.finish()


@dp.callback_query_handler(Text(startswith='admin_bot:'))
async def admin_bot_handler(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    if isinstance(message, types.CallbackQuery):
        bot_id = int(message.data.split(':')[1])
    else:
        data = await state.get_data()
        bot_id = int(data.get('bot_id'))

    bot = await models.Bot.get_by_id(bot_id)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.ADD_REGION_BTN,
                                      callback_data=f'admin_add_region:{bot_id}'))
    mk.row(types.InlineKeyboardButton(text='Изменить название города', callback_data=f'change_city_name:{bot.id}'))
    mk.row(types.InlineKeyboardButton(text='Изменить название области', callback_data=f'change_state_name:{bot.id}'))
    for town in bot.towns:
        mk.row(types.InlineKeyboardButton(text=town.name, callback_data=f'town_info:{town.id}'))
    mk.row(types.InlineKeyboardButton(text=bt.DELETE_BOT_BTN,
                                      callback_data=f'admin_delete_bot:{bot_id}'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
    msg_text = f'Бот @{bot.username}\n'
    msg_text += f'Город: <b>{bot.city}</b>\n'
    if bot.state:
        msg_text += f'Область: <b>{bot.state}</b>\n'
    for region in bot.towns:
        msg_text += f'Регион: <b>{region.name}</b>\n'

    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text=msg_text, reply_markup=mk)
    else:
        await message.answer(text=msg_text, reply_markup=mk)


@dp.callback_query_handler(Text(startswith='admin_delete_bot:'))
async def admin_delete_bot_handler(call: types.CallbackQuery, state: FSMContext):
    bot_id = int(call.data.split(':')[1])
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.CONFIRM_BTN, callback_data=f'admin_confirm_delete_bot:{bot_id}'))
    mk.row(types.InlineKeyboardButton(text=bt.DECLINE_BTN, callback_data=f'admin_bot:{bot_id}'))
    await call.message.edit_text(text='Вы уверены, что хотите удалить бота?', reply_markup=mk)


@dp.callback_query_handler(Text(startswith='admin_confirm_delete_bot:'))
async def admin_confirm_delete_bot_handler(call: types.CallbackQuery, state: FSMContext):
    bot_id = int(call.data.split(':')[1])
    bot = await models.Bot.get_by_id(bot_id)
    bot.status = False
    await bot.save()
    os.system(f'systemctl disable {bot.username}')
    os.system(f'systemctl stop {bot.username}')
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
    await call.message.edit_text(text=f'Бот @{bot.username} удален', reply_markup=mk)


@dp.callback_query_handler(Text(startswith='change_city_name:'))
async def change_city_name_handler(call: types.CallbackQuery, state: FSMContext):
    bot_id = int(call.data.split(':')[1])
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data=f'admin_bot:{bot_id}'))
    await call.message.edit_text(text='Введите новое название города', reply_markup=mk)
    await state.update_data(bot_id=bot_id)
    await state.set_state('change_city_name')


@dp.message_handler(state='change_city_name')
async def change_city_name_handler(message: types.Message, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    city = await search_city(message.text)
    if city is None:
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
        await message.answer(text='Город не найден. Введите еще раз', reply_markup=mk)
        return

    bot_id = int((await state.get_data()).get('bot_id'))
    bot = await models.Bot.get_by_id(bot_id)
    bot.city = city
    await bot.save()
    await message.answer(text='Название города изменено', reply_markup=mk)
    await state.reset_state(with_data=False)
    await admin_bot_handler(message, state)


@dp.callback_query_handler(Text(startswith='change_state_name:'))
async def change_state_name_handler(call: types.CallbackQuery, state: FSMContext):
    bot_id = int(call.data.split(':')[1])
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data=f'admin_bot:{bot_id}'))
    await call.message.edit_text(text='Введите новое название области', reply_markup=mk)
    await state.update_data(bot_id=bot_id)
    await state.set_state('change_state_name')


@dp.message_handler(state='change_state_name')
async def change_state_name_handler(message: types.Message, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    state_name = await search_state(message.text)
    if state_name is None:
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin_bots'))
        await message.answer(text='Область не найдена. Введите еще раз', reply_markup=mk)
        return
    data = await state.get_data()
    bot_id = int(data.get('bot_id'))
    bot = await models.Bot.get_by_id(bot_id)
    bot.state = state_name
    await bot.save()
    await message.answer(text='Название области изменено', reply_markup=mk)
    await state.reset_state(with_data=False)
    await admin_bot_handler(message, state)


@dp.callback_query_handler(Text(startswith='town_info:'))
async def town_info_handler(message: Union[types.CallbackQuery, types.Message], state: FSMContext):
    await state.reset_state(with_data=False)
    if isinstance(message, types.CallbackQuery):
        town_id = int(message.data.split(':')[1])
        await state.update_data(town_id=town_id)
    else:
        data = await state.get_data()
        town_id = int(data.get('town_id'))

    town = await models.Town.get_by_id(town_id)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text='Удалить регион',
                                      callback_data=f'delete_town:{town.id}'))
    mk.row(types.InlineKeyboardButton(text='Изменить имя',
                                      callback_data=f'change_town_name:{town.id}'))
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN,
                                      callback_data=f'admin_bot:{town.bot.id}'))
    msg_text = f'Регион <b>{town.name}</b>\n\n' \
               f'<i>Для изменения информации о регионе используйте кнопки ниже</i>'

    if isinstance(message, types.CallbackQuery):
        await message.message.edit_text(text=msg_text, reply_markup=mk)
    else:
        await message.answer(text=msg_text, reply_markup=mk)


@dp.callback_query_handler(Text(startswith='change_town_name:'), state='*')
async def change_town_name(call: types.CallbackQuery, state: FSMContext):
    town_id = int(call.data.split(':')[1])
    town = await models.Town.get_by_id(town_id)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN,
                                      callback_data=f'town_info:{town_id}'))
    await state.update_data(town_id=town_id)
    await call.message.edit_text(text=f'Введите новое название региона.\n'
                                      f'Текущее название: <b>{town.name}</b>')
    await state.set_state('change_town_name')


@dp.message_handler(state='change_town_name')
async def change_town_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    region = await search_city(message.text)
    town_id = int(data.get('town_id'))
    town = await models.Town.get_by_id(town_id)

    mk = types.InlineKeyboardMarkup()
    if region is None:
        mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN,
                                          callback_data=f'town_info:{town_id}'))

    town.name = region
    await town.save()
    await message.answer(text="Название региона изменено")
    await town_info_handler(message, state)


@dp.callback_query_handler(Text(startswith='delete_town:'), state='*')
async def delete_town_handler(call: types.CallbackQuery, state: FSMContext):
    town_id = int(call.data.split(':')[1])
    town = await models.Town.get_by_id(town_id)
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.CONFIRM_BTN,
                                      callback_data=f'confirm_delete_town:{town_id}'))
    mk.row(types.InlineKeyboardButton(text=bt.DECLINE_BTN,
                                      callback_data=f'town_info:{town_id}'))
    await call.message.edit_text(
        text=f'Вы уверены, что хотите удалить регион <b>{town.name}</b>?',
        reply_markup=mk
    )


@dp.callback_query_handler(Text(startswith='confirm_delete_town:'), state='*')
async def confirm_delete_town_handler(call: types.CallbackQuery, state: FSMContext):
    town_id = int(call.data.split(':')[1])
    town = await models.Town.get_by_id(town_id)
    town_name = town.name
    await town.delete()
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.BACK_BTN, callback_data='admin'))
    await call.message.edit_text(text=f'Регион {town_name} удален',
                                 reply_markup=mk)


@dp.callback_query_handler(Text(startswith='confirm_moderation:'), state='*')
async def confirm_moderation(call: types.CallbackQuery):
    implementer_id, series, number, city_dir = call.data.split(':')[1:]
    implementer = await models.Implementer.get_by_id(int(implementer_id))
    implementer.passport = f'{series} {number}'
    await implementer.save()
    await call.message.edit_caption(caption=call.message.html_text + '\n\n<b>Подтверждено</b>')

    if not implementer.inn:
        text = ('Ваши паспортные данные подтверждены, ваш приоритет на получение заказов повышен.\n'
                'А теперь подтвердите самозанятость, чтобы получать еще больше заказов')
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton(text='Подтвердить самозанятость', callback_data='implementer_self_employed'))

    else:
        text = 'Ваши паспортные данные подтверждены, ваш приоритет на получение заказов повышен.'
        mk = None

    with open(os.path.join('city_bots', city_dir, 'data.json'), 'r') as file:
        data = json.load(file)
        city_token = data['token']
        city_bot = Bot(token=city_token, parse_mode='HTML')
        await city_bot.send_message(chat_id=implementer.user.telegram_id,
                                    text=text, reply_markup=mk)
    try:
        fio = implementer.full_name.split(' ')
        data = {
            'first_name': fio[1],
            'surname': fio[0],
            'middle_name': fio[2],
            'phone': implementer.phone_number,
            'branch_id': 1,
            'birthday': implementer.date_birth.strftime("%Y-%m-%d"),
            'series': series,
            'number': number,
            'employment_type': 'contract',
            'employment_date': datetime.now().strftime("%Y-%m-%d"),
            "fact_address": "г. Москва, ул. Примерная, д. 1",
    }
        response = requests.post(CRM_URL+'loader', json=data, headers=HEADERS)
        logger.info(f'Ответ сервера {response}')
    except Exception as e:
        logger.error(f'Ошибка создания рабочего {e}')

@dp.callback_query_handler(Text(startswith='cancel_moderation:'), state='*')
async def cancel_moderation(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split(':')[1])
    await call.message.edit_reply_markup()
    mk = types.InlineKeyboardMarkup()
    await call.message.answer('Напишите причину отказа', reply_markup=mk)
    await state.set_state('cancel_moderation_message')
    await state.update_data({'user_id': user_id})
    

@dp.message_handler(state='cancel_moderation_message')
async def cancel_moderation_message(message: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        user_id = user_data.get('user_id')
        logger.info(f'cancel user data: {user_data}')
        user = await models.User.get_user(user_id)
        msg_text = 'Ваши данные не были подтверждены. Причина отказа:\n'
        msg_text += message.text
        await bot.send_message(
            chat_id=MODERATOR_ID,
            text=f'Данные пользователя @{user.username} не подтверждены.\nПричина: {message.text}',
        )
        await bot.send_message(
            text=msg_text,
            chat_id=user_id
        )
        await state.finish()
    except Exception as e:
        logger.info(f'Ошибка {e} cancel_moderation_message')

@dp.callback_query_handler(Text(startswith='approve_del:'),  state='*')
async def approve_deletion(call: types.CallbackQuery, state: FSMContext):
    old_implementer_id = int(call.data.split(':')[1])
    user_id = int(call.data.split(':')[2])
    old_implementer = await models.Implementer.get_by_id(old_implementer_id)
    if old_implementer:
        await old_implementer.delete()
        await call.message.edit_text(call.message.text + '\nСтарый профиль удален')
        await bot.send_message(chat_id=user_id,text='Ваш запрос на удаление старого профиля одобрен✅')
        await call.message.edit_reply_markup()
    else:
        await call.message.edit_text(call.message.text + '\nСтарый профиль не найден')

@dp.callback_query_handler(Text(startswith='cancel_del:'),  state='*')
async def cancel_deletion(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split(':')[1])
    await bot.send_message(chat_id=user_id,text='Ваш запрос на удаление старого профиля отклонен❌')
    await call.message.edit_text(call.message.text + '\n Стаый профиль не удален ')
    await call.message.edit_reply_markup()

def create_folder(destination_folder):
    # Создание папки
    os.makedirs(destination_folder, exist_ok=True)

def copy_files(source_folder, destination_folder):
    # Копирование файлов из исходной папки в папку назначения
    files = os.listdir(source_folder)
    for file_name in files:
        source_path = os.path.join(source_folder, file_name)
        destination_path = os.path.join(destination_folder, file_name)
        shutil.copy2(source_path, destination_path)


def copy_file(source_file, destination_folder):
    # Копирование файла в папку назначения
    shutil.copy2(source_file, destination_folder)


def replace_text(file_path, old_text, new_text):
    # Замена текста в файле
    with open(file_path, 'r') as file:
        file_data = file.read()
        file_data = file_data.replace(old_text, new_text)

    with open(file_path, 'w') as file:
        file.write(file_data)
