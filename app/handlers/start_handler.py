from typing import Union
from aiogram import types
from aiogram.dispatcher import FSMContext

from app.db import models
from app.dependencies import dp
from app.services import bot_texts as bt
from app.services.states import RegisterState
from app.dependencies import MODERATOR_ID, TICKETS_ID, SUPPORT_ID, REQUESTS_ID


async def operator_menu(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.ADD_REQUEST_BTN, callback_data='add_request'))
    mk.row(types.InlineKeyboardButton(text=bt.MY_REQUESTS_BTN, callback_data='my_requests'))
    if isinstance(message, types.CallbackQuery):
        message = message.message
        await message.edit_reply_markup()
    await message.answer(text=bt.OPERATOR_MENU_MSG, reply_markup=mk)


async def user_menu(message: types.Message, state: FSMContext):
    await state.finish()
    if isinstance(message, types.CallbackQuery):
        message = message.message
        await message.edit_reply_markup()
    await message.answer(text=bt.REGISTER_ALREADY_MSG)


async def register_user(message: types.Message, state: FSMContext):
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)
    mk.add(types.KeyboardButton(bt.SHARE_CONTACT_BTN, request_contact=True))
    if isinstance(message, types.CallbackQuery):
        message = message.message
        await message.edit_reply_markup()
    await message.answer(bt.SHARE_CONTACT_MSG, reply_markup=mk)
    await RegisterState.first()


@dp.callback_query_handler(text='start', state='*')
@dp.message_handler(commands=['start'], state='*', chat_type=types.ChatType.PRIVATE)
async def start(message: Union[types.Message, types.CallbackQuery], state: FSMContext):
    await state.finish()
    user = await models.User.get_user(message.from_user.id)
    if isinstance(message, types.CallbackQuery):
        message = message.message
    if message.chat.id == MODERATOR_ID or message.chat.id == TICKETS_ID or message.chat.id == SUPPORT_ID or message.chat.id == REQUESTS_ID:
        return
    if user is None:
        user = await models.User.add_user(message.from_user)

    operator = await models.Operator.get_operator(user=user)
    if operator:
        await operator_menu(message, state)
        return

    implementer = await models.Implementer.get_implementer(user=user)
    if implementer:
        await user_menu(message, state)

    else:
        await register_user(message, state)


@dp.message_handler(commands=['id'], state='*')
async def get_id(message: types.Message, state: FSMContext):
    await message.answer(text=f'Ваш ID: <code>{message.chat.id}</code>')


@dp.message_handler(commands=['reset'], state='*')
async def reset_implementer_handler(message: types.Message, state: FSMContext):
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(text=bt.CONFIRM_BTN, callback_data='reset_implementer_confirm'))
    await message.answer(text='Вы уверены, что хотите удалить свой профиль?', reply_markup=mk)


@dp.callback_query_handler(text='reset_implementer_confirm', state='*')
async def reset_implementer_confirm_handler(call: types.CallbackQuery, state: FSMContext):
    user = await models.User.get_user(call.from_user.id)
    if user is None:
        await call.message.answer(text='Вы не зарегистрированы. Введите /start для регистрации.')
        return
    implementer = await models.Implementer.get_implementer(user)
    if implementer is None:
        await call.message.answer(text='Вы не зарегистрированы. Введите /start для регистрации.')
        return

    await implementer.fetch_related('requests', 'towns', 'bots')
    await implementer.requests.clear()
    await implementer.towns.clear()
    await implementer.bots.clear()
    await implementer.delete()
    await call.message.answer(text='Ваш профиль удален. Введите /start для повторной регистрации.')
