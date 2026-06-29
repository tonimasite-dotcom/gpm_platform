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
from app.dependencies import dp, RAISING_ID
from app.services import bot_texts as bt
from app.services.city_location import search_address, ForbiddenError
from app.services.keyboard import requests_cd
from app.services.states import OperatorState
from app.services.ya_disk import delete_file, upload_file
from app.services.sending_manager import SenderCounter, sending_manager


@dp.callback_query_handler(text='raising_take', state='*')
async def rasing_take(call: types.CallbackQuery, state: FSMContext):
    user = await models.User.get_user(call.from_user.id)
    if user is None:
        call.message.answer('Пользователь не найден')
    msg_text = call.message.text
    msg_text += f'\nВзято в работу \nРекрутер: @{user.username}'
    await call.message.edit_text(text=msg_text)

@dp.message_handler(commands=['employ'], state='*')
async def confirm_employment(message: types.Message, state: FSMContext):
    command_args = message.text.split(' ')
    user = await models.User.get_user(message.from_user.id)
    operator = await models.Operator.get_operator(user)
    if operator is None and message.chat.id != RAISING_ID:
        return

    if len(command_args) == 1:
        await message.answer(text='Для перевода пользователя в штат введите /employ @username')
        return
    elif len(command_args) > 2:
        await message.answer(text='Неверный формат команды')
        return
    else:
        current_user = await models.User.get_or_none(username=command_args[1].replace('@', ''))
        if current_user is None:
            await message.answer(text='Пользователь не найден.')
            return
        implementer = await models.Implementer.get_implementer(current_user)
        if implementer is None:
            await message.answer(text='Исполнитель не найден.')
            return
    
        implementer.employment_type='state'
        await implementer.save()
        await message.answer(f'Пользователь @{current_user.username} был переведен в штат')

@dp.message_handler(commands=['unemploy'], state='*')
async def confirm_unemployment(message: types.Message, state: FSMContext):
    command_args = message.text.split(' ')
    user = await models.User.get_user(message.from_user.id)
    operator = await models.Operator.get_operator(user)
    if operator is None and message.chat.id != RAISING_ID:
        return

    if len(command_args) == 1:
        await message.answer(text='Для перевода пользователя в подрячики введите /unemploy @username')
        return
    elif len(command_args) > 2:
        await message.answer(text='Неверный формат команды')
        return
    else:
        current_user = await models.User.get_or_none(username=command_args[1].replace('@', ''))
        if current_user is None:
            await message.answer(text='Пользователь не найден.')
            return
        implementer = await models.Implementer.get_implementer(current_user)
        if implementer is None:
            await message.answer(text='Исполнитель не найден.')
            return
    
        implementer.employment_type='contract'
        await implementer.save()
        await message.answer(f'Пользователь @{current_user.username} был переведен в подрядчики')