from aiogram import types
from app.dependencies import ADMINS


async def notify_wakeup_bot(dp):
    try:
        await dp.bot.send_message(chat_id=ADMINS[2], text='Успешный запуск бота!')
        await dp.bot.send_message(chat_id=ADMINS[0], text='Успешный запуск бота!')
    except:
        pass